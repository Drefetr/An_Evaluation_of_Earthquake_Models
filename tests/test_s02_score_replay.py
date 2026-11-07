"""Small constructed S02 adapter controls; no archived history is evaluated."""
import importlib.util
import math
from pathlib import Path
import tempfile
import types
import unittest
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('s02_replay_under_test', ROOT/'reproduction/score_replay/s02_replay.py')
R = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(R)


class TestS02SelectedReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine.cpu_build import build_shared
        # Loaded Windows DLLs cannot be removed until process exit. Retain this
        # bounded system-temp build with source/compiler receipt, as other CPU tests do.
        cls.directory = Path(tempfile.mkdtemp(prefix='s02-replay-fixture-'))/'native'
        cls.build = build_shared(R.HERE/'components.cpp', cls.directory, dependency_root=R.HERE)
        if not cls.build['passed']:
            raise RuntimeError('Real C++17 build failed: '+str(cls.directory/'build.log'))
        cls.oracle = R.load_oracle()
        cls.native = cls.oracle.Native(cls.build['library'])
        cls.extra = R.Extra(cls.native, cls.oracle)
        cls.law = dict(T=3., coordinate=3., beta=2., gamma=.75*math.log(10), n=.5, ratio=.2,
                       stress=dict(kind='exp', tau=.3), trigger=dict(kind='exp', tau=.7))

    def state(self):
        return self.native.state(dict(times=np.array([1., 1., 2.]), times_lo=np.array([0., 1e-20, 0.]),
                                      event_gaps=np.array([1., 1e-20, 1.]), excess=np.array([.1, .2, .3])),
                                 self.law, 'paired', .2, 32, True)

    def test_original_direct_sum_integral_gradient_controls(self):
        result = self.oracle.fixtures(self.build['library'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['checks'], 36)
        self.assertLessEqual(result['maximum_direct_nll_error'], 1e-8)

    def test_empty_history_components_are_analytic(self):
        state = self.native.state(dict(times=np.array([]), excess=np.array([])), self.law, 'projected', .2, 32, True)
        try:
            p, exposure, immigrant, offspring, nodes = self.extra.components(state, [-2., 0., .5, 0.])
            self.assertEqual((p, offspring, nodes), (0., 0., 0.))
            self.assertAlmostEqual(exposure, 3*math.exp(-2), places=14)
            self.assertEqual(exposure, immigrant)
        finally:
            state.close()

    def test_components_and_common_mark_signs(self):
        state = self.state()
        try:
            par = [-2., .1, .5, .2]
            expected = float(state.evaluate(par)[0])
            mark = 3*math.log(2)-2*.6
            row = R.evaluate_selected(state, self.extra, par, expected, mark, 1e-4, 1e-8)
            self.assertTrue(row['passed'])
            self.assertAlmostEqual(row['joint'], row['P']+row['C']+row['M'], places=12)
            self.assertEqual(row['timing'], -row['nll_ground'])
            self.assertEqual(row['C'], -row['E'])
            self.assertAlmostEqual(row['M'], mark, places=14)
        finally:
            state.close()

    def test_direct_contrast_and_exact_null_tie(self):
        state = self.state()
        try:
            null, alternative = [-2., .1, .5, 0.], [-1.9, .12, .5, .2]
            result = self.extra.glr(state, null, alternative)
            expected = 2*(state.evaluate(null)[0]-state.evaluate(alternative)[0])
            self.assertAlmostEqual(result[0], expected, places=10)
            self.assertEqual(result[0], 2*(result[1]+result[2]))
            self.assertEqual(list(self.extra.glr(state, null, null)), [0., 0., 0.])
        finally:
            state.close()

    def test_expected_scalar_mismatch_is_failed_not_zeroed(self):
        state = self.state()
        try:
            parameters = [-2., .1, .5, .2]
            actual = float(state.evaluate(parameters)[0])
            row = R.evaluate_selected(state, self.extra, parameters, actual+1., 0., 1e-4, 1e-8)
            self.assertFalse(row['passed'])
            self.assertEqual(row['nll_ground'], actual)
            self.assertAlmostEqual(row['nll_delta'], -1.)
        finally:
            state.close()

    def test_clock_rejects_projected_tie_and_preserves_paired_gap(self):
        data = dict(times=np.array([1., 1.]), times_lo=np.array([0., 1e-20]),
                    event_gaps=np.array([1., 1e-20]), excess=np.array([0., 0.]))
        _, _, gaps, _, paired = self.oracle.clock(data, self.law, 'paired')
        self.assertTrue(paired)
        self.assertEqual(gaps[1], 1e-20)
        with self.assertRaises(ValueError):
            self.oracle.clock(data, self.law, 'projected')

    def test_archived_source_bytes_and_fixed_pilot_are_bound(self):
        protocol = R.read(R.HERE/'protocol.json')
        with zipfile.ZipFile(ROOT/'reproduction/s02/completed_inputs_20261031.zip') as source:
            for row in protocol['source_copies']:
                self.assertEqual((R.HERE/row['path']).read_bytes(), source.read(row['archive_member']))
                self.assertEqual(R.sha(R.HERE/row['path']), row['sha256'])
        self.assertEqual(protocol['pilot'], ['s000_h0p0', 's000_h0p5', 's000_h0p9', 's043_h0p0', 's043_h0p5', 's043_h0p9'])

    def test_unreviewed_admission_cannot_load_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'admission.json'; R.write(path, dict(passed=False))
            with self.assertRaisesRegex(ValueError, 'reviewed admission'):
                R.check_admission(types.SimpleNamespace(admission=path), R.read(R.HERE/'protocol.json'))

    def test_completion_cannot_omit_pilot(self):
        with self.assertRaisesRegex(ValueError, 'requires reviewed pilot'):
            R.completion_union(types.SimpleNamespace(pilot=None), {}, {}, {}, Path('.'))

    def test_paired_summary_requires_all_forest_units(self):
        row = R.paired_statistics(list(range(100)))
        self.assertEqual(row['mean'], 49.5)
        self.assertEqual(row['median'], 49.5)
        self.assertAlmostEqual(row['mcse'], math.sqrt(100*101/12)/10)
        with self.assertRaises(ValueError): R.paired_statistics(list(range(99)))


if __name__ == '__main__':
    unittest.main()
