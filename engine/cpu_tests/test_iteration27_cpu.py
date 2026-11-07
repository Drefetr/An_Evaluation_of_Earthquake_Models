"""CPU functional counterpart to the historical CUDA/CPU32 small-fit fixture.

The CUDA assertion is retained in its original suite. This test exercises the
CPU search plus finer CPU quadrature; it cannot establish GPU equivalence.
"""
from decimal import Decimal
from pathlib import Path
import sys
import time
import unittest
import numpy as np

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE / 'iteration_27/code'))
sys.path.insert(0, str(ENGINE / 'iteration_20/code'))


class CpuSmallFitFixture(unittest.TestCase):
    def test_complete_small_CPU16_CPU32_pair(self):
        from restricted_history import KnownLaw, KernelSpec
        from engine.cpu_fit import fit_pair
        # Same fixed fixture, start roster and numerical gates as the archived
        # CUDA test; only the explicitly labelled execution backend changes.
        rng = np.random.default_rng(81027)
        times = np.sort(rng.uniform(.1, 39.9, 30))
        q = rng.exponential(.1, 30)
        exact = [Decimal.from_float(float(t)) for t in times]
        gaps = np.array([float(t - (exact[i-1] if i else Decimal(0)))
                         for i, t in enumerate(exact)])
        arrays = dict(times=times, times_lo=np.zeros(30), event_gaps=gaps,
                      excess=q, exact_time_strings=np.array([str(t) for t in exact]))
        k = KernelSpec('exp', .7)
        law = KnownLaw(-2., .1, .3, 3., .4, 40., k, k, 40.)
        result = fit_pair(arrays, law,
                          dict(validation_reserve_seconds=5, maxls_tiers=[40, 200], maxiter=200),
                          None, time.perf_counter() + 30, backend='cpu')
        self.assertTrue(result['complete'], str(result))
        self.assertEqual(len(result['records']), 4)
        self.assertLess(max(result['deltas']), 1e-4)
        self.assertEqual(result['search_backend'], 'cpu')
        self.assertEqual(result['validation_backend'], 'cpu')
        self.assertEqual(result['comparison_scope'], 'CPU16/CPU32 refinement only')


if __name__ == '__main__':
    unittest.main(verbosity=2)
