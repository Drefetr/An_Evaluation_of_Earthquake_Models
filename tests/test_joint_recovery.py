"""Invented deterministic objectives and corruption fixtures; no saved-history calls."""
import copy
import datetime
import hashlib
import inspect
import json
import math
import os
from collections import Counter, defaultdict
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import numpy as np
from scipy.optimize import OptimizeResult
from experiments.s04b_joint_nuisance import fit
from experiments.s04b_joint_recovery import adapter, driver


class TinyPhase:
    def __init__(self):
        self.a={'event_time':np.arange(3)}
        self.fail=None
        self.calls=0
    def evaluate(self, theta, model='null', order=8, require_gradient=True):
        self.calls+=1
        if self.fail:
            exc,self.fail=self.fail,None
            raise exc
        x=np.asarray(theta,dtype=float)
        g=2*x.copy()
        if model=='null':g[5:]=0
        value=float(np.dot(x[:5],x[:5]) if model=='null' else np.dot(x,x))
        return dict(P=-value,E=0.,C=-0.,M=0.,joint=-value,nll=value),g


def returned(x,value):
    return OptimizeResult(x=np.asarray(x),fun=float(value),success=True,status=0,message='invented return',nfev=1,nit=1)


def science():
    return driver.read(driver.legacy.SCIENCE/'protocol.json')


def partial_fixture():
    protocol=science();phase=TinyPhase();trace=[];fitted={};checks={}
    initial=[-3.,0.,.3,0.,1.5,0.,np.log(30.),np.log(7.)]
    for model in ('null','LI','LIplus_immigrant'):
        current=-1
        def optimizer(objective,x,*,jac,bounds,method,options):
            nonlocal current
            if method=='L-BFGS-B':current+=1
            if model=='LIplus_immigrant' and current==5:
                if method=='L-BFGS-B':
                    objective(x)
                    trial=np.asarray(x).copy();trial[0]-=.001
                    phase.fail=ArithmeticError('Finite objective has unrepresentable gradient')
                    objective(trial)
                values=[]
                for j in range(3):
                    point=np.asarray(x).copy();point[0]-=.01*j
                    if j==2:phase.fail=TimeoutError('Joint experiment deadline')
                    values.append(objective(point))
            value=objective(x)
            return returned(x,value[0] if jac else value)
        try:
            eligible=initial if model=='null' else fitted['null']['selected']['parameters']
            fitted[model]=fit.fit_arm(phase,model,protocol,eligible,lambda x:trace.append(copy.deepcopy(x)),optimizer)
            checks[model]=fit.fine_check(phase,model,fitted[model],protocol)
        except TimeoutError:
            pass
    partial=dict(case_id='invented',passed=False,outcomes=[],fits=fitted,training_checks=checks)
    policy=copy.deepcopy(driver.read(driver.HERE/'recovery_protocol.json')['recovery'])
    policy['anchor_completed_returns']=2;policy['anchor_next_input_number']=3
    return partial,trace,protocol,policy


def new_optimizer(calls):
    def run(objective,x,*,jac,bounds,method,options):
        calls.append((method,np.asarray(x).tolist(),copy.deepcopy(options)))
        if method=='Powell':
            for j in range(3):
                point=np.asarray(x).copy();point[0]-=.01*j
                value=objective(point)
            return returned(point,value)
        return returned(x,objective(x)[0])
    return run


class RecoveryControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.partial,self.trace,self.science,self.policy=partial_fixture()
    def tearDown(self):self.temp.cleanup()
    def recorder(self, **kwargs):
        return adapter.RecoveryAdapter(self.partial,self.trace,self.science,self.policy,self.root/'calls.jsonl',**kwargs)
    def startup_fixture(self):
        """Actual frozen case_run/historical_floor, entirely invented inputs."""
        repo=self.root/'invented_repo';root=repo/'reproduction/synthetic';root.mkdir(parents=True)
        delegate=driver.legacy.runner_with_scheduler(None);delegate.REPO=repo
        name='invented';models=delegate.MODELS
        theta=[math.log(.2),.2,.35,math.log(.05),1.3,0.,math.log(30),math.log(7)]
        score=TinyPhase().evaluate(theta)[0]
        floor=[0.];fits={m:{'floor':floor} for m in models}
        states={m:[{'pars':floor}] for m in models}
        values={m:[[score['nll'],0.,0.,0.,0.,score['P']]] for m in models}
        expected={'phase_values':{'order16_train':values,'order32_test':values},'results':[]}
        old={'phases':{p:{'historical':score,'refitted':score} for p in ('train','test')},'outcomes':[]}
        for m in models:
            for gate in (('raw',) if m=='LI' else ('raw','BIC')):
                expected['results'].append(dict(model=m,gate=gate,selected_state_index=0,gain=0.))
                old['outcomes'].append(dict(model=m,gate=gate,selected_state_index=0,
                    original_floor_test_joint=score['joint'],saved_procedure_test_joint=score['joint'],
                    original_gain=0.,new_gain=0.,original_off_floor=False))
        np.savez(root/'rows.npz',rows=np.array([[31.,0.,0.,1.],[396.,0.,0.,1.]]))
        for key,value in [('states',states),('expected',expected),('receipt',{'counters':{}})]:driver.write(root/(key+'.json'),value)
        for m,value in fits.items():driver.write(root/(m+'.json'),value)
        oldroot=repo/'validation/live_results/methodological_20261106/refitted_floor';oldroot.mkdir(parents=True)
        driver.write(oldroot/(name+'.json'),old)
        case=dict(case_id=name,regime=4,seed=1,history='rows.npz',states='states.json',expected='expected.json',
            generator_receipt='receipt.json',fits={m:m+'.json' for m in models},n_train=1,n_test=1)
        generator=SimpleNamespace(MATCHED_NAMES=[name],ROSTER={name:(None,None,0.,30.,7.)},
            Law=lambda *a:SimpleNamespace(a=-3.,d=0.,n=.3,c=1.,p=1.5,r=.7),fitting_metadata=lambda law:{})
        recorder=SimpleNamespace(context='support_check',evaluations=defaultdict(Counter),last_evaluation=None,
            capture_selected_evaluation=lambda *a:None,consume_pending_support=lambda *a:a[-2:])
        phase=TinyPhase();wrapped=adapter.CountedPhase(phase,recorder,'train')
        delegate.model.phase_from_rows=lambda *a,**k:wrapped
        delegate.fit_arm=Mock(side_effect=RuntimeError('invented stop before optimizer'))
        return delegate,case,{'generator':generator},phase,recorder
    def test_counted_phase_matches_complete_frozen_evaluate_signature(self):
        from experiments.s04b_joint_execution.parallel_chunks import ParallelPhase
        self.assertEqual(inspect.signature(adapter.CountedPhase.evaluate),inspect.signature(driver.model.Phase.evaluate))
        self.assertEqual(inspect.signature(adapter.CountedPhase.evaluate),inspect.signature(ParallelPhase.evaluate))
        r=self.recorder();phase=adapter.CountedPhase(TinyPhase(),r,'train');theta=[0.]*8
        phase.evaluate(theta)
        phase.evaluate(theta,'null',16,False)
        self.assertEqual(r.evaluations['train|null|8|support_check|True']['returned'],1)
        self.assertEqual(r.evaluations['train|null|16|support_check|False']['returned'],1)
    def test_frozen_case_startup_reaches_optimizer_after_implicit_floor_call(self):
        delegate,case,modules,phase,recorder=self.startup_fixture()
        out=self.root/'case';out.mkdir()
        report=delegate.case_run(case,modules,None,self.science,out,time.monotonic()+60)
        self.assertEqual(report['error'],'invented stop before optimizer')
        self.assertEqual(report['error_type'],'RuntimeError')
        self.assertEqual(len(report['floor_checks']),3)
        self.assertEqual(len(report['historical_comparisons']),5)
        self.assertEqual(phase.calls,1)
        self.assertEqual(recorder.evaluations['train|null|8|support_check|True']['returned'],1)
        delegate.fit_arm.assert_called_once()
        self.assertEqual(delegate.fit_arm.call_args.args[1],'null')
        self.assertFalse((out/'invented.attempts.jsonl').exists())
    def test_driver_retains_primary_case_error_when_no_optimizer_trace_exists(self):
        delegate,case,modules,phase,recorder=self.startup_fixture()
        message="CountedPhase.evaluate() missing 1 required positional argument: 'order'"
        phase.fail=TypeError(message)
        args=SimpleNamespace(output=self.root/'driver_output')
        for name in ('admission','library','build_receipt'):
            path=self.root/(name+'.fixture');path.write_bytes(b'invented fixture');setattr(args,name,path)
        admission=dict(numerical_attempt_id='invented-startup-failure',wall_seconds=1200,
            expires_utc='2099-01-01T00:00:00+00:00',prior_index_sha256='invented')
        index=dict(cases=[],attempts=[],partial_case=None,original_failure={'prior_scientific_seconds':0.},
            recovery_transition={'known_outer_overhead_seconds':2.},
            pre_execution_failure={'charge_seconds':90,'nested_scientific_seconds':.6658659909999898})
        replacements=[(driver,'verify_protocol',{}),(driver,'check_admission',admission),
            (driver.frozen,'verify_inputs',[case]),(driver,'accepted_index',(index,False)),
            (driver,'allocation',({'case_id':case['case_id'],'scientific_reservation_seconds':1170},{})),
            (driver.model,'archived',modules),(driver.model,'Native',None),
            (driver.legacy,'OrderedChunkScheduler',nullcontext()),(driver.legacy,'runner_with_scheduler',delegate),
            (driver.legacy,'fit_census',{})]
        with ExitStack() as stack:
            for target,name,value in replacements:stack.enter_context(patch.object(target,name,return_value=value))
            code=driver.run(args,started=time.monotonic())
        self.assertEqual(code,1)
        report=driver.read(args.output/'result.json');partial=driver.read(args.output/'cases/invented.json')
        self.assertFalse(report['passed']);self.assertEqual(report['status'],'failed_requires_review')
        self.assertEqual((report['error_type'],report['error']),('TypeError',message))
        self.assertEqual((partial['error_type'],partial['error']),('TypeError',message))
        self.assertEqual(report['failed_case_sha256'],driver.sha(args.output/'cases/invented.json'))
        saved=driver.read(args.output/'index.json');self.assertIsNone(saved['partial_case']['trace_sha256'])
        self.assertFalse((args.output/'cases/invented.attempts.jsonl').exists())
        self.assertEqual(saved['cases'],[]);self.assertEqual(len(saved['attempts']),1)
        self.assertFalse(driver.read(args.output/saved['attempts'][0]['file'])['passed'])
        self.assertGreater(saved['attempts'][0]['seconds'],0.)
        self.assertEqual(saved['budget']['total_seconds'],saved['attempts'][0]['seconds'])
        self.assertEqual(report['operational_accounting'],saved['operational_accounting'])
        self.assertAlmostEqual(saved['operational_accounting']['accounted_seconds']-saved['budget']['total_seconds'],92.)
        self.assertEqual(saved['pre_execution_failure'],report['pre_execution_failure'])
        self.assertEqual(partial['fits'],{});delegate.fit_arm.assert_not_called()
    def test_frozen_protocol_and_actual_inputs_only_hash_validation(self):
        # This validates bytes and allocations, not any history's objective.
        p=driver.verify_protocol()
        self.assertEqual([len(h['case_ids']) for h in p['actual_hosts']],[1,5,5,5,5,8,8,3])
        self.assertEqual(sum(v['wall_seconds'] for v in p['fixed_slots']),71760)
    def test_completed_arms_and_starts_not_reoptimized(self):
        calls=[];r=self.recorder(optimizer=new_optimizer(calls));phase=adapter.CountedPhase(TinyPhase(),r,'train');logical=[]
        for name in ('null','LI','LIplus_immigrant','LIplus_inclusive'):
            eligible=(self.partial['fits']['null']['candidates'][0]['parameters'] if name=='null' else self.partial['fits']['null']['selected']['parameters'])
            result=r.fit_arm(phase,name,self.science,eligible,logical.append)
            if name in ('null','LI'):self.assertTrue(adapter.same(result,self.partial['fits'][name]))
            if name=='LIplus_immigrant':
                immigrant=result
                self.assertEqual(result['records'][5],r.original_error)
        self.assertEqual(len(calls),11) # one restarted rescue + two new starts + eight total starts
        self.assertTrue(all(v['observed'] and v['exact_match'] for v in r.reference_snapshots.values()))
        original=[adapter.bare(v) for v in self.trace if v['model']=='LIplus_immigrant' and v['event']=='attempt_end']
        self.assertEqual(immigrant['records'][:6],original[:6])
        rows=[json.loads(line) for line in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(sum(v['event']=='replayed_optimizer_return' for v in rows),5)
        self.assertEqual(sum(v['event']=='replayed_primary_error' for v in rows),1)
        self.assertEqual(sum(v['event']=='physical_optimizer_start' for v in rows),11)
        self.assertEqual(sum(v['event']=='reused_complete_arm' for v in rows),2)
        self.assertTrue(any('support' in key for key in r.evaluations))
        self.assertEqual(r.receipt()['original_physical_attempts_retained'],23)
        actual=next(v for v in rows if v['event']=='restart_return_reference')
        self.assertEqual(actual['actual'],{k:v for k,v in r.interrupted['last_evaluation'].items() if k!='evaluation_count'})
        pending=next(v for v in rows if v['event']=='restart_next_input_reference')
        self.assertEqual(pending['actual'],r.interrupted['failed_evaluation_parameters'])
    def test_complete_recovered_training_equals_uninterrupted_invented_reference(self):
        """Same frozen fit_arm, full candidates/selection/checks; no saved history."""
        reference={};reference_checks={};phase=TinyPhase()
        for name in ('null','LI','LIplus_immigrant','LIplus_inclusive'):
            start=-1
            def uninterrupted(objective,x,*,jac,bounds,method,options):
                nonlocal start
                if method=='L-BFGS-B':start+=1
                if name=='LIplus_immigrant' and start==5:
                    if method=='L-BFGS-B':
                        objective(x)
                        trial=np.asarray(x).copy();trial[0]-=.001
                        phase.fail=ArithmeticError('Finite objective has unrepresentable gradient')
                        objective(trial)
                    # Same deterministic Powell invocation, with no artificial
                    # resource interruption at its third objective call.
                    for j in range(3):
                        point=np.asarray(x).copy();point[0]-=.01*j
                        value=objective(point)
                    return returned(point,value)
                value=objective(x)
                return returned(x,value[0] if jac else value)
            eligible=(self.partial['fits']['null']['candidates'][0]['parameters'] if name=='null' else reference['null']['selected']['parameters'])
            reference[name]=fit.fit_arm(phase,name,self.science,eligible,optimizer=uninterrupted)
            reference_checks[name]=fit.fine_check(phase,name,reference[name],self.science)
        calls=[];recovery=self.recorder(optimizer=new_optimizer(calls))
        resumed_phase=adapter.CountedPhase(TinyPhase(),recovery,'train')
        actual={};actual_checks={}
        for name in ('null','LI','LIplus_immigrant','LIplus_inclusive'):
            eligible=(self.partial['fits']['null']['candidates'][0]['parameters'] if name=='null' else actual['null']['selected']['parameters'])
            actual[name]=recovery.fit_arm(resumed_phase,name,self.science,eligible,lambda _:None)
            actual_checks[name]=fit.fine_check(resumed_phase,name,actual[name],self.science)
        self.assertTrue(adapter.same(actual,reference))
        self.assertTrue(adapter.same(actual_checks,reference_checks))
        self.assertEqual(actual['LIplus_immigrant']['records'][5],recovery.original_error)
        self.assertEqual(len(calls),11)
    def test_corrupt_original_start_rejected(self):
        self.trace[0]['initial_parameters'][0]+=.1
        with self.assertRaisesRegex(ValueError,'initial point'):self.recorder()
    def test_missing_original_timeout_rejected(self):
        self.trace=self.trace[:-2]
        with self.assertRaisesRegex(ValueError,'trace record'):self.recorder()
    def test_wrong_primary_error_rejected(self):
        self.trace[-3]['error']='invented different error'
        with self.assertRaisesRegex(ValueError,'primary error'):self.recorder()
    def test_reused_arm_floor_change_rejected_before_calls(self):
        r=self.recorder();x=copy.deepcopy(self.partial['fits']['null']['candidates'][0]['parameters']);x[0]+=.1
        with self.assertRaisesRegex(ValueError,'eligible floor'):r.fit_arm(TinyPhase(),'null',self.science,x,lambda _:None)
        self.assertEqual(r.optimizer_calls,[])
    def test_second_complete_arm_invocation_rejected(self):
        r=self.recorder();x=self.partial['fits']['null']['candidates'][0]['parameters']
        r.fit_arm(TinyPhase(),'null',self.science,x,lambda _:None)
        with self.assertRaisesRegex(ValueError,'reordered arm'):r.fit_arm(TinyPhase(),'null',self.science,x,lambda _:None)
    def run_to_immigrant(self,r):
        phase=adapter.CountedPhase(TinyPhase(),r,'train')
        for name in ('null','LI'):
            eligible=self.partial['fits'][name]['candidates'][0]['parameters']
            r.fit_arm(phase,name,self.science,eligible,lambda _:None)
        return phase
    def test_changed_restart_reference_is_observational_only(self):
        self.trace[-1]['last_evaluation']['score']['nll']+=.5
        r=self.recorder(optimizer=new_optimizer([]));phase=self.run_to_immigrant(r)
        result=r.fit_arm(phase,'LIplus_immigrant',self.science,self.partial['fits']['null']['selected']['parameters'],lambda _:None)
        self.assertTrue(result['passed']);self.assertFalse(r.reference_snapshots['return']['exact_match'])
        self.assertEqual(r.reference_snapshots['return']['scope'],'observational_only')
    def test_changed_next_input_reference_does_not_change_actual_optimizer(self):
        self.trace[-1]['failed_evaluation_parameters'][0]+=.001
        r=self.recorder(optimizer=new_optimizer([]));phase=self.run_to_immigrant(r)
        result=r.fit_arm(phase,'LIplus_immigrant',self.science,self.partial['fits']['null']['selected']['parameters'],lambda _:None)
        self.assertTrue(result['passed']);self.assertFalse(r.reference_snapshots['next_input']['exact_match'])
    def test_restart_can_finish_before_reference_count_without_forced_calls(self):
        calls=[]
        def quick(objective,x,**kwargs):
            calls.append(kwargs['method']);value=objective(x)
            return returned(x,value[0] if kwargs['jac'] else value)
        r=self.recorder(optimizer=quick);phase=self.run_to_immigrant(r)
        result=r.fit_arm(phase,'LIplus_immigrant',self.science,self.partial['fits']['null']['selected']['parameters'],lambda _:None)
        self.assertTrue(result['passed']);self.assertEqual(calls,['Powell','L-BFGS-B','L-BFGS-B'])
        self.assertEqual(r.reference_snapshots,{'return':{'observed':False},'next_input':{'observed':False}})
    def test_original_exhausted_powell_return_preserves_unknown_starts_and_reason(self):
        calls=[];logical=[]
        def exhausted(objective,x,*,jac,bounds,method,options):
            # An invented capped return, not five thousand real evaluations.
            calls.append((method,copy.deepcopy(options)))
            self.assertEqual(method,'Powell');self.assertFalse(jac)
            value=objective(x)
            return OptimizeResult(x=np.asarray(x),fun=value,success=False,status=1,
                message='Maximum number of function evaluations has been exceeded.',
                nfev=options['maxfev'],nit=22)
        r=self.recorder(optimizer=exhausted);phase=self.run_to_immigrant(r)
        result=r.fit_arm(phase,'LIplus_immigrant',self.science,
            self.partial['fits']['null']['selected']['parameters'],logical.append)
        self.assertFalse(result['passed']);self.assertEqual(result['status'],'unknown_starts')
        self.assertNotIn('selected_state_index',result);self.assertNotIn('selected',result)
        self.assertEqual(result['resolved_starts'],[True]*5+[False])
        self.assertEqual(result['not_run_starts'],[6,7]);self.assertEqual(result['required_starts'],8)
        self.assertEqual(calls,[('Powell',self.science['solver']['powell'])])
        failure=result['records'][-1]
        self.assertEqual((failure['start_index'],failure['method'],failure['solver_status'],failure['nfev'],failure['nit']),
            (5,'Powell',1,5000,22))
        self.assertFalse(failure['success']);self.assertFalse(failure['solver_success'])
        self.assertTrue(failure['finite_feasible']);self.assertEqual(failure['fresh_nll_delta'],0.)
        self.assertEqual(failure['message'],'Maximum number of function evaluations has been exceeded.')
        self.assertTrue(adapter.same(adapter.bare(logical[-1]),failure))
        self.assertTrue(adapter.same(result['records'][5],r.original_error))
        original=[adapter.bare(v) for v in self.trace if v['event']=='attempt_end' and v['model']=='LIplus_immigrant']
        self.assertTrue(adapter.same(result['records'][:5],original[:5]))
        self.assertEqual(len(result['candidates']),6)
        self.assertEqual(len(r.replayed_candidates),5);self.assertIsNone(r.pending_return)
        self.assertEqual(r.optimizer_calls, [('LIplus_immigrant',i,'L-BFGS-B') for i in range(6)]+
            [('LIplus_immigrant',5,'Powell')])
    def test_changed_options_rejected(self):
        r=self.recorder();r.current=self.trace[32]
        with self.assertRaisesRegex(ValueError,'recipe'):r.optimizer(lambda _:None,np.array(r.current['initial_parameters']),jac=True,bounds=fit.bounds(self.science,'LIplus_immigrant'),method='L-BFGS-B',options={})
    def test_interruption_retains_execution_ledger(self):
        def interrupted(*args,**kwargs):raise KeyboardInterrupt('invented interruption')
        r=self.recorder(optimizer=interrupted);phase=self.run_to_immigrant(r)
        with self.assertRaises(KeyboardInterrupt):r.fit_arm(phase,'LIplus_immigrant',self.science,self.partial['fits']['null']['selected']['parameters'],lambda _:None)
        self.assertFalse(json.loads((self.root/'calls.jsonl').read_text().splitlines()[-1])['returned'])
    def test_allocation_keeps_failed_charge_and_enforces_next_slot(self):
        policy=driver.read(driver.HERE/'recovery_protocol.json')
        index=dict(cases=[dict(case_id=v) for v in policy['sequence'][:40]],partial_case=None,last_attempt_passed=None,attempts=[])
        a=dict(case_id=policy['sequence'][40],wall_seconds=1200,numerical_attempt_id='invented')
        with patch.object(driver.legacy,'charged',return_value=(21663.863217721,3321.086780193)):
            _,budget=driver.allocation(index,policy,a,True)
            self.assertAlmostEqual(budget['maximum_with_unspent_slots_seconds'],110044.885916780)
            self.assertEqual(budget['operational_failure_charge_seconds'],290)
            self.assertEqual(budget['operational_diagnostic_charge_seconds'],80)
            a['wall_seconds']=1201
            with self.assertRaisesRegex(ValueError,'slot'):driver.allocation(index,policy,a,True)
    def test_failed_or_duplicate_recovery_blocks_automatic_retry(self):
        p=driver.read(driver.HERE/'recovery_protocol.json');index=dict(cases=[dict(case_id=v) for v in p['sequence'][:41]],partial_case={'failed':True},last_attempt_passed=False,attempts=[])
        a=dict(case_id=p['sequence'][41],wall_seconds=1200,numerical_attempt_id='invented')
        with self.assertRaisesRegex(ValueError,'unresolved'):driver.allocation(index,p,a,False)
    def ordered_failure_policy(self):
        p=driver.read(driver.HERE/'recovery_protocol.json');first=p['pre_execution_failure']
        p['operational_diagnostics']=[]
        second=copy.deepcopy(first)
        second.update(status='failed_during_training_support',charge_seconds=120,
            nested_scientific_seconds=1.780888234,nested_supervised_seconds=2.537754305,
            support_evaluation_count=5,optimizer_call_count=0,archive='invented_second.zip',archive_sha256='b'*64)
        p['operational_failures']=[copy.deepcopy(first),second]
        p['operational_lineage_files']={first['archive_sha256']:copy.deepcopy(driver.STARTUP_FILES),'b'*64:copy.deepcopy(driver.SUPPORT_FILES)}
        return p
    def test_two_failed_launches_charge_once_and_keep_historical_alias(self):
        p=self.ordered_failure_policy()
        index=dict(cases=[dict(case_id=v) for v in p['sequence'][:40]],partial_case=None,last_attempt_passed=None,attempts=[])
        a=dict(case_id=p['sequence'][40],wall_seconds=1200,numerical_attempt_id='invented')
        with patch.object(driver.legacy,'charged',return_value=(21663.863217721,3321.086780193)):
            _,budget=driver.allocation(index,p,a,True)
        self.assertEqual(budget['operational_failure_charge_seconds'],210)
        self.assertAlmostEqual(budget['maximum_with_unspent_slots_seconds'],109884.885916780)
        self.assertEqual(p['pre_execution_failure'],p['operational_failures'][0])
        files=driver.operational_failure_files(p)
        self.assertEqual(len(files),8)
        self.assertEqual(files['startup_failure.zip'],(p['pre_execution_failure']['archive'],p['pre_execution_failure']['archive_sha256']))
        self.assertEqual(files['pilot02_support_failure.zip'],('invented_second.zip','b'*64))
    def test_ordered_failure_corruption_rejected(self):
        p=self.ordered_failure_policy()
        changes=[lambda q:q['operational_failures'].reverse(),
            lambda q:q['operational_failures'].append(copy.deepcopy(q['operational_failures'][1])),
            lambda q:q['operational_failures'][1].update(archive_sha256=q['operational_failures'][0]['archive_sha256']),
            lambda q:q['operational_failures'][1].update(charge_seconds=-1),
            lambda q:q['operational_lineage_files']['b'*64].update(archive='../escape.zip'),
            lambda q:q['operational_failures'][1].update(nested_supervised_seconds=121),
            lambda q:q['pre_execution_failure'].update(nested_scientific_seconds=0)]
        for change in changes:
            with self.subTest(change=change):
                bad=copy.deepcopy(p);change(bad)
                with self.assertRaises(ValueError):driver.operational_failures(bad)
    def test_persistence_separates_both_whole_launches_from_scientific_attempts(self):
        out=self.root/'two_failures';out.mkdir();(out/'attempts').mkdir()
        p=self.ordered_failure_policy();failures=p['operational_failures']
        index=dict(cases=[],attempts=[],partial_case=None,original_failure=dict(prior_scientific_seconds=1.),
            recovery_transition={'known_outer_overhead_seconds':.5},pre_execution_failure=failures[0],operational_failures=failures)
        result=dict(passed=False,status='failed_requires_review',cases=[],scientific_completion=False,admission_sha256='a')
        admission=dict(numerical_attempt_id='test',prior_index_sha256='b')
        with patch.object(driver.legacy,'fit_census',return_value={}):
            driver.persist(out,index,result,admission,dict(source_sha256={},recovery_protocol_sha256='c'),time.monotonic(),time.monotonic()+60,None)
        saved=driver.read(out/'index.json');report=driver.read(out/'result.json')
        self.assertEqual(len(saved['attempts']),1)
        self.assertEqual(saved['budget']['total_seconds'],1.+saved['attempts'][0]['seconds'])
        self.assertAlmostEqual(saved['operational_accounting']['accounted_seconds']-saved['budget']['total_seconds'],210.5)
        self.assertEqual(saved['operational_failures'],report['operational_failures'])
        self.assertEqual(report['pre_execution_failure'],failures[0])
    def test_diagnostic_charge_is_separate_and_not_counted_as_another_failure(self):
        p=driver.read(driver.HERE/'recovery_protocol.json')
        self.assertEqual(sum(r['charge_seconds'] for r in driver.operational_failures(p)),290)
        self.assertEqual(sum(r['charge_seconds'] for r in driver.operational_diagnostics(p)),80)
        self.assertEqual(len(driver.operational_evidence_files(p)),16)
        out=self.root/'all_operational';out.mkdir();(out/'attempts').mkdir()
        index=dict(cases=[],attempts=[],partial_case=None,original_failure=dict(prior_scientific_seconds=1.),
            recovery_transition={'known_outer_overhead_seconds':.5},pre_execution_failure=p['pre_execution_failure'],
            operational_failures=p['operational_failures'],operational_diagnostics=p['operational_diagnostics'])
        result=dict(passed=False,status='failed_requires_review',cases=[],scientific_completion=False,admission_sha256='a')
        with patch.object(driver.legacy,'fit_census',return_value={}):
            driver.persist(out,index,result,dict(numerical_attempt_id='test',prior_index_sha256='b'),
                dict(source_sha256={},recovery_protocol_sha256='c'),time.monotonic(),time.monotonic()+60,None)
        saved=driver.read(out/'index.json')
        self.assertAlmostEqual(saved['operational_accounting']['accounted_seconds']-saved['budget']['total_seconds'],370.5)
        self.assertEqual(saved['operational_accounting']['operational_diagnostic_charge_seconds'],80)
        self.assertEqual(len(saved['attempts']),1)
    def test_diagnostic_scope_or_duplicate_charge_corruption_is_rejected(self):
        policy=driver.read(driver.HERE/'recovery_protocol.json')
        mutations=[lambda p:p['operational_diagnostics'][0].update(charge_seconds=-1),
            lambda p:p['operational_diagnostics'][0].update(scientific_completion=True),
            lambda p:p['operational_diagnostics'][0].update(held_out_call_count=1),
            lambda p:p['operational_diagnostics'][0].update(archive_sha256=p['operational_failures'][0]['archive_sha256'])]
        for change in mutations:
            p=copy.deepcopy(policy);change(p)
            with self.assertRaises(ValueError):driver.operational_diagnostics(p)
    def test_final_serialization_deadline_clears_pass(self):
        out=self.root/'output';out.mkdir();(out/'attempts').mkdir()
        index=dict(cases=[],attempts=[],partial_case=None,original_failure=dict(prior_scientific_seconds=1.),
            recovery_transition={'known_outer_overhead_seconds':.5},pre_execution_failure={'charge_seconds':90})
        result=dict(passed=True,status='batch_complete',cases=[],scientific_completion=True,admission_sha256='a')
        admission=dict(numerical_attempt_id='test',prior_index_sha256='b')
        with patch.object(driver.legacy,'fit_census',return_value={}):
            driver.persist(out,index,result,admission,dict(source_sha256={},recovery_protocol_sha256='c'),time.monotonic(),0,None)
        saved=driver.read(out/'result.json')
        self.assertFalse(saved['passed']);self.assertEqual(saved['error_type'],'FinalizationDeadline')
        self.assertEqual(len(index['attempts']),1)
    def test_recomputed_support_must_match_original_saved_checks(self):
        original=copy.deepcopy(self.partial)
        original.update(input_sha256={'fixture':'abc'},historical_comparisons=[{'invented':True}],floor_checks=[dict(phase='train',model='LI',actual_nll=1.,expected_nll=1.,absolute_delta=0.,tolerance=1e-9)])
        report=copy.deepcopy(original)
        driver.validate_recovered_report(report,original)
        report['training_checks']['LI']['fine']['nll']+=.001
        with self.assertRaisesRegex(ValueError,'training check'):driver.validate_recovered_report(report,original)
    def admission_fixture(self):
        p=driver.read(driver.HERE/'recovery_protocol.json');old=p['predecessor']
        current=dict(source_sha256=driver.source_identity(),recovery_protocol_sha256=driver.sha(driver.HERE/'recovery_protocol.json'),
            runtime=dict(essential=old['runtime_essential']),library_sha256=old['library_sha256'],build_receipt_sha256=old['build_receipt_sha256'])
        build=self.root/'build.json';driver.write(build,dict(passed=True,source_sha256=driver.sha(driver.legacy.SCIENCE/'attenuation.cpp'),library_sha256=old['library_sha256']))
        admission=dict(mode='recovery_campaign',independent_review_passed=True,scheduler_review_passed=True,external_supervision=True,
            source_sha256=current['source_sha256'],recovery_protocol_sha256=current['recovery_protocol_sha256'],
            operational_run_id=p['shared_run']['run_id'],operational_run_config_sha256=p['shared_run']['config_sha256'],
            expires_utc=p['shared_run']['expires_utc'],lease_token_sha256=hashlib.sha256(b'invented').hexdigest(),threads=2,workers=1,
            sampled_process_tree_rss_cap_bytes=6442450944,minimum_host_free_bytes=2147483648,case_id=p['sequence'][40],case_ids=[p['sequence'][40]],
            library_sha256=old['library_sha256'],build_receipt_sha256=old['build_receipt_sha256'],numerical_attempt_id='invented')
        path=self.root/'admission.json';driver.write(path,admission)
        return p,current,admission,SimpleNamespace(admission=path,build_receipt=build)
    def test_runtime_source_and_expiry_admission_corruption(self):
        p,current,a,args=self.admission_fixture()
        with patch.dict(os.environ,JOINT_NUMERICAL_LEASE_TOKEN='invented'):
            driver.check_admission(args,p,current)
            changed=copy.deepcopy(current);changed['runtime']['essential']={'unexpected':'runtime'}
            with self.assertRaisesRegex(ValueError,'runtime'):driver.check_admission(args,p,changed)
            changed=copy.deepcopy(current);changed['source_sha256']['injected']='changed'
            with self.assertRaisesRegex(ValueError,'source/protocol'):driver.check_admission(args,p,changed)
            a['expires_utc']='2099-01-01T00:00:00+00:00';driver.write(args.admission,a)
            with self.assertRaisesRegex(ValueError,'Expired'):driver.check_admission(args,p,current)
    def test_removed_original_review_or_lineage_file_is_rejected(self):
        lineage=self.root/'recovery_lineage';lineage.mkdir()
        original=dict(cases=[{'case_id':'invented'}],attempts=[{'attempt_id':'failed'}],reviews=[{'original':'review'}])
        driver.write(lineage/'failed_index.json',original)
        keys={'index_sha256':'failed_index.json','case_sha256':'failed_case.json','trace_sha256':'failed_trace.jsonl',
            'review_sha256':'failed_review.json','result_sha256':'failed_result.json','supervision_sha256':'failed_supervision.json',
            'admission_sha256':'failed_admission.json','archive_sha256':'failed_host.zip'}
        for name in list(keys.values())[1:]+list(driver.STARTUP_FILES.values()):(lineage/name).write_bytes(b'invented immutable bytes')
        predecessor={key:driver.sha(lineage/name) for key,name in keys.items()};predecessor['known_outer_overhead_seconds']=.5
        startup=copy.deepcopy(driver.read(driver.HERE/'recovery_protocol.json')['pre_execution_failure'])
        startup.update({key+'_sha256':driver.sha(lineage/name) for key,name in driver.STARTUP_FILES.items()})
        transition=dict(schema='joint_interrupted_optimizer_transition_v1',original_status='failed',original_index_sha256=predecessor['index_sha256'],
            protocol_sha256=driver.sha(driver.HERE/'recovery_protocol.json'),known_outer_overhead_seconds=.5,
            pre_execution_failure=copy.deepcopy(startup),
            operational_failures=[copy.deepcopy(startup)],
            operational_diagnostics=[],
            files={'recovery_lineage/'+name:driver.sha(lineage/name) for name in list(keys.values())+list(driver.STARTUP_FILES.values())})
        index={**copy.deepcopy(original),'recovery_transition':transition,'pre_execution_failure':copy.deepcopy(startup),
            'operational_failures':[copy.deepcopy(startup)]}
        index['operational_diagnostics']=[]
        p=dict(predecessor=predecessor,pre_execution_failure=startup,operational_failures=[copy.deepcopy(startup)],operational_diagnostics=[],
            operational_lineage_files={startup['archive_sha256']:copy.deepcopy(driver.STARTUP_FILES)})
        driver.validate_recovery_transition(index,p,self.root)
        index['pre_execution_failure']['charge_seconds']=0
        with self.assertRaisesRegex(ValueError,'Startup failure accounting'):driver.validate_recovery_transition(index,p,self.root)
        index['pre_execution_failure']=copy.deepcopy(startup)
        logfile=lineage/driver.STARTUP_FILES['workflow_log'];original_log=logfile.read_bytes();logfile.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact changed'):driver.validate_recovery_transition(index,p,self.root)
        logfile.write_bytes(original_log)
        index['reviews']=[]
        with self.assertRaisesRegex(ValueError,'prefix'):driver.validate_recovery_transition(index,p,self.root)
        index['reviews']=original['reviews'];(lineage/'failed_host.zip').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact changed'):driver.validate_recovery_transition(index,p,self.root)


if __name__=='__main__':unittest.main()
