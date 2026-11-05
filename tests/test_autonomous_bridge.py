"""Deterministic autonomous identity controls; no catalogue fitting or simulation."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_autonomous_bridge_model',ROOT/'experiments/autonomous/model.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
fit_spec=importlib.util.spec_from_file_location('_autonomous_bridge_fit',ROOT/'experiments/autonomous/fit.py')
fit=importlib.util.module_from_spec(fit_spec)
with patch.dict(sys.modules,{'model':model}):fit_spec.loader.exec_module(fit)


class AutonomousBridgeTests(unittest.TestCase):
    def test_physical_modes_equal_diagnostic_with_predictable_history(self):
        times=np.array([.2,1.,2.2]);marks=np.array([.1,.4,.7]);w=np.array([.3,.7]);rates=np.array([.2,3.])
        for query in (0.,.2,.21,1.,1.5,3.):
            for eta,n in ((0.,0.),(0.,.6),(.4,0.),(.4,.6)):
                physical=model.physical_intensity(query,times,marks,-1.2,n,eta,3.,w,rates)
                direct=model.diagnostic_intensity(query,times,marks,-1.2,n,eta,3.,w,rates)
                self.assertAlmostEqual(physical['intensity'],direct,places=13)
                self.assertTrue(np.all(physical['Z']<=0));self.assertTrue(np.all(physical['U']>=0))
        # An event at the query time cannot change its own predictable intensity.
        self.assertEqual(model.physical_intensity(.2,times,marks,-1.2,.6,.4,3.,w,rates)['intensity'],math.exp(-1.2))

    def test_first_moment_gate_and_eta_zero_exception(self):
        valid=model.theorem_assumptions(-2.,.7,.3,3.)
        self.assertTrue(valid['eligible'])
        self.assertAlmostEqual(valid['m1'],.3*math.exp(-model.GAMMA)*3/(3-model.GAMMA))
        self.assertFalse(model.theorem_assumptions(-2.,.5,1.,model.GAMMA/2)['eligible'])
        zero=model.theorem_assumptions(-2.,.5,0.,model.GAMMA/2)
        self.assertTrue(zero['eligible']);self.assertEqual(zero['m1'],0.)
        with self.assertRaises(ValueError):model.theorem_assumptions(-2.,1.,.1,3.)

    def test_first_moments_do_not_imply_second_or_cross_moments(self):
        gates=model.theorem_assumptions(-2.,.5,.2,2.8494)
        self.assertTrue(gates['eligible'])
        for key in ('stress_second_moment_finite','productivity_second_moment_finite','cross_moment_finite','higher_moments_required_by_invoked_result'):
            self.assertFalse(gates[key])

    def test_pinned_positive_shared_finite_mixture(self):
        kernel=model.shared_kernel();weights,rates=kernel.mixture
        self.assertEqual(len(weights),195);self.assertTrue(np.all(weights>0));self.assertTrue(np.all(rates>0))
        self.assertAlmostEqual(float(weights.sum()),1.,places=14)
        lag=.7;step=1e-6
        self.assertAlmostEqual(kernel.h(lag),-(kernel.phi(lag+step)-kernel.phi(lag-step))/(2*step),places=8)

    def history(self):
        engine=model.load_engine();kernel=model.shared_kernel()
        history=engine.PredictiveHistory(np.array([.2,.9,1.6]),np.array([.1,.3,.2]),3.,0.,2.,2.,16,memory_limit_mb=16.)
        return model.ConstantBackgroundObjective(history,kernel)

    def test_exact_eta_zero_floor(self):
        objective=self.history();null,ng=objective.evaluate([-1.2,.4]);alt,ag=objective.evaluate([-1.2,.4,0.])
        self.assertEqual(null,alt);np.testing.assert_array_equal(ng,ag[:2])

    def test_engine_event_intensities_equal_physical_modes(self):
        objective=self.history();history=objective.history;weights,rates=objective.kernel.mixture
        logs,_,_=history.components([-1.2,0.,.4,.2],objective.kernel,model.RATIO,objective.kernel)
        expected=[math.log(model.physical_intensity(t,history.times,history.excess,-1.2,.4,.2,3.,weights,rates)['intensity']) for t in history.events]
        np.testing.assert_allclose(logs,expected,rtol=1e-13,atol=1e-13)

    def test_restricted_gradient(self):
        objective=self.history();p=np.array([-1.2,.4,.2]);_,analytic=objective.evaluate(p);step=1e-6
        numeric=[]
        for i in range(3):
            direction=np.zeros(3);direction[i]=step
            numeric.append((objective.evaluate(p+direction,False)-objective.evaluate(p-direction,False))/(2*step))
        np.testing.assert_allclose(analytic,numeric,rtol=2e-6,atol=2e-7)


class OptimizerReturnRetentionTests(unittest.TestCase):
    def run_fake(self,x,fun,fresh_error=False):
        class Objective:
            def evaluate(self,p):
                if float(p[0])==0:return 10.,np.zeros(1)
                if fresh_error:raise ArithmeticError('Deliberate fresh-control failure')
                return 9.,np.zeros(1)
        raw=SimpleNamespace(x=np.asarray(x),fun=fun,success=True,status=17,message='raw solver message',nfev=8,njev=4,nit=3)
        records=[];snapshots=[]
        def checkpoint():snapshots.append(json.loads(json.dumps(records,allow_nan=False)))
        with patch.object(fit,'minimize',return_value=raw):
            chosen=fit.solve_slot(Objective(),[0.],[(-1.,1.)],time.perf_counter()+30,records,checkpoint)
        return chosen,records,snapshots

    def assert_raw_metadata(self,row):
        self.assertEqual(row['raw_return']['status'],17)
        self.assertEqual(row['raw_return']['message'],'raw solver message')
        self.assertEqual(row['raw_return']['nfev'],8)
        self.assertEqual(row['raw_return']['njev'],4)
        self.assertEqual(row['raw_return']['nit'],3)

    def test_nonfinite_raw_vector_and_objective_survive_strict_json(self):
        chosen,records,_=self.run_fake([float('nan')],float('inf'))
        self.assertIsNone(chosen);self.assertEqual(len(records),3)
        for row in records:
            self.assert_raw_metadata(row)
            self.assertEqual(row['raw_return']['x'],[{'nonfinite':'NaN'}])
            self.assertEqual(row['reported_nll'],{'nonfinite':'+Infinity'})
            self.assertEqual(row['fresh_status'],'skipped_infeasible')
            self.assertFalse(row['success'])

    def test_infeasible_finite_vector_is_retained(self):
        chosen,records,_=self.run_fake([2.],9.)
        self.assertIsNone(chosen)
        for row in records:
            self.assert_raw_metadata(row);self.assertEqual(row['pars'],[2.])
            self.assertEqual(row['reported_nll'],9.)
            self.assertFalse(row['feasible_vector']);self.assertFalse(row['success'])

    def test_fresh_exception_preserves_already_checkpointed_return(self):
        chosen,records,snapshots=self.run_fake([.25],9.,fresh_error=True)
        self.assertIsNone(chosen)
        self.assertTrue(any(s and s[-1].get('raw_return') and s[-1]['fresh_status']=='not_attempted' for s in snapshots))
        for row in records:
            self.assert_raw_metadata(row);self.assertEqual(row['pars'],[.25])
            self.assertEqual(row['reported_nll'],9.)
            self.assertEqual(row['fresh_status'],'error')
            self.assertEqual(row['fresh_error_type'],'ArithmeticError')
            self.assertFalse(row['success'])

    def test_nonfinite_reported_objective_cannot_be_accepted(self):
        chosen,records,_=self.run_fake([.25],float('-inf'))
        self.assertIsNone(chosen)
        self.assertEqual(records[0]['reported_nll'],{'nonfinite':'-Infinity'})
        self.assertEqual(records[0]['fresh_nll'],9.)
        self.assertFalse(records[0]['fresh_reported_passed'])

    def test_fresh_reported_tolerance_remains_auditable_and_enforced(self):
        chosen,records,_=self.run_fake([.25],9.+5e-8)
        self.assertIsNotNone(chosen);self.assertEqual(len(records),1)
        self.assertEqual(records[0]['fresh_reported_tolerance'],1e-7)
        self.assertTrue(records[0]['fresh_reported_passed'])
        chosen,records,_=self.run_fake([.25],9.+2e-7)
        self.assertIsNone(chosen);self.assertFalse(records[0]['fresh_reported_passed'])
        self.assertGreater(records[0]['fresh_reported_abs_delta'],1e-7)


if __name__=='__main__':unittest.main()
