#!/usr/bin/env python3
"""Append Slice 7 bindings for the split New Zealand MDE rows and CA deltas.

The pre-change ledger bound the single New Zealand MDE row to the free-trend
authority.  Slice 7 splits that row into free-, zero- and fixed-null-trend
rows and expands the fractional-perturbation sentence to cover every contrast
in Table ``tab:mde``.  This script adds additive typed bindings for the newly
displayed zero/fixed cells and the California LI+/OC perturbations.  It never
edits a sealed authority.  Run ``scripts/verify_claims.py --write-receipts``
afterwards to refresh the compact display custody.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"
NZ = ROOT / "validation/live_results/forensic_remediation_20261114/nz_trend_controls.json"
MDE = ROOT / "validation/live_results/referee_remediation_20261113/mde_expanded.json"
LOC = ["chapters/14_power_and_mde.tex"]
ABSTRACT = ["abstract.tex", "chapters/14_power_and_mde.tex"]


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    spec = importlib.util.spec_from_file_location("_slice7_bind_verify", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    ledger = read(LEDGER)
    if any(c["id"].startswith("slice7-20261114-") for c in ledger["claims"]):
        raise SystemExit("Slice 7 claims already present")

    def make(claim_id: str, source: Path, pointer: str, display: str, locations: list[str],
             component: str, transformation=None) -> dict:
        data = read(source)
        raw = vc.resolve(data, pointer)
        claim = dict(
            id=claim_id,
            bundled_source=source.relative_to(ROOT).as_posix(),
            source_path=source.relative_to(ROOT).as_posix(),
            source_sha256=sha256(source),
            json_pointer=pointer,
            resolved_source_value=raw,
            display=display,
            transformation=transformation or "decimal rounding to displayed precision",
            json_value_kind="numeric_scalar",
            ledger_role="manuscript_binding",
            final_display_locations=locations,
            component=component,
            qualification=("Additive Slice 7 binding for the contrast-specific New Zealand trend arms and "
                           "California fractional perturbations; frozen sealed inputs and explicit JSON pointer."),
            status="source_bound",
            binding_kind="exact_json_pointer",
            reconciliation_status="verified_at_declared_granularity",
        )
        claim["value"] = vc.transformed(raw, claim, data)
        if not vc.equal_display(claim["value"], claim):
            raise ValueError(("display does not round", claim_id, raw, display))
        return claim

    add: list[dict] = []
    nz_base = "/full_grid/pooled"
    for arm, label, se_mde in (
        ("zero_d", "zero-trend", "zero"),
        ("fixed_null_d", "fixed-null-trend", "fixed"),
    ):
        for block in ("90", "180", "365"):
            se_ptr = f"{nz_base}/{arm}/block_days/{block}/se_total_nats"
            mde_ptr = f"{nz_base}/{arm}/block_days/{block}/mde95_total_nats"
            se_display = {"zero": {"90": "2.76", "180": "2.79", "365": "2.99"},
                          "fixed": {"90": "1.40", "180": "1.42", "365": "1.55"}}[se_mde][block]
            mde_display = {"zero": {"90": "5.42", "180": "5.47", "365": "5.87"},
                           "fixed": {"90": "2.74", "180": "2.79", "365": "3.04"}}[se_mde][block]
            per_event_display = {"zero": {"90": "0.0089", "180": "0.0089", "365": "0.0096"},
                                 "fixed": {"90": "0.0045", "180": "0.0046", "365": "0.0050"}}[se_mde][block]
            add.append(make(
                f"slice7-20261114-{len(add)+1:03d}", NZ, se_ptr, se_display, LOC,
                f"NZ {label} {block}-day block SE"))
            add.append(make(
                f"slice7-20261114-{len(add)+1:03d}", NZ, mde_ptr, mde_display,
                ABSTRACT if block == "90" else LOC,
                f"NZ {label} {block}-day MDE95"))
            add.append(make(
                f"slice7-20261114-{len(add)+1:03d}", NZ, mde_ptr, per_event_display, LOC,
                f"NZ {label} {block}-day MDE95 per event",
                {"operation": "divide", "divisor": 612}))
    add.append(make(
        "slice7-20261114-019", NZ, f"{nz_base}/zero_d/total_heldout", "-11.431", LOC,
        "Three-fold New Zealand zero-trend observed total"))
    add.append(make(
        "slice7-20261114-020", NZ, f"{nz_base}/fixed_null_d/total_heldout", "-5.006", LOC,
        "Three-fold New Zealand fixed-null-trend observed total"))

    ca = (
        ("1", "CA_LIplus_total_minus_floor", "California LI+ total", "15.6", "15.5", "15.5"),
        ("3", "CA_OC_minus_EP", "California OC minus EP", "52.5", "52.3", "51.7"),
    )
    for index, _contrast, label, d90, d180, d365 in ca:
        for block, display in (("90", d90), ("180", d180), ("365", d365)):
            add.append(make(
                f"slice7-20261114-{len(add)+1:03d}", MDE,
                f"/contrasts/{index}/block_days/{block}/required_rate_perturbation",
                display, LOC, f"{label} {block}-day fractional rate perturbation",
                {"operation": "multiply", "factor": 100}))

    ledger["claims"].extend(add)
    ledger["closure_revision"] = (
        "20261114: appended Slice 7 bindings for the separate New Zealand free-, zero- and fixed-null-trend "
        "MDE rows and the California LI+/OC fractional perturbations; sealed authorities retained.")
    LEDGER.write_bytes(vc.format_ledger(ledger))
    print(json.dumps({"added": len(add), "claims": len(ledger["claims"]),
                      "ledger_sha256": sha256(LEDGER)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
