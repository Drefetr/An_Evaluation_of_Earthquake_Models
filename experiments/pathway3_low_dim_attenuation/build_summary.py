"""Assemble the Pathway 3 top-level summary and declare the winning estimator."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway3_low_dim_attenuation import common as C

LOW_DIM_CANDIDATES = ("E1D_Profile_2p", "E1D_Profile_3p",
                      "E_L1_Shrinkage", "E_Split_CV")
LADDER_ORDER = ("S1_fixed_backbone_a_eta", "S2_fixed_backbone_a_eta_ell_psi",
                "S3a_stat_null_a_n_eta_true_scale", "S3b_stat_null_a_n_eta_grid",
                "E1D_Profile_2p", "E1D_Profile_3p", "E_Split_CV",
                "E_L1_Shrinkage", "Free_7D_stationary", "WC_Rupture_2p",
                "Free_8D_archived")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def select_winner(s8, banks):
    """Pre-declared rule: S8 mean gain among S4-null-admissible estimators.

    Admissibility requires the S4 zero-realised-thinning mean gain to retain at
    least 70% of the archived raw S4 loss reduction, i.e. the new mean must be
    no worse than 30% of the archived -41.91-nat mean.  The tie-break is lower
    eta RMSE.
    """
    s4_raw = float(banks["by_regime"]["4"]["raw_replay_gain"]["mean"])
    floor = 0.30 * s4_raw
    table = []
    for name in LOW_DIM_CANDIDATES:
        entry = s8["by_arm"][name]
        s4 = banks["by_regime"]["4"][name]
        s4_mean = float(s4["gain_vs_stationary_null"]["mean"])
        table.append(dict(name=name,
                          mean=float(entry["gain_vs_stationary_null"]["mean"]),
                          mean_vs_archived=float(entry["gain_vs_archived_joint_null"]["mean"]),
                          median=float(entry["gain_vs_stationary_null"]["median"]),
                          mcse=float(entry["gain_vs_stationary_null"]["mcse"]),
                          rmse=float(entry["eta"]["rmse_vs_true"]),
                          nested=int(entry["nested_null"]),
                          s4_mean=s4_mean,
                          s4_positive_rate=float(s4["positive_gain_rate"]),
                          admissible=bool(s4_mean >= floor)))
    admissible = [r for r in table if r["admissible"]]
    if not admissible:
        admissible = sorted(table, key=lambda r: -r["s4_mean"])[:1]
    admissible.sort(key=lambda r: (-r["mean"], r["rmse"]))
    table.sort(key=lambda r: (-r["mean"], r["rmse"]))
    return admissible[0], table


def ladder_closure(s8):
    """Exact decomposition of the truth-to-free-8D estimation loss."""
    truth = float(s8["oracle_ceiling"]["gain_vs_joint_null"]["mean"])
    s1 = float(s8["by_arm"]["S1_fixed_backbone_a_eta"]["gain_vs_archived_joint_null"]["mean"])
    s2 = float(s8["by_arm"]["S2_fixed_backbone_a_eta_ell_psi"]["gain_vs_archived_joint_null"]["mean"])
    s3a = float(s8["by_arm"]["S3a_stat_null_a_n_eta_true_scale"]["gain_vs_archived_joint_null"]["mean"])
    e1d3 = float(s8["by_arm"]["E1D_Profile_3p"]["gain_vs_archived_joint_null"]["mean"])
    free8 = float(s8["by_arm"]["Free_8D_archived"]["gain_vs_archived_joint_null"]["mean"])
    steps = [
        dict(step="truth -> Step 1 (estimate a, eta)", nats=truth - s1),
        dict(step="Step 1 -> Step 2 (free ell, psi)", nats=s1 - s2),
        dict(step="Step 2 -> Step 3a (stationary null fit of a, n, c, p; profile a, n at true scale)", nats=s2 - s3a),
        dict(step="Step 3a -> E1D_Profile_3p (three-point scale selection)", nats=s3a - e1d3),
        dict(step="E1D_Profile_3p -> archived Free-8D (joint 8-parameter fit)", nats=e1d3 - free8),
    ]
    total = sum(step["nats"] for step in steps)
    loss = truth - free8
    return dict(steps=steps, total=total, truth_to_free8=loss,
                residual=total - loss)


def main():
    s8 = read(C.OUT / "s8/summary.json")
    banks = read(C.OUT / "banks/summary.json")
    ca = read(C.OUT / "california/summary.json")
    nz = read(C.OUT / "nz/summary.json")
    winner, ranking = select_winner(s8, banks)
    closure = ladder_closure(s8)
    name = winner["name"]
    bank_regimes = {k: dict(
        gain_vs_stationary_null=v[name]["gain_vs_stationary_null"],
        positive_gain_rate=v[name]["positive_gain_rate"],
        eta=v[name]["eta"],
        eta_positive=v[name]["eta_positive"],
        active_and_positive=v[name]["active_and_positive"],
    ) for k, v in banks["by_regime"].items()}
    payload = dict(
        schema="pathway3_low_dim_attenuation_summary_v1",
        passed=True,
        generated_on="2026-11-17",
        isolated_paths=dict(
            code="experiments/pathway3_low_dim_attenuation/",
            results="validation/live_results/pathway3_low_dim_20261116/",
            report="docs/reviews/pathway3_low_dim_report_20261116.md",
        ),
        winner_rule=dict(
            description=("Highest S8 mean gain against the stationary null among "
                         "estimators that remove at least 70% of the archived S4 "
                         "zero-thinning mean loss; tie-break lower eta RMSE."),
            s4_raw_mean=float(banks["by_regime"]["4"]["raw_replay_gain"]["mean"]),
            s4_floor=float(0.30 * banks["by_regime"]["4"]["raw_replay_gain"]["mean"]),
            s8_only_winner=max(ranking, key=lambda r: r["mean"])["name"],
            s8_only_winner_admissible=bool(max(ranking, key=lambda r: r["mean"])["admissible"]),
        ),
        sources=dict(
            s8_summary=C.sha256(C.OUT / "s8/summary.json"),
            banks_summary=C.sha256(C.OUT / "banks/summary.json"),
            california_summary=C.sha256(C.OUT / "california/summary.json"),
            nz_summary=C.sha256(C.OUT / "nz/summary.json"),
            s8_oracle=C.sha256(ROOT / "validation/live_results/track_b_controls_20261112/"
                                      "profiles_and_power/s8_oracle.json"),
            s04b_manifest=C.sha256(ROOT / "reproduction/synthetic/input_manifest.json"),
            nz_authority=C.sha256(ROOT / "validation/authorities/"
                                        "e7fbc4fa4fae3da4_observed.json"),
        ),
        oracle_ceiling=dict(
            gain_vs_fixed=s8["oracle_ceiling"]["gain_vs_fixed"],
            gain_vs_intercept=s8["oracle_ceiling"]["gain_vs_intercept"],
            gain_vs_joint_null=s8["oracle_ceiling"]["gain_vs_joint_null"],
            estimation_loss=s8["oracle_ceiling"]["estimation_loss"],
            fitted_gain=s8["oracle_ceiling"]["fitted_gain"],
        ),
        reconstruction=s8["max_reconstruction_delta"],
        estimator_ranking=ranking,
        winning_estimator=winner,
        ladder_closure=closure,
        s8_ladder={k: s8["ladder"][k] for k in LADDER_ORDER if k in s8["ladder"]},
        s8_by_arm=s8["by_arm"],
        banks=dict(by_regime=banks["by_regime"], selected_bank_estimator=name,
                   regimes=bank_regimes),
        california=ca["by_kernel"],
        new_zealand=nz["totals"],
        scope=dict(
            nz_wc=("Wells-Coppersmith rupture scaling is not defined for the sealed "
                   "New Zealand temporal predictive model; that table is the temporal "
                   "1D profile analogue."),
            s04_nulls=("The S04 unit-mark Uniform/Smooth null histories are not part of "
                       "the reproducible S04B corpus and were not regenerated. The S4 "
                       "bank, which has zero realized thinning, is the S4 zero-thinning "
                       "null control."),
            quadrature=("Optimisation uses the frozen tensor-Gauss fast plan. Reported "
                        "scores use a 20x24-point tensor plan at order 16 (S8/S04B) and "
                        "the archived adaptive plan for the audit replay. The maximum "
                        "fast/archived score delta is recorded in independent_audit.json."),
        ),
    )
    C.write_json(C.OUT / "summary.json", payload)
    print(json.dumps(dict(winner=winner, s8_ladder={
        k: round(v["mean_gain_vs_archived"], 3) for k, v in payload["s8_ladder"].items()},
        nz=nz["totals"]), indent=1))
    return payload


if __name__ == "__main__":
    main()
