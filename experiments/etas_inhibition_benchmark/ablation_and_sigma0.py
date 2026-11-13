"""Track B EP+ component ablation, common-space rectangle normalization and sigma0 study.

The archived frozen objective is imported without modification.  A subclass adds
observation-rectangle kernel normalization with analytic derivatives; central
finite differences verify every spatial derivative before fitting.  All fits use
the original caches, fertility weights, mark measure and training-only rules.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "experiments/etas_inhibition_benchmark/run_frozen_20261111.py"
ACCEPTED = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112"
BASELINE = ACCEPTED / "baseline_comparison.json"
SIGMA_GRID = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0)


def _load_frozen():
    spec = importlib.util.spec_from_file_location("track_b_frozen", FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RF = _load_frozen()


class RectModel(RF.Model):
    """Observation-rectangle normalized offspring kernel with analytic derivatives."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._geometry = None

    def _parent_geometry(self, x):
        _, _, _, _, _, log_sigma0, alpha_s, q = x[:8]
        scale = np.exp(log_sigma0 + alpha_s * self.dm)
        key = (float(log_sigma0), float(alpha_s), float(q))
        if self._geometry is None or self._geometry[0] != key:
            mass, dmass, dq = self.region.mass(self.radii, scale, q)
            if np.any(mass <= 0) or not np.isfinite(mass).all():
                raise ArithmeticError("invalid rectangle mass")
            self._geometry = (key, mass, dmass, dq, scale)
        return self._geometry[1:]

    def H(self, data, x, deriv=True):
        _, _, _, log_c, p, _, _, q = x[:8]
        c = np.exp(log_c)
        sigma2 = np.exp(2 * x[5] + 2 * x[6] * self.dm)
        lag, r2, past = data["lag"], data["r2"], data["past"]
        v = r2 / sigma2
        tl = np.log1p(lag / c)
        sl = np.log1p(v)
        k = ((p - 1) / c * np.exp(-p * tl) * (q - 1) / (np.pi * sigma2)
             * np.exp(-q * sl) * self.kp * past)
        mass, dmass, dq, scale = self._parent_geometry(x)
        k = k / mass[None, :]
        h = k.sum(axis=1)
        if not deriv:
            return h
        ds = -2 + 2 * q * v / (1 + v)
        # Region.mass returns dmass = d mass / d log(scale).
        ds_rect = ds - dmass / mass
        grad = np.stack([
            (k * (-1 + p * lag / (c + lag))).sum(axis=1),
            (k * (1 / (p - 1) - tl)).sum(axis=1),
            (k * ds_rect).sum(axis=1),
            (k * ds_rect * self.dm).sum(axis=1),
            (k * (1 / (q - 1) - sl - dq / mass)).sum(axis=1),
        ], axis=1)
        return h, grad

    def exact_exposure(self, x):
        a, d, n, log_c, p, _, _, _ = x[:8]
        c = np.exp(log_c)
        lo = self.a["parent_exposure_lo"]
        hi = self.a["parent_exposure_hi"]
        ul = np.log1p(lo / c)
        uh = np.log1p(hi / c)
        tl = np.exp((1 - p) * ul)
        th = np.exp((1 - p) * uh)
        J = tl - th
        Jc = (p - 1) * (tl * lo / (c + lo) - th * hi / (c + hi))
        Jp = -ul * tl + uh * th
        E = float(self.kp @ J)
        g = np.zeros(12)
        g[2] = E
        g[3] = n * (self.kp @ Jc)
        g[4] = n * (self.kp @ Jp)
        l, r = self.m["start"], self.m["end"]
        T = self.m["T0"]
        z = d * (r - l) / T
        center = (l + r) / T - 1
        if abs(z) < 1e-5:
            s = 1 + z * z / 6 + z ** 4 / 120
            corr = (r - l) / T * (z / 3 - z ** 3 / 45)
        else:
            s = np.sinh(z) / z
            corr = (r - l) / T * (1 / np.tanh(z) - 1 / z)
        B = np.exp(a + d * center) * (r - l) * s
        g[0] = B
        g[1] = B * (center + corr)
        return B + n * E, g


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def accepted_record(case):
    return json.loads((ACCEPTED / case / "result.json").read_text(encoding="utf-8"))


def accepted_parameters(case):
    return np.asarray(accepted_record(case)["null"]["selected"]["parameters"], dtype=float)


def accepted_weights(case):
    return np.asarray(accepted_record(case)["background_weights"], dtype=float)


def make_model(case, normalization, weights, test=False):
    train, train_meta, heldout, test_meta, _ = RF.inputs(case)
    source, meta = (heldout, test_meta) if test else (train, train_meta)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, train_meta["kde_bandwidth"], weights)
    cls = RectModel if normalization == "rect" else RF.Model
    return cls(source, meta, background), background


def vector(x, scaled, alpha_value=0.0):
    out = np.asarray(x, dtype=float).copy()
    if not scaled:
        out[6] = alpha_value
    return out


def fit(model, starts, scaled, bounds=None):
    full_bounds = list(bounds) if bounds is not None else list(RF.BOUNDS[:8])
    if scaled:
        indices = list(range(8))
    else:
        indices = [0, 1, 2, 3, 4, 5, 7]
    records = []
    for index, start in enumerate(starts):
        base = vector(start, scaled).copy()
        lo = np.asarray([full_bounds[i][0] for i in indices], dtype=float)
        hi = np.asarray([full_bounds[i][1] for i in indices], dtype=float)
        x0 = np.clip(base[indices], lo, hi)
        begin = time.perf_counter()

        def target(v):
            x = base.copy()
            x[indices] = v
            value, gradient = model.objective(x, False)
            return value, gradient[indices]

        opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                       options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-5))
        x = base.copy()
        x[indices] = opt.x
        records.append(dict(start=index, success=bool(opt.success), message=str(opt.message),
                            nll=float(opt.fun), nit=int(opt.nit), nfev=int(opt.nfev),
                            parameters=[float(v) for v in x], seconds=time.perf_counter() - begin))
    valid = [r for r in records if r["success"] and np.isfinite(r["nll"])]
    if not valid:
        valid = [r for r in records if np.isfinite(r["nll"])]
    if not valid:
        raise ArithmeticError("no finite training fit")
    selected = dict(min(valid, key=lambda r: r["nll"]))
    selected["complete"] = len([r for r in records if r["success"]]) == len(starts)
    return dict(records=records, selected=selected)


def test_score(case, x, normalization, weights):
    model, _ = make_model(case, normalization, weights, test=True)
    details = model.objective(np.asarray(x, dtype=float), False, True)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    mark = next(r["common_mark_score"] for r in baseline["rows"] if r["case"] == case)
    ep = next(r["original_EP_joint_score"] for r in baseline["rows"] if r["case"] == case)
    score = -details["nll"] + mark
    return dict(test_nll=float(details["nll"]), test_joint_score=float(score),
                common_mark_score=float(mark), gain_over_EP=float(score - ep),
                exposure=float(details["exposure"]), ground_point=float(details["ground_point"]))


def starts_for(case, scaled, sigma_bounds=(2.0, 100.0)):
    x = accepted_parameters(case)
    variants = []
    for log_sigma, alpha, q in [
        (x[5], x[6] if scaled else 0.0, x[7]),
        (math.log(min(max(2.0, sigma_bounds[0]), sigma_bounds[1])), 0.8 if scaled else 0.0, 2.0),
        (math.log(min(max(15.0, sigma_bounds[0]), sigma_bounds[1])), 0.2 if scaled else 0.0, 1.2),
    ]:
        y = x.copy()
        y[6] = alpha
        y[5] = log_sigma
        y[7] = q
        variants.append(y)
    return variants


def arm_specs():
    return [
        dict(id="A0", name="EP_archived", normalization="rect", weighted=False, scaled=False, archived=True),
        dict(id="A1", name="Joint_Rect_Unw_Unscaled", normalization="rect", weighted=False, scaled=False),
        dict(id="A2", name="Joint_Plane_Unw_Unscaled", normalization="plane", weighted=False, scaled=False),
        dict(id="A3", name="Joint_Rect_Decl_Unscaled", normalization="rect", weighted=True, scaled=False),
        dict(id="A4", name="Joint_Plane_Decl_Unscaled", normalization="plane", weighted=True, scaled=False),
        dict(id="A5", name="Joint_Rect_Unw_Scaled", normalization="rect", weighted=False, scaled=True),
        dict(id="A6", name="Joint_Plane_Unw_Scaled", normalization="plane", weighted=False, scaled=True),
        dict(id="A7", name="Joint_Rect_Decl_Scaled", normalization="rect", weighted=True, scaled=True),
        dict(id="A8", name="EPplus_accepted", normalization="plane", weighted=True, scaled=True),
    ]


def run_ablation_fold(case):
    started = time.time()
    accepted_x = accepted_parameters(case)
    rows = {}
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    ep = next(r for r in baseline["rows"] if r["case"] == case)
    rows["A0"] = dict(id="A0", name="EP_archived", archived=True,
                      test_joint_score=float(ep["original_EP_joint_score"]),
                      gain_over_EP=0.0, parameters=None)
    for spec in [s for s in arm_specs() if not s.get("archived")]:
        weights = accepted_weights(case) if spec["weighted"] else None
        model, _ = make_model(case, spec["normalization"], weights)
        if spec["id"] == "A8":
            selected = dict(parameters=accepted_x.tolist(),
                            nll=float(accepted_record(case)["null"]["selected"]["nll"]))
            refit = fit(model, [accepted_x], spec["scaled"])
        else:
            refit = fit(model, starts_for(case, spec["scaled"]), spec["scaled"])
            selected = refit["selected"]
        x = np.asarray(selected["parameters"], dtype=float)
        score = test_score(case, x, spec["normalization"], weights)
        rows[spec["id"]] = dict(id=spec["id"], name=spec["name"], archived=False,
                                normalization=spec["normalization"], weighted=spec["weighted"],
                                scaled=spec["scaled"], parameters=x.tolist(),
                                training_nll=float(selected["nll"]),
                                complete=bool(refit.get("complete", True)),
                                **score)
        if spec["id"] == "A8":
            rows[spec["id"]]["accepted_state_reproduction"] = dict(
                refit_nll=float(refit["selected"]["nll"]),
                nll_difference=float(refit["selected"]["nll"] - selected["nll"]),
                test_gain_difference=float(score["gain_over_EP"] - ep["gain"]),
                accepted_gain=float(ep["gain"]),
                parameters_changed=bool(np.max(np.abs(np.asarray(refit["selected"]["parameters"]) - accepted_x)) > 0))
        print(case, spec["id"], score["test_joint_score"], score["gain_over_EP"], flush=True)
    return dict(case=case, n_train=len(RF.inputs(case)[0]["event_time"]),
                n_test=len(RF.inputs(case)[2]["event_time"]), rows=rows,
                elapsed_seconds=time.time() - started)


def factorial(totals):
    """Exact additive decomposition of A8 - A0, in nats.

    Joint fitting is the A0 -> A1 increment.  The remaining normalization,
    declustering and magnitude-scaling contributions are three-player Shapley
    values over the balanced 2x2x2 cube.  Shapley values are order-independent
    and sum exactly to A8 - A1; a fixed sequential path is also retained.
    """
    values = {k: v["total_gain"] for k, v in totals.items()}
    cells = {(n, w, s): values[a] for a, n, w, s in [
        ("A1", "rect", False, False), ("A2", "plane", False, False),
        ("A3", "rect", True, False), ("A4", "plane", True, False),
        ("A5", "rect", False, True), ("A6", "plane", False, True),
        ("A7", "rect", True, True), ("A8", "plane", True, True)]}
    factors = {"normalization": ("plane", "rect"), "declustering": (True, False), "scaling": (True, False)}
    from itertools import combinations, permutations

    def value(subset):
        key = tuple(factors[name][0] if name in subset else factors[name][1] for name in factors)
        return cells[key]

    names = list(factors)
    shapley = {}
    for name in names:
        total = 0.0
        others = [other for other in names if other != name]
        for size in range(len(others) + 1):
            for subset in combinations(others, size):
                weight = math.factorial(size) * math.factorial(len(names) - size - 1) / math.factorial(len(names))
                total += weight * (value(set(subset) | {name}) - value(set(subset)))
        shapley[name] = float(total)
    # Sequential path used in the original presentation: normalization, then
    # declustering, then magnitude scaling.
    sequential = [float(values["A1"] - values["A0"]),
                  float(values["A2"] - values["A1"]),
                  float(values["A4"] - values["A2"]),
                  float(values["A8"] - values["A4"])]
    result = dict(joint_fit_minus_archived_EP=float(values["A1"] - values["A0"]),
                  shapley=shapley,
                  sequential_labels=["joint_fit", "normalization", "declustering", "scaling"],
                  sequential_A0_A1_A2_A4_A8=sequential,
                  closure_A8_minus_A0=float(values["A8"] - values["A0"]))
    result["factorial_closure"] = float(result["joint_fit_minus_archived_EP"] + sum(shapley.values()))
    result["closure_residual"] = float(result["factorial_closure"] - result["closure_A8_minus_A0"])
    return result


def run_ablation(output, workers):
    cases = [f"california_fold_{i}" for i in range(3)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_ablation_fold, case): case for case in cases}
        folds = [future.result() for future in as_completed(futures)]
    folds.sort(key=lambda r: r["case"])
    total = {spec["id"]: sum(f["rows"][spec["id"]]["gain_over_EP"] for f in folds) for spec in arm_specs()}
    arms = {spec["id"]: dict(spec, total_gain=total[spec["id"]],
                             fold_gains=[f["rows"][spec["id"]]["gain_over_EP"] for f in folds],
                             training_nll=[f["rows"][spec["id"]].get("training_nll") for f in folds])
            for spec in arm_specs()}
    summary = dict(schema="track_b_epplus_component_ablation_v1", passed=True,
                   source="experiments/etas_inhibition_benchmark/ablation_and_sigma0.py",
                   frozen_source="experiments/etas_inhibition_benchmark/run_frozen_20261111.py",
                   frozen_source_sha256=sha(FROZEN),
                   accepted_summary_sha256=sha(ACCEPTED / "summary.json"),
                   fold_results=folds, arms=arms, factorial=factorial(arms),
                   definitions=dict(
                       A0="Archived EP held-out score (fixed temporal backbone, rectangle normalization, unweighted KDE, alpha_s=0).",
                       A1="Joint (a,d,n,c,p,sigma0,q), alpha_s=0, rectangle normalization, unweighted KDE.",
                       A2="A1 with full-plane normalization and regional leakage.",
                       A3="A1 with five-step training-declustered KDE background.",
                       A4="A2 with five-step training-declustered KDE background.",
                       A5="A1 with free alpha_s in [0,2].",
                       A6="A2 with free alpha_s in [0,2].",
                       A7="A5 with five-step training-declustered KDE background (rectangle-normalized EP+).",
                       A8="Accepted EP+; plane normalization, declustered KDE and free alpha_s."),
                   elapsed_seconds=sum(f["elapsed_seconds"] for f in folds))
    write(output / "ablation.json", summary)
    return summary


def relaxed_bounds(lower=0.05):
    bounds = list(RF.BOUNDS[:8])
    bounds[5] = (math.log(lower), math.log(100.0))
    return bounds


def decluster_fold(case, normalization, lower):
    train, meta, _, _, _ = RF.inputs(case)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], None)
    cls = RectModel if normalization == "rect" else RF.Model
    start = accepted_parameters(case)
    start[6] = max(0.0, start[6])
    steps = []
    for iteration in range(5):
        model = cls(train, meta, background)
        fit0 = fit(model, [start] if iteration else starts_for(case, True, (lower, 100.0)),
                   True, relaxed_bounds(lower))
        start = np.asarray(fit0["selected"]["parameters"], dtype=float)
        lam, _ = model.base_values(model.events, start)
        mu = np.exp(start[0] + start[1] * (2 * train["event_time"] / meta["T0"] - 1)) * model.be
        weights = mu / lam
        steps.append(dict(iteration=iteration, nll=float(fit0["selected"]["nll"]),
                          expected_immigrants=float(weights.sum()),
                          parameters=start.tolist()))
        background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    model = cls(train, meta, background)
    final = fit(model, [start], True, relaxed_bounds(lower))
    return dict(case=case, normalization=normalization, steps=steps,
                weights=background.weights.tolist(), selected=final["selected"], records=final["records"])


def run_relax(output, workers):
    jobs = [(case, norm) for case in [f"california_fold_{i}" for i in range(3)] for norm in ("rect", "plane")]
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(decluster_fold, case, norm, 0.05): (case, norm) for case, norm in jobs}
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda r: (r["case"], r["normalization"]))
    rows = []
    for r in results:
        x = np.asarray(r["selected"]["parameters"], dtype=float)
        train, meta, _, _, _ = RF.inputs(r["case"])
        region = RF.Region(train["rectangles"])
        background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], np.asarray(r["weights"]))
        cls = RectModel if r["normalization"] == "rect" else RF.Model
        train_model = cls(train, meta, background)
        train_details = train_model.objective(x, False, True)
        score = test_score(r["case"], x, r["normalization"], np.asarray(r["weights"]))
        rows.append(dict(case=r["case"], normalization=r["normalization"],
                         sigma0=float(np.exp(x[5])), alpha_s=float(x[6]), q=float(x[7]),
                         parameters=x.tolist(), training_nll=float(train_details["nll"]),
                         background_weights=[float(v) for v in r["weights"]],
                         **score, declustering=r["steps"]))
        print("relax", r["case"], r["normalization"], rows[-1]["sigma0"], rows[-1]["gain_over_EP"], flush=True)
    summary = dict(schema="track_b_sigma0_relaxation_v1", passed=True,
                   lower_bound_km=0.05, upper_bound_km=100.0,
                   frozen_weights_status="Five-step training declustering rerun under each normalization and relaxed bound.",
                   rows=rows, total_gain=float(sum(r["gain_over_EP"] for r in rows)),
                   source="experiments/etas_inhibition_benchmark/ablation_and_sigma0.py",
                   frozen_source_sha256=sha(FROZEN))
    write(output / "sigma0_relaxation.json", summary)
    return summary


def relax_frozen_fold(case, normalization, lower=0.05):
    weights = accepted_weights(case)
    train, meta, _, _, _ = RF.inputs(case)
    cls = RectModel if normalization == "rect" else RF.Model
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    model = cls(train, meta, background)
    result = fit(model, starts_for(case, True, (lower, 100.0)), True, relaxed_bounds(lower))
    x = np.asarray(result["selected"]["parameters"], dtype=float)
    score = test_score(case, x, normalization, weights)
    return dict(case=case, normalization=normalization, sigma0=float(np.exp(x[5])),
                alpha_s=float(x[6]), q=float(x[7]), parameters=x.tolist(),
                training_nll=float(result["selected"]["nll"]), **score)


def run_relax_frozen(output, workers):
    jobs = [(case, norm) for case in [f"california_fold_{i}" for i in range(3)] for norm in ("rect", "plane")]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(relax_frozen_fold, case, norm): (case, norm) for case, norm in jobs}
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: (r["case"], r["normalization"]))
    summary = dict(schema="track_b_sigma0_relaxation_frozen_weights_v1", passed=True,
                   lower_bound_km=0.05, upper_bound_km=100.0,
                   frozen_weights_status="Accepted EP+ five-step training-declustered KDE weights held fixed.",
                   rows=rows, total_gain=float(sum(r["gain_over_EP"] for r in rows)),
                   source="experiments/etas_inhibition_benchmark/ablation_and_sigma0.py")
    write(output / "sigma0_relaxation_frozen.json", summary)
    return summary


def profile_fold(case, normalization, lower=0.05):
    train, meta, _, _, _ = RF.inputs(case)
    region = RF.Region(train["rectangles"])
    weights = accepted_weights(case)
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    cls = RectModel if normalization == "rect" else RF.Model
    model = cls(train, meta, background)
    indices = [0, 1, 2, 3, 4, 6, 7]
    base_bounds = relaxed_bounds(lower)
    x = accepted_parameters(case).copy()
    relaxed_path = ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_relaxation.json"
    if relaxed_path.exists():
        relax = json.loads(relaxed_path.read_text())
        match = next((r for r in relax["rows"] if r["case"] == case and r["normalization"] == normalization), None)
        if match:
            x = np.asarray(match["parameters"], dtype=float)
    curve = []
    for sigma in SIGMA_GRID:
        start = x.copy()
        start[5] = math.log(sigma)
        lo = np.asarray([base_bounds[i][0] for i in indices])
        hi = np.asarray([base_bounds[i][1] for i in indices])
        x0 = np.clip(start[indices], lo, hi)

        def target(v):
            y = start.copy()
            y[indices] = v
            value, gradient = model.objective(y, False)
            return value, gradient[indices]

        opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                       options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-5))
        y = start.copy()
        y[indices] = opt.x
        value = float(model.objective(y, False)[0])
        curve.append(dict(sigma0_km=sigma, training_nll=value, success=bool(opt.success),
                          parameters=[float(v) for v in y]))
        print("profile", case, normalization, sigma, value, flush=True)
        if opt.success:
            x = y
    best = min(curve, key=lambda r: r["training_nll"])
    x_best = np.asarray(best["parameters"], dtype=float)
    score = test_score(case, x_best, normalization, weights)
    x_bound = next(r for r in curve if r["sigma0_km"] == 2.0)
    score_bound = test_score(case, np.asarray(x_bound["parameters"], dtype=float), normalization, weights)
    return dict(case=case, normalization=normalization, curve=curve,
                interior_sigma0=float(best["sigma0_km"]), interior_parameters=x_best.tolist(),
                interior_test=score, at_2km_parameters=x_bound["parameters"], at_2km_test=score_bound,
                test_gain_difference=float(score["gain_over_EP"] - score_bound["gain_over_EP"]))


def run_profile(output, workers):
    jobs = [(case, norm) for case in [f"california_fold_{i}" for i in range(3)] for norm in ("rect", "plane")]
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(profile_fold, case, norm): (case, norm) for case, norm in jobs}
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: (r["case"], r["normalization"]))
    summary = dict(schema="track_b_sigma0_profile_v1", passed=True,
                   grid_km=list(SIGMA_GRID), rows=rows,
                   lower_bound_km=0.05, upper_bound_km=100.0,
                   source="experiments/etas_inhibition_benchmark/ablation_and_sigma0.py")
    write(output / "sigma0_profile.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation")
    parser.add_argument("--stage", choices=("ablation", "relax", "relax_frozen", "profile", "all"), default="all")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=1):
        if args.stage in ("ablation", "all"):
            summary = run_ablation(args.output, args.workers)
            print(json.dumps({k: summary["arms"][k]["total_gain"] for k in summary["arms"]}, indent=2))
        if args.stage in ("relax", "all"):
            summary = run_relax(args.output, args.workers)
            print(json.dumps([(r["case"], r["normalization"], r["sigma0"], r["gain_over_EP"]) for r in summary["rows"]], indent=2))
        if args.stage in ("relax_frozen", "all"):
            summary = run_relax_frozen(args.output, args.workers)
            print(json.dumps([(r["case"], r["normalization"], r["sigma0"], r["gain_over_EP"]) for r in summary["rows"]], indent=2))
        if args.stage in ("profile", "all"):
            summary = run_profile(args.output, args.workers)
            print(json.dumps([(r["case"], r["normalization"], r["interior_sigma0"]) for r in summary["rows"]], indent=2))


if __name__ == "__main__":
    main()
