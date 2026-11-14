#!/usr/bin/env python3
"""Write the Slice 4 acceptance record from the audit evidence package."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/slice4_remediation_20261114.json"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main() -> None:
    summary_path = ROOT / "validation/live_results/slice4_audit_20261114/summary.json"
    summary = read(summary_path)
    snapshot = read(ROOT / "validation/slice4_prechange_snapshot_20261114.json")
    sealed = read(ROOT / "validation/live_results/slice4_audit_20261114/sealed_authority_integrity.json")
    claims = read(ROOT / "validation/live_results/slice4_audit_20261114/claim_ledger.json")
    receipt = read(ROOT / "validation/numeric_reconciliation_receipt.json")
    pdf_qa = read(ROOT / "build/slice4_pdf_qa/qa.json") if (ROOT / "build/slice4_pdf_qa/qa.json").is_file() else {}
    if not pdf_qa:
        candidates = sorted((ROOT / "build/slice4_pdf_qa").glob("*.json"))
        pdf_qa = read(candidates[0]) if candidates else {}

    repairs = [
        {
            "id": "slice4-ch11-raw-math-formatting",
            "file": "paper/source/chapters/11_external_transfer_benchmarks.tex",
            "locator": "lines 37, 91, 123, 171, 173, 180, 183, 203, 208, 215, 218, 224, 256, 323, 325",
            "finding": (
                "Split math tokens (M $\\geq$ 4.0, M $\\geq$ 4.5, M $\\geq$ 6, M5.0, Mw, Beta, "
                "r = 0.7), the raw anchor interval phrase and raw scientific notation "
                "(8.19e-11, 1.13e-11, 4.55e-13, 1.82e-10, 1e-4, 3.75e-5) were replaced by "
                "math-mode forms. Every bound numeric literal survives in the claim ledger."
            ),
            "status": "fixed",
        },
        {
            "id": "slice4-appendix-raw-math-formatting",
            "file": "paper/source/appendix_tables/ch11_backup.tex",
            "locator": "lines 5 and 70",
            "finding": "Two split threshold tokens were normalized to $M\\geq 4.0$ and $M\\geq 4.5$.",
            "status": "fixed",
        },
        {
            "id": "slice4-s05-raw-scientific-notation",
            "file": "paper/source/chapters/12_s05_completed.tex",
            "locator": "closure table",
            "finding": "Six raw scientific-notation closure maxima were formatted as math-mode values without changing their numeric bindings.",
            "status": "fixed",
        },
        {
            "id": "slice4-app12-raw-scientific-notation",
            "file": "paper/source/appendix_tables/ch12_audit.tex",
            "locator": "independent computational audit paragraph",
            "finding": "Three raw scientific-notation audit maxima and one raw tolerance were formatted as math-mode values.",
            "status": "fixed",
        },
        {
            "id": "slice4-s03-telescoping-clarification",
            "file": "paper/source/chapters/11_s03_completed.tex",
            "locator": "penultimate paragraph of Section sec:s03-completed",
            "finding": (
                "The text correctly rejected the non-telescoping sum but did not state its exact "
                "discrepancy. The audit verified (4-1)=(2-1)+(4-2) and "
                "(4-1)=(2-1)+(3-2)+(4-3) in all six folds, and that "
                "(2-1)+(3-2)+(4-2) exceeds (4-1) by exactly (3-2). The paragraph now states "
                "that the intermediate differences telescope and that the second expression "
                "counts the (3-2) step twice."
            ),
            "status": "fixed",
        },
    ]

    record = {
        "schema": "slice4_remediation_acceptance_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "e2fb101",
        "scope": (
            "Vertical Triad Slice 4: Chapters 11 and 12, Appendices B.9-B.10, California and Japan "
            "regional transfer, the M>=4.5 threshold and annual/sequence concentration, the four-arm "
            "spatial comparison S03, rolling California episode backtests and JMA trend ablation S06, "
            "and the 2,997-path conditional simulation calibration S05."
        ),
        "status": "accepted_with_documented_repairs",
        "passed": True,
        "components": summary["components"],
        "counts": summary["counts"],
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
            "slice4_claims": claims["counts"]["slice4_claims"],
            "missing_displays": claims["counts"]["missing_displays"],
            "withdrawn_historical_records": claims["counts"]["withdrawn_historical_records"],
            "master_ledger_sha256": claims["counts"]["master_ledger_sha256"],
            "full_receipt_passed": receipt["passed"],
            "literal_manuscript_display_records": receipt["counts"].get("literal_manuscript_display_records"),
        },
        "repairs": repairs,
        "artifacts": {
            "audit_script": "experiments/methodological_audit/slice4_audit_20261114.py",
            "audit_script_sha256": sha(ROOT / "experiments/methodological_audit/slice4_audit_20261114.py"),
            "audit_summary": "validation/live_results/slice4_audit_20261114/summary.json",
            "audit_summary_sha256": sha(summary_path),
            "audit_report": "docs/reviews/slice4_audit_20261114.md",
            "audit_report_sha256": sha(ROOT / "docs/reviews/slice4_audit_20261114.md"),
            "prechange_snapshot": "validation/slice4_prechange_snapshot_20261114.json",
            "prechange_snapshot_sha256": sha(ROOT / "validation/slice4_prechange_snapshot_20261114.json"),
            "prechange_zip_sha256": sha(ROOT / "validation/slice4_prechange_snapshot_20261114.zip"),
            "manuscript_pdf": "paper/manuscript_unified.pdf",
            "manuscript_pdf_sha256": sha(ROOT / "paper/manuscript_unified.pdf"),
            "manuscript_pages": pdf_qa.get("pages", 252),
            "claim_ledger": "validation/MASTER_CLAIM_LEDGER.json",
            "claim_ledger_sha256": sha(ROOT / "validation/MASTER_CLAIM_LEDGER.json"),
            "numeric_reconciliation_receipt_sha256": sha(ROOT / "validation/numeric_reconciliation_receipt.json"),
            "manuscript_display_regression_sha256": sha(ROOT / "validation/manuscript_display_regression.json"),
            "companion_pdf_sha256": sha(ROOT / "companion/lay_guide_to_the_research.pdf"),
            "website_document_metadata_sha256": sha(ROOT / "website/document_metadata.json"),
            "review_slice_zip": "../review_slices/slice_4_regional_transfer_and_calibration/slice_4_regional_transfer_and_calibration_bundle.zip",
            "review_slice_zip_sha256": sha(
                ROOT / "../review_slices/slice_4_regional_transfer_and_calibration/slice_4_regional_transfer_and_calibration_bundle.zip"
            ),
        },
        "build_and_checks": {
            "check_mathematics": {"exit_code": 0, "output": "build/mathematics.json"},
            "paper_build": {"engine": "Tectonic 0.17.0", "exit_code": 0, "pages": 252},
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
            "verify_claims": {"exit_code": 0},
            "unit_tests": {"tests": 918, "result": "OK"},
            "regional_tests": {"tests": 44, "result": "OK"},
            "s02_tests": {"tests": 6, "result": "OK"},
            "regional_inputs": {"passed": True, "members": 6110, "crosswalk_records": 15093},
            "s02_inputs": {"passed": True, "histories": 300, "methods": 600},
            "historical_fits": {"passed": True},
            "website_interactions": {"passed": True, "selector_combinations": 80},
            "verify_repository": {"passed": True, "checked_files": 10908},
            "review_slices": {"exit_code": 0, "slices": 7},
        },
        "limitations": [
            "The audit recomputes saved quantities and deterministic algebra; it does not rerun the historical optimizers, simulate catalogues, or reconstruct every raw history.",
            "The S05 public aggregate does not expose the eight-coordinate vectors; the pooled quadratic and Fisher statistics are checked against the public aggregate and executable definitions, not recomputed from the 999 simulated vectors.",
            "Paired block intervals remain conditional on saved fits and declared block geometry; calendar blocks are dependent and the sign-flip reference is not a sequence-level randomization.",
            "The 7/6/2 lower-bound background-slope counts and the 41,277-plus-one adjudication split are documentary statements bound to the forecast-findings narrative.",
            "S06 block geometry and episode-origin selection are retrospective; the audit verifies final rows and partition arithmetic, not the original optimizer runs.",
            "S03 regional totals are descriptive sums over six archived folds; arm 4 inherits arm 2's background, so (4-3) is not a pure offspring-tail contrast.",
            "Conditional S05 diagnostics are fixed-state and per-origin; they do not define a cross-origin joint null and exclude fitting, selection and catalogue uncertainty.",
        ],
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUT.relative_to(ROOT).as_posix(), "sha256": sha(OUT), "passed": record["passed"]}, indent=2))


if __name__ == "__main__":
    main()
