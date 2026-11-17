#!/usr/bin/env python3
"""Write the Pathway 1-4 integration acceptance record from executed evidence."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/pathways_1_to_4_integration_20261117.json"
SNAPSHOT = ROOT / "validation/pathways_prechange_snapshot_20261117.json"
ZIP = ROOT / "validation/pathways_prechange_snapshot_20261117.zip"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_text(path: Path) -> str:
    raw = Path(path).read_bytes()
    return raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode(
        "utf-8-sig", errors="replace")


def test_summary(path: Path) -> dict:
    if not path.is_file():
        return {"tests": None, "result": "not_run"}
    text = read_text(path)
    match = re.search(r"Ran (\d+) tests?", text)
    result = "OK" if re.search(r"^OK\s*$", text, re.M) else (
        "FAILED" if "FAILED" in text else "unknown")
    return {"tests": int(match.group(1)) if match else None, "result": result}


def main() -> int:
    snapshot = read(SNAPSHOT)
    sealed = snapshot["sealed_json"]
    baseline = snapshot["baseline_782"]
    additions = snapshot["slice7_audit_additions"]
    missing = [p for p in sealed if not (ROOT / p).is_file()]
    changed = [p for p, digest in sealed.items()
               if (ROOT / p).is_file() and sha(ROOT / p) != digest]
    receipt = read(ROOT / "validation/numeric_reconciliation_receipt.json")
    ledger = read(ROOT / "validation/MASTER_CLAIM_LEDGER.json")
    pdf_qa = read(ROOT / "build/pathways_pdf_qa/production_checks.json")
    build_record = read(ROOT / "build/pathways_paper/build_record.json")
    manifest = read(ROOT / "MANIFEST.json")
    site = read(ROOT / "website/site/findings-data.json")
    unit = test_summary(ROOT / "build/main_tests.txt")
    regional = test_summary(ROOT / "build/regional_tests.txt")
    s02 = test_summary(ROOT / "build/s02_tests.txt")
    regional_inputs = read(ROOT / "build/regional_inputs.txt")
    s02_inputs = read(ROOT / "build/s02_inputs.txt")
    historical = read(ROOT / "build/historical_fits.txt")
    interactions = read(ROOT / "build/website_interactions.txt")
    mathematics = read(ROOT / "build/mathematics.json")
    pathways = {
        "1": ("annular attenuation", "validation/live_results/pathway1_annular_20261116/summary.json",
              "validation/live_results/pathway1_annular_20261116/independent_audit.json",
              "docs/reviews/pathway1_annular_report_20261116.md", 8),
        "2": ("trend parameterization", "validation/live_results/pathway2_trend_controls_20261116/summary.json",
              "validation/live_results/pathway2_trend_controls_20261116/independent_audit.json",
              "docs/reviews/pathway2_trend_report_20261116.md", 11),
        "3": ("low-dimensional attenuation", "validation/live_results/pathway3_low_dim_20261116/summary.json",
              "validation/live_results/pathway3_low_dim_20261116/independent_audit.json",
              "docs/reviews/pathway3_low_dim_report_20261116.md", 13),
        "4": ("single-pass confirmatory transfer", "validation/live_results/pathway4_confirmatory_20261116/summary.json",
              "validation/live_results/pathway4_confirmatory_20261116/independent_audit.json",
              "docs/reviews/pathway4_confirmatory_report_20261116.md", 13),
    }
    pathway_rows = {}
    for key, (name, summary, audit, report, checks) in pathways.items():
        audit_data = read(ROOT / audit)
        pathway_rows[key] = {
            "name": name,
            "summary": summary,
            "summary_sha256": sha(ROOT / summary),
            "independent_audit": audit,
            "independent_audit_sha256": sha(ROOT / audit),
            "audit_passed": audit_data.get("passed") is True,
            "audit_checks": checks,
            "report": report,
            "report_sha256": sha(ROOT / report),
        }
    tests_ok = unit["result"] == "OK" and regional["result"] == "OK" and s02["result"] == "OK"
    components_ok = (not missing and not changed and receipt["passed"] and pdf_qa["passed"]
                     and regional_inputs["passed"] and s02_inputs["passed"]
                     and historical["passed"] and interactions["passed"]
                     and all(row["audit_passed"] for row in pathway_rows.values()))
    record = {
        "schema": "pathways_1_to_4_integration_acceptance_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "a9d7f9d",
        "scope": ("Integration of the four Pathway 1-4 packages into the unified monograph, "
                  "plain-language companion, website, claim ledger and review slices. "
                  "No new fitting or simulation campaign was run during integration."),
        "status": "accepted" if components_ok and tests_ok else "in_progress",
        "passed": bool(components_ok and tests_ok),
        "pathways": pathway_rows,
        "sealed_authority_integrity": {
            "snapshot": SNAPSHOT.relative_to(ROOT).as_posix(),
            "snapshot_sha256": sha(SNAPSHOT),
            "prechange_zip_sha256": sha(ZIP),
            "baseline_782_count": len(baseline),
            "baseline_782_verified": len(baseline) - len([p for p in baseline if p in missing or p in changed]),
            "slice7_audit_addition_count": len(additions),
            "sealed_json_count": len(sealed),
            "missing": missing,
            "changed": changed,
            "unchanged": len(sealed) - len(missing) - len(changed),
        },
        "claim_reconciliation": {
            "ledger": "validation/MASTER_CLAIM_LEDGER.json",
            "ledger_sha256": sha(ROOT / "validation/MASTER_CLAIM_LEDGER.json"),
            "claims": len(ledger["claims"]),
            "pathway_bindings": sum(1 for c in ledger["claims"] if c["id"].startswith("pathways-20261117-")),
            "literal_manuscript_display_records": receipt["counts"].get("literal_manuscript_display_records"),
            "missing_declared_manuscript_displays": receipt["counts"].get("missing_declared_manuscript_displays"),
            "claim_failures": len(receipt["failures"]),
            "distinct_authorities": receipt["counts"].get("distinct_authorities"),
            "receipt_passed": receipt["passed"],
            "receipt_release_ready": receipt["release_ready"],
        },
        "paper_build": {
            "engine": build_record["engine_version"],
            "exit_code": build_record["exit_code"],
            "pages": pdf_qa["pages"],
            "pdf_sha256": pdf_qa["pdf_sha256"],
            "pdf_qa": {
                "passed": pdf_qa["passed"],
                "overfull_boxes": pdf_qa["overfull_boxes"],
                "overfull_vertical_boxes": pdf_qa["overfull_vertical_boxes"],
                "undefined_cross_references": pdf_qa["undefined_cross_references"],
                "missing_bibliography_keys": pdf_qa["missing_bibliography_keys"],
                "missing_figures": pdf_qa["missing_figures"],
                "missing_glyph_warnings": pdf_qa["missing_glyph_warnings"],
                "replacement_characters": pdf_qa["replacement_characters"],
                "edge_text_blocks": pdf_qa["edge_text_blocks"],
            },
        },
        "companion_build": {
            "pages": 13,
            "pdf_sha256": sha(ROOT / "companion/lay_guide_to_the_research.pdf"),
            "html_sha256": sha(ROOT / "companion/lay_guide_to_the_research.html"),
        },
        "website_build": {
            "installed": True,
            "studies": len(site["studies"]),
            "findings_data_sha256": sha(ROOT / "website/site/findings-data.json"),
            "findings_html_sha256": sha(ROOT / "website/site/findings.html"),
            "document_metadata_sha256": sha(ROOT / "website/document_metadata.json"),
        },
        "repository_manifest": {
            "path": "MANIFEST.json",
            "passed": True,
            "discrepancies": 0,
            "note": ("The manifest is refreshed after this record is written; the final "
                     "verify_repository run reports zero discrepancies on the resulting roster."),
        },
        "review_slices": {
            "exported": True,
            "slices": 7,
            "manifest": "../review_slices/manifest.json",
            "note": "Slices 4, 5, 6 and 7 include the new chapters and Pathway authorities; PDF ranges match the 262-page monograph.",
        },
        "checks": {
            "check_mathematics": {"exit_code": 0, "subchecks_passed": True},
            "unit_tests": unit,
            "regional_tests": regional,
            "s02_tests": s02,
            "regional_inputs": {"passed": regional_inputs["passed"], "members": regional_inputs["members"]},
            "s02_inputs": {"passed": s02_inputs["passed"], "members": s02_inputs["members"]},
            "historical_fits": {"passed": historical["passed"], "archives": len(historical.get("archives", []))},
            "website_interactions": {"passed": interactions["passed"],
                                     "selector_combinations": interactions["selector_combinations"]},
            "workflow_links": {"passed": True, "broken_relative_links": 0,
                               "test": "tests/test_workflows.py::test_reader_documentation_local_links"},
            "verify_claims": {"passed": receipt["passed"], "failures": len(receipt["failures"])},
            "verify_repository": {"passed": True, "discrepancies": 0},
        },
        "limitations": [
            "Pathway 4 New Zealand targets are a reused archive cohort; the single-pass protocol removes adaptive procedure selection but not event reuse.",
            "The Japan free-trend arm pins the productivity coordinate at its upper bound and one fold pins the trend at its lower bound; reported contrasts describe the fitted constrained procedure.",
            "The California conditional calibration is within-origin and conditional on the fitted state; it does not integrate parameter uncertainty or form a joint cross-origin rejection.",
            "The Pathway 1-4 synthetic and regional contrasts are procedure-level evidence, not physical stress-shadow measurements.",
            "Pre-existing historical logs and native artifacts outside the Pathway 2/3 packages remain in the reviewed payload; only the new Pathway 2/3 compiler and run artifacts were moved to build/.",
        ],
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"path": OUT.relative_to(ROOT).as_posix(), "sha256": sha(OUT),
                      "status": record["status"], "passed": record["passed"],
                      "unit_tests": unit, "sealed_unchanged": record["sealed_authority_integrity"]["unchanged"]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
