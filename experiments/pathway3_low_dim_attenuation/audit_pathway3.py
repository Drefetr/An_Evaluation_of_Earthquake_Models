"""Independent audit of the Pathway 3 low-dimensional attenuation study.

The audit re-derives scores, closures, native kernels and custody.  It does not
re-use any selected-state score as an input to a new fit.
"""
from __future__ import annotations

import inspect
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.s04b_joint_nuisance import model as CORE  # noqa: E402
from experiments.pathway3_low_dim_attenuation import common as C  # noqa: E402
from experiments.pathway3_low_dim_attenuation import estimators as E  # noqa: E402
from experiments.pathway3_low_dim_attenuation import native, s8  # noqa: E402

OUT = C.OUT
WC_EXPECTED = {4.0: 0.8318, 5.0: 3.2359, 6.0: 12.5893, 7.0: 48.9779, 7.1: 56.1048}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(name, passed, detail):
    return dict(name=name, passed=bool(passed), detail=detail)


def custody():
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only", "--",
         "validation", "docs", "reproduction", "paper"],
        capture_output=True, text=True, check=True).stdout.split()
    status = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--",
         "validation", "docs", "reproduction"],
        capture_output=True, text=True, check=True).stdout.splitlines()
    untracked = [line[3:] for line in status if line.startswith("??")]
    allowed = ("experiments/pathway", "validation/live_results/pathway",
               "docs/reviews/pathway", "build/pathway")
    unexpected = [p.replace("\\", "/") for p in untracked
                  if not any(p.replace("\\", "/").startswith(a) for a in allowed)]
    return check(
        "sealed_custody",
        not tracked and not unexpected,
        dict(tracked_modifications=tracked, unexpected_untracked=unexpected,
             allowed_untracked=len(untracked) - len(unexpected)))


def source_pins():
    pins = {}
    for relative in (
        "experiments/s04b_joint_nuisance/model.py",
        "experiments/s04b_joint_nuisance/attenuation.cpp",
        "experiments/pathway1_annular_attenuation/annular_native.cpp",
        "experiments/etas_inhibition_benchmark/run_frozen_20261111.py",
        "validation/live_results/track_b_controls_20261112/profiles_and_power/s8_oracle.json",
        "reproduction/synthetic/input_manifest.json",
        "validation/authorities/e7fbc4fa4fae3da4_observed.json",
    ):
        pins[relative] = C.sha256(ROOT / relative)
    return check("source_pins", True, pins)


def wc_scale():
    rows = {}
    ok = True
    for magnitude, expected in WC_EXPECTED.items():
        value = 10.0 ** (-2.44 + 0.59 * magnitude)
        rows[str(magnitude)] = dict(value=value, expected=expected,
                                    delta=value - expected)
        ok = ok and abs(value - expected) < 0.01
    return check("wells_coppersmith_scale", ok, rows)


def native_rows_check():
    rng = np.random.default_rng(20261116)
    native_impl = native.NativeP3(native.build())
    rows, cols = 9, 7
    lag = np.abs(rng.normal(size=(rows, cols))) * 30.0
    r2 = np.abs(rng.normal(size=(rows, cols))) * 400.0
    dm = rng.uniform(0.0, 3.0, size=cols)
    fertility = rng.uniform(0.05, 2.0, size=cols)
    x = np.array([-1.2, 0.2, 0.3, math.log(0.05), 1.3,
                  math.log(5.0), 0.5, 1.6, 0.3, math.log(0.214), math.log(5.0),
                  0.75 * math.log(10.0)])
    alpha_ell = 0.59
    data = dict(lag=lag, r2=r2)
    out = dict()
    for kernel in ("mono", "ann2"):
        out[kernel] = native_impl.rows(data, dm, fertility, x, kernel=kernel,
                                       scaled=True, need_h=True, need_g=True,
                                       threads=1, alpha_ell=alpha_ell)
    # Independent NumPy reference for G and its three stress derivatives.
    ell2 = np.exp(2.0 * x[9] + 2.0 * alpha_ell * math.log(10.0) * dm)
    psi = math.exp(x[10])
    mag = np.exp(x[11] * dm)
    reference = {}
    for kernel in ("mono", "ann2"):
        G = np.zeros((rows, 4))
        for i in range(rows):
            for j in range(cols):
                if not lag[i, j] > 0:
                    continue
                v = r2[i, j] / ell2[j]
                one = 1.0 + v
                if kernel == "mono":
                    K = 1.0 / one ** 2
                    dK = 4.0 * v / one ** 3
                else:
                    K = 16.0 * v * v / one ** 4
                    dK = 64.0 * v * v * (v - 1.0) / one ** 5
                base = mag[j] * math.exp(-lag[i, j] / psi)
                G[i, 0] += base * K
                G[i, 1] += base * dK
                G[i, 2] += base * K * lag[i, j] / psi
                G[i, 3] += base * K * dm[j]
        reference[kernel] = G
    detail = {}
    ok = True
    for kernel in ("mono", "ann2"):
        delta = float(np.max(np.abs(out[kernel][:, [6, 7, 8, 9]] - reference[kernel])))
        detail[kernel] = dict(max_abs_delta=delta)
        ok = ok and delta < 1e-9
    # Central finite differences for the analytic stress derivatives.
    def rows_at(values):
        return native_impl.rows(data, dm, fertility, values, kernel="mono",
                                scaled=True, need_h=False, need_g=True,
                                threads=1, alpha_ell=alpha_ell)[:, [6, 7, 8, 9]]
    base = rows_at(x)
    fd = {}
    for index, name, column in ((9, "logell0", 1), (10, "logpsi", 2), (11, "gamma", 3)):
        eps = 1e-6
        upper = x.copy(); upper[index] += eps
        lower = x.copy(); lower[index] -= eps
        fd_g = (rows_at(upper)[:, 0] - rows_at(lower)[:, 0]) / (2 * eps)
        fd[name] = float(np.max(np.abs(fd_g - base[:, column])))
    detail["finite_difference_max_abs_delta"] = fd
    ok = ok and all(v < 5e-6 for v in fd.values())
    return check("native_annular_rows", ok, detail)


def deficit_fixture():
    native_impl = native.NativeP3(native.build())
    pt = np.array([0.5, 1.5])
    marks = np.array([1.0, math.exp(0.75 * math.log(10.0) * 1.0)])
    r2 = np.array([[1.0, 4.0], [9.0, 0.25]])
    area = np.array([1.0, 2.0])
    b = np.array([1.0, 0.5])
    t = np.array([0.75, 1.2, 2.0, 3.0])
    w = np.array([0.1, 0.2, 0.3, 0.4])
    theta = np.array([-1.0, 0.0, 0.2, math.log(0.05), 1.3, 0.4,
                      math.log(15.0), math.log(5.0)])
    ell2 = np.array([225.0, 225.0])

    def direct(ell_vector):
        ell_vec = np.sqrt(ell_vector)
        psi = math.exp(theta[7])
        total = np.zeros(9)
        for s in range(len(area)):
            G = L = P = 0.0
            clock = 0.0
            j = 0
            for i, ti in enumerate(t):
                while j < len(pt) and pt[j] < ti:
                    dt = pt[j] - clock
                    e = math.exp(-dt / psi)
                    P = e * (P + G * dt / psi)
                    G *= e
                    L *= e
                    v = r2[s, j] / ell_vector[j]
                    radial = marks[j] / (1 + v) ** 2
                    dell = radial * 4 * v / (1 + v)
                    G += radial
                    L += dell
                    clock = pt[j]
                    j += 1
                dt = ti - clock
                e = math.exp(-dt / psi)
                P = e * (P + G * dt / psi)
                G *= e
                L *= e
                clock = ti
                B = math.exp(theta[0]) * b[s]
                base = B
                ww = area[s] * w[i]
                e = math.exp(-theta[5] * G)
                lost = -math.expm1(-theta[5] * G)
                total[0] += ww * base * lost
                total[1] += ww * B * lost
                total[6] += ww * base * e * G
                total[7] += ww * base * e * theta[5] * L
                total[8] += ww * base * e * theta[5] * P
        return total

    zero = np.zeros(len(t))
    global_out = native_impl.integrate(pt, marks, r2, area, b, t, w, None, theta,
                                       zero, False, 0.0, 0.0, horizon=10.0)
    explicit = native_impl.integrate_ell(pt, marks, r2, area, b, t, w, None, theta,
                                         zero, ell2, False, 0.0, 0.0, horizon=10.0)
    reference = direct(ell2)
    delta_global = float(np.max(np.abs(global_out - reference)))
    delta_explicit = float(np.max(np.abs(explicit - reference)))
    return check("native_deficit_fixture",
                 delta_global < 1e-10 and delta_explicit < 1e-10,
                 dict(global_delta=delta_global, explicit_delta=delta_explicit,
                      reference=reference.tolist()))


def s8_replay(seeds=(410821, 410840)):
    summary = read(OUT / "s8/summary.json")
    rows = {r["seed"]: r for r in summary["rows"]}
    modules = CORE.archived()
    nat = native.NativeP3(native.build())
    clock = s8.ClockT0(760.0)
    deltas = {}
    closures = {}
    for seed in seeds:
        row = rows[seed]
        exact = s8.load_s8(seed, clock, nat, modules=modules, fast=False)
        xtr, xte = exact["train"], exact["test"]
        per_arm = {}
        for name, arm in row["arms"].items():
            theta = np.asarray(arm["parameters"], dtype=float)
            ell2 = None
            if arm["ell2"] == "wells_coppersmith":
                ell2 = 10.0 ** (-2.44 + 0.59 * (3.0 + exact["base_train"].a["parent_excess"]))
            tr = xtr.evaluate(theta, "LIplus_inclusive", 16, ell2=ell2)[0]
            ell2_test = None
            if arm["ell2"] == "wells_coppersmith":
                ell2_test = 10.0 ** (-2.44 + 0.59 * (3.0 + exact["base_test"].a["parent_excess"]))
            te = xte.evaluate(theta, "LIplus_inclusive", 16, ell2=ell2_test)[0]
            per_arm[name] = dict(
                archived_minus_reported_train=float(tr["nll"] - arm["train"]["nll"]),
                archived_minus_reported_test=float(te["joint"] - arm["test"]["joint"]),
                closure_train=float(arm["train"]["joint"]
                                    - (arm["train"]["P"] - arm["train"]["E"] + arm["train"]["M"])),
                closure_test=float(arm["test"]["joint"]
                                   - (arm["test"]["P"] - arm["test"]["E"] + arm["test"]["M"])),
            )
        deltas[str(seed)] = per_arm
        closures[str(seed)] = per_arm
    max_train = max(abs(v["archived_minus_reported_train"])
                    for d in deltas.values() for name, v in d.items()
                    if name != "WC_Rupture_2p")
    max_test = max(abs(v["archived_minus_reported_test"])
                   for d in deltas.values() for name, v in d.items()
                   if name != "WC_Rupture_2p")
    wc_test = max(abs(d["WC_Rupture_2p"]["archived_minus_reported_test"])
                  for d in deltas.values())
    max_closure = max(abs(v["closure_train"]) for d in closures.values() for v in d.values())
    max_closure = max(max_closure,
                      max(abs(v["closure_test"]) for d in closures.values() for v in d.values()))
    return check("s8_archived_plan_replay",
                 max_train < 1e-3 and max_test < 1e-3 and wc_test < 0.2
                 and max_closure < 1e-8,
                 dict(max_abs_train_delta=max_train, max_abs_test_delta=max_test,
                      wc_archived_test_delta=wc_test,
                      max_abs_closure=max_closure, per_seed=deltas))


def s8_gain_closures():
    summary = read(OUT / "s8/summary.json")
    max_error = 0.0
    for row in summary["rows"]:
        refs = row["references"]
        for name, arm in row["arms"].items():
            max_error = max(max_error, abs(
                arm["gain_vs_stationary_null"] - (arm["test"]["joint"] - refs["stationary_null"])))
            max_error = max(max_error, abs(
                arm["gain_vs_archived_joint_null"] - (arm["test"]["joint"] - refs["archived_joint_null"])))
    oracle = summary["oracle_ceiling"]
    oracle_error = max(
        abs(oracle["gain_vs_fixed"]["mean"] - 16.42868804868585),
        abs(oracle["gain_vs_intercept"]["mean"] - 14.540568689145351),
        abs(oracle["gain_vs_joint_null"]["mean"] - 18.111994353630667),
        abs(oracle["estimation_loss"]["mean"] + 17.817849589786825),
    )
    return check("s8_gain_closures", max_error < 1e-9 and oracle_error < 1e-6,
                 dict(max_gain_identity_error=max_error,
                      max_oracle_mean_error=oracle_error))


def s8_l1_kkt():
    summary = read(OUT / "s8/summary.json")
    rows = {r["seed"]: r for r in summary["rows"]}
    modules = CORE.archived()
    nat = native.NativeP3(native.build())
    clock = s8.ClockT0(760.0)
    detail = {}
    ok = True
    for seed in (410821, 410825, 410840):
        row = rows[seed]
        arm = row["arms"]["E_L1_Shrinkage"]
        fast = s8.load_s8(seed, clock, nat, modules=modules, fast=True)
        base = np.asarray(row["stationary_null"]["parameters"], dtype=float)
        ell = arm["scale"]["ell_km"]
        psi = arm["scale"]["psi_days"]
        base[6], base[7] = math.log(ell), math.log(psi)
        stress = fast["train"].event_stress(base)["G"]
        scale = float(stress.sum() if arm["per_event"] else stress.mean())
        theta = np.asarray(arm["parameters"], dtype=float)
        value, gradient = fast["train"].evaluate(theta, "LIplus_inclusive", 8)
        slope = -float(gradient[5])
        target = float(arm["lam"] * scale)
        if theta[5] > 1e-7:
            passed = abs(slope - target) < 5e-2
        else:
            passed = slope <= target + 5e-2
        detail[str(seed)] = dict(eta=float(theta[5]), slope=slope, target=target,
                                 passed=passed)
        ok = ok and passed
    return check("s8_l1_kkt", ok, detail)


def split_hygiene():
    summary = read(OUT / "s8/summary.json")
    saved = next(r for r in summary["rows"] if r["seed"] == 410821)
    modules = CORE.archived()
    nat = native.NativeP3(native.build())
    clock = s8.ClockT0(760.0)
    fast = s8.load_s8(410821, clock, nat, modules=modules, fast=True)
    null_fit = E.null_stationary(fast["train"], order=8)
    base = np.asarray(null_fit["selected"]["parameters"], dtype=float)
    grid = E.select_grid(fast["train"], base, "2p", C.S8_SCALE_GRID, order=8)
    fresh = np.asarray(grid["selected"]["selected"]["parameters"], dtype=float)
    stored = np.asarray(saved["arms"]["E1D_Profile_2p"]["parameters"], dtype=float)
    # The selected grid state can contain a different eta if a grid candidate
    # was nested on the exact rule; compare the scale and the (a, eta) pair.
    delta = float(np.max(np.abs(fresh - stored)))
    detail = dict(seed=410821, fresh=fresh.tolist(), stored=stored.tolist(),
                  max_abs_delta=delta,
                  estimator_functions_receive_test_argument={
                      name: "test" in str(inspect.signature(getattr(E, name)))
                      for name in ("null_stationary", "fit_e1d", "select_grid",
                                   "fit_l1", "fit_split_cv", "fit_free_stationary")})
    return check("training_only_reproduction", delta < 5e-2, detail)


def banks_audit():
    summary = read(OUT / "banks/summary.json")
    top = read(OUT / "summary.json")
    max_delta = max(abs(r["references"]["replay_gain_delta"]) for r in summary["rows"])
    max_closure = 0.0
    for row in summary["rows"]:
        for arm in row["arms"].values():
            max_closure = max(max_closure, abs(
                arm["gain_vs_stationary_null"]
                - (arm["test"]["joint"] - row["references"]["stationary_null"])))
    s4 = summary["by_regime"]["4"]
    name = top.get("banks", {}).get("selected_bank_estimator", "E_L1_Shrinkage")
    best = s4.get(name)
    return check("s04b_bank_audit",
                 max_delta < 5e-3 and max_closure < 1e-9,
                 dict(max_replay_gain_delta=max_delta, max_gain_closure=max_closure,
                      s4_replay_raw_gain=s4["raw_replay_gain"],
                      selected_bank_estimator=name,
                      s4_selected_gain=best,
                      completed=int(len(summary["rows"]))))


def california_audit():
    summary = read(OUT / "california/summary.json")
    max_joint_error = 0.0
    max_gain_error = 0.0
    max_quadrature = 0.0
    for row in summary["rows"]:
        mark = row["rows"]["mono"]["mark_logscore"]
        for kernel in ("mono", "ann2"):
            payload = row["rows"][kernel]
            for arm in payload["arms"].values():
                max_joint_error = max(max_joint_error, abs(
                    arm["test"]["joint"] - (-arm["test"]["nll"] + payload["mark_logscore"])))
                max_gain_error = max(max_gain_error, abs(
                    arm["gain_vs_null"] - (arm["test"]["joint"] - arm["null_test"]["joint"])))
                max_quadrature = max(max_quadrature, abs(arm["test_quadrature_delta"]))
    wc = summary["wc"]
    wc_ok = abs(wc["ell0_km"] - 10.0 ** (-2.44 + 0.59 * 3.0)) < 1e-12 and abs(wc["alpha"] - 0.59) < 1e-12
    return check("california_wc_audit",
                 max_joint_error < 1e-9 and max_gain_error < 1e-9
                 and max_quadrature < 5e-2 and wc_ok,
                 dict(max_joint_identity_error=max_joint_error,
                      max_gain_identity_error=max_gain_error,
                      max_quadrature_delta=max_quadrature,
                      wc_scale_ok=wc_ok))


def nz_audit():
    summary = read(OUT / "nz/summary.json")
    total = sum(summary["folds"][name]["arms"]["E1D_Profile_3p"]["gain"]
                for name in summary["folds"])
    delta = abs(total - summary["totals"]["E1D_Profile_3p"])
    wc_absent = all("not defined" in fold["wc_status"] for fold in summary["folds"].values())
    return check("nz_scope_and_closure", delta < 1e-9 and wc_absent,
                 dict(total=total, reported=summary["totals"]["E1D_Profile_3p"],
                      wc_explicitly_absent=wc_absent,
                      scope=summary["scope"]))


def top_level():
    summary = read(OUT / "summary.json")
    required = ("s8_ladder", "s8_by_arm", "banks", "california",
                "new_zealand", "winning_estimator", "oracle_ceiling")
    missing = [k for k in required if k not in summary]
    closure = summary.get("ladder_closure", {})
    closure_ok = abs(float(closure.get("residual", 1.0))) < 1e-9
    return check("top_level_summary", not missing and closure_ok,
                 dict(missing=missing, closure_residual=closure.get("residual"),
                      winner=summary.get("winning_estimator"),
                      report_exists=C.REPORT.exists()))

def main():
    checks = [
        custody(),
        source_pins(),
        wc_scale(),
        native_rows_check(),
        deficit_fixture(),
        s8_replay(),
        s8_gain_closures(),
        s8_l1_kkt(),
        split_hygiene(),
        banks_audit(),
        california_audit(),
        nz_audit(),
        top_level(),
    ]
    payload = dict(
        schema="pathway3_independent_audit_v1",
        passed=all(c["passed"] for c in checks),
        checks=checks,
        code_pins={name: C.sha256(Path(__file__).parent / name)
                   for name in ("s8.py", "estimators.py", "native.py",
                                "pathway3_native.cpp", "run_s8.py",
                                "run_banks.py", "run_california.py",
                                "run_nz.py", "build_summary.py")},
    )
    C.write_json(OUT / "independent_audit.json", payload)
    print(json.dumps(dict(passed=payload["passed"],
                          checks={c["name"]: c["passed"] for c in checks}), indent=1))
    return payload


if __name__ == "__main__":
    main()
