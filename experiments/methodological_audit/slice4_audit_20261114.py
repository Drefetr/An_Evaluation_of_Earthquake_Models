#!/usr/bin/env python3
"""Independent Slice 4 mathematical, statistical, code, and manuscript audit.

Scope: Chapters 11 and 12, Appendices B.9-B.10, the California primary and
higher-threshold transfer tables, annual and active-sequence partitions, the
JMA reported-record cohort and nine annual blocks, the completed four-arm
spatial comparison (S03), the rolling California episode backtests and JMA
trend ablation (S06), and the 2,997-path conditional simulation calibration
(S05).

The audit re-derives every displayed scalar from the bound JSON authorities,
the stored aggregation records, and the Python implementation.  It performs
deterministic algebra, table reconstruction from the LaTeX sources, block-score
recomputation, claim-ledger resolution, and byte-level sealed-authority
verification.  It does not fit new models, simulate catalogues, or modify a
sealed authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice4_audit_20261114"
SNAPSHOT = ROOT / "validation/slice4_prechange_snapshot_20261114.json"
SNAPSHOT_ZIP = ROOT / "validation/slice4_prechange_snapshot_20261114.zip"
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"

TEX = {
    "ch11": ROOT / "paper/source/chapters/11_external_transfer_benchmarks.tex",
    "unc": ROOT / "paper/source/chapters/11_score_uncertainty.tex",
    "s03": ROOT / "paper/source/chapters/11_s03_completed.tex",
    "s06": ROOT / "paper/source/chapters/11_s06_completed.tex",
    "ch12": ROOT / "paper/source/chapters/12_conditional_calibration.tex",
    "s05": ROOT / "paper/source/chapters/12_s05_completed.tex",
    "app11": ROOT / "paper/source/appendix_tables/ch11_backup.tex",
    "app12": ROOT / "paper/source/appendix_tables/ch12_audit.tex",
}
AUTH = {
    "ca_primary": ROOT / "validation/authorities/8bffeecbd7df0918_summary.json",
    "ca_aggregates": ROOT / "validation/authorities/bf4d50b9ecefc531_aggregates.json",
    "ca_bench": ROOT / "validation/authorities/d2b5938bb99e068d_summary.json",
    "ca_m45": ROOT / "validation/authorities/e93db40b7871acc7_approved_aggregates_v1.json",
    "ca_seq": ROOT / "validation/authorities/682a9c7ecf12bc8c_approved_aggregates_v2.json",
    "ca_events": ROOT / "reproduction/nzca/expected/california_events.json",
    "jma": ROOT / "validation/authorities/ad5c7b19cf47d0be_forecast_findings_v1.json",
    "jma_expected": ROOT / "reproduction/jma/expected_summary.json",
    "jma_manifest": ROOT / "reproduction/jma/input_manifest.json",
    "jma_md": ROOT / "validation/authorities/d32887a63d3c7250_forecast_findings_v1.md",
    "s03_derived": ROOT / "validation/authorities/1210ed825946f8e7_s02_s03_derived_values.json",
    "s03_ca0": ROOT / "validation/authorities/4017c6e7ab6843d9_m02_s03_ca_0_aggregate.json",
    "s03_ca1": ROOT / "validation/authorities/5bbbb33989a2d877_m02_s03_ca_1_aggregate.json",
    "s03_ca2": ROOT / "validation/authorities/9b121a7455e9a9cd_m02_s03_ca_2_aggregate.json",
    "s03_nz0": ROOT / "validation/authorities/d03344116f577c89_m02_s03_nz_0_aggregate.json",
    "s03_nz1": ROOT / "validation/authorities/de8465f0cc4a6064_m02_s03_nz_1_aggregate.json",
    "s03_nz2": ROOT / "validation/authorities/4cf9a1c1e82fc2db_m02_s03_nz_2_aggregate.json",
    "s06": ROOT / "validation/authorities/1b543087985ae113_s06_manuscript_values.json",
    "s06_accept": ROOT / "validation/authorities/341dad668a18b4fe_s06_saved_acceptance.json",
    "s05_public": ROOT / "validation/acceptances/S05_public.json",
    "s05_replay": ROOT / "validation/acceptances/S05_independent_replay_public.json",
    "s05_closure": ROOT / "validation/acceptances/S05_CLOSURE_REVIEW.json",
    "s05_scalar": ROOT / "validation/authorities/731a4a1481fc4dee_approved_scalar_report.json",
    "unc": ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json",
    "regional_inputs": ROOT / "reproduction/regional/inputs.py",
    "spatial_code": ROOT / "engine/stage2_followup/s03_s06_spatial_benchmarks/spatial.py",
    "omnibus_code": ROOT / "engine/stage2_followup/s03_s06_spatial_benchmarks/continuous_omnibus.py",
    "campaign_code": ROOT / "engine/stage2_followup/s03_s06_spatial_benchmarks/calibration_campaign.py",
    "jma_replay": ROOT / "reproduction/jma/replay.py",
}
SLICE4_TEX_FILES = {
    "chapters/11_external_transfer_benchmarks.tex",
    "chapters/11_score_uncertainty.tex",
    "chapters/11_s03_completed.tex",
    "chapters/11_s06_completed.tex",
    "chapters/12_conditional_calibration.tex",
    "chapters/12_s05_completed.tex",
    "appendix_tables/ch11_backup.tex",
    "appendix_tables/ch12_audit.tex",
}
EXPECTED_SEALED = 749


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def dump(name: str, payload) -> str:
    path = OUT / name
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def close(a, b, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def display_ok(actual, display, decimals: int) -> bool:
    if actual is None or display is None:
        return actual is display
    return abs(float(actual) - float(display)) <= 0.5 * 10.0 ** (-decimals) + 2e-12 * max(
        1.0, abs(float(actual))
    )


def add(checks: list, cid: str, ok: bool, **detail):
    checks.append({"id": cid, "passed": bool(ok), **detail})
    return bool(ok)


def split_latex_cells(line: str) -> list[str]:
    s = line.rstrip()
    if s.endswith("\\\\"):
        s = s[:-2]
    cells: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in s:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if ch == "&" and depth == 0:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    cells.append("".join(buf).strip())
    return cells


def cell_number(cell: str):
    s = cell.strip()
    s = s.replace("$", "").replace("{", "").replace("}", "")
    s = s.replace("\\,", "").replace("\\ ", " ").replace("\\%", "%")
    s = s.replace("~", " ").replace("\\text{---}", "---")
    s = s.replace("+", "+").replace("\\pm", "")
    s = s.strip()
    if s in ("", "---", "null"):
        return None
    if s.endswith("%"):
        s = s[:-1]
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def cell_decimals(cell: str) -> int:
    s = cell.strip().replace("$", "").replace("{}", "")
    if "%" in s:
        s = s.split("%")[0].strip()
    m = re.search(r"\.(\d+)", s)
    return len(m.group(1)) if m else 0


def cell_ok(actual, cell: str, decimals: int | None = None) -> bool:
    shown = cell_number(cell)
    if shown is None:
        return actual is None
    d = cell_decimals(cell) if decimals is None else decimals
    return display_ok(actual, shown, d)


def parse_interval(cell: str):
    s = cell.replace("$", "").replace("[", "").replace("]", "").replace("~", " ")
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        raise ValueError(f"not a two-ended interval: {cell!r}")
    return float(parts[0].replace(",", "")), float(parts[1].replace(",", ""))


def table_rows(path: Path, header: str, occurrence: int = 1) -> list[list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if header in line]
    if len(hits) < occurrence:
        raise ValueError(f"table header not found: {header!r} in {path.name}")
    start = hits[occurrence - 1]
    rows: list[list[str]] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if "\\end{longtable}" in stripped or "\\end{tabular}" in stripped:
            break
        if stripped.startswith("\\"):
            continue
        if "&" not in line or header in line:
            continue
        rows.append(split_latex_cells(line))
    return rows


def component_head(schema: str, scope: str, checks: list[dict], counts: dict, notes: list[str] | None = None):
    return {
        "schema": schema,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "passed": all(c["passed"] for c in checks),
        "counts": counts,
        "checks": checks,
        "notes": notes or [],
    }


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def year_of(event: dict) -> int:
    return int(event["origin_time_utc"][:4])


# ---------------------------------------------------------------------------
# 1. Sealed-authority integrity
# ---------------------------------------------------------------------------


def audit_sealed_integrity() -> dict:
    record = load(SNAPSHOT)
    sealed = record["sealed_json"]
    changed, missing = [], []
    for relative, expected in sealed.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path) != expected:
            changed.append({"path": relative, "expected": expected, "actual": sha256(path)})
    checks: list[dict] = []
    add(
        checks,
        "sealed-count",
        record["sealed_json_count"] == EXPECTED_SEALED == len(sealed),
        expected=EXPECTED_SEALED,
        actual=record["sealed_json_count"],
    )
    add(checks, "sealed-missing", not missing, missing=missing)
    add(checks, "sealed-changed", not changed, changed=changed)
    payload = component_head(
        "slice4_sealed_authority_integrity_v1",
        "Byte-level identity of every pre-existing JSON file under validation/authorities and "
        "validation/live_results plus the Slice 3 acceptance record.",
        checks,
        {
            "snapshot": len(sealed),
            "unchanged": len(sealed) - len(missing) - len(changed),
            "changed": len(changed),
            "missing": len(missing),
            "baseline_commit": record["baseline_commit"],
            "snapshot_sha256": sha256(SNAPSHOT),
            "prechange_zip_sha256": sha256(SNAPSHOT_ZIP),
        },
        notes=[record["scope"]],
    )
    dump("sealed_authority_integrity.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 2. California primary transfer, benchmarks, and block uncertainty
# ---------------------------------------------------------------------------


def audit_california_primary() -> dict:
    checks: list[dict] = []
    counts: dict = {}

    events = load(AUTH["ca_events"])
    m45 = [e for e in events if e["magnitude"] >= 4.5]
    add(checks, "cohort-total", len(events) == 1272, actual=len(events))
    add(checks, "cohort-unique", len({e["event_id"] for e in events}) == len(events))
    add(checks, "cohort-magnitude", all(e["magnitude"] >= 4.0 for e in events) and min(e["magnitude"] for e in events) == 4.0)
    add(checks, "cohort-domain", all(32.0 <= e["latitude"] <= 37.0 and -121.0 <= e["longitude"] <= -114.0 and -5.0 <= e["depth_km"] <= 40.0 for e in events))
    add(checks, "cohort-event-type", all(e["event_type"] == "eq" for e in events))
    add(checks, "cohort-warmup", sum(1 for e in events if 1981 <= year_of(e) <= 1985) == 106)
    add(checks, "cohort-training-0", sum(1 for e in events if 1986 <= year_of(e) < 2011) == 851)
    add(checks, "cohort-training-1", sum(1 for e in events if 1986 <= year_of(e) < 2016) == 930)
    add(checks, "cohort-training-2", sum(1 for e in events if 1986 <= year_of(e) < 2021) == 1097)
    test = [
        sum(1 for e in events if 2011 <= year_of(e) < 2016),
        sum(1 for e in events if 2016 <= year_of(e) < 2021),
        sum(1 for e in events if 2021 <= year_of(e) < 2026),
    ]
    add(checks, "cohort-test-windows", test == [79, 167, 69], actual=test)
    add(checks, "cohort-test-total", sum(test) == 315)
    add(checks, "m45-population", len(m45) == 391, actual=len(m45))
    add(checks, "m45-warmup", sum(1 for e in m45 if 1981 <= year_of(e) <= 1985) == 33)
    m45_train = [
        sum(1 for e in m45 if 1986 <= year_of(e) < 2011),
        sum(1 for e in m45 if 1986 <= year_of(e) < 2016),
        sum(1 for e in m45 if 1986 <= year_of(e) < 2021),
    ]
    m45_test = [
        sum(1 for e in m45 if 2011 <= year_of(e) < 2016),
        sum(1 for e in m45 if 2016 <= year_of(e) < 2021),
        sum(1 for e in m45 if 2021 <= year_of(e) < 2026),
    ]
    add(checks, "m45-training", m45_train == [271, 287, 340], actual=m45_train)
    add(checks, "m45-test", m45_test == [16, 53, 18], actual=m45_test)
    add(checks, "m45-total", sum(m45_test) == 87)

    agg = load(AUTH["ca_aggregates"])
    folds = {(c["contrast_id"], c["fold_id"]): c for c in agg["fold_contrasts"]}
    pooled = {c["contrast_id"]: c for c in agg["pooled_contrasts"]}
    primary_rows = [
        (0, 79, 0.099084, 0.001254, 91.803255, 1.162067),
        (1, 167, 32.722878, 0.195945, 465.829993, 2.789401),
        (2, 69, 4.968377, 0.072005, 116.690274, 1.691163),
    ]
    for fold, targets, tim, tim_per, loc, loc_per in primary_rows:
        t = folds[("timing_OC_minus_fixedML", fold)]
        l = folds[("location_OC_minus_OL", fold)]
        add(checks, f"primary-targets-f{fold}", t["target_count"] == l["target_count"] == targets, actual=t["target_count"])
        add(checks, f"primary-timing-f{fold}", display_ok(t["timing_logscore"], tim, 6), actual=t["timing_logscore"])
        add(checks, f"primary-timing-per-f{fold}", display_ok(t["timing_logscore"] / targets, tim_per, 6))
        add(checks, f"primary-location-f{fold}", display_ok(l["conditional_location_logscore"], loc, 6), actual=l["conditional_location_logscore"])
        add(checks, f"primary-location-per-f{fold}", display_ok(l["conditional_location_logscore"] / targets, loc_per, 6))
        add(checks, f"primary-joint-identity-f{fold}", close(t["joint_logscore"], t["timing_logscore"] + t["conditional_location_logscore"] + t["mark_logscore"], 1e-12))
    tpool = pooled["timing_OC_minus_fixedML"]
    lpool = pooled["location_OC_minus_OL"]
    add(checks, "primary-pooled-targets", tpool["target_count"] == lpool["target_count"] == 315)
    add(checks, "primary-pooled-timing", display_ok(tpool["timing_logscore"], 37.790339, 6), actual=tpool["timing_logscore"])
    add(checks, "primary-pooled-timing-per", display_ok(tpool["timing_logscore"] / 315, 0.119969, 6))
    add(checks, "primary-pooled-location", display_ok(lpool["conditional_location_logscore"], 674.323522, 6), actual=lpool["conditional_location_logscore"])
    add(checks, "primary-pooled-location-per", display_ok(lpool["conditional_location_logscore"] / 315, 2.140710, 6))
    add(
        checks,
        "primary-fold-sums",
        close(sum(folds[("timing_OC_minus_fixedML", f)]["timing_logscore"] for f in range(3)), tpool["timing_logscore"], 1e-12)
        and close(sum(folds[("location_OC_minus_OL", f)]["conditional_location_logscore"] for f in range(3)), lpool["conditional_location_logscore"], 1e-12),
    )
    share = lpool["within_cell_density_logscore"] / lpool["conditional_location_logscore"]
    add(checks, "location-within-share", round(100 * share, 3) == 96.927, actual=100 * share)
    add(
        checks,
        "location-decomposition",
        close(
            lpool["conditional_zone_logscore"] + lpool["conditional_cell_logscore"] + lpool["within_cell_density_logscore"],
            lpool["conditional_location_logscore"],
            1e-12,
        ),
    )
    add(checks, "location-zone", display_ok(lpool["conditional_zone_logscore"], 17.206741, 6), actual=lpool["conditional_zone_logscore"])
    add(checks, "location-cell", display_ok(lpool["conditional_cell_logscore"], 3.514553, 6), actual=lpool["conditional_cell_logscore"])
    add(checks, "location-within", display_ok(lpool["within_cell_density_logscore"], 653.602228, 6), actual=lpool["within_cell_density_logscore"])
    add(
        checks,
        "timing-decomposition",
        close(tpool["event_ground_log"] + tpool["exposure_contrast"], tpool["timing_logscore"], 1e-12),
    )
    add(checks, "timing-event-ground", display_ok(tpool["event_ground_log"], 40.898879, 6))
    add(checks, "timing-exposure", display_ok(tpool["exposure_contrast"], -3.108539, 6))
    add(checks, "timing-middle-share", round(100 * folds[("timing_OC_minus_fixedML", 1)]["timing_logscore"] / tpool["timing_logscore"], 1) == 86.6)

    primary = load(AUTH["ca_primary"])
    comp = {c["id"]: c for c in primary["comparisons"]}
    context = [
        ("context_freeML", 21.177884396423565, 0.06723137903626529),
        ("context_fixedML_spatial", 671.2443401348418, 2.130934413126482),
        ("complete_procedure", 747.8000205904509, 2.373968319334765),
    ]
    for cid, total, per in context:
        c = comp[cid]
        add(checks, f"{cid}-total", close(c["primary_delta_nats"], total, 1e-12), actual=c["primary_delta_nats"])
        add(checks, f"{cid}-per-target", close(c["primary_delta_nats_per_event"], per, 1e-12))
        add(checks, f"{cid}-positive-windows", c["positive_windows"] == 3 and all(x > 0 for x in c["window_deltas_nats"]))
        add(checks, f"{cid}-primary-component", c["status"] == "complete" and c["complete_windows"] == 3 and c["n_test"] == 315)
    cases = primary["cases"]
    add(checks, "primary-cases-train", [c["n_train"] for c in cases] == [851, 930, 1097])
    add(checks, "primary-cases-test", [c["n_test"] for c in cases] == [79, 167, 69])
    add(checks, "primary-bandwidth", all(c["selected_bandwidth_km"] == 5.0 for c in cases))
    add(checks, "primary-sigma", all(c["selected_sigma_km"] == 5.0 for c in cases))
    add(checks, "primary-independent-audit", primary["independent_audit"]["passed"] is True and primary["independent_audit"]["independent"] is True)

    bench = load(AUTH["ca_bench"])
    n0 = bench["contrasts"]["OC_minus_N0"]
    ep = bench["contrasts"]["OC_minus_EP"]
    n0s = n0["pooled_sum"]
    eps = ep["pooled_sum"]
    add(checks, "oc-n0-joint", display_ok(n0s["joint_logscore"], 1694.942967, 6), actual=n0s["joint_logscore"])
    add(checks, "oc-n0-timing", display_ok(n0s["timing_logscore"], 894.846, 3))
    add(checks, "oc-n0-location", display_ok(n0s["conditional_location_logscore"], 800.097, 3))
    add(checks, "oc-n0-joint-per", display_ok(n0s["joint_logscore"] / 315, 5.38077, 5))
    add(checks, "oc-n0-point", display_ok(n0s["event_log_point_intensity_sum"], 1612.690857, 6))
    add(checks, "oc-n0-compensator", display_ok(n0s["compensator_contribution"], 82.252111, 6))
    add(checks, "oc-n0-middle-share", display_ok(n0["middle_window_joint_share"], 0.774896, 6), actual=n0["middle_window_joint_share"])
    add(checks, "oc-n0-all-positive", all(w["joint_logscore"] > 0 and w["timing_logscore"] > 0 and w["conditional_location_logscore"] > 0 for w in n0["by_window"]))
    add(checks, "oc-ep-joint", display_ok(eps["joint_logscore"], -51.051205, 6), actual=eps["joint_logscore"])
    add(checks, "oc-ep-timing", display_ok(eps["timing_logscore"], 0.33625, 5))
    add(checks, "oc-ep-location", display_ok(eps["conditional_location_logscore"], -51.3875, 4))
    add(checks, "oc-ep-joint-per", display_ok(eps["joint_logscore"] / 315, -0.162067, 6))
    add(checks, "oc-ep-point", display_ok(eps["event_log_point_intensity_sum"], -54.591677, 6))
    add(checks, "oc-ep-compensator", display_ok(eps["compensator_contribution"], 3.540472, 6))
    add(checks, "oc-ep-timing-per", display_ok(eps["timing_logscore"] / 315, 0.001067, 6))
    fold_joint = [w["joint_logscore"] for w in ep["by_window"]]
    add(checks, "oc-ep-folds", all(display_ok(a, b, 6) for a, b in zip(fold_joint, [-6.288819, -31.742512, -13.019873])), actual=fold_joint)
    add(checks, "oc-ep-location-negative", all(w["conditional_location_logscore"] < 0 for w in ep["by_window"]))
    add(checks, "oc-ep-sum", close(n0s["event_log_point_intensity_sum"] + n0s["compensator_contribution"], n0s["joint_logscore"], 1e-12) and close(eps["event_log_point_intensity_sum"] + eps["compensator_contribution"], eps["joint_logscore"], 1e-12))

    unc = load(AUTH["unc"])
    rows = [r for r in unc["rows"] if r["contrast"] == "CA_OC_minus_EP"]
    expected = {
        "california_fold_0": (-6.288819096855438, -21.789978121010787, 3.2964251664021624, 0.57656, 21),
        "california_fold_1": (-31.742512448765165, -77.22884198605333, -3.991330163761346, 0.02558, 21),
        "california_fold_2": (-13.019873217436958, -22.823047628682982, -4.860972590339671, 0.00366, 21),
    }
    seen = set()
    for r in rows:
        total, lo, hi, p, blocks = expected[r["case"]]
        s = r["summary"]
        add(checks, f"unc-row-{r['case']}", close(s["total"], total, 1e-12) and close(s["ci95_total"][0], lo, 1e-12) and close(s["ci95_total"][1], hi, 1e-12) and close(s["paired_sign_permutation_p"], p, 1e-12) and s["blocks"] == blocks)
        seen.add(r["case"])
    add(checks, "unc-rows-complete", seen == set(expected))
    add(checks, "unc-row-sum", close(sum(r["summary"]["total"] for r in rows), unc["pooled"]["CA_OC_minus_EP"]["total"], 1e-12))
    p = unc["pooled"]["CA_OC_minus_EP"]
    add(checks, "unc-pooled", display_ok(p["total"], -51.051, 3) and close(p["ci95_total"][0], -99.93007657992813, 1e-12) and close(p["ci95_total"][1], -17.263597650041202, 1e-12) and close(p["paired_sign_permutation_p"], 0.00018, 1e-12) and p["blocks"] == 63)
    for days, lo, hi, pv in (("180", -96.89382414791918, -16.99878871150697, 0.00130), ("365", -93.18752961367102, -17.25709555997066, 0.00726)):
        q = unc["sensitivity"][days]["pooled"]["CA_OC_minus_EP"]
        add(checks, f"unc-pooled-{days}", display_ok(q["total"], -51.051, 3) and close(q["ci95_total"][0], lo, 1e-12) and close(q["ci95_total"][1], hi, 1e-12) and close(q["paired_sign_permutation_p"], pv, 1e-12))
    loc = unc["pooled"]["CA_OC_minus_EP_location"]
    add(checks, "unc-location", display_ok(loc["total"], -51.387, 3) and close(loc["ci95_total"][0], -98.56659842130466, 1e-12) and close(loc["ci95_total"][1], -18.423255446648515, 1e-12) and close(loc["paired_sign_permutation_p"], 0.00006, 1e-12))

    counts.update(
        {
            "cohort_records": len(events),
            "warmup_records": 106,
            "training_counts": [851, 930, 1097],
            "test_counts": test,
            "m45_training": m45_train,
            "m45_test": m45_test,
            "primary_rows": 3,
            "uncertainty_rows": len(rows),
            "within_cell_share_pct": 100 * share,
        }
    )
    payload = component_head(
        "slice4_california_primary_v1",
        "California cohort reconstruction, primary score table, within-cell decomposition, N0/EP benchmarks, and paired calendar-block uncertainty.",
        checks,
        counts,
    )
    dump("california_primary.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 3. California higher threshold, annual partition, and active sequence
# ---------------------------------------------------------------------------


def _labelled_days(duration_us: float) -> float:
    return float(duration_us) / 86_400_000_000.0


def audit_california_threshold_annual_sequence() -> dict:
    checks: list[dict] = []
    counts: dict = {}

    m45 = load(AUTH["ca_m45"])
    planned = m45["planned_denominators"]
    reached = m45["reached_denominators"]
    add(checks, "m45-planned-population", planned["population"] == 391 and planned["warmup"] == 33)
    add(checks, "m45-planned-training", planned["training"] == [271, 287, 340])
    add(checks, "m45-planned-targets", planned["targets"] == [16, 53, 18] and planned["total_targets"] == 87)
    add(checks, "m45-planned-roster", planned["procedures"] == 30 and planned["starts"] == 240 and planned["floors"] == 33 and planned["candidate_slots"] == 273 and planned["model_window_statuses"] == 15 and planned["primary_arm_windows"] == 12 and planned["contrast_windows"] == 9)
    add(checks, "m45-reached", reached == {"procedures": 30, "starts": 240, "floors": 33, "candidates": 273, "finite_solver_returns": 240, "model_statuses": 15, "primary_windows": 12})
    add(checks, "m45-score-audit", close(m45["numerical_audit"]["maximum_absolute_score_error"], 1.1226575225009583e-11, 1e-15) and m45["numerical_audit"]["score_absolute_tolerance"] == 1e-4)

    contr = {(c["contrast_id"], c["fold_id"]): c for c in m45["contrasts"]}
    expected_folds = {
        ("timing_OC_minus_fixedML", 0): (16, 0.07796838957069951, 0.00487302434816872),
        ("timing_OC_minus_fixedML", 1): (53, 11.741292701665895, 0.22153382455973386),
        ("timing_OC_minus_fixedML", 2): (18, 1.4301624001220432, 0.07945346667344684),
        ("location_OC_minus_OL", 0): (16, 36.07569174377883, 2.254730733986177),
        ("location_OC_minus_OL", 1): (53, 122.87053288532013, 2.318311941232455),
        ("location_OC_minus_OL", 2): (18, 25.8302446442581, 1.4350135913476723),
        ("joint_OC_minus_commonML", 0): (16, -0.6263476155539252, -0.03914672597212032),
        ("joint_OC_minus_commonML", 1): (53, 6.141657423232687, 0.11588032874023937),
        ("joint_OC_minus_commonML", 2): (18, 1.2287875674580846, 0.06826597596989359),
    }
    for (cid, fold), (targets, total, per) in expected_folds.items():
        c = contr[(cid, fold)]
        add(checks, f"m45-{cid}-f{fold}", c["target_count"] == targets and close(c["components"][{"timing_OC_minus_fixedML": "timing_logscore", "location_OC_minus_OL": "conditional_location_logscore", "joint_OC_minus_commonML": "joint_logscore"}[cid]], total, 1e-12) and close(c["nats_per_target"][{"timing_OC_minus_fixedML": "timing_logscore", "location_OC_minus_OL": "conditional_location_logscore", "joint_OC_minus_commonML": "joint_logscore"}[cid]], per, 1e-12))

    pooled = {c["contrast_id"]: c for c in m45["pooled_contrasts"]}
    add(checks, "m45-pooled-timing", display_ok(pooled["timing_OC_minus_fixedML"]["components"]["timing_logscore"], 13.2494, 4) and display_ok(pooled["timing_OC_minus_fixedML"]["nats_per_target"]["timing_logscore"], 0.152292, 6))
    add(checks, "m45-pooled-location", display_ok(pooled["location_OC_minus_OL"]["components"]["conditional_location_logscore"], 184.776, 3) and display_ok(pooled["location_OC_minus_OL"]["nats_per_target"]["conditional_location_logscore"], 2.12387, 5))
    add(checks, "m45-pooled-joint", display_ok(pooled["joint_OC_minus_commonML"]["components"]["joint_logscore"], 6.7441, 4) and display_ok(pooled["joint_OC_minus_commonML"]["nats_per_target"]["joint_logscore"], 0.0775184, 7))
    loc = pooled["location_OC_minus_OL"]["components"]
    share = loc["within_cell_density_logscore"] / loc["conditional_location_logscore"]
    add(checks, "m45-within-share", round(100 * share, 3) == 95.479, actual=100 * share)
    add(checks, "m45-location-parts", close(loc["conditional_zone_logscore"], 5.881780957377028, 1e-12) and close(loc["conditional_cell_logscore"], 2.4721204191276342, 1e-12) and close(loc["within_cell_density_logscore"], 176.42256789685246, 1e-12))
    tim = pooled["timing_OC_minus_fixedML"]["components"]
    add(checks, "m45-timing-parts", close(tim["event_ground_log"], 14.762895280772785, 1e-12) and close(tim["integrated_intensity"], 1.5134717894141545, 1e-12) and close(tim["event_ground_log"] - tim["integrated_intensity"], tim["timing_logscore"], 1e-12))
    jnt = pooled["joint_OC_minus_commonML"]["components"]
    add(checks, "m45-joint-parts", close(jnt["timing_logscore"], 5.99289718889089, 1e-12) and close(jnt["conditional_location_logscore"], 0.7512001862458533, 1e-12))

    # Higher-threshold annual table (display reconstruction).
    annual_m45 = {(c["block_id"].rsplit("__year_", 1)[1], c["contrast_id"]): c for c in m45["annual"]["contrast_blocks"]}
    rows = [r for r in table_rows(TEX["app11"], "{}UTC year & Targets & Timing versus fixedML & Location versus Omori lift & Joint versus commonML") if r[0].strip() not in ("UTC year",)]
    add(checks, "m45-annual-row-count", len(rows) == 15, actual=len(rows))
    for r in rows:
        year = r[0].replace("{}", "").strip()
        t = annual_m45[(year, "timing_OC_minus_fixedML")]
        l = annual_m45[(year, "location_OC_minus_OL")]
        j = annual_m45[(year, "joint_OC_minus_commonML")]
        cid = f"m45-annual-{year}"
        add(checks, cid, int(r[1]) == t["target_count"] and cell_ok(t["components"]["timing_logscore"], r[2]) and cell_ok(l["components"]["conditional_location_logscore"], r[3]) and cell_ok(j["components"]["joint_logscore"], r[4]), target=int(r[1]))
    add(checks, "m45-annual-target-sum", sum(annual_m45[(f"{y}", "timing_OC_minus_fixedML")]["target_count"] for y in range(2011, 2026)) == 87)
    add(checks, "m45-annual-sums", all(close(sum(annual_m45[(str(y), cid)]["components"][comp] for y in range(2011, 2026)), pooled[cid]["components"][comp], 1e-11) for cid, comp in (("timing_OC_minus_fixedML", "timing_logscore"), ("location_OC_minus_OL", "conditional_location_logscore"), ("joint_OC_minus_commonML", "joint_logscore"))))
    add(checks, "m45-zero-target-2015", annual_m45[("2015", "timing_OC_minus_fixedML")]["target_count"] == 0 and close(annual_m45[("2015", "timing_OC_minus_fixedML")]["components"]["timing_logscore"], -0.18665083250339976, 1e-12) and annual_m45[("2015", "location_OC_minus_OL")]["components"]["conditional_location_logscore"] == 0.0)
    add(checks, "m45-zero-target-2017", annual_m45[("2017", "timing_OC_minus_fixedML")]["target_count"] == 0 and close(annual_m45[("2017", "timing_OC_minus_fixedML")]["components"]["timing_logscore"], -0.10272675533758147, 1e-12))
    neg = sum(1 for y in range(2011, 2026) if annual_m45[(str(y), "timing_OC_minus_fixedML")]["components"]["timing_logscore"] < 0)
    add(checks, "m45-negative-timing-years", neg == 10, actual=neg)
    y2019 = annual_m45[("2019", "timing_OC_minus_fixedML")]
    add(checks, "m45-2019", y2019["target_count"] == 37 and display_ok(y2019["components"]["timing_logscore"], 10.977080, 6) and display_ok(annual_m45[("2019", "location_OC_minus_OL")]["components"]["conditional_location_logscore"], 112.007721, 6) and display_ok(annual_m45[("2019", "joint_OC_minus_commonML")]["components"]["joint_logscore"], 5.288450, 6))

    # Base annual table and 2019 concentration shares.
    agg = load(AUTH["ca_aggregates"])
    annual_m4 = {(c["block_id"].rsplit("__year_", 1)[1], c["contrast_id"]): c for c in agg["annual_contrasts"]}
    rows = [r for r in table_rows(TEX["app11"], "{}UTC year & Targets & Timing vs fixedML & Location vs Omori lift & Joint vs commonML") if r[0].strip() not in ("UTC year",)]
    add(checks, "m4-annual-row-count", len(rows) == 15, actual=len(rows))
    for r in rows:
        year = r[0].replace("{}", "").strip()
        t = annual_m4[(year, "timing_OC_minus_fixedML")]
        l = annual_m4[(year, "location_OC_minus_OL")]
        j = annual_m4[(year, "joint_OC_minus_commonML")]
        add(checks, f"m4-annual-{year}", int(r[1]) == t["target_count"] and cell_ok(t["timing_logscore"], r[2]) and cell_ok(l["conditional_location_logscore"], r[3]) and cell_ok(j["joint_logscore"], r[4]), target=int(r[1]))
    add(checks, "m4-annual-target-sum", sum(annual_m4[(str(y), "timing_OC_minus_fixedML")]["target_count"] for y in range(2011, 2026)) == 315)
    pooled_m4 = {c["contrast_id"]: c for c in agg["pooled_contrasts"]}
    add(checks, "m4-annual-sums", all(close(sum(annual_m4[(str(y), cid)][comp] for y in range(2011, 2026)), pooled_m4[cid][comp], 1e-11) for cid, comp in (("timing_OC_minus_fixedML", "timing_logscore"), ("location_OC_minus_OL", "conditional_location_logscore"), ("joint_OC_minus_commonML", "joint_logscore"))))
    y19_t = annual_m4[("2019", "timing_OC_minus_fixedML")]["timing_logscore"]
    y19_l = annual_m4[("2019", "location_OC_minus_OL")]["conditional_location_logscore"]
    y19_j = annual_m4[("2019", "joint_OC_minus_commonML")]["joint_logscore"]
    add(checks, "m4-2019-targets", annual_m4[("2019", "timing_OC_minus_fixedML")]["target_count"] == 116)
    add(checks, "m4-2019-timing", display_ok(y19_t, 29.280597, 6) and display_ok(100 * y19_t / pooled_m4["timing_OC_minus_fixedML"]["timing_logscore"], 77.48, 2))
    add(checks, "m4-2019-location", display_ok(y19_l, 392.773429, 6) and display_ok(100 * y19_l / pooled_m4["location_OC_minus_OL"]["conditional_location_logscore"], 58.247, 3))
    add(checks, "m4-2019-joint", display_ok(y19_j, 7.979400, 6) and display_ok(100 * y19_j / pooled_m4["joint_OC_minus_commonML"]["joint_logscore"], 37.678, 3))

    # Displayed base-window table and pooled comparison table.
    rows = [r for r in table_rows(TEX["app11"], "{}UTC window & Targets & Timing vs fixedML, nats (per target)") if r[0].strip() != "UTC window"]
    for r, fold in zip(rows, range(3)):
        t = next(c for c in agg["fold_contrasts"] if c["contrast_id"] == "timing_OC_minus_fixedML" and c["fold_id"] == fold)
        l = next(c for c in agg["fold_contrasts"] if c["contrast_id"] == "location_OC_minus_OL" and c["fold_id"] == fold)
        j = next(c for c in agg["fold_contrasts"] if c["contrast_id"] == "joint_OC_minus_commonML" and c["fold_id"] == fold)
        add(checks, f"m4-window-row-f{fold}", int(r[1]) == t["target_count"] and cell_ok(t["timing_logscore"], r[2].split("(")[0]) and cell_ok(l["conditional_location_logscore"], r[3].split("(")[0]) and cell_ok(j["joint_logscore"], r[4].split("(")[0]))

    rows = [r for r in table_rows(TEX["app11"], "{}Declared comparison & Original M4 nats (per 315 targets)") if r[0].strip() != "Declared comparison"]
    expected_pairs = [
        (pooled_m4["timing_OC_minus_fixedML"]["timing_logscore"], 0.119969, pooled["timing_OC_minus_fixedML"]["components"]["timing_logscore"], 0.152292),
        (pooled_m4["location_OC_minus_OL"]["conditional_location_logscore"], 2.140710, pooled["location_OC_minus_OL"]["components"]["conditional_location_logscore"], 2.123867),
        (pooled_m4["joint_OC_minus_commonML"]["joint_logscore"], 0.067231, pooled["joint_OC_minus_commonML"]["components"]["joint_logscore"], 0.077518),
    ]
    for r, (m4_total, m4_per, m45_total, m45_per) in zip(rows, expected_pairs):
        a = r[1].split("(")
        b = r[2].split("(")
        add(checks, f"pooled-compare-{r[0].replace('{}','').strip()[:8]}", cell_ok(m4_total, a[0]) and cell_ok(m4_per, a[1].rstrip(")")) and cell_ok(m45_total, b[0]) and cell_ok(m45_per, b[1].rstrip(")")))

    # Sequence partition authority.
    seq = load(AUTH["ca_seq"])
    rowmap = {(r["arm"], r["range"], r["category"]): r for r in seq["rows"]}
    cmap = {(c["candidate"], c["reference"], c["range"], c["category"]): c for c in seq["contrasts"]}
    add(checks, "sequence-counts", len(seq["rows"]) == 80 and len(seq["contrasts"]) == 64 and seq["planned_targets"] == 315 and seq["selected_states"] == 15)
    add(checks, "sequence-metadata", seq["partition_metadata"]["anchor_count"] == 13 and seq["partition_metadata"]["episode_count"] == 10 and seq["partition_metadata"]["ridgecrest_episode_number"] == 9 and seq["partition_metadata"]["ridgecrest_status"] == "unique")
    active = rowmap[("Omori_smooth_cont", "pooled", "active_period")]
    complement = rowmap[("Omori_smooth_cont", "pooled", "complement_period")]
    total = cmap[("Omori_smooth_cont", "fixedML_smooth_cont", "pooled", "total")]
    active_contrast = cmap[("Omori_smooth_cont", "fixedML_smooth_cont", "pooled", "active_period")]
    complement_contrast = cmap[("Omori_smooth_cont", "fixedML_smooth_cont", "pooled", "complement_period")]
    add(checks, "sequence-active-count", active["n_target"] == 110 and _labelled_days(active["duration_microseconds"]) >= 31.406991203)
    add(checks, "sequence-active-days", display_ok(_labelled_days(active["duration_microseconds"]), 31.406991204, 9))
    add(checks, "sequence-active-duration-exact", active["duration_microseconds"] == 2713564040000)
    add(checks, "sequence-complement-count", complement["n_target"] == 205)
    add(checks, "sequence-complement-days", display_ok(_labelled_days(complement["duration_microseconds"]), 5447.593008796, 9))
    add(checks, "sequence-total", total["n_target"] == 315 and active["n_target"] + complement["n_target"] == 315)
    active_share = active_contrast["timing"] / total["timing"]
    add(checks, "sequence-active-timing-share", round(100 * active_share, 2) == 79.54, actual=100 * active_share)
    add(checks, "sequence-active-timing", display_ok(active_contrast["timing"], 30.058155, 6) and display_ok(complement_contrast["timing"], 7.73218, 5))
    ocep_active = cmap[("Omori_smooth_cont", "EP", "pooled", "active_period")]
    ocep_comp = cmap[("Omori_smooth_cont", "EP", "pooled", "complement_period")]
    add(checks, "sequence-oc-ep-partition", close(ocep_active["joint"], -18.372230094628264, 1e-12) and close(ocep_comp["joint"], -32.67897466843033, 1e-12) and close(ocep_active["joint"] + ocep_comp["joint"], -51.05120476305865, 1e-12))
    add(checks, "sequence-oc-ep-active-parts", close(ocep_active["timing"], -0.8066828260601255, 1e-12) and close(ocep_active["conditional_location"], -17.56554726856814, 1e-12))
    add(checks, "sequence-oc-ep-complement-parts", close(ocep_comp["timing"], 1.1429323513087866, 1e-12) and close(ocep_comp["conditional_location"], -33.82190701973923, 1e-12))
    cal_comp_t = cmap[("Omori_smooth_cont", "fixedML_smooth_cont", "calendar_2019", "complement_period")]
    cal_comp_j = cmap[("Omori_smooth_cont", "commonML_smooth_cont", "calendar_2019", "complement_period")]
    add(checks, "sequence-calendar-complement", cal_comp_t["n_target"] == 6 and display_ok(cal_comp_t["timing"], -0.777558, 6) and display_ok(cal_comp_j["joint"], -1.898745, 6))
    add(checks, "sequence-2019-total", cmap[("Omori_smooth_cont", "fixedML_smooth_cont", "calendar_2019", "total")]["n_target"] == 116)
    add(checks, "sequence-active-zero-rows", all(rowmap[(arm, "fold_0", "active_period")]["n_target"] == 0 and rowmap[(arm, "fold_0", "active_period")]["timing"] == 0.0 and rowmap[(arm, "fold_0", "active_period")]["joint"] == 0.0 for arm in ("Omori_smooth_cont", "EP", "fixedML_smooth_cont", "Omori_smooth_lift", "commonML_smooth_cont")) and all(rowmap[(arm, "fold_2", "active_period")]["n_target"] == 0 for arm in ("Omori_smooth_cont", "EP", "fixedML_smooth_cont", "Omori_smooth_lift", "commonML_smooth_cont")))
    add(checks, "sequence-audit-error", display_ok(float(seq["maximum_absolute_discrepancy"]) / 1e-13, 4.55, 2), actual=seq["maximum_absolute_discrepancy"])

    # Displayed sequence tables.
    counts_rows = [r for r in table_rows(TEX["app11"], "{}Reporting range / category & Targets & Anchor targets & Exposure days") if r[0].strip() != "Reporting range / category"]
    add(checks, "sequence-count-table-rows", len(counts_rows) == 16, actual=len(counts_rows))
    range_map = {"2011-2016": "fold_0", "2016-2021": "fold_1", "2021-2026": "fold_2", "Calendar 2019": "calendar_2019", "Pooled 2011-2026": "pooled"}
    cat_map = {"Active": "active_period", "Complement": "complement_period", "Total": "total"}

    def parse_range(label: str):
        lab = label.replace("{}", "").strip()
        if "Episode 9" in lab:
            return "fold_1", "episode"
        rng, cat = [x.strip() for x in lab.split("/")]
        return range_map[rng], cat_map[cat]

    for r in counts_rows:
        rng, cat = parse_range(r[0])
        rec = rowmap[("Omori_smooth_cont", rng, cat)]
        n = rec["n_target"]
        anchors = rec["n_anchor_target"]
        days = _labelled_days(rec["duration_microseconds"])
        add(checks, f"sequence-count-{rng}-{cat}", int(r[1]) == n and int(r[2]) == anchors and cell_ok(days, r[3]), n=n)

    oc_ep_rows = [r for r in table_rows(TEX["app11"], "{}Range / category & Ground-event $\\Delta$") if r[0].strip() != "Range / category"]
    add(checks, "sequence-ocep-table-rows", len(oc_ep_rows) == 16, actual=len(oc_ep_rows))
    for r in oc_ep_rows:
        rng, cat = parse_range(r[0])
        rec = cmap[("Omori_smooth_cont", "EP", rng, cat)]
        per = None if rec["n_target"] == 0 else rec["joint"] / rec["n_target"]
        label = f"sequence-ocep-{rng}-{cat}"
        add(
            checks,
            label,
            cell_ok(rec["timing_event"], r[1])
            and cell_ok(-rec["timing_compensator"], r[2])
            and cell_ok(rec["timing"], r[3])
            and cell_ok(rec["conditional_location"], r[4])
            and cell_ok(rec["joint"], r[5])
            and ((per is None and cell_number(r[6]) is None) or (per is not None and cell_ok(per, r[6]))),
        )

    context_rows = [r for r in table_rows(TEX["app11"], "{}Range / category & OC-fixedML timing: nats (per target)") if r[0].strip() != "Range / category"]
    add(checks, "sequence-context-table-rows", len(context_rows) == 16, actual=len(context_rows))
    for r in context_rows:
        rng, cat = parse_range(r[0])
        vals = []
        for ref, cell in (("fixedML_smooth_cont", r[1]), ("Omori_smooth_lift", r[2]), ("commonML_smooth_cont", r[3])):
            rec = cmap[("Omori_smooth_cont", ref, rng, cat)]
            key = {"fixedML_smooth_cont": "timing", "Omori_smooth_lift": "conditional_location", "commonML_smooth_cont": "joint"}[ref]
            total = rec[key]
            per = None if rec["n_target"] == 0 else total / rec["n_target"]
            parts = cell.split("(")
            ok = cell_ok(total, parts[0])
            if per is not None and len(parts) > 1:
                ok = ok and cell_ok(per, parts[1].rstrip(")"))
            vals.append(ok)
        add(checks, f"sequence-context-{rng}-{cat}", all(vals))

    # Absolute pooled arm accounting tables.
    arm_map = {"OC": "Omori_smooth_cont", "EP": "EP", "fixedML": "fixedML_smooth_cont", "OL": "Omori_smooth_lift", "commonML": "commonML_smooth_cont"}
    timing_rows = [r for r in table_rows(TEX["app11"], "Arm / category & $Q$") if r[0].strip() not in ("Arm / category",) and "&" in r[0] + "&"]
    timing_rows = [r for r in timing_rows if len(r) == 4 and r[0].split("/")[0].strip() in arm_map]
    add(checks, "sequence-arm-timing-rows", len(timing_rows) == 15, actual=len(timing_rows))
    for r in timing_rows:
        arm, cat = [x.strip() for x in r[0].split("/")]
        rec = rowmap[(arm_map[arm], "pooled", cat_map[cat])]
        add(checks, f"sequence-arm-timing-{arm}-{cat}", cell_ok(rec["timing_event"], r[1]) and cell_ok(rec["timing_compensator"], r[2]) and cell_ok(rec["timing"], r[3]) and close(rec["timing_event"] - rec["timing_compensator"], rec["timing"], 1e-9))
    location_rows = [r for r in table_rows(TEX["app11"], "Arm / category & Location & $M$") if len(r) == 4 and r[0].split("/")[0].strip() in arm_map]
    add(checks, "sequence-arm-location-rows", len(location_rows) == 15, actual=len(location_rows))
    for r in location_rows:
        arm, cat = [x.strip() for x in r[0].split("/")]
        rec = rowmap[(arm_map[arm], "pooled", cat_map[cat])]
        add(checks, f"sequence-arm-location-{arm}-{cat}", cell_ok(rec["conditional_location"], r[1]) and cell_ok(rec["inherited_mark"], r[2]) and cell_ok(rec["joint"], r[3]) and close(rec["timing"] + rec["conditional_location"] + rec["inherited_mark"], rec["joint"], 1e-9))
    add(checks, "sequence-arm-partition-sums", all(close(rowmap[(arm, "pooled", "active_period")][key] + rowmap[(arm, "pooled", "complement_period")][key], rowmap[(arm, "pooled", "total")][key], 1e-9) for arm in arm_map.values() for key in ("timing", "conditional_location", "joint")))

    # Displayed higher-threshold window and arm tables.
    rows = [r for r in table_rows(TEX["app11"], "{}UTC window & Targets & Timing versus fixedML nats (per target)") if r[0].strip() != "UTC window"]
    add(checks, "m45-window-table-rows", len(rows) == 3, actual=len(rows))
    for i, r in enumerate(rows):
        ok = int(r[1]) == expected_folds[("timing_OC_minus_fixedML", i)][0]
        for cid, col in (("timing_OC_minus_fixedML", 2), ("location_OC_minus_OL", 3), ("joint_OC_minus_commonML", 4)):
            comp = {"timing_OC_minus_fixedML": "timing_logscore", "location_OC_minus_OL": "conditional_location_logscore", "joint_OC_minus_commonML": "joint_logscore"}[cid]
            total_cell, per_cell = r[col].split(" (")
            ok = ok and cell_ok(contr[(cid, i)]["components"][comp], total_cell) and cell_ok(contr[(cid, i)]["nats_per_target"][comp], per_cell.rstrip(")"))
        add(checks, f"m45-window-table-f{i}", ok)
    arm_rows = [r for r in table_rows(TEX["app11"], "{}Primary arm & Timing nats & Conditional-location nats & Joint nats") if r[0].strip() != "Primary arm"]
    add(checks, "m45-arm-table-rows", len(arm_rows) == 4, actual=len(arm_rows))
    pooled_arms = {a["arm_id"]: a for a in m45["pooled_arms"]}
    for r in arm_rows:
        label = r[0].replace("\\allowbreak{}", "").replace("{}", "").replace("\\texttt{", "").replace("\\_", "_").replace("}", "").strip()
        rec = pooled_arms[label]
        comps = rec["components"]
        add(checks, f"m45-arm-{label}", cell_ok(comps["timing_logscore"], r[1]) and cell_ok(comps["conditional_location_logscore"], r[2]) and cell_ok(comps["joint_logscore"], r[3]))

    roster_rows = [r for r in table_rows(TEX["app11"], "{}Planned item & Planned & Completed or audited") if r[0].strip() != "Planned item"]
    add(checks, "m45-roster-rows", len(roster_rows) == 9, actual=len(roster_rows))
    add(checks, "m45-roster-values", roster_rows[0][1].strip("{} ") == "30" and roster_rows[1][1].strip("{} ") == "240" and roster_rows[2][1].strip("{} ") == "33" and roster_rows[3][1].strip("{} ") == "273" and roster_rows[8][2].strip("{} ") == "87 total")

    counts.update(
        {
            "m45_planned_targets": planned["total_targets"],
            "m45_procedures": planned["procedures"],
            "m45_annual_rows": 15,
            "base_annual_rows": 15,
            "sequence_rows": len(seq["rows"]),
            "sequence_contrast_rows": len(seq["contrasts"]),
            "sequence_active_targets": active["n_target"],
            "sequence_complement_targets": complement["n_target"],
            "active_timing_share_pct": 100 * active_share,
            "m45_within_cell_share_pct": 100 * share,
            "negative_m45_timing_years": neg,
        }
    )
    payload = component_head(
        "slice4_california_threshold_annual_sequence_v1",
        "Higher-threshold denominator roster, displayed threshold and annual tables, 2019 signed shares, and the complete active/complement sequence partition.",
        checks,
        counts,
    )
    dump("california_threshold_annual_sequence.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 4. JMA cohort, transfer contrasts, and nine annual blocks
# ---------------------------------------------------------------------------


def audit_jma_transfer() -> dict:
    checks: list[dict] = []
    counts: dict = {}

    expected = load(AUTH["jma_expected"])
    c = expected["counts"]
    add(checks, "jma-raw-records", c["all_occurrences"] == 4019138, actual=c["all_occurrences"])
    add(checks, "jma-selected-records", c["target_row_predicate_passed"] == 4602)
    add(checks, "jma-nonqualifying", c["target_unresolved_potentially_eligible"] == 41278 and expected["adjudication"]["remaining_target_unknown"] == 0 and expected["adjudication"]["target_nonqualifying_reported_primary"] == 41278)
    add(checks, "jma-auxiliary", c["auxiliary_unresolved_potentially_eligible"] == 41279 and expected["adjudication"]["remaining_auxiliary_unknown"] == 1)
    folds = expected["folds"]
    add(checks, "jma-fold-count", len(folds) == 3)
    add(checks, "jma-warmup", all(f["phases"]["warmup_parent_only"]["n"] == 496 for f in folds))
    add(checks, "jma-training", [f["phases"]["scored_training"]["n"] for f in folds] == [2829, 3298, 3646])
    add(checks, "jma-test", [f["phases"]["test"]["n"] for f in folds] == [469, 348, 460])
    add(checks, "jma-test-total", sum(f["phases"]["test"]["n"] for f in folds) == 1277)
    add(checks, "jma-origin-days", [f["origin_key"] // 8640000 for f in folds] == [3652, 4748, 5844])
    add(checks, "jma-end-days", [f["end_key"] // 8640000 for f in folds] == [4748, 5844, 6940])
    add(checks, "jma-warmup-boundary", folds[0]["origin_key"] // 8640000 == 2 * 1826)

    manifest = load(AUTH["jma_manifest"])
    add(checks, "jma-archives", len(manifest["archives"]) == 19 and [a["year"] for a in manifest["archives"]] == list(range(2006, 2025)))

    jma = load(AUTH["jma"])
    pooled = {p["comparison"]: p for p in jma["pooled_contrasts"]}
    windows = {(w["comparison"], w["fold"]): w for w in jma["window_contrasts"]}
    main_rows = [r for r in table_rows(TEX["ch11"], "{}Comparison and component & Total nats & Nats/record (1,277)") if r[0].strip() != "Comparison and component"]
    expected_main = [
        ("OC_FC_timing", -58.5935, -0.0458837, -1),
        ("OC_OL_location", 1905.74, 1.49236, 1),
        ("OC_EP_joint", -221.211, -0.173227, -1),
        ("OC_MC_joint", -49.1946, -0.0385236, -1),
        ("FC_FL_location", 1847.64, 1.44686, 1),
    ]
    add(checks, "jma-main-row-count", len(main_rows) == 5, actual=len(main_rows))
    for r, (key, total, per, sign) in zip(main_rows, expected_main):
        p = pooled[key]
        signs = [1 if windows[(key, f)]["difference_nats"] > 0 else -1 for f in range(3)]
        add(checks, f"jma-main-{key}", cell_ok(p["difference_nats"], r[1]) and cell_ok(p["difference_nats_per_target"], r[2]) and signs == [sign, sign, sign] and p["n_targets"] == 1277 and p["fold_signs"] == [sign, sign, sign])

    audit_rows = [r for r in table_rows(TEX["app11"], "{}Comparison & Component & Pooled delta nats") if r[0].strip() != "Comparison"]
    label_map = {"OC--FC": "OC_FC_timing", "OC--OL": "OC_OL_location", "OC--MC": "OC_MC_joint", "FC--FL": "FC_FL_location", "OC--FL": "OC_FL_joint", "OC--EP": "OC_EP_joint", "OC--N0": "OC_N0_joint"}
    add(checks, "jma-appendix-row-count", len(audit_rows) == 7, actual=len(audit_rows))
    for r in audit_rows:
        label = r[0].replace("{}", "").strip()
        key = label_map[label]
        p = pooled[key]
        folds_vals = [windows[(key, f)]["difference_nats"] for f in range(3)]
        add(
            checks,
            f"jma-appendix-{key}",
            cell_ok(p["difference_nats"], r[2])
            and cell_ok(p["difference_nats_per_target"], r[3])
            and all(cell_ok(v, x) for v, x in zip(folds_vals, r[4:7]))
            and int(r[7]) == 1277,
        )

    # Nine annual source-JST blocks.
    blocks = sorted({r["block"] for r in jma["annual_contrasts"]})
    add(checks, "jma-annual-blocks", blocks == [str(y) for y in range(2016, 2025)], actual=blocks)
    annual_targets = {b: next(r["n_targets"] for r in jma["annual_contrasts"] if r["block"] == b) for b in blocks}
    add(checks, "jma-annual-targets", [annual_targets[b] for b in blocks] == [201, 125, 143, 106, 111, 131, 140, 126, 194], actual=[annual_targets[b] for b in blocks])
    add(checks, "jma-annual-target-sum", sum(annual_targets.values()) == 1277)
    add(checks, "jma-annual-arm-rows", len(jma["annual_arm_rows"]) == 63 and len(jma["annual_contrasts"]) == 63)
    for key, p in pooled.items():
        total = sum(r["difference_nats"] for r in jma["annual_contrasts"] if r["comparison"] == key)
        add(checks, f"jma-annual-sum-{key}", close(total, p["difference_nats"], 1e-10), actual=total)
    add(checks, "jma-annual-mark-zero", all(r["decomposition"]["mark_logscore"] == 0.0 for r in jma["annual_contrasts"]))

    # Descriptive quantities quoted in the manuscript.
    ep = pooled["OC_EP_joint"]["decomposition"]
    add(checks, "jma-oc-ep-location", display_ok(ep["conditional_location_logscore"], -213.485907, 6))
    add(checks, "jma-n0-positive", pooled["OC_N0_joint"]["difference_nats"] > 0 and display_ok(pooled["OC_N0_joint"]["difference_nats"], 3262.47, 2))
    nuisance = jma["training_nuisance"]
    add(checks, "jma-background-bandwidth", all(n["h_km"] == 5.0 and n["h_grid_edge"] is True for n in nuisance))
    add(checks, "jma-fc-scale", all(n["sigma_selection"]["selected_sigma_km"] == 15.0 and n["sigma_selection"]["grid_edge"] is False for n in nuisance))
    md = read_text(AUTH["jma_md"])
    add(checks, "jma-trend-documentary", "reaches its lower bound in 7, 6 and 2 of seven models in folds 0, 1 and 2" in md and "All three training bandwidth selectors chose 5 km" in md)
    add(checks, "jma-denominators", jma["fit_denominator_and_execution"]["denominators"] == {"prescribed_floors": 42, "prescribed_procedures": 36, "prescribed_slots": 330, "prescribed_starts": 288})
    observed = jma["fit_denominator_and_execution"]["observed_aggregate_counts"]
    add(checks, "jma-observed-denominators", observed["accepted_returns"] == 288 and observed["failed_slots"] == 0 and observed["procedures_complete"] == 36)
    max_spread = max(s["maximum_test_spread_per_target"] for s in jma["optimizer_stability_aggregate"])
    add(checks, "jma-stability", display_ok(max_spread / 1e-5, 3.75, 2) and max_spread < 0.01)
    add(checks, "jma-audit-status", jma["audit_status"] == "pass" and jma["audit_aggregate"]["status"] == "pass")
    stage = load(ROOT / "validation/authorities/0e5b1e2f4fa9e07e_stage_completion_v1.json")
    add(checks, "jma-stage-completion", stage["status"] == "complete" and stage["audit_status"] == "pass" and stage["final_independent_review"] == "accepted" and stage["total_test_records"] == 1277 and stage["test_window_counts"] == [469, 348, 460])
    add(checks, "jma-independent-score-error", display_ok(stage["maximum_independent_score_error_nats"] / 1e-10, 1.82, 2), actual=stage["maximum_independent_score_error_nats"])
    add(checks, "jma-nearoptimal-spread", display_ok(stage["maximum_nearoptimal_spread_nats_per_target"] / 1e-5, 3.75, 2), actual=stage["maximum_nearoptimal_spread_nats_per_target"])
    add(checks, "jma-registered-comparisons", len(stage["registered_comparisons"]) == 7)
    add(checks, "jma-transfer-rule", jma["interpretation"]["combined_descriptive_transfer"] == "not_demonstrated")

    counts.update(
        {
            "raw_records": c["all_occurrences"],
            "selected_records": c["target_row_predicate_passed"],
            "warmup_records": 496,
            "training_counts": [2829, 3298, 3646],
            "test_counts": [469, 348, 460],
            "total_targets": 1277,
            "annual_blocks": 9,
            "annual_arm_rows": len(jma["annual_arm_rows"]),
            "annual_contrast_rows": len(jma["annual_contrasts"]),
            "procedures": 36,
            "starts": 288,
            "floors": 42,
            "slots": 330,
        }
    )
    payload = component_head(
        "slice4_jma_transfer_v1",
        "JMA raw-to-cohort accounting, primary and contextual pooled contrasts, all seven appendix rows, fold signs, and nine annual source-JST blocks.",
        checks,
        counts,
    )
    dump("jma_transfer.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 5. Four-arm spatial comparison (S03)
# ---------------------------------------------------------------------------


def audit_s03_spatial() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    cases = [
        ("CA", 0, 79, AUTH["s03_ca0"]),
        ("CA", 1, 167, AUTH["s03_ca1"]),
        ("CA", 2, 69, AUTH["s03_ca2"]),
        ("NZ", 0, 203, AUTH["s03_nz0"]),
        ("NZ", 1, 155, AUTH["s03_nz1"]),
        ("NZ", 2, 254, AUTH["s03_nz2"]),
    ]
    joints = {}
    components = {}
    for region, fold, targets, path in cases:
        data = load(path)
        arms = {r["arm"]: r for r in data["results"]}
        add(checks, f"s03-arms-{region}-{fold}", sorted(arms) == [1, 2, 3, 4] and all(a["status"] == "complete" for a in arms.values()))
        add(checks, f"s03-targets-{region}-{fold}", all(a["n_test"] == targets for a in arms.values()), actual=targets)
        add(checks, f"s03-joint-nll-{region}-{fold}", all(close(a["scores"]["joint"], -a["scores"]["nll"], 1e-9) for a in arms.values()))
        add(checks, f"s03-joint-identity-{region}-{fold}", all(close(a["scores"]["joint"], a["scores"]["timing"] + a["scores"]["location"] + a["scores"]["mark"], 1e-8) for a in arms.values()))
        add(checks, f"s03-mark-equal-{region}-{fold}", len({a["scores"]["mark"] for a in arms.values()}) == 1)
        joints[(region, fold)] = {k: v["scores"]["joint"] for k, v in arms.items()}
        components[(region, fold)] = {
            k: {"timing": v["scores"]["timing"], "location": v["scores"]["location"], "joint": v["scores"]["joint"]} for k, v in arms.items()
        }
    add(checks, "s03-ca-target-total", sum(t for r, f, t, p in cases if r == "CA") == 315)
    add(checks, "s03-nz-target-total", sum(t for r, f, t, p in cases if r == "NZ") == 612)

    def contrast(region, fold, a, b):
        return joints[(region, fold)][a] - joints[(region, fold)][b]

    rows = table_rows(TEX["s03"], "Region & Fold & Targets & $2-1$")
    add(checks, "s03-table-row-count", len(rows) == 6, actual=len(rows))
    for r in rows:
        region = r[0].strip()
        fold = int(r[1])
        targets = int(r[2])
        c21, c32, c42, c41 = contrast(region, fold, 2, 1), contrast(region, fold, 3, 2), contrast(region, fold, 4, 2), contrast(region, fold, 4, 1)
        add(checks, f"s03-row-{region}-{fold}", targets == next(t for rg, f, t, p in cases if rg == region and f == fold), actual=targets)
        add(checks, f"s03-cells-{region}-{fold}", cell_ok(c21, r[3]) and cell_ok(c32, r[4]) and cell_ok(c42, r[5]) and cell_ok(c41, r[6]), c21=c21, c32=c32, c42=c42, c41=c41)
        add(checks, f"s03-identity-two-step-{region}-{fold}", close(c21 + c42, c41, 1e-12) and close(c21 + c32 + (joints[(region, fold)][4] - joints[(region, fold)][3]), c41, 1e-12))
        add(checks, f"s03-nontelescoping-{region}-{fold}", close((c21 + c32 + c42) - c41, c32, 1e-12))

    derived = load(AUTH["s03_derived"])
    totals = {d["region"]: d for d in derived["regions"]}
    region_totals = {}
    for region in ("CA", "NZ"):
        folds = [f for rg, f, t, p in cases if rg == region]
        timing = sum(components[(region, f)][4]["timing"] - components[(region, f)][1]["timing"] for f in folds)
        location = sum(components[(region, f)][4]["location"] - components[(region, f)][1]["location"] for f in folds)
        joint = sum(components[(region, f)][4]["joint"] - components[(region, f)][1]["joint"] for f in folds)
        region_totals[region] = (timing, location, joint)
        dec = totals[region]["decomposition"]
        add(checks, f"s03-region-timing-{region}", close(timing, dec["timing"]["EP_minus_OC"], 1e-12), actual=timing)
        add(checks, f"s03-region-location-{region}", close(location, dec["location"]["EP_minus_OC"], 1e-12), actual=location)
        add(checks, f"s03-region-joint-{region}", close(joint, dec["joint"]["EP_minus_OC"], 1e-12), actual=joint)
        add(checks, f"s03-region-joint-identity-{region}", close(joint, timing + location, 1e-12))
        add(checks, f"s03-region-targets-{region}", totals[region]["targets"] == (315 if region == "CA" else 612))
    add(checks, "s03-ca-display", display_ok(region_totals["CA"][0], -0.8205, 4) and display_ok(region_totals["CA"][1], 50.8289, 4) and display_ok(region_totals["CA"][2], 50.0085, 4))
    add(checks, "s03-nz-display", display_ok(region_totals["NZ"][0], 2.1452, 4) and display_ok(region_totals["NZ"][1], 48.1269, 4) and display_ok(region_totals["NZ"][2], 50.2721, 4))

    code = read_text(AUTH["spatial_code"])
    add(checks, "s03-code-reference-weighting", "mult=b if arm==1 else np.ones(9)" in code and "density(a['event_xy'],a['parent_xy'],scale,q,Z)" in code)
    add(checks, "s03-code-arm3-loo", "if arm==3:" in code and "LOO_IDENTITY_BINDING" in code and "background_cell_mass" in code)
    add(checks, "s03-code-arm4-background-inherited", "scale,q=ep_spatial if arm==4 else (m['sigma'],2)" in code)
    add(checks, "s03-code-arm4-no-loo", code.count("if arm==3:") == 1 and code.count("if arm==4:") == 0)
    for region, paths in (("CA", [AUTH["s03_ca0"], AUTH["s03_ca1"], AUTH["s03_ca2"]]), ("NZ", [AUTH["s03_nz0"], AUTH["s03_nz1"], AUTH["s03_nz2"]])):
        has_prerequisite = [("EP_prerequisite_shape_spread_per_event" in load(p)) for p in paths]
        if region == "CA":
            add(checks, "s03-ca-archived-ep", not any(has_prerequisite))
        else:
            add(checks, "s03-nz-prerequisite", all(has_prerequisite) and all(load(p)["EP_prerequisite_shape_spread_gate"] is True for p in paths))

    counts.update(
        {
            "folds": 6,
            "ca_targets": 315,
            "nz_targets": 612,
            "table_rows": len(rows),
            "regional_total_rows": 2,
        }
    )
    payload = component_head(
        "slice4_s03_spatial_v1",
        "Four-arm held-out joint contrasts across six folds, exact bookkeeping identities, regional EP-minus-OC timing/location/joint totals, and the arm-specific background procedure.",
        checks,
        counts,
    )
    dump("s03_spatial.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 6. Rolling California episode backtests and JMA trend ablation (S06)
# ---------------------------------------------------------------------------


def audit_s06_episodes() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    s06 = load(AUTH["s06"])
    ca = {row["year"]: row for row in s06["CA"]}
    rows = table_rows(TEX["s06"], "Year & Targets & FC & MC & OC & EP")
    add(checks, "s06-ca-row-count", len(rows) == 5, actual=len(rows))
    for r in rows:
        year = int(r[0])
        rec = ca[year]
        add(checks, f"s06-ca-{year}", int(r[1]) == rec["n"] and all(cell_ok(rec["joint"][k], r[i]) for i, k in ((2, "FC"), (3, "MC"), (4, "OC"), (5, "EP"))), targets=rec["n"])
    add(checks, "s06-ca-target-total", sum(rec["n"] for rec in ca.values()) == 421)
    add(checks, "s06-ca-oc-ep-best", all(ca[y]["joint"]["EP"] >= max(ca[y]["joint"][k] for k in ("FC", "MC", "OC")) for y in (1994, 1999, 2004, 2019)))
    add(checks, "s06-ca-ep-loses-2010", ca[2010]["joint"]["EP"] < min(ca[2010]["joint"][k] for k in ("FC", "MC", "OC")))

    prows = table_rows(TEX["s06"], "Year & Active $N$ & Complement $N$ & Full & Active & Complement")
    add(checks, "s06-partition-row-count", len(prows) == 5, actual=len(prows))
    for r in prows:
        year = int(r[0])
        rec = ca[year]
        add(
            checks,
            f"s06-partition-{year}",
            int(r[1]) == rec["n_active"]
            and int(r[2]) == rec["n_complement"]
            and int(r[1]) + int(r[2]) == rec["n"]
            and cell_ok(rec["OC_minus_FC_full"], r[3])
            and cell_ok(rec["OC_minus_FC_active"], r[4])
            and cell_ok(rec["OC_minus_FC_complement"], r[5])
            and close(rec["OC_minus_FC_active"] + rec["OC_minus_FC_complement"], rec["OC_minus_FC_full"], 1e-10)
            and close(rec["joint"]["OC"] - rec["joint"]["FC"], rec["OC_minus_FC_full"], 1e-10),
        )

    jma = {(r["fold"], r["trend"]): r for r in s06["JMA"]}
    jrows = table_rows(TEX["s06"], "Fold & Trend & Targets & OC--FC timing & OC--EP timing & OC--EP joint")
    add(checks, "s06-jma-row-count", len(jrows) == 8, actual=len(jrows))
    for r in jrows:
        fold = r[0].strip()
        trend = "dfree" if r[1].strip() == "free" else "d0"
        if fold == "All":
            rec = s06["totals"][trend]
            key = ("all", trend)
        else:
            rec = jma[(int(fold), trend)]
            key = (int(fold), trend)
        add(
            checks,
            f"s06-jma-{key[0]}-{trend}",
            int(r[2]) == rec["n"]
            and cell_ok(rec["OC_minus_FC_timing"], r[3])
            and cell_ok(rec["OC_minus_EP_timing"], r[4])
            and cell_ok(rec["OC_minus_EP_joint"], r[5]),
        )
    add(checks, "s06-jma-total-targets", all(v["n"] == 1277 for v in s06["totals"].values()))
    add(checks, "s06-jma-pooled-sums", all(close(sum(jma[(f, t)]["OC_minus_FC_timing"] for f in range(3)), s06["totals"][t]["OC_minus_FC_timing"], 1e-10) and close(sum(jma[(f, t)]["OC_minus_EP_joint"] for f in range(3)), s06["totals"][t]["OC_minus_EP_joint"], 1e-10) for t in ("dfree", "d0")))
    add(checks, "s06-jma-dfree-display", display_ok(s06["totals"]["dfree"]["OC_minus_FC_timing"], -58.5935, 4) and display_ok(s06["totals"]["d0"]["OC_minus_FC_timing"], -37.9115, 4) and display_ok(s06["totals"]["dfree"]["OC_minus_EP_timing"], -7.7256, 4) and display_ok(s06["totals"]["d0"]["OC_minus_EP_timing"], -13.5846, 4) and display_ok(s06["totals"]["dfree"]["OC_minus_EP_joint"], -221.2115, 4) and display_ok(s06["totals"]["d0"]["OC_minus_EP_joint"], -222.2269, 4))
    add(checks, "s06-trend-direction", all(jma[(f, "dfree")]["OC_minus_FC_timing"] < 0 for f in range(3)) and all(jma[(f, "d0")]["OC_minus_EP_joint"] < 0 for f in range(3)))

    accept = load(AUTH["s06_accept"])
    add(checks, "s06-acceptance-roster", accept["schema"] == "S06_saved_row_acceptance_v1" and accept["passed"] is True and accept["CA_sequences"] == 5 and accept["CA_years"] == [1994, 1999, 2004, 2010, 2019] and accept["CA_total_targets"] == 421 and accept["JMA_folds"] == 3 and accept["JMA_targets"] == 1277)
    add(checks, "s06-acceptance-bind", s06["acceptance_sha256"].startswith("341dad668a18b4fe"))

    counts.update(
        {
            "ca_rows": len(rows),
            "ca_targets": 421,
            "ca_partition_rows": len(prows),
            "jma_rows": len(jrows),
            "jma_targets": 1277,
        }
    )
    payload = component_head(
        "slice4_s06_episodes_v1",
        "Five rolling California episode blocks, active/complement partitions, and the eight free-trend versus d=0 JMA rows.",
        checks,
        counts,
    )
    dump("s06_episodes.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 7. Conditional simulation diagnostics and completed S05 calibration
# ---------------------------------------------------------------------------


def _sci_value(cell: str):
    s = cell.strip().replace("$", "").replace("{", "").replace("}", "")
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\\times\s*10\^([+-]?\d+)", s)
    if m:
        return float(m.group(1)) * 10.0 ** int(m.group(2))
    return cell_number(cell)


def _pair_ok(actual: list | tuple, cell: str) -> bool:
    s = cell.strip().replace("$", "")
    parts = [p.strip() for p in s.strip("[]").split(",")]
    if len(parts) != 2:
        return False
    return cell_ok(float(actual[0]), parts[0]) and cell_ok(float(actual[1]), parts[1])


def audit_s05_calibration() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    scalar = load(AUTH["s05_scalar"])
    origins = scalar["origins"]
    add(checks, "s05-path-roster", scalar["planned_R"] == 999 and scalar["complete"] == 2997 and scalar["failed"] == 0 and scalar["unknown"] == 0)
    add(checks, "s05-coordinate-count", all(len(o["diagnostics"]) == 84 for o in origins.values()) and len(origins) == 3)

    o0, o1, o2 = (origins[k]["diagnostics"] for k in ("california_fold_0", "california_fold_1", "california_fold_2"))
    count_checks = [
        ("fold0", o0["count"], 79.0, [121.0, 453.0], [0.001, 0.001]),
        ("fold1", o1["count"], 167.0, [90.0, 398.0], [0.704, 0.712]),
        ("fold2", o2["count"], 69.0, [69.0, 279.0], [0.021, 0.028]),
    ]
    for label, rec, observed, ri, ins in count_checks:
        add(checks, f"s05-count-{label}", rec["observed"] == observed and rec["reference_interval"] == ri and rec["insertion_rank"] == ins)
    add(checks, "s05-early-count-insertion", o0["count"]["lower_tail_count_le"] == 0 and o0["count"]["upper_tail_count_ge"] == 999)
    add(checks, "s05-early-exposure", close(o0["exposure"]["observed"], 114.54932024184329, 1e-13) and close(o0["trigger_exposure"]["observed"], 38.82182627332281, 1e-13) and o0["exposure"]["lower_tail_count_le"] == 0 and o0["trigger_exposure"]["lower_tail_count_le"] == 0)
    add(checks, "s05-early-gap-ks", display_ok(o0["gap_ks"]["observed"], 0.222245, 6) and o0["gap_ks"]["upper_tail_count_ge"] == 0)
    add(checks, "s05-early-spatial-ks", display_ok(o0["spatial_rosenblatt_ks_max"]["observed"], 0.167335, 6) and o0["spatial_rosenblatt_ks_max"]["upper_tail_count_ge"] == 0)
    add(checks, "s05-early-ordinary", o0["time_event_logsum"]["insertion_rank"] == [0.583, 0.583] and o0["censored_tail"]["insertion_rank"] == [0.111, 0.111] and o0["within_cell_dimensionless_absmax"]["insertion_rank"] == [0.187, 0.187])
    add(checks, "s05-middle-count", o1["count"]["lower_tail_count_le"] == 711 and o1["count"]["upper_tail_count_ge"] == 296 and o1["count"]["tie_count"] == 8)
    add(checks, "s05-middle-years", [o1[f"year_count[{i}]"]["observed"] for i in range(5)] == [12.0, 4.0, 8.0, 116.0, 27.0])
    add(checks, "s05-middle-subblock", display_ok(o1["subblock_balance_max"]["observed"], 0.683688, 6) and o1["subblock_balance_max"]["insertion_rank"] == [0.998, 0.998])
    add(checks, "s05-middle-serial", o1["gap_serial"]["lower_tail_count_le"] == 999)
    add(checks, "s05-middle-scores", o1["location_logscore"]["insertion_rank"] == [0.364, 0.364] and o1["within_cell_density_logscore"]["insertion_rank"] == [0.312, 0.312])
    add(checks, "s05-middle-balance", display_ok(o1["count_minus_exposure"]["observed"], -4.373291, 6) and o1["count_minus_exposure"]["insertion_rank"] == [0.391, 0.391])
    add(checks, "s05-late-gap", o2["gap_ks"]["insertion_rank"] == [0.676, 0.676] and o2["spatial_rosenblatt_ks_max"]["insertion_rank"] == [0.810, 0.810])
    add(checks, "s05-late-discrepant", o2["gap_serial"]["insertion_rank"] == [0.998, 0.998] and o2["spatial_rosenblatt_cross_abs"]["insertion_rank"] == [0.992, 0.992] and o2["location_dimensionless_log_variance"]["lower_tail_count_le"] == 999)
    add(checks, "s05-late-exposure", o2["exposure"]["insertion_rank"] == [0.012, 0.012] and display_ok(o2["count_minus_exposure"]["observed"], -13.980114, 6) and o2["count_minus_exposure"]["insertion_rank"] == [0.110, 0.110])
    add(checks, "s05-late-marginal", display_ok(o2["censored_tail"]["observed"], 1.586733, 6) and o2["censored_tail"]["insertion_rank"] == [0.700, 0.700] and o2["within_cell_dimensionless_absmax"]["insertion_rank"] == [0.499, 0.499])
    cell4 = [o0["cell_count[4]"]["observed"], o1["cell_count[4]"]["observed"], o2["cell_count[4]"]["observed"]]
    alloc4 = [o0["cell_conditional_expected[4]"]["observed"], o1["cell_conditional_expected[4]"]["observed"], o2["cell_conditional_expected[4]"]["observed"]]
    add(checks, "s05-cell4-counts", cell4 == [15.0, 7.0, 8.0], actual=cell4)
    add(checks, "s05-cell4-allocations", all(display_ok(a, b, 6) for a, b in zip(alloc4, [23.493717, 16.132286, 14.770085])), actual=alloc4)
    add(checks, "s05-cell4-ranks", [o0["cell_count_minus_conditional_expected[4]"]["insertion_rank"][0], o1["cell_count_minus_conditional_expected[4]"]["insertion_rank"][0], o2["cell_count_minus_conditional_expected[4]"]["insertion_rank"][0]] == [0.074, 0.029, 0.047])
    add(checks, "s05-cell8-tie", o0["cell_count[8]"]["observed"] == 0.0 and o0["cell_count[8]"]["tie_count"] == 562 and o0["cell_count[8]"]["insertion_rank"] == [0.001, 0.563])
    add(checks, "s05-middle-cell7", o1["cell_count[7]"]["observed"] == 124.0 and o1["cell_count[7]"]["insertion_rank"] == [0.992, 0.992])
    add(checks, "s05-late-cell3", display_ok(o2["cell_count_minus_conditional_expected[3]"]["observed"], 5.305104, 6) and o2["cell_count_minus_conditional_expected[3]"]["insertion_rank"] == [0.991, 0.991])
    add(checks, "s05-immigrant-tie", all(o["immigrant_exposure"]["tie_count"] == 999 and o["immigrant_exposure"]["insertion_rank"] == [0.001, 1.0] for o in (o0, o1, o2)))
    add(checks, "s05-exposure-rank-identity", all(o["exposure"]["insertion_rank"] == o["trigger_exposure"]["insertion_rank"] for o in (o0, o1, o2)))
    add(checks, "s05-exposure-difference", all(close(o["exposure"]["observed"] - o["trigger_exposure"]["observed"], o["immigrant_exposure"]["observed"], 1e-12) for o in (o0, o1, o2)))
    add(checks, "s05-count-minus-exposure", all(close(o["count"]["observed"] - o["exposure"]["observed"], o["count_minus_exposure"]["observed"], 1e-12) for o in (o0, o1, o2)))
    add(checks, "s05-early-score-direction", o0["joint_logscore"]["lower_tail_count_le"] == 999 and o0["location_logscore"]["lower_tail_count_le"] == 999)

    # All 252 displayed coordinate rows.
    rows = [
        l.strip()
        for l in read_text(TEX["app12"]).splitlines()
        if l.strip().startswith("{}") and "&" in l and not l.strip().startswith("{}Coordinate")
    ]
    add(checks, "s05-appendix-row-count", len(rows) == 252, actual=len(rows))
    bad = []
    idx = 0
    for origin_name in ("california_fold_0", "california_fold_1", "california_fold_2"):
        di = origins[origin_name]["diagnostics"]
        seen = set()
        while idx < len(rows) and len(seen) < 84:
            cells = split_latex_cells(rows[idx])
            idx += 1
            label = cells[0].replace("\\allowbreak{}", "").replace("{}", "").replace("\\_", "_").replace("$", "")
            label = label.replace(" (fixed)", "").strip()
            if label not in di:
                bad.append({"origin": origin_name, "label": label, "issue": "unknown_coordinate"})
                continue
            seen.add(label)
            rec = di[label]
            issues = []
            if not cell_ok(rec["observed"], cells[1]):
                issues.append(["observed", rec["observed"], cells[1]])
            if int(cells[2]) != rec["lower_tail_count_le"]:
                issues.append(["L", rec["lower_tail_count_le"], cells[2]])
            if int(cells[3]) != rec["upper_tail_count_ge"]:
                issues.append(["H", rec["upper_tail_count_ge"], cells[3]])
            if int(cells[4]) != rec["tie_count"]:
                issues.append(["ties", rec["tie_count"], cells[4]])
            if not _pair_ok(rec["insertion_rank"], cells[5]):
                issues.append(["insertion", rec["insertion_rank"], cells[5]])
            if not _pair_ok(rec["reference_interval"], cells[6]):
                issues.append(["reference", rec["reference_interval"], cells[6]])
            if issues:
                bad.append({"origin": origin_name, "label": label, "issues": issues})
        counts[f"rows_{origin_name}"] = len(seen)
    add(checks, "s05-appendix-rows-match", not bad, mismatches=bad[:20], mismatched=len(bad))
    appendix_row_count = len(rows)

    # Public aggregate rows and retained-coordinate table.
    public = load(AUTH["s05_public"])
    pub = {(r["model"], int(r["case_id"].rsplit("_", 1)[1])): r for r in public["rows"]}
    rows = [r for r in table_rows(TEX["s05"], "Model & Fold & Conditional $N$ & Min-rank & Quadratic & Fisher-type") if r[0].strip() != "Model"]
    add(checks, "s05-public-row-count", len(rows) == 6, actual=len(rows))
    for r in rows:
        key = (r[0].strip(), int(r[1]))
        rec = pub[key]
        add(
            checks,
            f"s05-public-{key[0]}-{key[1]}",
            cell_ok(rec["conditional_N"]["two_sided_inclusive"], r[2])
            and cell_ok(rec["minimum_rank"]["p_value"], r[3])
            and cell_ok(rec["quadratic"]["pooled_upper_inclusive_p"], r[4])
            and cell_ok(rec["fisher"]["pooled_upper_inclusive_p"], r[5]),
        )
        add(checks, f"s05-retained-{key[0]}-{key[1]}", rec["minimum_rank"]["retained_coordinates"] == 82 and rec["quadratic"]["number_equal_observed"] == 1 and rec["fisher"]["number_equal_observed"] == 1)
    tie_rows = [r for r in table_rows(TEX["s05"], "Model & Fold & Min-rank coordinates & Quadratic equal & Fisher equal") if r[0].strip() != "Model"]
    add(checks, "s05-tie-row-count", len(tie_rows) == 6 and all(int(r[2]) == 82 and int(r[3]) == 1 and int(r[4]) == 1 for r in tie_rows))
    add(checks, "s05-minrank-nonreject", all(rec["minimum_rank"]["reject"] is False and rec["minimum_rank"]["p_value"] > 0.05 for rec in pub.values()))
    add(checks, "s05-omnibus-reject", all(rec["quadratic"]["pooled_upper_inclusive_p"] < 0.05 and rec["fisher"]["pooled_upper_inclusive_p"] < 0.05 for rec in pub.values()))
    add(checks, "s05-exclusions", all(rec["minimum_rank"]["excluded"] == {"immigrant_exposure": "deterministic", "trigger_exposure": "identical_two_sided_ranks:exposure"} for rec in pub.values()))
    add(checks, "s05-public-method", close(public["ridge"], 1e-8, 1e-12) and public["pooling"] == "observed_plus_999_symmetric_inclusive_ties" and len(public["coordinates"]) == 8)

    # Independent closure maxima.
    replay = load(AUTH["s05_replay"])
    closure = load(AUTH["s05_closure"])
    add(checks, "s05-replay-paths", replay["all_future_point_replay"]["planned_paths"] == 5994 and replay["all_future_point_replay"]["passed_paths"] == 5994 and replay["all_future_point_replay"]["failed_paths"] == 0)
    add(checks, "s05-replay-full84", replay["EP_full84_replay"]["planned_paths"] == 15 and replay["EP_full84_replay"]["passed_paths"] == 15 and replay["EP_full84_replay"]["coordinates_per_path"] == 84 and replay["EP_full84_replay"]["event_detail_columns"] == 11)
    errs = replay["EP_full84_replay"]["maximum_errors"]
    checks_map = [
        ("point", replay["all_future_point_replay"]["maximum_absolute_error_nats"], 1.1714291758835316e-09),
        ("score", errs["score_error"], 9.094947017729282e-12),
        ("other", errs["other_error"], 8.185452315956354e-12),
        ("cdf", errs["cdf_error"], 6.661338147750939e-15),
        ("event", errs["event_log_error"], 1.1013412404281553e-13),
        ("gap", errs["gap_error"], 1.1546319456101628e-14),
    ]
    for label, actual, expected in checks_map:
        add(checks, f"s05-closure-{label}", close(float(actual), expected, 1e-12), actual=float(actual), expected=expected)
    add(checks, "s05-closure-review", closure["passed"] is True and closure["coverage"]["fullpoint_planned"] == 5994 and closure["coverage"]["fullpoint_passed"] == 5994 and closure["coverage"]["EPfull84_passed"] == 15 and closure["coverage"]["coordinates_per_EP_path"] == 84)
    add(checks, "s05-closure-maxima", close(float(closure["maximum_errors"]["point"]), 1.1714291758835316e-09, 1e-12) and close(float(closure["maximum_errors"]["full84"]["score_error"]), 9.094947017729282e-12, 1e-12))

    # Displayed closure table uses the same six maxima.
    closure_rows = [r for r in table_rows(TEX["s05"], "Independent closure quantity & Value") if r[0].strip() != "Independent closure quantity"]
    add(checks, "s05-closure-table-rows", len(closure_rows) == 8, actual=len(closure_rows))
    closure_expected = [5994.0, 15.0, 1.1714291758835316e-09, 9.094947017729282e-12, 8.185452315956354e-12, 6.661338147750939e-15, 1.1013412404281553e-13, 1.1546319456101628e-14]
    for r, expected in zip(closure_rows, closure_expected):
        shown = _sci_value(r[1])
        ok = shown is not None and (abs(shown - expected) <= max(5e-6 * abs(expected), 1e-15 * abs(expected)) if expected < 1e-6 else shown == expected)
        add(checks, f"s05-closure-row-{r[0].strip()[:18]}", ok, display=r[1], expected=expected)

    counts.update(
        {
            "origins": 3,
            "coordinates_per_origin": 84,
            "appendix_rows": appendix_row_count,
            "appendix_rows_checked": appendix_row_count,
            "public_rows": len(pub),
            "tie_rows": len(tie_rows),
            "completed_paths": 2997,
            "replay_paths": 5994,
            "full84_paths": 15,
        }
    )
    payload = component_head(
        "slice4_s05_calibration_v1",
        "Three-origin frozen OC count/KS/insertion summary, all 252 displayed coordinates, six public p-value rows, retained-coordinate ties, and the 5,994-path / 15-vector closure maxima.",
        checks,
        counts,
    )
    dump("s05_calibration.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 8. Claim ledger
# ---------------------------------------------------------------------------


def audit_claim_ledger() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    spec = importlib.util.spec_from_file_location("_slice4_verify_claims", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    receipt, ledgers, _ = vc.verify_ledgers(ROOT, authority_only=True)
    claims = ledgers[0][1]["claims"]
    add(checks, "ledger-authority-resolution", receipt["passed"], failures=receipt["failures"][:10])
    slice4 = [
        c
        for c in claims
        if c.get("tex_file") in SLICE4_TEX_FILES
        or any(f in SLICE4_TEX_FILES for f in c.get("final_display_locations", []))
    ]
    per_file = Counter()
    missing = []
    withdrawn = 0
    tex_numbers = {
        relative: vc.manuscript_numbers((ROOT / "paper/source" / relative).read_text(encoding="utf-8-sig"))
        for relative in sorted(SLICE4_TEX_FILES)
    }
    for c in slice4:
        files = [c.get("tex_file")] if c.get("tex_file") in SLICE4_TEX_FILES else []
        files += [f for f in c.get("final_display_locations", []) if f in SLICE4_TEX_FILES]
        files = sorted(set(files))
        for relative in files:
            per_file[relative] += 1
        if c.get("ledger_role") != "manuscript_binding":
            if c.get("ledger_role") == "withdrawn_historical_result":
                withdrawn += 1
            continue
        if c.get("display_format"):
            present = True
        else:
            wanted = vc.numeric_value(c["display"])
            present = any(wanted in tex_numbers[f] for f in files)
        if not present:
            missing.append({"id": c["id"], "display": c["display"], "files": files})
    add(checks, "ledger-slice4-display-presence", not missing, missing=missing[:20])
    counts["slice4_claims"] = len(slice4)
    counts["claims_by_file"] = dict(per_file)
    counts["missing_displays"] = len(missing)
    counts["withdrawn_historical_records"] = withdrawn
    counts["master_ledger_sha256"] = sha256(LEDGER)
    add(checks, "ledger-slice4-population", len(slice4) >= 1800, actual=len(slice4))
    notes = [
        "Withdrawn historical records are authority-checked but excluded from the current manuscript-display presence requirement, matching scripts/verify_claims.py."
    ]
    payload = component_head(
        "slice4_claim_ledger_v1",
        "Independent resolution of the master claim ledger and literal display presence for the eight Slice 4 LaTeX sources.",
        checks,
        counts,
        notes=notes,
    )
    payload["authority_receipt"] = {
        "passed": receipt["passed"],
        "counts": receipt["counts"],
        "failures": receipt["failures"][:20],
    }
    dump("claim_ledger.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 9. Manuscript repair record
# ---------------------------------------------------------------------------


def audit_manuscript_repairs() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    with zipfile.ZipFile(SNAPSHOT_ZIP) as zf:
        old = {
            relative: zf.read(f"paper/source/{relative}").decode("utf-8")
            for relative in sorted(SLICE4_TEX_FILES)
            if f"paper/source/{relative}" in zf.namelist()
        }
    new = {relative: (ROOT / "paper/source" / relative).read_text(encoding="utf-8") for relative in sorted(SLICE4_TEX_FILES)}
    add(checks, "repair-source-snapshot", len(old) == len(SLICE4_TEX_FILES), actual=len(old))
    spec = importlib.util.spec_from_file_location("_slice4_verify_claims_repairs", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)

    def scalar_literals(text: str) -> set:
        values = set()
        for line in text.splitlines():
            for token in vc.tokens(line):
                raw = token.text.replace("$", "")
                if token.kind == "numeric":
                    values.add(vc.numeric_value(token.text))
                elif token.kind == "numeric_sequence":
                    for match in vc.NUMBER.finditer(token.text):
                        values.add(vc.numeric_value(match.group(0)))
                elif token.kind == "mathematical_expression":
                    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*\\times\s*10\^\{([+-]?\d+)\}", raw)
                    if match:
                        values.add(vc.numeric_value(match.group(1)) * vc.numeric_value(10) ** int(match.group(2)))
                        continue
                    match = re.fullmatch(r"10\^\{([+-]?\d+)\}", raw)
                    if match:
                        values.add(vc.numeric_value(10) ** int(match.group(1)))
        present = {str(v) for v in values}
        for value in list(values):
            text = str(value)
            if len(text) == 6 and text[:3] in present and text[3:] in present:
                values.discard(value)
        return values

    preserved = {}
    for relative in sorted(SLICE4_TEX_FILES):
        before = scalar_literals(old[relative])
        after = scalar_literals(new[relative])
        missing = sorted(str(v) for v in before - after)
        preserved[relative] = {"before": len(before), "after": len(after), "removed": missing}
        add(checks, f"numeric-preservation-{relative}", not missing, removed=missing[:20], before=len(before), after=len(after))
    counts["numeric_preservation"] = preserved

    ch11 = new["chapters/11_external_transfer_benchmarks.tex"]
    required = {
        "r-eq": "$r=0.7$",
        "m40": "$M\\geq 4.0$",
        "m45": "$M\\geq 4.5$",
        "m6": "$M\\geq 6$",
        "m50": "$M\\,5.0$",
        "mw": "$M_{\\mathrm w}$",
        "beta": "The rate $\\beta$",
        "u-interval": "$u<t\\leq u+30$~days",
        "bench-sci": "$8.19\\times 10^{-11}$",
        "m45-sci": "$1.13\\times 10^{-11}$",
        "seq-sci": "$4.55\\times 10^{-13}$",
        "jma-sci": "$1.82\\times 10^{-10}$",
        "jma-tol": "$10^{-4}$-nat",
        "jma-spread": "$3.75\\times 10^{-5}$",
    }
    for cid, token in required.items():
        add(checks, f"repair-present-{cid}", token in ch11, token=token)
    absent = {
        "raw-r": "r = 0.7",
        "raw-m40": "M $\\geq$ 4.0",
        "raw-m45": "M $\\geq$ 4.5",
        "raw-m6": "M $\\geq$ 6",
        "raw-m50": "M5.0",
        "raw-mw": " Mw",
        "raw-beta": " Beta",
        "raw-u": "at u satisfies",
        "raw-sci": re.compile(r"(?<![\w.])[0-9]\.[0-9]+e-[0-9]+"),
    }
    for cid, pattern in absent.items():
        if hasattr(pattern, "finditer"):
            found = sorted({m.group(0) for m in pattern.finditer(ch11)})
            ok = not found
            add(checks, f"repair-absent-{cid}", ok, found=found)
        else:
            add(checks, f"repair-absent-{cid}", pattern not in ch11, pattern=pattern)

    app11 = new["appendix_tables/ch11_backup.tex"]
    add(checks, "repair-app11-m40", "$M\\geq 4.0$" in app11 and "M $\\geq$ 4.0" not in app11)
    add(checks, "repair-app11-m45", "$M\\geq 4.5$" in app11 and "M $\\geq$ 4.5" not in app11)
    s05 = new["chapters/12_s05_completed.tex"]
    for cid, token in {
        "point": "$1.17143\\times 10^{-9}$",
        "score": "$9.09495\\times 10^{-12}$",
        "other": "$8.18545\\times 10^{-12}$",
        "cdf": "$6.66134\\times 10^{-15}$",
        "event": "$1.10134\\times 10^{-13}$",
        "gap": "$1.15463\\times 10^{-14}$",
    }.items():
        add(checks, f"repair-s05-{cid}", token in s05, token=token)
    add(checks, "repair-s05-absent-raw", not re.search(r"(?<![\w.])[0-9]\.[0-9]+e-[0-9]+", s05))
    app12 = new["appendix_tables/ch12_audit.tex"]
    add(checks, "repair-app12-raw-absent", not re.search(r"(?<![\w.])[0-9]\.[0-9]+e-[0-9]+", app12))

    # Reference/denominator statements next to the Slice 4 tables.
    table_tokens = {
        "primary-references": ("chapters/11_external_transfer_benchmarks.tex", ["OC-FC timing", "OC-OL location", "Pooled (315)"]),
        "benchmark-denominator": ("chapters/11_external_transfer_benchmarks.tex", ["OC minus reference, pooled 315", "N0", "EP"]),
        "threshold-denominators": ("chapters/11_external_transfer_benchmarks.tex", ["$M\\geq 4.0$ nats/target (315)", "$M\\geq 4.5$ nats/target (87)"]),
        "s03-caption": ("chapters/11_s03_completed.tex", ["Positive values favour the first named arm", "Targets"]),
        "s06-partition": ("chapters/11_s06_completed.tex", ["OC minus FC joint contrasts", "Full equals active plus complement", "Active $N$ & Complement $N$"]),
        "s06-jma": ("chapters/11_s06_completed.tex", ["Positive values favour OC", "OC--FC timing", "OC--EP joint"]),
        "s05-pvalues": ("chapters/12_s05_completed.tex", ["inclusive-tail conventions", "Conditional $N$", "Min-rank"]),
        "appendix-jma-n": ("appendix_tables/ch11_backup.tex", ["Fold 0 delta & Fold 1 delta & Fold 2 delta & N", "1277"]),
        "s03-identity": ("chapters/11_s03_completed.tex", ["the intermediate differences telescope", "counts the $(3-2)$ step twice"]),
    }
    for cid, (relative, tokens) in table_tokens.items():
        text = new[relative]
        add(checks, f"table-statement-{cid}", all(tok in text for tok in tokens), tokens=tokens)

    counts["required_tokens"] = len(required) + 6
    payload = component_head(
        "slice4_manuscript_repairs_v1",
        "Byte-level numeric-preservation check and presence/absence checks for every confirmed Slice 4 editorial and mathematical repair.",
        checks,
        counts,
    )
    dump("manuscript_repairs.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 10. Code and implementation consistency
# ---------------------------------------------------------------------------


def audit_code_consistency() -> dict:
    checks: list[dict] = []
    counts: dict = {}

    spec = importlib.util.spec_from_file_location("_slice4_regional_inputs", AUTH["regional_inputs"])
    ri = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ri
    spec.loader.exec_module(ri)
    result = ri.verify(AUTH["regional_inputs"].parent)
    add(checks, "regional-inputs", result["passed"] is True and result["S05_simulated_paths"] == 5994 and result["S05_observed_paths"] == 6 and result["S05_states"] == 6 and result["S03_selected_arms"] == 12 and result["S06_fit_records"] == 55)
    counts["regional_input_members"] = result["members"]
    counts["regional_crosswalk_records"] = result["numerical_crosswalk_records"]

    omnibus = read_text(AUTH["omnibus_code"])
    add(checks, "omnibus-ridge", "RIDGE=1e-8" in omnibus)
    coords_match = re.search(r"COORDS=\(([^)]*)\)", omnibus)
    coords = tuple(x.strip().strip("'\"") for x in coords_match.group(1).split(",")) if coords_match else ()
    public = load(AUTH["s05_public"])
    add(checks, "omnibus-coordinates", coords == tuple(public["coordinates"]), actual=list(coords))
    add(checks, "omnibus-fisher", "fisher=-np.log(coordinate_p).sum(axis=1)" in omnibus and "coordinate_p[:,j]=np.minimum(1,2*np.minimum(lo,hi))" in omnibus)
    add(checks, "omnibus-inclusive-rank", "np.count_nonzero(scores>=scores[0])/len(scores)" in omnibus)
    add(checks, "omnibus-symmetric-pool", "mean=x.mean(axis=0);sd=x.std(axis=0,ddof=1)" in omnibus and "regularized=cov+RIDGE*np.eye(8)" in omnibus)

    campaign = read_text(AUTH["campaign_code"])
    add(checks, "campaign-denominator", "denominator=2997" in campaign and "planned=2997" in campaign)
    spatial = read_text(AUTH["spatial_code"])
    add(checks, "spatial-loo-only-arm3", spatial.count("if arm==3:") == 1 and "if arm==4:" not in spatial)
    add(checks, "spatial-ep-prerequisite", "ep_spatial if arm==4 else (m['sigma'],2)" in spatial)

    eligibility = read_text(ROOT / "reproduction/jma/source/eligibility_v2.py")
    add(checks, "jma-threshold", "if tenths<45:" in eligibility)
    add(checks, "jma-depth", "elif not 0<=depth<=60:" in eligibility)
    geometry = read_text(ROOT / "reproduction/jma/source/geometry_v1.py")
    add(checks, "jma-geometry", "R_KM = 6371.0088" in geometry and "PHI0_DEGREES, LAMBDA0_DEGREES = 37, 138" in geometry and "Fraction(-600)" in geometry and "Fraction(800)" in geometry)

    counts["source_files"] = 5
    counts["coordinates"] = len(coords)
    payload = component_head(
        "slice4_code_consistency_v1",
        "Executable implementation consistency: recovered regional payload, pooled omnibus formulas, S05 campaign denominators, four-arm background logic, and JMA selection geometry.",
        checks,
        counts,
    )
    dump("code_consistency.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 11. Summary and CLI
# ---------------------------------------------------------------------------


def audit_summary(components: dict[str, dict]) -> dict:
    passed = all(c["passed"] for c in components.values())
    counts = {name: c.get("counts", {}) for name, c in components.items()}
    return {
        "schema": "slice4_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "e2fb101",
        "scope": (
            "Vertical Triad Slice 4: Chapters 11 and 12, Appendices B.9-B.10, California and Japan "
            "regional transfer, M>=4.5 threshold and annual/sequence concentration, the four-arm "
            "spatial comparison S03, rolling California episode backtests and JMA trend ablation S06, "
            "and the 2,997-path conditional simulation calibration S05."
        ),
        "passed": passed,
        "components": {name: c["passed"] for name, c in components.items()},
        "counts": counts,
        "defects_and_repairs": [
            {
                "id": "slice4-ch11-raw-math-formatting",
                "file": "paper/source/chapters/11_external_transfer_benchmarks.tex",
                "locator": "lines 37, 91, 123, 171, 173, 180, 183, 203, 208, 215, 218, 224, 256, 323, 325",
                "finding": (
                    "Split math tokens (M $\\geq$ 4.0, M $\\geq$ 4.5, M $\\geq$ 6, M5.0, Mw, Beta, r = 0.7), "
                    "the raw anchor interval phrase and raw scientific notation (8.19e-11, 1.13e-11, "
                    "4.55e-13, 1.82e-10, 1e-4, 3.75e-5) were replaced by math-mode forms. Every bound "
                    "numeric literal survives in the claim ledger."
                ),
                "status": "fixed",
            },
            {
                "id": "slice4-appendix-raw-math-formatting",
                "file": "paper/source/appendix_tables/ch11_backup.tex",
                "locator": "lines 5 and 70",
                "finding": "Two split threshold tokens were normalized to $M\\geq 4.0$ and $M\\geq 4.5$.",
                "status": "fixed",
            },
            {
                "id": "slice4-s05-raw-scientific-notation",
                "file": "paper/source/chapters/12_s05_completed.tex",
                "locator": "closure table, lines 78-83",
                "finding": "Six raw scientific-notation closure maxima were formatted as math-mode values without changing their numeric bindings.",
                "status": "fixed",
            },
            {
                "id": "slice4-app12-raw-scientific-notation",
                "file": "paper/source/appendix_tables/ch12_audit.tex",
                "locator": "independent computational audit paragraph",
                "finding": "Three raw scientific-notation audit maxima and one raw tolerance were formatted as math-mode values.",
                "status": "fixed",
            },
            {
                "id": "slice4-s03-telescoping-clarification",
                "file": "paper/source/chapters/11_s03_completed.tex",
                "locator": "penultimate paragraph of Section sec:s03-completed",
                "finding": (
                    "The text correctly rejected the non-telescoping sum but did not state its exact "
                    "discrepancy. The audit verified (4-1)=(2-1)+(4-2) and "
                    "(4-1)=(2-1)+(3-2)+(4-3) in all six folds, and that "
                    "(2-1)+(3-2)+(4-2) exceeds (4-1) by exactly (3-2). The paragraph now states "
                    "that the intermediate differences telescope and that the second expression "
                    "counts the (3-2) step twice."
                ),
                "status": "fixed",
            },
        ],
        "artifacts": {name: f"validation/live_results/slice4_audit_20261114/{name}.json" for name in sorted(components)},
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
    }


def main(argv=None) -> int:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT, help="Output directory for machine-readable audit evidence.")
    args = parser.parse_args(argv)
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)

    components = {}
    for name, function in (
        ("sealed_authority_integrity", audit_sealed_integrity),
        ("california_primary", audit_california_primary),
        ("california_threshold_annual_sequence", audit_california_threshold_annual_sequence),
        ("jma_transfer", audit_jma_transfer),
        ("s03_spatial", audit_s03_spatial),
        ("s06_episodes", audit_s06_episodes),
        ("s05_calibration", audit_s05_calibration),
        ("claim_ledger", audit_claim_ledger),
        ("manuscript_repairs", audit_manuscript_repairs),
        ("code_consistency", audit_code_consistency),
    ):
        print(f"[slice4] {name} ...", flush=True)
        components[name] = function()
        print(
            f"[slice4] {name}: {'PASS' if components[name]['passed'] else 'FAIL'} "
            f"({sum(not c['passed'] for c in components[name]['checks'])} failed checks)",
            flush=True,
        )
    summary = audit_summary(components)
    dump("summary.json", summary)
    print(json.dumps({"passed": summary["passed"], "components": summary["components"]}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
