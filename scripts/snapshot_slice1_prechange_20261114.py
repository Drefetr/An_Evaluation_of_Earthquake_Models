#!/usr/bin/env python3
"""Freeze a byte-level pre-change snapshot for the Slice 1 math audit.

Sealed authorities are never edited by the audit.  This snapshot records every
JSON file under validation/authorities and validation/live_results together
with the publication-facing sources that the audit may repair.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "validation/slice1_prechange_snapshot_20261114.json"
OUT_ZIP = ROOT / "validation/slice1_prechange_snapshot_20261114.zip"
BASELINE = "d4539af50de91f36a00aaf357a65b875d80927d1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    sealed = sorted(
        p for parent in (ROOT / "validation/authorities", ROOT / "validation/live_results")
        for p in parent.rglob("*.json")
        if p.is_file()
    )
    publication = sorted(
        p
        for pattern in (
            "paper/source/**/*.tex",
            "scripts/check_mathematics.py",
            "experiments/methodological_audit/stability.py",
            "experiments/methodological_audit/moments.py",
            "validation/MASTER_CLAIM_LEDGER.json",
            "MANIFEST.json",
            "README.md",
            "companion/guide_content.json",
            "website/document_metadata.json",
        )
        for p in ROOT.glob(pattern)
        if p.is_file()
    )
    record = {
        "schema": "slice1_prechange_snapshot_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": BASELINE,
        "scope": (
            "Byte-level hashes of every JSON file under validation/authorities and "
            "validation/live_results, plus publication sources that Slice 1 may repair. "
            "The sealed JSON files are not modified by this audit."
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
