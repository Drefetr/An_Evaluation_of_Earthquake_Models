"""Stage P2.3b: California interior EP+ baseline under T1/T2/T3.

The frozen EP+ model, interior-scale background weights and Sobol integration
proposal are imported from the Pathway 1 annular experiment.  Only the
background clock and (for T3) the depletion residual are replaced.  Each fold
is evaluated by (i) refitting the eight-parameter null backbone under the law
and comparing its held-out joint score with the sealed original-EP score, and
(ii) profiling the total LI+ attenuation at that null over a fixed
(ell0, psi) grid, selecting eta on the training window and scoring the held-out
contrast.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway1_annular_attenuation import annular as A  # noqa: E402
from experiments.pathway2_trend_parameterization import background as B  # noqa: E402

CASES = ("california_fold_0", "california_fold_1", "california_fold_2")
LAWS = ("T1", "T2", "T3")
OUTPUT = ROOT / "validation/live_results/pathway2_trend_controls_20261116/california"
ELL_PSI = ((10.0, 2.0), (20.0, 5.0), (50.0, 30.0))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class LawModel(A.AnnularModel):
    def __init__(self, *args, law, **kwargs):
        super().__init__(*args, **kwargs)
        self.law = law

    def values_from_out(self, data, x, out):
        h = out[:, 0]
        hg = out[:, 1:6]
        xt = self.law.x(data["t"])
        B = np.exp(x[0] + x[1] * xt) * data["b"]
        lam = B + x[2] * h
        dlam = np.zeros((len(lam), 12))
        dlam[:, 0] = B
        dlam[:, 1] = B * xt
        dlam[:, 2] = h
        dlam[:, 3] = x[2] * hg[:, 0]
        dlam[:, 4] = x[2] * hg[:, 1]
        dlam[:, 5] = x[2] * hg[:, 2]
        dlam[:, 6] = x[2] * hg[:, 3]
        dlam[:, 7] = x[2] * hg[:, 4]
        return lam, B, h, dlam

    def exact_exposure(self, x):
        a, d, n, lc, p, ls, alph, q = x[:8]
        c = np.exp(lc)
        lo = self.a["parent_exposure_lo"]
        hi = self.a["parent_exposure_hi"]
        ul = np.log1p(lo / c)
        uh = np.log1p(hi / c)
        tl = np.exp((1 - p) * ul)
        th = np.exp((1 - p) * uh)
        J = tl - th
        Jc = (p - 1) * (tl * lo / (c + lo) - th * hi / (c + hi))
        Jp = -ul * tl + uh * th
        mass, ms, mq = self.region.mass(self.radii, np.exp(ls + alph * self.dm), q)
        E = float(self.kp @ (J * mass))
        g = np.zeros(12)
        g[2] = E
        g[3] = n * self.kp @ (Jc * mass)
        g[4] = n * self.kp @ (Jp * mass)
        g[5] = n * self.kp @ (J * ms)
        g[6] = n * self.kp @ (J * ms * self.dm)
        g[7] = n * self.kp @ (J * mq)
        Bint, Bd = self.law.integral(a, d, self.m["start"], self.m["end"])
        g[0] = Bint
        g[1] = Bd
        return Bint + n * E, g

    def objective(self, x, inhibit=False, details=False):
        x = np.asarray(x, dtype=float)
        out = self._event_out(x)
        lam, B, h, dlam = self.values_from_out(self.events, x, out)
        if np.any(lam <= 0) or not np.isfinite(lam).all():
            raise ArithmeticError("nonpositive event intensity")
        P = float(np.log(lam).sum())
        E, grad = self.exact_exposure(x)
        grad = np.asarray(grad, dtype=float).copy()
        grad -= np.sum(dlam / lam[:, None], axis=0)
        deficit = 0.0
        attenpoint = 0.0
        if details and inhibit and x[8] == 0.0:
            return dict(ground_point=P, exposure=E, uninhibited_exposure=E,
                        attenuation_deficit=0.0, nll=float(E - P))
        if inhibit:
            G = self.law.deplete(out[:, 6], self.law.x(self.events["t"]))
            gG = out[:, 7:12]
            attenpoint = float(x[8] * G.sum())
            grad[8] += G.sum()
            grad[9] += x[8] * gG[:, 0].sum()
            grad[10] += x[8] * gG[:, 1].sum()
            grad[11] += x[8] * gG[:, 2].sum()
            grad[5] += x[8] * gG[:, 3].sum()
            grad[6] += x[8] * gG[:, 4].sum()
            data = self.node_data
            if data is None:
                raise RuntimeError("missing frozen integration proposal")
            for j in range(0, len(data["t"]), 2048):
                raw = {k: v[j:j + 2048] for k, v in data.items()}
                nout = self._rows(raw, x, need_h=True, need_g=True)
                L, LB, _h, dL = self.values_from_out(raw, x, nout)
                g = self.law.deplete(nout[:, 6], self.law.x(raw["t"]))
                dg = nout[:, 7:12]
                atten = np.exp(-x[8] * g)
                dec = -np.expm1(-x[8] * g)
                w = raw["w"]
                deficit += float(w @ (L * dec))
                grad -= np.sum(dL * (w * dec)[:, None], axis=0)
                grad[8] -= float(w @ (L * atten * g))
                grad[9] -= float(np.sum(dg[:, 0] * (w * L * atten * x[8])))
                grad[10] -= float(np.sum(dg[:, 1] * (w * L * atten * x[8])))
                grad[11] -= float(np.sum(dg[:, 2] * (w * L * atten * x[8])))
                grad[5] -= float(np.sum(dg[:, 3] * (w * L * atten * x[8])))
                grad[6] -= float(np.sum(dg[:, 4] * (w * L * atten * x[8])))
        value = float(E - deficit - P + attenpoint)
        if details:
            return dict(ground_point=float(P - attenpoint), exposure=float(E - deficit),
                        uninhibited_exposure=float(E), attenuation_deficit=float(deficit),
                        nll=value)
        return value, grad


def build(case, law, native, x0_proposal):
    train, tm, test, vm, rows = A.RF.inputs(case)
    x0, weights, meta = A.load_baseline(case, "interior")
    region = A.RF.Region(train["rectangles"])
    background = A.RF.Background(train["event_xy"], region, tm["kde_bandwidth"], weights)
    train_model = LawModel(train, tm, background, native=native, kernel="mono", scaled=True, law=law)
    train_model.node_setup(x0_proposal, power=14, seed=20261111)
    train_model.freeze_nodes()
    test_model = LawModel(test, vm, background, native=native, kernel="mono", scaled=True, law=law)
    test_model.node_setup(x0_proposal, power=16, seed=20261120)
    test_model.freeze_nodes()
    return dict(case=case, train=train_model, test=test_model, x0=x0, meta=meta,
                train_data=train, test_data=test, tm=tm, vm=vm, weights=weights)


def adapt_start(kind, x, tm):
    x = np.asarray(x, dtype=float).copy()
    if kind == "T1":
        mean_x = (tm["start"] + tm["end"]) / tm["T0"] - 1.0
        x[0] = x[0] + x[1] * mean_x
        x[1] = 0.0
    elif kind in ("T2", "T3"):
        x[0] = x[0] + x[1] * (tm["end"] / tm["T0"] - 1.0)
    return x


def bounds():
    out = [tuple(b) for b in A.RF.BOUNDS]
    out[5] = (math.log(0.05), math.log(100.0))
    return out


def fit_null(model, start, kind, maxiter=400):
    box = bounds()
    indices = [0, 2, 3, 4, 5, 6, 7] if kind == "T1" else [0, 1, 2, 3, 4, 5, 6, 7]
    lo = np.asarray([box[i][0] for i in indices])
    hi = np.asarray([box[i][1] for i in indices])
    base = np.asarray(start, dtype=float).copy()
    base[1] = 0.0 if kind == "T1" else base[1]

    def target(v):
        x = base.copy()
        x[indices] = v
        try:
            value, gradient = model.objective(x, False)
        except (ArithmeticError, FloatingPointError, OverflowError):
            return 1e6, np.zeros(len(indices))
        return float(value), np.asarray(gradient[indices])

    opt = minimize(target, np.clip(base[indices], lo, hi), jac=True,
                   bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=maxiter, maxls=100, ftol=1e-10, gtol=2e-5))
    x = base.copy()
    x[indices] = opt.x
    value, gradient = model.objective(x, False)
    return dict(success=bool(opt.success), message=str(opt.message), nll=float(value),
                parameters=x.tolist(), nit=int(opt.nit), nfev=int(opt.nfev),
                indices=indices)


def profile(model, x, ell, psi, eta_grid=None):
    """Total LI+ attenuation profile at one null state."""
    x = np.asarray(x, dtype=float).copy()
    x[8] = 0.0
    x[9] = math.log(ell)
    x[10] = math.log(psi)
    out_e = model._event_out(x)
    lam_e, B_e, h_e, _ = model.values_from_out(model.events, x, out_e)
    G_e = model.law.deplete(out_e[:, 6], model.law.x(model.events["t"]))
    S_total = float(G_e.sum())
    wL, G_n = [], []
    A_total = 0.0
    data = model.node_data
    for j in range(0, len(data["t"]), 2048):
        raw = {k: v[j:j + 2048] for k, v in data.items()}
        nout = model._rows(raw, x, need_h=True, need_g=True)
        L, _B, _h, _ = model.values_from_out(raw, x, nout)
        g = model.law.deplete(nout[:, 6], model.law.x(raw["t"]))
        w = raw["w"]
        wL.append(w * L)
        G_n.append(g)
        A_total += float(w @ (L * g))
    wL = np.concatenate(wL)
    G_n = np.concatenate(G_n)
    slope = A_total - S_total

    def delta(e):
        return -e * S_total + float(wL @ (-np.expm1(-e * G_n)))

    def ddelta(e):
        return -S_total + float(wL @ (G_n * np.exp(-e * G_n)))

    if slope <= 0:
        eta_hat, train_gain = 0.0, 0.0
    else:
        lo, hi = 0.0, 1e-6
        while ddelta(hi) > 0 and hi < 50.0:
            hi *= 2.0
        for _ in range(120):
            mid = 0.5 * (lo + hi)
            if ddelta(mid) > 0:
                lo = mid
            else:
                hi = mid
        eta_hat = 0.5 * (lo + hi)
        train_gain = delta(eta_hat)
    return dict(ell0_km=float(ell), psi_days=float(psi), eta_hat=float(eta_hat),
                training_gain=float(train_gain), slope=float(slope),
                event_sum=float(S_total), exposure_integral=float(A_total))


def heldout_gain(test_model, x, ell, psi, eta):
    if eta == 0.0:
        return dict(delta_test=0.0, event_sum=0.0, exposure=0.0)
    x = np.asarray(x, dtype=float).copy()
    x[8] = float(eta)
    x[9] = math.log(ell)
    x[10] = math.log(psi)
    out_e = test_model._event_out(x)
    G_e = test_model.law.deplete(out_e[:, 6], test_model.law.x(test_model.events["t"]))
    S = float(G_e.sum())
    At = 0.0
    data = test_model.node_data
    for j in range(0, len(data["t"]), 2048):
        raw = {k: v[j:j + 2048] for k, v in data.items()}
        nout = test_model._rows(raw, x, need_h=True, need_g=True)
        L, _B, _h, _dL = test_model.values_from_out(raw, x, nout)
        g = test_model.law.deplete(nout[:, 6], test_model.law.x(raw["t"]))
        At += float(raw["w"] @ (L * (-np.expm1(-eta * g))))
    return dict(delta_test=float(-eta * S + At), event_sum=float(S), exposure=float(At))


def run_case(case):
    started = time.time()
    native = A.new_native(threads=1)
    _train, tm, _test, _vm, _rows = A.RF.inputs(case)
    law_t0 = B.BackgroundLaw("T0", tm["T0"], origin=tm["end"], train_start=tm["start"])
    base = build(case, law_t0, native, A.load_baseline(case, "interior")[0])
    x0 = base["x0"]
    mark = A.mark_logscore(case)
    comparison = read(ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/"
                      "baseline_comparison.json")
    original = next(r for r in comparison["rows"] if r["case"] == case)
    relaxation = read(ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/"
                      "sigma0_relaxation.json")
    interior = next(r for r in relaxation["rows"]
                    if r["case"] == case and r["normalization"] == "plane")
    t0_test = base["test"].objective(x0, False, True)
    t0_joint = float(-t0_test["nll"] + mark)
    t0 = dict(null_nll=float(t0_test["nll"]), null_joint=t0_joint,
              original_ep_joint=float(interior["test_joint_score"] - interior["gain_over_EP"]),
              sealed_epplus_joint=float(interior["test_joint_score"]),
              epplus_gain=float(t0_joint - (interior["test_joint_score"] - interior["gain_over_EP"])),
              evaluator_offset=float(t0_joint - interior["test_joint_score"]))
    rows = {}
    for kind in LAWS:
        law = B.BackgroundLaw(kind, tm["T0"], origin=tm["end"], train_start=tm["start"])
        model = build(case, law, native, x0)
        start = adapt_start(kind, x0, tm)
        null = fit_null(model["train"], start, kind)
        x_null = np.asarray(null["parameters"], dtype=float)
        test = model["test"].objective(x_null, False, True)
        joint = float(-test["nll"] + mark)
        # T3 projection uses the fitted T2 null stress field, frozen here.
        if kind == "T3":
            ell0, psi0 = 20.0, 5.0
            out_e = model["train"]._event_out(x_null)
            data = model["train"].node_data
            ge, gq, xe, xq, wq = [], [], [], [], []
            ge.append(model["train"].law.deplete(out_e[:, 6],
                                                 model["train"].law.x(model["train"].events["t"])))
            xe.append(model["train"].law.x(model["train"].events["t"]))
            for j in range(0, len(data["t"]), 2048):
                raw = {k: v[j:j + 2048] for k, v in data.items()}
                nout = model["train"]._rows(raw, x_null, need_h=True, need_g=True)
                gq.append(nout[:, 6])
                xq.append(model["train"].law.x(raw["t"]))
                wq.append(raw["w"])
            law.orthogonalise(np.concatenate(ge), np.concatenate(xe),
                              np.concatenate(gq), np.concatenate(xq), np.concatenate(wq))
            # The null is unchanged by T3; refit the profile with the frozen c,k.
        profile_rows = []
        for ell, psi in ELL_PSI:
            p = profile(model["train"], x_null, ell, psi)
            h = heldout_gain(model["test"], x_null, ell, psi, p["eta_hat"])
            profile_rows.append(dict(profile=p, heldout=h))
        best = max(profile_rows, key=lambda r: r["profile"]["training_gain"])
        rows[kind] = dict(
            law=law.describe(), projection=law.projection if kind == "T3" else None,
            null=null, test=dict(nll=float(test["nll"]), joint=joint,
                                 epplus_gain=float(joint - (interior["test_joint_score"] - interior["gain_over_EP"]))),
            best_profile=best,
            profiles=profile_rows,
        )
    row = dict(case=case, mark_logscore=float(mark), t0=t0, laws=rows,
               wall_seconds=float(time.time() - started))
    write(OUTPUT / "cases" / (case + ".json"), row)
    print("ca", case, "T0", round(t0["epplus_gain"], 2),
          {k: round(rows[k]["test"]["epplus_gain"], 2) for k in LAWS},
          f"{time.time()-started:.0f}s", flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=list(CASES))
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    from concurrent.futures import ProcessPoolExecutor, as_completed
    rows = []
    pending_cases = []
    for case in args.cases:
        path = OUTPUT / "cases" / (case + ".json")
        if path.exists():
            rows.append(read(path))
        else:
            pending_cases.append(case)
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_case, case) for case in pending_cases]
            for future in as_completed(futures):
                rows.append(future.result())
    # Include every case already on disk so a partial rerun does not truncate
    # the merged summary.
    for case in CASES:
        path = OUTPUT / "cases" / (case + ".json")
        if path.exists() and not any(r["case"] == case for r in rows):
            rows.append(read(path))
    rows.sort(key=lambda r: r["case"])
    payload = dict(
        schema="pathway2_california_epplus_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=__import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest(),
        cases=list(CASES), laws=["T0", *LAWS],
        note=("Interior EP+ baseline. T0 uses the sealed interior null state. T1/T2/T3 refit "
              "the null backbone under the law with the frozen background weights and Sobol "
              "proposal. The attenuation profile fixes (ell0,psi) on a three-point grid and "
              "selects eta on the training window."),
        rows=rows,
    )
    write(OUTPUT / "summary.json", payload)
    print(json.dumps({r["case"]: {"T0": round(r["t0"]["epplus_gain"], 2),
                                  **{k: round(r["laws"][k]["test"]["epplus_gain"], 2) for k in LAWS}}
                      for r in rows}, indent=1))


if __name__ == "__main__":
    main()
