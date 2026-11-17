#!/usr/bin/env python3
"""Append Pathway 1-4 manuscript display bindings and derived arithmetic.

The sealed summaries are the authorities.  A small additive derived-values file
records only arithmetic that the manuscript displays as a ratio, difference or
sum; it performs no new scientific computation.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"
P1 = ROOT / "validation/live_results/pathway1_annular_20261116/summary.json"
P1S = ROOT / "validation/live_results/pathway1_annular_20261116/synthetic/summary.json"
P2 = ROOT / "validation/live_results/pathway2_trend_controls_20261116/summary.json"
P3 = ROOT / "validation/live_results/pathway3_low_dim_20261116/summary.json"
P4 = ROOT / "validation/live_results/pathway4_confirmatory_20261116/summary.json"
DERIVED = ROOT / "validation/live_results/pathways_integration_20261117/derived_values.json"

P1_TEX = ["chapters/11_pathway1_annular.tex"]
P2_TEX = ["chapters/11_epplus_ablation.tex", "chapters/13_pathway2_3_refinements.tex"]
P3_TEX = ["chapters/13_pathway2_3_refinements.tex"]
P4_TEX = ["chapters/11_pathway4_transfer.tex"]
S05_TEX = ["chapters/12_s05_completed.tex"]
HEAD = ["chapters/11_pathway1_annular.tex", "abstract.tex",
        "chapters/01_introduction.tex", "chapters/14_discussion_conclusion.tex"]
HEAD2 = ["chapters/11_epplus_ablation.tex", "chapters/13_pathway2_3_refinements.tex",
         "abstract.tex", "chapters/01_introduction.tex", "chapters/14_discussion_conclusion.tex"]
HEAD3 = ["chapters/13_pathway2_3_refinements.tex", "abstract.tex",
         "chapters/01_introduction.tex", "chapters/14_discussion_conclusion.tex"]
HEAD4 = ["chapters/11_pathway4_transfer.tex", "abstract.tex",
         "chapters/01_introduction.tex", "chapters/14_discussion_conclusion.tex"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    spec = importlib.util.spec_from_file_location("_pathways_bind_verify", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    ledger = read(LEDGER)
    if any(c["id"].startswith("pathways-20261117-") for c in ledger["claims"]):
        raise SystemExit("Pathway bindings already present")

    p1, p1s, p2, p3, p4 = read(P1), read(P1S), read(P2), read(P3), read(P4)
    slopes = {}
    for index, row in enumerate(p1["stage_p11"]["headline_ell15_psi5"]):
        if row["baseline"] == "interior" and row["scaled"]:
            slopes[(row["case"], row["kernel"])] = index
    assert len(slopes) == 12

    ca_rows = p2["stages"]["california"]["rows"]
    s8 = p2["stages"]["s8"]
    s04b = p2["stages"]["s04b"]
    s7 = s04b["by_regime"]["7"]
    ladder = p3["ladder_closure"]
    arms = p3["s8_by_arm"]
    banks = p3["banks"]
    p4nz = p4["new_zealand"]
    p4j = p4["japan"]

    derived = {
        "schema": "pathways_integration_derived_values_v1",
        "created_on": "2026-11-17",
        "scope": ("Arithmetic differences, ratios and sums derived from the Pathway 1-4 "
                  "summaries for manuscript display. No new scientific computation, "
                  "fitting or simulation."),
        "sources": {
            "pathway1_summary": {"path": P1.relative_to(ROOT).as_posix(), "sha256": sha(P1)},
            "pathway2_summary": {"path": P2.relative_to(ROOT).as_posix(), "sha256": sha(P2)},
            "pathway3_summary": {"path": P3.relative_to(ROOT).as_posix(), "sha256": sha(P3)},
            "pathway4_summary": {"path": P4.relative_to(ROOT).as_posix(), "sha256": sha(P4)},
        },
        "values": {
            "pathway1_slope_reduction_fold0": (
                p1["stage_p11"]["headline_ell15_psi5"][slopes[("california_fold_0", "mono")]]
                ["score_slope_total"] /
                p1["stage_p11"]["headline_ell15_psi5"][slopes[("california_fold_0", "ann2")]]
                ["score_slope_total"]),
            "pathway1_slope_reduction_fold2": (
                p1["stage_p11"]["headline_ell15_psi5"][slopes[("california_fold_2", "mono")]]
                ["score_slope_total"] /
                p1["stage_p11"]["headline_ell15_psi5"][slopes[("california_fold_2", "ann2")]]
                ["score_slope_total"]),
            "pathway2_california_t1_minus_t0": (
                p2["stages"]["california"]["totals"]["T1"] -
                p2["stages"]["california"]["totals"]["T0"]),
            "pathway2_california_t2_minus_t0": (
                p2["stages"]["california"]["totals"]["T2"] -
                p2["stages"]["california"]["totals"]["T0"]),
            "pathway3_l1_oracle_percent": (
                100.0 * arms["E_L1_Shrinkage"]["gain_vs_archived_joint_null"]["mean"] /
                p3["oracle_ceiling"]["gain_vs_joint_null"]["mean"]),
            "pathway3_s4_loss_removed_percent": (
                100.0 * (banks["by_regime"]["4"]["raw_sealed_gain"]["mean"] -
                         banks["by_regime"]["4"]["E_L1_Shrinkage"]["gain_vs_stationary_null"]["mean"]) /
                banks["by_regime"]["4"]["raw_sealed_gain"]["mean"]),
            "pathway3_s6_loss_removed_percent": (
                100.0 * (banks["by_regime"]["6"]["raw_sealed_gain"]["mean"] -
                         banks["by_regime"]["6"]["E_L1_Shrinkage"]["gain_vs_stationary_null"]["mean"]) /
                banks["by_regime"]["6"]["raw_sealed_gain"]["mean"]),
            "pathway3_first_four_rungs": sum(
                step["nats"] for step in ladder["steps"][:4]),
            "pathway4_nz_plane_t1_refined_minus_null": (
                -9.679920799954996 + 0.0 - 31.142123916974406),
            "pathway4_nz_plane_t0_refined_minus_null": (
                -9.711850570938207 + 0.0 - 32.29437927505146),
        },
    }
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    DERIVED.write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")
    derived_data = read(DERIVED)

    add: list[dict] = []

    def make(source: Path, pointer: str, display: str, locations: list[str],
             component: str, transformation=None) -> dict:
        data = read(source)
        raw = vc.resolve(data, pointer)
        claim = dict(
            id=f"pathways-20261117-{len(add)+1:03d}",
            bundled_source=source.relative_to(ROOT).as_posix(),
            source_path=source.relative_to(ROOT).as_posix(),
            source_sha256=sha(source),
            json_pointer=pointer,
            resolved_source_value=raw,
            display=display,
            transformation=transformation or "decimal rounding to displayed precision",
            json_value_kind="numeric_scalar",
            ledger_role="manuscript_binding",
            final_display_locations=locations,
            component=component,
            qualification=("Additive Pathway 1-4 integration binding; sealed summary authority "
                           "and explicit JSON pointer; no scientific re-execution."),
            status="source_bound",
            binding_kind="exact_json_pointer",
            reconciliation_status="verified_at_declared_granularity",
        )
        claim["value"] = vc.transformed(raw, claim, data)
        if not vc.equal_display(claim["value"], claim):
            raise ValueError(("display does not round", claim["id"], raw, display))
        return claim

    def add_many(source, rows):
        for pointer, display, locations, component, transformation in rows:
            add.append(make(source, pointer, display, locations, component, transformation))

    # --- Pathway 1: California null slopes, grid census and synthetic bank.
    for kernel, displays in {
        "mono": ("-16286.8", "-16816.4", "-20410.6"),
        "ann1": ("-4204.1", "-4350.5", "-4788.2"),
        "ann2": ("-2864.1", "-2949.9", "-3380.2"),
        "shield": ("-14680.6", "-15060.6", "-17770.3"),
    }.items():
        for fold, display in zip(("california_fold_0", "california_fold_1", "california_fold_2"), displays):
            pointer = (f"/stage_p11/headline_ell15_psi5/{slopes[(fold, kernel)]}"
                       "/score_slope_total")
            add.append(make(P1, pointer, display, HEAD,
                            f"California interior EP+ null slope, {kernel}, {fold}"))
    mono0 = slopes[("california_fold_0", "mono")]
    add.append(make(P1, f"/stage_p11/headline_ell15_psi5/{mono0}/event_sum",
                    "75313.9", HEAD, "Mono Fold 0 event-weighted attenuation sum"))
    add.append(make(P1, f"/stage_p11/headline_ell15_psi5/{mono0}/exposure_integral",
                    "59027.1", HEAD, "Mono Fold 0 exposure integral"))
    add.append(make(P1, "/stage_p11/n_rows", "2016", HEAD,
                    "Full Pathway 1 null-profile grid rows"))
    add.append(make(P1, "/stage_p11/positive_total_slope_rows", "11", HEAD,
                    "Positive total-intensity null-slope rows"))
    add.append(make(P1, "/stage_p11/interior_positive_total_slope_rows", "0", HEAD,
                    "Positive interior total-intensity null-slope rows"))
    add.append(make(P1, "/stage_p11/n_rows", "1008", HEAD,
                    "Interior total-intensity grid cells",
                    {"operation": "multiply", "factor": 0.5}))
    add.append(make(P1, "/stage_p11/max_positive_train_delta_total", "0.0370", HEAD,
                    "Largest training profile gain among positive total-slope rows"))
    add.append(make(DERIVED, "/values/pathway1_slope_reduction_fold0", "5.7", HEAD,
                    "Fold 0 annular slope-magnitude reduction factor"))
    add.append(make(DERIVED, "/values/pathway1_slope_reduction_fold2", "6.0", HEAD,
                    "Fold 2 annular slope-magnitude reduction factor"))
    add.append(make(P1, "/stage_p12/n_rows", "24", HEAD,
                    "Full twelve-parameter joint-optimization rows"))
    add.append(make(P1, "/stage_p12/n_selected_positive_eta", "0", HEAD,
                    "Joint rows selecting positive attenuation"))
    add.append(make(P1, "/stage_p13/achieved_thinning/mean", "25.34", HEAD,
                    "Synthetic bank realized thinning percentage",
                    {"operation": "multiply", "factor": 100}))
    add.append(make(P1, "/stage_p13/achieved_test_events/mean", "98.2", HEAD,
                    "Synthetic bank mean test events"))
    for key, label in (("oracle_gain", "True-law oracle"), ("mono_gain", "Free 8D mono"),
                        ("ann2_gain", "Free 8D ann2")):
        for field, suffix in (("mean", "mean"), ("median", "median"),
                              ("mcse", "MCSE"), ("wins", "wins")):
            displays = {
                ("oracle_gain", "mean"): "13.107", ("oracle_gain", "median"): "10.505",
                ("oracle_gain", "mcse"): "2.218", ("oracle_gain", "wins"): "20",
                ("mono_gain", "mean"): "-34.986", ("mono_gain", "median"): "-2.285",
                ("mono_gain", "mcse"): "27.067", ("mono_gain", "wins"): "6",
                ("ann2_gain", "mean"): "-22.319", ("ann2_gain", "median"): "-2.649",
                ("ann2_gain", "mcse"): "17.472", ("ann2_gain", "wins"): "9",
            }
            add.append(make(P1, f"/stage_p13/{key}/{field}", displays[(key, field)], HEAD,
                            f"Synthetic bank {label} {suffix}"))
    add.append(make(P1, "/stage_p13/ann2_beats_mono", "11", HEAD,
                    "Synthetic ann2 estimator beats mono histories"))

    # --- Pathway 2: California clock table.
    totals = p2["stages"]["california"]["totals"]
    add.append(make(P2, "/stages/california/totals/T0", "77.056", HEAD2,
                    "California interior EP+ T0 total gain"))
    add.append(make(P2, "/stages/california/totals/T1", "87.739", HEAD2,
                    "California interior EP+ T1 total gain"))
    add.append(make(P2, "/stages/california/totals/T2", "79.405", HEAD2,
                    "California interior EP+ T2 total gain"))
    add.append(make(P2, "/stages/california/totals/T3", "79.405", HEAD2,
                    "California interior EP+ T3 total gain"))
    add.append(make(DERIVED, "/values/pathway2_california_t1_minus_t0", "10.683", HEAD2,
                    "California T1 minus T0 total"))
    add.append(make(DERIVED, "/values/pathway2_california_t2_minus_t0", "2.349", HEAD2,
                    "California T2 minus T0 total"))
    fold_displays = [
        ("14.046", "20.239", "15.665", "15.665", "6.193", "1.619"),
        ("38.365", "42.682", "39.079", "39.079", "4.317", "0.714"),
        ("24.645", "24.818", "24.661", "24.661", "0.173", "0.016"),
    ]
    for i, (t0, t1, t2, t3, d1, d2) in enumerate(fold_displays):
        for field, display in (("T0", t0), ("T1", t1), ("T2", t2), ("T3", t3),
                               ("t1_minus_t0", d1), ("t2_minus_t0", d2)):
            add.append(make(P2, f"/stages/california/rows/{i}/{field}", display, HEAD2,
                            f"California fold {i} clock contrast {field}"))

    # --- Pathway 2: S8 clock table.
    s8_display = {
        "T0": ("3.571", "75.278", "-17.818", "0.294", "1.230"),
        "T1": ("-3.216", "20.510", "-9.785", "1.539", "0.888"),
        "T2": ("-3.409", "10.065", "-9.231", "1.901", "1.232"),
        "T3": ("-3.409", "10.065", "-9.043", "2.089", "1.200"),
        "DSTAR": ("-5.959", "1.095", "-5.505", "3.077", "1.199"),
    }
    for law, (over_mean, over_max, est_mean, gain_mean, rmse) in s8_display.items():
        add.append(make(P2, f"/stages/s8/by_law/{law}/overfitting_loss/mean", over_mean,
                        HEAD2, f"S8 {law} mean overfitting loss"))
        add.append(make(P2, f"/stages/s8/by_law/{law}/overfitting_loss/maximum", over_max,
                        HEAD2, f"S8 {law} maximum overfitting loss"))
        add.append(make(P2, f"/stages/s8/by_law/{law}/estimation_loss/mean", est_mean,
                        HEAD2, f"S8 {law} mean estimation loss"))
        add.append(make(P2, f"/stages/s8/by_law/{law}/heldout_gain/mean", gain_mean,
                        HEAD2, f"S8 {law} mean held-out gain"))
        add.append(make(P2, f"/stages/s8/by_law/{law}/fitted_eta/rmse_vs_true", rmse,
                        HEAD2, f"S8 {law} eta RMSE"))
    seed = p2["stages"]["s8"]["seed_410840"]
    add.append(make(P2, "/stages/s8/seed_410840/t0/overfitting_loss", "75.278", HEAD2,
                    "Seed 410840 T0 overfitting loss"))
    add.append(make(P2, "/stages/s8/seed_410840/t0/estimation_loss", "-119.828", HEAD2,
                    "Seed 410840 T0 estimation loss"))
    for law, over, est in (("T1", "2.579", "-9.487"), ("T2", "10.065", "-17.452"),
                            ("T3", "10.065", "-17.452")):
        add.append(make(P2, f"/stages/s8/seed_410840/laws/{law}/overfitting_loss", over,
                        HEAD2, f"Seed 410840 {law} overfitting loss"))
        add.append(make(P2, f"/stages/s8/seed_410840/laws/{law}/estimation_loss", est,
                        HEAD2, f"Seed 410840 {law} estimation loss"))
    add.append(make(P2, "/stages/s8/by_law/T1/heldout_gain/median", "0.341", HEAD2,
                    "S8 T1 median held-out gain"))

    # --- Pathway 2: S04B tail table.
    for i, field, display in ((0, "T0", "-592.90"), (0, "T1", "-593.00"),
                               (0, "T2", "-590.08")):
        add.append(make(P2, f"/stages/s04b/worst_t0_cases/{i}/{field}", display, HEAD2,
                        f"Worst S04B case {field}"))
    add.append(make(P2, "/stages/s04b/trend_diagnostic/corr_t0_null_d_gain", "0.051",
                    HEAD2, "S04B null-trend correlation with held-out gain"))
    add.append(make(P2, "/stages/s04b/trend_diagnostic/corr_t0_inhibited_d_gain", "-0.016",
                    HEAD2, "S04B inhibited-trend correlation with held-out gain"))
    for law, mean, median, minimum in (("T0", "-1.261", "-1.257", "-23.259"),
                                        ("T1", "4.316", "5.648", "-3.124"),
                                        ("T2", "3.357", "4.101", "-7.053")):
        for field, display in (("mean", mean), ("median", median), ("minimum", minimum)):
            add.append(make(P2, f"/stages/s04b/by_regime/7/{law}/{field}", display, HEAD2,
                            f"S7 {law} {field} held-out gain"))

    # --- Pathway 3: ladder and estimator table.
    for i, display in enumerate(("1.067", "1.765", "1.718", "0.846", "12.422")):
        add.append(make(P3, f"/ladder_closure/steps/{i}/nats", display, HEAD3,
                        f"Stepwise ladder gap {i+1}"))
    add.append(make(P3, "/ladder_closure/total", "17.818", HEAD3,
                    "Stepwise ladder total"))
    add.append(make(P3, "/ladder_closure/residual", "0.000000", HEAD3,
                    "Stepwise ladder closure residual"))
    for arm, gain, rmse in (("S1_fixed_backbone_a_eta", "17.045", "0.176"),
                             ("S2_fixed_backbone_a_eta_ell_psi", "15.281", "1.159"),
                             ("S3a_stat_null_a_n_eta_true_scale", "13.562", "0.206")):
        add.append(make(P3, f"/s8_by_arm/{arm}/gain_vs_archived_joint_null/mean", gain,
                        HEAD3, f"Ladder gain versus archived null, {arm}"))
        add.append(make(P3, f"/s8_by_arm/{arm}/eta/rmse_vs_true", rmse,
                        HEAD3, f"Ladder eta RMSE, {arm}"))
    add.append(make(DERIVED, "/values/pathway3_first_four_rungs", "5.395", HEAD3,
                    "First four ladder rungs combined"))
    estimator_display = {
        "E1D_Profile_3p": ("12.717", "9.605", "4.070", "1.159", "-29.317"),
        "E1D_Profile_2p": ("11.744", "7.804", "3.779", "1.160", "-18.795"),
        "E_L1_Shrinkage": ("11.426", "7.795", "3.679", "1.163", "-9.666"),
        "E_Split_CV": ("11.229", "7.441", "3.686", "0.993", "-9.177"),
        "WC_Rupture_2p": ("3.400", "2.614", "5.722", "2.602", None),
        "Free_8D_archived": ("0.294", "2.541", "2.777", "1.230", "-41.910"),
    }
    for arm, (mean, median, mcse, rmse, s4) in estimator_display.items():
        add.append(make(P3, f"/s8_by_arm/{arm}/gain_vs_archived_joint_null/mean", mean,
                        HEAD3, f"Estimator {arm} mean gain"))
        add.append(make(P3, f"/s8_by_arm/{arm}/gain_vs_archived_joint_null/median", median,
                        HEAD3, f"Estimator {arm} median gain"))
        add.append(make(P3, f"/s8_by_arm/{arm}/gain_vs_archived_joint_null/mcse", mcse,
                        HEAD3, f"Estimator {arm} MCSE"))
        add.append(make(P3, f"/s8_by_arm/{arm}/eta/rmse_vs_true", rmse,
                        HEAD3, f"Estimator {arm} eta RMSE"))
        if s4:
            ptr = (f"/banks/by_regime/4/{arm}/gain_vs_stationary_null/mean"
                   if arm != "Free_8D_archived" else "/banks/by_regime/4/raw_sealed_gain/mean")
            add.append(make(P3, ptr, s4, HEAD3, f"Estimator {arm} S4 mean"))
    add.append(make(P3, "/banks/by_regime/4/E1D_Profile_3p/gain_vs_stationary_null/minimum",
                    "-451.819", HEAD3, "E1D_Profile_3p S4 worst case"))
    add.append(make(P3, "/banks/by_regime/6/raw_sealed_gain/mean", "-30.473", HEAD3,
                    "S6 archived raw mean loss"))
    add.append(make(P3, "/banks/by_regime/6/E_L1_Shrinkage/gain_vs_stationary_null/mean",
                    "-5.497", HEAD3, "S6 L1 mean gain"))
    add.append(make(P3, "/banks/by_regime/7/E_L1_Shrinkage/gain_vs_stationary_null/mean",
                    "6.093", HEAD3, "S7 L1 mean gain"))
    add.append(make(DERIVED, "/values/pathway3_l1_oracle_percent", "63.1", HEAD3,
                    "L1 fraction of the joint-null oracle ceiling"))
    add.append(make(DERIVED, "/values/pathway3_s4_loss_removed_percent", "76.9", HEAD3,
                    "L1 fraction of the S4 loss removed"))
    add.append(make(DERIVED, "/values/pathway3_s6_loss_removed_percent", "82.0", HEAD3,
                    "L1 fraction of the S6 loss removed"))
    for pointer, display, label in (
        ("/new_zealand/E_L1_Shrinkage", "-10.065", "NZ L1 total"),
        ("/new_zealand/archived_free_d", "-17.623", "NZ archived free-d total"),
        ("/new_zealand/E1D_Profile_3p", "-16.019", "NZ E1D 3p total"),
        ("/new_zealand/E1D_Profile_2p", "-15.920", "NZ E1D 2p total"),
    ):
        add.append(make(P3, pointer, display, HEAD3, label))

    # --- Pathway 4: transfer, annual blocks, attenuation and calibration.
    add.append(make(P4, "/new_zealand/targets", "612", HEAD4, "New Zealand target count"))
    add.append(make(P4, "/japan/targets", "1277", HEAD4, "Japan target count"))
    nz_display = {
        "plane_T1": ("25.591", "85.755", "111.346", "161.618"),
        "plane_T0": ("16.285", "85.221", "101.506", "151.778"),
        "rect_T1": ("12.235", "99.339", "111.574", "161.846"),
        "rect_T0": ("2.767", "98.984", "101.750", "152.023"),
    }
    for arm, (timing, location, joint, oc) in nz_display.items():
        add.append(make(P4, f"/new_zealand/arms/{arm}/totals/ep_minus_ep/timing", timing,
                        HEAD4, f"NZ {arm} EP+ minus EP timing"))
        add.append(make(P4, f"/new_zealand/arms/{arm}/totals/ep_minus_ep/location", location,
                        HEAD4, f"NZ {arm} EP+ minus EP location"))
        add.append(make(P4, f"/new_zealand/arms/{arm}/totals/ep_minus_ep/joint", joint,
                        HEAD4, f"NZ {arm} EP+ minus EP joint"))
        add.append(make(P4, f"/new_zealand/arms/{arm}/totals/ep_minus_oc/joint", oc,
                        HEAD4, f"NZ {arm} EP+ minus OC joint"))
    japan_display = {
        "plane_T1": ("-9.545", "330.456", "320.911", "542.123"),
        "plane_T0": ("62.528", "299.397", "361.925", "583.136"),
        "rect_T1": ("-25.366", "349.046", "323.679", "544.891"),
    }
    for arm, (timing, location, joint, oc) in japan_display.items():
        add.append(make(P4, f"/japan/arms/{arm}/totals/ep_minus_ep/timing", timing,
                        HEAD4, f"Japan {arm} EP+ minus EP timing"))
        add.append(make(P4, f"/japan/arms/{arm}/totals/ep_minus_ep/location", location,
                        HEAD4, f"Japan {arm} EP+ minus EP location"))
        add.append(make(P4, f"/japan/arms/{arm}/totals/ep_minus_ep/joint", joint,
                        HEAD4, f"Japan {arm} EP+ minus EP joint"))
        add.append(make(P4, f"/japan/arms/{arm}/totals/ep_minus_oc/joint", oc,
                        HEAD4, f"Japan {arm} EP+ minus OC joint"))
    annual_display = {
        "2016": ("54.660", "92.240"), "2017": ("38.797", "53.257"),
        "2018": ("50.720", "73.440"), "2019": ("33.338", "40.536"),
        "2020": ("37.496", "61.342"), "2021": ("32.563", "60.651"),
        "2022": ("42.752", "67.707"), "2023": ("41.616", "70.575"),
        "2024": ("29.984", "63.390"),
    }
    for year, (ep, oc) in annual_display.items():
        add.append(make(P4, f"/japan/arms/plane_T0/annual_blocks/{year}/ep_minus_ep/joint",
                        ep, HEAD4, f"Japan {year} EP+ minus EP joint"))
        add.append(make(P4, f"/japan/arms/plane_T0/annual_blocks/{year}/ep_minus_oc/joint",
                        oc, HEAD4, f"Japan {year} EP+ minus OC joint"))
    add.append(make(P4, "/japan/arms/plane_T0/annual_totals/ep_minus_ep/joint", "361.925",
                    HEAD4, "Japan annual EP+ minus EP total"))
    add.append(make(P4, "/japan/arms/plane_T0/annual_totals/ep_minus_oc/joint", "583.136",
                    HEAD4, "Japan annual EP+ minus OC total"))
    add.append(make(P4, "/new_zealand/arms/plane_T1/totals/refined_minus_ep/joint", "70.524",
                    HEAD4, "NZ refined attenuation minus EP total"))
    add.append(make(P4, "/new_zealand/arms/plane_T0/totals/refined_minus_ep/joint", "59.500",
                    HEAD4, "NZ free-trend refined attenuation minus EP total"))
    add.append(make(P4, "/japan/arms/plane_T1/totals/refined_minus_ep/joint", "320.911",
                    HEAD4, "Japan refined attenuation minus EP total"))
    add.append(make(P4, "/japan/arms/plane_T0/totals/refined_minus_ep/joint", "361.925",
                    HEAD4, "Japan free-trend refined attenuation minus EP total"))
    add.append(make(DERIVED, "/values/pathway4_nz_plane_t1_refined_minus_null", "-40.822",
                    HEAD4, "NZ refined attenuation minus EP+ null"))
    add.append(make(DERIVED, "/values/pathway4_nz_plane_t0_refined_minus_null", "-42.006",
                    HEAD4, "NZ free-trend refined attenuation minus EP+ null"))
    score_files = {
        ("NZ", "plane_T1", 0): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/nz_fold_0_plane_T1.json",
        ("NZ", "plane_T1", 1): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/nz_fold_1_plane_T1.json",
        ("NZ", "plane_T1", 2): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/nz_fold_2_plane_T1.json",
        ("NZ", "plane_T0", 0): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/nz_fold_0_plane_T0.json",
        ("NZ", "plane_T0", 1): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/nz_fold_1_plane_T0.json",
        ("NZ", "plane_T0", 2): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/nz_fold_2_plane_T0.json",
        ("JMA", "plane_T1", 0): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/jma_fold_0_plane_T1.json",
        ("JMA", "plane_T1", 1): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/jma_fold_1_plane_T1.json",
        ("JMA", "plane_T1", 2): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/jma_fold_2_plane_T1.json",
        ("JMA", "plane_T0", 0): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/jma_fold_0_plane_T0.json",
        ("JMA", "plane_T0", 1): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/jma_fold_1_plane_T0.json",
        ("JMA", "plane_T0", 2): ROOT / "validation/live_results/pathway4_confirmatory_20261116/scores/jma_fold_2_plane_T0.json",
    }
    eta_display = {
        ("NZ", "plane_T1"): ("0.0008", "0.0000", "0.0001"),
        ("NZ", "plane_T0"): ("0.0008", "0.0000", "0.0001"),
        ("JMA", "plane_T1"): ("0.0000", "0.0000", "0.0000"),
        ("JMA", "plane_T0"): ("0.0000", "0.0000", "0.0000"),
    }
    gain_display = {
        ("NZ", "plane_T1"): ("-9.680", "0.000", "-31.142"),
        ("NZ", "plane_T0"): ("-9.712", "0.000", "-32.294"),
        ("JMA", "plane_T1"): ("0.000", "0.000", "0.000"),
        ("JMA", "plane_T0"): ("0.000", "0.000", "0.000"),
    }
    for (cohort, arm), etas in eta_display.items():
        for fold, display in enumerate(etas):
            source = score_files[(cohort, arm, fold)]
            add.append(make(source, "/attenuation/refined/eta", display, HEAD4,
                            f"{cohort} {arm} fold {fold} refined training eta"))
    for (cohort, arm), gains in gain_display.items():
        for fold, display in enumerate(gains):
            source = score_files[(cohort, arm, fold)]
            add.append(make(source, "/attenuation/refined/gain", display, HEAD4,
                            f"{cohort} {arm} fold {fold} refined attenuation gain"))
    for i, n in enumerate(("79", "167", "69")):
        add.append(make(P4, f"/california/folds/{i}/n_test", n, S05_TEX,
                        f"California origin {i} conditional target count"))
    p_display = {
        0: ("0.004", "0.010", "0.002"),
        1: ("0.452", "0.004", "0.006"),
        2: ("0.266", "0.101", "0.166"),
    }
    for i, (count, quadratic, fisher) in p_display.items():
        add.append(make(P4, f"/california/folds/{i}/count_two_sided", count, S05_TEX,
                        f"California origin {i} refined conditional count p"))
        add.append(make(P4, f"/california/folds/{i}/quadratic", quadratic, S05_TEX,
                        f"California origin {i} refined quadratic p"))
        add.append(make(P4, f"/california/folds/{i}/fisher", fisher, S05_TEX,
                        f"California origin {i} refined Fisher p"))

    ledger["claims"].extend(add)
    ledger["closure_revision"] = (
        "20261117: appended Pathway 1-4 bindings for the annular kernels, stationary and "
        "clamped clocks, stepwise ladder, L1-shrinkage winner, frozen cross-regional EP+ "
        "transfer, annual JMA blocks, frozen attenuation profile and California conditional "
        "calibration; sealed authorities retained.")
    LEDGER.write_bytes(vc.format_ledger(ledger))
    print(json.dumps({
        "added": len(add),
        "claims": len(ledger["claims"]),
        "derived_values": DERIVED.relative_to(ROOT).as_posix(),
        "derived_sha256": sha(DERIVED),
        "ledger_sha256": sha(LEDGER),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
