"""Low-dimensional and penalised estimators for Pathway 3.

Every estimator receives training phases only.  Held-out phases are passed
solely to the ``score`` helpers after the training state is frozen.

Coordinate layout (archived S8/S04B convention):
    0 a, 1 d, 2 n, 3 log c, 4 p, 5 eta, 6 log ell, 7 log psi
Stationary arms fix d = 0.
"""
from __future__ import annotations

import math

import numpy as np

from experiments.pathway3_low_dim_attenuation import s8


def null_stationary(train, maxiter=200, order=8):
    """Uninhibited four-parameter stationary backbone (a, n, log c, p)."""
    base = np.zeros(8)
    base[0] = -3.0
    base[1] = 0.0
    base[2] = 0.30
    base[3] = math.log(0.05)
    base[4] = 1.3
    starts = []
    for da, nn, pp in ((0.0, 0.30, 1.3), (0.4, 0.30, 1.3), (-0.4, 0.30, 1.3),
                       (0.0, 0.05, 1.3), (0.0, 0.30, 1.8), (0.4, 0.05, 1.8)):
        starts.append([base[0] + da, nn, base[3], pp])
    fit = s8.fit(train, "null", [0, 2, 3, 4], base, starts,
                 maxiter=maxiter, order=order, label="stationary_null")
    return fit


def fixed_true_backbone():
    """Truth values with eta = 0, used by the fixed-backbone ladder rungs."""
    base = np.zeros(8)
    base[:5] = [math.log(0.25), 0.2, 0.35, math.log(0.05), 1.3]
    return base


def _scale_theta(base, ell, psi):
    theta = np.asarray(base, dtype=float).copy()
    theta[5] = 0.0
    theta[6] = math.log(float(ell))
    theta[7] = math.log(float(psi))
    return theta


def _nested_null(train, base, ell, psi, order):
    theta = _scale_theta(base, ell, psi)
    value = train.evaluate(theta, "null", order)[0]
    return theta, value


def _e1d_starts(base, mode, null_theta, eta_starts=(0.4, 0.1),
                a_shifts=(0.0, -0.5, 0.5)):
    if mode == "2p":
        return [[base[0] + da, eta] for da in a_shifts for eta in eta_starts]
    combos = ((0.0, 0.0, 0.4), (0.0, -0.15, 0.4), (-0.5, 0.0, 0.4),
              (0.5, 0.0, 0.4), (0.0, 0.0, 0.1), (-0.5, -0.15, 0.1))
    return [[base[0] + da, max(base[2] + dn, 0.0), eta]
            for da, dn, eta in combos]


def fit_e1d(train, null_theta, mode, ell, psi, order=8, maxiter=180,
            ell2=None):
    """Profile (a, eta) or (a, n, eta) at one fixed attenuation scale."""
    indices = [0, 5] if mode == "2p" else [0, 2, 5]
    base = np.asarray(null_theta, dtype=float).copy()
    base[5] = 0.0
    base[6] = math.log(float(ell))
    base[7] = math.log(float(psi))
    starts = _e1d_starts(base, mode, null_theta)
    fit = s8.fit(train, "LIplus_inclusive", indices, base, starts,
                 maxiter=maxiter, order=order, ell2=ell2, label="e1d_" + mode)
    null_value = train.evaluate(base, "null", order, ell2=ell2)[0]
    nested = fit["selected"]["nll"] >= null_value["nll"] - 1e-9
    if nested:
        fit["selected"] = dict(parameters=base.tolist(), nll=float(null_value["nll"]),
                               gradient=[], start_index=-1, free=[], nested_null=True)
    fit["nested_null"] = bool(nested)
    fit["null_training"] = null_value
    fit["scale"] = dict(ell_km=float(ell), psi_days=float(psi))
    fit["eta"] = float(fit["selected"]["parameters"][5])
    fit["training_gain"] = float(null_value["nll"] - fit["selected"]["nll"])
    return fit


def select_grid(train, null_theta, mode, scales, order=8, maxiter=180):
    """Fit every pre-declared scale; select by training likelihood.

    The reported training criterion adds the declared log-K multiplicity
    penalty; the candidate ordering itself is by likelihood, because the
    penalty is common to all K candidates.  The penalty is recorded so that a
    selected-scale model can be compared with a fixed-scale model.
    """
    rows = []
    for ell, psi in scales:
        fit = fit_e1d(train, null_theta, mode, ell, psi, order=order,
                      maxiter=maxiter)
        rows.append(fit)
    selected = min(rows, key=lambda r: (r["selected"]["nll"], r["scale"]["ell_km"]))
    penalty = math.log(len(scales))
    return dict(mode=mode, candidates=rows, selected=selected,
                selection_penalty_nats=float(penalty),
                training_criterion=float(selected["selected"]["nll"] + penalty),
                scale=selected["scale"], eta=selected["eta"],
                nested_null=selected["nested_null"])


def fit_l1(train, null_theta, mode, ell, psi, lam, order=8, maxiter=180,
           per_event=False, ell2=None):
    """Penalised training fit with an exponential prior on eta.

    The literal handoff penalty is ``lam * eta * mean(G_event)``.  The
    ``per_event`` sensitivity uses ``lam * eta * sum(G_event)``, i.e. a prior
    whose strength grows with the training event count.
    """
    indices = [0, 5] if mode == "2p" else [0, 2, 5]
    base = np.asarray(null_theta, dtype=float).copy()
    base[5] = 0.0
    base[6] = math.log(float(ell))
    base[7] = math.log(float(psi))
    stress = train.event_stress(base, ell2=ell2)["G"]
    scale = float(stress.sum() if per_event else stress.mean())
    null_value = train.evaluate(base, "null", order, ell2=ell2)[0]

    def target(v):
        theta = base.copy()
        theta[indices] = v
        try:
            value, gradient = train.evaluate(theta, "LIplus_inclusive", order, ell2=ell2)
        except (ArithmeticError, FloatingPointError, OverflowError):
            return 1e6, np.zeros(len(indices))
        eta = float(theta[5])
        pen = lam * eta * scale
        grad = np.asarray(gradient, dtype=float).copy()
        grad[5] += lam * scale
        return float(value["nll"] + pen), grad[indices]

    from scipy.optimize import minimize

    lo = np.asarray([s8.bounds_for(indices)[k][0] for k in range(len(indices))])
    hi = np.asarray([s8.bounds_for(indices)[k][1] for k in range(len(indices))])
    records = []
    best = None
    for start in _e1d_starts(base, mode, null_theta):
        opt = minimize(target, np.clip(np.asarray(start, dtype=float), lo, hi),
                       jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                       options=dict(maxiter=maxiter, maxls=100, ftol=1e-10, gtol=2e-5))
        theta = base.copy()
        theta[indices] = opt.x
        try:
            value, _ = train.evaluate(theta, "LIplus_inclusive", order, ell2=ell2)
        except (ArithmeticError, FloatingPointError, OverflowError) as exc:
            records.append(dict(success=False, message=str(exc)))
            continue
        penalised = float(value["nll"] + lam * float(theta[5]) * scale)
        records.append(dict(success=bool(opt.success), message=str(opt.message),
                            nfev=int(opt.nfev), nll=float(value["nll"]),
                            penalised=penalised, parameters=theta.tolist()))
        if best is None or penalised < best["penalised"]:
            best = dict(success=bool(opt.success), message=str(opt.message),
                        nfev=int(opt.nfev), nll=float(value["nll"]),
                        penalised=penalised, parameters=theta.tolist())
    if best is None:
        raise ArithmeticError("no resolved L1 start")
    theta = np.asarray(best["parameters"], dtype=float)
    # Exact eta=0 candidate: the penalty makes zero strictly preferred when the
    # raw score slope is below lam * scale.
    null_pen = float(null_value["nll"])
    if float(theta[5]) <= 1e-8 or null_pen <= best["penalised"] + 1e-9:
        theta = base.copy()
        value = null_value
        nested = True
    else:
        value = train.evaluate(theta, "LIplus_inclusive", order, ell2=ell2)[0]
        nested = False
    return dict(mode=mode, lam=float(lam), per_event=bool(per_event),
                scale=dict(ell_km=float(ell), psi_days=float(psi)),
                eta=float(theta[5]), parameters=[float(v) for v in theta],
                training_nll=float(value["nll"]),
                training_penalised=float(value["nll"] + lam * float(theta[5]) * scale),
                nested_null=bool(nested), penalty_scale=scale,
                candidates=records)


def rebalance_a(train, theta, order=8, ell2=None, model="LIplus_inclusive"):
    """Profile the intercept a at fixed inhibition coordinates."""
    theta = np.asarray(theta, dtype=float).copy()

    def target(a):
        trial = theta.copy()
        trial[0] = float(a)
        try:
            value, gradient = train.evaluate(trial, model, order, ell2=ell2)
        except (ArithmeticError, FloatingPointError, OverflowError):
            return 1e6, 0.0
        return float(value["nll"]), float(gradient[0])

    from scipy.optimize import minimize

    opt = minimize(target, np.asarray([theta[0]]), jac=True,
                   bounds=[s8.bounds_for([0])[0]], method="L-BFGS-B",
                   options=dict(maxiter=200, maxls=100, ftol=1e-10, gtol=2e-5))
    trial = theta.copy()
    trial[0] = float(opt.x[0])
    value = train.evaluate(trial, model, order, ell2=ell2)[0]
    return trial, dict(success=bool(opt.success), nfev=int(opt.nfev),
                       nll=float(value["nll"]), a=float(opt.x[0]))


def fit_split_cv(full_train, first_train, second_train, full_null,
                 first_null, ell, psi, alphas, order=8, maxiter=180):
    """Within-training chronological split shrinkage of eta."""
    base_first = np.asarray(first_null, dtype=float).copy()
    base_first[5] = 0.0
    base_first[6] = math.log(float(ell))
    base_first[7] = math.log(float(psi))
    fit_first = s8.fit(first_train, "LIplus_inclusive", [0, 5], base_first,
                       _e1d_starts(base_first, "2p", first_null), maxiter=maxiter,
                       order=order, label="split_first_half")
    eta_first = float(fit_first["selected"]["parameters"][5])
    rows = []
    for alpha in alphas:
        eta = float(alpha) * eta_first
        theta = np.asarray(full_null, dtype=float).copy()
        theta[5] = eta
        theta[6] = math.log(float(ell))
        theta[7] = math.log(float(psi))
        theta, rebalance = rebalance_a(full_train, theta, order=order)
        second = second_train.evaluate(theta, "LIplus_inclusive", order)
        rows.append(dict(alpha=float(alpha), eta=float(eta),
                         second_nll=float(second[0]["nll"]),
                         second_joint=float(second[0]["joint"]),
                         rebalance=rebalance, parameters=[float(v) for v in theta]))
    selected = max(rows, key=lambda r: (r["second_joint"], -r["alpha"]))
    return dict(first_half=dict(eta=eta_first, fit=fit_first),
                candidates=rows, selected=selected, alpha=selected["alpha"],
                eta=selected["eta"], parameters=selected["parameters"],
                scale=dict(ell_km=float(ell), psi_days=float(psi)))


def fit_free_stationary(train, starts, order=8, maxiter=200):
    """Seven-parameter stationary free fit (a, n, log c, p, eta, log ell, log psi)."""
    base = np.zeros(8)
    base[0] = -1.5
    base[2] = 0.35
    base[3] = math.log(0.05)
    base[4] = 1.3
    return s8.fit(train, "LIplus_inclusive", [0, 2, 3, 4, 5, 6, 7], base, starts,
                  maxiter=maxiter, order=order, label="free_7d_stationary")


def score(test, theta, model="LIplus_inclusive", order=16, ell2=None):
    value, gradient = test.evaluate(theta, model, order, ell2=ell2)
    return value, gradient
