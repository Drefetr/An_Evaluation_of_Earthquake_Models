"""Independent audit of the 14 November 2026 forensic remediation package.

This script does not import the producer modules.  It recomputes every
reported identity from the written JSON, checks the root-finding residuals and
per-event arithmetic, and verifies that the sealed pre-change snapshot is
byte-for-byte intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "validation/forensic_prechange_snapshot_20261114.json"


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=ROOT / "validation/live_results/forensic_remediation_20261114")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    out = args.input.resolve()
    checks = []
    failures = []

    def check(name, condition, detail=None):
        checks.append(dict(name=name, passed=bool(condition), detail=detail))
        if not condition:
            failures.append(dict(name=name, detail=detail))

    # 0. Snapshot integrity.
    snapshot = read(SNAPSHOT)
    mismatched = [rec["path"] for rec in snapshot["files"]
                  if not (ROOT / rec["path"]).exists()
                  or sha(ROOT / rec["path"]) != rec["sha256"]]
    check("sealed_snapshot_file_count", snapshot["file_count"] >= 345,
          snapshot["file_count"])
    check("sealed_snapshot_unchanged", not mismatched, mismatched[:10])

    # 1. New Zealand MDE arithmetic.
    nz = read(out / "nz_trend_controls.json")
    for name, record in nz["controls_rebuilt"].items():
        for days, block in record["block_days"].items():
            check(f"nz_{name}_{days}_mde_identity",
                  close(block["mde95_total_nats"], 1.96 * block["se_total_nats"], 1e-10),
                  block)
            check(f"nz_{name}_{days}_z_identity",
                  close(block["z"], record["total"] / block["se_total_nats"], 1e-10),
                  block)
            check(f"nz_{name}_{days}_standardized_ratio",
                  close(block["standardized_ratio"],
                        abs(record["total"]) / (1.96 * block["se_total_nats"]), 1e-10))
            check(f"nz_{name}_{days}_per_event_identity",
                  close(block["mde95_nats_per_event"],
                        1.96 * block["se_total_nats"] / 612.0, 1e-12))
    fixed = nz["controls_rebuilt"]["fixed_null_d"]["block_days"]
    check("nz_fixed_null_se90", close(fixed["90"]["se_total_nats"], 1.3955978289659632, 1e-9))
    check("nz_fixed_null_mde90", close(fixed["90"]["mde95_total_nats"], 2.7353717447732877, 1e-9))
    check("nz_fixed_null_z", close(fixed["90"]["z"], -3.5868091555013515, 1e-8))
    check("nz_fixed_null_ratio", close(fixed["90"]["standardized_ratio"], 1.830004671174159, 1e-9))
    grid = nz["full_grid"]
    check("nz_full_grid_cells", grid["cells_per_fold"] == 18, grid["cells_per_fold"])
    check("nz_full_grid_zero_total", close(grid["pooled"]["zero_d"]["total_heldout"],
                                           -11.43117364480338, 5e-4))
    check("nz_full_grid_fixed_total", close(grid["pooled"]["fixed_null_d"]["total_heldout"],
                                            -5.005783652743219, 5e-4))
    check("nz_full_grid_mde_identity",
          all(close(v["mde95_total_nats"], 1.96 * v["se_total_nats"], 1e-10)
              for control in grid["pooled"].values()
              for v in control["block_days"].values()))

    # 2. California eta profiles.
    eta = read(out / "eta_profiles.json")
    for case, record in eta["cases"].items():
        for scale, block in record["fixed_backbone"].items():
            for label, target in eta["thresholds"].items():
                if label.startswith("note"):
                    continue
                root = block["roots"][label]
                check(f"eta_{case}_{scale}_{label}_newton_residual",
                      abs(root["residual"]) < 1e-6, root["residual"])
                check(f"eta_{case}_{scale}_{label}_brentq_residual",
                      abs(root["brentq_residual"]) < 1e-6, root["brentq_residual"])
                check(f"eta_{case}_{scale}_{label}_newton_brentq",
                      close(root["eta"], root["brentq_eta"], 1e-9))
        prof = record["profiled_s8_scale"]
        check(f"eta_{case}_profile_baseline",
              close(prof["curve"][0]["train_loglik_gain"], 0.0, 1e-8),
              prof["curve"][0])
        eta04 = next(r for r in prof["curve"] if abs(r["eta"] - 0.4) < 1e-12)
        check(f"eta_{case}_corrected_test_gain",
              close(prof["s8_eta_test_gain"],
                    prof["null_test_nll"] - prof["s8_eta_test_nll"], 1e-9))
        check(f"eta_{case}_test_gain_finite",
              math.isfinite(prof["s8_eta_test_gain"]))
        check(f"eta_{case}_profile_root_residual",
              prof["eta95_upper"]["residual"] is not None
              and abs(prof["eta95_upper"]["residual"]) < 1e-6,
              prof["eta95_upper"])
        fine = eta["scaled_ell15_psi5_profile"][case]["eta95_upper"]
        check(f"eta_{case}_fine_profile_residual",
              abs(fine["residual"]) < 1e-12, fine)
    # expected fixed-backbone roots for the S8 scale pair (15/5).
    expected = {
        "california_fold_0": (1.1414237998275211e-4, 8.166486670108451e-5),
        "california_fold_1": (1.1175376694945352e-4, 7.989817840660443e-5),
        "california_fold_2": (9.096374377353929e-5, 6.495661438470821e-5),
    }
    for case, (two, one) in expected.items():
        block = eta["cases"][case]["fixed_backbone"]["ell15_psi5"]["roots"]
        check(f"eta_{case}_expected_two_sided",
              close(block["two_sided_95"]["eta"], two, 1e-9), block["two_sided_95"])
        check(f"eta_{case}_expected_one_sided",
              close(block["one_sided_95"]["eta"], one, 1e-9), block["one_sided_95"])
    for case, values in (("california_fold_0", 8.887321114474671e-4),
                         ("california_fold_1", 8.533172340182197e-4),
                         ("california_fold_2", 5.86875467260335e-4)):
        check(f"eta_{case}_unscaled_root",
              close(eta["unscaled_ell15_psi5"][case]["eta95_upper"]["eta"], values, 1e-9))
    check("eta_ridgecrest_ell", close(eta["ridgecrest_ell_km"], 532.220083850363, 0.001),
          eta["ridgecrest_ell_km"])
    f0 = eta["cases"]["california_fold_0"]["fixed_backbone"]["ell15_psi5"]
    check("eta_epicentral_event_sum", close(f0["event_sum_G"], 75313.90275560762, 1e-6))
    check("eta_epicentral_exposure", close(f0["exposure_integral_lambda0_G"], 59415.47941914608, 1e-6))
    check("eta_epicentral_slope", close(f0["training_score_slope_at_zero"], -15898.423336461536, 1e-6))

    # 3. S8 oracle sign and partial oracles.
    s8 = read(out / "s8_oracle.json")
    check("s8_sign_mean", close(s8["sign_correction"]["mean_nats"], 3.571425664485332, 1e-9))
    check("s8_sign_other_mean", close(s8["sign_correction"]["other_seed_mean"], -0.2025960225016182, 1e-9))
    check("s8_sign_median", close(s8["sign_correction"]["median"], -1.6831136976599055, 1e-9))
    check("s8_seed_410840", close(s8["sign_correction"]["seed_410840"]["contrast_value"],
                                  75.27783771723705, 1e-9))
    check("s8_partial_b_mean", close(s8["partial_oracle_b"]["gain_vs_joint_null"]["mean"],
                                     2.823657383237122, 1e-9))
    check("s8_partial_c_mean", close(s8["partial_oracle_c"]["loss_vs_true"]["mean"],
                                     -6.513221037516632, 1e-9))
    check("s8_partial_c_median", close(s8["partial_oracle_c"]["loss_vs_true"]["median"],
                                       -3.1306456698728766, 1e-9))
    check("s8_partial_b_multistart",
          all(len(r["multi_start_nll"]) == 5 for r in s8["partial_oracle_b"]["rows"]))
    check("s8_closure", abs(s8["closure"]["identity_residual"]) < 1e-9)

    # 4. Japan arithmetic and annual blocks.
    japan = read(out / "japan_mde.json")
    repaired = japan["repaired"]
    check("japan_per_fold_per_event_identity",
          close(repaired["per_fold"]["mde95_nats_per_event"],
                repaired["three_fold_sum"]["mde95_nats_per_event"], 1e-12))
    check("japan_per_event_factor",
          close(repaired["three_fold_sum"]["mde95_nats_per_event"],
                1.96 * japan["archived"]["three_fold_sum"]["se_total_nats"] / 1277.0, 1e-12))
    check("japan_delta", close(repaired["three_fold_sum"]["required_rate_perturbation"],
                               0.2740020993815968, 1e-9))
    check("japan_annual_se", close(japan["annual_pooled"]["se_total_nats"],
                                   28.82987572487176, 1e-9))
    check("japan_annual_mde", close(repaired["annual_nine_blocks"]["mde95_total_nats"],
                                    1.96 * japan["annual_pooled"]["se_total_nats"], 1e-9))
    check("japan_nine_blocks", len(japan["annual_blocks"]) == 9, len(japan["annual_blocks"]))
    check("japan_fold_windows", japan["fold_windows"] == {
        "0": "2016-2018", "1": "2019-2021", "2": "2022-2024"})

    # 5. Clean ablation and relaxed totals.
    abl = read(out / "epplus_ablation.json")["clean_ablation"]
    check("ablation_closure", abs(abl["closure_residual"]) < 1e-8, abl["closure_residual"])
    check("ablation_declustering", close(abl["shapley"]["declustering"],
                                         27.604694408005646, 1e-9))
    check("ablation_scaling", close(abl["shapley"]["scaling"], 31.669094480073188, 1e-9))
    check("ablation_a3_lower_than_frozen",
          abl["totals"]["A3"] < abl["frozen_a8_weight_reference"]["totals"]["A3"] - 1.0)
    check("ablation_a4_lower_than_frozen",
          abl["totals"]["A4"] < abl["frozen_a8_weight_reference"]["totals"]["A4"] - 1.0)
    # Self-declustered weights must differ from the accepted A8 weights.
    accepted = read(ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/"
                           "california_fold_0/result.json")["background_weights"]
    for case in ("california_fold_0", "california_fold_1", "california_fold_2"):
        row = abl["rows"]["A8"][case]
        check(f"ablation_A8_{case}_own_weights",
              not np.allclose(np.asarray(row["background_weights"]),
                              np.asarray(read(ROOT / "validation/live_results/"
                                                   "etas_inhibition_benchmark_interior_20261112" /
                                              case / "result.json")["background_weights"]),
                              rtol=0.0, atol=1e-12))
    totals = read(out / "epplus_sigma0_totals.json")
    check("relaxed_plane_total", close(totals["relaxed"]["plane"]["total_gain"],
                                       77.0557339839778, 1e-9))
    check("relaxed_rect_total", close(totals["relaxed"]["rect"]["total_gain"],
                                      77.05874171993219, 1e-9))
    check("relaxed_not_double_counted",
          not close(totals["archived_double_counted_total"],
                    totals["relaxed"]["plane"]["total_gain"], 1e-6))

    # 5b. Relaxed-sigma0 inhibited benchmark.
    relaxed_path = out / "epplus_relaxed_inhibited.json"
    if relaxed_path.exists():
        relaxed = read(relaxed_path)
        check("relaxed_inhibited_all_eta_zero", relaxed["all_selected_eta_zero"] is True)
        check("relaxed_inhibited_interior_sigma",
              all(r["selected"]["sigma0_km"] > 0.05 for r in relaxed["rows"]))

    # 6. Tightened Pinsker bound.
    vis = read(out / "mathematics_visibility.json")["finite_horizon_visibility"]
    check("pinsker_original_C", close(vis["C_T_195_days_squared"], 2866250.949488237, 1e-6))
    check("pinsker_tight_C", close(vis["C_T_tight_days_squared"], 0.10424014954814537, 1e-9))
    check("pinsker_reduction", close(vis["C_T_reduction_factor"],
                                      vis["C_T_195_days_squared"] / vis["C_T_tight_days_squared"], 1e-9))
    check("pinsker_tight_K", close(vis["K_T_tight"],
                                    vis["K_T"] * vis["C_T_tight_days_squared"]
                                    / vis["C_T_195_days_squared"], 1e-9))
    check("pinsker_tight_threshold", close(vis["eta_tight_at_which_clipped_bound_equals_one"],
                                            12.250403506767263, 1e-8))
    check("pinsker_tight_nonvacuous", vis["tight_bound_for_eta_1_65"] < 1.0)
    check("pinsker_original_vacuous", vis["bound_for_eta_1_65"] == 1.0)

    # 7. Date synchronization and custody.
    for relative in ("paper/source/main.tex", "companion/guide_content.json",
                     "website/document_metadata.json", "website/findings.html",
                     "README.md", "REVIEWER_START_HERE.md"):
        body = (ROOT / relative).read_text(encoding="utf-8", errors="replace")
        check(f"date_{relative}", "14 November 2026" in body)
    check("date_website_metadata", read(ROOT / "website/document_metadata.json").get(
        "edition_date") == "14 November 2026")
    check("custody_quantiles_chapter",
          (ROOT / "paper/source/chapters/13_s04b_joint_quantiles.tex").exists())

    receipt = dict(
        schema="forensic_remediation_independent_audit_v1",
        passed=not failures,
        source="experiments/methodological_audit/audit_forensic_remediation_20261114.py",
        input=str(out.relative_to(ROOT)).replace("\\", "/"),
        input_hashes={p.name: sha(p) for p in sorted(out.glob("*.json"))},
        checks=checks, failures=failures,
        check_count=len(checks), failure_count=len(failures),
        completeness_limit=("Recomputes reported algebraic and numerical identities from the "
                            "written JSON, checks the sealed snapshot and date/custody fields, "
                            "and does not re-run the producer optimizers."))
    destination = args.output or (out / "independent_audit.json")
    destination.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(passed=receipt["passed"], checks=len(checks),
                          failures=failures[:5]), indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
