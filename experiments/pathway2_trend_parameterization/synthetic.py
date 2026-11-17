"""Fast native S8 / S04B evaluator with a selectable background clock.

The likelihood, spatial plan, temporal trigger fields and native deficit
integral follow ``experiments/s04b_joint_nuisance/model.py``.  Only the
background clock, its analytic integral and (for T3) the depletion residual
are replaced.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.s04b_joint_nuisance import model as S8  # noqa: E402
from experiments.pathway2_trend_parameterization.background import BackgroundLaw  # noqa: E402

SHARED_BOUNDS = [(-12.0, 0.0), (-2.0, 2.0), (0.0, 0.98),
                 (math.log(0.0001), math.log(20.0)), (1.01, 2.5)]
INHIBITION_BOUNDS = [(0.0, 4.0), (math.log(5.0), math.log(150.0)),
                     (math.log(1.0 / 24.0), math.log(365.0))]
SHARED_TEMPLATES = [
    (0.0, -0.2, 0.2, 0.0001, 1.1),
    (0.0, -0.2, 0.6, 0.001, 1.3),
    (0.0, 0.2, 0.2, 0.01, 1.1),
    (0.0, 0.2, 0.6, 0.1, 1.3),
    (-0.5, -0.2, 0.2, 1.0, 1.7),
    (-0.5, -0.2, 0.6, 20.0, 2.5),
    (-0.5, 0.2, 0.2, 0.01, 2.5),
    (-0.5, 0.2, 0.6, 0.1, 1.01),
]
INHIBITION_TEMPLATES = [
    (0.0, 30.0, 7.0), (0.1, 5.0, 1.0 / 24.0), (0.3, 15.0, 0.25),
    (0.7, 50.0, 7.0), (1.5, 150.0, 30.0), (3.0, 5.0, 365.0),
    (4.0, 150.0, 1.0 / 24.0), (0.5, 30.0, 365.0),
]


def reduced_indices(kind: str, model: str):
    shared = [0, 2, 3, 4] if kind == "T1" else [0, 1, 2, 3, 4]
    return shared if model == "null" else shared + [5, 6, 7]


def expand(x, kind: str, model: str) -> np.ndarray:
    """Map a reduced optimiser vector to the fixed eight-coordinate layout."""
    x = np.asarray(x, dtype=float)
    theta = np.zeros(8)
    if kind == "T1":
        theta[0], theta[2], theta[3], theta[4] = x[0], x[1], x[2], x[3]
        if model != "null":
            theta[5:] = x[4:]
    else:
        theta[:5] = x[:5]
        if model != "null":
            theta[5:] = x[5:]
    return theta


def bounds(kind: str, model: str):
    box = list(SHARED_BOUNDS)
    if kind == "T1":
        box = [box[i] for i in (0, 2, 3, 4)]
    if model != "null":
        box = box + list(INHIBITION_BOUNDS)
    return box


class LawPhase:
    """An S8/S04B phase under one background law."""

    def __init__(self, base, law: BackgroundLaw, native):
        self.base = base
        self.law = law
        self.native = native
        self.a = base.a
        self.m = base.m
        self.modules = base.modules
        self.lag = base.lag
        self.event_r2 = base.event_r2
        self.M = base.M
        self.evaluations = 0
        self._temporal = {}

    # -- shared frozen plan ---------------------------------------------
    def plan(self, order):
        return self.base.plan(order)

    def check(self):
        return self.base.check()

    # -- background exposure --------------------------------------------
    def baseline(self, theta):
        a, d, n, logc, p = theta[:5]
        ks = S8.temporal(self.lag, logc, p)
        a0 = self.a
        hp = [(v * a0["parent_fertility"][None, :] * a0["event_parent_density"]).sum(axis=1)
              for v in ks]
        js = S8.exposure(a0["parent_exposure_lo"], a0["parent_exposure_hi"], logc, p)
        jj = np.array([v @ a0["parent_fertility"] for v in js])
        B, Bd = self.law.integral(a, d, self.m["start"], self.m["end"])
        E = B + n * jj[0]
        grad = np.array([B, Bd, jj[0], n * jj[1], n * jj[2], 0.0, 0.0, 0.0])
        return hp, E, grad

    # -- depletion -------------------------------------------------------
    def deficit(self, theta, model, order):
        grid = self.plan(order)
        t = grid["t"]
        clock = self.law.x(t)
        inclusive = model == "LIplus_inclusive"
        plus = model != "LI"
        marks = np.exp((0.75 * math.log(10) if plus else 0.0) * self.a["parent_excess"])
        key = (order, float(theta[3]), float(theta[4]), inclusive)
        if self._temporal.get("key") != key:
            lag = t[:, None] - self.a["parent_time"][None, :]
            self._temporal = dict(
                key=key,
                value=np.concatenate([v.T for v in S8.temporal(lag, theta[3], theta[4])],
                                     axis=1),
            )
        fields = self._temporal["value"]
        total = np.zeros(9)
        orth = self.law.kind == "T3"
        for start in range(0, len(grid["b"]), 256):
            self.check()
            sl = slice(start, start + 256)
            h = np.ascontiguousarray(grid["coeff"][sl] @ fields) if inclusive else None
            total += self.native.integrate(
                self.a["parent_time"], marks, grid["r2"][sl], grid["area"][sl],
                grid["b"][sl], t, grid["w"], h, theta, clock,
                orth, self.law.orth_c, self.law.orth_k, horizon=self.m["T0"],
            )
        return total

    # -- likelihood ------------------------------------------------------
    def evaluate(self, theta, model="null", order=8, require_gradient=True):
        self.check()
        theta = np.asarray(theta, dtype=float)
        if theta.shape != (8,) or not np.isfinite(theta).all():
            raise ValueError("Eight finite coordinates required")
        self.evaluations += 1
        hp, E, eg = self.baseline(theta)
        B_total = float(eg[0])
        a, d, n, _, _, eta, logell, logpsi = theta
        x = self.law.x(self.a["event_time"])
        logB = a + d * x + np.log(self.a["event_background_density"])
        H = hp[0]
        logH = np.full(len(H), -np.inf)
        if n > 0:
            np.log(n * H, out=logH, where=H > 0)
        G = L = Q = np.zeros(len(H))
        if model != "null":
            ell = math.exp(logell)
            psi = math.exp(logpsi)
            r = self.event_r2 / (ell * ell)
            z = np.maximum(self.lag, 0) / psi
            gamma = 0.75 * math.log(10) if model != "LI" else 0.0
            terms = np.exp(gamma * self.a["parent_excess"][None, :] - z) / (1 + r) ** 2 * (self.lag > 0)
            G = terms.sum(axis=1)
            L = (terms * 4 * r / (1 + r)).sum(axis=1)
            Q = (terms * z).sum(axis=1)
            G = self.law.deplete(G, x)
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
            deficit = self.deficit(theta, model, order)
            E -= deficit[0]
            eg -= deficit[1:]
        P = float(point.sum())
        joint = P - E + self.M
        gradient = eg - pg
        if not all(math.isfinite(v) for v in (P, E, joint)) or E < max(
                getattr(self, "exposure_floor", -1e-9),
                getattr(self, "exposure_relative_floor", 0.0) * B_total):
            raise ArithmeticError("Nonfinite or negative full exposure")
        if require_gradient and not np.isfinite(gradient).all():
            raise ArithmeticError("Finite objective has unrepresentable gradient")
        return dict(P=P, E=float(E), C=-float(E), M=self.M, joint=joint, nll=-joint), gradient


class FastLawPhase(LawPhase):
    """Same likelihood on a frozen Gauss plan for exploratory refits.

    The archived adaptive plan carries 8,000 spatial nodes and 5,952 time
    nodes; eight-start refits at that resolution are prohibitively slow.  This
    plan uses tensor Gauss-Legendre space (12 or 16 per axis per cell) and
    log-panel time (8 or 16 nodes per interval).  The exact archived plan is
    always re-evaluated for the selected training states and all held-out
    scores, and the audit records the quadrature delta.
    """

    def __init__(self, base, law, native, spatial_order=12, time_order=8):
        super().__init__(base, law, native)
        self.spatial_order = int(spatial_order)
        self.time_order = int(time_order)
        self._fast = {}
        self.exposure_floor = 0.0
        self.exposure_relative_floor = 0.005

    def _build(self, key):
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
        grid = dict(b=b, area=space_weight, r2=np.ascontiguousarray(r2),
                    coeff=coeff, t=np.ascontiguousarray(t), w=np.ascontiguousarray(w),
                    space_nodes=len(xy), time_nodes=len(t),
                    parents=len(a["parent_time"]))
        self._fast[key] = grid
        return grid

    def plan(self, order):
        return self._build(self._grid_key(order))

    def _grid_key(self, order):
        if order == 8:
            return self.spatial_order, self.time_order
        if order == 16:
            return max(self.spatial_order, 16), max(self.time_order, 16)
        return max(self.spatial_order, 20), max(self.time_order, 24)


def adapt_t0_start(kind: str, theta_t0, model: str, law: BackgroundLaw | None = None):
    """Transform a T0 fitted state into a starting vector for another law."""
    theta = np.asarray(theta_t0, dtype=float).copy()
    if kind == "T1":
        # Preserve the average training background: mean x_trend on [30,395)
        # is -0.440789... for T0 = 760.
        mean_x = (30.0 + 395.0) / 760.0 - 1.0
        theta[0] = theta[0] + theta[1] * mean_x
        theta[1] = 0.0
    elif kind == "T2":
        # Preserve the background at the forecast origin, where x_clamp = 0.
        theta[0] = theta[0] + theta[1] * (2.0 * 395.0 / 760.0 - 1.0)
    return theta[reduced_indices(kind, model)]


def t3_projection(phase: LawPhase, ell: float, psi: float):
    """Freeze the training-event depletion projection for T3.

    The stress scale and time scale are fixed at their generating (S8/S04B) or
    archived (regional) values so the projection is defined before any
    inhibited fit and is not re-estimated at each optimiser step.
    """
    if phase.law.kind != "T3":
        return phase.law.projection
    x = phase.law.x(phase.a["event_time"])
    r = phase.event_r2 / (float(ell) ** 2)
    z = np.maximum(phase.lag, 0) / float(psi)
    gamma = 0.75 * math.log(10)
    terms = np.exp(gamma * phase.a["parent_excess"][None, :] - z) / (1 + r) ** 2 * (phase.lag > 0)
    g = terms.sum(axis=1)
    return phase.law.orthogonalise(g, x)


def fit_dstar_conditional(phase: LawPhase, t0_null_theta, maxiter=400):
    """True-trend control with the T0-fitted trigger nuisance held fixed.

    An unrestricted d = 0.2 refit develops a p -> 2.5, n -> 0 overfitting ridge
    on several S8 histories: it improves the training score while destroying
    the held-out forecast.  This control therefore fixes the shared trigger
    coordinates (n, log c, p) at the archived T0 null fit and refits only the
    intercept and, in the inhibited arm, (eta, log ell, log psi).  Both arms
    use the same background law and the same fixed shared nuisance.
    """
    base = np.asarray(t0_null_theta, dtype=float)
    fixed = dict(d=0.2, n=float(base[2]), logc=float(base[3]), p=float(base[4]))

    def expand(v, model):
        theta = np.r_[float(v[0]), fixed["d"], fixed["n"], fixed["logc"], fixed["p"], 0.0, 0.0, 0.0]
        if model != "null":
            theta[5:] = v[1:]
        return theta

    box_null = [(-12.0, 0.0)]
    box_inh = [(-12.0, 0.0), (0.0, 4.0),
               (math.log(5.0), math.log(150.0)),
               (math.log(1.0 / 24.0), math.log(365.0))]
    a0 = float(base[0])
    null_starts = [np.array([a]) for a in (a0, a0 + 0.5, a0 - 0.5)]
    null_candidates = []
    for start in null_starts:
        def target(v):
            theta = expand(v, "null")
            try:
                value, gradient = phase.evaluate(theta, "null", 8)
            except (ArithmeticError, FloatingPointError, OverflowError):
                return 1e6, np.zeros(1)
            return float(value["nll"]), np.asarray(gradient[:1])

        opt = minimize(target, start, jac=True, bounds=box_null, method="L-BFGS-B",
                       options=dict(maxiter=maxiter, maxls=100, ftol=1e-10, gtol=2e-5))
        theta = expand(opt.x, "null")
        try:
            value, gradient = phase.evaluate(theta, "null", 8)
        except (ArithmeticError, FloatingPointError, OverflowError):
            continue
        null_candidates.append(dict(parameters=theta.tolist(), score=value,
                                    gradient=np.asarray(gradient).tolist(),
                                    success=bool(opt.success), nfev=int(opt.nfev)))
    if not null_candidates:
        raise ArithmeticError("no feasible conditional true-trend null")
    null_selected = min(null_candidates, key=lambda v: v["score"]["nll"])
    starts = []
    for eta, ell, psi in ((0.1, 5.0, 1.0 / 24.0), (0.4, 15.0, 5.0),
                          (1.0, 50.0, 30.0), (0.2, 15.0, 5.0)):
        starts.append(np.array([null_selected["parameters"][0], eta,
                                math.log(ell), math.log(psi)]))
    candidates = []
    for start in starts:
        def target(v):
            theta = expand(v, "alt")
            try:
                value, gradient = phase.evaluate(theta, "LIplus_inclusive", 8)
            except (ArithmeticError, FloatingPointError, OverflowError):
                return 1e6, np.zeros(4)
            return float(value["nll"]), np.asarray(gradient[[0, 5, 6, 7]])

        opt = minimize(target, start, jac=True, bounds=box_inh, method="L-BFGS-B",
                       options=dict(maxiter=maxiter, maxls=100, ftol=1e-10, gtol=2e-5))
        theta = expand(opt.x, "alt")
        try:
            value, gradient = phase.evaluate(theta, "LIplus_inclusive", 8)
        except (ArithmeticError, FloatingPointError, OverflowError):
            continue
        candidates.append(dict(parameters=theta.tolist(), score=value,
                               gradient=np.asarray(gradient).tolist(),
                               success=bool(opt.success), nfev=int(opt.nfev)))
    if not candidates:
        raise ArithmeticError("no feasible conditional true-trend inhibited arm")
    selected = min(candidates, key=lambda v: v["score"]["nll"])
    null_score = null_selected["score"]
    if null_score["nll"] <= selected["score"]["nll"] + 1e-9:
        theta0 = np.asarray(null_selected["parameters"], dtype=float)
        value0, grad0 = phase.evaluate(theta0, "LIplus_inclusive", 8)
        selected = dict(parameters=theta0.tolist(), score=value0,
                        gradient=np.asarray(grad0).tolist(), success=True,
                        nfev=0, nested_null=True)
    return dict(null=null_selected, inhibited=selected,
                fixed_shared=fixed, null_candidates=null_candidates,
                inhibited_candidates=candidates)


def starts_for(kind: str, n_train: int, model: str, null_theta=None):
    a0 = float(np.clip(math.log(0.6 * max(n_train, 1) / 365.0), -11.5, -0.1))
    out = []
    for i, (da, d, n, c, p) in enumerate(SHARED_TEMPLATES):
        shared = [float(np.clip(a0 + da, -12.0, 0.0)), d, n, math.log(c), p]
        if kind == "T1":
            shared = [shared[0], shared[2], shared[3], shared[4]]
        if model == "null":
            out.append(shared)
        else:
            if i == 0 and null_theta is not None:
                shared = [float(v) for v in np.asarray(null_theta)[reduced_indices(kind, "null")]]
            eta, ell, psi = INHIBITION_TEMPLATES[i]
            out.append([*shared, eta, math.log(ell), math.log(psi)])
    return out


def fit_arm(phase: LawPhase, model: str, kind: str, n_train: int,
            null_theta=None, maxiter=400, maxls=100, n_starts=8, extra_start=None):
    box = bounds(kind, model)
    dim = len(box)
    lo = np.asarray([b[0] for b in box])
    hi = np.asarray([b[1] for b in box])
    records = []
    candidates = []
    starts = starts_for(kind, n_train, model, null_theta)
    if extra_start is not None:
        starts = [np.asarray(extra_start, dtype=float)[:dim]] + starts[:max(0, n_starts - 1)]
    else:
        starts = starts[:n_starts]
    for index, initial in enumerate(starts):
        start = np.clip(np.asarray(initial, dtype=float)[:dim], lo, hi)
        current = start.copy()
        success = False
        for attempt in range(2):
            failures = [0]

            def target(v):
                theta = expand(v, kind, model)
                try:
                    value, gradient = phase.evaluate(theta, model, 8)
                except (ArithmeticError, FloatingPointError, OverflowError):
                    failures[0] += 1
                    return 1e6, np.zeros(dim)
                return float(value["nll"]), np.asarray(gradient[:dim])

            opt = minimize(target, current, jac=True, bounds=box, method="L-BFGS-B",
                           options=dict(maxiter=maxiter if attempt == 0 else 4 * maxiter,
                                        maxls=maxls, ftol=1e-10, gtol=2e-5))
            current = np.asarray(opt.x, dtype=float)
            theta = expand(current, kind, model)
            try:
                value, gradient = phase.evaluate(theta, model, 8)
            except (ArithmeticError, FloatingPointError, OverflowError) as exc:
                records.append(dict(start_index=index, attempt=attempt,
                                    success=False, message=str(exc), nfev=int(opt.nfev),
                                    nit=int(opt.nit), parameters=theta.tolist(),
                                    nll=None, gradient=None))
                continue
            records.append(dict(start_index=index, attempt=attempt,
                                success=bool(opt.success), message=str(opt.message),
                                nfev=int(opt.nfev), nit=int(opt.nit),
                                parameters=theta.tolist(), nll=float(value["nll"]),
                                gradient=np.asarray(gradient, dtype=float).tolist()))
            if opt.success:
                success = True
                break
        if success:
            candidates.append(dict(state_index=len(candidates), start_index=index,
                                   parameters=theta.tolist(), score=value,
                                   gradient=np.asarray(gradient, dtype=float).tolist()))
    if not candidates:
        raise ArithmeticError("No resolved start for " + model)
    selected = min(candidates, key=lambda v: (v["score"]["nll"], v["start_index"]))
    null_candidate = None
    if model != "null":
        # The exact eta=0 state with the selected null coordinates is always
        # an eligible nested candidate.
        theta0 = np.asarray(null_theta, dtype=float).copy()
        theta0[5:] = 0.0
        value0, grad0 = phase.evaluate(theta0, model, 8)
        null_candidate = dict(state_index=len(candidates), kind="exact_nested_null",
                              parameters=theta0.tolist(), score=value0,
                              gradient=np.asarray(grad0, dtype=float).tolist())
        if value0["nll"] <= selected["score"]["nll"] + 1e-9:
            selected = null_candidate
    return dict(model=model, law=kind, selected=selected, candidates=candidates,
                records=records, resolved_starts=sum(1 for c in candidates),
                required_starts=len(SHARED_TEMPLATES),
                nested_null=(selected is null_candidate and null_candidate is not None))


def score(phase: LawPhase, theta, model, order=16):
    value, gradient = phase.evaluate(theta, model, order)
    return value, gradient


def load_s8_case(seed: int, modules, native):
    data = ROOT / "reproduction/synthetic/s8_moderate_total"
    receipt = next(r for r in _read_json(data / "receipts.json") if r["seed"] == seed)
    rows = np.load(data / f"{seed}.npz")["rows"]
    base_train = S8.phase_from_rows(rows, receipt["metadata"], 30.0, 395.0, modules, None)
    base_test = S8.phase_from_rows(rows, receipt["metadata"], 395.0, 760.0, modules, None)
    return rows, receipt, base_train, base_test


def load_s04b_case(case, modules):
    data = ROOT / "reproduction/synthetic"
    rows = np.load(data / case["history"])["rows"]
    meta = _read_json(data / case["generator_receipt"])
    # S04B records do not store fitting metadata; rebuild it from the roster.
    G = modules["generator"]
    name = G.MATCHED_NAMES[case["regime"] - 4]
    _, bg, eta, ell, psi = G.ROSTER[name]
    law = G.Law(name, case["seed"], bg, eta, ell, psi)
    gm = G.fitting_metadata(law)
    base_train = S8.phase_from_rows(rows, gm, 30.0, 395.0, modules, None)
    base_test = S8.phase_from_rows(rows, gm, 395.0, 760.0, modules, None)
    return rows, gm, base_train, base_test


def _read_json(path):
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))
