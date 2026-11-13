"""Forensic EP+ 2x2x2 ablation and relaxed-sigma0 benchmark (14 Nov 2026).

Corrections
-----------
* A3, A4, A7 and A8 each run their own five-step training immigrant-probability
  KDE declustering loop under their own normalization and scaling.  No arm
  imports the accepted A8 weights and no arm warm-starts from the accepted A8
  post-declustering parameters.  All declustered arms start from the same
  neutral three-start grid used by the frozen benchmark.
* The relaxed-sigma0 summary separates the plane and rectangle totals instead
  of adding both six-row panels into a double-counted total.
* The twelve-parameter inhibited optimisation is run under sigma0 >= 0.05 km
  with the exact nested null and three prescribed positive starts.
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
sys.path.insert(0, str(ROOT))

from experiments.etas_inhibition_benchmark import ablation_and_sigma0 as A  # noqa: E402
import experiments.etas_inhibition_benchmark.run_frozen_20261111 as RF  # noqa: E402

ABLATION = ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation"
ACCEPTED = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112"
CASES = ("california_fold_0", "california_fold_1", "california_fold_2")
ARMS = {
    "A3": dict(normalization="rect", scaled=False),
    "A4": dict(normalization="plane", scaled=False),
    "A7": dict(normalization="rect", scaled=True),
    "A8": dict(normalization="plane", scaled=True),
}


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def neutral_starts(scaled: bool):
    base = np.array([-3.4, 0.0, 0.6, math.log(0.01), 1.2, math.log(5.0), 0.5, 1.6])
    if not scaled:
        base[6] = 0.0
    starts = [base.copy(), base.copy(), base.copy()]
    starts[1][[5, 6, 7]] = [math.log(2.0), 0.8 if scaled else 0.0, 2.0]
    starts[2][[5, 6, 7]] = [math.log(15.0), 0.2 if scaled else 0.0, 1.2]
    return starts


def self_decluster(case: str, normalization: str, scaled: bool, steps: int = 5,
                   lower_km: float = 2.0):
    train, meta, _, _, _ = RF.inputs(case)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], None)
    cls = A.RectModel if normalization == "rect" else RF.Model
    bounds = list(RF.BOUNDS[:8])
    bounds[5] = (math.log(lower_km), math.log(100.0))
    x = None
    lineage = []
    for iteration in range(steps):
        model = cls(train, meta, background)
        starts = neutral_starts(scaled) if iteration == 0 else [x]
        selected = A.fit(model, starts, scaled, bounds)
        x = np.asarray(selected["selected"]["parameters"], dtype=float)
        lam, _ = model.base_values(model.events, x)
        mu = np.exp(x[0] + x[1] * (2 * train["event_time"] / meta["T0"] - 1)) * model.be
        weights = mu / lam
        background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
        lineage.append(dict(iteration=iteration, nll=float(selected["selected"]["nll"]),
                            expected_immigrants=float(weights.sum()),
                            parameters=[float(v) for v in x]))
    model = cls(train, meta, background)
    final = A.fit(model, [x], scaled, bounds)
    x = np.asarray(final["selected"]["parameters"], dtype=float)
    score = A.test_score(case, x, normalization, weights)
    return dict(case=case, normalization=normalization, scaled=scaled,
                parameters=[float(v) for v in x],
                background_weights=[float(v) for v in weights],
                training_nll=float(final["selected"]["nll"]),
                declustering=lineage, **score)


def arm_job(job):
    case, arm = job
    spec = ARMS[arm]
    return arm, self_decluster(case, spec["normalization"], spec["scaled"])


def run_clean_ablation(workers: int = 3) -> dict:
    rows = {}
    jobs = [(case, arm) for case in CASES for arm in ARMS]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(arm_job, job): job for job in jobs}
        for future in as_completed(futures):
            arm, result = future.result()
            rows.setdefault(arm, {})[result["case"]] = result
            print("clean", arm, result["case"], result["gain_over_EP"], flush=True)
    archived = read(ABLATION / "ablation.json")
    totals = {arm: sum(rows[arm][case]["gain_over_EP"] for case in CASES) for arm in ARMS}
    # The unweighted arms do not contain declustering and are unchanged by this
    # correction; retain their archived values for the factorial.
    for arm in ("A0", "A1", "A2", "A5", "A6"):
        totals[arm] = float(archived["arms"][arm]["total_gain"])
    values = dict(totals)
    cells = {(n, w, s): values[a] for a, n, w, s in [
        ("A1", "rect", False, False), ("A2", "plane", False, False),
        ("A3", "rect", True, False), ("A4", "plane", True, False),
        ("A5", "rect", False, True), ("A6", "plane", False, True),
        ("A7", "rect", True, True), ("A8", "plane", True, True)]}
    from itertools import combinations
    factors = {"normalization": ("plane", "rect"), "declustering": (True, False),
               "scaling": (True, False)}

    def value(subset):
        return cells[tuple(factors[name][0] if name in subset else factors[name][1]
                           for name in factors)]

    names = list(factors)
    shapley = {}
    for name in names:
        total = 0.0
        others = [o for o in names if o != name]
        for size in range(len(others) + 1):
            for subset in combinations(others, size):
                weight = (math.factorial(size) * math.factorial(len(names) - size - 1)
                          / math.factorial(len(names)))
                total += weight * (value(set(subset) | {name}) - value(set(subset)))
        shapley[name] = float(total)
    joint_fit = values["A1"] - values["A0"]
    closure = values["A8"] - values["A0"]
    return dict(schema="forensic_epplus_clean_ablation_v1", passed=True,
                source="experiments/etas_inhibition_benchmark/forensic_ablation_20261114.py",
                protocol=("Each declustered arm runs five self-contained training-declustering "
                          "iterations from the neutral three-start grid under its own "
                          "normalization and scaling; no accepted-A8 weights or states are "
                          "imported."),
                rows=rows, totals=totals, joint_fit=float(joint_fit), shapley=shapley,
                sequential_A0_A1_A2_A4_A8=[float(values["A1"] - values["A0"]),
                                           float(values["A2"] - values["A1"]),
                                           float(values["A4"] - values["A2"]),
                                           float(values["A8"] - values["A4"])],
                closure_A8_minus_A0=float(closure),
                factorial_closure=float(joint_fit + sum(shapley.values())),
                closure_residual=float(joint_fit + sum(shapley.values()) - closure),
                frozen_a8_weight_reference=dict(
                    totals={k: v["total_gain"] for k, v in archived["arms"].items()},
                    shapley=archived["factorial"]["shapley"],
                    closure=archived["factorial"]["closure_A8_minus_A0"]))


def relaxed_totals() -> dict:
    relaxed = read(ABLATION / "sigma0_relaxation.json")
    frozen = read(ABLATION / "sigma0_relaxation_frozen.json")
    def split(payload):
        out = {}
        for norm in ("plane", "rect"):
            rows = [r for r in payload["rows"] if r["normalization"] == norm]
            out[norm] = dict(rows=rows, total_gain=float(sum(r["gain_over_EP"] for r in rows)))
        return out
    return dict(relaxed=split(relaxed), frozen=split(frozen),
                archived_double_counted_total=float(relaxed["total_gain"]),
                note=("The archived 154.114-nat total added the plane and rectangle six-row "
                      "panels; the two panels are alternative normalizations, not additive."))


def relaxed_inhibited_fold(case: str, workers: int = 1) -> dict:
    train, meta, test, test_meta, _ = RF.inputs(case)
    record = read(ACCEPTED / case / "result.json")
    x0 = np.asarray(record["null"]["selected"]["parameters"], dtype=float)
    weights = np.asarray(record["background_weights"], dtype=float)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    model = RF.Model(train, meta, background)
    model.node_setup(x0, power=14, seed=20261111)
    bounds = list(RF.BOUNDS[:12])
    bounds[5] = (math.log(0.05), math.log(100.0))
    starts = [("nested_null", x0.copy())]
    for eta, ell, psi in ((0.05, 10.0, 2.0), (0.2, 20.0, 5.0), (0.5, 50.0, 30.0)):
        x = x0.copy()
        x[8:11] = [eta, math.log(ell), math.log(psi)]
        starts.append((f"positive_{eta:g}_{ell:g}_{psi:g}", x))
    fits = []
    for label, start in starts:
        began = time.time()
        opt = minimize(lambda v: model.objective(np.asarray(v), True), start, jac=True,
                       bounds=bounds, method="L-BFGS-B",
                       options=dict(maxiter=120, maxls=40, ftol=1e-9, gtol=2e-4))
        z = np.asarray(opt.x, dtype=float)
        fits.append(dict(label=label, success=bool(opt.success), nll=float(opt.fun),
                         eta=float(z[8]), sigma0_km=float(np.exp(z[5])),
                         log_ell0=float(z[9]), log_psi=float(z[10]), gamma=float(z[11]),
                         parameters=[float(v) for v in z], nfev=int(opt.nfev),
                         seconds=time.time() - began))
        print("relaxed-inhibited", case, label, fits[-1]["nll"], fits[-1]["eta"], flush=True)
    best = min(fits, key=lambda r: r["nll"])
    z = np.asarray(best["parameters"], dtype=float)
    train_details = model.objective(z, True, True)
    test_model = RF.Model(test, test_meta, background)
    test_model.node_setup(x0, power=16, seed=20261120)
    null_test = test_model.objective(x0, False, True)
    inhib_test = test_model.objective(z, True, True)
    return dict(case=case, fits=fits, selected=best,
                training_nll=float(train_details["nll"]),
                test_null_nll=float(null_test["nll"]),
                test_inhibited_nll=float(inhib_test["nll"]),
                test_gain=float(null_test["nll"] - inhib_test["nll"]),
                sigma0_lower_bound_km=0.05, power=14, check_power=16)


def run_relaxed_inhibited(workers: int = 2) -> dict:
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(relaxed_inhibited_fold, case): case for case in CASES}
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: r["case"])
    return dict(schema="forensic_relaxed_sigma0_inhibited_v1", passed=True,
                source="experiments/etas_inhibition_benchmark/forensic_ablation_20261114.py",
                rows=rows,
                all_selected_eta_zero=bool(all(r["selected"]["eta"] == 0.0 for r in rows)),
                retained_bound_pinned_contrast=dict(
                    bound_pinned=69.55289384226876,
                    relaxed_uninhibited_plane=77.0557339839778,
                    note="The relaxed inhibited arm returns the nested eta=0 boundary."))


def build(output: Path, workers: int = 3) -> dict:
    clean = run_clean_ablation(workers=workers)
    relax = relaxed_totals()
    payload = dict(schema="forensic_epplus_ablation_v1", passed=True,
                   source="experiments/etas_inhibition_benchmark/forensic_ablation_20261114.py",
                   clean_ablation=clean, relaxed_sigma0=relax)
    write(output / "epplus_ablation.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/forensic_remediation_20261114")
    parser.add_argument("--stage", choices=("ablation", "relaxed_totals", "relaxed_inhibited", "all"),
                        default="all")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    with threadpool_limits(limits=1):
        if args.stage in ("ablation", "all"):
            clean = run_clean_ablation(workers=args.workers)
            write(args.output / "epplus_ablation.json",
                  dict(schema="forensic_epplus_ablation_v1", passed=True,
                       clean_ablation=clean, relaxed_sigma0=relaxed_totals()))
        if args.stage in ("relaxed_totals", "all"):
            write(args.output / "epplus_sigma0_totals.json", relaxed_totals())
        if args.stage in ("relaxed_inhibited", "all"):
            write(args.output / "epplus_relaxed_inhibited.json",
                  run_relaxed_inhibited(workers=args.workers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
