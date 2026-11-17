"""Stage P1.2: full 12-parameter joint annular EP+ optimization.

Each (case, baseline, kernel) job starts from the exact interior/bound null and
the six prescribed positive (eta, ell0, psi) starts, fits all twelve parameters
with analytic gradients, retains the exact eta=0 nested candidate, and evaluates
held-out log scores at check_power=16 over four independent Sobol scrambles.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway1_annular_attenuation import annular as A  # noqa: E402

CASES = ("california_fold_0", "california_fold_1", "california_fold_2")
POSITIVE_STARTS = (
    (0.05, 5.0, 2.0),
    (0.05, 10.0, 5.0),
    (0.1, 15.0, 5.0),
    (0.2, 20.0, 15.0),
    (0.5, 30.0, 30.0),
    (1.0, 10.0, 10.0),
)
TEST_SEEDS = (20261250, 20261251, 20261252, 20261253)


def bounds():
    out = [tuple(b) for b in A.RF.BOUNDS]
    out[5] = (math.log(0.05), math.log(100.0))
    return out


def make_start(x0, eta, ell, psi):
    x = np.asarray(x0, dtype=float).copy()
    x[8] = float(eta)
    x[9] = math.log(float(ell))
    x[10] = math.log(float(psi))
    return x


def fit_start(model, start, box, index, label="prescribed_positive"):
    started = time.time()
    base = np.asarray(start, dtype=float).copy()
    attempts = []

    def target(v):
        return model.objective(v, True)

    opt = minimize(
        target,
        base,
        jac=True,
        bounds=box,
        method="L-BFGS-B",
        options=dict(maxiter=400, maxls=100, ftol=1e-10, gtol=2e-5),
    )
    attempts.append(dict(success=bool(opt.success), message=str(opt.message),
                         nfev=int(opt.nfev), nit=int(opt.nit), nll=float(opt.fun)))
    if not opt.success:
        opt = minimize(
            target,
            opt.x,
            jac=True,
            bounds=box,
            method="L-BFGS-B",
            options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-5),
        )
        attempts.append(dict(success=bool(opt.success), message=str(opt.message),
                             nfev=int(opt.nfev), nit=int(opt.nit), nll=float(opt.fun)))
    x = np.asarray(opt.x, dtype=float).copy()
    value, grad = model.objective(x, True)
    return dict(
        start=index,
        start_kind=label,
        start_eta_ell_psi=[float(start[8]), float(math.exp(start[9])), float(math.exp(start[10]))],
        success=bool(opt.success),
        message=str(opt.message),
        nll=float(value),
        nit=int(opt.nit),
        nfev=int(opt.nfev),
        seconds=float(time.time() - started),
        parameters=[float(v) for v in x],
        eta=float(x[8]),
        ell0_km=float(math.exp(x[9])),
        psi_days=float(math.exp(x[10])),
        sigma0_km=float(math.exp(x[5])),
        gradient=[float(v) for v in grad],
        gradient_infinity_norm=float(np.max(np.abs(grad))),
        boundary_flags=[
            bool(abs(v - lo) <= 1e-8 or abs(v - hi) <= 1e-8)
            for v, (lo, hi) in zip(x, box)
        ],
        attempts=attempts,
    )


def zero_block_intervals(vm):
    from experiments.methodological_audit.score_uncertainty_cuda_frozen_v2_20261111 import resample

    out = {}
    for days in (90, 180, 365):
        edges = np.r_[np.arange(vm["start"], vm["end"], days), vm["end"]]
        block_scores = np.zeros(len(edges) - 1)
        out[str(days)] = dict(
            blocks=dict(block_days=int(days), edges=[float(v) for v in edges],
                        event_blocks=[0.0] * len(block_scores),
                        exposure_blocks=[0.0] * len(block_scores),
                        block_scores=[0.0] * len(block_scores), total=0.0),
            resample=resample(block_scores),
        )
    out["closure_error"] = 0.0
    out["gain_total"] = 0.0
    out["gain_attenuation"] = 0.0
    out["nuisance_gain"] = 0.0
    return out


def test_evaluate(bundle, selected_x, case, test_power, test_seeds):
    model = bundle["test_model"]
    x0 = bundle["x0"]
    mark = A.mark_logscore(case)
    if selected_x[8] == 0.0 and np.array_equal(selected_x, x0):
        null = model.objective(x0, False, True)
        scores = [
            dict(seed=int(seed), null=null, same_backbone_null=null, inhibited=null,
                 gain_total=0.0, gain_attenuation=0.0, nuisance_gain=0.0,
                 null_joint=float(-null["nll"] + mark),
                 inhibited_joint=float(-null["nll"] + mark))
            for seed in test_seeds
        ]
        return dict(
            scores=scores, gain_mean=0.0, gain_standard_error=0.0, gain_sd=0.0,
            attenuation_gain_mean=0.0, attenuation_gain_standard_error=0.0,
            attenuation_gain_sd=0.0, block_intervals=zero_block_intervals(bundle["vm"]),
            mark_logscore=float(mark), test_power=int(test_power),
            note="exact nested eta=0 state; held-out contrast is identically zero, no test quadrature required",
        )
    scores = []
    primary_blocks = None
    for seed in test_seeds:
        model.node_setup(x0, power=test_power, seed=seed)
        model.freeze_nodes()
        null = model.objective(x0, False, True)
        same_backbone_null_x = np.asarray(selected_x, dtype=float).copy()
        same_backbone_null_x[8] = 0.0
        same_backbone_null = model.objective(same_backbone_null_x, False, True)
        inhibited = model.objective(selected_x, True, True)
        gain_total = float(null["nll"] - inhibited["nll"])
        gain_attenuation = float(same_backbone_null["nll"] - inhibited["nll"])
        scores.append(
            dict(
                seed=int(seed),
                null=null,
                same_backbone_null=same_backbone_null,
                inhibited=inhibited,
                gain_total=gain_total,
                gain_attenuation=gain_attenuation,
                nuisance_gain=float(gain_total - gain_attenuation),
                null_joint=float(-null["nll"] + mark),
                inhibited_joint=float(-inhibited["nll"] + mark),
            )
        )
        if seed == test_seeds[0]:
            primary_blocks = A.block_uncertainty(model, selected_x)
            closure = primary_blocks["90"]["blocks"]["total"] - gain_attenuation
            if abs(closure) > 1e-6:
                raise ArithmeticError("block score does not close to the attenuation gain: " + str(closure))
            primary_blocks["closure_error"] = float(closure)
            primary_blocks["gain_total"] = float(gain_total)
            primary_blocks["gain_attenuation"] = float(gain_attenuation)
            primary_blocks["nuisance_gain"] = float(gain_total - gain_attenuation)
    total_gains = np.asarray([s["gain_total"] for s in scores], dtype=float)
    atten_gains = np.asarray([s["gain_attenuation"] for s in scores], dtype=float)
    total_sd = float(total_gains.std(ddof=1)) if len(total_gains) > 1 else 0.0
    atten_sd = float(atten_gains.std(ddof=1)) if len(atten_gains) > 1 else 0.0
    return dict(
        scores=scores,
        gain_mean=float(total_gains.mean()),
        gain_standard_error=float(total_sd / math.sqrt(len(total_gains))),
        gain_sd=total_sd,
        attenuation_gain_mean=float(atten_gains.mean()),
        attenuation_gain_standard_error=float(atten_sd / math.sqrt(len(atten_gains))),
        attenuation_gain_sd=atten_sd,
        block_intervals=primary_blocks,
        mark_logscore=float(mark),
        test_power=int(test_power),
    )


def grid_positive_start(case, baseline, kernel):
    """Seventh sensitivity start at the strongest positive P1.1 grid corner."""
    path = ROOT / "validation/live_results/pathway1_annular_20261116/stage_p11_null_profiles.json"
    if not path.exists():
        return None
    stage = json.loads(path.read_text(encoding="utf-8"))
    subset = [r for r in stage["rows"] if r["case"] == case and r["baseline"] == baseline
              and r["kernel"] == kernel and r["score_slope_total"] > 0]
    if not subset:
        return None
    best = max(subset, key=lambda r: r["score_slope_total"])
    return dict(eta=float(min(max(best["eta_hat_train_total"], 1e-6), 4.0)),
                ell=float(best["ell0_km"]), psi=float(best["psi_days"]),
                source=dict(ell0_km=best["ell0_km"], psi_days=best["psi_days"],
                            score_slope_total=best["score_slope_total"],
                            eta_hat_train_total=best["eta_hat_train_total"]))


def run_job(case, baseline, kernel, output, train_power, test_power, threads, test_seeds):
    started = time.time()
    native = A.new_native(threads=threads)
    bundle = A.build_models(case, baseline, native, train_power=train_power,
                            test_power=test_power, test_seed=test_seeds[0])
    x0 = bundle["x0"]
    tm = bundle["train_model"]
    tm.kernel = kernel
    tm.scaled = True
    box = bounds()
    null_nll = float(tm.objective(x0, False)[0])
    triplets = [(0.0, math.exp(x0[9]), math.exp(x0[10]), "exact_null")]
    triplets += [(eta, ell, psi, "prescribed_positive") for eta, ell, psi in POSITIVE_STARTS]
    if kernel == "mono":
        triplets = triplets[:3]
    extra = grid_positive_start(case, baseline, kernel)
    if extra is not None and kernel != "mono":
        triplets.append((extra["eta"], extra["ell"], extra["psi"], "grid_positive_sensitivity"))
    starts = [make_start(x0, eta, ell, psi) for eta, ell, psi, _label in triplets]
    records = [fit_start(tm, start, box, i, label) for i, (start, (_e, _l, _p, label))
               in enumerate(zip(starts, triplets))]
    valid = [r for r in records if r["success"] and math.isfinite(r["nll"])]
    if not valid:
        valid = [r for r in records if math.isfinite(r["nll"])]
    if not valid:
        raise ArithmeticError("no finite training fit")
    selected = min(valid, key=lambda r: r["nll"])
    eta_collapsed = bool(selected["eta"] < 1e-7)
    nested = bool(eta_collapsed or null_nll <= selected["nll"] + 1e-9)
    if nested:
        _null_value, _null_grad = tm.objective(x0, True)
        selected = dict(
            start=-1,
            start_kind="exact_nested_null",
            start_eta_ell_psi=[0.0, float(math.exp(x0[9])), float(math.exp(x0[10]))],
            success=True,
            message="exact eta=0 candidate retained",
            nll=float(null_nll),
            nit=0,
            nfev=1,
            seconds=0.0,
            parameters=[float(v) for v in x0],
            eta=0.0,
            ell0_km=float(math.exp(x0[9])),
            psi_days=float(math.exp(x0[10])),
            sigma0_km=float(math.exp(x0[5])),
            gradient=[float(v) for v in _null_grad],
            gradient_infinity_norm=float(np.max(np.abs(_null_grad))),
            boundary_flags=[bool(abs(v - lo) <= 1e-8 or abs(v - hi) <= 1e-8)
                            for v, (lo, hi) in zip(x0, box)],
            attempts=[],
            nested_null=True,
            eta_tolerance_collapsed=eta_collapsed,
        )
    selected_x = np.asarray(selected["parameters"], dtype=float)
    test = test_evaluate(bundle, selected_x, case, test_power, test_seeds)
    row = dict(
        case=case,
        baseline=baseline,
        kernel=kernel,
        scaled=True,
        n_train=int(len(bundle["train"]["event_time"])),
        n_test=int(len(bundle["test"]["event_time"])),
        baseline_meta=bundle["meta"],
        bounds=[list(b) for b in box],
        parameter_names=list(A.RF.NAMES),
        null_training_nll=float(null_nll),
        grid_positive_start=extra,
        records=records,
        selected=selected,
        selected_by_exact_nested_null=nested,
        training_nll_gain=float(null_nll - selected["nll"]),
        training_selected_eta=float(selected_x[8]),
        test=test,
        elapsed_seconds=float(time.time() - started),
    )
    A.write_json(output / f"joint_{case}_{baseline}_{kernel}.json", row)
    print("joint", case, baseline, kernel, "nll", selected["nll"], "eta", selected_x[8],
          "gain", test["gain_mean"], f"{time.time()-started:.1f}s", flush=True)
    return row


def merge(output, rows):
    rows.sort(key=lambda r: (r["case"], r["baseline"], r["kernel"]))
    positive = [r for r in rows if r["training_selected_eta"] > 0]
    nested = [r for r in rows if r["selected_by_exact_nested_null"]]
    by_kernel = {}
    for kernel in A.KERNELS:
        subset = [r for r in rows if r["kernel"] == kernel]
        by_kernel[kernel] = dict(
            n=len(subset),
            selected_positive_eta=sum(r["training_selected_eta"] > 0 for r in subset),
            exact_nested_null=sum(r["selected_by_exact_nested_null"] for r in subset),
            training_gain_total=float(sum(r["training_nll_gain"] for r in subset)),
            test_gain_total=float(sum(r["test"]["gain_mean"] for r in subset)),
            attenuation_gain_total=float(sum(r["test"].get("attenuation_gain_mean", 0.0) for r in subset)),
            test_gain_by_fold={r["case"] + "|" + r["baseline"]: r["test"]["gain_mean"] for r in subset},
            attenuation_gain_by_fold={r["case"] + "|" + r["baseline"]: r["test"].get("attenuation_gain_mean", 0.0) for r in subset},
            selected_eta={r["case"] + "|" + r["baseline"]: r["training_selected_eta"] for r in subset},
            selected_ell0={r["case"] + "|" + r["baseline"]: r["selected"]["ell0_km"] for r in subset},
            selected_psi={r["case"] + "|" + r["baseline"]: r["selected"]["psi_days"] for r in subset},
        )
    summary = dict(
        schema="pathway1_joint_annular_optimization_v1",
        passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=A.sha256(Path(__file__)),
        frozen_source=str(A.FROZEN.relative_to(ROOT).as_posix()),
        frozen_source_sha256=A.sha256(A.FROZEN),
        parameter_names=list(A.RF.NAMES),
        bounds=[list(b) for b in bounds()],
        positive_starts=[list(v) for v in POSITIVE_STARTS],
        test_power=16,
        test_seeds=list(TEST_SEEDS),
        n_rows=len(rows),
        n_selected_positive_eta=len(positive),
        n_exact_nested_null=len(nested),
        by_kernel=by_kernel,
        rows=rows,
    )
    A.write_json(output / "stage_p12_joint_optimization.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/pathway1_annular_20261116")
    parser.add_argument("--cases", nargs="+", default=list(CASES))
    parser.add_argument("--baselines", nargs="+", default=list(A.BASELINES))
    parser.add_argument("--kernels", nargs="+", default=list(A.KERNELS))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--train-power", type=int, default=14)
    parser.add_argument("--test-power", type=int, default=16)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(case, baseline, kernel) for case in args.cases
            for baseline in args.baselines for kernel in args.kernels]
    rows = []
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(run_job, case, baseline, kernel, args.output,
                            args.train_power, args.test_power, args.threads, TEST_SEEDS): (case, baseline, kernel)
                for case, baseline, kernel in jobs
            }
            for future in as_completed(futures):
                rows.append(future.result())
    summary = merge(args.output, rows)
    print(json.dumps({k: summary[k] for k in (
        "n_rows", "n_selected_positive_eta", "n_exact_nested_null")}, indent=2))
    print(json.dumps(summary["by_kernel"], indent=2))


if __name__ == "__main__":
    main()
