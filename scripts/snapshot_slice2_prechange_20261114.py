#!/usr/bin/env python3
"""Freeze a byte-level pre-change snapshot for the Slice 2 audit.

The sealed JSON authorities are never edited by the audit.  This snapshot
records every pre-existing JSON file under validation/authorities and
validation/live_results, the Slice 1 acceptance record (the 724th pre-existing
JSON identity), and the publication-facing sources that Slice 2 may repair.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "validation/slice2_prechange_snapshot_20261114.json"
OUT_ZIP = ROOT / "validation/slice2_prechange_snapshot_20261114.zip"
BASELINE = "ce8581b"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sealed = sorted(
        p
        for parent in (ROOT / "validation/authorities", ROOT / "validation/live_results")
        for p in parent.rglob("*.json")
        if p.is_file()
    )
    slice1_record = ROOT / "validation/slice1_math_remediation_20261114.json"
    if slice1_record.is_file():
        sealed.append(slice1_record)
    publication = sorted(
        p
        for pattern in (
            "paper/source/**/*.tex",
            "paper/source/references.bib",
            "docs/reviews/slice1_math_audit_20261114.md",
            "scripts/check_mathematics.py",
            "scripts/build_paper.py",
            "scripts/validate_pdf.py",
            "scripts/verify_claims.py",
            "scripts/verify_repository.py",
            "scripts/snapshot_slice2_prechange_20261114.py",
            "experiments/methodological_audit/slice2_audit_20261114.py",
            "validation/MASTER_CLAIM_LEDGER.json",
            "validation/mathematics.json",
            "MANIFEST.json",
            "README.md",
            "companion/guide_content.json",
            "companion/build_guide.py",
            "website/document_metadata.json",
            "website/build_site.py",
            "review_slices/slice_2_synthetic_mark_kernel/PROMPT.md",
            "review_slices/slice_2_synthetic_mark_kernel/SLICE_2_CONTEXT.md",
            "review_slices/slice_2_synthetic_mark_kernel/slice_2_synthetic_mark_kernel_pages.pdf",
        )
        for p in ROOT.glob(pattern)
        if p.is_file()
    )
    record = {
        "schema": "slice2_prechange_snapshot_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": BASELINE,
        "scope": (
            "Byte-level hashes of every pre-existing JSON file under "
            "validation/authorities and validation/live_results, plus the Slice 1 "
            "acceptance record that completes the 724-record pre-existing JSON "
            "roster, and publication sources that Slice 2 may repair. The sealed "
            "JSON files are not modified by this audit."
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
