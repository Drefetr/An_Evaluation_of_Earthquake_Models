"""Stage P4.3: conditional branching calibration of interior-scale EP+.

The frozen California EP+ states are the plane-normalised interior fits in
``sigma0_relaxation.json``.  Only their training-side fields (parameters,
declustered background weights, training NLL) enter the simulation.  Each
origin receives 999 conditional branching paths; the observed vector plus the
  simulated vectors form the symmetric pool used by the archived eight-
coordinate quadratic and Fisher-type omnibus statistics.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C, data
from experiments.pathway4_confirmatory_transfer.forecast import (
    COORDINATES, diagnostics8, simulate_future)
from experiments.pathway4_confirmatory_transfer.model import EPModel
from experiments.pathway4_confirmatory_transfer.scoring import (
    pooled_continuous_tests as pooled_tests)

N_SIM = 999
CHUNK = 25
WORKERS = 6

ARCHIVED = {
    0: dict(OC=dict(count=0.002, min_rank=0.070, quadratic=0.004, fisher=0.001),
            EP=dict(count=0.002, min_rank=0.070, quadratic=0.004, fisher=0.002)),
    1: dict(OC=dict(count=0.594, min_rank=0.075, quadratic=0.003, fisher=0.004),
            EP=dict(count=0.698, min_rank=0.075, quadratic=0.005, fisher=0.006)),
    2: dict(OC=dict(count=0.056, min_rank=0.069, quadratic=0.007, fisher=0.012),
            EP=dict(count=0.036, min_rank=0.069, quadratic=0.009, fisher=0.008)),
}


def frozen_state(fold: int):
    d = C.read_json(C.CA_INTERIOR)
    row = next(r for r in d["rows"]
               if r["case"] == f"california_fold_{fold}"
               and r["normalization"] == "plane")
    return dict(
        parameters=[float(v) for v in row["parameters"][:8]],
        background_weights=[float(v) for v in row["background_weights"]],
        training_nll=float(row["training_nll"]),
        declustering=row["declustering"],
        source="validation/live_results/track_b_controls_20261112/"
               "epplus_ablation/sigma0_relaxation.json",
        source_sha256=C.sha256(C.CA_INTERIOR),
        sigma0_km=float(row["sigma0"]),
        alpha_s=float(row["alpha_s"]),
        q=float(row["q"]),
        archived_test_joint_score=float(row["test_joint_score"]),
        archived_common_mark_score=float(row["common_mark_score"]),
    )


def _model_for(fold: int):
    state = frozen_state(fold)
    train = data.ca_train_view(fold, weights=state["background_weights"],
                               floor_mode="uniform")
    test = data.ca_test_view(fold, train.background)
    return state, test, EPModel(test, "plane")


def _simulate_chunk(args):
    fold, seeds = args
    state, test, model = _model_for(fold)
    x = np.asarray(state["parameters"], dtype=float)
    out = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        events = simulate_future(model, x, rng)
        diag = diagnostics8(model, x, events)
        out.append(dict(seed=int(seed), count=int(len(events)),
                        diagnostics=[float(v) for v in diag]))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--simulations", type=int, default=N_SIM)
    parser.add_argument("--fold", type=int, default=None)
    parser.add_argument("--output", type=Path, default=C.OUT / "california")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summary = {}
    folds = [args.fold] if args.fold is not None else [0, 1, 2]
    for fold in folds:
        state, test, model = _model_for(fold)
        x = np.asarray(state["parameters"], dtype=float)
        observed_events = np.c_[test.event_time, test.event_excess, test.event_xy]
        observed = diagnostics8(model, x, observed_events)
        observed_count = int(len(observed_events))
        # model validation against the archived interior test score
        null = model.scores(x)
        mark = float(len(test.event_excess) * math.log(test.beta) -
                     test.beta * test.event_excess.sum())
        model_test_joint = float(null["ground_joint"] + mark)
        master = 20261116 + fold * 1000
        seeds = list(range(master, master + args.simulations))
        chunks = [seeds[i:i + CHUNK] for i in range(0, len(seeds), CHUNK)]
        rows = []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for part in pool.map(_simulate_chunk,
                                 [(fold, chunk) for chunk in chunks]):
                rows.extend(part)
        rows.sort(key=lambda r: r["seed"])
        if len(rows) != args.simulations:
            raise RuntimeError("simulation count mismatch")
        counts = np.array([r["count"] for r in rows], dtype=int)
        sims = np.array([r["diagnostics"] for r in rows], dtype=float)
        lower = float(np.count_nonzero(counts <= observed_count) / len(counts))
        upper = float(np.count_nonzero(counts >= observed_count) / len(counts))
        pool = np.vstack([observed[None, :], sims])
        pooled = pooled_tests(pool)
        result = dict(
            schema="pathway4_ca_conditional_calibration_v1",
            fold=fold, origin_year=("2011", "2016", "2021")[fold],
            n_test=observed_count,
            frozen_state=state,
            model_test_joint=model_test_joint,
            model_test_joint_delta=model_test_joint -
            state["archived_test_joint_score"],
            observed=dict(count=observed_count,
                          diagnostics=[float(v) for v in observed]),
            simulated=dict(
                n=len(rows), seeds=[master, master + args.simulations - 1],
                count_mean=float(counts.mean()),
                count_sd=float(counts.std(ddof=1)),
                count_q025=float(np.percentile(counts, 2.5)),
                count_q975=float(np.percentile(counts, 97.5)),
                diagnostics_mean=[float(v) for v in sims.mean(axis=0)],
                diagnostics_sd=[float(v) for v in sims.std(axis=0, ddof=1)],
            ),
            conditional_count=dict(
                observed=observed_count,
                lower_inclusive=lower,
                upper_inclusive=upper,
                two_sided_inclusive=min(1.0, 2.0 * min(lower, upper)),
            ),
            pooled=pooled,
            archived_reference=ARCHIVED[fold],
            coordinates=list(COORDINATES),
        )
        C.write_json(args.output / f"ca_fold_{fold}_calibration.json", result)
        summary[fold] = dict(
            n_test=observed_count,
            count_two_sided=result["conditional_count"]["two_sided_inclusive"],
            quadratic=pooled["quadratic"]["pooled_upper_inclusive_p"],
            fisher=pooled["fisher"]["pooled_upper_inclusive_p"],
            gap_ks_observed=float(observed[2]),
            spatial_ks_observed=float(observed[4]),
            model_test_joint_delta=result["model_test_joint_delta"],
        )
        print("fold", fold, summary[fold], flush=True)
    merged = {}
    for fold in range(3):
        path = args.output / f"ca_fold_{fold}_calibration.json"
        if not path.exists():
            continue
        result = C.read_json(path)
        pooled = result["pooled"]
        merged[fold] = dict(
            n_test=result["n_test"],
            count_two_sided=result["conditional_count"]["two_sided_inclusive"],
            quadratic=pooled["quadratic"]["pooled_upper_inclusive_p"],
            fisher=pooled["fisher"]["pooled_upper_inclusive_p"],
            gap_ks_observed=float(result["observed"]["diagnostics"][2]),
            spatial_ks_observed=float(result["observed"]["diagnostics"][4]),
            model_test_joint_delta=result["model_test_joint_delta"],
        )
    if len(merged) == 3:
        C.write_json(args.output / "summary.json",
                     dict(schema="pathway4_ca_conditional_summary_v1",
                          simulations=args.simulations,
                          coordinates=list(COORDINATES),
                          archived_source="paper/source/chapters/"
                                          "12_s05_completed.tex",
                          folds=merged))


if __name__ == "__main__":
    main()
