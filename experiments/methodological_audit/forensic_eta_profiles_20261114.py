"""Forensic California EP+ eta profiles (14 November 2026).

The archived profile script used a linear secant between eta=0 and eta=0.01
(where the training likelihood has already fallen by hundreds of nats) and
evaluated the profiled-null baseline at the eta-profiled parameter vector.
This additive script repairs both errors.

* The fixed-backbone score derivative is evaluated analytically at eta=0.
* Roots of the training profile at the two-sided 95% (one-sided 97.5%)
  cutoff -1.9207 and the one-sided 95% cutoff -1.3528 are found by an exact
  Newton/brentq iteration on the implemented likelihood.
* The profiled curve is re-based on the uninhibited MLE x0 = psi_hat(0), not
  on psi_hat(eta), and the held-out contrast is re-based the same way.
* An unscaled ell=15 km profile is computed alongside the rupture-scaled
  ell_j = 15 * 10^{0.5(M_j-4)} km kernel.

No sealed authority is rewritten.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import minimize, root_scalar
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import experiments.methodological_audit.eta_profiles_and_power as E  # noqa: E402

TARGETS = {"two_sided_95": -1.9207, "one_sided_95": -1.3528}
FINE_GRID = (0.0, 1e-5, 2.5e-5, 5e-5, 7.5e-5, 1e-4, 1.5e-4, 2.5e-4, 5e-4, 0.01)
SCALE_PAIRS = ((10.0, 2.0), (15.0, 5.0), (20.0, 5.0), (50.0, 30.0))
CASES = ("california_fold_0", "california_fold_1", "california_fold_2")


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def base_model(case: str, power: int = 14):
    train, meta, test, test_meta, _ = E.RF.inputs(case)
    record = read(E.ACCEPTED / case / "result.json")
    weights = np.asarray(record["background_weights"], dtype=float)
    region = E.RF.Region(train["rectangles"])
    background = E.RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    train_model = E.RF.Model(train, meta, background)
    test_model = E.RF.Model(test, test_meta, background)
    x0 = np.asarray(record["null"]["selected"]["parameters"], dtype=float)
    train_model.node_setup(x0, power=power, seed=20261111)
    test_model.node_setup(x0, power=16, seed=20261120)
    return record, train_model, test_model, x0


class UnscaledGModel(E.RF.Model):
    """Model with ell_j == ell0 (no magnitude scaling of the spatial range)."""

    def G(self, data, x):
        eta, le, lp, gamma = x[8:]
        psi = np.exp(lp)
        ell2 = float(np.exp(2 * le))
        lag, r2, past = data["lag"], data["r2"], data["past"]
        v = r2 / ell2
        k = np.exp(gamma * self.dm - lag / psi) * (1 + v) ** -2 * past
        return k.sum(axis=1), np.stack([(k * 4 * v / (1 + v)).sum(axis=1),
                                        (k * lag / psi).sum(axis=1),
                                        (k * self.dm).sum(axis=1)], axis=1)


def precompute(model, x0, ell, psi):
    """Precompute the eta-dependent pieces of the fixed-backbone likelihood."""
    x = np.asarray(x0, dtype=float).copy()
    x[8] = 0.0
    x[9] = math.log(ell)
    x[10] = math.log(psi)
    lam, _ = model.base_values(model.events, x)
    P0 = float(np.log(lam).sum())
    E0 = float(model.exact_exposure(x)[0])
    event_g = model.G(model.events, x)[0]
    event_sum = float(event_g.sum())
    data = model.nodes
    Ls, gs, ws = [], [], []
    for start in range(0, len(data["t"]), 1024):
        raw = {k: v[start:start + 1024] for k, v in data.items()}
        z = model.prepare(raw["t"], raw["xy"], raw["b"])
        L, _ = model.base_values(z, x)
        g, _ = model.G(z, x)
        Ls.append(L)
        gs.append(g)
        ws.append(raw["w"])
    return dict(P0=P0, E0=E0, event_sum=event_sum,
                L=np.concatenate(Ls), g=np.concatenate(gs), w=np.concatenate(ws),
                base=float(model.objective(x0, False, True)["nll"]))


def gain_and_derivative(pc, eta):
    deficit = float(pc["w"] @ (pc["L"] * (-np.expm1(-eta * pc["g"]))))
    nll = pc["E0"] - deficit - pc["P0"] + eta * pc["event_sum"]
    dnll = -float(pc["w"] @ (pc["L"] * pc["g"] * np.exp(-eta * pc["g"]))) + pc["event_sum"]
    return pc["base"] - nll, -dnll


def newton_root(pc, target, guess=None):
    if guess is None:
        guess = target / gain_and_derivative(pc, 0.0)[1]
    eta = float(guess)
    residual = float("inf")
    for _ in range(60):
        value, derivative = gain_and_derivative(pc, eta)
        residual = value - target
        if abs(residual) < 1e-13:
            break
        step = residual / derivative
        eta_next = eta - step
        if not np.isfinite(eta_next):
            break
        if abs(eta_next - eta) < 1e-16:
            eta = eta_next
            break
        eta = eta_next
    return dict(eta=eta, residual=float(residual), iterations=None)


def brentq_root(pc, target, bracket=(0.0, 0.01)):
    """Independent bracketed check of the Newton root."""
    def f(eta):
        return gain_and_derivative(pc, eta)[0] - target
    return root_scalar(f, bracket=bracket, method="brentq", xtol=1e-14, rtol=1e-14)


def profile_curve(case, model_cls, ell, psi, power):
    """Re-optimize (a,d,n) at each eta on the corrected profile curve."""
    record, train_model, test_model, x0 = base_model(case, power=power)
    if model_cls is UnscaledGModel:
        train_model = UnscaledGModel(train_model.a, train_model.m, train_model.bg)
        train_model.node_setup(x0, power=power, seed=20261111)
    base = float(train_model.objective(x0, False, True)["nll"])
    stored = read(ROOT / "validation/live_results/track_b_controls_20261112/"
                        "profiles_and_power/california_eta_profiles.json")
    row = next(r for r in stored["rows"] if r["case"] == case)
    seed_curve = row["profiled_s8_scale"]["curve"]
    indices = [0, 1, 2]
    lo = np.asarray([E.RF.BOUNDS[i][0] for i in indices])
    hi = np.asarray([E.RF.BOUNDS[i][1] for i in indices])
    start = np.asarray(seed_curve[0]["parameters"], dtype=float)
    curve = []
    for eta in (0.0, 1e-4, 5e-4, 1e-3, 2e-3, 5e-3, 0.01):
        x = start.copy()
        x[8] = eta
        x[9] = math.log(ell)
        x[10] = math.log(psi)

        def target(v):
            y = x.copy()
            y[indices] = v
            value, gradient = train_model.objective(y, True)
            return value, gradient[indices]

        opt = minimize(target, np.clip(x[indices], lo, hi), jac=True,
                       bounds=list(zip(lo, hi)), method="L-BFGS-B",
                       options=dict(maxiter=600, maxls=80, ftol=1e-9, gtol=1e-4))
        y = x.copy()
        y[indices] = opt.x
        nll = float(train_model.objective(y, True, True)["nll"])
        curve.append(dict(eta=eta, train_nll=nll, train_loglik_gain=base - nll,
                          success=bool(opt.success), parameters=[float(v) for v in y]))
        if opt.success:
            start = y
    return dict(case=case, base_nll=base, curve=curve,
                eta95_upper=pchip_root(curve, -1.9207),
                eta95_upper_one_sided=pchip_root(curve, -1.3528))


def pchip_root(curve, target):
    eta = np.asarray([r["eta"] for r in curve], dtype=float)
    gain = np.asarray([r["train_loglik_gain"] for r in curve], dtype=float)
    order = np.argsort(eta)
    interpolant = PchipInterpolator(eta[order], gain[order])
    lo, hi = float(eta.min()), 1e-4
    # Expand the upper end until the target is crossed, remaining inside the
    # stored curve's support.
    if interpolant(hi) > target:
        hi = float(eta.max())
    f = lambda e: float(interpolant(e)) - target
    try:
        result = root_scalar(f, bracket=(lo, hi), method="brentq", xtol=1e-16, rtol=1e-14)
        return dict(eta=float(result.root), residual=float(f(result.root)), bracket=[lo, hi])
    except ValueError:
        return dict(eta=None, residual=None, bracket=[lo, hi])


def fixed_backbone(case: str) -> dict:
    record, train_model, test_model, x0 = base_model(case, power=14)
    base = float(train_model.objective(x0, False, True)["nll"])
    out = {}
    for ell, psi in SCALE_PAIRS:
        pc = precompute(train_model, x0, ell, psi)
        slope0 = gain_and_derivative(pc, 0.0)[1]
        fine = [dict(eta=eta, gain=gain_and_derivative(pc, eta)[0]) for eta in FINE_GRID]
        roots = {}
        for label, target in TARGETS.items():
            root = newton_root(pc, target)
            check = brentq_root(pc, target)
            roots[label] = dict(eta=root["eta"], residual=root["residual"],
                                brentq_eta=float(check.root),
                                brentq_residual=float(gain_and_derivative(pc, check.root)[0] - target),
                                iterations=int(check.iterations))
        out[f"ell{ell:g}_psi{psi:g}"] = dict(
            ell_km=ell, psi_days=psi,
            training_score_slope_at_zero=float(slope0),
            event_sum_G=pc["event_sum"],
            exposure_integral_lambda0_G=float(pc["w"] @ (pc["L"] * pc["g"])),
            event_minus_exposure=float(pc["event_sum"] - (pc["w"] @ (pc["L"] * pc["g"]))),
            fine_grid=fine, roots=roots)
    # Corrected profiled curve and held-out baseline.
    stored = read(ROOT / "validation/live_results/track_b_controls_20261112/"
                        "profiles_and_power/california_eta_profiles.json")
    row = next(r for r in stored["rows"] if r["case"] == case)
    curve = row["profiled_s8_scale"]["curve"]
    corrected = [dict(eta=r["eta"], train_nll=r["train_nll"],
                      train_loglik_gain=base - r["train_nll"],
                      archived_train_loglik_gain=r["train_loglik_gain"],
                      parameters=r["parameters"]) for r in curve]
    eta04 = next(r for r in corrected if abs(r["eta"] - 0.4) < 1e-12)
    test_prof = test_model.objective(np.asarray(eta04["parameters"], dtype=float), True, True)
    null_test = test_model.objective(x0, False, True)["nll"]
    prof_roots = {}
    for label, target in TARGETS.items():
        prof_roots[label] = pchip_root(corrected, target)
    # Old, corrupted held-out baseline: null evaluated at psi_hat(0.4).
    old_test_null = test_model.objective(np.asarray(eta04["parameters"], dtype=float), False, True)["nll"]
    return dict(case=case, n_train=row["n_train"], n_test=row["n_test"],
                fixed_backbone=out,
                profiled_s8_scale=dict(
                    curve=corrected, eta95_upper=prof_roots["two_sided_95"],
                    eta95_upper_one_sided=prof_roots["one_sided_95"],
                    null_train_nll=float(base), null_test_nll=float(null_test),
                    s8_eta_test_gain=float(null_test - test_prof["nll"]),
                    s8_eta_test_nll=float(test_prof["nll"]),
                    corrupted_archived_test_gain=float(row["profiled_s8_scale"]["s8_eta_test_gain"]),
                    corrupted_archived_test_null=float(old_test_null)))


def build(output: Path) -> dict:
    cases = {}
    for case in CASES:
        cases[case] = fixed_backbone(case)
        print("fixed", case,
              {k: {l: r["eta"] for l, r in v["roots"].items()}
               for k, v in cases[case]["fixed_backbone"].items()}, flush=True)
    # Unscaled ell=15 km profile, evaluated on a coarse but monotone eta grid.
    unscaled = {}
    for case in CASES:
        unscaled[case] = profile_curve(case, UnscaledGModel, 15.0, 5.0, power=12)
        print("unscaled", case, unscaled[case]["eta95_upper"]["eta"], flush=True)
    scaled_profile = {}
    for case in CASES:
        scaled_profile[case] = profile_curve(case, E.RF.Model, 15.0, 5.0, power=12)
        print("scaled-profile", case, scaled_profile[case]["eta95_upper"]["eta"], flush=True)
    for case in CASES:
        payload_case = cases[case]['profiled_s8_scale']
        payload_case['coarse_pchip_upper'] = payload_case['eta95_upper']
        payload_case['coarse_pchip_one_sided'] = payload_case['eta95_upper_one_sided']
        payload_case['eta95_upper'] = scaled_profile[case]['eta95_upper']
        payload_case['eta95_upper_one_sided'] = scaled_profile[case]['eta95_upper_one_sided']
    payload = dict(
        schema="forensic_california_eta_profiles_v1", passed=True,
        source="experiments/methodological_audit/forensic_eta_profiles_20261114.py",
        thresholds=dict(two_sided_95=-1.9207, one_sided_95=-1.3528,
                        note="The -1.9207 cutoff is the two-sided 95% / one-sided 97.5% "
                             "descriptive likelihood-drop cutoff; -1.3528 is the one-sided 95% cutoff."),
        scale_pairs=[dict(ell_km=e, psi_days=p) for e, p in SCALE_PAIRS],
        fine_grid=list(FINE_GRID),
        ridgecrest_ell_km=float(15.0 * 10 ** (0.5 * (7.1 - 4.0))),
        cases=cases, unscaled_ell15_psi5=unscaled,
        scaled_ell15_psi5_profile=scaled_profile,
        correction=dict(
            interpolate_bound_error=("The archived linear secant between eta=0 and eta=0.01 "
                                     "underestimated every upper bound because Delta ell(0.01) is "
                                     "hundreds to thousands of nats negative."),
            profile_baseline=("The archived profiled curve used null_train_nll at psi_hat(eta) "
                              "instead of the uninhibited MLE psi_hat(0); the corrected curve "
                              "subtracts each stored train_nll from the fixed x0 baseline."),
            heldout_baseline=("The archived held-out contrast subtracted a null evaluated at the "
                              "eta-profiled parameters; the corrected contrast uses x0 = psi_hat(0).")))
    write(output / "eta_profiles.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/forensic_remediation_20261114")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        payload = build(args.output)
    print(json.dumps({"ridgecrest_ell_km": payload["ridgecrest_ell_km"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
