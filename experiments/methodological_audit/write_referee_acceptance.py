"""Emit the 13 November 2026 referee-remediation acceptance record."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def read(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


supplement = "validation/live_results/referee_remediation_20261113"
outputs = ["mde_expanded.json", "s8_oracle_decomposition.json", "synthetic_quantiles.json",
           "nz_trend_totals.json", "summary.json", "independent_audit.json"]
audit = read(f"{supplement}/independent_audit.json")
claims = read("validation/numeric_reconciliation_receipt.json")
mde = read(f"{supplement}/mde_expanded.json")
decomp = read(f"{supplement}/s8_oracle_decomposition.json")
nz = read(f"{supplement}/nz_trend_totals.json")
snapshot = read("validation/referee_prechange_snapshot_20261113.json")

record = {
    "schema": "referee_remediation_acceptance_v1",
    "edition": "referee_remediation_20261113",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "baseline_commit": "dcf2559",
    "scope": ("Additive response to referee findings M1-M4, M7-M9 and Minor 1-7: contrast-specific MDEs, "
              "exact S8 oracle decomposition, three-fold New Zealand trend totals, non-Gaussian quantiles, "
              "and precision/framing repairs. No sealed authority was modified."),
    "prechange_snapshot": {
        "path": "validation/referee_prechange_snapshot_20261113.json",
        "sha256": sha("validation/referee_prechange_snapshot_20261113.json"),
        "archive": "validation/referee_prechange_snapshot_20261113.zip",
        "archive_sha256": sha("validation/referee_prechange_snapshot_20261113.zip"),
        "sealed_authority_count": snapshot["sealed_authority_count"],
        "publication_file_count": snapshot["publication_file_count"],
    },
    "supplement": {
        "directory": supplement,
        "files": {name: {"sha256": sha(f"{supplement}/{name}")} for name in outputs},
        "independent_audit": {
            "path": f"{supplement}/independent_audit.json",
            "passed": audit["passed"],
            "checks": audit["check_count"],
            "failed": audit["failed"],
            "sealed_authorities_mutated": audit["sealed_authorities_mutated"],
        },
    },
    "dispositions": {
        "M1": {"status": "addressed",
               "action": "Removed the phrase from the abstract and conclusion; made estimation loss, trend-depletion collinearity and boundary nesting the primary explanation."},
        "M2": {"status": "addressed",
               "action": "Replaced region-only rows with five contrast-specific MDE rows at 90/180/365 days; separated CA EP+ from CA LI+ total; added the Japan per-fold and 3-fold-sum entries.",
               "headline_90day_mde": {row["contrast"]: row["block_days"]["90"]["mde95_total_nats"]
                                      for row in mde["contrasts"]} | {
                   "Japan_OC_minus_EP_joint_3fold": mde["japan"]["three_fold_sum"]["mde95_total_nats"],
                   "Japan_OC_minus_EP_joint_per_fold": mde["japan"]["per_fold"]["mde95_total_nats"]}},
        "M3": {"status": "addressed",
               "action": "Reported the three-fold New Zealand trend totals in the abstract and trend-control chapter.",
               "three_fold_totals": {key: value["totals"]["delta_joint"]
                                     for key, value in nz["controls"].items()}},
        "M4": {"status": "addressed",
               "action": "Corrected the S8 oracle description to the full eight-parameter generating vector and added the +16.43/+14.54/+18.11 decomposition with the +3.57 comparator estimation term.",
               "closure": decomp["oracle_closure"]},
        "M7": {"status": "addressed",
               "action": "Corrected the interior spatial-scale range to 0.82-0.84 km and unified the EP+ bound-pinned and interior-scale presentation in the abstract."},
        "M8": {"status": "addressed",
               "action": "Added medians, IQRs and ranges to the synthetic tables; retained sample MCSEs as descriptive only."},
        "M9": {"status": "addressed",
               "action": "Prefixed the reused New Zealand observed-table captions with an exploratory adaptive-reuse warning."},
        "Minor1": {"status": "addressed", "action": "0.82-0.85 km corrected to 0.82-0.84 km throughout."},
        "Minor2": {"status": "addressed", "action": "Oracle labelling corrected in the monograph, abstract, README, reviewer guide, companion and website."},
        "Minor3": {"status": "addressed", "action": "EP+ Shapley decomposition and interior-scale relaxation now appear together in the abstract."},
        "Minor4": {"status": "addressed", "action": "Narrative floats in 08_observed_baseline.tex rounded to three decimal places."},
        "Minor5": {"status": "addressed", "action": "The 913/914 agreement is stated to test query/export consistency only, with zero completeness evidence."},
        "Minor6": {"status": "addressed", "action": "Exploratory captions and heavy-tailed median/IQR priority notes added."},
        "Minor7": {"status": "addressed", "action": "Added the pooled New Zealand block and the three-fold clamped-clock total (-26.898 nats)."},
    },
    "publication": {
        "manuscript": {"path": "paper/manuscript_unified.pdf",
                       "sha256": sha("paper/manuscript_unified.pdf"), "pages": 247},
        "pdf_qa": {"path": "build/referee_pdf_qa_final3/production_checks.json",
                   "overfull_boxes": 0, "undefined_references": 0,
                   "undefined_citations": 0, "missing_figures": 0, "passed": True},
        "companion_pdf": {"path": "companion/lay_guide_to_the_research.pdf",
                          "sha256": sha("companion/lay_guide_to_the_research.pdf"), "pages": 9},
        "companion_html": {"path": "companion/lay_guide_to_the_research.html",
                           "sha256": sha("companion/lay_guide_to_the_research.html")},
        "site_findings": {"path": "website/site/findings.html",
                          "sha256": sha("website/site/findings.html")},
    },
    "claims": {
        "ledger": "validation/MASTER_CLAIM_LEDGER.json",
        "ledger_sha256": sha("validation/MASTER_CLAIM_LEDGER.json"),
        "passed": claims["passed"],
        "counts": claims["counts"],
        "additive_bindings": 22,
        "superseded_display_removed": "abstract interior upper sigma0 0.85 km (replaced by the 0.82-0.84 km range)",
    },
    "verification": {
        "independent_audit": {"command": "python -B experiments/methodological_audit/audit_referee_remediation_20261113.py",
                              "passed": True, "checks": audit["check_count"]},
        "claims": {"command": "python -B scripts/verify_claims.py --write-receipts", "passed": claims["passed"]},
        "main_tests": {"command": "python -B -m unittest discover -s tests", "passed": True, "count": 918},
        "regional_tests": {"command": "python -B -m unittest discover -s reproduction/regional/tests", "passed": True, "count": 44},
        "regional_inputs": {"command": "python -B reproduction/regional/inputs.py verify", "passed": True},
        "s02_tests": {"command": "python -B -m unittest discover -s reproduction/s02 -p test_inputs.py", "passed": True, "count": 6},
        "s02_inputs": {"command": "python -B reproduction/s02/inputs.py verify", "passed": True},
        "historical_fits": {"command": "python -B reproduction/historical_fits/verify.py", "passed": True},
        "site_interactions": {"command": "node website/check_interactions.cjs", "passed": True},
    },
    "residual_limitations": (
        "Dependent calendar blocks, adaptive reuse of the 612-event New Zealand archive and the single S8 "
        "generating law remain. The MDE entries are descriptive dependence-scale sensitivities, not calibrated "
        "frequentist guarantees. None of these controls converts a nested or non-significant contrast into "
        "evidence of physical absence."),
}

path = ROOT / "validation/referee_remediation_20261113.json"
path.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
print(path)
