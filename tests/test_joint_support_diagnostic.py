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
        fake=SimpleNamespace(model=SimpleNamespace(phase_from_rows=lambda *a,**k:None),fine_check=lambda *a:actual,historical_floor=lambda *a:None)
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
    def selected_check(self, phase_type=TinyPhase):
        partial,trace,science,policy=partial_fixture()
        fake=SimpleNamespace(model=SimpleNamespace(phase_from_rows=lambda *a,**k:None),
            fine_check=diagnostic.fit.fine_check,historical_floor=lambda *a,**k:None)
        with patch.object(driver.legacy,'runner_with_scheduler',return_value=fake):
            delegate,recorder=driver.recovery_delegate(None,partial,trace,science,{'recovery':policy},self.fixture.root)
        phase=adapter.CountedPhase(phase_type(),recorder,'train')
        return delegate,recorder,phase,partial,science
    def test_selected_raw_gradients_rederived_and_original_check_retained(self):
        class Shifted(TinyPhase):
            def evaluate(self,*args,**kwargs):
                score,g=super().evaluate(*args,**kwargs);g[3]+=.125
                return score,g
        delegate,r,phase,partial,science=self.selected_check(Shifted)
        for name in ('null','LI'):
            result=delegate.fine_check(phase,name,partial['fits'][name],science)
            self.assertTrue(adapter.same(result,partial['training_checks'][name]))
            record=r.receipt()['repeated_training_checks'][name]
            self.assertTrue(record['passed']);self.assertFalse(record['exact_match'])
            self.assertTrue(record['actual_criteria']['fresh_projections_exact'])
            self.assertFalse(record['expected_criteria']['raw_gradient_available'])
            self.assertEqual(len(r.receipt()['selected_check_evaluations'][name]),2)
        self.assertEqual(phase.calls,4);self.assertEqual(r.optimizer_calls,[])
    def test_selected_original_criteria_and_raw_projection_cannot_be_bypassed(self):
        delegate,r,phase,partial,science=self.selected_check()
        delegate.fine_check(phase,'LI',partial['fits']['LI'],science)
        actual=r.repeated_training_checks['LI']['actual'];raw=r.selected_check_evaluations['LI']
        self.assertTrue(adapter.selected_check_criteria(actual,science,'LI',raw)['passed'])
        for mutation in (lambda x:x.update(passed=False),lambda x:x.update(projected_gradient_scaled_delta=1.),
                         lambda x:x.update(projected_kkt_infinity_norm=100.),
                         lambda x:x['projected_gradient_coarse'].__setitem__(0,999.)):
            bad=copy.deepcopy(actual);mutation(bad)
            self.assertFalse(adapter.selected_check_criteria(bad,science,'LI',raw)['passed'])
        badraw=copy.deepcopy(raw);badraw[0]['gradient'][0]+=1.
        self.assertFalse(adapter.selected_check_criteria(actual,science,'LI',badraw)['passed'])
        badraw=copy.deepcopy(raw);badraw[0]['parameters'][0]+=1.
        self.assertFalse(adapter.selected_check_criteria(actual,science,'LI',badraw)['passed'])
    def test_score_contract_absolute_tolerance_identities_and_original_exposure_scope(self):
        expected=dict(P=0.,E=0.,C=-0.,M=0.,joint=0.,nll=-0.)
        actual=dict(P=1e-9,E=0.,C=-0.,M=0.,joint=1e-9,nll=-1e-9)
        self.assertTrue(adapter.score_comparison(actual,expected)['passed'])
        over=np.nextafter(1e-9,np.inf);actual.update(P=over,joint=over,nll=-over)
        self.assertFalse(adapter.score_comparison(actual,expected)['passed'])
        for change in (lambda x:x.update(C=1e-12),lambda x:x.update(joint=1e-12),
                       lambda x:x.update(nll=1e-12),lambda x:x.update(P=float('nan'))):
            bad=copy.deepcopy(expected);change(bad)
            self.assertFalse(adapter.score_comparison(bad,expected)['passed'])
        coarse=dict(P=-1e-10,E=-1e-10,C=1e-10,M=0.,joint=0.,nll=-0.)
        self.assertTrue(adapter.score_comparison(coarse,coarse)['passed'])
        selected=copy.deepcopy(self.fixture.partial['training_checks']['LI'])
        selected['coarse']=coarse;selected['fine']=coarse;selected['absolute_joint_delta']=0.
        self.assertFalse(adapter.selected_check_criteria(selected,self.fixture.science,'LI')['passed'])
    def pending(self):
        r=self.fixture.recorder();r.context='eligible_floor_or_fresh_return_support'
        r.current=copy.deepcopy(self.fixture.trace[32])
        result=r.optimizer(lambda _:self.fail('Completed optimizer must not run'),np.array(r.current['initial_parameters']),
            jac=True,bounds=diagnostic.fit.bounds(self.fixture.science,'LIplus_immigrant'),method='L-BFGS-B',
            options={k:self.fixture.science['solver'][k] for k in ('maxiter','maxls','ftol','gtol')})
        return r,result
    def test_one_shot_support_precedes_candidate_and_never_replaces_an_optimizer_value(self):
        r,result=self.pending();old=r.ends[('LIplus_immigrant',0,'L-BFGS-B')]
        class Drift(TinyPhase):
            def evaluate(self,*args,**kwargs):
                score,g=super().evaluate(*args,**kwargs)
                score['P']+=1e-11;score['joint']=score['P']-score['E']+score['M'];score['nll']=-score['joint'];g[3]+=.125
                return score,g
        phase=adapter.CountedPhase(Drift(),r,'train')
        score,g=phase.evaluate(result.x,'LIplus_immigrant',8)
        self.assertTrue(adapter.same(score,old['fresh_score']));self.assertEqual(g.tolist(),old['gradient'])
        saved=r.replayed_start_support['0'];self.assertTrue(saved['passed'])
        self.assertNotEqual(saved['actual_evaluation']['score'],score)
        self.assertIsNone(r.pending_return)
        # A subsequent ordinary evaluation receives its actual value: the token is consumed.
        actual,gradient=phase.evaluate(result.x,'LIplus_immigrant',8)
        self.assertNotEqual(actual,score);self.assertNotEqual(gradient.tolist(),g.tolist())
        rows=[json.loads(x) for x in r.ledger_path.read_text().splitlines()]
        self.assertEqual(sum(x['event']=='token_consumed' for x in rows),1)
        self.assertEqual(sum(x['event']=='physical_optimizer_start' for x in rows),0)
    def test_pending_token_rejects_wrong_model_order_parameters_or_optimizer_context(self):
        for index,kind in enumerate(('model','order','parameters','optimizer','start')):
            with self.subTest(kind=kind):
                self.fixture.root=self.fixture.root/str(index);self.fixture.root.mkdir()
                r,result=self.pending();theta=result.x.copy();name='LIplus_immigrant';order=8
                if kind=='model':name='LI'
                if kind=='order':order=16
                if kind=='parameters':theta[0]+=.01
                if kind=='optimizer':r.active_physical_optimizer=True
                if kind=='start':r.current['start_index']=6
                phase=adapter.CountedPhase(TinyPhase(),r,'train')
                with self.assertRaisesRegex(ValueError,'Pending support token'):phase.evaluate(theta,name,order)
                self.assertIsNone(r.pending_return);self.assertEqual(r.replayed_start_support,{})
    def test_bad_support_score_and_nonfinite_gradient_fail_before_canonical_return(self):
        for i,kind in enumerate(('score','gradient')):
            self.fixture.root=self.fixture.root/str(i);self.fixture.root.mkdir()
            r,result=self.pending()
            class Bad(TinyPhase):
                def evaluate(self,*a,**kw):
                    score,g=super().evaluate(*a,**kw)
                    if kind=='score':score.update(P=score['P']-1e-6,joint=score['joint']-1e-6,nll=score['nll']+1e-6)
                    else:g[0]=float('nan')
                    return score,g
            with self.assertRaisesRegex(ValueError,'original scientific freshness'):
                adapter.CountedPhase(Bad(),r,'train').evaluate(result.x,'LIplus_immigrant',8)
            self.assertFalse(r.replayed_start_support['0']['passed'])
            self.assertIsNone(r.replayed_start_support['0']['canonical_return'])
    def test_floor_retains_actual_rows_and_checks_both_original_and_cross_run_tolerances(self):
        expected=[dict(phase='train',model='LI',actual_nll=0.,expected_nll=0.,absolute_delta=0.,tolerance=1e-9)]
        actual=copy.deepcopy(expected);actual[0].update(actual_nll=1e-10,absolute_delta=1e-10)
        checked=adapter.floor_rows_comparison(actual,expected)
        self.assertTrue(checked['passed']);self.assertEqual(checked['actual'],actual)
        expected[0].update(actual_nll=-9e-10,absolute_delta=9e-10)
        actual[0].update(actual_nll=9e-10,absolute_delta=9e-10)
        self.assertFalse(adapter.floor_rows_comparison(actual,expected)['passed'])
    def test_full_recovery_keeps_preselection_candidates_under_support_drift(self):
        results=[];call_lists=[];recorders=[]
        for drift in (False,True):
            directory=self.fixture.root/str(drift);directory.mkdir()
            calls=[];recorder=adapter.RecoveryAdapter(self.fixture.partial,self.fixture.trace,self.fixture.science,
                self.fixture.policy,directory/'calls.jsonl',optimizer=recovery_fixtures.new_optimizer(calls))
            class Phase(TinyPhase):
                def evaluate(self,theta,model='null',order=8,require_gradient=True):
                    score,g=super().evaluate(theta,model,order,require_gradient)
                    # Only support immediately following a replayed return drifts.
                    # Every actual optimizer and new start sees unmodified values.
                    if drift and recorder.pending_return is not None:
                        score['E']+=3e-15;score['C']=-score['E']
                        score['joint']=score['P']-score['E']+score['M'];score['nll']=-score['joint']
                        g[3]+=.125
                    return score,g
            phase=adapter.CountedPhase(Phase(),recorder,'train');fitted={}
            for name in ('null','LI','LIplus_immigrant','LIplus_inclusive'):
                eligible=self.fixture.partial['fits']['null']['candidates'][0]['parameters'] if name=='null' else fitted['null']['selected']['parameters']
                fitted[name]=recorder.fit_arm(phase,name,self.fixture.science,eligible,lambda _:None)
            results.append(fitted);call_lists.append(calls);recorders.append(recorder)
        self.assertTrue(adapter.same(results[0],results[1]))
        self.assertEqual(call_lists[0],call_lists[1]);self.assertEqual(len(call_lists[1]),11)
        retained=recorders[1].receipt()
        self.assertEqual(len(retained['replayed_start_support']),5)
        self.assertTrue(all(r['passed'] and r['actual_evaluation']!=r['expected_evaluation'] for r in retained['replayed_start_support'].values()))
        self.assertTrue(all(r['passed'] and r['exact_match'] for r in retained['replayed_candidates'].values()))
        self.assertIsNone(retained['pending_return'])

    def test_near_tie_is_canonicalized_before_frozen_candidate_selection(self):
        partial,trace,science,policy=partial_fixture()
        # Five invented completed candidates tie at one nat. A fresh diagnostic
        # for start one is slightly better; it must not win a new comparison.
        for row in trace:
            if row['event']=='attempt_end' and row['model']=='LIplus_immigrant' and row['start_index']<5:
                row.update(returned_nll=1.,fresh_nll_delta=0.,gradient=[0.]*8,projected_gradient=[0.]*8,
                    fresh_score=dict(P=-1.,E=0.,C=-0.,M=0.,joint=-1.,nll=1.))
        calls=[];r=adapter.RecoveryAdapter(partial,trace,science,policy,self.fixture.root/'tie.jsonl',
            optimizer=recovery_fixtures.new_optimizer(calls))
        class Flat(TinyPhase):
            def evaluate(self,theta,model='null',order=8,require_gradient=True):
                self.calls+=1;value=2.
                if r.pending_return is not None:
                    value=1.-(5e-10 if r.pending_return['start_index']==1 else 0.)
                return dict(P=-value,E=0.,C=-0.,M=0.,joint=-value,nll=value),np.zeros(8)
        phase=adapter.CountedPhase(Flat(),r,'train')
        for name in ('null','LI','LIplus_immigrant'):
            eligible=partial['fits']['null']['candidates'][0]['parameters'] if name=='null' else partial['fits']['null']['selected']['parameters']
            result=r.fit_arm(phase,name,science,eligible,lambda _:None)
        self.assertEqual(result['selected']['start_index'],0)
        self.assertLess(r.replayed_start_support['1']['actual_evaluation']['score']['nll'],
            r.replayed_start_support['0']['actual_evaluation']['score']['nll'])
        self.assertTrue(all(c['score']['nll']==1. for c in result['candidates'][1:6]))
        self.assertEqual(len(calls),3)


if __name__=='__main__':unittest.main()
