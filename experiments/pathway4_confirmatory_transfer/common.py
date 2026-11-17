"""Shared paths, custody helpers and descriptive statistics for Pathway 4."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/pathway4_confirmatory_20261116"
REPORT = ROOT / "docs/reviews/pathway4_confirmatory_report_20261116.md"
PROTOCOL = ROOT / "experiments/pathway4_confirmatory_transfer/frozen_protocol_v1.json"
PROTOCOL_SHA = ROOT / "experiments/pathway4_confirmatory_transfer/frozen_protocol_v1.sha256"

S03_REGISTRY = ROOT / "reproduction/score_replay/s03/registry.json"
S03_ARCHIVE = ROOT / "reproduction/score_replay/s03/inputs/cached_01.zip"
JMA_REGISTRY = ROOT / "reproduction/score_replay/jma/registry.json"
JMA_ARCHIVE = ROOT / "reproduction/score_replay/jma/inputs/cached_01.zip"
CA_REGISTRY = ROOT / "reproduction/score_replay/california/registry.json"
CA_ARCHIVE = ROOT / "reproduction/score_replay/california/inputs/cached_01.zip"
CA_ARCHIVE_2 = ROOT / "reproduction/score_replay/california/inputs/cached_02.zip"
NZ_AUTHORITIES = {
    0: ROOT / "validation/authorities/d03344116f577c89_m02_s03_nz_0_aggregate.json",
    1: ROOT / "validation/authorities/de8465f0cc4a6064_m02_s03_nz_1_aggregate.json",
    2: ROOT / "validation/authorities/4cf9a1c1e82fc2db_m02_s03_nz_2_aggregate.json",
}
CA_INTERIOR = ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_relaxation.json"
CA_BENCHMARK = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112"
FORENSIC = ROOT / "validation/live_results/forensic_remediation_20261114"

M0 = {"NZ": 5.0, "JMA": 4.5, "CA": 4.0}
MIN_MAG = {"NZ": 5.0, "JMA": 4.5, "CA": 4.0}

PARAM_NAMES = ["a", "d", "n", "log_c", "p", "log_sigma0", "alpha_s", "q",
               "eta", "log_ell0", "log_psi", "gamma"]


def read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def stats(values) -> dict:
    v = np.asarray(values, dtype=float)
    if len(v) == 0:
        raise ValueError("empty statistic")
    return dict(
        N=int(len(v)),
        mean=float(v.mean()),
        median=float(np.median(v)),
        sample_sd=float(v.std(ddof=1)) if len(v) > 1 else 0.0,
        mcse=float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else 0.0,
        wins=int(np.sum(v > 0)),
        q25=float(np.percentile(v, 25)),
        q75=float(np.percentile(v, 75)),
        minimum=float(v.min()),
        maximum=float(v.max()),
        values=[float(x) for x in v],
    )


def get_pointer(value, pointer: str):
    """Minimal JSON pointer reader (the same semantics as score_replay.core)."""
    if pointer == "":
        return value
    for part in pointer.lstrip("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def file_manifest(paths) -> dict:
    return {str(Path(p).relative_to(ROOT)).replace("\\", "/"): sha256(p)
            for p in paths}
