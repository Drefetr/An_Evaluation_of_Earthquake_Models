#!/usr/bin/env python3
"""Add the corrected Slice 1 visibility displays to the claim ledger.

The 14 November F6 display was not enumerated in the ledger.  This script adds
the replacement one-event and full-process statements as explicit numeric
bindings to the new audited supplement, then leaves presence refresh to
``scripts/verify_claims.py --write-receipts``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"
SOURCE = ROOT / "validation/live_results/slice1_math_audit_20261114/visibility_correction.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(data, pointer):
    node = data
    for part in pointer.lstrip("/").split("/") if pointer else []:
        key = part.replace("~1", "/").replace("~0", "~")
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node


def main() -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8-sig"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    source_hash = sha(SOURCE)
    source_relative = SOURCE.relative_to(ROOT).as_posix()
    records = [
        ("slice1-visibility-one-event-010", "/one_event_single_parent/clipped_bounds/0.1",
         "0.0015266", "chapters/04_identifiability.tex", 4,
         "One-event single-parent visibility bound at eta=0.10"),
        ("slice1-visibility-one-event-0178", "/one_event_single_parent/clipped_bounds/0.178",
         "0.0042328", "chapters/04_identifiability.tex", 4,
         "One-event single-parent visibility bound at eta=0.178"),
        ("slice1-visibility-one-event-165", "/one_event_single_parent/clipped_bounds/1.65",
         "0.1867405", "chapters/04_identifiability.tex", 4,
         "One-event single-parent visibility bound at eta=1.65"),
        ("slice1-visibility-one-event-4", "/one_event_single_parent/clipped_bounds/4.0",
         "0.7883534", "chapters/04_identifiability.tex", 4,
         "One-event single-parent visibility bound at eta=4"),
        ("slice1-visibility-one-event-threshold", "/one_event_single_parent/eta_clipped_threshold",
         "4.6419", "chapters/04_identifiability.tex", 4,
         "Eta at which the one-event clipped bound first reaches one"),
        ("slice1-visibility-K1", "/one_event_single_parent/K_1",
         "0.2416084", "chapters/04_identifiability.tex", 4,
         "Linearised one-event single-parent coefficient K_1"),
        ("slice1-visibility-sqrt-K1", "/one_event_single_parent/sqrt_K_1_over_2",
         "0.3475690", "chapters/04_identifiability.tex", 4,
         "Square root of half K_1"),
        ("slice1-visibility-abstract-010", "/one_event_single_parent/clipped_bounds/0.1",
         "1.53e-3", "abstract.tex", 4,
         "Abstract one-event visibility bound at eta=0.10"),
        ("slice1-visibility-abstract-165", "/one_event_single_parent/clipped_bounds/1.65",
         "0.1867", "abstract.tex", 4,
         "Abstract one-event visibility bound at eta=1.65"),
        ("slice1-visibility-abstract-4", "/one_event_single_parent/clipped_bounds/4.0",
         "0.7884", "abstract.tex", 4,
         "Abstract one-event visibility bound at eta=4"),
        ("slice1-visibility-abstract-threshold", "/one_event_single_parent/eta_clipped_threshold",
         "4.64", "abstract.tex", 4,
         "Abstract one-event threshold"),
    ]
    claims = ledger["claims"]
    by_id = {c["id"]: c for c in claims}
    added = 0
    for claim_id, pointer, display, location, chapter, component in records:
        record = {
            "id": claim_id,
            "chapter": chapter,
            "tex_file": location,
            "display": display,
            "value": resolve(source, pointer),
            "source_path": source_relative,
            "bundled_source": source_relative,
            "source_sha256": source_hash,
            "json_pointer": pointer,
            "transformation": "decimal rounding to displayed precision",
            "component": component,
            "comparator": "deterministic one-event quadrature on the frozen reference background",
            "denominator": "24,394-day horizon; implemented 195-mode pair; declared exponential mark law",
            "qualification": ("One-event single-parent bound; not a full-process multi-event bound. "
                              "The non-vacuous range is the one-event stratum."),
            "status": "source_bound",
            "ledger_role": "manuscript_binding",
            "binding_kind": "exact_json_pointer",
            "value_semantics": "transformed_authority_scalar",
            "json_value_kind": "numeric_scalar",
            "final_display_locations": [location],
            "reconciliation_status": "verified_at_declared_granularity",
        }
        if claim_id in by_id:
            by_id[claim_id].update(record)
            by_id[claim_id].pop("final_display_presence", None)
        else:
            claims.append(record)
            added += 1
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"added": added, "ledger_sha256": sha(LEDGER)}, indent=2))


if __name__ == "__main__":
    main()
