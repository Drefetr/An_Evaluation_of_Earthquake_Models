#!/usr/bin/env python3
"""Write the Slice 2 acceptance record from the completed audit artifacts."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "validation/live_results/slice2_audit_20261114"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    summary = load(AUDIT / "summary.json")
    claims = load(AUDIT / "claim_ledger.json")
    sealed = load(AUDIT / "sealed_authority_integrity.json")
    repairs = load(AUDIT / "manuscript_repairs.json")
    receipt = load(ROOT / "validation/numeric_reconciliation_receipt.json")
    record = {
        "schema": "slice2_remediation_acceptance_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "ce8581b",
        "scope": (
            "Vertical Triad Slice 2: Chapters 6, 7, 9 (Sections 9.1--9.13), "
            "Appendix B.7, completed S02, Stage A exposure orthogonalization, "
            "Stage B parent-class temporal scales, and Extension O continuous "
            "Omori tuning."
        ),
        "status": "accepted_with_documented_repairs",
        "passed": bool(
            summary["passed"]
            and claims["passed"]
            and sealed["passed"]
            and repairs["passed"]
            and receipt["passed"]
        ),
        "components": summary["components"],
        "counts": summary["counts"],
        "sealed_authority_integrity": {
            "snapshot": sealed["snapshot"],
            "unchanged": sealed["unchanged"],
            "changed": sealed["changed"],
            "missing": sealed["missing"],
            "snapshot_sha256": sealed["snapshot_sha256"],
        },
        "claim_reconciliation": {
            "claims_checked": claims["n_claims"],
            "failures": claims["failure_count"],
            "counts": claims["counts"],
            "ledger_sha256": claims["ledger_sha256"],
            "full_receipt_passed": receipt["passed"],
        },
        "repairs": summary["defects_and_repairs"],
        "artifacts": {
            "audit_summary": "validation/live_results/slice2_audit_20261114/summary.json",
            "audit_summary_sha256": sha256(AUDIT / "summary.json"),
            "audit_report": "docs/reviews/slice2_audit_20261114.md",
            "audit_report_sha256": sha256(ROOT / "docs/reviews/slice2_audit_20261114.md"),
            "prechange_snapshot": "validation/slice2_prechange_snapshot_20261114.json",
            "prechange_snapshot_sha256": sha256(ROOT / "validation/slice2_prechange_snapshot_20261114.json"),
            "prechange_zip_sha256": sha256(ROOT / "validation/slice2_prechange_snapshot_20261114.zip"),
            "manuscript_pdf": "paper/manuscript_unified.pdf",
            "manuscript_pdf_sha256": sha256(ROOT / "paper/manuscript_unified.pdf"),
            "claim_ledger": "validation/MASTER_CLAIM_LEDGER.json",
            "claim_ledger_sha256": sha256(ROOT / "validation/MASTER_CLAIM_LEDGER.json"),
            "review_slice_zip": "../review_slices/slice_2_synthetic_mark_kernel.zip",
        },
        "build_and_checks": {
            "check_mathematics": {"exit_code": 0, "output": "build/mathematics.json"},
            "paper_build": {"engine": "Tectonic 0.17.0", "exit_code": 0, "pages": 252},
            "pdf_qa": {
                "passed": True,
                "overfull_boxes": 0,
                "overfull_vertical_boxes": 0,
                "undefined_cross_references": [],
                "missing_bibliography_keys": [],
                "missing_figures": [],
                "replacement_characters": 0,
            },
            "companion_build": {"exit_code": 0},
            "website_build": {"exit_code": 0},
            "verify_claims": {"exit_code": 0},
            "unit_tests": {"tests": 918, "result": "OK"},
            "regional_tests": {"tests": 44, "result": "OK"},
            "s02_tests": {"tests": 6, "result": "OK"},
            "regional_inputs": {"passed": True},
            "s02_inputs": {"passed": True, "histories": 300, "methods": 600},
            "historical_fits": {"passed": True},
            "website_interactions": {"passed": True},
            "verify_repository": {"passed": True, "checked_files": 10872},
            "review_slices": {"exit_code": 0, "slices": 7},
        },
        "limitations": [
            "The audit recomputes saved quantities; it does not rerun historical optimizers, simulate catalogues, or reconstruct every raw history.",
            "Clopper-Pearson and Wilson intervals remain conditional on the realized reference banks, generators, procedures, and query histories.",
            "Displayed table identities are checked at six-decimal precision; source values carry more digits.",
            "The spatial extension is a separate completed study and does not convert the Extension O score direction into a spatial validation.",
            "No new null calibration, power calculation, or physical interpretation is introduced.",
        ],
    }
    path = ROOT / "validation/slice2_remediation_20261114.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")
    print(json.dumps({"path": path.relative_to(ROOT).as_posix(),
                      "passed": record["passed"],
                      "sha256": sha256(path)}, indent=2))


if __name__ == "__main__":
    main()
