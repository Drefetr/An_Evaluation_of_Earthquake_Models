"""Constructed support/check payloads only; no native or saved-history scores."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from experiments.s04b_joint_recovery import adapter,driver,support_diagnostic as diagnostic
from tests import test_joint_recovery as recovery_fixtures
TinyPhase=recovery_fixtures.TinyPhase
partial_fixture=recovery_fixtures.partial_fixture


class SupportDiagnosticControls(unittest.TestCase):
    def setUp(self):
        self.fixture=recovery_fixtures.RecoveryControls();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
    def inputs(self):
        delegate,case,modules,phase,recorder=self.fixture.startup_fixture()
        root=delegate.REPO/'reproduction/synthetic'
        old=driver.read(delegate.REPO/'validation/live_results/methodological_20261106/refitted_floor/invented.json')
        expected=driver.read(root/case['expected']);states=driver.read(root/case['states'])
        fits={m:driver.read(root/v) for m,v in case['fits'].items()}
        partial=copy.deepcopy(self.fixture.partial)
        partial['floor_checks']=delegate.historical_floor(TinyPhase(),case,old,expected,states,fits,'train')[1]
        return case,old,expected,states,fits,partial
    def test_exact_five_training_checks_and_no_optimizer(self):
        phase=TinyPhase();result=dict(evaluations=[],training_checks={});snapshots=[]
        def save():snapshots.append(copy.deepcopy(result))
        with patch.object(diagnostic.fit,'fit_arm',side_effect=AssertionError('No fitting permitted')):
            diagnostic.checks(phase,*self.inputs(),self.fixture.science,result,save)
        self.assertEqual(phase.calls,5)
        self.assertEqual([(r['model'],r['order']) for r in result['evaluations']],diagnostic.EXPECTED_CALLS)
        self.assertTrue(result['equality_passed'])
        self.assertTrue(all(r['returned'] for r in result['evaluations']))
        self.assertTrue(all(len(r['gradient'])==8 for r in result['evaluations']))
        self.assertEqual(snapshots[-1]['training_checks']['LI']['differences'],[])
    def test_five_check_diagnostic_retains_actual_shape_mismatch_without_relaxation(self):
        class Altered(TinyPhase):
            def evaluate(self,theta,model='null',order=8,require_gradient=True):
                score,g=super().evaluate(theta,model,order,require_gradient)
                if model=='LI' and order==16:g[1]+=1e-12
                return score,g
        result=dict(evaluations=[],training_checks={});phase=Altered()
        diagnostic.checks(phase,*self.inputs(),self.fixture.science,result,lambda:None)
        self.assertEqual(phase.calls,5);self.assertFalse(result['equality_passed'])
        check=result['training_checks']['LI']
        self.assertTrue(check['actual']['passed']) # frozen quadrature gate is unchanged
        self.assertFalse(check['exact_match'])    # exact recovery guard remains stricter
        self.assertTrue(any(v['path']=='/projected_gradient_fine/1' and v['absolute_delta']>0 for v in check['differences']))
        self.assertEqual(set(check['actual']),set(check['expected']))
    def test_recovery_records_full_check_before_unchanged_guard_raises(self):
        partial,trace,science,policy=partial_fixture()
        actual=copy.deepcopy(partial['training_checks']['LI']);actual['fine']['joint']+=1e-12
        fake=SimpleNamespace(model=SimpleNamespace(phase_from_rows=lambda *a,**k:None),fine_check=lambda *a:actual)
        with patch.object(driver.legacy,'runner_with_scheduler',return_value=fake):
            delegate,recorder=driver.recovery_delegate(None,partial,trace,science,{'recovery':policy},self.fixture.root)
        with self.assertRaisesRegex(ValueError,'Repeated completed-arm training check differs'):
            delegate.fine_check(None,'LI',partial['fits']['LI'],science)
        row=json.loads((self.fixture.root/'recovery_calls.jsonl').read_text().splitlines()[-1])
        self.assertEqual(row['event'],'repeated_training_check')
        self.assertEqual(row['actual'],actual);self.assertEqual(row['expected'],partial['training_checks']['LI'])
        self.assertFalse(row['exact_match']);self.assertEqual(row['differences'][0]['path'],'/fine/joint')
        self.assertEqual(recorder.receipt()['repeated_training_checks']['LI']['actual'],actual)
        self.assertEqual(recorder.optimizer_calls,[])
    def test_recursive_comparison_preserves_signed_zero_and_missing_fields(self):
        compared=adapter.check_comparison({'x':-0.,'y':[1.,2.]},{'x':0.,'y':[1.,3.],'z':True})
        self.assertFalse(compared['exact_match'])
        paths={r['path']:r for r in compared['differences']}
        self.assertEqual(paths['/x']['delta'],0.)
        self.assertEqual(paths['/y/1']['delta'],-1.)
        self.assertFalse(paths['/z']['actual_present'])
    def test_guard_rejects_sixth_or_wrong_evaluation_before_objective(self):
        phase=TinyPhase();rows=[];guard=diagnostic.RetainedPhase(phase,rows,lambda:None)
        with self.assertRaisesRegex(ValueError,'Undeclared'):guard.evaluate([0.]*8,'LI',8)
        self.assertEqual(phase.calls,0)
        for name,order in diagnostic.EXPECTED_CALLS:guard.evaluate([0.]*8,name,order)
        with self.assertRaisesRegex(ValueError,'Undeclared'):guard.evaluate([0.]*8)
        self.assertEqual(phase.calls,5)
    def test_partial_evaluation_error_is_durable(self):
        phase=TinyPhase();phase.fail=ArithmeticError('invented arithmetic failure');rows=[];snapshots=[]
        guard=diagnostic.RetainedPhase(phase,rows,lambda:snapshots.append(copy.deepcopy(rows)))
        with self.assertRaisesRegex(ArithmeticError,'invented'):guard.evaluate([0.]*8)
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['returned'])
        self.assertEqual(snapshots[-1][0]['error_type'],'ArithmeticError')
    def training_check(self):
        check=copy.deepcopy(self.fixture.partial['training_checks']['LI'])
        check['projected_gradient_coarse']=[1e-3]+[0.]*7
        check['projected_gradient_fine']=[1e-3]+[0.]*7
        check['projected_gradient_scaled_delta']=0.
        check['projected_kkt_infinity_norm']=1e-3
        return check
    def test_finite_gradient_boundary_and_nonfinite_controls(self):
        bound=64*np.finfo(float).eps
        self.assertTrue(adapter.finite_gradient_equivalence([bound]+[0.]*7,[0.]*8)['passed'])
        for value in (np.nextafter(bound,np.inf),float('inf'),float('nan'),True):
            self.assertFalse(adapter.finite_gradient_equivalence([value]+[0.]*7,[0.]*8)['passed'])
        self.assertFalse(adapter.finite_gradient_equivalence([0.]*7,[0.]*8)['passed'])
    def test_li_only_envelope_preserves_exact_saved_check_and_actual_payload(self):
        expected=self.training_check();actual=copy.deepcopy(expected);bound=64*np.finfo(float).eps
        actual['projected_gradient_fine'][3]=bound;actual['projected_gradient_scaled_delta']=bound
        partial,trace,science,policy=partial_fixture();partial['training_checks']['LI']=expected
        fake=SimpleNamespace(model=SimpleNamespace(phase_from_rows=lambda *a,**k:None),fine_check=lambda *a:actual)
        with patch.object(driver.legacy,'runner_with_scheduler',return_value=fake):
            delegate,recorder=driver.recovery_delegate(None,partial,trace,science,{'recovery':policy},self.fixture.root)
        returned=delegate.fine_check(None,'LI',partial['fits']['LI'],science)
        self.assertTrue(adapter.same(returned,expected));self.assertIsNot(returned,expected)
        retained=recorder.receipt()['repeated_training_checks']['LI']
        self.assertEqual(retained['actual'],actual);self.assertFalse(retained['exact_match'])
        self.assertTrue(retained['operational_equivalence']['passed'])
        self.assertEqual(retained['accepted_check_source'],'original_saved_check')
        with self.assertRaisesRegex(ValueError,'training check'):
            delegate.fine_check(None,'null',partial['fits']['null'],science)
    def test_li_envelope_rejects_scores_parameters_flags_norm_or_inconsistent_delta(self):
        expected=self.training_check()
        changes=[lambda v:v['fine'].update(joint=v['fine']['joint']+1e-12),
            lambda v:v['parameters'].__setitem__(0,v['parameters'][0]+1e-12),
            lambda v:v.update(passed=False),lambda v:v.update(projected_kkt_infinity_norm=2e-3),
            lambda v:v.update(projected_gradient_scaled_delta=1e-15),
            lambda v:v['projected_gradient_fine'].__setitem__(2,float('nan')),
            lambda v:v['projected_gradient_fine'].__setitem__(2,65*np.finfo(float).eps)]
        for change in changes:
            actual=copy.deepcopy(expected);change(actual)
            self.assertFalse(adapter.li_training_equivalence(actual,expected)['passed'])
    def test_powell_unused_gradient_envelope_keeps_fullscore_and_parameters_exact(self):
        expected=dict(parameters=[0.]*8,score=dict(nll=2.,P=-1.,E=1.,C=-1.,M=0.,joint=-2.),gradient=[0.]*8)
        actual=copy.deepcopy(expected);actual['gradient'][0]=64*np.finfo(float).eps
        self.assertTrue(adapter.powell_anchor_equivalence(actual,expected)['passed'])
        for change in [lambda v:v['score'].update(P=-1.+1e-15),lambda v:v['parameters'].__setitem__(0,1e-15),
                       lambda v:v['gradient'].__setitem__(0,65*np.finfo(float).eps),lambda v:v.update(gradient=None)]:
            bad=copy.deepcopy(actual);change(bad)
            self.assertFalse(adapter.powell_anchor_equivalence(bad,expected)['passed'])
    def test_completed_record_projection_and_scientific_fields_are_independent_guards(self):
        _,trace,science,_=partial_fixture()
        original=adapter.bare(next(r for r in trace if r['event']=='attempt_end' and r['model']=='LIplus_immigrant' and r['start_index']==0))
        box=diagnostic.fit.bounds(science,'LIplus_immigrant')
        actual=copy.deepcopy(original);actual['gradient'][3]+=4*np.finfo(float).eps
        actual['projected_gradient']=diagnostic.fit.projected_gradient(actual['parameters'],actual['gradient'],box).tolist()
        self.assertTrue(adapter.replayed_record_equivalence(actual,original,box)['passed'])
        changes=[lambda v:v['fresh_score'].update(nll=v['fresh_score']['nll']+1e-12),
            lambda v:v.update(success=False),lambda v:v.update(nfev=v['nfev']+1),
            lambda v:v['parameters'].__setitem__(0,v['parameters'][0]+1e-12),
            lambda v:v['projected_gradient'].__setitem__(3,v['projected_gradient'][3]+1e-15)]
        for change in changes:
            bad=copy.deepcopy(actual);change(bad)
            self.assertFalse(adapter.replayed_record_equivalence(bad,original,box)['passed'])
    def test_full_invented_recovery_preserves_candidates_selection_and_optimizer_calls_with_gradient_drift(self):
        partial,trace,science,policy=partial_fixture()
        results=[];call_lists=[];recorders=[]
        for drift in (False,True):
            directory=self.fixture.root/('drift' if drift else 'exact');directory.mkdir()
            calls=[];recorder=adapter.RecoveryAdapter(partial,trace,science,policy,directory/'calls.jsonl',
                optimizer=recovery_fixtures.new_optimizer(calls))
            class Phase(TinyPhase):
                def evaluate(self,theta,model='null',order=8,require_gradient=True):
                    score,g=super().evaluate(theta,model,order,require_gradient)
                    current=recorder.current
                    if drift and model=='LIplus_immigrant' and current is not None and (
                        current['start_index'] in range(5) or (current['method']=='Powell'
                        and recorder.context=='restarted_interrupted_invocation')):
                        g[3]=np.nextafter(g[3],np.inf)
                    return score,g
            phase=adapter.CountedPhase(Phase(),recorder,'train');fitted={}
            for name in ('null','LI','LIplus_immigrant','LIplus_inclusive'):
                eligible=partial['fits']['null']['candidates'][0]['parameters'] if name=='null' else fitted['null']['selected']['parameters']
                fitted[name]=recorder.fit_arm(phase,name,science,eligible,lambda _:None)
            results.append(fitted);call_lists.append(calls);recorders.append(recorder)
        # Replayed records/candidates are canonical originals, despite retained
        # non-bitwise support checks; no optimizer trajectory is repeated.
        self.assertTrue(adapter.same(results[0],results[1]))
        self.assertEqual(call_lists[0],call_lists[1]);self.assertEqual(len(call_lists[1]),11)
        retained=recorders[1].receipt()
        self.assertEqual(len(retained['replayed_start_support']),5)
        self.assertEqual(len(retained['replayed_candidates']),5)
        self.assertTrue(all(not row['exact_match'] and row['operational_equivalence']['passed'] for row in retained['replayed_start_support'].values()))
        self.assertTrue(all(row['accepted_candidate_gradient_source']=='original_saved_record.gradient' for row in retained['replayed_candidates'].values()))
        log=[json.loads(line) for line in (self.fixture.root/'drift/calls.jsonl').read_text().splitlines()]
        anchor=next(row for row in log if row['event']=='restart_return_anchor_verified')
        self.assertFalse(anchor['exact_match']);self.assertTrue(anchor['operational_equivalence']['passed'])
        self.assertTrue(recorders[1].anchor_next_input_verified)


if __name__=='__main__':unittest.main()
