"""Forensic S8 oracle decomposition (14 November 2026).

Repairs the sign interpretation of the partial-oracle contrast, adds the full
multi-start partial oracle B, and computes the complementary partial oracle C
(true generating backbone combined with each history's fitted attenuation).

The original archived decomposition remains untouched.  All new rows are
written under ``validation/live_results/forensic_remediation_20261114``.
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
sys.path.insert(0, str(ROOT))

import experiments.methodological_audit.referee_remediation_20261113 as R  # noqa: E402


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def stats(values) -> dict:
    v = np.asarray(values, dtype=float)
    return dict(N=int(len(v)), mean=float(v.mean()), median=float(np.median(v)),
                sample_sd=float(v.std(ddof=1)),
                mcse=float(v.std(ddof=1) / math.sqrt(len(v))),
                wins=int(np.sum(v > 0)), values=[float(x) for x in v])


def true_theta():
    return np.asarray(R.TRUE_THETA, dtype=float)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/forensic_remediation_20261114")
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        from experiments.s04b_joint_nuisance import model
        from experiments.s04b_completion.recover import native_library
        from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler

        run = R.load_frozen(R.S8_SOURCE, "forensic_s8_runner")
        thresholds = read(R.SUPPLEMENT)["s8"]["boundary_bounds"]
        modules = model.archived()
        native = model.Native(native_library())
        receipts = read(R.S8_DATA / "receipts.json")
        seeds = sorted(int(p.name.split(".")[0]) for p in R.S8_DATA.glob("*.npz"))
        order = [("a", "a"), ("d", "d"), ("n", "n"), ("log_c", "log_c"), ("p", "p")]
        box = [(thresholds[key]["lower"], thresholds[key]["upper"]) for _, key in order]
        lo = np.asarray([b[0] for b in box], dtype=float)
        hi = np.asarray([b[1] for b in box], dtype=float)
        star = true_theta()
        rows, partial_a, partial_b, partial_c = [], [], [], []
        for seed in seeds:
            began = time.time()
            result = read(R.S8 / str(seed) / "result.json")
            record = next(r for r in receipts if r["seed"] == seed)
            history = np.load(R.S8_DATA / f"{seed}.npz")["rows"]
            train_base = model.phase_from_rows(history, record["metadata"], 30.0, 395.0, modules, native)
            test_base = model.phase_from_rows(history, record["metadata"], 395.0, 760.0, modules, native)
            with OrderedChunkScheduler() as scheduler:
                train = run.TensorPhase(train_base.a, train_base.m, modules, native, math.inf, scheduler=scheduler)
                test = run.TensorPhase(test_base.a, test_base.m, modules, native, math.inf, scheduler=scheduler)
                backbone = np.asarray(result["fits"]["null"]["selected"]["parameters"], dtype=float)
                joint_null = float(result["null_test"]["joint"])
                fitted_atten = np.asarray(result["fits"]["LIplus_inclusive"]["selected"]["parameters"],
                                          dtype=float)[5:8]

                # Partial oracle A: fitted null backbone + true attenuation,
                # scalar intercept refitted on training data.
                def intercept_nll(a):
                    theta = R.truth_at(backbone)
                    theta[0] = float(a)
                    return float(train.evaluate(theta, "LIplus_inclusive", 16)[0]["nll"])

                opt_a = minimize_scalar(intercept_nll, bounds=(-12.0, 0.0), method="bounded",
                                        options=dict(xatol=1e-10, maxiter=320))
                theta_a = R.truth_at(backbone)
                theta_a[0] = float(opt_a.x)
                score_a = test.evaluate(theta_a, "LIplus_inclusive", 32)[0]

                # Partial oracle B: re-fit the five backbone parameters at true
                # attenuation, with the full multi-start schedule.
                a0 = float(np.clip(math.log(max(result["n_train"], 1) / 395.0 * 0.6),
                                   -11.5, -0.1))
                starts = [R.truth_at(backbone), theta_a, star.copy(),
                          np.asarray([a0, 0.0, 0.35, math.log(0.05), 1.3]),
                          np.asarray([star[0], 0.2, 0.5, math.log(0.1), 1.5])]
                fits = []
                for start in starts:
                    start = np.asarray(start, dtype=float).copy()
                    anchor = star.copy()

                    def objective(v):
                        theta = anchor.copy()
                        theta[:5] = v
                        value, gradient = train.evaluate(theta, "LIplus_inclusive", 16)
                        return float(value["nll"]), np.asarray(gradient[:5], dtype=float)

                    fit = minimize(objective, np.clip(start[:5], lo, hi), jac=True, bounds=box,
                                   method="L-BFGS-B",
                                   options=dict(maxiter=500, maxls=100, ftol=1e-10, gtol=2e-5))
                    theta = anchor.copy()
                    theta[:5] = fit.x
                    fits.append(dict(theta=theta, nll=float(fit.fun), success=bool(fit.success),
                                     nfev=int(fit.nfev), start=[float(v) for v in start[:5]]))
                best_b = min(fits, key=lambda item: item["nll"])
                theta_b = best_b["theta"]
                score_b = test.evaluate(theta_b, "LIplus_inclusive", 32)[0]
                train_b = train.evaluate(theta_b, "LIplus_inclusive", 16)[0]

                # Partial oracle C: true generating backbone (and its
                # intercept-refitted version) plus each history's fitted
                # attenuation coordinates.
                theta_c_true = star.copy()
                theta_c_true[5:8] = fitted_atten
                theta_c_intercept = theta_c_true.copy()
                theta_c_intercept[0] = float(opt_a.x)
                score_c_true = test.evaluate(theta_c_true, "LIplus_inclusive", 32)[0]
                score_c_intercept = test.evaluate(theta_c_intercept, "LIplus_inclusive", 32)[0]
                true_score = test.evaluate(star, "LIplus_inclusive", 32)[0]

            partial_a.append(dict(seed=seed, refitted_intercept_a=float(opt_a.x),
                                  test_joint=float(score_a["joint"]),
                                  gain_vs_joint_null=float(score_a["joint"] - joint_null)))
            partial_b.append(dict(
                seed=seed, parameters=[float(v) for v in theta_b],
                training_nll=float(train_b["nll"]), test_joint=float(score_b["joint"]),
                gain_vs_joint_null=float(score_b["joint"] - joint_null),
                success=best_b["success"], nfev=best_b["nfev"],
                multi_start_nll=[float(f["nll"]) for f in fits],
                start_labels=["fitted_backbone_true_atten", "refit_intercept_true_atten",
                              "true_generating_backbone", "neutral_1", "neutral_2"],
                boundaries=[bool(abs(v - b[0]) <= 1e-8 or abs(v - b[1]) <= 1e-8)
                            for v, b in zip(theta_b[:5], box)]))
            partial_c.append(dict(
                seed=seed, fitted_attenuation=[float(v) for v in fitted_atten],
                true_backbone_plus_fitted_atten_test_joint=float(score_c_true["joint"]),
                intercept_refit_plus_fitted_atten_test_joint=float(score_c_intercept["joint"]),
                true_generating_test_joint=float(true_score["joint"]),
                loss_vs_true=float(score_c_true["joint"] - true_score["joint"]),
                intercept_loss_vs_true=float(score_c_intercept["joint"] - true_score["joint"]),
                gain_vs_joint_null=float(score_c_true["joint"] - joint_null)))
            rows.append(dict(seed=seed, fitted_eta=float(result["eta"]),
                             true_joint=float(true_score["joint"]),
                             joint_null=joint_null,
                             fitted_inhibited=float(result["inhibited_test"]["joint"]),
                             refitted_intercept_minus_fitted_null=float(score_a["joint"] - joint_null),
                             true_null_minus_fitted_null=float(true_score["joint"] - joint_null)))
            print(f"s8 {seed} A={partial_a[-1]['gain_vs_joint_null']:.3f} "
                  f"B={partial_b[-1]['gain_vs_joint_null']:.3f} "
                  f"C={partial_c[-1]['loss_vs_true']:.3f} ({time.time()-began:.1f}s)", flush=True)

    oracle = read(R.S8_ORACLE)
    fixed = [r["fixed_true_backbone_null_joint"] for r in oracle["rows"]]
    intercept = [r["refitted_intercept_null_joint"] for r in oracle["rows"]]
    joint = [r["jointly_fitted_null_joint"] for r in oracle["rows"]]
    true_joint = [r["true_generating_joint"] for r in oracle["rows"]]
    gain_a = stats([r["gain_vs_joint_null"] for r in partial_a])
    gain_b = stats([r["gain_vs_joint_null"] for r in partial_b])
    loss_c = stats([r["loss_vs_true"] for r in partial_c])
    intercept_loss_c = stats([r["intercept_loss_vs_true"] for r in partial_c])
    null_minus_fitted = stats([a - b for a, b in zip(intercept, joint)])
    exact_minus_fitted = stats([a - b for a, b in zip(true_joint, joint)])
    payload = dict(
        schema="forensic_s8_oracle_decomposition_v1", passed=True,
        source="experiments/methodological_audit/forensic_s8_oracle_20261114.py",
        sign_correction=dict(
            contrast="l_test(a_hat, theta_star,0,-a) - l_test(theta_hat_0)",
            mean_nats=float(np.mean(intercept) - np.mean(joint)),
            interpretation=("Positive means the five-parameter training-fitted null comparator "
                            "scores WORSE on held-out data than the intercept-refitted true "
                            "backbone: a finite-sample overfitting loss, not an estimation gain."),
            seed_410840=dict(note="Seed 410840 contributes the -75.278-nat test-window blow-up.",
                             contrast_value=float((intercept[seeds.index(410840)]
                                                   - joint[seeds.index(410840)]))),
            other_seed_mean=float(np.mean([(intercept[i] - joint[i])
                                           for i, s in enumerate(seeds) if s != 410840])),
            median=float(np.median([intercept[i] - joint[i] for i in range(len(seeds))]))),
        definitions=dict(
            partial_oracle_a=("True attenuation on each history's fitted training null backbone "
                              "with a scalar intercept refit on training data."),
            partial_oracle_b=("True attenuation fixed; five nuisance-backbone parameters refit on "
                              "training data from five starts (fitted true-backbone, intercept-"
                              "refitted, true generating backbone and two neutral interior starts)."),
            partial_oracle_c=("True generating backbone, and its intercept-refitted version, "
                              "combined with each history's fitted (eta, log ell, log psi); the "
                              "held-out loss isolates attenuation-estimation error.")),
        partial_oracle_a=dict(rows=partial_a, gain_vs_joint_null=gain_a),
        partial_oracle_b=dict(rows=partial_b, gain_vs_joint_null=gain_b),
        partial_oracle_c=dict(rows=partial_c, loss_vs_true=loss_c,
                              intercept_loss_vs_true=intercept_loss_c),
        null_minus_fitted_stats=null_minus_fitted,
        exact_true_null_minus_fitted_stats=exact_minus_fitted,
        archived_oracle_rows=oracle["rows"],
        archived_stats=dict(oracle_gain_vs_fixed=oracle["oracle_gain_vs_fixed"],
                            oracle_gain_vs_intercept=oracle["oracle_gain_vs_intercept"],
                            oracle_gain_vs_joint_null=oracle["oracle_gain_vs_joint_null"],
                            estimation_loss=oracle["estimation_loss"]),
        closure=dict(
            oracle_gain_vs_joint_null_mean=float(np.mean(true_joint) - np.mean(joint)),
            oracle_gain_vs_intercept_mean=float(np.mean(true_joint) - np.mean(intercept)),
            comparator_overfitting_loss_mean=float(np.mean(intercept) - np.mean(joint)),
            identity_residual=float((np.mean(true_joint) - np.mean(joint))
                                    - (np.mean(true_joint) - np.mean(intercept))
                                    - (np.mean(intercept) - np.mean(joint)))))
    write(args.output / "s8_oracle.json", payload)
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "values"}
                      for k, v in dict(A=gain_a, B=gain_b, C=loss_c).items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
