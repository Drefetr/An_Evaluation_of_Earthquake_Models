"""Hash-pin the publication artefacts and sealed authorities before remediation.

The snapshot itself is written under validation/ and is not part of the sealed
authority set.  No tracked file is modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SEALED_DIRS = (
    "validation/authorities",
    "validation/live_results/s04b_joint_complete_20261111",
    "validation/live_results/s8_moderate_complete_20261111",
    "validation/live_results/etas_inhibition_benchmark_interior_20261112",
    "validation/live_results/score_uncertainty_remote_v2_20261111",
    "validation/live_results/track_a_supplement_20261112",
    "validation/live_results/track_b_controls_20261112",
)

PUBLICATION = (
    "paper/source",
    "paper/manuscript_unified.pdf",
    "README.md",
    "REVIEWER_START_HERE.md",
    "companion",
    "website",
    "validation/MASTER_CLAIM_LEDGER.json",
    "MANIFEST.json",
    "docs/reviews",
    "docs/changes.md",
    "docs/result_provenance.md",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_under(path: Path):
    if path.is_file():
        yield path
        return
    for child in sorted(path.rglob("*")):
        if child.is_file() and "__pycache__" not in child.parts and child.suffix not in {".pyc", ".pyo"}:
            yield child


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/referee_prechange_snapshot_20261113.json")
    parser.add_argument("--archive", type=Path,
                        default=ROOT / "validation/referee_prechange_snapshot_20261113.zip")
    args = parser.parse_args()

    sealed = []
    for directory in SEALED_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.json")):
            sealed.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                           "sha256": digest(path)})

    publication = []
    members = []
    for relative in PUBLICATION:
        path = ROOT / relative
        if not path.exists():
            continue
        for item in files_under(path):
            publication.append({"path": item.relative_to(ROOT).as_posix(),
                                "bytes": item.stat().st_size, "sha256": digest(item)})
            members.append(item)

    snapshot = {
        "schema": "referee_prechange_snapshot_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "dcf2559",
        "scope": ("Hash-pinned state immediately before the 13 November 2026 referee remediation. "
                  "Sealed authorities are listed for custody; publication artefacts are also archived."),
        "sealed_authority_count": len(sealed),
        "sealed_authorities": sealed,
        "publication_file_count": len(publication),
        "publication_files": publication,
        "archive": args.archive.relative_to(ROOT).as_posix(),
    }
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")

    with zipfile.ZipFile(args.archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("validation/referee_prechange_snapshot_20261113.json",
                    args.output.read_bytes())
        for item in members:
            zf.write(item, item.relative_to(ROOT).as_posix())

    print(json.dumps({"sealed": len(sealed), "publication": len(publication),
                      "archive": args.archive.relative_to(ROOT).as_posix()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
