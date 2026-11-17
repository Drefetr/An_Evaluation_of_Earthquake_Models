#!/usr/bin/env python3
"""Byte-for-byte snapshot before integrating Pathways 1-4.

The sealed roster is every JSON file under ``validation/authorities`` and every
pre-Pathway JSON file under ``validation/live_results`` at baseline commit
``a9d7f9d``, plus the three prior-slice root records that complete the
historical 782-record roster.  No sealed file is written by this script.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation/pathways_prechange_snapshot_20261117.json"
ZIP = ROOT / "validation/pathways_prechange_snapshot_20261117.zip"
PRIOR = ROOT / "validation/slice7_prechange_snapshot_20261114.json"
ROOT_RECORDS = [
    "validation/slice5_remediation_20261114.json",
    "validation/slice6_prechange_snapshot_20261114.json",
    "validation/slice6_remediation_20261114.json",
]
PUBLICATION = [
    "paper/source/main.tex",
    "paper/source/abstract.tex",
    "paper/source/preamble.tex",
    "paper/source/chapters/01_introduction.tex",
    "paper/source/chapters/11_epplus_benchmark.tex",
    "paper/source/chapters/11_epplus_ablation.tex",
    "paper/source/chapters/11_epplus_eta_profiles.tex",
    "paper/source/chapters/12_s05_completed.tex",
    "paper/source/chapters/13_s8_oracle.tex",
    "paper/source/chapters/14_discussion_conclusion.tex",
    "paper/manuscript_unified.pdf",
    "README.md",
    "REVIEWER_START_HERE.md",
    "docs/changes.md",
    "companion/guide_content.json",
    "companion/lay_guide_to_the_research.pdf",
    "companion/lay_guide_to_the_research.html",
    "website/document_metadata.json",
    "website/findings.html",
    "website/site/findings.html",
    "website/site/findings-data.json",
    "validation/authority_manifest.json",
    "validation/MASTER_CLAIM_LEDGER.json",
    "validation/numeric_reconciliation_receipt.json",
    "validation/manuscript_display_regression.json",
    "MANIFEST.json",
    "../export_review_slice.py",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUT.exists() or ZIP.exists():
        raise SystemExit("snapshot already exists; refuse to overwrite")
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    sealed: dict[str, str] = {}
    for directory, pattern in (("validation/authorities", "*.json"),
                               ("validation/live_results", "*.json")):
        for path in sorted((ROOT / directory).rglob(pattern)):
            relative = path.relative_to(ROOT).as_posix()
            if "/pathway" in relative:
                continue
            sealed[relative] = sha(path)
    for relative in ROOT_RECORDS:
        sealed[relative] = sha(ROOT / relative)
    baseline_782 = {path: digest for path, digest in prior["sealed_json"].items()}
    missing = sorted(set(baseline_782) - set(sealed))
    changed = sorted(p for p in baseline_782 if p in sealed and sealed[p] != baseline_782[p])
    if missing or changed:
        raise SystemExit(f"baseline roster mismatch: missing={missing} changed={changed}")
    additions = sorted(set(sealed) - set(baseline_782))
    publication = {}
    for relative in PUBLICATION:
        path = (ROOT / relative).resolve()
        if path.is_file():
            publication[Path(relative).as_posix()] = sha(path)
    record = {
        "schema": "pathways_prechange_snapshot_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "a9d7f9d",
        "scope": ("Byte-level hashes of every pre-existing JSON file under "
                  "validation/authorities and the pre-Pathway validation/live_results "
                  "tree, plus the three prior-slice root records. The historical "
                  "782-record roster is retained explicitly and the six Slice 7 audit "
                  "outputs present at the baseline commit are recorded as additions."),
        "sealed_json_count": len(sealed),
        "baseline_782_count": len(baseline_782),
        "slice7_audit_addition_count": len(additions),
        "sealed_json": sealed,
        "baseline_782": baseline_782,
        "slice7_audit_additions": additions,
        "publication_file_count": len(publication),
        "publication_files": publication,
    }
    OUT.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sealed:
            archive.write(ROOT / relative, arcname=relative)
    print(json.dumps({
        "path": OUT.relative_to(ROOT).as_posix(),
        "sha256": sha(OUT),
        "zip": ZIP.relative_to(ROOT).as_posix(),
        "zip_sha256": sha(ZIP),
        "sealed_json_count": len(sealed),
        "baseline_782_count": len(baseline_782),
        "slice7_audit_additions": len(additions),
        "publication_file_count": len(publication),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
