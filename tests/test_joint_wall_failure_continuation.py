"""Invented metadata/host controls; no native evaluation or process launch."""
import copy
import datetime as dt
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from experiments import s04b_wall_failure_continuation as M
from experiments.s04b_wall_failure_continuation import transition as T,host as H
from experiments.s04b_exposure_refinement import host as F
from experiments.s04b_joint_remaining import host as G
from tests.test_joint_exposure_refinement_host import report,records


def invented_base():
    p=copy.deepcopy(M.read(M.REPO/M.PROTOCOL));p['core_source_sha256']={}
    old=F.read(F.HERE/'protocol.json');old=copy.deepcopy(old)
    old['shared_run']['expires_utc']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=2)).isoformat()
    p['shared_run']=old['shared_run']
    index=dict(schema='joint_exposure_refinement_index_v1',records=records(old,55),
        attempts=[dict(case_id=n,seconds=1.,outer_seconds=2.) for n in old['full_sequence'][44:55]],
        scientific_source_sha256={},host_source_sha256={},protocol_sha256=p['numerical_protocol']['sha256'])
    census=dict(case_id=M.FAILURE,held_out_calls=0,new_outcomes_available=0,physical_optimizer_attempts=29)
    p['failure']['failure_census']=census
    case=dict(case_id=M.FAILURE,regime=6,seed=410615,input_sha256={},n_train=7,n_test=3,stratum='invented',
        thinning={},fixed_spatial_mark_law={},historical_comparisons=[],passed=False,status='unknown',
        error_type='TimeoutError',error='Joint experiment deadline',outcomes=[])
    result=dict(case_id=M.FAILURE,passed=False,scientific_passed=False,handled=False,disposition_valid=False,
        disposition='technical_failure',error_type='ValueError',error='Case optimizer records differ from trace',
        scientific_clock_cap_exceeded=True,wall_seconds=float(p['accounting']['failure_scientific_seconds']),
        numerical_attempt_id='failed-attempt',actual_optimizer_attempts=29,reused_optimizer_attempts=0,
        allocation={'scientific_seconds':2490,'wall_seconds':2520},numerical_amendment={})
    sup=dict(wall_seconds_including_cleanup=float(p['accounting']['failure_outer_seconds']))
    return p,old,(index,case,result,sup,dict(failure=census))


class TransitionControls(unittest.TestCase):
    def setUp(self):self.p,self.old,self.evidence=invented_base()
    def seal(self):
        with patch.object(T,'source_identity',return_value={}):return T.build_sealed(self.p,*self.evidence)
    def test_real_policy_only_retains_original_untouched_groups(self):
        p=M.verify_protocol();self.assertEqual(len(p['case_ids']),24);self.assertEqual([g['host'] for g in p['hosts']],[5,6,7,8])
        self.assertNotIn(M.FAILURE,p['case_ids']);self.assertNotIn('S5_broad_long_imm_seed410518',p['case_ids'])
    def test_seal_preserves_all_prefix_records_and_raw_failure_flags(self):
        before=copy.deepcopy(self.evidence);sealed=self.seal()
        self.assertEqual(self.evidence,before);self.assertEqual(sealed['records'][:55],before[0]['records'])
        self.assertEqual(sealed['attempts'][:11],before[0]['attempts']);self.assertFalse(sealed['passed'])
        self.assertEqual(sealed['counts']['wall_time_failure_histories'],1);self.assertEqual(sealed['counts']['computed_outcomes'],270)
        self.assertEqual(sealed['records'][-1]['outcomes'],[]);self.assertEqual(sealed['records'][-1]['primary_error']['type'],'TimeoutError')
        self.assertEqual(sealed['records'][-1]['secondary_error']['type'],'ValueError')
    def test_raw_failure_relabel_and_cap_clamping_rejected(self):
        for key,value in [('passed',True),('disposition','scientific_unknown'),('wall_seconds',2490.)]:
            with self.subTest(key=key):
                data=copy.deepcopy(self.evidence);data[2][key]=value
                with self.assertRaises(ValueError):T.failure_projection(self.p,*data[1:])
    def test_counts_never_interpret_failure_as_scientific_unknown_or_loss(self):
        sealed=self.seal();rows=sealed['records'];rows[-1]['disposition']='scientific_unknown'
        with self.assertRaises(ValueError):T.counts(rows)
        rows[-1]['disposition']='wall_time_failure';rows[-1]['outcomes']=[{'new_win':False}]
        with self.assertRaises(ValueError):T.counts(rows)
    def test_budget_uses_once_only_baseline_not_nested_science(self):
        b=self.seal()['budget'];self.assertEqual(b['accounted_seconds'],'37761.34182158000334')
        self.assertEqual(b['upper_bound_seconds'],'88974.45304182100310')
        self.assertEqual(b['remaining_case_slots_seconds'],35400)
        attempts=self.seal()['attempts']+[dict(case_id=self.p['case_ids'][0],seconds=1.,outer_seconds=2.)]
        a=T.budget(self.p,attempts);self.assertEqual(a['accounted_seconds'],'37763.34182158000334')
        overhead=dict(execution_id='later',seconds='10',review={'path':'r','sha256':'p'},archive={'path':'a','sha256':'q'})
        c=T.budget(self.p,attempts,[overhead]);self.assertEqual(c['upper_bound_seconds'],a['upper_bound_seconds'])
        with self.assertRaises(ValueError):T.budget(self.p,attempts,[overhead,overhead])
    def test_future_caps_and_roster_stay_strict(self):
        base=self.seal()['attempts']
        for row in [dict(case_id=M.FAILURE,seconds=1,outer_seconds=2),
                    dict(case_id=self.p['case_ids'][0],seconds=2490.00001,outer_seconds=2500),
                    dict(case_id=self.p['case_ids'][0],seconds=1,outer_seconds=2520.001)]:
            with self.assertRaises(ValueError):T.budget(self.p,base+[row])
    def test_failed_source_and_prefix_are_not_silently_accepted(self):
        data=copy.deepcopy(self.evidence);data[0]['records'][0]['case_id']='changed'
        with self.assertRaises(ValueError):T.build_sealed(self.p,*data)


class HostControls(unittest.TestCase):
    def setUp(self):
        self.p,self.old,self.evidence=invented_base();self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def guard_fixture(self,batch):
        with patch.object(T,'source_identity',return_value={}):index=T.build_sealed(self.p,*self.evidence)
        preceding=sum(len(g['case_ids']) for g in self.p['hosts'][:batch-5])
        index['records']+=records(self.old,56+preceding)[56:]
        index['attempts'] += [dict(case_id=n,seconds=1.,outer_seconds=2.) for n in self.p['case_ids'][:preceding]]
        index['counts']=T.counts(index['records']);index['budget']=T.budget(self.p,index['attempts'])
        names=self.p['hosts'][batch-5]['case_ids']
        a=dict(batch_id=batch,case_ids=names,child_attempt_ids={n:'attempt-'+n for n in names},operational_mode='wall_failure_continuation',
            operational_continuation=M.operational_reference(),scientific_source_sha256={},source_sha256={},protocol_sha256=self.p['numerical_protocol']['sha256'],
            prior_index_sha256='index',prior_review_sha256='review',prior_archive_sha256=self.p['base']['archive']['sha256'],
            sealed_predecessor={'index':{'sha256':'index'},'review':{'sha256':'review'}} if batch==5 else None)
        review=dict(passed=True,audit_passed=True,disposition_valid=True,review_kind='live_agent_saved_output_review',live_agent_review=True,
            final_batch_agent_review_required=False,scientific_completion=False,index_sha256='index',artifact_sha256=a['prior_archive_sha256'])
        return a,index,review
    def guarded(self,a,index,review):
        with patch.object(H,'verify_protocol',return_value=self.p),patch.object(H,'source_identity',return_value={}),\
             patch.object(T,'source_identity',return_value={}),patch.object(T,'base_evidence',return_value=self.evidence),\
             patch.object(H,'sealed_predecessor'),patch.object(H,'prior_overhead',return_value=None):
            return H.next_cases(self.old,a,index,review)
    def test_exact_host_boundaries_no_retry_source_disguise_or_prefix_relabel(self):
        a,index,review=self.guard_fixture(5);self.assertEqual(self.guarded(a,index,review)['host'],5)
        for mutation in ({'batch_id':4},{'case_ids':[M.FAILURE]},{'source_sha256':{'fake':'hash'}}):
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.guarded(dict(a,**mutation),index,review)
        index['records'][55]['disposition']='scientific_unknown'
        with self.assertRaisesRegex(ValueError,'Immutable'):self.guarded(a,index,review)
    def test_all_later_host_boundaries_require_live_acceptance(self):
        for batch in (6,7,8):
            a,index,review=self.guard_fixture(batch);self.assertEqual(self.guarded(a,index,review)['host'],batch)
            for key,value in [('live_agent_review',False),('final_batch_agent_review_required',True),('passed',False)]:
                with self.subTest(batch=batch,key=key),self.assertRaises(ValueError):self.guarded(a,index,dict(review,**{key:value}))
    def fixture(self,complete=True,technical=False,checker_passes=True):
        p,old=self.p,self.old;g=p['hosts'][0];names=g['case_ids'];token='invented';pins={'checker':'pin'}
        with patch.object(T,'source_identity',return_value={}):sealed=T.build_sealed(p,*self.evidence)
        prior=self.root/'sealed.json';review=self.root/'seal_review.json';config=self.root/'config.json'
        F.write(prior,sealed);F.write(review,{});F.write(config,{})
        old['shared_run']['config_sha256']=F.sha(config);p['shared_run']=old['shared_run']
        native=self.root/'lib';native.write_bytes(b'never loaded');build=self.root/'build';build.write_bytes(b'{}')
        old['original_native'].update(library_sha256=F.sha(native),build_receipt_sha256=F.sha(build))
        sr=self.root/'source';sr.write_bytes(b'{}')
        a=dict(mode='exposure_refinement_host_batch',operational_mode='wall_failure_continuation',operational_continuation=M.operational_reference(),
            batch_id=5,case_ids=names,child_attempt_ids={n:'child-'+n for n in names},numerical_attempt_id='new-host',
            source_sha256={},scientific_source_sha256={},protocol_sha256=F.sha(F.HERE/'protocol.json'),amendment_protocol_sha256=F.sha(F.HERE/'protocol.json'),
            host_batch_source_review_passed=True,checker_source_review_passed=True,shared_run=old['shared_run'],expires_utc=old['shared_run']['expires_utc'],
            rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
            library_sha256=F.sha(native),build_receipt_sha256=F.sha(build),prior_index_sha256=F.sha(prior),prior_review_sha256=F.sha(review),
            prior_archive_sha256='raw55',conductor_review={},source_commit='invented',source_review_sha256=F.sha(sr),checker_source_review_sha256=F.sha(sr),
            host_started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),execution_window_seconds=g['whole_host_upper_seconds']-600,
            sealed_predecessor={'index':{'path':'seal','sha256':F.sha(prior)},'review':{'path':'review','sha256':F.sha(review)}},prior_host_overhead=None)
        ap=self.root/'admission';F.write(ap,a)
        args=SimpleNamespace(output=self.root/'host',admission=ap,prior_index=prior,prior_review=review,config=config,source_review=sr,
            checker_review=sr,library=native,build_receipt=build,failed_prior=None)
        calls=[]
        def numerical_boundary(command,output,cap,admission,env,spec):
            calls.append(command);output.mkdir(parents=True);F.write(spec,{'command':command});F.write(output/'result.json',{'wall_seconds_including_cleanup':2.})
            if command[3]=='experiments.s04b_exposure_refinement.case_driver':
                self.assertEqual(command[4:6],['--mode','untouched'])
                science=Path(command[command.index('--output')+1]);(science/'cases').mkdir(parents=True);name=command[command.index('--case-id')+1]
                for fn in ('reuse_map.json','refinement_events.jsonl','execution_calls.jsonl'):(science/fn).write_bytes(b'{}\n')
                amendment={k:F.sha(science/f) for k,f in [('reuse_map_sha256','reuse_map.json'),('refinement_event_log_sha256','refinement_events.jsonl'),('execution_calls_sha256','execution_calls.jsonl')]}
                case=report(name,complete);case['numerical_amendment']=amendment;F.write(science/'cases/c.json',case);(science/'cases/t').write_bytes(b'{}\n')
                actual=dict(schema='joint_exposure_refinement_case_v1',case_id=name,handled=not technical,disposition_valid=not technical,status='terminal_disposition',
                    passed=complete,scientific_passed=complete,disposition='complete' if complete else 'scientific_unknown',source_sha256={},protocol_sha256=a['protocol_sha256'],
                    numerical_attempt_id=a['child_attempt_ids'][name],report_file='cases/c.json',report_sha256=F.sha(science/'cases/c.json'),trace_file='cases/t',trace_sha256=F.sha(science/'cases/t'),
                    numerical_amendment=amendment,refinement_census={'started':0,'accepted':0,'rejected':0},wall_seconds=1.,actual_optimizer_attempts=32,reused_optimizer_attempts=0)
                if not complete:actual.update(unknown_reason={},model_census={},terminal_solver_return={})
                F.write(science/'result.json',actual)
            else:
                self.assertEqual(command[3],p['checker']['module']);child=Path(command[command.index('--current')+1])
                F.write(Path(command[command.index('--output')+1]),dict(passed=checker_passes,audit_passed=checker_passes,disposition_valid=checker_passes,
                    index_sha256=F.sha(child/'index.json'),live_agent_review=False,live_agent_review_performed=False,scientific_completion=False,
                    final_batch_agent_review_required=True,checker_sources_sha256=pins,checker_source_review_sha256=F.sha(sr)))
        with patch.object(H,'verify_protocol',return_value=p),patch.object(F,'verify_protocol',return_value=old),patch.object(H,'source_identity',return_value={}),\
             patch.object(F.driver,'source_identity',return_value={}),patch.object(H,'check_source_reviews',return_value=pins),\
             patch.object(H,'next_cases',return_value=g),patch.object(G,'supervised',side_effect=numerical_boundary),patch.dict(F.os.environ,JOINT_NUMERICAL_LEASE_TOKEN=token):
            code=H.run(args)
        return code,F.read(args.output/'result.json'),args,calls,sealed
    def test_whole_frozen_group_preserves_failure_and_real_supervisor_field(self):
        code,result,args,calls,sealed=self.fixture();self.assertEqual(code,0,result)
        index=F.read(args.output/'index.json');self.assertEqual(index['records'][:56],sealed['records']);self.assertEqual(len(calls),10)
        self.assertEqual(index['counts']['processed_histories'],61);self.assertEqual(index['counts']['wall_time_failure_histories'],1)
        first=F.read(args.output/result['children'][0]['artifact']/'index.json')
        self.assertEqual(first['predecessor']['kind'],'sealed_failure_transition');self.assertIsNone(first['predecessor']['archive_sha256'])
        self.assertIsNone(index['predecessor']['archive_sha256']);self.assertEqual(index['attempts'][-1]['outer_seconds'],2.)
    def test_future_technical_failure_stops_without_sealing_or_retry(self):
        code,result,args,calls,_=self.fixture(technical=True);self.assertEqual(code,1);self.assertEqual(len(calls),1)
        self.assertFalse((args.output/'index.json').exists());self.assertEqual(result['status'],'stopped_requires_review')
    def test_checker_rejection_never_promotes_candidate(self):
        code,result,args,calls,_=self.fixture(checker_passes=False);self.assertEqual(code,1);self.assertEqual(len(calls),2)
        self.assertFalse((args.output/'index.json').exists())
    def test_genuine_new_finite_cap_unknown_is_separate_from_wall_failure(self):
        code,result,args,calls,_=self.fixture(complete=False);self.assertEqual(code,0,result)
        self.assertEqual(result['counts']['unknown_histories'],6);self.assertEqual(result['counts']['wall_time_failure_histories'],1)


if __name__=='__main__':unittest.main()
