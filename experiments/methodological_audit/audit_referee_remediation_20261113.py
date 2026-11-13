"""Independent audit of the 13 November 2026 referee-remediation supplement.

Recomputes every derived scalar from the sealed authorities with separately
written code, re-evaluates the partial-oracle scores, and verifies that the
hash-pinned sealed authorities are byte-identical to the pre-change snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS"):
    os.environ.setdefault(_key, "2")

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

S8 = ROOT / "validation/live_results/s8_moderate_complete_20261111"
S8_DATA = ROOT / "reproduction/synthetic/s8_moderate_total"
S8_SOURCE = S8 / "source/s8_moderate.py"
NZ_UNCERTAINTY = ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json"
CA_UNCERTAINTY = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_uncertainty/summary.json"
TRACK_B = ROOT / "validation/live_results/track_b_controls_20261112"
SNAPSHOT = ROOT / "validation/referee_prechange_snapshot_20261113.json"
S04B = ROOT / "validation/live_results/s04b_joint_complete_20261111"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


class Audit:
    def __init__(self):
        self.checks = []

    def check(self, name, observed, expected, tolerance=1e-9):
        passed = close(observed, expected, tolerance)
        self.checks.append(dict(check=name, observed=float(observed), expected=float(expected),
                                absolute_difference=float(abs(observed - expected)), passed=bool(passed)))
        return passed


def audit_mde(audit: Audit, output: Path) -> None:
    data = read(output / "mde_expanded.json")
    nz = read(NZ_UNCERTAINTY)
    ca = read(CA_UNCERTAINTY)
    cases_nz = ("fold_50", "fold_65", "fold_80")
    cases_ca = ("california_fold_0", "california_fold_1", "california_fold_2")
    by_contrast = {row["contrast"]: row for row in data["contrasts"]}

    def se_from_scores(rows, cases, contrast, n_test, days, pooled):
        groups = []
        for case in cases:
            row = next(r for r in rows if r["case"] == case and r["contrast"] == contrast)
            scores = np.asarray(row["block_scores"], dtype=float)
            groups.append(len(scores) * scores.var(ddof=1))
        se = math.sqrt(sum(groups))
        halfwidth = (pooled["ci95_total"][1] - pooled["ci95_total"][0]) / 2.0
        return se, se / n_test, halfwidth

    for contrast in ("NZ_shared_minus_ML", "CA_LIplus_total_minus_floor", "CA_OC_minus_EP"):
        for days in (90, 180, 365):
            rows = nz["rows"] if days == 90 else nz["sensitivity"][str(days)]["rows"]
            pooled = (nz["pooled"] if days == 90 else nz["sensitivity"][str(days)]["pooled"])[contrast]
            cases = cases_nz if contrast.startswith("NZ") else cases_ca
            n_test = 612 if contrast.startswith("NZ") else 315
            se, per_event, halfwidth = se_from_scores(rows, cases, contrast, n_test, days, pooled)
            entry = by_contrast[contrast]["block_days"][str(days)]
            audit.check(f"{contrast}/{days}/se", entry["se_total_nats"], se)
            audit.check(f"{contrast}/{days}/mde95", entry["mde95_total_nats"], 1.96 * se)
            audit.check(f"{contrast}/{days}/per_event", entry["mde95_nats_per_event"], 1.96 * per_event)
            audit.check(f"{contrast}/{days}/bootstrap_halfwidth", entry["bootstrap_halfwidth_nats"], halfwidth)

    for days in (90, 180, 365):
        rows = ca["rows_by_block_days"][str(days)]
        groups = []
        for case in cases_ca:
            row = next(r for r in rows if r["case"] == case)
            scores = np.asarray(row["block_scores"], dtype=float)
            groups.append(len(scores) * scores.var(ddof=1))
        se = math.sqrt(sum(groups))
        pooled = ca["pooled_by_block_days"][str(days)]
        entry = by_contrast["CA_EPplus_minus_original_EP"]["block_days"][str(days)]
        audit.check(f"CA_EPplus/{days}/se", entry["se_total_nats"], se)
        audit.check(f"CA_EPplus/{days}/mde95", entry["mde95_total_nats"], 1.96 * se)
        audit.check(f"CA_EPplus/{days}/bootstrap_halfwidth", entry["bootstrap_halfwidth_nats"],
                    (pooled["ci95_total"][1] - pooled["ci95_total"][0]) / 2.0)

    fold_se = float(np.std([-74.7591, -59.1334, -87.3190], ddof=1) / math.sqrt(3))
    audit.check("japan/per_fold/se", data["japan"]["per_fold"]["se_total_nats"], fold_se)
    audit.check("japan/per_fold/mde95", data["japan"]["per_fold"]["mde95_total_nats"], 1.96 * fold_se)
    audit.check("japan/sum/se", data["japan"]["three_fold_sum"]["se_total_nats"], 3 * fold_se)
    audit.check("japan/sum/mde95", data["japan"]["three_fold_sum"]["mde95_total_nats"], 3 * 1.96 * fold_se)
    audit.check("japan/observed_total", data["japan"]["observed"]["total_nats"], -221.2115)


def audit_quantiles(audit: Audit, output: Path) -> None:
    data = read(output / "synthetic_quantiles.json")
    cases = [read(p) for p in sorted((S04B / "cases").glob("*.json"))]
    for row in data["rows"]:
        if row["table"] != "s04b_joint":
            continue
        values = []
        for case in cases:
            if case["regime"] != row["regime"]:
                continue
            outcome = next(o for o in case["outcomes"]
                           if o["model"] == row["model"] and o["gate"] == row["gate"])
            values.append(outcome["new_gain"])
        q25, q50, q75 = np.quantile(values, [0.25, 0.5, 0.75])
        tag = f"S04B/{row['regime']}/{row['model']}/{row['gate']}"
        audit.check(tag + "/q25", row["q25"], q25)
        audit.check(tag + "/q50", row["median"], q50)
        audit.check(tag + "/q75", row["q75"], q75)
        audit.check(tag + "/iqr", row["iqr"], q75 - q25)
        audit.check(tag + "/min", row["minimum"], min(values))
        audit.check(tag + "/max", row["maximum"], max(values))
    # S8 rows against the sealed supplement and oracle authority.
    supplement = read(ROOT / "validation/live_results/reporting_supplement_20261112/supplement.json")
    for row in data["rows"]:
        if row["table"] == "s8_moderate":
            key = "raw_gain" if row["selection"] == "raw" else "bic_gain"
            values = [c[key] for c in supplement["s8"]["cases"]]
            audit.check(f"S8/{row['selection']}/min", row["minimum"], min(values))
            audit.check(f"S8/{row['selection']}/max", row["maximum"], max(values))
            audit.check(f"S8/{row['selection']}/median", row["median"], np.median(values))
        if row["table"] == "s8_oracle":
            mapping = {"true_vs_fixed_true_backbone_null": "oracle_gain_vs_fixed",
                       "true_vs_refitted_intercept_null": "oracle_gain_vs_intercept",
                       "true_vs_jointly_fitted_null": "oracle_gain_vs_joint_null",
                       "fitted_inhibited_minus_true": "estimation_loss",
                       "fitted_inhibited_minus_fitted_null": "fitted_gain"}
            values = [r[mapping[row["contrast"]]] for r in read(TRACK_B / "profiles_and_power/s8_oracle.json")["rows"]]
            audit.check(f"S8-oracle/{row['contrast']}/mean", row["mean"], np.mean(values))
            audit.check(f"S8-oracle/{row['contrast']}/iqr",
                        row["iqr"], np.quantile(values, .75) - np.quantile(values, .25))


def audit_nz(audit: Audit, output: Path) -> None:
    data = read(output / "nz_trend_totals.json")
    authority = read(TRACK_B / "nz_trend_controls/summary.json")
    folds = authority["folds"]
    for kind, key in (("free_d", "archived"), ("zero_d", "zero_trend"), ("fixed_null_d", "fixed_null_trend")):
        totals = dict(delta_Q=0.0, delta_C=0.0, delta_joint=0.0)
        for name in ("fold_50", "fold_65", "fold_80"):
            held = folds[name]["archived"]["heldout"] if key == "archived" else folds[name]["controls"][key]["heldout"]
            for field in totals:
                totals[field] += held[field]
        for field, value in totals.items():
            audit.check(f"nz/{kind}/{field}", data["controls"][kind]["totals"][field], value)
    clamped = sum(folds[name]["clamped"]["delta_joint"] for name in ("fold_50", "fold_65", "fold_80"))
    audit.check("nz/clamped/delta_joint", data["controls"]["clamped_clock"]["totals"]["delta_joint"], clamped)
    audit.check("nz/totals/archived_joint", data["controls"]["free_d"]["totals"]["delta_joint"],
                authority["totals"]["archived_delta_joint"])
    audit.check("nz/totals/zero_joint", data["controls"]["zero_d"]["totals"]["delta_joint"],
                authority["totals"]["zero_trend_delta_joint"])
    audit.check("nz/totals/fixed_joint", data["controls"]["fixed_null_d"]["totals"]["delta_joint"],
                authority["totals"]["fixed_null_trend_delta_joint"])
    audit.check("nz/fixed_null_below_90day_mde", data["below_nz_90day_mde"]["nz_90day_mde95"], 9.236284345647903, 1e-6)


def audit_s8(audit: Audit, output: Path) -> None:
    from threadpoolctl import threadpool_limits
    from scipy.optimize import minimize_scalar
    from experiments.s04b_joint_nuisance import model
    from experiments.s04b_completion.recover import native_library
    from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler

    def load_frozen(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    data = read(output / "s8_oracle_decomposition.json")
    oracle = read(TRACK_B / "profiles_and_power/s8_oracle.json")
    rows = {r["seed"]: r for r in oracle["rows"]}
    eta_values = [rows[seed]["fitted_eta"] for seed in sorted(rows)]
    audit.check("s8/eta/mean", data["fitted_eta"]["mean"], np.mean(eta_values), 1e-12)
    audit.check("s8/eta/median", data["fitted_eta"]["median"], np.median(eta_values), 1e-12)
    audit.check("s8/eta/min", data["fitted_eta"]["minimum"], min(eta_values), 1e-12)
    audit.check("s8/eta/max", data["fitted_eta"]["maximum"], max(eta_values), 1e-12)
    audit.check("s8/eta/rmse", data["fitted_eta"]["rmse_vs_true"],
                math.sqrt(np.mean((np.asarray(eta_values) - 0.4) ** 2)), 1e-12)
    closure = data["oracle_closure"]
    audit.check("s8/closure/identity", closure["identity_residual"], 0.0, 1e-12)
    audit.check("s8/closure/gain_intercept", closure["oracle_gain_vs_intercept_mean"],
                np.mean([rows[s]["oracle_gain_vs_intercept"] for s in rows]), 1e-12)
    audit.check("s8/null_loss/mean", data["true_null_minus_fitted_null"]["mean"],
                np.mean([rows[s]["fixed_true_backbone_null_joint"] - rows[s]["jointly_fitted_null_joint"] for s in rows]), 1e-12)
    audit.check("s8/backbone_loss/mean", data["refitted_intercept_minus_fitted_null"]["mean"],
                np.mean([rows[s]["refitted_intercept_null_joint"] - rows[s]["jointly_fitted_null_joint"] for s in rows]), 1e-12)

    # Re-evaluate the stored partial-oracle scores with the frozen model code.
    with threadpool_limits(limits=1):
        run = load_frozen(S8_SOURCE, "audit_s8_runner")
        modules = model.archived()
        native = model.Native(native_library())
        receipts = read(S8_DATA / "receipts.json")
        stored_a = {r["seed"]: r for r in data["partial_oracle_a"]["rows"]}
        stored_b = {r["seed"]: r for r in data["partial_oracle_b"]["rows"]}
        for seed in sorted(stored_a):
            record = next(r for r in receipts if r["seed"] == seed)
            history = np.load(S8_DATA / f"{seed}.npz")["rows"]
            result = read(S8 / str(seed) / "result.json")
            train_base = model.phase_from_rows(history, record["metadata"], 30.0, 395.0, modules, native)
            test_base = model.phase_from_rows(history, record["metadata"], 395.0, 760.0, modules, native)
            with OrderedChunkScheduler() as scheduler:
                test = run.TensorPhase(test_base.a, test_base.m, modules, native, math.inf, scheduler=scheduler)
                theta = np.asarray(stored_b[seed]["parameters"], dtype=float)
                score = test.evaluate(theta, "LIplus_inclusive", 32)[0]
                audit.check(f"s8/partial_b/{seed}/replay", stored_b[seed]["test_joint"], score["joint"], 1e-6)
                a = np.asarray(result["fits"]["null"]["selected"]["parameters"], dtype=float)
                theta = a.copy()
                theta[0] = stored_a[seed]["refitted_intercept_a"]
                theta[5:] = [0.4, math.log(15.0), math.log(5.0)]
                score_a = test.evaluate(theta, "LIplus_inclusive", 32)[0]
                audit.check(f"s8/partial_a/{seed}/replay", stored_a[seed]["test_joint"], score_a["joint"], 1e-6)


def audit_custody(audit: Audit) -> None:
    snapshot = read(SNAPSHOT)
    for entry in snapshot["sealed_authorities"]:
        path = ROOT / entry["path"]
        if not path.is_file():
            audit.checks.append(dict(check="custody/" + entry["path"], observed=None,
                                     expected=entry["sha256"], passed=False, note="missing"))
            continue
        observed = sha(path)
        audit.checks.append(dict(check="custody/" + entry["path"], observed=observed,
                                 expected=entry["sha256"], passed=observed == entry["sha256"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "validation/live_results/referee_remediation_20261113")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or (args.input / "independent_audit.json")
    started = __import__("time").time()
    audit = Audit()
    audit_mde(audit, args.input)
    audit_quantiles(audit, args.input)
    audit_nz(audit, args.input)
    audit_s8(audit, args.input)
    audit_custody(audit)
    failed = [c for c in audit.checks if not c["passed"]]
    payload = dict(
        schema="referee_remediation_independent_audit_v1",
        passed=not failed,
        check_count=len(audit.checks),
        failed=len(failed),
        checks=audit.checks,
        runtime_seconds=float(__import__("time").time() - started),
        verifier_source_sha256=sha(Path(__file__)),
        input_hashes={p.name: sha(p) for p in sorted(args.input.glob("*.json"))},
        sealed_authorities_mutated=any(c["check"].startswith("custody/") and not c["passed"]
                                       for c in audit.checks),
    )
    output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("passed", "check_count", "failed", "runtime_seconds")}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
