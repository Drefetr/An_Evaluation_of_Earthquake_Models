"""Explicit replay of saved optimizer returns through the unchanged fit function.

The consolidated scientific trace is logical, not a claim of fresh optimization.
The append-only call ledger and immutable failed trace identify physical work.
"""
from __future__ import annotations
import copy
import json
import math
import os
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import numpy as np
from scipy.optimize import OptimizeResult, minimize
from experiments.s04b_joint_nuisance import fit, checkpoint

SUPPORT_EQUIVALENCE_POLICY = {'schema': 'joint_original_contract_recovery_v2',
 'score_absolute_tolerance': 1e-09,
 'score_fields': ['P', 'E', 'C', 'M', 'joint', 'nll'],
 'score_identities': ['C=-E', 'joint=P-E+M', 'nll=-joint'],
 'unused_gradient_policy': 'Cross-run differences descriptive; finite gradients and correct '
                           'projections required; no added epsilon or bitwise eligibility gate',
 'completed_return_support': {'model': 'LIplus_immigrant',
                              'starts': [0, 1, 2, 3, 4],
                              'one_shot_token': True,
                              'exact_model_start_parameters': True,
                              'order': 8,
                              'require_gradient': True,
                              'actual_support_recorded_before_reuse': True,
                              'original_returned_nll_freshness_required': True,
                              'canonical_saved_score_and_gradient_before_candidate_construction': True,
                              'forbidden_in_actual_optimizer_or_new_start': True},
 'reused_selected_checks': {'models': ['null', 'LI'],
                            'capture_existing_raw_coarse_fine_evaluations': True,
                            'independently_rederive_original_scientific_criteria': True,
                            'actual_and_original_must_pass': True,
                            'return_original_saved_check_after_validation': True,
                            'original_fine_raw_gradient_not_archived': True},
 'historical_floor': {'retain_fresh_actual_nll_and_discrepancy': True,
                      'original_absolute_tolerance': 1e-09,
                      'identifiers_expected_values_exact': True},
 'powell_reference_snapshots': {'observational_only': True,
                                'record_if_naturally_reached': True,
                                'not_reached_allowed': True,
                                'no_forced_evaluations': True,
                                'initial_bounds_options_caps_unchanged': True},
 'scope': 'Operational recovery of completed work under the original scientific acceptance '
          'criteria; no hardware or bitwise-trajectory guarantee'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def same(a, b):
    return checkpoint.dumps(a, sort_keys=True, separators=(',', ':')) == checkpoint.dumps(b, sort_keys=True, separators=(',', ':'))


def check_comparison(actual, expected):
    """Retain exact mismatches, including signed zero; this applies no tolerance."""
    a, b = [json.loads(checkpoint.dumps(v)) for v in (actual, expected)]
    differences = []
    def visit(left, right, path):
        if same(left, right):
            return
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                child = path+'/'+str(key).replace('~','~0').replace('/','~1')
                if key not in left or key not in right:
                    differences.append(dict(path=child,kind='missing_key',actual_present=key in left,
                        expected_present=key in right,actual=left.get(key),expected=right.get(key)))
                else:visit(left[key],right[key],child)
        elif isinstance(left,list) and isinstance(right,list) and len(left)==len(right):
            for i,(x,y) in enumerate(zip(left,right)):visit(x,y,path+'/'+str(i))
        else:
            row=dict(path=path,kind='value',actual=left,expected=right)
            if isinstance(left,(int,float)) and not isinstance(left,bool) and isinstance(right,(int,float)) and not isinstance(right,bool):
                delta=left-right
                row.update(delta=delta if math.isfinite(delta) else None,absolute_delta=abs(delta) if math.isfinite(delta) else None)
            differences.append(row)
    visit(a,b,'')
    return dict(actual=a,expected=b,exact_match=same(a,b),differences=differences)


def finite_vector(value, length):
    return isinstance(value,list) and len(value)==length and all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in value)


def score_comparison(actual, expected, tolerance=1e-9):
    fields=('P','E','C','M','joint','nll')
    result=dict(passed=False,tolerance=tolerance,components=[],identities={})
    for label,row in [('actual',actual),('expected',expected)]:
        if not isinstance(row,dict) or set(row)!=set(fields) or not finite_vector([row[k] for k in fields],6):
            result['reason']='Invalid score tuple';return result
        identity=dict(signed_exposure=row['C']==-row['E'],joint=row['joint']==row['P']-row['E']+row['M'],
            negative_joint=row['nll']==-row['joint'],model_exposure=row['E']>=-1e-9)
        result['identities'][label]=identity
        if not all(identity.values()):result['reason']='Score identity or original exposure bound';return result
    for key in fields:
        delta=actual[key]-expected[key]
        result['components'].append(dict(field=key,actual=actual[key],expected=expected[key],delta=delta,absolute_delta=abs(delta),passed=abs(delta)<=tolerance))
    result['passed']=all(r['passed'] for r in result['components'])
    return result


def selected_check_criteria(check, protocol, model, raw=None):
    box=fit.bounds(protocol,model);dims=len(box)
    result=dict(passed=False,raw_gradient_available=raw is not None)
    if not finite_vector(check.get('parameters'),8):return result
    coarse=check.get('projected_gradient_coarse');fine=check.get('projected_gradient_fine')
    if not finite_vector(coarse,dims) or not finite_vector(fine,dims):return result
    if not score_comparison(check.get('coarse'),check.get('coarse'))['passed'] or not score_comparison(check.get('fine'),check.get('fine'))['passed']:return result
    if raw is not None:
        if len(raw)!=2:return result
        for order,key,row in zip((8,16),('coarse','fine'),raw):
            if row['model']!=model or row['order']!=order or not same(row['parameters'],check['parameters']) or not same(row['score'],check[key]) or not finite_vector(row['gradient'],8):return result
            projected=fit.projected_gradient(row['parameters'][:dims],row['gradient'][:dims],box).tolist()
            if not same(projected,check['projected_gradient_'+key]):return result
        result['fresh_projections_exact']=True
    pg=np.asarray(coarse);pf=np.asarray(fine)
    delta=abs(check['coarse']['joint']-check['fine']['joint'])
    scaled=float(np.max(np.abs(pg-pf)/np.maximum(1.,np.maximum(np.abs(pg),np.abs(pf))),initial=0))
    norm=float(np.max(np.abs(pf),initial=0))
    arithmetic=same(delta,check.get('absolute_joint_delta')) and same(scaled,check.get('projected_gradient_scaled_delta')) and same(norm,check.get('projected_kkt_infinity_norm'))
    scientific=delta<=protocol['quadrature']['joint_absolute_tolerance'] and scaled<=protocol['quadrature']['selected_training_gradient_scaled_tolerance'] and check['fine']['E']>=0
    null_functional=model!='null' or delta<=1e-9
    result.update(passed=arithmetic and scientific and null_functional and check.get('passed') is True,
        derived_fields_exact=arithmetic,absolute_joint_delta=delta,projected_gradient_scaled_delta=scaled,
        projected_kkt_infinity_norm=norm,original_scientific_pass=scientific,null_functional_pass=null_functional)
    return result


def floor_rows_comparison(actual, expected):
    result=dict(passed=False,actual=copy.deepcopy(actual),expected=copy.deepcopy(expected),rows=[])
    if len(actual)!=len(expected):return result
    for a,b in zip(actual,expected):
        metadata=same({k:v for k,v in a.items() if k not in ('actual_nll','absolute_delta')},{k:v for k,v in b.items() if k not in ('actual_nll','absolute_delta')})
        valid=metadata and a.get('tolerance')==1e-9
        for row in (a,b):
            valid=valid and math.isfinite(row['actual_nll']) and row['absolute_delta']==abs(row['actual_nll']-row['expected_nll']) and row['absolute_delta']<=1e-9
        cross_delta=a['actual_nll']-b['actual_nll']
        result['rows'].append(dict(passed=bool(valid and abs(cross_delta)<=1e-9),actual_nll_difference=cross_delta))
    result['passed']=all(r['passed'] for r in result['rows'])
    return result


def bare(record):
    return {k: copy.deepcopy(v) for k, v in record.items() if k not in ('event', 'model')}


class CountedPhase:
    """Retain actual evaluations; explicitly reuse completed-return support only."""
    def __init__(self, phase, recorder, phase_name):
        self._phase, self._recorder, self._name = phase, recorder, phase_name

    def __getattr__(self, name):
        return getattr(self._phase, name)

    def evaluate(self, theta, model='null', order=8, require_gradient=True):
        owner = self._recorder
        key = '|'.join(map(str, (self._name, model, order, owner.context, require_gradient)))
        owner.evaluations[key]['attempted'] += 1
        try:
            score, gradient = self._phase.evaluate(theta, model, order, require_gradient=require_gradient)
        except BaseException:
            owner.evaluations[key]['errors'] += 1
            raise
        owner.evaluations[key]['returned'] += 1
        owner.last_evaluation = dict(parameters=np.asarray(theta, dtype=float).tolist(), score=copy.deepcopy(score),
            gradient=np.asarray(gradient).tolist() if np.isfinite(gradient).all() else None)
        owner.capture_selected_evaluation(model,order,owner.last_evaluation)
        return owner.consume_pending_support(model,order,require_gradient,owner.last_evaluation,score,gradient)


class RecoveryAdapter:
    def __init__(self, partial, trace, science, policy, ledger_path, optimizer=minimize):
        from collections import defaultdict
        self.partial, self.trace, self.science, self.policy = partial, trace, science, policy
        require(same(policy.get('support_equivalence'),SUPPORT_EQUIVALENCE_POLICY), 'Unreviewed support-equivalence policy')
        self.ledger_path, self.real_optimizer = Path(ledger_path), optimizer
        require(not self.ledger_path.exists(), 'Recovery call ledger must be fresh')
        self.context = 'support_check'
        self.evaluations = defaultdict(Counter)
        self.last_evaluation = None
        self.repeated_training_checks = {}
        self.replayed_start_support = {}
        self.replayed_candidates = {}
        self.arm_calls, self.optimizer_calls = [], []
        self.reference_snapshots={'return':{'observed':False},'next_input':{'observed':False}}
        self.pending_return=None;self.active_physical_optimizer=False
        self.selected_check_name=None;self.selected_check_evaluations={};self.historical_floor_replay=None
        self.current = None
        self._validate_partial()
        self.ends = {(r['model'], r['start_index'], r['method']): bare(r) for r in trace if r['event'] == 'attempt_end'}
        self.original_error = self.ends[(policy['model'], policy['replayed_primary_error_start'], 'L-BFGS-B')]
        self.interrupted = self.ends[(policy['model'], policy['replayed_primary_error_start'], 'Powell')]
        self.log('lineage', original_failed_physical_attempts=len(self.ends), interrupted=self.interrupted,
            scope='Original interrupted invocation is not a successful logical return or an internal-state resume')

    def record_training_check(self, name, actual, expected):
        checked = check_comparison(actual, expected)
        checked['score_comparisons']={key:score_comparison(actual[key],expected[key]) for key in ('coarse','fine')}
        checked['actual_criteria']=selected_check_criteria(actual,self.science,name,self.selected_check_evaluations.get(name,[]))
        checked['expected_criteria']=selected_check_criteria(expected,self.science,name)
        metadata=set(actual)==set(expected) and same(actual['parameters'],expected['parameters']) and actual['selection']==expected['selection']
        passed=metadata and checked['actual_criteria']['passed'] and checked['expected_criteria']['passed'] and all(v['passed'] for v in checked['score_comparisons'].values())
        checked['passed']=passed
        checked['accepted_check_source']='original_saved_check' if passed else None
        self.repeated_training_checks[name] = checked
        self.log('repeated_training_check', model=name, **checked)
        return checked

    def capture_selected_evaluation(self, model, order, evaluation):
        if self.selected_check_name is None:return
        require(self.pending_return is None and not self.active_physical_optimizer,'Selected support inside optimizer or pending return')
        rows=self.selected_check_evaluations.setdefault(self.selected_check_name,[])
        require(model==self.selected_check_name and len(rows)<2 and order==(8,16)[len(rows)],'Selected support roster differs')
        row=dict(model=model,order=order,**copy.deepcopy(evaluation));rows.append(row)
        self.log('selected_support_evaluation',check_name=model,**row)

    def consume_pending_support(self, model, order, require_gradient, evaluation, score, gradient):
        if self.pending_return is None:return score,gradient
        token=self.pending_return;self.pending_return=None
        require(not self.active_physical_optimizer and self.context=='eligible_floor_or_fresh_return_support'
            and self.current['model']==model==token['model'] and self.current['start_index']==token['start_index']
            and self.current['method']=='L-BFGS-B' and order==8 and require_gradient is True
            and same(evaluation['parameters'],token['parameters']), 'Pending support token used outside exact completed-return boundary')
        original=self.ends[(model,token['start_index'],'L-BFGS-B')];box=fit.bounds(self.science,model)
        actual=copy.deepcopy(evaluation)
        actual['projected_gradient']=(fit.projected_gradient(actual['parameters'],actual['gradient'],box).tolist()
            if finite_vector(actual['gradient'],8) else None)
        expected=dict(parameters=original['parameters'],score=original['fresh_score'],gradient=original['gradient'],projected_gradient=original['projected_gradient'])
        compared=score_comparison(actual['score'],expected['score'])
        freshness=abs(actual['score']['nll']-original['returned_nll'])
        finite=finite_vector(actual['gradient'],8) and finite_vector(expected['gradient'],8)
        saved_projection=finite and same(fit.projected_gradient(expected['parameters'],expected['gradient'],box).tolist(),expected['projected_gradient'])
        passed=compared['passed'] and freshness<=1e-9 and finite and saved_projection
        row=dict(token=copy.deepcopy(token),actual_evaluation=actual,expected_evaluation=expected,score_comparison=compared,
            gradient_differences=check_comparison(actual['gradient'],expected['gradient']),actual_returned_nll_delta=freshness,
            finite_gradients=finite,saved_projection_exact=bool(saved_projection),consumed_once=True,physical_optimizer_active=False,
            passed=bool(passed),canonical_return=dict(score=copy.deepcopy(expected['score']),gradient=copy.deepcopy(expected['gradient'])) if passed else None,
            accepted_source='original_completed_return' if passed else None)
        self.replayed_start_support[str(token['start_index'])]=row
        self.log('completed_return_support',**row)
        require(passed,'Completed-return support fails original scientific freshness contract')
        self.log('token_consumed',token=copy.deepcopy(token),canonical_return=row['canonical_return'],before_candidate_construction=True)
        return copy.deepcopy(expected['score']),np.asarray(expected['gradient'],dtype=float).copy()

    def _validate_partial(self):
        r, p = self.partial, self.policy
        require(r['passed'] is False and r['outcomes'] == [] and not r.get('training_selections_frozen', False), 'Not the uncompleted training checkpoint')
        require(set(r['fits']) == set(p['reused_complete_arms']) == {'null', 'LI'}, 'Wrong complete arms')
        expected = [(m, i, 'L-BFGS-B') for m in ('null', 'LI') for i in range(8)]
        expected += [(p['model'], i, 'L-BFGS-B') for i in p['replayed_successful_starts']]
        expected += [(p['model'], p['replayed_primary_error_start'], m) for m in ('L-BFGS-B', 'Powell')]
        require(len(self.trace) == 2 * len(expected), 'Missing or extra original trace record')
        for pair, key in enumerate(expected):
            start, end = self.trace[2*pair:2*pair+2]
            require(start['event'] == 'attempt_start' and end['event'] == 'attempt_end', 'Original trace order changed')
            require((start['model'], start['start_index'], start['method']) == key == (end['model'], end['start_index'], end['method']), 'Original trace identity changed')
            require(same(start['initial_parameters'], end['initial_parameters']), 'Original initial point changed')
        for name in p['reused_complete_arms']:
            arm = r['fits'][name]
            require(arm['passed'] is True and arm['resolved_starts'] == [True]*8 and r['training_checks'][name]['passed'] is True, 'Unresolved reused fit/check')
            ends = [bare(v) for v in self.trace if v['event'] == 'attempt_end' and v['model'] == name]
            require(same(ends, arm['records']) and all(v['success'] for v in ends), 'Reused fit and trace differ')
        ends = [bare(v) for v in self.trace if v['event'] == 'attempt_end' and v['model'] == p['model']]
        require(all(v['success'] for v in ends[:-2]), 'A supposedly completed start failed')
        require(ends[-2]['error_type'] == 'ArithmeticError' and ends[-2]['error'] == 'Finite objective has unrepresentable gradient', 'Unexpected primary error')
        require(ends[-1]['error_type'] == 'TimeoutError' and ends[-1]['error'] == 'Joint experiment deadline', 'Unexpected interrupted invocation')
        require(ends[-1]['last_evaluation']['evaluation_count'] == p['anchor_completed_returns'], 'Wrong restart anchor count')
        require(same(ends[-1]['initial_parameters'], ends[-2]['initial_parameters']), 'Rescue did not use original initial point')

    def log(self, event, **details):
        with self.ledger_path.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(checkpoint.dumps(dict(event=event, **details))+'\n')
            stream.flush()
            os.fsync(stream.fileno())

    @contextmanager
    def operation(self, context):
        previous = self.context
        self.context = context
        try:
            yield
        finally:
            self.context = previous

    def fit_arm(self, phase, model, protocol, eligible, callback):
        require(same(protocol, self.science), 'Scientific protocol changed in fit delegation')
        expected = ['null', 'LI', self.policy['model'], 'LIplus_inclusive']
        require(self.arm_calls == expected[:len(self.arm_calls)] and model == expected[len(self.arm_calls)], 'Repeated or reordered arm')
        self.arm_calls.append(model)
        if model in self.policy['reused_complete_arms']:
            saved = self.partial['fits'][model]
            require(same(eligible, saved['candidates'][0]['parameters']), 'Reused arm eligible floor differs')
            self.log('reused_complete_arm', model=model, optimizer_calls=0, source='immutable failed checkpoint')
            for record in self.trace:
                if record['model'] == model:
                    callback(copy.deepcopy(record))
            return copy.deepcopy(saved)
        if model != self.policy['model']:
            return fit.fit_arm(phase, model, protocol, eligible, self._callback(callback), optimizer=self.optimizer)
        require(same(eligible, self.partial['fits']['null']['selected']['parameters']), 'Matched eligible null differs')
        with self.operation('eligible_floor_or_fresh_return_support'):
            result = fit.fit_arm(phase, model, protocol, eligible, self._callback(callback), optimizer=self.optimizer)
        # The injected exception did not evaluate an objective: retain its actual old
        # last-evaluation payload rather than the temporary empty closure state.
        for i, record in enumerate(result['records']):
            if record['start_index'] == self.policy['replayed_primary_error_start'] and record['method'] == 'L-BFGS-B':
                result['records'][i] = copy.deepcopy(self.original_error)
        require(self.pending_return is None, 'Unconsumed completed-return token')
        for i,record in enumerate(result['records']):
            if record['start_index'] in self.policy['replayed_successful_starts']:
                original=self.ends[(model,record['start_index'],'L-BFGS-B')]
                require(same(record,original), 'Canonical completed result changed after support check')
        for candidate in result['candidates']:
            start=candidate['start_index']
            if candidate['kind']!='optimizer' or start not in self.policy['replayed_successful_starts']:continue
            original=self.ends[(model,start,'L-BFGS-B')]
            expected=dict(state_index=start+1,kind='optimizer',start_index=start,parameters=original['parameters'],
                score=original['fresh_score'],gradient=original['gradient'])
            comparison=check_comparison(candidate,expected)
            comparison.update(passed=comparison['exact_match'],source_support_token_id=self.replayed_start_support[str(start)]['token']['id'],
                accepted_candidate_source='original_completed_return_before_selection')
            self.replayed_candidates[str(start)]=comparison
            self.log('replayed_candidate_preserved',model=model,start_index=start,**comparison)
            require(comparison['passed'], 'Preselection canonical candidate changed')
        selected=next(v for v in result['candidates'] if v['state_index']==result['selected_state_index'])
        require(same(result['selected'],selected), 'Selected candidate changed during support restoration')
        return result

    def _callback(self, callback):
        def wrapped(record):
            if record['event'] == 'attempt_start':
                self.current = copy.deepcopy(record)
            if record['event'] == 'attempt_end' and record['model'] == self.policy['model'] and record['start_index'] in self.policy['replayed_successful_starts']:
                original=self.ends[(record['model'],record['start_index'],'L-BFGS-B')]
                support=self.replayed_start_support.get(str(record['start_index']),{})
                comparison=check_comparison(bare(record),original)
                self.log('canonical_completed_record',model=record['model'],start_index=record['start_index'],**comparison)
                require(self.pending_return is None and support.get('passed') is True and comparison['exact_match'],
                    'Completed record was not canonicalized before candidate construction')
            if record['event'] == 'attempt_end' and (record['model'], record['start_index'], record['method']) == (self.policy['model'], self.policy['replayed_primary_error_start'], 'L-BFGS-B'):
                require(record['error_type'] == self.original_error['error_type'] and record['error'] == self.original_error['error'] and same(record['initial_parameters'], self.original_error['initial_parameters']), 'Injected error identity differs')
                record = dict(event='attempt_end', model=self.policy['model'], **copy.deepcopy(self.original_error))
            callback(record)
        return wrapped

    def optimizer(self, objective, initial, *, jac, bounds, method, options):
        current = self.current
        require(current is not None, 'Optimizer called without a declared start')
        name, start = current['model'], current['start_index']
        expected_options = ({k:self.science['solver'][k] for k in ('maxiter','maxls','ftol','gtol')}
                            if method == 'L-BFGS-B' else self.science['solver']['powell'])
        require(method == current['method'] and same(initial, current['initial_parameters']) and same(bounds, fit.bounds(self.science, name)) and same(options, expected_options) and jac == (method == 'L-BFGS-B'), 'Optimizer recipe changed')
        key = (name, start, method)
        require(key not in self.optimizer_calls, 'Repeated optimizer invocation')
        self.optimizer_calls.append(key)
        old = self.ends.get(key)
        if name == self.policy['model'] and start in self.policy['replayed_successful_starts']:
            require(method == 'L-BFGS-B' and same(initial, old['initial_parameters']), 'Wrong completed start replay')
            require(self.pending_return is None and not self.active_physical_optimizer, 'Overlapping completed-return token')
            self.pending_return=dict(id=name+'/'+str(start),model=name,start_index=start,
                parameters=copy.deepcopy(old['parameters']),order=8,require_gradient=True)
            self.log('token_created',token=copy.deepcopy(self.pending_return))
            self.log('replayed_optimizer_return', model=name, start_index=start, method=method, actual_objective_calls=0,
                historical_nfev=old['nfev'], historical_nit=old['nit'])
            return OptimizeResult(x=np.asarray(old['returned_parameters']), fun=old['returned_nll'], success=old['solver_success'],
                status=old['solver_status'], message=old['message'], nfev=old['nfev'], nit=old['nit'])
        if name == self.policy['model'] and start == self.policy['replayed_primary_error_start'] and method == 'L-BFGS-B':
            require(same(initial, self.original_error['initial_parameters']), 'Primary error initial point differs')
            self.log('replayed_primary_error', model=name, start_index=start, method=method, actual_objective_calls=0, original_record=self.original_error)
            raise ArithmeticError(self.original_error['error'])
        restart = name == self.policy['model'] and start == self.policy['replayed_primary_error_start'] and method == 'Powell'
        if restart:
            require(same(initial, self.interrupted['initial_parameters']) and same(options, self.policy['original_powell_options']), 'Interrupted rescue restart differs')
        kind = 'restarted_interrupted_invocation' if restart else 'new_optimizer_invocation'
        count = 0
        self.log('physical_optimizer_start', kind=kind, model=name, start_index=start, method=method, initial_parameters=np.asarray(initial).tolist(), options=options)
        def counted(x):
            nonlocal count
            if restart and count == self.policy['anchor_completed_returns']:
                snapshot=dict(observed=True,reference_count=count+1,scope='observational_only',
                    **check_comparison(np.asarray(x).tolist(),self.interrupted['failed_evaluation_parameters']))
                self.reference_snapshots['next_input']=snapshot
                self.log('restart_next_input_reference',**snapshot)
            value = objective(x)
            count += 1
            if restart and count == self.policy['anchor_completed_returns']:
                anchor = {k:v for k,v in self.interrupted['last_evaluation'].items() if k != 'evaluation_count'}
                snapshot=dict(observed=True,reference_count=count,scope='observational_only',**check_comparison(self.last_evaluation,anchor))
                self.reference_snapshots['return']=snapshot
                self.log('restart_return_reference',**snapshot)
            return value
        returned = False
        require(self.pending_return is None and not self.active_physical_optimizer, 'Pending replay support at physical optimizer entry')
        self.active_physical_optimizer=True
        try:
            with self.operation(kind):
                result = self.real_optimizer(counted, initial, jac=jac, bounds=bounds, method=method, options=options)
            returned = True
            return result
        finally:
            self.active_physical_optimizer=False
            self.log('physical_optimizer_end', kind=kind, model=name, start_index=start, method=method,
                returned=returned, completed_objective_returns=count, actual_evaluations=dict(self.evaluations))

    def receipt(self):
        return dict(schema='joint_partial_optimizer_recovery_calls_v2',arm_calls=self.arm_calls,
            logical_optimizer_calls=[list(v) for v in self.optimizer_calls], actual_evaluations=dict(self.evaluations),
            repeated_training_checks=self.repeated_training_checks,
            replayed_start_support=self.replayed_start_support,replayed_candidates=self.replayed_candidates,
            selected_check_evaluations=self.selected_check_evaluations,historical_floor_replay=self.historical_floor_replay,
            reference_snapshots=self.reference_snapshots,pending_return=self.pending_return,
            reference_snapshot_scope='Observational only; not-reached is allowed and no extra evaluations are requested',
            reused_complete_arms=self.policy['reused_complete_arms'],replayed_successful_starts=self.policy['replayed_successful_starts'],
            original_physical_attempts_retained=len(self.ends),original_interrupted_powell=self.interrupted,
            original_primary_error=self.original_error,logical_trace_scope='Consolidated reused/new logical records; call ledger labels physical execution',
            exact_internal_optimizer_resume=False)
