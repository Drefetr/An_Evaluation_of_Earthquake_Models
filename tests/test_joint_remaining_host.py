"""Constructed host/custody controls; no scientific/native execution."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('remaining_host_tested', ROOT/'experiments/s04b_joint_remaining/host.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)


def report(name, complete=True):
    return dict(case_id=name,regime=5,seed=int(name.rsplit('seed',1)[1]),n_train=7,n_test=3,thinning={'rejected':0},
        outcomes=[dict(model='invented',gate=str(i),new_gain=.1) for i in range(5)] if complete else [],
        fits={'null':dict(passed=True,records=[dict(success=True)],null_search_gaps=[]),
              'LI':dict(passed=complete,records=[dict(success=complete)],**({'null_search_gaps':[]} if complete else {}))})


def base_records(p):
    rows=[]
    for i,name in enumerate(p['full_sequence'][:41]):
        rows.append(H.projection(report(name,i<40),'complete' if i<40 else 'scientific_unknown',{'kind':'fixture'}))
    return rows


class HostControls(unittest.TestCase):
    def setUp(self):
        self.p=H.read(ROOT/'experiments/s04b_joint_remaining/protocol.json')
        self.t=tempfile.TemporaryDirectory();self.d=Path(self.t.name)
        self.addCleanup(self.t.cleanup)

    def test_actual_protocol_metadata_only(self):
        p=H.verify_protocol()
        self.assertEqual(len(p['case_ids']),39)
        self.assertEqual([len(r['case_ids']) for r in p['actual_hosts']],[1,4,5,5,5,8,8,3])

    def test_original_failure_charged_once(self):
        b=H.budget(self.p,[])
        self.assertAlmostEqual(b['accounted_seconds'],22764.885916780003)
        self.assertAlmostEqual(b['upper_bound_seconds'],109524.885916780003)
        self.assertLess(b['upper_bound_seconds'],115200)
        self.assertEqual(b['operational_failure_charge_seconds'],290)
        self.assertEqual(b['operational_diagnostic_charge_seconds'],80)

    def test_new_actual_time_replaces_reserved_slot(self):
        a=[dict(case_id=self.p['case_ids'][0],numerical_attempt_id='new',seconds=20.)]
        b=H.budget(self.p,a)
        self.assertEqual(b['new_case_seconds'],20.)
        self.assertEqual(b['remaining_case_slots_seconds'],70560-1200)
        self.assertEqual(b['reserved_host_overhead_seconds'],14400)

    def test_no_repeat_or_skip_or_oversized_time(self):
        name=self.p['case_ids'][0]
        a=dict(case_id=name,numerical_attempt_id='id',seconds=1)
        for rows in ([a,a],[dict(a,case_id=self.p['case_ids'][1])],[dict(a,seconds=1201)],[dict(a,seconds=float('nan'))]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):H.budget(self.p,rows)

    def test_unknown_has_no_absent_arm_diagnostics(self):
        r=H.projection(report(self.p['case_ids'][0],False),'scientific_unknown',{})
        self.assertEqual(r['null_search_gap_by_arm'],{'null':False})
        self.assertEqual(r['optimizer_failed_attempts_by_arm'],{'null':0,'LI':1})
        self.assertNotIn('LIplus_inclusive',r['optimizer_failed_attempts_by_arm'])
        self.assertEqual(r['outcomes'],[])

    def test_counts_do_not_impute_unknown_outcomes(self):
        c=H.counts(base_records(self.p))
        self.assertEqual(c,dict(processed_histories=41,complete_histories=40,unknown_histories=1,
                               unattempted_histories=39,computed_outcomes=200))
        rows=base_records(self.p);rows[-1]['outcomes']=[{'score':0}]
        with self.assertRaises(ValueError):H.counts(rows)

    def test_complete_slot_required_after_preparation(self):
        now=dt.datetime.now(dt.timezone.utc);group=self.p['actual_hosts'][0]
        H.timing(self.p,group,(now-dt.timedelta(seconds=10)).isoformat(),0,1200,now)
        with self.assertRaises(ValueError):H.timing(self.p,group,(now-dt.timedelta(seconds=1100)).isoformat(),0,1200,now)
        with self.assertRaises(ValueError):H.timing(self.p,group,(now+dt.timedelta(seconds=1)).isoformat(),0,1200,now)

    def first_admission(self):
        name=self.p['case_ids'][0];ref=self.p['immutable_failure_reference']
        return dict(batch_id=1,case_ids=[name],prior_index_sha256=ref['index_sha256'],
            prior_review_sha256=ref['review_sha256'],numerical_attempt_id='lease',
            child_attempt_ids={name:'lease-case-042'})

    def test_first_host_is_only_exact_untouched_pilot(self):
        a=self.first_admission();index=dict(last_attempt_passed=False,cases=[{'case_id':n} for n in self.p['full_sequence'][:40]])
        review=dict(audit_passed=True,passed=False)
        self.assertEqual(H.next_cases(self.p,a,index,review)['case_ids'],self.p['case_ids'][:1])
        for mutate in (lambda x:x['case_ids'].append(self.p['case_ids'][1]),
                       lambda x:x.update(prior_index_sha256='wrong'),
                       lambda x:x['child_attempt_ids'].update({self.p['case_ids'][0]:'reused'})):
            wrong=copy.deepcopy(a);mutate(wrong)
            with self.assertRaises(ValueError):H.next_cases(self.p,wrong,index,review)

    def test_second_host_requires_live_pilot_review(self):
        name=self.p['case_ids'][0];rows=base_records(self.p)+[H.projection(report(name),'complete',{})]
        attempts=[dict(case_id=name,numerical_attempt_id='first',seconds=20)]
        a=dict(batch_id=2,case_ids=self.p['actual_hosts'][1]['case_ids'],protocol_sha256='p',source_sha256={},
               scientific_source_sha256={},prior_index_sha256='i',numerical_attempt_id='two',child_attempt_ids={})
        a['child_attempt_ids']={n:'two-case-%03d'%(self.p['full_sequence'].index(n)+1) for n in a['case_ids']}
        index=dict(schema='joint_remaining_index_v1',protocol_sha256='p',host_source_sha256={},scientific_source_sha256={},
            original_native=self.p['original_native'],immutable_failure_reference=self.p['immutable_failure_reference'],
            passed=False,scientific_completion=False,records=rows,attempts=attempts,budget=H.budget(self.p,attempts),counts=H.counts(rows))
        review=dict(audit_passed=True,disposition_valid=True,index_sha256='i',live_agent_review=False,final_batch_agent_review_required=True)
        with self.assertRaises(ValueError):H.next_cases(self.p,a,index,review)
        review.update(live_agent_review=True,final_batch_agent_review_required=False,review_kind='live_agent_saved_output_review')
        self.assertEqual(H.next_cases(self.p,a,index,review)['host'],2)
        index['records'][40]['scientific_passed']=True
        with self.assertRaises(ValueError):H.next_cases(self.p,a,index,review)

    def test_third_host_also_requires_live_review(self):
        names=self.p['case_ids'][:5]
        rows=base_records(self.p)+[H.projection(report(n),'complete',{}) for n in names]
        attempts=[dict(case_id=n,numerical_attempt_id='first'+str(i),seconds=20) for i,n in enumerate(names)]
        a=dict(batch_id=3,case_ids=self.p['actual_hosts'][2]['case_ids'],protocol_sha256='p',source_sha256={},
               scientific_source_sha256={},prior_index_sha256='i',numerical_attempt_id='three')
        a['child_attempt_ids']={n:'three-case-%03d'%(self.p['full_sequence'].index(n)+1) for n in a['case_ids']}
        index=dict(schema='joint_remaining_index_v1',protocol_sha256='p',host_source_sha256={},scientific_source_sha256={},
            original_native=self.p['original_native'],immutable_failure_reference=self.p['immutable_failure_reference'],
            passed=False,scientific_completion=False,records=rows,attempts=attempts,budget=H.budget(self.p,attempts),counts=H.counts(rows))
        review=dict(audit_passed=True,disposition_valid=True,index_sha256='i',live_agent_review=False,
                    final_batch_agent_review_required=True,review_kind='automated_saved_output_check')
        with self.assertRaises(ValueError):H.next_cases(self.p,a,index,review)

    def case_files(self,complete):
        out=self.d/'host';current=out/'children'/'01_fixture';(current/'science/cases').mkdir(parents=True)
        (current/'supervision').mkdir()
        name=self.p['case_ids'][0];r=report(name,complete)
        case=current/'science/cases/case.json';trace=current/'science/cases/trace.jsonl'
        H.write(case,r);trace.write_bytes(b'{"fixture":true}\n');H.write(current/'supervision/result.json',{'status':'passed'})
        a=dict(scientific_source_sha256={'fixture':'pin'},source_sha256={},protocol_sha256='p',
               numerical_attempt_id='host',child_attempt_ids={name:'host-case-042'},prior_archive_sha256='oldzip',prior_artifact_id=5)
        actual=dict(schema='joint_remaining_case_result_v1',case_id=name,handled=True,disposition_valid=True,status='terminal_disposition',
            disposition='complete' if complete else 'scientific_unknown',passed=complete,scientific_passed=complete,
            source_sha256=a['scientific_source_sha256'],protocol_sha256='p',numerical_attempt_id='host-case-042',
            report_file='cases/case.json',report_sha256=H.sha(case),trace_file='cases/trace.jsonl',trace_sha256=H.sha(trace),
            wall_seconds=20,unknown_reason={'arm_status':'unknown_starts'},model_census={'not_run_models':['LIplus_inclusive']},
            terminal_solver_return={'nfev':5000})
        H.write(current/'science/result.json',actual)
        old=self.d/'prior.json';rev=self.d/'review.json';H.write(old,{});H.write(rev,{})
        return out,current,a,actual,old,rev

    def test_candidate_complete_and_unknown_exact_schema(self):
        out,c,a,actual,prior,rev=self.case_files(False)
        candidate=H.append_candidate(self.p,a,dict(records=base_records(self.p),attempts=[]),c,out,prior,rev)
        row=candidate['records'][-1]
        self.assertEqual(row['unknown_origin'],'new_frozen_solver_cap')
        self.assertEqual(row['terminal_solver_return'],actual['terminal_solver_return'])
        self.assertFalse(candidate['passed']);self.assertFalse(candidate['scientific_completion'])
        self.assertEqual(candidate['counts']['unknown_histories'],2)
        self.assertEqual(candidate['counts']['computed_outcomes'],200)
        self.assertEqual(candidate['attempts'][0]['seconds'],20)
        self.assertEqual(row['source']['result_path'],'children/01_fixture/science/result.json')

    def test_local_predecessor_is_not_falsely_attributed_to_prior_zip(self):
        out,c,a,actual,prior,rev=self.case_files(True)
        local=out/'earlier_index.json';H.write(local,{})
        candidate=H.append_candidate(self.p,a,dict(records=base_records(self.p),attempts=[]),c,out,local,rev)
        self.assertEqual(candidate['predecessor']['index_sha256'],H.sha(local))
        self.assertIsNone(candidate['predecessor']['archive_sha256'])
        self.assertIsNone(candidate['predecessor']['artifact_id'])
        external=H.append_candidate(self.p,a,dict(records=base_records(self.p),attempts=[]),c,out,prior,rev)
        self.assertEqual(external['predecessor']['archive_sha256'],'oldzip')

    def test_failed_or_misattributed_result_cannot_advance(self):
        out,c,a,actual,prior,rev=self.case_files(True)
        for updates in ({'handled':False},{'disposition_valid':False},{'disposition':'technical_failure'},
                        {'passed':False},{'source_sha256':{}},{'numerical_attempt_id':'other'}):
            H.write(c/'science/result.json',dict(actual,**updates))
            with self.subTest(updates=updates),self.assertRaises(ValueError):
                H.append_candidate(self.p,a,dict(records=base_records(self.p),attempts=[]),c,out,prior,rev)

    def test_checker_receipt_actual_interface_and_rejections(self):
        candidate=self.d/'index.json';H.write(candidate,{})
        path=self.d/'review.json';pins={'checker':'hash'}
        receipt=dict(audit_passed=True,disposition_valid=True,index_sha256=H.sha(candidate),live_agent_review=False,
            live_agent_review_performed=False,scientific_completion=False,final_batch_agent_review_required=True,
            checker_sources_sha256=pins,checker_source_review_sha256='review')
        H.write(path,receipt);H.check_receipt(path,candidate,pins,'review')
        for changes in ({'checker_sources_sha256':{}},{'scientific_completion':True},{'live_agent_review_performed':True},
                        {'index_sha256':'different'},{'disposition_valid':False}):
            H.write(path,dict(receipt,**changes))
            with self.subTest(changes=changes),self.assertRaises(ValueError):H.check_receipt(path,candidate,pins,'review')
        broken=receipt.copy();broken['checker_source_sha256']=broken.pop('checker_sources_sha256');H.write(path,broken)
        with self.assertRaises(ValueError):H.check_receipt(path,candidate,pins,'review')

    def test_path_escape_rejected(self):
        for value in ('../escape','/absolute','C:/machine','bad\\path'):
            with self.subTest(value=value),self.assertRaises(ValueError):H.safe(self.d,value)

    def test_child_admission_does_not_resume_old_case(self):
        a=self.first_admission();a.update(protocol_sha256='pin',expires_utc=self.p['shared_run']['expires_utc'],rss_cap_bytes=6442450944,
            host_headroom_bytes=2147483648,lease_token_sha256='lease',library_sha256='lib',build_receipt_sha256='build')
        name=self.p['case_ids'][0];child=H.child_admission(a,self.p,{},name,self.p['case_slots'][0])
        self.assertEqual(child['mode'],'untouched_remaining_case');self.assertEqual(child['case_ids'],[name])
        self.assertNotIn('prior_index',child);self.assertNotIn('resume',child)

    def test_supervisor_failure_blocks_before_saved_result(self):
        with patch.object(H.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(ValueError):H.supervised(['fixture'],self.d/'supervision',10,
                dict(rss_cap_bytes=100,host_headroom_bytes=10),{},self.d/'spec.json')

    def execute_fixture(self,complete=True,checker_passes=True):
        p=copy.deepcopy(self.p);name=p['case_ids'][0]
        prior=self.d/'prior.json';review=self.d/'prior_review.json';config=self.d/'config.json'
        H.write(prior,dict(last_attempt_passed=False,cases=[{'case_id':n} for n in p['full_sequence'][:40]]))
        H.write(review,dict(passed=False,audit_passed=True));H.write(config,{})
        p['immutable_failure_reference'].update(index_sha256=H.sha(prior),review_sha256=H.sha(review))
        p['shared_run']['config_sha256']=H.sha(config)
        native=self.d/'native.so';native.write_bytes(b'invented, never loaded')
        build=self.d/'build.json';H.write(build,{})
        p['original_native'].update(library_sha256=H.sha(native),build_receipt_sha256=H.sha(build))
        token='fixture-lease';source_review=self.d/'source_review.json';checker_review=self.d/'checker_review.json'
        H.write(source_review,{});H.write(checker_review,{})
        a=self.first_admission();a.update(mode='remaining_host_batch',source_sha256=H.source_identity(),scientific_source_sha256={},
            protocol_sha256=H.sha(H.HERE/'protocol.json'),scientific_protocol_sha256=p['scientific_protocol_sha256'],
            host_batch_source_review_passed=True,checker_source_review_passed=True,shared_run=p['shared_run'],
            expires_utc=p['shared_run']['expires_utc'],rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
            lease_token_sha256=H.hashlib.sha256(token.encode()).hexdigest(),library_sha256=H.sha(native),build_receipt_sha256=H.sha(build),
            prior_index_sha256=H.sha(prior),prior_review_sha256=H.sha(review),execution_window_seconds=2400,
            source_review_sha256=H.sha(source_review),checker_source_review_sha256=H.sha(checker_review),
            host_started_utc=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=1)).isoformat(),conductor_review={},
            source_commit='fixture',prior_archive_sha256='old',prior_artifact_id=None)
        admission=self.d/'admission.json';H.write(admission,a)
        args=SimpleNamespace(output=self.d/'host',admission=admission,prior_index=prior,prior_review=review,config=config,
            source_review=source_review,checker_review=checker_review,library=native,build_receipt=build)
        calls=[];pins={'fixture_checker':'pin'}
        def fake(command,output,cap,admitted,env,spec_path):
            calls.append(command);output.mkdir(parents=True);H.write(spec_path,{'command':command})
            H.write(output/'result.json',dict(status='passed',returncode=0,cleanup_errors=[],survivors_after_cleanup=[]))
            if 'experiments.s04b_joint_remaining.case_driver' in command:
                science=Path(command[command.index('--output')+1]);(science/'cases').mkdir(parents=True)
                case=science/'cases/case.json';trace=science/'cases/trace.jsonl'
                H.write(case,report(name,complete));trace.write_bytes(b'{"fixture":true}\n')
                H.write(science/'result.json',dict(schema='joint_remaining_case_result_v1',case_id=name,handled=True,
                    disposition_valid=True,status='terminal_disposition',disposition='complete' if complete else 'scientific_unknown',
                    passed=complete,scientific_passed=complete,source_sha256={},protocol_sha256=a['protocol_sha256'],
                    numerical_attempt_id=a['child_attempt_ids'][name],report_file='cases/case.json',report_sha256=H.sha(case),
                    trace_file='cases/trace.jsonl',trace_sha256=H.sha(trace),wall_seconds=0.0001,
                    unknown_reason={'arm_status':'unknown_starts'},model_census={'not_run_models':['LIplus_inclusive']},
                    terminal_solver_return={'nfev':5000}))
            else:
                child=Path(command[command.index('--current')+1]);receipt=Path(command[command.index('--output')+1])
                # Checker sees a durable candidate before any host index is promoted.
                self.assertTrue((child/'index.json').is_file());self.assertFalse((args.output/'index.json').exists())
                H.write(receipt,dict(audit_passed=checker_passes,disposition_valid=True,index_sha256=H.sha(child/'index.json'),
                    live_agent_review=False,live_agent_review_performed=False,scientific_completion=False,
                    final_batch_agent_review_required=True,checker_sources_sha256=pins,checker_source_review_sha256=H.sha(checker_review)))
            return H.read(output/'result.json')
        with patch.object(H,'verify_protocol',return_value=p),patch.object(H,'load_driver',return_value=SimpleNamespace(source_identity=lambda:{})),\
             patch.object(H,'check_source_reviews',return_value=pins),patch.object(H,'initial_records',return_value=base_records(p)),\
             patch.object(H,'supervised',side_effect=fake),patch.dict(H.os.environ,{'JOINT_NUMERICAL_LEASE_TOKEN':token}):
            code=H.run(args)
        return code,args.output,calls

    def test_whole_host_fixture_complete_promotes_only_after_checker(self):
        code,out,calls=self.execute_fixture()
        self.assertEqual(code,0);self.assertEqual(len(calls),2)
        result=H.read(out/'result.json');self.assertTrue(result['host_execution_passed']);self.assertFalse(result['passed'])
        self.assertFalse(result['scientific_completion']);self.assertEqual(result['counts']['computed_outcomes'],205)
        child=out/result['children'][0]['artifact']
        self.assertEqual((out/'index.json').read_bytes(),(child/'index.json').read_bytes())
        self.assertFalse(list(out.rglob('*.zip')));self.assertFalse(list(out.rglob('*.so')))

    def test_whole_host_fixture_unknown_stays_unknown(self):
        code,out,calls=self.execute_fixture(False)
        self.assertEqual(code,0);result=H.read(out/'result.json')
        self.assertTrue(result['host_execution_passed']);self.assertEqual(result['counts']['unknown_histories'],2)
        self.assertEqual(result['counts']['computed_outcomes'],200)
        self.assertFalse(result['children'][0]['scientific_passed'])

    def test_whole_host_fixture_checker_rejection_retains_unpromoted_candidate(self):
        code,out,calls=self.execute_fixture(checker_passes=False)
        self.assertEqual(code,1);result=H.read(out/'result.json')
        self.assertFalse(result['host_execution_passed']);self.assertEqual(result['children'],[])
        self.assertFalse((out/'index.json').exists())
        self.assertTrue((out/result['failed_child']['artifact']/'index.json').exists())


if __name__=='__main__':unittest.main()
