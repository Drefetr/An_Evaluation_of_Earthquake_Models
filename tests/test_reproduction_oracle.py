"""Known-law replay custody and independent tiny likelihood/rank controls."""
import importlib.util
import math
from pathlib import Path
import unittest
import numpy as np
from scipy.integrate import quad

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'reproduction/oracle'
spec=importlib.util.spec_from_file_location('oracle_replay_subject',HERE/'replay.py')
replay=importlib.util.module_from_spec(spec);spec.loader.exec_module(replay)


class OracleReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cpu,cls.stats=replay.load_modules()

    def law(self,kind='exp',n=.3):
        kernel=self.cpu.KernelSpec(kind,.7)
        return self.cpu.KnownLaw(-2.,.1,n,2.,.7,1.4,kernel,kernel)

    def direct(self,arrays,law,eta):
        """Direct parent sums and adaptive scalar integral, no modal recurrence."""
        t=arrays['times'];q=arrays['excess'];weights,rates=law.stress.mixture
        tw,tr=law.trigger.mixture
        stress=np.exp(.75*math.log(10.)*(q-1.))
        productivity=(1-law.ratio)*np.exp(law.beta*law.ratio*q)
        def fields(x):
            past=t<x;lag=x-t[past]
            g=sum(float(v)*math.fsum(float(w)*math.exp(-float(r)*float(l)) for w,r in zip(weights,rates)) for v,l in zip(stress[past],lag))
            h=sum(float(v)*math.fsum(float(w*r)*math.exp(-float(r)*float(l)) for w,r in zip(tw,tr)) for v,l in zip(productivity[past],lag))
            b=math.exp(law.a+law.d*(2*x/law.coordinate-1))
            return b,g,h
        l0=[];ratios=[]
        for x in t:
            b,g,h=fields(float(x));zero=b+law.n*h;one=b*math.exp(-eta*g)+law.n*h
            l0.append(math.log(zero));ratios.append(math.log(one/zero))
        def reduction(x):
            b,g,_=fields(x);return b*(-math.expm1(-eta*g))
        edges=[0.,*map(float,t),law.horizon]
        integral=math.fsum(quad(reduction,a,b,epsabs=1e-11,epsrel=1e-11,limit=200)[0] for a,b in zip(edges[:-1],edges[1:]))
        baseline=quad(lambda x:math.exp(law.a+law.d*(2*x/law.coordinate-1)),0.,law.horizon,epsabs=1e-12)[0]
        trigger=math.fsum(float(v)*math.fsum(float(w)*(-math.expm1(-float(r)*(law.horizon-float(x)))) for w,r in zip(tw,tr)) for x,v in zip(t,productivity))
        lr=math.fsum(ratios)+integral;nll0=baseline+law.n*trigger-math.fsum(l0)
        return dict(log_lr=lr,event_log_ratio_sum=math.fsum(ratios),compensator_reduction=integral,nll0=nll0,nll1=nll0-lr)

    def test_complete_exact_history_mapping(self):
        manifest=replay.read(HERE/'input_manifest.json')
        result=replay.verify_inputs(manifest)
        self.assertEqual(result['histories'],2149)
        self.assertEqual(result['paired_ids'],['null_0841'])
        self.stats.validate_protocol(replay.read(HERE/'protocol.json'))

    def test_tiny_direct_likelihood_for_exponential_and_finite_mixture(self):
        arrays=dict(times=np.array([.2,.8]),excess=np.array([.3,.6]))
        for kind in ['exp','ml']:
            law=self.law(kind)
            for eta in [0.,.4885010300470942]:
                expected=self.direct(arrays,law,eta)
                result=self.cpu.evaluate_oracle(arrays,law,clock_mode='original_projected_clock',eta=eta,order=32)
                for key,value in expected.items():self.assertAlmostEqual(result[key],value,delta=1e-8)
                if eta==0:self.assertEqual(result['log_lr'],0.)

    def test_paired_low_component_retains_strict_prior_event(self):
        law=self.law();eta=.5
        arrays=dict(times=np.array([1.,1.]),times_lo=np.array([0.,1e-16]),event_gaps=np.array([1.,1e-16]),excess=np.array([.3,.6]))
        result=self.cpu.evaluate_oracle(arrays,law,clock_mode='paired_clock',eta=eta,order=32)
        stress=math.exp(.75*math.log(10.)*(.3-1.))*math.exp(-1e-16/.7)
        trigger=law.n*(1-law.ratio)*math.exp(law.beta*law.ratio*.3)*math.exp(-1e-16/.7)/.7
        background=math.exp(law.a+law.d*(2/law.coordinate-1))
        expected=math.log((background*math.exp(-eta*stress)+trigger)/(background+trigger))
        self.assertAlmostEqual(result['event_log_ratio_sum'],expected,delta=1e-12)
        with self.assertRaises(ValueError):self.cpu.evaluate_oracle(arrays,law,clock_mode='original_projected_clock',eta=eta,order=32)

    def test_rank_ties_threshold_and_missing_reference(self):
        refs=[(3.,1e-6)]*49+[(1.,1e-6)]*950
        accepted=self.stats.classify((2.,1e-6),refs)
        self.assertEqual(accepted['rank'],.05);self.assertTrue(accepted['reject'])
        rejected=self.stats.classify((2.,1e-6),[(3.,1e-6)]*50+[(1.,1e-6)]*949)
        self.assertEqual(rejected['rank'],.051);self.assertFalse(rejected['reject'])
        tied=self.stats.classify((1.,1e-6),[(1.,1e-6)]*999)
        self.assertEqual(tied['rank'],1.);self.assertIsNone(tied['reject'])
        self.assertIsNone(self.stats.classify((2.,1e-6),refs[:-1]+[None])['reject'])

    def test_partial_bank_cannot_calibrate_and_history_paths_cannot_escape(self):
        with self.assertRaises(ValueError):replay.calibrate({},dict())
        with self.assertRaises(ValueError):replay.history_path('../README.md')
        with self.assertRaises(ValueError):replay.local_path('../synthetic/input_manifest.json')


if __name__=='__main__':unittest.main()
