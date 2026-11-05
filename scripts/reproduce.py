"""Replay recovered study inputs; each study retains its own numerical scope.

This entry point executes the public replay modules and retains their output,
including failures. It does not run optimizers or reinterpret retrospective
results as prospective evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIES = {
    "nz": ("reproduction/nzca/replay.py", ["--region", "nz"]),
    "california": ("reproduction/nzca/replay.py", ["--region", "california"]),
    "jma": ("reproduction/jma/replay.py", []),
    "s04b": ("reproduction/synthetic/replay.py", []),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay(studies, output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Output must be a new directory: " + str(output))
    for name in studies:
        entry = ROOT / STUDIES[name][0]
        if not entry.is_file():
            raise FileNotFoundError("Replay entry point missing: " + str(entry))
    output.mkdir(parents=True)
    receipt = {
        "schema": "recovered_study_replay_v1",
        "scope": "Exact input reconstruction and the explicitly selected saved-state calculations; no automatic refitting or confirmatory inference.",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "studies": [],
        "passed": False,
    }
    started = time.monotonic()
    for name in studies:
        relative, extra = STUDIES[name]
        destination = output / name
        args = [sys.executable, "-B", str(ROOT / relative), *extra,
                "--output", str(destination)]
        with (output / (name + ".log")).open("w", encoding="utf-8") as log:
            completed = subprocess.run(args, cwd=ROOT, stdout=log,
                                       stderr=subprocess.STDOUT, check=False)
        result_path = destination / "result.json"
        child_passed = False
        if result_path.is_file():
            try:
                child_passed = json.loads(result_path.read_text(encoding="utf-8")).get("passed") is True
            except (ValueError, AttributeError):
                pass
        result = {
            "study": name,
            "entry_point": relative,
            "entry_point_sha256": digest(ROOT / relative),
            "arguments": [*extra, "--output", name],
            "exit_code": completed.returncode,
            "passed": child_passed,
            "log": name + ".log",
            "result": name + "/result.json" if result_path.is_file() else None,
            "result_sha256": digest(result_path) if result_path.is_file() else None,
        }
        receipt["studies"].append(result)
        receipt["elapsed_seconds"] = time.monotonic() - started
        (output / "replay.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        if completed.returncode != 0 or not child_passed:
            return receipt
    receipt["passed"] = True
    receipt["elapsed_seconds"] = time.monotonic() - started
    (output / "replay.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=[*STUDIES, "all"], default="all")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    studies = list(STUDIES) if args.study == "all" else [args.study]
    try:
        receipt = replay(studies, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
