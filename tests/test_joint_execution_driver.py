"""Constructed driver/index tests only; no scientific histories or fits."""
import copy,hashlib,json,math,tempfile,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from engine.cpu_build import build_shared
import numpy as np
from threadpoolctl import threadpool_limits
from experiments.s04b_joint_nuisance import model,fit,run as frozen,checkpoint
from experiments.s04b_joint_execution import driver
from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler,ParallelPhase
from test_s04b_joint_nuisance import fixture


class FullCaseEquivalence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.limits=threadpool_limits(limits=2);cls.limits.__enter__();cls.temp=tempfile.TemporaryDirectory(prefix='joint_driver_controls_')
        receipt=build_shared(model.HERE/'attenuation.cpp',Path(cls.temp.name)/'native',dependency_root=model.HERE);cls.native=model.Native(receipt['library'])
    @classmethod
    def tearDownClass(cls):
        try:cls.temp.cleanup()
        except PermissionError:pass
        cls.limits.__exit__(None,None,None)
    def test_delegated_full_case_matches_serial_science_exactly(self):
        with tempfile.TemporaryDirectory()as temp,OrderedChunkScheduler()as scheduler:
            repo=Path(temp);root=repo/'reproduction/synthetic';root.mkdir(parents=True)
            old=repo/'validation/live_results/methodological_20261106/refitted_floor';old.mkdir(parents=True)
            np.savez(root/'rows.npz',rows=np.zeros((4,4)))
            for name,value in [('states.json',{}),('expected.json',{}),('receipt.json',{'counters':{}})]:checkpoint.write(root/name,value)
            checkpoint.write(old/'constructed.json',{})
            case=dict(case_id='constructed',regime=4,seed=1,history='rows.npz',fits={},states='states.json',expected='expected.json',generator_receipt='receipt.json',n_train=3,n_test=3)
            protocol=frozen.read(model.HERE/'protocol.json');theta=np.array([math.log(.2),.2,.35,math.log(.05),1.3,0.,math.log(30),math.log(7)])
            generator=SimpleNamespace(MATCHED_NAMES=['fixture'],ROSTER={'fixture':(None,None,0.,30.,7.)},Law=lambda *a:SimpleNamespace(a=theta[0],d=theta[1],n=theta[2],c=.05,p=theta[4],r=.7),fitting_metadata=lambda law:{'beta':2.,'sigma_km':2.})
            def historical(phase,case,old,expected,states,fits,label):
                score,_=phase.evaluate(theta,'null');return score,[dict(phase=label,model=m,actual_nll=score['nll'],expected_nll=score['nll'],absolute_delta=0.,tolerance=1e-9)for m in fit.MODELS]
            score=fixture(self.native).evaluate(theta,'null')[0]
            comparisons=[dict(model=m,gate=g,saved_procedure_joint=score['joint'])for m in fit.MODELS for g in(('raw',)if m=='LI'else('raw','BIC'))]
            def fitted(phase,name,protocol,eligible,callback):
                def fixed(fun,x,**kwargs):
                    values=eligible[:len(x)];v=fun(values);return SimpleNamespace(x=np.array(values),fun=v[0]if isinstance(v,tuple)else v,success=True,status=0,message='invented fixed-return optimizer',nfev=1,nit=0)
                return fit.fit_arm(phase,name,protocol,eligible,callback,optimizer=fixed)
            original_factory=model.phase_from_rows;reports=[]
            for mode in('serial','scheduled'):
                delegate=driver.runner_with_scheduler(scheduler)
                def make_phase(*args):
                    phase=fixture(self.native)
                    if mode=='serial':return phase
                    parallel=ParallelPhase(phase.a,phase.m,{},self.native,scheduler=scheduler)
                    parallel._grids=phase._grids;parallel.plan=lambda o:parallel._grids[o];return parallel
                delegate.model.phase_from_rows=make_phase;output=repo/mode;output.mkdir()
                with patch.object(delegate,'REPO',repo),patch.object(delegate,'compare_historical',return_value=comparisons),patch.object(delegate,'historical_floor',side_effect=historical),patch.object(delegate,'fit_arm',side_effect=fitted):
                    report=delegate.case_run(case,{'generator':generator},self.native,protocol,output,math.inf)
                self.assertTrue(report['passed'],report.get('error'));reports.append(report)
            self.assertIs(model.phase_from_rows,original_factory)
            for report in reports:
                for key in('current_attempt_wall_seconds','wall_seconds'):report.pop(key)
            self.assertEqual(checkpoint.dumps(reports[0],sort_keys=True),checkpoint.dumps(reports[1],sort_keys=True))
    def test_factory_is_local_and_preserves_original_constructor_inputs(self):
        sentinel=model.phase_from_rows;serial=fixture(self.native)
        with OrderedChunkScheduler()as scheduler:
            delegate=driver.runner_with_scheduler(scheduler)
            with patch.object(model,'phase_from_rows',return_value=serial)as constructor:
                phase=delegate.model.phase_from_rows('invented argument')
            constructor.assert_called_once_with('invented argument');self.assertIsInstance(phase,ParallelPhase)
            self.assertIs(phase.a,serial.a);self.assertIs(phase.m,serial.m);self.assertIs(phase.native,self.native)
        self.assertIs(model.phase_from_rows,sentinel)


class IndexAndBudgetControls(unittest.TestCase):
    def setUp(self):
        self.op={'pilot':['a','b'],'sequence':['a','b','c','d'],'science_protocol_sha256':'science','original_failure':{'prior_scientific_seconds':17.}}
        self.current=dict(source_sha256={'driver':'pin'},operational_protocol_sha256='op',runtime={'essential':{'runtime':'pin'}},library_sha256='lib',build_receipt_sha256='build')
        self.index=driver.new_index(self.op,self.current)
    def test_fixed_order_no_repeat_or_phase_crossing(self):
        self.assertEqual(driver.next_batch(self.index,self.op,['a']),'pilot')
        for batch in([],['a','a'],['b'],['a','b'],['c']):
            with self.assertRaises(ValueError):driver.next_batch(self.index,self.op,batch)
        self.index['cases']=[{'case_id':'a'},{'case_id':'b'}]
        self.assertEqual(driver.next_batch(self.index,self.op,['c','d']),'campaign')
        with self.assertRaises(ValueError):driver.next_batch(self.index,self.op,['b'])
    def test_failed_attempt_time_is_counted_once(self):
        self.index['attempts']=[dict(attempt_id='old-failed',seconds=3.,phase='pilot'),dict(attempt_id='new-complete',seconds=5.,phase='campaign')]
        self.index['budget']=dict(total_seconds=25.,pilot_seconds=20.)
        self.assertEqual(driver.charged(self.index,self.op),(25.,20.))
        self.index['attempts'].append(self.index['attempts'][0].copy())
        with self.assertRaisesRegex(ValueError,'Duplicate'):driver.charged(self.index,self.op)
    def test_tampered_or_nonfinite_cost_is_rejected(self):
        self.index['budget']['total_seconds']=0.
        with self.assertRaises(ValueError):driver.charged(self.index,self.op)
        self.index=driver.new_index(self.op,self.current);self.index['attempts']=[dict(attempt_id='bad',seconds=float('nan'),phase='pilot')]
        with self.assertRaises(ValueError):driver.charged(self.index,self.op)
    def test_failed_partial_index_cannot_automatically_continue(self):
        with tempfile.TemporaryDirectory()as temp:
            base=Path(temp);prior=base/'prior';prior.mkdir();out=base/'out';out.mkdir()
            self.index['partial_case']={'case_id':'a','status':'failed'};checkpoint.write(prior/'index.json',self.index)
            review=dict(passed=True,index_sha256=driver.sha(prior/'index.json'));checkpoint.write(prior/'review.json',review)
            args=SimpleNamespace(prior_index=prior/'index.json',prior_review=prior/'review.json')
            admission=dict(prior_index_sha256=driver.sha(args.prior_index),prior_review_sha256=driver.sha(args.prior_review))
            with self.assertRaisesRegex(ValueError,'partial fit'):driver.accepted_index(args,admission,self.op,self.current,[],out)
    def test_bound_copy_rejects_tampering_and_overwrite(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);source=root/'source';source.mkdir();target=root/'target';target.mkdir();checkpoint.write(source/'case.json',{'x':1})
            pin=driver.sha(source/'case.json');driver.copy_bound(source,target,'case.json',pin)
            self.assertEqual((source/'case.json').read_bytes(),(target/'case.json').read_bytes())
            with self.assertRaisesRegex(ValueError,'Duplicate'):driver.copy_bound(source,target,'case.json',pin)
            checkpoint.write(source/'case.json',{'x':2})
            with self.assertRaisesRegex(ValueError,'changed'):driver.copy_bound(source,target,'case.json',pin)
    def test_projection_uses_prior_training_plus_resumed_test_cost(self):
        with tempfile.TemporaryDirectory()as temp:
            output=Path(temp);names=list('abcdef');cases=[dict(case_id=n,parents_train=1,parents_test=1,n_train=1,n_test=1)for n in names]
            records=[]
            for i,name in enumerate(names[:5]):
                report=dict(case_id=name,wall_seconds=20. if i==0 else 1.,current_attempt_wall_seconds=2. if i==0 else 1.,prior_training_attempt_seconds=18. if i==0 else 0.,plan_dimensions={'train':{'8':dict(space_nodes=2,parents=1)}})
                file=name+'.json';checkpoint.write(output/file,report);records.append(dict(case_id=name,file=file))
            estimate=driver.remaining_projection(cases,{'cases':records},{'pilot':names[:5]},output)
            self.assertEqual(estimate['remaining_seconds'],60.)
            self.assertNotEqual(estimate['remaining_seconds'],6.)
    def test_final_serialization_deadline_is_checked_after_writing(self):
        with tempfile.TemporaryDirectory()as temp:
            output=Path(temp);records=[]
            for i in range(80):
                file=str(i)+'.json';checkpoint.write(output/file,dict(floor_checks=[{}]*6,historical_comparisons=[{}]*5));records.append({'file':file})
            now={'value':0.};original=driver.write
            def late_write(path,value):
                original(path,value)
                if Path(path).name=='summary.json':now['value']=2.
            with patch.object(frozen,'aggregate',return_value=[{'constructed':True}]),patch.object(driver,'write',side_effect=late_write),patch.object(driver.time,'monotonic',side_effect=lambda:now['value']):
                with self.assertRaisesRegex(ValueError,'summary serialization'):driver.final_summary({'cases':records},{},output,1.)
            self.assertTrue((output/'summary.json').exists())
            with patch.object(frozen,'aggregate',return_value=[{'constructed':True}]),patch.object(driver.time,'monotonic',return_value=0.):
                self.assertEqual(driver.final_summary({'cases':records},{},output,1.),driver.sha(output/'summary.json'))
    def test_unavailable_partial_checkpoint_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory()as temp:
            index={'cases':[],'partial_case':{'case_id':'a','file':'missing.json'}}
            value=driver.fit_census(index,Path(temp));self.assertEqual(value['completed_case_fit_arms'],0)
            self.assertIsNone(value['partial_fit_checkpoint']['recorded_fit_arms']);self.assertIsNone(value['partial_fit_checkpoint']['recorded_completed_fit_arm_names'])


class BatchControls(unittest.TestCase):
    def exercise(self,base,name,prior=None,fail=False,wall=30.,cap=100.,attempt=None):
        op=dict(pilot=['a','b'],sequence=['a','b','c'],science_protocol_sha256='invented-science',original_failure={'prior_scientific_seconds':17.},resources=dict(campaign_aggregate_seconds=cap,pilot_aggregate_seconds=cap,batch_wall_seconds=100.))
        cases=[dict(case_id=v,n_train=3,n_test=3)for v in op['sequence']]
        folder=base/name;lib=base/'library';build=base/'build';lib.write_bytes(b'invented library identifier only');build.write_bytes(b'invented build identifier only')
        args=SimpleNamespace(output=folder,library=lib,build_receipt=build,admission=base/(name+'.admission.json'),prior_index=None,prior_review=None,resume_training='invented',resume_review='invented',resume_archive='invented')
        case='a';grant=dict(numerical_attempt_id=attempt or name,phase='pilot',wall_seconds=wall,expires_utc='2099-01-01T00:00:00+00:00',case_ids=['a'],case_reservations_seconds={'a':1.})
        if prior:
            args.prior_index=prior/'index.json';args.prior_review=base/(name+'.review.json');args.resume_training=args.resume_review=args.resume_archive=None
            checkpoint.write(args.prior_review,dict(passed=True,index_sha256=driver.sha(args.prior_index)))
            grant.update(prior_index_sha256=driver.sha(args.prior_index),prior_review_sha256=driver.sha(args.prior_review),case_ids=['b'],case_reservations_seconds={'b':1.});case='b'
        checkpoint.write(args.admission,grant);calls=[]
        def fake_case(case,modules,native,science,out,deadline,resume):
            calls.append((case['case_id'],resume is not None));trace=out/(case['case_id']+'.attempts.jsonl');trace.write_text('{}\n')
            arms={m:dict(passed=True,required_starts=8,resolved_starts=[True]*8)for m in('null',*fit.MODELS)}
            report=dict(case_id=case['case_id'],passed=not fail,status='complete'if not fail else'unknown',training_selections_frozen=True,fits=arms,outcomes=[{}]*5,floor_checks=[{}]*6,historical_comparisons=[{}]*5,n_train=3,n_test=3,training_checks={m:{'passed':True}for m in arms},input_sha256={},attempts_sha256=driver.sha(trace))
            checkpoint.write(out/(case['case_id']+'.json'),report);return report
        with ExitStack()as stack:
            stack.enter_context(patch.object(driver,'verify_protocol',return_value=(op,{})))
            stack.enter_context(patch.object(driver,'check_admission',return_value=grant))
            stack.enter_context(patch.object(frozen,'runtime_identity',return_value={'essential':{'invented':'fixed'}}))
            stack.enter_context(patch.object(frozen,'verify_inputs',return_value=cases))
            stack.enter_context(patch.object(frozen,'load_training_resume',return_value={'case_id':'a'}))
            stack.enter_context(patch.object(model,'archived',return_value={}))
            stack.enter_context(patch.object(model,'Native',return_value=object()))
            stack.enter_context(patch.object(driver,'runner_with_scheduler',return_value=SimpleNamespace(case_run=fake_case)))
            code=driver.run(args)
        return code,folder,calls
    def test_first_partial_training_then_exact_complete_case_reuse(self):
        with tempfile.TemporaryDirectory()as temp:
            base=Path(temp);code,first,calls=self.exercise(base,'first');self.assertEqual(code,0);self.assertEqual(calls,[('a',True)])
            original=(first/'cases/a.json').read_bytes();code,second,calls=self.exercise(base,'second',prior=first)
            self.assertEqual(code,0);self.assertEqual(calls,[('b',False)]);self.assertEqual((second/'cases/a.json').read_bytes(),original)
            index=driver.read(second/'index.json');self.assertEqual([x['case_id']for x in index['cases']],['a','b'])
            self.assertEqual(len(index['attempts']),2);self.assertEqual(index['cases'][0]['reused_fit_arms'],4);self.assertEqual(index['cases'][1]['new_fit_arms'],4)
            self.assertAlmostEqual(index['budget']['total_seconds'],17.+sum(x['seconds']for x in index['attempts']),delta=1e-12)
    def test_failed_case_is_retained_charged_and_not_accepted(self):
        with tempfile.TemporaryDirectory()as temp:
            code,output,calls=self.exercise(Path(temp),'failed',fail=True)
            self.assertEqual(code,1);index=driver.read(output/'index.json');self.assertEqual(index['cases'],[])
            self.assertEqual(index['partial_case']['case_id'],'a');self.assertGreater(index['budget']['total_seconds'],17.)
            self.assertFalse(driver.read(output/'attempts/failed.json')['passed']);self.assertEqual(calls,[('a',True)])
            result=driver.read(output/'result.json');self.assertEqual(result['completed_case_fit_arms'],0)
            self.assertEqual(result['partial_fit_checkpoint']['recorded_fit_arms'],4)
            self.assertEqual(len(result['partial_fit_checkpoint']['recorded_completed_fit_arm_names']),4)
            self.assertNotIn('cumulative_distinct_fit_arms',result)
    def test_exhausted_budget_stops_before_any_case_call(self):
        with tempfile.TemporaryDirectory()as temp:
            code,output,calls=self.exercise(Path(temp),'cap',cap=18.,wall=30.)
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertIn('Aggregate allowance',driver.read(output/'result.json')['error'])
    def test_duplicate_attempt_cannot_overwrite_prior_receipt(self):
        with tempfile.TemporaryDirectory()as temp:
            base=Path(temp);_,first,_=self.exercise(base,'first');old=(first/'attempts/first.json').read_bytes()
            code,second,calls=self.exercise(base,'second',prior=first,attempt='first')
            self.assertEqual(code,1);self.assertEqual(calls,[]);self.assertEqual((second/'attempts/first.json').read_bytes(),old)
            self.assertTrue(driver.read(second/'result.json')['unindexed_attempt_requires_conductor_accounting'])


if __name__=='__main__':unittest.main()
