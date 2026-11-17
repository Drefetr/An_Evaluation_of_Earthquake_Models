"""Synthetic annular control bank: generator, evaluator and fitting.

The bank reuses the archived S8 chronological simulator and fitting geometry.
Only the attenuation stress kernel is replaced (mono or ann2); the ETAS
backbone, mark law and background remain the archived S8 moderate design.
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway1_annular_attenuation import annular as A  # noqa: E402

GENERATOR = ROOT / "reproduction/synthetic/source/generator.py"
S8_DATA = ROOT / "reproduction/synthetic/s8_moderate_total"
S8_RESULTS = ROOT / "validation/live_results/s8_moderate_complete_20261111"
GAMMA = 0.75 * math.log(10.0)


def load_generator():
    spec = importlib.util.spec_from_file_location("pathway1_generator", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pathway1_generator"] = module
    spec.loader.exec_module(module)
    return module


def load_s8():
    from experiments.s04b_joint_nuisance import model as S8

    return S8


def ann2_stress(t, x, y, history, ell, psi):
    """Strictly-prior ann2 stress with the archived mark weighting."""
    ell2 = ell * ell
    terms = []
    for event in history:
        if event.time < t:
            r2 = (x - event.x) ** 2 + (y - event.y) ** 2
            v = r2 / ell2
            kernel = 16.0 * v * v / (1.0 + v) ** 4
            terms.append(math.exp(GAMMA * event.Q - (t - event.time) / psi) * kernel)
    return math.fsum(terms)


def ann1_stress(t, x, y, history, ell, psi):
    ell2 = ell * ell
    terms = []
    for event in history:
        if event.time < t:
            r2 = (x - event.x) ** 2 + (y - event.y) ** 2
            v = r2 / ell2
            kernel = 6.75 * v / (1.0 + v) ** 3
            terms.append(math.exp(GAMMA * event.Q - (t - event.time) / psi) * kernel)
    return math.fsum(terms)


def mono_stress(t, x, y, history, ell, psi):
    ell2 = ell * ell
    terms = []
    for event in history:
        if event.time < t:
            r2 = (x - event.x) ** 2 + (y - event.y) ** 2
            v = r2 / ell2
            kernel = 1.0 / (1.0 + v) ** 2
            terms.append(math.exp(GAMMA * event.Q - (t - event.time) / psi) * kernel)
    return math.fsum(terms)


def generate_history(seed, eta, ell, psi, horizon=760.0, a=math.log(0.25), d=0.2,
                     n=0.35, c=0.05, p=1.3, background="smooth", case_id="P1_ann2"):
    G = load_generator()
    if case_id not in G.MATCHED_NAMES:
        G.MATCHED_NAMES.append(case_id)
    G.strict_stress_plus = ann2_stress
    law = G.Law(case_id, int(seed), background, float(eta), float(ell), float(psi),
                horizon=float(horizon), T0=float(horizon), a=float(a), d=float(d),
                n=float(n), c=float(c), p=float(p), sigma=10.0, beta=2.0, r=0.7,
                x0=0.0, x1=100.0, y0=0.0, y1=100.0)
    limits = G.Limits()
    budget = G.Budget(limits)
    streams = G.ScalarStreams(int(seed), limits, budget)
    simulator = G._Simulator(law, limits, budget, streams)
    simulator.run()
    rows = np.asarray([[e.time, e.x, e.y, e.Q] for e in simulator.history], dtype=float)
    metadata = G.fitting_metadata(law)
    counters = G.asdict(simulator.counts)
    return rows, metadata, counters, law


def thinning_fraction(counters):
    return float((counters["rejected_immigrants"] + counters["rejected_offspring"])
                 / counters["queue_processed"])


class SyntheticAnnular:
    """Eight-parameter S8 backbone with a selectable annular stress kernel."""

    def __init__(self, phase, native, kernel="ann2"):
        self.p = phase
        self.native = native
        self.kernel = kernel
        self.gamma = GAMMA
        self._deficit_cache = {}
        self._temporal = {}

    def _event_stress(self, theta):
        a, d, n, logc, p, eta, logell, logpsi = theta
        x12 = np.array([a, d, n, logc, p, math.log(10.0), 0.0, 2.0,
                        eta, logell, logpsi, self.gamma], dtype=float)
        data = dict(lag=self.p.lag, r2=self.p.event_r2, past=self.p.lag > 0)
        out = self.native.rows(data, self.p.a["parent_excess"],
                               self.p.a["parent_fertility"], x12,
                               kernel=self.kernel, scaled=False,
                               need_h=False, need_g=True)
        return out[:, 6], out[:, 7], out[:, 8]

    def deficit(self, theta, order=8):
        key = (int(order),) + tuple(float(v) for v in theta) + (self.kernel,)
        if key in self._deficit_cache:
            return self._deficit_cache[key].copy()
        S8 = load_s8()
        grid = self.p.plan(order)
        t, w, area, b, r2 = grid["t"], grid["w"], grid["area"], grid["b"], grid["r2"]
        tkey = (int(order), float(theta[3]), float(theta[4]))
        if self._temporal.get("key") != tkey:
            lag = t[:, None] - self.p.a["parent_time"][None, :]
            self._temporal = dict(
                key=tkey,
                value=np.concatenate(
                    [v.T for v in S8.temporal(lag, theta[3], theta[4])], axis=1
                ),
            )
        temporal_fields = self._temporal["value"]
        marks = np.exp(self.gamma * self.p.a["parent_excess"])
        theta8 = np.asarray(theta, dtype=float)
        total = np.zeros(9)
        for start in range(0, len(b), 256):
            sl = slice(start, start + 256)
            h = np.ascontiguousarray(grid["coeff"][sl] @ temporal_fields)
            total += self.native.joint_integral_annular(
                self.p.a["parent_time"], marks, r2[sl], area[sl], b[sl], t, w, h,
                theta8, self.p.m["T0"], kernel=self.kernel, inclusive=True,
            )
        self._deficit_cache[key] = total.copy()
        return total

    def evaluate(self, theta, model="null", order=8):
        theta = np.asarray(theta, dtype=float)
        if theta.shape != (8,) or not np.isfinite(theta).all():
            raise ValueError("eight finite coordinates required")
        hp, E, eg = self.p.baseline(theta)
        a, d, n, logc, p, eta, logell, logpsi = theta
        x = self.p.a["event_x"]
        logB = a + d * x + np.log(self.p.a["event_background_density"])
        H = hp[0]
        logH = np.full(len(H), -np.inf)
        if n > 0:
            np.log(n * H, out=logH, where=H > 0)
        basepoint = np.logaddexp(logB, logH)
        rawlog = np.zeros(len(H))
        np.log(H, out=rawlog, where=H > 0)
        if model == "null":
            point = basepoint
            fraction = np.exp(logB - basepoint)
            trigger_fraction = np.zeros(len(H))
            np.exp(logH - basepoint, out=trigger_fraction, where=H > 0)
            ratio = np.zeros(len(H))
            np.exp(rawlog - basepoint, out=ratio, where=H > 0)
            pg = np.array([
                float(fraction.sum()),
                float((x * fraction).sum()),
                float(ratio.sum()),
                float((trigger_fraction * (hp[1] / np.where(H > 0, H, 1))).sum()),
                float((trigger_fraction * (hp[2] / np.where(H > 0, H, 1))).sum()),
                0.0, 0.0, 0.0,
            ])
            gradient = np.asarray(eg, dtype=float) - pg
            P = float(point.sum())
            return dict(P=P, E=float(E), C=-float(E), M=float(self.p.M),
                        joint=float(P - E + self.p.M), nll=float(E - P - self.p.M)), gradient
        G, L, Q = self._event_stress(theta)
        point = basepoint - eta * G
        fraction = np.exp(logB - basepoint)
        trigger_fraction = np.zeros(len(H))
        np.exp(logH - basepoint, out=trigger_fraction, where=H > 0)
        ratio = np.zeros(len(H))
        np.exp(rawlog - basepoint, out=ratio, where=H > 0)
        c_ratio = hp[1] / np.where(H > 0, H, 1)
        p_ratio = hp[2] / np.where(H > 0, H, 1)
        pg = np.array([
            float(fraction.sum()),
            float((x * fraction).sum()),
            float(ratio.sum()),
            float((trigger_fraction * c_ratio).sum()),
            float((trigger_fraction * p_ratio).sum()),
            float(-G.sum()),
            float(-(eta * L).sum()),
            float(-(eta * Q).sum()),
        ])
        deficit = self.deficit(theta, order)
        E_total = E - deficit[0]
        eg_total = np.asarray(eg, dtype=float) - deficit[1:]
        gradient = eg_total - pg
        P = float(point.sum())
        return dict(P=P, E=float(E_total), C=-float(E_total), M=float(self.p.M),
                    joint=float(P - E_total + self.p.M),
                    nll=float(E_total - P - self.p.M)), gradient


class FastSyntheticAnnular(SyntheticAnnular):
    """Same likelihood with the frozen spatial plan and a coarser temporal plan.

    The archived order-8 grid carries 5,952 log-panel time nodes per phase; the
    fitting grid uses four Gauss nodes per parent interval. The spatial plan is
    the frozen adaptive order-8/16 plan, so spatial cusps remain resolved. The
    final order-16 scores use eight temporal nodes per interval.
    """

    def __init__(self, phase, native, kernel="ann2", time_order=8, spatial_order=12):
        super().__init__(phase, native, kernel)
        self.time_order = int(time_order)
        self.spatial_order = int(spatial_order)
        self._fast_grids = {}

    def _build_fast_grid(self, order):
        S8 = load_s8()
        from numpy.polynomial.legendre import leggauss

        a = self.p.a
        z, wz = leggauss(self.spatial_order)
        xy, space_weight, cells = [], [], []
        for k, (x0, x1, y0, y1) in enumerate(a["rectangles"]):
            xx = (x0 + x1) / 2.0 + (x1 - x0) / 2.0 * z
            yy = (y0 + y1) / 2.0 + (y1 - y0) / 2.0 * z
            X, Y = np.meshgrid(xx, yy)
            xy.extend(np.c_[X.ravel(), Y.ravel()])
            space_weight.extend((np.outer(wz, wz) * (x1 - x0) * (y1 - y0) / 4.0).ravel())
            cells.extend([k] * (self.spatial_order * self.spatial_order))
        xy = np.asarray(xy, dtype=float)
        space_weight = np.asarray(space_weight, dtype=float)
        cells = np.asarray(cells, dtype=int)
        controls = self.p.modules["controls_campaign"]
        b, _cells = controls.background(xy, a, self.p.m)
        r2 = np.empty((len(xy), len(a["parent_time"])))
        for j in range(0, len(xy), 512):
            r2[j:j + 512] = ((xy[j:j + 512, None, :] - a["parent_xy"][None, :, :]) ** 2).sum(axis=2)
        rho = a["reference_pi"][cells] / a["cell_areas"][cells]
        coeff = (np.exp(-2.0 * np.log1p(r2 / self.p.m["sigma"] ** 2))
                 * rho[:, None] * a["parent_fertility"][None, :]
                 / a["parent_normalizer"][None, :])
        t, w = controls.time_plan(
            a["parent_time"], self.p.m["start"], self.p.m["end"], 0.0001,
            self.time_order,
        )
        grid = dict(
            xy=xy, space_weight=space_weight * b, area=space_weight, b=b,
            r2=r2, coeff=coeff, t=np.ascontiguousarray(t), w=np.ascontiguousarray(w),
            xx=2.0 * t / self.p.m["T0"] - 1.0,
        )
        self._fast_grids[order] = grid
        return grid

    def deficit(self, theta, order=8):
        key = (int(order),) + tuple(float(v) for v in theta) + (self.kernel,)
        if key in self._deficit_cache:
            return self._deficit_cache[key].copy()
        grid = self._fast_grids.get(order) or self._build_fast_grid(order)
        S8 = load_s8()
        t, w = grid["t"], grid["w"]
        tkey = (int(order), float(theta[3]), float(theta[4]))
        if self._temporal.get("key") != tkey:
            lag = t[:, None] - self.p.a["parent_time"][None, :]
            self._temporal = dict(
                key=tkey,
                value=np.concatenate(
                    [v.T for v in S8.temporal(lag, theta[3], theta[4])], axis=1
                ),
            )
        temporal_fields = self._temporal["value"]
        marks = np.exp(self.gamma * self.p.a["parent_excess"])
        theta8 = np.asarray(theta, dtype=float)
        total = np.zeros(9)
        for start in range(0, len(grid["b"]), 256):
            sl = slice(start, start + 256)
            h = np.ascontiguousarray(grid["coeff"][sl] @ temporal_fields)
            total += self.native.joint_integral_annular(
                self.p.a["parent_time"], marks, grid["r2"][sl], grid["area"][sl],
                grid["b"][sl], t, w, h, theta8, self.p.m["T0"],
                kernel=self.kernel, inclusive=True,
            )
        self._deficit_cache[key] = total.copy()
        return total


def make_phase(rows, metadata, start, end, native, modules=None):
    S8 = load_s8()
    if modules is None:
        modules = S8.archived()
    return S8.phase_from_rows(rows, metadata, start, end, modules, None)


def shared_bounds():
    return [(-12.0, 0.0), (-2.0, 2.0), (0.0, 0.98), (math.log(0.0001), math.log(20.0)),
            (1.01, 2.5)]


def inhibition_bounds():
    return [(0.0, 4.0), (math.log(5.0), math.log(150.0)),
            (math.log(1.0 / 24.0), math.log(365.0))]


def null_starts(n_train):
    a0 = float(np.clip(math.log(0.6 * max(n_train, 1) / 365.0), -11.5, -0.1))
    templates = [
        (0.0, -0.2, 0.2, 0.0001, 1.1),
        (0.0, 0.2, 0.6, 0.1, 1.3),
        (-0.5, 0.2, 0.2, 0.01, 2.5),
    ]
    out = []
    for da, d, n, c, p in templates:
        out.append(np.array([float(np.clip(a0 + da, -12.0, 0.0)), d, n, math.log(c), p]))
    return out


def fit_arm(synthetic, model, starts, order=8, maxiter=200):
    box = shared_bounds() + ([] if model == "null" else inhibition_bounds())
    dims = len(box)
    records = []
    for index, start in enumerate(starts):
        started = time.time()
        base = np.asarray(start, dtype=float).copy()
        if model == "null":
            base = base[:5]
        else:
            base = base[:dims]

        def target(v):
            full = np.r_[v, [0.0, math.log(30.0), math.log(7.0)]] if model == "null" else v
            value, gradient = synthetic.evaluate(full, model, order)
            return value["nll"], gradient[:dims]

        opt = minimize(target, base, jac=True, bounds=box, method="L-BFGS-B",
                       options=dict(maxiter=maxiter, maxls=200, ftol=1e-10, gtol=2e-6))
        full = (np.r_[opt.x, [0.0, math.log(30.0), math.log(7.0)]]
                if model == "null" else np.asarray(opt.x, dtype=float))
        value, gradient = synthetic.evaluate(full, model, order)
        records.append(dict(start=index, success=bool(opt.success), message=str(opt.message),
                            nfev=int(opt.nfev), nit=int(opt.nit), nll=float(value["nll"]),
                            parameters=[float(v) for v in full],
                            gradient=[float(v) for v in gradient],
                            seconds=float(time.time() - started)))
    valid = [r for r in records if r["success"] and math.isfinite(r["nll"])]
    if not valid:
        valid = [r for r in records if math.isfinite(r["nll"])]
    if not valid:
        raise ArithmeticError("no finite synthetic fit")
    selected = min(valid, key=lambda r: r["nll"])
    return dict(records=records, selected=selected)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Synthetic annular bank utilities")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--seeds", nargs="+", type=int, default=[499901, 499902, 499903])
    parser.add_argument("--etas", nargs="+", type=float, default=[0.2, 0.3, 0.4, 0.5])
    parser.add_argument("--ell", type=float, default=15.0)
    parser.add_argument("--psi", type=float, default=5.0)
    args = parser.parse_args()
    if args.pilot:
        for eta in args.etas:
            rows_all = []
            counters_all = []
            for seed in args.seeds:
                rows, metadata, counters, _law = generate_history(seed, eta, args.ell, args.psi)
                rows_all.append(rows)
                counters_all.append(counters)
            test = [int(np.sum(r[:, 0] >= 395)) for r in rows_all]
            train = [int(np.sum((r[:, 0] >= 30) & (r[:, 0] < 395))) for r in rows_all]
            frac = [thinning_fraction(c) for c in counters_all]
            print(json.dumps(dict(eta=eta, thinning=frac, mean_thinning=float(np.mean(frac)),
                                  test_events=test, mean_test=float(np.mean(test)),
                                  train_events=train, mean_train=float(np.mean(train))), indent=1))
