"""Constructed admission/archive controls; no scientific model calls."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import zipfile

from scripts import run_joint_exposure_refinement as launch


class LauncherControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo'; self.root.mkdir()
        self.enter=mock.patch.object(launch,'ROOT',self.root); self.enter.start(); self.addCleanup(self.enter.stop)
        def put(name,value):
            p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(value) if not isinstance(value,str) else value,encoding='utf-8'); return p
        self.put=put
        self.expires=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).isoformat()
        put(launch.PACKAGE+'/__init__.py','')
        put(launch.PACKAGE+'/protocol.json',{'schema':'fixture'})
        put(launch.CHECKER+'/__init__.py','')
        design=put(launch.EVIDENCE+'/independent_design_review.json',{'passed':True})
        resources=put(launch.EVIDENCE+'/resources.json',{'deadline_utc':self.expires,
            'future_hosts':[{'case_ids':['caseA' if i==0 else 'caseB'],'case_outer_seconds':1806,
                             'whole_host_upper_seconds':3606} for i in range(8)]})
        for key,path in [('DESIGN_SHA',design),('RESOURCES_SHA',resources)]:
            patch=mock.patch.object(launch,key,launch.sha(path)); patch.start(); self.addCleanup(patch.stop)
        put(launch.SHARED,{'deadline_utc':self.expires})
        for name in launch.mandatory_sources():
            if not (self.root/name).exists(): put(name,'fixture')
        put('frozen.py','original dependency')
        self.deps={'frozen.py':launch.sha(self.root/'frozen.py')}
        fake=types.ModuleType('experiments.s04b_exposure_refinement')
        fake.host=types.SimpleNamespace(source_identity=lambda:self.deps)
        fake.case_driver=types.SimpleNamespace(source_identity=lambda:self.deps)
        patch=mock.patch.dict('sys.modules',{'experiments.s04b_exposure_refinement':fake})
        patch.start();self.addCleanup(patch.stop)
        pins={name:launch.sha(self.root/name) for name in launch.mandatory_sources()|set(self.deps)}
        src=put('source_review.json',{'passed':True,'live_agent_review':True,'reviewed_files_sha256':pins})
        prior=self.root/launch.FAILED_ARCHIVE;prior.parent.mkdir(parents=True,exist_ok=True)
        index=json.dumps({'records':[]}).encode()
        with zipfile.ZipFile(prior,'w') as z:z.writestr('host/index.json',index)
        audit=put(launch.FAILED_REVIEW,{'audit_passed':True,'live_agent_review':True,'passed':False,'artifact_sha256':launch.sha(prior),
            'disposition_valid':False,'index_sha256':hashlib.sha256(index).hexdigest()})
        for key,path in [('FAILED_ARCHIVE_SHA',prior),('FAILED_REVIEW_SHA',audit)]:
            patch=mock.patch.object(launch,key,launch.sha(path));patch.start();self.addCleanup(patch.stop)
        self.review=dict(schema='joint_exposure_refinement_admission_v1',independent_source_review='passed',
            scientific_completion=False,numerical_attempt_id='fixture-attempt',batch_id=1,case_ids=['caseA'],
            whole_host_upper_seconds=3606,wall_cap_seconds=3006,rss_cap_bytes=6442450944,
            host_headroom_bytes=2147483648,child_attempt_ids={'caseA':'fixture-child'},
            shared_config_sha256=launch.sha(self.root/launch.SHARED),expires_utc=self.expires,
            source_review='source_review.json',source_review_sha256=launch.sha(src),reviewed_files_sha256=pins,
            prior_archive=launch.FAILED_ARCHIVE,prior_archive_sha256=launch.sha(prior),
            prior_review=launch.FAILED_REVIEW,prior_review_sha256=launch.sha(audit),
            prior_index_sha256=hashlib.sha256(index).hexdigest())
        patch=mock.patch.dict('os.environ',{'GITHUB_RUN_ATTEMPT':'1'});patch.start();self.addCleanup(patch.stop)

    def test_exact_failed_predecessor_is_eligible_but_not_scientific_success(self):
        group,_,_=launch.validate(self.review)
        self.assertEqual(group['case_ids'],['caseA'])
        self.assertFalse(launch.read(self.root/launch.FAILED_REVIEW)['passed'])

    def test_budget_roster_deadline_and_retry_changes_fail(self):
        for key,value in [('case_ids',['caseB']),('wall_cap_seconds',3007),('scientific_completion',True),
                          ('batch_id',True),('child_attempt_ids',{}),('expires_utc','2000-01-01T00:00:00+00:00')]:
            with self.subTest(key=key):
                altered=copy.deepcopy(self.review);altered[key]=value
                with self.assertRaises(ValueError):launch.validate(altered)
        with mock.patch.dict('os.environ',{'GITHUB_RUN_ATTEMPT':'2'}),self.assertRaises(ValueError):
            launch.validate(self.review)

    def test_source_is_verified_before_producer_import(self):
        self.put('frozen.py','changed')
        with self.assertRaisesRegex(ValueError,'Reviewed source changed'):launch.validate(self.review)

    def test_unreviewed_dependency_fails(self):
        self.deps['extra.py']='not-reviewed'
        with self.assertRaisesRegex(ValueError,'Imported dependency'):launch.validate(self.review)

    def test_required_launcher_pin_cannot_be_omitted(self):
        key='scripts/run_joint_exposure_refinement.py'
        del self.review['reviewed_files_sha256'][key]
        p=self.put('source_review.json',{'passed':True,'live_agent_review':True,
                                       'reviewed_files_sha256':self.review['reviewed_files_sha256']})
        self.review['source_review_sha256']=launch.sha(p)
        with self.assertRaisesRegex(ValueError,'Incomplete amendment source'):launch.validate(self.review)

    def test_later_host_rejects_failed_or_unbound_predecessor(self):
        self.review.update(batch_id=2,case_ids=['caseB'],child_attempt_ids={'caseB':'next-child'})
        with self.assertRaisesRegex(ValueError,'accepted compact predecessor'):launch.validate(self.review)
        p=self.put(launch.FAILED_REVIEW,{'audit_passed':True,'live_agent_review':True,'disposition_valid':True,
            'artifact_sha256':self.review['prior_archive_sha256'],
            'index_sha256':self.review['prior_index_sha256']})
        self.review['prior_review_sha256']=launch.sha(p)
        self.assertEqual(launch.validate(self.review)[0]['case_ids'],['caseB'])

    def test_repacked_archive_with_same_index_is_not_accepted_as_reviewed_execution(self):
        self.review.update(batch_id=2,case_ids=['caseB'],child_attempt_ids={'caseB':'next-child'})
        audit={'audit_passed':True,'live_agent_review':True,'disposition_valid':True,
            'artifact_sha256':self.review['prior_archive_sha256'],'index_sha256':self.review['prior_index_sha256']}
        p=self.put(launch.FAILED_REVIEW,audit);self.review['prior_review_sha256']=launch.sha(p)
        with zipfile.ZipFile(self.root/launch.FAILED_ARCHIVE,'a') as z:z.writestr('unreviewed',b'changed execution')
        self.review['prior_archive_sha256']=launch.sha(self.root/launch.FAILED_ARCHIVE)
        with self.assertRaisesRegex(ValueError,'exact execution archive'):launch.validate(self.review)
        audit['artifact_sha256']=self.review['prior_archive_sha256'];audit['live_agent_review']=False
        p=self.put(launch.FAILED_REVIEW,audit);self.review['prior_review_sha256']=launch.sha(p)
        with self.assertRaisesRegex(ValueError,'live independent'):launch.validate(self.review)

    def test_consumed_final_validation_margin_cannot_extend_host(self):
        group=launch.validate(self.review)[0]
        early=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=10)).isoformat()
        late=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=100)).isoformat()
        self.assertGreater(launch.remaining_window(self.review,group,early),launch.remaining_window(self.review,group,late))
        exhausted=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=1051)).isoformat()
        with self.assertRaisesRegex(ValueError,'Complete case'):launch.remaining_window(self.review,group,exhausted)

    def test_archive_escape_duplicate_and_overwrite_rejected(self):
        import warnings
        for names in (['../escape'],['/absolute'],['a','a'],['a','a/../a']):
            with self.subTest(names=names):
                archive=Path(self.temp.name)/'malformed.zip'
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',UserWarning)
                    with zipfile.ZipFile(archive,'w') as z:
                        for name in names:z.writestr(name,b'payload')
                with self.assertRaises(ValueError):launch.extract(archive,Path(self.temp.name)/'out')
        archive=self.root/launch.FAILED_ARCHIVE;out=Path(self.temp.name)/'exact'
        launch.extract(archive,out)
        with self.assertRaises(FileExistsError):launch.extract(archive,out)

    def test_prepare_uses_original_native_and_only_new_host_output(self):
        native_path=self.root/'native.zip';library=b'pinned native fixture';receipt=b'{}'
        with zipfile.ZipFile(native_path,'w') as z:z.writestr('lib',library);z.writestr('receipt',receipt)
        old=dict(immutable_failure_reference={'archive':'native.zip','archive_sha256':launch.sha(native_path),
            'library_member':'lib','build_receipt_member':'receipt'},original_native={
            'library_sha256':hashlib.sha256(library).hexdigest(),'build_receipt_sha256':hashlib.sha256(receipt).hexdigest()},
            scientific_protocol_sha256='frozen-science',shared_run={'deadline_utc':self.expires})
        self.put('experiments/s04b_joint_remaining/protocol.json',old)
        out=Path(self.temp.name)/'launch';out.mkdir()
        started=dt.datetime.now(dt.timezone.utc).isoformat()
        with mock.patch.object(launch.subprocess,'check_output',return_value='fixture-commit\n'):
            spec=launch.prepare(self.review,out,started)
        self.assertIn('--failed-prior',spec['command'])
        self.assertIn('experiments.s04b_exposure_refinement.host',spec['command'])
        self.assertLessEqual(spec['wall_cap_seconds'],3006)
        self.assertGreater(spec['wall_cap_seconds'],1806)
        self.assertEqual((out/'build/attenuation.so').read_bytes(),library)
        self.assertNotIn('GITHUB_TOKEN',spec['env'])
        self.assertEqual(launch.read(out/'admission.json')['scientific_protocol_sha256'],'frozen-science')
        with self.assertRaises(ValueError):
            launch.prepare(self.review,out,(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=1051)).isoformat())


if __name__=='__main__':
    unittest.main()
