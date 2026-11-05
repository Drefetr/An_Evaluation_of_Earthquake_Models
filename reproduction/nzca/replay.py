"""Reconstruct NZ/California cohorts from verified original provider bytes.

No model fitting, simulation or network access occurs here. Outputs must be new.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import sys

BUNDLE = Path(__file__).resolve().parent


class ReplayError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ReplayError(code)


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def safe_path(root, relative):
    """Manifest paths are POSIX-relative and may never escape their root."""
    require(isinstance(relative, str) and relative and "\\" not in relative and ":" not in relative,
            "unsafe_manifest_path")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and ".." not in path.parts, "unsafe_manifest_path")
    result = (Path(root) / path).resolve()
    require(result.is_relative_to(Path(root).resolve()), "unsafe_manifest_path")
    return result


def checked_bytes(path, expected):
    require(Path(path).is_file(), "input_missing")
    require(Path(path).stat().st_size == expected["bytes"], "input_size_mismatch")
    payload = Path(path).read_bytes()
    require(sha256(payload) == expected["sha256"], "input_hash_mismatch")
    return payload


def load_manifest(bundle=BUNDLE):
    payload = (Path(bundle) / "input_manifest.json").read_bytes()
    manifest = json.loads(payload)
    require(manifest.get("schema_version") == 1, "unsupported_manifest_schema")
    return manifest, sha256(payload)


def load_source(name, relative, manifest, bundle=BUNDLE):
    entries = {r["path"]: r for r in manifest["source_code"]}
    require(relative in entries, "unbound_source")
    path = safe_path(bundle, relative)
    checked_bytes(path, entries[relative])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_bytes(region, record, raw_input=None, bundle=BUNDLE):
    if raw_input is None:
        compressed = checked_bytes(safe_path(bundle, record["compressed"]["path"]), record["compressed"])
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                payload = stream.read(record["bytes"] + 1)
        except (OSError, EOFError) as error:
            raise ReplayError("invalid_gzip_input") from error
    else:
        payload = checked_bytes(safe_path(raw_input, region + "/" + record["filename"]), record)
    require(len(payload) == record["bytes"], "raw_size_mismatch")
    require(sha256(payload) == record["sha256"], "raw_hash_mismatch")
    if "git_blob_sha1" in record:
        git_blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
        require(git_blob == record["git_blob_sha1"], "raw_git_blob_mismatch")
    return payload


def write_json(path, value):
    Path(path).write_bytes(json_bytes(value))


def replay_nz(output, manifest, raw_input=None, bundle=BUNDLE):
    output.mkdir()
    source = load_source("nzca_nz_selection", "sources/nz_selection.py", manifest, bundle)
    dataset = manifest["datasets"]["nz"]
    rows = {"main": [], "prehistory": []}
    verified = []
    required_fields = {"publicid", "origintime", "magnitude", "depth", "latitude", "longitude",
                       "magnitudetype", "eventtype"}
    for record in dataset["raw_files"]:
        payload = raw_bytes("nz", record, raw_input, bundle)
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        require(required_fields <= set(reader.fieldnames or []), "nz_source_schema_mismatch")
        parsed = list(reader)
        require(len(parsed) == record["rows"], "nz_raw_row_count_mismatch")
        for lineno, row in enumerate(parsed, 2):
            row.update(_source_file="nz/" + record["filename"], _source_row=lineno)
        rows[record["role"]].extend(parsed)
        verified.append({"file": record["filename"], "sha256": sha256(payload), "rows": len(parsed)})
    results = {}
    for role in ("main", "prehistory"):
        options = {} if role == "main" else {"start": datetime(1950, 1, 1, tzinfo=timezone.utc), "end": source.ORIGIN}
        selected, ledger, duplicates = source.select_rows(rows[role], **options)
        payload = source.csv_bytes(selected, source.FIELDS)
        expected = dataset["expected"][role]
        expected_payload = checked_bytes(safe_path(bundle, expected["path"]), expected)
        filename = Path(expected["path"]).name
        (output / filename).write_bytes(payload)
        with (output / (role + "_filter_ledger.jsonl")).open("wb") as stream:
            for row in ledger:
                stream.write(json_bytes(row))
        require(payload == expected_payload, "nz_" + role + "_csv_mismatch")
        reasons = dict(sorted(Counter(r["primary_reason"] for r in ledger).items()))
        require(len(selected) == dataset["expected_counts"][role + "_rows"], "nz_selected_count_mismatch")
        if role == "main":
            require(len(rows[role]) == dataset["expected_counts"]["main_raw_rows"], "nz_total_raw_count_mismatch")
            require(reasons == dataset["expected_counts"]["main_primary_reasons"], "nz_exclusion_counts_mismatch")
        results[role] = {"output": "nz/" + filename, "selected_rows": len(selected),
                         "raw_rows": len(rows[role]), "sha256": sha256(payload),
                         "exact_expected_bytes": True, "primary_reasons": reasons, **duplicates}
    return {"status": "passed", "verified_raw": verified, "cohorts": results}


def ca_counts(events):
    counts = {"events": len(events), "unique_ids": len({e["event_id"] for e in events}),
              "warmup": sum(e["origin_time_utc"] < "1986-01-01" for e in events),
              "folds": [], "m4p5_folds": []}
    for start, end in [("2011-01-01", "2016-01-01"), ("2016-01-01", "2021-01-01"), ("2021-01-01", "2026-01-01")]:
        selected = [e for e in events if start <= e["origin_time_utc"] < end]
        counts["folds"].append(len(selected))
        counts["m4p5_folds"].append(sum(e["magnitude"] >= 4.5 for e in selected))
    return counts


def replay_california(output, manifest, raw_input=None, bundle=BUNDLE):
    output.mkdir()
    parser = load_source("nzca_ca_parser", "sources/ca_parser.py", manifest, bundle)
    source = load_source("nzca_ca_selection", "sources/ca_selection.py", manifest, bundle)
    dataset = manifest["datasets"]["california"]
    raw_dir = output / "raw"
    raw_dir.mkdir()
    verified = []
    entries = {"train": [], "protected": []}
    for record in dataset["raw_files"]:
        payload = raw_bytes("california", record, raw_input, bundle)
        # Filename validation happens independently of the trusted input bundle.
        destination = safe_path(raw_dir, record["filename"])
        require(destination.parent == raw_dir.resolve(), "unsafe_raw_filename")
        destination.write_bytes(payload)
        entries[record["lane"]].append({"path": record["filename"]})
        verified.append({"file":record["filename"],"sha256":sha256(payload),"bytes":len(payload)})
    all_events = []
    lane_results = {}
    for lane in ("train", "protected"):
        lane_output = output / lane
        lane_output.mkdir()
        opposite = None if lane == "train" else output / "train/raw_id_index.json"
        events, diagnostics, training_admission = source.parse_lane(
            raw_dir, entries[lane], parser, lane, lane_output, opposite_index=opposite)
        audit = json.loads((lane_output / "private_parse_audit.json").read_text())
        expected_ref = dataset["expected_parse_audits"][lane]
        expected_audit = json.loads(checked_bytes(safe_path(bundle, expected_ref["path"]), expected_ref))
        require(audit == expected_audit, "california_" + lane + "_exclusion_audit_mismatch")
        write_json(lane_output / "events.json", events)
        lane_results[lane] = {"events":len(events),"diagnostic_events":len(diagnostics),
                              "exact_parse_audit":True,"parse_audit":audit}
        if training_admission is not None:
            require(training_admission["training_admit_boolean"], "california_training_admission_failed")
            lane_results[lane]["training_admission"] = training_admission
        all_events.extend(events)
        del diagnostics
    all_events.sort(key=lambda r: (r["origin_time_us"], r["event_id"]))
    require(len({e["event_id"] for e in all_events}) == len(all_events), "california_duplicate_event_id")
    expected_ref = dataset["expected_events"]
    expected_payload = checked_bytes(safe_path(bundle, expected_ref["path"]), expected_ref)
    payload = json_bytes(all_events)
    (output / "events.json").write_bytes(payload)
    # Compare full event objects, including source line numbers and original tokens.
    require(all_events == json.loads(expected_payload), "california_event_objects_mismatch")
    require(payload == expected_payload, "california_canonical_serialization_mismatch")
    counts = ca_counts(all_events)
    require(counts == dataset["expected_counts"], "california_count_mismatch")
    return {"status":"passed","verified_raw":verified,"lanes":lane_results,"counts":counts,
            "output":"california/events.json","event_objects_sha256":sha256(payload),
            "exact_event_objects":True,"exact_expected_bytes":True}


def main(argv=None):
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--region", choices=("nz", "california", "all"), default="all")
    command.add_argument("--output", type=Path, required=True, help="New directory; existing paths are refused.")
    command.add_argument("--raw-input", type=Path, help="Optional directory produced by acquisition.py.")
    args = command.parse_args(argv)
    if args.output.exists():
        print(json.dumps({"status":"failed","passed":False,"error":"output_already_exists"}))
        return 2
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"schema_version":1,"status":"running","passed":False,"region":args.region,
              "scope":"Raw-to-cohort reconstruction only; no model fitting, simulation or score replay.","regions":{}}
    try:
        manifest, manifest_sha = load_manifest()
        result["input_manifest_sha256"] = manifest_sha
        for region in (("nz", "california") if args.region == "all" else (args.region,)):
            runner = replay_nz if region == "nz" else replay_california
            result["regions"][region] = runner(args.output / region, manifest, args.raw_input)
        result["status"] = "passed"
        result["passed"] = True
        return_code = 0
    except Exception as error:
        result.update(status="failed",passed=False,error_type=type(error).__name__,
                      error=str(error) if isinstance(error, ReplayError) else getattr(error,"code","source_or_io_failure"))
        return_code = 1
    write_json(args.output / "result.json", result)
    print(json.dumps({"status":result["status"],"region":args.region,"result":"result.json"}))
    return return_code


if __name__ == "__main__":
    sys.exit(main())
