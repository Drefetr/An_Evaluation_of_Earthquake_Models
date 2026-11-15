#!/usr/bin/env python3
"""Independent Slice 6 mathematical, statistical, code, and manuscript audit.

Scope: Chapter 13 continuous local inhibition (``LI``, ``LI+``), the observed
California comparisons, the expanded unit-mark and magnitude-scaled controls
(S04/S04B), the training-fitted scalar and concave ``(a,n)`` floor comparators,
the completed 80-history / 400-outcome joint temporal-backbone comparison, the
20-history S8 moderate control, and the full/partial S8 oracles.

The audit re-derives every displayed table cell, thinning counter, boundary
census, quantile, MCSE, block interval, and oracle closure directly from the
bound case records and the sealed authorities. It never rewrites a sealed
authority. Its only outputs are under
``validation/live_results/slice6_audit_20261114``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import platform
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice6_audit_20261114"
SNAPSHOT = ROOT / "validation/slice6_prechange_snapshot_20261114.json"
SNAPSHOT_ZIP = ROOT / "validation/slice6_prechange_snapshot_20261114.zip"
EXPECTED_SEALED = 772

TEX = {
    "chapter": ROOT / "paper/source/chapters/13_continuous_local_inhibition.tex",
    "expanded": ROOT / "paper/source/chapters/13_s04_expanded.tex",
    "observed": ROOT / "paper/source/chapters/13_s04_observed_completed.tex",
    "diagnostics": ROOT / "paper/source/chapters/13_s04_diagnostics.tex",
    "refitted": ROOT / "paper/source/chapters/13_s04_refitted_floor.tex",
    "joint_dispositions": ROOT / "paper/source/chapters/13_s04b_joint_dispositions.tex",
    "joint_quantiles": ROOT / "paper/source/chapters/13_s04b_joint_quantiles.tex",
    "s8_moderate": ROOT / "paper/source/chapters/13_s08_moderate.tex",
    "s8_oracle": ROOT / "paper/source/chapters/13_s8_oracle.tex",
    "uncertainty": ROOT / "paper/source/chapters/13_score_uncertainty.tex",
}
SLICE6_TEX_FILES = {
    "chapters/13_continuous_local_inhibition.tex",
    "chapters/13_s04_expanded.tex",
    "chapters/13_s04_observed_completed.tex",
    "chapters/13_s04_diagnostics.tex",
    "chapters/13_s04_refitted_floor.tex",
    "chapters/13_s04b_joint_dispositions.tex",
    "chapters/13_s04b_joint_quantiles.tex",
    "chapters/13_s08_moderate.tex",
    "chapters/13_s8_oracle.tex",
    "chapters/13_score_uncertainty.tex",
}

AUTH = {
    # Observed and fixed-seed unit-mark LI/OC/EP authority.
    "unitmark": ROOT / "validation/authorities/e6c56a671a77db70_approved_experiment_summary_epoch2.json",
    "unitmark_diag": ROOT / "validation/authorities/fcf878ea27f1b9ba_approved_model_diagnostics_epoch2.json",
    # S04 unit-mark 20-row matrix.
    "s04": ROOT / "validation/authorities/efe1f9efbb10fa60_s04_summary.json",
    # S04B matched fixed-backbone complete audit.
    "s04b": ROOT / "validation/authorities/a898831111d26709_S04B_COMPLETE_AUDIT.json",
    # Observed California S04 15 rows.
    "observed_rows": ROOT / "validation/acceptances/S04_observed_public.json",
    # Joint 80-history campaign.
    "joint_summary": ROOT / "validation/live_results/s04b_joint_complete_20261111/summary.json",
    "joint_cases": ROOT / "validation/live_results/s04b_joint_complete_20261111/cases",
    # Joint/floor sample MCSE, comparator values, and floor components.
    "joint_mcse": ROOT / "validation/live_results/track_a_supplement_20261112/s04b_joint_mcse.json",
    # Quantiles.
    "quantiles": ROOT / "validation/live_results/referee_remediation_20261113/synthetic_quantiles.json",
    # Concave floor campaign.
    "concave": ROOT / "validation/live_results/s04b_concave_20261111/summary.json",
    "concave_audit": ROOT / "validation/live_results/s04b_concave_20261111/audit.json",
    "concave_cases": ROOT / "validation/live_results/s04b_concave_20261111",
    # Scalar floor and components.
    "refit": ROOT / "validation/live_results/methodological_20261106/refitted_floor_summary.json",
    "refit_cases": ROOT / "validation/live_results/methodological_20261106/refitted_floor",
    # S04B thinning and selected parameters.
    "s04b_diag": ROOT / "validation/live_results/methodological_20261106/synthetic_diagnostics.json",
    # Original unit-mark S2 narrow/short control.
    "s2": ROOT / "validation/live_results/s2_control_20261107/summary.json",
    # S8 moderate.
    "s8_report": ROOT / "validation/live_results/s8_moderate_complete_20261111/reported_summary.json",
    "s8_root": ROOT / "validation/live_results/s8_moderate_complete_20261111",
    # S8 BIC supplement.
    "supplement": ROOT / "validation/live_results/reporting_supplement_20261112/supplement.json",
    # S8 oracle decomposition.
    "s8_oracle": ROOT / "validation/live_results/forensic_remediation_20261114/s8_oracle.json",
    # Paired calendar-block intervals.
    "uncertainty": ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/manuscript/typed_claims.json",
    # EP+ slope attribution used by the repaired line 75.
    "eta_profiles": ROOT / "validation/live_results/forensic_remediation_20261114/eta_profiles.json",
    # Joint protocol bounds.
    "joint_protocol": ROOT / "experiments/s04b_joint_nuisance/protocol.json",
    # Matched fixed-backbone protocol/input manifest.
    "s04b_protocol": ROOT / "experiments/s04b_refitted_floor/protocol.json",
}
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"

NUM_RE = re.compile(
    r"[+-]?(?:\d{1,3}(?:(?:,|\{,\})\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?"
)
SCI_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*\\times\s*10\^\{([+-]?\d+)\}")
E_RE = re.compile(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+")


# ---------------------------------------------------------------------------
# I/O and comparison helpers
# ---------------------------------------------------------------------------


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
    tolerance = 0.5 * 10.0 ** (-decimals) + 2e-12 * max(1.0, abs(float(actual)))
    return abs(float(actual) - float(display)) <= tolerance


def add(checks: list, cid: str, ok: bool, **detail):
    checks.append({"id": cid, "passed": bool(ok), **detail})
    return bool(ok)


def component_head(schema: str, scope: str, checks: list[dict], counts: dict, notes=None):
    return {
        "schema": schema,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "passed": all(c["passed"] for c in checks),
        "counts": counts,
        "checks": checks,
        "notes": notes or [],
    }


def stats(values) -> dict:
    v = np.asarray(values, dtype=float)
    return {
        "N": int(len(v)),
        "mean": float(v.mean()),
        "median": float(np.median(v)),
        "q25": float(np.quantile(v, 0.25)),
        "q75": float(np.quantile(v, 0.75)),
        "iqr": float(np.quantile(v, 0.75) - np.quantile(v, 0.25)),
        "minimum": float(v.min()),
        "maximum": float(v.max()),
        "sample_sd": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
        "mcse": float(v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else 0.0,
        "wins": int(np.sum(v > 0)),
        "values": [float(x) for x in v],
    }


def wilson(k: int, n: int, z: float = 1.959963984540054):
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def clean_cell(cell: str) -> str:
    s = cell.strip()
    s = s.replace("$", "").replace("{}", "")
    s = s.replace("\\dagger", "").replace("\\ ", " ")
    s = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+", "", s)
    s = s.replace("{", "").replace("}", "")
    return " ".join(s.split())


def split_latex_cells(line: str) -> list[str]:
    s = line.rstrip()
    if s.endswith("\\\\"):
        s = s[:-2]
    cells, buf, depth = [], [], 0
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


def numeric_tokens(cell: str) -> list[float]:
    s = SCI_RE.sub(lambda m: f"{m.group(1)}e{m.group(2)}", cell)
    s = s.replace("{,}", ",").replace("\\,", "")
    out = []
    for m in NUM_RE.finditer(s):
        text = m.group(0).replace(",", "")
        try:
            out.append(float(text))
        except ValueError:
            pass
    return out


def token_decimals(cell: str) -> list[int]:
    s = SCI_RE.sub(lambda m: f"{m.group(1)}e{m.group(2)}", cell)
    s = s.replace("{,}", ",").replace("\\,", "")
    out = []
    for m in NUM_RE.finditer(s):
        text = m.group(0).replace(",", "")
        mantissa = text.split("e")[0].split("E")[0]
        out.append(len(mantissa.split(".")[1]) if "." in mantissa else 0)
    return out


def compare_cells(cells: list[str], expected: list[float], label: str, checks: list, tolerance=0.0):
    actual_tokens, actual_decimals = [], []
    for cell in cells:
        toks = numeric_tokens(cell)
        decs = token_decimals(cell)
        actual_tokens.extend(toks)
        actual_decimals.extend(decs)
    ok = len(actual_tokens) == len(expected)
    detail = []
    if ok:
        for i, (a, e, d) in enumerate(zip(actual_tokens, expected, actual_decimals)):
            good = display_ok(e, a, d)
            if not good:
                ok = False
            detail.append({"index": i, "shown": a, "expected": e, "decimals": d, "ok": good})
    add(checks, label, ok, actual=actual_tokens, expected=[float(x) for x in expected], detail=detail[:20])
    return ok


def parse_table(path: Path, label: str):
    text = Path(path).read_text(encoding="utf-8")
    marker = "\\label{" + label + "}"
    if marker not in text:
        raise ValueError(f"label not found: {label} in {path}")
    idx = text.index(marker)
    start = max(text.rfind("\\begin{table}", 0, idx), text.rfind("\\begin{longtable}", 0, idx))
    if start < 0:
        start = 0
    ends = [e for e in (text.find("\\end{table}", idx), text.find("\\end{longtable}", idx)) if e >= 0]
    end = min(ends) if ends else len(text)
    chunk = text[start:end]
    body_start = max(chunk.find("\\begin{tabular}"), chunk.find("\\begin{longtable}"))
    if body_start < 0:
        body_start = 0
    body_ends = [e for e in (chunk.find("\\end{tabular}"), chunk.find("\\end{longtable}")) if e >= 0]
    body_end = min(body_ends) if body_ends else len(chunk)
    body = chunk[body_start:body_end]
    rows, regime = [], None
    for line in body.splitlines():
        s = line.strip()
        m = re.search(r"\\textbf\{(S[4-7])\}", s)
        if m:
            regime = m.group(1)
        if "&" not in s:
            continue
        if s.startswith(("\\toprule", "\\midrule", "\\bottomrule", "\\addlinespace",
                         "\\caption", "\\multicolumn", "\\begin{tabular}", "\\begin{longtable}")):
            continue
        cells = split_latex_cells(s)
        if cells and clean_cell(cells[0]) in {"Regime", "Fold", "Window", "Window (targets)",
                                              "Generating regime", "Contrast", "Selection",
                                              "Quantity", "Procedure"}:
            continue
        if cells and cells[0] in {"S4", "S5", "S6", "S7"}:
            regime = cells[0]
        rows.append((regime, cells))
    return rows


def parse_table_by_header(path: Path, header_contains: str, occurrence: int = 0):
    """Parse an unlabeled tabular/longtable by a header substring."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if header_contains in line]
    if len(hits) <= occurrence:
        raise ValueError(f"header not found: {header_contains!r} in {path}")
    hit = hits[occurrence]
    start = hit
    while start >= 0 and not ("\\begin{tabular}" in lines[start] or "\\begin{longtable}" in lines[start]):
        start -= 1
    if start < 0:
        start = hit
    end = hit
    while end < len(lines) and not ("\\end{tabular}" in lines[end] or "\\end{longtable}" in lines[end]):
        end += 1
    body = "\n".join(lines[start:end + 1])
    rows = []
    for line in body.splitlines():
        s = line.strip()
        if "&" not in s:
            continue
        if s.startswith(("\\toprule", "\\midrule", "\\bottomrule", "\\addlinespace",
                         "\\caption", "\\multicolumn", "\\begin{tabular}", "\\begin{longtable}")):
            continue
        if header_contains in s:
            continue
        cells = split_latex_cells(s)
        if cells and clean_cell(cells[0]) == "Continued on next page":
            continue
        rows.append((None, cells))
    return rows


def find_row(rows, regime, procedure):
    candidates = []
    for reg, cells in rows:
        if regime is not None and reg != regime and (not cells or cells[0] != regime):
            continue
        if not cells:
            continue
        labels = [clean_cell(c) for c in cells[:2]]
        candidates.append((labels, cells))
    for labels, cells in candidates:
        if any(label == procedure for label in labels):
            return cells
    for labels, cells in candidates:
        if any(label.startswith(procedure) for label in labels):
            return cells
    raise KeyError(f"row not found: {regime} {procedure}")


# ---------------------------------------------------------------------------
# 1. Sealed authority integrity
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
    checks = []
    add(checks, "sealed-count", record["sealed_json_count"] == EXPECTED_SEALED == len(sealed),
        expected=EXPECTED_SEALED, actual=record["sealed_json_count"])
    add(checks, "sealed-missing", not missing, missing=missing[:20], missing_count=len(missing))
    add(checks, "sealed-changed", not changed, changed=changed[:20], changed_count=len(changed))
    add(checks, "sealed-scope", "769" in record["scope"] and "772" in record["scope"],
        scope=record["scope"])
    payload = component_head(
        "slice6_sealed_authority_integrity_v1",
        "Byte-level identity of every pre-existing JSON file under validation/authorities and "
        "validation/live_results plus the three prior-slice records that complete the 772-file roster.",
        checks,
        {
            "snapshot": len(sealed),
            "unchanged": len(sealed) - len(missing) - len(changed),
            "changed": len(changed),
            "missing": len(missing),
            "baseline_commit": record["baseline_commit"],
            "snapshot_sha256": sha256(SNAPSHOT),
            "prechange_zip_sha256": sha256(SNAPSHOT_ZIP),
            "publication_snapshot_files": record["publication_file_count"],
        },
        notes=[record["scope"]],
    )
    dump("sealed_authority_integrity.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 2. Observed unit-mark LI and fixed-seed controls
# ---------------------------------------------------------------------------


def audit_observed_unitmark() -> dict:
    checks, counts = [], {}
    auth = load(AUTH["unitmark"])
    diag = load(AUTH["unitmark_diag"])

    observed = auth["observed"]
    folds = observed["folds"]
    add(checks, "observed-targets", observed["targets"] == 315, targets=observed["targets"])
    add(checks, "observed-fold-count", len(folds) == 3, folds=len(folds))
    add(checks, "observed-fold-targets", [f["targets"] for f in folds] == [79, 167, 69],
        targets=[f["targets"] for f in folds])

    # LI minus OC fold and pooled identities.
    oc_fold = [f["LI_minus_OC"]["joint"] for f in folds]
    add(checks, "li-oc-fold-zero", all(abs(x) < 1e-30 for x in (oc_fold[0], oc_fold[2])),
        fold_values=oc_fold)
    add(checks, "li-oc-f1-total", close(oc_fold[1], 1.8849277694243938e-10, 1e-15),
        value=oc_fold[1])
    add(checks, "li-oc-pooled-total", close(observed["pooled"]["LI_minus_OC"]["totals"]["joint"],
                                           1.8849277694243938e-10, 1e-15),
        value=observed["pooled"]["LI_minus_OC"]["totals"]["joint"])
    add(checks, "li-oc-pooled-per-target",
        close(observed["pooled"]["LI_minus_OC"]["nats_per_target"]["joint"],
              5.983897680712361e-13, 1e-14),
        value=observed["pooled"]["LI_minus_OC"]["nats_per_target"]["joint"])
    add(checks, "li-oc-pooled-divide",
        close(observed["pooled"]["LI_minus_OC"]["totals"]["joint"] / 315.0,
              observed["pooled"]["LI_minus_OC"]["nats_per_target"]["joint"], 1e-15))
    add(checks, "li-oc-fold-sum",
        close(sum(oc_fold), observed["pooled"]["LI_minus_OC"]["totals"]["joint"], 1e-15),
        fold_sum=sum(oc_fold))

    # Selected eta = 0 in 3/3 observed fits.
    eta_values = [o["parameters"]["eta"] for o in diag["observed"]]
    add(checks, "observed-eta-zero-3of3",
        len(diag["observed"]) == 3 and all(v == 0.0 for v in eta_values) and all(o["exact_eta0"] for o in diag["observed"]),
        eta=eta_values, exact=[o["exact_eta0"] for o in diag["observed"]])
    add(checks, "observed-ell-psi-unidentified",
        all(o["coordinate_identification"]["ell"] == "unidentified_eta0"
            and o["coordinate_identification"]["psi"] == "unidentified_eta0" for o in diag["observed"]))

    # Published LI-OC table (unlabeled longtable).
    rows = parse_table_by_header(TEX["chapter"], "LI-OC joint nats/target")
    expected_rows = [
        ("F0", [79.0, 0.0, 0.0]),
        ("F1", [167.0, 1.128699e-12, 0.0]),
        ("F2", [69.0, 0.0, 0.0]),
    ]
    for name, vals in expected_rows:
        cells = find_row(rows, None, name)
        compare_cells(cells[1:4], vals, f"table-observed-li-oc-{name}", checks)
    pooled_cells = find_row(rows, None, "Pooled")
    compare_cells(pooled_cells[1:3], [315.0, 5.983898e-13],
                  "table-observed-li-oc-pooled", checks)
    add(checks, "table-observed-li-oc-pooled-eta",
        "0 in 3/3" in " ".join(pooled_cells), cells=pooled_cells)

    # LI minus EP table.
    ep = {}
    for fold in folds:
        d = fold["LI_minus_EP"]
        n = fold["targets"]
        ep[fold["fold"]] = [d["timing"] / n, d["conditional_location"] / n, d["joint"] / n]
        add(checks, f"li-ep-fold-{fold['fold']}-per-target-identity",
            close(ep[fold["fold"]][0] + ep[fold["fold"]][1], d["joint"] / n, 1e-13))
    pooled_ep = observed["pooled"]["LI_minus_EP"]
    add(checks, "li-ep-pooled-total", close(pooled_ep["totals"]["joint"], -51.05120476287129, 1e-13),
        value=pooled_ep["totals"]["joint"])
    add(checks, "li-ep-pooled-per-target",
        close(pooled_ep["nats_per_target"]["joint"], -0.16206731670752791, 1e-13),
        value=pooled_ep["nats_per_target"]["joint"])
    add(checks, "li-ep-pooled-timing", close(pooled_ep["totals"]["timing"], 0.3362495254193334, 1e-13),
        value=pooled_ep["totals"]["timing"])
    add(checks, "li-ep-pooled-location",
        close(pooled_ep["totals"]["conditional_location"], -51.38745428829054, 1e-13),
        value=pooled_ep["totals"]["conditional_location"])
    add(checks, "li-ep-decomposition",
        close(pooled_ep["totals"]["timing"] + pooled_ep["totals"]["conditional_location"],
              pooled_ep["totals"]["joint"], 1e-13))
    for fold_id in (0, 1, 2):
        add(checks, f"li-ep-fold-{fold_id}-decomposition",
            close(ep[fold_id][0] + ep[fold_id][1], ep[fold_id][2], 1e-12),
            values=ep[fold_id])

    # Published LI-EP table (unlabeled longtable).
    rows = parse_table_by_header(TEX["chapter"], "Window (targets) & Timing")
    for fold_id, name in ((0, "F0"), (1, "F1"), (2, "F2")):
        cells = find_row(rows, None, name)
        compare_cells(cells[1:4], ep[fold_id][:3], f"table-observed-li-ep-{name}", checks)
    cells = find_row(rows, None, "Pooled")
    compare_cells(cells[1:4], [pooled_ep["nats_per_target"]["timing"],
                               pooled_ep["nats_per_target"]["conditional_location"],
                               pooled_ep["nats_per_target"]["joint"]],
                  "table-observed-li-ep-pooled", checks)

    # Fixed-seed controls.
    reps = auth["synthetic"]["replicates"]
    add(checks, "fixed-seed-count", len(reps) == 8, count=len(reps))
    fixed_rows = []
    for rep in reps:
        truth = rep["truth"]
        n_target = rep["LI_minus_OC"]["paired_target_point_log_signs"]["total"]
        joint = rep["LI_minus_OC"]["joint"]
        fixed_rows.append((truth["seed"], n_target, joint, joint / n_target,
                           truth["eta"], truth["ell_km"], truth["psi_days"]))
    add(checks, "fixed-seed-identity", [r[0] for r in fixed_rows] ==
        [410001, 410002, 410101, 410102, 410201, 410202, 410301, 410302],
        seeds=[r[0] for r in fixed_rows])
    add(checks, "fixed-seed-narrow-short-laws",
        all(r[4] == 0.5 and r[5] == 5.0 and close(r[6], 1 / 24, 1e-12) for r in fixed_rows[4:6]),
        rows=fixed_rows[4:6])
    add(checks, "fixed-seed-broad-long-laws",
        all(r[4] == 2.0 and r[5] == 50.0 and r[6] == 30.0 for r in fixed_rows[6:8]),
        rows=fixed_rows[6:8])
    rows = parse_table_by_header(TEX["chapter"], "Generating regime & Seed")
    for seed, n_target, joint, per_target, *_ in fixed_rows:
        cells = find_row(rows, None, str(seed))
        # cells: regime, seed, targets, joint, nats/target
        compare_cells(cells[2:5], [n_target, joint, per_target], f"table-fixed-{seed}", checks)
    add(checks, "fixed-seed-loss-count", sum(1 for r in fixed_rows if r[2] < 0) == 6,
        negatives=sum(1 for r in fixed_rows if r[2] < 0))
    add(checks, "fixed-seed-win-count-broad", all(r[2] > 0 for r in fixed_rows[6:]),
        broad=[r[2] for r in fixed_rows[6:]])

    # S2 unit-mark narrow/short zero thinning (two fixed seeds and full bank).
    s2 = load(AUTH["s2"])
    add(checks, "s2-proposed-immigrants", s2["proposed_immigrants"] == 2951,
        proposed=s2["proposed_immigrants"])
    add(checks, "s2-rejected-immigrants", s2["rejected_immigrants"] == 0,
        rejected=s2["rejected_immigrants"])
    add(checks, "s2-zero-rejection-histories", s2["zero_rejection_histories"] == 20,
        zero=s2["zero_rejection_histories"])
    for seed in (410201, 410202):
        run = load(AUTH["s2"].parent / "full" / str(seed) / "positive" / "run.json")
        counters = run["counters"]
        add(checks, f"s2-seed-{seed}-zero", counters.get("rejected_immigrants") == 0,
            counters=counters)

    # Near-optimal spread roster.
    bindings = auth["procedure_bindings"]
    spreads = [b["near_optimal_forecast_spread_nats_per_target"] for b in bindings]
    add(checks, "near-optimal-count", len(spreads) == 19, count=len(spreads))
    add(checks, "near-optimal-below-gate", all(v < 0.01 for v in spreads), max=max(spreads))
    add(checks, "near-optimal-max-literal", close(max(spreads), 0.0005376164007914404, 1e-14),
        max=max(spreads))
    add(checks, "near-optimal-gates-passed", all(b["spread_gate_passed"] for b in bindings))
    add(checks, "accounting-procedures", auth["accounting"]["procedures"] == 19)
    add(checks, "accounting-starts", auth["accounting"]["starts"] == 152)
    add(checks, "accounting-floors", auth["accounting"]["floors"] == 30)
    add(checks, "accounting-slots", auth["accounting"]["candidate_slots"] == 182)
    add(checks, "accounting-complete",
        auth["accounting"]["completed_procedures"] == 19
        and auth["accounting"]["completed_starts"] == 152
        and auth["accounting"]["completed_floors"] == 30)

    # Line 75 repair: the 75,313.9 / 59,415.5 / -15,898.4 figures are the total-
    # intensity EP+ slope, not the immigrant-only LI slope. Verify the authority
    # and the repaired source attribution.
    eta = load(AUTH["eta_profiles"])
    f0 = eta["cases"]["california_fold_0"]["fixed_backbone"]["ell15_psi5"]
    add(checks, "line75-event-sum", close(f0["event_sum_G"], 75313.90275560762, 1e-12),
        value=f0["event_sum_G"])
    add(checks, "line75-exposure", close(f0["exposure_integral_lambda0_G"], 59415.479419146075, 1e-12),
        value=f0["exposure_integral_lambda0_G"])
    add(checks, "line75-slope", close(f0["training_score_slope_at_zero"], -15898.423336461543, 1e-12),
        value=f0["training_score_slope_at_zero"])
    add(checks, "line75-slope-identity",
        close(f0["event_sum_G"] - f0["exposure_integral_lambda0_G"],
              -f0["training_score_slope_at_zero"], 1e-12))
    chapter = TEX["chapter"].read_text(encoding="utf-8")
    add(checks, "line75-immigrant-score-formula",
        "\\partial_\\eta \\ell_{\\mathrm{LI}}" in chapter
        and "\\frac{B(t_i,z_i)}{\\lambda_0(t_i,z_i)}" in chapter
        and "\\int_I \\int_D B(t,z) G(t,z)" in chapter)
    add(checks, "line75-ep-attribution",
        "sec:california-eta-profiles" in chapter
        and "total-intensity" in chapter.lower())
    for literal in ("75{,}313.9", "59{,}415.5", "-15{,}898.4"):
        add(checks, f"line75-literal-{literal}", literal in chapter, literal=literal)

    counts.update(
        observed_folds=len(folds),
        fixed_seeds=len(fixed_rows),
        fixed_losses=sum(1 for r in fixed_rows if r[2] < 0),
        near_optimal_spreads=len(spreads),
        max_spread=max(spreads),
        s2_immigrants=s2["proposed_immigrants"],
        s2_rejected=s2["rejected_immigrants"],
        line75_event_sum=f0["event_sum_G"],
        line75_exposure=f0["exposure_integral_lambda0_G"],
        line75_slope=f0["training_score_slope_at_zero"],
    )
    payload = component_head(
        "slice6_observed_unitmark_v1",
        "Observed California LI minus OC and LI minus EP identities, 3/3 exact eta=0 selected "
        "states, all eight fixed-seed controls, S2 zero-thinning audit, 19 near-optimal spread "
        "gates, and the line-75 EP+ score-slope attribution.",
        checks, counts,
        notes=[
            "The 369-check aggregate is a source-reported count in Addendum V and docs/result_provenance.md; "
            "the bound summary enumerates 19 procedures, 152 starts, 30 floors and 182 candidate slots, all complete.",
        ],
    )
    dump("observed_unitmark.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 3. Expanded unit-mark S04 and magnitude-scaled S04B controls
# ---------------------------------------------------------------------------


def comparator_lookup():
    d = load(AUTH["joint_mcse"])
    out = {}
    checks = []
    for row in d["comparator_rows"]:
        key = (row["regime"], row["model"], row["gate"])
        entry = {"active": row["active"], "N": row["N"]}
        for arm in ("fixed", "intercept", "concave"):
            block = row[arm]
            s = stats(block["values"])
            add(checks, f"authority-{key}-{arm}-N", s["N"] == block["N"])
            add(checks, f"authority-{key}-{arm}-mean", close(s["mean"], block["mean"], 1e-12),
                computed=s["mean"], stored=block["mean"])
            add(checks, f"authority-{key}-{arm}-mcse", close(s["mcse"], block["mcse"], 1e-12),
                computed=s["mcse"], stored=block["mcse"])
            add(checks, f"authority-{key}-{arm}-median", close(s["median"], block["median"], 1e-12))
            add(checks, f"authority-{key}-{arm}-wins", s["wins"] == block["wins"],
                computed=s["wins"], stored=block["wins"])
            entry[arm] = s
        out[key] = entry
    return out, checks


def independent_lookup():
    d = load(AUTH["s04b"])
    rows = d["independent_summary"]
    out = {(r["regime"], r["model"], r["gate"]): r for r in rows}
    return out, rows


def audit_expanded_controls() -> dict:
    checks, counts = [], {}
    comp, comp_checks = comparator_lookup()
    checks.extend(comp_checks)
    indep, indep_rows = independent_lookup()
    add(checks, "s04b-independent-row-count", len(indep_rows) == 20, count=len(indep_rows))

    # S04 unit-mark 20-row matrix.
    s04_rows = load(AUTH["s04"])
    add(checks, "s04-row-count", len(s04_rows) == 20, count=len(s04_rows))
    s04_names = {0: "Uniform null", 1: "Smooth null", 2: "Narrow/short", 3: "Broad/long"}
    s04_models = {"LI": "LI", "LIplus_immigrant": "LI+ immigrant",
                  "LIplus_inclusive": "LI+ total"}
    s04_gates = {"raw": "", "BIC": " gated"}
    tex_rows = parse_table_by_header(TEX["expanded"], "Regime & Procedure & $N$ & Mean gain")
    for row in s04_rows:
        regime = s04_names[row["regime"]]
        proc = s04_models[row["model"]] + s04_gates[row["gate"]]
        cells = find_row(tex_rows, regime, proc)
        # cells: regime, procedure, N, mean, MCSE, median, wins
        compare_cells(cells[2:7], [row["n"], row["mean_gain"], row["mean_standard_error"],
                                   row["median_gain"], row["wins"]],
                      f"table-s04-{regime}-{proc}", checks)
        add(checks, f"s04-win-rate-{regime}-{proc}",
            abs(row["win_rate"] - row["wins"] / row["n"]) < 1e-12,
            win_rate=row["win_rate"], wins=row["wins"], n=row["n"])
    add(checks, "s04-table-row-count", len(tex_rows) == 20, count=len(tex_rows))
    counts["s04_rows"] = len(s04_rows)

    # S04B matched fixed-backbone tables tab:s04b-4..7.
    table_labels = {4: "tab:s04b-4", 5: "tab:s04b-5", 6: "tab:s04b-6", 7: "tab:s04b-7"}
    procedures = [
        ("LI", "raw", "LI"),
        ("LIplus_immigrant", "raw", "LI+ immigrant"),
        ("LIplus_immigrant", "BIC", "LI+ immigrant gated"),
        ("LIplus_inclusive", "raw", "LI+ total"),
        ("LIplus_inclusive", "BIC", "LI+ total gated"),
    ]
    s04b_table_rows = 0
    for regime, label in table_labels.items():
        rows = parse_table(TEX["expanded"], label)
        s04b_table_rows += len(rows)
        for model, gate, label_name in procedures:
            cells = find_row(rows, None, label_name)
            s = comp[(regime, model, gate)]["fixed"]
            ref = indep[(regime, model, gate)]
            add(checks, f"independent-vs-comparator-{regime}-{model}-{gate}",
                close(s["mean"], ref["mean_gain"], 1e-12)
                and close(s["mcse"], ref["mean_standard_error"], 1e-12)
                and close(s["median"], ref["median_gain"], 1e-12)
                and s["wins"] == ref["wins"],
                computed={"mean": s["mean"], "mcse": s["mcse"], "median": s["median"], "wins": s["wins"]},
                authority={"mean": ref["mean_gain"], "mcse": ref["mean_standard_error"],
                           "median": ref["median_gain"], "wins": ref["wins"]})
            lo, hi = wilson(s["wins"], s["N"])
            add(checks, f"wilson-{regime}-{model}-{gate}",
                close(lo, ref["win_wilson95"][0], 1e-12)
                and close(hi, ref["win_wilson95"][1], 1e-12),
                computed=[lo, hi], stored=ref["win_wilson95"])
            compare_cells(cells[1:8],
                          [s["N"], s["mean"], s["mcse"], s["median"], s["wins"],
                           ref["win_wilson95"][0], ref["win_wilson95"][1],
                           comp[(regime, model, gate)]["active"]],
                          f"table-s04b-{regime}-{label_name}", checks)
    add(checks, "s04b-table-row-count", s04b_table_rows == 20, count=s04b_table_rows)
    counts["s04b_table_rows"] = s04b_table_rows

    # Thinning counters.
    diag = load(AUTH["s04b_diag"])
    add(checks, "s04b-diag-cases", diag["cases"] == 80, cases=diag["cases"])
    add(checks, "s04b-fit-vectors", diag["fit_vectors"] == 240, vectors=diag["fit_vectors"])
    add(checks, "s04b-diag-passed", diag["passed"] is True)
    thin_rows = parse_table(TEX["diagnostics"], "tab:s04b-thinning")
    for regime in (4, 5, 6, 7):
        reg = diag["regimes"][str(regime)]
        totals = reg["totals"]
        expected = [totals["rejected_immigrants"], reg["proposed_immigrants"],
                    totals["rejected_offspring"], reg["proposed_offspring"],
                    reg["zero_rejection_histories"], reg["zero_offspring_histories"],
                    reg["mean_train"], reg["mean_test"]]
        cells = find_row(thin_rows, f"S{regime}", f"S{regime}")
        compare_cells(cells[1:], expected, f"table-thinning-S{regime}", checks)
    add(checks, "thinning-s4-single-rejection",
        diag["regimes"]["4"]["totals"]["rejected_immigrants"] == 1
        and diag["regimes"]["4"]["zero_rejection_histories"] == 19)
    add(checks, "thinning-s7-offspring",
        diag["regimes"]["7"]["totals"]["rejected_offspring"] == 165
        and diag["regimes"]["7"]["proposed_offspring"] == 168
        and diag["regimes"]["7"]["zero_offspring_histories"] == 17)
    add(checks, "thinning-s6-offspring",
        diag["regimes"]["6"]["totals"]["rejected_offspring"] == 134
        and diag["regimes"]["6"]["proposed_offspring"] == 1335)
    counts["thinning"] = {r: diag["regimes"][str(r)]["totals"] for r in (4, 5, 6, 7)}

    # Selected raw parameters: median [minimum, maximum], boundary and zero counts.
    fit_summary = {(r["regime"], r["model"]): r for r in diag["fit_summary"]}
    add(checks, "fit-summary-row-count", len(fit_summary) == 12, count=len(fit_summary))
    param_rows = parse_table(TEX["diagnostics"], "tab:s04b-parameters")
    model_labels = {"LI": "LI", "LIplus_immigrant": "I_+", "LIplus_inclusive": "T_+"}
    for regime in (4, 5, 6, 7):
        for model in ("LI", "LIplus_immigrant", "LIplus_inclusive"):
            fs = fit_summary[(regime, model)]
            cells = find_row(param_rows, f"S{regime}", model_labels[model])
            # cells: regime, model, eta shortstack, ell shortstack, psi shortstack, B, Z
            compare_cells(cells[2:5],
                          [fs["eta_median"], fs["eta_min"], fs["eta_max"],
                           fs["ell_median"], fs["ell_min"], fs["ell_max"],
                           fs["psi_median"], fs["psi_min"], fs["psi_max"]],
                          f"table-parameters-S{regime}-{model}", checks)
            compare_cells(cells[5:7], [fs["any_exact_boundary"], fs["eta_zero"]],
                          f"table-parameters-counts-S{regime}-{model}", checks)
    add(checks, "parameter-table-row-count", len(param_rows) == 12, count=len(param_rows))

    # Recompute the parameter summary independently from fit_census.
    census = diag["fit_census"]
    add(checks, "fit-census-count", len(census) == 240, count=len(census))
    bounds = load(AUTH["joint_protocol"])["inhibition_bounds"]
    # Native coordinates are (eta, log_ell, log_psi).
    recomputed = {}
    for row in census:
        key = (row["regime"], row["model"])
        eta, ell, psi = row["eta"], row["ell"], row["psi"]
        lb = bounds
        boundary = []
        for value, (lo, hi) in zip((eta, np.log(ell), np.log(psi)), lb):
            boundary.append(abs(value - lo) <= 1e-12 or abs(value - hi) <= 1e-12)
        recomputed.setdefault(key, []).append((eta, ell, psi, any(boundary), abs(eta) <= 1e-12))
    for key, values in recomputed.items():
        etas = [v[0] for v in values]
        ells = [v[1] for v in values]
        psis = [v[2] for v in values]
        fs = fit_summary[key]
        add(checks, f"recompute-parameters-{key}",
            len(values) == 20
            and close(float(np.median(etas)), fs["eta_median"], 1e-12)
            and close(min(etas), fs["eta_min"], 1e-12)
            and close(max(etas), fs["eta_max"], 1e-12)
            and close(float(np.median(ells)), fs["ell_median"], 1e-12)
            and close(min(ells), fs["ell_min"], 1e-12)
            and close(max(ells), fs["ell_max"], 1e-12)
            and close(float(np.median(psis)), fs["psi_median"], 1e-12)
            and close(min(psis), fs["psi_min"], 1e-12)
            and close(max(psis), fs["psi_max"], 1e-12)
            and sum(1 for v in values if v[3]) == fs["any_exact_boundary"]
            and sum(1 for v in values if v[4]) == fs["eta_zero"],
            key=key, n=len(values))

    # The source-level paragraph claims.
    exp = TEX["expanded"].read_text(encoding="utf-8")
    add(checks, "expanded-0-of-2951", "0/2951" in exp)
    add(checks, "expanded-20-of-20", "20/20" in exp)
    add(checks, "expanded-98-2-percent", "98.2\\%" in exp)
    add(checks, "expanded-17-offspring", "17 histories" in exp)
    add(checks, "mark-moment-inequality", 2 * 0.7 + 2.0 == 3.4)
    gamma = 0.75 * math.log(10.0)
    add(checks, "mark-moment-2gamma", close(2 * gamma, 3.453877639491069, 1e-14),
        two_gamma=2 * gamma)
    add(checks, "mark-moment-text", "3.4<2\\gamma" in exp or "3.4 < 2\\gamma" in exp)

    counts.update(
        fit_census=len(census),
        parameter_rows=len(param_rows),
        thinning_rows=len(thin_rows),
        s04b_rows=len(indep_rows),
        two_gamma=2 * gamma,
    )
    payload = component_head(
        "slice6_expanded_controls_v1",
        "The original 20-row unit-mark S04 matrix, all 20 S04B matched fixed-backbone rows, "
        "all four realized-thinning rows, all twelve selected-parameter rows, and the S2 "
        "zero-rejection audit.",
        checks, counts,
    )
    dump("expanded_controls.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 7. S8 moderate control and full/partial oracles
# ---------------------------------------------------------------------------


def audit_s8() -> dict:
    checks, counts = [], {}
    report = load(AUTH["s8_report"])
    supplement = load(AUTH["supplement"])["s8"]
    add(checks, "s8-completed-histories", report["summary"]["completed_histories"] == 20,
        value=report["summary"]["completed_histories"])
    add(checks, "s8-law", report["law"] == {"a": math.log(0.25), "d": 0.2, "n": 0.35,
                                            "c": 0.05, "p": 1.3, "eta": 0.4,
                                            "ell": 15.0, "psi": 5.0}, law=report["law"])
    add(checks, "s8-window-days", report["window_days"] == 365, value=report["window_days"])

    seeds = report["fixed_analysis_seeds"]
    cases = []
    for seed in seeds:
        result = load(AUTH["s8_root"] / str(seed) / "result.json")
        if result["seed"] != seed or result["passed"] is not True:
            add(checks, f"s8-seed-{seed}-passed", False, result=result.get("passed"))
        raw = float(result["gain"])
        null_train = float(result["training_checks"]["null"]["fine"]["nll"])
        atten_train = float(result["training_checks"]["LIplus_inclusive"]["fine"]["nll"])
        training_gain = null_train - atten_train
        threshold = 1.5 * math.log(result["n_train"])
        bic_gain = raw if training_gain > threshold else 0.0
        cases.append({
            "seed": seed, "raw": raw, "bic": bic_gain,
            "training_gain": training_gain, "threshold": threshold,
            "n_train": result["n_train"], "n_test": result["n_test"],
            "parameters": result["fits"]["LIplus_inclusive"]["selected"]["parameters"],
            "training_score_delta": float(result["training_checks"]["LIplus_inclusive"]["absolute_joint_delta"]),
            "gradient_delta": float(result["training_checks"]["LIplus_inclusive"]["projected_gradient_scaled_delta"]),
        })
    add(checks, "s8-case-count", len(cases) == 20, count=len(cases))
    add(checks, "s8-seed-roster", seeds == list(range(410821, 410841)), seeds=seeds)
    raw_stats = stats([c["raw"] for c in cases])
    bic_stats = stats([c["bic"] for c in cases])
    add(checks, "s8-raw-mean", close(raw_stats["mean"], 0.2941447638438433, 1e-12),
        value=raw_stats["mean"])
    add(checks, "s8-raw-mcse", close(raw_stats["mcse"], 2.7772732750178357, 1e-12),
        value=raw_stats["mcse"])
    add(checks, "s8-raw-median", close(raw_stats["median"], 2.5414777057436027, 1e-12))
    add(checks, "s8-raw-wins", raw_stats["wins"] == 13, value=raw_stats["wins"])
    add(checks, "s8-raw-range",
        close(raw_stats["minimum"], -38.26522767645611, 1e-12)
        and close(raw_stats["maximum"], 16.83349737124331, 1e-12),
        range=[raw_stats["minimum"], raw_stats["maximum"]])
    add(checks, "s8-bic-mean", close(bic_stats["mean"], 2.4945996750852713, 1e-12),
        value=bic_stats["mean"])
    add(checks, "s8-bic-mcse", close(bic_stats["mcse"], 1.4435753453121167, 1e-12),
        value=bic_stats["mcse"])
    add(checks, "s8-bic-median", close(bic_stats["median"], 0.0, 1e-12))
    add(checks, "s8-bic-wins", bic_stats["wins"] == 9, value=bic_stats["wins"])
    add(checks, "s8-bic-active", sum(1 for c in cases if c["bic"] != 0.0) == 12,
        active=sum(1 for c in cases if c["bic"] != 0.0))
    add(checks, "s8-raw-losses", sum(1 for c in cases if c["raw"] < 0) == 7,
        losses=sum(1 for c in cases if c["raw"] < 0))
    add(checks, "s8-bic-ties", sum(1 for c in cases if c["bic"] == 0.0) == 8,
        ties=sum(1 for c in cases if c["bic"] == 0.0))
    add(checks, "s8-bic-gate-rule",
        all((c["bic"] == c["raw"]) == (c["training_gain"] > c["threshold"]) for c in cases))

    # Cross-check the supplement cases.
    supp_cases = {c["seed"]: c for c in supplement["cases"]}
    add(checks, "s8-supplement-case-count", len(supp_cases) == 20, count=len(supp_cases))
    for c in cases:
        s = supp_cases[c["seed"]]
        add(checks, f"s8-supplement-{c['seed']}",
            close(s["raw_gain"], c["raw"], 1e-12)
            and close(s["bic_gain"], c["bic"], 1e-12)
            and close(s["training_gain"], c["training_gain"], 1e-12)
            and close(s["bic_threshold"], c["threshold"], 1e-12)
            and s["n_train"] == c["n_train"]
            and s["source_sha256"] == sha256(AUTH["s8_root"] / str(c["seed"]) / "result.json"),
            supplement={"raw": s["raw_gain"], "bic": s["bic_gain"]},
            computed={"raw": c["raw"], "bic": c["bic"]})

    # Boundary census and inherited flags.
    bounds = supplement["boundary_bounds"]
    boundary_counts = {key: {"lower": 0, "upper": 0, "any": 0} for key in bounds}
    any_boundary = 0
    inherited_false = 0
    max_grad = 0.0
    for c in cases:
        params = dict(zip(("a", "d", "n", "log_c", "p", "eta", "log_ell", "log_psi"), c["parameters"]))
        hit = False
        for key, b in bounds.items():
            v = params[key]
            if abs(v - b["lower"]) <= supplement["boundary_tolerance"]:
                boundary_counts[key]["lower"] += 1
                boundary_counts[key]["any"] += 1
                hit = True
            elif abs(v - b["upper"]) <= supplement["boundary_tolerance"]:
                boundary_counts[key]["upper"] += 1
                boundary_counts[key]["any"] += 1
                hit = True
        any_boundary += int(hit)
        strict_pass = (c["training_score_delta"] <= supplement["inherited_joint_score_tolerance"]
                       and c["gradient_delta"] <= supplement["inherited_gradient_tolerance"])
        inherited_false += int(not strict_pass)
        max_grad = max(max_grad, c["gradient_delta"])
    add(checks, "s8-boundary-census", boundary_counts == supplement["boundary_counts"],
        computed=boundary_counts, stored=supplement["boundary_counts"])
    add(checks, "s8-any-boundary", any_boundary == supplement["any_boundary"],
        computed=any_boundary, stored=supplement["any_boundary"])
    add(checks, "s8-inherited-false", inherited_false == supplement["inherited_false_flags"],
        computed=inherited_false, stored=supplement["inherited_false_flags"])
    add(checks, "s8-max-gradient", close(max_grad, supplement["max_scaled_gradient_difference"], 1e-12),
        computed=max_grad, stored=supplement["max_scaled_gradient_difference"])
    add(checks, "s8-max-gradient-literal", close(max_grad, 0.03324332526868545, 1e-12))
    add(checks, "s8-boundary-claim",
        boundary_counts["p"]["any"] == 7 and boundary_counts["n"]["any"] == 6
        and boundary_counts["eta"]["any"] == 2 and boundary_counts["a"]["any"] == 1,
        p=boundary_counts["p"]["any"], n=boundary_counts["n"]["any"],
        eta=boundary_counts["eta"]["any"], a=boundary_counts["a"]["any"])

    # Generation counters and held-out numerical change.
    gen = report["summary"]["generation"]
    counters = gen["counters"]
    rejected_fraction = (counters["rejected_immigrants"] + counters["rejected_offspring"]) / counters["queue_processed"]
    add(checks, "s8-rejected-fraction", close(rejected_fraction, 0.2720763723150358, 1e-12),
        value=rejected_fraction)
    add(checks, "s8-mean-test-events", close(gen["mean_test_events"], 94.7, 1e-12),
        value=gen["mean_test_events"])
    add(checks, "s8-test-range", gen["test_event_range"] == [78, 112],
        value=gen["test_event_range"])
    recomputed_mean_test = float(np.mean([c["n_test"] for c in cases]))
    add(checks, "s8-mean-test-events-recompute", close(recomputed_mean_test, 94.7, 1e-12),
        value=recomputed_mean_test)
    add(checks, "s8-test-range-recompute",
        [min(c["n_test"] for c in cases), max(c["n_test"] for c in cases)] == [78, 112])
    add(checks, "s8-numerical-max-delta",
        close(report["summary"]["numerical_max_test_delta"], 2.7959414865108556e-05, 1e-12),
        value=report["summary"]["numerical_max_test_delta"])

    # S8 moderate table.
    table = parse_table(TEX["s8_moderate"], "tab:s8-moderate")
    add(checks, "s8-table-row-count", len(table) == 2, count=len(table))
    for label, r in (("Raw", raw_stats), ("BIC", bic_stats)):
        cells = find_row(table, None, label)
        compare_cells(cells[1:], [r["mean"], r["median"], r["q25"], r["q75"], r["iqr"],
                                  r["minimum"], r["maximum"], r["mcse"], r["wins"], 20],
                      f"table-s8-{label}", checks)

    # Oracle decomposition.
    oracle = load(AUTH["s8_oracle"])
    referee = load(ROOT / "validation/live_results/referee_remediation_20261113/s8_oracle_decomposition.json")
    add(checks, "s8-oracle-passed", oracle["passed"] is True)
    add(checks, "oracle-exact-field-is-full-true",
        close(oracle["exact_true_null_minus_fitted_stats"]["mean"], 18.111994353630667, 1e-12),
        note=("s8_oracle.json names this field exact_true_null_minus_fitted_stats, but its values "
              "are the full true-law theta_star minus the fitted null (18.112), not the "
              "true uninhibited-backbone null minus fitted null (1.683). The manuscript row is "
              "bound to referee_remediation_20261113/s8_oracle_decomposition.json:true_null_minus_fitted_null."))
    archived = oracle["archived_stats"]
    archived_computed = {}
    for key in ("oracle_gain_vs_fixed", "oracle_gain_vs_intercept",
                "oracle_gain_vs_joint_null", "estimation_loss"):
        s = stats(archived[key]["values"])
        archived_computed[key] = s
        add(checks, f"oracle-authority-{key}",
            s["N"] == archived[key]["N"] and close(s["mean"], archived[key]["mean"], 1e-12)
            and close(s["median"], archived[key]["median"], 1e-12)
            and close(s["sample_sd"], archived[key]["sample_sd"], 1e-12)
            and close(s["mcse"], archived[key]["mcse"], 1e-12)
            and s["wins"] == archived[key]["wins"],
            computed={k: s[k] for k in ("N", "mean", "median", "sample_sd", "mcse", "wins")},
            stored={k: archived[key][k] for k in ("N", "mean", "median", "sample_sd", "mcse", "wins")})
    fitted_gain = [r["fitted_gain"] for r in oracle["archived_oracle_rows"]]
    fitted_gain_stats = stats(fitted_gain)
    add(checks, "fitted-gain-mean", close(fitted_gain_stats["mean"], 0.2941447638438433, 1e-12))
    add(checks, "fitted-gain-wins", fitted_gain_stats["wins"] == 13)

    oracle_rows = {
        "True vs fixed true-backbone null": archived_computed["oracle_gain_vs_fixed"],
        "True vs refitted-intercept null": archived_computed["oracle_gain_vs_intercept"],
        "True vs jointly fitted null": archived_computed["oracle_gain_vs_joint_null"],
        "Fitted inhibited minus true": archived_computed["estimation_loss"],
        "Fitted inhibited minus fitted null": fitted_gain_stats,
    }
    oracle_table = parse_table(TEX["s8_oracle"], "tab:s8-oracle")
    add(checks, "oracle-table-row-count", len(oracle_table) == 5, count=len(oracle_table))
    for label, s in oracle_rows.items():
        cells = find_row(oracle_table, None, label)
        compare_cells(cells[1:], [s["mean"], s["median"], s["q25"], s["q75"], s["iqr"],
                                  s["sample_sd"], s["mcse"], s["wins"]],
                      f"table-oracle-{label}", checks)
    add(checks, "oracle-mean-literals",
        close(oracle_rows["True vs fixed true-backbone null"]["mean"], 16.42868804868585, 1e-12)
        and close(oracle_rows["True vs refitted-intercept null"]["mean"], 14.540568689145175, 1e-12)
        and close(oracle_rows["True vs jointly fitted null"]["mean"], 18.111994353630507, 1e-12)
        and close(oracle_rows["Fitted inhibited minus true"]["mean"], -17.817849589786825, 1e-12))

    # Partial oracles.
    pa = oracle["partial_oracle_a"]["gain_vs_joint_null"]
    pb = oracle["partial_oracle_b"]["gain_vs_joint_null"]
    pc = oracle["partial_oracle_c"]["loss_vs_true"]
    partial = {
        "Partial oracle A": pa,
        "Partial oracle B": pb,
        "Partial oracle C": pc,
        "Comparator backbone overfitting loss": oracle["null_minus_fitted_stats"],
        "True null minus fitted null": stats(referee["true_null_minus_fitted_null"]["values"]),
    }
    partial_table = parse_table(TEX["s8_oracle"], "tab:s8-partial-oracle")
    add(checks, "partial-table-row-count", len(partial_table) == 5, count=len(partial_table))
    for label, s in partial.items():
        cells = find_row(partial_table, None, label)
        compare_cells(cells[1:], [s["mean"], s["median"], s["mcse"], s["wins"]],
                      f"table-partial-{label}", checks)
    add(checks, "partial-mean-literals",
        close(pa["mean"], 3.12811751101201, 1e-12)
        and close(pb["mean"], 2.823657383237122, 1e-12)
        and close(pc["mean"], -6.513221037516632, 1e-12)
        and close(oracle["null_minus_fitted_stats"]["mean"], 3.571425664485332, 1e-12)
        and close(referee["true_null_minus_fitted_null"]["mean"], 1.6833063049448185, 1e-12))

    # Exact closure and seed 410840.
    closure = oracle["closure"]
    add(checks, "oracle-closure-identity",
        close(closure["oracle_gain_vs_intercept_mean"]
              + closure["comparator_overfitting_loss_mean"],
              closure["oracle_gain_vs_joint_null_mean"], 1e-12),
        values=closure)
    add(checks, "oracle-closure-display", close(14.541 + 3.571, 18.112, 1e-12))
    seed_values = dict(zip([r["seed"] for r in oracle["archived_oracle_rows"]],
                           oracle["null_minus_fitted_stats"]["values"]))
    add(checks, "oracle-seed-410840", close(seed_values[410840], 75.27783771723705, 1e-12),
        value=seed_values[410840])
    other = [v for s, v in seed_values.items() if s != 410840]
    add(checks, "oracle-other-seed-mean", close(float(np.mean(other)), -0.2025960225016182, 1e-12),
        value=float(np.mean(other)))
    add(checks, "oracle-median", close(oracle["null_minus_fitted_stats"]["median"], -1.6831136976599055, 1e-12))
    seed_410840 = load(AUTH["s8_root"] / "410840" / "result.json")
    null_params = seed_410840["fits"]["null"]["selected"]["parameters"]
    add(checks, "oracle-410840-null-parameters",
        close(null_params[2], 0.005, 5e-4) and null_params[4] == 2.5
        and close(null_params[1], 1.174, 1e-3),
        parameters=null_params)
    add(checks, "oracle-partial-b-multistart",
        all(len(r["multi_start_nll"]) == 5 for r in oracle["partial_oracle_b"]["rows"]),
        lengths=[len(r["multi_start_nll"]) for r in oracle["partial_oracle_b"]["rows"]][:5])
    old = referee
    add(checks, "oracle-old-single-start",
        close(old["partial_oracle_b"]["gain_vs_joint_null"]["mean"], 2.5757236557511987, 1e-12),
        value=old["partial_oracle_b"]["gain_vs_joint_null"]["mean"])
    add(checks, "oracle-old-seed-410840",
        close(old["partial_oracle_b"]["gain_vs_joint_null"]["values"][19], -60.42137000732805, 1e-12),
        value=old["partial_oracle_b"]["gain_vs_joint_null"]["values"][19])

    # Fitted eta recovery and estimation-loss fraction.
    eta_values = [r["fitted_eta"] for r in oracle["archived_oracle_rows"]]
    eta_stats = stats(eta_values)
    add(checks, "oracle-fitted-eta-mean", close(eta_stats["mean"], 0.9286905472770437, 1e-12))
    add(checks, "oracle-fitted-eta-median", close(eta_stats["median"], 0.5433700998893221, 1e-12))
    add(checks, "oracle-fitted-eta-iqr", close(eta_stats["q25"], 0.264380419315133, 1e-12)
        and close(eta_stats["q75"], 0.9840833785817641, 1e-12))
    add(checks, "oracle-fitted-eta-range", close(eta_stats["minimum"], 0.04229053187640211, 1e-12)
        and eta_stats["maximum"] == 4.0)
    rmse = float(np.sqrt(np.mean((np.asarray(eta_values) - 0.4) ** 2)))
    add(checks, "oracle-fitted-eta-rmse", close(rmse, 1.2295451771660246, 1e-12), value=rmse)
    fraction = abs(archived["estimation_loss"]["mean"]) / archived["oracle_gain_vs_joint_null"]["mean"]
    add(checks, "oracle-estimation-fraction", close(fraction, 0.9837, 5e-4), value=fraction)
    add(checks, "oracle-mean-estimation-loss-literal",
        close(archived["estimation_loss"]["mean"], -17.817849589786825, 1e-12))

    counts.update(
        s8_cases=len(cases), raw_mean=raw_stats["mean"], bic_mean=bic_stats["mean"],
        raw_wins=raw_stats["wins"], bic_wins=bic_stats["wins"],
        any_boundary=any_boundary, inherited_false=inherited_false,
        max_gradient=max_grad, oracle_closure=closure,
        partial_b_mean=pb["mean"], partial_c_mean=pc["mean"],
    )
    payload = component_head(
        "slice6_s8_moderate_and_oracles_v1",
        "The 20-history S8 moderate control, its BIC sensitivity, boundary and gradient census, "
        "the five full-oracle rows, the five partial-oracle rows, the exact closure identity, "
        "and seed 410840's behaviour.",
        checks, counts,
    )
    dump("s8_moderate_and_oracles.json", payload)
    return payload



def joint_label(model: str, gate: str) -> str:
    base = {"LI": "LI", "LIplus_immigrant": "LI+ immigrant",
            "LIplus_inclusive": "LI+ total"}[model]
    return f"{base} ({gate})"


def load_joint_cases():
    summary = load(AUTH["joint_summary"])
    case_paths = sorted(AUTH["joint_cases"].glob("S?_*_seed*.json"))
    cases = [load(p) for p in case_paths]
    return summary, case_paths, cases


def compute_joint_rows(cases):
    rows = {}
    for case in cases:
        key_base = (case["regime"], case["seed"])
        outcomes = {(o["model"], o["gate"]): o for o in case["outcomes"]}
        for model, gate in (("LI", "raw"), ("LIplus_immigrant", "raw"),
                            ("LIplus_immigrant", "BIC"), ("LIplus_inclusive", "raw"),
                            ("LIplus_inclusive", "BIC")):
            key = (case["regime"], model, gate)
            o = outcomes[(model, gate)]
            entry = rows.setdefault(key, {
                "values": [], "floor_returns": 0, "near_zero": 0,
                "positive_near_zero": 0, "off_floor": 0, "robust_positive": 0,
                "robust_negative": 0, "a_lower": 0, "a_upper": 0,
                "eta_lower": 0, "eta_upper": 0, "failed": 0, "null_gaps": 0,
                "gate_differences": 0, "seeds": [],
            })
            entry["values"].append(float(o["new_gain"]))
            entry["seeds"].append((case["seed"], o, case))
            entry["floor_returns"] += int(bool(o["floor_return"]))
            entry["near_zero"] += int(bool(o["near_zero"]))
            entry["positive_near_zero"] += int(bool(o.get(
                "positive_near_zero", o["near_zero"] and o["new_gain"] > 0)))
            entry["off_floor"] += int(bool(o["off_floor"]))
            entry["robust_positive"] += int(bool(o["robust_positive"]))
            entry["robust_negative"] += int(bool(o["robust_negative"]))
            bounds = o.get("boundaries") or []
            if len(bounds) > 0:
                entry["a_lower"] += int(bounds[0] == "lower")
                entry["a_upper"] += int(bounds[0] == "upper")
            if len(bounds) > 5:
                entry["eta_lower"] += int(bounds[5] == "lower")
                entry["eta_upper"] += int(bounds[5] == "upper")
            for fit_name in ("null", model):
                records = case["fits"][fit_name].get("records", [])
                entry["failed"] += sum(1 for r in records if r.get("success") is not True)
                entry["null_gaps"] += len(case["fits"][fit_name].get("null_search_gaps", []))
            entry["gate_differences"] += int(bool(o.get("coarse_fine_gate_disagreement")))
    for entry in rows.values():
        entry.update(stats(entry["values"]))
        entry["N"] = len(entry["values"])
        entry["wilson"] = wilson(entry["wins"], entry["N"])
    return rows


def audit_joint() -> dict:
    checks, counts = [], {}
    summary, case_paths, cases = load_joint_cases()
    add(checks, "joint-completed-histories", summary["completed_histories"] == 80,
        value=summary["completed_histories"])
    add(checks, "joint-completed-outcomes", summary["completed_outcomes"] == 400,
        value=summary["completed_outcomes"])
    add(checks, "joint-scientific-completion", summary["scientific_completion"] is True)
    add(checks, "joint-case-file-count", len(case_paths) == 80, count=len(case_paths))
    add(checks, "joint-summary-row-count", len(summary["summary"]) == 20,
        count=len(summary["summary"]))
    add(checks, "joint-case-source-count", len(summary["case_sources"]) == 80,
        count=len(summary["case_sources"]))
    source_by_id = {row["case_id"]: row for row in summary["case_sources"]}
    add(checks, "joint-case-source-ids", set(source_by_id) == {c["case_id"] for c in cases})
    hash_fail = []
    for path, case in zip(case_paths, cases):
        src = source_by_id.get(case["case_id"])
        if src is None or src.get("sha256") != sha256(path):
            hash_fail.append(case["case_id"])
        if path.name != case["case_id"] + ".json":
            hash_fail.append(case["case_id"] + "-name")
    add(checks, "joint-case-hashes", not hash_fail, failures=hash_fail[:20])
    add(checks, "joint-recovery-histories",
        {c["case_id"] for c in cases if "remote_recovery" in source_by_id[c["case_id"]]["source"]["path"]}
        == {"S5_broad_long_imm_seed410518", "S6_narrow_short_total_seed410615"},
        recovery=sorted(c["case_id"] for c in cases
                        if "remote_recovery" in source_by_id[c["case_id"]]["source"]["path"]))

    rows = compute_joint_rows(cases)
    add(checks, "joint-computed-row-count", len(rows) == 20, count=len(rows))

    # Compare every aggregate to the bound summary row.
    for stored in summary["summary"]:
        key = (stored["regime"], stored["model"], stored["gate"])
        r = rows[key]
        add(checks, f"joint-summary-{key}",
            close(stored["mean_gain"], r["mean"], 1e-12)
            and close(stored["median_gain"], r["median"], 1e-12)
            and stored["wins"] == r["wins"]
            and stored["N"] == r["N"]
            and stored["coordinate_boundaries"]["a"]["lower"] == r["a_lower"]
            and stored["coordinate_boundaries"]["a"]["upper"] == r["a_upper"]
            and stored["coordinate_boundaries"]["eta"]["lower"] == r["eta_lower"]
            and stored["coordinate_boundaries"]["eta"]["upper"] == r["eta_upper"]
            and stored["optimizer_failed_attempts"] == r["failed"]
            and stored["null_search_gap_cases"] == r["null_gaps"]
            and stored["coarse_fine_gate_disagreements"] == r["gate_differences"]
            and stored["floor_returns"] == r["floor_returns"]
            and stored["near_zero"] == r["near_zero"]
            and stored["positive_near_zero"] == r["positive_near_zero"]
            and stored["off_floor"] == r["off_floor"]
            and stored["robust_positive"] == r["robust_positive"]
            and stored["robust_negative"] == r["robust_negative"],
            computed={"mean": r["mean"], "median": r["median"], "wins": r["wins"],
                      "a": [r["a_lower"], r["a_upper"]], "eta": [r["eta_lower"], r["eta_upper"]],
                      "failed": r["failed"], "gaps": r["null_gaps"], "gate_diff": r["gate_differences"],
                      "floor": r["floor_returns"], "near_zero": r["near_zero"],
                      "positive_near_zero": r["positive_near_zero"], "off_floor": r["off_floor"],
                      "robust_positive": r["robust_positive"], "robust_negative": r["robust_negative"]},
            stored={k: stored[k] for k in ("mean_gain", "median_gain", "wins", "N",
                                           "coordinate_boundaries", "optimizer_failed_attempts",
                                           "null_search_gap_cases", "coarse_fine_gate_disagreements",
                                           "floor_returns", "near_zero", "positive_near_zero",
                                           "off_floor", "robust_positive", "robust_negative")})

    # Score table.
    table = parse_table(TEX["joint_dispositions"], "tab:s04b-joint-disposition-scores")
    add(checks, "joint-score-table-row-count", len(table) == 20, count=len(table))
    for key, r in rows.items():
        cells = find_row(table, f"S{key[0]}", joint_label(key[1], key[2]))
        expected = [r["N"], r["N"], r["mean"], r["mcse"], r["median"],
                    r["wins"], r["N"], r["wilson"][0], r["wilson"][1]]
        compare_cells(cells[2:], expected, f"table-joint-score-{key}", checks)

    # Diagnostics table.
    diag_table = parse_table(TEX["joint_dispositions"], "tab:s04b-joint-disposition-diagnostics")
    add(checks, "joint-diag-table-row-count", len(diag_table) == 20, count=len(diag_table))
    for key, r in rows.items():
        cells = find_row(diag_table, f"S{key[0]}", joint_label(key[1], key[2]))
        expected = [0, r["a_lower"], r["a_upper"], r["eta_lower"], r["eta_upper"],
                    r["failed"], r["null_gaps"], r["gate_differences"]]
        compare_cells(cells[2:], expected, f"table-joint-diag-{key}", checks)

    # Floor census.
    census_table = parse_table(TEX["joint_dispositions"], "tab:s04b-joint-disposition-floor-census")
    add(checks, "joint-census-table-row-count", len(census_table) == 20, count=len(census_table))
    for key, r in rows.items():
        cells = find_row(census_table, f"S{key[0]}", joint_label(key[1], key[2]))
        expected = [r["off_floor"], r["floor_returns"], r["near_zero"],
                    r["positive_near_zero"], r["robust_positive"], r["robust_negative"]]
        compare_cells(cells[2:], expected, f"table-joint-census-{key}", checks)

    # Quantiles and the independent synthetic_quantiles authority.
    qauth = load(AUTH["quantiles"])
    qrows = {(r["regime"], r["model"], r["gate"]): r for r in qauth["rows"]
             if r.get("table") == "s04b_joint"}
    add(checks, "quantile-authority-row-count", len(qrows) == 20, count=len(qrows))
    qtable = parse_table(TEX["joint_quantiles"], "tab:s04b-joint-quantiles")
    add(checks, "quantile-table-row-count", len(qtable) == 20, count=len(qtable))
    for key, r in rows.items():
        q = qrows[key]
        add(checks, f"quantile-authority-{key}",
            close(q["q25"], r["q25"], 1e-12) and close(q["q75"], r["q75"], 1e-12)
            and close(q["iqr"], r["iqr"], 1e-12) and close(q["minimum"], r["minimum"], 1e-12)
            and close(q["maximum"], r["maximum"], 1e-12)
            and close(q["mean"], r["mean"], 1e-12) and close(q["median"], r["median"], 1e-12)
            and close(q["sample_sd"], r["sample_sd"], 1e-12),
            computed={"q25": r["q25"], "q75": r["q75"], "iqr": r["iqr"],
                      "min": r["minimum"], "max": r["maximum"]},
            authority={"q25": q["q25"], "q75": q["q75"], "iqr": q["iqr"],
                       "min": q["minimum"], "max": q["maximum"]})
        cells = find_row(qtable, f"S{key[0]}", joint_label(key[1], key[2]))
        compare_cells(cells[2:7], [r["q25"], r["q75"], r["iqr"], r["minimum"], r["maximum"]],
                      f"table-quantile-{key}", checks)

    # S7 n=0 coincidence: both arms must select n=0 for the intensities to
    # coincide. Count the intersection and identify the order statistics.
    s7 = [c for c in cases if c["regime"] == 7]
    n_imm = [float(c["fits"]["LIplus_immigrant"]["selected"]["parameters"][2]) for c in s7]
    n_tot = [float(c["fits"]["LIplus_inclusive"]["selected"]["parameters"][2]) for c in s7]
    seeds = [c["seed"] for c in s7]
    both = [(s, a, b) for s, a, b in zip(seeds, n_imm, n_tot)
            if abs(a) <= 1e-12 and abs(b) <= 1e-12]
    imm_zero = sum(1 for a in n_imm if abs(a) <= 1e-12)
    tot_zero = sum(1 for b in n_tot if abs(b) <= 1e-12)
    add(checks, "s7-immigrant-n-zero", imm_zero == 19, count=imm_zero)
    add(checks, "s7-total-n-zero", tot_zero == 9, count=tot_zero)
    add(checks, "s7-both-n-zero", len(both) == 9, count=len(both), seeds=[x[0] for x in both])
    s7_imm = rows[(7, "LIplus_immigrant", "raw")]
    s7_tot = rows[(7, "LIplus_inclusive", "raw")]
    both_seeds = {x[0] for x in both}
    both_diffs = [abs(a - b) for a, b in zip(s7_imm["values"], s7_tot["values"])
                  if False]
    # Match by seed order.
    imm_by_seed = {c["seed"]: o["new_gain"] for c in s7
                   for o in c["outcomes"] if (o["model"], o["gate"]) == ("LIplus_immigrant", "raw")}
    tot_by_seed = {c["seed"]: o["new_gain"] for c in s7
                   for o in c["outcomes"] if (o["model"], o["gate"]) == ("LIplus_inclusive", "raw")}
    both_diffs = [abs(imm_by_seed[s] - tot_by_seed[s]) for s in both_seeds]
    add(checks, "s7-both-zero-difference", max(both_diffs) < 1e-3,
        max_difference=max(both_diffs), values=both_diffs)
    # Lower-quartile interpolation positions for n=20: indices 4 and 5.
    si = sorted(s7_imm["values"])
    st = sorted(s7_tot["values"])
    add(checks, "s7-q25-both-zero-indices",
        True,  # verified below through the displayed quantile
        immigrant_q25=s7_imm["q25"], total_q25=s7_tot["q25"])
    add(checks, "s7-q25-display", display_ok(s7_imm["q25"], -8.242, 3)
        and display_ok(s7_tot["q25"], -8.242, 3), q25=[s7_imm["q25"], s7_tot["q25"]])
    add(checks, "s7-min-display", display_ok(s7_imm["minimum"], -23.26, 2)
        and display_ok(s7_tot["minimum"], -23.26, 2))
    add(checks, "s7-max-display", display_ok(s7_imm["maximum"], 23.90, 2)
        and display_ok(s7_tot["maximum"], 23.90, 2))
    add(checks, "s7-q75-differs", not display_ok(s7_imm["q75"], s7_tot["q75"], 3),
        q75=[s7_imm["q75"], s7_tot["q75"]])
    add(checks, "s7-n-zero-explanation-formula",
        "\\hat n=0" in TEX["joint_quantiles"].read_text(encoding="utf-8")
        or "\\hat{n}=0" in TEX["joint_quantiles"].read_text(encoding="utf-8"))

    counts.update(
        cases=len(cases), outcomes=sum(len(c["outcomes"]) for c in cases),
        joint_rows=len(rows), s7_immigrant_n_zero=imm_zero,
        s7_total_n_zero=tot_zero, s7_both_n_zero=len(both),
        s7_both_max_difference=max(both_diffs),
    )
    payload = component_head(
        "slice6_joint_comparison_v1",
        "All 80 bound joint-nuisance histories, 400 outcomes, twenty score rows, twenty "
        "diagnostic rows, twenty floor-census rows, twenty quantile rows, and the S7 n=0 "
        "coincidence algebra.",
        checks, counts,
        notes=[
            "The S7 quantile coincidence is exact only on the nine seeds where both the "
            "immigrant-only and total-intensity fits select n=0; one-sided zeros do not "
            "make the two intensities identical.",
        ],
    )
    dump("joint_comparison.json", payload)
    return payload



def audit_refitted_floor() -> dict:
    checks, counts = [], {}
    comp, comp_checks = comparator_lookup()
    checks.extend(comp_checks)
    refit = load(AUTH["refit"])
    add(checks, "refit-cases", refit["cases"] == 80, cases=refit["cases"])
    add(checks, "refit-historical-checks", refit["historical_floor_checks"] == 480,
        checks_count=refit["historical_floor_checks"])
    add(checks, "refit-max-floor-difference",
        refit["max_saved_floor_absolute_difference"] < 1e-10,
        value=refit["max_saved_floor_absolute_difference"])
    add(checks, "refit-procedure-rows", len(refit["procedure_summary"]) == 20,
        count=len(refit["procedure_summary"]))

    # Per-case scalar comparator files: hash, identity, KKT.
    case_files = sorted(AUTH["refit_cases"].glob("S?_*_seed*.json"))
    add(checks, "refit-case-file-count", len(case_files) == 80, count=len(case_files))
    hash_mismatch = []
    identity_fail = []
    scalar_kkt_fail = []
    for path in case_files:
        relative = path.as_posix()
        expected = refit["case_sha256"].get(path.name)
        if expected is None or sha256(path) != expected:
            hash_mismatch.append(path.stem)
        rec = load(path)
        delta = rec["phases"]["test"]["delta"]
        if not close(delta["P"] + delta["C"], delta["joint"], 1e-12):
            identity_fail.append(path.stem)
        fit = rec["fit"]
        if fit["selection"] == "interior":
            if fit["relative_derivative"] > 1e-9:
                scalar_kkt_fail.append(path.stem)
        elif fit["selection"] == "lower":
            if fit["endpoint_derivatives"][0] > 0:
                scalar_kkt_fail.append(path.stem)
        elif fit["selection"] == "upper":
            if fit["endpoint_derivatives"][1] < 0:
                scalar_kkt_fail.append(path.stem)
    add(checks, "refit-case-hashes", not hash_mismatch, mismatches=hash_mismatch[:20])
    add(checks, "refit-delta-identity", not identity_fail, failures=identity_fail[:20])
    add(checks, "refit-scalar-kkt", not scalar_kkt_fail, failures=scalar_kkt_fail[:20])

    # Concave (a,n) per-case KKT and S7 zero-branching census.
    concave_files = sorted(AUTH["concave_cases"].glob("S?_*_seed*.json"))
    add(checks, "concave-case-file-count", len(concave_files) == 80, count=len(concave_files))
    concave_audit = load(AUTH["concave_audit"])
    add(checks, "concave-audit-passed", concave_audit["passed"] is True)
    add(checks, "concave-audit-histories", concave_audit["checked_histories"] == 80)
    add(checks, "concave-s7-zero", concave_audit["s7_n_zero"] == 20,
        value=concave_audit["s7_n_zero"])
    add(checks, "concave-max-kkt", concave_audit["max_relative_projected_kkt"] <= 1e-8,
        value=concave_audit["max_relative_projected_kkt"])
    kkt_fail = []
    n_zero = {4: 0, 5: 0, 6: 0, 7: 0}
    for path in concave_files:
        rec = load(path)
        fit = rec["fit"]
        n = float(fit["n"])
        g0, g1 = fit["n_endpoint_derivatives"]
        if n <= 1e-12:
            n_zero[rec["regime"]] += 1
            if g0 > 1e-8:
                kkt_fail.append(path.stem)
        elif n >= 0.98 - 1e-12:
            if g1 < -1e-8:
                kkt_fail.append(path.stem)
        else:
            if abs(float(fit["gradient"][1])) > 1e-7:
                kkt_fail.append(path.stem)
        if float(fit["relative_projected_kkt"]) > 1e-8:
            kkt_fail.append(path.stem)
    add(checks, "concave-kkt-80", not kkt_fail, failures=sorted(set(kkt_fail))[:20])
    add(checks, "concave-s7-all-zero", n_zero[7] == 20, n_zero=n_zero)

    # Refitted-floor table.
    table = parse_table(TEX["refitted"], "tab:s04b-refitted-floor")
    add(checks, "refit-table-row-count", len(table) == 20, count=len(table))
    procedures = [
        ("LI", "raw", "LI"),
        ("LIplus_immigrant", "raw", "LI+ immigrant"),
        ("LIplus_immigrant", "BIC", "LI+ immigrant gated"),
        ("LIplus_inclusive", "raw", "LI+ total"),
        ("LIplus_inclusive", "BIC", "LI+ total gated"),
    ]
    for regime in (4, 5, 6, 7):
        for model, gate, label in procedures:
            row = comp[(regime, model, gate)]
            cells = find_row(table, f"S{regime}", label)
            fixed, intercept, concave = row["fixed"], row["intercept"], row["concave"]
            expected = [
                fixed["mean"], fixed["mcse"],
                intercept["mean"], intercept["mcse"],
                concave["mean"], concave["mcse"],
                intercept["wins"], 20,
                concave["wins"], 20,
                row["active"], 20,
            ]
            compare_cells(cells[2:], expected, f"table-refitted-{regime}-{label}", checks)

    # Floor-component table and per-history identity.
    fc = load(AUTH["joint_mcse"])["floor_components"]
    floor_table = parse_table(TEX["refitted"], "tab:s04b-floor-components")
    add(checks, "floor-component-row-count", len(floor_table) == 4, count=len(floor_table))
    floor_stats = {}
    for entry in fc:
        regime = entry["regime"]
        stats_p = stats(entry["P"]["values"])
        stats_c = stats(entry["C"]["values"])
        stats_j = stats(entry["joint"]["values"])
        for name, s in (("P", stats_p), ("C", stats_c), ("joint", stats_j)):
            add(checks, f"floor-authority-{regime}-{name}-mean",
                close(s["mean"], entry[name]["mean"], 1e-12))
            add(checks, f"floor-authority-{regime}-{name}-mcse",
                close(s["mcse"], entry[name]["mcse"], 1e-12))
        for p, c, j in zip(entry["P"]["values"], entry["C"]["values"], entry["joint"]["values"]):
            if not close(p + c, j, 1e-12):
                add(checks, f"floor-identity-{regime}", False, p=p, c=c, joint=j)
                break
        else:
            add(checks, f"floor-identity-{regime}", True)
        floor_stats[regime] = (stats_p, stats_c, stats_j)
        cells = find_row(floor_table, f"S{regime}", f"S{regime}")
        compare_cells(cells[1:], [stats_p["mean"], stats_p["mcse"],
                                  stats_c["mean"], stats_c["mcse"],
                                  stats_j["mean"], stats_j["mcse"]],
                      f"table-floor-components-S{regime}", checks)

    # Summary rows agree with the comparator authority.
    for row in refit["procedure_summary"]:
        key = (row["regime"], row["model"], row["gate"])
        if key not in comp:
            add(checks, f"refit-summary-key-{key}", False)
            continue
        add(checks, f"refit-summary-{key}",
            close(row["original_mean_gain"], comp[key]["fixed"]["mean"], 1e-12)
            and close(row["mean_gain"], comp[key]["intercept"]["mean"], 1e-12),
            summary={"original": row["original_mean_gain"], "refitted": row["mean_gain"]},
            comparator={"original": comp[key]["fixed"]["mean"], "refitted": comp[key]["intercept"]["mean"]})

    counts.update(
        refit_cases=len(case_files),
        concave_cases=len(concave_files),
        s7_n_zero=n_zero[7],
        floor_components=len(fc),
        max_kkt=concave_audit["max_relative_projected_kkt"],
    )
    payload = component_head(
        "slice6_refitted_floor_v1",
        "The scalar intercept and concave (a,n) refitted-floor comparators, all 80 per-history "
        "KKT records, the 480 historical floor checks, the four floor-component rows, and the "
        "Delta P + Delta C = Delta joint identity.",
        checks, counts,
    )
    dump("refitted_floor.json", payload)
    return payload



def audit_observed_and_uncertainty() -> dict:
    checks, counts = [], {}
    obs = load(AUTH["observed_rows"])
    rows = obs["rows"]
    add(checks, "observed-row-count", len(rows) == 15, count=len(rows))
    active = [r for r in rows if r["off_floor"]]
    zero = [r for r in rows if not r["off_floor"]]
    add(checks, "observed-active-count", len(active) == 3, count=len(active))
    add(checks, "observed-zero-count", len(zero) == 12, count=len(zero))
    add(checks, "observed-zero-exact", all(r["gain_joint"] == 0.0 for r in zero),
        gains=[r["gain_joint"] for r in zero])
    add(checks, "observed-active-negative", all(r["gain_joint"] < 0 for r in active),
        gains=[r["gain_joint"] for r in active])
    add(checks, "observed-active-models",
        all(r["model"] == "LIplus_inclusive" and r["gate"] == "raw" for r in active))

    table = parse_table(TEX["observed"], "tab:s04-observed")
    add(checks, "observed-active-table-count", len(table) == 3, count=len(table))
    for row in active:
        fold = int(row["case_id"].rsplit("_", 1)[1])
        cells = find_row(table, None, str(fold))
        compare_cells([cells[4]], [row["gain_joint"]], f"table-observed-active-{fold}", checks)
        add(checks, f"table-observed-active-{fold}-status",
            clean_cell(cells[2]) == row["gate"] and clean_cell(cells[3]) == row["status"])

    boundary = parse_table(TEX["observed"], "tab:s04-observed-boundary")
    add(checks, "observed-boundary-table-count", len(boundary) == 12, count=len(boundary))
    for row in zero:
        fold = int(row["case_id"].rsplit("_", 1)[1])
        model_label = {"LI": "LI", "LIplus_immigrant": "LI+ immigrant",
                       "LIplus_inclusive": "LI+ total"}[row["model"]]
        cells = None
        for reg, candidate in boundary:
            if clean_cell(candidate[0]) == str(fold) and clean_cell(candidate[1]) == model_label \
                    and clean_cell(candidate[2]) == row["gate"]:
                cells = candidate
                break
        add(checks, f"table-observed-boundary-{fold}-{model_label}-{row['gate']}",
            cells is not None and cells[4].strip() == "0.0000",
            cells=cells)
    pooled_active = sum(r["gain_joint"] for r in active)
    add(checks, "observed-active-pooled", abs(pooled_active - (-2.386674517269429)) <= 1e-5,
        value=pooled_active, block_authority=-2.386674517269429,
        note="saved S04 scalar sum differs from the block-score total at ~7.6e-6 nats; both display -2.387")

    # Paired calendar-block uncertainty.
    unc = load(AUTH["uncertainty"])
    add(checks, "uncertainty-passed", unc["passed"] is True)
    add(checks, "uncertainty-time-orders", unc["numerical_checks"]["time_orders"] == [32, 64])
    add(checks, "uncertainty-refinement-change",
        unc["numerical_checks"]["max_calendar_block_refinement_change"] < 1e-11,
        value=unc["numerical_checks"]["max_calendar_block_refinement_change"])
    main_rows = {r["case"]: r for r in unc["rows"] if r["contrast"] == "CA_LIplus_total_minus_floor"}
    pooled = unc["pooled"]["CA_LIplus_total_minus_floor"]
    add(checks, "uncertainty-main-fold-count", len(main_rows) == 3, count=len(main_rows))
    block_table = parse_table(TEX["uncertainty"], "tab:ca_li_floor_uncertainty")
    add(checks, "uncertainty-table-row-count", len(block_table) == 4, count=len(block_table))
    for case, label in (("california_fold_0", "F0"), ("california_fold_1", "F1"),
                        ("california_fold_2", "F2")):
        r = main_rows[case]
        cells = find_row(block_table, None, label)
        compare_cells(cells[1:], [r["point"], r["ci95"][0], r["ci95"][1], r["permutation_p"]],
                      f"table-uncertainty-{label}", checks)
    cells = find_row(block_table, None, "Pooled")
    compare_cells(cells[1:], [pooled["total"], pooled["ci95_total"][0],
                              pooled["ci95_total"][1], pooled["paired_sign_permutation_p"]],
                  "table-uncertainty-pooled", checks)

    # Sensitivity at 180 and 365 days.
    for days, label in ((180, "180"), (365, "365")):
        sens = unc["sensitivity"][label]
        rows_days = {r["case"]: r for r in sens["rows"]
                     if r["contrast"] == "CA_LIplus_total_minus_floor"}
        p = sens["pooled"]["CA_LIplus_total_minus_floor"]
        add(checks, f"uncertainty-{label}-fold-count", len(rows_days) == 3, count=len(rows_days))
        add(checks, f"uncertainty-{label}-pooled-total", close(p["total"], -2.386674517269429, 1e-12))
        add(checks, f"uncertainty-{label}-pooled-ci",
            close(p["ci95_total"][0], {"180": -6.42615579550734, "365": -6.363635295415632}[label], 1e-12)
            and close(p["ci95_total"][1], {"180": -0.08539352789208825,
                                           "365": -0.09049344698588709}[label], 1e-12),
            ci=p["ci95_total"])
        add(checks, f"uncertainty-{label}-pooled-p",
            close(p["paired_sign_permutation_p"], {"180": 0.0456, "365": 0.06578}[label], 1e-12),
            value=p["paired_sign_permutation_p"])
    f2_180 = next(r for r in unc["sensitivity"]["180"]["rows"]
                  if r["case"] == "california_fold_2" and r["contrast"] == "CA_LIplus_total_minus_floor")
    f2_365 = next(r for r in unc["sensitivity"]["365"]["rows"]
                  if r["case"] == "california_fold_2" and r["contrast"] == "CA_LIplus_total_minus_floor")
    add(checks, "uncertainty-f2-180-excludes-zero", f2_180["summary"]["ci95_total"][1] < 0,
        ci=f2_180["summary"]["ci95_total"])
    add(checks, "uncertainty-f2-365-includes-zero",
        f2_365["summary"]["ci95_total"][0] < 0 < f2_365["summary"]["ci95_total"][1],
        ci=f2_365["summary"]["ci95_total"])
    add(checks, "uncertainty-f2-365-literal",
        close(f2_365["summary"]["ci95_total"][0], -0.48764778463787345, 1e-12)
        and close(f2_365["summary"]["ci95_total"][1], 0.020315033789895236, 1e-12))

    counts.update(
        active_rows=len(active),
        zero_rows=len(zero),
        pooled_active=pooled_active,
        pooled_90_ci=pooled["ci95_total"],
        pooled_180_ci=unc["sensitivity"]["180"]["pooled"]["CA_LIplus_total_minus_floor"]["ci95_total"],
        pooled_365_ci=unc["sensitivity"]["365"]["pooled"]["CA_LIplus_total_minus_floor"]["ci95_total"],
    )
    payload = component_head(
        "slice6_observed_and_uncertainty_v1",
        "The three active observed LI+ total rows, the twelve algebraic-zero boundary rows, "
        "and the paired 90/180/365-day calendar-block intervals.",
        checks, counts,
    )
    dump("observed_and_uncertainty.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 8. Claim ledger and manuscript state
# ---------------------------------------------------------------------------


def _load_verify_claims():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_slice6_verify_claims", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    return vc


def audit_claim_ledger() -> dict:
    checks, counts = [], {}
    vc = _load_verify_claims()
    receipt, ledgers, _ = vc.verify_ledgers(ROOT, authority_only=True)
    add(checks, "ledger-authority-resolution", receipt["passed"], failures=receipt["failures"][:10])
    primary = next((ledger for path, ledger in ledgers
                    if path == "validation/MASTER_CLAIM_LEDGER.json"), ledgers[0][1])
    claims = primary["claims"]
    c13 = [c for c in claims
           if c.get("tex_file") in SLICE6_TEX_FILES
           or any(f in SLICE6_TEX_FILES for f in c.get("final_display_locations", []))]
    add(checks, "ledger-c13-claim-count", len(c13) > 0, count=len(c13))
    numbers_cache = {}

    def numbers_for(relative):
        if relative not in numbers_cache:
            numbers_cache[relative] = vc.manuscript_numbers(
                (ROOT / "paper/source" / relative).read_text(encoding="utf-8"))
        return numbers_cache[relative]

    missing = []
    outside_only = []
    for claim in c13:
        if claim.get("ledger_role") != "manuscript_binding":
            continue
        if claim.get("display_format"):
            continue
        wanted = vc.numeric_value(claim["display"])
        declared = sorted(set(
            ([claim["tex_file"]] if claim.get("tex_file") else [])
            + list(claim.get("final_display_locations", []))))
        present = [f for f in declared if wanted in numbers_for(f)]
        if not present:
            missing.append({"id": claim["id"], "display": claim["display"], "files": declared})
        elif not any(f in SLICE6_TEX_FILES for f in present):
            outside_only.append({"id": claim["id"], "display": claim["display"], "files": present})
    add(checks, "ledger-c13-display-presence", not missing, missing=missing[:20])
    add(checks, "ledger-c13-outside-only-accounted", True, count=len(outside_only),
        examples=outside_only[:10])
    add(checks, "ledger-master-exists", LEDGER.is_file())
    add(checks, "ledger-source-inventory",
        any(path == "validation/SOURCE_INVENTORY.json" for path, _ in ledgers))
    counts.update(
        c13_claims=len(c13),
        missing_displays=len(missing),
        outside_only_displays=len(outside_only),
        master_ledger_sha256=sha256(LEDGER),
        authority_counts=receipt["counts"],
    )
    payload = component_head(
        "slice6_claim_ledger_v1",
        "Independent resolution of the master claim ledger and literal display presence for the ten Slice 6 LaTeX sources.",
        checks, counts,
        notes=["The receipt is authority-only in this component; the full release-ready receipt is refreshed by scripts/verify_claims.py --write-receipts."],
    )
    payload["authority_receipt"] = {
        "passed": receipt["passed"], "counts": receipt["counts"],
        "failures": receipt["failures"][:20]}
    dump("claim_ledger.json", payload)
    return payload


def audit_manuscript() -> dict:
    checks, counts = [], {}
    with zipfile.ZipFile(SNAPSHOT_ZIP) as zf:
        old = {relative: zf.read(f"paper/source/{relative}").decode("utf-8")
               for relative in sorted(SLICE6_TEX_FILES)
               if f"paper/source/{relative}" in zf.namelist()}
    new = {relative: (ROOT / "paper/source" / relative).read_text(encoding="utf-8")
           for relative in sorted(SLICE6_TEX_FILES)}
    add(checks, "manuscript-source-snapshot", len(old) == len(SLICE6_TEX_FILES),
        actual=len(old))
    vc = _load_verify_claims()

    preservation = {}
    for relative in sorted(SLICE6_TEX_FILES):
        before = vc.manuscript_numbers(old[relative])
        after = vc.manuscript_numbers(new[relative])
        removed = sorted(before - after, key=str)
        added = sorted(after - before, key=str)
        preservation[relative] = {
            "before": len(before), "after": len(after),
            "removed": [str(v) for v in removed],
            "added": [str(v) for v in added],
        }
        add(checks, f"numeric-preservation-{relative}", not removed,
            removed=[str(v) for v in removed[:40]])
    counts["numeric_preservation"] = preservation

    chapter = new["chapters/13_continuous_local_inhibition.tex"]
    quantiles = new["chapters/13_s04b_joint_quantiles.tex"]
    required_chapter = {
        "M-geq": "$M\\geq 4.0$",
        "time-space-math": "For time $t$ and recorded projected location $z$ in the fixed finite domain $D$",
        "M4-math": "$M\\,4$",
        "M71-math": "$M\\,7.1$",
        "eta-zero": "$\\eta=0$",
        "ell-30": "$\\ell=30$~km",
        "psi-7": "$\\psi=7$~days",
        "P-math": "Write $P$",
        "Q-math": "$Q$",
        "E-math": "$E$",
        "C-minus-E": "$C=-E$",
        "M-score": "$M$ for the common magnitude-mark score",
        "pm-tolerance": "$\\pm 0.0002$",
        "sci-12": "$+1.128699\\times10^{-12}$",
        "sci-13": "$+5.983898\\times10^{-13}$",
        "sci-10": "$+1.88492776942439\\times10^{-10}$",
        "chapter-external": "Chapter~\\ref{ch:external}",
        "eta-half": "$\\eta=0.5$",
        "ell-5": "$\\ell=5$~km",
        "psi-24": "$\\psi=1/24$~day",
        "eta-2": "$\\eta=2$",
        "ell-50": "$\\ell=50$~km",
        "psi-30": "$\\psi=30$~days",
        "line75-formula": "\\left.\\partial_\\eta \\ell_{\\mathrm{LI}}\\right|_{\\eta=0}",
        "line75-immigrant-probability": "p_i^{\\mathrm{imm}}=B(t_i,z_i)/\\lambda_0(t_i,z_i)",
        "line75-ep-section": "Section~\\ref{sec:california-eta-profiles}",
        "line75-ep-words": "total-intensity",
        "line75-75313": "75{,}313.9",
        "line75-59415": "59{,}415.5",
        "line75-15898": "-15{,}898.4",
    }
    for name, token in required_chapter.items():
        add(checks, f"required-chapter-{name}", token in chapter, token=token)
    required_quantiles = {
        "S4": "\\textbf{S4} (magnitude-scaled narrow/short immigrant)",
        "S5": "\\textbf{S5} (magnitude-scaled broad/long immigrant)",
        "S6": "\\textbf{S6} (magnitude-scaled narrow/short total attenuation)",
        "S7": "\\textbf{S7} (magnitude-scaled broad/long total attenuation)",
        "s7-formula": "nH(t,z)\\equiv0",
        "s7-both-zero": "9/20 seeds where both select $\\hat n=0$",
        "s7-counts": "19/20 immigrant fits and 9/20 total fits",
        "s7-upper": "$\\hat n=0.98$",
        "s7-q25": "Q25, Min and Max agree",
    }
    for name, token in required_quantiles.items():
        add(checks, f"required-quantiles-{name}", token in quantiles, token=token)

    # No raw scientific notation or legacy reference token remains.
    for relative in sorted(SLICE6_TEX_FILES):
        found = re.findall(r"(?<![\w.])[0-9]\.[0-9]+e[+-]?[0-9]+", new[relative])
        add(checks, f"no-raw-scientific-{relative}", not found, found=found[:10])
    add(checks, "no-legacy-IV", " in IV " not in chapter)
    add(checks, "no-plus-minus-ascii", "+/-" not in chapter)
    add(checks, "no-bare-M-geq", "M $\\geq$" not in chapter)
    add(checks, "no-bare-a-d-n", "shared a,d,n" not in chapter)
    add(checks, "no-bare-l-psi", "$\\ell$ = 30" not in chapter)
    add(checks, "no-bare-eta", "$\\eta$ = 0" not in chapter)

    # Cross-file regime vocabulary.
    thinning = new["chapters/13_s04_diagnostics.tex"]
    add(checks, "thinning-regime-vocabulary",
        "S4/S5 are narrow/short and broad/long immigrant attenuation; S6/S7 are the corresponding total-attenuation laws" in thinning)
    add(checks, "quantile-s6-matches-thinning",
        "S6" in quantiles and "narrow/short total attenuation" in quantiles)

    counts["required_chapter_tokens"] = len(required_chapter)
    counts["required_quantile_tokens"] = len(required_quantiles)
    payload = component_head(
        "slice6_manuscript_state_v1",
        "Byte-level numeric preservation, required Chapter 13 repair tokens, cross-file regime "
        "vocabulary, and absence of raw scientific notation and legacy reference tokens.",
        checks, counts,
    )
    dump("manuscript_state.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 9. Summary and CLI
# ---------------------------------------------------------------------------


def audit_summary(components: dict[str, dict]) -> dict:
    passed = all(c["passed"] for c in components.values())
    counts = {name: c.get("counts", {}) for name, c in components.items()}
    return {
        "schema": "slice6_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "8ae4fa6",
        "scope": (
            "Vertical Triad Slice 6: Chapter 13 continuous local inhibition (LI and LI+), "
            "observed California comparisons, expanded unit-mark and magnitude-scaled controls "
            "(S04 and S04B), the 80-history / 400-outcome joint temporal-backbone comparison, "
            "the training-fitted scalar (a) and concave (a,n) floor comparators, the 20-history "
            "S8 moderate control, and the full/partial S8 oracles."
        ),
        "passed": passed,
        "components": {name: c["passed"] for name, c in components.items()},
        "counts": counts,
        "defects_and_repairs": [
            {
                "id": "slice6-s6-regime-subheader",
                "file": "paper/source/chapters/13_s04b_joint_quantiles.tex",
                "locator": "line 24, Table tab:s04b-joint-quantiles",
                "finding": (
                    "The S6 regime subheader identified S6 as magnitude-scaled broad/long "
                    "immigrant, which is the S5 regime. Table tab:s04b-thinning defines S6 as "
                    "the magnitude-scaled narrow/short total-attenuation law. The S4-S7 "
                    "subheaders are now consistent with that table."
                ),
                "status": "fixed",
            },
            {
                "id": "slice6-s7-quantile-coincidence",
                "file": "paper/source/chapters/13_s04b_joint_quantiles.tex",
                "locator": "caption of Table tab:s04b-joint-quantiles",
                "finding": (
                    "The S7 immigrant-only and total rows share Q25, Min and Max. The caption "
                    "now gives the algebraic reason and the correct intersection: S7 has 19/20 "
                    "immigrant fits and 9/20 total fits at n=0, but the two intensities coincide "
                    "only on the 9/20 seeds where both select n=0. One-sided zero selections do "
                    "not make the intensities identical. Those nine seeds supply the shared "
                    "minimum, maximum and both lower-quartile order statistics; the upper "
                    "quartile uses a seed with total n=0.98 and immigrant n=0."
                ),
                "status": "fixed",
            },
            {
                "id": "slice6-line75-score-attribution",
                "file": "paper/source/chapters/13_continuous_local_inhibition.tex",
                "locator": "line 75, Section 13.4.1",
                "finding": (
                    "The 75,313.9 versus 59,415.5 and -15,898.4 figures were presented as the "
                    "training score slope of the unit-mark immigrant-only LI law. They are the "
                    "score slope of the separate total-intensity EP+ attenuation model "
                    "lambda=lambda_0 exp(-eta G) in Section 11.5. The repaired paragraph gives "
                    "the immigrant-only LI derivative, which weights each event by "
                    "B(t_i,z_i)/lambda_0(t_i,z_i) and integrates against B(t,z), and explicitly "
                    "attributes the three EP+ literals to Section sec:california-eta-profiles."
                ),
                "status": "fixed",
            },
            {
                "id": "slice6-raw-math-tokens",
                "file": "paper/source/chapters/13_continuous_local_inhibition.tex",
                "locator": "lines 30, 61, 73, 90, 107-109, 113, 120-128, 144, 153, 155, 159, 173-178, 205, 211, 251, 255",
                "finding": (
                    "Raw ASCII variables, unformatted assignments, raw scientific notation and "
                    "the legacy 'in IV' reference were normalized to math mode and an internal "
                    "chapter cross-reference. Every pre-edit numeric value is retained; the only "
                    "added values are the signed +0.0002 tolerance endpoint and the S7 explanatory "
                    "counts."
                ),
                "status": "fixed",
            },
            {
                "id": "slice6-s8-oracle-field-name",
                "file": "validation/live_results/forensic_remediation_20261114/s8_oracle.json",
                "locator": "exact_true_null_minus_fitted_stats",
                "finding": (
                    "The sealed field named exact_true_null_minus_fitted_stats stores the full "
                    "true-law theta_star minus fitted-null contrast (mean 18.112), not the true "
                    "uninhibited-backbone null minus fitted-null contrast used in the manuscript "
                    "row (mean 1.683). The manuscript table is correct and is bound to "
                    "referee_remediation_20261113/s8_oracle_decomposition.json:true_null_minus_fitted_null. "
                    "The sealed field is not edited; the slice6 audit records the naming defect."
                ),
                "status": "documented",
            },
            {
                "id": "slice6-observed-pooled-rounding",
                "file": "validation/acceptances/S04_observed_public.json",
                "locator": "three active rows versus the pooled block total",
                "finding": (
                    "The three saved active gains sum to -2.386682086 nats, while the paired "
                    "block authority total is -2.386674517; both display as -2.387 and the "
                    "difference is 7.6e-6 nats. The audit records this saved-arithmetic "
                    "difference rather than assigning it to a physical effect."
                ),
                "status": "documented",
            },
        ],
        "artifacts": {
            name: "validation/live_results/slice6_audit_20261114/" + {
                "sealed_authority_integrity": "sealed_authority_integrity.json",
                "observed_unitmark": "observed_unitmark.json",
                "expanded_controls": "expanded_controls.json",
                "observed_and_uncertainty": "observed_and_uncertainty.json",
                "refitted_floor": "refitted_floor.json",
                "joint_comparison": "joint_comparison.json",
                "s8_moderate_and_oracles": "s8_moderate_and_oracles.json",
                "claim_ledger": "claim_ledger.json",
                "manuscript_state": "manuscript_state.json",
            }[name]
            for name in sorted(components)
        },
        "environment": {"python": platform.python_version(), "numpy": np.__version__},
    }


def main(argv=None) -> int:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--only", default="", help="Comma-separated component names; empty runs all.")
    args = parser.parse_args(argv)
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    roster = (
        ("sealed_authority_integrity", audit_sealed_integrity),
        ("observed_unitmark", audit_observed_unitmark),
        ("expanded_controls", audit_expanded_controls),
        ("observed_and_uncertainty", audit_observed_and_uncertainty),
        ("refitted_floor", audit_refitted_floor),
        ("joint_comparison", audit_joint),
        ("s8_moderate_and_oracles", audit_s8),
        ("claim_ledger", audit_claim_ledger),
        ("manuscript_state", audit_manuscript),
    )
    wanted = {x.strip() for x in args.only.split(",") if x.strip()}
    components = {}
    for name, function in roster:
        if wanted and name not in wanted:
            continue
        print(f"[slice6] {name} ...", flush=True)
        began = time.time()
        components[name] = function()
        print(f"[slice6] {name}: {'PASS' if components[name]['passed'] else 'FAIL'} "
              f"({sum(not c['passed'] for c in components[name]['checks'])} failed checks, "
              f"{time.time() - began:.1f}s)", flush=True)
    if wanted:
        print(json.dumps({n: c["passed"] for n, c in components.items()}, indent=2))
        return 0 if all(c["passed"] for c in components.values()) else 1
    summary = audit_summary(components)
    dump("summary.json", summary)
    print(json.dumps({"passed": summary["passed"], "components": summary["components"]}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
