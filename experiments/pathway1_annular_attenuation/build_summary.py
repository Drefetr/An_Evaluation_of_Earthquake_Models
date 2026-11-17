"""Assemble the top-level Pathway 1 summary.json from stage authorities."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "validation/live_results/pathway1_annular_20261116"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    stage11_path = RESULTS / "stage_p11_null_profiles.json"
    stage12_path = RESULTS / "stage_p12_joint_optimization.json"
    synth_path = RESULTS / "synthetic/summary.json"
    audit_path = RESULTS / "independent_audit.json"
    stage11 = read(stage11_path)
    stage12 = read(stage12_path) if stage12_path.exists() else None
    synth = read(synth_path) if synth_path.exists() else None
    audit = read(audit_path) if audit_path.exists() else None
    headline = []
    for row in stage11["rows"]:
        if row["ell0_km"] == 15.0 and row["psi_days"] == 5.0:
            headline.append({
                "case": row["case"], "baseline": row["baseline"], "kernel": row["kernel"],
                "scaled": row["scaled"], "event_sum": row["event_sum"],
                "exposure_integral": row["exposure_integral"],
                "score_slope_total": row["score_slope_total"],
                "score_slope_immigrant": row["score_slope_immigrant"],
                "eta_hat_train_total": row["eta_hat_train_total"],
                "delta_train_max_total": row["delta_train_max_total"],
                "delta_test_total": row["delta_test_total"],
            })
    positive_total = [r for r in stage11["rows"] if r["score_slope_total"] > 0]
    positive_imm = [r for r in stage11["rows"] if r["score_slope_immigrant"] > 0]
    payload = {
        "schema": "pathway1_annular_summary_v1",
        "passed": bool(audit and audit.get("passed")),
        "created_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "question": "Do annular or trigger-core-shielded attenuation kernels flip the California null score slope positive and improve held-out log score over interior-scale EP+?",
        "source_sha256": {
            "experiments/pathway1_annular_attenuation/annular.py": sha(ROOT / "experiments/pathway1_annular_attenuation/annular.py"),
            "experiments/pathway1_annular_attenuation/annular_native.cpp": sha(ROOT / "experiments/pathway1_annular_attenuation/annular_native.cpp"),
            "experiments/pathway1_annular_attenuation/run_diagnostics.py": sha(ROOT / "experiments/pathway1_annular_attenuation/run_diagnostics.py"),
            "experiments/pathway1_annular_attenuation/run_joint.py": sha(ROOT / "experiments/pathway1_annular_attenuation/run_joint.py"),
            "experiments/pathway1_annular_attenuation/run_synthetic.py": sha(ROOT / "experiments/pathway1_annular_attenuation/run_synthetic.py"),
            "experiments/etas_inhibition_benchmark/run_frozen_20261111.py": sha(ROOT / "experiments/etas_inhibition_benchmark/run_frozen_20261111.py"),
        },
        "stage_p11": {
            "artifact": str(stage11_path.relative_to(ROOT).as_posix()),
            "sha256": sha(stage11_path),
            "n_rows": stage11["n_rows"],
            "positive_total_slope_rows": stage11["positive_total_slope_rows"],
            "positive_immigrant_slope_rows": stage11["positive_immigrant_slope_rows"],
            "interior_positive_total_slope_rows": sum(
                1 for r in stage11["rows"] if r["baseline"] == "interior" and r["score_slope_total"] > 0),
            "best_total_slope": {k: stage11["best_total_slope"][k] for k in (
                "case", "baseline", "kernel", "scaled", "ell0_km", "psi_days",
                "score_slope_total", "score_slope_immigrant",
                "eta_hat_train_total", "delta_train_max_total", "delta_test_total")},
            "best_immigrant_slope": {k: stage11["best_immigrant_slope"][k] for k in (
                "case", "baseline", "kernel", "scaled", "ell0_km", "psi_days",
                "score_slope_total", "score_slope_immigrant",
                "eta_hat_train_immigrant", "delta_train_max_immigrant", "delta_test_immigrant")},
            "max_positive_train_delta_total": max(
                [r["delta_train_max_total"] for r in positive_total], default=0.0),
            "max_positive_train_delta_immigrant": max(
                [r["delta_train_max_immigrant"] for r in positive_imm], default=0.0),
            "positive_total_rows": [
                {k: r[k] for k in ("case", "baseline", "kernel", "scaled", "ell0_km",
                                   "psi_days", "score_slope_total", "score_slope_immigrant",
                                   "eta_hat_train_total", "delta_train_max_total",
                                   "delta_test_total")}
                for r in sorted(positive_total, key=lambda r: -r["score_slope_total"])
            ],
            "positive_immigrant_rows": [
                {k: r[k] for k in ("case", "baseline", "kernel", "scaled", "ell0_km",
                                   "psi_days", "score_slope_total", "score_slope_immigrant",
                                   "eta_hat_train_immigrant", "delta_train_max_immigrant",
                                   "delta_test_immigrant")}
                for r in sorted(positive_imm, key=lambda r: -r["score_slope_immigrant"])
            ],
            "headline_ell15_psi5": headline,
            "integration_checks": {
                "n": len(stage11.get("integration_checks", [])),
                "max_abs_slope_difference_vs_primary": max(
                    [abs(c["slope_difference_vs_primary"]) for c in stage11.get("integration_checks", [])
                     if "slope_difference_vs_primary" in c], default=0.0),
                "median_abs_slope_difference_vs_primary": (
                    sorted([abs(c["slope_difference_vs_primary"]) for c in stage11.get("integration_checks", [])
                            if "slope_difference_vs_primary" in c])[len(stage11.get("integration_checks", [])) // 2]
                    if stage11.get("integration_checks") else 0.0),
            },
        },
        "stage_p12": None if stage12 is None else {
            "artifact": str(stage12_path.relative_to(ROOT).as_posix()),
            "sha256": sha(stage12_path),
            "n_rows": stage12["n_rows"],
            "n_selected_positive_eta": stage12["n_selected_positive_eta"],
            "n_exact_nested_null": stage12["n_exact_nested_null"],
            "by_kernel": stage12["by_kernel"],
            "eta_zero_nuisance_refits": stage12.get("eta_zero_nuisance_refits", []),
        },
        "stage_p13": None if synth is None else {
            "artifact": str(synth_path.relative_to(ROOT).as_posix()),
            "sha256": sha(synth_path),
            "N": synth["N"],
            "achieved_thinning": synth["achieved_thinning"],
            "achieved_test_events": synth["achieved_test_events"],
            "mono_gain": synth["mono_gain"],
            "ann2_gain": synth["ann2_gain"],
            "oracle_gain": synth["oracle_gain"],
            "ann2_recovery_fraction": synth["ann2_recovery_fraction"],
            "ann2_beats_mono": synth["ann2_beats_mono"],
            "ann2_beats_null": synth["ann2_beats_null"],
            "mono_beats_null": synth["mono_beats_null"],
        },
        "independent_audit": None if audit is None else {
            "artifact": str(audit_path.relative_to(ROOT).as_posix()),
            "sha256": sha(audit_path),
            "passed": audit.get("passed"),
            "components": {k: audit[k].get("passed") for k in (
                "integrity", "kernels", "objective_gradients", "slopes",
                "profiles", "joint", "synthetic") if k in audit},
            "max_objective_gradient_relative_error": max(
                (x for r in audit.get("objective_gradients", {}).get("checks", [])
                 for x in r.get("errors", {}).values()), default=None),
            "max_recomputed_slope_relative_error": audit.get("slopes", {}).get("max_slope_rel"),
            "synthetic_fast_vs_frozen_joint_delta": audit.get("synthetic", {}).get("fast_minus_frozen_abs"),
        },
        "interpretation": {
            "interior_baseline": "No positive total-intensity null slope anywhere in the interior grid; annuli reduce the negative slope magnitude but do not reverse it.",
            "bound_2km_comparator": "Positive total slopes are confined to the bound-pinned ann2 unscaled ell0=5 km corner, with profile gains below 0.04 nats; this is a numerical sign reversal, not a detectable improvement.",
            "joint_optimization": "See stage_p12 for selected eta and held-out gains.",
            "synthetic_bank": "The ann2 shadow is detectable when the law is known, but the fitted ann2 estimator does not recover the oracle gain at about 95 test events.",
        },
    }
    out = RESULTS / "summary.json"
    out.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
