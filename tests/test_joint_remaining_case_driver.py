"""Invented original-runner cases only; no native or historical fitting."""
import copy
import datetime as dt
import hashlib
import json
import math
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import OptimizeResult
from experiments.s04b_joint_remaining import case_driver as driver
from experiments.s04b_joint_nuisance import fit
from tests import test_joint_recovery as recovery_fixtures
TinyPhase = recovery_fixtures.TinyPhase


class RemainingCaseControls(unittest.TestCase):
    def setUp(self):
        self.fixture=recovery_fixtures.RecoveryControls();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root
        self.science=self.fixture.science

    def setup_case(self, unknown_model=None, technical=False, iteration=False, primary_exception=False):
        delegate,case,modules,_,_=self.fixture.startup_fixture()
        construction=[];calls=[]
        class Phase(TinyPhase):
            _grids={strkey:dict(space_nodes=1,time_nodes=1,parents=1,estimate=1) for strkey in (8,16)}
            def evaluate(self,theta,model='null',order=8,require_gradient=True):
                # A shared invented backbone makes all eta-zero arms identical.
                return super().evaluate(theta,'null',order,require_gradient)
        def factory(rows,gm,start,end,mods,native,deadline=math.inf):
            construction.append((start,end));p=Phase();p.a={'event_time':np.array([start+1])};return p
        delegate.model.phase_from_rows=factory
        def fitting(phase,model,protocol,eligible,callback):
            index=-1
            def optimizer(objective,x,*,jac,bounds,method,options):
                nonlocal index
                if method=='L-BFGS-B':index+=1
                calls.append((model,index,method))
                if technical and model==unknown_model:raise TimeoutError('invented technical deadline')
                value=objective(x);value=value[0] if jac else value
                bad=model==unknown_model and index==2
                if bad and primary_exception and method=='L-BFGS-B':raise ArithmeticError('invented primary gradient failure')
                return OptimizeResult(x=np.asarray(x),fun=value,success=not bad,status=(2 if iteration else 1) if bad else 0,
                    message='Maximum number of function evaluations has been exceeded.' if bad else 'invented successful return',
                    nfev=(3 if iteration else options['maxfev']) if bad and method=='Powell' else 1,
                    nit=options['maxiter'] if bad and method=='Powell' and iteration else 22 if bad and method=='Powell' else 1)
            return fit.fit_arm(phase,model,protocol,eligible,callback,optimizer)
        delegate.fit_arm=fitting
        return delegate,case,modules,construction,calls

    def execute_fixture(self, **kwargs):
        late_finalize=kwargs.pop('late_finalize',False)
        delegate,case,modules,construction,calls=self.setup_case(**kwargs)
        args=SimpleNamespace(case_id=case['case_id'],output=self.root/'out')
        for field in ('library','build_receipt','admission'):
            p=self.root/(field+'.fixture');p.write_text('{}');setattr(args,field,p)
        policy=dict(immutable_failure_reference={'archive_sha256':'unchanged-invented-failure'})
        slot=dict(case_id=case['case_id'],wall_seconds=1200,scientific_seconds=1170)
        admission=dict(numerical_attempt_id='invented-case',expires_utc='2099-01-01T00:00:00+00:00')
        replacements=[(driver,'verify_protocol',policy),(driver,'source_identity',{}),
            (driver,'check_admission',(admission,slot)),(driver.frozen,'verify_inputs',[case]),
            (driver.frozen,'runtime_identity',{'essential':{}}),(driver.model,'archived',modules),
            (driver.model,'Native',None),(driver.legacy,'OrderedChunkScheduler',nullcontext()),
            (driver.legacy,'runner_with_scheduler',delegate)]
        with ExitStack() as stack:
            for obj,name,value in replacements:stack.enter_context(patch.object(obj,name,return_value=value))
            # The independent source/output audit covers real input custody.
            stack.enter_context(patch.object(driver.legacy,'verify_case',return_value=None))
            if late_finalize:
                real_write=driver.write;real_clock=time.monotonic;expired=[False]
                def delayed_write(path,value):
                    real_write(path,value)
                    if Path(path).name=='result.json' and value.get('disposition_valid'):expired[0]=True
                stack.enter_context(patch.object(driver,'write',side_effect=delayed_write))
                stack.enter_context(patch.object(driver.time,'monotonic',side_effect=lambda:real_clock()+(2000 if expired[0] else 0)))
            code=driver.run(args,started=time.monotonic())
        result=driver.read(args.output/'result.json')
        report=driver.read(args.output/'cases/invented.json')
        return code,result,report,construction,calls,args

    def test_original_complete_case_stays_successful_with_all_four_fits(self):
        code,result,report,phases,calls,args=self.execute_fixture()
        self.assertEqual(code,0);self.assertTrue(result['passed']);self.assertTrue(result['scientific_passed'])
        self.assertEqual(result['disposition'],'complete');self.assertTrue(result['disposition_valid'])
        self.assertEqual(phases,[(30,395),(395,760)]);self.assertEqual(len(calls),32)
        self.assertEqual(len(report['outcomes']),5);self.assertEqual(result['unknown_outcome_count'],0)
        self.assertEqual(result['report_sha256'],driver.sha(args.output/result['report_file']))

    def test_original_alternative_cap_is_handled_unknown_without_test_phase(self):
        code,result,report,phases,calls,args=self.execute_fixture(unknown_model='LI')
        self.assertEqual(code,0);self.assertTrue(result['handled']);self.assertTrue(result['disposition_valid'])
        self.assertFalse(result['passed']);self.assertFalse(result['scientific_passed'])
        self.assertEqual(result['disposition'],'scientific_unknown')
        self.assertEqual(report['error'],'Unresolved alternative starts');self.assertEqual(report['status'],'unknown')
        self.assertEqual(phases,[(30,395)]);self.assertEqual(report['outcomes'],[])
        self.assertEqual(result['model_census']['completed_models'],['null'])
        self.assertEqual(result['model_census']['unresolved_model'],'LI')
        self.assertEqual(result['model_census']['not_run_starts'],[3,4,5,6,7])
        self.assertEqual(result['model_census']['not_run_models'],['LIplus_immigrant','LIplus_inclusive'])
        self.assertEqual(result['terminal_solver_return'],report['fits']['LI']['records'][-1])
        self.assertEqual(result['terminal_solver_return']['nfev'],5000)
        self.assertEqual(len(calls),12);self.assertEqual(result['unknown_outcome_count'],5)
        self.assertNotIn('selected',report['fits']['LI']);self.assertNotIn('new_null_test',report)

    def test_original_null_iteration_cap_has_no_completed_models(self):
        code,result,report,phases,calls,args=self.execute_fixture(unknown_model='null',iteration=True)
        self.assertEqual(code,0);self.assertEqual(result['disposition'],'scientific_unknown')
        self.assertEqual(result['unknown_reason']['error'],'Unresolved null starts')
        self.assertEqual(result['model_census']['completed_models'],[])
        self.assertEqual(result['terminal_solver_return']['nit'],400)
        self.assertEqual(phases,[(30,395)]);self.assertEqual(len(calls),4)

    def test_attempt_census_includes_primary_exception_without_calling_it_a_return(self):
        code,result,report,_,calls,_=self.execute_fixture(unknown_model='null',primary_exception=True)
        self.assertEqual(code,0);self.assertEqual(result['disposition'],'scientific_unknown')
        self.assertEqual(report['fits']['null']['records'][-2]['status'],'exception')
        self.assertEqual(result['model_census']['logical_optimizer_attempts'],4)
        self.assertEqual(len(calls),4);self.assertNotIn('logical_optimizer_returns',result['model_census'])

    def test_technical_timeout_never_becomes_scientific_unknown(self):
        code,result,report,phases,calls,args=self.execute_fixture(unknown_model='null',technical=True)
        self.assertEqual(code,1);self.assertFalse(result['handled']);self.assertFalse(result['disposition_valid'])
        self.assertEqual(result['disposition'],'technical_failure')
        self.assertEqual(result['original_case_error'],{'error_type':'TimeoutError','error':'invented technical deadline'})
        self.assertEqual(report['outcomes'],[]);self.assertEqual(phases,[(30,395)])

    def test_unknown_corruptions_and_other_solver_failures_are_rejected(self):
        _,result,report,_,_,args=self.execute_fixture(unknown_model='LI')
        trace=driver.trace_records(args.output/result['trace_file'])
        changes=[lambda r:r.update(error='different failure'),lambda r:r.update(training_selections_frozen=True),
            lambda r:r.update(outcomes=[{'invented':True}]),lambda r:r['fits']['LI'].update(selected_state_index=0),
            lambda r:r['fits']['LI']['records'][-1].update(solver_status=3),
            lambda r:r['fits']['LI']['records'][-1].update(nfev=4999),
            lambda r:r['fits']['LI']['records'][-1].update(fresh_nll_delta=1.),
            lambda r:r['fits']['LI']['records'][-1]['parameters'].__setitem__(0,float('inf'))]
        for change in changes:
            bad=copy.deepcopy(report);change(bad)
            rows=copy.deepcopy(trace)
            # Rebind the trace to isolate semantic guards from the hash/crosswalk guard.
            for row in rows:
                if row['event']=='attempt_end' and row['model']=='LI' and row['method']=='Powell':
                    row.update(bad['fits']['LI']['records'][-1])
            with self.assertRaises((ValueError,TypeError)):
                driver.classify(bad,{'case_id':'invented'},self.science,rows,result['phase_constructions'])
        with self.assertRaisesRegex(ValueError,'held-out'):
            driver.classify(report,{'case_id':'invented'},self.science,trace,
                result['phase_constructions']+[dict(start=395,end=760,returned=True)])

    def test_protocol_excludes_prior_unknown_and_completed_prefix(self):
        policy=driver.verify_protocol()
        self.assertEqual(len(policy['case_ids']),39)
        self.assertNotIn('S5_broad_long_imm_seed410518',policy['case_ids'])
        self.assertEqual(policy['case_ids'],policy['full_sequence'][41:])
        self.assertEqual(sum(s['wall_seconds'] for s in policy['case_slots']),70560)

    def test_trace_truncation_or_pair_identity_is_not_an_unknown(self):
        _,result,_,_,_,args=self.execute_fixture(unknown_model='null')
        path=args.output/result['trace_file'];lines=path.read_text().splitlines()
        path.write_text('\n'.join(lines[:-1])+'\n')
        with self.assertRaisesRegex(ValueError,'Incomplete'):driver.trace_records(path)
        rows=[json.loads(s) for s in lines];rows[-1]['start_index']+=1
        path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        with self.assertRaisesRegex(ValueError,'identity'):driver.trace_records(path)

    def test_finalization_deadline_revokes_handled_disposition(self):
        code,result,report,phases,calls,args=self.execute_fixture(unknown_model='null',late_finalize=True)
        self.assertEqual(code,1);self.assertFalse(result['handled']);self.assertFalse(result['disposition_valid'])
        self.assertTrue(result['finalization_deadline_exceeded'])
        self.assertEqual(result['disposition'],'technical_failure')
        self.assertEqual(report['fits']['null']['status'],'unknown_starts')

    def test_admission_rejects_old_history_source_runtime_and_cap_changes(self):
        p=driver.verify_protocol();native=p['original_native'];case=p['case_ids'][0]
        p['shared_run']['expires_utc']=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=2)).isoformat()
        build=self.root/'build.json';driver.write(build,dict(passed=True,source_sha256=driver.sha(driver.legacy.SCIENCE/'attenuation.cpp'),library_sha256=native['library_sha256']))
        current=dict(source_sha256=driver.source_identity(),protocol_sha256=driver.sha(driver.HERE/'protocol.json'),
            runtime={'essential':native['runtime_essential']},library_sha256=native['library_sha256'],build_receipt_sha256=native['build_receipt_sha256'])
        a=dict(mode='untouched_remaining_case',case_id=case,case_ids=[case],source_sha256=current['source_sha256'],protocol_sha256=current['protocol_sha256'],
            independent_review_passed=True,external_supervision=True,operational_run_id=p['shared_run']['run_id'],
            operational_run_config_sha256=p['shared_run']['config_sha256'],expires_utc=p['shared_run']['expires_utc'],
            wall_seconds=p['case_slots'][0]['wall_seconds'],threads=2,workers=1,sampled_process_tree_rss_cap_bytes=6442450944,
            minimum_host_free_bytes=2147483648,lease_token_sha256=hashlib.sha256(b'invented').hexdigest(),
            library_sha256=native['library_sha256'],build_receipt_sha256=native['build_receipt_sha256'])
        admission=self.root/'admission.json';driver.write(admission,a)
        args=SimpleNamespace(case_id=case,admission=admission,build_receipt=build)
        with patch.dict(driver.os.environ,JOINT_NUMERICAL_LEASE_TOKEN='invented'):
            driver.check_admission(args,p,current)
            for mutation in (lambda x:x.update(wall_seconds=1201),lambda x:x.update(protocol_sha256='changed'),
                             lambda x:x.update(case_ids=['S5_broad_long_imm_seed410518']),
                             lambda x:x.update(expires_utc='2099-01-01T00:00:00+00:00')):
                bad=copy.deepcopy(a);mutation(bad);driver.write(admission,bad)
                with self.assertRaises(ValueError):driver.check_admission(args,p,current)
            driver.write(admission,a);bad=copy.deepcopy(current);bad['runtime']['essential']={}
            with self.assertRaisesRegex(ValueError,'runtime'):driver.check_admission(args,p,bad)


if __name__=='__main__':unittest.main()
