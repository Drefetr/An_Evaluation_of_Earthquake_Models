"""Verify relocated saved coverage and its custody; no scientific replay.

Run from any directory with --repository pointing to the repository checkout.
Only the existing pinned coverage/inventory metadata code is executed. The
temporary coverage output is removed automatically; repository files are read-only.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(base, name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or str(p) != name or "\\" in name or ":" in name or ".." in p.parts:
        raise ValueError("Nonportable path: " + name)
    resolved = (base / name).resolve()
    if resolved == base or not resolved.is_relative_to(base):
        raise ValueError("Path escapes base: " + name)
    return resolved


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repository.resolve()
    package = Path(__file__).resolve().parent
    manifest = json.loads((package / "relocation_manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema"] == "publication_coverage_relocation_v1", "Relocation schema")
    for name, expected in manifest["payload_sha256"].items():
        require(sha(relative(package, name)) == expected, "Package identity: " + name)
    review = json.loads((package / "independent_source_review.json").read_text(encoding="utf-8"))
    require(review["passed"] is True and review["source_custody_acceptance"] is True,
            "Source custody review is not accepted")
    require(review["new_scientific_replay_acceptance"] is False, "Review scope")
    for original, target in manifest["original_package_destinations"].items():
        require(sha(relative(package, target)) == review["package_files_sha256"][original],
                "Original evidence identity: " + original)
    require(set(manifest["original_package_destinations"]) == set(review["package_files_sha256"]),
            "Original evidence roster")
    for mapping in (review["current_source_sha256"], review["producer_sha256"]):
        for name, expected in mapping.items():
            require(sha(relative(repo, name)) == expected, "Repository identity: " + name)
    prior = review["historical_acceptance"]
    require(sha(relative(repo, prior["path"])) == prior["sha256"], "Prior acceptance identity")
    with tempfile.TemporaryDirectory(prefix="publication-coverage-metadata-") as temporary:
        output = Path(temporary) / "coverage.json"
        command = [sys.executable, "-B", str(repo / "reproduction/score_replay/coverage_report.py"),
                   "--repository", str(repo), "--evidence", str(package / "coverage_inputs.json"),
                   "--output", str(output)]
        completed = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        require(completed.returncode == 0, "Saved coverage check failed: " + completed.stdout + completed.stderr)
        require(output.read_bytes() == (package / "coverage.json").read_bytes(),
                "Relocated coverage is not byte-identical")
        coverage = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"passed": True, "scope": "saved-evidence metadata verification only",
                      "coverage_sha256": sha(package / "coverage.json"),
                      "manifest_sha256": sha(package / "coverage_inputs.json"),
                      "source_review_sha256": sha(package / "independent_source_review.json"),
                      "payload_files_checked": len(manifest["payload_sha256"]),
                      "current_source_files_checked": len(review["current_source_sha256"]),
                      "producer_files_checked": len(review["producer_sha256"]),
                      "table_count": coverage["table_count"], "status_counts": coverage["status_counts"],
                      "byte_identical_after_relocation": True, "scientific_calls": 0}))


if __name__ == "__main__":
    main()
