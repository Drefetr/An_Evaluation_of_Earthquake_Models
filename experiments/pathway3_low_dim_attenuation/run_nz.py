"""Stage P3.3b: low-dimensional attenuation profile on the New Zealand folds.

The sealed New Zealand predictive model is a temporal renewal/Omori mixture
with no epicentral-distance kernel.  A Wells-Coppersmith rupture length is a
spatial scale and is therefore not defined in that model.  This module records
that scope limitation explicitly and evaluates the temporal analogue of
``E_1D_Profile``: the archived trigger and stress kernels are held fixed and
only (a, eta) or (a, n, eta) are estimated with the stationary clock d = 0.
``E_L1_Shrinkage`` is evaluated on the same fixed stress field.

No sealed authority or pre-existing live-result file is written.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.methodological_audit import nz_trend_controls as NZ  # noqa: E402
from experiments.pathway2_trend_parameterization import background as B  # noqa: E402
from experiments.pathway2_trend_parameterization.run_nz import (  # noqa: E402
    DAY, FOLDS, LawHistory, record, score)
from experiments.pathway3_low_dim_attenuation import common as C  # noqa: E402

OUTPUT = C.OUT / "nz"
A = NZ.A
BOUNDS = dict(a=(-12.0, 0.0), n=(0.0, 0.98), eta=(0.0, 3.0))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    C.write_json(path, value)


def fit_pars(history, trigger, ratio, stress, start, free_n, eta_mode,
             lam=0.0, penalty_scale=0.0, maxiter=1200):
    """Fit (a|a,n) and optionally eta with d = 0.

    ``start`` is a four-vector (a, d, n, eta).  When ``eta_mode`` is false the
    stress field is absent and eta is fixed at zero.  The optional L1 penalty
    adds ``lam * eta * penalty_scale`` to the negative log-likelihood.
    """
    names = ["a"] + (["n"] if free_n else []) + (["eta"] if eta_mode else [])
    index = {"a": 0, "n": 2, "eta": 3}
    lo = np.asarray([BOUNDS[n][0] for n in names])
    hi = np.asarray([BOUNDS[n][1] for n in names])

    def expand(v):
        pars = [float(start[0]), 0.0, float(start[2]), 0.0]
        for name, value in zip(names, v):
            pars[index[name]] = float(value)
        return pars

    x0 = np.clip(np.asarray([start[index[n]] for n in names], dtype=float), lo, hi)

    def target(v):
        pars = expand(v)
        value, gradient = history.objective(pars, trigger, ratio, stress, True)
        grad = np.asarray([gradient[index[n]] for n in names])
        if eta_mode and lam:
            value = value + lam * pars[3] * penalty_scale
            grad[-1] += lam * penalty_scale
        return value, grad

    opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=maxiter, maxls=200, ftol=1e-11, gtol=2e-6))
    return dict(success=bool(opt.success), message=str(opt.message),
                nll=float(opt.fun), parameters=expand(opt.x),
                nit=int(opt.nit), nfev=int(opt.nfev))


def run_fold(name, times, excess, fold):
    train_end = float(fold["train_end"])
    test_end = float(fold["test_end"])
    beta = float(fold["fit"]["beta_train"])
    ratio = float(fold["fit"]["best"]["ml_shared"]["ratio"])
    trigger = fold["fit"]["best"]["ml_shared"]["trigger"]
    stress = fold["fit"]["best"]["ml_shared"]["stress"]
    null_start = np.asarray(fold["fit"]["best"]["ml_trigger"]["pars"], dtype=float)
    if len(null_start) == 3:
        null_start = np.r_[null_start, 0.0]
    law = B.BackgroundLaw("T1", DAY, origin=train_end, train_start=0.0)
    train = LawHistory(times, excess, beta, 0.0, train_end, DAY, 32, law)
    test = LawHistory(times, excess, beta, train_end, test_end, DAY, 32, law)
    mid = 0.5 * train_end
    first = LawHistory(times, excess, beta, 0.0, mid, DAY, 32, law)
    second = LawHistory(times, excess, beta, mid, train_end, DAY, 32, law)
    kernel = A.KernelSpec(**stress)
    ge, _gq = train.stress(kernel)
    gbar = float(np.mean(ge))
    gsum = float(np.sum(ge))
    trigger_spec = A.KernelSpec(**trigger)

    archived = NZ.archived_fold(name, times, excess, fold)
    train_null_an = fit_pars(train, trigger_spec, ratio, None, null_start, True, False)
    train_null_a = fit_pars(train, trigger_spec, ratio, None, null_start, False, False)
    first_null_an = fit_pars(first, trigger_spec, ratio, None, null_start, True, False)

    arms = {}
    for mode, free_n, null_fit in (("2p", False, train_null_a),
                                   ("3p", True, train_null_an)):
        fit = fit_pars(train, trigger_spec, ratio, kernel, null_start, free_n, True)
        nested = fit["nll"] >= null_fit["nll"] - 1e-9
        if nested:
            fit = dict(fit, parameters=null_fit["parameters"], nll=null_fit["nll"],
                       nested_null=True)
        null_pars = list(fit["parameters"])
        null_pars[3] = 0.0
        test_state = score(test, record(fit["parameters"], trigger, ratio, stress))
        test_null = score(test, record(null_pars, trigger, ratio, None))
        arms[f"E1D_Profile_{mode}"] = dict(
            fit=fit, parameters=[float(v) for v in fit["parameters"]],
            test=test_state, null_test=test_null,
            gain=float(test_state["joint"] - test_null["joint"]),
            training_gain=float(null_fit["nll"] - fit["nll"]),
            nested_null=bool(nested), eta=float(fit["parameters"][3]),
        )

    lambda_rows = {}
    for lam in C.LAMBDA_GRID:
        for per_event in (False, True):
            scale = gsum if per_event else gbar
            fit = fit_pars(first, trigger_spec, ratio, kernel, first_null_an["parameters"],
                           False, True, lam=lam, penalty_scale=scale)
            second_state = (fit["parameters"][0], 0.0, fit["parameters"][2],
                            fit["parameters"][3])
            second_score = score(second, record(list(second_state), trigger, ratio, stress))
            lambda_rows[f"{lam:g}" + ("_per_event" if per_event else "")] = dict(
                fit=fit, second_joint=float(second_score["joint"]),
                lam=lam, per_event=per_event)
    key, payload = max(lambda_rows.items(),
                       key=lambda kv: (kv[1]["second_joint"], -kv[1]["lam"]))
    l1_fit = fit_pars(train, trigger_spec, ratio, kernel,
                      train_null_an["parameters"], False, True,
                      lam=payload["lam"],
                      penalty_scale=(gsum if payload["per_event"] else gbar))
    l1_null_pars = list(l1_fit["parameters"])
    l1_null_pars[3] = 0.0
    l1_state = score(test, record(l1_fit["parameters"], trigger, ratio, stress))
    l1_null_state = score(test, record(l1_null_pars, trigger, ratio, None))
    arms["E_L1_Shrinkage"] = dict(
        fit=l1_fit, parameters=[float(v) for v in l1_fit["parameters"]],
        test=l1_state, null_test=l1_null_state,
        gain=float(l1_state["joint"] - l1_null_state["joint"]),
        eta=float(l1_fit["parameters"][3]), lam=float(payload["lam"]),
        per_event=bool(payload["per_event"]), lambda_key=key,
        training_gain=0.0,
        lambda_grid={k: dict(eta=float(v["fit"]["parameters"][3]),
                             second_joint=float(v["second_joint"]))
                     for k, v in lambda_rows.items()},
    )
    # Training gain for the L1 arm is reported against the same fixed-null fit.
    arms["E_L1_Shrinkage"]["training_gain"] = float(
        fit_pars(train, trigger_spec, ratio, None, l1_null_pars, False, False)["nll"]
        - l1_fit["nll"])

    # Stationary full (a, n, eta) comparator.
    t1_fit = fit_pars(train, trigger_spec, ratio, kernel, null_start, True, True)
    t1_null_pars = list(t1_fit["parameters"])
    t1_null_pars[3] = 0.0
    t1_test = score(test, record(t1_fit["parameters"], trigger, ratio, stress))
    t1_null_test = score(test, record(t1_null_pars, trigger, ratio, None))

    return dict(fold=name, train_end=train_end, test_end=test_end,
                n_train=int(fold["fit"]["n_train"]), beta=beta,
                trigger=trigger, stress=stress, ratio=ratio,
                archived=archived,
                t1_full=dict(fit=t1_fit, test=t1_test, null_test=t1_null_test,
                             gain=float(t1_test["joint"] - t1_null_test["joint"])),
                arms=arms,
                wc_status=("not defined: the sealed New Zealand predictive model has no "
                           "epicentral-distance kernel, so a rupture-length scale is absent"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    catalogue = pd.read_csv(NZ.CATALOGUE)
    times = catalogue.t_days.to_numpy(dtype=float)
    excess = catalogue.excess.to_numpy(dtype=float)
    authority = read(NZ.AUTHORITY)
    with threadpool_limits(limits=1):
        folds = {name: run_fold(name, times, excess, authority["folds"][name])
                 for name in FOLDS}
    totals = {}
    for key in ("E1D_Profile_2p", "E1D_Profile_3p", "E_L1_Shrinkage"):
        totals[key] = float(sum(folds[n]["arms"][key]["gain"] for n in FOLDS))
    totals["T1_full"] = float(sum(folds[n]["t1_full"]["gain"] for n in FOLDS))
    totals["archived_free_d"] = float(sum(folds[n]["archived"]["heldout"]["delta_joint"]
                                          for n in FOLDS))
    payload = dict(
        schema="pathway3_nz_low_dim_profile_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=C.sha256(Path(__file__)),
        catalogue_sha256=NZ.sha(NZ.CATALOGUE), authority_sha256=NZ.sha(NZ.AUTHORITY),
        folds=folds, totals=totals,
        scope=("Wells-Coppersmith rupture scaling is not defined for the sealed New "
               "Zealand temporal predictive model. The table reports the temporal "
               "one-dimensional profile analogue, not a spatial WC test."),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write(args.output / "summary.json", payload)
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
