"""Stage P3.1: stepwise degree-of-freedom ladder on the 20 S8 histories.

The ladder moves from the full generating truth down to the archived
eight-parameter free fit, then evaluates the four Pathway 3 estimators:

    E_1D_Profile    (a, eta) and (a, n, eta) on a three-point physical grid
    E_L1_Shrinkage  literal mean-stress penalty and a per-event sensitivity
    E_Split_CV      within-training chronological shrinkage of eta
    E_WC_Rupture    Wells-Coppersmith per-parent rupture length (sensitivity)

Optimisation uses the frozen tensor-Gauss fast plan.  Every reported score is
re-evaluated on the archived adaptive plan at order 16; the truth is also
evaluated at order 32.  Only new files under the Pathway 3 result directory
are written.
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

OUTPUT = C.OUT / "s8"
S8_RESULTS = ROOT / "validation/live_results/s8_moderate_complete_20261111"
S8_ORACLE = ROOT / "validation/live_results/track_b_controls_20261112/profiles_and_power/s8_oracle.json"
M0 = 3.0
WC_PSI = 5.0


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    C.write_json(path, value)


def wc_ell(parent_excess):
    """Wells-Coppersmith subsurface rupture length in km."""
    return 10.0 ** (-2.44 + 0.59 * (M0 + np.asarray(parent_excess, dtype=float)))


def exact_eval(phase, theta, model, ell2, order=16):
    return phase.evaluate(np.asarray(theta, dtype=float), model, order, ell2=ell2)[0]


def reselect_exact(grid, train, order=16):
    """Re-rank grid candidates on the archived training plan."""
    rows = []
    for candidate in grid["candidates"]:
        theta = np.asarray(candidate["selected"]["parameters"], dtype=float)
        value = train.evaluate(theta, "LIplus_inclusive", order)[0]
        rows.append((float(value["nll"]), candidate))
    rows.sort(key=lambda item: (item[0], item[1]["scale"]["ell_km"]))
    return rows[0][1], rows


def arm_record(fast_train, exact_train, exact_test, theta, base_null,
               fast_null_nll, exact_null_train_nll, exact_null_test,
               ell2=None, ell2_test=None, extra=None, order=16):
    """Nested selection on the fast plan; exact re-score of the frozen state."""
    theta = np.asarray(theta, dtype=float)
    fast_arm = fast_train.evaluate(theta, "LIplus_inclusive", 8, ell2=ell2)[0]
    nested_fast = float(theta[5]) < 1e-8 or fast_arm["nll"] >= fast_null_nll - 1e-9
    if nested_fast:
        theta = np.asarray(base_null, dtype=float).copy()
    train_state = exact_eval(exact_train, theta, "LIplus_inclusive", ell2, order)
    nested_exact = train_state["nll"] >= exact_null_train_nll - 1e-9
    if nested_exact:
        theta = np.asarray(base_null, dtype=float).copy()
        train_state = dict(exact_null_test["train"])
        test_state = dict(exact_null_test["test"])
    else:
        test_state = exact_eval(exact_test, theta, "LIplus_inclusive",
                                ell2_test if ell2_test is not None else ell2, order)
    out = dict(parameters=[float(v) for v in theta],
               train=train_state, test=test_state,
               nested_null=bool(nested_fast or nested_exact),
               nested_fast=bool(nested_fast), nested_exact=bool(nested_exact),
               eta=float(theta[5]),
               ell_km=(None if ell2 is not None else float(math.exp(theta[6]))),
               psi_days=float(math.exp(theta[7])),
               ell2=("wells_coppersmith" if ell2 is not None else "global"))
    if ell2 is not None:
        out["wc_ell_km"] = dict(
            minimum=float(np.min(ell2)), maximum=float(np.max(ell2)),
            at_M4=float(10.0 ** (-2.44 + 0.59 * 4.0)),
            at_M5=float(10.0 ** (-2.44 + 0.59 * 5.0)),
            at_M6=float(10.0 ** (-2.44 + 0.59 * 6.0)),
            at_M7=float(10.0 ** (-2.44 + 0.59 * 7.0)))
    if extra:
        out.update(extra)
    return out


def refit_intercept(train, truth, order=16):
    from scipy.optimize import minimize_scalar

    theta = np.asarray(truth, dtype=float).copy()
    theta[5] = 0.0

    def target(a):
        trial = theta.copy()
        trial[0] = float(a)
        return float(train.evaluate(trial, "null", order)[0]["nll"])

    opt = minimize_scalar(target, bounds=(-12.0, 0.0), method="bounded",
                          options=dict(xatol=1e-10, maxiter=200))
    theta[0] = float(opt.x)
    return theta, float(opt.fun)


def split_phase(rows, meta, start, end, modules, nat, clock, fast):
    base = CORE.phase_from_rows(rows, meta, start, end, modules, None)
    phase = s8.Phase3(base.a, base.m, modules, nat, clock)
    if fast:
        phase.fast = True
        phase.exposure_relative_floor = 0.005
    return phase


def run_seed(seed):
    started = time.time()
    modules = CORE.archived()
    nat = native.NativeP3(native.build())
    clock = s8.ClockT0(760.0)
    fast = s8.load_s8(seed, clock, nat, modules=modules, fast=True)
    score = s8.load_s8(seed, clock, nat, modules=modules, fast=True,
                       spatial_order=20, time_order=24)
    ftr, fte = fast["train"], fast["test"]
    xtr, xte = score["train"], score["test"]

    archived = read(S8_RESULTS / str(seed) / "result.json")
    oracle = next(r for r in read(S8_ORACLE)["rows"] if r["seed"] == seed)
    truth = C.S8_TRUTH
    null_t0 = np.asarray(archived["fits"]["null"]["selected"]["parameters"], dtype=float)
    inh_t0 = np.asarray(archived["fits"]["LIplus_inclusive"]["selected"]["parameters"], dtype=float)

    # -- truth and oracle reconstruction --------------------------------
    tr32 = fte.evaluate(truth, "LIplus_inclusive", 32)[0]
    truth_test = exact_eval(xte, truth, "LIplus_inclusive", None, 16)
    truth_train = exact_eval(xtr, truth, "LIplus_inclusive", None, 16)
    fixed_truth = truth.copy()
    fixed_truth[5] = 0.0
    fixed_null = dict(
        train=exact_eval(xtr, fixed_truth, "null", None, 16),
        test=exact_eval(xte, fixed_truth, "null", None, 16))
    intercept_theta, _ = refit_intercept(xtr, truth, order=16)
    intercept_null = dict(
        train=exact_eval(xtr, intercept_theta, "null", None, 16),
        test=exact_eval(xte, intercept_theta, "null", None, 16))
    replay_t0 = dict(
        train=exact_eval(xtr, null_t0, "null", None, 16),
        test=exact_eval(xte, null_t0, "null", None, 16))
    replay_inh = dict(
        train=exact_eval(xtr, inh_t0, "LIplus_inclusive", None, 16),
        test=exact_eval(xte, inh_t0, "LIplus_inclusive", None, 16))
    reconstruction = dict(
        truth_test_order32=float(tr32["joint"]),
        truth_test_order16=float(truth_test["joint"]),
        truth_train_nll=float(truth_train["nll"]),
        fixed_true_backbone_null_joint=float(fixed_null["test"]["joint"]),
        refitted_intercept_null_joint=float(intercept_null["test"]["joint"]),
        refitted_intercept_a=float(intercept_theta[0]),
        archived_joint_null_joint=float(archived["null_test"]["joint"]),
        archived_inhibited_joint=float(archived["inhibited_test"]["joint"]),
        archived_gain=float(archived["gain"]),
        archived_eta=float(archived["eta"]),
        replay_null_test_delta=float(replay_t0["test"]["joint"] - archived["null_test"]["joint"]),
        replay_inhibited_test_delta=float(replay_inh["test"]["joint"] - archived["inhibited_test"]["joint"]),
        oracle_deltas=dict(
            truth32=float(tr32["joint"] - oracle["true_generating_joint"]),
            truth16=float(truth_test["joint"] - oracle["true_order16_joint"]),
            fixed_null=float(fixed_null["test"]["joint"] - oracle["fixed_true_backbone_null_joint"]),
            intercept_null=float(intercept_null["test"]["joint"] - oracle["refitted_intercept_null_joint"]),
        ),
    )

    # -- stationary null backbone ---------------------------------------
    null_fit = E.null_stationary(ftr, order=8)
    stat_null_fast = np.asarray(null_fit["selected"]["parameters"], dtype=float)
    stat_null = dict(
        train=exact_eval(xtr, stat_null_fast, "null", None, 16),
        test=exact_eval(xte, stat_null_fast, "null", None, 16))
    stationary_null = dict(
        parameters=[float(v) for v in stat_null_fast],
        train=stat_null["train"], test=stat_null["test"],
        fast_training_nll=float(null_fit["selected"]["nll"]),
        resolved_starts=len(null_fit["candidates"]),
    )
    fast_null_stat = ftr.evaluate(stat_null_fast, "null", 8)[0]["nll"]
    fast_null_truth = ftr.evaluate(fixed_truth, "null", 8)[0]["nll"]

    arms = {}

    # -- ladder step 1: fixed true backbone, fit (a, eta) ---------------
    base1 = E.fixed_true_backbone()
    fit1 = E.fit_e1d(ftr, base1, "2p", 15.0, 5.0, order=8)
    arms["S1_fixed_backbone_a_eta"] = arm_record(
        ftr, xtr, xte, np.asarray(fit1["selected"]["parameters"], dtype=float),
        base1, fast_null_truth, fixed_null["train"]["nll"], fixed_null,
        extra=dict(fast_training_nll=float(fit1["selected"]["nll"]),
                   resolved_starts=len(fit1["candidates"])))

    # -- ladder step 2: fixed true backbone, fit (a, eta, ell, psi) -----
    base2 = E.fixed_true_backbone()
    starts2 = []
    for eta, ell, psi in ((0.4, 15.0, 5.0), (0.2, 10.0, 2.0),
                          (0.6, 30.0, 15.0), (0.1, 50.0, 30.0)):
        s = base2.copy()
        s[5], s[6], s[7] = eta, math.log(ell), math.log(psi)
        starts2.append([s[0], s[5], s[6], s[7]])
    fit2 = s8.fit(ftr, "LIplus_inclusive", [0, 5, 6, 7], base2, starts2,
                  maxiter=180, order=8, label="fixed_true_backbone_4p")
    arms["S2_fixed_backbone_a_eta_ell_psi"] = arm_record(
        ftr, xtr, xte, np.asarray(fit2["selected"]["parameters"], dtype=float),
        base2, fast_null_truth, fixed_null["train"]["nll"], fixed_null,
        extra=dict(fast_training_nll=float(fit2["selected"]["nll"]),
                   resolved_starts=len(fit2["candidates"])))

    # -- ladder step 3: stationary null backbone -----------------------
    base3 = stat_null_fast.copy()
    fit3a = E.fit_e1d(ftr, base3, "3p", 15.0, 5.0, order=8)
    arms["S3a_stat_null_a_n_eta_true_scale"] = arm_record(
        ftr, xtr, xte, np.asarray(fit3a["selected"]["parameters"], dtype=float),
        base3, fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(fast_training_nll=float(fit3a["selected"]["nll"]),
                   scale=fit3a["scale"]))
    grid3 = E.select_grid(ftr, base3, "3p", C.S8_SCALE_GRID, order=8)
    arms["S3b_stat_null_a_n_eta_grid"] = arm_record(
        ftr, xtr, xte, np.asarray(grid3["selected"]["selected"]["parameters"], dtype=float),
        base3, fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(fast_training_nll=float(grid3["selected"]["selected"]["nll"]),
                   scale=grid3["scale"],
                   selection_penalty_nats=grid3["selection_penalty_nats"]))

    # -- E_1D_Profile ---------------------------------------------------
    grid2 = E.select_grid(ftr, base3, "2p", C.S8_SCALE_GRID, order=8)
    arms["E1D_Profile_2p"] = arm_record(
        ftr, xtr, xte, np.asarray(grid2["selected"]["selected"]["parameters"], dtype=float),
        base3, fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(fast_training_nll=float(grid2["selected"]["selected"]["nll"]),
                   scale=grid2["scale"],
                   selection_penalty_nats=grid2["selection_penalty_nats"],
                   grid=[dict(ell_km=c["scale"]["ell_km"], psi_days=c["scale"]["psi_days"],
                              fast_nll=float(c["selected"]["nll"]), eta=float(c["eta"]),
                              nested_null=bool(c["nested_null"]))
                         for c in grid2["candidates"]]))
    arms["E1D_Profile_3p"] = arm_record(
        ftr, xtr, xte, np.asarray(grid3["selected"]["selected"]["parameters"], dtype=float),
        base3, fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(fast_training_nll=float(grid3["selected"]["selected"]["nll"]),
                   scale=grid3["scale"],
                   selection_penalty_nats=grid3["selection_penalty_nats"],
                   grid=[dict(ell_km=c["scale"]["ell_km"], psi_days=c["scale"]["psi_days"],
                              fast_nll=float(c["selected"]["nll"]), eta=float(c["eta"]),
                              nested_null=bool(c["nested_null"]))
                         for c in grid3["candidates"]]))

    # -- within-training split -----------------------------------------
    meta = fast["receipt"]["metadata"]
    first = split_phase(fast["rows"], meta, 30.0, C.S8_MID, modules, nat, clock, True)
    second_exact = split_phase(fast["rows"], meta, C.S8_MID, 395.0, modules, nat, clock, True)
    first_null_fit = E.null_stationary(first, order=8)
    first_null = np.asarray(first_null_fit["selected"]["parameters"], dtype=float)
    split = E.fit_split_cv(ftr, first, second_exact, base3, first_null,
                           grid2["scale"]["ell_km"], grid2["scale"]["psi_days"],
                           C.ALPHA_GRID, order=8)
    arms["E_Split_CV"] = arm_record(
        ftr, xtr, xte, np.asarray(split["parameters"], dtype=float), base3,
        fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(alpha=float(split["alpha"]),
                   first_half_eta=float(split["first_half"]["eta"]),
                   scale=split["scale"],
                   candidates=[dict(alpha=r["alpha"], eta=r["eta"],
                                    second_joint=r["second_joint"])
                               for r in split["candidates"]]))

    # -- E_L1_Shrinkage -------------------------------------------------
    ell_l1 = grid2["scale"]["ell_km"]
    psi_l1 = grid2["scale"]["psi_days"]
    lambda_rows = {}
    for lam in C.LAMBDA_GRID:
        for per_event in (False, True):
            key = f"{lam:g}" + ("_per_event" if per_event else "")
            fit = E.fit_l1(ftr, base3, "2p", ell_l1, psi_l1, lam, order=8,
                           per_event=per_event)
            second = second_exact.evaluate(np.asarray(fit["parameters"], dtype=float),
                                           "LIplus_inclusive", 16)[0]
            lambda_rows[key] = dict(fit=fit, second_joint=float(second["joint"]))
    split_key, split_payload = max(lambda_rows.items(),
                                   key=lambda kv: (kv[1]["second_joint"], -kv[1]["fit"]["lam"]))
    primary_l1 = split_payload["fit"]
    arms["E_L1_Shrinkage"] = arm_record(
        ftr, xtr, xte, np.asarray(primary_l1["parameters"], dtype=float), base3,
        fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(lam=float(primary_l1["lam"]), per_event=bool(primary_l1["per_event"]),
                   lambda_selected_by="second-half training score",
                   lambda_key=split_key, scale=primary_l1["scale"],
                   training_penalised=float(primary_l1["training_penalised"]),
                   lambda_grid={k: dict(eta=float(v["fit"]["eta"]),
                                        fast_training_nll=float(v["fit"]["training_nll"]),
                                        training_penalised=float(v["fit"]["training_penalised"]),
                                        second_joint=float(v["second_joint"]))
                                for k, v in lambda_rows.items()}))
    ref_l1 = lambda_rows["1"]["fit"]
    arms["E_L1_Shrinkage_lambda1"] = arm_record(
        ftr, xtr, xte, np.asarray(ref_l1["parameters"], dtype=float), base3,
        fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(lam=1.0, per_event=False, scale=ref_l1["scale"],
                   training_penalised=float(ref_l1["training_penalised"])))

    # -- free seven-parameter stationary fit ---------------------------
    starts7 = []
    for eta, ell, psi in ((0.4, 15.0, 5.0), (0.2, 8.0, 2.0),
                          (0.6, 30.0, 15.0), (0.15, 50.0, 30.0)):
        s = base3.copy()
        s[5], s[6], s[7] = eta, math.log(ell), math.log(psi)
        starts7.append([s[0], s[2], s[3], s[4], s[5], s[6], s[7]])
    free7 = E.fit_free_stationary(ftr, starts7, order=8)
    arms["Free_7D_stationary"] = arm_record(
        ftr, xtr, xte, np.asarray(free7["selected"]["parameters"], dtype=float),
        base3, fast_null_stat, stat_null["train"]["nll"], stat_null,
        extra=dict(fast_training_nll=float(free7["selected"]["nll"]),
                   resolved_starts=len(free7["candidates"])))

    # -- Wells-Coppersmith sensitivity on S8 ---------------------------
    ellw_train = wc_ell(fast["base_train"].a["parent_excess"])
    ellw_test = wc_ell(fast["base_test"].a["parent_excess"])
    fast_null_wc = ftr.evaluate(base3, "null", 8, ell2=ellw_train)[0]["nll"]
    wc2 = E.fit_e1d(ftr, base3, "2p", 15.0, WC_PSI, order=8, ell2=ellw_train)
    arms["WC_Rupture_2p"] = arm_record(
        ftr, xtr, xte, np.asarray(wc2["selected"]["parameters"], dtype=float), base3,
        fast_null_wc, stat_null["train"]["nll"], stat_null,
        ell2=ellw_train, ell2_test=ellw_test,
        extra=dict(fast_training_nll=float(wc2["selected"]["nll"]),
                   wc_psi_days=WC_PSI,
                   wc_ell_km=dict(M4=0.83, M5=3.24, M6=12.6, M6_5=28.9, M7=56.1)))

    # -- archived free-8D arm ------------------------------------------
    arms["Free_8D_archived"] = dict(
        parameters=[float(v) for v in inh_t0],
        train=replay_inh["train"], test=replay_inh["test"],
        nested_null=bool(abs(float(inh_t0[5])) < 1e-8),
        nonpositive_gain=bool(float(archived["gain"]) <= 0.0),
        nested_fast=False, nested_exact=False,
        eta=float(inh_t0[5]), ell_km=float(math.exp(inh_t0[6])),
        psi_days=float(math.exp(inh_t0[7])), ell2="global",
        source="validation/live_results/s8_moderate_complete_20261111/" + str(seed))

    # -- gains against the three reference nulls -----------------------
    refs = dict(
        archived_joint_null=float(archived["null_test"]["joint"]),
        stationary_null=float(stat_null["test"]["joint"]),
        fixed_true_backbone_null=float(fixed_null["test"]["joint"]),
        refitted_intercept_null=float(intercept_null["test"]["joint"]),
    )
    for name, arm in arms.items():
        arm["gain_vs_archived_joint_null"] = float(arm["test"]["joint"] - refs["archived_joint_null"])
        arm["gain_vs_stationary_null"] = float(arm["test"]["joint"] - refs["stationary_null"])
        arm["gain_vs_fixed_true_null"] = float(arm["test"]["joint"] - refs["fixed_true_backbone_null"])
        arm["gain_vs_refit_intercept_null"] = float(arm["test"]["joint"] - refs["refitted_intercept_null"])
        arm["oracle_fraction_vs_archived_null"] = float(
            arm["gain_vs_archived_joint_null"] / oracle["oracle_gain_vs_joint_null"]) \
            if oracle["oracle_gain_vs_joint_null"] else 0.0
        theta = np.asarray(arm["parameters"], dtype=float)
        ell2 = ellw_train if arm["ell2"] == "wells_coppersmith" else None
        ell2_test = ellw_test if arm["ell2"] == "wells_coppersmith" else None
        fast_test = fte.evaluate(theta, "LIplus_inclusive", 16,
                                 ell2=ell2_test)[0]
        fast_train = ftr.evaluate(theta, "LIplus_inclusive", 8, ell2=ell2)[0]
        arm["fast_test_joint"] = float(fast_test["joint"])
        arm["fast_train_nll"] = float(fast_train["nll"])
        arm["test_quadrature_delta"] = float(fast_test["joint"] - arm["test"]["joint"])

    row = dict(seed=int(seed), n_train=int(fast["receipt"]["n_train"]),
               n_test=int(fast["receipt"]["n_test"]),
               oracle=oracle, reconstruction=reconstruction,
               stationary_null=stationary_null, references=refs,
               arms=arms, wall_seconds=float(time.time() - started))
    write(OUTPUT / "histories" / f"{seed}.json", row)
    print("s8", seed,
          "E1D2", round(arms["E1D_Profile_2p"]["gain_vs_stationary_null"], 2),
          "E1D3", round(arms["E1D_Profile_3p"]["gain_vs_stationary_null"], 2),
          "L1", round(arms["E_L1_Shrinkage"]["gain_vs_stationary_null"], 2),
          "S1", round(arms["S1_fixed_backbone_a_eta"]["gain_vs_archived_joint_null"], 2),
          f"{time.time()-started:.0f}s", flush=True)
    return row


def summarize(rows):
    seed_rows = sorted(rows, key=lambda r: r["seed"])
    names = list(seed_rows[0]["arms"].keys())
    by_arm = {}
    for name in names:
        arms = [r["arms"][name] for r in seed_rows]
        by_arm[name] = dict(
            gain_vs_archived_joint_null=C.stats([a["gain_vs_archived_joint_null"] for a in arms]),
            gain_vs_stationary_null=C.stats([a["gain_vs_stationary_null"] for a in arms]),
            gain_vs_fixed_true_null=C.stats([a["gain_vs_fixed_true_null"] for a in arms]),
            gain_vs_refit_intercept_null=C.stats([a["gain_vs_refit_intercept_null"] for a in arms]),
            eta=dict(C.stats([a["eta"] for a in arms]),
                     rmse_vs_true=C.rmse([a["eta"] for a in arms], 0.4)),
            nested_null=int(sum(bool(a["nested_null"]) for a in arms)),
            eta_zero=int(sum(float(a["eta"]) < 1e-8 for a in arms)),
            max_test_quadrature_delta=float(max(abs(a["test_quadrature_delta"]) for a in arms)),
            selected_scale_counts={
                str(k): int(sum(1 for a in arms
                                if a.get("scale") and a["scale"]["ell_km"] == k))
                for k in (5.0, 15.0, 50.0)},
            lambda_key_counts={
                key: int(sum(1 for a in arms if a.get("lambda_key") == key))
                for key in ("0.5", "0.5_per_event", "1", "1_per_event",
                            "2", "2_per_event")} if name == "E_L1_Shrinkage" else None,
            per_event_count=(int(sum(1 for a in arms if a.get("per_event")))
                             if name == "E_L1_Shrinkage" else None),
        )
        if name == "Free_8D_archived":
            by_arm[name]["eta"] = dict(
                C.stats([r["oracle"]["fitted_eta"] for r in seed_rows]),
                rmse_vs_true=C.rmse([r["oracle"]["fitted_eta"] for r in seed_rows], 0.4))
    ladder = {}
    for name in names:
        ladder[name] = dict(
            mean_gain_vs_archived=float(np.mean([r["arms"][name]["gain_vs_archived_joint_null"]
                                                 for r in seed_rows])),
            mean_gain_vs_stationary=float(np.mean([r["arms"][name]["gain_vs_stationary_null"]
                                                    for r in seed_rows])),
            median_gain_vs_archived=float(np.median([r["arms"][name]["gain_vs_archived_joint_null"]
                                                     for r in seed_rows])),
            wins_vs_stationary=int(sum(r["arms"][name]["gain_vs_stationary_null"] > 0
                                       for r in seed_rows)),
        )
    payload = dict(
        schema="pathway3_s8_dof_ladder_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=C.sha256(Path(__file__)),
        native_source_sha256=C.sha256(native.SOURCE),
        seeds=[int(s) for s in C.S8_SEEDS],
        truth=[float(v) for v in C.S8_TRUTH],
        scale_grid=[list(v) for v in C.S8_SCALE_GRID],
        lambda_grid=list(C.LAMBDA_GRID), alpha_grid=list(C.ALPHA_GRID),
        oracle_ceiling=dict(
            gain_vs_fixed=C.read_json(S8_ORACLE)["oracle_gain_vs_fixed"],
            gain_vs_intercept=C.read_json(S8_ORACLE)["oracle_gain_vs_intercept"],
            gain_vs_joint_null=C.read_json(S8_ORACLE)["oracle_gain_vs_joint_null"],
            estimation_loss=C.read_json(S8_ORACLE)["estimation_loss"],
            fitted_gain=C.read_json(S8_ORACLE)["fitted_gain"],
        ),
        max_reconstruction_delta=dict(
            truth32=float(max(abs(r["reconstruction"]["oracle_deltas"]["truth32"]) for r in seed_rows)),
            truth16=float(max(abs(r["reconstruction"]["oracle_deltas"]["truth16"]) for r in seed_rows)),
            fixed_null=float(max(abs(r["reconstruction"]["oracle_deltas"]["fixed_null"]) for r in seed_rows)),
            intercept_null=float(max(abs(r["reconstruction"]["oracle_deltas"]["intercept_null"]) for r in seed_rows)),
            replay_null=float(max(abs(r["reconstruction"]["replay_null_test_delta"]) for r in seed_rows)),
            replay_inhibited=float(max(abs(r["reconstruction"]["replay_inhibited_test_delta"]) for r in seed_rows)),
        ),
        by_arm=by_arm, ladder=ladder, rows=seed_rows,
    )
    write(OUTPUT / "summary.json", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(C.S8_SEEDS))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    seeds = args.seeds[:args.limit] if args.limit else args.seeds
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    pending = []
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for seed in seeds:
                path = OUTPUT / "histories" / f"{seed}.json"
                if args.resume and path.exists():
                    rows.append(read(path))
                else:
                    pending.append(pool.submit(run_seed, seed))
            for future in as_completed(pending):
                rows.append(future.result())
    rows.sort(key=lambda r: r["seed"])
    if len(rows) == len(C.S8_SEEDS):
        summary = summarize(rows)
        print(json.dumps({k: round(v["gain_vs_stationary_null"]["mean"], 3)
                          for k, v in summary["by_arm"].items()}, indent=2))
    else:
        write(OUTPUT / "partial.json", dict(seeds=[r["seed"] for r in rows], rows=rows))


if __name__ == "__main__":
    main()
