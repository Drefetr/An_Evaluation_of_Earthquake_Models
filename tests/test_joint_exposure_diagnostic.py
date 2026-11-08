"""Invented finite arrays only; no historical model or optimizer execution."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np
from experiments.s04b_exposure_diagnostic import numerics as N
from experiments.s04b_exposure_diagnostic import run as R


def fixture(eta=.6):
    pt=np.array([.2, 1., 1.7]); marks=np.array([1., 2., .5])
    r2=np.array([[0., 1., 2.], [.2, .7, 3.]])
    area=np.array([.4, .6]); b=np.array([.8, 1.2])
    times=np.array([.2, .5, 1., 1.2, 2.]); weights=np.array([.2,.3,.1,.4,.2])
    h=np.zeros((2,15));h[:,:5]=np.array([[.5,.6,.9,.2,.4],[.1,.3,.4,.8,.7]])
    theta=np.array([-.2,.1,.3,0.,1.4,eta,math.log(2),math.log(.8)])
    return pt,marks,r2,area,b,times,weights,h,theta,3.


def direct_reference(args):
    pt, marks, r2, area, b, times, weights, h, theta, horizon=args
    a,d,n,_,_,eta,logell,logpsi=theta
    channels=[[] for _ in range(6)]
    for s in range(len(area)):
        for i,t in enumerate(times):
            G=math.fsum(float(marks[j])/(1+float(r2[s,j])/math.exp(2*logell))**2
                *math.exp(-(float(t)-float(pt[j]))/math.exp(logpsi))
                for j in range(len(pt)) if pt[j]<t)
            B=math.exp(a+d*(2*t/horizon-1))*b[s];H=h[s,i]
            w=area[s]*weights[i];e=math.exp(-eta*G);lost=-math.expm1(-eta*G)
            for store,value in zip(channels,(w*B,w*n*H,w*B*e,w*n*H*e,w*B*lost,w*n*H*lost)):
                store.append(value)
    return [math.fsum(v) for v in channels]


class ExposureDiagnostic(unittest.TestCase):
    def test_same_nodes_match_independent_direct_sum(self):
        a=fixture();r=N.same_node_sums(*a);expected=direct_reference(a)
        for key,value in zip(('Q0_background','Q0_trigger','Qa_background','Qa_trigger','D_background','D_trigger'),expected):
            self.assertAlmostEqual(r[key],value,places=14)
        self.assertEqual(r['negative_terms'],0);self.assertEqual(r['nonfinite_terms'],0)
        self.assertEqual(r['terms_per_channel'],10)

    def test_eta_zero_is_positive_integral_not_deficit(self):
        r=N.same_node_sums(*fixture(0))
        self.assertEqual(r['D'],0);self.assertEqual(r['Qa'],r['Q0'])

    def test_parent_at_node_is_strictly_excluded(self):
        a=list(fixture());a[5]=np.array([.2]);a[6]=np.array([1.]);a[7]=np.ones((2,3))
        r=N.same_node_sums(*a)
        self.assertEqual(r['D'],0);self.assertEqual(r['maximum_G'],0)

    def test_underflow_retained_without_clipping_exposure(self):
        a=list(fixture(1e7));r=N.same_node_sums(*a)
        self.assertGreater(r['attenuation_underflow_count'],0)
        self.assertGreaterEqual(r['Qa'],0);self.assertGreater(r['D'],0)

    def test_reject_wrong_triggering_shape_and_time_order(self):
        a=list(fixture());a[7]=a[7][:,:5]
        with self.assertRaises(ValueError):N.same_node_sums(*a)
        a=list(fixture());a[5]=a[5][::-1]
        with self.assertRaises(ValueError):N.same_node_sums(*a)

    def test_deadline_is_bounded(self):
        with self.assertRaises(TimeoutError):N.same_node_sums(*fixture(),deadline=0)

    def test_compensated_sum_small_terms(self):
        total=np.array([1.]);correction=np.zeros(1)
        for _ in range(100):N.add_compensated(total,correction,np.array([1e-16]))
        self.assertEqual(total[0],math.fsum([1.]+[1e-16]*100))

    def test_split_chunk_equivalence(self):
        a=fixture();whole=N.same_node_sums(*a);chunks=[]
        for s in range(2):
            part=list(a)
            for k in (2,3,4,7):part[k]=a[k][s:s+1]
            d=N.same_node_sums(*part)
            chunks.append(dict(row_start=s,space_nodes=1,native_return=[d['D']]+[0]*8,diagnostic=d))
        result=N.combine_chunks(chunks,dict(E0=10.,background=8.,trigger=2.),[sum(r['native_return'][0] for r in chunks)]+[0]*8)
        for key in ('Q0','Qa','D'):
            self.assertAlmostEqual(result[key],whole[key],places=14)
        self.assertTrue(result['native_chunk_sum_matches_original_D'])

    def test_negative_original_exposure_is_not_replaced(self):
        d=N.same_node_sums(*fixture());original_D=d['D']
        row=dict(row_start=0,space_nodes=2,native_return=[original_D]+[0]*8,diagnostic=d)
        E0=original_D-.25
        r=N.combine_chunks([row],dict(E0=E0,background=E0,trigger=0.),[original_D]+[0]*8)
        self.assertEqual(r['original_E'],-.25)
        self.assertGreaterEqual(r['Qa'],0)
        self.assertAlmostEqual(r['positive_node_reconstruction'],r['original_E'],places=14)

    def test_missing_or_duplicate_chunks_rejected(self):
        d=N.same_node_sums(*fixture());row=dict(row_start=1,space_nodes=2,native_return=[d['D']]+[0]*8,diagnostic=d)
        with self.assertRaises(ValueError):N.combine_chunks([row],dict(E0=1.,background=1.,trigger=0.),[d['D']]+[0]*8)

    def test_nonfinite_serialization_has_explicit_tags(self):
        r=R.json_value(dict(x=np.array([float('inf'),float('nan')]),flag=np.bool_(True)))
        self.assertEqual(r,{'x':[{'nonfinite':'+inf'},{'nonfinite':'nan'}],'flag':True})
        json.dumps(r,allow_nan=False)

    def test_observer_returns_original_object_even_on_diagnostic_failure(self):
        args=fixture();value=np.arange(9,dtype=float)
        native=types.SimpleNamespace(integrate=mock.Mock(return_value=value))
        diagnostic=mock.Mock(side_effect=ArithmeticError('invented diagnostic fault'))
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);(out/'order8').mkdir()
            observer=R.NativeObserver(native,diagnostic,N.array_identity,out,math.inf)
            observer.order=8;observer.grid={'r2':args[2]};observer.chunks=[]
            returned=observer.integrate(*args)
            self.assertIs(returned,value);np.testing.assert_array_equal(value,np.arange(9,dtype=float))
            self.assertEqual(observer.chunks[0]['diagnostic_error']['message'],'invented diagnostic fault')
            self.assertEqual(native.integrate.call_count,1)
            self.assertTrue((out/'order8/chunk_000000.json').is_file())

    def test_observer_reraises_original_native_exception(self):
        args=fixture();error=ArithmeticError('invented native failure')
        native=types.SimpleNamespace(integrate=mock.Mock(side_effect=error));diagnostic=mock.Mock()
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);(out/'order8').mkdir()
            observer=R.NativeObserver(native,diagnostic,N.array_identity,out,math.inf)
            observer.order=8;observer.grid={'r2':args[2]};observer.chunks=[]
            with self.assertRaises(ArithmeticError) as caught:observer.integrate(*args)
            self.assertIs(caught.exception,error);diagnostic.assert_not_called()
            self.assertEqual(observer.chunks[0]['native_error']['message'],'invented native failure')

    def test_capture_unchanged_original_exception_locals(self):
        from experiments.s04b_joint_nuisance import model
        class Fake(model.Phase):
            def __init__(self):
                self.M=0.;self.evaluations=0
                self.a={'event_x':np.zeros(1),'event_background_density':np.ones(1),'parent_excess':np.zeros(1)}
                self.lag=np.ones((1,1));self.event_r2=np.zeros((1,1))
            def check(self):pass
            def baseline(self,t):return [np.ones(1),np.zeros(1),np.zeros(1)],1.,np.zeros(8)
            def deficit(self,t,name,order):return np.array([2.]+[0.]*8)
        r=R.observed_original(Fake(),fixture()[8],8,model)
        self.assertFalse(r['returned']);self.assertTrue(r['frame_observed'])
        self.assertEqual(r['scalars']['E'],-1.);self.assertFalse(r['exposure_gate_passed'])
        self.assertTrue(all(r['finite'].values()))

    def test_protocol_preflight_does_not_import_scientific_modules(self):
        command='import sys;from experiments.s04b_exposure_diagnostic.run import verify_protocol,source_identity;verify_protocol();source_identity();assert not any(k.startswith(("numpy","scipy","experiments.s04b_joint_nuisance")) for k in sys.modules)'
        r=subprocess.run([sys.executable,'-B','-c',command],cwd=R.REPO,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_changed_source_rejected_before_numerical_import(self):
        p=copy.deepcopy(R.read(R.HERE/'protocol.json'))
        p['source_sha256']['experiments/s04b_joint_nuisance/model.py']='0'*64
        with mock.patch.object(R,'read',return_value=p):
            with self.assertRaisesRegex(ValueError,'Changed source_sha256'):R.verify_protocol()


if __name__=='__main__':unittest.main()
