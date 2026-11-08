"""Invented host/custody fixtures; never launch a process or scientific call."""
import copy
import datetime as dt
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from experiments.s04b_exposure_refinement import host as H
from experiments.s04b_joint_remaining import host as original


def report(name,complete=True):
    return dict(case_id=name,regime=6,seed=int(name.rsplit('seed',1)[1]),n_train=7,n_test=3,thinning={},
        outcomes=[dict(model='invented',gate=str(i),new_gain=.1) for i in range(5)] if complete else [],
        fits={'null':dict(passed=True,records=[dict(success=True)],null_search_gaps=[]),
              'LI':dict(passed=complete,records=[dict(success=complete)],**({'null_search_gaps':[]} if complete else {}))})


def records(p,n):
    return [original.projection(report(name,i!=40),'complete' if i!=40 else 'scientific_unknown',{'kind':'fixture'})
            for i,name in enumerate(p['full_sequence'][:n])]


class HostControls(unittest.TestCase):
    def setUp(self):
        self.p=H.read(H.HERE/'protocol.json');self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_actual_protocol_metadata_and_fixed_roster_only(self):
        p=H.verify_protocol();self.assertEqual(p['case_ids'],p['full_sequence'][44:]);self.assertEqual(len(p['case_ids']),36)
        self.assertEqual(p['case_slots'][0]['scientific_seconds'],1776);self.assertEqual(p['case_slots'][0]['wall_seconds'],1806)
        self.assertNotIn('S5_broad_long_imm_seed410518',p['case_ids']);self.assertEqual(len(p['resources']['future_hosts']),8)
    def test_original_charges_and_conservative_reservations_are_not_repeated(self):
        b=H.budget(self.p,[])
        self.assertEqual(b['base_accounted_seconds'],float(self.p['resources']['accounted_seconds']))
        self.assertEqual(b['remaining_case_slots_seconds'],64926);self.assertEqual(b['all_eight_host_overhead_reserved_seconds'],14400)
        self.assertLess(b['upper_bound_seconds'],115200)
        a=dict(case_id=self.p['partial_case_id'],seconds=100.,outer_seconds=101.)
        c=H.budget(self.p,[a]);self.assertEqual(c['accounted_seconds']-b['accounted_seconds'],101.)
        self.assertEqual(c['remaining_case_slots_seconds'],64926-1806)
    def test_strict_partial_new_and_cumulative_caps_no_added_slack(self):
        a=dict(case_id=self.p['partial_case_id'],seconds=1776.,outer_seconds=1806.)
        H.budget(self.p,[a])
        for mutation in ({'seconds':1776.001},{'outer_seconds':1806.001},{'outer_seconds':float('nan')},{'seconds':-1}):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):H.budget(self.p,[dict(a,**mutation)])
        bad=copy.deepcopy(self.p);bad['resources']['partial_case_original_outer_seconds']='715'
        with self.assertRaisesRegex(ValueError,'Cumulative'):H.budget(bad,[a])
    def test_new_host_boundary_always_requires_live_prior_review(self):
        p=self.p;names=p['resources']['future_hosts'][2]['case_ids'];source={};attempts=[dict(case_id=n,seconds=1.,outer_seconds=2.) for n in p['case_ids'][:2]]
        a=dict(batch_id=3,case_ids=names,child_attempt_ids={n:'new'+str(i) for i,n in enumerate(names)},protocol_sha256='p',source_sha256=source,scientific_source_sha256=source,prior_index_sha256='i',prior_archive_sha256='a')
        index=dict(schema='joint_exposure_refinement_index_v1',protocol_sha256='p',host_source_sha256=source,scientific_source_sha256=source,records=records(p,46),attempts=attempts,budget=H.budget(p,attempts))
        review=dict(passed=True,audit_passed=True,review_kind='live_agent_saved_output_review',live_agent_review=True,final_batch_agent_review_required=False,index_sha256='i',artifact_sha256='a')
        H.next_cases(p,a,index,review)
        for key,value in [('live_agent_review',False),('final_batch_agent_review_required',True),('artifact_sha256','wrong')]:
            with self.assertRaises(ValueError):H.next_cases(p,a,index,dict(review,**{key:value}))
        index['records'][44]['disposition']='scientific_unknown'
        with self.assertRaisesRegex(ValueError,'Partial pilot'):H.next_cases(p,a,index,review)
    def test_complete_case_and_checker_reservation_must_remain_after_preparation(self):
        now=dt.datetime.now(dt.timezone.utc);g=self.p['resources']['future_hosts'][0]
        a=dict(host_started_utc=(now-dt.timedelta(seconds=1)).isoformat(),expires_utc=(now+dt.timedelta(hours=2)).isoformat(),execution_window_seconds=g['whole_host_upper_seconds']-600)
        H.timing(self.p,g,a,1806,now)
        with self.assertRaises(ValueError):H.timing(self.p,g,dict(a,host_started_utc=(now-dt.timedelta(seconds=1100)).isoformat()),1806,now)
        with self.assertRaises(ValueError):H.timing(self.p,g,dict(a,expires_utc=(now+dt.timedelta(seconds=1900)).isoformat()),1806,now)
    def fixture(self,batch=1,complete=True,checker_passes=True):
        p=copy.deepcopy(self.p);g=p['resources']['future_hosts'][batch-1];names=g['case_ids']
        prefix=44+sum(len(v['case_ids']) for v in p['resources']['future_hosts'][:batch-1])
        prior=self.root/'prior.json';review=self.root/'prior_review.json';config=self.root/'config.json'
        attempted=[dict(case_id=n,seconds=1.,outer_seconds=2.) for n in p['case_ids'][:prefix-44]]
        old=dict(schema='joint_remaining_index_v1' if batch==1 else 'joint_exposure_refinement_index_v1',records=records(p,prefix),attempts=attempted,
                 protocol_sha256=H.sha(H.HERE/'protocol.json'),host_source_sha256={},scientific_source_sha256={},budget=H.budget(p,attempted))
        H.write(prior,old);H.write(config,{})
        r=dict(passed=False,audit_passed=True,accepted_completed_prefix=True) if batch==1 else dict(passed=True,audit_passed=True,live_agent_review=True,
            review_kind='live_agent_saved_output_review',final_batch_agent_review_required=False,index_sha256=H.sha(prior),artifact_sha256='prior-zip')
        H.write(review,r);p['base'].update(index_sha256=H.sha(prior),review_sha256=H.sha(review),archive_sha256='prior-zip')
        p['shared_run']['config_sha256']=H.sha(config);p['shared_run']['expires_utc']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=24)).isoformat()
        native=self.root/'native.so';native.write_bytes(b'invented-never-loaded');build=self.root/'build.json';H.write(build,{})
        p['original_native'].update(library_sha256=H.sha(native),build_receipt_sha256=H.sha(build))
        sr=self.root/'source.json';cr=self.root/'checker.json';H.write(sr,{});H.write(cr,{})
        token='invented';a=dict(mode='exposure_refinement_host_batch',batch_id=batch,case_ids=names,child_attempt_ids={n:'attempt-'+n for n in names},
            numerical_attempt_id='host-attempt',source_sha256={},scientific_source_sha256={},protocol_sha256=H.sha(H.HERE/'protocol.json'),
            amendment_protocol_sha256=H.sha(H.HERE/'protocol.json'),host_batch_source_review_passed=True,checker_source_review_passed=True,
            shared_run=p['shared_run'],expires_utc=p['shared_run']['expires_utc'],rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
            lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),library_sha256=H.sha(native),build_receipt_sha256=H.sha(build),
            prior_index_sha256=H.sha(prior),prior_review_sha256=H.sha(review),prior_archive_sha256='prior-zip',conductor_review={},source_commit='fixture',
            source_review_sha256=H.sha(sr),checker_source_review_sha256=H.sha(cr),host_started_utc=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=1)).isoformat(),execution_window_seconds=g['whole_host_upper_seconds']-600)
        admission=self.root/'admission.json';H.write(admission,a)
        args=SimpleNamespace(output=self.root/'host',admission=admission,prior_index=prior,prior_review=review,config=config,source_review=sr,checker_review=cr,library=native,build_receipt=build,failed_prior=self.root/'prior_artifact' if batch==1 else None)
        calls=[];pins={'invented-checker':'pin'}
        def supervised(command,output,cap,admitted,environment,spec):
            calls.append(command);output.mkdir(parents=True);H.write(spec,dict(command=command))
            H.write(output/'result.json',dict(status='passed',returncode=0,cleanup_errors=[],survivors_after_cleanup=[],wall_seconds_including_cleanup=2.))
            if 'experiments.s04b_exposure_refinement.case_driver' in command:
                science=Path(command[command.index('--output')+1]);(science/'cases').mkdir(parents=True)
                name=command[command.index('--case-id')+1];case=science/'cases/case.json';trace=science/'cases/trace.jsonl';trace.write_bytes(b'{"fixture":true}\n')
                for f in ('reuse_map.json','refinement_events.jsonl','execution_calls.jsonl'):(science/f).write_bytes(b'{}\n')
                amendment=dict(reuse_map_sha256=H.sha(science/'reuse_map.json'),refinement_event_log_sha256=H.sha(science/'refinement_events.jsonl'),execution_calls_sha256=H.sha(science/'execution_calls.jsonl'))
                actual_report=report(name,complete);actual_report['numerical_amendment']=amendment;H.write(case,actual_report)
                result=dict(schema='joint_exposure_refinement_case_v1',case_id=name,handled=True,disposition_valid=True,status='terminal_disposition',passed=complete,scientific_passed=complete,
                    disposition='complete' if complete else 'scientific_unknown',source_sha256={},protocol_sha256=a['protocol_sha256'],numerical_attempt_id=a['child_attempt_ids'][name],
                    report_file='cases/case.json',report_sha256=H.sha(case),trace_file='cases/trace.jsonl',trace_sha256=H.sha(trace),numerical_amendment=amendment,
                    refinement_census=dict(started=0,accepted=0,rejected=0),wall_seconds=1.,actual_optimizer_attempts=4 if batch==1 else 32,reused_optimizer_attempts=28 if batch==1 else 0)
                if not complete:result.update(unknown_reason={},model_census={},terminal_solver_return={})
                H.write(science/'result.json',result)
            else:
                child=Path(command[command.index('--current')+1]);target=Path(command[command.index('--output')+1])
                H.write(target,dict(passed=checker_passes,audit_passed=checker_passes,disposition_valid=checker_passes,index_sha256=H.sha(child/'index.json'),
                    live_agent_review=False,live_agent_review_performed=False,scientific_completion=False,final_batch_agent_review_required=True,checker_sources_sha256=pins,checker_source_review_sha256=H.sha(cr)))
        with patch.object(H,'verify_protocol',return_value=p),patch.object(H,'source_identity',return_value={}),patch.object(H.driver,'source_identity',return_value={}),patch.object(H,'check_source_reviews',return_value=pins),patch.object(original,'supervised',side_effect=supervised),patch.dict(H.os.environ,JOINT_NUMERICAL_LEASE_TOKEN=token):
            code=H.run(args)
        return code,H.read(args.output/'result.json'),args,calls
    def test_whole_host_uses_real_supervisor_schema_and_preserves_unknown_prefix(self):
        code,result,args,calls=self.fixture()
        self.assertEqual(code,0,result);self.assertTrue(result['host_execution_passed']);self.assertFalse(result['scientific_completion'])
        index=H.read(args.output/'index.json');self.assertEqual(index['counts']['complete_histories'],44);self.assertEqual(index['counts']['unknown_histories'],1)
        self.assertEqual(index['attempts'][0]['outer_seconds'],2.);self.assertEqual(len(calls),2)
        self.assertTrue(index['predecessor']['archive_sha256']=='prior-zip')
    def test_partial_unknown_cannot_unlock_future_cases(self):
        code,result,args,calls=self.fixture(complete=False)
        self.assertEqual(code,1);self.assertFalse(result['host_execution_passed']);self.assertEqual(len(calls),1)
        self.assertIn('partial pilot',result['error']);self.assertFalse((args.output/'index.json').exists())
    def test_checker_rejection_retains_candidate_without_accepted_host_index(self):
        code,result,args,calls=self.fixture(checker_passes=False)
        self.assertEqual(code,1);self.assertEqual(len(calls),2);self.assertFalse((args.output/'index.json').exists())
        self.assertTrue((args.output/result['failed_child']['artifact']/'index.json').exists())
    def test_multi_child_host_local_predecessors_have_no_prior_archive_claim(self):
        code,result,args,calls=self.fixture(batch=3)
        self.assertEqual(code,0,result);self.assertEqual(len(result['children']),5);self.assertEqual(len(calls),10)
        for i,child in enumerate(result['children']):
            index=H.read(args.output/child['artifact']/'index.json')
            self.assertEqual(index['predecessor']['archive_sha256'],'prior-zip' if i==0 else None)
        self.assertEqual(result['counts']['processed_histories'],51)


if __name__=='__main__':unittest.main()
