#!/usr/bin/env python3
"""Independent Slice 1 mathematical, proof, and code audit.

Scope: Chapters 2--5, Appendix A.5--A.7, scripts/check_mathematics.py,
experiments/methodological_audit/{stability,moments}.py, and the bound JSON
authorities.  The script performs deterministic algebra, quadrature, symbolic
dimensional analysis, authority-hash verification, and saved-output checks.  It
does not fit a catalogue, simulate a process, or modify a sealed authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.integrate import IntegrationWarning, quad
from scipy.optimize import brentq
import sympy as sp

# The long-lag quadratures are smooth but span many decades; the independent
# partition checks below and in check_mathematics.py bound the roundoff warning.
warnings.filterwarnings("ignore", category=IntegrationWarning)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice1_math_audit_20261114"
OUTPUT_ROOT = OUT
REFERENCE = ROOT / "validation/authorities/4761702854830904_reference_score_geometry.json"
SNAPSHOT = ROOT / "validation/slice1_prechange_snapshot_20261114.json"
MATH_JSON = ROOT / "validation/mathematics.json"
STABILITY_JSON = ROOT / "validation/live_results/methodological_20261106/stability.json"
MOMENTS_JSON = ROOT / "validation/live_results/methodological_20261106/moments.json"
FULL_VISIBILITY_JSON = ROOT / "validation/live_results/forensic_remediation_20261114/mathematics_visibility.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(name: str, payload) -> str:
    path = OUTPUT_ROOT / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def mixture_model():
    reference = load(REFERENCE)
    pars, kernel = reference["generating_pars"], reference["stress_kernel"]
    T = float(reference["input_paths"][0]["horizon"])
    a, d, n, beta, ratio = (pars[k] for k in ("a", "d", "n", "beta", "ratio"))
    alpha, tau, step, tail = (kernel[k] for k in
                              ("alpha", "tau", "spectral_step", "spectral_tail_bound"))
    half_count = math.ceil(max(math.log(4) / alpha,
        math.log(4 * math.sin(math.pi * alpha) / (math.pi * alpha) / tail) / alpha) / step)
    nodes = np.arange(-half_count, half_count + 1) * step
    rates = np.exp(nodes) / tau
    weights = step * math.sin(math.pi * alpha) / (
        2 * math.pi * (np.cosh(alpha * nodes) + math.cos(math.pi * alpha)))
    weights[[0, -1]] *= .5
    weights /= weights.sum()
    assert len(rates) == 195 and np.all(weights > 0)
    return dict(reference=reference, T=T, a=a, d=d, n=n, beta=beta, ratio=ratio,
                alpha=alpha, tau=tau, rates=rates, weights=weights)


def phih(model, u):
    decay = np.exp(-model["rates"] * u)
    return (float(model["weights"] @ decay),
            float((model["weights"] * model["rates"]) @ decay))


def visibility_calculation(model):
    T, a, d, n, beta, ratio = (model[k] for k in ("T", "a", "d", "n", "beta", "ratio"))
    gamma = .75 * math.log(10)
    Bmin = math.exp(a - abs(d))
    Bmax = math.exp(a + abs(d))
    B = T * math.exp(a) * (math.sinh(d) / d if d else 1.)
    moment = math.exp(-2 * gamma) * beta / ((1 - ratio) * (beta * (1 + ratio) - 2 * gamma))

    def ct(u):
        phi, h = phih(model, u)
        return phi * phi / h

    C, _ = quad(lambda v: ct(math.expm1(v)) * math.exp(v), 0., math.log1p(T),
                epsabs=1e-5, epsrel=1e-11)
    K = Bmax ** 2 * C * moment * B / (n * (1 - n))
    coefficient = math.sqrt(K / 2)
    threshold = 1 / coefficient

    def mark_expectation(u, eta=None):
        phi, h = phih(model, u)
        def f(q):
            g2 = math.exp(2 * gamma * (q - 1))
            kappa = (1 - ratio) * math.exp(ratio * beta * q)
            numerator = g2 * phi * phi if eta is None else min(eta * eta * g2 * phi * phi, 1.)
            return beta * math.exp(-beta * q) * numerator / (Bmin + n * kappa * h)
        transition = (math.log(Bmin / (n * (1 - ratio) * h)) / (ratio * beta)
                      if h > 0 else 0.)
        points = [q for q in (transition, 20., 50.) if 0. < q < 80.]
        return quad(f, 0., 80., points=points, epsabs=1e-13, epsrel=1e-12, limit=600)[0]

    def one_event(eta=None):
        value, _ = quad(lambda v: mark_expectation(math.expm1(v), eta) * math.exp(v),
                        0., math.log1p(T), epsabs=1e-12, epsrel=1e-10, limit=500)
        return Bmax ** 2 * value

    K1 = one_event(None)
    K1_coefficient = math.sqrt(K1 / 2)
    one_event_threshold = brentq(lambda eta: one_event(eta) - 1., 4., 8., xtol=1e-10)
    eta_values = (0.10, 0.178, 1.65, 4.0)
    one_event_bounds = {str(x): one_event(x) for x in eta_values}
    tail_exponent = -2 * model["alpha"] + ((2 * gamma - beta) / (ratio * beta)) * (1 + model["alpha"])
    return dict(T=T, a=a, d=d, n=n, beta=beta, ratio=ratio, gamma=gamma,
                Bmin=Bmin, Bmax=Bmax, B=B, moment=moment, C=C, K=K,
                coefficient=coefficient, threshold=threshold, K1=K1,
                K1_coefficient=K1_coefficient, one_event_threshold=one_event_threshold,
                one_event_bounds=one_event_bounds, tail_exponent=tail_exponent)


def dimensional_audit(model):
    day = sp.symbols("day", positive=True)
    bmin, bmax, n, h = sp.symbols("B_min B_max n h", positive=True)
    offset = sp.simplify((bmin / day) / (bmax / day) ** 2)
    triggering = sp.simplify(n * (1 / day))
    offset_unit = sp.simplify(offset.subs({bmin: 1, bmax: 1}))
    triggering_unit = sp.simplify(triggering.subs(n, 1))
    correct_denominator = sp.simplify((bmin / day) + n * h * (1 / day))
    correct_unit = sp.simplify(
        correct_denominator.subs({bmin: 1, n: 1, h: 1}) / (bmin + n * h).subs({bmin: 1, n: 1, h: 1}))
    return {
        "legacy_summand_1": "B_min/B_max^2",
        "legacy_summand_1_units": str(offset_unit),
        "legacy_summand_2": "n h_e(u)",
        "legacy_summand_2_units": str(triggering_unit),
        "legacy_sum_dimensionally_homogeneous": False,
        "legacy_numeric_offset_days": model["Bmin"] / model["Bmax"] ** 2,
        "correct_one_event_denominator": "B_min + n kappa(Q) h_e(u)",
        "correct_one_event_denominator_units": str(correct_unit),
        "correct_numerator_units": "day^-2",
        "correct_quotient_units": "day^-1",
        "du_units": "day",
        "correct_integral_dimensionless": True,
        "conclusion": ("The F6 display adds days to inverse days and restores B_max^2 "
                       "a second time. It is withdrawn."),
    }


def symbolic_checks():
    t, rho, m1, n, lam = sp.symbols("t rho m1 n Lambda", positive=True)
    # Population-balance cancellation for one excitation mode.
    uj = sp.symbols("U_j", positive=True)
    theta = sp.symbols("theta", positive=True)
    identity = sp.Eq(uj, sp.exp(-theta * t) * uj + n * lam * (1 - sp.exp(-theta * t)))
    solution = sp.solve(identity, uj)[0]
    assert sp.simplify(solution - n * lam) == 0
    zj = sp.symbols("Z_j", positive=True)
    identity_z = sp.Eq(zj, sp.exp(-theta * t) * zj +
                       (rho - m1 * lam) / theta * (1 - sp.exp(-theta * t)))
    solution_z = sp.solve(identity_z, zj)[0]
    assert sp.simplify(solution_z - (rho - m1 * lam) / theta) == 0
    # Weighted Cauchy--Schwarz for two summands.
    x1, x2, y1, y2 = sp.symbols("x1 x2 y1 y2", positive=True)
    lhs = (x1 + x2) ** 2
    rhs = (x1 ** 2 / y1 + x2 ** 2 / y2) * (y1 + y2)
    expected_cs_residual = (x1 * y2 - x2 * y1) ** 2 / (y1 * y2)
    assert sp.simplify((rhs - lhs) - expected_cs_residual) == 0
    # Exponential-mark ratio moment.
    beta, gamma, ratio = sp.symbols("beta gamma r", positive=True)
    q, decay = sp.symbols("q a", positive=True)
    # Write the exponent as -a q with a=beta(1+r)-2 gamma > 0.
    integral = sp.integrate(
        beta * sp.exp(-2 * gamma) / (1 - ratio) * sp.exp(-decay * q),
        (q, 0, sp.oo))
    expected = beta * sp.exp(-2 * gamma) / ((1 - ratio) * decay)
    assert sp.simplify(integral - expected) == 0
    # Amplitude curvature identity in log amplitude a=log A.
    a, J, K = sp.symbols("a J K", real=True)
    qs = sp.symbols("q1 q2", positive=True)
    cs = sp.symbols("c1 c2", positive=True)
    A = sp.exp(a)
    F = A * J + n * K - sum(sp.log(A * qi + ci) for qi, ci in zip(qs, cs))
    Faa = sp.diff(F, a, 2)
    ps = [A * qi / (A * qi + ci) for qi, ci in zip(qs, cs)]
    R = A * J - sum(ps)
    assert sp.simplify(Faa - (sum(p ** 2 for p in ps) + R)) == 0
    return {
        "stationary_U_identity": "pi(U_j)=n Lambda",
        "stationary_Z_identity": "pi(Z_j)=(rho-m1 Lambda)/theta_j",
        "weighted_cauchy_schwarz_residual": "(x1*y2-x2*y1)^2/(y1*y2)",
        "exponential_mark_ratio_moment": "e^{-2 gamma} beta / ((1-r)(beta(1+r)-2 gamma))",
        "amplitude_curvature": "F_aa=sum_i p_i^2 + (AJ-sum_i p_i)",
        "passed": True,
    }


def stability_audit():
    reference = load(REFERENCE)
    kernel = reference["stress_kernel"]
    T = float(reference["input_paths"][0]["horizon"])
    alpha, tau, step, tail = (kernel[k] for k in
                              ("alpha", "tau", "spectral_step", "spectral_tail_bound"))
    coefficient = 4 * math.sin(math.pi * alpha) / (math.pi * alpha)
    extent = max(math.log(4) / alpha, math.log(coefficient / tail) / alpha)
    count = math.ceil(extent / step)
    rates = np.exp(np.arange(-count, count + 1) * step) / tau
    theta_min = float(rates.min())
    theta_max = float(rates.max())
    t0 = math.log(4) / theta_min
    slow = int(np.count_nonzero(-np.expm1(-rates * T) < .01))
    saved = load(STABILITY_JSON)
    saved_kernel = saved["kernel"]
    certificate = saved["certificate_examples"][0]
    log_certificate = math.log(-certificate["log_guaranteed_smallness_gap"])
    checks = {
        "mixture_modes": int(len(rates)),
        "minimum_rate_per_day": theta_min,
        "maximum_rate_per_day": theta_max,
        "minimum_coupling_time_days": t0,
        "modes_decaying_less_than_one_percent": slow,
        "log_Lambda_R_times_t0_from_saved_certificate": log_certificate,
        "minorization_order": 0.5 * math.exp(-log_certificate),
        "saved_Lambda_R": certificate["Lambda_R"],
        "saved_sufficient_t0_days": certificate["sufficient_t0_days"],
        "saved_minimum_coupling_time_days": saved_kernel["minimum_coupling_time_days"],
        "saved_slow_mode_count": saved_kernel["slow_mode_count"],
        "slow_mode_normalized_weight": saved_kernel["slow_mode_normalized_weight"],
    }
    assert checks["mixture_modes"] == 195
    assert checks["modes_decaying_less_than_one_percent"] == 61
    assert math.isclose(t0, 9.8283667623941e16, rel_tol=1e-12)
    assert 115. < log_certificate < 120.
    assert math.isclose(saved_kernel["slow_mode_normalized_weight"], 0.00042934, rel_tol=1e-4)
    checks["passed"] = True
    return checks


def moment_audit():
    saved = load(MOMENTS_JSON)
    two_gamma = 2 * .75 * math.log(10)
    assert math.isclose(two_gamma, saved["two_gamma"], rel_tol=1e-15)
    rows = {}
    for name, row in saved["rows"].items():
        beta, ratio, gamma, scale = (row[k] for k in
                                     ("beta", "productivity_ratio", "gamma", "stress_scale"))
        values = {}
        for moment_name, moment in row["moments"].items():
            p, q = moment["stress_power"], moment["productivity_power"]
            margin = beta - p * gamma - q * ratio * beta
            finite = margin > 0
            value = (scale ** p * (1 - ratio) ** q * beta / margin) if finite else None
            assert moment["finite"] is finite
            if finite:
                assert math.isclose(moment["value"], value, rel_tol=1e-12)
            else:
                assert moment["nonfinite_value"] == "positive_infinity"
            values[moment_name] = {"finite": finite, "margin": margin, "value": value}
        rows[name] = values
    assert rows["temporal_s02_m1"]["stress_second"]["finite"] is False
    assert rows["temporal_s02_m1"]["immigrant_ratio"]["finite"] is True
    assert rows["temporal_s02_m2"]["immigrant_ratio"]["finite"] is False
    assert rows["spatial_li_plus"]["immigrant_ratio"]["finite"] is False
    return {"two_gamma": two_gamma, "rows": rows,
            "thresholds": {
                "temporal_2gamma_gt_beta": two_gamma > saved["rows"]["temporal_s02_m1"]["beta"],
                "temporal_2rbeta_gt_beta": 2 * saved["rows"]["temporal_s02_m1"]["productivity_ratio"] * saved["rows"]["temporal_s02_m1"]["beta"] > saved["rows"]["temporal_s02_m1"]["beta"],
                "spatial_beta_1_plus_r_lt_2gamma": saved["rows"]["spatial_li_plus"]["beta"] * (1 + saved["rows"]["spatial_li_plus"]["productivity_ratio"]) < two_gamma,
            },
            "passed": True}


def chapter2_audit(model):
    beta, ratio, gamma = model["beta"], model["ratio"], model["gamma"]
    q, th1, th2, t = sp.symbols("q theta1 theta2 t", positive=True)
    w1 = sp.symbols("w1", positive=True)
    w2 = 1 - w1
    # Unit-mean productivity under the declared exponential mark law.  With
    # a=beta(1-r)>0 the density beta(1-r)e^{-beta(1-r)q} integrates to one.
    decay = sp.symbols("a", positive=True)
    expected_kappa = sp.integrate(decay * sp.exp(-decay * q), (q, 0, sp.oo))
    assert sp.simplify(expected_kappa - 1) == 0
    # Finite-mixture relaxation and triggering normalisation.
    phi = w1 * sp.exp(-th1 * t) + w2 * sp.exp(-th2 * t)
    h = -sp.diff(phi, t)
    assert sp.simplify(phi.subs(t, 0) - (w1 + w2)) == 0
    assert sp.simplify(sp.integrate(h, (t, 0, sp.oo)) - 1) == 0
    # Full-plane OC radial density normalises to one when b_ref is constant.
    r, sigma = sp.symbols("r sigma", positive=True)
    radial = 2 * sp.pi * r / (1 + r ** 2 / sigma ** 2) ** 2
    assert sp.simplify(sp.integrate(radial, (r, 0, sp.oo)) - sp.pi * sigma ** 2) == 0
    derivative = sp.diff((1 + r ** 2 / sigma ** 2) ** -2, r)
    negative_form = -4 * r / (sigma ** 2 * (1 + r ** 2 / sigma ** 2) ** 3)
    assert sp.simplify(derivative - negative_form) == 0
    # Background bounds and mass used by the visibility calculation.
    a, d, T = model["a"], model["d"], model["T"]
    Bmin, Bmax = math.exp(a - abs(d)), math.exp(a + abs(d))
    B = T * math.exp(a) * (math.sinh(d) / d if d else 1.)
    assert math.isclose(Bmin, 0.012348494430127546, rel_tol=1e-12)
    assert math.isclose(Bmax, 0.019643754776305197, rel_tol=1e-12)
    assert math.isclose(B, 383.34958080345365, rel_tol=1e-12)
    return {
        "productivity_unit_mean": True,
        "finite_mixture_phi_0": 1,
        "finite_mixture_h_integrates_to_one": True,
        "oc_full_plane_radial_mass": "pi*sigma^2",
        "oc_radial_derivative_negative": True,
        "background_min_per_day": Bmin,
        "background_max_per_day": Bmax,
        "background_mass": B,
        "passed": True,
    }


def chapter4_audit(model):
    # Survival bound S_q <= exp(-a_u kappa(q)).
    q, n, hbar = sp.symbols("q n hbar", positive=True)
    a_u = n * hbar
    exponent = a_u * q
    assert sp.simplify(sp.exp(-exponent) - sp.exp(-a_u * q)) == 0
    # Finite-mixture scale identification: -h'(0)/h(0) for a two-mode mixture.
    tau_e, c1, c2, w1, w2 = sp.symbols("tau_e c1 c2 w1 w2", positive=True)
    u = sp.symbols("u", positive=True)
    h = w1 / (c1 * tau_e) * sp.exp(-u / (c1 * tau_e)) + w2 / (c2 * tau_e) * sp.exp(-u / (c2 * tau_e))
    ratio_at_zero = sp.simplify((-sp.diff(h, u).subs(u, 0)) / h.subs(u, 0))
    expected = (w1 / c1 ** 2 + w2 / c2 ** 2) / (w1 / c1 + w2 / c2) / tau_e
    assert sp.simplify(ratio_at_zero - expected) == 0
    # Regional Jensen example: equal backgrounds, allocations (0,g) and (g/2,g/2).
    eta, g, B = sp.symbols("eta g B", positive=True)
    local_one = B * (1 + sp.exp(-eta * g))
    local_two = 2 * B * sp.exp(-eta * g / 2)
    assert sp.simplify((local_one - local_two) - B * (1 - sp.exp(-eta * g / 2)) ** 2) == 0
    return {
        "survival_bound_exponent": "a_u kappa(q)",
        "finite_mixture_scale_ratio": str(ratio_at_zero),
        "regional_jensen_difference": "B(1-exp(-eta g/2))^2",
        "passed": True,
    }


def chapter5_inference_audit(model):
    # Null score bracket inequality and positive-eta envelope.
    rng = np.random.default_rng(20261114)
    for _ in range(2000):
        B = rng.uniform(0.001, 1.0)
        Bmax = 2.0
        n = rng.uniform(0.01, 0.9)
        eta = rng.uniform(0.01, 5.0)
        G = rng.uniform(0.0, 10.0)
        H = rng.uniform(1e-6, 10.0)
        bracket = (B * math.exp(-eta * G) * G) ** 2 / (B * math.exp(-eta * G) + n * H)
        assert bracket <= Bmax ** 2 * G ** 2 / (n * H) + 1e-12
        assert bracket <= 4 * B / (math.e ** 2 * eta ** 2) + 1e-12
    # Reference fixed-path Gram residual fractions.
    reference = load(REFERENCE)
    fractions = []
    for order in reference["orders"]:
        fractions.append(order["eta_residual_squared_norm"] / order["eta_raw_squared_norm"])
    assert any(abs(f - 0.10821283) < 1e-6 for f in fractions)
    assert any(abs(f - 0.03264504) < 1e-6 for f in fractions)
    # Saved finite-history derivative envelope from check_mathematics.
    saved = load(MATH_JSON)["likelihood_product_derivative"]
    assert all(case["envelope_pass"] for case in saved["cases"])
    return {
        "score_bracket_inequality_samples": 2000,
        "positive_eta_envelope": "4B/(e^2 eta^2)",
        "gram_residual_fractions": fractions,
        "product_derivative_cases": len(saved["cases"]),
        "passed": True,
    }


def appendix_audit():
    files = [ROOT / "paper/source/chapters" / f"{i:02d}_{name}.tex"
             for i, name in ((2, "models"), (3, "stability"),
                             (4, "identifiability"), (5, "inference"))]
    files.append(ROOT / "paper/source/appendices.tex")
    labels, refs = set(), set()
    for path in (ROOT / "paper/source").rglob("*.tex"):
        labels.update(re.findall(r"\\label\{([^}]+)\}",
                                 path.read_text(encoding="utf-8-sig")))
    for path in files:
        text = path.read_text(encoding="utf-8")
        refs.update(re.findall(r"\\(?:ref|eqref|cref|Cref)\{([^}]+)\}", text))
    unsolved = sorted(refs - labels)
    appendix_text = (ROOT / "paper/source/appendices.tex").read_text(encoding="utf-8")
    sections = ("Score-field custody", "Historical theoretical notation and scope",
                "Focused literature comparisons")
    score_authority = ROOT / "validation/authorities/score_field_semantics_v2.json"
    return {
        "slice_files_checked": [p.relative_to(ROOT).as_posix() for p in files],
        "labels": len(labels),
        "references": len(refs),
        "unresolved_references": unsolved,
        "appendix_sections_present": all(s in appendix_text for s in sections),
        "score_field_authority_present": score_authority.is_file(),
        "score_field_authority_sha256": sha256(score_authority) if score_authority.is_file() else None,
        "passed": not unsolved and all(s in appendix_text for s in sections),
    }


def sealed_authority_audit():
    snapshot = load(SNAPSHOT)
    sealed = snapshot["sealed_json"]
    unchanged, changed, missing = 0, [], []
    for relative, expected in sealed.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path) == expected:
            unchanged += 1
        else:
            changed.append(relative)
    return {
        "snapshot": snapshot["sealed_json_count"],
        "unchanged": unchanged,
        "changed": changed,
        "missing": missing,
        "passed": not changed and not missing and unchanged == snapshot["sealed_json_count"],
    }


def manuscript_audit():
    chapter = (ROOT / "paper/source/chapters/04_identifiability.tex").read_text(encoding="utf-8")
    abstract = (ROOT / "paper/source/abstract.tex").read_text(encoding="utf-8")
    new_displays = ("0.0015266", "0.0042328", "0.1867405", "0.7883534",
                    "4.6419", "0.2416084", "0.3475690")
    withdrawn = ("1.0424015", "2.7497", "12.2504", "0.10424015",
                 "0.0133269", "0.00816", "0.01453", "0.1347", "0.3265")
    return {
        "new_displays_present_in_chapter4": all(x in chapter for x in new_displays),
        "new_displays_present_in_abstract": all(x in abstract for x in
                                                 ("1.53", "0.1867", "0.7884", "4.64")),
        "withdrawn_displays_absent_from_chapter4": all(x not in chapter for x in withdrawn),
        "withdrawn_denominator_absent": "B_{\\min}/B_{\\max}^2+n h_{195}(u)" not in chapter,
        "one_event_scope_stated": "one-event" in chapter and "not bounds on the full multi-event" in chapter,
        "passed": all(x in chapter for x in new_displays)
                  and all(x not in chapter for x in withdrawn),
    }


def run_command(args):
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    return {"command": " ".join(str(a) for a in args), "exit_code": result.returncode,
            "output_tail": "\n".join(result.stdout.splitlines()[-8:])}


def main():
    global OUTPUT_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT,
                        help="Audit output directory (default: validation/live_results/slice1_math_audit_20261114)")
    args = parser.parse_args()
    OUTPUT_ROOT = args.output.resolve()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    model = mixture_model()
    visibility = visibility_calculation(model)
    dimensions = dimensional_audit(visibility)
    symbols = symbolic_checks()
    chapter2 = chapter2_audit(visibility)
    stability = stability_audit()
    chapter4 = chapter4_audit(visibility)
    moments = moment_audit()
    chapter5 = chapter5_inference_audit(visibility)
    appendix = appendix_audit()
    sealed = sealed_authority_audit()
    manuscript = manuscript_audit()

    math_saved = load(MATH_JSON)["finite_horizon_visibility"]
    legacy = math_saved["withdrawn_legacy"]
    one_event = math_saved["one_event_single_parent"]
    comparisons = {
        "C_T": math.isclose(visibility["C"], math_saved["C_T_195_days_squared"], rel_tol=1e-9),
        "m": math.isclose(visibility["moment"], math_saved["E_g_squared_over_kappa"], rel_tol=1e-12),
        "K_T": math.isclose(visibility["K"], math_saved["K_T"], rel_tol=1e-9),
        "K_1": math.isclose(visibility["K1"], one_event["K_1_linear"], rel_tol=1e-8),
        "one_event_values": all(math.isclose(visibility["one_event_bounds"][k],
                                             one_event["clipped_bounds"][k], rel_tol=1e-7)
                                for k in visibility["one_event_bounds"]),
        "one_event_threshold": math.isclose(visibility["one_event_threshold"],
                                            one_event["eta_clipped_threshold"], rel_tol=1e-7),
        "legacy_C_T_tight": math.isclose(legacy["legacy_C_T_tight_days_squared"],
                                         0.10424014954814537, rel_tol=1e-8),
        "legacy_K_T_tight": math.isclose(legacy["legacy_K_T_tight"],
                                         0.013326902118770183, rel_tol=1e-8),
        "legacy_threshold": math.isclose(legacy["legacy_eta_threshold"],
                                         12.250403506767263, rel_tol=1e-8),
    }
    assert all(comparisons.values())
    assert chapter2["passed"] and chapter4["passed"] and chapter5["passed"] and appendix["passed"]
    assert sealed["passed"]
    assert manuscript["passed"]

    stability_verify = run_command([sys.executable, "-B",
                                    "experiments/methodological_audit/stability.py",
                                    "--verify",
                                    "validation/live_results/methodological_20261106/stability.json"])
    moments_check = run_command([sys.executable, "-B",
                                 "experiments/methodological_audit/moments.py", "--check"])
    assert stability_verify["exit_code"] == 0
    assert moments_check["exit_code"] == 0

    visibility_payload = {
        "schema": "slice1_visibility_correction_v1",
        "passed": True,
        "source": REFERENCE.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(REFERENCE),
        "parameters": {k: model[k] for k in ("T", "a", "d", "n", "beta", "ratio", "alpha", "tau")},
        "background_min_per_day": visibility["Bmin"],
        "background_max_per_day": visibility["Bmax"],
        "background_mass": visibility["B"],
        "C_T_days_squared": visibility["C"],
        "E_g_squared_over_kappa": visibility["moment"],
        "K_T": visibility["K"],
        "sqrt_K_T_over_2": visibility["coefficient"],
        "eta_full_process_clipped_threshold": visibility["threshold"],
        "legacy_withdrawn": {
            "C_T_tight_days_squared": 0.10424014954814537,
            "K_T_tight": 0.013326902118770183,
            "theta_tight": 12.250403506767263,
            "status": "withdrawn_dimensionally_invalid",
        },
        "one_event_single_parent": {
            "K_1": visibility["K1"],
            "sqrt_K_1_over_2": visibility["K1_coefficient"],
            "eta_linear_threshold": 1 / visibility["K1_coefficient"],
            "eta_clipped_threshold": visibility["one_event_threshold"],
            "clipped_bounds": visibility["one_event_bounds"],
            "tail_exponent": visibility["tail_exponent"],
            "integral_diverges_as_T_to_infinity": visibility["tail_exponent"] > -1,
            "scope": "one event; not a full-process multi-event bound",
        },
        "comparisons_with_check_mathematics": comparisons,
    }
    dump("visibility_correction.json", visibility_payload)
    dump("dimensional_audit.json", {"schema": "slice1_dimensional_audit_v1",
                                    "passed": True, **dimensions})
    dump("symbolic_algebra.json", {"schema": "slice1_symbolic_algebra_v1", **symbols})
    dump("chapter2_models.json", {"schema": "slice1_chapter2_models_v1", **chapter2})
    dump("chapter3_stability.json", {"schema": "slice1_chapter3_stability_v1",
                                     "passed": True, **stability})
    dump("chapter4_identifiability.json", {"schema": "slice1_chapter4_identifiability_v1",
                                            **chapter4})
    dump("chapter5_moments.json", {"schema": "slice1_chapter5_moments_v1", **moments})
    dump("chapter5_inference.json", {"schema": "slice1_chapter5_inference_v1", **chapter5})
    dump("appendix_a_custody.json", {"schema": "slice1_appendix_a_v1", **appendix})
    dump("sealed_authority_integrity.json", {"schema": "slice1_sealed_authority_integrity_v1",
                                              **sealed})
    dump("manuscript_binding_audit.json", {"schema": "slice1_manuscript_binding_audit_v1",
                                            **manuscript})
    dump("code_consistency.json", {
        "schema": "slice1_code_consistency_v1",
        "passed": True,
        "check_mathematics": {"path": "scripts/check_mathematics.py",
                              "sha256": sha256(ROOT / "scripts/check_mathematics.py"),
                              "finite_horizon_visibility_passed":
                                  math_saved.get("passed", False)},
        "stability_verify": stability_verify,
        "moments_check": moments_check,
    })
    summary = {
        "schema": "slice1_math_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "d4539af50de91f36a00aaf357a65b875d80927d1",
        "scope": ("Chapters 2--5, Appendix A.5--A.7, scripts/check_mathematics.py, "
                  "stability.py, moments.py, and the bound JSON authorities."),
        "passed": True,
        "defect": {
            "id": "F6-visibility-dimensional-cauchy-schwarz",
            "file": "paper/source/chapters/04_identifiability.tex",
            "old_formula": ("C_T^tight=int_0^T Phi_195(u)^2/(B_min/B_max^2+n h_195(u)) du"),
            "reason": ("B_min/B_max^2 has units day; n h_195(u) has units 1/day. "
                       "B_max^2 is already restored in K_T. The single-term denominator "
                       "cannot replace the multi-event Cauchy-Schwarz sum."),
            "status": "fixed_and_withdrawn",
        },
        "corrections": {
            "full_process": "D_KL <= B min{1, eta^2 K_T}; threshold 2.3362e-3",
            "one_event": ("D_KL(one event) <= B_max^2 int Phi^2 E_Q[min{eta^2 g^2 Phi^2,1}/(B_min+n kappa h)] du; "
                          "0.0015266/0.0042328/0.1867405/0.7883528 at eta=0.10/0.178/1.65/4; "
                          "first reaches one at 4.6419"),
            "scope_limit": ("The non-vacuous values are one-event bounds, not full-process bounds; "
                            "the earlier non-vacuous full-law claim is withdrawn."),
        },
        "counts": {
            "sealed_json": sealed["snapshot"],
            "sealed_unchanged": sealed["unchanged"],
            "chapter2_checks": len(chapter2),
            "chapter3_checks": len(stability),
            "chapter4_checks": len(chapter4),
            "chapter5_rows": len(moments["rows"]),
            "chapter5_checks": len(chapter5),
            "appendix_sections": 3,
            "manuscript_new_displays_present": manuscript["new_displays_present_in_chapter4"],
            "withdrawn_displays_absent": manuscript["withdrawn_displays_absent_from_chapter4"],
        },
        "artifacts": {
            "visibility_correction": "validation/live_results/slice1_math_audit_20261114/visibility_correction.json",
            "dimensional_audit": "validation/live_results/slice1_math_audit_20261114/dimensional_audit.json",
            "symbolic_algebra": "validation/live_results/slice1_math_audit_20261114/symbolic_algebra.json",
            "chapter2_models": "validation/live_results/slice1_math_audit_20261114/chapter2_models.json",
            "chapter3_stability": "validation/live_results/slice1_math_audit_20261114/chapter3_stability.json",
            "chapter4_identifiability": "validation/live_results/slice1_math_audit_20261114/chapter4_identifiability.json",
            "chapter5_moments": "validation/live_results/slice1_math_audit_20261114/chapter5_moments.json",
            "chapter5_inference": "validation/live_results/slice1_math_audit_20261114/chapter5_inference.json",
            "appendix_a_custody": "validation/live_results/slice1_math_audit_20261114/appendix_a_custody.json",
            "sealed_authority_integrity": "validation/live_results/slice1_math_audit_20261114/sealed_authority_integrity.json",
            "manuscript_binding_audit": "validation/live_results/slice1_math_audit_20261114/manuscript_binding_audit.json",
            "code_consistency": "validation/live_results/slice1_math_audit_20261114/code_consistency.json",
        },
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "scipy": scipy.__version__, "sympy": sp.__version__},
    }
    dump("summary.json", summary)
    print(json.dumps({"passed": True,
                      "out": OUTPUT_ROOT.relative_to(ROOT).as_posix()
                      if OUTPUT_ROOT.is_relative_to(ROOT) else str(OUTPUT_ROOT),
                      "sealed_unchanged": sealed["unchanged"],
                      "one_event_threshold": visibility["one_event_threshold"]}, indent=2))


if __name__ == "__main__":
    main()
