"""Stage P3.2: low-dimensional estimators on the matched S04B banks.

The primary banks are S4 (narrow/short immigrant; zero realized thinning) and
S6 (narrow/short total).  S5 and S7 are retained as positive-bank sensitivity
controls.  The archived raw eight-parameter joint-fit losses are the
comparators; the new arms use a stationary backbone and a pre-declared
three-point scale grid.
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

from experiments.s04b_joint_nuisance import model as CORE  # noqa: E402
from experiments.pathway3_low_dim_attenuation import common as C  # noqa: E402
from experiments.pathway3_low_dim_attenuation import estimators as E  # noqa: E402
from experiments.pathway3_low_dim_attenuation import native, s8  # noqa: E402
from experiments.pathway3_low_dim_attenuation.run_s8 import (  # noqa: E402
    arm_record, exact_eval, reselect_exact)

OUTPUT = C.OUT / "banks"
S04B_MANIFEST = ROOT / "reproduction/synthetic/input_manifest.json"
S04B_RESULTS = ROOT / "validation/live_results/s04b_joint_complete_20261111/cases"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    C.write_json(path, value)


def true_theta(case):
    modules = CORE.archived()
    G = modules["generator"]
    name = G.MATCHED_NAMES[case["regime"] - 4]
    _, _bg, eta, ell, psi = G.ROSTER[name]
    return np.array([math.log(0.25), 0.2, 0.35, math.log(0.05), 1.3, eta,
                     math.log(ell), math.log(psi)])


def split_phase(rows, meta, start, end, modules, nat, clock, fast):
    base = CORE.phase_from_rows(rows, meta, start, end, modules, None)
    phase = s8.Phase3(base.a, base.m, modules, nat, clock)
    if fast:
        phase.fast = True
        phase.exposure_relative_floor = 0.005
    return phase


def run_case(case):
    started = time.time()
    modules = CORE.archived()
    nat = native.NativeP3(native.build())
    clock = s8.ClockT0(760.0)
    fast = s8.load_s04b(case, clock, nat, modules=modules, fast=True)
    score = s8.load_s04b(case, clock, nat, modules=modules, fast=True,
                         spatial_order=20, time_order=24)
    ftr, fte = fast["train"], fast["test"]
    xtr, xte = score["train"], score["test"]
    truth = true_theta(case)
    archived = read(S04B_RESULTS / (case["case_id"] + ".json"))
    t0_null = np.asarray(archived["fits"]["null"]["selected"]["parameters"], dtype=float)
    t0_inh = np.asarray(archived["fits"]["LIplus_inclusive"]["selected"]["parameters"], dtype=float)
    sealed_null = float(archived["new_null_test"]["joint"])
    sealed_inh = float(next(o for o in archived["outcomes"]
                            if o["model"] == "LIplus_inclusive" and o["gate"] == "raw")["score"]["joint"])
    truth_state = dict(train=exact_eval(xtr, truth, "LIplus_inclusive", None, 16),
                       test=exact_eval(xte, truth, "LIplus_inclusive", None, 16))
    replay_null = dict(train=exact_eval(xtr, t0_null, "null", None, 16),
                       test=exact_eval(xte, t0_null, "null", None, 16))
    replay_inh = dict(train=exact_eval(xtr, t0_inh, "LIplus_inclusive", None, 16),
                      test=exact_eval(xte, t0_inh, "LIplus_inclusive", None, 16))
    t0_gain = float(replay_inh["test"]["joint"] - replay_null["test"]["joint"])

    null_fit = E.null_stationary(ftr, order=8)
    stat_null_fast = np.asarray(null_fit["selected"]["parameters"], dtype=float)
    stat_theta, stat_state, stat_nested = _nested(xtr, xte, stat_null_fast, stat_null_fast)

    meta = fast["gm"]
    first = split_phase(fast["rows"], meta, 30.0, C.S8_MID, modules, nat, clock, True)
    second_exact = split_phase(fast["rows"], meta, C.S8_MID, 395.0, modules, nat, clock, True)
    first_null_fit = E.null_stationary(first, order=8)
    first_null = np.asarray(first_null_fit["selected"]["parameters"], dtype=float)

    base = stat_theta
    fast_null_stat = ftr.evaluate(base, "null", 8)[0]["nll"]
    null_train_nll = stat_state["train"]["nll"]
    arms = {}
    grid2 = E.select_grid(ftr, base, "2p", C.S8_SCALE_GRID, order=8)
    grid2_sel, grid2_exact = reselect_exact(grid2, xtr)
    arms["E1D_Profile_2p"] = arm_record(
        ftr, xtr, xte, np.asarray(grid2_sel["selected"]["parameters"], dtype=float),
        base, fast_null_stat, null_train_nll, stat_state,
        extra=dict(scale=grid2_sel["scale"],
                   training_nll=float(grid2_exact[0][0])))
    grid3 = E.select_grid(ftr, base, "3p", C.S8_SCALE_GRID, order=8)
    grid3_sel, grid3_exact = reselect_exact(grid3, xtr)
    arms["E1D_Profile_3p"] = arm_record(
        ftr, xtr, xte, np.asarray(grid3_sel["selected"]["parameters"], dtype=float),
        base, fast_null_stat, null_train_nll, stat_state,
        extra=dict(scale=grid3_sel["scale"],
                   training_nll=float(grid3_exact[0][0])))

    split = E.fit_split_cv(ftr, first, second_exact, base, first_null,
                           grid2_sel["scale"]["ell_km"], grid2_sel["scale"]["psi_days"],
                           C.ALPHA_GRID, order=8)
    arms["E_Split_CV"] = arm_record(
        ftr, xtr, xte, np.asarray(split["parameters"], dtype=float), base,
        fast_null_stat, null_train_nll, stat_state,
        extra=dict(alpha=float(split["alpha"]),
                   first_half_eta=float(split["first_half"]["eta"]),
                   scale=split["scale"]))

    lambda_rows = {}
    for lam in C.LAMBDA_GRID:
        for per_event in (False, True):
            key = f"{lam:g}" + ("_per_event" if per_event else "")
            fit = E.fit_l1(ftr, base, "2p", grid2_sel["scale"]["ell_km"],
                           grid2_sel["scale"]["psi_days"], lam, order=8,
                           per_event=per_event)
            second = second_exact.evaluate(np.asarray(fit["parameters"], dtype=float),
                                           "LIplus_inclusive", 16)[0]
            lambda_rows[key] = dict(fit=fit, second_joint=float(second["joint"]))
    split_key, split_payload = max(lambda_rows.items(),
                                   key=lambda kv: (kv[1]["second_joint"], -kv[1]["fit"]["lam"]))
    primary = split_payload["fit"]
    arms["E_L1_Shrinkage"] = arm_record(
        ftr, xtr, xte, np.asarray(primary["parameters"], dtype=float), base,
        fast_null_stat, null_train_nll, stat_state,
        extra=dict(lam=float(primary["lam"]), per_event=bool(primary["per_event"]),
                   lambda_key=split_key, scale=primary["scale"]))

    starts7 = []
    for eta, ell, psi in ((0.4, 15.0, 5.0), (0.2, 8.0, 2.0), (0.6, 30.0, 15.0)):
        s = base.copy()
        s[5], s[6], s[7] = eta, math.log(ell), math.log(psi)
        starts7.append([s[0], s[2], s[3], s[4], s[5], s[6], s[7]])
    free7 = E.fit_free_stationary(ftr, starts7, order=8)
    arms["Free_7D_stationary"] = arm_record(
        ftr, xtr, xte, np.asarray(free7["selected"]["parameters"], dtype=float),
        base, fast_null_stat, null_train_nll, stat_state,
        extra=dict(training_nll=float(free7["selected"]["nll"])))

    references = dict(
        sealed_null=sealed_null, sealed_inhibited=sealed_inh,
        sealed_raw_gain=float(sealed_inh - sealed_null),
        replay_null=float(replay_null["test"]["joint"]),
        replay_inhibited=float(replay_inh["test"]["joint"]),
        replay_raw_gain=t0_gain,
        replay_gain_delta=float(t0_gain - (sealed_inh - sealed_null)),
        stationary_null=float(stat_state["test"]["joint"]),
        truth_test_joint=float(truth_state["test"]["joint"]),
    )
    for name, arm in arms.items():
        arm["gain_vs_archived_null"] = float(arm["test"]["joint"] - references["replay_null"])
        arm["gain_vs_stationary_null"] = float(arm["test"]["joint"] - references["stationary_null"])
        arm["gain_vs_sealed_null"] = float(arm["test"]["joint"] - sealed_null)
        arm["estimation_loss_vs_truth"] = float(arm["test"]["joint"] - references["truth_test_joint"])
        arm["raw_loss_eliminated"] = float(arm["test"]["joint"] - references["replay_null"] - t0_gain)

    row = dict(case_id=case["case_id"], regime=int(case["regime"]), seed=int(case["seed"]),
               n_train=int(case["n_train"]), n_test=int(case["n_test"]),
               realized_thinning=archived.get("thinning"),
               truth_parameters=[float(v) for v in truth],
               references=references, stationary_null=dict(parameters=[float(v) for v in stat_theta]),
               arms=arms, wall_seconds=float(time.time() - started))
    write(OUTPUT / "cases" / (case["case_id"] + ".json"), row)
    print("bank", case["case_id"],
          {k: round(v["gain_vs_stationary_null"], 2) for k, v in arms.items()},
          f"{time.time()-started:.0f}s", flush=True)
    return row


def _nested(train, test, theta, base_null, order=16):
    arm = dict(train=exact_eval(train, theta, "LIplus_inclusive", None, order),
               test=exact_eval(test, theta, "LIplus_inclusive", None, order))
    null = dict(train=exact_eval(train, base_null, "null", None, order),
                test=exact_eval(test, base_null, "null", None, order))
    if arm["train"]["nll"] >= null["train"]["nll"] - 1e-9:
        return base_null, null, True
    return theta, arm, False


def summarize(rows):
    by_regime = {}
    for regime in (4, 5, 6, 7):
        group = [r for r in rows if r["regime"] == regime]
        entry = dict(N=len(group),
                     raw_sealed_gain=C.stats([r["references"]["sealed_raw_gain"] for r in group]),
                     raw_replay_gain=C.stats([r["references"]["replay_raw_gain"] for r in group]),
                     realized_thinning=dict(
                         accepted_immigrants=int(sum((r.get("realized_thinning") or {}).get("accepted_immigrants", 0) for r in group)),
                         rejected_immigrants=int(sum((r.get("realized_thinning") or {}).get("rejected_immigrants", 0) for r in group)),
                         accepted_offspring=int(sum((r.get("realized_thinning") or {}).get("accepted_offspring", 0) for r in group)),
                         rejected_offspring=int(sum((r.get("realized_thinning") or {}).get("rejected_offspring", 0) for r in group))))
        for name in group[0]["arms"]:
            arms = [r["arms"][name] for r in group]
            good = [a["gain_vs_stationary_null"] > 0 for a in arms]
            active = [a["eta"] > 1e-8 for a in arms]
            entry[name] = dict(
                gain_vs_stationary_null=C.stats([a["gain_vs_stationary_null"] for a in arms]),
                gain_vs_archived_null=C.stats([a["gain_vs_archived_null"] for a in arms]),
                gain_vs_sealed_null=C.stats([a["gain_vs_sealed_null"] for a in arms]),
                estimation_loss_vs_truth=C.stats([a["estimation_loss_vs_truth"] for a in arms]),
                eta=C.stats([a["eta"] for a in arms]),
                nested_null=int(sum(bool(a["nested_null"]) for a in arms)),
                eta_positive=int(sum(active)),
                positive_gain=int(sum(good)),
                positive_gain_rate=float(np.mean(good)),
                positive_gain_wilson95=C.wilson(int(sum(good)), len(arms)),
                active_and_positive=int(sum(a and g for a, g in zip(active, good))),
                raw_loss_eliminated=C.stats([a["raw_loss_eliminated"] for a in arms]),
            )
        by_regime[str(regime)] = entry
    payload = dict(
        schema="pathway3_low_dim_bank_controls_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=C.sha256(Path(__file__)),
        manifest_sha256=C.sha256(S04B_MANIFEST),
        note=("S4 has zero realized thinning in the generator receipt and is used "
              "as the S4 zero-thinning null control. S6 is the primary positive total bank. "
              "S5/S7 are secondary positive controls. The S04 unit-mark Uniform/Smooth "
              "null histories are not part of the reproducible S04B corpus and are not regenerated."),
        by_regime=by_regime, rows=rows,
    )
    write(OUTPUT / "summary.json", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--regimes", nargs="+", type=int, default=[4, 5, 6, 7])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    manifest = read(S04B_MANIFEST)["s04b"]["cases"]
    manifest = [c for c in manifest if c["regime"] in args.regimes]
    if args.limit:
        manifest = manifest[:args.limit]
    OUTPUT.mkdir(parents=True, exist_ok=True)
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
    payload = summarize(rows)
    print(json.dumps({k: {kk: round(vv["gain_vs_stationary_null"]["mean"], 2)
                          for kk, vv in v.items() if isinstance(vv, dict) and "gain_vs_stationary_null" in vv}
                      for k, v in payload["by_regime"].items()}, indent=1))


if __name__ == "__main__":
    main()
