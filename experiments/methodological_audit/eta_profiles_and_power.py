"""Track B S8 oracle ceiling, California eta profiles and minimum detectable effects.

All computations reuse frozen authorities and frozen model code.  The S8 oracle
evaluates the true generating law and three uninhibited comparators; California
profiles are training-only slices of the accepted EP+ fit; MDEs are derived from
sealed block-score authorities plus the three reported Japan fold totals.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
S8 = ROOT / "validation/live_results/s8_moderate_complete_20261111"
S8_DATA = ROOT / "reproduction/synthetic/s8_moderate_total"
S8_SOURCE = S8 / "source/s8_moderate.py"
NZ_UNCERTAINTY = ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json"
CA_UNCERTAINTY = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_uncertainty/summary.json"
FROZEN = ROOT / "experiments/etas_inhibition_benchmark/run_frozen_20261111.py"
ACCEPTED = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112"
ETA_GRID = (0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40, 0.80, 1.50, 2.50, 4.00)
SCALE_PAIRS = ((10.0, 2.0), (15.0, 5.0), (20.0, 5.0), (50.0, 30.0))
JAPAN_FOLD_TOTALS = (-74.7591, -59.1334, -87.3190)
JAPAN_TEST_EVENTS = 1277
TEST_EVENTS = {"NZ_shared_minus_ML": 612, "CA_EPplus_minus_original_EP": 315}


def load_frozen(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RF = load_frozen(FROZEN, "track_b_frozen_profiles")


def sha(path):
    return __import__("hashlib").sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def stats(values):
    values = np.asarray(values, dtype=float)
    return dict(N=int(len(values)), mean=float(values.mean()), median=float(np.median(values)),
                sample_sd=float(values.std(ddof=1)), mcse=float(values.std(ddof=1) / np.sqrt(len(values))),
                wins=int(np.sum(values > 0)), values=[float(v) for v in values])


# ---------------------------------------------------------------------------
# S8 oracle ceiling
# ---------------------------------------------------------------------------

def s8_modules():
    from experiments.s04b_joint_nuisance import model
    from experiments.s04b_completion.recover import native_library
    archived = model.archived()
    native = model.Native(native_library())
    return model, archived, native


def s8_oracle(output):
    from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler
    model, modules, native = s8_modules()
    run = load_frozen(S8_SOURCE, "track_b_s8_runner")
    receipts = json.loads((S8_DATA / "receipts.json").read_text(encoding="utf-8"))
    seeds = sorted(int(p.name.split(".")[0]) for p in S8_DATA.glob("*.npz"))
    true_theta = np.array([math.log(.25), .2, .35, math.log(.05), 1.3, .4, math.log(15.0), math.log(5.0)])
    rows = []
    for seed in seeds:
        result = json.loads((S8 / str(seed) / "result.json").read_text(encoding="utf-8"))
        record = next(r for r in receipts if r["seed"] == seed)
        npz = np.load(S8_DATA / f"{seed}.npz")
        history = npz["rows"]
        base_train = model.phase_from_rows(history, record["metadata"], 30.0, 395.0, modules, native)
        base_test = model.phase_from_rows(history, record["metadata"], 395.0, 760.0, modules, native)
        with OrderedChunkScheduler() as scheduler:
            train = run.TensorPhase(base_train.a, base_train.m, modules, native, math.inf, scheduler=scheduler)
            test = run.TensorPhase(base_test.a, base_test.m, modules, native, math.inf, scheduler=scheduler)
            fixed_null = test.evaluate(true_theta * np.array([1, 1, 1, 1, 1, 0, 1, 1]), "null", 16)[0]
            true16 = test.evaluate(true_theta, "LIplus_inclusive", 16)[0]
            true32 = test.evaluate(true_theta, "LIplus_inclusive", 32)[0]
            def intercept_nll(a):
                theta = true_theta.copy()
                theta[0] = float(a)
                theta[5] = 0.0
                return float(train.evaluate(theta, "null", 16)[0]["nll"])
            opt = minimize_scalar(intercept_nll, bounds=(-12.0, 0.0), method="bounded",
                                  options=dict(xatol=1e-10, maxiter=200))
            refit_theta = true_theta.copy()
            refit_theta[0] = float(opt.x)
            refit_theta[5] = 0.0
            refit_intercept = test.evaluate(refit_theta, "null", 16)[0]
        true_joint = float(true32["joint"])
        joint_null = float(result["null_test"]["joint"])
        fitted = float(result["inhibited_test"]["joint"])
        rows.append(dict(seed=seed,
                         true_generating_joint=true_joint,
                         true_order16_joint=float(true16["joint"]),
                         quadrature_delta=float(true16["joint"] - true32["joint"]),
                         fixed_true_backbone_null_joint=float(fixed_null["joint"]),
                         refitted_intercept_null_joint=float(refit_intercept["joint"]),
                         jointly_fitted_null_joint=joint_null,
                         fitted_inhibited_joint=fitted,
                         oracle_gain_vs_fixed=float(true_joint - fixed_null["joint"]),
                         oracle_gain_vs_intercept=float(true_joint - refit_intercept["joint"]),
                         oracle_gain_vs_joint_null=float(true_joint - joint_null),
                         estimation_loss=float(fitted - true_joint),
                         fitted_gain=float(result["gain"]),
                         fitted_eta=float(result["eta"]),
                         refitted_intercept_a=float(opt.x),
                         n_train=int(result["n_train"]), n_test=int(result["n_test"])))
        print("s8", seed, rows[-1]["oracle_gain_vs_joint_null"], rows[-1]["estimation_loss"], flush=True)
    summary = dict(schema="track_b_s8_oracle_ceiling_v1", passed=True,
                   source="experiments/methodological_audit/eta_profiles_and_power.py",
                   true_parameters=dict(a=math.log(.25), d=.2, n=.35, c=.05, p=1.3,
                                        eta=.4, ell_km=15.0, psi_days=5.0),
                   rows=rows,
                   oracle_gain_vs_fixed=stats([r["oracle_gain_vs_fixed"] for r in rows]),
                   oracle_gain_vs_intercept=stats([r["oracle_gain_vs_intercept"] for r in rows]),
                   oracle_gain_vs_joint_null=stats([r["oracle_gain_vs_joint_null"] for r in rows]),
                   estimation_loss=stats([r["estimation_loss"] for r in rows]),
                   fitted_gain=stats([r["fitted_gain"] for r in rows]),
                   max_true_quadrature_delta=float(max(abs(r["quadrature_delta"]) for r in rows)))
    write(output / "s8_oracle.json", summary)
    return summary


# ---------------------------------------------------------------------------
# California eta profiles
# ---------------------------------------------------------------------------

def accepted(case):
    record = json.loads((ACCEPTED / case / "result.json").read_text(encoding="utf-8"))
    return record


def eta_value(x, eta, ell, psi):
    out = np.asarray(x, dtype=float).copy()
    out[8] = eta
    out[9] = math.log(ell)
    out[10] = math.log(psi)
    return out


def loglik_gain(model, x0, eta, ell, psi):
    details = model.objective(eta_value(x0, eta, ell, psi), True, True)
    null = model.objective(x0, False, True)
    return float(null["nll"] - details["nll"]), float(details["nll"])


def profile_fold(case):
    train, meta, test, test_meta, _ = RF.inputs(case)
    weights = np.asarray(accepted(case)["background_weights"], dtype=float)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    train_model = RF.Model(train, meta, background)
    x0 = np.asarray(accepted(case)["null"]["selected"]["parameters"], dtype=float)
    train_model.node_setup(x0, power=14, seed=20261111)
    test_model = RF.Model(test, test_meta, background)
    test_model.node_setup(x0, power=16, seed=20261120)
    fixed = {}
    for ell, psi in SCALE_PAIRS:
        key = f"ell{ell:g}_psi{psi:g}"
        curve = []
        for eta in ETA_GRID:
            gain, nll = loglik_gain(train_model, x0, eta, ell, psi)
            curve.append(dict(eta=eta, train_loglik_gain=gain, train_nll=nll))
        slope_point = eta_value(x0, 1e-6, ell, psi)
        slope_nll, slope_grad = train_model.objective(slope_point, True, False)
        slope = float(-slope_grad[8])
        eta95 = interpolate_bound(curve)
        test_gain, test_nll = loglik_gain(test_model, x0, 0.4, ell, psi)
        fixed[key] = dict(ell_km=ell, psi_days=psi, curve=curve,
                          training_score_slope_at_zero=slope,
                          eta95=-1.9207, eta95_upper=eta95,
                          s8_eta_test_gain=float(test_gain), s8_eta_test_nll=float(test_nll))
    # Profiled (a,d,n) at the S8 scale pair, warm-started along the eta grid.
    ell, psi = 15.0, 5.0
    bounds = [RF.BOUNDS[0], RF.BOUNDS[1], RF.BOUNDS[2]]
    current = x0.copy()
    profiled = []
    for eta in ETA_GRID:
        start = eta_value(current, eta, ell, psi)
        indices = [0, 1, 2]
        lo = np.asarray([bounds[i][0] for i in indices])
        hi = np.asarray([bounds[i][1] for i in indices])

        def target(v):
            x = start.copy()
            x[indices] = v
            value, gradient = train_model.objective(x, True)
            return value, gradient[indices]

        x_start = np.clip(start[indices], lo, hi)
        opt = minimize(target, x_start, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                       options=dict(maxiter=800, maxls=100, ftol=1e-10, gtol=2e-5))
        x = start.copy()
        x[indices] = opt.x
        details = train_model.objective(x, True, True)
        null = train_model.objective(x, False, True)
        profiled.append(dict(eta=eta, train_nll=float(details["nll"]),
                             train_loglik_gain=float(null["nll"] - details["nll"]),
                             success=bool(opt.success), parameters=[float(v) for v in x]))
        if opt.success:
            current = x
    profiled_bound = interpolate_bound(profiled)
    s8_row = next(r for r in profiled if abs(r["eta"] - 0.4) < 1e-12)
    test_prof = test_model.objective(np.asarray(s8_row["parameters"], dtype=float), True, True)
    test_null = test_model.objective(np.asarray(s8_row["parameters"], dtype=float), False, True)
    return dict(case=case, n_train=len(train["event_time"]), n_test=len(test["event_time"]),
                fixed_backbone=fixed,
                profiled_s8_scale=dict(curve=profiled, eta95_upper=profiled_bound,
                                       s8_eta_test_gain=float(test_null["nll"] - test_prof["nll"]),
                                       s8_eta_test_nll=float(test_prof["nll"])))


def interpolate_bound(curve):
    target = -1.9207
    previous = None
    for row in curve:
        gain = row["train_loglik_gain"] if "train_loglik_gain" in row else row["train_loglik_gain"]
        eta = row["eta"]
        if gain <= target:
            if previous is None:
                return 0.0
            x0, y0 = previous
            return float(x0 + (target - y0) * (eta - x0) / (gain - y0))
        previous = (eta, gain)
    return float("inf")


def run_profiles(output, workers=3):
    from concurrent.futures import ProcessPoolExecutor, as_completed
    cases = [f"california_fold_{i}" for i in range(3)]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(profile_fold, case): case for case in cases}
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: r["case"])
    summary = dict(schema="track_b_california_eta_profiles_v1", passed=True,
                   source="experiments/methodological_audit/eta_profiles_and_power.py",
                   eta_grid=list(ETA_GRID), scale_pairs=[dict(ell_km=e, psi_days=p) for e, p in SCALE_PAIRS],
                   profile_threshold_nats=-1.9207,
                   rows=rows)
    write(output / "california_eta_profiles.json", summary)
    return summary


# ---------------------------------------------------------------------------
# Minimum detectable effects
# ---------------------------------------------------------------------------

def block_se(rows, n_test):
    scores = np.asarray(rows["block_scores"], dtype=float)
    blocks = len(scores)
    se = float(math.sqrt(blocks) * scores.std(ddof=1))
    return dict(blocks=blocks, total_nats=se, per_event_nats=se / n_test,
                ci_width_over_392=float((rows["summary"]["ci95_total"][1] - rows["summary"]["ci95_total"][0]) / 3.92))


def pooled_block_se(groups, n_test):
    variance = sum(group["blocks"] * (group["total_nats"] / math.sqrt(group["blocks"])) ** 2 for group in groups)
    se = float(math.sqrt(variance))
    return dict(blocks=int(sum(g["blocks"] for g in groups)), total_nats=se,
                per_event_nats=se / n_test)


def mde_row(name, n_test, se_by_block, source):
    out = dict(region=name, n_test=int(n_test), source=source, block_days={})
    for days, se in se_by_block.items():
        out["block_days"][str(days)] = dict(
            se_total_nats=float(se["total_nats"]), se_nats_per_event=float(se["per_event_nats"]),
            mde95_total_nats=float(1.96 * se["total_nats"]),
            mde95_nats_per_event=float(1.96 * se["per_event_nats"]),
            mde80_total_nats=float(2.80 * se["total_nats"]),
            mde80_nats_per_event=float(2.80 * se["per_event_nats"]),
            required_rate_perturbation=float(math.sqrt(2 * 1.96 * se["total_nats"] / n_test)),
            blocks=int(se.get("blocks", 0)))
    return out


def run_mde(output):
    nz = json.loads(NZ_UNCERTAINTY.read_text(encoding="utf-8"))
    ca = json.loads(CA_UNCERTAINTY.read_text(encoding="utf-8"))
    nz_groups = {}
    for days in (90, 180, 365):
        rows = nz["rows"] if days == 90 else nz["sensitivity"][str(days)]["rows"]
        groups = []
        for case in ("fold_50", "fold_65", "fold_80"):
            row = next(r for r in rows if r["case"] == case and r["contrast"] == "NZ_shared_minus_ML")
            groups.append(block_se(row, TEST_EVENTS["NZ_shared_minus_ML"] / 3))
        nz_groups[days] = pooled_block_se(groups, TEST_EVENTS["NZ_shared_minus_ML"])
    ca_groups = {}
    for days in (90, 180, 365):
        rows = ca["rows_by_block_days"][str(days)]
        groups = []
        for case in ("california_fold_0", "california_fold_1", "california_fold_2"):
            row = next(r for r in rows if r["case"] == case)
            groups.append(block_se(row, TEST_EVENTS["CA_EPplus_minus_original_EP"] / 3))
        ca_groups[days] = pooled_block_se(groups, TEST_EVENTS["CA_EPplus_minus_original_EP"])
    japan_values = np.asarray(JAPAN_FOLD_TOTALS, dtype=float)
    japan_se = float(japan_values.std(ddof=1) / math.sqrt(len(japan_values)))
    japan = {days: dict(blocks=3, total_nats=japan_se, per_event_nats=japan_se / JAPAN_TEST_EVENTS)
             for days in (90, 180, 365)}
    summary = dict(schema="track_b_minimum_detectable_effects_v1", passed=True,
                   source="experiments/methodological_audit/eta_profiles_and_power.py",
                   definition="MDE95=1.96*SE_B and MDE80=2.80*SE_B; per-event values divide by the regional test-event count.",
                   block_inference_qualification="Contiguous calendar blocks are dependent under long memory; these are descriptive multi-scale sensitivities, not calibrated frequentist guarantees.",
                   rows=[
                       mde_row("NZ_shared_minus_ML", TEST_EVENTS["NZ_shared_minus_ML"], nz_groups, "score_uncertainty_remote_v2_20261111"),
                       mde_row("CA_EPplus_minus_original_EP", TEST_EVENTS["CA_EPplus_minus_original_EP"], ca_groups, "etas_inhibition_benchmark_interior_20261112/baseline_uncertainty"),
                       mde_row("Japan_OC_minus_EP_joint", JAPAN_TEST_EVENTS, japan, "three reported JMA fold totals; between-window SE, not 90/180/365-day block bootstrap")],
                   japan_fold_totals=list(JAPAN_FOLD_TOTALS),
                   japan_note="Japan has three annual fold totals only; the same between-window SE is repeated at each block label and is not a calendar-block estimate.")
    write(output / "mde.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/track_b_controls_20261112/profiles_and_power")
    parser.add_argument("--stage", choices=("s8", "profiles", "mde", "all"), default="all")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=1):
        if args.stage in ("s8", "all"):
            result = s8_oracle(args.output)
            print(json.dumps({k: result[k] for k in ("oracle_gain_vs_fixed", "oracle_gain_vs_intercept", "oracle_gain_vs_joint_null", "estimation_loss")}, indent=2))
        if args.stage in ("profiles", "all"):
            result = run_profiles(args.output, args.workers)
            print(json.dumps([(r["case"], {k: v["eta95_upper"] for k, v in r["fixed_backbone"].items()}) for r in result["rows"]], indent=2))
        if args.stage in ("mde", "all"):
            result = run_mde(args.output)
            print(json.dumps(result["rows"], indent=2))


if __name__ == "__main__":
    main()
