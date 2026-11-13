"""Track B New Zealand Fold-1 trend/depletion controls.

Reconstructs the archived frozen fits, then refits with the linear trend fixed
at zero or at the uninhibited null value.  A clamped-clock counterfactual
removes positive test-window extrapolation without changing any frozen fit.
No sealed authority is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv"
AUTHORITY = ROOT / "validation/authorities/e7fbc4fa4fae3da4_observed.json"
ADEQUACY = ROOT / "engine/iteration_27/code/adequacy.py"
AUTONOMOUS = ROOT / "validation/live_results/autonomous_20261105/result.json"
FOLDS = ("fold_50", "fold_65", "fold_80")
PINS = {
    "reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv": "feacccb7581d1c4c33f88874cd6b198c41639da6930a7fc35e46f910a594fb3e",
    "validation/authorities/e7fbc4fa4fae3da4_observed.json": "e7fbc4fa4fae3da4f8880695064798a8ebfc9342ab09303073f7afd7334439d8",
    "engine/iteration_27/code/adequacy.py": "9662c90f9ff7e120fe26c1dfc0bd969071f16774feec686b9e97731337e0ff90",
    "engine/iteration_5/code/kernels.py": "3561ef3471adf349caebebc6c2ca12881f2a3d9c7c7415d15453b5be20b978ae",
}
VALIDATION_BOUNDS = dict(a=(-12.0, 0.0), n=(0.0, 0.98), eta=(0.0, 3.0))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_adequacy():
    for relative, pin in PINS.items():
        if sha(ROOT / relative) != pin:
            raise ValueError("pinned source changed: " + relative)
    spec = importlib.util.spec_from_file_location("_track_b_adequacy", ADEQUACY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


A = load_adequacy()


def history_for(fold_name, times, excess, T0, train_end, order=32):
    fold = json.loads(AUTHORITY.read_text(encoding="utf-8"))["folds"][fold_name]
    beta = float(fold["fit"]["beta_train"])
    return A.PredictiveHistory(times, excess, beta, 0.0, train_end, T0, order), fold


def fit_fixed_trend(history, trigger, ratio, stress, d_fixed, start, eta_mode):
    names = ["a", "n", "eta"] if eta_mode else ["a", "n"]
    indices = [0, 2, 3] if eta_mode else [0, 2]
    lo = np.asarray([VALIDATION_BOUNDS[n][0] for n in names])
    hi = np.asarray([VALIDATION_BOUNDS[n][1] for n in names])

    def expand(v):
        if eta_mode:
            return [float(v[0]), float(d_fixed), float(v[1]), float(v[2])]
        return [float(v[0]), float(d_fixed), float(v[1])]

    x0 = np.asarray([start[i] for i in indices], dtype=float)
    x0 = np.clip(x0, lo, hi)

    def target(v):
        pars = expand(v)
        value, gradient = history.objective(pars, trigger, ratio, stress, True)
        return value, np.asarray([gradient[i] for i in indices])

    opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-6))
    return dict(success=bool(opt.success), message=str(opt.message), nll=float(opt.fun),
                parameters=expand(opt.x), nit=int(opt.nit), nfev=int(opt.nfev))


def component_record(parameters, trigger, ratio, stress):
    return dict(pars=[float(v) for v in parameters],
                trigger=trigger, ratio=float(ratio), stress=stress)


def window_score(times, excess, record, start, end, T0, beta, order=32):
    return A.evaluate_window(times, excess, record, start, end, T0, beta, order)


def clamped_score(times, excess, record, start, end, T0, beta, order=32):
    """Test score with the affine clock fixed at its training-window endpoint."""
    history = A.PredictiveHistory(times, excess, beta, start, end, T0, order)
    trigger = A.KernelSpec(**record["trigger"]) if record.get("trigger") else None
    stress = A.KernelSpec(**record["stress"]) if record.get("stress") else None
    pars = record["pars"]
    a, d, n = pars[:3]
    eta = float(pars[3]) if stress is not None else 0.0
    ge, gq = history.stress(stress) if stress is not None else (np.zeros(len(history.events)), np.zeros(len(history.tq)))
    he, hi = history.trigger(trigger, record["ratio"]) if trigger is not None else (np.zeros(len(history.events)), np.zeros(len(history.edges) - 1))
    x_clamp = 2.0 * start / T0 - 1.0
    logb = a + d * x_clamp - eta * ge
    logh = np.full_like(he, -np.inf)
    np.log(he, out=logh, where=he > 0)
    loglam = np.logaddexp(logb, logh + np.log(n) if n > 0 else np.full_like(he, -np.inf))
    if stress is None:
        background = math.exp(a + d * x_clamp) * (end - start)
    else:
        bq = np.exp(a + d * x_clamp - eta * gq)
        background = float(history.wq @ bq)
    pieces = background + (n * hi.sum() if trigger is not None else 0.0)
    mark = float(len(history.events) * math.log(beta) - beta * history.excess[history.mask].sum())
    ground = float(loglam.sum() - pieces)
    return dict(ground=ground, mark=mark, joint=ground + mark,
                integrated_intensity=float(pieces), n_events=len(history.events),
                x_clamp=float(x_clamp))


def fit_control(fold_name, times, excess, fold, d_fixed, label):
    train_end = float(fold["train_end"])
    test_end = float(fold["test_end"])
    T0 = 24394.0
    ratio = float(fold["fit"]["best"]["ml_shared"]["ratio"])
    trigger = fold["fit"]["best"]["ml_shared"]["trigger"]
    stress = fold["fit"]["best"]["ml_shared"]["stress"]
    beta = float(fold["fit"]["beta_train"])
    null_start = np.asarray(fold["fit"]["best"]["ml_trigger"]["pars"], dtype=float)
    alt_start = np.asarray(fold["fit"]["best"]["ml_shared"]["pars"], dtype=float)
    history = A.PredictiveHistory(times, excess, beta, 0.0, train_end, T0, 32)
    null = fit_fixed_trend(history, A.KernelSpec(**trigger), ratio, None, d_fixed, null_start, False)
    inhibited = fit_fixed_trend(history, A.KernelSpec(**trigger), ratio, A.KernelSpec(**stress),
                                d_fixed, alt_start, True)
    # One recovery start from the zero-inhibition fit if the first inhibited fit fails.
    if not inhibited["success"]:
        recovery = [null["parameters"][0], d_fixed, null["parameters"][2], 1.0]
        inhibited = fit_fixed_trend(history, A.KernelSpec(**trigger), ratio, A.KernelSpec(**stress),
                                    d_fixed, recovery, True)
    null_record = component_record(null["parameters"], trigger, ratio, None)
    inhibited_record = component_record(inhibited["parameters"], trigger, ratio, stress)
    null_test = window_score(times, excess, null_record, train_end, test_end, T0, beta)
    inhibited_test = window_score(times, excess, inhibited_record, train_end, test_end, T0, beta)
    delta_point = float(inhibited_test["ground_loglik"] - null_test["ground_loglik"])
    delta_exposure = float(inhibited_test["integrated_intensity"] - null_test["integrated_intensity"])
    return dict(label=label, d_fixed=float(d_fixed), ratio=ratio,
                null=dict(training=null, test=null_test),
                inhibited=dict(training=inhibited, test=inhibited_test),
                heldout=dict(delta_point=delta_point,
                             delta_exposure=delta_exposure,
                             delta_Q=float(delta_point + delta_exposure),
                             delta_C=float(-delta_exposure),
                             delta_joint=float(inhibited_test["full_marked_loglik"] - null_test["full_marked_loglik"]),
                             training_delta_loglik=float(null["nll"] - inhibited["nll"])))


def archived_fold(fold_name, times, excess, fold):
    train_end = float(fold["train_end"])
    test_end = float(fold["test_end"])
    T0 = 24394.0
    beta = float(fold["fit"]["beta_train"])
    out = {}
    for family in ("ml_trigger", "ml_shared"):
        best = fold["fit"]["best"][family]
        record = dict(best)
        scored = A.evaluate_window(times, excess, record, train_end, test_end, T0, beta, 32)
        archived = fold["test_controls"][family]["order32"]
        error = abs(scored["full_marked_loglik"] - archived["full_marked_loglik"])
        out[family] = dict(record=dict(pars=best["pars"], trigger=best["trigger"],
                                       stress=best["stress"], ratio=best["ratio"]),
                           test=scored, archived_error=float(error))
    delta_point = out["ml_shared"]["test"]["ground_loglik"] - out["ml_trigger"]["test"]["ground_loglik"]
    delta_exposure = out["ml_shared"]["test"]["integrated_intensity"] - out["ml_trigger"]["test"]["integrated_intensity"]
    out["heldout"] = dict(delta_point=delta_point, delta_exposure=delta_exposure,
                          delta_Q=float(delta_point + delta_exposure), delta_C=float(-delta_exposure),
                          delta_joint=out["ml_shared"]["test"]["full_marked_loglik"] - out["ml_trigger"]["test"]["full_marked_loglik"],
                          training_delta_loglik=float(fold["fit"]["best"]["ml_trigger"]["nll"] - fold["fit"]["best"]["ml_shared"]["nll"]))
    return out


def autonomous_summary():
    data = json.loads(AUTONOMOUS.read_text(encoding="utf-8"))
    rows = []
    for key in ("fold_50", "fold_65", "fold_80"):
        if key in data:
            rows.append((key, data[key]))
    return data


def calculate():
    rows = pd.read_csv(CATALOGUE)
    times = rows.t_days.to_numpy(dtype=float)
    excess = rows.excess.to_numpy(dtype=float)
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    if len(times) != 913:
        raise ValueError("unexpected catalogue size")
    folds = {}
    for name in FOLDS:
        fold = authority["folds"][name]
        archived = archived_fold(name, times, excess, fold)
        d_null = float(fold["fit"]["best"]["ml_trigger"]["pars"][1])
        controls = {}
        controls["fixed_null_trend"] = fit_control(name, times, excess, fold, d_null, "Fixed_Null_Trend_d")
        controls["zero_trend"] = fit_control(name, times, excess, fold, 0.0, "Matched_Zero_Trend_d0")
        clamped = {}
        for family in ("ml_trigger", "ml_shared"):
            record = archived[family]["record"]
            clamped[family] = clamped_score(times, excess, record, float(fold["train_end"]),
                                            float(fold["test_end"]), 24394.0,
                                            float(fold["fit"]["beta_train"]), 32)
        clamped["delta_joint"] = clamped["ml_shared"]["joint"] - clamped["ml_trigger"]["joint"]
        folds[name] = dict(train_end=float(fold["train_end"]), test_end=float(fold["test_end"]),
                           n_train=int(fold["fit"]["n_train"]), d_null=d_null,
                           archived=archived, controls=controls, clamped=clamped)
        print(name, "archived", archived["heldout"]["delta_joint"],
              "zero", controls["zero_trend"]["heldout"]["delta_joint"],
              "fixed-null", controls["fixed_null_trend"]["heldout"]["delta_joint"],
              "clamped", clamped["delta_joint"], flush=True)
    # Deficit fractions use the archived free-d loss as denominator.
    for name in FOLDS:
        archived_loss = -folds[name]["archived"]["heldout"]["delta_joint"]
        zero_loss = -folds[name]["controls"]["zero_trend"]["heldout"]["delta_joint"]
        fixed_loss = -folds[name]["controls"]["fixed_null_trend"]["heldout"]["delta_joint"]
        clamped_loss = -folds[name]["clamped"]["delta_joint"]
        folds[name]["attribution"] = dict(
            archived_loss=float(archived_loss),
            zero_trend_loss=float(zero_loss),
            fixed_null_trend_loss=float(fixed_loss),
            clamped_loss=float(clamped_loss),
            trend_extrapolation_fraction_zero=float((archived_loss - zero_loss) / archived_loss) if archived_loss else None,
            trend_extrapolation_fraction_fixed_null=float((archived_loss - fixed_loss) / archived_loss) if archived_loss else None,
            clamped_removed_fraction=float((archived_loss - clamped_loss) / archived_loss) if archived_loss else None,
            detrended_residual_fraction_zero=float(zero_loss / archived_loss) if archived_loss else None)
    total_archived = sum(folds[n]["archived"]["heldout"]["delta_joint"] for n in FOLDS)
    total_zero = sum(folds[n]["controls"]["zero_trend"]["heldout"]["delta_joint"] for n in FOLDS)
    total_fixed = sum(folds[n]["controls"]["fixed_null_trend"]["heldout"]["delta_joint"] for n in FOLDS)
    total_clamped = sum(folds[n]["clamped"]["delta_joint"] for n in FOLDS)
    summary = dict(schema="track_b_nz_trend_controls_v1", passed=True,
                   source="experiments/methodological_audit/nz_trend_controls.py",
                   authority_sha256=sha(AUTHORITY), catalogue_sha256=sha(CATALOGUE),
                   adequacy_source_sha256=sha(ADEQUACY),
                   source_pins=PINS, catalogue_events=int(len(times)),
                   folds=folds,
                   totals=dict(archived_delta_joint=float(total_archived),
                               zero_trend_delta_joint=float(total_zero),
                               fixed_null_trend_delta_joint=float(total_fixed),
                               clamped_delta_joint=float(total_clamped),
                               archived_loss=float(-total_archived),
                               zero_trend_loss=float(-total_zero),
                               fixed_null_trend_loss=float(-total_fixed),
                               pooled_archived_fold1_loss=float(-folds["fold_50"]["archived"]["heldout"]["delta_joint"])),
                   controls=dict(
                       Free_d="Archived ml_trigger and ml_shared fits, evaluated at order 32.",
                       Fixed_Null_Trend_d="Fit (a,n,eta) with d frozen at the archived uninhibited ml_trigger trend.",
                       Zero_Trend_d0="Fit (a,n) and (a,n,eta) with d=0 and the archived productivity ratio and kernels.",
                       Clamped="Archived free-d fits evaluated with x(t)=2t/T0-1 fixed at its training endpoint for all held-out times."),
                   autonomous=json.loads(AUTONOMOUS.read_text(encoding="utf-8")))
    write(ROOT / "validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/track_b_controls_20261112/nz_trend_controls")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        summary = calculate()
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / "summary.json", summary)
    print(json.dumps(summary["totals"], indent=2))


if __name__ == "__main__":
    main()
