"""Deterministic scalar/control fixtures; no original history is fitted or scored."""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

MODULE = Path(__file__).resolve().parents[1]/'experiments/s04b_refitted_floor/run.py'
spec = importlib.util.spec_from_file_location('s04b_refitted_floor_tested',MODULE)
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


def fixture(count=3, exposure=5., trigger=.2, background=1.):
    f=dict(b=np.full(count,background),x=np.zeros(count),hp=np.full(count,trigger),
           hg=np.full(count,trigger),exposure=2.,marks=-1.25,
           start=0.,end=exposure,T0=10.)
    return R.sufficient(f,0.,1.)


class ScalarControls(unittest.TestCase):
    def test_no_excitation_has_clipped_count_over_exposure_solution(self):
        s=fixture(count=3,exposure=5.,trigger=0.)
        fit=R.fit_intercept(s,math.log(.2))
        self.assertAlmostEqual(fit['b'],.6,places=12)
        self.assertEqual(fit['selection'],'interior')

    def test_positive_excitation_root_matches_closed_form(self):
        fit=R.fit_intercept(fixture(),math.log(.2))
        self.assertAlmostEqual(fit['b'],.4,places=12)
        self.assertLess(fit['relative_derivative'],1e-9)

    def test_lower_endpoint_kkt(self):
        fit=R.fit_intercept(fixture(trigger=100.),math.log(.2))
        self.assertEqual(fit['b'],math.exp(-12.))
        self.assertEqual(fit['selection'],'lower')
        self.assertLess(fit['derivative'],0)

    def test_upper_endpoint_kkt(self):
        fit=R.fit_intercept(fixture(exposure=.1,trigger=0.),math.log(.2))
        self.assertEqual(fit['b'],1.)
        self.assertEqual(fit['selection'],'upper')
        self.assertGreater(fit['derivative'],0)

    def test_zero_targets_uses_lower_box_endpoint(self):
        fit=R.fit_intercept(fixture(count=0),math.log(.2))
        self.assertEqual(fit['selection'],'lower')

    def test_signed_exposure_and_mark_identity(self):
        s=fixture();before=R.components(s,.2);after=R.components(s,.4)
        d={k:after[k]-before[k] for k in ('P','E','C','M','joint')}
        self.assertEqual(d['M'],0.)
        self.assertEqual(d['C'],-d['E'])
        self.assertAlmostEqual(d['joint'],d['P']+d['C']+d['M'],places=13)
        self.assertAlmostEqual(after['timing']+after['location']+after['M'],after['joint'],places=13)

    def test_derivative_is_monotone(self):
        s=fixture()
        values=[R.derivative(s,b) for b in (.0001,.01,.2,.4,1.)]
        self.assertEqual(values,sorted(values,reverse=True))

    def test_nonfinite_and_negative_features_rejected(self):
        base=dict(b=np.array([1.]),x=np.array([0.]),hp=np.array([.2]),hg=np.array([.2]),exposure=1.,marks=0.,start=0.,end=5.,T0=5.)
        for key,value in [('b',np.array([float('nan')])),('b',np.array([0.])),('hp',np.array([-.2])),('exposure',float('nan'))]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                R.sufficient({**base,key:value},0.,1.)
        with self.assertRaises(ValueError):
            R.components(fixture(),float('nan'))

    def test_out_of_box_historical_value_rejected(self):
        with self.assertRaises(ValueError):
            R.fit_intercept(fixture(),-13.)

    def test_zero_trend_integral_continuity(self):
        self.assertEqual(R.integral(0.,30.,395.,760.),365.)
        self.assertAlmostEqual(R.integral(1e-12,30.,395.,760.),365.,places=8)

    def test_saved_spatial_features_exclude_equal_time_parent(self):
        path=R.INPUT/'source/spatial.py'
        spec=importlib.util.spec_from_file_location('_fixture_archived_spatial',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        a=dict(event_time=np.array([2.]),parent_time=np.array([1.,2.,3.]),
               parent_fertility=np.ones(3),event_parent_density=np.ones((1,3)),
               parent_exposure_lo=np.array([0.,0.,0.]),parent_exposure_hi=np.array([4.,3.,2.]),
               event_background_density=np.ones(1),event_x=np.zeros(1),event_excess=np.zeros(1))
        f=module.features(a,dict(start=0,end=5,T0=5,beta=2),[math.log(.5),1.3])
        expected=.3/.5*(1+1/.5)**(-1.3)
        self.assertAlmostEqual(f['hp'][0],expected,places=14)

    def test_scalar_components_match_archived_formula_on_fixture(self):
        path=R.INPUT/'source/spatial.py'
        spec=importlib.util.spec_from_file_location('_fixture_archived_spatial2',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        f=dict(b=np.array([.2,.6]),x=np.array([-.3,.4]),hp=np.array([.1,.8]),hg=np.array([.4,.9]),
               exposure=2.,marks=-3.,start=30.,end=395.,T0=760.)
        s=R.sufficient(f,.2,.35)
        class Wrapper: pass
        wrapper=Wrapper();wrapper.S=module
        for a in (-12.,math.log(.2),0.):
            self.assertTrue(all(abs(x)<1e-9 for x in R.crosscheck(wrapper,f,s,a,.2,.35).values()))


class CustodyControls(unittest.TestCase):
    def roster(self):
        return [dict(case_id=f'{r}_{s}',regime=r,seed=s) for r in range(4,8)
                for s in range(410001+100*r,410021+100*r)]

    def test_missing_duplicate_and_changed_seed_are_rejected(self):
        rows=self.roster();R.validate_roster(rows)
        for invalid in (rows[:-1],rows[:-1]+[rows[0]],[{**rows[0],'seed':1}]+rows[1:]):
            with self.assertRaises(ValueError):R.validate_roster(invalid)

    def test_path_escape_is_rejected(self):
        with self.assertRaises(ValueError):R.safe_input('../outside')
        with self.assertRaises(ValueError):R.safe_input(str(R.REPO.resolve()))

    def test_changed_protocol_rejected_before_any_scientific_call(self):
        with mock.patch.object(R,'sha',return_value='changed'), self.assertRaisesRegex(ValueError,'protocol'):
            R.verify_inputs()

    def test_wrong_dll_receipt_rejected_without_loading(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);lib=p/'radial.dll';lib.write_bytes(b'not a DLL')
            receipt=p/'receipt.json';receipt.write_text(json.dumps(dict(sources={'radial.cpp':'bad'},libraries={'radial':{'file':lib.name,'sha256':R.sha(lib)}})))
            with self.assertRaises(ValueError):R.verified_radial(lib,receipt)

    def test_failed_admission_retains_failed_result_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/'new'
            args=type('Args',(),dict(output=str(output),phase='pilot',acknowledge_reviewed_numerical_admission=''))()
            self.assertEqual(R.run(args),1)
            result=R.read(output/'result.json')
            self.assertFalse(result['passed'])
            self.assertEqual(result['error_type'],'ValueError')

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            args=type('Args',(),dict(output=td,phase='pilot'))()
            with self.assertRaises(FileExistsError):R.run(args)

    def test_incomplete_full_roster_cannot_aggregate(self):
        with self.assertRaises(ValueError):R.aggregate([])
        with self.assertRaises(ValueError):R.aggregate(self.roster())


if __name__=='__main__':
    unittest.main()
