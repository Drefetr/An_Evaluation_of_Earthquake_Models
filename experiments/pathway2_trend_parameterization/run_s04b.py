"""Stage P2.2: S04B tail-outlier evaluation under T1 and T2.

Eighty sealed S04B histories (S4-S7) are refitted with the uninhibited and
``LI+ total`` arms under the stationary (T1) and origin-clamped (T2)
background laws.  The archived T0 per-case fits are the comparator.  The
primary output is the held-out gain distribution by regime, with emphasis on
the negative tail that produced the archived -592.90 / -118.24 / -178.40 /
-155.21-nat outliers.
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

from experiments.s04b_joint_nuisance import model as S8  # noqa: E402
from experiments.pathway2_trend_parameterization import background as B  # noqa: E402
from experiments.pathway2_trend_parameterization import synthetic as SY  # noqa: E402
from experiments.pathway2_trend_parameterization.native import build, NativeLaw  # noqa: E402

LAWS = ("T1", "T2")
OUTPUT = ROOT / "validation/live_results/pathway2_trend_controls_20261116/s04b"
T0_RESULTS = ROOT / "validation/live_results/s04b_joint_complete_20261111/cases"
MANIFEST = ROOT / "reproduction/synthetic/input_manifest.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def true_theta(case):
    G = S8.archived()["generator"]
    name = G.MATCHED_NAMES[case["regime"] - 4]
    _, _bg, eta, ell, psi = G.ROSTER[name]
    return np.array([math.log(0.25), 0.2, 0.35, math.log(0.05), 1.3, eta,
                     math.log(ell), math.log(psi)])


def run_case(case):
    started = time.time()
    modules = S8.archived()
    native = NativeLaw(build())
    rows, gm, base_train, base_test = SY.load_s04b_case(case, modules)
    t0 = read(T0_RESULTS / (case["case_id"] + ".json"))
    t0_null = np.asarray(t0["fits"]["null"]["selected"]["parameters"], dtype=float)
    t0_inh = np.asarray(t0["fits"]["LIplus_inclusive"]["selected"]["parameters"], dtype=float)
    t0_null_test = float(t0["new_null_test"]["joint"])
    t0_inh_test = float(next(o for o in t0["outcomes"]
                             if o["model"] == "LIplus_inclusive" and o["gate"] == "raw")["score"]["joint"])
    truth = true_theta(case)
    law0 = B.BackgroundLaw("T0", 760.0, origin=395.0, train_start=30.0, d_fixed=0.2)
    truth_test = SY.FastLawPhase(base_test, law0, native, spatial_order=20, time_order=24).evaluate(
        truth, "LIplus_inclusive", 32)[0]
    truth_train = SY.FastLawPhase(base_train, law0, native, spatial_order=20, time_order=24).evaluate(
        truth, "LIplus_inclusive", 32)[0]
    t0_null_eval = SY.FastLawPhase(base_test, law0, native, spatial_order=20, time_order=24).evaluate(
        t0_null, "null", 32)[0]
    t0_inh_eval = SY.FastLawPhase(base_test, law0, native, spatial_order=20, time_order=24).evaluate(
        t0_inh, "LIplus_inclusive", 32)[0]
    t0_eval_gain = float(t0_inh_eval["joint"] - t0_null_eval["joint"])

    arms = {}
    for kind in LAWS:
        law = B.BackgroundLaw(kind, 760.0, origin=395.0, train_start=30.0, d_fixed=0.2)
        fast = SY.FastLawPhase(base_train, law, native, spatial_order=10, time_order=6)
        null_fit = SY.fit_arm(fast, "null", kind, case["n_train"], maxiter=100,
                              n_starts=4, extra_start=SY.adapt_t0_start(kind, t0_null, "null"))
        inh_fit = SY.fit_arm(fast, "LIplus_inclusive", kind, case["n_train"],
                             null_fit["selected"]["parameters"], maxiter=100, n_starts=4,
                             extra_start=SY.adapt_t0_start(kind, t0_inh, "LIplus_inclusive"))
        null_theta = np.asarray(null_fit["selected"]["parameters"], dtype=float)
        inh_theta = np.asarray(inh_fit["selected"]["parameters"], dtype=float)
        null_tr = SY.FastLawPhase(base_train, law, native, spatial_order=20, time_order=24).evaluate(
            null_theta, "null", 32)[0]
        null_te = SY.FastLawPhase(base_test, law, native, spatial_order=20, time_order=24).evaluate(
            null_theta, "null", 32)[0]
        inh_tr = SY.FastLawPhase(base_train, law, native, spatial_order=20, time_order=24).evaluate(
            inh_theta, "LIplus_inclusive", 32)[0]
        inh_te = SY.FastLawPhase(base_test, law, native, spatial_order=20, time_order=24).evaluate(
            inh_theta, "LIplus_inclusive", 32)[0]
        arms[kind] = dict(
            law=law.describe(),
            null_fit=dict(selected=null_fit["selected"], resolved_starts=null_fit["resolved_starts"],
                          required_starts=null_fit["required_starts"]),
            inhibited_fit=dict(selected=inh_fit["selected"],
                               resolved_starts=inh_fit["resolved_starts"],
                               required_starts=inh_fit["required_starts"],
                               nested_null=inh_fit["nested_null"]),
            null_train=null_tr, null_test=null_te,
            inhibited_train=inh_tr, inhibited_test=inh_te,
            heldout_gain=float(inh_te["joint"] - null_te["joint"]),
            estimation_loss=float(inh_te["joint"] - truth_test["joint"]),
            overfitting_loss=float(truth_test["joint"] - null_te["joint"]),
            fitted_eta=float(inh_theta[5]),
            null_parameters=[float(v) for v in null_theta],
            inhibited_parameters=[float(v) for v in inh_theta],
        )
    row = dict(case_id=case["case_id"], regime=int(case["regime"]), seed=int(case["seed"]),
               n_train=int(case["n_train"]), n_test=int(case["n_test"]),
               truth_parameters=[float(v) for v in truth],
               truth_test_joint=float(truth_test["joint"]),
               truth_train_nll=float(truth_train["nll"]),
               t0=dict(null_test_joint=t0_null_test, inhibited_test_joint=t0_inh_test,
                       heldout_gain=float(t0_inh_test - t0_null_test),
                       fitted_eta=float(t0_inh[5]),
                       overfitting_loss=float(truth_test["joint"] - t0_null_test),
                       estimation_loss=float(t0_inh_test - truth_test["joint"]),
                       evaluator_gain=float(t0_eval_gain),
                       evaluator_gain_delta=float(t0_eval_gain - (t0_inh_test - t0_null_test))),
               laws=arms, wall_seconds=float(time.time() - started))
    write(OUTPUT / "cases" / (case["case_id"] + ".json"), row)
    print("s04b", case["case_id"], "T1", round(arms["T1"]["heldout_gain"], 2),
          "T2", round(arms["T2"]["heldout_gain"], 2), f"{time.time()-started:.0f}s", flush=True)
    return row


def stats(values):
    v = np.asarray(values, dtype=float)
    return dict(N=int(len(v)), mean=float(v.mean()), median=float(np.median(v)),
                sample_sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                mcse=float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else 0.0,
                wins=int(np.sum(v > 0)),
                q01=float(np.percentile(v, 1)), q05=float(np.percentile(v, 5)),
                q25=float(np.percentile(v, 25)), q75=float(np.percentile(v, 75)),
                q95=float(np.percentile(v, 95)), q99=float(np.percentile(v, 99)),
                minimum=float(v.min()), maximum=float(v.max()), values=[float(x) for x in v])


def summarize(rows):
    by_regime = {}
    for regime in (4, 5, 6, 7):
        group = [r for r in rows if r["regime"] == regime]
        by_regime[str(regime)] = dict(
            N=len(group),
            T0=dict(gain=stats([r["t0"]["heldout_gain"] for r in group]),
                    overfitting_loss=stats([r["t0"]["overfitting_loss"] for r in group]),
                    estimation_loss=stats([r["t0"]["estimation_loss"] for r in group])),
        )
        for kind in LAWS:
            by_regime[str(regime)][kind] = dict(
                gain=stats([r["laws"][kind]["heldout_gain"] for r in group]),
                overfitting_loss=stats([r["laws"][kind]["overfitting_loss"] for r in group]),
                estimation_loss=stats([r["laws"][kind]["estimation_loss"] for r in group]),
                fitted_eta=stats([r["laws"][kind]["fitted_eta"] for r in group]),
                nested_null=sum(bool(r["laws"][kind]["inhibited_fit"]["nested_null"]) for r in group),
                eta_zero=sum(abs(r["laws"][kind]["fitted_eta"]) < 1e-8 for r in group),
                null_p_at_upper_bound=sum(abs(r["laws"][kind]["null_parameters"][4] - 2.5) < 1e-8
                                          for r in group),
                null_n_at_zero=sum(abs(r["laws"][kind]["null_parameters"][2]) < 1e-8 for r in group),
            )
    # Worst tail members and their fate under each law.
    worst = sorted(rows, key=lambda r: r["t0"]["heldout_gain"])[:8]
    tail = [dict(case_id=r["case_id"], regime=r["regime"], T0=r["t0"]["heldout_gain"],
                 T1=r["laws"]["T1"]["heldout_gain"], T2=r["laws"]["T2"]["heldout_gain"]) for r in worst]
    payload = dict(
        schema="pathway2_s04b_tail_control_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=__import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest(),
        N=len(rows), laws=["T0", *LAWS],
        max_t0_evaluator_gain_delta=float(max(abs(r["t0"]["evaluator_gain_delta"]) for r in rows)),
        by_regime=by_regime, worst_t0_cases=tail,
        rows=rows,
    )
    write(OUTPUT / "summary.json", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--cases", nargs="+", default=None)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = read(MANIFEST)["s04b"]["cases"]
    if args.cases:
        manifest = [c for c in manifest if c["case_id"] in args.cases]
    if args.limit:
        manifest = manifest[:args.limit]
    rows = []
    pending = []
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for case in manifest:
                path = OUTPUT / "cases" / (case["case_id"] + ".json")
                if args.resume and path.exists():
                    rows.append(read(path))
                else:
                    pending.append(pool.submit(run_case, case))
            for future in as_completed(pending):
                rows.append(future.result())
    rows.sort(key=lambda r: (r["regime"], r["seed"]))
    if len(rows) == 80:
        summary = summarize(rows)
        print(json.dumps({k: {kk: round(v["gain"]["mean"], 3) for kk, v in vv.items()
                              if isinstance(v, dict) and "gain" in v}
                          for k, vv in summary["by_regime"].items()}, indent=1))


if __name__ == "__main__":
    main()
