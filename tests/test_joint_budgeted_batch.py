"""Constructed host orchestration controls; no native build, fit or likelihood call."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.s04b_joint_host_batch import batch
from experiments.s04b_joint_budgeted import driver


class HostBatchControls(unittest.TestCase):
    def test_exact_fixed_nine_partitions_preserve_every_remaining_slot(self):
        policy, allocation = batch.verify_policy()
        self.assertEqual([len(b['case_ids']) for b in policy['batches']],[5,5,5,15,10,5,5,5,19])
        self.assertEqual([n for b in policy['batches'] for n in b['case_ids']],allocation['sequence'][6:])
        self.assertEqual(sum(b['slot_seconds'] for b in policy['batches']),106680)
        self.assertTrue(all(b['slot_seconds'] <= 12600 for b in policy['batches']))

    def prefix(self, policy, allocation, count=6):
        index=dict(cases=[{'case_id':n} for n in allocation['sequence'][:count]],attempts=[],
                   partial_case=None,last_attempt_passed=True)
        group=policy['batches'][0]['case_ids'];names=group[count-6:]
        admission=dict(batch_id=1,case_ids=names,numerical_attempt_id='shared',
                       child_attempt_ids={n:'shared-case-%03d'%(allocation['sequence'].index(n)+1) for n in names})
        return index,admission

    def test_accepted_case07_yields_only_fixed_batch_suffix(self):
        policy,allocation=batch.verify_policy();index,a=self.prefix(policy,allocation,7)
        self.assertEqual(batch.next_cases(policy,allocation,a,index),policy['batches'][0]['case_ids'][1:])
        for key,value in [('case_ids',policy['batches'][0]['case_ids']),('batch_id',2),
                          ('child_attempt_ids',{n:'reused' for n in a['case_ids']})]:
            with self.assertRaises(ValueError):batch.next_cases(policy,allocation,dict(a,**{key:value}),index)

    def test_partial_failed_or_reordered_prefix_stops(self):
        p,a=batch.verify_policy();index,grant=self.prefix(p,a)
        for change in ({'partial_case':{'case_id':'partial'}},{'last_attempt_passed':False},
                       {'cases':list(reversed(index['cases']))}):
            with self.assertRaises(ValueError):batch.next_cases(p,a,grant,dict(index,**change))

    def test_no_slot_shrinking_or_upload_reserve_consumption(self):
        policy,_=batch.verify_policy();now=dt.datetime.now(dt.timezone.utc)
        start=(now-dt.timedelta(seconds=100)).isoformat()
        batch.timing(policy,start,0,2520,now)
        for elapsed,child in [(11300,11000),(1200,0),(-1,0)]:
            with self.assertRaises(ValueError):
                batch.timing(policy,(now-dt.timedelta(seconds=elapsed)).isoformat(),child,2520,now)

    def fixture(self, root):
        policy,allocation=batch.verify_policy();policy=copy.deepcopy(policy)
        # Two unexecuted children from the end of the same actual fixed first batch.
        index,grant=self.prefix(policy,allocation,9)
        prior=root/'prior';(prior/'science').mkdir(parents=True);(prior/'build').mkdir()
        batch.write(prior/'science/index.json',dict(index,budget={'total_seconds':100.,'pilot_seconds':10.}))
        (prior/'build/attenuation.so').write_bytes(b'invented native')
        batch.write(prior/'build/build_receipt.json',{'passed':True,'invented':True})
        allocation=copy.deepcopy(allocation)
        allocation['predecessor'].update(library_sha256=batch.sha(prior/'build/attenuation.so'),
                                         build_receipt_sha256=batch.sha(prior/'build/build_receipt.json'))
        batch.write(root/'prior_review.json',{'passed':True,'index_sha256':batch.sha(prior/'science/index.json')})
        repo=root/'repo';repo.mkdir();source=repo/'experiments/s04b_joint_audit/check.py';source.parent.mkdir(parents=True)
        source.write_text('invented checker')
        (root/'failed.zip').write_bytes(b'invented original failure')
        old=repo/'experiments/s04b_joint_execution/operational_protocol.json';old.parent.mkdir(parents=True)
        batch.write(old,{'original_failure':{'failed_archive_sha256':batch.sha(root/'failed.zip')}})
        batch.write(root/'config.json',{'invented':True})
        core=repo/'experiments/s04b_joint_nuisance_audit/audit.py';core.parent.mkdir(parents=True);core.write_text('invented audit core')
        checker_pins={p.relative_to(repo).as_posix():batch.sha(p) for p in (source,core)}
        batch.write(root/'checker_review.json',{'passed':True,'reviewed_files_sha256':checker_pins})
        policy['checker']=dict(source_sha256=checker_pins,source_review_sha256=batch.sha(root/'checker_review.json'))
        policy['shared_run'].update(config_sha256=batch.sha(root/'config.json'),expires_utc='2099-01-01T00:00:00+00:00')
        grant.update(mode='fixed_host_batch',source_sha256={'host':'fixture'},scientific_source_sha256={'science':'frozen'},
            batch_policy_sha256=batch.sha(batch.HERE/'batch_policy.json'),shared_run=policy['shared_run'],
            host_batch_source_review_passed=True,checker_source_review_passed=True,rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
            lease_token_sha256=batch.hashlib.sha256(b'fixture-token').hexdigest(),prior_index_sha256=batch.sha(prior/'science/index.json'),
            prior_review_sha256=batch.sha(root/'prior_review.json'),expires_utc='2098-01-01T00:00:00+00:00',
            checker_source_review_sha256=batch.sha(root/'checker_review.json'),
            reviewed_files_sha256=checker_pins,
            host_started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_commit='abcdef1',conductor_review={})
        batch.write(root/'admission.json',grant)
        args=argparse.Namespace(output=root/'output',admission=root/'admission.json',prior=prior,prior_review=root/'prior_review.json',
            config=root/'config.json',checker_review=root/'checker_review.json',failed_archive=root/'failed.zip')
        return args,grant,policy,allocation,repo

    def execute(self,args,grant,policy,allocation,repo,failure=None):
        calls=[]
        def fake(command,output,cap,admission,environment,spec_path):
            is_check=Path(command[2]).name=='check.py';calls.append(('check' if is_check else 'case',cap))
            self.assertEqual(environment['OMP_NUM_THREADS'],'2')
            output.mkdir(parents=True);batch.write(spec_path,{'command':command,'wall_cap_seconds':cap})
            batch.write(output/'result.json',{'status':'passed','returncode':0,'cleanup_errors':[],'survivors_after_cleanup':[]})
            destination=Path(command[command.index('--output')+1])
            if is_check:
                current=Path(command[command.index('--current')+1])
                receipt=dict(passed=failure!='checker',index_sha256=batch.sha(current/'science/index.json'),
                    review_kind='automated_saved_output_check',live_agent_review=False,live_agent_review_performed=False,
                    final_batch_agent_review_required=True,checker_source_review_sha256=grant['checker_source_review_sha256'],
                    checker_sources_sha256=grant['reviewed_files_sha256'])
                batch.write(destination,receipt)
            else:
                if failure=='second' and len([c for c in calls if c[0]=='case'])==2:
                    raise ValueError('invented second-child failure')
                admission=batch.read(command[command.index('--admission')+1]);parent=batch.read(command[command.index('--prior-index')+1])
                destination.mkdir();parent['cases'].append({'case_id':admission['case_id']})
                batch.write(destination/'index.json',parent)
                batch.write(destination/'result.json',dict(passed=failure!='zero_exit',status='batch_complete',
                    cases=[{'case_id':admission['case_id']}],index_sha256=batch.sha(destination/'index.json')))
            return batch.read(output/'result.json')
        with patch.object(batch,'REPO',repo),patch.object(batch,'verify_policy',return_value=(policy,allocation)),\
                patch.object(batch,'source_identity',return_value={'host':'fixture'}),\
                patch.object(driver,'source_identity',return_value={'science':'frozen'}),\
                patch.dict(batch.os.environ,{'JOINT_NUMERICAL_LEASE_TOKEN':'fixture-token'}),\
                patch.object(batch,'supervised',side_effect=fake):
            code=batch.run(args)
        return code,batch.read(args.output/'result.json'),calls

    def test_two_children_preserve_order_native_bytes_and_require_checks_between(self):
        with tempfile.TemporaryDirectory()as directory:
            args,grant,policy,allocation,repo=self.fixture(Path(directory))
            code,result,calls=self.execute(args,grant,policy,allocation,repo)
            self.assertEqual(code,0);self.assertEqual(calls,[('case',2520),('check',120),('case',2520),('check',120)])
            self.assertEqual([r['case_id'] for r in result['children']],grant['case_ids'])
            for row in result['children']:
                child=args.output/row['artifact']
                self.assertEqual((child/'build/attenuation.so').read_bytes(),b'invented native')
                self.assertEqual((child/'original_failure.zip').read_bytes(),args.failed_archive.read_bytes())
            self.assertFalse(result['live_agent_review']);self.assertTrue(result['final_batch_agent_review_required'])

    def test_failed_checker_or_false_zero_exit_never_starts_next_case(self):
        for failure in ('checker','zero_exit'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory()as directory:
                values=self.fixture(Path(directory));code,result,calls=self.execute(*values,failure=failure)
                self.assertEqual(code,1);self.assertEqual(len([c for c in calls if c[0]=='case']),1)
                self.assertFalse(result['passed']);self.assertIn('active_child',result)

    def test_second_failure_retains_first_accepted_index_without_repetition(self):
        with tempfile.TemporaryDirectory()as directory:
            values=self.fixture(Path(directory))
            with patch.object(batch,'timing',return_value=(0,0)),patch.object(batch.time,'monotonic',side_effect=[10,13,20,25]):
                code,result,calls=self.execute(*values,failure='second')
            self.assertEqual(code,1);self.assertEqual(len(result['children']),1)
            self.assertEqual(batch.sha(values[0].output/result['latest_index']),result['children'][0]['index_sha256'])
            self.assertEqual(result['supervised_case_process_seconds'],8)
            self.assertIsNotNone(result['failed_child']['evidence']['supervision/result.json'])

    def test_preparation_must_leave_whole_fixed_slot_before_launch(self):
        with tempfile.TemporaryDirectory()as directory:
            values=self.fixture(Path(directory))
            with patch.object(batch,'timing',side_effect=[(0,0),ValueError('preparation consumed margin')]):
                code,result,calls=self.execute(*values)
            self.assertEqual(code,1);self.assertEqual(calls,[])
            self.assertIn('preparation consumed margin',result['error'])

    def test_changed_predecessor_or_expiry_stops_before_any_child(self):
        for failure in ('prior','expiry'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory()as directory:
                args,grant,policy,allocation,repo=self.fixture(Path(directory))
                if failure=='prior':(args.prior/'science/index.json').write_text('{}')
                else:grant['expires_utc']='2000-01-01T00:00:00+00:00';batch.write(args.admission,grant)
                code,result,calls=self.execute(args,grant,policy,allocation,repo)
                self.assertEqual(code,1);self.assertEqual(calls,[])

    def test_survivor_or_uncertain_supervisor_stops(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory)
            for change in ({'survivors_after_cleanup':[{'pid':123}]},{'cleanup_errors':['uncertain']},{'returncode':1}):
                batch.write(root/'result.json',dict(status='passed',returncode=0,cleanup_errors=[],survivors_after_cleanup=[],**{}))
                record=batch.read(root/'result.json');record.update(change);batch.write(root/'result.json',record)
                with self.assertRaises(ValueError):batch.checked_supervision(root)


if __name__=='__main__':
    unittest.main()
