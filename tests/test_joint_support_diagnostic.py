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


if __name__=='__main__':unittest.main()
