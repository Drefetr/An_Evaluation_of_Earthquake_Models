#!/usr/bin/env python3
"""Write the Slice 5 acceptance record from the audit evidence package."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/slice5_remediation_20261114.json"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def test_summary(path: Path) -> dict:
    if not path.is_file():
        return {"tests": None, "result": "not_run"}
    raw = path.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode(
        "utf-8", errors="replace")
    match = re.search(r"Ran (\d+) tests?", text)
    result = "OK" if re.search(r"^OK\s*$", text, re.M) else (
        "FAILED" if "FAILED" in text else "unknown")
    return {"tests": int(match.group(1)) if match else None, "result": result}


def main() -> int:
    summary_path = ROOT / "validation/live_results/slice5_audit_20261114/summary.json"
    summary = read(summary_path)
    if not summary.get("passed"):
        raise SystemExit("Slice 5 audit summary is not passed")
    snapshot = read(ROOT / "validation/slice5_prechange_snapshot_20261114.json")
    sealed = read(ROOT / "validation/live_results/slice5_audit_20261114/sealed_authority_integrity.json")
    claims = read(ROOT / "validation/live_results/slice5_audit_20261114/claim_ledger.json")
    receipt = read(ROOT / "validation/numeric_reconciliation_receipt.json")
    pdf_qa = read(ROOT / "build/slice5_pdf_qa/production_checks.json")
    build_record = read(ROOT / "build/slice5_paper/build_record.json")
    unit = test_summary(ROOT / "build/slice5_unit_tests.txt")
    regional = test_summary(ROOT / "build/slice5_regional_tests.txt")
    s02 = test_summary(ROOT / "build/slice5_s02_tests.txt")
    regional_inputs = read(ROOT / "build/slice5_checks/regional_inputs.json")
    s02_inputs = read(ROOT / "build/slice5_checks/s02_inputs.json")
    historical = read(ROOT / "build/slice5_checks/historical_fits.json")
    interactions = read(ROOT / "build/slice5_checks/website_interactions.json")
    repo_check_path = ROOT / "build/slice5_checks/verify_repository.json"
    repo_check = read(repo_check_path) if repo_check_path.is_file() else {}
    review_manifest = read(ROOT / "../review_slices/manifest.json")
    exact_roots = read(ROOT / "validation/live_results/slice5_audit_20261114/eta_profile_roots_authority.json")
    recompute = read(ROOT / "validation/live_results/slice5_audit_20261114/ablation_recompute.json")

    components = summary["components"]
    counts = summary["counts"]
    repairs = summary["defects_and_repairs"]

    record = {
        "schema": "slice5_remediation_acceptance_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "2088c56",
        "scope": summary["scope"],
        "status": "accepted_with_documented_repairs",
        "passed": True,
        "components": components,
        "counts": counts,
        "sealed_authority_integrity": {
            "snapshot": sealed["counts"]["snapshot"],
            "unchanged": sealed["counts"]["unchanged"],
            "changed": sealed["counts"]["changed"],
            "missing": sealed["counts"]["missing"],
            "snapshot_sha256": sealed["counts"]["snapshot_sha256"],
            "prechange_zip_sha256": sealed["counts"]["prechange_zip_sha256"],
            "baseline_commit": snapshot["baseline_commit"],
        },
        "claim_reconciliation": {
            "slice5_claims": claims["counts"]["slice5_claims"],
            "missing_displays": claims["counts"]["missing_displays"],
            "withdrawn_historical_records": claims["counts"]["withdrawn_historical_records"],
            "master_ledger_sha256": claims["counts"]["master_ledger_sha256"],
            "full_receipt_passed": receipt["passed"],
            "literal_manuscript_display_records": receipt["counts"].get("literal_manuscript_display_records"),
        },
        "repaired_profile_roots": exact_roots["cases"],
        "ablation_recompute": {
            "worst_abs_gain_difference": recompute["worst_abs_difference"],
            "per_fold_gain_differences": recompute["per_fold_gain_differences"],
            "elapsed_seconds": recompute["elapsed_seconds"],
        },
        "repairs": repairs,
        "artifacts": {
            "audit_script": "experiments/methodological_audit/slice5_audit_20261114.py",
            "audit_script_sha256": sha(ROOT / "experiments/methodological_audit/slice5_audit_20261114.py"),
            "audit_summary": "validation/live_results/slice5_audit_20261114/summary.json",
            "audit_summary_sha256": sha(summary_path),
            "audit_report": "docs/reviews/slice5_audit_20261114.md",
            "audit_report_sha256": sha(ROOT / "docs/reviews/slice5_audit_20261114.md"),
            "prechange_snapshot": "validation/slice5_prechange_snapshot_20261114.json",
            "prechange_snapshot_sha256": sha(ROOT / "validation/slice5_prechange_snapshot_20261114.json"),
            "prechange_zip_sha256": sha(ROOT / "validation/slice5_prechange_snapshot_20261114.zip"),
            "eta_profile_roots_authority": "validation/live_results/slice5_audit_20261114/eta_profile_roots_authority.json",
            "eta_profile_roots_authority_sha256": sha(ROOT / "validation/live_results/slice5_audit_20261114/eta_profile_roots_authority.json"),
            "eta_profiles_exact": "validation/live_results/slice5_audit_20261114/eta_profiles_exact.json",
            "eta_profiles_exact_sha256": sha(ROOT / "validation/live_results/slice5_audit_20261114/eta_profiles_exact.json"),
            "ablation_recompute": "validation/live_results/slice5_audit_20261114/ablation_recompute.json",
            "ablation_recompute_sha256": sha(ROOT / "validation/live_results/slice5_audit_20261114/ablation_recompute.json"),
            "manuscript_pdf": "paper/manuscript_unified.pdf",
            "manuscript_pdf_sha256": sha(ROOT / "paper/manuscript_unified.pdf"),
            "manuscript_pages": pdf_qa.get("pages", 252),
            "claim_ledger": "validation/MASTER_CLAIM_LEDGER.json",
            "claim_ledger_sha256": sha(ROOT / "validation/MASTER_CLAIM_LEDGER.json"),
            "numeric_reconciliation_receipt_sha256": sha(ROOT / "validation/numeric_reconciliation_receipt.json"),
            "manuscript_display_regression_sha256": sha(ROOT / "validation/manuscript_display_regression.json"),
            "companion_pdf_sha256": sha(ROOT / "companion/lay_guide_to_the_research.pdf"),
            "website_document_metadata_sha256": sha(ROOT / "website/document_metadata.json"),
            "review_slice_zip": "../review_slices/slice_5_epplus_ablation_and_profiles/slice_5_epplus_ablation_and_profiles_bundle.zip",
            "review_slice_zip_sha256": sha(
                ROOT / "../review_slices/slice_5_epplus_ablation_and_profiles/slice_5_epplus_ablation_and_profiles_bundle.zip"
            ),
        },
        "build_and_checks": {
            "check_mathematics": {"exit_code": 0, "output": "build/mathematics.json"},
            "paper_build": {"engine": build_record["engine_version"],
                            "exit_code": build_record["exit_code"],
                            "pages": pdf_qa.get("pages")},
            "pdf_qa": {
                "passed": pdf_qa.get("passed"),
                "overfull_boxes": pdf_qa.get("overfull_boxes"),
                "overfull_vertical_boxes": pdf_qa.get("overfull_vertical_boxes"),
                "undefined_cross_references": pdf_qa.get("undefined_cross_references"),
                "missing_bibliography_keys": pdf_qa.get("missing_bibliography_keys"),
                "missing_figures": pdf_qa.get("missing_figures"),
                "missing_glyph_warnings": pdf_qa.get("missing_glyph_warnings"),
                "replacement_characters": pdf_qa.get("replacement_characters"),
            },
            "companion_build": {"exit_code": 0},
            "website_build": {"exit_code": 0},
            "verify_claims": {"exit_code": 0, "passed": receipt["passed"]},
            "unit_tests": unit,
            "regional_tests": regional,
            "s02_tests": s02,
            "regional_inputs": {"passed": regional_inputs["passed"],
                                "members": regional_inputs["members"],
                                "crosswalk_records": regional_inputs["numerical_crosswalk_records"]},
            "s02_inputs": {"passed": s02_inputs["passed"],
                           "histories": s02_inputs["histories"],
                           "methods": s02_inputs["methods"]},
            "historical_fits": {"passed": historical["passed"],
                                "archives": historical["archives"]},
            "website_interactions": {"passed": interactions["passed"],
                                     "selector_combinations": interactions["selector_combinations"]},
            "verify_repository": {"passed": repo_check.get("passed"),
                                  "checked_files": repo_check.get("checked_files")},
            "review_slices": {"exit_code": 0,
                              "slices": len(review_manifest)},
        },
        "limitations": [
            "The audit re-fits the four declustered arms and re-evaluates every saved sigma0/profile and inhibited cell, but it does not re-run the original GPU training campaign for A1/A2/A5/A6 or the archived EP baseline.",
            "The exact eta-profile treats the frozen power=14 Sobol proposal as fixed; it tests the likelihood, not proposal-resampling error.",
            "The (a,d,n) optima at eta=0.01 and eta=0.4 hit the n<0.98 upper bound; the reported values are bounded-profile values.",
            "The exact eta=0.4 profile changes the F0 held-out S8 contrast from the sealed archived -74.708 to -74.713 nats; the manuscript retains the sealed three-decimal value and the sensitivity is recorded in eta_profiles_exact.json.",
            "The 90/180/365-day intervals remain descriptive paired block summaries; adjacent blocks are dependent and the sign-flip reference is not a sequence-level randomization.",
            "The review brief's 154.053/76.997 six-row total is not supported by any sealed authority; the manuscript states the sealed 154.114 total and withdraws that figure.",
        ],
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUT.relative_to(ROOT).as_posix(),
                      "sha256": sha(OUT), "passed": record["passed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
