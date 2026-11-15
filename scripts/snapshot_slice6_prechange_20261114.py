#!/usr/bin/env python3
"""Freeze a byte-level pre-change snapshot for the Slice 6 audit.

The sealed JSON authorities are never edited by the audit. This snapshot
records every pre-existing JSON file under validation/authorities and
validation/live_results (769 files) plus the three prior-slice records at the
validation root that complete the 772-record pre-existing JSON roster, and the
publication-facing sources that Slice 6 may repair.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "validation/slice6_prechange_snapshot_20261114.json"
OUT_ZIP = ROOT / "validation/slice6_prechange_snapshot_20261114.zip"
BASELINE = "8ae4fa6"

PRIOR_RECORDS = (
    "validation/slice4_remediation_20261114.json",
    "validation/slice5_prechange_snapshot_20261114.json",
    "validation/slice5_remediation_20261114.json",
)

PUBLICATION_PATTERNS = (
    "paper/source/**/*.tex",
    "paper/source/references.bib",
    "paper/manuscript_unified.pdf",
    "docs/reviews/slice6_audit_20261114.md",
    "scripts/check_mathematics.py",
    "scripts/build_paper.py",
    "scripts/validate_pdf.py",
    "scripts/verify_claims.py",
    "scripts/verify_repository.py",
    "scripts/snapshot_slice6_prechange_20261114.py",
    "scripts/build_slice6_acceptance_20261114.py",
    "experiments/methodological_audit/slice6_audit_20261114.py",
    "validation/slice6_remediation_20261114.json",
    "validation/MASTER_CLAIM_LEDGER.json",
    "validation/mathematics.json",
    "validation/numeric_reconciliation_receipt.json",
    "validation/manuscript_display_regression.json",
    "MANIFEST.json",
    "README.md",
    "companion/guide_content.json",
    "companion/build_guide.py",
    "companion/lay_guide_to_the_research.pdf",
    "companion/lay_guide_to_the_research.html",
    "website/document_metadata.json",
    "website/build_site.py",
    "website/check_interactions.cjs",
    "website/site/index.html",
    "website/site/findings.html",
    "website/site/guide.html",
    "review_slices/manifest.json",
    "review_slices/slice_6_local_inhibition_s04b_and_s8/PROMPT.md",
    "review_slices/slice_6_local_inhibition_s04b_and_s8/SLICE_6_CONTEXT.md",
    "review_slices/slice_6_local_inhibition_s04b_and_s8/slice_6_local_inhibition_s04b_and_s8_pages.pdf",
    "docs/reviews/slice5_audit_20261114.md",
    "validation/slice5_remediation_20261114.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUT_JSON.exists() or OUT_ZIP.exists():
        raise SystemExit("Slice 6 pre-change snapshot already exists")
    sealed = sorted(
        p
        for parent in (ROOT / "validation/authorities", ROOT / "validation/live_results")
        for p in parent.rglob("*.json")
        if p.is_file()
    )
    sealed += [ROOT / relative for relative in PRIOR_RECORDS if (ROOT / relative).is_file()]
    publication = sorted(
        {p for pattern in PUBLICATION_PATTERNS for p in ROOT.glob(pattern) if p.is_file()},
        key=lambda p: p.as_posix(),
    )
    record = {
        "schema": "slice6_prechange_snapshot_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": BASELINE,
        "scope": (
            "Byte-level hashes of every pre-existing JSON file under "
            "validation/authorities and validation/live_results (769 files) plus "
            "the three prior-slice records at the validation root that complete "
            "the 772-record pre-existing JSON roster, and publication sources "
            "that Slice 6 may repair. The sealed JSON files are not modified by "
            "this audit."
        ),
        "sealed_json_count": len(sealed),
        "sealed_json": {
            p.relative_to(ROOT).as_posix(): sha256(p) for p in sealed
        },
        "publication_file_count": len(publication),
        "publication_files": {
            p.relative_to(ROOT).as_posix(): sha256(p) for p in publication
        },
    }
    OUT_JSON.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(OUT_JSON, OUT_JSON.relative_to(ROOT).as_posix())
        for p in publication:
            zf.write(p, p.relative_to(ROOT).as_posix())
    print(json.dumps({
        "snapshot": OUT_JSON.relative_to(ROOT).as_posix(),
        "snapshot_sha256": sha256(OUT_JSON),
        "zip": OUT_ZIP.relative_to(ROOT).as_posix(),
        "zip_sha256": sha256(OUT_ZIP),
        "sealed_json_count": len(sealed),
        "publication_file_count": len(publication),
    }, indent=2))


if __name__ == "__main__":
    main()
