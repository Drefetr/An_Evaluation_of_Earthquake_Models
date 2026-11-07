"""Operational recovery admission controls; invented inputs, no model calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from scripts import run_continuation as controller


class RecoveryControllerControls(unittest.TestCase):
    def fixture(self, root):
        prior = root/'download'/'child'
        (prior/'science').mkdir(parents=True)
        controller.write(prior/'science/index.json', {'schema':'invented_failed_index'})
        controller.write(root/'prior_review.json', {'audit_passed':True,'passed':False})
        for name in ('config.json','checker.json','source.json','evidence.json'):
            controller.write(root/name, {'fixture':name})
        for package, name in (('s04b_joint_recovery','recovery_protocol.json'),
                              ('s04b_joint_recovery_host','batch_policy.json')):
            folder = root/'experiments'/package
            folder.mkdir(parents=True)
            controller.write(folder/name, {'fixture':name})
        (root/'original.zip').write_bytes(b'invented retained failure')
        shared = dict(run_id='same-run', config_sha256=controller.sha(root/'config.json'),
                      expires_utc='2099-01-01T00:00:00+00:00')
        policy = dict(actual_hosts=[dict(host=1, outer_maximum_seconds=3000,
                                         upload_reserve_seconds=600)], shared_run=shared,
                      resources=dict(sampled_process_tree_rss_cap_bytes=6*2**30,
                                     minimum_host_free_bytes=2*2**30))
        batch = types.SimpleNamespace(verify_policy=lambda:({},policy),
                                      source_identity=lambda:{'host':'invented'},
                                      next_cases=Mock(return_value=['remaining']))
        driver = types.SimpleNamespace(source_identity=lambda:{'science':'unchanged'})
        review = dict(stage=controller.RECOVERY_HOST_STAGE, driver_source_review_passed=True,
                      scheduler_source_review_passed=True,recovery_protocol_review_passed=True,
                      host_batch_source_review_passed=True,checker_source_review_passed=True,
                      batch_id=1, wall_cap_seconds=2400,rss_cap_bytes=6*2**30,
                      host_headroom_bytes=2*2**30,prior_index_path='child/science/index.json',
                      prior_index_sha256=controller.sha(prior/'science/index.json'),
                      prior_index_review='prior_review.json',operational_run_config_path='config.json',
                      operational_run_config_sha256=shared['config_sha256'],
                      operational_run_id=shared['run_id'],expires_utc=shared['expires_utc'],
                      checker_source_review='checker.json',source_review_record='source.json',
                      checker_source_review_sha256=controller.sha(root/'checker.json'),
                      source_review_sha256=controller.sha(root/'source.json'),
                      recovery_evidence_sha256={'evidence.json':controller.sha(root/'evidence.json')},
                      case_ids=['remaining'],child_attempt_ids={'remaining':'lease-case'},
                      numerical_attempt_id='lease',reviewed_files_sha256={'fixture':'pin'},
                      failed_archive='original.zip')
        return review, batch, driver

    def prepare(self, root, review, batch, driver, name='out'):
        output=root/name
        output.mkdir()
        with patch.object(controller,'ROOT',root), patch.dict(controller.os.environ,{
                'CONTINUATION_HOST_TIMEOUT_MINUTES':'240',
                'CONTINUATION_HOST_STARTED_UTC':'2098-12-31T00:00:00+00:00'}), \
                patch.object(controller.subprocess,'check_output',return_value='fixture-head\n'), \
                patch.object(controller.subprocess,'run') as process:
            result=controller.joint_recovery_host(review,output,'ephemeral',root/'download',batch,driver)
            process.assert_not_called()
            return result

    def test_explicit_failed_transition_is_delegated_without_changing_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);review,batch,driver=self.fixture(root)
            admission,command=self.prepare(root,review,batch,driver)
            self.assertEqual(admission['mode'],'recovery_host_batch')
            self.assertEqual(admission['execution_window_seconds'],2400)
            self.assertEqual(admission['lease_token_sha256'],hashlib.sha256(b'ephemeral').hexdigest())
            self.assertIn('experiments.s04b_joint_recovery_host.batch',command)
            self.assertEqual(batch.next_cases.call_args.args[-1],{'audit_passed':True,'passed':False})
            self.assertFalse(controller.read(root/'prior_review.json')['passed'])

    def test_stage_reviews_old_projection_and_resource_extensions_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);review,batch,driver=self.fixture(root)
            for number, change in enumerate((
                    {'stage':controller.HOST_BATCH_STAGE},
                    {'recovery_protocol_review_passed':False},
                    {'driver_source_review_passed':False},
                    {'checker_source_review_passed':False},
                    {'pilot_projection_review_passed':True}, {'batch_id':9},
                    {'wall_cap_seconds':13800},{'rss_cap_bytes':7*2**30},
                    {'host_headroom_bytes':1},{'expires_utc':'2100-01-01T00:00:00+00:00'},
                    {'operational_run_id':'new-run'}, {'prior_index_sha256':'changed'},
                    {'source_review_sha256':'changed'},{'checker_source_review_sha256':'changed'},
                    {'recovery_evidence_sha256':{'evidence.json':'changed'}})):
                with self.subTest(change=change),self.assertRaises(ValueError):
                    self.prepare(root,dict(review,**change),batch,driver,str(number))

    def test_independent_prefix_and_pilot_rejection_prevents_command_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);review,batch,driver=self.fixture(root)
            batch.next_cases.side_effect=ValueError('unaccepted pilot or wrong prefix')
            with self.assertRaisesRegex(ValueError,'unaccepted pilot'):
                self.prepare(root,review,batch,driver)
            self.assertFalse((root/'out/run_config.json').exists())

    def test_recovery_sources_retain_failed_legacy_lineage_and_new_audit(self):
        review=dict(failed_archive='original.zip',prior_artifact_id=1,
                    prior_index_review='partial.json',source_review_record='source.json',
                    checker_source_review='checker.json',operational_run_config_path='config.json',
                    recovery_evidence_sha256={'failed05.zip':'pin','design.json':'pin'},
                    recovery_test_paths=['tests/test_joint_recovery.py'],
                    recovery_checker_source_paths=['experiments/s04b_joint_recovery_audit/check.py'])
        pins=controller.mandatory_sources(controller.RECOVERY_HOST_STAGE,review)
        self.assertTrue({'failed05.zip','design.json','partial.json','original.zip',
                         'experiments/s04b_joint_nuisance/fit.py',
                         'experiments/s04b_joint_budgeted/allocation_protocol.json',
                         'tests/test_joint_recovery_controller.py',
                         'tests/test_joint_recovery.py',
                         'experiments/s04b_joint_recovery_audit/check.py'}.issubset(pins))


if __name__ == '__main__':
    unittest.main()
