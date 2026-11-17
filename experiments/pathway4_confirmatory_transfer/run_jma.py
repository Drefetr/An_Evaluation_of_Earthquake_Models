"""Stage P4.2 fits: single-pass interior-scale EP+ and frozen attenuation
profiles on the three JMA folds.

This script reads only training-prefix arrays.  Test events and archived score
totals are opened exclusively by ``score_jma.py`` after ``fit_seal.json`` exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C, data
from experiments.pathway4_confirmatory_transfer.pipeline import (
    add_attenuation_profiles, fit_null_arm, strip_private)

ARMS = (("plane", "T0"), ("plane", "T1"), ("rect", "T1"))


def archived_start(fold: int):
    state = data.load_jma_state(fold)
    p = state["parameters"]
    return [float(p[0]), float(p[1]), float(p[2]), float(p[3]), float(p[4]),
            float(p[5]), 0.0, float(p[6])]


def run_fold(fold: int, protocol_sha: str, arms=ARMS):
    cat = data.load_jma_catalogue_arrays()
    results = {}
    for normalization, trend in arms:
        view = data.jma_train_view(fold, cat=cat, weights=None,
                                   floor_mode="uniform")
        result = fit_null_arm(view, "JMA", normalization, trend,
                              archived_start=archived_start(fold))
        if normalization == "plane":
            result = add_attenuation_profiles(result)
        payload = strip_private(result)
        payload.update(
            schema="pathway4_jma_fit_v1",
            fold=fold,
            case=f"JMA_fold_{fold}",
            source="experiments/pathway4_confirmatory_transfer/run_jma.py",
            source_sha256=C.sha256(Path(__file__)),
            protocol_sha256=protocol_sha,
            created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        path = C.OUT / "fits" / f"jma_fold_{fold}_{normalization}_{trend}.json"
        C.write_json(path, payload)
        results[(normalization, trend)] = dict(
            nll=payload["training_nll"],
            parameters=payload["parameters"],
            attenuation=(payload.get("attenuation_profiles", {}) or {}).get(
                "refined_ann2_wc", {}).get("eta"),
            wall_seconds=payload["wall_seconds"])
        print("jma", fold, normalization, trend, payload["training_nll"],
              results[(normalization, trend)]["attenuation"], flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold", type=int, required=True)
    parser.add_argument("--protocol", type=Path, default=C.PROTOCOL)
    args = parser.parse_args()
    if not args.protocol.exists():
        raise SystemExit("frozen protocol missing; run freeze_protocol.py first")
    protocol_sha = C.sha256(args.protocol)
    if args.protocol.with_suffix(".sha256").exists():
        pinned = args.protocol.with_suffix(".sha256").read_text().strip().split()[0]
        if pinned != protocol_sha:
            raise SystemExit("protocol sha256 pin does not match the protocol file")
    run_fold(args.fold, protocol_sha)


if __name__ == "__main__":
    main()
