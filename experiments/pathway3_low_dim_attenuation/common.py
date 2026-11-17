"""Shared paths, JSON custody and descriptive statistics for Pathway 3."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/pathway3_low_dim_20261116"
REPORT = ROOT / "docs/reviews/pathway3_low_dim_report_20261116.md"

S8_TRUTH = np.array([math.log(0.25), 0.2, 0.35, math.log(0.05), 1.3, 0.4,
                     math.log(15.0), math.log(5.0)])
S8_SCALE_GRID = ((5.0, 1.0), (15.0, 5.0), (50.0, 30.0))
S8_TRAIN = (30.0, 395.0)
S8_TEST = (395.0, 760.0)
S8_MID = 212.5
S8_SEEDS = tuple(range(410821, 410841))
LAMBDA_GRID = (0.5, 1.0, 2.0)
ALPHA_GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


def read_json(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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


def rmse(values, target: float) -> float:
    v = np.asarray(values, dtype=float)
    return float(math.sqrt(np.mean((v - target) ** 2)))


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if n <= 0:
        return [0.0, 1.0]
    p = successes / n
    den = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(max(0.0, center - half)), float(min(1.0, center + half))]


def oracle_fraction(gain: float, ceiling: float) -> float:
    return float(gain / ceiling) if ceiling else 0.0
