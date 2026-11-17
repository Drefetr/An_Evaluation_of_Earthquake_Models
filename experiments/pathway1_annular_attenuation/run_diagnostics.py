"""Stage P1.1: null score slopes and eta profiles for annular kernels.

Runs the exact analytic null score derivative and the power=14 training profile
over the full (ell0, psi) grid for every California fold, kernel and scaling,
against both the interior-scale and bound-pinned EP+ baselines. Held-out
contrasts use the frozen check_power=16 test proposal (seed 20261120).

Each (fold, baseline) job writes one JSON shard; the parent merges shards into
``stage_p11_null_profiles.json`` and always leaves the source hash pins.
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
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway1_annular_attenuation import annular as A  # noqa: E402
from experiments.pathway1_annular_attenuation.native import DEFAULT_OUTPUT as NATIVE_BUILD  # noqa: E402

CASES = ("california_fold_0", "california_fold_1", "california_fold_2")


def run_job(case, baseline, output, train_power, test_power, test_seed, threads):
    started = time.time()
    native = A.new_native(threads=threads)
    bundle = A.build_models(
        case,
        baseline,
        native,
        train_power=train_power,
        test_power=test_power,
        train_seed=20261111,
        test_seed=test_seed,
    )
    x0 = bundle["x0"]
    tm = bundle["train_model"]
    vm = bundle["test_model"]
    null_nll = float(tm.objective(x0, False)[0])

    rows = []
    for kernel in A.KERNELS:
        for scaled in (True, False):
            tm.kernel = kernel
            tm.scaled = scaled
            vm.kernel = kernel
            vm.scaled = scaled
            for ell in A.ELL_GRID_KM:
                for psi in A.PSI_GRID_DAYS:
                    x = x0.copy()
                    x[8] = 0.0
                    x[9] = math.log(ell)
                    x[10] = math.log(psi)
                    summary = A.stage_summary(tm, x)
                    test = A.heldout_profile(
                        vm, x, summary["eta_hat_train_total"], summary["eta_hat_train_immigrant"]
                    )
                    row = dict(
                        case=case,
                        baseline=baseline,
                        kernel=kernel,
                        scaled=bool(scaled),
                        ell0_km=float(ell),
                        psi_days=float(psi),
                        null_training_nll=float(null_nll),
                        **{k: v for k, v in summary.items() if not k.startswith("_")},
                        **{k: v for k, v in test.items() if not k.startswith("_")},
                    )
                    row["delta_train_max_total"] = float(row["delta_train_max_total"])
                    row["delta_test_total"] = float(row["delta_test_total"])
                    rows.append(row)
            print(
                "diag",
                case,
                baseline,
                kernel,
                "scaled" if scaled else "unscaled",
                "positive_total",
                sum(1 for r in rows[-42:] if r["score_slope_total"] > 0),
                "best_total",
                max(r["score_slope_total"] for r in rows[-42:]),
                flush=True,
            )
    shard = dict(
        case=case,
        baseline=baseline,
        rows=rows,
        baseline_meta=bundle["meta"],
        n_train=int(len(bundle["train"]["event_time"])),
        n_test=int(len(bundle["test"]["event_time"])),
        training_proposal=dict(power=train_power, seed=20261111),
        test_proposal=dict(power=test_power, seed=test_seed),
        elapsed_seconds=float(time.time() - started),
        source_pin=A.sha256(A.FROZEN),
        native_build=json.loads((NATIVE_BUILD / "build_receipt.json").read_text()),
    )
    A.write_json(output / f"shard_{case}_{baseline}.json", shard)
    return shard


def integration_check(case, baseline, output, threads):
    """Independent scrambles and a higher-power reference at the headline state."""
    native = A.new_native(threads=threads)
    checks = []
    for train_power, test_power, train_seed, test_seed, label in [
        (14, 16, 20261111, 20261120, "primary"),
        (14, 16, 20261112, 20261121, "independent_scramble"),
        (16, 18, 20261113, 20261122, "high_power_reference"),
    ]:
        bundle = A.build_models(
            case,
            baseline,
            native,
            train_power=train_power,
            test_power=test_power,
            train_seed=train_seed,
            test_seed=test_seed,
        )
        x0 = bundle["x0"]
        tm = bundle["train_model"]
        vm = bundle["test_model"]
        for kernel in A.KERNELS:
            for scaled in (True, False):
                tm.kernel = kernel
                tm.scaled = scaled
                vm.kernel = kernel
                vm.scaled = scaled
                x = x0.copy()
                x[8] = 0.0
                x[9] = math.log(15.0)
                x[10] = math.log(5.0)
                s = A.stage_summary(tm, x)
                h = A.heldout_profile(vm, x, s["eta_hat_train_total"], s["eta_hat_train_immigrant"])
                checks.append(dict(
                    case=case,
                    baseline=baseline,
                    label=label,
                    train_power=train_power,
                    test_power=test_power,
                    train_seed=train_seed,
                    test_seed=test_seed,
                    kernel=kernel,
                    scaled=bool(scaled),
                    ell0_km=15.0,
                    psi_days=5.0,
                    event_sum=s["event_sum"],
                    exposure_integral=s["exposure_integral"],
                    score_slope_total=s["score_slope_total"],
                    score_slope_immigrant=s["score_slope_immigrant"],
                    eta_hat_train_total=s["eta_hat_train_total"],
                    delta_train_max_total=s["delta_train_max_total"],
                    delta_test_total=h["delta_test_total"],
                ))
        print("integration", case, baseline, label, flush=True)
    # Pairwise differences relative to the primary baseline.
    primary = {(r["kernel"], r["scaled"]): r for r in checks if r["label"] == "primary"}
    for row in checks:
        base = primary[(row["kernel"], row["scaled"])]
        row["slope_difference_vs_primary"] = float(row["score_slope_total"] - base["score_slope_total"])
        row["exposure_difference_vs_primary"] = float(row["exposure_integral"] - base["exposure_integral"])
    A.write_json(output / f"integration_check_{case}_{baseline}.json", dict(
        case=case, baseline=baseline, rows=checks,
        note="Primary uses the frozen power=14 train / power=16 test proposal. Independent scrambles and a power=18/20 reference quantify quadrature error only at the headline state (ell0=15 km, psi=5 d).",
    ))
    return checks


def read_integration_checks(output, jobs):
    rows = []
    for case, baseline in jobs:
        path = output / f"integration_check_{case}_{baseline}.json"
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["rows"]:
            tagged = dict(row)
            tagged["case"] = case
            tagged["baseline"] = baseline
            rows.append(tagged)
    return rows


def merge(output, shards, checks):
    rows = []
    for shard in shards:
        rows.extend(shard["rows"])
    rows.sort(key=lambda r: (r["case"], r["baseline"], r["kernel"], not r["scaled"], r["ell0_km"], r["psi_days"]))
    positive_total = [r for r in rows if r["score_slope_total"] > 0]
    positive_imm = [r for r in rows if r["score_slope_immigrant"] > 0]
    best_total = max(rows, key=lambda r: r["score_slope_total"])
    best_imm = max(rows, key=lambda r: r["score_slope_immigrant"])
    best_delta = max(rows, key=lambda r: r["delta_train_max_total"])
    summary = dict(
        schema="pathway1_null_score_profiles_v1",
        passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=A.sha256(Path(__file__)),
        frozen_source=str(A.FROZEN.relative_to(ROOT).as_posix()),
        frozen_source_sha256=A.sha256(A.FROZEN),
        kernels=list(A.KERNELS),
        baselines=list(A.BASELINES),
        ell_grid_km=list(A.ELL_GRID_KM),
        psi_grid_days=list(A.PSI_GRID_DAYS),
        eta_grid=list(A.ETA_GRID),
        training_power=14,
        test_power=16,
        training_seed=20261111,
        test_seed=20261120,
        n_rows=len(rows),
        positive_total_slope_rows=len(positive_total),
        positive_immigrant_slope_rows=len(positive_imm),
        best_total_slope=best_total,
        best_immigrant_slope=best_imm,
        best_training_delta=best_delta,
        integration_checks=checks,
        shards=[dict(case=s["case"], baseline=s["baseline"], n_rows=len(s["rows"]),
                     elapsed_seconds=s["elapsed_seconds"], baseline_meta=s["baseline_meta"],
                     training_proposal=s["training_proposal"], test_proposal=s["test_proposal"])
                for s in shards],
        rows=rows,
    )
    A.write_json(output / "stage_p11_null_profiles.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/pathway1_annular_20261116")
    parser.add_argument("--cases", nargs="+", default=list(CASES))
    parser.add_argument("--baselines", nargs="+", default=list(A.BASELINES))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--train-power", type=int, default=14)
    parser.add_argument("--test-power", type=int, default=16)
    parser.add_argument("--test-seed", type=int, default=20261120)
    parser.add_argument("--skip-integration", action="store_true")
    parser.add_argument("--integration-only", action="store_true")
    parser.add_argument("--merge-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(case, baseline) for case in args.cases for baseline in args.baselines]
    if args.merge_only:
        shards = [json.loads((args.output / f"shard_{case}_{baseline}.json").read_text(encoding="utf-8"))
                  for case, baseline in jobs]
        checks = read_integration_checks(args.output, jobs)
        if not checks:
            checks_path = args.output / "integration_checks_all.json"
            checks = json.loads(checks_path.read_text(encoding="utf-8"))["rows"] if checks_path.exists() else []
        summary = merge(args.output, shards, checks)
        print(json.dumps({k: summary[k] for k in (
            "n_rows", "positive_total_slope_rows", "positive_immigrant_slope_rows")}, indent=2))
        return
    if args.integration_only:
        checks = []
        with ProcessPoolExecutor(max_workers=min(2, args.workers, len(jobs))) as pool:
            futures = {pool.submit(integration_check, case, baseline, args.output, args.threads): (case, baseline)
                       for case, baseline in jobs}
            for future in as_completed(futures):
                checks.extend(future.result())
        A.write_json(args.output / "integration_checks_all.json", dict(
            schema="pathway1_integration_checks_v1",
            rows=checks,
            note="Primary is the frozen power=14/16 proposal; independent scrambles and a power=16/18 reference quantify quadrature error at ell0=15 km, psi=5 d.",
        ))
        print(json.dumps(dict(n_checks=len(checks)), indent=2))
        return
    shards = []
    checks = []
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(run_job, case, baseline, args.output,
                            args.train_power, args.test_power, args.test_seed, args.threads): (case, baseline)
                for case, baseline in jobs
            }
            for future in as_completed(futures):
                shard = future.result()
                shards.append(shard)
                print("completed", shard["case"], shard["baseline"], shard["elapsed_seconds"], flush=True)
        if not args.skip_integration:
            with ProcessPoolExecutor(max_workers=min(2, args.workers, len(jobs))) as pool:
                futures = {pool.submit(integration_check, case, baseline, args.output, args.threads): (case, baseline)
                           for case, baseline in jobs}
                for future in as_completed(futures):
                    checks.extend(future.result())
    summary = merge(args.output, shards, checks)
    print(json.dumps({k: summary[k] for k in (
        "n_rows", "positive_total_slope_rows", "positive_immigrant_slope_rows")}, indent=2))


if __name__ == "__main__":
    main()
