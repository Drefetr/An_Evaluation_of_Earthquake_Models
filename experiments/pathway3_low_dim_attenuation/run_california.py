"""Stage P3.3a: Wells-Coppersmith rupture scaling on the California folds.

``E_WC_Rupture`` fixes, for every parent j,

    ell_j = 10^(-2.44 + 0.59 M_j) km,      gamma = 0.75 log 10,

and estimates only the low-dimensional inhibition coordinates on top of the
sealed interior EP+ backbone.  Both the archived monotone kernel and Pathway
1's ``ann2`` annular kernel are evaluated.  The temporal relaxation time is
fixed at the pre-declared 5-day scale in the primary arm and profiled as a
sensitivity.

The sealed interior EP+ null, background weights and Sobol proposal are
imported read-only from Pathway 1 / the sealed benchmark.  Only new files
under the Pathway 3 result directory are written.
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
from experiments.pathway3_low_dim_attenuation import common as C  # noqa: E402
from experiments.pathway3_low_dim_attenuation import native  # noqa: E402

OUTPUT = C.OUT / "california"
CASES = ("california_fold_0", "california_fold_1", "california_fold_2")
KERNELS = ("mono", "ann2")
M0 = 3.0
WC_ALPHA = 0.59
WC_ELL0 = 10.0 ** (-2.44 + WC_ALPHA * M0)
WC_PSI = 5.0
TEST_POWER = 16
TEST_SEED = 20261120
CHECK_SEED = 20261121


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    C.write_json(path, value)


class WCModel(A.AnnularModel):
    """Annular model with an explicit magnitude exponent for ell_j."""

    def __init__(self, *args, alpha_ell=WC_ALPHA, **kwargs):
        super().__init__(*args, **kwargs)
        self.alpha_ell = float(alpha_ell)

    def _rows(self, data, x, need_h=True, need_g=True):
        return self.ann_native.rows(
            data, self.dm, self.kp, x, kernel=self.kernel, scaled=self.scaled,
            need_h=need_h, need_g=need_g, threads=1, alpha_ell=self.alpha_ell,
        )


def wc_start(x0, kernel):
    x = np.asarray(x0, dtype=float).copy()
    x[8] = 0.0
    x[9] = math.log(WC_ELL0)
    x[10] = math.log(WC_PSI)
    x[11] = 0.75 * math.log(10.0)
    return x


def build(case, kernel, nat):
    train, tm, test, vm, rows = A.RF.inputs(case)
    x0, weights, meta = A.load_baseline(case, "interior")
    region = A.RF.Region(train["rectangles"])
    background = A.RF.Background(train["event_xy"], region, tm["kde_bandwidth"], weights)
    train_model = WCModel(train, tm, background, native=nat, kernel=kernel, scaled=True)
    train_model.node_setup(x0, power=14, seed=20261111)
    train_model.freeze_nodes()
    test_model = WCModel(test, vm, background, native=nat, kernel=kernel, scaled=True)
    test_model.node_setup(x0, power=TEST_POWER, seed=TEST_SEED)
    test_model.freeze_nodes()
    check_model = WCModel(test, vm, background, native=nat, kernel=kernel, scaled=True)
    check_model.node_setup(x0, power=TEST_POWER, seed=CHECK_SEED)
    check_model.freeze_nodes()
    return dict(case=case, train=train_model, test=test_model, check=check_model,
                x0=x0, meta=meta, mark=A.mark_logscore(case))


def bounds(indices):
    return [tuple(A.RF.BOUNDS[i]) for i in indices]


def fit(model, indices, base, starts, inhibit=True, maxiter=400):
    base = np.asarray(base, dtype=float)
    box = bounds(indices)
    lo = np.asarray([b[0] for b in box])
    hi = np.asarray([b[1] for b in box])
    candidates = []
    records = []
    for start in starts:
        current = np.clip(np.asarray(start, dtype=float), lo, hi)
        value = None
        gradient = None
        x = None
        for attempt in range(2):
            def target(v):
                x = base.copy()
                x[indices] = v
                try:
                    value, gradient = model.objective(x, inhibit)
                except (ArithmeticError, FloatingPointError, OverflowError):
                    return 1e6, np.zeros(len(indices))
                return float(value), np.asarray(gradient)[indices]

            opt = minimize(target, current, jac=True, bounds=box, method="L-BFGS-B",
                           options=dict(maxiter=maxiter if attempt == 0 else 2 * maxiter,
                                        maxls=100, ftol=1e-10, gtol=2e-5))
            current = np.asarray(opt.x, dtype=float)
            x = base.copy()
            x[indices] = current
            try:
                value, gradient = model.objective(x, inhibit)
            except (ArithmeticError, FloatingPointError, OverflowError) as exc:
                records.append(dict(success=False, message=str(exc)))
                continue
            records.append(dict(success=bool(opt.success), message=str(opt.message),
                                nfev=int(opt.nfev), nll=float(value)))
            if opt.success:
                break
        if value is not None and np.isfinite(value):
            candidates.append(dict(parameters=x.tolist(), nll=float(value),
                                   gradient=np.asarray(gradient).tolist(),
                                   success=bool(opt.success)))
    if not candidates:
        raise ArithmeticError("no resolved California start")
    return dict(selected=min(candidates, key=lambda r: r["nll"]),
                candidates=candidates, records=records)


def state(model, x, inhibit, mark):
    value = model.objective(np.asarray(x, dtype=float), inhibit, True)
    return dict(nll=float(value["nll"]),
                event=float(value["ground_point"]),
                exposure=float(value["exposure"]),
                deficit=float(value["attenuation_deficit"]),
                joint=float(-value["nll"] + mark))


def run_case(case, kernels=KERNELS):
    started = time.time()
    nat = native.NativeP3(native.build())
    rows = {}
    base0 = None
    for kernel in kernels:
        bundle = build(case, kernel, nat)
        train, test, check = bundle["train"], bundle["test"], bundle["check"]
        mark = bundle["mark"]
        x0 = bundle["x0"]
        if base0 is None:
            base0 = x0.copy()
        wc = wc_start(x0, kernel)
        # Nested nulls on the training window.
        null_a = fit(train, [0], wc, [[wc[0]], [wc[0] + 0.5], [wc[0] - 0.5]],
                     inhibit=False)
        null_an = fit(train, [0, 2], wc,
                      [[wc[0], wc[2]], [wc[0] - 0.5, wc[2]], [wc[0], max(wc[2] - 0.2, 0.0)]],
                      inhibit=False)
        nulls = dict(eta=wc,
                     a_eta=np.asarray(null_a["selected"]["parameters"], dtype=float),
                     a_n_eta=np.asarray(null_an["selected"]["parameters"], dtype=float),
                     a_eta_psi=np.asarray(null_a["selected"]["parameters"], dtype=float),
                     a_n_eta_psi=np.asarray(null_an["selected"]["parameters"], dtype=float))
        for key in ("a_eta", "a_n_eta", "a_eta_psi", "a_n_eta_psi"):
            nulls[key][8] = 0.0
            nulls[key][9] = math.log(WC_ELL0)
            nulls[key][10] = math.log(WC_PSI)
            nulls[key][11] = 0.75 * math.log(10.0)
        null_states = {k: state(train, v, False, mark) for k, v in nulls.items()}
        test_null = {k: state(test, v, False, mark) for k, v in nulls.items()}

        arms = {}
        specs = {
            "WC_eta": ([8], "eta", [(0.1,), (0.4,), (1.0,)]),
            "WC_a_eta": ([0, 8], "a_eta", [(wc[0], 0.1), (wc[0], 0.4), (wc[0] - 0.5, 0.4)]),
            "WC_a_n_eta": ([0, 2, 8], "a_n_eta",
                           [(wc[0], wc[2], 0.1), (wc[0], wc[2], 0.4),
                            (wc[0] - 0.5, max(wc[2] - 0.2, 0.0), 0.4)]),
            "WC_a_eta_psi": ([0, 8, 10], "a_eta_psi",
                             [(wc[0], 0.1, math.log(2.0)), (wc[0], 0.4, math.log(5.0)),
                              (wc[0], 0.4, math.log(30.0))]),
            "WC_a_n_eta_psi": ([0, 2, 8, 10], "a_n_eta_psi",
                               [(wc[0], wc[2], 0.1, math.log(2.0)),
                                (wc[0], wc[2], 0.4, math.log(5.0)),
                                (wc[0] - 0.5, max(wc[2] - 0.2, 0.0), 0.4, math.log(30.0))]),
        }
        for name, (indices, null_key, starts) in specs.items():
            base = wc.copy() if null_key != "eta" else wc.copy()
            if null_key != "eta":
                base = nulls[null_key].copy()
            fit_result = fit(train, indices, base, starts, inhibit=True)
            theta = np.asarray(fit_result["selected"]["parameters"], dtype=float)
            theta[9] = math.log(WC_ELL0)
            theta[11] = 0.75 * math.log(10.0)
            if name not in ("WC_a_eta_psi", "WC_a_n_eta_psi"):
                theta[10] = math.log(WC_PSI)
            train_state = state(train, theta, True, mark)
            nested = train_state["nll"] >= null_states[null_key]["nll"] - 1e-9
            if nested:
                theta = nulls[null_key].copy()
                train_state = null_states[null_key]
            test_state = state(test, theta, True, mark)
            check_state = state(check, theta, True, mark)
            arms[f"{kernel}_{name}"] = dict(
                kernel=kernel, arm=name, indices=indices,
                parameters=[float(v) for v in theta],
                train=train_state, test=test_state, check=check_state,
                nested_null=bool(nested),
                eta=float(theta[8]),
                psi_days=float(math.exp(theta[10])),
                ell0_km=float(math.exp(theta[9])),
                alpha_ell=WC_ALPHA,
                gain_vs_null=float(test_state["joint"] - test_null[null_key]["joint"]),
                gain_vs_null_check=float(check_state["joint"] - test_null[null_key]["joint"]),
                test_quadrature_delta=float(check_state["joint"] - test_state["joint"]),
                null_key=null_key,
                null_training=null_states[null_key],
                null_test=test_null[null_key],
                training_gain=float(null_states[null_key]["nll"] - train_state["nll"]),
            )
        rows[kernel] = dict(baseline=bundle["meta"], arms=arms,
                            mark_logscore=float(bundle["mark"]))
    payload = dict(case=case, kernels=list(kernels), rows=rows,
                   wc=dict(alpha=WC_ALPHA, ell0_km=WC_ELL0, M0=M0,
                           ell_by_magnitude={str(m): float(10.0 ** (-2.44 + WC_ALPHA * m))
                                             for m in (4.0, 5.0, 6.0, 6.5, 7.0, 7.1)}),
                   wall_seconds=float(time.time() - started))
    write(OUTPUT / "cases" / (case + ".json"), payload)
    print("ca", case,
          {k: round(v["gain_vs_null"], 2) for k, v in payload["rows"]["mono"]["arms"].items()},
          f"{time.time()-started:.0f}s", flush=True)
    return payload


def summarize(rows):
    by_kernel = {}
    for kernel in KERNELS:
        arms = [r["rows"][kernel]["arms"] for r in rows]
        names = list(arms[0].keys())
        entry = {}
        for name in names:
            entry[name] = dict(
                eta=C.stats([a[name]["eta"] for a in arms]),
                psi_days=C.stats([a[name]["psi_days"] for a in arms]),
                gain_vs_null=C.stats([a[name]["gain_vs_null"] for a in arms]),
                gain_vs_null_check=C.stats([a[name]["gain_vs_null_check"] for a in arms]),
                training_gain=C.stats([a[name]["training_gain"] for a in arms]),
                nested_null=int(sum(a[name]["nested_null"] for a in arms)),
                eta_zero=int(sum(a[name]["eta"] < 1e-8 for a in arms)),
                test_quadrature_delta=C.stats([a[name]["test_quadrature_delta"] for a in arms]),
            )
        by_kernel[kernel] = entry
    payload = dict(
        schema="pathway3_california_wc_rupture_v1", passed=True,
        source=str(Path(__file__).relative_to(ROOT).as_posix()),
        source_sha256=C.sha256(Path(__file__)),
        cases=list(CASES), kernels=list(KERNELS),
        wc=dict(alpha=WC_ALPHA, ell0_km=WC_ELL0, M0=M0),
        note=("The sealed interior EP+ null is the backbone comparator. WC arms refit "
              "only the listed coordinates; ell_j and gamma are fixed. The first test "
              "proposal (seed 20261120) is primary and the second (20261121) is an "
              "independent quadrature check."),
        by_kernel=by_kernel, rows=rows,
    )
    write(OUTPUT / "summary.json", payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=list(CASES))
    parser.add_argument("--kernels", nargs="+", default=list(KERNELS))
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    from concurrent.futures import ProcessPoolExecutor, as_completed

    rows = []
    pending = []
    for case in args.cases:
        path = OUTPUT / "cases" / (case + ".json")
        if path.exists():
            rows.append(read(path))
        else:
            pending.append(case)
    with threadpool_limits(limits=1):
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_case, case, tuple(args.kernels)) for case in pending]
            for future in as_completed(futures):
                rows.append(future.result())
    for case in CASES:
        path = OUTPUT / "cases" / (case + ".json")
        if path.exists() and not any(r["case"] == case for r in rows):
            rows.append(read(path))
    rows.sort(key=lambda r: r["case"])
    payload = summarize(rows)
    print(json.dumps({k: {kk: round(vv["gain_vs_null"]["mean"], 2)
                          for kk, vv in v.items()}
                      for k, v in payload["by_kernel"].items()}, indent=1))


if __name__ == "__main__":
    main()
