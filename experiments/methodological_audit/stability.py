"""Portable scalar stability diagnostics and saved-procedure comparison.

No engine imports, likelihood evaluations, simulations or optimizer calls.
Run from any directory. --output refuses to overwrite; --verify is read-only.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    'engine/iteration_5/code/kernels.py': '3561ef3471adf349caebebc6c2ca12881f2a3d9c7c7415d15453b5be20b978ae',
    'engine/iteration_27/code/adequacy.py': '9662c90f9ff7e120fe26c1dfc0bd969071f16774feec686b9e97731337e0ff90',
    'experiments/autonomous/model.py': 'ddff28c9375660f72000455813bb6d8963f9227716c166dd644ab76765f47fb3',
    'experiments/autonomous/fit.py': '56d8ccda6b82974602d16a154ec7d7681fcda631070aaccadfa05843685b277e',
    'experiments/autonomous/protocol.json': 'ee30fac9d16b97d9f03425a95192b4d195d610f0126b8f0173e8878b97120754',
    'validation/live_results/autonomous_20261105/result.json': 'a8c590950f0b7296059538d22438c5c1c3130ff392b868982f95bc0570d6f47c',
    'validation/authorities/cf8397fb41830b31_summary.json': 'cf8397fb41830b31d93b73784d47be320f05f826b92a1a28b953e10e221a111e',
    'experiments/methodological_audit/stability_sources/H_observed_protocol.json': '81838dd3125548edfe37b846abc93bed2b771ce2bc2052e7839daf904b476683',
    'experiments/methodological_audit/stability_sources/stage_A_observed_protocol.json': '355facda79967efa0831ae3a3440e840fa6a9c7dd12e2367a5fe5993dc8ef483',
}


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def calculate():
    for relative, expected in PINS.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Input identity mismatch: ' + relative)
    protocol = read('experiments/autonomous/protocol.json')
    historical = read('experiments/methodological_audit/stability_sources/stage_A_observed_protocol.json')
    h_protocol = read('experiments/methodological_audit/stability_sources/H_observed_protocol.json')
    new = read('validation/live_results/autonomous_20261105/result.json')
    old = read('validation/authorities/cf8397fb41830b31_summary.json')
    spec = protocol['law']['shared_kernel']
    for key in ('kind', 'tau', 'alpha', 'spectral_step', 'spectral_tail_bound'):
        if any(p['common_nuisance']['trigger'][key] != spec[key] for p in (historical, h_protocol)):
            raise ValueError('Shared kernel comparison changed: ' + key)
    if historical['fixed']['r'] != protocol['law']['ratio'] or h_protocol['common_nuisance']['productivity_ratio'] != protocol['law']['ratio']:
        raise ValueError('Productivity ratio comparison changed')
    for key in ('a', 'n', 'eta'):
        if any(p['parameter_bounds'][key] != protocol['bounds'][key] for p in (historical, h_protocol)):
            raise ValueError('Parameter bounds comparison changed: ' + key)

    # Scalar transcription of the pinned KernelSpec.mixture formula, not a fit.
    alpha, step, tail, tau = (spec[k] for k in ('alpha', 'spectral_step', 'spectral_tail_bound', 'tau'))
    coefficient = 4 * math.sin(math.pi * alpha) / (math.pi * alpha)
    extent = max(math.log(4) / alpha, math.log(coefficient / tail) / alpha)
    count = math.ceil(extent / step)
    indices = list(range(-count, count + 1))
    rates = [math.exp(j * step) / tau for j in indices]
    raw = [step * math.sin(math.pi * alpha) / (2 * math.pi * (math.cosh(alpha * j * step) + math.cos(math.pi * alpha))) for j in indices]
    raw[0] *= .5
    raw[-1] *= .5
    weights = [v / sum(raw) for v in raw]
    if min(weights) <= 0 or min(rates) <= 0 or abs(sum(weights) - 1) > 1e-14:
        raise ArithmeticError('Positive normalized mixture check failed')
    horizon = protocol['T0']
    threshold = .01
    slow = [j for j, rate in zip(indices, rates) if -math.expm1(-rate * horizon) < threshold]
    theta = rates[0]
    minimum_t0 = math.log(4) / theta
    exponent = math.floor(math.log10(minimum_t0))
    kernel = {
        'modes': len(rates), 'half_count': count, 'log_rate_min': -count * step,
        'log_rate_max': count * step, 'min_rate_per_day': theta,
        'inverse_min_rate_days': 1 / theta, 'inverse_min_rate_years_365_25': 1 / theta / 365.25,
        'minimum_coupling_time_days': minimum_t0,
        'minimum_coupling_time_days_mantissa': minimum_t0 / 10 ** exponent,
        'minimum_coupling_time_days_exponent': exponent,
        'minimum_coupling_time_years_365_25': minimum_t0 / 365.25,
        'epsilon_upper_if_L_at_least_one': theta / 4,
        'horizon_days': horizon, 'decay_threshold': threshold, 'decay_threshold_percent': 100 * threshold,
        'slow_mode_count': len(slow), 'slow_indices': slow,
        'slow_mode_normalized_weight': sum(weights[j + count] for j in slow),
        'decay_at_index': {str(j): -math.expm1(-math.exp(j * step) * horizon / tau) for j in (-37, -36, -26)},
        'equilibrium_loading_coefficient_days': sum(w / rate for w, rate in zip(weights, rates)),
    }
    comparisons, certificates = [], []
    for index, (fold_id, fold) in enumerate(new['folds'].items()):
        records = {m['model']: m for m in old['selected_models'] if m['case_id'] == f'constant_background_fold_{index}'}
        null, inhibited = records['E0_ml'], records['I0_raw_ml']
        comparisons.append({
            'fold': fold_id, 'old_case_id': f'constant_background_fold_{index}',
            'old_beta': null['beta'], 'new_beta': fold['beta_train'],
            'old_gain': inhibited['forecast']['joint_logscore'] - null['forecast']['joint_logscore'],
            'new_gain': fold['heldout_gain'],
            'old_null_parameters': null['parameters'], 'old_inhibited_parameters': inhibited['parameters'],
            'new_null_parameters': fold['null']['selected']['pars'],
            'new_inhibited_parameters': fold['inhibited']['selected']['pars'],
        })
        for arm in ('null', 'inhibited'):
            assumptions = fold[arm]['theorem_assumptions']
            m1, n, psi = (assumptions[k] for k in ('m1', 'productivity_mean', 'link_upper_bound'))
            c = 2 * m1 / (1 - n) if m1 > 0 else 1.
            delta = c * (1 - n) - m1
            kappa_v = theta * min(1, delta / c)
            D = kappa_v + (m1 + c * n) * psi
            R = 4 * D / kappa_v
            epsilon = theta / (4 * max(psi, 1.))
            diameter = 2 * (R - 1) * max(1, rates[-1] / c)
            t0 = max(math.log(4), math.log(2 * diameter / epsilon)) / theta
            lambda_R = psi + rates[-1] * R / c
            certificates.append({
                'fold': fold_id, 'arm': arm, 'c': c, 'delta': delta, 'kappa_V_per_day': kappa_v,
                'invariant_V_upper': D / kappa_v, 'R': R, 'epsilon': epsilon,
                'diameter_upper': diameter, 'sufficient_t0_days': t0, 'Lambda_R': lambda_R,
                'log_guaranteed_smallness_gap': math.log(.5) - lambda_R * t0,
                'optimistic_log_certificate_gap_upper': math.log(.5) - psi * minimum_t0,
            })
    old_pooled = next(row['joint'] for row in old['aggregates'] if row['variant'] == 'constant_background' and row['comparison'] == 'I0_raw_ml-E0_ml')
    if abs(sum(row['old_gain'] for row in comparisons) - old_pooled) > 1e-10 or abs(sum(row['new_gain'] for row in comparisons) - new['pooled_gain']) > 1e-10:
        raise ArithmeticError('Saved pooled-score reconciliation failed')
    return {
        'schema': 'methodological_stability_diagnostic_v1', 'passed': True,
        'scope': 'Scalar proof-certificate calculations and saved-record comparison only; no model imports, likelihoods, simulations or optimizers.',
        'source_sha256': PINS,
        'diagnostic_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'kernel': kernel, 'certificate_examples': certificates, 'comparisons': comparisons,
        'old_pooled_gain': old_pooled, 'new_pooled_gain': new['pooled_gain'],
        'old_fit_policy': historical['fit_policy'], 'new_starts': protocol['starts'], 'new_solver': protocol['solver'],
        'interpretation': {
            'rate': 'Sufficient proof certificates do not estimate or lower-bound the actual process mixing time.',
            'weight': 'Normalized Phi weight is not a bound for arbitrary initial states or total observed stress.',
            'family': 'Same raw constant-background conditional intensity family, different nuisance and optimizer procedures.',
            'attribution': 'No controlled beta-only comparison is present; the score change cannot be assigned solely to beta.',
            'loading': 'Equilibrium initialization confounds rho with the exponential-link intercept; it is not stationary event-process initialization.',
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path, help='Write a new result file; existing files are refused.')
    group.add_argument('--verify', type=Path, help='Compare the deterministic result with an existing JSON file.')
    args = parser.parse_args()
    result = calculate()
    if args.verify:
        if json.loads(args.verify.read_text(encoding='utf-8')) != result:
            raise SystemExit('FAIL: diagnostic differs from saved result')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'modes': result['kernel']['modes'], 'slow_modes': result['kernel']['slow_mode_count']}))


if __name__ == '__main__':
    main()
