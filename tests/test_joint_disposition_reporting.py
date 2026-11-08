"""Invented bytes only: no model, optimizer, simulator or historical replay."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

from scripts import build_joint_disposition_report as builder
from scripts import render_joint_disposition_results as formatter
from scripts import verify_claims


def data(value):
    return (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data(value))


class InventedDispositionEvidence:
    """A complete fake custody chain, including 41 immutable + 39 new records."""
    def __init__(self, root, extra_unknown=False):
        self.repo = root/'repo'
        self.base = 'validation/reproductions/invented/'
        self.paths = {key:self.base+key+'.json' for key in ('index', 'registry', 'index_review')}
        self.public = {key:self.base+name+'.json' for key, name in
                       [('report', 'report'), ('audit', 'independent_review'), ('completion_review', 'completion_review')]}
        self.cases = []
        for regime in range(4, 8):
            for seed in range(20):
                case_id = builder.UNKNOWN_CASE if (regime, seed) == (5, 17) else f'S{regime}_invented_seed{regime*100+seed}'
                self.cases.append(dict(case_id=case_id, regime=regime, seed=regime*100+seed,
                                       expected='invented/'+case_id+'.json'))
        prefix = self.cases[:20]+self.cases[20:37]+self.cases[40:42]+self.cases[60:61]
        unknown = self.cases[37]
        self.sequence = [case['case_id'] for case in prefix+[unknown]]
        self.sequence += [case['case_id'] for case in self.cases if case['case_id'] not in self.sequence]
        self.by_id = {case['case_id']:case for case in self.cases}
        self.new_unknown = self.sequence[-1] if extra_unknown else None
        self.native = dict(library_sha256='1'*64, build_receipt_sha256='2'*64,
                           runtime_essential={'implementation':'invented, not executed'})
        self.sources = {'invented_source.py':'3'*64}
        self.science = dict(roster=[case['case_id'] for case in self.cases],
            solver={'powell':dict(maxfev=5000, maxiter=5000)}, shared_bounds=[[-10, 10]]*5,
            inhibition_bounds=[[0, 1], [-10, 10], [-10, 10]],
            coordinates=['a', 'd', 'n', 'log_c', 'p', 'eta', 'log_tau', 'log_sigma'])
        self.terminal = dict(start_index=5, method='Powell', status='returned', finite_feasible=True,
            success=False, solver_success=False, solver_status=1, nfev=5000, nit=22, returned_nll=123.)
        self.original_census = dict(new_completed_cases=0, new_test_evaluations=0, new_optimizer_invocations=1)
        self.reports, self.traces = {}, {}
        for case in self.cases:
            key = case['case_id']
            is_unknown = key in (builder.UNKNOWN_CASE, self.new_unknown)
            gain = [-1., 0., 1e-10, 1.][case['seed'] % 4]
            fits = {arm:dict(passed=True, records=[dict(success=True)], null_search_gaps=[]) for arm in builder.ARMS}
            comparisons = [dict(model=m, gate=g, passed=True, fixed_floor_gain=5., intercept_only_gain=6.)
                           for m, g in builder.PROCEDURES]
            outcomes = [dict(model=m, gate=g, new_gain=gain, new_win=gain>0, near_zero=abs(gain)<=1e-9,
                floor_return=False, parameters=[0.]*5+[.5, 0., 0.], selected_state_index=1,
                score=dict(joint=gain), new_null_score=dict(joint=0.),
                coarse_fine_gate_disagreement=False, historical=deepcopy(comparisons[i]))
                for i, (m, g) in enumerate(builder.PROCEDURES)]
            report = dict(case_id=key, regime=case['regime'], seed=case['seed'], n_train=10, n_test=10,
                thinning=dict(accepted_immigrants=3, rejected_immigrants=1, accepted_offspring=4, rejected_offspring=1),
                passed=not is_unknown, status='unknown' if is_unknown else 'complete', fits=fits,
                outcomes=[] if is_unknown else outcomes, historical_comparisons=[] if is_unknown else comparisons,
                floor_checks=[dict(phase=p, model=m, actual_nll=1., expected_nll=1., absolute_delta=0., tolerance=1e-9)
                              for p in (('train',) if is_unknown else ('train', 'test')) for m in builder.LABELS])
            if is_unknown:
                if key == builder.UNKNOWN_CASE:
                    report['fits'] = {name:fits[name] for name in ('null', 'LI')}
                    report.update(error_type='KeyError', error="'selected_state_index'")
                else:
                    report['fits'] = {name:fits[name] for name in ('null', 'LI')}
                    report['fits']['LIplus_immigrant'] = dict(passed=False, status='unknown_starts', records=[self.terminal])
                    report.update(error_type='ValueError', error='Unresolved alternative starts')
                trace = [dict(event='attempt_end', model='LIplus_immigrant', **self.terminal)]
            else:
                trace = [dict(event='attempt_end', model='null', success=True)]
            self.reports[key], self.traces[key] = report, trace
        write(self.repo/builder.MANIFEST, {'s04b':{'cases':self.cases}})
        frozen = {builder.MANIFEST:builder.sha(self.repo/builder.MANIFEST)}
        for case in self.cases:
            expected_path = 'reproduction/synthetic/'+case['expected']
            old_path = 'validation/live_results/methodological_20261106/refitted_floor/'+case['case_id']+'.json'
            write(self.repo/expected_path, dict(seed=case['seed'], regime=case['regime'], results=[
                dict(model=m, gate=g, status='complete', gain=5., win=True, selected_state_index=1)
                for m, g in builder.PROCEDURES]))
            write(self.repo/old_path, dict(case_id=case['case_id'], regime=case['regime'], outcomes=[
                dict(model=m, gate=g, original_gain=5., new_gain=6., new_win=True, selected_state_index=1)
                for m, g in builder.PROCEDURES]))
            frozen.update({name:builder.sha(self.repo/name) for name in (expected_path, old_path)})
        write(self.repo/builder.INPUT_PINS, frozen)
        self.science['input_pins_sha256'] = builder.sha(self.repo/builder.INPUT_PINS)
        write(self.repo/builder.SCIENCE, self.science)
        self.historical = []
        for kind in ('fixed_floor', 'intercept_only'):
            relative = self.base+kind+'.json'
            write(self.repo/relative, dict(passed=True, fixture='invented historical acceptance'))
            reference = dict(path=relative, sha256=builder.sha(self.repo/relative))
            self.historical.append(dict(kind=kind, artifact=reference, review=reference))
        self.index = dict(schema='joint_remaining_index_v1', passed=False, scientific_completion=False,
                          original_native=self.native, scientific_source_sha256=self.sources)
        self.policy = dict(full_sequence=self.sequence, case_ids=self.sequence[41:], original_native=self.native,
                           scientific_protocol_sha256=builder.sha(self.repo/builder.SCIENCE))
        self.overrides = {}
        self.persist()

    def zip(self, name, values):
        path = self.repo/self.base/name
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, 'w') as saved:
            for key, value in values.items():
                saved.writestr(key, value)
        return dict(path=path.relative_to(self.repo).as_posix(), sha256=builder.sha(path))

    def persist(self):
        immutable, new = {}, {}
        locations = {}
        for i, key in enumerate(self.sequence):
            report = data(self.reports[key])
            trace = b''.join(json.dumps(event).encode()+b'\n' for event in self.traces[key])
            prefix = 'prefix/' if i < 41 else 'children/'+key+'/'
            locations[key] = dict(case=prefix+'case.json', trace=prefix+'trace.jsonl',
                                  case_sha256=builder.digest(report), trace_sha256=builder.digest(trace))
            # Immutable entries have distinct case member names too.
            if i < 41:
                locations[key]['case'] = 'prefix/'+key+'.json'
                locations[key]['trace'] = 'prefix/'+key+'.jsonl'
                immutable[locations[key]['case']] = report
                immutable[locations[key]['trace']] = trace
            else:
                new['host/'+locations[key]['case']] = report
                new['host/'+locations[key]['trace']] = trace
        archive = self.zip('immutable.zip', immutable)
        unknown = locations[builder.UNKNOWN_CASE]
        original_review = dict(passed=False, audit_passed=True, scientific_completion=False,
            live_agent_review=True, review_kind='live_agent_failure_and_partial_output_review',
            archive_sha256=archive['sha256'], source_sha256=self.sources,
            failure=dict(capped_optimizer_record=self.terminal), execution_census=self.original_census)
        review_path = self.base+'failure_review.json'
        write(self.repo/review_path, original_review)
        review_ref = dict(path=review_path, sha256=builder.sha(self.repo/review_path))
        failure = dict(archive=archive['path'], archive_sha256=archive['sha256'], review=review_path,
            review_sha256=review_ref['sha256'], case_id=builder.UNKNOWN_CASE,
            case_member=unknown['case'], trace_member=unknown['trace'],
            case_sha256=unknown['case_sha256'], trace_sha256=unknown['trace_sha256'],
            complete_case_ids=self.sequence[:40])
        self.policy['immutable_failure_reference'] = failure
        write(self.repo/builder.POLICY, self.policy)
        records = []
        for i, key in enumerate(self.sequence):
            report, location = self.reports[key], locations[key]
            complete = report['passed']
            disposition = 'complete' if complete else 'scientific_unknown'
            source = dict(case_sha256=location['case_sha256'], trace_sha256=location['trace_sha256'])
            if i < 41:
                source.update(kind='immutable_archive', archive_sha256=archive['sha256'],
                              case_member=location['case'], trace_member=location['trace'])
            else:
                result_path = 'children/'+key+'/result.json'
                supervision_path = 'children/'+key+'/supervision.json'
                census = dict(held_out_phase_constructed=False, unresolved_model='LIplus_immigrant',
                    attempted_models=['null', 'LI', 'LIplus_immigrant'], not_run_models=['LIplus_inclusive'],
                    unresolved_start=5, not_run_starts=[6, 7], logical_optimizer_attempts=3)
                result = dict(schema='joint_remaining_case_result_v1', handled=True, disposition_valid=True,
                    status='terminal_disposition', case_id=key, disposition=disposition, scientific_passed=complete,
                    passed=complete, report_sha256=location['case_sha256'], trace_sha256=location['trace_sha256'],
                    protocol_sha256=builder.sha(self.repo/builder.POLICY), immutable_failure_reference=failure,
                    runtime=dict(essential=self.native['runtime_essential']), source_sha256=self.sources,
                    library_sha256=self.native['library_sha256'], build_receipt_sha256=self.native['build_receipt_sha256'])
                if not complete:
                    result.update(unknown_outcome_count=5, terminal_solver_return=self.terminal,
                        phase_constructions=[dict(start=30, end=395, returned=True)], model_census=census,
                        unknown_reason=dict(error_type=report['error_type'], error=report['error'], arm_status='unknown_starts'))
                supervision = dict(status='passed', returncode=0, launched=True, stop_reason=None,
                                   cleanup_errors=[], survivors_after_cleanup=[])
                new['host/'+result_path], new['host/'+supervision_path] = data(result), data(supervision)
                source.update(kind='host_execution', execution_id='invented-parent-attempt', case_path=location['case'],
                    trace_path=location['trace'], result_path=result_path, result_sha256=builder.digest(data(result)),
                    supervision_path=supervision_path, supervision_sha256=builder.digest(data(supervision)))
            record = dict(builder.projection(report), disposition=disposition, scientific_passed=complete,
                          source=source, outcomes=report['outcomes'])
            if not complete:
                record.update(unknown_origin='audited_retained_failure' if i == 40 else 'new_frozen_solver_cap',
                              model_census=self.original_census if i == 40 else census)
                if i != 40:
                    record.update(terminal_solver_return=self.terminal, unknown_reason=result['unknown_reason'])
            record.update(deepcopy(self.overrides.get(key, {})))
            records.append(record)
        new_archive = self.zip('new.zip', new)
        host_review_path = self.base+'host_review.json'
        host_review = dict(passed=True, audit_passed=True, scientific_completion=False,
            live_agent_review=True, review_kind='live_agent_saved_output_review', artifact_sha256=new_archive['sha256'],
            execution_id='invented-parent-attempt', checked_case_ids=self.sequence[41:])
        write(self.repo/host_review_path, host_review)
        host_review_ref = dict(path=host_review_path, sha256=builder.sha(self.repo/host_review_path))
        self.registry = dict(schema='joint_disposition_execution_registry_v1', archives=[dict(archive=archive, review=review_ref)],
            executions=[dict(execution_id='invented-parent-attempt', member_prefix='host/', archive=new_archive, review=host_review_ref)],
            historical_comparators=self.historical)
        self.index.update(protocol_sha256=builder.sha(self.repo/builder.POLICY), immutable_failure_reference=failure,
            records=records, counts=dict(processed_histories=80, complete_histories=sum(r['scientific_passed'] for r in records),
                unknown_histories=sum(not r['scientific_passed'] for r in records), unattempted_histories=0,
                computed_outcomes=5*sum(r['scientific_passed'] for r in records)))
        write(self.repo/self.paths['index'], self.index)
        write(self.repo/self.paths['registry'], self.registry)
        self.index_review = dict(passed=True, audit_passed=True, scientific_completion=False,
            live_agent_review=True, review_kind='live_agent_saved_output_review',
            index_sha256=builder.sha(self.repo/self.paths['index']), counts=self.index['counts'], all_histories_attempted=True)
        write(self.repo/self.paths['index_review'], self.index_review)

    def accept(self):
        report, pins = builder.build(self.repo, self.paths)
        write(self.repo/self.public['report'], report)
        audit = dict(reporting_accepted=True, disposition_accounting_complete=True, scientific_completion=False,
            original_publication_gate_satisfied=False, live_independent_review=True,
            review_kind=formatter.REVIEW_KIND, reviewer='invented independent reviewer',
            campaign_identity=report['campaign_identity'], counts=report['counts'],
            report_sha256=builder.sha(self.repo/self.public['report']), source_pins=pins,
            independent_summary=deepcopy(report['regime_summary']))
        write(self.repo/self.public['audit'], audit)
        acceptance = {key:value for key, value in audit.items() if key not in
                      ('report_sha256', 'source_pins', 'independent_summary')}
        acceptance.update(schema=formatter.SCHEMA,
            artifact_sha256={self.public[key]:builder.sha(self.repo/self.public[key]) for key in ('report', 'audit')},
            tasks=dict(task1=dict(disposition_reporting_accepted=True, scientific_completion=False,
                acceptance=dict(path=self.public['audit'], sha256=builder.sha(self.repo/self.public['audit'])))))
        for task in ('task2', 'task3'):
            name = self.base+task+'.json'
            write(self.repo/name, dict(passed=True, fixture='invented acceptance'))
            acceptance['tasks'][task] = dict(passed=True, acceptance=dict(path=name, sha256=builder.sha(self.repo/name)))
        write(self.repo/self.public['completion_review'], acceptance)
        return report, audit, acceptance


class TestDispositionReporting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = InventedDispositionEvidence(self.root)

    def test_five_missing_slots_and_all_twenty_rows_with_complete_groups_only(self):
        aggregate = builder.arithmetic().aggregate
        calls = []
        def checked(reports, science):
            calls.append(len(reports))
            self.assertEqual(len(reports), 20)
            return aggregate(reports, science)
        core = builder.arithmetic()
        core.aggregate = checked
        with patch.object(builder, 'arithmetic', return_value=core):
            report, pins = builder.build(self.fixture.repo, self.fixture.paths)
        self.assertEqual(calls, [20, 20, 20])
        self.assertEqual(report['complete_regimes'], [4, 6, 7])
        self.assertEqual(len(report['case_dispositions']), 80)
        self.assertEqual(len(report['outcomes']), 400)
        self.assertEqual(len({r['id'] for r in report['outcomes']}), 400)
        self.assertEqual(len(report['regime_summary']), 20)
        self.assertEqual(report['counts']['computed_outcomes'], 395)
        self.assertEqual(report['counts']['unavailable_outcomes'], 5)
        for row in report['regime_summary']:
            self.assertEqual(row['statistics_available'], row['regime'] != 5)
            if row['regime'] == 5:
                self.assertIsNone(row['full_regime'])
                self.assertEqual(row['computed_histories'], 19)
            else:
                self.assertEqual(row['full_regime']['wins'], 10)
                self.assertEqual(row['full_regime']['positive_near_zero'], 5)
        for row in report['outcomes']:
            if row['availability'] == 'unavailable':
                self.assertTrue(all(row[key] is None for key in builder.NULL_FIELDS))
                self.assertEqual(row['historical_comparators']['fixed_floor_gain'], 5.)
                self.assertEqual(row['historical_comparators']['intercept_only_gain'], 6.)
        self.assertEqual(report['coverage']['verified_retained_floor_checks'], 477)
        self.assertEqual(report['coverage']['verified_new_historical_comparison_rows'], 395)
        self.assertFalse(report['scientific_completion'])
        self.assertFalse(report['reporting_accepted'])
        self.assertIn(builder.INPUT_PINS, pins)

    def test_additional_cap_unknown_makes_entire_second_regime_unavailable(self):
        fixture = InventedDispositionEvidence(self.root/'second', extra_unknown=True)
        report, _ = builder.build(fixture.repo, fixture.paths)
        self.assertEqual(report['complete_regimes'], [4, 6])
        self.assertEqual(report['counts']['unavailable_outcomes'], 10)
        self.assertEqual(sum(row['full_regime'] is None for row in report['regime_summary']), 10)

    def test_immutable_unknown_cannot_be_promoted_even_with_repinned_index(self):
        self.fixture.overrides[builder.UNKNOWN_CASE] = dict(disposition='complete', scientific_passed=True)
        self.fixture.persist()
        with self.assertRaisesRegex(ValueError, 'Permanent unknown'):
            builder.build(self.fixture.repo, self.fixture.paths)

    def test_unknown_heldout_value_and_technical_failure_are_rejected_after_repinning(self):
        self.fixture.reports[builder.UNKNOWN_CASE]['new_null_test'] = {'joint':99.}
        self.fixture.persist()
        with self.assertRaisesRegex(ValueError, 'Unknown contains held-out'):
            builder.build(self.fixture.repo, self.fixture.paths)
        fixture = InventedDispositionEvidence(self.root/'technical', extra_unknown=True)
        fixture.reports[fixture.new_unknown]['error_type'] = 'TimeoutError'
        fixture.persist()
        with self.assertRaisesRegex(ValueError, 'Technical failure'):
            builder.build(fixture.repo, fixture.paths)

    def test_sources_are_resolved_not_trusted_from_compact_projection(self):
        key = self.fixture.sequence[-1]
        altered = deepcopy(self.fixture.reports[key]['outcomes'])
        altered[0]['new_gain'] = 99.
        self.fixture.overrides[key] = dict(outcomes=altered)
        self.fixture.persist()
        with self.assertRaisesRegex(ValueError, 'projection differs'):
            builder.build(self.fixture.repo, self.fixture.paths)
        self.fixture.overrides.clear()
        self.fixture.persist()
        old_path = 'validation/live_results/methodological_20261106/refitted_floor/'+key+'.json'
        value = builder.read(self.fixture.repo/old_path)
        value['outcomes'][0]['new_gain'] = 99.
        write(self.fixture.repo/old_path, value)
        with self.assertRaisesRegex(ValueError, 'Source hash differs'):
            builder.build(self.fixture.repo, self.fixture.paths)

    def test_unreviewed_host_and_unresolved_registry_fail_closed(self):
        registry = self.fixture.registry
        review_ref = registry['executions'][0]['review']
        review = builder.read(self.fixture.repo/review_ref['path'])
        review['live_agent_review'] = False
        write(self.fixture.repo/review_ref['path'], review)
        review_ref['sha256'] = builder.sha(self.fixture.repo/review_ref['path'])
        write(self.fixture.repo/self.fixture.paths['registry'], registry)
        with self.assertRaisesRegex(ValueError, 'live independent'):
            builder.build(self.fixture.repo, self.fixture.paths)
        self.fixture.persist()
        registry = self.fixture.registry
        registry['executions'].clear()
        write(self.fixture.repo/self.fixture.paths['registry'], registry)
        with self.assertRaisesRegex(ValueError, 'Unregistered host'):
            builder.build(self.fixture.repo, self.fixture.paths)

    def test_roster_count_types_and_trace_hash_cannot_be_replaced_by_acceptance_flags(self):
        index = self.fixture.index
        index['records'][-1] = deepcopy(index['records'][-2])
        write(self.fixture.repo/self.fixture.paths['index'], index)
        with self.assertRaisesRegex(ValueError, 'Final compact disposition index'):
            builder.build(self.fixture.repo, self.fixture.paths)
        self.fixture.persist()
        index = self.fixture.index
        index['counts']['unattempted_histories'] = False
        write(self.fixture.repo/self.fixture.paths['index'], index)
        with self.assertRaisesRegex(ValueError, 'Invalid census count'):
            builder.build(self.fixture.repo, self.fixture.paths)
        self.fixture.persist()
        index = self.fixture.index
        index['records'][-1]['source']['trace_sha256'] = '0'*64
        write(self.fixture.repo/self.fixture.paths['index'], index)
        review = self.fixture.index_review
        review['index_sha256'] = builder.sha(self.fixture.repo/self.fixture.paths['index'])
        write(self.fixture.repo/self.fixture.paths['index_review'], review)
        with self.assertRaisesRegex(ValueError, 'Result does not bind'):
            builder.build(self.fixture.repo, self.fixture.paths)

    def test_duplicate_and_unsafe_zip_members_rejected_without_extraction(self):
        for member in ('good.json', '../escape.json', 'C:/escape.json', 'a\\escape.json'):
            path = self.root/(str(len(member))+'.zip')
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                with zipfile.ZipFile(path, 'w') as archive:
                    info = zipfile.ZipInfo('safe.json')
                    info.filename = member  # Preserve raw spelling even on Windows.
                    archive.writestr(info, '{}')
                    if member == 'good.json':
                        archive.writestr(member, '{}')
            evidence = builder.Evidence(self.root)
            with self.assertRaisesRegex(ValueError, 'Duplicate archive|Unsafe archive'):
                evidence.archive(dict(path=path.name, sha256=builder.sha(path)))
        with self.assertRaises(ValueError):
            builder.document(b'{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            builder.document(b'{"x":NaN}')

    def test_accepted_staging_is_external_additive_and_all_numeric_claims_resolve(self):
        report, _, _ = self.fixture.accept()
        before = {str(path.relative_to(self.fixture.repo)):builder.sha(path)
                  for path in self.fixture.repo.rglob('*') if path.is_file()}
        receipt = formatter.stage(self.fixture.repo, self.fixture.public, self.root/'stage')
        self.assertFalse(receipt['scientific_completion'])
        self.assertFalse(receipt['original_publication_gate_satisfied'])
        self.assertFalse(receipt['manuscript_installed'])
        self.assertEqual(receipt['scientific_calls'], 0)
        tex = (self.root/'stage'/formatter.TEX_LOCATION).read_text(encoding='utf-8')
        self.assertIn('Unavailable', tex)
        self.assertIn('original full-success publication gate remains unsatisfied', tex)
        self.assertIn('jointly training-refitted uninhibited comparator', tex)
        self.assertIn('common spatial and mark laws held fixed', tex)
        claims = builder.read(self.root/'stage/claims.additions.json')['claims']
        self.assertTrue(all(claim['id'].startswith('s04b-joint-disposition-') for claim in claims))
        for claim in claims:
            raw = verify_claims.resolve(report, claim['json_pointer'])
            self.assertIsNotNone(raw)
            self.assertTrue(verify_claims.equal_display(verify_claims.transformed(raw, claim, report), claim))
        after = {str(path.relative_to(self.fixture.repo)):builder.sha(path)
                 for path in self.fixture.repo.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_formatter_rejects_fabricated_incomplete_summary_even_with_repinned_acceptance(self):
        report, audit, acceptance = self.fixture.accept()
        row = next(row for row in report['regime_summary'] if row['regime'] == 5)
        row['full_regime'] = dict(N=19, mean_gain=0., median_gain=0., wins=0, wilson95=[0., 1.])
        row['statistics_available'] = True
        write(self.fixture.repo/self.fixture.public['report'], report)
        audit['report_sha256'] = builder.sha(self.fixture.repo/self.fixture.public['report'])
        audit['independent_summary'] = report['regime_summary']
        write(self.fixture.repo/self.fixture.public['audit'], audit)
        acceptance['artifact_sha256'] = {self.fixture.public[key]:builder.sha(self.fixture.repo/self.fixture.public[key])
                                         for key in ('report', 'audit')}
        write(self.fixture.repo/self.fixture.public['completion_review'], acceptance)
        with self.assertRaisesRegex(ValueError, 'Report differs'):
            formatter.validate(self.fixture.repo, self.fixture.public)

    def test_task2_and_task3_acceptance_and_separate_scientific_flags_remain_required(self):
        _, _, acceptance = self.fixture.accept()
        acceptance['tasks']['task2']['passed'] = False
        write(self.fixture.repo/self.fixture.public['completion_review'], acceptance)
        with self.assertRaisesRegex(ValueError, 'Incomplete task2'):
            formatter.validate(self.fixture.repo, self.fixture.public)
        acceptance['tasks']['task2']['passed'] = True
        acceptance['scientific_completion'] = True
        write(self.fixture.repo/self.fixture.public['completion_review'], acceptance)
        with self.assertRaisesRegex(ValueError, 'disposition acceptance'):
            formatter.validate(self.fixture.repo, self.fixture.public)

    def test_half_even_display_and_fresh_external_staging(self):
        report, _, _ = self.fixture.accept()
        report['regime_summary'][0]['full_regime'].update(mean_gain=-1e-10, median_gain=1.23445)
        _, claims = formatter.render(report, 'invented.json', 'a'*64)
        by_pointer = {claim['json_pointer']:claim for claim in claims}
        self.assertEqual(by_pointer['/regime_summary/0/full_regime/mean_gain']['display'], '0.0000')
        self.assertEqual(by_pointer['/regime_summary/0/full_regime/median_gain']['display'], '1.2344')
        with self.assertRaisesRegex(ValueError, 'Fresh external'):
            formatter.stage(self.fixture.repo, self.fixture.public, self.fixture.repo/'stage')
        target = self.fixture.repo/'paper/source'/formatter.TEX_LOCATION
        target.parent.mkdir(parents=True)
        target.write_text('Existing source', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'must not be replaced'):
            formatter.stage(self.fixture.repo, self.fixture.public, self.root/'stage')

    def test_contradictory_live_or_pending_flags_fail_even_after_hashes_are_repinned(self):
        _, audit, acceptance = self.fixture.accept()
        for field, value in (('live_agent_review', False), ('live_agent_review_performed', False),
                             ('final_batch_agent_review_required', True)):
            for target in ('audit', 'completion_review'):
                with self.subTest(field=field, target=target):
                    changed_audit, changed_acceptance = deepcopy(audit), deepcopy(acceptance)
                    changed = changed_audit if target == 'audit' else changed_acceptance
                    changed[field] = value
                    write(self.fixture.repo/self.fixture.public['audit'], changed_audit)
                    audit_pin = builder.sha(self.fixture.repo/self.fixture.public['audit'])
                    changed_acceptance['artifact_sha256'][self.fixture.public['audit']] = audit_pin
                    changed_acceptance['tasks']['task1']['acceptance']['sha256'] = audit_pin
                    write(self.fixture.repo/self.fixture.public['completion_review'], changed_acceptance)
                    with self.assertRaisesRegex(ValueError, 'live independent disposition acceptance'):
                        formatter.validate(self.fixture.repo, self.fixture.public)


if __name__ == '__main__':
    unittest.main()
