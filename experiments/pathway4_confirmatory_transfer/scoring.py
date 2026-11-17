"""Fit sealing and held-out scoring helpers (Pathway 4)."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np

from . import common as C
from .model import (make_attenuation_nodes, test_attenuation_gain,
                    wells_coppersmith_ell)
from .pipeline import GAMMA_FIXED

EXPECTED_FITS = (
    [(f"nz_fold_{f}_{n}_{t}", f"NZ_fold_{f}", n, t)
     for f in range(3) for n, t in (("plane", "T0"), ("plane", "T1"),
                                    ("rect", "T0"), ("rect", "T1"))]
    + [(f"jma_fold_{f}_{n}_{t}", f"JMA_fold_{f}", n, t)
       for f in range(3) for n, t in (("plane", "T0"), ("plane", "T1"),
                                      ("rect", "T1"))]
)


def manifest_sha(files: dict) -> str:
    body = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return C.sha256_bytes(body)


def build_fit_seal(protocol_path: Path = C.PROTOCOL) -> dict:
    if not protocol_path.exists():
        raise FileNotFoundError("frozen protocol missing")
    protocol_sha = C.sha256(protocol_path)
    pin = protocol_path.with_suffix(".sha256")
    if not pin.exists():
        raise FileNotFoundError("protocol hash pin missing")
    pinned = pin.read_text(encoding="utf-8").strip().split()[0]
    if pinned != protocol_sha:
        raise ValueError("protocol hash pin mismatch")
    files = {}
    for name, case, norm, trend in EXPECTED_FITS:
        path = C.OUT / "fits" / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"missing sealed fit: {path}")
        payload = C.read_json(path)
        if payload.get("protocol_sha256") != protocol_sha:
            raise ValueError(f"fit protocol mismatch: {name}")
        if payload.get("case") != case:
            raise ValueError(f"fit case mismatch: {name}")
        if payload.get("normalization") != norm or payload.get("trend") != trend:
            raise ValueError(f"fit arm mismatch: {name}")
        if any(str(k).startswith("test_") for k in payload):
            raise ValueError(f"test-derived key in fit artifact: {name}")
        files[str(path.relative_to(C.ROOT)).replace("\\", "/")] = C.sha256(path)
    seal = dict(
        schema="pathway4_fit_seal_v1",
        protocol_sha256=protocol_sha,
        sealed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        expected_arms=[dict(name=n, case=c, normalization=no, trend=t)
                       for n, c, no, t in EXPECTED_FITS],
        files=files,
        manifest_sha256=manifest_sha(files),
        source_pins=C.file_manifest([
            C.ROOT / "experiments/pathway4_confirmatory_transfer/geometry.py",
            C.ROOT / "experiments/pathway4_confirmatory_transfer/data.py",
            C.ROOT / "experiments/pathway4_confirmatory_transfer/model.py",
            C.ROOT / "experiments/pathway4_confirmatory_transfer/fit.py",
            C.ROOT / "experiments/pathway4_confirmatory_transfer/pipeline.py",
            C.ROOT / "experiments/pathway4_confirmatory_transfer/run_nz.py",
            C.ROOT / "experiments/pathway4_confirmatory_transfer/run_jma.py",
        ]),
    )
    C.write_json(C.OUT / "fit_seal.json", seal)
    return seal


def verify_fit_seal(seal_path: Path = C.OUT / "fit_seal.json",
                    protocol_path: Path = C.PROTOCOL) -> dict:
    seal = C.read_json(seal_path)
    protocol_sha = C.sha256(protocol_path)
    if seal.get("protocol_sha256") != protocol_sha:
        raise ValueError("fit seal protocol hash mismatch")
    pinned = protocol_path.with_suffix(".sha256").read_text(
        encoding="utf-8").strip().split()[0]
    if pinned != protocol_sha:
        raise ValueError("protocol pin mismatch")
    for rel, digest in seal["files"].items():
        path = C.ROOT / rel
        if not path.exists() or C.sha256(path) != digest:
            raise ValueError(f"sealed fit changed: {rel}")
    if manifest_sha(seal["files"]) != seal["manifest_sha256"]:
        raise ValueError("fit seal manifest hash mismatch")
    return seal


def fit_payload(name: str) -> dict:
    return C.read_json(C.OUT / "fits" / f"{name}.json")


def attenuation_test(payload: dict, model, x, power: int = 16,
                     seed: int = 20261120):
    """Held-out attenuation contrasts at the training-selected eta."""
    profiles = payload.get("attenuation_profiles", {}) or {}
    if profiles.get("status") != "complete":
        return dict(status="not_run", reason=profiles.get("reason"))
    mono_key = profiles["mono_selected"]["key"]
    mono = profiles["mono_grid"][mono_key]
    refined = profiles["refined_ann2_wc"]
    if float(mono["eta"]) == 0.0 and float(refined["eta"]) == 0.0:
        # The exact nested eta=0 state makes both held-out gains identically
        # zero; no importance sample is required.
        return dict(
            status="complete", power=power, seed=seed,
            short_circuit="both training etas are exactly zero",
            mono=dict(eta=0.0, gain=0.0),
            refined=dict(eta=0.0, gain=0.0, gain_check=0.0,
                         quadrature_delta=0.0),
        )
    excess = model.view.parent_excess
    M0 = getattr(model.view, "M0", 4.0)
    mono_key = profiles["mono_selected"]["key"]
    mono = profiles["mono_grid"][mono_key]
    mono_ell = mono["ell0_km"] * 10.0 ** (0.5 * excess)
    mono_nodes = make_attenuation_nodes(model, x, mono_ell, mono["psi_days"],
                                        GAMMA_FIXED, power=power, seed=seed)
    mono_gain = test_attenuation_gain(
        model, x, "mono", mono["ell0_km"], mono["psi_days"], GAMMA_FIXED,
        mono["eta"], mono_nodes)
    refined = profiles["refined_ann2_wc"]
    wc_ell = wells_coppersmith_ell(excess, M0)
    wc_nodes = make_attenuation_nodes(model, x, wc_ell, refined["psi_days"],
                                      GAMMA_FIXED, power=power, seed=seed)
    refined_gain = test_attenuation_gain(
        model, x, "ann2", None, refined["psi_days"], GAMMA_FIXED,
        refined["eta"], wc_nodes)
    # independent quadrature control
    wc_nodes2 = make_attenuation_nodes(model, x, wc_ell, refined["psi_days"],
                                       GAMMA_FIXED, power=power, seed=seed + 1)
    refined_check = test_attenuation_gain(
        model, x, "ann2", None, refined["psi_days"], GAMMA_FIXED,
        refined["eta"], wc_nodes2)
    return dict(
        status="complete",
        power=power, seed=seed,
        mono=dict(eta=mono["eta"], gain=mono_gain["gain"],
                  event_sum=mono_gain["event_sum"],
                  node_exposure=mono_gain["exposure_integral"]),
        refined=dict(eta=refined["eta"], gain=refined_gain["gain"],
                     event_sum=refined_gain["event_sum"],
                     node_exposure=refined_gain["exposure_integral"],
                     gain_check=refined_check["gain"],
                     quadrature_delta=refined_check["gain"] - refined_gain["gain"]),
    )


def contrast(ep_timing, ep_location, ep_joint, arch) -> dict:
    return dict(
        timing=float(ep_timing - arch["timing"]),
        location=float(ep_location - arch["location"]),
        joint=float(ep_joint - arch["joint"]),
    )


def mark_score_continuous(excess, beta) -> float:
    excess = np.asarray(excess, dtype=float)
    return float(len(excess) * math.log(beta) - beta * excess.sum())


def mark_score_lattice(Q, beta) -> float:
    Q = np.asarray(Q, dtype=float)
    K = np.rint(Q * 10.0)
    return float(len(Q) * math.log(-math.expm1(-beta * 0.1)) -
                 beta * 0.1 * K.sum())


# The pooled continuous omnibus is the archived implementation in
# ``engine/stage2_followup/s03_s06_spatial_benchmarks/continuous_omnibus.py``.
# It is reproduced here because that directory is not an importable package.
POOLED_RIDGE = 1e-8


def pooled_continuous_tests(x):
    x = np.asarray(x, float)
    if x.shape != (1000, 8) or not np.isfinite(x).all():
        raise ValueError("pooled continuous tests need 1000 finite rows x 8")
    mean = x.mean(axis=0)
    sd = x.std(axis=0, ddof=1)
    if not np.all(sd > 0):
        raise ValueError("DETERMINISTIC_CONTINUOUS_COORDINATE")
    z = (x - mean) / sd
    cov = z.T @ z / (len(x) - 1)
    regularized = cov + POOLED_RIDGE * np.eye(8)
    quadratic = np.einsum("ij,ji->i", z,
                          np.linalg.solve(regularized, z.T))
    coordinate_p = np.empty_like(x)
    ties = []
    for j in range(8):
        ordered = np.sort(x[:, j])
        lo = np.searchsorted(ordered, x[:, j], side="right") / len(x)
        hi = (len(x) - np.searchsorted(ordered, x[:, j], side="left")) / len(x)
        coordinate_p[:, j] = np.minimum(1, 2 * np.minimum(lo, hi))
        ties.append(int(len(x) - len(np.unique(x[:, j]))))
    fisher = -np.log(coordinate_p).sum(axis=1)

    def report(scores):
        return dict(
            observed_statistic=float(scores[0]),
            pooled_upper_inclusive_p=float(
                np.count_nonzero(scores >= scores[0]) / len(scores)),
            number_equal_observed=int(np.count_nonzero(scores == scores[0])),
            pooled_n=len(scores))

    return dict(
        quadratic=report(quadratic), fisher=report(fisher),
        coordinate_duplicate_counts=ties,
        observed_coordinate_two_sided_inclusive_p=coordinate_p[0].tolist(),
        covariance_condition_number=float(np.linalg.cond(regularized)),
        calibration="each statistic computed symmetrically on observed+999 "
                    "simulated rows; inclusive pooled upper rank; conservative "
                    "under ties",
        ridge=POOLED_RIDGE,
    )
