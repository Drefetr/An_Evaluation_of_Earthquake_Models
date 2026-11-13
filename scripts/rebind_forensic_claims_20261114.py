"""Rebind the claim-ledger rows corrected by the 14 November 2026 audit.

The ledger is a custody document, not a scientific authority.  This script
updates only the enumerated claim records whose displayed value or source
pointer changed in the forensic remediation.  It deliberately removes the old
presence binding; the subsequent ``verify_claims.py --write-receipts`` run
rebuilds the compact custody record from the edited manuscript.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"
ABLATION = ROOT / "validation/live_results/forensic_remediation_20261114/epplus_ablation.json"
ETA = ROOT / "validation/live_results/forensic_remediation_20261114/eta_profiles.json"
JAPAN = ROOT / "validation/live_results/forensic_remediation_20261114/japan_mde.json"
S8 = ROOT / "validation/live_results/forensic_remediation_20261114/s8_oracle.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve(data, pointer):
    node = data
    for part in pointer.lstrip("/").split("/") if pointer else []:
        key = part.replace("~1", "/").replace("~0", "~")
        node = node[int(key)] if isinstance(node, list) else node[key]
    return node


def main():
    ledger = read(LEDGER)
    claims = {c["id"]: c for c in ledger["claims"]}
    ablation_full = read(ABLATION)
    ablation = ablation_full["clean_ablation"]
    eta = read(ETA)
    japan = read(JAPAN)
    s8 = read(S8)
    updates = {}

    def bind(claim_id, source, pointer, display, value_lookup=None):
        data = read(source) if value_lookup is None else value_lookup
        value = resolve(data, pointer)
        updates[claim_id] = dict(source=source, pointer=pointer,
                                 display=display, value=value)

    # Ablation fold/total cells.
    ablation_cells = {
        "track-b-20261112-013": ("A3", "california_fold_0", "11.1001"),
        "track-b-20261112-014": ("A3", "california_fold_1", "3.1047"),
        "track-b-20261112-015": ("A3", "california_fold_2", "20.6032"),
        "track-b-20261112-016": ("A3", None, "34.8080"),
        "track-b-20261112-017": ("A4", "california_fold_0", "11.0546"),
        "track-b-20261112-018": ("A4", "california_fold_1", "3.1770"),
        "track-b-20261112-019": ("A4", "california_fold_2", "20.5625"),
        "track-b-20261112-020": ("A4", None, "34.7941"),
        "track-b-20261112-029": ("A7", "california_fold_0", "14.6189"),
        "track-b-20261112-030": ("A7", "california_fold_1", "30.6297"),
        "track-b-20261112-031": ("A7", "california_fold_2", "24.2986"),
        "track-b-20261112-032": ("A7", None, "69.5472"),
        "track-b-20261112-033": ("A8", "california_fold_0", "14.5777"),
        "track-b-20261112-034": ("A8", "california_fold_1", "30.6913"),
        "track-b-20261112-036": ("A8", None, "69.5514"),
        "track-b-20261112-128": ("A7", None, "69.547"),
    }
    for claim_id, (arm, case, display) in ablation_cells.items():
        pointer = (f"/clean_ablation/rows/{arm}/{case}/gain_over_EP" if case
                   else f"/clean_ablation/totals/{arm}")
        bind(claim_id, ABLATION, pointer, display, value_lookup=ablation_full)
    bind("track-b-20261112-041", ABLATION,
         "/clean_ablation/sequential_A0_A1_A2_A4_A8/2", "24.464", value_lookup=ablation_full)
    bind("track-b-20261112-043", ABLATION,
         "/clean_ablation/sequential_A0_A1_A2_A4_A8/3", "34.757", value_lookup=ablation_full)

    # California eta-profile fixed-backbone slopes and exact roots.
    scale_map = {"ell10_psi2": "ell10_psi2", "ell15_psi5": "ell15_psi5",
                 "ell20_psi5": "ell20_psi5", "ell50_psi30": "ell50_psi30"}
    for fold_index, case in enumerate(("california_fold_0", "california_fold_1",
                                       "california_fold_2")):
        for scale_index, scale in enumerate(("ell10_psi2", "ell15_psi5",
                                             "ell20_psi5", "ell50_psi30")):
            base = 251 + 12 * fold_index + 3 * scale_index
            block = eta["cases"][case]["fixed_backbone"][scale]
            bind(f"track-b-20261112-{base}", ETA,
                 f"/cases/{case}/fixed_backbone/{scale}/training_score_slope_at_zero",
                 f"{block['training_score_slope_at_zero']:.4f}", value_lookup=eta)
            bind(f"track-b-20261112-{base+1}", ETA,
                 f"/cases/{case}/fixed_backbone/{scale}/roots/two_sided_95/eta",
                 f"{block['roots']['two_sided_95']['eta']:.4e}", value_lookup=eta)
    for claim_id, case, display in (
            ("track-b-20261112-287", "california_fold_0", "1.1398e-4"),
            ("track-b-20261112-288", "california_fold_1", "1.1187e-4"),
            ("track-b-20261112-289", "california_fold_2", "9.2864e-5")):
        bind(claim_id, ETA, f"/scaled_ell15_psi5_profile/{case}/eta95_upper/eta",
             display, value_lookup=eta)
    for claim_id, case, display in (
            ("track-b-20261112-290", "california_fold_0", "-74.708"),
            ("track-b-20261112-291", "california_fold_1", "-10118.507"),
            ("track-b-20261112-292", "california_fold_2", "-27.189")):
        bind(claim_id, ETA, f"/cases/{case}/profiled_s8_scale/s8_eta_test_gain",
             display, value_lookup=eta)

    # Japan repaired arithmetic.
    for claim_id, section in (
            ("track-b-20261112-326", "per_fold"),
            ("track-b-20261112-331", "three_fold_sum"),
            ("track-b-20261112-336", "annual_nine_blocks")):
        bind(claim_id, JAPAN, f"/repaired/{section}/mde95_nats_per_event", "0.0375"
             if section != "annual_nine_blocks" else "0.0442", value_lookup=japan)
    for claim_id, section in (
            ("track-b-20261112-327", "per_fold"),
            ("track-b-20261112-332", "three_fold_sum"),
            ("track-b-20261112-337", "annual_nine_blocks")):
        bind(claim_id, JAPAN, f"/repaired/{section}/required_rate_perturbation",
             "27.4" if section != "annual_nine_blocks" else "29.8", value_lookup=japan)

    # S8 multi-start partial oracle B.
    bind("referee-20261113-014", S8, "/partial_oracle_b/gain_vs_joint_null/mean",
         "2.824", value_lookup=s8)

    updated = 0
    for claim_id, update in updates.items():
        claim = claims[claim_id]
        claim["bundled_source"] = str(update["source"].relative_to(ROOT)).replace("\\", "/")
        claim["source_path"] = claim["bundled_source"]
        claim["source_sha256"] = sha(update["source"])
        claim["json_pointer"] = update["pointer"]
        claim["resolved_source_value"] = update["value"]
        claim["value"] = update["value"]
        claim["display"] = update["display"]
        claim["transformation"] = "decimal rounding to displayed precision"
        claim["json_value_kind"] = "numeric_scalar"
        claim.pop("final_display_presence", None)
        updated += 1
    LEDGER.write_text(json.dumps(ledger, indent=1, ensure_ascii=False, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps(dict(updated=updated, ledger_sha256=sha(LEDGER)), indent=2))


if __name__ == "__main__":
    main()
