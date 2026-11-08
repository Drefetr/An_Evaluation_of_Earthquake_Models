"""Invented saved-output corruptions; no science/optimizer/native calls."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


A = module('remaining_output_audit_tested', ROOT/'experiments/s04b_joint_remaining_audit/check.py')
F = module('remaining_invented_fixture', ROOT/'tests/test_joint_output_audit.py')


def unknown_fixture(model='LI', index=3):
    protocol, report = F.fixture()
    order = list(A.ARMS)
    selected = order.index(model)
    report['fits'] = {name: report['fits'][name] for name in order[:selected+1]}
    report['training_checks'] = {name: report['training_checks'][name] for name in order[:selected]}
    report.update(passed=False, status='unknown', outcomes=[], error_type='ValueError',
                  error='Unresolved null starts' if model == 'null' else 'Unresolved alternative starts')
    for key in ('training_selections_frozen', 'test_checks', 'new_null_test', 'bic_threshold'):
        report.pop(key, None)
    report['floor_checks'] = [row for row in report['floor_checks'] if row['phase'] == 'train']
    fitted = report['fits'][model]
    original = copy.deepcopy(fitted['records'][index])
    primary = copy.deepcopy(original)
    primary.update(success=False, solver_success=False, solver_status=2)
    rescue = copy.deepcopy(primary)
    rescue.update(method='Powell', initial_parameters=primary['returned_parameters'],
                  nfev=5000, nit=22, solver_status=1,
                  message='Maximum number of function evaluations has been exceeded.')
    fitted.update(passed=False, status='unknown_starts',
                  records=fitted['records'][:index]+[primary, rescue],
                  candidates=fitted['candidates'][:index+1],
                  resolved_starts=[True]*index+[False], not_run_starts=list(range(index+1, 8)))
    for key in ('selected', 'selected_state_index', 'null_search_gaps'):
        fitted.pop(key)
    return protocol, report


def trace(path, report):
    rows = []
    for model in A.ARMS:
        for record in report['fits'].get(model, {}).get('records', []):
            rows.append(dict(event='attempt_start', model=model, start_index=record['start_index'],
                             method=record['method'], initial_parameters=record['initial_parameters'],
                             status='running', success=False))
            rows.append(dict(event='attempt_end', model=model, **record))
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
    report['attempts_sha256'] = A.sha(path)


class UnknownDisposition(unittest.TestCase):
    def check(self, report=None, protocol=None, phases=None):
        if report is None:
            protocol, report = unknown_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'attempts.jsonl'
            trace(path, report)
            return A.inspect_unknown(report, protocol, phases or [dict(start=30, end=395, returned=True)], path)

    def reject(self, mutate):
        protocol, report = unknown_fixture()
        mutate(report)
        with self.assertRaises((A.custody.AuditError, A.core.AuditError)):
            self.check(report, protocol)

    def test_finite_capped_return_remains_unknown(self):
        result = self.check()
        self.assertEqual(result['unknown_outcome_count'], 5)
        self.assertEqual(result['unresolved_start'], 3)
        self.assertEqual(result['not_run_models'], ['LIplus_immigrant', 'LIplus_inclusive'])

    def test_null_unknown_and_last_start_unknown(self):
        for model, index in [('null', 0), ('LIplus_inclusive', 7)]:
            with self.subTest(model=model):
                p, r = unknown_fixture(model, index)
                self.assertEqual(self.check(r, p)['unresolved_start'], index)

    def test_iteration_cap_supported(self):
        p, r = unknown_fixture()
        r['fits']['LI']['records'][-1].update(nfev=123, nit=400, solver_status=2)
        self.assertEqual(self.check(r, p)['terminal_nit'], 400)

    def test_technical_exception_not_unknown(self):
        self.reject(lambda r: r.update(error_type='KeyError', error='selected_state_index'))

    def test_arbitrary_value_error_not_unknown(self):
        self.reject(lambda r: r.update(error='Selected training quadrature/gradient check'))

    def test_noncap_solver_failure_rejected(self):
        self.reject(lambda r: r['fits']['LI']['records'][-1].update(nfev=100, solver_status=3))

    def test_extended_cap_rejected(self):
        self.reject(lambda r: r['fits']['LI']['records'][-1].update(nfev=5001))

    def test_nonfinite_return_rejected(self):
        self.reject(lambda r: r['fits']['LI']['records'][-1].update(finite_feasible=False))

    def test_original_fresh_score_gate_required(self):
        self.reject(lambda r: r['fits']['LI']['records'][-1].update(returned_nll=999))

    def test_selected_unknown_rejected(self):
        self.reject(lambda r: r['fits']['LI'].update(selected_state_index=0))

    def test_partial_candidate_substitution_rejected(self):
        self.reject(lambda r: r['fits']['LI']['candidates'].append(copy.deepcopy(r['fits']['LI']['candidates'][-1])))

    def test_missing_earlier_training_check_rejected(self):
        self.reject(lambda r: r['training_checks'].clear())

    def test_missing_historical_comparison_rejected(self):
        self.reject(lambda r: r['historical_comparisons'].pop())

    def test_test_phase_or_scoring_rejected(self):
        p, r = unknown_fixture()
        with self.assertRaises(A.custody.AuditError):
            self.check(r, p, [dict(start=30, end=395, returned=True), dict(start=395, end=760, returned=True)])
        self.reject(lambda r: r.update(new_null_test=F.score(-3)))
        self.reject(lambda r: r.update(outcomes=[dict(new_gain=0, new_win=False)]))

    def test_future_starts_not_relabelled_not_run(self):
        self.reject(lambda r: r['fits']['LI'].update(not_run_starts=[]))

    def test_changed_recipe_rejected(self):
        self.reject(lambda r: r['fits']['LI']['records'][0]['initial_parameters'].__setitem__(0, -11))

    def test_trace_loss_rejected(self):
        p, r = unknown_fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace'
            trace(path, r)
            path.write_text(path.read_text().splitlines()[0]+'\n')
            r['attempts_sha256'] = A.sha(path)
            with self.assertRaises(A.custody.AuditError):
                A.inspect_unknown(r, p, [dict(start=30, end=395, returned=True)], path)


class PlannedDenominator(unittest.TestCase):
    def test_unknown_stratum_has_no_summary(self):
        p, report = F.fixture()
        dispositions, reports = [], {}
        for i, case_id in enumerate(p['roster']):
            unknown = i == 25
            dispositions.append(dict(case_id=case_id, disposition='scientific_unknown' if unknown else 'complete'))
            if not unknown:
                reports[case_id] = copy.deepcopy(report)
        result = A.disposition_summary(dispositions, reports, p['roster'])
        for row in result:
            if row['regime'] == 5:
                self.assertEqual((row['complete_N'], row['unknown_N'], row['not_run_N']), (19, 1, 0))
                self.assertFalse(row['summary_available'])
                for key in ('mean_gain', 'median_gain', 'wins', 'win_fraction', 'wilson95'):
                    self.assertIsNone(row[key])
            else:
                self.assertTrue(row['summary_available'])
                self.assertEqual(row['complete_N'], 20)

    def test_not_run_is_not_unknown_or_loss(self):
        p, report = F.fixture()
        dispositions = [dict(case_id=k, disposition='complete') for k in p['roster'][:19]]
        rows = A.disposition_summary(dispositions, {k: report for k in p['roster'][:19]}, p['roster'])
        self.assertEqual((rows[0]['complete_N'], rows[0]['unknown_N'], rows[0]['not_run_N']), (19, 0, 1))
        self.assertIsNone(rows[0]['wins'])

    def test_duplicate_or_nonprefix_not_accepted(self):
        p, report = F.fixture()
        for keys in ([p['roster'][1]], [p['roster'][0], p['roster'][0]]):
            with self.subTest(keys=keys), self.assertRaises(A.custody.AuditError):
                A.disposition_summary([dict(case_id=k, disposition='complete') for k in keys], {k: report for k in keys}, p['roster'])


class CompactTransition(unittest.TestCase):
    def fixture(self, directory, unknown=False):
        p, report = F.fixture()
        sequence = p['roster'][:40]+[A.UNKNOWN_CASE]+p['roster'][41:]
        new_id = sequence[41]
        current = Path(directory)/'artifact/host/children/01_case'
        (current/'science/cases').mkdir(parents=True)
        (current/'supervision').mkdir()
        report.update(case_id=new_id)
        disposition = 'complete'
        if unknown:
            p, report = unknown_fixture()
            report['case_id'] = new_id
            disposition = 'scientific_unknown'
        result = dict(case_id=new_id, disposition=disposition, wall_seconds=3., numerical_attempt_id='fresh-attempt',
                      report_file='cases/current.json', trace_file='cases/current.attempts.jsonl')
        if unknown:
            result.update(unknown_reason={'invented':'original-cap'}, model_census={'invented':'not-run'},
                          terminal_solver_return=report['fits']['LI']['records'][-1])
        for path, value in [(current/'science/current-unused.json', {}),
                            (current/'science/cases/current.json', report),
                            (current/'science/result.json', result), (current/'supervision/result.json', {'passed':True})]:
            F.dump(path, value)
        (current/'science/cases/current.attempts.jsonl').write_text('invented retained trace\n')
        source = dict(kind='host_execution',execution_id='fresh-host')
        for key, path in dict(case_path=current/'science/cases/current.json', trace_path=current/'science/cases/current.attempts.jsonl',
                              result_path=current/'science/result.json',supervision_path=current/'supervision/result.json').items():
            source[key]=path.relative_to(current.parent.parent).as_posix()
            source[key.replace('_path','_sha256')]=A.sha(path)
        rows=[]
        for i, key in enumerate(sequence[:41]):
            rows.append(dict(case_id=key,disposition='complete' if i < 40 else 'scientific_unknown'))
        new=A.projection(report,disposition,source)
        if unknown:
            new.update(unknown_origin='new_frozen_solver_cap',unknown_reason=result['unknown_reason'],model_census=result['model_census'],
                       terminal_solver_return=result['terminal_solver_return'])
        ref=dict(scientific_indexed_seconds=1000.,known_prior_outer_overhead_seconds=1.,operational_failure_charge_seconds=290.,
                 operational_diagnostic_charge_seconds=80.,additional_workflow_overhead_seconds=94.6,
                 included_current_scientific_seconds=585.4,whole_workflow_bound_seconds=680.,accounted_base_seconds=1465.6)
        policy=dict(full_sequence=sequence,case_ids=sequence[41:],immutable_failure_reference=ref,original_native={'fixture':True},
                    case_slots=[dict(case_id=key,wall_seconds=1200)for key in sequence[41:]],
                    resources=dict(campaign_aggregate_seconds=115200,future_host_overhead_reserve_seconds=14400,
                                   global_finalization_reserve_seconds=1800))
        budget=dict(base_scientific_indexed_seconds=1000.,new_case_seconds=3.,scientific_indexed_seconds=1003.,
                    known_prior_outer_overhead_seconds=1.,operational_failure_charge_seconds=290.,operational_diagnostic_charge_seconds=80.,
                    pilot04_incremental_workflow_overhead_seconds=94.6,accounted_seconds=1468.6,remaining_case_slots_seconds=38*1200,
                    reserved_host_overhead_seconds=14400,global_finalization_reserve_seconds=1800,upper_bound_seconds=63268.6)
        index=dict(schema='joint_remaining_index_v1',passed=False,scientific_completion=False,
                   original_native=policy['original_native'],immutable_failure_reference=ref,records=rows+[new],
                   attempts=[dict(case_id=new_id,numerical_attempt_id='fresh-attempt',host_execution_id='fresh-host',
                                  seconds=3.,result_sha256=A.sha(current/'science/result.json'))],budget=budget)
        index['counts']=A.expected_counts(index['records'])
        return index, {'schema':'old_failed_index'}, rows, {}, result, report, current, policy

    def test_completed_or_unknown_advances_disposition_only(self):
        for unknown in (False,True):
            with self.subTest(unknown=unknown),tempfile.TemporaryDirectory()as d:
                args=self.fixture(d,unknown)
                A.inspect_transition(*args)
                self.assertFalse(args[0]['scientific_completion'])
                self.assertEqual(args[0]['counts']['unknown_histories'],2 if unknown else 1)
                self.assertEqual(args[0]['counts']['computed_outcomes'],200 if unknown else 205)

    def test_prefix_is_exact_not_merely_same_count(self):
        with tempfile.TemporaryDirectory()as d:
            args=self.fixture(d);args[0]['records'][3]=dict(args[0]['records'][3],disposition='scientific_unknown')
            with self.assertRaises(A.custody.AuditError):A.inspect_transition(*args)

    def test_unknown_cannot_be_success_or_scored_zero(self):
        for mutate in (lambda x:x.update(scientific_completion=True),
                       lambda x:x['records'][-1].update(outcomes=[{'new_gain':0,'new_win':False}])):
            with tempfile.TemporaryDirectory()as d:
                args=self.fixture(d,True);mutate(args[0])
                with self.assertRaises(A.custody.AuditError):A.inspect_transition(*args)

    def test_changed_case_payload_rejected_even_with_same_case_id(self):
        with tempfile.TemporaryDirectory()as d:
            args=self.fixture(d);args[0]['records'][-1]['outcomes']=[]
            with self.assertRaises(A.custody.AuditError):A.inspect_transition(*args)

    def test_repeat_failed_case_or_skip_next_case_rejected(self):
        for key in (A.UNKNOWN_CASE,'S7_seed19'):
            with tempfile.TemporaryDirectory()as d:
                args=self.fixture(d);args[0]['records'][-1]['case_id']=key
                with self.assertRaises(A.custody.AuditError):A.inspect_transition(*args)

    def test_charge_cannot_be_dropped_or_duplicated(self):
        for delta in (-585.4,680.):
            with tempfile.TemporaryDirectory()as d:
                args=self.fixture(d);args[0]['budget']['accounted_seconds']+=delta
                with self.assertRaises(A.core.AuditError):A.inspect_transition(*args)

    def test_unknown_count_cannot_be_treated_as_completed(self):
        with tempfile.TemporaryDirectory()as d:
            args=self.fixture(d,True);args[0]['counts']['computed_outcomes']=205
            with self.assertRaises(A.custody.AuditError):A.inspect_transition(*args)

    def test_attempt_and_evidence_hashes_required(self):
        for field in ('result_sha256','seconds'):
            with tempfile.TemporaryDirectory()as d:
                args=self.fixture(d);args[0]['attempts'][-1][field]='changed'
                with self.assertRaises(A.custody.AuditError):A.inspect_transition(*args)

    def test_recorded_linux_native_path_relocates_only_within_artifact(self):
        with tempfile.TemporaryDirectory()as d:
            current=Path(d)/'artifact/host/children/01';current.mkdir(parents=True)
            remote='/tmp/job/artifact/host/children/01/science'
            self.assertEqual(A.recorded_path('/tmp/job/artifact/build/native.so',remote,current),Path(d)/'artifact/build/native.so')
            with self.assertRaises(A.custody.AuditError):A.recorded_path('/etc/passwd',remote,current)

    def origin_fixture(self, directory):
        index,prior,rows,review,result,report,current,policy=self.fixture(directory)
        index.update(host_source_sha256={'fixture-host':'pin'},scientific_source_sha256={'fixture-science':'pin'},
                     protocol_sha256='policy-pin',predecessor=dict(index_sha256='prior-index',review_sha256='prior-review'))
        policy['actual_hosts']=[dict(host=1,case_ids=[result['case_id']])]
        policy['immutable_failure_reference'].update(index_sha256='prior-index',review_sha256='prior-review')
        grant=dict(mode='remaining_host_batch',batch_id=1,case_ids=[result['case_id']],numerical_attempt_id='fresh-host',
                   child_attempt_ids={result['case_id']:'fresh-attempt'},source_sha256=index['host_source_sha256'],
                   scientific_source_sha256=index['scientific_source_sha256'],protocol_sha256='policy-pin',
                   prior_index_sha256='prior-index',prior_review_sha256='prior-review')
        return index,prior,review,result,grant,policy

    def test_host_and_child_execution_ids_are_admitted(self):
        with tempfile.TemporaryDirectory()as d:
            A.inspect_host_origin(*self.origin_fixture(d))

    def test_agreeing_forged_host_strings_still_rejected(self):
        with tempfile.TemporaryDirectory()as d:
            args=self.origin_fixture(d)
            args[0]['records'][-1]['source']['execution_id']='same-forged-string'
            args[0]['attempts'][-1]['host_execution_id']='same-forged-string'
            with self.assertRaises(A.custody.AuditError):A.inspect_host_origin(*args)

    def test_next_host_cannot_reuse_automated_prior_review(self):
        with tempfile.TemporaryDirectory()as d:
            args=self.origin_fixture(d)
            args[4]['batch_id']=2;args[5]['actual_hosts'][0]['host']=2
            args[2].update(review_kind='automated_saved_output_check',live_agent_review=False)
            with self.assertRaises(A.custody.AuditError):A.inspect_host_origin(*args)


class FullCurrentEvidence(unittest.TestCase):
    def fixture(self, root, unknown=False):
        original=F.artifact_fixture(root)
        repo=Path(root)/'repo';science=A.read(repo/'experiments/s04b_joint_nuisance/protocol.json')
        case=A.read(repo/'reproduction/synthetic/input_manifest.json')['s04b']['cases'][0]
        case_id=case['case_id']
        artifact=Path(root)/'retained';current=artifact/'host/children/01_case'
        (current/'science/cases').mkdir(parents=True);(current/'supervision').mkdir()
        (artifact/'build').mkdir()
        for src,dest in [(original['library_path'],artifact/'build/attenuation.so'),(original['build_path'],artifact/'build/build_receipt.json')]:
            dest.write_bytes(src.read_bytes())
        report=A.read(original['results']/(case_id+'.json'))
        if unknown:
            _, partial=unknown_fixture()
            for key in ('fits','training_checks','floor_checks','outcomes','passed','status','error_type','error'):
                report[key]=partial[key]
            for key in ('training_selections_frozen','test_checks','new_null_test','bic_threshold'):
                report.pop(key,None)
        report.update(prior_training_attempt_seconds=0.,current_attempt_wall_seconds=.4,wall_seconds=.4)
        source={'experiments/s04b_joint_nuisance/run.py':A.sha(repo/'experiments/s04b_joint_nuisance/run.py')}
        config=dict(run_id='invented-run',deadline_utc='2099-01-01T00:00:00+00:00')
        policy=dict(case_ids=[case_id],immutable_failure_reference={'permanent_unknown':True},
                    original_native=dict(runtime_essential={'invented':True},library_sha256=A.sha(artifact/'build/attenuation.so'),
                                         build_receipt_sha256=A.sha(artifact/'build/build_receipt.json')),
                    shared_run=dict(run_id='invented-run',config_sha256='invented-config'),
                    case_slots=[dict(case_id=case_id,wall_seconds=1200,scientific_seconds=1170)])
        F.dump(repo/'experiments/s04b_joint_remaining/protocol.json',policy)
        admission=dict(mode='untouched_remaining_case',case_id=case_id,case_ids=[case_id],source_sha256=source,
                       protocol_sha256=A.sha(repo/'experiments/s04b_joint_remaining/protocol.json'),numerical_attempt_id='invented-attempt',
                       wall_seconds=1200,independent_review_passed=True,external_supervision=True,threads=2,workers=1,
                       sampled_process_tree_rss_cap_bytes=6442450944,minimum_host_free_bytes=2147483648,
                       operational_run_id='invented-run',operational_run_config_sha256='invented-config',expires_utc=config['deadline_utc'],
                       **{k:policy['original_native'][k]for k in ('library_sha256','build_receipt_sha256')})
        F.dump(current/'admission.json',admission)
        F.dump(repo/'source_review.json',dict(passed=True,live_agent_review=True,reviewed_files_sha256=source))
        source_review_pin=A.sha(repo/'source_review.json')
        F.dump(current/'conductor_review.json',dict(reviewed_files_sha256=source,source_review_record='source_review.json',
               source_review_sha256=source_review_pin,host_source_review_sha256=source_review_pin))
        result=dict(schema='joint_remaining_case_result_v1',case_id=case_id,handled=True,disposition_valid=True,
                    status='terminal_disposition',source_sha256=source,admission_sha256=A.sha(current/'admission.json'),
                    protocol_sha256=admission['protocol_sha256'],immutable_failure_reference=policy['immutable_failure_reference'],
                    runtime=dict(essential=policy['original_native']['runtime_essential']),numerical_attempt_id='invented-attempt',
                    allocation=policy['case_slots'][0],wall_seconds=.6,input_case=case,original_case_status='complete',original_case_error={},
                    report_file='cases/'+case_id+'.json',trace_file='cases/'+case_id+'.attempts.jsonl',
                    disposition='complete',passed=True,scientific_passed=True,unknown_outcome_count=0,
                    phase_constructions=[dict(start=30,end=395,returned=True),dict(start=395,end=760,returned=True)],
                    model_census=dict(attempted_models=list(A.ARMS),completed_models=list(A.ARMS),not_run_models=[],
                                      logical_optimizer_attempts=32,held_out_phase_constructed=True),
                    **{k:admission[k]for k in ('library_sha256','build_receipt_sha256')})
        if unknown:
            failed=report['fits']['LI']
            result.update(disposition='scientific_unknown',passed=False,scientific_passed=False,unknown_outcome_count=5,
                          original_case_status='unknown',original_case_error={key:report[key]for key in ('error_type','error')},
                          terminal_solver_return=failed['records'][-1],
                          unknown_reason=dict(error_type=report['error_type'],error=report['error'],arm_status=failed['status']),
                          phase_constructions=[dict(start=30,end=395,returned=True)],
                          model_census=dict(attempted_models=['null','LI'],completed_models=['null'],
                                            not_run_models=['LIplus_immigrant','LIplus_inclusive'],logical_optimizer_attempts=13,
                                            held_out_phase_constructed=False,unresolved_model='LI',unresolved_start=3,
                                            resolved_starts=[True]*3+[False],not_run_starts=[4,5,6,7]))
        trace(current/'science'/result['trace_file'],report)
        F.dump(current/'science'/result['report_file'],report)
        result.update(report_sha256=A.sha(current/'science'/result['report_file']),trace_sha256=A.sha(current/'science'/result['trace_file']))
        F.dump(current/'science/result.json',result)
        remote='/tmp/worker/artifact'
        command=['python','-B','-m','experiments.s04b_joint_remaining.case_driver','--case-id',case_id,
                 '--output',remote+'/host/children/01_case/science','--admission',remote+'/host/children/01_case/admission.json',
                 '--library',remote+'/build/attenuation.so','--build-receipt',remote+'/build/build_receipt.json']
        spec=dict(command=command,wall_cap_seconds=1200,rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
                  env={k:'2'for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
        F.dump(current/'supervisor_spec.json',spec)
        (current/'supervision/execution.log').write_text('invented output\n')
        path=repo/'scripts/supervise_research.py';path.parent.mkdir();path.write_text('# opaque constructed source\n')
        supervision=dict(status='passed',returncode=0,launched=True,stop_reason=None,cleanup_errors=[],survivors_after_cleanup=[],
                         spec_sha256=A.sha(current/'supervisor_spec.json'),execution_log_sha256=A.sha(current/'supervision/execution.log'),
                         supervisor_sha256=A.sha(path),started_utc='2098-01-01T00:00:00+00:00',finished_utc='2098-01-01T00:00:01+00:00',
                         execution_wall_seconds=1.,sampled_peak_tree_rss_bytes=10000,minimum_sampled_host_available_bytes=4000000000)
        F.dump(current/'supervision/result.json',supervision)
        return current,repo,policy,science,config,'invented-commit',{}

    def test_whole_current_payload_and_relocated_native(self):
        with tempfile.TemporaryDirectory()as d,patch.object(A.custody,'verify_reviewed_sources'):
            args=self.fixture(d)
            result,report,unknown=A.inspect_current(*args)
            self.assertEqual(result['disposition'],'complete')
            self.assertEqual(len(report['outcomes']),5)
            self.assertIsNone(unknown)

    def test_whole_current_unknown_has_no_comparison(self):
        with tempfile.TemporaryDirectory()as d,patch.object(A.custody,'verify_reviewed_sources'):
            result,report,unknown=A.inspect_current(*self.fixture(d,True))
            self.assertFalse(result['scientific_passed'])
            self.assertEqual(report['outcomes'],[])
            self.assertEqual(unknown['unknown_outcome_count'],5)

    def test_custody_resource_and_census_corruptions_fail(self):
        for file,field,value in [('science/result.json','trace_sha256','wrong'),
                                 ('science/result.json','handled',False),
                                 ('science/result.json','model_census',{}),
                                 ('supervision/result.json','survivors_after_cleanup',[1234]),
                                 ('supervision/result.json','execution_wall_seconds',1201)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory()as d,patch.object(A.custody,'verify_reviewed_sources'):
                args=self.fixture(d);path=args[0]/file;payload=A.read(path);payload[field]=value;F.dump(path,payload)
                with self.assertRaises((A.custody.AuditError,A.core.AuditError)):
                    A.inspect_current(*args)


if __name__ == '__main__':
    unittest.main()
