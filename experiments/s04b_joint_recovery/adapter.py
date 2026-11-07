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

SUPPORT_EQUIVALENCE_POLICY = {
    'schema':'joint_operational_gradient_equivalence_v1',
    'dtype':'float64','epsilon_multiplier':64,
    'bound':'64 * float64_epsilon * max(1, abs(actual), abs(expected))',
    'reused_LI_training_check':{
        'policy':'reused_LI_training_support_gradient_only_v1','model':'LI',
        'fields':['projected_gradient_coarse','projected_gradient_fine','projected_gradient_scaled_delta'],
        'recompute_derived_delta':True,'other_fields_exact':True,'return_original_saved_check':True},
    'unused_Powell_anchor_gradient':{
        'policy':'unused_Powell_anchor_gradient_only_v1','fields':['gradient'],
        'objective_uses_gradient':False,'parameters_scores_counts_options_next_input_exact':True},
    'replayed_completed_start_support':{
        'policy':'replayed_completed_start_support_gradient_only_v1','model':'LIplus_immigrant','starts':[0,1,2,3,4],
        'record_fields':['gradient','projected_gradient'],'candidate_fields':['gradient'],
        'projection':'frozen fit.projected_gradient at exact parameters and bounds',
        'other_fields_exact':True,'preserve_original_record_and_candidate_gradient':True,
        'new_optimizer_gradients_unchanged':True},
    'scope':'Measured operational equivalence; no established hardware cause or general error bound'}


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
                row.update(delta=left-right,absolute_delta=abs(left-right))
            differences.append(row)
    visit(a,b,'')
    return dict(actual=a,expected=b,exact_match=same(a,b),differences=differences)


def finite_gradient_equivalence(actual, expected, length=8):
    """Operational comparison only; not a general numerical-error theorem."""
    result=dict(passed=False,epsilon=float(np.finfo(np.float64).eps),multiplier=64,
        formula='64 * float64_epsilon * max(1, abs(actual), abs(expected))',components=[])
    if not isinstance(actual,list) or not isinstance(expected,list) or len(actual)!=length or len(expected)!=length:
        result['reason']='gradient shape';return result
    for i,(a,b) in enumerate(zip(actual,expected)):
        if isinstance(a,bool) or isinstance(b,bool) or not isinstance(a,(int,float)) or not isinstance(b,(int,float)) or not math.isfinite(a) or not math.isfinite(b):
            result['reason']='nonfinite or nonnumeric gradient';return result
        delta=a-b;bound=64*result['epsilon']*max(1.,abs(a),abs(b))
        result['components'].append(dict(index=i,actual=a,expected=b,
            delta=delta if math.isfinite(delta) else None,absolute_delta=abs(delta) if math.isfinite(delta) else None,
            bound=bound,passed=math.isfinite(delta) and abs(delta)<=bound))
    result['passed']=all(v['passed'] for v in result['components'])
    return result


def li_training_equivalence(actual, expected):
    """Only reused LI support gradients may differ; all scientific fields exact."""
    allowed={'projected_gradient_coarse','projected_gradient_fine','projected_gradient_scaled_delta'}
    result=dict(passed=False,policy='reused_LI_training_support_gradient_only_v1',gradient_checks={},
        scientific_criteria_unchanged=True,hardware_cause_established=False)
    if actual.get('passed') is not True or expected.get('passed') is not True:
        result['reason']='Original scientific fine-check pass required';return result
    if not same({k:v for k,v in actual.items() if k not in allowed},{k:v for k,v in expected.items() if k not in allowed}):
        result['reason']='Non-gradient training-check field differs';return result
    for key in ('projected_gradient_coarse','projected_gradient_fine'):
        comparison=finite_gradient_equivalence(actual.get(key),expected.get(key))
        result['gradient_checks'][key]=comparison
        if not comparison['passed']:result['reason']='Gradient comparison failed';return result
    derived={}
    for label,check in [('actual',actual),('expected',expected)]:
        coarse=np.asarray(check['projected_gradient_coarse']);fine=np.asarray(check['projected_gradient_fine'])
        value=float(np.max(np.abs(coarse-fine)/np.maximum(1.,np.maximum(np.abs(coarse),np.abs(fine))),initial=0))
        derived[label]=value
        if not same(value,check.get('projected_gradient_scaled_delta')):
            result.update(reason='Derived gradient delta inconsistent',recomputed_gradient_delta=derived);return result
    comparison=finite_gradient_equivalence([derived['actual']],[derived['expected']],1)
    result.update(passed=comparison['passed'],recomputed_gradient_delta=derived,derived_delta_comparison=comparison)
    return result


def powell_anchor_equivalence(actual, expected):
    """Powell consumes scalar NLL: only its unused finite gradient is compared."""
    result=dict(passed=False,policy='unused_Powell_anchor_gradient_only_v1',
        objective_parameters_and_scores_exact=same({k:v for k,v in actual.items() if k!='gradient'},
            {k:v for k,v in expected.items() if k!='gradient'}))
    if not result['objective_parameters_and_scores_exact']:
        result['reason']='Anchor parameter or score field differs';return result
    comparison=finite_gradient_equivalence(actual.get('gradient'),expected.get('gradient'))
    result.update(passed=comparison['passed'],gradient_comparison=comparison)
    return result


def replayed_record_equivalence(actual, expected, box):
    allowed={'gradient','projected_gradient'}
    result=dict(passed=False,policy='replayed_completed_start_support_gradient_only_v1',
        non_gradient_fields_exact=same({k:v for k,v in actual.items() if k not in allowed},
            {k:v for k,v in expected.items() if k not in allowed}))
    if not result['non_gradient_fields_exact']:return result
    raw=finite_gradient_equivalence(actual.get('gradient'),expected.get('gradient'))
    projected=finite_gradient_equivalence(actual.get('projected_gradient'),expected.get('projected_gradient'))
    result.update(raw_gradient_comparison=raw,projected_gradient_comparison=projected)
    if not raw['passed'] or not projected['passed']:return result
    for label,row in [('actual',actual),('expected',expected)]:
        derived=fit.projected_gradient(row['parameters'],row['gradient'],box).tolist()
        result[label+'_projection_exact']=same(derived,row['projected_gradient'])
    result['passed']=result['actual_projection_exact'] and result['expected_projection_exact']
    return result


def bare(record):
    return {k: copy.deepcopy(v) for k, v in record.items() if k not in ('event', 'model')}


class CountedPhase:
    """Count actual evaluations; never synthesize a scientific response."""
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
        return score, gradient


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
        self.anchor_return_verified = self.anchor_next_input_verified = False
        self.current = None
        self._validate_partial()
        self.ends = {(r['model'], r['start_index'], r['method']): bare(r) for r in trace if r['event'] == 'attempt_end'}
        self.original_error = self.ends[(policy['model'], policy['replayed_primary_error_start'], 'L-BFGS-B')]
        self.interrupted = self.ends[(policy['model'], policy['replayed_primary_error_start'], 'Powell')]
        self.log('lineage', original_failed_physical_attempts=len(self.ends), interrupted=self.interrupted,
            scope='Original interrupted invocation is not a successful logical return or an internal-state resume')

    def record_training_check(self, name, actual, expected):
        checked = check_comparison(actual, expected)
        checked['operational_equivalence']=(li_training_equivalence(checked['actual'],checked['expected'])
            if name=='LI' else dict(passed=checked['exact_match'],policy='exact_saved_training_check'))
        checked['accepted_check_source']='original_saved_check' if checked['operational_equivalence']['passed'] else None
        self.repeated_training_checks[name] = checked
        self.log('repeated_training_check', model=name, **checked)
        return checked

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
        require(self.anchor_return_verified and self.anchor_next_input_verified, 'Interrupted invocation did not reach both original anchors')
        for i,record in enumerate(result['records']):
            if record['start_index'] in self.policy['replayed_successful_starts']:
                saved=self.replayed_start_support[str(record['start_index'])]
                require(same(record,saved['actual']) and saved['operational_equivalence']['passed'], 'Replayed successful result changed after support check')
                result['records'][i]=copy.deepcopy(saved['expected'])
        for candidate in result['candidates']:
            start=candidate['start_index']
            if candidate['kind']!='optimizer' or start not in self.policy['replayed_successful_starts']:continue
            original=self.ends[(model,start,'L-BFGS-B')]
            expected=dict(state_index=start+1,kind='optimizer',start_index=start,parameters=original['parameters'],
                score=original['fresh_score'],gradient=original['gradient'])
            comparison=check_comparison(candidate,expected)
            other=same({k:v for k,v in candidate.items() if k!='gradient'},{k:v for k,v in expected.items() if k!='gradient'})
            gradient=finite_gradient_equivalence(candidate.get('gradient'),expected['gradient'])
            equivalence=dict(passed=other and gradient['passed'],non_gradient_fields_exact=other,gradient_comparison=gradient)
            comparison.update(operational_equivalence=equivalence,accepted_candidate_gradient_source='original_saved_record.gradient' if equivalence['passed'] else None)
            self.replayed_candidates[str(start)]=comparison
            self.log('replayed_candidate_support',model=model,start_index=start,**comparison)
            require(equivalence['passed'] and same(candidate['gradient'],self.replayed_start_support[str(start)]['actual']['gradient']),
                'Replayed candidate or fresh gradient differs')
            # Mutate the existing candidate so its selected-state alias remains exact.
            candidate['gradient']=copy.deepcopy(expected['gradient'])
            self.log('replayed_candidate_preserved',model=model,start_index=start,**comparison)
        selected=next(v for v in result['candidates'] if v['state_index']==result['selected_state_index'])
        require(same(result['selected'],selected), 'Selected candidate changed during support restoration')
        return result

    def _callback(self, callback):
        def wrapped(record):
            if record['event'] == 'attempt_start':
                self.current = copy.deepcopy(record)
            if record['event'] == 'attempt_end' and record['model'] == self.policy['model'] and record['start_index'] in self.policy['replayed_successful_starts']:
                original=self.ends[(record['model'],record['start_index'],'L-BFGS-B')]
                comparison=check_comparison(bare(record),original)
                equivalence=replayed_record_equivalence(comparison['actual'],comparison['expected'],fit.bounds(self.science,record['model']))
                comparison.update(operational_equivalence=equivalence,accepted_record_source='original_saved_record' if equivalence['passed'] else None)
                self.replayed_start_support[str(record['start_index'])]=comparison
                self.log('replayed_completed_start_support',model=record['model'],start_index=record['start_index'],**comparison)
                require(equivalence['passed'], 'Replayed successful return or fresh support changed')
                record=dict(event='attempt_end',model=self.policy['model'],**copy.deepcopy(original))
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
                require(same(np.asarray(x).tolist(), self.interrupted['failed_evaluation_parameters']), 'Restart next-input anchor differs')
                self.anchor_next_input_verified = True
                self.log('restart_next_input_anchor_verified', evaluation_number=count+1, parameters=np.asarray(x).tolist())
            value = objective(x)
            count += 1
            if restart and count == self.policy['anchor_completed_returns']:
                anchor = {k:v for k,v in self.interrupted['last_evaluation'].items() if k != 'evaluation_count'}
                comparison=check_comparison(self.last_evaluation,anchor)
                equivalence=powell_anchor_equivalence(comparison['actual'],comparison['expected'])
                self.log('restart_return_anchor_comparison',evaluation_count=count,**comparison,operational_equivalence=equivalence)
                require(equivalence['passed'], 'Restart completed-return anchor differs')
                self.anchor_return_verified = True
                self.log('restart_return_anchor_verified', evaluation_count=count, actual_evaluation=copy.deepcopy(self.last_evaluation),
                    expected_evaluation=copy.deepcopy(anchor),exact_match=comparison['exact_match'],operational_equivalence=equivalence)
            return value
        returned = False
        try:
            with self.operation(kind):
                result = self.real_optimizer(counted, initial, jac=jac, bounds=bounds, method=method, options=options)
            returned = True
            return result
        finally:
            self.log('physical_optimizer_end', kind=kind, model=name, start_index=start, method=method,
                returned=returned, completed_objective_returns=count, actual_evaluations=dict(self.evaluations))

    def receipt(self):
        return dict(schema='joint_partial_optimizer_recovery_calls_v1',arm_calls=self.arm_calls,
            logical_optimizer_calls=[list(v) for v in self.optimizer_calls], actual_evaluations=dict(self.evaluations),
            repeated_training_checks=self.repeated_training_checks,
            replayed_start_support=self.replayed_start_support,replayed_candidates=self.replayed_candidates,
            anchor_return_verified=self.anchor_return_verified,anchor_next_input_verified=self.anchor_next_input_verified,
            reused_complete_arms=self.policy['reused_complete_arms'],replayed_successful_starts=self.policy['replayed_successful_starts'],
            original_physical_attempts_retained=len(self.ends),original_interrupted_powell=self.interrupted,
            original_primary_error=self.original_error,logical_trace_scope='Consolidated reused/new logical records; call ledger labels physical execution',
            exact_internal_optimizer_resume=False)
