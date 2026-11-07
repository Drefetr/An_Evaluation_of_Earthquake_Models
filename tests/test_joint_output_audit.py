"""Constructed output-corruption controls; no scientific likelihood or fitting."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('independent_joint_audit', Path(__file__).resolve().parents[1] /
                                            'experiments/s04b_joint_nuisance_audit/audit.py')
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def protocol():
    return dict(coordinates=['a', 'd', 'n', 'log_c', 'p', 'eta', 'log_ell', 'log_psi'],
                shared_bounds=[[-12, 0], [-2, 2], [0, .98], [math.log(.0001), math.log(20)], [1.01, 2.5]],
                inhibition_bounds=[[0, 4], [math.log(5), math.log(150)], [math.log(1/24), math.log(365)]],
                starts=dict(shared_templates=[[0, -.2, .2, .01, 1.3]] * 8,
                            inhibition_templates=[[0, 30, 7]] + [[.4, 30, 7]] * 7),
                solver=dict(maxiter=200, powell=dict(maxiter=400, maxfev=5000)),
                quadrature=dict(joint_absolute_tolerance=1e-4, selected_training_gradient_scaled_tolerance=1e-4),
                roster=['S'+str(regime)+'_seed'+str(seed) for regime in range(4, 8) for seed in range(20)],
                pilot=['S4_seed0', 'S5_seed0', 'S6_seed0', 'S6_seed4', 'S7_seed0'])


def score(joint):
    return dict(P=joint + 1.75, E=2., C=-2., M=.25, joint=joint, nll=-joint)


def fit(arm, p, null):
    box = p['shared_bounds'] + ([] if arm == 'null' else p['inhibition_bounds'])
    floor = dict(state_index=0, kind='historical_floor' if arm == 'null' else 'new_null_floor',
                 start_index=-1, parameters=null.copy(), score=score(-10.), gradient=[0.]*8)
    candidates, records = [floor], []
    for index in range(8):
        initial = A.expected_start(p, 10, arm, index, null)
        # Invented fixture points, unrelated to earthquake histories/results.
        theta = initial + [0., math.log(30), math.log(7)] if arm == 'null' else initial.copy()
        if arm != 'null':
            theta[5] = .4
        value = score(-8. if arm != 'null' and index == 0 else -11.)
        record = dict(start_index=index, method='L-BFGS-B', initial_parameters=initial,
                      status='returned', success=True, solver_success=True, solver_status=0,
                      nfev=1, nit=0, finite_feasible=True, returned_parameters=theta[:len(box)],
                      returned_nll=value['nll'], parameters=theta, fresh_score=value, gradient=[0.]*8,
                      fresh_nll_delta=0., projected_gradient=[0.]*len(box), boundaries=A.sides(theta[:len(box)], box))
        records.append(record)
        candidates.append(dict(state_index=index+1, kind='optimizer', start_index=index, parameters=theta,
                               score=value, gradient=[0.]*8))
    selected = candidates[0 if arm == 'null' else 1]
    return dict(passed=True, status='complete', model=arm, required_starts=8, resolved_starts=[True]*8,
                candidates=candidates, records=records, selected=selected,
                selected_state_index=selected['state_index'], null_search_gaps=[])


def fixture():
    p = protocol()
    null = [math.log(.2), .2, .35, math.log(.05), 1.3, 0., math.log(30), math.log(7)]
    fits = {arm: fit(arm, p, null) for arm in ('null', *A.MODELS)}
    checks = {}
    for arm, fitted in fits.items():
        state = fitted['selected']
        size = 5 if arm == 'null' else 8
        checks[arm] = dict(passed=True, parameters=state['parameters'], coarse=state['score'], fine=copy.deepcopy(state['score']),
                           absolute_joint_delta=0., projected_gradient_coarse=[0.]*size, projected_gradient_fine=[0.]*size,
                           projected_gradient_scaled_delta=0., projected_kkt_infinity_norm=0.)
    null_test, raw = score(-13.), score(-12.)
    threshold = 1.5*math.log(10)
    rows, historical = [], []
    for model, gate in A.OUTCOMES:
        old = dict(model=model, gate=gate, passed=True, fixed_floor_gain=1., intercept_only_gain=2.,
                   saved_procedure_joint=-12., fixed_floor_joint=-13., intercept_floor_joint=-14.,
                   historical_off_floor=True, selected_state_index=1)
        historical.append(old)
        floor = gate == 'BIC'
        theta = null if floor else fits[model]['selected']['parameters']
        chosen = null_test if floor else raw
        delta = {key: chosen[key]-null_test[key] for key in A.SCORE_KEYS}
        gain = 0. if floor else 1.
        rows.append(dict(model=model, gate=gate, floor_return=floor, selected_state_index=0 if floor else 1,
                         parameters=theta, score=chosen, new_null_score=null_test, new_gain=gain, delta=delta,
                         new_win=not floor, near_zero=floor, robust_positive=not floor, robust_negative=False,
                         off_floor=not floor, null_search_gap_detected=False, training_gain=2., coarse_training_gain=2.,
                         fine_threshold_distance=2.-threshold, coarse_threshold_distance=2.-threshold,
                         gate_active=False, coarse_fine_gate_disagreement=False,
                         boundaries=A.sides(theta, p['shared_bounds']+p['inhibition_bounds']), historical=old,
                         saved_procedure_vs_new_null=1.))
    report = dict(case_id='S4_seed0', regime=4, seed=0, n_train=10, n_test=11, passed=True, status='complete',
                  training_selections_frozen=True, fits=fits, training_checks=checks, new_null_test=null_test,
                  bic_threshold=threshold, outcomes=rows, historical_comparisons=historical,
                  test_checks={m: dict(fine=raw, coarse=copy.deepcopy(raw), absolute_joint_delta=0.) for m in A.MODELS},
                  floor_checks=[dict(phase=phase, model=m, actual_nll=value, expected_nll=value, absolute_delta=0., tolerance=1e-9)
                                for phase, value in [('train', 10.), ('test', 13.)] for m in A.MODELS],
                  thinning=dict(accepted_immigrants=17, rejected_immigrants=1, accepted_offspring=4, rejected_offspring=0))
    return p, report


def root_record(p, phase='pilot'):
    roster = p['pilot'] if phase == 'pilot' else p['pilot']+[c for c in p['roster'] if c not in p['pilot']]
    return dict(phase=phase, passed=True, status='complete', cases=[dict(case_id=c) for c in roster],
                unknown_case_ids=[], not_run_case_ids=[c for c in p['roster'] if c not in roster],
                new_fit_count=20 if phase == 'pilot' else 300, cumulative_fit_count=4*len(roster),
                outcome_count=5*len(roster), historical_floor_checks=6*len(roster), historical_comparison_rows=5*len(roster))


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def artifact_fixture(tmp, full=False):
    """Whole-file fabricated evidence; opaque history bytes are never evaluated."""
    base = Path(tmp)
    repo, outputs = base/'repo', base/'pilot'
    source = repo/'experiments/s04b_joint_nuisance'
    source.mkdir(parents=True)
    outputs.mkdir()
    p, template = fixture()
    (source/'run.py').write_text('# Constructed non-executable fixture\n', encoding='utf-8')
    (source/'attenuation.cpp').write_text('// Constructed fixture; never compiled\n', encoding='utf-8')
    library = base/'fixture.so'
    library.write_bytes(b'opaque test fixture, not a loadable library')
    build_path = base/'build.json'
    dump(build_path, dict(passed=True, source_sha256=A.sha(source/'attenuation.cpp'), library_sha256=A.sha(library)))
    synthetic = repo/'reproduction/synthetic'
    manifest = []
    all_reports = {}
    for case_id in p['roster']:
        regime, seed = int(case_id[1]), int(case_id.split('seed')[1])
        meta = dict(case_id=case_id, regime=regime, seed=seed, n_train=10, n_test=11,
                    history=case_id+'/history.bin', expected=case_id+'/expected.json',
                    generator_receipt=case_id+'/generation.json', states=case_id+'/states.json',
                    fits={arm: case_id+'/'+arm+'.json' for arm in A.MODELS})
        manifest.append(meta)
        path = synthetic/meta['history']; path.parent.mkdir(parents=True); path.write_bytes(b'constructed')
        r = copy.deepcopy(template)
        r.update(case_id=case_id, regime=regime, seed=seed,
                 stratum='count-suppressed/weak-geometry' if regime in (5, 7) else 'narrow-short')
        dump(synthetic/meta['generator_receipt'], dict(counters=r['thinning']))
        state_rows = {arm: [dict(pars=[0., math.log(30), math.log(7)]), dict(pars=[.4, math.log(30), math.log(7)])] for arm in A.MODELS}
        dump(synthetic/meta['states'], state_rows)
        for arm in A.MODELS:
            dump(synthetic/meta['fits'][arm], dict(floor=state_rows[arm][0]['pars']))
        archived = dict(phase_values={phase: {arm: [[nll, 0, 0, 0, 0, -nll+1.75], [nll-1, 0, 0, 0, 0, -nll+2.75]] for arm in A.MODELS}
                                     for phase, nll in [('order16_train', 10.), ('order32_test', 13.)]},
                        results=[dict(model=arm, gate=gate, selected_state_index=1, gain=1.) for arm, gate in A.OUTCOMES])
        dump(synthetic/meta['expected'], archived)
        old_relative = 'validation/live_results/methodological_20261106/refitted_floor/'+case_id+'.json'
        old = dict(fixed_backbone=dict(a_historical=math.log(.2), d=.2, n=.35, c=.05, p=1.3),
                   phases=dict(train=dict(historical=score(-10)), test=dict(historical=score(-13), refitted=score(-14))),
                   outcomes=[dict(model=arm, gate=gate, selected_state_index=1, original_gain=1., new_gain=2.,
                                  saved_procedure_test_joint=-12., original_floor_test_joint=-13., original_off_floor=True)
                             for arm, gate in A.OUTCOMES])
        dump(repo/old_relative, old)
        r['input_sha256'] = {**{meta[k]: A.sha(synthetic/meta[k]) for k in ('history', 'generator_receipt', 'expected')},
                             old_relative: A.sha(repo/old_relative)}
        all_reports[case_id] = r
    dump(synthetic/'input_manifest.json', dict(s04b=dict(cases=manifest)))
    pins = {str(path.relative_to(repo)).replace('\\', '/'): A.sha(path) for path in repo.rglob('*')
            if path.is_file() and not path.is_relative_to(source)}
    dump(source/'input_pins.json', pins)
    p['input_pins_sha256'] = A.sha(source/'input_pins.json')
    dump(source/'protocol.json', p)
    identities = {path.name: A.sha(path) for path in source.iterdir()}
    admission_path = base/'admission.json'
    admission = dict(phase='pilot', independent_review_passed=True, source_sha256=identities,
                     protocol_sha256=A.sha(source/'protocol.json'), input_pins_sha256=p['input_pins_sha256'],
                     numerical_attempt_id='constructed-fixture', library_sha256=A.sha(library), build_receipt_sha256=A.sha(build_path),
                     threads=2, sampled_process_tree_rss_cap_bytes=6442450944, wall_seconds=1800)
    dump(admission_path, admission)
    result = root_record(p)
    result.update(source_sha256=identities, admission_sha256=A.sha(admission_path), numerical_attempt_id='constructed-fixture',
                  library_sha256=A.sha(library), build_receipt_sha256=A.sha(build_path), runtime=dict(essential=dict(fixture=True)),
                  resources=dict(threads=2, workers=1, sampled_process_tree_rss_cap_bytes=6442450944),
                  threadpools=[dict(num_threads=2)], wall_seconds=1.)
    for entry in result['cases']:
        case_id = entry['case_id']
        r = all_reports[case_id]
        trace = []
        for arm in ('null', *A.MODELS):
            for record in r['fits'][arm]['records']:
                trace.extend([dict(event='attempt_start', model=arm, start_index=record['start_index'], method=record['method'],
                                   initial_parameters=record['initial_parameters'], status='running', success=False),
                              dict(event='attempt_end', model=arm, **record)])
        trace_path = outputs/(case_id+'.attempts.jsonl')
        trace_path.write_text('\n'.join(json.dumps(row) for row in trace)+'\n', encoding='utf-8')
        r['attempts_sha256'] = A.sha(trace_path)
        case_path = outputs/(case_id+'.json')
        dump(case_path, r)
        entry.update(file=case_path.name, sha256=A.sha(case_path), source='new joint fit')
    dump(outputs/'result.json', result)
    args = dict(results=outputs, protocol_path=source/'protocol.json', admission_path=admission_path,
                build_path=build_path, library_path=library)
    if full:
        full_out = base/'full'; full_out.mkdir()
        full_result = {**result, **root_record(p, 'full'), 'pilot_result_sha256': A.sha(outputs/'result.json'), 'pilot_runtime': result['runtime']}
        admission.update(phase='full', pilot_result_sha256=full_result['pilot_result_sha256'], pilot_output_review_passed=True)
        full_admission = base/'full_admission.json'; dump(full_admission, admission)
        full_result['admission_sha256'] = A.sha(full_admission)
        for entry in full_result['cases']:
            case_id = entry['case_id']
            r = all_reports[case_id]
            trace_path = full_out/(case_id+'.attempts.jsonl')
            if case_id in p['pilot']:
                trace_path.write_bytes((outputs/trace_path.name).read_bytes())
            else:
                trace = []
                for arm in ('null', *A.MODELS):
                    for record in r['fits'][arm]['records']:
                        trace += [dict(event='attempt_start', model=arm, start_index=record['start_index'], method=record['method'],
                                       initial_parameters=record['initial_parameters'], status='running', success=False),
                                  dict(event='attempt_end', model=arm, **record)]
                trace_path.write_text('\n'.join(json.dumps(row) for row in trace)+'\n', encoding='utf-8')
            r['attempts_sha256'] = A.sha(trace_path)
            case_path = full_out/(case_id+'.json'); dump(case_path, r)
            entry.update(file=case_path.name, sha256=A.sha(case_path), source='exact pilot reuse' if case_id in p['pilot'] else 'new joint fit')
        dump(full_out/'summary.json', A.aggregate(list(all_reports.values()), p))
        full_result['summary_sha256'] = A.sha(full_out/'summary.json')
        dump(full_out/'result.json', full_result)
        args.update(results=full_out, admission_path=full_admission, pilot=outputs)
    return args


class TestJointOutputAudit(unittest.TestCase):
    def test_valid_constructed_case(self):
        p, case = fixture()
        self.assertIs(A.inspect_case(case, p), case)

    def test_floor_return_cannot_hide_tiny_positive_gain(self):
        p, case = fixture()
        case['outcomes'][2]['new_gain'] = 1e-12
        with self.assertRaisesRegex(A.AuditError, 'exact stored null'):
            A.inspect_case(case, p)

    def test_strict_win_and_near_zero_are_distinct(self):
        p, case = fixture()
        raw = case['test_checks'][A.MODELS[0]]
        raw['coarse'] = raw['fine'] = score(-13+5e-10)
        row = case['outcomes'][0]
        row['score'] = raw['fine']
        row['new_gain'] = raw['fine']['joint']+13
        row['delta'] = {k: raw['fine'][k]-row['new_null_score'][k] for k in A.SCORE_KEYS}
        row['near_zero'], row['robust_positive'] = True, False
        A.inspect_case(case, p)
        self.assertTrue(row['new_win'])
        row['new_win'] = False
        with self.assertRaisesRegex(A.AuditError, 'new_win'):
            A.inspect_case(case, p)

    def test_gate_must_follow_training_scores(self):
        p, case = fixture()
        case['outcomes'][2]['gate_active'] = True
        with self.assertRaisesRegex(A.AuditError, 'Training-only gate'):
            A.inspect_case(case, p)

    def test_selected_state_must_minimize_candidate_objectives(self):
        p, case = fixture()
        f = case['fits']['LI']
        f['selected'] = f['candidates'][2]
        f['selected_state_index'] = 2
        with self.assertRaisesRegex(A.AuditError, 'Selected state'):
            A.inspect_case(case, p)

    def test_missing_start_cannot_be_nonrejection(self):
        p, case = fixture()
        case['fits']['null']['resolved_starts'][-1] = False
        with self.assertRaisesRegex(A.AuditError, 'Unresolved'):
            A.inspect_case(case, p)

    def test_failed_capped_primary_and_successful_rescue_stay_visible(self):
        p, case = fixture()
        records = case['fits']['LI']['records']
        primary = copy.deepcopy(records[0])
        primary.update(success=False, solver_success=False, nit=200)
        records[0]['method'] = 'Powell'
        records[0]['initial_parameters'] = primary['returned_parameters']
        records.insert(0, primary)
        A.inspect_case(case, p)
        row = next(r for r in A.attempt_census([case], p) if r['model'] == 'LI')
        self.assertEqual((row['failed_attempts'], row['capped_attempts'], row['rescue_attempts'], row['unresolved_starts']), (1, 1, 1, 0))

    def test_compensator_sign_and_boundary_census_are_checked(self):
        for field in ('score', 'boundary'):
            p, case = fixture()
            if field == 'score':
                case['new_null_test']['C'] = 2
            else:
                case['outcomes'][0]['boundaries'][5] = 'upper'
            with self.assertRaises(A.AuditError):
                A.inspect_case(case, p)

    def test_unknown_or_missing_case_fails_complete_roster(self):
        p = protocol()
        for change in ('missing', 'unknown', 'duplicate', 'notrun'):
            value = root_record(p, 'full')
            if change == 'missing': value['cases'].pop()
            if change == 'unknown': value['unknown_case_ids'] = [p['roster'][0]]
            if change == 'duplicate': value['cases'][-1] = value['cases'][0]
            if change == 'notrun': value['not_run_case_ids'] = [p['roster'][-1]]
            with self.assertRaises(A.AuditError): A.inspect_roster(value, p)
        self.assertEqual(len(A.inspect_roster(root_record(p, 'pilot'), p)), 5)
        self.assertEqual(len(A.inspect_roster(root_record(p, 'full'), p)), 80)

    def test_independent_full_400_row_aggregation_and_wilson(self):
        p, case = fixture()
        reports = []
        for regime in range(4, 8):
            for index in range(20):
                r = copy.deepcopy(case)
                r.update(regime=regime, seed=index, case_id='S'+str(regime)+'_seed'+str(index))
                reports.append(r)
        rows = A.aggregate(reports, p)
        self.assertEqual(len(rows), 20)
        self.assertEqual(sum(r['N'] for r in rows), 400)
        self.assertEqual(sum(r['primary'] for r in rows), 2)
        for row in rows:
            active = row['gate'] == 'raw'
            self.assertEqual(row['wins'], 20 if active else 0)
            self.assertEqual(row['mean_gain'], 1 if active else 0)
            self.assertEqual(row['floor_returns'], 0 if active else 20)
            self.assertAlmostEqual(row['wilson95'][0 if active else 1], .8388748419471806 if active else .1611251580528194)
        corrupted = copy.deepcopy(rows[0]); corrupted['wins'] = 19
        with self.assertRaises(A.AuditError): A.compare_tree(corrupted, rows[0])

    def test_attempt_trace_binds_order_and_values(self):
        _, case = fixture()
        lines = []
        for arm in ('null', *A.MODELS):
            for rec in case['fits'][arm]['records']:
                lines += [dict(event='attempt_start', model=arm, start_index=rec['start_index'], method=rec['method'],
                               initial_parameters=rec['initial_parameters'], status='running', success=False),
                          dict(event='attempt_end', model=arm, **rec)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'trace.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in lines), encoding='utf-8')
            case['attempts_sha256'] = A.sha(path)
            A.inspect_trace(path, case)
            lines[1]['returned_nll'] += 1
            path.write_text('\n'.join(json.dumps(r) for r in lines), encoding='utf-8')
            case['attempts_sha256'] = A.sha(path)
            with self.assertRaisesRegex(A.AuditError, 'trace differs'):
                A.inspect_trace(path, case)

    def test_paths_cannot_escape_artifact_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(A.AuditError): A.safe(tmp, '../outside.json')

    def test_end_to_end_pilot_is_partial_and_checks_external_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = artifact_fixture(tmp)
            report = A.audit_files(**args)
            self.assertTrue(report['passed'])
            self.assertFalse(report['full_complete'])
            self.assertEqual((report['cases'], report['outcomes'], report['historical_floor_checks']), (5, 25, 30))
            self.assertEqual(sum(r['starts'] for r in report['attempt_census']), 160)
            self.assertEqual(report['scientific_likelihood_calls'], 0)
            args['library_path'].write_bytes(b'changed binary')
            with self.assertRaisesRegex(A.AuditError, 'Native binary'):
                A.audit_files(**args)

    def test_end_to_end_source_change_fails_before_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = artifact_fixture(tmp)
            (args['protocol_path'].parent/'run.py').write_text('# changed source\n', encoding='utf-8')
            with self.assertRaisesRegex(A.AuditError, 'source identity'):
                A.audit_files(**args)

    def test_full_artifact_checks_400_outcomes_and_rejects_forged_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = artifact_fixture(tmp, full=True)
            report = A.audit_files(**args)
            self.assertTrue(report['full_complete'])
            self.assertEqual((report['cases'], report['outcomes'], report['historical_floor_checks'], report['historical_comparison_rows']), (80, 400, 480, 400))
            path = args['results']/'summary.json'
            summary = A.read(path); summary[0]['wins'] -= 1; dump(path, summary)
            root = A.read(args['results']/'result.json'); root['summary_sha256'] = A.sha(path); dump(args['results']/'result.json', root)
            with self.assertRaisesRegex(A.AuditError, 'wins'):
                A.audit_files(**args)

    def test_reuse_requires_exact_case_and_trace_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = artifact_fixture(tmp)
            p = A.read(args['protocol_path'])
            prior = A.read(args['results']/'result.json')
            full = copy.deepcopy(prior)
            full.update(pilot_result_sha256=A.sha(args['results']/'result.json'), pilot_runtime=prior['runtime'])
            for row in full['cases']: row['source'] = 'exact pilot reuse'
            admission = dict(pilot_result_sha256=full['pilot_result_sha256'], pilot_output_review_passed=True)
            A.inspect_pilot_reuse(full, args['results'], args['results'], p, admission)
            full['runtime'] = dict(essential=dict(fixture=False))
            with self.assertRaisesRegex(A.AuditError, 'runtime changed'):
                A.inspect_pilot_reuse(full, args['results'], args['results'], p, admission)


if __name__ == '__main__':
    unittest.main()
