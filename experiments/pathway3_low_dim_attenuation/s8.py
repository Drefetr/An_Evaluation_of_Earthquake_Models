"""S8/S04B evaluator for the Pathway 3 low-dimensional estimators.

The likelihood, frozen spatial/mark laws and native deficit recurrence follow
``experiments/s04b_joint_nuisance/model.py``.  This module adds only:

* a selectable background clock (archived trend T0 or stationary T1);
* a fast tensor-Gauss optimisation plan used for fitting, with the archived
  adaptive plan retained for every reported score;
* an explicit per-parent squared attenuation scale, so that
  ``ell_j = 10^(-2.44 + 0.59 M_j)`` can be evaluated exactly.

No sealed authority or pre-existing live-result file is written.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.s04b_joint_nuisance import model as CORE  # noqa: E402

SHARED_BOUNDS = [(-12.0, 0.0), (-2.0, 2.0), (0.0, 0.98),
                 (math.log(0.0001), math.log(20.0)), (1.01, 2.5)]
INHIBITION_BOUNDS = [(0.0, 4.0), (math.log(5.0), math.log(150.0)),
                     (math.log(1.0 / 24.0), math.log(365.0))]


class ClockT0:
    """Archived affine background clock x(t)=2t/T0-1."""
    kind = "T0"

    def __init__(self, T0: float):
        self.T0 = float(T0)

    def x(self, t):
        return 2.0 * np.asarray(t, dtype=float) / self.T0 - 1.0

    def integral(self, a, d, lo, hi):
        return CORE.background_exposure(a, d, lo, hi, self.T0)

    def deplete(self, g, x):
        return np.asarray(g, dtype=float)

    def describe(self):
        return dict(kind=self.kind, T0=self.T0)


class ClockT1:
    """Stationary background clock: d is identically zero."""
    kind = "T1"

    def x(self, t):
        return np.zeros_like(np.asarray(t, dtype=float))

    def integral(self, a, d, lo, hi):
        value = math.exp(a) * (float(hi) - float(lo))
        return value, 0.0

    def deplete(self, g, x):
        return np.asarray(g, dtype=float)

    def describe(self):
        return dict(kind=self.kind, T0=None)


class Phase3(CORE.Phase):
    """Archived S8 likelihood with a selectable clock and attenuation scale."""

    def __init__(self, arrays, meta, modules, native, clock, deadline=math.inf):
        super().__init__(arrays, meta, modules, native, deadline)
        self.clock = clock
        self.fast = False
        self.spatial_order = 12
        self.time_order = 8
        self._fast_grids = {}
        self.exposure_floor = None
        self.exposure_relative_floor = None

    # -- background ------------------------------------------------------
    def baseline(self, theta):
        a, d, n, logc, p = theta[:5]
        ks = CORE.temporal(self.lag, logc, p)
        a0 = self.a
        hp = [(v * a0["parent_fertility"][None, :] * a0["event_parent_density"]).sum(axis=1)
              for v in ks]
        js = CORE.exposure(a0["parent_exposure_lo"], a0["parent_exposure_hi"], logc, p)
        jj = np.array([v @ a0["parent_fertility"] for v in js])
        B, Bd = self.clock.integral(a, d, self.m["start"], self.m["end"])
        E = B + n * jj[0]
        grad = np.array([B, Bd, jj[0], n * jj[1], n * jj[2], 0.0, 0.0, 0.0])
        return hp, E, grad

    # -- quadrature plan -------------------------------------------------
    def plan(self, order):
        if not self.fast:
            return super().plan(order)
        key = self._grid_key(order)
        if key not in self._fast_grids:
            self._fast_grids[key] = self._build_fast(key)
        return self._fast_grids[key]

    def _grid_key(self, order):
        if order <= 8:
            return self.spatial_order, self.time_order
        if order <= 16:
            return max(self.spatial_order, 16), max(self.time_order, 16)
        return max(self.spatial_order, 20), max(self.time_order, 24)

    def _build_fast(self, key):
        from numpy.polynomial.legendre import leggauss

        spatial, time_order = key
        a = self.a
        z, wz = leggauss(spatial)
        xy, space_weight, cells = [], [], []
        for k, (x0, x1, y0, y1) in enumerate(a["rectangles"]):
            xx = (x0 + x1) / 2.0 + (x1 - x0) / 2.0 * z
            yy = (y0 + y1) / 2.0 + (y1 - y0) / 2.0 * z
            X, Y = np.meshgrid(xx, yy)
            xy.extend(np.c_[X.ravel(), Y.ravel()])
            space_weight.extend((np.outer(wz, wz) * (x1 - x0) * (y1 - y0) / 4.0).ravel())
            cells.extend([k] * (spatial * spatial))
        xy = np.asarray(xy, dtype=float)
        space_weight = np.asarray(space_weight, dtype=float)
        cells = np.asarray(cells, dtype=int)
        controls = self.modules["controls_campaign"]
        b, _cells = controls.background(xy, a, self.m)
        r2 = np.empty((len(xy), len(a["parent_time"])))
        for j in range(0, len(xy), 512):
            r2[j:j + 512] = ((xy[j:j + 512, None, :] - a["parent_xy"][None, :, :]) ** 2).sum(axis=2)
        rho = a["reference_pi"][cells] / a["cell_areas"][cells]
        coeff = (np.exp(-2.0 * np.log1p(r2 / self.m["sigma"] ** 2))
                 * rho[:, None] * a["parent_fertility"][None, :]
                 / a["parent_normalizer"][None, :])
        t, w = controls.time_plan(a["parent_time"], self.m["start"], self.m["end"],
                                  0.0001, time_order)
        return dict(b=b, area=space_weight, r2=np.ascontiguousarray(r2),
                    coeff=coeff, t=np.ascontiguousarray(t), w=np.ascontiguousarray(w),
                    space_nodes=len(xy), time_nodes=len(t),
                    parents=len(a["parent_time"]))

    # -- deficit ---------------------------------------------------------
    def deficit(self, theta, model, order, ell2=None):
        if self.native is None:
            raise ValueError("native integral required for an inhibited law")
        grid = self.plan(order)
        t = grid["t"]
        inclusive = model == "LIplus_inclusive"
        plus = model != "LI"
        marks = np.exp((0.75 * math.log(10) if plus else 0.0) * self.a["parent_excess"])
        key = (order, float(theta[3]), float(theta[4]), inclusive)
        if self._temporal.get("key") != key:
            lag = t[:, None] - self.a["parent_time"][None, :]
            self._temporal = dict(
                key=key,
                value=np.concatenate([v.T for v in CORE.temporal(lag, theta[3], theta[4])], axis=1),
            )
        fields = self._temporal["value"]
        total = np.zeros(9)
        horizon = self.m["T0"]
        clock = self.clock.x(t)
        orthogonal = False
        for start in range(0, len(grid["b"]), 256):
            self.check()
            sl = slice(start, start + 256)
            h = np.ascontiguousarray(grid["coeff"][sl] @ fields) if inclusive else None
            if ell2 is None:
                total += self.native.integrate(
                    self.a["parent_time"], marks, grid["r2"][sl], grid["area"][sl],
                    grid["b"][sl], t, grid["w"], h, theta, clock, orthogonal,
                    0.0, 0.0, horizon=horizon,
                )
            else:
                total += self.native.integrate_ell(
                    self.a["parent_time"], marks, grid["r2"][sl], grid["area"][sl],
                    grid["b"][sl], t, grid["w"], h, theta, clock,
                    np.asarray(ell2, dtype=float) ** 2,
                    orthogonal, 0.0, 0.0, horizon=horizon,
                )
        return total

    # -- likelihood ------------------------------------------------------
    def event_stress(self, theta, ell2=None):
        """Attenuation stress G at the observed events (strict prehistory)."""
        theta = np.asarray(theta, dtype=float)
        if ell2 is None:
            ell_vec = np.full(len(self.a["parent_time"]), math.exp(theta[6]))
        else:
            ell_vec = np.asarray(ell2, dtype=float)
        psi = math.exp(theta[7])
        gamma = 0.75 * math.log(10)
        r = self.event_r2 / (ell_vec[None, :] ** 2)
        z = np.maximum(self.lag, 0.0) / psi
        terms = np.exp(gamma * self.a["parent_excess"][None, :] - z) / (1 + r) ** 2 * (self.lag > 0)
        return dict(G=terms.sum(axis=1), L=(terms * 4 * r / (1 + r)).sum(axis=1),
                    Q=(terms * z).sum(axis=1))

    def evaluate(self, theta, model="null", order=8, require_gradient=True, ell2=None):
        self.check()
        theta = np.asarray(theta, dtype=float)
        if theta.shape != (8,) or not np.isfinite(theta).all():
            raise ValueError("Eight finite coordinates required")
        self.evaluations += 1
        hp, E, eg = self.baseline(theta)
        B_total = float(eg[0])
        a, d, n, _, _, eta, logell, logpsi = theta
        x = self.clock.x(self.a["event_time"])
        logB = a + d * x + np.log(self.a["event_background_density"])
        H = hp[0]
        logH = np.full(len(H), -np.inf)
        if n > 0:
            np.log(n * H, out=logH, where=H > 0)
        G = L = Q = np.zeros(len(H))
        if ell2 is None:
            ell_vec = np.full(len(self.a["parent_time"]), math.exp(logell))
        else:
            ell_vec = np.asarray(ell2, dtype=float)
        if model != "null":
            psi = math.exp(logpsi)
            r = self.event_r2 / (ell_vec[None, :] ** 2)
            z = np.maximum(self.lag, 0.0) / psi
            gamma = 0.75 * math.log(10) if model != "LI" else 0.0
            terms = np.exp(gamma * self.a["parent_excess"][None, :] - z) / (1 + r) ** 2 * (self.lag > 0)
            G = terms.sum(axis=1)
            L = (terms * 4 * r / (1 + r)).sum(axis=1)
            Q = (terms * z).sum(axis=1)
            G = self.clock.deplete(G, x)
        inclusive = model == "LIplus_inclusive"
        basepoint = np.logaddexp(logB, logH)
        point = basepoint - eta * G if inclusive else np.logaddexp(logB - eta * G, logH)
        if model == "null":
            point = np.logaddexp(logB, logH)
        fraction = np.exp(logB - basepoint) if inclusive else np.exp(logB - eta * G - point)
        if model == "null":
            fraction = np.exp(logB - point)
        denominator = basepoint if inclusive else point
        ratio = np.zeros(len(H))
        rawlog = np.zeros(len(H))
        np.log(H, out=rawlog, where=H > 0)
        with np.errstate(over="ignore", invalid="ignore"):
            np.exp(rawlog - denominator, out=ratio, where=H > 0)
        trigger_fraction = np.zeros(len(H))
        if n > 0:
            np.exp(logH - denominator, out=trigger_fraction, where=H > 0)
        c_ratio = np.divide(hp[1], H, out=np.zeros(len(H)), where=H > 0)
        p_ratio = np.divide(hp[2], H, out=np.zeros(len(H)), where=H > 0)
        pg = np.array([fraction.sum(), (x * fraction).sum(), ratio.sum(),
                       (trigger_fraction * c_ratio).sum(),
                       (trigger_fraction * p_ratio).sum(), 0.0, 0.0, 0.0])
        if model != "null":
            f = np.ones(len(H)) if inclusive else fraction
            pg[5:] = [-(G * f).sum(), -(eta * L * f).sum(), -(eta * Q * f).sum()]
            deficit = self.deficit(theta, model, order, ell2=ell2)
            E -= deficit[0]
            eg -= deficit[1:]
        P = float(point.sum())
        joint = P - E + self.M
        gradient = eg - pg
        floor = -1e-9
        if self.exposure_relative_floor is not None:
            floor = max(floor, self.exposure_relative_floor * B_total)
        if not all(math.isfinite(v) for v in (P, E, joint)) or E < floor:
            raise ArithmeticError("Nonfinite or negative full exposure")
        if require_gradient and not np.isfinite(gradient).all():
            raise ArithmeticError("Finite objective has unrepresentable gradient")
        return dict(P=P, E=float(E), C=-float(E), M=self.M, joint=joint, nll=-joint), gradient


def load_s8(seed: int, clock, native, modules=None, fast=False,
            spatial_order=12, time_order=8):
    modules = modules or CORE.archived()
    data = ROOT / "reproduction/synthetic/s8_moderate_total"
    receipt = next(r for r in _read_json(data / "receipts.json") if r["seed"] == seed)
    rows = np.load(data / f"{seed}.npz")["rows"]
    base_train = CORE.phase_from_rows(rows, receipt["metadata"], 30.0, 395.0, modules, None)
    base_test = CORE.phase_from_rows(rows, receipt["metadata"], 395.0, 760.0, modules, None)
    train = Phase3(base_train.a, base_train.m, modules, native, clock)
    test = Phase3(base_test.a, base_test.m, modules, native, clock)
    if fast:
        for phase in (train, test):
            phase.fast = True
            phase.spatial_order = int(spatial_order)
            phase.time_order = int(time_order)
            phase.exposure_relative_floor = 0.005
    return dict(rows=rows, receipt=receipt, train=train, test=test,
                base_train=base_train, base_test=base_test)


def load_s04b(case, clock, native, modules=None, fast=False,
              spatial_order=12, time_order=8):
    modules = modules or CORE.archived()
    data = ROOT / "reproduction/synthetic"
    rows = np.load(data / case["history"])["rows"]
    meta = _read_json(data / case["generator_receipt"])
    G = modules["generator"]
    name = G.MATCHED_NAMES[case["regime"] - 4]
    _, bg, eta, ell, psi = G.ROSTER[name]
    law = G.Law(name, case["seed"], bg, eta, ell, psi)
    gm = G.fitting_metadata(law)
    base_train = CORE.phase_from_rows(rows, gm, 30.0, 395.0, modules, None)
    base_test = CORE.phase_from_rows(rows, gm, 395.0, 760.0, modules, None)
    train = Phase3(base_train.a, base_train.m, modules, native, clock)
    test = Phase3(base_test.a, base_test.m, modules, native, clock)
    if fast:
        for phase in (train, test):
            phase.fast = True
            phase.spatial_order = int(spatial_order)
            phase.time_order = int(time_order)
            phase.exposure_relative_floor = 0.005
    return dict(rows=rows, metadata=meta, gm=gm, train=train, test=test,
                base_train=base_train, base_test=base_test)


def _read_json(path):
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))


def bounds_for(indices):
    out = []
    for i in indices:
        out.append(SHARED_BOUNDS[i] if i < 5 else INHIBITION_BOUNDS[i - 5])
    return out


def fit(phase, model, indices, base, starts, maxiter=250, order=8,
        ell2=None, label=""):
    """Fit a subset of the eight coordinates with analytic gradients."""
    base = np.asarray(base, dtype=float)
    box = bounds_for(indices)
    lo = np.asarray([b[0] for b in box])
    hi = np.asarray([b[1] for b in box])
    records = []
    candidates = []
    for index, start in enumerate(starts):
        start = np.clip(np.asarray(start, dtype=float), lo, hi)
        current = start.copy()
        resolved = False
        theta = None
        value = None
        gradient = None
        for attempt in range(2):
            def target(v):
                theta = base.copy()
                theta[indices] = v
                try:
                    value, gradient = phase.evaluate(theta, model, order, ell2=ell2)
                except (ArithmeticError, FloatingPointError, OverflowError):
                    return 1e6, np.zeros(len(indices))
                return float(value["nll"]), np.asarray(gradient)[indices]

            from scipy.optimize import minimize

            opt = minimize(target, current, jac=True, bounds=box, method="L-BFGS-B",
                           options=dict(maxiter=maxiter if attempt == 0 else 4 * maxiter,
                                        maxls=100, ftol=1e-10, gtol=2e-5))
            current = np.asarray(opt.x, dtype=float)
            theta = base.copy()
            theta[indices] = current
            try:
                value, gradient = phase.evaluate(theta, model, order, ell2=ell2)
            except (ArithmeticError, FloatingPointError, OverflowError) as exc:
                records.append(dict(start_index=index, attempt=attempt, success=False,
                                    message=str(exc), nfev=int(opt.nfev),
                                    parameters=theta.tolist()))
                continue
            records.append(dict(start_index=index, attempt=attempt,
                                success=bool(opt.success), message=str(opt.message),
                                nfev=int(opt.nfev), nit=int(opt.nit),
                                nll=float(value["nll"]), parameters=theta.tolist(),
                                free=[float(v) for v in current]))
            if opt.success:
                resolved = True
                break
            if attempt == 1 and value is not None and np.isfinite(value["nll"]):
                resolved = True
        if resolved and theta is not None and value is not None:
            candidates.append(dict(parameters=theta.tolist(), nll=float(value["nll"]),
                                   gradient=np.asarray(gradient, dtype=float).tolist(),
                                   start_index=index, free=[float(v) for v in current]))
    if not candidates:
        raise ArithmeticError("no resolved start for " + label)
    selected = min(candidates, key=lambda r: (r["nll"], r["start_index"]))
    return dict(label=label, model=model, indices=[int(i) for i in indices],
                selected=selected, candidates=candidates, records=records,
                resolved=True, starts=len(starts))
