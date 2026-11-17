"""Stage P4.1 fits: single-pass interior-scale EP+ and frozen attenuation
profiles on the three New Zealand S03 folds.

This script reads only training-prefix arrays.  Test events and archived score
totals are opened exclusively by ``score_nz.py`` after ``fit_seal.json`` exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C, data
from experiments.pathway4_confirmatory_transfer.pipeline import (
    add_attenuation_profiles, fit_null_arm, strip_private)

ARMS = (("plane", "T0"), ("plane", "T1"), ("rect", "T0"), ("rect", "T1"))


def archived_start(fold: int):
    rows = data.nz_registry_rows(fold)
    row = rows[4]
    state = json.loads(data._zip_member(
        data.S03_REGISTRY.parent / row["state"]["archive"],
        row["state"]["member"]))
    a, d, n = state["parameters"]
    lc, p = state["temporal"]
    scale, q = state["ep_spatial"]
    import math
    return [float(a), float(d), float(n), float(lc), float(p),
            float(math.log(scale)), 0.0, float(q)]


def run_fold(fold: int, protocol_sha: str):
    results = {}
    for normalization, trend in ARMS:
        view = data.nz_train_view(fold, weights=None, floor_mode="uniform")
        result = fit_null_arm(view, "NZ", normalization, trend,
                              archived_start=archived_start(fold))
        if normalization == "plane":
            result = add_attenuation_profiles(result)
        payload = strip_private(result)
        payload.update(
            schema="pathway4_nz_fit_v1",
            fold=fold,
            case=f"NZ_fold_{fold}",
            source="experiments/pathway4_confirmatory_transfer/run_nz.py",
            source_sha256=C.sha256(Path(__file__)),
            protocol_sha256=protocol_sha,
            created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        )
        path = C.OUT / "fits" / f"nz_fold_{fold}_{normalization}_{trend}.json"
        C.write_json(path, payload)
        results[(normalization, trend)] = dict(
            nll=payload["training_nll"],
            parameters=payload["parameters"],
            attenuation=(payload.get("attenuation_profiles", {}) or {}).get(
                "refined_ann2_wc", {}).get("eta"),
            wall_seconds=payload["wall_seconds"])
        print("nz", fold, normalization, trend, payload["training_nll"],
              results[(normalization, trend)]["attenuation"], flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fold", type=int, default=None)
    parser.add_argument("--protocol", type=Path, default=C.PROTOCOL)
    args = parser.parse_args()
    if not args.protocol.exists():
        raise SystemExit("frozen protocol missing; run freeze_protocol.py first")
    protocol_sha = C.sha256(args.protocol)
    if args.protocol.with_suffix(".sha256").exists():
        pinned = args.protocol.with_suffix(".sha256").read_text().strip().split()[0]
        if pinned != protocol_sha:
            raise SystemExit("protocol sha256 pin does not match the protocol file")
    folds = [args.fold] if args.fold is not None else [0, 1, 2]
    for fold in folds:
        run_fold(fold, protocol_sha)


if __name__ == "__main__":
    main()
