"""Update MASTER claim bindings for the 13 November 2026 referee remediation.

Only presentation precision and new additive bindings change.  No sealed
authority is touched.  Run ``scripts/verify_claims.py --write-receipts`` after
this script to refresh the compact display custody.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import verify_claims as V

SUPPLEMENT = ROOT / "validation/live_results/referee_remediation_20261113"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_claim(claim_id, source: Path, pointer, display, locations, component, transformation=None):
    data = read(source)
    raw = V.resolve(data, pointer)
    claim = dict(
        id=claim_id,
        bundled_source=source.relative_to(ROOT).as_posix(),
        source_path=source.relative_to(ROOT).as_posix(),
        source_sha256=sha(source),
        json_pointer=pointer,
        resolved_source_value=raw,
        display=str(display),
        transformation=transformation or "decimal rounding to displayed precision",
        json_value_kind="numeric_scalar",
        ledger_role="manuscript_binding",
        final_display_locations=list(locations),
        component=component,
        qualification=("Additive deterministic referee-remediation calculation; frozen sealed inputs and "
                       "explicit JSON pointer."),
        status="source_bound",
        binding_kind="exact_json_pointer",
        reconciliation_status="verified_at_declared_granularity",
    )
    claim["value"] = V.transformed(raw, claim, data)
    if not V.equal_display(claim["value"], claim):
        raise ValueError(("display does not round", claim_id, raw, display))
    return claim


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=ROOT / "validation/MASTER_CLAIM_LEDGER.json")
    args = parser.parse_args()
    ledger = read(args.ledger)
    claims = ledger["claims"]

    # 1. Presentation precision in 08_observed_baseline.tex.
    precision = {
        "temporal-02808": ("2.849", "Observed catalogue slope rounded for narrative prose"),
        "temporal-02976": ("0.164", "Largest matched magnitude difference rounded for prose"),
        "temporal-02978": ("-17.623", "Total shared score rounded for prose"),
        "temporal-02979": ("-17.618", "Replacement-magnitude shared score rounded for prose"),
        "temporal-02980": ("+0.005", "Replacement-magnitude score change rounded for prose"),
    }
    for claim in claims:
        if claim["id"] in precision:
            display, component = precision[claim["id"]]
            claim["display"] = display
            claim["component"] = component
            if not V.equal_display(claim["value"], claim):
                raise ValueError(("rounded display invalid", claim["id"]))

    # 2. The abstract now reports the primary (non-frozen) interior range 0.82--0.84.
    claims[:] = [c for c in claims if c["id"] != "track-b-20261112-355"]

    if any(c["id"].startswith("referee-20261113-") for c in claims):
        raise ValueError("referee claims already present")

    abstract = ["abstract.tex"]
    mde = SUPPLEMENT / "mde_expanded.json"
    nz = SUPPLEMENT / "nz_trend_totals.json"
    s8 = SUPPLEMENT / "s8_oracle_decomposition.json"
    qu = SUPPLEMENT / "synthetic_quantiles.json"
    power = ["chapters/14_power_and_mde.tex"]
    s8loc = ["chapters/13_s8_oracle.tex"]
    nzloc = ["chapters/08_nz_trend_controls.tex"]
    add = [
        (mde, "/contrasts/0/block_days/90/mde95_total_nats", "9.24", abstract + power,
         "Contrast-specific 90-day MDE for New Zealand shared attenuation"),
        (mde, "/contrasts/1/block_days/90/mde95_total_nats", "3.82", abstract + power,
         "Contrast-specific 90-day MDE for California LI+ total attenuation"),
        (mde, "/contrasts/1/block_days/90/bootstrap_halfwidth_nats", "3.27", abstract + power,
         "Pooled percentile half-width for California LI+ total attenuation"),
        (mde, "/contrasts/2/block_days/90/mde95_total_nats", "48.30", abstract + power,
         "Contrast-specific 90-day MDE for California EP+ minus EP"),
        (mde, "/contrasts/3/block_days/90/mde95_total_nats", "43.35", abstract + power,
         "Contrast-specific 90-day MDE for California OC minus EP"),
        (mde, "/japan/three_fold_sum/mde95_total_nats", "47.94", abstract + power,
         "Three-fold Japan OC minus EP sum MDE"),
        (mde, "/japan/per_fold/mde95_total_nats", "15.98", abstract + power,
         "Per-fold Japan OC minus EP MDE"),
        (mde, "/japan/observed/total_nats", "-221.212", power,
         "Japan three-fold observed total"),
        (nz, "/controls/zero_d/totals/delta_joint", "-11.431", abstract + nzloc,
         "Three-fold New Zealand zero-trend total"),
        (nz, "/controls/fixed_null_d/totals/delta_joint", "-5.006", abstract + nzloc,
         "Three-fold New Zealand fixed-null-trend total"),
        (nz, "/controls/clamped_clock/totals/delta_joint", "-26.898", nzloc,
         "Three-fold New Zealand clamped-clock counterfactual total"),
        (nz, "/fold1/clamped_clock/delta_joint", "-24.791", nzloc,
         "Fold 1 clamped-clock counterfactual total"),
        (s8, "/partial_oracle_a/gain_vs_joint_null/mean", "3.128", abstract + s8loc,
         "Partial oracle A mean gain"),
        (s8, "/partial_oracle_b/gain_vs_joint_null/mean", "2.576", abstract + s8loc,
         "Partial oracle B mean gain"),
        (s8, "/fitted_eta/mean", "0.929", abstract + s8loc,
         "Mean fitted S8 attenuation amplitude"),
        (s8, "/fitted_eta/minimum", "0.042", abstract + s8loc,
         "Minimum fitted S8 attenuation amplitude"),
        (s8, "/fitted_eta/maximum", "4.000", abstract + s8loc,
         "Maximum fitted S8 attenuation amplitude"),
        (s8, "/fitted_eta/rmse_vs_true", "1.230", s8loc,
         "RMSE of fitted S8 attenuation amplitude"),
        (s8, "/estimation_loss_fraction_of_oracle", "98.4", abstract + s8loc,
         "Estimation loss as a percentage of the oracle advantage",
         dict(operation="multiply", factor=100)),
        (qu, "/rows/20/q25", "-2.677", ['chapters/13_s08_moderate.tex'],
         "S8 raw Q25"),
        (qu, "/rows/20/q75", "6.813", ['chapters/13_s08_moderate.tex'],
         "S8 raw Q75"),
        (qu, "/rows/20/iqr", "9.49", ['chapters/13_s08_moderate.tex'],
         "S8 raw interquartile range"),
    ]
    for index, item in enumerate(add, 1):
        source, pointer, display, locations, component = item[:5]
        transformation = item[5] if len(item) > 5 else None
        claim = make_claim(f"referee-20261113-{index:03d}", source, pointer, display,
                           locations, component, transformation)
        claims.append(claim)

    ledger["current_edition"] = {
        "id": "referee_remediation_20261113",
        "baseline_commit": "dcf2559",
        "scope": ("Referee remediation: contrast-specific MDEs, exact S8 oracle decomposition, three-fold "
                  "New Zealand trend totals, non-Gaussian quantiles and precision/framing repairs; sealed "
                  "authorities unchanged."),
        "result_provenance": "docs/result_provenance.md",
        "joint_summary": "validation/live_results/s04b_joint_complete_20261111/summary.json",
        "withdrawal_registry": "validation/withdrawals/JOINT_TABLE_SUPERSESSION_20261111.json",
        "acceptance_record": "validation/referee_remediation_20261113.json",
        "track_a_acceptance": "validation/track_a_remediation_20261112.json",
        "track_b_controls": "validation/live_results/track_b_controls_20261112/",
        "referee_remediation": "validation/live_results/referee_remediation_20261113/",
    }
    ledger["closure_revision"] = (
        "20261113: appended contrast-specific MDE, S8 oracle decomposition, three-fold trend-total and "
        "quantile bindings; removed the superseded 0.85 km abstract display; sealed authorities retained.")
    args.ledger.write_text(json.dumps(ledger, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"claims": len(claims), "added": len(add)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
