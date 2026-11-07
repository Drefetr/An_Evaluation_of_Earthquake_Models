"""Admission controls using invented identifiers; no scientific execution."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('continuation_controller', ROOT/'scripts/run_continuation.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class AdmissionControls(unittest.TestCase):
    def setUp(self):
        self.registry = {'rows': [{'id': name} for name in ('ordinary', 'large', 'other')]}
        self.proposal = {'row_ids': ['ordinary', 'large']}

    def test_pilot_must_keep_predeclared_order_and_members(self):
        good = {'stage': 'regional-pilot', 'row_ids': ['ordinary', 'large']}
        self.assertEqual(controller.replay_roster(good, self.proposal, self.registry)[0], good['row_ids'])
        for rows in (['large', 'ordinary'], ['ordinary'], ['ordinary', 'large', 'other']):
            with self.assertRaises(ValueError):
                controller.replay_roster(dict(good, row_ids=rows), self.proposal, self.registry)

    def test_completion_requires_accepted_pilot_and_exact_remaining_rows(self):
        good = {'stage': 'cached-completion', 'row_ids': ['other'], 'pilot_output_review_passed': True}
        self.assertEqual(controller.replay_roster(good, self.proposal, self.registry)[0], ['other'])
        for changed in ({'pilot_output_review_passed': False}, {'row_ids': []},
                        {'row_ids': ['ordinary', 'other']}, {'row_ids': ['other', 'other']}):
            with self.assertRaises(ValueError):
                controller.replay_roster(dict(good, **changed), self.proposal, self.registry)

    def test_registry_duplicates_and_unknown_pilot_are_rejected(self):
        good = {'stage': 'regional-pilot', 'row_ids': ['ordinary', 'large']}
        with self.assertRaises(ValueError):
            controller.replay_roster(good, self.proposal, {'rows': self.registry['rows']*2})
        with self.assertRaises(ValueError):
            controller.replay_roster(good, {'row_ids': ['unknown']}, self.registry)

    def test_nested_registry_and_proposal_are_both_mandatory_pins(self):
        review = {'registry': 'reproduction/score_replay/jma/registry.json',
                  'proposal': 'reproduction/score_replay/jma/pilot_proposal.json'}
        pins = controller.mandatory_sources('regional-pilot', review)
        self.assertTrue({review['registry'], review['proposal'],
                         'reproduction/score_replay/jma/input_manifest.json',
                         'reproduction/score_replay/regional_replay.py'}.issubset(pins))
        with self.assertRaises(ValueError):
            controller.replay_paths(dict(review, proposal='reproduction/score_replay/s03/pilot_proposal.json'))
        with self.assertRaises(ValueError):
            controller.replay_paths(dict(review, registry='../outside.json'))

    def test_inhibition_route_requires_its_own_evaluator_and_build_pins(self):
        review = {'registry': 'reproduction/score_replay/s04_original/registry.json',
                  'proposal': 'reproduction/score_replay/s04_original/pilot_proposal.json'}
        pins = controller.mandatory_sources('inhibition-pilot', review)
        self.assertTrue({review['registry'], review['proposal'],
                         'reproduction/score_replay/inhibition_build.py',
                         'reproduction/score_replay/inhibition_replay.py'}.issubset(pins))

    def test_s02_binds_original_oracle_and_new_component_wrapper(self):
        pins = controller.mandatory_sources('s02-pilot')
        self.assertTrue({'reproduction/score_replay/s02_replay.py',
                         'reproduction/score_replay/s02/protocol.json',
                         'reproduction/score_replay/s02/components.cpp',
                         'reproduction/score_replay/s02/original/independent_f_oracle.cpp',
                         'tests/test_s02_score_replay.py'}.issubset(pins))

    def test_initial_mark_binds_own_protocol_and_shared_original_oracle(self):
        pins = controller.mandatory_sources('initialmark-pilot')
        self.assertTrue({'reproduction/score_replay/initial_mark_replay.py',
                         'reproduction/score_replay/initial_mark/protocol.json',
                         'reproduction/score_replay/s02/components.cpp',
                         'reproduction/score_replay/s02/original/independent_f_oracle.cpp',
                         'tests/test_initial_mark_replay.py'}.issubset(pins))

    def test_original_li_binds_its_dedicated_evaluator(self):
        review = {'registry': 'reproduction/score_replay/original_li/registry.json',
                  'proposal': 'reproduction/score_replay/original_li/pilot_proposal.json'}
        pins = controller.mandatory_sources('li-pilot', review)
        self.assertTrue({review['registry'], review['proposal'],
                         'reproduction/score_replay/li_replay.py'}.issubset(pins))

    def test_partition_dependencies_require_actual_passed_rows_and_array_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = b'invented event array bytes'
            row = {'id':'row','passed':True,'status':'replayed','actual':{'native_array_components':{
                'path':'native_components.npz','sha256':hashlib.sha256(data).hexdigest()}}}
            archive = root/'evidence.zip'
            def save(report):
                with zipfile.ZipFile(archive,'w') as z:
                    z.writestr('science/rows/0/result.json',json.dumps(report))
                    z.writestr('science/rows/0/native_components.npz',data)
                return {'fresh_artifacts_sha256':{'evidence.zip':controller.sha(archive)}}
            with patch.object(controller,'ROOT',root):
                review = save(row)
                path = controller.materialize_fresh_scores(review,root/'out',{'row'})
                self.assertEqual(set(controller.read(path)['rows']),{'row'})
                with self.assertRaises(ValueError):
                    controller.materialize_fresh_scores(review,root/'missing',{'unknown'})
                review = save(dict(row,passed=False))
                with self.assertRaises(ValueError):
                    controller.materialize_fresh_scores(review,root/'failed',{'row'})
                bad = dict(row,actual={'native_array_components':{'path':'../escape','sha256':'x'}})
                review = save(bad)
                with self.assertRaises(ValueError):
                    controller.materialize_fresh_scores(review,root/'escape',{'row'})

    def test_partition_artifacts_and_interval_source_are_mandatory(self):
        review = {'registry':'reproduction/score_replay/california_blocks/registry.json',
                  'proposal':'reproduction/score_replay/california_blocks/pilot_proposal.json',
                  'fresh_artifacts_sha256':{'validation/reproductions/invented.zip':'fixture'}}
        pins = controller.mandatory_sources('blocks-pilot',review)
        self.assertTrue({'reproduction/score_replay/california_blocks_replay.py',
                         'validation/reproductions/invented.zip'}.issubset(pins))


class JointContinuationControls(unittest.TestCase):
    """Invented archives/indexes only; no library load, optimizer or score call."""
    def fixture(self, root):
        from experiments.s04b_joint_execution import driver
        self.driver = driver
        science = root/'experiments/s04b_joint_nuisance';science.mkdir(parents=True)
        execution = root/'experiments/s04b_joint_execution';execution.mkdir(parents=True)
        (execution/'operational_protocol.json').write_text('{}')
        def encoded(value):return json.dumps(value,sort_keys=True).encode()
        def digest(value):return hashlib.sha256(value).hexdigest()
        build = encoded({'passed':True,'library_sha256':digest(b'invented native bytes')})
        failed = encoded({'passed':False,'library_sha256':digest(b'invented native bytes'),
                          'build_receipt_sha256':digest(build)})
        audit = encoded({'passed':True,'scientific_pilot_passed':False})
        (root/'training_review.json').write_bytes(audit)
        checkpoint,trace = encoded({'constructed':True}),b'constructed trace\n'
        archive = root/'original.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name,raw in {'build/attenuation.so':b'invented native bytes','build/build_receipt.json':build,
                             'science/result.json':failed,'science/a.json':checkpoint,'science/a.attempts.jsonl':trace}.items():
                z.writestr(name,raw)
        policy = dict(case_id='a',failed_result_sha256=digest(failed),checkpoint_sha256=digest(checkpoint),
                      attempts_sha256=digest(trace),failed_archive_sha256=controller.sha(archive),audit_sha256=digest(audit))
        (science/'checkpoint_repair.json').write_bytes(encoded(policy))
        op = dict(resources=dict(batch_wall_seconds=14400,sampled_process_tree_rss_cap_bytes=6442450944,
                                 minimum_host_free_bytes=2147483648),pilot=['a','b'],sequence=['a','b','c'],
                  original_failure={'failed_archive_sha256':controller.sha(archive),'prior_scientific_seconds':17.})
        review = dict(stage='joint-continuation-pilot',driver_source_review_passed=True,scheduler_source_review_passed=True,
                      operational_run_id='invented-separate-run',operational_run_config_sha256='c'*64,
                      expires_utc='2099-01-01T00:00:00+00:00',numerical_attempt_id='invented-attempt',
                      wall_cap_seconds=60.,rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
                      case_ids=['a'],case_reservations_seconds={'a':30.},failed_archive='original.zip',
                      training_review='training_review.json')
        return review,op,{'constructed/source.py':'a'*64}

    def prepare(self, root, review, op, sources, output, prior=None):
        output.mkdir()
        with patch.object(controller,'ROOT',root),patch.object(self.driver,'verify_protocol',return_value=(op,{})),patch.object(self.driver,'source_identity',return_value=sources),patch.object(controller.subprocess,'run')as process:
            value = controller.joint_continuation(review,output,'invented-token',prior)
            process.assert_not_called()
            return value

    def accepted(self, root, review, op, sources, names):
        prior = root/'prior';(prior/'science').mkdir(parents=True)
        index = dict(cases=[{'case_id':n}for n in names],attempts=[],partial_case=None,
                     source_sha256=sources,operational_protocol_sha256=controller.sha(root/'experiments/s04b_joint_execution/operational_protocol.json'),
                     original_failure=op['original_failure'],budget={'total_seconds':17.,'pilot_seconds':17.})
        controller.write(prior/'science/index.json',index)
        controller.write(root/'index_review.json',{'passed':True,'index_sha256':controller.sha(prior/'science/index.json')})
        value=dict(review,prior_artifact_id=123,prior_archive_sha256='a'*64,prior_index_path='science/index.json',
                   prior_index_sha256=controller.sha(prior/'science/index.json'),prior_index_review='index_review.json')
        value.pop('training_review')
        return value,prior

    def test_new_route_requires_driver_scheduler_frozen_archive_and_review_pins(self):
        review={'failed_archive':'validation/invented.zip','training_review':'validation/invented_review.json'}
        pins=controller.mandatory_sources('joint-continuation-pilot',review)
        self.assertTrue({'experiments/s04b_joint_execution/driver.py','experiments/s04b_joint_execution/parallel_chunks.py',
                         'experiments/s04b_joint_execution/operational_protocol.json','tests/test_joint_execution_driver.py',
                         'tests/test_joint_parallel_chunks.py','experiments/s04b_joint_nuisance/pre_repair_source.zip',
                         review['failed_archive'],review['training_review']}.issubset(pins))
        review.update(prior_artifact_id=1,prior_index_review='validation/index_review.json')
        self.assertIn(review['prior_index_review'],controller.mandatory_sources('joint-continuation-campaign',review))

    def test_first_resume_keeps_original_binary_and_all_five_training_evidence_pins(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);review,op,sources=self.fixture(root);out=root/'out'
            admission,command=self.prepare(root,review,op,sources,out)
            self.assertEqual((out/'build/attenuation.so').read_bytes(),b'invented native bytes')
            self.assertEqual((out/'original_failure.zip').read_bytes(),(root/'original.zip').read_bytes())
            self.assertEqual(admission['case_ids'],['a']);self.assertIn('--resume-training',command)
            self.assertNotIn('--prior-index',command)
            policy=controller.read(root/'experiments/s04b_joint_nuisance/checkpoint_repair.json')
            self.assertEqual({k:v for k,v in admission['training_resume'].items()if k!='independent_review_passed'},
                             {k:v for k,v in policy.items()if k!='case_id'})

    def test_later_index_uses_exact_next_case_without_original_training_resume(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);review,op,sources=self.fixture(root)
            review,prior=self.accepted(root,review,op,sources,['a'])
            review.update(case_ids=['b'],case_reservations_seconds={'b':30.})
            admission,command=self.prepare(root,review,op,sources,root/'out',prior)
            self.assertIn('--prior-index',command);self.assertNotIn('--resume-training',command)
            self.assertNotIn('training_resume',admission);self.assertEqual(admission['prior_index_sha256'],review['prior_index_sha256'])

    def test_substituted_repeated_or_phase_crossing_case_is_rejected(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);review,op,sources=self.fixture(root)
            review,prior=self.accepted(root,review,op,sources,['a'])
            for i,names in enumerate((['a'],['c'],['b','c'],['b','b'])):
                with self.assertRaises(ValueError):
                    self.prepare(root,dict(review,case_ids=names,case_reservations_seconds={n:10. for n in names}),op,sources,root/str(i),prior)

    def test_campaign_requires_accepted_pilot_and_explicit_projection(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);review,op,sources=self.fixture(root)
            review,prior=self.accepted(root,review,op,sources,['a','b'])
            review.update(stage='joint-continuation-campaign',case_ids=['c'],case_reservations_seconds={'c':30.})
            with self.assertRaisesRegex(ValueError,'projection'):
                self.prepare(root,review,op,sources,root/'fail',prior)
            admission,_=self.prepare(root,dict(review,pilot_projection_review_passed=True,projection_sha256='b'*64),op,sources,root/'pass',prior)
            self.assertEqual(admission['projection_sha256'],'b'*64)

    def test_tampered_artifact_and_review_or_missing_new_envelope_fail(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);review,op,sources=self.fixture(root)
            for i,changes in enumerate(({'operational_run_id':''},{'operational_run_config_sha256':'bad'},
                                       {'driver_source_review_passed':False},{'scheduler_source_review_passed':False},
                                       {'wall_cap_seconds':14401},{'rss_cap_bytes':1},{'host_headroom_bytes':1})):
                with self.assertRaises(ValueError):self.prepare(root,dict(review,**changes),op,sources,root/str(i))
            (root/'training_review.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'training or review'):
                self.prepare(root,review,op,sources,root/'review-fail')
            with (root/'original.zip').open('ab')as stream:stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'artifact changed'):
                self.prepare(root,review,op,sources,root/'archive-fail')

    def test_failed_partial_and_unaccepted_index_block_continuation(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);review,op,sources=self.fixture(root)
            review,prior=self.accepted(root,review,op,sources,['a'])
            review.update(case_ids=['b'],case_reservations_seconds={'b':30.})
            path=prior/'science/index.json';index=controller.read(path);index['partial_case']={'case_id':'b'}
            path.write_text(json.dumps(index));review['prior_index_sha256']=controller.sha(path)
            (root/'index_review.json').write_text(json.dumps({'passed':True,'index_sha256':controller.sha(path)}))
            with self.assertRaisesRegex(ValueError,'failed partial'):
                self.prepare(root,review,op,sources,root/'partial',prior)
            (root/'index_review.json').write_text(json.dumps({'passed':False,'index_sha256':controller.sha(path)}))
            with self.assertRaisesRegex(ValueError,'independent acceptance'):
                self.prepare(root,review,op,sources,root/'review-fail',prior)

    def test_zero_exit_cannot_pass_failed_or_incomplete_batch(self):
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);(root/'science').mkdir();controller.write(root/'science/index.json',{})
            good=dict(passed=True,status='batch_complete',cases=[{'case_id':'a'}],index_sha256=controller.sha(root/'science/index.json'))
            for changes in ({'passed':False},{'cases':[]},{'cases':[{'case_id':'b'}]},{'index_sha256':'bad'},{}):
                (root/'science/result.json').write_text(json.dumps(dict(good,**changes)))
                if changes:
                    with self.assertRaises(ValueError):controller.joint_batch_passed(root,{'case_ids':['a']})
                else:controller.joint_batch_passed(root,{'case_ids':['a']})


if __name__ == '__main__':
    unittest.main()
