"""Small dependency/ABI controls; never launch a research campaign."""
from pathlib import Path
import importlib
import math
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
PREFIX = 'engine.stage2_followup.'


class PublicWorkflows(unittest.TestCase):
    def test_supported_and_preserved_dependencies_import_without_execution(self):
        for name in ('s01_s02_temporal.campaign', 's01_s02_temporal.s01_aggregate',
                     's01_s02_temporal.s02_campaign',
                     's03_s06_spatial_benchmarks.continuous_omnibus',
                     's03_s06_spatial_benchmarks.calibration_campaign',
                     's03_s06_spatial_benchmarks.s06.runner',
                     's04_s04b_local_inhibition.controls_campaign',
                     's04_s04b_local_inhibition.summarize'):
            with self.subTest(module=name):
                importlib.import_module(PREFIX + name)

    def test_direct_public_cli_help_needs_no_private_workspace(self):
        stage = ROOT / 'engine/stage2_followup'
        for name in ('s04_s04b_local_inhibition/build.py',
                     's04_s04b_local_inhibition/controls_campaign.py',
                     's04_s04b_local_inhibition/summarize.py',
                     's03_s06_spatial_benchmarks/continuous_omnibus.py',
                     's03_s06_spatial_benchmarks/ep/adapter.py'):
            with self.subTest(script=name):
                result = subprocess.run([sys.executable, '-B', str(stage / name), '--help'],
                                        cwd=ROOT, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)

    def test_native_build_uses_existing_shared_radial_source(self):
        from engine.stage2_followup.native_build import targets
        for group in ('li', 'temporal', 'spatial', 's06'):
            for _, source in targets(group):
                self.assertTrue(source.is_file(), source)
        radial = dict(targets('li'))['radial.dll']
        self.assertEqual(radial.parent.name, 's03_s06_spatial_benchmarks')

    def test_unknown_reference_cannot_be_silently_zero_filled(self):
        from engine.stage2_followup.s01_s02_temporal.calibration_arithmetic import calibrate
        answer = calibrate([[0, 0, 0, 0], [None, None, None, None]], [[1, 1, 1, 1]], .5)
        self.assertEqual(answer['rank_intervals']['I00'], [[1 / 3, 2 / 3]])
        self.assertEqual(answer['decisions']['I00'], [None])
        self.assertEqual(answer['rejection_bounds']['I00'], [0, 1])

    def test_inclusive_rank_ties_and_deterministic_coordinates(self):
        from engine.stage2_followup.s03_s06_spatial_benchmarks.rank_envelope import envelope
        answer = envelope([[1, 7], [1, 7], [1, 7]], ['score', 'immigrant_exposure'])
        self.assertEqual(answer['p_value'], 1)
        self.assertFalse(answer['reject'])
        self.assertTrue(answer['degenerate'])


@unittest.skipUnless(os.environ.get('INHIBITORY_TEST_NATIVE_ROOT'),
                     'Set INHIBITORY_TEST_NATIVE_ROOT to separately built native groups')
class NativeFixtures(unittest.TestCase):
    def setUp(self):
        self.native = Path(os.environ['INHIBITORY_TEST_NATIVE_ROOT'])

    def test_li_handcrafted_gradient_and_boundary_fixture(self):
        result = subprocess.run([str(self.native / 'li/fixture.exe')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"passed":true', result.stdout)

    def test_s06_python_native_geometry_abi(self):
        from engine.stage2_followup.s03_s06_spatial_benchmarks.s06 import engine
        with patch.dict(os.environ, INHIBITORY_S06_NATIVE_DIR=str(self.native / 's06')):
            values = engine.rectangle_integrals(np.array([[0., 0.]]), 100.)
        self.assertEqual(values.shape, (1, 9))
        self.assertTrue(np.isfinite(values).all())
        self.assertTrue((values > 0).all())

    def test_temporal_cached_history_matches_handcrafted_poisson(self):
        from engine import api
        from engine.stage2_followup.s01_s02_temporal.stage2_history import CachedHistory
        old = api.load('restricted')
        law = old.KnownLaw(math.log(.2), 0., 0., 1., 0., 10.,
                           old.KernelSpec('exp', 1.), old.KernelSpec('exp', 1.))
        arrays = {'times': np.array([1., 3.]), 'excess': np.array([.2, .4])}
        model = CachedHistory(self.native / 'temporal/temporal_stage2.dll', arrays, law,
                              old.cpu, clock_mode='projected', order=16)
        try:
            value = model.objective([law.a, 0., 0., 0.], gradient=False)
            self.assertTrue(model.cache_active)
            # The cached objective omits the fixed mark-density constant.
            self.assertAlmostEqual(value, 2 - 2 * math.log(.2), places=10)
            self.assertAlmostEqual(model.mark_nll_constant, .6, places=12)
        finally:
            model.close()


if __name__ == '__main__':
    unittest.main()
