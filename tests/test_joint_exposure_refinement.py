"""Invented controls only: no historical/native evaluation or real optimizer."""
import ast
import copy
import datetime as dt
import inspect
import json
import math
from contextlib import ExitStack, nullcontext
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import OptimizeResult
from experiments.s04b_exposure_refinement import adapter as A, partial_fit as F, case_driver as D
from experiments.s04b_joint_execution import driver as legacy
from experiments.s04b_joint_nuisance import fit, model
from tests import test_joint_recovery as fixtures
TinyPhase=fixtures.TinyPhase
science=fixtures.science


THETA=np.array([-3.,0.,.3,0.,1.5,.2,math.log(30),math.log(7)])


class ExposurePhase(model.Phase):
    """Actual frozen evaluate guard with hand-authored empty arrays/reductions."""
    def __init__(self, coarse=-1e-8, fine=1e-8, fine_gradient=None):
        self.a=dict(event_time=np.array([]),event_x=np.array([]),event_background_density=np.array([]),parent_excess=np.array([]))
        self.lag=np.empty((0,0));self.event_r2=np.empty((0,0));self.M=0.;self.evaluations=0
        self.coarse,self.fine=coarse,fine;self.fine_gradient=fine_gradient;self.orders=[]
    def check(self):pass
    def baseline(self,theta):return [np.array([])]*3,2.,np.zeros(8)
    def deficit(self,theta,name,order):
        self.orders.append(order);v=np.zeros(9);v[0]=2.-(self.coarse if order==8 else self.fine)
        if order==16 and self.fine_gradient is not None:v[1:]=-np.asarray(self.fine_gradient)
        return v


def returned(x,value):
    return OptimizeResult(x=np.asarray(x),fun=float(value),success=True,status=0,message='invented',nfev=1,nit=1)


class RefinementControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.science=science()
    def owner(self,phase=None,optimizer=None):
        owner=A.Adapter(self.science,self.root,optimizer=optimizer or (lambda fn,x,**kw:returned(x,fn(x)[0])))
        phase=phase or ExposurePhase();wrapped=owner.wrap_phase(phase,30,395)
        owner.current=dict(model='LIplus_inclusive',start_index=4,method='L-BFGS-B',initial_parameters=THETA.tolist())
        return owner,wrapped,phase
    def call(self,owner,wrapped):
        def objective(x):
            score,g=wrapped.evaluate(x,'LIplus_inclusive',8);return score['nll'],g
        return owner.optimizer(objective,THETA,jac=True,bounds=fit.bounds(self.science,'LIplus_inclusive'),
            method='L-BFGS-B',options={k:self.science['solver'][k] for k in ('maxiter','maxls','ftol','gtol')})
    def events(self):return [json.loads(v) for v in (self.root/'refinement_events.jsonl').read_text().splitlines()]
    def test_actual_guard_refines_only_inside_optimizer_and_clears_before_fresh(self):
        owner,wrapped,phase=self.owner()
        with self.assertRaisesRegex(ArithmeticError,'full exposure'):wrapped.evaluate(THETA,'LIplus_inclusive',8)
        result=self.call(owner,wrapped)
        self.assertTrue(math.isfinite(result.fun));self.assertEqual(owner.refinement_accepted,1)
        self.assertIsNone(owner.callback);self.assertFalse(owner.refining)
        with self.assertRaisesRegex(ArithmeticError,'full exposure'):wrapped.evaluate(THETA,'LIplus_inclusive',8)
        self.assertEqual(phase.orders,[8,8,16,8])
        rows=self.events();self.assertEqual([v['event'] for v in rows],['refinement_start','refinement_end'])
        self.assertEqual(rows[0]['context']['phase'],'train');self.assertTrue(rows[1]['accepted'])
        self.assertGreaterEqual(rows[1]['fine_seconds'],0);self.assertGreaterEqual(rows[1]['coarse_seconds'],0)
        self.assertEqual(rows[0]['coarse']['origin_sha256'],D.sha(Path(model.__file__)))
    def test_unrelated_same_message_frame_does_not_trigger(self):
        class Foreign(ExposurePhase):
            def evaluate(self,*a,**k):raise ArithmeticError('Nonfinite or negative full exposure')
        owner,wrapped,_=self.owner(Foreign())
        with self.assertRaises(ArithmeticError):self.call(owner,wrapped)
        self.assertEqual(owner.refinement_sequence,0);self.assertIsNone(owner.callback)
    def test_tiny_negative_accepted_original_value_does_not_trigger(self):
        owner,wrapped,phase=self.owner(ExposurePhase(coarse=-1e-10))
        self.call(owner,wrapped)
        self.assertEqual(phase.orders,[8]);self.assertEqual(owner.refinement_sequence,0)
    def test_nonfinite_coarse_rejected_without_fine(self):
        owner,wrapped,phase=self.owner(ExposurePhase(coarse=float('nan')))
        with self.assertRaises(ArithmeticError):self.call(owner,wrapped)
        self.assertEqual(phase.orders,[8]);self.assertEqual(owner.refinement_sequence,0)
    def test_fine_gradient_mismatch_does_not_replace_original_error(self):
        owner,wrapped,_=self.owner(ExposurePhase(fine_gradient=np.ones(8)))
        with self.assertRaisesRegex(ArithmeticError,'full exposure'):self.call(owner,wrapped)
        self.assertEqual(owner.refinement_rejected,1);self.assertFalse(self.events()[-1]['accepted'])
        self.assertFalse(owner.refining);self.assertIsNone(owner.callback)
    def test_nonfinite_fine_return_retained_as_tags_and_rejected(self):
        class NonfiniteFine(ExposurePhase):
            def evaluate(self,theta,name='null',order=8,require_gradient=True):
                if order==16:return dict(P=0.,E=float('nan'),C=float('nan'),M=0.,joint=float('nan'),nll=float('nan')),np.full(8,np.inf)
                return super().evaluate(theta,name,order,require_gradient)
        owner,wrapped,_=self.owner(NonfiniteFine())
        with self.assertRaisesRegex(ArithmeticError,'full exposure'):self.call(owner,wrapped)
        rows=self.events();self.assertEqual(len(rows),2)
        self.assertEqual(rows[-1]['fine']['score']['E'],{'nonfinite':'nan'})
        self.assertEqual(rows[-1]['fine']['gradient'][0],{'nonfinite':'positive_infinity'})
        self.assertFalse(rows[-1]['comparison']['finite']);self.assertIsNone(owner.callback)
    def test_same_point_and_original_tolerances_not_only_positive_exposure(self):
        phase=ExposurePhase()
        try:phase.evaluate(THETA,'LIplus_inclusive',8)
        except ArithmeticError as exc:coarse=A.coarse_packet(exc,phase)
        fine,g=phase.evaluate(THETA,'LIplus_inclusive',16)
        self.assertTrue(A.compare_pair(coarse,fine,g,THETA,'LIplus_inclusive',self.science)['passed'])
        for changed in (dict(fine,P=1.),dict(fine,E=1.,C=-1.,joint=-1.,nll=1.),dict(fine,E=-1e-10)):
            self.assertFalse(A.compare_pair(coarse,changed,g,THETA,'LIplus_inclusive',self.science)['passed'])
    def test_heldout_or_order16_call_cannot_refine(self):
        owner,wrapped,phase=self.owner()
        held=owner.wrap_phase(ExposurePhase(coarse=-1e-8,fine=-1e-8),395,760)
        owner.callback=dict(phase=held,model='LIplus_inclusive',start_index=4,method='L-BFGS-B',callback_index=1,theta=THETA.tolist())
        with self.assertRaises(ArithmeticError):held.evaluate(THETA,'LIplus_inclusive',8)
        owner.callback=dict(owner.callback,phase=wrapped)
        with self.assertRaises(ArithmeticError):held.evaluate(THETA,'LIplus_inclusive',16)
        self.assertEqual(owner.refinement_sequence,0)
    def test_partial_loop_body_and_final_selection_are_exact_original_ast(self):
        original=ast.parse(inspect.getsource(fit.fit_arm)).body[0]
        resumed=ast.parse(inspect.getsource(F.resume_partial_fit)).body[0]
        i=next(i for i,v in enumerate(original.body) if isinstance(v,ast.For))
        j=next(i for i,v in enumerate(resumed.body) if isinstance(v,ast.For) and isinstance(v.iter,ast.Subscript))
        self.assertEqual(ast.dump(ast.Module(body=original.body[i].body,type_ignores=[])),ast.dump(ast.Module(body=resumed.body[j].body,type_ignores=[])))
        self.assertEqual(ast.dump(ast.Module(body=original.body[i+1:],type_ignores=[])),ast.dump(ast.Module(body=resumed.body[j+1:],type_ignores=[])))
    def partial(self):
        phase=TinyPhase();eligible=THETA.copy();eligible[5]=0;calls=[]
        def opt(fn,x,**kw):
            index=len(calls);calls.append(kw['method'])
            if index>=4:raise ArithmeticError('Nonfinite or negative full exposure')
            return returned(x,fn(x)[0])
        arm=fit.fit_arm(phase,'LIplus_inclusive',self.science,eligible,lambda v:None,opt)
        self.assertEqual(arm['resolved_starts'],[True]*4+[False]);return phase,eligible,arm
    def test_partial_suffix_runs_only_four_new_starts_preserves_prefix(self):
        phase,eligible,arm=self.partial();before=copy.deepcopy(arm);calls=[];trace=[]
        def opt(fn,x,**kw):calls.append(np.asarray(x).tolist());return returned(x,fn(x)[0])
        result=F.resume_partial_fit(phase,'LIplus_inclusive',self.science,eligible,arm,trace.append,opt)
        self.assertEqual(arm,before);self.assertEqual(result['records'][:4],arm['records'][:4]);self.assertEqual(result['candidates'][:5],arm['candidates'])
        self.assertEqual(calls,fit.starts(self.science,3,'LIplus_inclusive',eligible)[4:]);self.assertEqual(len(trace),8)
        self.assertTrue(result['passed']);self.assertEqual(result['resolved_starts'],[True]*8)
    def test_partial_failed_primary_uses_original_powell_and_fresh_gate(self):
        phase,eligible,arm=self.partial();methods=[]
        def opt(fn,x,**kw):
            methods.append(kw['method']);value=fn(x);value=value[0] if kw['jac'] else value
            if len(methods)==1:raise ArithmeticError('invented gradient failure')
            return returned(x,value+1.)  # Fresh discrepancy cannot be excused by refinement.
        result=F.resume_partial_fit(phase,'LIplus_inclusive',self.science,eligible,arm,lambda v:None,opt)
        self.assertEqual(methods,['L-BFGS-B','Powell']);self.assertFalse(result['passed']);self.assertEqual(result['not_run_starts'],[5,6,7])
        self.assertEqual(result['records'][-1]['fresh_nll_delta'],1.)


class WholeDriverControls(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RecoveryControls();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root
    def execute(self,late=False,partial=False):
        delegate,case,modules,_,_=self.fixture.startup_fixture()
        class Phase(TinyPhase):
            _grids={k:dict(space_nodes=1,time_nodes=1,parents=1,estimate=1) for k in (8,16)}
            def evaluate(self,theta,model='null',order=8,require_gradient=True):
                score,g=super().evaluate(theta,'null',order,require_gradient)
                score['joint']=np.float64(score['joint']);score['nll']=np.float64(score['nll'])
                return score,g
        def factory(rows,gm,start,end,*args):
            p=Phase();p.a={'event_time':np.array([start+1])};return p
        delegate.model.phase_from_rows=factory
        partial_report=partial_trace=None
        if partial:
            previous='invented';case['case_id']='S6_narrow_short_total_seed410603'
            oldroot=delegate.REPO/'validation/live_results/methodological_20261106/refitted_floor'
            (oldroot/(previous+'.json')).rename(oldroot/(case['case_id']+'.json'))
            def partial_arm(phase,name,protocol,eligible,checkpoint):
                index=-1
                def opt(fn,x,**kw):
                    nonlocal index
                    if kw['method']=='L-BFGS-B':index+=1
                    if name=='LIplus_inclusive' and index==4:raise ArithmeticError('Nonfinite or negative full exposure')
                    value=fn(x);return returned(x,value[0] if kw['jac'] else value)
                return fit.fit_arm(phase,name,protocol,eligible,checkpoint,opt)
            delegate.fit_arm=partial_arm
            prior=self.root/'partial';prior.mkdir()
            delegate.case_run(case,modules,None,self.fixture.science,prior,time.monotonic()+60,None)
            partial_report=D.read(prior/(case['case_id']+'.json'))
            partial_trace=[json.loads(v) for v in (prior/(case['case_id']+'.attempts.jsonl')).read_text().splitlines()]
            self.assertEqual(len(partial_trace),60);self.assertFalse(partial_report['passed'])
        original_adapter=A.Adapter
        def adapter(*args,**kw):
            def optimizer(fn,x,**opts):
                value=fn(x);return returned(x,value[0] if opts['jac'] else value)
            return original_adapter(*args,**kw,optimizer=optimizer)
        args=SimpleNamespace(case_id=case['case_id'],mode='partial' if partial else 'untouched',output=self.root/'out',failed_prior=self.root/'partial' if partial else None)
        for name in ('library','build_receipt','admission'):
            path=self.root/(name+'.fixture');path.write_bytes(b'{}');setattr(args,name,path)
        p=dict(case_ids=[case['case_id']],version='invented_amendment',original_scientific_protocol_sha256='old',failed_case={})
        slot=dict(wall_seconds=1200,scientific_seconds=1170,mode='untouched');grant={'numerical_attempt_id':'fixture'}
        D.write(args.admission,dict(source_sha256={},protocol_sha256=D.sha(D.HERE/'protocol.json')))
        now=time.monotonic()
        replacements=[(D,'verify_protocol',p),(D,'source_identity',{}),(D,'admission',(grant,slot,dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=2))),
            (legacy.frozen,'verify_inputs',[case]),(legacy.frozen,'runtime_identity',{'essential':{}}),(legacy.model,'archived',modules),
            (legacy.model,'Native',None),(legacy,'OrderedChunkScheduler',nullcontext()),(legacy,'runner_with_scheduler',delegate),(legacy,'verify_case',None)]
        with ExitStack() as stack:
            for obj,name,value in replacements:stack.enter_context(patch.object(obj,name,return_value=value))
            stack.enter_context(patch.object(D,'PROCESS_STARTED',now));stack.enter_context(patch.object(A,'Adapter',side_effect=adapter))
            if partial:stack.enter_context(patch.object(D,'load_partial',return_value=(partial_report,partial_trace)))
            if late:
                original=delegate.case_run
                def delayed(*a,**kw):
                    report=original(*a,**kw);D.PROCESS_STARTED=time.monotonic()-1171;return report
                delegate.case_run=delayed
            code=D.run(args)
        self.partial_original=partial_report
        return code,D.read(args.output/'result.json'),D.read(args.output/'cases'/(case['case_id']+'.json'))
    def test_original_case_run_numpy_scores_roundtrip_through_amended_driver(self):
        code,result,report=self.execute()
        self.assertEqual(code,0,result);self.assertTrue(result['scientific_passed']);self.assertTrue(report['passed'])
        self.assertEqual(len(report['outcomes']),5);self.assertTrue(all(type(v['gate_active']) is bool for v in report['outcomes']))
        self.assertEqual(result['actual_optimizer_attempts'],32);self.assertEqual(result['reused_optimizer_attempts'],0)
        self.assertEqual(result['refinement_census'],dict(started=0,accepted=0,rejected=0))
        self.assertEqual([v['phase'] for v in report['floor_checks']],['train']*3+['test']*3)
    def test_scientific_wall_cap_revokes_late_disposition(self):
        code,result,_=self.execute(late=True)
        self.assertEqual(code,1);self.assertFalse(result['handled']);self.assertTrue(result['scientific_clock_cap_exceeded'])
    def test_partial_original_case_run_reuses_three_arms_and_only_runs_tail(self):
        code,result,report=self.execute(partial=True)
        self.assertEqual(code,0,result);self.assertEqual(result['actual_optimizer_attempts'],4)
        self.assertEqual(result['reused_optimizer_attempts'],28)
        self.assertEqual(result['adapter']['physical_optimizer_calls'],[['LIplus_inclusive',i,'L-BFGS-B'] for i in range(4,8)])
        for name in ('null','LI','LIplus_immigrant'):
            self.assertEqual(report['fits'][name],self.partial_original['fits'][name])
            self.assertEqual(report['training_checks'][name],self.partial_original['training_checks'][name])
        self.assertEqual(report['fits']['LIplus_inclusive']['records'][:4],self.partial_original['fits']['LIplus_inclusive']['records'][:4])
        self.assertEqual(report['fits']['LIplus_inclusive']['candidates'][:5],self.partial_original['fits']['LIplus_inclusive']['candidates'])
        self.assertEqual(len(report['outcomes']),5)


if __name__=='__main__':unittest.main()
