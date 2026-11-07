"""Invented deterministic objectives and corruption fixtures; no saved-history calls."""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import OptimizeResult
from experiments.s04b_joint_nuisance import fit
from experiments.s04b_joint_recovery import adapter, driver


class TinyPhase:
    def __init__(self):
        self.a={'event_time':np.arange(3)}
        self.fail=None
        self.calls=0
    def evaluate(self, theta, model, order, **kwargs):
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
        self.assertTrue(r.anchor_return_verified and r.anchor_next_input_verified)
        original=[adapter.bare(v) for v in self.trace if v['model']=='LIplus_immigrant' and v['event']=='attempt_end']
        self.assertEqual(immigrant['records'][:6],original[:6])
        rows=[json.loads(line) for line in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(sum(v['event']=='replayed_optimizer_return' for v in rows),5)
        self.assertEqual(sum(v['event']=='replayed_primary_error' for v in rows),1)
        self.assertEqual(sum(v['event']=='physical_optimizer_start' for v in rows),11)
        self.assertEqual(sum(v['event']=='reused_complete_arm' for v in rows),2)
        self.assertTrue(any('support' in key for key in r.evaluations))
        self.assertEqual(r.receipt()['original_physical_attempts_retained'],23)
        actual=next(v for v in rows if v['event']=='restart_return_anchor_verified')
        self.assertEqual(actual['actual_evaluation'],{k:v for k,v in r.interrupted['last_evaluation'].items() if k!='evaluation_count'})
        pending=next(v for v in rows if v['event']=='restart_next_input_anchor_verified')
        self.assertEqual(pending['parameters'],r.interrupted['failed_evaluation_parameters'])
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
    def test_changed_restart_anchor_fails_and_records_physical_attempt(self):
        self.trace[-1]['last_evaluation']['score']['nll']+=.5
        r=self.recorder(optimizer=new_optimizer([]));phase=self.run_to_immigrant(r)
        with self.assertRaisesRegex(ValueError,'return anchor'):r.fit_arm(phase,'LIplus_immigrant',self.science,self.partial['fits']['null']['selected']['parameters'],lambda _:None)
        rows=[json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertFalse(rows[-1]['returned']);self.assertEqual(rows[-1]['completed_objective_returns'],2)
    def test_changed_next_input_fails_before_extra_evaluation(self):
        self.trace[-1]['failed_evaluation_parameters'][0]+=.001
        r=self.recorder(optimizer=new_optimizer([]));phase=self.run_to_immigrant(r)
        with self.assertRaisesRegex(ValueError,'next-input'):r.fit_arm(phase,'LIplus_immigrant',self.science,self.partial['fits']['null']['selected']['parameters'],lambda _:None)
        rows=[json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['completed_objective_returns'],2)
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
            self.assertAlmostEqual(budget['maximum_with_unspent_slots_seconds'],109674.885916780)
            a['wall_seconds']=1201
            with self.assertRaisesRegex(ValueError,'slot'):driver.allocation(index,policy,a,True)
    def test_failed_or_duplicate_recovery_blocks_automatic_retry(self):
        p=driver.read(driver.HERE/'recovery_protocol.json');index=dict(cases=[dict(case_id=v) for v in p['sequence'][:41]],partial_case={'failed':True},last_attempt_passed=False,attempts=[])
        a=dict(case_id=p['sequence'][41],wall_seconds=1200,numerical_attempt_id='invented')
        with self.assertRaisesRegex(ValueError,'unresolved'):driver.allocation(index,p,a,False)
    def test_final_serialization_deadline_clears_pass(self):
        out=self.root/'output';out.mkdir();(out/'attempts').mkdir()
        index=dict(cases=[],attempts=[],partial_case=None,original_failure=dict(prior_scientific_seconds=1.))
        result=dict(passed=True,status='batch_complete',cases=[],scientific_completion=True,admission_sha256='a')
        admission=dict(numerical_attempt_id='test',prior_index_sha256='b')
        with patch.object(driver.legacy,'fit_census',return_value={}):
            driver.persist(out,index,result,admission,dict(source_sha256={},recovery_protocol_sha256='c'),time.monotonic(),0,None)
        saved=driver.read(out/'result.json')
        self.assertFalse(saved['passed']);self.assertEqual(saved['error_type'],'FinalizationDeadline')
        self.assertEqual(len(index['attempts']),1)
    def test_recomputed_support_must_match_original_saved_checks(self):
        original=copy.deepcopy(self.partial)
        original.update(input_sha256={'fixture':'abc'},historical_comparisons=[{'invented':True}],floor_checks=[{'phase':'train','invented':0}])
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
        for name in list(keys.values())[1:]:(lineage/name).write_bytes(b'invented immutable bytes')
        predecessor={key:driver.sha(lineage/name) for key,name in keys.items()};predecessor['known_outer_overhead_seconds']=.5
        transition=dict(schema='joint_interrupted_optimizer_transition_v1',original_status='failed',original_index_sha256=predecessor['index_sha256'],
            protocol_sha256=driver.sha(driver.HERE/'recovery_protocol.json'),known_outer_overhead_seconds=.5,
            files={'recovery_lineage/'+name:driver.sha(lineage/name) for name in keys.values()})
        index={**copy.deepcopy(original),'recovery_transition':transition};p=dict(predecessor=predecessor)
        driver.validate_recovery_transition(index,p,self.root)
        index['reviews']=[]
        with self.assertRaisesRegex(ValueError,'prefix'):driver.validate_recovery_transition(index,p,self.root)
        index['reviews']=original['reviews'];(lineage/'failed_host.zip').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'artifact changed'):driver.validate_recovery_transition(index,p,self.root)


if __name__=='__main__':unittest.main()
