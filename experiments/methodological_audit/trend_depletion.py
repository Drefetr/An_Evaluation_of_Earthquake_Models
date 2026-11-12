"""Reconstruct first-fold trend/depletion geometry from frozen observations.

No fitting or likelihood integration is performed. The archived pre-event
modal recursion is reused, its event intensities are checked against archived
scores, and ordinary least squares supplies a descriptive coordinate change.
That projection is not a likelihood-weighted collinearity or causal analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = 'reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv'
AUTHORITY = 'validation/authorities/e7fbc4fa4fae3da4_observed.json'
ADEQUACY = 'engine/iteration_27/code/adequacy.py'
KERNEL = 'engine/iteration_5/code/kernels.py'
PINS = {
    CATALOGUE: 'feacccb7581d1c4c33f88874cd6b198c41639da6930a7fc35e46f910a594fb3e',
    AUTHORITY: 'e7fbc4fa4fae3da4f8880695064798a8ebfc9342ab09303073f7afd7334439d8',
    ADEQUACY: '9662c90f9ff7e120fe26c1dfc0bd969071f16774feec686b9e97731337e0ff90',
    KERNEL: '3561ef3471adf349caebebc6c2ca12881f2a3d9c7c7415d15453b5be20b978ae',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values):
    return {name: float(function(values)) for name, function in
            [('mean', np.mean), ('median', np.median), ('min', np.min), ('max', np.max)]}


def calculate():
    for relative, pin in PINS.items():
        actual = sha(ROOT / relative)
        if actual != pin:
            raise ValueError('Source identity changed: '+relative+' ('+actual+')')
    authority = json.loads((ROOT/AUTHORITY).read_text(encoding='utf-8'))
    # Match the original run_adequacy.py CSV parser, including float parsing.
    # Python csv/float and pandas can differ in their last binary digit.
    rows = pd.read_csv(ROOT/CATALOGUE)
    times = rows.t_days.to_numpy()
    excess = rows.excess.to_numpy()
    assert len(times) == authority['input_binding']['n_events'] == 913
    assert np.all(np.diff(times) > 0) and np.all(excess >= 0)
    for label, array in [('times_f64le', times), ('excess_f64le', excess)]:
        assert hashlib.sha256(array.astype('<f8').tobytes()).hexdigest() == authority['array_binding'][label]

    spec = importlib.util.spec_from_file_location('_trend_depletion_adequacy', ROOT/ADEQUACY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fold = authority['folds']['fold_50']
    train_end, test_end, horizon = fold['train_end'], fold['test_end'], authority['T0']
    best = fold['fit']['best']
    inhibited, null = best['ml_shared'], best['ml_trigger']
    a, d, n, eta = inhibited['pars']
    a_null, d_null, n_null = null['pars']
    stress_kernel = module.KernelSpec(**inhibited['stress'])
    weights, rates = stress_kernel.mixture
    parents = times < test_end
    t, q = times[parents], excess[parents]
    amplitude = np.exp(module.GAMMA*(q-1.))
    before = module._modal_states(t, amplitude, rates)
    G = before@weights
    x = 2*t/horizon-1
    train = t < train_end
    test = (t >= train_end) & (t < test_end)
    assert int(train.sum()) == fold['fit']['n_train'] == 301
    slow = -np.expm1(-rates*horizon) < .01
    slow_G = before[:, slow]@weights[slow]

    # Equal-event-weight OLS: G = c + k*x + residual, fitted on training only.
    design = np.column_stack([np.ones(int(train.sum())), x[train]])
    c, k = np.linalg.lstsq(design, G[train], rcond=None)[0]
    residual = G-(c+k*x)
    assert np.max(np.abs(design.T@residual[train])) < 1e-10
    total_variation = np.sum((G[train]-np.mean(G[train]))**2)
    rss = float(residual[train]@residual[train])
    r_squared = float(1-rss/total_variation)
    transformed_a, transformed_d = a-eta*c, d-eta*k
    reconstructed = transformed_a+transformed_d*x-eta*residual
    log_background = a+d*x-eta*G
    identity_error = float(np.max(np.abs(reconstructed-log_background)))
    assert identity_error < 1e-12

    score_checks = {}
    for family in ('ml_trigger', 'ml_shared'):
        fitted = best[family]
        aa, dd, nn = fitted['pars'][:3]
        ee = fitted['pars'][3] if family == 'ml_shared' else 0.
        wt, rt = module.KernelSpec(**fitted['trigger']).mixture
        productivity = (1-fitted['ratio'])*np.exp(fold['fit']['beta_train']*fitted['ratio']*q)
        H = module._modal_states(t, productivity, rt)@(wt*rt)
        event_logs = np.logaddexp(aa+dd*x-ee*G, math.log(nn)+np.log(H, where=H>0,
                                      out=np.full_like(H, -np.inf)))
        score_checks[family] = {}
        for label, mask in [('training_controls', train), ('test_controls', test)]:
            archived = fold[label][family]['order32']
            saved = np.array(archived['event_log_intensities'])
            difference = float(np.max(np.abs(event_logs[mask]-saved)))
            assert difference < 1e-12
            score_checks[family][label] = difference

    null_test = fold['test_controls']['ml_trigger']['order32']
    inhibited_test = fold['test_controls']['ml_shared']['order32']
    delta_point = float(math.fsum(inhibited_test['event_log_intensities'])-
                        math.fsum(null_test['event_log_intensities']))
    delta_exposure = inhibited_test['integrated_intensity']-null_test['integrated_intensity']
    delta_joint = inhibited_test['full_marked_loglik']-null_test['full_marked_loglik']
    assert abs(delta_joint-(delta_point-delta_exposure)) < 1e-12

    # Event-log-intensity derivatives in (a,d,eta) are v*(1,x,-G),
    # where v is the fitted immigrant fraction. Remove the intercept before
    # comparing trend and depletion; their geometry weights each event by v^2.
    saved_train_logs = np.asarray(fold['training_controls']['ml_shared']['order32']['event_log_intensities'])
    fraction = np.exp(log_background[train]-saved_train_logs)
    score_weight = fraction**2
    centered_x = x[train]-np.average(x[train], weights=score_weight)
    centered_g = G[train]-np.average(G[train], weights=score_weight)
    weighted_correlation = float(np.sum(score_weight*centered_x*centered_g)/
        np.sqrt(np.sum(score_weight*centered_x**2)*np.sum(score_weight*centered_g**2)))
    scores = fraction[:, None]*np.column_stack([np.ones(int(train.sum())), x[train], -G[train]])
    normalized_scores = scores/np.linalg.norm(scores, axis=0)
    correlations = np.corrcoef(x[train], G[train])
    result = {
        'schema': 'first_fold_trend_depletion_geometry_v1',
        'passed': True,
        'source': 'Frozen first-origin ml_shared stress kernel and training observations; no refit.',
        'source_sha256': PINS,
        'script_sha256': sha(Path(__file__)),
        'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                     'pandas': pd.__version__, 'scipy': scipy.__version__},
        'events': int(train.sum()), 'test_events': int(test.sum()),
        'horizon_days': horizon, 'train_end_days': train_end, 'test_end_days': test_end,
        'x_min': float(x[train].min()), 'x_max': float(x[train].max()),
        'correlation_G_with_trend': float(correlations[0, 1]),
        'event_score_weighted_trend_depletion_correlation': weighted_correlation,
        'normalized_event_score_condition_number': float(np.linalg.cond(normalized_scores)),
        'event_score_weighting': 'Squared immigrant intensity fraction v^2; intercept removed. Positive correlation compares x with G; eta score has the opposite sign.',
        'spearman': float(spearmanr(x[train], G[train]).statistic),
        'linear_regression_slope': float(k),
        'stress_start': float(G[train][0]), 'stress_last': float(G[train][-1]),
        'fraction_positive_event_pre_stress_increments': float(np.mean(np.diff(G[train]) > 0)),
        'mixture_modes': len(weights), 'slow_modes': int(slow.sum()),
        'slow_mode_weight': float(weights[slow].sum()),
        'slow_mode_weight_percent': float(100*weights[slow].sum()),
        'slow_component_training': summary(slow_G[train]),
        'slow_component_fraction_of_last_training_G': float(slow_G[train][-1]/G[train][-1]),
        'G_training': summary(G[train]),
        'projection': {
            'weighting': 'Ordinary least squares with equal weights on training pre-event states only.',
            'intercept_c': float(c), 'slope_k': float(k), 'r_squared': r_squared,
            'explained_variance_percent': 100*r_squared,
            'unexplained_variance_fraction': 1-r_squared,
            'residual_train': summary(residual[train]), 'residual_test': summary(residual[test]),
            'identity': 'a+d*x-eta*G = (a-eta*c)+(d-eta*k)*x-eta*(G-c-k*x)',
            'identity_max_absolute_residual': identity_error,
            'projected_inhibited_a': float(transformed_a),
            'projected_inhibited_d': float(transformed_d),
            'eta_times_slope_k': float(eta*k),
            'parameter_tradeoff': 'Holding residual history fixed, da=c*deta and dd=k*deta preserves projected log-background level and slope; the residual term changes by -deta*(G-c-k*x).',
        },
        'fit_contrast': {
            'null_a': a_null, 'null_d': d_null, 'null_n': n_null,
            'inhibited_a': a, 'inhibited_d': d, 'inhibited_n': n, 'inhibited_eta': eta,
            'unattenuated_intercept_ratio': math.exp(a-a_null),
            'trend_coefficient_change': d-d_null,
            'training_log_background_minus_null': summary(log_background[train]-(a_null+d_null*x[train])),
            'test_log_background_minus_null': summary(log_background[test]-(a_null+d_null*x[test])),
        },
        'saved_heldout_accounting': {
            'null_integrated_intensity': null_test['integrated_intensity'],
            'inhibited_integrated_intensity': inhibited_test['integrated_intensity'],
            'delta_point': delta_point, 'delta_exposure': delta_exposure,
            'delta_signed_exposure': -delta_exposure, 'delta_joint': delta_joint,
        },
        'archived_event_intensity_max_absolute_errors': score_checks,
        'interpretation': {
            'supported': 'The nonzero projection slope shows an affine training component of depletion can exchange with intercept and trend in the log-background. The displayed identity is exact after retaining the residual.',
            'not_supported': 'Neither 61 slow modes nor these equal-event-weight correlations establishes monotone total depletion, a likelihood ridge, or a causal explanation of the heldout loss. The slow modes have very small total normalized weight and half of consecutive pre-event stress increments are negative.',
            'heldout_direction': 'The inhibited fitted procedure has LOWER heldout integrated intensity than ML. Its negative event-log-intensity contrast is larger than its compensator saving; unattenuated intercept/trend comparisons do not establish rate overprediction.',
        },
    }
    assert abs(result['correlation_G_with_trend']-.3863194913447053) < 1e-12
    assert abs(result['spearman']-.6727715561813822) < 1e-12
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'validation/live_results/trend_depletion_20261111.json')
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        result = calculate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'output': str(args.output),
                      'projection': result['projection'],
                      'heldout': result['saved_heldout_accounting']}, indent=2))


if __name__ == '__main__':
    main()
