"""Constructed dispatch/archive controls; no optimizer or scientific inputs."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from scripts import run_continuation as c


class RemainingController(unittest.TestCase):
    def fixture(self, root):
        def save(name, value):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return p
        config=save('config.json',{'invented':True})
        review=save('failure.json',{'passed':False,'audit_passed':True})
        source=save('source.json',{'passed':True});checker=save('checker.json',{'passed':True})
        index=json.dumps({'cases':[],'last_attempt_passed':False}).encode()
        native=b'constructed library';receipt=b'{"invented": true}'
        archive=root/'failure.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('original/index.json',index);z.writestr('original/lib.so',native)
            z.writestr('original/build.json',receipt);z.writestr('not-needed/large-history.txt',b'untouched')
        digest=lambda b:hashlib.sha256(b).hexdigest()
        shared=dict(run_id='invented',config_sha256=c.sha(config),expires_utc='2099-01-01T00:00:00+00:00')
        policy=dict(actual_hosts=[dict(host=1,case_ids=['new-case'],outer_maximum_seconds=3000,upload_reserve_seconds=600),
                                 dict(host=2,case_ids=['later-case'],outer_maximum_seconds=3000,upload_reserve_seconds=600)],
            resources=dict(sampled_process_tree_rss_cap_bytes=6442450944,minimum_host_free_bytes=2147483648),
            shared_run=shared,scientific_protocol_sha256='frozen',
            original_native=dict(library_sha256=digest(native),build_receipt_sha256=digest(receipt)),
            immutable_failure_reference=dict(archive='failure.zip',archive_sha256=c.sha(archive),
                index_member='original/index.json',index_sha256=digest(index),review='failure.json',review_sha256=c.sha(review),
                library_member='original/lib.so',build_receipt_member='original/build.json'))
        save('experiments/s04b_joint_remaining/protocol.json',policy)
        grant=dict(stage=c.REMAINING_HOST_STAGE,remaining_protocol_review_passed=True,host_batch_source_review_passed=True,
            checker_source_review_passed=True,batch_id=1,case_ids=['new-case'],wall_cap_seconds=2400,
            rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,operational_run_config_path='config.json',
            operational_run_config_sha256=c.sha(config),operational_run_id='invented',expires_utc=shared['expires_utc'],
            source_review_record='source.json',source_review_sha256=c.sha(source),checker_source_review='checker.json',
            checker_source_review_sha256=c.sha(checker),remaining_evidence_sha256={'failure.zip':c.sha(archive)},
            prior_index_review='failure.json',prior_review_sha256=c.sha(review),prior_index_sha256=digest(index),
            child_attempt_ids={'new-case':'invented-child'},numerical_attempt_id='invented-attempt',reviewed_files_sha256={})
        return policy,grant

    def prepare(self,root,grant,output,prior=None):
        output.mkdir()
        stub=SimpleNamespace(source_identity=lambda:{'fixture':'source'})
        with patch.object(c,'ROOT',root),patch.object(c.subprocess,'check_output',return_value='invented-commit\n'),\
                patch.dict(c.os.environ,{'CONTINUATION_HOST_TIMEOUT_MINUTES':'240','CONTINUATION_HOST_STARTED_UTC':'2098-01-01T00:00:00+00:00'}):
            return c.joint_remaining_host(grant,output,'fixture-token',prior,stub,stub)

    def test_initial_materializes_only_exact_index_and_native_members(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);policy,grant=self.fixture(root);out=root/'out'
            admission,command=self.prepare(root,grant,out)
            self.assertEqual(sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()),
                ['build/attenuation.so','build/build_receipt.json','initial_failed_index.json'])
            self.assertEqual(admission['mode'],'remaining_host_batch')
            self.assertEqual(admission['case_ids'],['new-case'])
            self.assertIn('experiments.s04b_joint_remaining.host',command)
            self.assertEqual(c.sha(out/'build/attenuation.so'),policy['original_native']['library_sha256'])

    def test_frozen_roster_limit_review_and_predecessor_mismatches_rejected(self):
        for field,value in [('case_ids',['failed-case']),('wall_cap_seconds',2401),('rss_cap_bytes',1),
                            ('expires_utc','2100-01-01T00:00:00+00:00'),('prior_index_sha256','wrong'),
                            ('source_review_sha256','wrong'),('prior_review_sha256','wrong')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                root=Path(d);_,grant=self.fixture(root);grant[field]=value
                with self.assertRaises(ValueError):self.prepare(root,grant,root/'out')

    def test_initial_pilot_cannot_take_a_different_previous_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,grant=self.fixture(root)
            with self.assertRaises(ValueError):self.prepare(root,grant,root/'out',root/'other')

    def test_later_host_uses_compact_predecessor_without_copying_its_cases(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);_,grant=self.fixture(root);prior=root/'prior';(prior/'host').mkdir(parents=True)
            (prior/'host/index.json').write_text('{"compact":true}')
            grant.update(batch_id=2,case_ids=['later-case'],child_attempt_ids={'later-case':'next'},
                prior_index_path='host/index.json',prior_index_sha256=c.sha(prior/'host/index.json'))
            admission,command=self.prepare(root,grant,root/'out',prior)
            self.assertEqual(command[command.index('--prior-index')+1],str(prior/'host/index.json'))
            self.assertFalse((root/'out/initial_failed_index.json').exists())
            self.assertEqual(admission['prior_index_sha256'],grant['prior_index_sha256'])

    def test_native_member_tampering_fails_even_if_archive_hash_rebound(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);policy,grant=self.fixture(root)
            with zipfile.ZipFile(root/'failure.zip','a') as z:z.writestr('original/lib.so',b'wrong')
            policy['immutable_failure_reference']['archive_sha256']=c.sha(root/'failure.zip')
            (root/'experiments/s04b_joint_remaining/protocol.json').write_text(json.dumps(policy))
            grant['remaining_evidence_sha256']['failure.zip']=c.sha(root/'failure.zip')
            with self.assertRaisesRegex(ValueError,'duplicated'):self.prepare(root,grant,root/'out')

    def test_successful_orchestration_does_not_claim_scientific_completion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'host').mkdir();(root/'host/index.json').write_text('{}')
            result=dict(host_execution_passed=True,status='host_batch_complete',scientific_completion=False,
                children=[{'case_id':'a'}],live_agent_review=False,final_batch_agent_review_required=True,
                latest_index='index.json',index_sha256=c.sha(root/'host/index.json'))
            path=root/'host/result.json';path.write_text(json.dumps(result))
            c.remaining_host_passed(root,{'case_ids':['a']})
            for key,value in [('scientific_completion',True),('host_execution_passed',False),('index_sha256','wrong')]:
                changed=dict(result,**{key:value});path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):c.remaining_host_passed(root,{'case_ids':['a']})

    def test_source_map_requires_terminal_evidence_and_current_checker(self):
        grant=dict(source_review_record='source.json',checker_source_review='checker.json',
            operational_run_config_path='config.json',prior_index_review='failure.json',
            remaining_evidence_sha256={'failure.zip':'x','failure.json':'y'})
        pins=c.mandatory_sources(c.REMAINING_HOST_STAGE,grant)
        self.assertTrue({'failure.zip','failure.json','checker.json',
            'experiments/s04b_joint_nuisance/fit.py','experiments/s04b_joint_execution/parallel_chunks.py',
            'tests/test_joint_remaining_controller.py'}.issubset(pins))

    def test_source_map_covers_actual_case_and_host_dependencies(self):
        from experiments.s04b_joint_remaining import case_driver, host
        grant=dict(source_review_record='source.json',checker_source_review='checker.json',
            operational_run_config_path='config.json',prior_index_review='failure.json',remaining_evidence_sha256={})
        pins=c.mandatory_sources(c.REMAINING_HOST_STAGE,grant)
        self.assertTrue(set(case_driver.source_identity()).issubset(pins))
        self.assertTrue(set(host.source_identity()).issubset(pins))
        self.assertIn('tests/test_joint_recovery.py',pins)


if __name__=='__main__':unittest.main()
