"""Independent verification for the Pathway 2 trend-parameterisation study."""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway2_trend_parameterization import background as B  # noqa: E402
from experiments.pathway2_trend_parameterization import synthetic as SY  # noqa: E402
from experiments.pathway2_trend_parameterization.native import NativeLaw, build  # noqa: E402

BASE = ROOT / "validation/live_results/pathway2_trend_controls_20261116"
S8_RESULTS = ROOT / "validation/live_results/s8_moderate_complete_20261111"
S8_ORACLE = ROOT / "validation/live_results/track_b_controls_20261112/profiles_and_power/s8_oracle.json"
NZ_SEALED = ROOT / "validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json"
MANIFEST = ROOT / "MANIFEST.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add(checks, name, passed, **value):
    checks.append(dict(id=name, passed=bool(passed), **value))


def audit_background(checks):
    rng = np.random.default_rng(20261116)
    worst = 0.0
    rows = []
    for kind in B.LAWS:
        law = B.BackgroundLaw(kind, 760.0, origin=395.0, train_start=30.0, d_fixed=0.2)
        for _ in range(8):
            lo = float(rng.uniform(30, 700))
            hi = float(min(759.0, lo + rng.uniform(0.5, 300)))
            a = float(rng.uniform(-8, 0))
            d = float(rng.uniform(-1.5, 1.5))
            value, derivative = law.integral(a, d, lo, hi)
            f = lambda t: math.exp(a + law.effective_d(d) * law.x_scalar(t))
            ref = quad(f, lo, hi, epsabs=1e-13, epsrel=1e-12, limit=200)[0]
            dref = quad(lambda t: law.x_scalar(t) * f(t), lo, hi,
                        epsabs=1e-13, epsrel=1e-12, limit=200)[0]
            rel = abs(value - ref) / max(1.0, abs(ref))
            drel = abs(derivative - dref) / max(1.0, abs(dref))
            worst = max(worst, rel, drel)
            rows.append(dict(kind=kind, lo=lo, hi=hi, value=value, reference=ref,
                             derivative=derivative, derivative_reference=dref,
                             relative_delta=max(rel, drel)))
    add(checks, "background_integral_quadrature", worst < 1e-8, worst_relative_delta=worst,
        rows=rows, tolerance=1e-8)


def audit_native(checks):
    """Direct fixture: compare the C++ deficit recurrence with a NumPy formula."""
    native = NativeLaw(build())
    pt = np.array([0.0, 1.0])
    marks = np.array([1.0, 0.7])
    r2 = np.array([[0.25, 1.0], [2.0, 0.5]])
    area = np.array([0.3, 0.7])
    b = np.array([1.2, 0.8])
    times = np.array([0.5, 1.5, 2.5, 3.0])
    weights = np.array([0.2, 0.3, 0.25, 0.25])
    theta = np.array([-2.0, 0.2, 0.4, math.log(0.05), 1.3, 0.6,
                      math.log(2.0), math.log(1.5)])
    clock = np.array([-0.5, -0.2, 0.0, 0.0])
    orth_c, orth_k = 0.11, 0.23
    rows = []
    for orth in (False, True):
        got = native.integrate(pt, marks, r2, area, b, times, weights, None, theta, clock,
                               orth, orth_c, orth_k, horizon=10.0)
        eta = theta[5]
        ell = math.exp(theta[6])
        psi = math.exp(theta[7])
        total = np.zeros(9)
        for s in range(len(b)):
            for i, t in enumerate(times):
                # Direct sums over all strictly earlier parents (no recurrence).
                g = sum(marks[j] * math.exp(-(t - pt[j]) / psi) / (1 + r2[s, j] / ell ** 2) ** 2
                        for j in range(len(pt)) if pt[j] < t)
                l = sum(marks[j] * math.exp(-(t - pt[j]) / psi) /
                        (1 + r2[s, j] / ell ** 2) ** 2 * 4 * (r2[s, j] / ell ** 2) /
                        (1 + r2[s, j] / ell ** 2) for j in range(len(pt)) if pt[j] < t)
                p = sum(marks[j] * math.exp(-(t - pt[j]) / psi) /
                        (1 + r2[s, j] / ell ** 2) ** 2 * ((t - pt[j]) / psi)
                        for j in range(len(pt)) if pt[j] < t)
                rr = g - (orth_c + orth_k * clock[i]) if orth else g
                e = math.exp(-eta * rr)
                lost = -math.expm1(-eta * rr)
                base = math.exp(theta[0] + theta[1] * clock[i]) * b[s]
                w = area[s] * weights[i]
                total[0] += w * base * lost
                total[1] += w * base * lost
                total[2] += w * clock[i] * base * lost
                total[6] += w * base * e * rr
                total[7] += w * base * e * eta * l
                total[8] += w * base * e * eta * p
        delta = np.max(np.abs(got - total) / np.maximum(1.0, np.abs(total)))
        rows.append(dict(orthogonal=orth, native=[float(v) for v in got],
                         reference=[float(v) for v in total], relative_delta=float(delta)))
    add(checks, "native_deficit_reference", max(r["relative_delta"] for r in rows) < 1e-10,
        rows=rows, tolerance=1e-10)


def audit_gradients(checks):
    from experiments.s04b_joint_nuisance import model as S8

    modules = S8.archived()
    native = NativeLaw(build())
    rows, rec, base_train, _ = SY.load_s8_case(410840, modules, native)
    sealed = read(S8_RESULTS / "410840/result.json")
    theta = np.asarray(sealed["fits"]["LIplus_inclusive"]["selected"]["parameters"], dtype=float)
    out = []
    for kind in ("T2", "T3"):
        law = B.BackgroundLaw(kind, 760.0, origin=395.0, train_start=30.0, d_fixed=0.2)
        phase = SY.FastLawPhase(base_train, law, native, spatial_order=10, time_order=8)
        if kind == "T3":
            SY.t3_projection(SY.LawPhase(base_train, law, native), 15.0, 5.0)
        value, gradient = phase.evaluate(theta, "LIplus_inclusive", 8)
        errors = []
        for i in range(8):
            h = 1e-6 * max(1.0, abs(theta[i]))
            plus = theta.copy()
            minus = theta.copy()
            plus[i] += h
            minus[i] -= h
            vp = phase.evaluate(plus, "LIplus_inclusive", 8, require_gradient=False)[0]["nll"]
            vm = phase.evaluate(minus, "LIplus_inclusive", 8, require_gradient=False)[0]["nll"]
            fd = (vp - vm) / (2 * h)
            errors.append(abs(gradient[i] - fd) / max(1.0, abs(fd)))
        out.append(dict(law=kind, nll=float(value["nll"]), gradient=list(map(float, gradient)),
                        max_relative_finite_difference=float(max(errors))))
    add(checks, "analytic_gradient_finite_difference",
        max(r["max_relative_finite_difference"] for r in out) < 1e-4,
        rows=out, tolerance=1e-4)


def audit_s8_replay(checks):
    from experiments.s04b_joint_nuisance import model as S8

    modules = S8.archived()
    native = NativeLaw(build())
    rows = []
    for seed in range(410821, 410841):
        rows_, rec, base_train, base_test = SY.load_s8_case(seed, modules, native)
        sealed = read(S8_RESULTS / str(seed) / "result.json")
        law = B.BackgroundLaw("T0", 760.0, origin=395.0, train_start=30.0, d_fixed=0.2)
        null = SY.LawPhase(base_test, law, native).evaluate(
            np.asarray(sealed["fits"]["null"]["selected"]["parameters"]), "null", 16)[0]
        inh = SY.LawPhase(base_test, law, native).evaluate(
            np.asarray(sealed["fits"]["LIplus_inclusive"]["selected"]["parameters"]),
            "LIplus_inclusive", 16)[0]
        rows.append(dict(seed=seed, null_delta=float(null["joint"] - sealed["null_test"]["joint"]),
                         inhibited_delta=float(inh["joint"] - sealed["inhibited_test"]["joint"])))
    worst = max(max(abs(r["null_delta"]), abs(r["inhibited_delta"])) for r in rows)
    add(checks, "s8_t0_replay", worst < 1e-6, max_absolute_delta=worst, rows=rows,
        tolerance=1e-6)


def audit_score_identities(checks):
    path = BASE / "s8/summary.json"
    if not path.exists():
        add(checks, "s8_score_identities", False, note="summary missing")
        return
    data = read(path)
    worst = 0.0
    count = 0
    for row in data["rows"]:
        for law in ("T1", "T2", "T3", "DSTAR"):
            entry = row["laws"][law]
            for key in ("null_test_archived", "inhibited_test_archived"):
                score = entry[key]
                worst = max(worst, abs(score["joint"] - (score["P"] - score["E"] + score["M"])))
                worst = max(worst, abs(score["C"] + score["E"]))
                count += 1
    add(checks, "s8_score_identities", worst < 1e-9, worst_error=worst, scores_checked=count,
        tolerance=1e-9)


def audit_quadrature(checks):
    path = BASE / "s8/summary.json"
    if not path.exists():
        add(checks, "s8_quadrature", False, note="summary missing")
        return
    data = read(path)
    worst = max(v["max_test_quadrature_delta"] for v in data["by_law"].values())
    add(checks, "s8_quadrature_fast32_vs_archived16", worst < 0.01, worst_delta=worst,
        tolerance=0.01)


def audit_nz(checks):
    path = BASE / "nz/summary.json"
    if not path.exists():
        add(checks, "nz_crosschecks", False, note="summary missing")
        return
    nz = read(path)
    sealed = read(NZ_SEALED)
    t1_delta = abs(nz["totals"]["T1"] - sealed["totals"]["zero_trend_delta_joint"])
    t0_delta = abs(nz["totals"]["T0"] - sealed["totals"]["archived_delta_joint"])
    fold1 = nz["folds"]["fold_50"]
    clamped = sealed["folds"]["fold_50"]["clamped"]["delta_joint"]
    t2_delta = abs(fold1["laws"]["T2"]["heldout"]["delta_joint"] - clamped)
    t3_delta = abs(fold1["laws"]["T3"]["heldout"]["delta_joint"] - clamped)
    add(checks, "nz_control_crosschecks", max(t1_delta, t0_delta, t2_delta, t3_delta) < 1e-4,
        t1_vs_sealed_zero_trend=t1_delta, t0_vs_sealed_archived=t0_delta,
        fold1_t2_vs_sealed_clamped=t2_delta, fold1_t3_vs_sealed_clamped=t3_delta,
        tolerance=1e-4)


def audit_s04b(checks):
    path = BASE / "s04b/summary.json"
    if not path.exists():
        add(checks, "s04b_t0_replay", False, note="summary missing")
        return
    data = read(path)
    worst = 0.0
    for row in data["rows"]:
        sealed = read(ROOT / "validation/live_results/s04b_joint_complete_20261111/cases"
                      / (row["case_id"] + ".json"))
        sealed_null = float(sealed["new_null_test"]["joint"])
        sealed_inh = float(next(o for o in sealed["outcomes"]
                                if o["model"] == "LIplus_inclusive" and o["gate"] == "raw")["score"]["joint"])
        worst = max(worst, abs(row["t0"]["null_test_joint"] - sealed_null),
                    abs(row["t0"]["inhibited_test_joint"] - sealed_inh))
    evaluator = float(data["max_t0_evaluator_gain_delta"])
    add(checks, "s04b_t0_replay", worst < 1e-9 and evaluator < 0.01,
        max_absolute_delta=worst, max_evaluator_gain_delta=evaluator,
        cases=len(data["rows"]), tolerance=1e-9, evaluator_tolerance=0.01)


def audit_ca(checks):
    path = BASE / "california/summary.json"
    if not path.exists():
        add(checks, "california_interior_replay", False, note="summary missing")
        return
    data = read(path)
    offsets = [abs(r["t0"]["evaluator_offset"]) for r in data["rows"]]
    add(checks, "california_interior_replay", max(offsets) < 1e-9,
        max_absolute_offset=float(max(offsets)), folds=len(data["rows"]), tolerance=1e-9)


def audit_projection(checks):
    worst = 0.0
    count = 0
    paths = [BASE / "s8/summary.json", BASE / "nz/summary.json", BASE / "california/summary.json"]
    for path in paths:
        if not path.exists():
            continue
        data = read(path)
        if "rows" in data and path.name == "summary.json" and "s8" in str(path.parent):
            projections = [r["laws"]["T3"]["projection"] for r in data["rows"]]
        elif "folds" in data:
            projections = [data["folds"][f]["laws"]["T3"]["projection"] for f in data["folds"]]
        elif "rows" in data:
            projections = [r["laws"]["T3"]["projection"] for r in data["rows"]]
        else:
            projections = []
        for proj in projections:
            if proj is None:
                continue
            worst = max(worst, abs(proj.get("event_correlation_after") or 0.0))
            count += 1
    add(checks, "t3_event_projection_orthogonality", worst < 1e-10, projections_checked=count,
        worst_absolute_residual_correlation=worst, tolerance=1e-10)


def audit_manifest(checks):
    manifest = read(MANIFEST)["files"]
    authority = [r for r in manifest if r["path"].startswith("validation/authorities/")]
    live = [r for r in manifest if r["path"].startswith("validation/live_results/")]
    bad = []
    checked = 0
    for entry in authority + live:
        path = ROOT / entry["path"]
        if not path.exists():
            bad.append(dict(path=entry["path"], reason="missing"))
            continue
        if sha(path) != entry["sha256"]:
            bad.append(dict(path=entry["path"], reason="hash"))
        checked += 1
    add(checks, "sealed_authority_and_live_result_hashes", not bad,
        files_checked=checked, authorities=len(authority), live_results=len(live), mismatches=bad)


def main():
    checks = []
    with threadpool_limits(limits=1):
        audit_background(checks)
        audit_native(checks)
        audit_gradients(checks)
        audit_s8_replay(checks)
        audit_score_identities(checks)
        audit_quadrature(checks)
        audit_nz(checks)
        audit_s04b(checks)
        audit_ca(checks)
        audit_projection(checks)
        audit_manifest(checks)
    passed = all(c["passed"] for c in checks)
    payload = dict(schema="pathway2_independent_audit_v1", passed=passed,
                   source=str(Path(__file__).relative_to(ROOT).as_posix()),
                   source_sha256=sha(Path(__file__)),
                   checks=checks,
                   failed=[c["id"] for c in checks if not c["passed"]])
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "independent_audit.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=passed, failed=payload["failed"],
                          checks=[(c["id"], c["passed"]) for c in checks]), indent=1))


if __name__ == "__main__":
    main()
