"""Read-only adapters for the three confirmatory cohorts.

Every loader returns an ``EPView``.  The training loaders only expose the
training prefix; test-window arrays are opened by the scoring stage after all
fits have been sealed.  Archived comparator scores are read by the separate
scoring stage only.
"""
from __future__ import annotations

import io
import json
import math
import zipfile
from pathlib import Path
from typing import Optional

import numpy as np

from .common import (CA_REGISTRY, JMA_REGISTRY, NZ_AUTHORITIES, S03_REGISTRY,
                     read_json)
from .geometry import Background, Region
from .model import EPView

JMA_RECT = np.array([(-600.0, -200.0, -800.0, -800.0 / 3.0),
                     (-200.0, 200.0, -800.0, -800.0 / 3.0),
                     (200.0, 600.0, -800.0, -800.0 / 3.0),
                     (-600.0, -200.0, -800.0 / 3.0, 800.0 / 3.0),
                     (-200.0, 200.0, -800.0 / 3.0, 800.0 / 3.0),
                     (200.0, 600.0, -800.0 / 3.0, 800.0 / 3.0),
                     (-600.0, -200.0, 800.0 / 3.0, 800.0),
                     (-200.0, 200.0, 800.0 / 3.0, 800.0),
                     (200.0, 600.0, 800.0 / 3.0, 800.0)])


def _zip_member(archive: Path, member: str) -> bytes:
    with zipfile.ZipFile(archive) as z:
        return z.read(member)


def _npz(data: bytes) -> dict:
    with np.load(io.BytesIO(data), allow_pickle=False) as f:
        return {k: f[k].copy() for k in f.files}


def _metadata(arrays: dict) -> dict:
    return json.loads(str(arrays["metadata_json"].item()))


# --------------------------------------------------------------------------- #
# California (primary M >= 4.0 cohort; the interior EP+ calibration origins)
# --------------------------------------------------------------------------- #

def ca_registry_rows(fold: int):
    reg = read_json(CA_REGISTRY)
    rows = [r for r in reg["rows"]
            if r["case"] == f"california_fold_{fold}"
            and r["procedure_key"] == "Omori_smooth_cont"
            and r["study"] == "primary_california"]
    out = {r["phase"]: r for r in rows}
    if set(out) != {"train", "test"}:
        raise ValueError("California primary train/test roster")
    return out


def load_ca_arrays(fold: int):
    rows = ca_registry_rows(fold)
    folder = CA_REGISTRY.parent
    arrays = {}
    meta = {}
    for phase, row in rows.items():
        spec = row["cache"]
        arrays[phase] = _npz(_zip_member(folder / spec["archive"], spec["member"]))
        meta[phase] = _metadata(arrays[phase])
    return rows, arrays, meta


def ca_train_view(fold: int, weights=None, floor_mode: str = "uniform") -> EPView:
    _rows, arrays, meta = load_ca_arrays(fold)
    a = arrays["train"]
    m = meta["train"]
    region = Region(a["rectangles"])
    bg = Background(a["kde_training_xy"], region, m["kde_bandwidth"], weights,
                    reference_pi=a["reference_pi"], floor_mode=floor_mode)
    return EPView(
        region=region, background=bg, T0=float(m["T0"]),
        start=float(m["start"]), end=float(m["end"]),
        parent_time=a["parent_time"], parent_excess=a["parent_excess"],
        parent_xy=a["parent_xy"], parent_fertility=a["parent_fertility"],
        event_time=a["event_time"], event_excess=a["event_excess"],
        event_xy=a["event_xy"], event_x=a["event_x"], M0=4.0,
        beta=float(m["beta"]),
        leave_self_background=True,
    )


def ca_test_view(fold: int, background: Background) -> EPView:
    _rows, arrays, meta = load_ca_arrays(fold)
    a = arrays["test"]
    m = meta["test"]
    return EPView(
        region=background.region, background=background, T0=float(m["T0"]),
        start=float(m["start"]), end=float(m["end"]),
        parent_time=a["parent_time"], parent_excess=a["parent_excess"],
        parent_xy=a["parent_xy"], parent_fertility=a["parent_fertility"],
        event_time=a["event_time"], event_excess=a["event_excess"],
        event_xy=a["event_xy"], event_x=a["event_x"], M0=4.0,
        beta=float(m["beta"]),
    )


def ca_mark_score(fold: int, phase: str = "test") -> dict:
    _rows, arrays, meta = load_ca_arrays(fold)
    a = arrays[phase]
    beta = float(meta[phase]["beta"])
    score = float(len(a["event_excess"]) * math.log(beta) -
                  beta * a["event_excess"].sum())
    return dict(score=score, beta=beta, n=int(len(a["event_excess"])))


# --------------------------------------------------------------------------- #
# New Zealand (S03 cached spatial folds)
# --------------------------------------------------------------------------- #

def nz_registry_rows(fold: int):
    reg = read_json(S03_REGISTRY)
    rows = [r for r in reg["rows"] if r["case"] == f"NZ_fold_{fold}"]
    out = {r["arm"]: r for r in rows}
    if set(out) != {1, 2, 3, 4}:
        raise ValueError("S03 NZ four-arm roster")
    return out


def load_nz_cache(fold: int):
    rows = nz_registry_rows(fold)
    spec = rows[1]["cache"]
    arrays = _npz(_zip_member(S03_REGISTRY.parent / spec["archive"], spec["member"]))
    return rows, arrays, _metadata(arrays)


def nz_train_view(fold: int, weights=None, floor_mode: str = "uniform") -> EPView:
    _rows, a, m = load_nz_cache(fold)
    start = float(m["start"])
    keep = a["parent_time"] < start
    if not np.array_equal(a["kde_training_xy"], a["parent_xy"][keep]):
        raise ValueError("NZ KDE training set is not the pre-origin parent prefix")
    region = Region(a["rectangles"])
    bg = Background(a["kde_training_xy"], region, m["kde_bandwidth"], weights,
                    reference_pi=a["reference_pi"], floor_mode=floor_mode)
    t = a["parent_time"][keep]
    return EPView(
        region=region, background=bg, T0=float(m["T0"]),
        start=0.0, end=start,
        parent_time=t, parent_excess=a["parent_excess"][keep],
        parent_xy=a["parent_xy"][keep],
        parent_fertility=a["parent_fertility"][keep],
        event_time=t, event_excess=a["parent_excess"][keep],
        event_xy=a["parent_xy"][keep], event_x=2.0 * t / float(m["T0"]) - 1.0,
        M0=5.0, beta=float(m["beta"]), leave_self_background=True,
    )


def nz_test_view(fold: int, background: Background) -> EPView:
    _rows, a, m = load_nz_cache(fold)
    t = a["event_time"]
    return EPView(
        region=background.region, background=background, T0=float(m["T0"]),
        start=float(m["start"]), end=float(m["end"]),
        parent_time=a["parent_time"], parent_excess=a["parent_excess"],
        parent_xy=a["parent_xy"], parent_fertility=a["parent_fertility"],
        event_time=t, event_excess=a["event_excess"],
        event_xy=a["event_xy"], event_x=2.0 * t / float(m["T0"]) - 1.0,
        M0=5.0, beta=float(m["beta"]),
    )


def nz_mark_score(fold: int) -> dict:
    _rows, a, m = load_nz_cache(fold)
    beta = float(m["beta"])
    score = float(len(a["event_excess"]) * math.log(beta) -
                  beta * a["event_excess"].sum())
    return dict(score=score, beta=beta, n=int(len(a["event_excess"])))


def nz_archived(fold: int) -> dict:
    d = read_json(NZ_AUTHORITIES[fold])
    out = {}
    for row in d["results"]:
        out[int(row["arm"])] = dict(scores=row["scores"], n_test=row["n_test"],
                                    bandwidth_km=row["bandwidth_km"])
    return dict(fold=fold, arms=out, case_id=d["case_id"])


def nz_archived_comparators(fold: int) -> dict:
    d = nz_archived(fold)
    oc = d["arms"][1]
    ep = d["arms"][4]
    return dict(
        oc=dict(timing=oc["scores"]["timing"], location=oc["scores"]["location"],
                joint=oc["scores"]["joint"], mark=oc["scores"]["mark"],
                n_test=oc["n_test"]),
        ep=dict(timing=ep["scores"]["timing"], location=ep["scores"]["location"],
                joint=ep["scores"]["joint"], mark=ep["scores"]["mark"],
                n_test=ep["n_test"]),
        case_id=d["case_id"],
    )


# --------------------------------------------------------------------------- #
# Japan (JMA reported-primary M >= 4.5 cohort)
# --------------------------------------------------------------------------- #

def _jma_rows(fold: int):
    reg = read_json(JMA_REGISTRY)
    return [r for r in reg["rows"] if r["case"] == f"JMA_fold_{fold}"]


def load_jma_catalogue():
    reg = read_json(JMA_REGISTRY)
    row = next(r for r in reg["rows"] if "catalogue" in r)
    arrays = _npz(_zip_member(JMA_REGISTRY.parent / row["catalogue"]["archive"],
                              row["catalogue"]["member"]))
    return arrays


def load_jma_state(fold: int) -> dict:
    rows = _jma_rows(fold)
    row = next(r for r in rows if r["id"].endswith("/EP/full"))
    return json.loads(_zip_member(JMA_REGISTRY.parent / row["state"]["archive"],
                                  row["state"]["member"]))


def jma_nuisance(fold: int) -> dict:
    return load_jma_state(fold)["nuisance"]


def _jma_training_mask(cat, fold):
    return cat["fold_training_mask"][fold]


def _jma_test_mask(cat, fold):
    return cat["fold_test_mask"][fold]


def load_jma_catalogue_arrays():
    cat = load_jma_catalogue()
    cat["rectangles"] = JMA_RECT
    cat["cell_areas"] = ((JMA_RECT[:, 1] - JMA_RECT[:, 0]) *
                         (JMA_RECT[:, 3] - JMA_RECT[:, 2]))
    return cat


def _jma_fertility(cat, nu):
    return nu["kappa_prefactor"] * np.exp(0.7 * nu["beta"] * 0.1 *
                                          cat["K"].astype(float))


def jma_train_view(fold: int, cat=None, weights=None,
                    floor_mode: str = "uniform") -> EPView:
    if cat is None:
        cat = load_jma_catalogue_arrays()
    nu = jma_nuisance(fold)
    origin = float(cat["fold_origin_days"][fold])
    # training events are the fold training mask; the parent prefix includes
    # the preceding warm-up events that can trigger them.
    train = _jma_training_mask(cat, fold)
    if int(train.sum()) != int(nu["N"]):
        raise ValueError("JMA training count differs from nuisance state")
    parent_keep = cat["t_days"] < origin
    xy = cat["xy_km"][parent_keep]
    region = Region(cat["rectangles"])
    h = float(nu["h_km"])
    bg = Background(cat["xy_km"][train], region, h, weights,
                    reference_pi=nu["reference_pi"], floor_mode=floor_mode)
    t = cat["t_days"][train]
    return EPView(
        region=region, background=bg, T0=float(nu["T0"]),
        start=float(nu["training_start"]), end=origin,
        parent_time=cat["t_days"][parent_keep],
        parent_excess=cat["Q"][parent_keep],
        parent_xy=xy,
        parent_fertility=_jma_fertility(cat, nu)[parent_keep],
        event_time=t, event_excess=cat["Q"][train],
        event_xy=cat["xy_km"][train],
        event_x=2.0 * t / float(nu["T0"]) - 1.0,
        M0=4.5, beta=float(nu["beta"]), leave_self_background=True,
    )


def jma_test_view(fold: int, background: Background, cat=None) -> EPView:
    if cat is None:
        cat = load_jma_catalogue_arrays()
    nu = jma_nuisance(fold)
    origin = float(cat["fold_origin_days"][fold])
    end = float(cat["fold_end_days"][fold])
    test = _jma_test_mask(cat, fold)
    parent_keep = cat["t_days"] < end
    return EPView(
        region=background.region, background=background, T0=float(nu["T0"]),
        start=origin, end=end,
        parent_time=cat["t_days"][parent_keep],
        parent_excess=cat["Q"][parent_keep],
        parent_xy=cat["xy_km"][parent_keep],
        parent_fertility=_jma_fertility(cat, nu)[parent_keep],
        event_time=cat["t_days"][test], event_excess=cat["Q"][test],
        event_xy=cat["xy_km"][test],
        event_x=2.0 * cat["t_days"][test] / float(nu["T0"]) - 1.0,
        M0=4.5, beta=float(nu["beta"]),
    )


def jma_mark_score(fold: int, cat=None) -> dict:
    if cat is None:
        cat = load_jma_catalogue_arrays()
    nu = jma_nuisance(fold)
    test = _jma_test_mask(cat, fold)
    n = int(test.sum())
    beta = float(nu["beta"])
    K = int(cat["K"][test].sum())
    score = float(n * math.log(-math.expm1(-beta * 0.1)) - beta * 0.1 * K)
    return dict(score=score, beta=beta, n=n, sum_K=K)


def jma_archived(fold: int, cat=None) -> dict:
    """Archived OC and EP components, both fold totals and annual blocks."""
    if cat is None:
        cat = load_jma_catalogue_arrays()
    rows = _jma_rows(fold)
    out = {"partitions": {}, "full": {}}
    for arm in ("OC", "EP"):
        ann = {}
        for row in rows:
            if row["arm"] != arm:
                continue
            part = row["partition"]
            if part == "full":
                out["full"][arm] = dict(row["expected_components"],
                                        n_test=row["n_events_expected"])
            else:
                ann[part] = dict(row["expected_components"],
                                 n_test=row["n_events_expected"])
        out["partitions"][arm] = ann
    return out


JMA_BLOCK_DAYS = {
    0: ((3652.0, 4018.0, "2016"), (4018.0, 4383.0, "2017"),
        (4383.0, 4748.0, "2018")),
    1: ((4748.0, 5113.0, "2019"), (5113.0, 5479.0, "2020"),
        (5479.0, 5844.0, "2021")),
    2: ((5844.0, 6209.0, "2022"), (6209.0, 6574.0, "2023"),
        (6574.0, 6940.0, "2024")),
}


def jma_block_view(fold: int, block_start: float, block_end: float,
                   background: Background, cat=None) -> EPView:
    if cat is None:
        cat = load_jma_catalogue_arrays()
    nu = jma_nuisance(fold)
    test = _jma_test_mask(cat, fold)
    test &= (cat["t_days"] >= block_start) & (cat["t_days"] < block_end)
    parent_keep = cat["t_days"] < block_end
    return EPView(
        region=background.region, background=background, T0=float(nu["T0"]),
        start=float(block_start), end=float(block_end),
        parent_time=cat["t_days"][parent_keep],
        parent_excess=cat["Q"][parent_keep],
        parent_xy=cat["xy_km"][parent_keep],
        parent_fertility=_jma_fertility(cat, nu)[parent_keep],
        event_time=cat["t_days"][test], event_excess=cat["Q"][test],
        event_xy=cat["xy_km"][test],
        event_x=2.0 * cat["t_days"][test] / float(nu["T0"]) - 1.0,
        M0=4.5, beta=float(nu["beta"]),
    )
