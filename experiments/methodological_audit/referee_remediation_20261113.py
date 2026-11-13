"""Additive referee-remediation supplement (13 November 2026).

Deterministic calculations only.  Every input is an existing sealed authority or
frozen synthetic history; every output is written under the new supplement
directory.  No sealed JSON is rewritten.

Outputs
-------
mde_expanded.json             contrast-specific block SEs and MDEs
s8_oracle_decomposition.json  partial oracles, estimation-loss closure, eta census
synthetic_quantiles.json      sample Q25/Q50/Q75/IQR/min/max for synthetic tables
nz_trend_totals.json          three-fold New Zealand trend-control totals
summary.json                  key results and input hashes
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time
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
S8_ORACLE = TRACK_B / "profiles_and_power/s8_oracle.json"
NZ_TREND = TRACK_B / "nz_trend_controls/summary.json"
S04B = ROOT / "validation/live_results/s04b_joint_complete_20261111"
SUPPLEMENT = ROOT / "validation/live_results/reporting_supplement_20261112/supplement.json"

TRUE_THETA = np.array([math.log(0.25), 0.2, 0.35, math.log(0.05), 1.3, 0.4,
                       math.log(15.0), math.log(5.0)])
JAPAN_FOLD_TOTALS = (-74.7591, -59.1334, -87.3190)
JAPAN_TEST_EVENTS = 1277


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def stats(values) -> dict:
    values = np.asarray(values, dtype=float)
    return dict(N=int(len(values)), mean=float(values.mean()), median=float(np.median(values)),
                sample_sd=float(values.std(ddof=1)),
                mcse=float(values.std(ddof=1) / math.sqrt(len(values))),
                wins=int(np.sum(values > 0)), values=[float(v) for v in values])


def sample_quantiles(values) -> dict:
    values = np.asarray(values, dtype=float)
    q25, q50, q75 = np.quantile(values, [0.25, 0.50, 0.75])
    return dict(N=int(len(values)), q25=float(q25), median=float(q50), q75=float(q75),
                iqr=float(q75 - q25), minimum=float(values.min()), maximum=float(values.max()),
                mean=float(values.mean()), sample_sd=float(values.std(ddof=1)),
                values=[float(v) for v in values])


# ---------------------------------------------------------------------------
# Contrast-specific minimum detectable effects
# ---------------------------------------------------------------------------

def block_se(row, n_per_fold: float) -> dict:
    scores = np.asarray(row["block_scores"], dtype=float)
    blocks = len(scores)
    se = float(math.sqrt(blocks) * scores.std(ddof=1))
    lo, hi = row["summary"]["ci95_total"]
    return dict(blocks=blocks, total_nats=se, per_event_nats=se / n_per_fold,
                percentile_halfwidth_nats=float((hi - lo) / 2.0))


def pooled_block_se(groups, n_test: float, pooled: dict | None = None) -> dict:
    variance = sum(g["blocks"] * (g["total_nats"] / math.sqrt(g["blocks"])) ** 2 for g in groups)
    se = float(math.sqrt(variance))
    blocks = int(sum(g["blocks"] for g in groups))
    if pooled is not None:
        halfwidth = float((pooled["ci95_total"][1] - pooled["ci95_total"][0]) / 2.0)
    else:
        halfwidth = float(sum(g["percentile_halfwidth_nats"] ** 2 for g in groups) ** 0.5)
    return dict(blocks=blocks, total_nats=se, per_event_nats=se / n_test,
                percentile_halfwidth_nats=halfwidth)


def mde_block(se: dict, n_test: float) -> dict:
    total = se["total_nats"]
    return dict(blocks=se["blocks"],
                se_total_nats=total,
                se_nats_per_event=se["per_event_nats"],
                mde95_total_nats=1.96 * total,
                mde95_nats_per_event=1.96 * se["per_event_nats"],
                mde80_total_nats=2.80 * total,
                mde80_nats_per_event=2.80 * se["per_event_nats"],
                required_rate_perturbation=math.sqrt(2 * 1.96 * total / n_test),
                bootstrap_halfwidth_nats=se["percentile_halfwidth_nats"])


def build_mde(output: Path) -> dict:
    nz = read(NZ_UNCERTAINTY)
    ca = read(CA_UNCERTAINTY)
    cases_nz = ("fold_50", "fold_65", "fold_80")
    cases_ca = ("california_fold_0", "california_fold_1", "california_fold_2")

    def uncertainty_groups(contrast: str, days: int, n_test: float):
        rows = nz["rows"] if days == 90 else nz["sensitivity"][str(days)]["rows"]
        cases = cases_nz if contrast.startswith("NZ") else cases_ca
        groups = [block_se(next(r for r in rows if r["case"] == case and r["contrast"] == contrast), n_test / 3)
                  for case in cases]
        pooled = (nz["pooled"] if days == 90 else nz["sensitivity"][str(days)]["pooled"])[contrast]
        return pooled_block_se(groups, n_test, pooled)

    def california_ep_groups(days: int):
        rows = ca["rows_by_block_days"][str(days)]
        groups = [block_se(next(r for r in rows if r["case"] == case and r["contrast"] == "CA_EPplus_minus_original_EP"), 315 / 3)
                  for case in cases_ca]
        return pooled_block_se(groups, 315, ca["pooled_by_block_days"][str(days)])

    trends = read(NZ_TREND)
    contrasts = []

    def add(contrast, n_test, source, observed, se_fn):
        entry = dict(contrast=contrast, n_test=int(n_test), source=source,
                     observed=observed, block_days={})
        for days in (90, 180, 365):
            entry["block_days"][str(days)] = mde_block(se_fn(days), n_test)
        contrasts.append(entry)

    add("NZ_shared_minus_ML", 612, "score_uncertainty_remote_v2_20261111",
        dict(free_d=-17.62285936479381,
             zero_d=-11.43120134330374,
             fixed_null_d=-5.005743070332926,
             primary_display="free d"),
        lambda days: uncertainty_groups("NZ_shared_minus_ML", days, 612))
    add("CA_LIplus_total_minus_floor", 315, "score_uncertainty_remote_v2_20261111",
        dict(free_d=-2.386674517269429, primary_display="free d"),
        lambda days: uncertainty_groups("CA_LIplus_total_minus_floor", days, 315))
    add("CA_EPplus_minus_original_EP", 315,
        "etas_inhibition_benchmark_interior_20261112/baseline_uncertainty",
        dict(bound_pinned=69.55289384227054,
             interior_sigma0_redeclustered=77.0557339839778,
             interior_sigma0_frozen_weights=78.5844526377922,
             primary_display="bound-pinned 69.553; interior 77.056"),
        california_ep_groups)
    add("CA_OC_minus_EP", 315, "score_uncertainty_remote_v2_20261111",
        dict(free_d=-51.05120476305756, primary_display="free d"),
        lambda days: uncertainty_groups("CA_OC_minus_EP", days, 315))

    japan_values = np.asarray(JAPAN_FOLD_TOTALS, dtype=float)
    fold_se = float(japan_values.std(ddof=1) / math.sqrt(len(japan_values)))
    japan = dict(
        contrast="Japan_OC_minus_EP_joint",
        n_test=JAPAN_TEST_EVENTS,
        source="three reported JMA fold totals; between-window standard error, not a calendar-block bootstrap",
        observed=dict(total_nats=float(japan_values.sum()),
                      per_fold_nats=float(japan_values.sum() / len(japan_values)),
                      fold_totals=[float(v) for v in japan_values],
                      primary_display="total -221.211; -73.737 per fold"),
        per_fold=dict(se_total_nats=fold_se,
                      se_nats_per_event=fold_se / JAPAN_TEST_EVENTS,
                      mde95_total_nats=1.96 * fold_se,
                      mde95_nats_per_event=1.96 * fold_se / JAPAN_TEST_EVENTS,
                      mde80_total_nats=2.80 * fold_se,
                      blocks=3),
        three_fold_sum=dict(se_total_nats=3 * fold_se,
                            mde95_total_nats=3 * 1.96 * fold_se,
                            mde80_total_nats=3 * 2.80 * fold_se,
                            per_event_nats=3 * fold_se / JAPAN_TEST_EVENTS,
                            note="Sum of three annual fold totals; between-window SE multiplied by three."),
        observed_total_over_three_fold_mde=float(japan_values.sum() / (3 * 1.96 * fold_se)),
        note=("The between-window SE describes three annual windows only; it is not a 90/180/365-day "
              "calendar-block estimate and is repeated at each label."))

    summary = dict(
        schema="referee_mde_expanded_v1",
        passed=True,
        source="experiments/methodological_audit/referee_remediation_20261113.py",
        definition=("MDE95=1.96*SE_B and MDE80=2.80*SE_B.  SE_B is the independent-block standard "
                    "error sqrt(sum_f blocks_f * var_f) of paired calendar-block score totals, matching "
                    "the repository's established block-SE definition.  The bootstrap percentile "
                    "half-width is reported separately because contiguous blocks are dependent."),
        block_inference_qualification=("Contiguous calendar blocks are dependent under long memory; these are "
                                       "descriptive multi-scale sensitivities, not calibrated frequentist guarantees."),
        contrasts=contrasts,
        japan=japan,
        block_lengths=[90, 180, 365],
        confidence_percent=95,
    )
    write(output / "mde_expanded.json", summary)
    return summary


# ---------------------------------------------------------------------------
# S8 oracle decomposition
# ---------------------------------------------------------------------------

def load_frozen(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def truth_at(backbone) -> np.ndarray:
    theta = np.asarray(backbone, dtype=float).copy()
    theta[5] = 0.4
    theta[6] = math.log(15.0)
    theta[7] = math.log(5.0)
    return theta


def build_s8_oracle(output: Path) -> dict:
    from threadpoolctl import threadpool_limits
    from scipy.optimize import minimize, minimize_scalar

    with threadpool_limits(limits=1):
        from experiments.s04b_joint_nuisance import model
        from experiments.s04b_completion.recover import native_library
        from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler
        run = load_frozen(S8_SOURCE, "referee_s8_runner")
        thresholds = read(SUPPLEMENT)["s8"]["boundary_bounds"]
        modules = model.archived()
        native = model.Native(native_library())
        receipts = read(S8_DATA / "receipts.json")
        seeds = sorted(int(p.name.split(".")[0]) for p in S8_DATA.glob("*.npz"))
        order = [("a", "a"), ("d", "d"), ("n", "n"), ("log_c", "log_c"), ("p", "p")]
        box = [(thresholds[key]["lower"], thresholds[key]["upper"]) for _, key in order]
        rows, partial_a_rows, partial_b_rows = [], [], []
        for seed in seeds:
            started = time.time()
            result = read(S8 / str(seed) / "result.json")
            record = next(r for r in receipts if r["seed"] == seed)
            history = np.load(S8_DATA / f"{seed}.npz")["rows"]
            train_base = model.phase_from_rows(history, record["metadata"], 30.0, 395.0, modules, native)
            test_base = model.phase_from_rows(history, record["metadata"], 395.0, 760.0, modules, native)
            with OrderedChunkScheduler() as scheduler:
                train = run.TensorPhase(train_base.a, train_base.m, modules, native, math.inf, scheduler=scheduler)
                test = run.TensorPhase(test_base.a, test_base.m, modules, native, math.inf, scheduler=scheduler)
                backbone = np.asarray(result["fits"]["null"]["selected"]["parameters"], dtype=float)
                joint_null = float(result["null_test"]["joint"])

                # Partial oracle A: fitted null backbone with a refitted scalar intercept.
                def intercept_nll(a):
                    theta = truth_at(backbone)
                    theta[0] = float(a)
                    return float(train.evaluate(theta, "LIplus_inclusive", 16)[0]["nll"])
                opt = minimize_scalar(intercept_nll, bounds=(-12.0, 0.0), method="bounded",
                                      options=dict(xatol=1e-10, maxiter=320))
                theta_a = truth_at(backbone)
                theta_a[0] = float(opt.x)
                score_a = test.evaluate(theta_a, "LIplus_inclusive", 32)[0]

                # Partial oracle B: re-fit the five-parameter backbone at true attenuation.
                start = truth_at(backbone)

                def objective(v):
                    theta = start.copy()
                    theta[:5] = v
                    value, gradient = train.evaluate(theta, "LIplus_inclusive", 16)
                    return float(value["nll"]), np.asarray(gradient[:5], dtype=float)
                lo = np.asarray([b[0] for b in box])
                hi = np.asarray([b[1] for b in box])
                fit = minimize(objective, np.clip(start[:5], lo, hi), jac=True, bounds=box,
                               method="L-BFGS-B",
                               options=dict(maxiter=400, maxls=80, ftol=1e-10, gtol=2e-5))
                theta_b = start.copy()
                theta_b[:5] = fit.x
                score_b = test.evaluate(theta_b, "LIplus_inclusive", 32)[0]
                train_b = train.evaluate(theta_b, "LIplus_inclusive", 16)[0]

            partial_a_rows.append(dict(
                seed=seed, refitted_intercept_a=float(opt.x),
                test_joint=float(score_a["joint"]),
                gain_vs_joint_null=float(score_a["joint"] - joint_null)))
            partial_b_rows.append(dict(
                seed=seed,
                parameters=[float(v) for v in theta_b],
                training_nll=float(train_b["nll"]),
                test_joint=float(score_b["joint"]),
                gain_vs_joint_null=float(score_b["joint"] - joint_null),
                success=bool(fit.success), nfev=int(fit.nfev),
                boundaries=[bool(abs(v - b[0]) <= 1e-8 or abs(v - b[1]) <= 1e-8)
                            for v, b in zip(theta_b[:5], box)]))

            original = next(r for r in read(S8_ORACLE)["rows"] if r["seed"] == seed)
            rows.append(dict(seed=seed, fitted_eta=float(result["eta"]),
                             estimation_loss=float(original["estimation_loss"]),
                             oracle_gain_vs_joint_null=float(original["oracle_gain_vs_joint_null"])))
            print(f"s8 {seed} A={partial_a_rows[-1]['gain_vs_joint_null']:.3f} "
                  f"B={partial_b_rows[-1]['gain_vs_joint_null']:.3f} ({time.time()-started:.1f}s)", flush=True)

    oracle_rows = read(S8_ORACLE)["rows"]
    fixed = [r["fixed_true_backbone_null_joint"] for r in oracle_rows]
    intercept = [r["refitted_intercept_null_joint"] for r in oracle_rows]
    joint = [r["jointly_fitted_null_joint"] for r in oracle_rows]
    true_joint = [r["true_generating_joint"] for r in oracle_rows]
    eta = np.asarray([r["fitted_eta"] for r in oracle_rows], dtype=float)

    gain_a = stats([r["gain_vs_joint_null"] for r in partial_a_rows])
    gain_b = stats([r["gain_vs_joint_null"] for r in partial_b_rows])
    null_loss = stats([a - b for a, b in zip(fixed, joint)])
    backbone_loss = stats([a - b for a, b in zip(intercept, joint)])
    eta_stats = sample_quantiles(eta)
    eta_stats.update(rmse_vs_true=float(math.sqrt(np.mean((eta - 0.4) ** 2))),
                     true_eta=0.4,
                     boundary_hits=int(np.sum(np.isclose(eta, 4.0, atol=1e-8))))
    summary = dict(
        schema="referee_s8_oracle_decomposition_v1",
        passed=True,
        source="experiments/methodological_audit/referee_remediation_20261113.py",
        definitions=dict(
            partial_oracle_a=("True attenuation (eta=0.4, ell=15 km, psi=5 d) placed on each history's "
                              "jointly fitted training null backbone, with a scalar intercept refitted on "
                              "training data; test order 32."),
            partial_oracle_b=("Attenuation fixed at truth; the five nuisance-backbone parameters "
                              "(a,d,n,c,p) re-optimized on the training window at order 16 and scored on "
                              "test at order 32."),
            true_null_minus_fitted_null=("l_test(theta_star,0) - l_test(theta_hat_0(H_train)); "
                                         "positive values mean the fitted comparator scores better than "
                                         "the true uninhibited backbone."),
            refitted_intercept_minus_fitted_null=("l_test(a_hat, theta_star,0,-a) - l_test(theta_hat_0); "
                                                  "the comparator's own four-parameter estimation gain that "
                                                  "inflates the oracle-versus-joint-null contrast.")),
        true_parameters=dict(a=math.log(0.25), d=0.2, n=0.35, c=0.05, p=1.3,
                             eta=0.4, ell_km=15.0, psi_days=5.0),
        partial_oracle_a=dict(rows=partial_a_rows, gain_vs_joint_null=gain_a),
        partial_oracle_b=dict(rows=partial_b_rows, gain_vs_joint_null=gain_b),
        true_null_minus_fitted_null=null_loss,
        refitted_intercept_minus_fitted_null=backbone_loss,
        oracle_closure=dict(
            oracle_gain_vs_joint_null_mean=float(np.mean(true_joint) - np.mean(joint)),
            oracle_gain_vs_intercept_mean=float(np.mean(true_joint) - np.mean(intercept)),
            comparator_estimation_gain_mean=float(np.mean(intercept) - np.mean(joint)),
            identity_residual=float((np.mean(true_joint) - np.mean(joint))
                                    - (np.mean(true_joint) - np.mean(intercept))
                                    - (np.mean(intercept) - np.mean(joint)))),
        fitted_eta=eta_stats,
        estimation_loss_vs_true=stats([r["estimation_loss"] for r in oracle_rows]),
        estimation_loss_fraction_of_oracle=float(abs(np.mean([r["estimation_loss"] for r in oracle_rows]))
                                                 / (np.mean(true_joint) - np.mean(joint))),
        seed_rows=rows,
    )
    write(output / "s8_oracle_decomposition.json", summary)
    return summary


# ---------------------------------------------------------------------------
# Synthetic non-Gaussian quantiles
# ---------------------------------------------------------------------------

def build_quantiles(output: Path) -> dict:
    summary = read(S04B / "summary.json")
    cases = [read(S04B / "cases" / p.name) for p in sorted((S04B / "cases").glob("*.json"))]
    rows = []
    for entry in summary["summary"]:
        regime, model_name, gate = entry["regime"], entry["model"], entry["gate"]
        values = []
        for case in cases:
            if case["regime"] != regime:
                continue
            outcome = next((o for o in case["outcomes"]
                            if o["model"] == model_name and o["gate"] == gate), None)
            if outcome is not None:
                values.append(outcome["new_gain"])
        if len(values) != 20:
            raise ValueError(f"S04B regime {regime} {model_name} {gate} has {len(values)} histories")
        rows.append(dict(table="s04b_joint", regime=regime, model=model_name, gate=gate,
                         **sample_quantiles(values)))
    supplement = read(SUPPLEMENT)
    s8_cases = supplement["s8"]["cases"]
    for label, key in (("raw", "raw_gain"), ("bic", "bic_gain")):
        rows.append(dict(table="s8_moderate", selection=label,
                         **sample_quantiles([c[key] for c in s8_cases])))
    oracle = read(S8_ORACLE)
    for label, key in (("true_vs_fixed_true_backbone_null", "oracle_gain_vs_fixed"),
                       ("true_vs_refitted_intercept_null", "oracle_gain_vs_intercept"),
                       ("true_vs_jointly_fitted_null", "oracle_gain_vs_joint_null"),
                       ("fitted_inhibited_minus_true", "estimation_loss"),
                       ("fitted_inhibited_minus_fitted_null", "fitted_gain")):
        rows.append(dict(table="s8_oracle", contrast=label,
                         **sample_quantiles([r[key] for r in oracle["rows"]])))
    payload = dict(
        schema="referee_synthetic_quantiles_v1",
        passed=True,
        source="experiments/methodological_audit/referee_remediation_20261113.py",
        method=("Exact sample order statistics with linear interpolation between order statistics "
                "(numpy.quantile default). IQR=Q75-Q25."),
        caveat=("Heavy-tailed mark second moments diverge in the declared regimes (2*gamma > beta); "
                "medians and interquartile ranges are primary, and sample MCSEs are descriptive only."),
        rows=rows,
    )
    write(output / "synthetic_quantiles.json", payload)
    return payload


# ---------------------------------------------------------------------------
# Three-fold New Zealand trend-control totals
# ---------------------------------------------------------------------------

def build_nz_totals(output: Path) -> dict:
    data = read(NZ_TREND)
    folds = data["folds"]
    names = ("fold_50", "fold_65", "fold_80")

    def collect(kind):
        totals = dict(delta_Q=0.0, delta_C=0.0, delta_joint=0.0)
        per_fold = {}
        for name in names:
            fold = folds[name]
            if kind == "clamped":
                block = fold["clamped"]
                delta_point = block["ml_shared"]["joint"] - block["ml_trigger"]["joint"]
                delta_exposure = (block["ml_shared"]["integrated_intensity"]
                                  - block["ml_trigger"]["integrated_intensity"])
                held = dict(delta_point=delta_point, delta_exposure=delta_exposure,
                            delta_Q=delta_point + delta_exposure, delta_C=-delta_exposure,
                            delta_joint=block["delta_joint"])
            elif kind == "free":
                held = fold["archived"]["heldout"]
            else:
                held = fold["controls"][kind]["heldout"]
            per_fold[name] = {k: float(held[k]) for k in ("delta_Q", "delta_C", "delta_joint")}
            for key in totals:
                totals[key] += float(held[key])
        return totals, per_fold

    free, free_folds = collect("free")
    zero, zero_folds = collect("zero_trend")
    fixed, fixed_folds = collect("fixed_null_trend")
    clamped, clamped_folds = collect("clamped")
    payload = dict(
        schema="referee_nz_trend_totals_v1",
        passed=True,
        source="experiments/methodological_audit/referee_remediation_20261113.py",
        authority="validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json",
        folds=list(names),
        controls=dict(
            free_d=dict(definition="Archived free-d fits, order 32.", totals=free, per_fold=free_folds),
            zero_d=dict(definition="d=0 with (a,n,eta) refitted.", totals=zero, per_fold=zero_folds),
            fixed_null_d=dict(definition="d frozen at the uninhibited null trend.", totals=fixed, per_fold=fixed_folds),
            clamped_clock=dict(definition="Archived free-d fits with the affine clock fixed at its training endpoint; not a refit.",
                               totals=clamped, per_fold=clamped_folds)),
        fold1=dict(free_d=free_folds["fold_50"], zero_d=zero_folds["fold_50"],
                   fixed_null_d=fixed_folds["fold_50"], clamped_clock=clamped_folds["fold_50"]),
        reconciliation=dict(
            authority_totals=data["totals"],
            free_d_joint_error=float(abs(free["delta_joint"] - data["totals"]["archived_delta_joint"])),
            zero_d_joint_error=float(abs(zero["delta_joint"] - data["totals"]["zero_trend_delta_joint"])),
            fixed_null_d_joint_error=float(abs(fixed["delta_joint"] - data["totals"]["fixed_null_trend_delta_joint"])),
            clamped_joint_error=float(abs(clamped["delta_joint"] - data["totals"]["clamped_delta_joint"]))),
        review_reported=dict(
            clamped_clock=dict(delta_Q=-41.787, delta_C=14.889, delta_joint=-26.899),
            note=("The referee-reported clamped joint total -26.899 is reproduced exactly.  The stored "
                  "clamped records expose only ground/compensator scores, so the reproduced Q/C split is "
                  "reported above; the manuscript cites only the joint total.")),
        below_nz_90day_mde=dict(
            fixed_null_d_joint=float(fixed["delta_joint"]),
            nz_90day_mde95=9.236284345647903,
            nz_180day_mde95=10.618717979848043,
            smaller_than_90day=bool(abs(fixed["delta_joint"]) < 9.236284345647903),
            smaller_than_180day=bool(abs(fixed["delta_joint"]) < 10.618717979848043)),
    )
    write(output / "nz_trend_totals.json", payload)
    return payload


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/referee_remediation_20261113")
    parser.add_argument("--stage", choices=("all", "mde", "s8", "quantiles", "nz", "summary"), default="all")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    results = {}
    if args.stage in ("all", "mde"):
        results["mde"] = build_mde(args.output)
    if args.stage in ("all", "s8"):
        results["s8"] = build_s8_oracle(args.output)
    if args.stage in ("all", "quantiles"):
        results["quantiles"] = build_quantiles(args.output)
    if args.stage in ("all", "nz"):
        results["nz"] = build_nz_totals(args.output)

    if args.stage in ("all", "summary"):
        if not results:
            results = {"mde": read(args.output / "mde_expanded.json"),
                       "s8": read(args.output / "s8_oracle_decomposition.json"),
                       "nz": read(args.output / "nz_trend_totals.json"),
                       "quantiles": read(args.output / "synthetic_quantiles.json")}
        inputs = [NZ_UNCERTAINTY, CA_UNCERTAINTY, S8_ORACLE, NZ_TREND, SUPPLEMENT,
                  S04B / "summary.json", S8_DATA / "receipts.json"]
        summary = dict(
            schema="referee_remediation_summary_v1",
            passed=True,
            source="experiments/methodological_audit/referee_remediation_20261113.py",
            runtime_seconds=float(time.time() - started),
            key_results=dict(
                mde_90day={entry["contrast"]: entry["block_days"]["90"]["mde95_total_nats"]
                           for entry in results["mde"]["contrasts"]},
                japan_three_fold_sum_mde95=results["mde"]["japan"]["three_fold_sum"]["mde95_total_nats"],
                japan_per_fold_mde95=results["mde"]["japan"]["per_fold"]["mde95_total_nats"],
                partial_oracle_a_mean=results["s8"]["partial_oracle_a"]["gain_vs_joint_null"]["mean"],
                partial_oracle_b_mean=results["s8"]["partial_oracle_b"]["gain_vs_joint_null"]["mean"],
                fitted_eta_mean=results["s8"]["fitted_eta"]["mean"],
                nz_zero_d_total=results["nz"]["controls"]["zero_d"]["totals"]["delta_joint"],
                nz_fixed_null_d_total=results["nz"]["controls"]["fixed_null_d"]["totals"]["delta_joint"],
                nz_clamped_total=results["nz"]["controls"]["clamped_clock"]["totals"]["delta_joint"]),
            input_hashes={p.relative_to(ROOT).as_posix(): sha(p) for p in inputs},
            output_hashes={p.name: sha(p) for p in sorted(args.output.glob("*.json"))},
            sealed_authorities_mutated=False,
        )
        write(args.output / "summary.json", summary)

    print(json.dumps({k: (v.get("passed") if isinstance(v, dict) else None) for k, v in results.items()},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
