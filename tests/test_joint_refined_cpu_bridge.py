"""Invented source/dispatch/custody controls; no likelihood or optimizer calls."""
import builtins
import copy
import datetime as dt
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from experiments.s04b_refined_cpu_bridge import host as B, contract as C
from experiments.s04b_exposure_refinement import host as H
from experiments.s04b_joint_remaining import host as G


class BridgeControls(unittest.TestCase):
    def launcher(self):
        spec=importlib.util.spec_from_file_location('public_reader_launcher_fixture',C.REPO/'scripts/run_joint_refined_cpu_host.py')
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
        return value

    def test_new_source_graph_checked_before_metadata_module_import(self):
        launcher=self.launcher()
        with self.assertRaisesRegex(ValueError,'Incomplete public'):
            launcher.check_public_sources({'reviewed_files_sha256':{}})
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        for name in launcher.PUBLIC_REQUIRED:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('invented-not-imported',encoding='utf-8')
        profile=root/'experiments/s04b_refined_cpu_reader/profile.json'
        H.write(profile,dict(producer_source_paths=sorted(launcher.PUBLIC_REQUIRED)))
        pins={name:H.sha(root/name) for name in launcher.PUBLIC_REQUIRED}
        with patch.object(launcher,'ROOT',root):
            launcher.check_public_sources({'reviewed_files_sha256':pins})
            (root/'experiments/s04b_refined_cpu_reader/__init__.py').write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Changed public'):
                launcher.check_public_sources({'reviewed_files_sha256':pins})

    def test_profile_cannot_omit_or_add_unreviewed_dependency(self):
        launcher=self.launcher();temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        for name in launcher.PUBLIC_REQUIRED:
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('invented',encoding='utf-8')
        profile=root/'experiments/s04b_refined_cpu_reader/profile.json'
        with patch.object(launcher,'ROOT',root):
            for names in ([],sorted(launcher.PUBLIC_REQUIRED)+['unexpected.py']):
                H.write(profile,dict(producer_source_paths=names))
                pins={name:H.sha(root/name) for name in launcher.PUBLIC_REQUIRED}
                with self.assertRaises(ValueError):launcher.check_public_sources({'reviewed_files_sha256':pins})

    def test_frozen_loop_and_global_modules_are_unchanged(self):
        before=dict(H.__dict__); original_import=builtins.__import__
        run=B.facade()
        self.assertIs(run.__code__,H.run.__code__)
        self.assertEqual(H.__dict__,before)
        self.assertIs(builtins.__import__,original_import)
        importer=run.__globals__['__builtins__']['__import__']
        self.assertIs(importer('math'),__import__('math'))
        self.assertIs(importer('experiments.s04b_joint_remaining.host',fromlist=('projection',)),G)
        bridge=importer('experiments.s04b_joint_remaining.host',fromlist=('supervised','projection'))
        self.assertIs(bridge.supervised,B.supervised);self.assertIs(bridge.projection,G.projection)

    def test_actual_command_preserves_original_cap_and_has_no_partial_route(self):
        command=[sys.executable,'-B','-m','experiments.s04b_exposure_refinement.case_driver',
                 '--mode','untouched','--case-id','S6_narrow_short_total_seed410606',
                 '--library','original.so','--build-receipt','build.json','--admission','admission.json','--output','science']
        converted=B.reader_command(command,2520)
        self.assertEqual(converted[:4],[sys.executable,'-B',str(C.REPO/'scripts/fit_joint_refined_cpu.py'),'fit'])
        self.assertEqual(converted[converted.index('--wall-seconds')+1],'2520')
        self.assertIn('--execution-record',converted);self.assertNotIn('--library',converted)
        command[5]='partial'
        with self.assertRaisesRegex(ValueError,'partial'):B.reader_command(command,2520)
        with self.assertRaises(ValueError):B.reader_command(command+['--extra','x'],2520)

    def test_unrecognized_dispatch_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unrecognized'):
            B.supervised(['unrelated'],None,1,None,None,None)

    def fixture(self, fail_checker_at=None, unknown_at=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        p=copy.deepcopy(H.read(H.HERE/'protocol.json'));group=p['resources']['future_hosts'][2]
        names=group['case_ids'];producer={'schema':'invented-explicit-reader','entrypoint':'fixture'}
        def report(name,complete=True):
            return dict(case_id=name,regime=6,seed=int(name.rsplit('seed',1)[1]),n_train=7,n_test=3,thinning={},
                        outcomes=[dict(model='invented',gate=str(i),new_gain=.1) for i in range(5)] if complete else [],
                        fits={'null':dict(passed=True,records=[dict(success=True)],null_search_gaps=[])})
        prior_rows=[G.projection(report(n,i!=40),'complete' if i!=40 else 'scientific_unknown',{'kind':'fixture'})
                    for i,n in enumerate(p['full_sequence'][:46])]
        attempts=[dict(case_id=n,seconds=1.,outer_seconds=2.) for n in p['case_ids'][:2]]
        prior=root/'prior.json';review=root/'review.json';config=root/'config.json'
        index=dict(schema='joint_exposure_refinement_index_v1',records=prior_rows,attempts=attempts,
                   protocol_sha256=H.sha(H.HERE/'protocol.json'),host_source_sha256={},scientific_source_sha256={},budget=H.budget(p,attempts))
        H.write(prior,index);H.write(config,{})
        H.write(review,dict(passed=True,audit_passed=True,live_agent_review=True,review_kind='live_agent_saved_output_review',
                           final_batch_agent_review_required=False,index_sha256=H.sha(prior),artifact_sha256='prior-archive'))
        p['shared_run']['config_sha256']=H.sha(config)
        p['shared_run']['expires_utc']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=24)).isoformat()
        native=root/'native.so';native.write_bytes(b'invented-never-loaded');build=root/'build.json';H.write(build,{})
        p['original_native'].update(library_sha256=H.sha(native),build_receipt_sha256=H.sha(build))
        source=root/'source_review.json';H.write(source,{})
        token='invented';pins={'invented-audit':'pin'}
        a=dict(mode='exposure_refinement_host_batch',batch_id=3,case_ids=names,child_attempt_ids={n:'attempt-'+n for n in names},
               numerical_attempt_id='host-attempt',source_sha256={},scientific_source_sha256={},protocol_sha256=H.sha(H.HERE/'protocol.json'),
               amendment_protocol_sha256=H.sha(H.HERE/'protocol.json'),host_batch_source_review_passed=True,checker_source_review_passed=True,
               shared_run=p['shared_run'],expires_utc=p['shared_run']['expires_utc'],rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
               lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),library_sha256=H.sha(native),build_receipt_sha256=H.sha(build),
               prior_index_sha256=H.sha(prior),prior_review_sha256=H.sha(review),prior_archive_sha256='prior-archive',conductor_review={},source_commit='fixture',
               source_review_sha256=H.sha(source),checker_source_review_sha256=H.sha(source),
               host_started_utc=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=1)).isoformat(),
               execution_window_seconds=group['whole_host_upper_seconds']-600,reader_source_review={'path':'fixture','sha256':'pin'},execution_producer=producer)
        admission=root/'admission.json';H.write(admission,a)
        args=SimpleNamespace(output=root/'host',admission=admission,prior_index=prior,prior_review=review,config=config,
                             source_review=source,checker_review=source,library=native,build_receipt=build,failed_prior=None)
        commands=[]
        def invented_supervision(command,output,cap,admitted,environment,spec):
            commands.append(command);output.mkdir(parents=True);H.write(spec,dict(command=command))
            H.write(output/'result.json',dict(status='passed',returncode=0,cleanup_errors=[],survivors_after_cleanup=[],wall_seconds_including_cleanup=2.))
            if command[3]=='fit':
                self.assertEqual(cap,2520)
                science=Path(command[command.index('--output')+1]);(science/'cases').mkdir(parents=True)
                grant=H.read(command[command.index('--execution-record')+1]);self.assertEqual(grant['source_sha256'],{'reader':'pin'})
                name=command[command.index('--case-id')+1];complete=name!=unknown_at
                case=science/'cases/case.json';trace=science/'cases/trace.jsonl';trace.write_bytes(b'{"fixture":true}\n')
                H.write(science/'reuse_map.json',dict(entries=[],reused_optimizer_attempts=0))
                for filename in ('refinement_events.jsonl','execution_calls.jsonl'):(science/filename).write_bytes(b'')
                amendment=dict(reuse_map_sha256=H.sha(science/'reuse_map.json'),refinement_event_log_sha256=H.sha(science/'refinement_events.jsonl'),execution_calls_sha256=H.sha(science/'execution_calls.jsonl'))
                r=report(name,complete);r.update(numerical_amendment=amendment,execution_producer=producer);H.write(case,r)
                value=dict(schema='joint_refined_cpu_case_v1',case_id=name,handled=True,disposition_valid=True,status='terminal_disposition',
                    passed=complete,scientific_passed=complete,disposition='complete' if complete else 'scientific_unknown',
                    execution_producer=producer,source_sha256={'reader':'pin'},protocol_sha256=a['protocol_sha256'],numerical_attempt_id=grant['numerical_attempt_id'],
                    report_file='cases/case.json',report_sha256=H.sha(case),trace_file='cases/trace.jsonl',trace_sha256=H.sha(trace),numerical_amendment=amendment,
                    refinement_census=dict(started=0,accepted=0,rejected=0),wall_seconds=1.,actual_optimizer_attempts=32,reused_optimizer_attempts=0)
                if not complete:value.update(unknown_reason={},model_census={},terminal_solver_return={})
                H.write(science/'result.json',value)
            else:
                self.assertEqual(command[3],C.CHECKER);self.assertEqual(cap,120)
                child=Path(command[command.index('--current')+1]);passed=names.index(H.read(child/'science/result.json')['case_id'])!=fail_checker_at
                H.write(Path(command[command.index('--output')+1]),dict(passed=passed,audit_passed=passed,disposition_valid=passed,index_sha256=H.sha(child/'index.json'),
                    live_agent_review=False,live_agent_review_performed=False,scientific_completion=False,final_batch_agent_review_required=True,
                    checker_sources_sha256=pins,checker_source_review_sha256=H.sha(source),execution_producer=producer))
        with patch.object(H,'verify_protocol',return_value=p),patch.object(H,'source_identity',return_value={}),patch.object(H.driver,'source_identity',return_value={}),\
             patch.object(C,'source_identity',return_value={'reader':'pin'}),patch.object(C,'producer',return_value=producer),\
             patch.object(C,'check_source_reviews',return_value=pins),patch.object(G,'supervised',side_effect=invented_supervision),\
             patch.dict(H.os.environ,JOINT_NUMERICAL_LEASE_TOKEN=token):
            code=B.run(args)
        return code,H.read(args.output/'result.json'),args,commands,prior_rows,p,a

    def test_full_five_case_group_actual_argv_prefix_and_next_frozen_boundary(self):
        code,result,args,commands,prefix,p,a=self.fixture()
        self.assertEqual(code,0,result);self.assertEqual(len(commands),10)
        index=H.read(args.output/'index.json')
        self.assertEqual(index['records'][:46],prefix)
        self.assertEqual([r['case_id'] for r in index['records'][46:]],p['resources']['future_hosts'][2]['case_ids'])
        self.assertTrue(all('execution_producer' in r for r in index['records'][46:]))
        self.assertEqual(index['host_source_sha256'],{});self.assertEqual(index['scientific_source_sha256'],{})
        next_a=dict(a,batch_id=4,case_ids=p['resources']['future_hosts'][3]['case_ids'],
                    child_attempt_ids={n:'next-'+n for n in p['resources']['future_hosts'][3]['case_ids']},
                    prior_index_sha256=H.sha(args.output/'index.json'))
        live=dict(passed=True,audit_passed=True,live_agent_review=True,review_kind='live_agent_saved_output_review',
                  final_batch_agent_review_required=False,index_sha256=next_a['prior_index_sha256'],artifact_sha256=a['prior_archive_sha256'])
        self.assertEqual(H.next_cases(p,next_a,index,live)['host'],4)
        self.assertFalse(result['scientific_completion']);self.assertEqual(result['schema'],'joint_refined_cpu_host_v1')

    def test_checker_failure_stops_without_retry_or_next_case(self):
        code,result,args,commands,*_=self.fixture(fail_checker_at=1)
        self.assertEqual(code,1);self.assertEqual(len(commands),4)
        self.assertEqual(H.read(args.output/'index.json')['counts']['processed_histories'],47)
        self.assertEqual(len(result['children']),1)

    def test_new_cap_unknown_keeps_empty_outcomes_and_advances_disposition_only(self):
        name='S6_narrow_short_total_seed410606'
        code,result,args,commands,*_=self.fixture(unknown_at=name)
        self.assertEqual(code,0,result)
        row=H.read(args.output/'index.json')['records'][46]
        self.assertEqual(row['disposition'],'scientific_unknown');self.assertEqual(row['outcomes'],[])
        self.assertEqual(result['counts']['unknown_histories'],2)


if __name__=='__main__':unittest.main()
