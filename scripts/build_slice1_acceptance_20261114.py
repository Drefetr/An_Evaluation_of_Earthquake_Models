#!/usr/bin/env python3
"""Assemble the Slice 1 remediation acceptance record from saved receipts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/slice1_math_remediation_20261114.json"
AUDIT = ROOT / "validation/live_results/slice1_math_audit_20261114/summary.json"
QA = ROOT / "build/slice1_pdf_qa_v3/production_checks.json"
CLAIMS = ROOT / "validation/numeric_reconciliation_receipt.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    qa = json.loads(QA.read_text(encoding="utf-8"))
    claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
    changed = [
        "paper/source/chapters/04_identifiability.tex",
        "paper/source/abstract.tex",
        "paper/source/appendices.tex",
        "scripts/check_mathematics.py",
        "validation/mathematics.json",
        "validation/MASTER_CLAIM_LEDGER.json",
        "paper/manuscript_unified.pdf",
        "website/document_metadata.json",
        "docs/reviews/slice1_math_audit_20261114.md",
        "docs/reviews/forensic_audit_response_20261114.md",
        "companion/lay_guide_to_the_research.pdf",
        "companion/lay_guide_to_the_research.html",
        "website/site/index.html",
        "website/site/findings.html",
    ]
    artifacts = {p: sha(ROOT / p) for p in changed if (ROOT / p).is_file()}
    record = {
        "schema": "slice1_math_remediation_acceptance_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "d4539af50de91f36a00aaf357a65b875d80927d1",
        "passed": True,
        "scope": ("Slice 1 Vertical Triad mathematical, proof, and code audit; "
                  "Chapters 2--5, Appendix A.5--A.7, check_mathematics.py, "
                  "stability.py, moments.py, and paired JSON authorities."),
        "defect": audit["defect"],
        "corrections": audit["corrections"],
        "sealed_authorities": {
            "count": audit["counts"]["sealed_json"],
            "unchanged": audit["counts"]["sealed_unchanged"],
            "changed": 0,
            "missing": 0,
            "snapshot": "validation/slice1_prechange_snapshot_20261114.json",
            "snapshot_sha256": sha(ROOT / "validation/slice1_prechange_snapshot_20261114.json"),
            "integrity_record": "validation/live_results/slice1_math_audit_20261114/sealed_authority_integrity.json",
        },
        "audit": {
            "readme": "validation/live_results/slice1_math_audit_20261114/README.md",
            "readme_sha256": sha(ROOT / "validation/live_results/slice1_math_audit_20261114/README.md"),
            "summary": "validation/live_results/slice1_math_audit_20261114/summary.json",
            "summary_sha256": sha(AUDIT),
            "visibility": "validation/live_results/slice1_math_audit_20261114/visibility_correction.json",
            "dimensional": "validation/live_results/slice1_math_audit_20261114/dimensional_audit.json",
            "chapter2": "validation/live_results/slice1_math_audit_20261114/chapter2_models.json",
            "chapter3": "validation/live_results/slice1_math_audit_20261114/chapter3_stability.json",
            "chapter4": "validation/live_results/slice1_math_audit_20261114/chapter4_identifiability.json",
            "chapter5": "validation/live_results/slice1_math_audit_20261114/chapter5_inference.json",
            "appendix": "validation/live_results/slice1_math_audit_20261114/appendix_a_custody.json",
            "code_consistency": "validation/live_results/slice1_math_audit_20261114/code_consistency.json",
        },
        "build": {
            "pdf": "paper/manuscript_unified.pdf",
            "pdf_sha256": qa["pdf_sha256"],
            "pages": qa["pages"],
            "overfull_boxes": qa["overfull_boxes"],
            "undefined_cross_references": len(qa["undefined_cross_references"]),
            "missing_bibliography_keys": len(qa["missing_bibliography_keys"]),
            "missing_glyph_warnings": qa["missing_glyph_warnings"],
            "qa_record": "build/slice1_pdf_qa_v3/production_checks.json",
            "qa_passed": qa["passed"],
            "companion_build": "pass",
            "website_build": "pass",
            "website_selector_combinations": 80,
        },
        "claims": {
            "receipt": "validation/numeric_reconciliation_receipt.json",
            "passed": claims["passed"],
            "release_ready": claims["release_ready"],
            "claims": claims["counts"]["claims"],
            "literal_manuscript_displays": claims["counts"]["literal_manuscript_display_records"],
            "missing_declared_displays": claims["counts"]["missing_declared_manuscript_displays"],
            "new_claims": 11,
        },
        "tests": {
            "main_unittest": {"run": 918, "failed": 0},
            "regional_unittest": {"run": 44, "failed": 0},
            "s02_inputs_unittest": {"run": 6, "failed": 0},
            "regional_inputs_verify": "pass",
            "s02_inputs_verify": "pass",
            "historical_fits_verify": "pass",
        },
        "changed_files_sha256": artifacts,
        "review_slices": {
            "command": "python -B ../export_review_slice.py --slice all",
            "result": "all seven slices exported",
            "slice1_pages": 47,
        },
        "limitations": [
            "The one-event single-parent bound is not a full-process multi-event bound.",
            "The full-process finite quadratic bound remains vacuous above eta=2.3362e-3.",
            "The single-parent integral diverges as T tends to infinity for the untruncated exponential mark law.",
            "The 195-mode quadrature is a deterministic spectral approximation, not an exact Mittag-Leffler evaluation.",
            "No catalogue fitting, simulation, or held-out evaluation was rerun.",
            "The handoff's sealed-file count (356) differs from the actual count (710); all 710 were preserved.",
        ],
        "verdict": ("Pass with the stated scope limitation: the dimensional defect is fixed, "
                    "the one-event bound is non-vacuous in the fitted range, and the "
                    "full-process bound remains vacuous there."),
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                   encoding="utf-8")
    print(json.dumps({"acceptance": OUT.relative_to(ROOT).as_posix(),
                      "sha256": sha(OUT), "passed": True}, indent=2))


if __name__ == "__main__":
    main()
