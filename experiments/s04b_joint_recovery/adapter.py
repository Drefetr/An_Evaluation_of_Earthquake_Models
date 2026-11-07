"""Explicit replay of saved optimizer returns through the unchanged fit function.

The consolidated scientific trace is logical, not a claim of fresh optimization.
The append-only call ledger and immutable failed trace identify physical work.
"""
from __future__ import annotations
import copy
import json
import os
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import numpy as np
from scipy.optimize import OptimizeResult, minimize
from experiments.s04b_joint_nuisance import fit, checkpoint


def require(ok, message):
    if not ok:
        raise ValueError(message)


def same(a, b):
    return checkpoint.dumps(a, sort_keys=True, separators=(',', ':')) == checkpoint.dumps(b, sort_keys=True, separators=(',', ':'))


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
        self.ledger_path, self.real_optimizer = Path(ledger_path), optimizer
        require(not self.ledger_path.exists(), 'Recovery call ledger must be fresh')
        self.context = 'support_check'
        self.evaluations = defaultdict(Counter)
        self.last_evaluation = None
        self.arm_calls, self.optimizer_calls = [], []
        self.anchor_return_verified = self.anchor_next_input_verified = False
        self.current = None
        self._validate_partial()
        self.ends = {(r['model'], r['start_index'], r['method']): bare(r) for r in trace if r['event'] == 'attempt_end'}
        self.original_error = self.ends[(policy['model'], policy['replayed_primary_error_start'], 'L-BFGS-B')]
        self.interrupted = self.ends[(policy['model'], policy['replayed_primary_error_start'], 'Powell')]
        self.log('lineage', original_failed_physical_attempts=len(self.ends), interrupted=self.interrupted,
            scope='Original interrupted invocation is not a successful logical return or an internal-state resume')

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
        for record in result['records']:
            if record['start_index'] in self.policy['replayed_successful_starts']:
                require(same(record, self.ends[(model, record['start_index'], 'L-BFGS-B')]), 'Replayed successful result or fresh support check changed')
        return result

    def _callback(self, callback):
        def wrapped(record):
            if record['event'] == 'attempt_start':
                self.current = copy.deepcopy(record)
            if record['event'] == 'attempt_end' and record['model'] == self.policy['model'] and record['start_index'] in self.policy['replayed_successful_starts']:
                require(same(bare(record), self.ends[(record['model'], record['start_index'], 'L-BFGS-B')]), 'Replayed successful return or fresh support changed')
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
                require(same(self.last_evaluation, anchor), 'Restart completed-return anchor differs')
                self.anchor_return_verified = True
                self.log('restart_return_anchor_verified', evaluation_count=count, actual_evaluation=copy.deepcopy(self.last_evaluation))
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
            anchor_return_verified=self.anchor_return_verified,anchor_next_input_verified=self.anchor_next_input_verified,
            reused_complete_arms=self.policy['reused_complete_arms'],replayed_successful_starts=self.policy['replayed_successful_starts'],
            original_physical_attempts_retained=len(self.ends),original_interrupted_powell=self.interrupted,
            original_primary_error=self.original_error,logical_trace_scope='Consolidated reused/new logical records; call ledger labels physical execution',
            exact_internal_optimizer_resume=False)
