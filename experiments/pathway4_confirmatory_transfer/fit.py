"""Training-only EP+ estimation: five-step declustering and profile arms."""
from __future__ import annotations

import math
from typing import Iterable, Optional

import numpy as np
from scipy.optimize import minimize

from .model import EPModel, EPView

BOUNDS = {
    "a": (-12.0, 0.0),
    "d": (-2.0, 2.0),
    "n": (0.0, 0.98),
    "log_c": (math.log(1e-4), math.log(20.0)),
    "p": (1.01, 2.5),
    "log_sigma0": (math.log(0.05), math.log(100.0)),
    "alpha_s": (0.0, 2.0),
    "q": (1.05, 3.0),
}
FREE_ORDER = ("a", "d", "n", "log_c", "p", "log_sigma0", "alpha_s", "q")


def _pack(free: Iterable[str]):
    names = tuple(free)
    lo = np.array([BOUNDS[k][0] for k in names])
    hi = np.array([BOUNDS[k][1] for k in names])
    return names, lo, hi


def fit_ep(model: EPModel, starts, free=("a", "d", "n", "log_c", "p",
                                         "log_sigma0", "alpha_s", "q"),
           maxiter: int = 600, ftol: float = 1e-11, gtol: float = 2e-6):
    """Multi-start L-BFGS-B on the analytic EP+ objective."""
    names, lo, hi = _pack(free)
    index = {k: i for i, k in enumerate(names)}
    records = []
    for start_index, start in enumerate(starts):
        start = np.asarray(start, dtype=float)
        if start.shape != (8,):
            raise ValueError("starts must be eight-vectors")
        x0 = np.clip(np.array([start[FREE_ORDER.index(k)] for k in names]),
                     lo, hi)

        def expand(v):
            x = start.copy()
            for name, value in zip(names, v):
                x[FREE_ORDER.index(name)] = float(value)
            return x

        def target(v):
            x = expand(v)
            value, gradient = model.objective(x)
            return value, np.array([gradient[FREE_ORDER.index(k)] for k in names])

        opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)),
                       method="L-BFGS-B",
                       options=dict(maxiter=maxiter, maxls=200, ftol=ftol,
                                    gtol=gtol))
        attempts = [dict(success=bool(opt.success), message=str(opt.message),
                         nfev=int(opt.nfev), nll=float(opt.fun))]
        if not opt.success:
            opt = minimize(target, opt.x, jac=True, bounds=list(zip(lo, hi)),
                           method="L-BFGS-B",
                           options=dict(maxiter=2000, maxls=400,
                                        ftol=1e-12, gtol=gtol))
            attempts.append(dict(success=bool(opt.success),
                                 message=str(opt.message),
                                 nfev=int(opt.nfev), nll=float(opt.fun)))
        x = expand(opt.x)
        records.append(dict(start=start_index, success=bool(opt.success),
                            message=str(opt.message), parameters=x.tolist(),
                            nll=float(opt.fun), nit=int(opt.nit),
                            nfev=int(opt.nfev), attempts=attempts))
    valid = [r for r in records if r["success"] and np.isfinite(r["nll"])]
    if not valid:
        raise ArithmeticError("no successful EP+ training optimization")
    return dict(records=records,
                selected=min(valid, key=lambda r: r["nll"]),
                complete=len(valid) == len(starts))


def _reweight(view: EPView, x, normalization: str):
    model = EPModel(view, normalization)
    h = model.H(x, deriv=False)
    mu = np.exp(x[0] + x[1] * view.event_x) * view.be
    lam = mu + x[2] * h
    if np.any(lam <= 0) or not np.isfinite(lam).all():
        raise FloatingPointError("non-positive intensity in declustering")
    weights = mu / lam
    return weights / weights.sum(), float(weights.sum())


def _replace_background(view: EPView, weights):
    bg = view.background
    view.background = type(bg)(bg.xy, bg.region, bg.h, weights,
                               reference_pi=(None if bg.floor_cell is None
                                             else bg.floor_cell * bg.region.cell_areas / 0.05),
                               floor_mode=bg.floor_mode)
    view.be = None
    return view


def decluster(view: EPView, starts, normalization: str = "plane",
              steps: int = 5, free=("a", "d", "n", "log_c", "p",
                                     "log_sigma0", "alpha_s", "q"),
              initial_multi_start: bool = True):
    """Five-step training immigrant-probability KDE declustering."""
    trace = []
    current = [np.asarray(s, dtype=float) for s in starts]
    for step in range(steps):
        model = EPModel(view, normalization)
        use = current if (step == 0 and initial_multi_start) else [current[0]]
        fit = fit_ep(model, use, free=free)
        x = np.asarray(fit["selected"]["parameters"], dtype=float)
        weights, expected_immigrants = _reweight(view, x, normalization)
        trace.append(dict(step=step, training_nll=fit["selected"]["nll"],
                          expected_immigrants=expected_immigrants,
                          parameters=x.tolist(),
                          fit_success=fit["selected"]["success"]))
        _replace_background(view, weights)
        current = [x]
    return view, trace


def final_null_fit(view: EPView, starts, normalization: str = "plane",
                   free=("a", "d", "n", "log_c", "p", "log_sigma0",
                         "alpha_s", "q")):
    model = EPModel(view, normalization)
    fit = fit_ep(model, starts, free=free)
    return model, fit


DEFAULT_STARTS = {
    "generic": np.array([-3.5, 0.0, 0.60, math.log(0.01), 1.15,
                         math.log(5.0), 0.50, 1.80]),
    "diffuse": np.array([-4.0, 0.2, 0.80, math.log(0.02), 1.20,
                         math.log(2.0), 0.80, 2.20]),
    "wide": np.array([-3.0, -0.2, 0.40, math.log(0.05), 1.10,
                      math.log(20.0), 0.20, 1.30]),
    "nz_ep": np.array([-4.265134996447479, -0.2268806781408922,
                       0.34230416058051294, -3.0027946525338636,
                       1.4114382760615138, math.log(6.531658827886768),
                       0.0, 1.826378529126951]),
    "jma_ep": None,
    "ca_ep": None,
}


def region_starts(region: str, archived: Optional[np.ndarray] = None):
    starts = [DEFAULT_STARTS["generic"].copy(),
              DEFAULT_STARTS["diffuse"].copy()]
    if region == "NZ" and archived is None:
        starts = [DEFAULT_STARTS["nz_ep"].copy(), starts[1]]
    elif region == "JMA" and archived is not None:
        starts = [np.asarray(archived, dtype=float), starts[1]]
    elif region == "CA" and archived is not None:
        starts = [np.asarray(archived, dtype=float), starts[1]]
    return starts


def parameter_summary(x):
    return {k: float(v) for k, v in zip(FREE_ORDER, x)}
