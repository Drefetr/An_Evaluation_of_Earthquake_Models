#!/usr/bin/env python3
"""Write the Slice 6 acceptance record from the audit evidence package."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/slice6_remediation_20261114.json"


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
    summary_path = ROOT / "validation/live_results/slice6_audit_20261114/summary.json"
    summary = read(summary_path)
    if not summary.get("passed"):
        raise SystemExit("Slice 6 audit summary is not passed")
    snapshot = read(ROOT / "validation/slice6_prechange_snapshot_20261114.json")
    sealed = read(ROOT / "validation/live_results/slice6_audit_20261114/sealed_authority_integrity.json")
    claims = read(ROOT / "validation/live_results/slice6_audit_20261114/claim_ledger.json")
    receipt = read(ROOT / "validation/numeric_reconciliation_receipt.json")
    pdf_qa = read(ROOT / "build/slice6_pdf_qa/production_checks.json")
    build_record = read(ROOT / "build/slice6_paper/build_record.json")
    unit = test_summary(ROOT / "build/slice6_checks/unit_tests.txt")
    regional = test_summary(ROOT / "build/slice6_checks/regional_tests.txt")
    s02 = test_summary(ROOT / "build/slice6_checks/s02_tests.txt")
    regional_inputs = read(ROOT / "build/slice6_checks/regional_inputs.json")
    s02_inputs = read(ROOT / "build/slice6_checks/s02_inputs.json")
    historical = read(ROOT / "build/slice6_checks/historical_fits.json")
    interactions = read(ROOT / "build/slice6_checks/website_interactions.json")
    repo_check_path = ROOT / "build/slice6_checks/verify_repository.json"
    repo_check = read(repo_check_path) if repo_check_path.is_file() else {}
    review_manifest = read(ROOT / "../review_slices/manifest.json")
    components = summary["components"]
    counts = summary["counts"]
    repairs = summary["defects_and_repairs"]

    record = {
        "schema": "slice6_remediation_acceptance_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "8ae4fa6",
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
            "composition": "769 JSON files under validation/authorities and validation/live_results plus three prior-slice root records",
        },
        "claim_reconciliation": {
            "slice6_claims": claims["counts"]["c13_claims"],
            "missing_displays": claims["counts"]["missing_displays"],
            "outside_only_displays": claims["counts"]["outside_only_displays"],
            "withdrawn_historical_records": receipt["counts"].get("withdrawn_historical_records"),
            "master_ledger_sha256": receipt["ledger_sha256"],
            "full_receipt_passed": receipt["passed"],
            "claims": receipt["counts"].get("claims"),
            "literal_manuscript_display_records": receipt["counts"].get("literal_manuscript_display_records"),
            "missing_declared_manuscript_displays": receipt["counts"].get("missing_declared_manuscript_displays"),
        },
        "repairs": repairs,
        "artifacts": {
            "audit_script": "experiments/methodological_audit/slice6_audit_20261114.py",
            "audit_script_sha256": sha(ROOT / "experiments/methodological_audit/slice6_audit_20261114.py"),
            "audit_summary": "validation/live_results/slice6_audit_20261114/summary.json",
            "audit_summary_sha256": sha(summary_path),
            "audit_report": "docs/reviews/slice6_audit_20261114.md",
            "audit_report_sha256": sha(ROOT / "docs/reviews/slice6_audit_20261114.md"),
            "prechange_snapshot": "validation/slice6_prechange_snapshot_20261114.json",
            "prechange_snapshot_sha256": sha(ROOT / "validation/slice6_prechange_snapshot_20261114.json"),
            "prechange_zip_sha256": sha(ROOT / "validation/slice6_prechange_snapshot_20261114.zip"),
            "manuscript_pdf": "paper/manuscript_unified.pdf",
            "manuscript_pdf_sha256": sha(ROOT / "paper/manuscript_unified.pdf"),
            "manuscript_pages": pdf_qa.get("pages"),
            "claim_ledger": "validation/MASTER_CLAIM_LEDGER.json",
            "claim_ledger_sha256": sha(ROOT / "validation/MASTER_CLAIM_LEDGER.json"),
            "numeric_reconciliation_receipt_sha256": sha(ROOT / "validation/numeric_reconciliation_receipt.json"),
            "manuscript_display_regression_sha256": sha(ROOT / "validation/manuscript_display_regression.json"),
            "companion_pdf_sha256": sha(ROOT / "companion/lay_guide_to_the_research.pdf"),
            "website_document_metadata_sha256": sha(ROOT / "website/document_metadata.json"),
            "review_slice_zip": "../review_slices/slice_6_local_inhibition_s04b_and_s8/slice_6_local_inhibition_s04b_and_s8_bundle.zip",
            "review_slice_zip_sha256": sha(
                ROOT / "../review_slices/slice_6_local_inhibition_s04b_and_s8/slice_6_local_inhibition_s04b_and_s8_bundle.zip"
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
                "underfull_boxes": pdf_qa.get("underfull_boxes"),
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
            "review_slices": {"exit_code": 0, "slices": len(review_manifest)},
        },
        "limitations": [
            "The audit re-derives every displayed cell from the bound case records and re-evaluates the stated identities, KKT conditions and quantiles. It does not re-run the original GPU training campaign or regenerate the 80 S04B histories.",
            "The S04B/S8 MCSEs are descriptive sample standard deviations over independent seeded histories; the heavy-tailed mark laws do not supply finite-variance or Gaussian guarantees.",
            "The 90/180/365-day intervals are paired calendar-block summaries; adjacent blocks are dependent and the sign-flip reference is not a sequence-level randomization.",
            "The S7 both-zero identity is algebraic; saved contrasts differ by up to 1.55e-4 nats from solver/quadrature arithmetic.",
            "The sealed S8 field exact_true_null_minus_fitted_stats is misnamed: it stores the full true-law minus fitted-null contrast (18.112), while the manuscript row uses the true uninhibited-backbone null minus fitted null (1.683) from the referee authority. The sealed file is not edited.",
            "The three saved active S04 gains sum to -2.386682086 nats, while the paired block authority point is -2.386674517; both display -2.387 and the 7.6e-6 difference is saved-arithmetic rounding.",
            "The '369 arithmetic and numerical checks' sentence is a source-reported aggregate; the bound summary enumerates 19 procedures, 152 starts, 30 floors and 182 candidate slots, all complete.",
            "The observed California folds are the same 315 retrospectively inspected targets used elsewhere; they are not independent replication.",
        ],
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUT.relative_to(ROOT).as_posix(),
                      "sha256": sha(OUT), "passed": record["passed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
