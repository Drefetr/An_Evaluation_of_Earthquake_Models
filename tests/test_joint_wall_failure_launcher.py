"""Separate raw55/sealed56 launcher controls using invented public evidence."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile
from scripts import run_joint_wall_failure_continuation as L
from experiments import s04b_wall_failure_continuation as M
from experiments.s04b_wall_failure_continuation import host as H
from experiments.s04b_exposure_refinement import case_driver as D


class LauncherControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        for mod in (L,M,H):
            patch=mock.patch.object(mod,'ROOT' if mod is L else 'REPO',self.root);patch.start();self.addCleanup(patch.stop)
        def put(name,data):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(data if isinstance(data,str) else json.dumps(data),encoding='utf-8');return path
        self.put=put
        def ref(name):return {'path':name,'sha256':L.sha(self.root/name)}
        self.ref=ref;expiry=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).isoformat()
        put(L.SHARED,{'deadline_utc':expiry})
        self.p=dict(core_source_sha256={'core.py':''},producer_source_paths=[L.PACKAGE+'/protocol.json'],
            checker={'sources':['checker.py'],'test':'tests/checker.py'},shared_run={'expires_utc':expiry,'config_sha256':L.sha(self.root/L.SHARED)},
            hosts=[dict(host=i,case_ids=['case'+str(i)],case_outer_seconds=1200,whole_host_upper_seconds=3000) for i in range(5,9)])
        raw=self.root/'raw.zip'
        with zipfile.ZipFile(raw,'w') as z:z.writestr('host/index.json',b'{"records":55}')
        put('raw_review.json',{'passed':False,'audit_passed':True})
        self.p['base']={'archive':ref('raw.zip'),'review':ref('raw_review.json'),'index_member':'host/index.json','index_sha256':hashlib.sha256(b'{"records":55}').hexdigest()}
        put(L.PACKAGE+'/protocol.json',self.p)
        for name in L.mandatory_sources(self.p):
            if not (self.root/name).exists():put(name,'invented bytes')
        self.p['core_source_sha256']['core.py']=L.sha(self.root/'core.py');put(L.PACKAGE+'/protocol.json',self.p)
        put('sealed.json',{'records':56})
        review=dict(passed=True,audit_passed=True,review_kind='live_operational_failure_transition_review',live_agent_review=True,
            live_agent_review_performed=True,final_batch_agent_review_required=False,failure_accounting_valid=True,scientific_execution_passed=False,
            scientific_completion=False,index_sha256=L.sha(self.root/'sealed.json'),operational_continuation=ref(L.PACKAGE+'/protocol.json'),
            raw_archive=self.p['base']['archive'],raw_review=self.p['base']['review'],raw_index_sha256=self.p['base']['index_sha256'])
        put('seal_review.json',review)
        self.refs={'index':ref('sealed.json'),'review':ref('seal_review.json'),'raw_archive':ref('raw.zip'),'raw_review':ref('raw_review.json'),
            'raw_index_member':'host/index.json','raw_index_sha256':self.p['base']['index_sha256']}
        pins={n:L.sha(self.root/n) for n in L.mandatory_sources(self.p)}
        put('source.json',{'passed':True,'live_agent_review':True,'reviewed_files_sha256':pins})
        self.a=dict(schema='joint_wall_failure_continuation_admission_v1',independent_source_review='passed',scientific_completion=False,
            numerical_attempt_id='host-five',batch_id=5,case_ids=['case5'],child_attempt_ids={'case5':'child5'},whole_host_upper_seconds=3000,
            wall_cap_seconds=2400,rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,expires_utc=expiry,
            shared_config_sha256=L.sha(self.root/L.SHARED),operational_continuation=ref(L.PACKAGE+'/protocol.json'),
            source_review='source.json',source_review_sha256=L.sha(self.root/'source.json'),reviewed_files_sha256=pins,
            prior_archive='raw.zip',prior_archive_sha256=L.sha(raw),prior_review='seal_review.json',prior_review_sha256=L.sha(self.root/'seal_review.json'),
            prior_index_sha256=L.sha(self.root/'sealed.json'),sealed_predecessor=self.refs,prior_host_overhead=None)
        for target,name,value in [(H,'source_identity',self.p['core_source_sha256']),(D,'source_identity',self.p['core_source_sha256']),(H,'verify_protocol',self.p)]:
            patch=mock.patch.object(target,name,return_value=value);patch.start();self.addCleanup(patch.stop)
        patch=mock.patch.dict('os.environ',GITHUB_RUN_ATTEMPT='1');patch.start();self.addCleanup(patch.stop)
    def test_separate_raw55_and_sealed56_are_required(self):
        self.assertEqual(L.validate(self.a)[0]['host'],5)
        bad=copy.deepcopy(self.a);bad['prior_index_sha256']=self.p['base']['index_sha256']
        with self.assertRaises(ValueError):L.validate(bad)
    def test_seal_review_cannot_pretend_failed_host_passed(self):
        r=L.read(self.root/'seal_review.json');r['execution_id']='fake-second-host04'
        self.put('seal_review.json',r);self.a['prior_review_sha256']=L.sha(self.root/'seal_review.json');self.refs['review']=self.ref('seal_review.json')
        with self.assertRaisesRegex(ValueError,'relabel'):L.validate(self.a)
    def test_pin_gate_precedes_producer_import(self):
        self.put('core.py','changed')
        with mock.patch.object(H,'source_identity',side_effect=AssertionError('import used early')),\
             self.assertRaisesRegex(ValueError,'Reviewed source changed'):L.validate(self.a)
    def test_policy_and_mandatory_launcher_cannot_be_omitted(self):
        for key in (L.PACKAGE+'/protocol.json','scripts/run_joint_wall_failure_continuation.py'):
            bad=copy.deepcopy(self.a);del bad['reviewed_files_sha256'][key]
            self.put('source.json',{'passed':True,'live_agent_review':True,'reviewed_files_sha256':bad['reviewed_files_sha256']})
            bad['source_review_sha256']=L.sha(self.root/'source.json')
            with self.assertRaisesRegex(ValueError,'Incomplete source'):L.validate(bad)
    def test_retry_roster_cap_and_deadline_changes_reject(self):
        for key,value in [('batch_id',4),('case_ids',['S6_narrow_short_total_seed410615']),('wall_cap_seconds',2401),('scientific_completion',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):L.validate(dict(self.a,**{key:value}))
        with mock.patch.dict('os.environ',GITHUB_RUN_ATTEMPT='2'),self.assertRaises(ValueError):L.validate(self.a)
    def later(self):
        self.a.update(batch_id=6,case_ids=['case6'],child_attempt_ids={'case6':'child6'},sealed_predecessor=None)
        r=dict(passed=True,audit_passed=True,review_kind='live_agent_saved_output_review',live_agent_review=True,
            live_agent_review_performed=True,final_batch_agent_review_required=False,disposition_valid=True,scientific_completion=False,
            execution_id='host-five',artifact_sha256=self.a['prior_archive_sha256'],index_sha256=self.a['prior_index_sha256'],
            resource={'whole_workflow_overhead_beyond_all_child_outer_seconds':'12.5'})
        self.put('later_review.json',r);self.a.update(prior_review='later_review.json',prior_review_sha256=L.sha(self.root/'later_review.json'))
        self.a['prior_host_overhead']=dict(execution_id='host-five',seconds='12.5',review=self.ref('later_review.json'),archive=self.ref('raw.zip'))
        return r
    def test_later_overhead_requires_exact_unique_live_execution_evidence(self):
        self.later();self.assertEqual(L.validate(self.a)[0]['host'],6)
        for key,value in [('seconds','13'),('execution_id','not-host-five')]:
            bad=copy.deepcopy(self.a);bad['prior_host_overhead'][key]=value
            with self.assertRaisesRegex(ValueError,'Overhead differs'):L.validate(bad)
        r=self.later();r['live_agent_review']=False;self.put('later_review.json',r);self.a['prior_review_sha256']=L.sha(self.root/'later_review.json')
        with self.assertRaises(ValueError):L.validate(self.a)
    def test_prepare_does_not_replace_raw_index_with_seal_or_copy_prior_to_public_output(self):
        native=self.root/'native.zip'
        with zipfile.ZipFile(native,'w') as z:z.writestr('lib',b'invented');z.writestr('receipt',b'{}')
        old=dict(immutable_failure_reference={'archive':'native.zip','archive_sha256':L.sha(native),'library_member':'lib','build_receipt_member':'receipt'},
            original_native={'library_sha256':hashlib.sha256(b'invented').hexdigest(),'build_receipt_sha256':hashlib.sha256(b'{}').hexdigest()},
            scientific_protocol_sha256='original-science',shared_run=self.p['shared_run'])
        self.put('experiments/s04b_joint_remaining/protocol.json',old);self.put('experiments/s04b_exposure_refinement/protocol.json',{})
        out=Path(self.temp.name)/'output';out.mkdir();started=dt.datetime.now(dt.timezone.utc).isoformat()
        with mock.patch.object(L.subprocess,'check_output',return_value='invented-commit\n'):spec=L.prepare(self.a,out,started)
        self.assertEqual(L.read(out/'prior/host/index.json'),{'records':55})
        self.assertEqual(spec['command'][spec['command'].index('--prior-index')+1],str(self.root/'sealed.json'))
        self.assertNotIn('--failed-prior',spec['command']);self.assertEqual((out/'build/attenuation.so').read_bytes(),b'invented')
        grant=L.read(out/'admission.json');self.assertEqual(grant['operational_mode'],'wall_failure_continuation');self.assertNotIn('GITHUB_TOKEN',spec['env'])
    def test_workflow_unique_marker_same_active_concurrency_no_prior_upload(self):
        text=(Path(__file__).resolve().parents[1]/'.github/workflows/joint-wall-failure-continuation.yml').read_text()
        self.assertIn("'[wall-failure-continuation]') && 'reviewed-research-continuation'",text)
        self.assertIn("format('inactive-{0}-{1}', github.workflow, github.run_id)",text)
        self.assertIn('cancel-in-progress: false',text);self.assertNotIn('/prior/**',text)


if __name__=='__main__':unittest.main()
