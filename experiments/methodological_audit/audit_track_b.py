"""Independent computational audit of the Track B control authorities.

Recomputes saved objective values, held-out scores, factorial closure, profile
points and block standard errors from the frozen inputs.  It writes a separate
audit record and never mutates a primary summary.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "validation/live_results/track_b_controls_20261112"
ABLATION = BASE / "epplus_ablation"
NZ = BASE / "nz_trend_controls"
PROFILES = BASE / "profiles_and_power"
AUTHORITY = ROOT / "validation/authorities/e7fbc4fa4fae3da4_observed.json"
CATALOGUE = ROOT / "reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv"
NZ_UNCERTAINTY = ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json"
CA_UNCERTAINTY = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_uncertainty/summary.json"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AB = load(ROOT / "experiments/etas_inhibition_benchmark/ablation_and_sigma0.py", "track_b_audit_ablation")
EP = load(ROOT / "experiments/methodological_audit/eta_profiles_and_power.py", "track_b_audit_profiles")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(checks, label, observed, expected, tolerance=1e-8):
    difference = abs(float(observed) - float(expected))
    checks.append(dict(check=label, observed=float(observed), expected=float(expected),
                       absolute_difference=float(difference), passed=bool(difference <= tolerance)))
    return difference <= tolerance


# ---------------------------------------------------------------------------
# B1
# ---------------------------------------------------------------------------

def audit_ablation(checks):
    data = read(ABLATION / "ablation.json")
    baseline = read(AB.ACCEPTED / "baseline_comparison.json")
    for fold in data["fold_results"]:
        case = fold["case"]
        weights = AB.accepted_weights(case)
        ep = next(r for r in baseline["rows"] if r["case"] == case)
        check(checks, f"{case}/A0/test", fold["rows"]["A0"]["test_joint_score"], ep["original_EP_joint_score"], 1e-12)
        for arm_id, row in fold["rows"].items():
            if arm_id == "A0":
                continue
            w = weights if row["weighted"] else None
            model, _ = AB.make_model(case, row["normalization"], w)
            x = np.asarray(row["parameters"], dtype=float)
            value = float(model.objective(x, False)[0])
            check(checks, f"{case}/{arm_id}/training_nll", value, row["training_nll"], 1e-7)
            score = AB.test_score(case, x, row["normalization"], w)
            check(checks, f"{case}/{arm_id}/test_joint", score["test_joint_score"], row["test_joint_score"], 1e-9)
            check(checks, f"{case}/{arm_id}/gain", score["gain_over_EP"], row["gain_over_EP"], 1e-9)
    # Finite-difference check of the rectangle gradient at a generic interior
    # state (large derivatives, no near-zero optimum coordinates).
    fold = data["fold_results"][0]
    case = fold["case"]
    row = fold["rows"]["A1"]
    model, _ = AB.make_model(case, "rect", None)
    x = np.asarray(row["parameters"], dtype=float)
    x[5], x[6], x[7] = math.log(4.0), 0.7, 1.8
    _, analytic = model.objective(x, False)
    max_relative = 0.0
    for index in range(8):
        def central(step):
            xp, xm = x.copy(), x.copy()
            xp[index] += step
            xm[index] -= step
            return (model.objective(xp, False)[0] - model.objective(xm, False)[0]) / (2 * step)
        numeric = (4 * central(5e-6) - central(1e-5)) / 3
        scale = max(1.0, abs(numeric), abs(analytic[index]))
        max_relative = max(max_relative, abs(numeric - analytic[index]) / scale)
    checks.append(dict(check="rect_gradient_max_relative_error", observed=float(max_relative),
                       expected=1e-7, absolute_difference=float(max_relative), passed=bool(max_relative < 1e-7)))
    # At the fitted state many coordinates are near zero; report an absolute
    # central-difference residual rather than a ratio with a vanishing scale.
    x_fit = np.asarray(row["parameters"], dtype=float)
    _, analytic_fit = model.objective(x_fit, False)
    max_absolute = 0.0
    for index in range(8):
        step = 1e-4
        xp, xm = x_fit.copy(), x_fit.copy()
        xp[index] += step
        xm[index] -= step
        numeric = (model.objective(xp, False)[0] - model.objective(xm, False)[0]) / (2 * step)
        max_absolute = max(max_absolute, abs(numeric - analytic_fit[index]))
    checks.append(dict(check="rect_gradient_fitted_state_max_absolute", observed=float(max_absolute),
                       expected=1e-2, absolute_difference=float(max_absolute), passed=bool(max_absolute < 1e-2)))
    # Factorial arithmetic from the saved arm totals.
    totals = {k: dict(total_gain=v["total_gain"]) for k, v in data["arms"].items()}
    recomputed = AB.factorial(totals)
    check(checks, "factorial/closure_residual", recomputed["closure_residual"], 0.0, 1e-12)
    check(checks, "factorial/closure_total", recomputed["factorial_closure"], recomputed["closure_A8_minus_A0"], 1e-12)


def audit_relax(checks):
    for name, path, frozen in [
        ("redeclustered", ABLATION / "sigma0_relaxation.json", False),
        ("frozen", ABLATION / "sigma0_relaxation_frozen.json", True),
    ]:
        if not path.exists():
            checks.append(dict(check=f"{name}/present", observed=False, expected=True, passed=False))
            continue
        data = read(path)
        for row in data["rows"]:
            case = row["case"]
            weights = AB.accepted_weights(case) if frozen else np.asarray(row["background_weights"], dtype=float)
            model, _ = AB.make_model(case, row["normalization"], weights)
            x = np.asarray(row["parameters"], dtype=float)
            value = float(model.objective(x, False)[0])
            check(checks, f"{name}/{case}/{row['normalization']}/training_nll", value, row["training_nll"], 1e-7)
            score = AB.test_score(case, x, row["normalization"], weights)
            check(checks, f"{name}/{case}/{row['normalization']}/test_joint", score["test_joint_score"], row["test_joint_score"], 1e-9)
            check(checks, f"{name}/{case}/{row['normalization']}/sigma0", float(np.exp(x[5])), row["sigma0"], 1e-12)


def audit_profile(checks):
    data = read(ABLATION / "sigma0_profile.json")
    for row in data["rows"]:
        case = row["case"]
        weights = AB.accepted_weights(case)
        model, _ = AB.make_model(case, row["normalization"], weights)
        for point in row["curve"]:
            x = np.asarray(point["parameters"], dtype=float)
            value = float(model.objective(x, False)[0])
            check(checks, f"profile/{case}/{row['normalization']}/{point['sigma0_km']}/nll", value, point["training_nll"], 1e-7)
        score = AB.test_score(case, np.asarray(row["interior_parameters"], dtype=float), row["normalization"], weights)
        check(checks, f"profile/{case}/{row['normalization']}/interior_test", score["test_joint_score"], row["interior_test"]["test_joint_score"], 1e-9)


# ---------------------------------------------------------------------------
# B2
# ---------------------------------------------------------------------------

def audit_nz(checks):
    A = load(ROOT / "engine/iteration_27/code/adequacy.py", "track_b_audit_adequacy")
    import pandas as pd
    rows = pd.read_csv(CATALOGUE)
    times = rows.t_days.to_numpy(dtype=float)
    excess = rows.excess.to_numpy(dtype=float)
    authority = read(AUTHORITY)
    data = read(NZ / "summary.json")
    for name in ("fold_50", "fold_65", "fold_80"):
        fold = authority["folds"][name]
        stored = data["folds"][name]
        start, end = float(fold["train_end"]), float(fold["test_end"])
        T0, beta = 24394.0, float(fold["fit"]["beta_train"])
        for family in ("ml_trigger", "ml_shared"):
            record = dict(fold["fit"]["best"][family])
            scored = A.evaluate_window(times, excess, record, start, end, T0, beta, 32)
            check(checks, f"nz/{name}/{family}/free_d_joint", scored["full_marked_loglik"], stored["archived"][family]["test"]["full_marked_loglik"], 1e-10)
        for control in ("fixed_null_trend", "zero_trend"):
            stored_control = stored["controls"][control]
            trigger = fold["fit"]["best"]["ml_shared"]["trigger"]
            stress = fold["fit"]["best"]["ml_shared"]["stress"]
            ratio = fold["fit"]["best"]["ml_shared"]["ratio"]
            null_record = dict(pars=stored_control["null"]["training"]["parameters"], trigger=trigger,
                               ratio=ratio, stress=None)
            alt_record = dict(pars=stored_control["inhibited"]["training"]["parameters"], trigger=trigger,
                              ratio=ratio, stress=stress)
            null_test = A.evaluate_window(times, excess, null_record, start, end, T0, beta, 32)
            alt_test = A.evaluate_window(times, excess, alt_record, start, end, T0, beta, 32)
            check(checks, f"nz/{name}/{control}/null_joint", null_test["full_marked_loglik"], stored_control["null"]["test"]["full_marked_loglik"], 1e-10)
            check(checks, f"nz/{name}/{control}/inhibited_joint", alt_test["full_marked_loglik"], stored_control["inhibited"]["test"]["full_marked_loglik"], 1e-10)
            check(checks, f"nz/{name}/{control}/delta_joint", alt_test["full_marked_loglik"] - null_test["full_marked_loglik"], stored_control["heldout"]["delta_joint"], 1e-10)
    fold1 = data["folds"]["fold_50"]["attribution"]
    check(checks, "nz/fold1/zero_fraction", fold1["trend_extrapolation_fraction_zero"], 0.4851510622921639, 1e-12)
    check(checks, "nz/fold1/fixed_fraction", fold1["trend_extrapolation_fraction_fixed_null"], 0.7241932290310844, 1e-12)


# ---------------------------------------------------------------------------
# B3
# ---------------------------------------------------------------------------

def audit_s8(checks):
    with tempfile.TemporaryDirectory() as tmp:
        result = EP.s8_oracle(Path(tmp))
    stored = read(PROFILES / "s8_oracle.json")
    check(checks, "s8/oracle_joint_mean", result["oracle_gain_vs_joint_null"]["mean"], stored["oracle_gain_vs_joint_null"]["mean"], 1e-9)
    check(checks, "s8/oracle_intercept_mean", result["oracle_gain_vs_intercept"]["mean"], stored["oracle_gain_vs_intercept"]["mean"], 1e-9)
    check(checks, "s8/estimation_loss_mean", result["estimation_loss"]["mean"], stored["estimation_loss"]["mean"], 1e-9)
    check(checks, "s8/max_quadrature", result["max_true_quadrature_delta"], stored["max_true_quadrature_delta"], 1e-12)


def audit_profiles(checks):
    data = read(PROFILES / "california_eta_profiles.json")
    for row in data["rows"]:
        case = row["case"]
        train, meta, test, test_meta, _ = EP.RF.inputs(case)
        weights = np.asarray(EP.accepted(case)["background_weights"], dtype=float)
        region = EP.RF.Region(train["rectangles"])
        background = EP.RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
        train_model = EP.RF.Model(train, meta, background)
        x0 = np.asarray(EP.accepted(case)["null"]["selected"]["parameters"], dtype=float)
        train_model.node_setup(x0, power=14, seed=20261111)
        test_model = EP.RF.Model(test, test_meta, background)
        test_model.node_setup(x0, power=16, seed=20261120)
        for key, fixed in row["fixed_backbone"].items():
            for eta in (0.0, 0.4, 1.5):
                point = next(p for p in fixed["curve"] if abs(p["eta"] - eta) < 1e-12)
                gain, _ = EP.loglik_gain(train_model, x0, eta, fixed["ell_km"], fixed["psi_days"])
                check(checks, f"profile/{case}/{key}/eta{eta}/train_gain", gain, point["train_loglik_gain"], 1e-7)
            test_gain, _ = EP.loglik_gain(test_model, x0, 0.4, fixed["ell_km"], fixed["psi_days"])
            check(checks, f"profile/{case}/{key}/test_gain", test_gain, fixed["s8_eta_test_gain"], 1e-7)
        s8 = row["profiled_s8_scale"]
        for eta in (0.0, 0.4, 1.5):
            point = next(p for p in s8["curve"] if abs(p["eta"] - eta) < 1e-12)
            x = np.asarray(point["parameters"], dtype=float)
            value = float(train_model.objective(x, True)[0])
            check(checks, f"profile/{case}/profiled/eta{eta}/nll", value, point["train_nll"], 1e-7)


def audit_mde(checks):
    data = read(PROFILES / "mde.json")
    nz = read(NZ_UNCERTAINTY)
    ca = read(CA_UNCERTAINTY)
    for region in data["rows"]:
        if region["region"].startswith("NZ"):
            for days in ("90", "180", "365"):
                rows = nz["rows"] if days == "90" else nz["sensitivity"][days]["rows"]
                groups = []
                for case in ("fold_50", "fold_65", "fold_80"):
                    row = next(r for r in rows if r["case"] == case and r["contrast"] == "NZ_shared_minus_ML")
                    scores = np.asarray(row["block_scores"])
                    groups.append(math.sqrt(len(scores)) * scores.std(ddof=1))
                se = math.sqrt(sum(value ** 2 for value in groups))
                check(checks, f"mde/NZ/{days}/se", se, region["block_days"][days]["se_total_nats"], 1e-10)
        elif region["region"].startswith("CA"):
            for days in ("90", "180", "365"):
                rows = ca["rows_by_block_days"][days]
                groups = []
                for case in ("california_fold_0", "california_fold_1", "california_fold_2"):
                    row = next(r for r in rows if r["case"] == case)
                    scores = np.asarray(row["block_scores"])
                    groups.append(math.sqrt(len(scores)) * scores.std(ddof=1))
                se = math.sqrt(sum(value ** 2 for value in groups))
                check(checks, f"mde/CA/{days}/se", se, region["block_days"][days]["se_total_nats"], 1e-10)


def audit_sealed(checks):
    snapshot = read(ROOT / "validation/track_b_prechange_snapshot_20261112.json")
    for path, expected in snapshot["sealed_json_sha256"].items():
        actual = sha(ROOT / path)
        checks.append(dict(check="sealed/" + path, observed=actual, expected=expected,
                           absolute_difference=0.0 if actual == expected else 1.0,
                           passed=bool(actual == expected)))
    checks.append(dict(check="sealed/prior_roster_unchanged",
                       observed=len(snapshot["changed_against_prior"]),
                       expected=0, absolute_difference=float(len(snapshot["changed_against_prior"])),
                       passed=bool(not snapshot["changed_against_prior"])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, default=BASE / "independent_track_b_audit.json")
    args = parser.parse_args()
    checks = []
    sections = [
        ("ablation", audit_ablation),
        ("sigma0_relaxation", audit_relax),
        ("sigma0_profile", audit_profile),
        ("nz_trend_controls", audit_nz),
        ("s8_oracle", audit_s8),
        ("california_eta_profiles", audit_profiles),
        ("minimum_detectable_effects", audit_mde),
        ("sealed_custody", audit_sealed),
    ]
    for name, function in sections:
        beginning = len(checks)
        try:
            function(checks)
        except Exception as error:  # record a section failure without hiding prior checks
            checks.append(dict(check=name + "/exception", observed=repr(error), expected="no exception", passed=False))
        print(name, len(checks) - beginning, "checks", flush=True)
    result = dict(schema="track_b_independent_computational_audit_v1",
                  passed=all(c["passed"] for c in checks), checks=checks,
                  check_count=len(checks), failed=[c for c in checks if not c["passed"]],
                  source_sha256=sha(Path(__file__)),
                  sealed_authorities_mutated=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=result["passed"], checks=result["check_count"], failed=len(result["failed"])), indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
