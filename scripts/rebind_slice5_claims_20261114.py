#!/usr/bin/env python3
"""Rebind the three archived profiled-eta claims to the exact Slice 5 roots.

The pre-change ledger bound the manuscript displays 1.1398e-4, 1.1187e-4 and
9.2864e-5 to the archived power=12 PCHIP roots in eta_profiles.json.  The
Slice 5 audit replaces those roots with resolution-matched power=14 brentq
roots.  This script rewrites only the three typed claims and leaves every
other claim untouched.  The downstream ``verify_claims.py --write-receipts``
refreshes the compact display-custody hashes and presence records.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"
AUTHORITY = ROOT / "validation/live_results/slice5_audit_20261114/eta_profile_roots_authority.json"

UPDATES = {
    "track-b-20261112-287": ("california_fold_0", "1.1638e-4"),
    "track-b-20261112-288": ("california_fold_1", "1.1373e-4"),
    "track-b-20261112-289": ("california_fold_2", "9.2641e-5"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    spec = importlib.util.spec_from_file_location("_slice5_rebind_verify", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    ledger = json.loads(LEDGER.read_text(encoding="utf-8-sig"))
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    digest = sha256(AUTHORITY)
    updated = []
    for claim in ledger["claims"]:
        if claim["id"] not in UPDATES:
            continue
        case, display = UPDATES[claim["id"]]
        value = authority["cases"][case]["scaled"]["two_sided_95"]["profiled_eta"]
        claim.update({
            "bundled_source": AUTHORITY.relative_to(ROOT).as_posix(),
            "source_path": AUTHORITY.relative_to(ROOT).as_posix(),
            "source_sha256": digest,
            "json_pointer": f"/cases/{case}/scaled/two_sided_95/profiled_eta",
            "resolved_source_value": value,
            "display": display,
            "transformation": "decimal rounding to displayed precision",
            "json_value_kind": "numeric_scalar",
            "ledger_role": "manuscript_binding",
            "component": f"{case} profiled eta95 (power=14 exact)",
            "qualification": (
                "Resolution-matched power=14 Sobol profile with exact brentq root; "
                "supersedes the archived power=12 PCHIP value."
            ),
            "status": "source_bound",
            "binding_kind": "exact_json_pointer",
            "reconciliation_status": "verified_at_declared_granularity",
            "value": value,
        })
        claim.pop("final_display_presence", None)
        updated.append(claim["id"])
    if sorted(updated) != sorted(UPDATES):
        raise SystemExit(f"expected three claims, updated {updated}")
    LEDGER.write_bytes(vc.format_ledger(ledger))
    print(json.dumps({"updated": updated, "ledger_sha256": sha256(LEDGER),
                      "authority_sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
