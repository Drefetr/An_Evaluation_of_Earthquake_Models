"""Stage P2.1: S8 moderate control under forecast-admissible backgrounds.

Twenty sealed S8 histories are refitted with the uninhibited comparator and
the ``LI+ total`` arm under T1, T2, T3 and the true-trend control.  The
archived T0 fits are re-scored under the same evaluator and tied to the sealed
oracle rows.  Only new files under the Pathway 2 result directory are written.
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

SEEDS = tuple(range(410821, 410841))
LAWS = ("T1", "T2", "T3")
T0_LAW = "T0"
TRUE_THETA = np.array([math.log(0.25), 0.2, 0.35, math.log(0.05), 1.3, 0.4,
                       math.log(15.0), math.log(5.0)])
S8_RESULTS = ROOT / "validation/live_results/s8_moderate_complete_20261111"
S8_ORACLE = ROOT / "validation/live_results/track_b_controls_20261112/profiles_and_power/s8_oracle.json"
OUTPUT = ROOT / "validation/live_results/pathway2_trend_controls_20261116/s8"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def make_law(kind):
    return B.BackgroundLaw(kind, 760.0, origin=395.0, train_start=30.0, d_fixed=0.2)


def score_archived(base_train, base_test, law, native, theta, model, order_train=16, order_test=16):
    train = SY.LawPhase(base_train, law, native)
    test = SY.LawPhase(base_test, law, native)
    tr = train.evaluate(theta, model, order_train)[0]
    te = test.evaluate(theta, model, order_test)[0]
    return tr, te


def run_seed(seed, oracle_by_seed):
    started = time.time()
    modules = S8.archived()
    native = NativeLaw(build())
    rows, receipt, base_train, base_test = SY.load_s8_case(seed, modules, native)
    sealed = read(S8_RESULTS / str(seed) / "result.json")
    oracle = oracle_by_seed[seed]
    null_t0 = np.asarray(sealed["fits"]["null"]["selected"]["parameters"], dtype=float)
    inh_t0 = np.asarray(sealed["fits"]["LIplus_inclusive"]["selected"]["parameters"], dtype=float)

    # Exact T0 replay against the sealed phase scores.
    law0 = make_law(T0_LAW)
    t0_train = SY.LawPhase(base_train, law0, native)
    t0_test = SY.LawPhase(base_test, law0, native)
    replay_null_train = t0_train.evaluate(null_t0, "null", 8)[0]
    replay_null_test = t0_test.evaluate(null_t0, "null", 16)[0]
    replay_inh_test = t0_test.evaluate(inh_t0, "LIplus_inclusive", 16)[0]
    t0_reproduction = dict(
        null_train_nll=float(replay_null_train["nll"]),
        null_train_sealed=float(sealed["fits"]["null"]["selected"]["score"]["nll"]),
        null_train_delta=float(replay_null_train["nll"] - sealed["fits"]["null"]["selected"]["score"]["nll"]),
        null_test_joint=float(replay_null_test["joint"]),
        null_test_sealed=float(sealed["null_test"]["joint"]),
        null_test_delta=float(replay_null_test["joint"] - sealed["null_test"]["joint"]),
        inhibited_test_joint=float(replay_inh_test["joint"]),
        inhibited_test_sealed=float(sealed["inhibited_test"]["joint"]),
        inhibited_test_delta=float(replay_inh_test["joint"] - sealed["inhibited_test"]["joint"]),
    )

    true_train, true_test = score_archived(
        base_train, base_test, law0, native, TRUE_THETA, "LIplus_inclusive", 16, 16
    )
    t0 = dict(
        null_train_nll=float(sealed["fits"]["null"]["selected"]["score"]["nll"]),
        null_test_joint=float(sealed["null_test"]["joint"]),
        inhibited_train_nll=float(sealed["fits"]["LIplus_inclusive"]["selected"]["score"]["nll"]),
        inhibited_test_joint=float(sealed["inhibited_test"]["joint"]),
        fitted_gain=float(sealed["inhibited_test"]["joint"] - sealed["null_test"]["joint"]),
        true_test_joint=float(oracle["true_generating_joint"]),
        intercept_null_joint=float(oracle["refitted_intercept_null_joint"]),
        true_test_joint_this_evaluator=float(true_test["joint"]),
        true_train_nll_this_evaluator=float(true_train["nll"]),
        overfitting_loss=float(oracle["refitted_intercept_null_joint"] - sealed["null_test"]["joint"]),
        estimation_loss=float(sealed["inhibited_test"]["joint"] - oracle["true_generating_joint"]),
        fitted_eta=float(sealed["eta"]),
        oracle_sha256=__import__("hashlib").sha256(S8_ORACLE.read_bytes()).hexdigest(),
    )

    arm_rows = {}
    for kind in LAWS:
        law = make_law(kind)
        if kind == "T3":
            SY.t3_projection(SY.LawPhase(base_train, law, native), 15.0, 5.0)
        fast_train = SY.FastLawPhase(base_train, law, native)
        null_fit = SY.fit_arm(fast_train, "null", kind, receipt["n_train"], maxiter=200)
        inh_fit = SY.fit_arm(fast_train, "LIplus_inclusive", kind, receipt["n_train"],
                             null_fit["selected"]["parameters"], maxiter=200)
        null_theta = np.asarray(null_fit["selected"]["parameters"], dtype=float)
        inh_theta = np.asarray(inh_fit["selected"]["parameters"], dtype=float)
        # Archived-plan verification of the selected training state.
        null_tr, null_te = score_archived(base_train, base_test, law, native, null_theta,
                                          "null", 16, 16)
        inh_tr, inh_te = score_archived(base_train, base_test, law, native, inh_theta,
                                        "LIplus_inclusive", 16, 16)
        inh_fine = SY.FastLawPhase(base_test, law, native, spatial_order=20, time_order=24).evaluate(
            inh_theta, "LIplus_inclusive", 32)[0]
        arm_rows[kind] = dict(
            law=law.describe(),
            projection=law.projection if kind == "T3" else None,
            null_fit=dict(selected=null_fit["selected"], resolved_starts=null_fit["resolved_starts"],
                          required_starts=null_fit["required_starts"],
                          fast_training_nll=float(null_fit["selected"]["score"]["nll"])),
            inhibited_fit=dict(selected=inh_fit["selected"], resolved_starts=inh_fit["resolved_starts"],
                               required_starts=inh_fit["required_starts"],
                               nested_null=inh_fit["nested_null"],
                               fast_training_nll=float(inh_fit["selected"]["score"]["nll"])),
            null_train_archived=null_tr, null_test_archived=null_te,
            inhibited_train_archived=inh_tr, inhibited_test_archived=inh_te,
            inhibited_test_order32=inh_fine,
            test_quadrature_delta=float(abs(inh_fine["joint"] - inh_te["joint"])),
            overfitting_loss=float(oracle["refitted_intercept_null_joint"] - null_te["joint"]),
            estimation_loss=float(inh_te["joint"] - oracle["true_generating_joint"]),
            heldout_gain=float(inh_te["joint"] - null_te["joint"]),
            fitted_eta=float(inh_theta[5]),
            eta_rmse_component=float((inh_theta[5] - 0.4) ** 2),
            null_parameters=[float(v) for v in null_theta],
            inhibited_parameters=[float(v) for v in inh_theta],
        )
    # Conditional true-trend control: d = 0.2 and the T0-fitted trigger
    # nuisance held fixed in both arms.
    law = make_law("DSTAR")
    fast_train = SY.FastLawPhase(base_train, law, native)
    conditional = SY.fit_dstar_conditional(fast_train, null_t0)
    null_theta = np.asarray(conditional["null"]["parameters"], dtype=float)
    inh_theta = np.asarray(conditional["inhibited"]["parameters"], dtype=float)
    null_tr, null_te = score_archived(base_train, base_test, law, native, null_theta,
                                      "null", 16, 16)
    inh_tr, inh_te = score_archived(base_train, base_test, law, native, inh_theta,
                                    "LIplus_inclusive", 16, 16)
    inh_fine = SY.FastLawPhase(base_test, law, native, spatial_order=20, time_order=24).evaluate(
        inh_theta, "LIplus_inclusive", 32)[0]
    arm_rows["DSTAR"] = dict(
        law=law.describe(),
        projection=None,
        fixed_shared=conditional["fixed_shared"],
        null_fit=dict(selected=conditional["null"], resolved_starts=3, required_starts=3,
                      fast_training_nll=float(conditional["null"]["score"]["nll"])),
        inhibited_fit=dict(selected=conditional["inhibited"], resolved_starts=4, required_starts=4,
                           nested_null=bool(conditional["inhibited"].get("nested_null")),
                           fast_training_nll=float(conditional["inhibited"]["score"]["nll"])),
        null_train_archived=null_tr, null_test_archived=null_te,
        inhibited_train_archived=inh_tr, inhibited_test_archived=inh_te,
        inhibited_test_order32=inh_fine,
        test_quadrature_delta=float(abs(inh_fine["joint"] - inh_te["joint"])),
        overfitting_loss=float(oracle["refitted_intercept_null_joint"] - null_te["joint"]),
        estimation_loss=float(inh_te["joint"] - oracle["true_generating_joint"]),
        heldout_gain=float(inh_te["joint"] - null_te["joint"]),
        fitted_eta=float(inh_theta[5]),
        eta_rmse_component=float((inh_theta[5] - 0.4) ** 2),
        null_parameters=[float(v) for v in null_theta],
        inhibited_parameters=[float(v) for v in inh_theta],
        control_scope="d=0.2 with T0-fitted (n, log c, p) fixed in both arms",
    )
    row = dict(seed=int(seed), n_train=int(receipt["n_train"]), n_test=int(receipt["n_test"]),
               t0=t0, t0_reproduction=t0_reproduction, laws=arm_rows,
               wall_seconds=float(time.time() - started))
    write(OUTPUT / "histories" / f"{seed}.json", row)
    print("s8", seed,
          "T1", round(arm_rows["T1"]["heldout_gain"], 3),
          "T2", round(arm_rows["T2"]["heldout_gain"], 3),
          "T3", round(arm_rows["T3"]["heldout_gain"], 3),
          "D*", round(arm_rows["DSTAR"]["heldout_gain"], 3),
          f"{time.time()-started:.0f}s", flush=True)
    return row


def stats(values):
    v = np.asarray(values, dtype=float)
    return dict(N=int(len(v)), mean=float(v.mean()), median=float(np.median(v)),
                sample_sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                mcse=float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else 0.0,
                wins=int(np.sum(v > 0)),
                q25=float(np.percentile(v, 25)), q75=float(np.percentile(v, 75)),
                minimum=float(v.min()), maximum=float(v.max()), values=[float(x) for x in v])


def summarize(rows):
    by_law = {}
    for kind in (T0_LAW,) + LAWS + ("DSTAR",):
        if kind == T0_LAW:
            over = [r["t0"]["overfitting_loss"] for r in rows]
            est = [r["t0"]["estimation_loss"] for r in rows]
            gain = [r["t0"]["fitted_gain"] for r in rows]
            eta = [r["t0"]["fitted_eta"] for r in rows]
            delta = [r["t0_reproduction"]["inhibited_test_delta"] for r in rows]
            null_params = None
        else:
            over = [r["laws"][kind]["overfitting_loss"] for r in rows]
            est = [r["laws"][kind]["estimation_loss"] for r in rows]
            gain = [r["laws"][kind]["heldout_gain"] for r in rows]
            eta = [r["laws"][kind]["fitted_eta"] for r in rows]
            delta = [r["laws"][kind]["test_quadrature_delta"] for r in rows]
            null_params = [r["laws"][kind]["null_parameters"] for r in rows]
        by_law[kind] = dict(
            overfitting_loss=stats(over), estimation_loss=stats(est),
            heldout_gain=stats(gain),
            fitted_eta=dict(stats(eta),
                            rmse_vs_true=float(math.sqrt(np.mean((np.asarray(eta) - 0.4) ** 2)))),
            max_test_quadrature_delta=float(max(delta)),
            max_abs_t0_reproduction_delta=float(max(abs(v) for v in delta)) if kind == T0_LAW else None,
            null_parameters=null_params,
        )
        # BIC-gated sensitivity: 1.5 log N training-gain threshold, otherwise
        # return the exact null with zero held-out gain.
        if kind == T0_LAW:
            train_gain = [r["t0"]["null_train_nll"] - r["t0"]["inhibited_train_nll"] for r in rows]
        else:
            train_gain = [r["laws"][kind]["null_train_archived"]["nll"]
                          - r["laws"][kind]["inhibited_train_archived"]["nll"] for r in rows]
        threshold = [1.5 * math.log(max(r["n_train"], 1)) for r in rows]
        gated = [g if tg > th else 0.0 for g, tg, th in zip(gain, train_gain, threshold)]
        by_law[kind]["bic_gated_gain"] = stats(gated)
        by_law[kind]["bic_gate_active"] = int(sum(tg > th for tg, th in zip(train_gain, threshold)))
    # Seed-by-seed deltas against T0.
    deltas = {}
    for kind in LAWS + ("DSTAR",):
        deltas[kind] = dict(
            overfitting_loss_change=[r["laws"][kind]["overfitting_loss"] - r["t0"]["overfitting_loss"] for r in rows],
            estimation_loss_change=[r["laws"][kind]["estimation_loss"] - r["t0"]["estimation_loss"] for r in rows],
            gain_change=[r["laws"][kind]["heldout_gain"] - r["t0"]["fitted_gain"] for r in rows],
        )
        deltas[kind] = {k: stats(v) for k, v in deltas[kind].items()}
    seed_410840 = next(r for r in rows if r["seed"] == 410840)
    payload = dict(
        schema="pathway2_s8_moderate_control_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=__import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest(),
        seeds=[int(s) for s in SEEDS], laws=[T0_LAW, *LAWS, "DSTAR"],
        true_parameters=[float(v) for v in TRUE_THETA],
        primary_definition=dict(
            overfitting_loss="l_test(a_hat, theta_star,0,-a) - l_test(theta_hat_0), positive = fitted null worse",
            estimation_loss="l_test(theta_hat_1) - l_test(theta_star); theta_star scored under T0 at order 32",
            heldout_gain="l_test(theta_hat_1) - l_test(theta_hat_0)",
        ),
        by_law=by_law, deltas_vs_t0=deltas,
        seed_410840={k: seed_410840[k] for k in ("t0", "laws")},
        t0_reproduction_max_abs={
            "null_train": float(max(abs(r["t0_reproduction"]["null_train_delta"]) for r in rows)),
            "null_test": float(max(abs(r["t0_reproduction"]["null_test_delta"]) for r in rows)),
            "inhibited_test": float(max(abs(r["t0_reproduction"]["inhibited_test_delta"]) for r in rows)),
        },
        rows=rows,
    )
    write(OUTPUT / "summary.json", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    oracle = {r["seed"]: r for r in read(S8_ORACLE)["rows"]}
    rows = []
    pending = []
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for seed in args.seeds:
                path = OUTPUT / "histories" / f"{seed}.json"
                if args.resume and path.exists():
                    rows.append(read(path))
                else:
                    pending.append(pool.submit(run_seed, seed, oracle))
            for future in as_completed(pending):
                rows.append(future.result())
    rows.sort(key=lambda r: r["seed"])
    if len(rows) == len(SEEDS):
        summary = summarize(rows)
        print(json.dumps({k: {kk: round(vv["mean"], 3) for kk, vv in v.items()
                              if isinstance(vv, dict) and "mean" in vv}
                          for k, v in summary["by_law"].items()}, indent=1))


if __name__ == "__main__":
    main()
