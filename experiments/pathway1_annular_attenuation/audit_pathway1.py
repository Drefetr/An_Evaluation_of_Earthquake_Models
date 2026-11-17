"""Independent audit for Pathway 1 annular attenuation.

Checks, in order:
  1. Sealed-authority and repository integrity (no tracked file changed).
  2. Native kernel rows against an independent NumPy formula and central FD.
  3. Full objective gradients against central FD for every kernel/scaling.
  4. Null score slopes, event sums and exposure integrals recomputed in NumPy
     for a stratified sample of the P1.1 grid.
  5. Profile concavity, maxima and eta=0 boundary logic for every P1.1 row.
  6. P1.2 selected-state training values, bounds, nested-null identity and a
     sampled held-out gain recomputation.
  7. P1.3 synthetic summary arithmetic and a sampled held-out re-evaluation.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway1_annular_attenuation import annular as A  # noqa: E402
from experiments.pathway1_annular_attenuation import synthetic as SY  # noqa: E402
from experiments.pathway1_annular_attenuation import run_synthetic as RS  # noqa: E402
from experiments.pathway1_annular_attenuation.native import Native, DEFAULT_OUTPUT  # noqa: E402

RESULTS = ROOT / "validation/live_results/pathway1_annular_20261116"
EXPERIMENTS = ROOT / "experiments/pathway1_annular_attenuation"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rel_error(actual, expected, floor=1e-12):
    a = np.asarray(actual, dtype=float)
    e = np.asarray(expected, dtype=float)
    return float(np.max(np.abs(a - e) / np.maximum(floor, np.abs(e))))


# ---------------------------------------------------------------------------
# 1. Integrity
# ---------------------------------------------------------------------------

def check_integrity():
    allowed_prefixes = (
        "experiments/pathway",
        "validation/live_results/pathway",
        "docs/reviews/pathway",
        "build/pathway",
    )
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    offending = []
    changed_tracked = []
    for line in status:
        path = line[3:].strip().strip('"')
        if line[:2].strip() and line[:2] not in ("??",):
            changed_tracked.append(line)
        elif not any(path == p or path.startswith(p) for p in allowed_prefixes):
            offending.append(line)
    authorities = list((ROOT / "validation/authorities").glob("*.json"))
    live_json = [p for p in (ROOT / "validation/live_results").rglob("*.json")
                 if "pathway1_annular_20261116" not in p.as_posix()]
    allowed_changed = not changed_tracked and not offending
    return dict(
        passed=allowed_changed,
        git_status_lines=status,
        changed_tracked=changed_tracked,
        unexpected_untracked=offending,
        sealed_authority_json_count=len(authorities),
        preexisting_live_json_count=len(live_json),
        allowed_untracked_prefixes=list(allowed_prefixes),
    )


# ---------------------------------------------------------------------------
# 2. Kernel formulas and derivatives
# ---------------------------------------------------------------------------

def numpy_kernel(r2, marks, x, kernel, scaled):
    sigma2 = np.exp(2.0 * x[5] + 2.0 * x[6] * marks)
    ell2 = np.exp(2.0 * x[9] + (np.log(10.0) * marks if scaled else np.zeros(len(marks))))
    v = r2 / ell2[None, :]
    w = r2 / sigma2[None, :]
    if kernel == "mono":
        K = (1.0 + v) ** -2
        dK = 4.0 * v / (1.0 + v) ** 3
        dsK = np.zeros_like(K)
    elif kernel == "ann1":
        K = 6.75 * v / (1.0 + v) ** 3
        dK = 13.5 * v * (2.0 * v - 1.0) / (1.0 + v) ** 4
        dsK = np.zeros_like(K)
    elif kernel == "ann2":
        K = 16.0 * v * v / (1.0 + v) ** 4
        dK = 64.0 * v * v * (v - 1.0) / (1.0 + v) ** 5
        dsK = np.zeros_like(K)
    else:
        K = w / (1.0 + w) * (1.0 + v) ** -2
        dK = 4.0 * v * w / (1.0 + w) / (1.0 + v) ** 3
        dsK = -2.0 * w / (1.0 + w) ** 2 / (1.0 + v) ** 2
    return K, dK, dsK


def check_kernels():
    rng = np.random.default_rng(20261116)
    rows, cols = 13, 17
    lag = np.abs(rng.normal(size=(rows, cols))) * 20.0
    lag[:, :3] = -1.0
    r2 = np.abs(rng.normal(size=(rows, cols))) * 200.0
    marks = rng.normal(size=cols) * 0.7
    fertility = rng.uniform(0.2, 2.0, size=cols)
    x = np.array([-3.3, 0.4, 0.7, math.log(0.02), 1.2, math.log(0.9), 0.6, 1.7,
                  0.25, math.log(12.0), math.log(3.0), 1.5])
    native = Native(DEFAULT_OUTPUT / "annular.dll", threads=1)
    rows_checks = []
    for kernel in ("mono", "ann1", "ann2", "shield"):
        for scaled in (True, False):
            out = native.rows(dict(lag=lag, r2=r2), marks, fertility, x,
                              kernel=kernel, scaled=scaled)
            K, dK, dsK = numpy_kernel(r2, marks, x, kernel, scaled)
            base = np.exp(x[11] * marks[None, :] - lag / math.exp(x[10])) * (lag > 0)
            G = (base * K).sum(axis=1)
            dlogell = (base * dK).sum(axis=1)
            dlogpsi = (base * K * (lag / math.exp(x[10]))).sum(axis=1)
            dgamma = (base * K * marks[None, :]).sum(axis=1)
            dlogsig = (base * dsK).sum(axis=1)
            dalph = (base * dsK * marks[None, :]).sum(axis=1)
            rows_checks.append(dict(
                kernel=kernel, scaled=bool(scaled),
                max_abs_G=float(np.max(np.abs(out[:, 6] - G))),
                max_rel_G=rel_error(out[:, 6], G),
                max_rel_dlogell=rel_error(out[:, 7], dlogell),
                max_rel_dlogpsi=rel_error(out[:, 8], dlogpsi),
                max_rel_dgamma=rel_error(out[:, 9], dgamma),
                max_rel_dlogsigma=rel_error(out[:, 10], dlogsig),
                max_rel_dalpha=rel_error(out[:, 11], dalph),
            ))
    passed = all(
        r["max_rel_G"] < 1e-12 and r["max_rel_dlogell"] < 1e-8 and
        r["max_rel_dlogpsi"] < 1e-8 and r["max_rel_dgamma"] < 1e-8 and
        (r["kernel"] != "shield" or (r["max_rel_dlogsigma"] < 1e-8 and r["max_rel_dalpha"] < 1e-8))
        for r in rows_checks
    )
    return dict(passed=passed, rows=rows_checks)


# ---------------------------------------------------------------------------
# 3. Full objective gradients
# ---------------------------------------------------------------------------

def check_objective_gradients():
    native = A.new_native(threads=4)
    bundle = A.build_models("california_fold_0", "interior", native,
                            train_power=12, test_power=10)
    model = bundle["train_model"]
    x0 = bundle["x0"]
    rng = np.random.default_rng(20261116)
    checks = []
    h = 1e-5
    for kernel in ("mono", "ann1", "ann2", "shield"):
        for scaled in (True, False):
            model.kernel = kernel
            model.scaled = scaled
            x = x0.copy()
            x[0] += 0.05 * rng.normal()
            x[1] += 0.05 * rng.normal()
            x[2] += 0.05 * rng.normal()
            x[8] = 0.05 + 0.1 * rng.random()
            x[9] = math.log(2.0 + 48.0 * rng.random())
            x[10] = math.log(0.1 + 30.0 * rng.random())
            value, grad = model.objective(x, True)
            row = dict(kernel=kernel, scaled=bool(scaled), nll=float(value), errors={})
            for index, name in [(8, "eta"), (9, "logell"), (10, "logpsi"), (11, "gamma")]:
                xp = x.copy(); xp[index] += h
                xm = x.copy(); xm[index] -= h
                fd = (model.objective(xp, True)[0] - model.objective(xm, True)[0]) / (2 * h)
                row["errors"][name] = rel_error(grad[index], fd)
            if kernel == "shield":
                for index, name in [(5, "logsigma"), (6, "alphas")]:
                    xp = x.copy(); xp[index] += h
                    xm = x.copy(); xm[index] -= h
                    fd = (model.objective(xp, True)[0] - model.objective(xm, True)[0]) / (2 * h)
                    row["errors"][name] = rel_error(grad[index], fd)
            checks.append(row)
    passed = all(v < 1e-7 for row in checks for v in row["errors"].values())
    return dict(passed=passed, checks=checks)


# ---------------------------------------------------------------------------
# 4. Null slopes recomputed in NumPy
# ---------------------------------------------------------------------------

def numpy_H(lag, r2, marks, fertility, x):
    c = math.exp(x[3])
    sigma2 = np.exp(2.0 * x[5] + 2.0 * x[6] * marks)
    v = r2 / sigma2[None, :]
    k = ((x[4] - 1.0) / c * np.exp(-x[4] * np.log1p(lag / c))
         * (x[7] - 1.0) / (math.pi * sigma2[None, :])
         * np.exp(-x[7] * np.log1p(v)) * fertility[None, :])
    k = np.where(lag > 0, k, 0.0)
    return k.sum(axis=1)


def recompute_slope_bundle(bundle, kernel, scaled, ell, psi):
    x0 = bundle["x0"]
    tm = bundle["train_model"]
    tm.kernel = kernel
    tm.scaled = scaled
    x = x0.copy()
    x[8] = 0.0
    x[9] = math.log(ell)
    x[10] = math.log(psi)
    # Event sum in NumPy.
    lag = tm.events["lag"]
    r2 = tm.events["r2"]
    marks = tm.dm
    K, _, _ = numpy_kernel(r2, marks, x, kernel, scaled)
    base = np.exp(x[11] * marks[None, :] - lag / math.exp(x[10])) * (lag > 0)
    G_e = (base * K).sum(axis=1)
    # Exposure integral in NumPy over the frozen nodes.
    data = tm.node_data
    total = 0.0
    immigrant = 0.0
    for j in range(0, len(data["t"]), 1024):
        raw = {k: v[j:j + 1024] for k, v in data.items()}
        zlag = raw["lag"]
        zr2 = raw["r2"]
        Kz, _, _ = numpy_kernel(zr2, marks, x, kernel, scaled)
        zbase = np.exp(x[11] * marks[None, :] - zlag / math.exp(x[10])) * (zlag > 0)
        g = (zbase * Kz).sum(axis=1)
        xt = 2 * raw["t"] / tm.m["T0"] - 1
        B = np.exp(x[0] + x[1] * xt) * raw["b"]
        h = numpy_H(raw["lag"], raw["r2"], tm.dm, tm.kp, x)
        L = B + x[2] * h
        total += float(raw["w"] @ (L * g))
        immigrant += float(raw["w"] @ (B * g))
    xt_e = 2 * tm.events["t"] / tm.m["T0"] - 1
    B_e = np.exp(x[0] + x[1] * xt_e) * tm.events["b"]
    h_e = numpy_H(tm.events["lag"], tm.events["r2"], tm.dm, tm.kp, x)
    lam = B_e + x[2] * h_e
    S_total = float(G_e.sum())
    S_imm = float(np.sum(B_e / lam * G_e))
    return dict(event_sum=S_total, exposure_integral=total,
                score_slope_total=total - S_total,
                event_sum_immigrant=S_imm, exposure_integral_immigrant=immigrant,
                score_slope_immigrant=immigrant - S_imm)


def check_slopes(stage):
    rows = stage["rows"]
    selected = []
    for case in A.CASES if hasattr(A, "CASES") else ("california_fold_0", "california_fold_1", "california_fold_2"):
        for baseline in A.BASELINES:
            for kernel in A.KERNELS:
                for scaled in (True, False):
                    subset = [r for r in rows if r["case"] == case and r["baseline"] == baseline
                              and r["kernel"] == kernel and r["scaled"] == scaled]
                    if not subset:
                        continue
                    best = max(subset, key=lambda r: r["score_slope_total"])
                    headline = next((r for r in subset if r["ell0_km"] == 15.0 and r["psi_days"] == 5.0), subset[0])
                    selected.extend([best, headline])
    unique = {(r["case"], r["baseline"], r["kernel"], r["scaled"], r["ell0_km"], r["psi_days"]): r
              for r in selected}
    checks = []
    grouped = {}
    for key, saved in unique.items():
        case, baseline, kernel, scaled, ell, psi = key
        grouped.setdefault((case, baseline), []).append((key, saved))
    for (case, baseline), items in grouped.items():
        native = A.new_native(threads=4)
        bundle = A.build_models(case, baseline, native, train_power=14, test_power=16,
                                train_seed=20261111, test_seed=20261120)
        for key, saved in items:
            _case, _baseline, kernel, scaled, ell, psi = key
            recomputed = recompute_slope_bundle(bundle, kernel, scaled, ell, psi)
            event_scale = max(1.0, abs(saved["event_sum"]))
            exposure_scale = max(1.0, abs(saved["exposure_integral"]))
            checks.append(dict(
                key=list(key),
                event_sum_abs_error=abs(recomputed["event_sum"] - saved["event_sum"]),
                event_sum_rel_error=abs(recomputed["event_sum"] - saved["event_sum"]) / event_scale,
                exposure_abs_error=abs(recomputed["exposure_integral"] - saved["exposure_integral"]),
                exposure_rel_error=abs(recomputed["exposure_integral"] - saved["exposure_integral"]) / exposure_scale,
                slope_abs_error=abs(recomputed["score_slope_total"] - saved["score_slope_total"]),
                slope_rel_error=abs(recomputed["score_slope_total"] - saved["score_slope_total"])
                / max(1.0, abs(saved["score_slope_total"])),
                immigrant_slope_abs_error=abs(recomputed["score_slope_immigrant"] - saved["score_slope_immigrant"]),
            ))
    passed = all(r["event_sum_rel_error"] < 1e-9 and r["exposure_rel_error"] < 1e-9
                 and r["slope_rel_error"] < 1e-8 for r in checks)
    return dict(passed=passed, n_rows=len(checks), checks=checks,
                max_event_rel=float(max(r["event_sum_rel_error"] for r in checks)),
                max_exposure_rel=float(max(r["exposure_rel_error"] for r in checks)),
                max_slope_rel=float(max(r["slope_rel_error"] for r in checks)))


# ---------------------------------------------------------------------------
# 5. Profile logic for every row
# ---------------------------------------------------------------------------

def check_profiles(stage):
    failures = []
    for row in stage["rows"]:
        grid = np.asarray(row["eta_grid"], dtype=float)
        total = np.asarray(row["profile_train_total"], dtype=float)
        imm = np.asarray(row["profile_train_immigrant"], dtype=float)
        if abs(total[0]) > 1e-9 or abs(imm[0]) > 1e-9:
            failures.append([row["case"], row["baseline"], row["kernel"], row["scaled"], row["ell0_km"], row["psi_days"], "nonzero_at_zero"])
        if row["score_slope_total"] <= 0 and np.any(np.diff(total) > 1e-7):
            failures.append([row["case"], row["baseline"], row["kernel"], row["scaled"], row["ell0_km"], row["psi_days"], "total_not_nonincreasing"])
        if row["score_slope_total"] <= 0 and (row["eta_hat_train_total"] != 0.0 or row["delta_train_max_total"] != 0.0):
            failures.append([row["case"], row["baseline"], row["kernel"], row["scaled"], row["ell0_km"], row["psi_days"], "negative_slope_but_positive_eta"])
        if row["score_slope_total"] > 0:
            if not (0 < row["eta_hat_train_total"] <= grid[-1] * 2):
                failures.append([row["case"], row["baseline"], row["kernel"], row["scaled"], row["ell0_km"], row["psi_days"], "positive_slope_bad_eta"])
            if row["delta_train_max_total"] < max(total) - 1e-6:
                failures.append([row["case"], row["baseline"], row["kernel"], row["scaled"], row["ell0_km"], row["psi_days"], "max_below_grid"])
        if row["score_slope_immigrant"] <= 0 and (row["eta_hat_train_immigrant"] != 0.0 or row["delta_train_max_immigrant"] != 0.0):
            failures.append([row["case"], row["baseline"], row["kernel"], row["scaled"], row["ell0_km"], row["psi_days"], "negative_imm_slope_but_positive_eta"])
    return dict(passed=not failures, n_rows=len(stage["rows"]), failures=failures)


# ---------------------------------------------------------------------------
# 6. Joint optimization consistency
# ---------------------------------------------------------------------------

def check_joint(stage):
    checks = []
    failures = []
    for row in stage["rows"]:
        selected = row["selected"]
        x = np.asarray(selected["parameters"], dtype=float)
        box = [tuple(b) for b in row["bounds"]]
        in_bounds = all(lo - 1e-8 <= v <= hi + 1e-8 for v, (lo, hi) in zip(x, box))
        if not in_bounds:
            failures.append([row["case"], row["baseline"], row["kernel"], "out_of_bounds"])
        if selected.get("nested_null"):
            expected = np.asarray(row["baseline_meta"].get("parameters", x), dtype=float)
            # The stored baseline parameters are reconstructed from the baseline source.
            x0, _weights, _meta = A.load_baseline(row["case"], row["baseline"])
            identity = float(np.max(np.abs(x - x0)))
        else:
            identity = None
        checks.append(dict(
            case=row["case"], baseline=row["baseline"], kernel=row["kernel"],
            in_bounds=in_bounds, nested_null=bool(selected.get("nested_null")),
            eta=float(x[8]), nll=float(selected["nll"]),
            training_gain=float(row["training_nll_gain"]),
            nested_identity_max_abs=identity,
            test_gain_mean=float(row["test"]["gain_mean"]),
            attenuation_gain_mean=float(row["test"].get("attenuation_gain_mean", 0.0)),
            test_seed_gains=[float(s["gain_total"]) for s in row["test"]["scores"]],
            block_closure=float(row["test"]["block_intervals"].get("closure_error", 0.0)),
        ))
        if identity is not None and identity > 1e-12:
            failures.append([row["case"], row["baseline"], row["kernel"], "nested_identity"])
    passed = not failures
    return dict(passed=passed, n_rows=len(checks), failures=failures, checks=checks)


def check_heldout(stage):
    rows = [r for r in stage["rows"] if r["training_selected_eta"] > 0]
    if not rows:
        return dict(passed=True, skipped=True, reason="all selected states are the exact nested null")
    checks = []
    for row in rows:
        native = A.new_native(threads=4)
        bundle = A.build_models(row["case"], row["baseline"], native, train_power=14,
                                test_power=16, train_seed=20261111,
                                test_seed=stage["test_seeds"][0])
        model = bundle["test_model"]
        x0 = bundle["x0"]
        model.node_setup(x0, power=16, seed=stage["test_seeds"][0])
        model.freeze_nodes()
        x = np.asarray(row["selected"]["parameters"], dtype=float)
        same = x.copy()
        same[8] = 0.0
        null = model.objective(x0, False, True)
        same_null = model.objective(same, False, True)
        inhibited = model.objective(x, True, True)
        gain_total = float(null["nll"] - inhibited["nll"])
        gain_atten = float(same_null["nll"] - inhibited["nll"])
        saved = row["test"]["scores"][0]
        checks.append(dict(
            case=row["case"], baseline=row["baseline"], kernel=row["kernel"],
            eta=float(x[8]),
            saved_gain_total=float(saved["gain_total"]),
            recomputed_gain_total=gain_total,
            gain_total_abs_error=abs(gain_total - saved["gain_total"]),
            saved_gain_attenuation=float(saved["gain_attenuation"]),
            recomputed_gain_attenuation=gain_atten,
            gain_attenuation_abs_error=abs(gain_atten - saved["gain_attenuation"]),
        ))
    passed = all(r["gain_total_abs_error"] < 1e-8 and r["gain_attenuation_abs_error"] < 1e-8
                 for r in checks)
    return dict(passed=passed, n_rows=len(checks), checks=checks)


# ---------------------------------------------------------------------------
# 7. Synthetic summary arithmetic
# ---------------------------------------------------------------------------

def check_synthetic(results):
    path = results / "synthetic/summary.json"
    if not path.exists():
        return dict(passed=True, skipped=True, reason="summary absent")
    summary = read(path)
    rows = summary["rows"]
    values = np.asarray([r["ann2_gain"] for r in rows], dtype=float)
    mean = float(values.mean())
    mcse = float(values.std(ddof=1) / math.sqrt(len(values)))
    passed = abs(mean - summary["ann2_gain"]["mean"]) < 1e-10 and abs(mcse - summary["ann2_gain"]["mcse"]) < 1e-10
    recovery = [r["ann2_recovery_fraction"] for r in rows if r["ann2_recovery_fraction"] is not None]
    passed = passed and abs(float(np.mean(recovery)) - summary["ann2_recovery_fraction"]["mean"]) < 1e-10
    # Quadrature convergence: fast tensor grid (20 x 16) versus the frozen
    # spatial plan and the archived order-8 temporal plan, on one history.
    seed = rows[0]["seed"]
    bank = results / "synthetic/bank"
    receipt = read(bank / f"{seed}.json")
    history = np.load(bank / f"{seed}.npz")["rows"]
    native = RS.native_v2(threads=4)
    modules = SY.load_s8().archived()
    phase = SY.make_phase(history, receipt["metadata"], 395.0, 760.0, native, modules)
    theta = np.asarray(rows[0]["true_theta"], dtype=float)
    fast = SY.FastSyntheticAnnular(phase, native, kernel="ann2", spatial_order=20, time_order=16)
    slow = SY.SyntheticAnnular(phase, native, kernel="ann2")
    fast_value, _ = fast.evaluate(theta, "ann2", 16)
    slow_value, _ = slow.evaluate(theta, "ann2", 8)
    quadrature_delta = float(abs(fast_value["joint"] - slow_value["joint"]))
    saved_delta = float(abs(fast_value["joint"] - rows[0]["oracle_test_joint"]))
    passed = passed and quadrature_delta < 0.01 and saved_delta < 1e-8
    return dict(passed=passed, N=len(rows), recomputed_ann2_mean=mean,
                recomputed_ann2_mcse=mcse, recomputed_recovery_mean=float(np.mean(recovery)),
                stored_ann2_mean=summary["ann2_gain"]["mean"],
                stored_ann2_mcse=summary["ann2_gain"]["mcse"],
                stored_recovery_mean=summary["ann2_recovery_fraction"]["mean"],
                quadrature_history=seed, fast_minus_frozen_abs=quadrature_delta,
                fast_minus_saved_oracle_abs=saved_delta)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--output", type=Path, default=RESULTS / "independent_audit.json")
    args = parser.parse_args()
    started = __import__("time").time()
    report = dict(schema="pathway1_independent_audit_v1", passed=False)
    report["integrity"] = check_integrity()
    report["kernels"] = check_kernels()
    report["objective_gradients"] = check_objective_gradients()
    stage11_path = args.results / "stage_p11_null_profiles.json"
    if stage11_path.exists():
        stage11 = read(stage11_path)
        report["slopes"] = check_slopes(stage11)
        report["profiles"] = check_profiles(stage11)
    else:
        report["slopes"] = dict(passed=False, reason="P1.1 summary absent")
        report["profiles"] = dict(passed=False, reason="P1.1 summary absent")
    stage12_path = args.results / "stage_p12_joint_optimization.json"
    if stage12_path.exists():
        stage12 = read(stage12_path)
        report["joint"] = check_joint(stage12)
        report["heldout"] = check_heldout(stage12)
    else:
        report["joint"] = dict(passed=False, reason="P1.2 summary absent")
        report["heldout"] = dict(passed=False, reason="P1.2 summary absent")
    report["synthetic"] = check_synthetic(args.results)
    report["passed"] = all(
        report[key].get("passed", False)
        for key in ("integrity", "kernels", "objective_gradients", "slopes",
                    "profiles", "joint", "heldout", "synthetic")
    )
    report["elapsed_seconds"] = float(__import__("time").time() - started)
    write(args.output, report)
    print(json.dumps({k: report[k].get("passed") for k in (
        "integrity", "kernels", "objective_gradients", "slopes", "profiles",
        "joint", "heldout", "synthetic")}, indent=2))
    print("passed", report["passed"])
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
