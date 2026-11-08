"""Admission controls on invented files; no scientific evaluation or optimizer."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile
from scripts import run_joint_exposure_diagnostic as launcher


class ExposureAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base/'repo'
        self.repo.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(launcher,'ROOT',self.repo).start()
        patch.dict(os.environ,{'GITHUB_RUN_ATTEMPT':'1'}).start()
        package=types.ModuleType('experiments.s04b_exposure_diagnostic')
        package.run=types.SimpleNamespace(source_identity=lambda:{})
        patch.dict(sys.modules,{'experiments.s04b_exposure_diagnostic':package}).start()
        names=['scripts/run_joint_exposure_diagnostic.py','.github/workflows/joint-exposure-diagnostic.yml',
            'scripts/supervise_research.py','experiments/s04b_exposure_diagnostic/__init__.py',
            'experiments/s04b_exposure_diagnostic/numerics.py',
            'experiments/s04b_exposure_diagnostic/run.py','experiments/s04b_exposure_diagnostic/protocol.json',
            'tests/test_joint_exposure_diagnostic.py','tests/test_joint_exposure_diagnostic_launcher.py',
            'requirements-cpu.txt','requirements.txt',
            'validation/reproductions/continuation_20261107/shared_run_config.json']
        for name in names:
            target=self.repo/name
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text('invented fixture\n',encoding='utf-8')
        self.shared=self.repo/names[-1]
        self.shared.write_text(json.dumps({'deadline_utc':'2099-01-01T00:00:00+00:00'}),encoding='utf-8')
        self.archive=self.repo/launcher.ARCHIVE
        self.archive.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(self.archive,'w') as z:
            z.writestr('retained.json','{"invented":true}')
        archive_sha=launcher.sha(self.archive)
        patch.object(launcher,'ARCHIVE_SHA',archive_sha).start()
        pins={name:launcher.sha(self.repo/name) for name in names}
        self.source=self.repo/'review.json'
        self.source.write_text(json.dumps({'passed':True,'live_agent_review':True,'source_sha256':pins}),encoding='utf-8')
        self.review=dict(case_id=launcher.CASE,orders=[8,16],parameter_vectors=1,optimizer_calls=0,
            held_out_calls=0,wall_cap_seconds=300,scientific_completion=False,independent_source_review='passed',
            numerical_attempt_id='invented-attempt',shared_run_config_sha256=launcher.sha(self.shared),
            expires_utc='2099-01-01T00:00:00+00:00',archive=launcher.ARCHIVE,archive_sha256=archive_sha,
            source_review='review.json',source_review_sha256=launcher.sha(self.source),source_sha256=pins)

    def test_plan_retains_input_and_bounds_one_diagnostic_without_launch(self):
        out=self.base/'out';out.mkdir()
        with patch.object(launcher.subprocess,'run',side_effect=AssertionError('No execution in plan')):
            spec=launcher.plan(self.review,out)
        self.assertEqual((out/'prior/retained.json').read_text(),'{"invented":true}')
        self.assertEqual(spec['wall_cap_seconds'],300)
        self.assertEqual(spec['command'][-2:],['--wall-seconds','300'])
        self.assertEqual(set(spec['env'].values()),{'2'})
        self.assertNotIn('fit',spec['command'])

    def test_scope_expansion_is_rejected(self):
        for name,value in [('case_id','another'),('orders',[8]),('parameter_vectors',2),
            ('optimizer_calls',1),('held_out_calls',1),('wall_cap_seconds',301),('scientific_completion',True)]:
            with self.subTest(name=name):
                changed=copy.deepcopy(self.review);changed[name]=value
                with self.assertRaises(ValueError): launcher.validate(changed)

    def test_changed_dependency_is_rejected(self):
        (self.repo/'requirements.txt').write_text('changed',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Diagnostic source changed'):launcher.validate(self.review)

    def test_missing_review_pin_is_rejected(self):
        changed=copy.deepcopy(self.review);changed['source_sha256'].pop('scripts/supervise_research.py')
        self.source.write_text(json.dumps({'passed':True,'live_agent_review':True,'source_sha256':changed['source_sha256']}))
        changed['source_review_sha256']=launcher.sha(self.source)
        with self.assertRaisesRegex(ValueError,'Incomplete diagnostic source'):launcher.validate(changed)

    def test_rerun_and_expired_deadline_are_rejected(self):
        with patch.dict(os.environ,{'GITHUB_RUN_ATTEMPT':'2'}):
            with self.assertRaisesRegex(ValueError,'retry'):launcher.validate(self.review)
        changed=copy.deepcopy(self.review);changed['expires_utc']='2000-01-01T00:00:00+00:00'
        self.shared.write_text(json.dumps({'deadline_utc':changed['expires_utc']}))
        changed['shared_run_config_sha256']=launcher.sha(self.shared)
        with self.assertRaisesRegex(ValueError,'Insufficient deadline'):launcher.validate(changed)

    def test_changed_archive_is_rejected(self):
        self.archive.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'archive changed'):launcher.validate(self.review)

    def test_archive_escape_is_rejected(self):
        with zipfile.ZipFile(self.archive,'w') as z:z.writestr('../outside','bad')
        current=launcher.sha(self.archive)
        changed=copy.deepcopy(self.review);changed['archive_sha256']=current
        out=self.base/'out';out.mkdir()
        with patch.object(launcher,'ARCHIVE_SHA',current):
            with self.assertRaisesRegex(ValueError,'Archive member escapes'):launcher.plan(changed,out)
        self.assertFalse((out/'outside').exists())


if __name__=='__main__':
    unittest.main()
