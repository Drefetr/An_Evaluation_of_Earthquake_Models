"""Post-process P1.2 records for eta=0 nuisance-refit states.

The primary P1.2 selection retains the exact nested eta=0 candidate, so every
row is an exact-null contrast. Several bound-pinned jobs also found an eta=0
backbone with a lower training NLL (the 2 km bound is relaxed). Those states
are not attenuation fits, but they are legitimate null-model nuisance refits;
this script evaluates their held-out score separately and attaches a
transparent supplemental section.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway1_annular_attenuation import annular as A  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path,
                        default=ROOT / "validation/live_results/pathway1_annular_20261116")
    parser.add_argument("--test-seeds", nargs="+", type=int, default=[20261250, 20261251])
    parser.add_argument("--test-power", type=int, default=16)
    args = parser.parse_args()
    path = args.results / "stage_p12_joint_optimization.json"
    stage = read(path)
    supplemental = []
    for row in stage["rows"]:
        best = min(row["records"], key=lambda r: r["nll"])
        if best["eta"] >= 1e-7:
            continue
        gain = float(row["null_training_nll"] - best["nll"])
        if gain <= 1e-6:
            continue
        native = A.new_native(threads=2)
        bundle = A.build_models(row["case"], row["baseline"], native,
                                train_power=14, test_power=args.test_power,
                                train_seed=20261111, test_seed=args.test_seeds[0])
        model = bundle["test_model"]
        x0 = bundle["x0"]
        x = np.asarray(best["parameters"], dtype=float)
        gains = []
        null_joints = []
        for seed in args.test_seeds:
            model.node_setup(x0, power=args.test_power, seed=seed)
            model.freeze_nodes()
            null = model.objective(x0, False, True)
            inhibited = model.objective(x, True, True)
            gains.append(float(null["nll"] - inhibited["nll"]))
            null_joints.append(float(-null["nll"] + A.mark_logscore(row["case"])))
        supplemental.append(dict(
            case=row["case"], baseline=row["baseline"], kernel=row["kernel"],
            training_nll_exact_null=float(row["null_training_nll"]),
            training_nll_eta_zero_refit=float(best["nll"]),
            training_gain=float(gain),
            selected_parameters=[float(v) for v in x],
            selected_eta=float(x[8]),
            selected_ell0_km=float(math.exp(x[9])),
            selected_psi_days=float(math.exp(x[10])),
            selected_sigma0_km=float(math.exp(x[5])),
            heldout_gain_mean=float(np.mean(gains)),
            heldout_gain_standard_error=float(np.std(gains, ddof=1) / math.sqrt(len(gains)))
            if len(gains) > 1 else 0.0,
            heldout_gain_values=[float(v) for v in gains],
            null_test_joint_mean=float(np.mean(null_joints)),
            test_seeds=[int(s) for s in args.test_seeds],
            interpretation="eta=0 nuisance refit; the attenuation contrast is identically zero",
        ))
        print("nuisance", row["case"], row["baseline"], row["kernel"], gain, supplemental[-1]["heldout_gain_mean"], flush=True)
    stage["eta_zero_nuisance_refits"] = supplemental
    stage["eta_zero_nuisance_refit_note"] = (
        "The primary selected state is the exact nested eta=0 null in every row. "
        "These supplemental rows report the best fitted eta=0 backbone when it "
        "improved the training NLL; they are nuisance relaxations, not annular "
        "attenuation effects, and their attenuation contrast is zero."
    )
    path.write_text(json.dumps(stage, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(n=len(supplemental), total_training_gain=float(sum(r["training_gain"] for r in supplemental)),
                          total_heldout_gain=float(sum(r["heldout_gain_mean"] for r in supplemental))), indent=2))


if __name__ == "__main__":
    main()
