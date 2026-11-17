"""Stage P2.3a: New Zealand trend--depletion controls under T1/T2/T3.

The archived three-fold New Zealand fits are reconstructed from the sealed
authority.  Null and inhibited arms are refitted under each forecast-admissible
background law with the archived trigger/stress kernels and productivity ratio
held fixed.  Test scores use the same independent predictive-history
quadrature as the sealed trend controls.
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

A = NZ.A
FOLDS = ("fold_50", "fold_65", "fold_80")
DAY = 24394.0
LAWS = ("T1", "T2", "T3")
OUTPUT = ROOT / "validation/live_results/pathway2_trend_controls_20261116/nz"
BOUNDS = dict(a=(-12.0, 0.0), d=(-2.0, 2.0), n=(0.0, 0.98), eta=(0.0, 3.0))


class LawHistory(A.PredictiveHistory):
    def __init__(self, times, excess, beta, start, end, T0, order, law):
        super().__init__(times, excess, beta, start, end, T0, order)
        self.law = law
        self.xe = law.x(self.events)
        self.xq = law.x(self.tq)

    def components(self, pars, trigger=None, ratio=0.0, stress=None):
        a, d = np.asarray(pars, dtype=float)[:2]
        n = float(pars[2]) if trigger is not None else 0.0
        eta = float(pars[3]) if stress is not None else 0.0
        if stress is not None:
            ge, gq = self.stress(stress)
            ge = self.law.deplete(ge, self.xe)
            gq = self.law.deplete(gq, self.xq)
        else:
            ge = np.zeros(len(self.events))
            gq = np.zeros(len(self.tq))
        if trigger is not None:
            he, hi = self.trigger(trigger, ratio)
        else:
            he = np.zeros(len(self.events))
            hi = np.zeros(len(self.edges) - 1)
        logb = a + d * self.xe - eta * ge
        logh = np.full_like(he, -np.inf)
        np.log(he, out=logh, where=he > 0)
        loglam = np.logaddexp(logb, logh + np.log(n) if n > 0 else np.full_like(he, -np.inf))
        bq = np.exp(a + d * self.xq - eta * gq)
        if stress is None:
            pieces = np.array([self.law.integral(a, d, lo, hi_)[0]
                               for lo, hi_ in zip(self.edges[:-1], self.edges[1:])])
        else:
            pieces = np.bincount(self.group, weights=self.wq * bq, minlength=len(self.edges) - 1)
        pieces = pieces + n * hi
        return loglam, pieces, (ge, gq, he, hi, bq, logb, logh)

    def objective(self, pars, trigger=None, ratio=0.0, stress=None, gradient=False):
        loglam, pieces, aux = self.components(pars, trigger, ratio, stress)
        value = float(pieces.sum() - loglam.sum())
        if not math.isfinite(value):
            raise FloatingPointError("nonfinite likelihood")
        if not gradient:
            return value
        ge, gq, he, hi, bq, logb, logh = aux
        eb = np.exp(logb - loglam)
        if stress is None:
            Bint, Bd = self.law.integral(pars[0], pars[1], self.start, self.end)
        else:
            Bint = self.wq @ bq
            Bd = self.wq @ (bq * self.xq)
        grad = [-eb.sum() + Bint, -eb @ self.xe + Bd]
        if trigger is not None:
            grad.append(-np.exp(logh - loglam).sum() + hi.sum())
        if stress is not None:
            grad.append(eb @ ge - self.wq @ (bq * gq))
        if not np.isfinite(grad).all():
            raise FloatingPointError("nonfinite gradient")
        return value, np.asarray(grad)


def fit_law(history, kind, trigger, ratio, stress, start, eta_mode):
    names = (["a", "d", "n"] if kind != "T1" else ["a", "n"])
    indices = [0, 1, 2] if kind != "T1" else [0, 2]
    if eta_mode:
        names = names + ["eta"]
        indices = indices + [3]
    lo = np.asarray([BOUNDS[n][0] for n in names])
    hi = np.asarray([BOUNDS[n][1] for n in names])

    def expansion(v):
        if kind == "T1":
            pars = [float(v[0]), 0.0, float(v[1])]
            if eta_mode:
                pars.append(float(v[2]))
            return pars
        pars = [float(v[0]), float(v[1]), float(v[2])]
        if eta_mode:
            pars.append(float(v[3]))
        return pars

    x0 = np.clip(np.asarray([start[i] for i in indices], dtype=float), lo, hi)

    def target(v):
        pars = expansion(v)
        value, gradient = history.objective(pars, trigger, ratio, stress, True)
        return value, np.asarray([gradient[i] for i in indices])

    opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-6))
    return dict(success=bool(opt.success), message=str(opt.message), nll=float(opt.fun),
                parameters=expansion(opt.x), nit=int(opt.nit), nfev=int(opt.nfev))


def record(parameters, trigger, ratio, stress):
    return dict(pars=[float(v) for v in parameters], trigger=trigger,
                ratio=float(ratio), stress=stress)


def score(history, rec):
    loglam, pieces, _ = history.components(rec["pars"], trigger=A.KernelSpec(**rec["trigger"]),
                                            ratio=rec["ratio"],
                                            stress=A.KernelSpec(**rec["stress"]) if rec["stress"] else None)
    n = len(history.events)
    mark = float(n * np.log(history.beta) - history.beta * history.excess[history.mask].sum())
    ground = float(loglam.sum() - pieces.sum())
    return dict(ground=ground, mark=mark, joint=ground + mark,
                integrated_intensity=float(pieces.sum()), n_events=n)


def fold_run(fold_name, times, excess, fold, archived):
    train_end = float(fold["train_end"])
    test_end = float(fold["test_end"])
    ratio = float(fold["fit"]["best"]["ml_shared"]["ratio"])
    trigger = fold["fit"]["best"]["ml_shared"]["trigger"]
    stress = fold["fit"]["best"]["ml_shared"]["stress"]
    beta = float(fold["fit"]["beta_train"])
    null_start = np.asarray(fold["fit"]["best"]["ml_trigger"]["pars"], dtype=float)
    alt_start = np.asarray(fold["fit"]["best"]["ml_shared"]["pars"], dtype=float)
    rows = {}
    for kind in LAWS:
        law = B.BackgroundLaw(kind, DAY, origin=train_end, train_start=0.0)
        train = LawHistory(times, excess, beta, 0.0, train_end, DAY, 32, law)
        test = LawHistory(times, excess, beta, train_end, test_end, DAY, 32, law)
        if kind == "T3":
            ge, gq = train.stress(A.KernelSpec(**stress))
            law.orthogonalise(ge, train.xe, gq, train.xq, train.wq)
        null = fit_law(train, kind, A.KernelSpec(**trigger), ratio, None, null_start, False)
        alt = fit_law(train, kind, A.KernelSpec(**trigger), ratio, A.KernelSpec(**stress),
                      alt_start, True)
        if not alt["success"]:
            recovery = [null["parameters"][0]]
            if kind != "T1":
                recovery.append(null["parameters"][1])
            recovery += [null["parameters"][2] if kind != "T1" else null["parameters"][1], 1.0]
            alt = fit_law(train, kind, A.KernelSpec(**trigger), ratio, A.KernelSpec(**stress),
                          recovery, True)
        null_rec = record(null["parameters"], trigger, ratio, None)
        alt_rec = record(alt["parameters"], trigger, ratio, stress)
        null_test = score(test, null_rec)
        alt_test = score(test, alt_rec)
        rows[kind] = dict(
            law=law.describe(), projection=law.projection if kind == "T3" else None,
            null=dict(training=null, test=null_test, record=null_rec),
            inhibited=dict(training=alt, test=alt_test, record=alt_rec),
            heldout=dict(
                delta_joint=float(alt_test["joint"] - null_test["joint"]),
                delta_point=float(alt_test["ground"] - null_test["ground"]),
                delta_exposure=float(alt_test["integrated_intensity"] - null_test["integrated_intensity"]),
                training_delta=float(null["nll"] - alt["nll"]),
            ),
        )
    return dict(train_end=train_end, test_end=test_end, n_train=int(fold["fit"]["n_train"]),
                d_null=float(null_start[1]), archived=archived, laws=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    catalogue = pd.read_csv(NZ.CATALOGUE)
    times = catalogue.t_days.to_numpy(dtype=float)
    excess = catalogue.excess.to_numpy(dtype=float)
    authority = json.loads(NZ.AUTHORITY.read_text(encoding="utf-8"))
    folds = {}
    with threadpool_limits(limits=1):
        for name in FOLDS:
            fold = authority["folds"][name]
            archived = NZ.archived_fold(name, times, excess, fold)
            folds[name] = fold_run(name, times, excess, fold, archived)
            print(name, {k: round(v["heldout"]["delta_joint"], 3) for k, v in folds[name]["laws"].items()},
                  flush=True)
    total = {kind: float(sum(folds[n]["laws"][kind]["heldout"]["delta_joint"] for n in FOLDS))
             for kind in LAWS}
    total["T0"] = float(sum(folds[n]["archived"]["heldout"]["delta_joint"] for n in FOLDS))
    sealed = json.loads((ROOT / "validation/live_results/track_b_controls_20261112/"
                         "nz_trend_controls/summary.json").read_text(encoding="utf-8"))
    total["fixed_null_trend"] = float(sealed["totals"]["fixed_null_trend_delta_joint"])
    total["zero_trend"] = float(sealed["totals"]["zero_trend_delta_joint"])
    payload = dict(
        schema="pathway2_nz_trend_controls_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=__import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest(),
        catalogue_sha256=NZ.sha(NZ.CATALOGUE), authority_sha256=NZ.sha(NZ.AUTHORITY),
        folds=folds, totals=total,
        note=("T0 is the archived free-d fit. T1 fixes d=0. T2 refits a,d,n and a,d,n,eta "
              "with the origin-clamped clock. T3 additionally residualises G on (1,x_clamp) "
              "over the training exposure nodes. Trigger/stress kernels and ratio are fixed "
              "at the archived per-fold selection."),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(total, indent=2))


if __name__ == "__main__":
    main()
