"""Training-only arm execution shared by the New Zealand and Japan runners."""
from __future__ import annotations

import math
import time
from typing import Dict, List

import numpy as np

from .fit import (DEFAULT_STARTS, decluster, final_null_fit, parameter_summary)
from .model import EPModel, profile_attenuation

FREE_T0 = ("a", "d", "n", "log_c", "p", "log_sigma0", "alpha_s", "q")
FREE_T1 = ("a", "n", "log_c", "p", "log_sigma0", "alpha_s", "q")

MONO_GRID = ((5.0, 1.0), (15.0, 5.0), (50.0, 30.0))
GAMMA_FIXED = 0.75 * math.log(10.0)


def _starts(region, archived, trend):
    starts = [DEFAULT_STARTS["generic"].copy(),
              DEFAULT_STARTS["diffuse"].copy()]
    if region == "NZ" and archived is None:
        starts = [DEFAULT_STARTS["nz_ep"].copy(), starts[1]]
    elif archived is not None:
        starts = [np.asarray(archived, dtype=float), starts[1]]
    if trend == "T1":
        for s in starts:
            s[1] = 0.0
    return starts


def fit_null_arm(view, region: str, normalization: str, trend: str,
                 archived_start=None, steps: int = 5,
                 seed: int = 20261116):
    free = FREE_T0 if trend == "T0" else FREE_T1
    starts = _starts(region, archived_start, trend)
    began = time.perf_counter()
    view, trace = decluster(view, starts, normalization, steps=steps, free=free)
    final_starts = [np.asarray(trace[-1]["parameters"], dtype=float),
                    starts[0], starts[1]]
    if trend == "T1":
        for s in final_starts:
            s[1] = 0.0
    model, fit = final_null_fit(view, final_starts, normalization, free=free)
    x = np.asarray(fit["selected"]["parameters"], dtype=float)
    return dict(
        region=region, normalization=normalization, trend=trend,
        free=list(free), parameters=x.tolist(),
        parameter_summary=parameter_summary(x),
        training_nll=float(fit["selected"]["nll"]),
        fit_records=fit["records"], selected_start=fit["selected"]["start"],
        complete=bool(fit["complete"]),
        declustering=trace,
        background_weights=view.background.weights.tolist(),
        background_bandwidth_km=view.background.h,
        background_floor_mode=view.background.floor_mode,
        n_train=int(len(view.event_time)), n_parents=int(len(view.parent_time)),
        window=dict(start=float(view.start), end=float(view.end),
                    T0=float(view.T0)),
        wall_seconds=float(time.perf_counter() - began),
        _view=view, _model=model, _x=x,
    )


def add_attenuation_profiles(result: dict, power: int = 13,
                             seed: int = 20261116):
    """One-dimensional training profiles on the frozen null backbone."""
    from .model import make_attenuation_nodes, wells_coppersmith_ell
    model: EPModel = result["_model"]
    x = result["_x"]
    if result["normalization"] != "plane":
        result["attenuation_profiles"] = dict(
            status="not_run", reason="rect-normalised profile is a declared "
            "sensitivity; attenuation profiles are run on the plane arm only")
        return result
    excess = model.view.parent_excess
    M0 = getattr(model.view, "M0", 4.0)
    exact_E = model.exposure(x)[0]
    profiles = {}
    proposal_meta = {}
    for ell, psi in MONO_GRID:
        key = f"mono_{ell:g}_{psi:g}"
        mono_ell = ell * 10.0 ** (0.5 * excess)
        nodes = make_attenuation_nodes(model, x, mono_ell, psi, GAMMA_FIXED,
                                       power=power, seed=seed)
        profiles[key] = profile_attenuation(
            model, x, "mono", ell, psi, GAMMA_FIXED, nodes, max_eta=4.0)
        proposal_meta[key] = dict(draws=nodes["draws"],
                                  inside=nodes["inside"],
                                  Z_G=nodes["Z_G"],
                                  g_exposure=profiles[key]["exposure_integral"])
    wc_ell = wells_coppersmith_ell(excess, M0)
    nodes_wc = make_attenuation_nodes(model, x, wc_ell, 5.0, GAMMA_FIXED,
                                      power=power, seed=seed)
    profiles["ann2_wc"] = profile_attenuation(
        model, x, "ann2", None, 5.0, GAMMA_FIXED, nodes_wc, max_eta=4.0)
    proposal_meta["ann2_wc"] = dict(draws=nodes_wc["draws"],
                                    inside=nodes_wc["inside"],
                                    Z_G=nodes_wc["Z_G"],
                                    g_exposure=profiles["ann2_wc"]["exposure_integral"])
    mono_keys = [k for k in profiles if k.startswith("mono_")]
    mono_best = max(mono_keys, key=lambda k: (profiles[k]["gain"],
                                              -profiles[k]["eta"]))
    refined = profiles["ann2_wc"]
    result["attenuation_profiles"] = dict(
        status="complete",
        proposal=dict(power=power, seed=seed,
                      exact_null_exposure=float(exact_E),
                      per_arm=proposal_meta,
                      design="ann2 field importance proposal; Z_G is the "
                             "analytic in-domain ann2 normaliser"),
        mono_grid={k: profiles[k] for k in mono_keys},
        mono_selected=dict(key=mono_best,
                           eta=profiles[mono_best]["eta"],
                           gain=profiles[mono_best]["gain"]),
        refined_ann2_wc=refined,
        gamma=GAMMA_FIXED, psi_days=5.0,
    )
    return result


def strip_private(result: dict) -> dict:
    out = {k: v for k, v in result.items() if not k.startswith("_")}
    return out
