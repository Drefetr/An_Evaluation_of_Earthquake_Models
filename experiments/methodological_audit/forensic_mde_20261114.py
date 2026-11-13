"""Forensic Japan MDE arithmetic and nine annual JMA blocks (14 November 2026).

Repairs the omitted 1.96 factor and the wrong denominator in the archived
Japan per-event statistics, and replaces the mislabelled "three annual fold
totals" with the nine genuine annual ``OC - EP`` joint contrast blocks stored
in ``ad5c7b19cf47d0be_forecast_findings_v1.json``.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "validation/authorities/ad5c7b19cf47d0be_forecast_findings_v1.json"
ARCHIVED = ROOT / "validation/live_results/referee_remediation_20261113/mde_expanded.json"
N_TEST = 1277
FOLD_TOTALS = (-74.75911649585487, -59.13340261235726, -87.3189732542919)


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def annual_blocks() -> list:
    data = read(AUTHORITY)
    rows = [r for r in data["annual_contrasts"]
            if r["comparison"] == "OC_EP_joint" and r["component"] == "joint_logscore"]
    rows.sort(key=lambda r: (r["fold"], r["block"]))
    if len(rows) != 9:
        raise ValueError(f"expected nine annual OC-EP joint blocks, found {len(rows)}")
    return rows


def within_fold_pooled_se(rows) -> dict:
    groups = []
    for fold in (0, 1, 2):
        values = np.asarray([r["difference_nats"] for r in rows if r["fold"] == fold], dtype=float)
        se = float(math.sqrt(len(values)) * values.std(ddof=1))
        groups.append(dict(fold=fold, blocks=int(len(values)), se_total_nats=se,
                           values=[float(v) for v in values]))
    pooled = float(math.sqrt(sum(g["se_total_nats"] ** 2 for g in groups)))
    return dict(groups=groups, se_total_nats=pooled, blocks=sum(g["blocks"] for g in groups))


def statistic(mde_total: float, n_events: float) -> dict:
    return dict(mde95_total_nats=float(mde_total),
                n_events=float(n_events),
                mde95_nats_per_event=float(mde_total / n_events),
                required_rate_perturbation=float(math.sqrt(2.0 * mde_total / n_events)))


def build(output: Path) -> dict:
    archived = read(ARCHIVED)
    per_fold = archived["japan"]["per_fold"]
    three = archived["japan"]["three_fold_sum"]
    rows = annual_blocks()
    annual = within_fold_pooled_se(rows)
    mde_annual = 1.96 * annual["se_total_nats"]
    mean_fold_events = N_TEST / 3.0
    payload = dict(
        schema="forensic_japan_mde_v1", passed=True,
        source="experiments/methodological_audit/forensic_mde_20261114.py",
        authority_sha256=sha(AUTHORITY),
        archived=dict(per_fold=per_fold, three_fold_sum=three,
                      fold_totals=list(FOLD_TOTALS)),
        repaired=dict(
            per_fold=statistic(per_fold["mde95_total_nats"], mean_fold_events),
            three_fold_sum=statistic(three["mde95_total_nats"], N_TEST),
            annual_nine_blocks=statistic(mde_annual, N_TEST),
            fold_mean_events=float(mean_fold_events)),
        arithmetic_checks=dict(
            archived_per_fold_per_event=float(per_fold["mde95_total_nats"] / mean_fold_events),
            archived_three_fold_per_event=float(three["mde95_total_nats"] / N_TEST),
            repaired_per_fold_matches_three_fold=bool(abs(
                (per_fold["mde95_total_nats"] / mean_fold_events)
                - (three["mde95_total_nats"] / N_TEST)) < 1e-12),
            three_fold_mde_over_n_equals_196_se=bool(abs(
                three["mde95_total_nats"] / N_TEST
                - 1.96 * three["se_total_nats"] / N_TEST) < 1e-12),
            archived_bug_reproduction=dict(
                omitted_factor_per_event=float(three["se_total_nats"] / N_TEST),
                wrong_per_fold_denominator=float(per_fold["mde95_total_nats"] / N_TEST),
                repaired_factor=1.96)),
        annual_blocks=[dict(fold=int(r["fold"]), block=str(r["block"]),
                            n_targets=int(r["n_targets"]),
                            difference_nats=float(r["difference_nats"]),
                            difference_nats_per_target=float(r["difference_nats_per_target"]))
                       for r in rows],
        annual_pooled=annual,
        fold_windows={0: "2016-2018", 1: "2019-2021", 2: "2022-2024"},
        note=("The three folds are three-year windows (2016-2018, 2019-2021 and 2022-2024), "
              "not three annual fold totals.  The nine annual JMA blocks are pooled by fold "
              "into the same sqrt(sum se_f^2) independent-block standard error used elsewhere."))
    write(output / "japan_mde.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/forensic_remediation_20261114")
    args = parser.parse_args()
    payload = build(args.output)
    print(json.dumps(payload["repaired"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
