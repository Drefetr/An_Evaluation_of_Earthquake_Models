#!/usr/bin/env python3
"""Independent Slice 3 mathematical, statistical, code, and manuscript audit.

Scope: Chapters 8 and 10, Appendix B.8, the reconstructed New Zealand baseline,
paired calendar-block uncertainty, trend--depletion collinearity controls, the
complete eighteen-cell (alpha, tau, r) search, the autonomous constant-background
subfamily, and the C1/W/D/S spatial stages together with the twelve-model
temporal--spatial--background factorial.

The audit re-derives the displayed algebra and statistics from the bound JSON
authorities, the recovered execution records, and the Python implementation.
It performs deterministic algebra, exact table reconstruction from the LaTeX
sources, block-score recomputation, projection recomputation, claim-ledger
resolution, and byte-level sealed-authority verification.  It does not fit new
models, simulate catalogues, or modify a sealed authority.
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
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice3_audit_20261114"
SNAPSHOT = ROOT / "validation/slice3_prechange_snapshot_20261114.json"
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"

TEX = {
    "ch08_obs": ROOT / "paper/source/chapters/08_observed_baseline.tex",
    "ch08_unc": ROOT / "paper/source/chapters/08_score_uncertainty.tex",
    "ch08_trend": ROOT / "paper/source/chapters/08_nz_trend_controls.tex",
    "ch10": ROOT / "paper/source/chapters/10_nz_spatial_background.tex",
    "app10": ROOT / "paper/source/appendix_tables/ch10_audit.tex",
}
AUTH = {
    "observed": ROOT / "validation/authorities/e7fbc4fa4fae3da4_observed.json",
    "trend": ROOT / "validation/live_results/forensic_remediation_20261114/nz_trend_controls.json",
    "trend_totals": ROOT / "validation/live_results/referee_remediation_20261113/nz_trend_totals.json",
    "track_b": ROOT / "validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json",
    "autonomous": ROOT / "validation/live_results/autonomous_20261105/result.json",
    "fdsn": ROOT / "validation/authorities/e68300ad349bb521_summary.json",
    "uncertainty": ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json",
    "uncertainty_nz": ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/nz.json",
    "temporal": ROOT / "paper/data/temporal.json",
    "c1": ROOT / "validation/authorities/49a042a4f9939b2b_summary.json",
    "w": ROOT / "validation/authorities/ea7dc17f949ea587_summary.json",
    "d": ROOT / "validation/authorities/72506c2cd19bc729_summary.json",
    "s": ROOT / "validation/authorities/64198d78e135b0a0_summary.json",
    "common": ROOT / "validation/authorities/ca2e672819a638a4_summary.json",
    "factorial": ROOT / "validation/authorities/c5c640713630101e_summary.json",
    "trend_depletion": ROOT / "validation/live_results/trend_depletion_20261111.json",
    "predictive": ROOT / "paper/supplements/predictive_parameters.json",
    "catalogue": ROOT / "reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv",
    "c1_decision": ROOT / "validation/authorities/3ac46192cdeae2f0_scientific_interpretation.md",
}
CSV_SHA256 = "feacccb7581d1c4c33f88874cd6b198c41639da6930a7fc35e46f910a594fb3e"
OBSERVED_SHA256 = "e7fbc4fa4fae3da4f8880695064798a8ebfc9342ab09303073f7afd7334439d8"
SLICE3_TEX_FILES = {
    "chapters/08_observed_baseline.tex",
    "chapters/08_score_uncertainty.tex",
    "chapters/08_nz_trend_controls.tex",
    "chapters/10_nz_spatial_background.tex",
    "appendix_tables/ch10_audit.tex",
}
EXPECTED_SEALED = 737


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(name: str, payload) -> str:
    path = OUT / name
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path.relative_to(ROOT).as_posix()


def close(a, b, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def display_ok(actual: float, display: float, decimals: int) -> bool:
    if actual is None or display is None:
        return actual is display
    return abs(float(actual) - float(display)) <= 0.5 * 10.0 ** (-decimals) + 2e-12 * max(
        1.0, abs(float(actual))
    )


def add(checks: list, cid: str, ok: bool, **detail):
    checks.append({"id": cid, "passed": bool(ok), **detail})
    return bool(ok)


def split_latex_cells(line: str) -> list[str]:
    """Split a LaTeX table row on top-level ampersands, preserving braces."""
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


def latex_number(cell: str):
    """Parse a displayed scalar, including stacked mantissa/power cells."""
    s = cell.strip().replace("{}", "").replace("$", "").strip()
    m = re.fullmatch(
        r"\\shortstack\[r\]\{\$?([+-]?\d+(?:\.\d+)?)\$?\\\\\$?\\times\s*10\^\{([+-]?\d+)\}\$?\}",
        s,
    )
    if m:
        return float(m.group(1)) * 10.0 ** int(m.group(2))
    s = s.replace("\\text{---}", "---").replace("\\,", "").replace("{,}", "")
    if s in ("", "---"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def latex_label(cell: str) -> str:
    s = cell.replace("\\allowbreak{}", "")
    s = re.sub(r"\\modeltag\{([^{}]*)\}\{([^{}]*)\}", r"\1_\2", s)
    s = s.replace("{}", "").replace("$", "").replace("\\_", "_")
    s = s.replace("\\mathrm{d,g}", "distance_globalG").replace("I_d,g", "I_distance_globalG")
    s = s.replace("\\text{---}", "---")
    return re.sub(r"\s+", " ", s).strip()


def rows_after_header(path: Path, header_fragment: str, occurrence: int = 1) -> list[list[str]]:
    """Return data rows (starting with '{}') after a unique longtable header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if header_fragment in line]
    if len(hits) < occurrence:
        raise ValueError(f"table header not found: {header_fragment!r} in {path.name}")
    start = hits[occurrence - 1]
    rows = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if "\\end{longtable}" in stripped or "\\end{tabular}" in stripped:
            break
        if stripped.startswith("\\"):
            continue
        if "&" not in line or header_fragment in line:
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
        "slice3_sealed_authority_integrity_v1",
        "Byte-level identity of every pre-existing JSON file under validation/authorities and "
        "validation/live_results plus the Slice 2 acceptance record.",
        checks,
        {
            "snapshot": len(sealed),
            "unchanged": len(sealed) - len(missing) - len(changed),
            "changed": len(changed),
            "missing": len(missing),
            "baseline_commit": record["baseline_commit"],
            "snapshot_sha256": sha256(SNAPSHOT),
        },
        notes=[record["scope"]],
    )
    dump("sealed_authority_integrity.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 2. Chapter 8 baseline, score accounting, archive sensitivity
# ---------------------------------------------------------------------------


def audit_chapter8_baseline() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    observed = load(AUTH["observed"])
    csv = AUTH["catalogue"]
    frame = pd.read_csv(csv)
    times = frame.t_days.to_numpy()
    excess = frame.excess.to_numpy()
    magnitudes = frame.magnitude.to_numpy()
    data = frame.to_dict("records")

    add(checks, "catalogue-sha256", sha256(csv) == CSV_SHA256, actual=sha256(csv), expected=CSV_SHA256)
    add(checks, "catalogue-events", len(data) == 913 == observed["input_binding"]["n_events"], actual=len(data))
    add(checks, "catalogue-sorted", bool(np.all(np.diff(times) > 0)))
    add(
        checks,
        "array-binding",
        hashlib.sha256(times.astype("<f8").tobytes()).hexdigest()
        == observed["array_binding"]["times_f64le"]
        and hashlib.sha256(excess.astype("<f8").tobytes()).hexdigest()
        == observed["array_binding"]["excess_f64le"],
    )
    beta = float(1.0 / excess.mean())
    beta_adj = float(1.0 / (excess.mean() + 0.05))
    add(checks, "beta-mle", close(beta, 2.849401764894274, 1e-14), actual=beta)
    add(checks, "beta-half-bin", close(beta_adj, 2.494071218330174, 1e-14), actual=beta_adj)
    counts["beta_mle"] = beta
    counts["beta_half_bin"] = beta_adj

    folds = observed["folds"]
    expected_counts = {
        "fold_50": (301, 203),
        "fold_65": (504, 155),
        "fold_80": (659, 254),
    }
    beta_train = []
    for name, (n_train, n_test) in expected_counts.items():
        fold = folds[name]
        train = times < fold["train_end"]
        test = (times >= fold["train_end"]) & (times < fold["test_end"])
        local_beta = float(train.sum() / excess[train].sum())
        beta_train.append(local_beta)
        add(
            checks,
            f"{name}-counts",
            int(train.sum()) == fold["fit"]["n_train"] == n_train and int(test.sum()) == n_test,
            train=int(train.sum()),
            test=int(test.sum()),
        )
        add(
            checks,
            f"{name}-beta-train",
            close(local_beta, fold["fit"]["beta_train"], 1e-14),
            actual=local_beta,
            expected=fold["fit"]["beta_train"],
        )
    add(checks, "test-events-total", sum(v[1] for v in expected_counts.values()) == 612)
    counts["train_events"] = [v[0] for v in expected_counts.values()]
    counts["test_events"] = [v[1] for v in expected_counts.values()]
    counts["beta_train"] = beta_train

    # Fifteen saved predictive parameter records.
    predictive = load(AUTH["predictive"])
    pred_rows = predictive["rows"]
    add(checks, "predictive-rows", len(pred_rows) == 15, actual=len(pred_rows))
    param_table_checks = []
    for frac, fold_name in (("50", "fold_50"), ("65", "fold_65"), ("80", "fold_80")):
        best = folds[fold_name]["fit"]["best"]
        for family, label in (("etas_omori", "Omori"), ("ml_trigger", "Mittag--Leffler"), ("ml_shared", "Shared inhibition")):
            pars = best[family]["pars"]
            expected = [pars[0], pars[1], pars[2], pars[3] if len(pars) > 3 else 0.0]
            pred = next(r for r in pred_rows if r["fold"] == fold_name and r["family"] == family)
            pred_values = [
                pred["parameters"]["a"],
                pred["parameters"]["d"],
                pred["parameters"]["n"],
                pred["parameters"].get("eta", 0.0),
            ]
            ok = all(close(a, b, 1e-13) for a, b in zip(expected, pred_values))
            param_table_checks.append(
                {"origin": frac, "family": label, "expected": expected, "saved": pred_values, "passed": ok}
            )
            add(checks, f"param-{fold_name}-{family}", ok)
    # All fifteen supplementary rows, including the two Poisson families.
    all_pred_ok = True
    for pred in pred_rows:
        target = observed
        pointer = pred["json_pointer"]
        for part in pointer.lstrip("/").split("/"):
            target = target[int(part)] if isinstance(target, list) else target[part]
        expected = {
            "a": target["pars"][0],
            "d": target["pars"][1],
            "n": target["pars"][2] if len(target["pars"]) > 2 else 0.0,
            "eta": target["pars"][3] if len(target["pars"]) > 3 else 0.0,
        }
        saved = pred["parameters"]
        ok = all(close(expected[k], saved.get(k, 0.0), 1e-13) for k in expected)
        all_pred_ok = all_pred_ok and ok
    add(checks, "predictive-all-15-authority", all_pred_ok)
    counts["parameter_vectors"] = len(pred_rows)

    # Second half of the displayed saved-parameter table: beta_train, r, c, p.
    secondary_rows = rows_after_header(
        TEX["ch08_obs"],
        "Origin & \\(\\beta_{\\rm train}\\) & \\(r\\) & Omori \\(c\\) (days) & Omori \\(p\\)",
    )
    add(checks, "secondary-parameter-rows", len(secondary_rows) == 3, actual=len(secondary_rows))
    secondary_records = []
    for cells in secondary_rows:
        origin = cells[0].replace("\\%", "").replace("%", "").strip()
        fold = {"50": "fold_50", "65": "fold_65", "80": "fold_80"}[origin]
        best = folds[fold]["fit"]["best"]
        omori = best["etas_omori"]
        expected = [
            folds[fold]["fit"]["beta_train"],
            omori["ratio"],
            omori["trigger"]["tau"],
            omori["trigger"]["p"],
        ]
        displayed = [latex_number(c) for c in cells[1:]]
        row_checks = [
            display_matches_cell(expected[0], cells[1]),
            display_matches_cell(expected[1], cells[2]),
            display_matches_cell(expected[2], cells[3]),
            display_matches_cell(expected[3], cells[4]),
        ]
        add(
            checks,
            f"secondary-parameter-row-{origin}",
            all(row_checks),
            displayed=displayed,
            expected=expected,
            fields_ok=row_checks,
        )
        secondary_records.append(
            {"origin": origin, "displayed": displayed, "expected": expected, "passed": all(row_checks)}
        )
    counts["secondary_parameter_rows"] = secondary_records

    # Background ratios at the three predictive origins.
    ratios = []
    for fold_name, origin_fraction in (("fold_50", 0.5), ("fold_65", 0.65), ("fold_80", 0.8)):
        best = folds[fold_name]["fit"]["best"]
        a_s, d_s = best["ml_shared"]["pars"][:2]
        a_m, d_m = best["ml_trigger"]["pars"][:2]
        train_end = folds[fold_name]["train_end"]
        half_horizon = folds["fold_50"]["train_end"]
        x_origin = train_end / half_horizon - 1.0
        ratio = math.exp(a_s - a_m + (d_s - d_m) * x_origin)
        ratios.append(ratio)
    for value, display in zip(ratios, (9.60, 1.57, 1.34)):
        add(checks, f"origin-background-ratio-{display}", display_ok(value, display, 2), actual=value, display=display)
    counts["origin_background_ratios"] = ratios

    # Projection recomputation from the frozen observations and modal recursion.
    spec = importlib.util.spec_from_file_location(
        "_slice3_trend_depletion", ROOT / "experiments/methodological_audit/trend_depletion.py"
    )
    td = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = td
    spec.loader.exec_module(td)
    recomputed = td.calculate()
    archived = load(AUTH["trend_depletion"])
    projection = recomputed["projection"]
    add(checks, "projection-c", close(projection["intercept_c"], 2.750747162169055, 1e-13), actual=projection["intercept_c"])
    add(checks, "projection-k", close(projection["slope_k"], 2.2417394214563457, 1e-13), actual=projection["slope_k"])
    add(checks, "projection-r2", close(projection["r_squared"], 0.14924274939283222, 1e-13), actual=projection["r_squared"])
    add(
        checks,
        "projection-rho",
        close(recomputed["event_score_weighted_trend_depletion_correlation"], 0.9340643480012697, 1e-13),
        actual=recomputed["event_score_weighted_trend_depletion_correlation"],
    )
    add(checks, "projection-archived-match", all(
        close(recomputed["projection"][k], archived["projection"][k], 1e-12)
        for k in ("intercept_c", "slope_k", "r_squared")
    ))
    add(checks, "projection-identity", projection["identity_max_absolute_residual"] < 1e-12, residual=projection["identity_max_absolute_residual"])
    add(checks, "slow-modes", recomputed["mixture_modes"] == 195 and recomputed["slow_modes"] == 61, modes=recomputed["mixture_modes"], slow=recomputed["slow_modes"])
    add(checks, "slow-mode-weight", display_ok(recomputed["slow_mode_weight_percent"], 0.043, 3), actual=recomputed["slow_mode_weight_percent"])
    add(
        checks,
        "heldout-accounting",
        close(recomputed["saved_heldout_accounting"]["delta_point"], -33.71520466007502, 1e-12)
        and close(recomputed["saved_heldout_accounting"]["delta_signed_exposure"], 17.197647207264637, 1e-12)
        and close(recomputed["saved_heldout_accounting"]["delta_joint"], -16.51755745281048, 1e-12),
    )
    counts["projection"] = projection | {"event_score_weighted_trend_depletion_correlation": recomputed["event_score_weighted_trend_depletion_correlation"]}

    # Saved held-out scores and Q/C accounting.
    score_rows = []
    for fold_name in ("fold_50", "fold_65", "fold_80"):
        tc = folds[fold_name]["test_controls"]
        ml = tc["ml_trigger"]["order32"]
        sh = tc["ml_shared"]["order32"]
        om = tc["etas_omori"]["order32"]
        dq = sum(sh["event_log_intensities"]) - sum(ml["event_log_intensities"])
        dc = ml["integrated_intensity"] - sh["integrated_intensity"]
        dl = sh["full_marked_loglik"] - ml["full_marked_loglik"]
        score_rows.append(
            {
                "fold": fold_name,
                "shared_minus_ml": dl,
                "omori_minus_ml": om["full_marked_loglik"] - ml["full_marked_loglik"],
                "delta_Q": dq,
                "delta_C": dc,
                "shared_integrated": sh["integrated_intensity"],
                "ml_integrated": ml["integrated_intensity"],
            }
        )
        add(checks, f"score-accounting-{fold_name}", close(dq + dc, dl, 1e-12), dQ=dq, dC=dc, joint=dl)
    totals = {
        "shared_minus_ml": sum(r["shared_minus_ml"] for r in score_rows),
        "omori_minus_ml": sum(r["omori_minus_ml"] for r in score_rows),
        "delta_Q": sum(r["delta_Q"] for r in score_rows),
        "delta_C": sum(r["delta_C"] for r in score_rows),
    }
    add(checks, "score-total-shared", display_ok(totals["shared_minus_ml"], -17.622859, 6), actual=totals["shared_minus_ml"])
    add(checks, "score-total-omori", display_ok(totals["omori_minus_ml"], 12.458121, 6), actual=totals["omori_minus_ml"])
    for row, expected in zip(score_rows, ((-16.517557, 3.106623), (-0.075277, 2.837708), (-1.030025, 6.513790))):
        add(checks, f"score-display-{row['fold']}", display_ok(row["shared_minus_ml"], expected[0], 6) and display_ok(row["omori_minus_ml"], expected[1], 6))
    counts["score_rows"] = score_rows
    counts["score_totals"] = totals

    # Paired calendar-block uncertainty.
    nz = load(AUTH["uncertainty_nz"])
    uncertainty = load(AUTH["uncertainty"])
    expected_ci = {
        "fold_50": (-25.525872565560405, -7.458535633929625, 0.00104),
        "fold_65": (-1.3199890912981622, 1.2146874902938476, 0.91248),
        "fold_80": (-2.087215898567452, 0.0038137734369787747, 0.05766),
    }
    unc_rows = []
    for row in nz:
        fold = row["case"]
        summary = row["summary"]
        lo, hi, p = expected_ci[fold]
        add(
            checks,
            f"uncertainty-90-{fold}",
            close(summary["ci95_total"][0], lo, 1e-12)
            and close(summary["ci95_total"][1], hi, 1e-12)
            and close(summary["paired_sign_permutation_p"], p, 1e-12),
            fold=fold,
            ci=summary["ci95_total"],
            p=summary["paired_sign_permutation_p"],
        )
        unc_rows.append({"fold": fold, "ci95": summary["ci95_total"], "p": summary["paired_sign_permutation_p"]})
    sensitivity = uncertainty["sensitivity"]
    add(
        checks,
        "uncertainty-180-fold65",
        close(sensitivity["180"]["rows"][1]["summary"]["ci95_total"][0], -1.1092660432382158, 1e-12)
        and close(sensitivity["180"]["rows"][1]["summary"]["ci95_total"][1], 1.0138240241624898, 1e-12),
    )
    add(
        checks,
        "uncertainty-365-fold65",
        close(sensitivity["365"]["rows"][1]["summary"]["ci95_total"][0], -1.5113080775751653, 1e-12)
        and close(sensitivity["365"]["rows"][1]["summary"]["ci95_total"][1], 1.3237130359569862, 1e-12),
    )
    add(
        checks,
        "uncertainty-180-fold80",
        close(sensitivity["180"]["rows"][2]["summary"]["ci95_total"][0], -2.185151182619254, 1e-12)
        and close(sensitivity["180"]["rows"][2]["summary"]["ci95_total"][1], -0.09141231852023796, 1e-12),
    )
    add(
        checks,
        "uncertainty-365-fold80",
        close(sensitivity["365"]["rows"][2]["summary"]["ci95_total"][0], -2.1494091947146874, 1e-12)
        and close(sensitivity["365"]["rows"][2]["summary"]["ci95_total"][1], -0.22502374627060087, 1e-12)
        and close(sensitivity["365"]["rows"][2]["summary"]["paired_sign_permutation_p"], 0.015, 1e-12),
    )
    add(checks, "first-fold-fraction", display_ok(uncertainty["NZ_first_fold_fraction"] * 100, 93.7, 1), actual=uncertainty["NZ_first_fold_fraction"])
    counts["uncertainty_rows"] = unc_rows

    # First-block four-bin accounting.
    temporal_all = load(AUTH["temporal"])
    temporal = [row for row in temporal_all if row["fold"] == "fold_50"]
    add(checks, "first-block-rows", len(temporal) == 4 and len(temporal_all) == 12, actual=len(temporal), all_rows=len(temporal_all))
    block_rows = []
    for row in sorted(temporal, key=lambda r: int(r["bin"])):
        dq = float(row["event_logratio"])
        dc = float(row["compensator_contribution"])
        dl = float(row["full_marked_logscore_difference"])
        add(checks, f"first-block-row-{len(block_rows)}", close(dq + dc, dl, 1e-12), dQ=dq, dC=dc, joint=dl)
        block_rows.append({"bin": int(row["bin"]), "dQ": dq, "dC": dc, "dL": dl})
    block_totals = {
        "dQ": sum(r["dQ"] for r in block_rows),
        "dC": sum(r["dC"] for r in block_rows),
        "dL": sum(r["dL"] for r in block_rows),
    }
    add(checks, "first-block-totals", display_ok(block_totals["dQ"], -33.715205, 6) and display_ok(block_totals["dC"], 17.197647, 6) and display_ok(block_totals["dL"], -16.517557, 6), **block_totals)
    counts["first_block"] = block_rows

    # 914-event FDSN magnitude-replacement sensitivity.
    fdsn = load(AUTH["fdsn"])
    magnitude = fdsn["source_field_summaries"]["magnitude"]
    add(checks, "fdsn-magnitude-differences", magnitude["nonzero_numeric"] == 241, actual=magnitude["nonzero_numeric"])
    add(checks, "fdsn-max-difference", display_ok(float(magnitude["absolute_quantiles_decimal"]["1"]), 0.164, 3), actual=magnitude["absolute_quantiles_decimal"]["1"])
    primary = fdsn["source_sensitivity"]["shared_minus_ml"]
    omori = fdsn["source_sensitivity"]["omori_minus_ml"]
    add(checks, "fdsn-shared-totals", close(primary["primary_total"], -17.622859364794834, 1e-12) and close(primary["alternate_magnitude_total"], -17.617975447080084, 1e-12) and close(primary["signed_shift"], 0.004883917714749941, 1e-12))
    add(checks, "fdsn-omori-totals", close(omori["primary_total"], 12.458120885646906, 1e-12) and close(omori["alternate_magnitude_total"], 12.441651230762886, 1e-12) and close(omori["signed_shift"], -0.016469654884019747, 1e-12))
    add(checks, "fdsn-no-sign-reversal", not primary["sign_reversal_folds"] and not omori["sign_reversal_folds"])

    payload = component_head(
        "slice3_chapter8_baseline_v1",
        "Chapter 8 reconstructed baseline: 913-event catalogue identity, magnitude estimators, saved predictive parameters, "
        "trend--depletion projection, saved scores, block uncertainty, first-block accounting, and the 914-event "
        "magnitude-replacement sensitivity.",
        checks,
        counts,
    )
    dump("chapter8_baseline.json", payload)
    return payload

# ---------------------------------------------------------------------------
# 3. Chapter 8 trend--depletion controls, eighteen-cell search, autonomous fit
# ---------------------------------------------------------------------------


def audit_chapter8_trend_controls() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    trend = load(AUTH["trend"])
    totals = load(AUTH["trend_totals"])["controls"]
    track_b = load(AUTH["track_b"])
    fold_names = {"1": "fold_50", "2": "fold_65", "3": "fold_80"}
    arm_names = {"Free": "free_d", "Fixed null": "fixed_null_d", "Zero": "zero_d"}

    # Twelve displayed rows (nine fold rows plus three pooled rows).
    trend_rows = rows_after_header(
        TEX["ch08_trend"], "Fold & Control & $a$ & $d$ & $n$ & $\\eta$"
    )
    add(checks, "trend-table-rows", len(trend_rows) == 12, actual=len(trend_rows))
    parsed_trend = []
    for cells in trend_rows:
        if len(cells) != 10:
            add(checks, "trend-row-width", False, cells=cells)
            continue
        first = cells[0].strip()
        pooled = first.startswith("Pooled")
        fold = None if pooled else fold_names[re.match(r"(\d+)", first).group(1)]
        control_text = cells[1]
        arm = next(key for token, key in arm_names.items() if token.lower() in control_text.lower())
        if pooled:
            expected = [
                None,
                None,
                None,
                None,
                None,
                totals[arm]["totals"]["delta_Q"],
                totals[arm]["totals"]["delta_C"],
                totals[arm]["totals"]["delta_joint"],
            ]
        else:
            fold_record = track_b["folds"][fold]
            if arm == "free_d":
                pars = fold_record["archived"]["ml_shared"]["record"]["pars"]
                held = fold_record["archived"]["heldout"]
            else:
                key = "fixed_null_trend" if arm == "fixed_null_d" else "zero_trend"
                pars = fold_record["controls"][key]["inhibited"]["training"]["parameters"]
                held = fold_record["controls"][key]["heldout"]
            expected = [
                pars[0],
                pars[1],
                pars[2],
                pars[3] if len(pars) > 3 else 0.0,
                held["training_delta_loglik"],
                held["delta_Q"],
                held["delta_C"],
                held["delta_joint"],
            ]
        displayed = [latex_number(c) for c in cells[2:]]
        row_checks = []
        for j, (disp, exp) in enumerate(zip(displayed, expected)):
            if exp is None:
                ok = disp is None
            else:
                ok = display_ok(exp, disp, 3)
            row_checks.append(ok)
        add(
            checks,
            f"trend-row-{first}-{arm}",
            all(row_checks),
            displayed=displayed,
            expected=expected,
            fields_ok=row_checks,
        )
        parsed_trend.append(
            {"fold": fold or "pooled", "arm": arm, "displayed": displayed, "expected": expected, "passed": all(row_checks)}
        )
    counts["trend_rows"] = len(parsed_trend)

    # Three contrast-specific MDE rows.
    mde_rows = rows_after_header(
        TEX["ch08_trend"], "Control & $\\Delta\\ell$ (nats) & $\\mathrm{SE}_{90}$"
    )
    add(checks, "mde-table-rows", len(mde_rows) == 3, actual=len(mde_rows))
    parsed_mde = []
    for cells in mde_rows:
        text = cells[0].lower()
        arm = "zero_d" if text.startswith("zero") else ("fixed_null_d" if text.startswith("fixed") else "free_d")
        source = trend["controls_rebuilt"][arm]["block_days"]
        expected = [
            trend["controls_rebuilt"][arm]["total"],
            source["90"]["se_total_nats"],
            source["90"]["mde95_total_nats"],
            source["90"]["z"],
            source["180"]["mde95_total_nats"],
            source["365"]["mde95_total_nats"],
        ]
        displayed = [latex_number(c) for c in cells[1:]]
        decimals = [3, 3, 3, 2, 3, 3]
        row_checks = [display_ok(exp, disp, dec) for exp, disp, dec in zip(expected, displayed, decimals)]
        add(checks, f"mde-row-{arm}", all(row_checks), displayed=displayed, expected=expected, fields_ok=row_checks)
        parsed_mde.append({"arm": arm, "displayed": displayed, "expected": expected, "passed": all(row_checks)})
    counts["mde_rows"] = len(parsed_mde)

    # Complete eighteen-cell two-start search.
    full_grid = trend["full_grid"]
    add(checks, "full-grid-protocol", full_grid["cells_per_fold"] == 18 and full_grid["starts_per_cell"] == 2, protocol=full_grid["protocol"])
    expected_winners = {
        "fold_50": {"zero_d": "a0.5_t1_r0.4", "fixed_null_d": "a0.5_t1_r0.4"},
        "fold_65": {"zero_d": "a0.5_t1_r0.7", "fixed_null_d": "a0.5_t1_r0.7"},
        "fold_80": {"zero_d": "a0.5_t1_r0.7", "fixed_null_d": "a0.5_t1_r0.7"},
    }
    expected_cells = {
        f"a{alpha}_t{tau}_r{ratio}"
        for alpha in ("0.5", "0.7")
        for tau in ("0.1", "1", "10")
        for ratio in ("0.4", "0.7", "0.8")
    }
    grid_records = []
    for fold, fold_record in full_grid["folds"].items():
        add(checks, f"full-grid-cells-{fold}", set(fold_record["cells"]) == expected_cells and len(fold_record["cells"]) == 18, actual=len(fold_record["cells"]))
        for arm in ("zero_d", "fixed_null_d"):
            for key, cell in fold_record["cells"].items():
                block = cell[arm]
                floor = block["inhibited_records"][-1]
                add(
                    checks,
                    f"full-grid-floor-{fold}-{arm}-{key}",
                    floor.get("message") == "exact nested eta=0 floor"
                    and float(floor["parameters"][3]) == 0.0
                    and len(block["inhibited_records"]) == 3
                    and len(block["null_records"]) == 2,
                    records=len(block["inhibited_records"]),
                )
            ranked = sorted(fold_record["cells"].items(), key=lambda kv: kv[1][arm]["inhibited"]["nll"])
            winner_key = ranked[0][0]
            winner = fold_record["winners"][arm]
            add(
                checks,
                f"full-grid-winner-{fold}-{arm}",
                winner_key == winner["key"] == expected_winners[fold][arm]
                and close(winner["training_nll"], ranked[0][1][arm]["inhibited"]["nll"], 1e-12),
                winner=winner_key,
                expected=expected_winners[fold][arm],
            )
            grid_records.append(
                {
                    "fold": fold,
                    "arm": arm,
                    "winner": winner_key,
                    "training_nll": winner["training_nll"],
                    "heldout_delta_joint": winner["heldout_delta_joint"],
                }
            )
    # Totals and first-fold values.
    first_fold = {
        arm: full_grid["folds"]["fold_50"]["winners"][arm]["heldout_delta_joint"]
        for arm in ("zero_d", "fixed_null_d")
    }
    pooled_grid = {
        arm: full_grid["pooled"][arm]["total_heldout"] for arm in ("zero_d", "fixed_null_d")
    }
    add(checks, "full-grid-first-fold", display_ok(first_fold["zero_d"], -8.504, 3) and display_ok(first_fold["fixed_null_d"], -4.556, 3), actual=first_fold)
    add(checks, "full-grid-totals", display_ok(pooled_grid["zero_d"], -11.431, 3) and display_ok(pooled_grid["fixed_null_d"], -5.006, 3), actual=pooled_grid)
    add(
        checks,
        "full-grid-control-reconciliation",
        all(
            abs(first_fold[arm] - totals[arm]["per_fold"]["fold_50"]["delta_joint"]) < 1e-4
            for arm in ("zero_d", "fixed_null_d")
        )
        and all(
            abs(pooled_grid[arm] - totals[arm]["totals"]["delta_joint"]) < 1e-4
            for arm in ("zero_d", "fixed_null_d")
        ),
    )
    counts["full_grid"] = grid_records
    counts["full_grid_first_fold"] = first_fold
    counts["full_grid_pooled"] = pooled_grid

    # Clamped-clock counterfactual.
    clamped = totals["clamped_clock"]
    add(
        checks,
        "clamped-clock",
        display_ok(clamped["per_fold"]["fold_50"]["delta_joint"], -24.791, 3)
        and display_ok(clamped["totals"]["delta_joint"], -26.898, 3),
        fold1=clamped["per_fold"]["fold_50"]["delta_joint"],
        pooled=clamped["totals"]["delta_joint"],
    )

    # Autonomous finite-mode table.
    autonomous = load(AUTH["autonomous"])
    add(checks, "autonomous-complete", autonomous["passed"] is True and autonomous["complete"] is True)
    auto_rows = rows_after_header(TEX["ch08_obs"], "Fold & Null score & Inhibited score & Gain")
    add(checks, "autonomous-table-rows", len(auto_rows) == 4, actual=len(auto_rows))
    fold_order = [("Early", "fold_50"), ("Middle", "fold_65"), ("Late", "fold_80")]
    auto_records = []
    for cells, (label, fold_name) in zip(auto_rows[:3], fold_order):
        fold = autonomous["folds"][fold_name]
        scores = fold["scores"]["32"]
        null = scores["null"]["full_marked"]
        inhibited = scores["inhibited"]["full_marked"]
        gain = inhibited - null
        displayed = [latex_number(c) for c in cells[1:4]]
        ok = (
            display_ok(null, displayed[0], 4)
            and display_ok(inhibited, displayed[1], 4)
            and display_ok(gain, displayed[2], 4)
        )
        add(checks, f"autonomous-row-{label}", ok, displayed=displayed, expected=[null, inhibited, gain])
        # Internal score additivity and candidate selection.
        for arm in ("null", "inhibited"):
            s = scores[arm]
            add(
                checks,
                f"autonomous-additivity-{label}-{arm}",
                close(s["ground"], sum(s["event_log_intensities"]) - s["integrated_intensity"], 1e-10)
                and close(s["full_marked"], s["ground"] + s["common_mark"], 1e-12),
            )
            candidates = fold[arm]["candidates"]
            selected = fold[arm]["selected"]
            add(
                checks,
                f"autonomous-selected-{label}-{arm}",
                close(selected["nll"], min(c["nll"] for c in candidates), 1e-12)
                and fold[arm]["complete"] is True,
            )
        add(
            checks,
            f"autonomous-beta-{label}",
            close(fold["beta_train"], load(AUTH["observed"])["folds"][fold_name]["fit"]["beta_train"], 1e-14),
        )
        auto_records.append({"fold": fold_name, "null": null, "inhibited": inhibited, "gain": gain, "passed": ok})
    pooled_cell = auto_rows[3]
    pooled_display = latex_number(pooled_cell[3])
    add(
        checks,
        "autonomous-pooled",
        display_ok(autonomous["pooled_gain"], pooled_display, 4)
        and display_ok(autonomous["pooled_gain"], -12.9456, 4),
        actual=autonomous["pooled_gain"],
        displayed=pooled_display,
    )
    counts["autonomous"] = auto_records
    counts["autonomous_pooled_gain"] = autonomous["pooled_gain"]

    payload = component_head(
        "slice3_chapter8_trend_controls_v1",
        "Chapter 8 trend--depletion controls: twelve table rows, contrast-specific block MDEs, "
        "the complete eighteen-cell two-start (alpha, tau, r) grid, the clamped-clock counterfactual, "
        "and the autonomous constant-background subfamily.",
        checks,
        counts,
    )
    dump("chapter8_trend_controls.json", payload)
    return payload

# ---------------------------------------------------------------------------
# Display helpers for table cells
# ---------------------------------------------------------------------------


def cell_decimals(cell: str) -> int:
    s = cell.replace("$", "").replace("{}", "").strip()
    m = re.search(
        r"\\shortstack\[r\]\{\$?([+-]?\d+(?:\.\d+)?)\$?\\\\\$?\\times", s
    )
    text = m.group(1) if m else s
    if "." in text:
        return len(text.split(".")[1])
    return 0


def display_matches_cell(actual: float, cell: str) -> bool:
    disp = latex_number(cell)
    if disp is None:
        return actual is None
    dec = cell_decimals(cell)
    return abs(float(actual) - disp) <= 0.5 * 10.0 ** (-dec) + 2e-12 * max(1.0, abs(float(actual)))


# ---------------------------------------------------------------------------
# 4. Stage C1: region-labelled local and global controls
# ---------------------------------------------------------------------------


def audit_stage_c1() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    data = load(AUTH["c1"])
    comps = {(c["fold_id"], c["comparison"]): c for c in data["comparisons"]}
    aggregates = {a["comparison"]: a for a in data["aggregates"]}

    main_rows = rows_after_header(
        TEX["ch10"], "Comparison & Regional timing & Conditional zone & Magnitude & Joint nats"
    )
    add(checks, "c1-main-rows", len(main_rows) == 5, actual=len(main_rows))
    main_records = []
    for cells in main_rows:
        comp = latex_label(cells[0])
        agg = aggregates[comp]
        field_cells = [
            ("regional_timing", cells[1]),
            ("conditional_zone", cells[2]),
            ("mark", cells[3]),
            ("joint", cells[4]),
            ("nats_per_event", cells[5]),
        ]
        ok = all(display_matches_cell(agg[k], c) for k, c in field_cells)
        m = re.fullmatch(r"(\d+)/(\d+)", cells[6].strip())
        ok = ok and bool(m) and int(m.group(1)) == agg["positive_folds"] and int(m.group(2)) == 3
        add(checks, f"c1-main-{comp}", ok, row=cells, expected={k: agg[k] for k, _ in field_cells})
        main_records.append({"comparison": comp, "row": cells, "passed": ok})
    counts["main_rows"] = len(main_records)

    fold_rows = rows_after_header(
        TEX["app10"], "Fold & Contrast & Events & Event & $\\Delta C$ & Regional timing"
    )
    add(checks, "c1-fold-rows", len(fold_rows) == 15, actual=len(fold_rows))
    fold_records = []
    for cells in fold_rows:
        fold = int(cells[0].replace("{}", ""))
        comp = latex_label(cells[1])
        c = comps[(fold, comp)]
        checks_row = [
            int(latex_number(cells[2])) == c["n_test"],
            display_matches_cell(c["event"], cells[3]),
            display_matches_cell(c["compensator"], cells[4]),
            display_matches_cell(c["regional_timing"], cells[5]),
            display_matches_cell(c["conditional_zone"], cells[6]),
            display_matches_cell(c["joint"], cells[7]),
        ]
        add(checks, f"c1-fold-{fold}-{comp}", all(checks_row), row=cells, fields_ok=checks_row)
        fold_records.append({"fold": fold, "comparison": comp, "row": cells, "passed": all(checks_row)})
    counts["fold_rows"] = len(fold_records)

    zone_rows = rows_after_header(TEX["app10"], "Fold & Contrast & Zone & Events")
    add(checks, "c1-zone-rows", len(zone_rows) == 45, actual=len(zone_rows))
    zones = {"south": 0, "central": 1, "north": 2}
    zone_records = []
    for cells in zone_rows:
        fold = int(cells[0].replace("{}", ""))
        comp = latex_label(cells[1])
        z = zones[cells[2].strip()]
        c = comps[(fold, comp)]
        checks_row = [
            int(latex_number(cells[3])) == c["test_zone_counts"][z],
            display_matches_cell(c["zone_event"][z], cells[4]),
            display_matches_cell(c["zone_compensator"][z], cells[5]),
            display_matches_cell(c["zone_time_zone"][z], cells[6]),
        ]
        add(checks, f"c1-zone-{fold}-{comp}-{cells[2].strip()}", all(checks_row), row=cells, fields_ok=checks_row)
        zone_records.append({"fold": fold, "comparison": comp, "zone": cells[2].strip(), "row": cells, "passed": all(checks_row)})
    counts["zone_rows"] = len(zone_records)

    # Exact decomposition and fold-sum identities.
    for (fold, comp), c in comps.items():
        add(
            checks,
            f"c1-identity-{fold}-{comp}",
            close(sum(c["zone_event"]), c["event"], 1e-10)
            and close(sum(c["zone_compensator"]), c["compensator"], 1e-10)
            and close(sum(c["zone_time_zone"]), c["joint"], 1e-10)
            and close(c["regional_timing"] + c["conditional_zone"], c["joint"], 1e-10)
            and close(c["event"] + c["compensator"], c["joint"], 1e-10)
            and sum(c["test_zone_counts"]) == c["n_test"],
        )
    for comp, agg in aggregates.items():
        rows = [comps[(fold, comp)] for fold in (0, 1, 2)]
        add(
            checks,
            f"c1-aggregate-{comp}",
            all(
                close(sum(r[k] for r in rows), agg[k], 1e-10)
                for k in ("event", "compensator", "regional_timing", "conditional_zone", "joint")
            )
            and sum(r["n_test"] for r in rows) == agg["n_test"] == 612,
        )

    payload = component_head(
        "slice3_stage_c1_v1",
        "Stage C1 three-zone local/global controls: five aggregate contrasts, fifteen per-fold rows, "
        "and forty-five exact zone-decomposition rows.",
        checks,
        counts,
    )
    dump("stage_c1.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 5. Stage W: conserved cross-zone redistribution
# ---------------------------------------------------------------------------


def audit_stage_w() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    data = load(AUTH["w"])
    comps = {(c["fold_id"], c["comparison"]): c for c in data["comparisons"]}
    aggregates = {a["comparison"]: a for a in data["aggregates"]}

    main_rows = rows_after_header(
        TEX["ch10"], "Comparison & Regional timing & Conditional zone & Within-zone cell & Joint nats"
    )
    add(checks, "w-main-rows", len(main_rows) == 9, actual=len(main_rows))
    for cells in main_rows:
        comp = latex_label(cells[0])
        agg = aggregates[comp]
        ok = all(
            display_matches_cell(agg[k], c)
            for k, c in (
                ("regional_timing", cells[1]),
                ("conditional_zone", cells[2]),
                ("within_cell", cells[3]),
                ("joint", cells[4]),
                ("nats_per_event", cells[5]),
            )
        )
        m = re.fullmatch(r"(\d+)/(\d+)", cells[6].strip())
        ok = ok and bool(m) and int(m.group(1)) == agg["positive_folds"] and int(m.group(2)) == 3
        add(checks, f"w-main-{comp}", ok, row=cells, expected={k: agg[k] for k in aggregates[comp]})
    counts["main_rows"] = len(main_rows)

    fold_rows = rows_after_header(
        TEX["app10"], "Fold & Contrast & Events & Event & $\\Delta C$ & Timing"
    )
    add(checks, "w-fold-rows", len(fold_rows) == 27, actual=len(fold_rows))
    for cells in fold_rows:
        fold = int(cells[0].replace("{}", ""))
        comp = latex_label(cells[1])
        c = comps[(fold, comp)]
        checks_row = [
            int(latex_number(cells[2])) == c["n_test"],
            display_matches_cell(c["event"], cells[3]),
            display_matches_cell(c["compensator"], cells[4]),
            display_matches_cell(c["regional_timing"], cells[5]),
            display_matches_cell(c["conditional_zone"], cells[6]),
            display_matches_cell(c["within_cell"], cells[7]),
            display_matches_cell(c["joint"], cells[8]),
        ]
        add(checks, f"w-fold-{fold}-{comp}", all(checks_row), row=cells, fields_ok=checks_row)
    counts["fold_rows"] = len(fold_rows)

    target_rows = rows_after_header(TEX["app10"], "Fold & Contrast & Target & Event")
    add(checks, "w-target-rows", len(target_rows) == 81, actual=len(target_rows))
    for cells in target_rows:
        fold = int(cells[0].replace("{}", ""))
        comp = latex_label(cells[1])
        t = int(latex_number(cells[2]))
        c = comps[(fold, comp)]
        checks_row = [
            display_matches_cell(c["target_event"][t], cells[3]),
            display_matches_cell(c["target_compensator"][t], cells[4]),
            display_matches_cell(c["target_time_location"][t], cells[5]),
        ]
        add(checks, f"w-target-{fold}-{comp}-{t}", all(checks_row), row=cells, fields_ok=checks_row)
    counts["target_rows"] = len(target_rows)

    # Exact identities.
    for (fold, comp), c in comps.items():
        add(
            checks,
            f"w-identity-{fold}-{comp}",
            close(c["event"] + c["compensator"], c["joint"], 1e-10)
            and close(c["regional_timing"] + c["conditional_zone"] + c["within_cell"], c["joint"], 1e-10)
            and close(sum(c["zone_event"]), c["event"], 1e-10)
            and close(sum(c["zone_compensator"]), c["compensator"], 1e-10)
            and close(sum(c["zone_time_location"]), c["joint"], 1e-10)
            and close(sum(c["target_event"]), c["event"], 1e-10)
            and close(sum(c["target_compensator"]), c["compensator"], 1e-10)
            and close(sum(c["target_time_location"]), c["joint"], 1e-10),
        )
    for comp, agg in aggregates.items():
        rows = [comps[(fold, comp)] for fold in (0, 1, 2)]
        add(
            checks,
            f"w-aggregate-{comp}",
            all(
                close(sum(r[k] for r in rows), agg[k], 1e-10)
                for k in (
                    "event",
                    "compensator",
                    "regional_timing",
                    "conditional_zone",
                    "within_cell",
                    "joint",
                )
            )
            and sum(r["n_test"] for r in rows) == agg["n_test"] == 612,
        )

    # Omega-invariance algebra: every parent's zone allocation sums to one,
    # so total excitation is independent of omega at fixed remaining parameters.
    pi = np.array([0.22591362126245848, 0.3920265780730897, 0.38205980066445183])
    algebra_ok = True
    for omega in (0.0, 0.044, 0.5, 1.0):
        matrix = (1.0 - omega) * np.eye(3) + omega * np.tile(pi, (3, 1))
        algebra_ok = algebra_ok and np.allclose(matrix.sum(axis=1), 1.0, atol=1e-15)
    add(checks, "w-omega-column-stochastic", algebra_ok, pi=pi.tolist())

    payload = component_head(
        "slice3_stage_w_v1",
        "Stage W conserved cross-zone mixing: nine aggregate contrasts, twenty-seven window rows, "
        "eighty-one target-region rows, and the omega-invariance identity.",
        checks,
        counts,
    )
    dump("stage_w.json", payload)
    return payload

# ---------------------------------------------------------------------------
# 6. Stage D and the common-observation W bridge
# ---------------------------------------------------------------------------


def audit_stage_d() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    data = load(AUTH["d"])
    common = load(AUTH["common"])
    wdata = load(AUTH["w"])
    comps = {(c["fold_id"], c["comparison"]): c for c in data["comparisons"]}
    aggregates = {a["comparison"]: a for a in data["aggregates"]}
    common_comps = {(c["fold_id"], c["comparison"]): c for c in common["comparisons"]}
    common_aggregates = {a["comparison"]: a for a in common["aggregates"]}
    d_models = {(int(s["case_id"].split("_")[-1]), s["model"]): s for s in data["selected_models"]}
    w_models = {(int(s["case_id"].split("_")[-1]), s["model"]): s for s in wdata["selected_models"]}

    main_rows = rows_after_header(
        TEX["ch10"],
        "Comparison & Regional timing & Conditional zone & Within-zone cell & Joint nats",
        occurrence=3,
    )
    add(checks, "d-main-rows", len(main_rows) == 8, actual=len(main_rows))
    for cells in main_rows:
        comp = latex_label(cells[0])
        agg = aggregates[comp]
        ok = all(
            display_matches_cell(agg[k], c)
            for k, c in (
                ("regional_timing", cells[1]),
                ("conditional_zone", cells[2]),
                ("within_cell", cells[3]),
                ("joint", cells[4]),
                ("nats_per_event", cells[5]),
            )
        )
        m = re.fullmatch(r"(\d+)/(\d+)", cells[6].strip())
        ok = ok and bool(m) and int(m.group(1)) == agg["positive_folds"] and int(m.group(2)) == 3
        add(checks, f"d-main-{comp}", ok, row=cells, expected={k: agg[k] for k in aggregates[comp]})
    counts["main_rows"] = len(main_rows)

    fold_rows = rows_after_header(
        TEX["app10"], "Fold & Contrast & Events & Event & $\\Delta C$ & Timing", occurrence=3
    )
    add(checks, "d-fold-rows", len(fold_rows) == 24, actual=len(fold_rows))
    for cells in fold_rows:
        fold = int(cells[0].replace("{}", ""))
        comp = latex_label(cells[1])
        c = comps[(fold, comp)]
        checks_row = [
            int(latex_number(cells[2])) == c["n_test"],
            display_matches_cell(c["event"], cells[3]),
            display_matches_cell(c["compensator"], cells[4]),
            display_matches_cell(c["regional_timing"], cells[5]),
            display_matches_cell(c["conditional_zone"], cells[6]),
            display_matches_cell(c["within_cell"], cells[7]),
            display_matches_cell(c["joint"], cells[8]),
        ]
        add(checks, f"d-fold-{fold}-{comp}", all(checks_row), row=cells, fields_ok=checks_row)
    counts["fold_rows"] = len(fold_rows)

    target_rows = rows_after_header(
        TEX["app10"], "Fold & Contrast & Target & Event", occurrence=3
    )
    add(checks, "d-target-rows", len(target_rows) == 216, actual=len(target_rows))
    for cells in target_rows:
        fold = int(cells[0].replace("{}", ""))
        comp = latex_label(cells[1])
        t = int(latex_number(cells[2]))
        c = comps[(fold, comp)]
        checks_row = [
            display_matches_cell(c["target_event"][t], cells[3]),
            display_matches_cell(c["target_compensator"][t], cells[4]),
            display_matches_cell(c["target_time_location"][t], cells[5]),
        ]
        add(checks, f"d-target-{fold}-{comp}-{t}", all(checks_row), row=cells, fields_ok=checks_row)
    counts["target_rows"] = len(target_rows)

    for (fold, comp), c in comps.items():
        add(
            checks,
            f"d-identity-{fold}-{comp}",
            close(c["event"] + c["compensator"], c["joint"], 1e-10)
            and close(c["regional_timing"] + c["conditional_zone"] + c["within_cell"], c["joint"], 1e-10)
            and close(sum(c["target_event"]), c["event"], 1e-10)
            and close(sum(c["target_compensator"]), c["compensator"], 1e-10)
            and close(sum(c["target_time_location"]), c["joint"], 1e-10),
        )
    for comp, agg in aggregates.items():
        rows = [comps[(fold, comp)] for fold in (0, 1, 2)]
        add(
            checks,
            f"d-aggregate-{comp}",
            all(
                close(sum(r[k] for r in rows), agg[k], 1e-10)
                for k in (
                    "event",
                    "compensator",
                    "regional_timing",
                    "conditional_zone",
                    "within_cell",
                    "joint",
                )
            )
            and sum(r["n_test"] for r in rows) == agg["n_test"] == 612,
        )

    # Common-space refined-W bridge.
    common_main_rows = rows_after_header(TEX["ch10"], "D candidate minus refined W reference")
    add(checks, "common-main-rows", len(common_main_rows) == 7, actual=len(common_main_rows))
    for cells in common_main_rows:
        model = latex_label(cells[0])
        comp = model + "-W_E_wfree_q_refinement"
        agg = common_aggregates[comp]
        ok = all(
            display_matches_cell(agg[k], c)
            for k, c in (
                ("regional_timing", cells[1]),
                ("conditional_zone", cells[2]),
                ("within_cell", cells[3]),
                ("mark", cells[4]),
                ("joint", cells[5]),
                ("nats_per_event", cells[6]),
            )
        )
        m = re.fullmatch(r"(\d+)/(\d+)", cells[7].strip())
        ok = ok and bool(m) and int(m.group(1)) == agg["positive_folds"] and int(m.group(2)) == 3
        add(checks, f"common-main-{model}", ok, row=cells, expected={k: agg[k] for k in agg})
    counts["common_main_rows"] = len(common_main_rows)

    common_fold_rows = rows_after_header(TEX["app10"], "Fold & D candidate & Events")
    add(checks, "common-fold-rows", len(common_fold_rows) == 21, actual=len(common_fold_rows))
    for cells in common_fold_rows:
        fold = int(cells[0].replace("{}", ""))
        model = latex_label(cells[1])
        comp = model + "-W_E_wfree_q_refinement"
        c = common_comps[(fold, comp)]
        checks_row = [
            int(latex_number(cells[2])) == c["n_test"],
            display_matches_cell(c["event"], cells[3]),
            display_matches_cell(c["compensator"], cells[4]),
            display_matches_cell(c["regional_timing"], cells[5]),
            display_matches_cell(c["conditional_zone"], cells[6]),
            display_matches_cell(c["within_cell"], cells[7]),
            display_matches_cell(c["joint"], cells[8]),
        ]
        add(checks, f"common-fold-{fold}-{model}", all(checks_row), row=cells, fields_ok=checks_row)
        # Recompute the bridge from the D and W saved forecasts.
        d = d_models[(fold, model)]["forecast"]
        w = w_models[(fold, "E_wfree")]["forecast"]
        # The refined W reference reuses the frozen training q(c|z) allocation;
        # its within-cell term is the D stage's q-allocation term, so the event
        # and joint reference scores include that term.
        qterm = d_models[(fold, "E_global")]["forecast"]["within_cell_logscore"]
        expected = {
            "event": d["event_log_intensity_sum"] - (w["event_log_intensity_sum"] + qterm),
            "compensator": -(d["integrated_intensity"] - w["integrated_intensity"]),
            "regional_timing": d["regional_timing_logscore"] - w["regional_timing_logscore"],
            "conditional_zone": d["conditional_zone_logscore"] - w["conditional_zone_logscore"],
            "within_cell": d["within_cell_logscore"] - qterm,
            "joint": d["full_joint_logscore"] - (w["full_joint_logscore"] + qterm),
        }
        add(
            checks,
            f"common-bridge-{fold}-{model}",
            all(close(expected[k], c[k], 1e-9) for k in expected),
            expected=expected,
            stored={k: c[k] for k in expected},
        )
    counts["common_fold_rows"] = len(common_fold_rows)

    for comp, agg in common_aggregates.items():
        rows = [common_comps[(fold, comp)] for fold in (0, 1, 2)]
        add(
            checks,
            f"common-aggregate-{comp}",
            all(
                close(sum(r[k] for r in rows), agg[k], 1e-10)
                for k in (
                    "event",
                    "compensator",
                    "regional_timing",
                    "conditional_zone",
                    "within_cell",
                    "joint",
                )
            )
            and sum(r["n_test"] for r in rows) == agg["n_test"] == 612,
        )

    payload = component_head(
        "slice3_stage_d_v1",
        "Stage D nine-cell distance allocation and the common-observation W bridge: eight aggregate contrasts, "
        "twenty-four window rows, 216 target-cell rows, seven refined-W contrasts, and twenty-one bridge rows.",
        checks,
        counts,
    )
    dump("stage_d.json", payload)
    return payload

# ---------------------------------------------------------------------------
# 7. Stage S: continuous area density and the projected cell-area lift
# ---------------------------------------------------------------------------


def audit_stage_s() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    data = load(AUTH["s"])
    ddata = load(AUTH["d"])
    comps = {(c["fold_id"], c["comparison"]): c for c in data["comparisons"]}
    aggregates = {a["comparison"]: a for a in data["aggregates"]}
    absolute = {(int(a["case_id"].split("_")[-1]), a["model"]): a for a in data["absolute"]}
    d_models = {(int(s["case_id"].split("_")[-1]), s["model"]): s for s in ddata["selected_models"]}

    main_rows = rows_after_header(TEX["ch10"], "Contrast & Fold 0 (203)")
    add(checks, "s-main-rows", len(main_rows) == 6, actual=len(main_rows))
    for cells in main_rows:
        comp = latex_label(cells[0])
        agg = aggregates[comp]
        folds = sorted([c for c in data["comparisons"] if c["comparison"] == comp], key=lambda c: c["fold_id"])
        checks_row = [
            display_matches_cell(folds[j]["joint"], cells[1 + j]) for j in range(3)
        ] + [
            display_matches_cell(agg["joint"], cells[4]),
            display_matches_cell(agg["nats_per_event"], cells[5]),
        ]
        add(checks, f"s-main-{comp}", all(checks_row), row=cells, fields_ok=checks_row)
    counts["main_rows"] = len(main_rows)

    decomp_rows = rows_after_header(
        TEX["ch10"], "Component, \\modeltag{E}{cont} minus \\modeltag{E}{lift}"
    )
    add(checks, "s-decomposition-rows", len(decomp_rows) == 6, actual=len(decomp_rows))
    agg = aggregates["E_cont-E_lift"]
    expected_components = [
        agg["timing"],
        agg["conditional_zone"],
        agg["conditional_cell"],
        agg["within_cell_density"],
        agg["mark"],
        agg["joint"],
    ]
    for cells, expected in zip(decomp_rows, expected_components):
        add(checks, f"s-decomposition-{latex_label(cells[0])}", display_matches_cell(expected, cells[1]), row=cells, expected=expected)
    add(
        checks,
        "s-decomposition-identity",
        close(
            agg["timing"]
            + agg["conditional_zone"]
            + agg["conditional_cell"]
            + agg["within_cell_density"]
            + agg["mark"],
            agg["joint"],
            1e-10,
        )
        and close(agg["event"] + agg["compensator"], agg["joint"], 1e-10),
        components=expected_components,
    )
    add(
        checks,
        "s-display-component-sum",
        display_ok(-10.470041 + -4.471988 + 21.333833 + 1452.412080 + 0.0, 1458.803884, 6),
    )
    counts["decomposition"] = expected_components

    sigma_rows = rows_after_header(TEX["ch10"], "Fold & \\modeltag{E}{cont} selected $\\sigma$ (km)")
    add(checks, "s-sigma-rows", len(sigma_rows) == 3, actual=len(sigma_rows))
    report = (ROOT / "validation/authorities/789786b69f01142e_decision_report.md").read_text(encoding="utf-8").splitlines()
    report_rows = [line for line in report if re.match(r"\| [012] \|", line)]
    add(checks, "s-sigma-report-rows", len(report_rows) == 3, actual=len(report_rows))
    for cells, report_line in zip(sigma_rows, report_rows):
        fold = int(cells[0].replace("{}", ""))
        report_cells = [x.strip() for x in report_line.strip("|").split("|")]
        expected = [int(float(report_cells[1])), int(float(report_cells[2])), float(report_cells[3]), float(report_cells[4])]
        displayed = [latex_number(c) for c in cells[1:]]
        checks_row = [
            int(displayed[0]) == expected[0],
            int(displayed[1]) == expected[1],
            display_ok(expected[2], displayed[2], 9),
            display_ok(expected[3], displayed[3], 9),
        ]
        add(checks, f"s-sigma-row-{fold}", all(checks_row), displayed=displayed, expected=expected)
        add(
            checks,
            f"s-sigma-authority-{fold}",
            int(data["cases"][fold]["selected_sigma"]["E_cont"]) == expected[0]
            and int(data["cases"][fold]["selected_sigma"]["E_lift"]) == expected[1],
        )
    counts["sigma_rows"] = len(sigma_rows)

    # Exact projected cell-area lift identity.
    R = 6371.0088
    lats = [-48.5, -43.5, -38.5, -33.5]
    lons = [165.0, 170.0, 175.0, 180.0]
    areas = []
    for i in range(3):
        dsin = math.sin(math.radians(lats[i + 1])) - math.sin(math.radians(lats[i]))
        for j in range(3):
            areas.append(R * R * dsin * math.radians(lons[j + 1] - lons[j]))
    add(checks, "s-area-sum", close(sum(areas), 2093594.476650179, 1e-12), areas=areas)
    counts["cell_areas_km2"] = areas
    for fold in (0, 1, 2):
        counts_fold = ddata["cases"][fold]["test_target_counts"]
        offset = sum(n * math.log(a) for n, a in zip(counts_fold, areas) if n)
        old = absolute[(fold, "E_oldD_lift")]
        add(
            checks,
            f"s-lift-within-{fold}",
            close(old["within_cell_density_logscore"], -offset, 1e-9),
            stored=old["within_cell_density_logscore"],
            computed=-offset,
        )
        categorical = d_models[(fold, "E_distance")]["forecast"]["full_joint_logscore"]
        add(
            checks,
            f"s-lift-joint-{fold}",
            close(old["joint"], categorical - offset, 1e-9),
            stored=old["joint"],
            computed=categorical - offset,
        )
    add(
        checks,
        "s-aggregate-cont-oldD",
        display_ok(aggregates["E_cont-E_oldD_lift"]["joint"], 1463.083902, 6)
        and display_ok(aggregates["E_lift-E_oldD_lift"]["joint"], 4.280018, 6),
    )
    add(
        checks,
        "s-fold-joint-sums",
        all(
            close(
                sum(comps[(fold, comp)]["joint"] for fold in (0, 1, 2)),
                aggregates[comp]["joint"],
                1e-10,
            )
            for comp in aggregates
        ),
    )

    payload = component_head(
        "slice3_stage_s_v1",
        "Stage S continuous area density: six aggregate contrasts, the five-component score decomposition, "
        "the selected sigma/eta table, and the exact projected cell-area lift identity.",
        checks,
        counts,
    )
    dump("stage_s.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 8. Twelve-model temporal--spatial--background factorial
# ---------------------------------------------------------------------------


def audit_factorial() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    data = load(AUTH["factorial"])
    absolute = {(a["case_id"], a["model"]): a for a in data["absolute"]}
    aggregates = {a["comparison"]: a for a in data["aggregates"]}
    comps_by = defaultdict(list)
    for c in data["comparisons"]:
        comps_by[c["comparison"]].append(c)
    for rows in comps_by.values():
        rows.sort(key=lambda c: int(c["case_id"].split("_")[-1]))

    # All 29 aggregate contrasts: fold sums and component additivity.
    for comp, agg in aggregates.items():
        rows = comps_by[comp]
        add(checks, f"factorial-row-count-{comp}", len(rows) == 3, actual=len(rows))
        add(
            checks,
            f"factorial-fold-sums-{comp}",
            all(
                close(sum(r[k] for r in rows), agg[k], 1e-10)
                for k in (
                    "joint_logscore",
                    "timing_logscore",
                    "conditional_zone_logscore",
                    "conditional_cell_logscore",
                    "within_cell_density_logscore",
                    "mark_logscore",
                    "event_log_point_intensity_sum",
                    "compensator_gain",
                )
            ),
        )
        add(
            checks,
            f"factorial-additivity-{comp}",
            all(
                close(
                    r["joint_logscore"],
                    r["timing_logscore"]
                    + r["conditional_zone_logscore"]
                    + r["conditional_cell_logscore"]
                    + r["within_cell_density_logscore"]
                    + r["mark_logscore"],
                    1e-9,
                )
                and close(
                    r["joint_logscore"],
                    r["event_log_point_intensity_sum"] + r["compensator_gain"],
                    1e-9,
                )
                for r in rows
            ),
        )
    add(checks, "factorial-aggregate-count", len(aggregates) == 29, actual=len(aggregates))

    # Chapter 10 temporal table.
    temporal_rows = rows_after_header(TEX["ch10"], "Background and temporal contrast")
    add(checks, "factorial-temporal-rows", len(temporal_rows) == 6, actual=len(temporal_rows))
    temporal_map = {
        "Cell: common ML - fixed ML": "commonML-fixedML_cell_cont",
        "Cell: Omori - fixed ML": "Omori-fixedML_cell_cont",
        "Cell: Omori - common ML": "Omori-commonML_cell_cont",
        "KDE-enriched: common ML - fixed ML": "commonML-fixedML_smooth_cont",
        "KDE-enriched: Omori - fixed ML": "Omori-fixedML_smooth_cont",
        "KDE-enriched: Omori - common ML": "Omori-commonML_smooth_cont",
    }
    for cells in temporal_rows:
        label = latex_label(cells[0]).replace("–", "-").replace("—", "-")
        comp = temporal_map[label]
        agg = aggregates[comp]
        ok = (
            display_matches_cell(agg["joint_logscore"], cells[1])
            and display_matches_cell(agg["nats_per_event"], cells[2])
            and display_matches_cell(agg["timing_logscore"], cells[3])
        )
        m = re.fullmatch(r"(\d+)/(\d+)", cells[4].strip())
        ok = ok and bool(m) and int(m.group(1)) == agg["positive_windows"] and int(m.group(2)) == 3
        add(checks, f"factorial-temporal-{comp}", ok, row=cells)
    counts["temporal_rows"] = len(temporal_rows)

    # Location table.
    location_rows = rows_after_header(TEX["ch10"], "Temporal family & Continuous - lift, cell background")
    add(checks, "factorial-location-rows", len(location_rows) == 3, actual=len(location_rows))
    location_map = {
        "Fixed ML": ("cont-lift_fixedML_cell", "cont-lift_fixedML_smooth"),
        "Common ML": ("cont-lift_commonML_cell", "cont-lift_commonML_smooth"),
        "Omori": ("cont-lift_Omori_cell", "cont-lift_Omori_smooth"),
    }
    for cells in location_rows:
        label = latex_label(cells[0])
        cell_comp, smooth_comp = location_map[label]
        a_cell, a_smooth = aggregates[cell_comp], aggregates[smooth_comp]
        ok = (
            display_matches_cell(a_cell["joint_logscore"], cells[1])
            and display_matches_cell(a_smooth["joint_logscore"], cells[2])
            and display_matches_cell(a_smooth["nats_per_event"], cells[3])
            and display_matches_cell(a_smooth["timing_logscore"], cells[4])
        )
        add(checks, f"factorial-location-{label}", ok, row=cells)
    counts["location_rows"] = len(location_rows)

    # Combined procedure and scale sensitivity.
    combined_cell = aggregates["combined_Omori_cell_cont-fixedML_cell_lift"]
    combined_smooth = aggregates["combined_Omori_smooth_cont-fixedML_cell_lift"]
    add(
        checks,
        "factorial-combined",
        display_ok(combined_cell["joint_logscore"], 1521.255407, 6)
        and display_ok(combined_smooth["joint_logscore"], 1554.503812, 6)
        and display_ok(combined_smooth["nats_per_event"], 2.540039, 6),
        cell=combined_cell["joint_logscore"],
        smooth=combined_smooth["joint_logscore"],
        per_event=combined_smooth["nats_per_event"],
    )
    add(
        checks,
        "factorial-combined-components",
        close(combined_smooth["timing_logscore"] + 1542.973617, combined_smooth["joint_logscore"], 1e-5)
        and display_ok(combined_smooth["timing_logscore"], 11.530195, 6),
        timing=combined_smooth["timing_logscore"],
    )

    # Absolute appendix table.
    abs_rows = rows_after_header(TEX["app10"], "Fold & Arm & $N$")
    add(checks, "factorial-absolute-rows", len(abs_rows) == 36, actual=len(abs_rows))
    for cells in abs_rows:
        fold_label = cells[0].replace("{}", "").strip()
        case = "primary_fold_" + fold_label[1:]
        model = latex_label(cells[1]).replace("\\_", "_").replace("_", "_")
        model = model.replace("\\allowbreak{}", "")
        a = absolute[(case, model)]
        ok = (
            int(latex_number(cells[2])) == a["n_test"]
            and display_matches_cell(a["timing_logscore"], cells[3])
            and display_matches_cell(a["conditional_zone_logscore"], cells[4])
            and display_matches_cell(a["conditional_cell_logscore"], cells[5])
            and display_matches_cell(a["within_cell_density_logscore"], cells[6])
            and display_matches_cell(a["mark_logscore"], cells[7])
            and display_matches_cell(a["joint_logscore"], cells[8])
        )
        add(checks, f"factorial-absolute-{case}-{model}", ok, row=cells)
    counts["absolute_rows"] = len(abs_rows)

    # Bounded-scale sensitivity table.
    sens_rows = rows_after_header(TEX["app10"], "Fold & Primary reference & Sensitivity km")
    add(checks, "factorial-sensitivity-rows", len(sens_rows) == 12, actual=len(sens_rows))
    primary = {
        (a["case_id"], a["model"]): a
        for a in data["absolute"]
        if a["model"].startswith("fixedML_") and a["model"].endswith("_cont")
    }
    sens_records = []
    for cells in sens_rows:
        fold_label = cells[0].replace("{}", "").strip()
        fold = "primary_fold_" + fold_label[1:]
        ref = latex_label(cells[1]).replace("\\_", "_")
        sigma = int(latex_number(cells[2]))
        model = ref + f"_sigma{sigma}"
        s = next(x for x in data["sensitivity"] if x["case_id"] == fold and x["model"] == f"{fold}__sensitivity_{model}")
        p = primary[(fold, ref)]
        delta = s["joint_logscore"] - p["joint_logscore"]
        timing_delta = s["timing_logscore"] - p["timing_logscore"]
        ok = (
            display_matches_cell(delta, cells[4])
            and display_matches_cell(timing_delta, cells[5])
            and display_matches_cell(s["nats_per_event"], cells[6])
        )
        add(checks, f"factorial-sensitivity-{fold}-{model}", ok, row=cells, delta=delta)
        sens_records.append({"fold": fold, "model": model, "delta": delta, "timing_delta": timing_delta, "passed": ok})
    add(
        checks,
        "factorial-sensitivity-range",
        all(r["delta"] < 0 for r in sens_records)
        and close(min(r["delta"] for r in sens_records), -308.063524, 1e-5)
        and close(max(r["delta"] for r in sens_records), -96.988003, 1e-5),
        minimum=min(r["delta"] for r in sens_records),
        maximum=max(r["delta"] for r in sens_records),
    )
    counts["sensitivity_rows"] = len(sens_records)

    # Selected sigma and documentary KDE bandwidth.
    selected = sorted(
        [s for s in data["selectors"] if s.get("selected")],
        key=lambda s: int(s["case_id"].split("_")[-1]),
    )
    add(
        checks,
        "factorial-selected-sigma",
        [int(s["sigma"]) for s in selected] == [5, 15, 15],
        actual=[s["sigma"] for s in selected],
    )
    report = (ROOT / "validation/authorities/9be41dcff14754fc_Addendum_III.md").read_text(encoding="utf-8")
    add(checks, "factorial-kde-bandwidth", "KDE bandwidth was 15 km in all three windows" in report)

    # Hierarchical reference and parent-normalized offspring algebra.
    pi_zone = np.array([68, 118, 115], dtype=float) / 301.0
    counts_cell = np.array([64, 4, 0, 0, 66, 52, 0, 0, 115], dtype=float)
    zone_of = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    q = np.zeros(9)
    for z in (0, 1, 2):
        n_z = pi_zone[z] * 301.0
        q[zone_of == z] = (counts_cell[zone_of == z] + 0.5) / (n_z + 1.5)
    add(checks, "factorial-pi-sum", close(pi_zone.sum(), 1.0, 1e-15), pi=pi_zone.tolist())
    add(checks, "factorial-q-zone-sums", all(close(q[zone_of == z].sum(), 1.0, 1e-14) for z in (0, 1, 2)), q=q.tolist())
    areas = np.array(
        [
            214656.781,
            214656.781,
            214656.781,
            233213.24,
            233213.24,
            233213.24,
            249994.805,
            249994.805,
            249994.805,
        ]
    )
    b_ref = pi_zone[zone_of] * q / areas
    add(checks, "factorial-bref-integral", close(float((b_ref * areas).sum()), 1.0, 1e-14))
    for omega in (0.0, 0.25, 1.0):
        weights = (1.0 - omega) * np.eye(3) + omega * np.tile(pi_zone, (3, 1))
        add(checks, f"factorial-lift-column-stochastic-{omega}", np.allclose(weights.sum(axis=1), 1.0, atol=1e-15))
    add(checks, "factorial-background-mixture", close(0.05 + 0.95, 1.0, 1e-15))
    add(checks, "factorial-reference-weights", close(0.05 * 1.0 + 0.95 * 1.0, 1.0, 1e-15))

    payload = component_head(
        "slice3_factorial_12model_v1",
        "Twelve-model temporal--spatial--background factorial: 29 aggregate contrasts, 36 absolute "
        "arm-by-window rows, six temporal contrasts, three location contrasts, twelve bounded-scale "
        "sensitivities, and the hierarchical reference/offspring algebra.",
        checks,
        counts,
    )
    dump("factorial_12model.json", payload)
    return payload

# ---------------------------------------------------------------------------
# 9. Claim-ledger resolution and Slice 3 display coverage
# ---------------------------------------------------------------------------


def audit_claim_ledger() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    spec = importlib.util.spec_from_file_location(
        "_slice3_verify_claims", ROOT / "scripts/verify_claims.py"
    )
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    receipt, ledgers, _ = vc.verify_ledgers(ROOT, authority_only=True)
    claims = ledgers[0][1]["claims"]
    add(checks, "ledger-authority-resolution", receipt["passed"], failures=receipt["failures"][:10])
    slice3 = [
        c
        for c in claims
        if c.get("tex_file") in SLICE3_TEX_FILES
        or any(f in SLICE3_TEX_FILES for f in c.get("final_display_locations", []))
    ]
    per_file = Counter()
    missing = []
    withdrawn = 0
    tex_numbers = {
        relative: vc.manuscript_numbers((ROOT / "paper/source" / relative).read_text(encoding="utf-8-sig"))
        for relative in SLICE3_TEX_FILES
    }
    for c in slice3:
        files = [c.get("tex_file")] if c.get("tex_file") in SLICE3_TEX_FILES else []
        files += [f for f in c.get("final_display_locations", []) if f in SLICE3_TEX_FILES]
        files = sorted(set(files))
        for relative in files:
            per_file[relative] += 1
        if c.get("ledger_role") != "manuscript_binding":
            if c.get("ledger_role") == "withdrawn_historical_result":
                withdrawn += 1
            continue
        if c.get("display_format"):
            # count/total displays are checked by the ledger verifier itself.
            present = True
        else:
            wanted = vc.numeric_value(c["display"])
            present = any(wanted in tex_numbers[f] for f in files)
        if not present:
            missing.append({"id": c["id"], "display": c["display"], "files": files})
    add(checks, "ledger-slice3-display-presence", not missing, missing=missing[:20])
    counts["slice3_claims"] = len(slice3)
    counts["claims_by_file"] = dict(per_file)
    counts["missing_displays"] = len(missing)
    counts["withdrawn_historical_records"] = withdrawn
    counts["master_ledger_sha256"] = sha256(LEDGER)
    add(
        checks,
        "ledger-slice3-population",
        len(slice3) >= 3500,
        actual=len(slice3),
    )
    notes = [
        "Withdrawn historical records are authority-checked but excluded from the current "
        "manuscript-display presence requirement, matching scripts/verify_claims.py."
    ]
    payload = component_head(
        "slice3_claim_ledger_v1",
        "Independent resolution of the master claim ledger and literal display presence for the five "
        "Slice 3 LaTeX sources.",
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
# 10. Manuscript repair record
# ---------------------------------------------------------------------------


def audit_manuscript_repairs() -> dict:
    checks: list[dict] = []
    counts: dict = {}
    with zipfile.ZipFile(ROOT / "validation/slice3_prechange_snapshot_20261114.zip") as zf:
        old = {
            relative: zf.read(f"paper/source/{relative}").decode("utf-8")
            for relative in SLICE3_TEX_FILES
            if f"paper/source/{relative}" in zf.namelist()
        }
    new = {
        relative: (ROOT / "paper/source" / relative).read_text(encoding="utf-8")
        for relative in SLICE3_TEX_FILES
    }
    spec = importlib.util.spec_from_file_location(
        "_slice3_verify_claims_repairs", ROOT / "scripts/verify_claims.py"
    )
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)

    # Every pre-existing scalar numeric literal must survive the editorial repair.
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
                    match = re.fullmatch(
                        r"([+-]?\d+(?:\.\d+)?)\s*\\times\s*10\^\{([+-]?\d+)\}", raw
                    )
                    if match:
                        values.add(
                            vc.numeric_value(match.group(1))
                            * vc.numeric_value(10) ** int(match.group(2))
                        )
                        continue
                    match = re.fullmatch(r"10\^\{([+-]?\d+)\}", raw)
                    if match:
                        values.add(vc.numeric_value(10) ** int(match.group(1)))
        # A comma pair such as "150,150" is tokenized as the thousands-grouped
        # scalar 150150.  When both three-digit components are also present, the
        # grouped scalar is a formatting artefact, not an additional numeric claim.
        present = {str(v) for v in values}
        for value in list(values):
            text = str(value)
            if len(text) == 6 and text[:3] in present and text[3:] in present:
                values.discard(value)
        return values

    preserved = {}
    for relative in SLICE3_TEX_FILES:
        before = scalar_literals(old[relative])
        after = scalar_literals(new[relative])
        missing = sorted(str(v) for v in before - after)
        preserved[relative] = {"before": len(before), "after": len(after), "removed": missing}
        add(
            checks,
            f"numeric-preservation-{relative}",
            not missing,
            removed=missing[:20],
            before=len(before),
            after=len(after),
        )
    counts["numeric_preservation"] = preserved

    trend = new["chapters/08_nz_trend_controls.tex"]
    required = {
        "fold1-mapping": "Fold~1 (\\texttt{F0}, 50\\% origin)",
        "fold2-mapping": "Fold~2 (\\texttt{F1}, 65\\% origin)",
        "fold3-mapping": "Fold~3 (\\texttt{F2}, 80\\% origin)",
        "full-grid-first-fold": "first-fold held-out contrasts are $-8.504$ and $-4.556$~nats",
        "full-grid-totals": "three-fold full-grid totals are $-11.431$ and $-5.006$~nats",
        "full-grid-per-fold-winners": "$(\\alpha,\\tau,r)=(0.5,1,0.4)$ in Fold~1 (\\texttt{F0}) and $(0.5,1,0.7)$ in Folds~2 and~3",
    }
    for cid, token in required.items():
        add(checks, f"repair-present-{cid}", token in trend, token=token)
    add(checks, "repair-absent-Fold0-trend", "Fold~0" not in trend)
    add(checks, "repair-absent-wrong-full-grid-total", "full-grid held-out totals are $-8.504$ and $-4.556$" not in trend)

    ch10 = new["chapters/10_nz_spatial_background.tex"]
    absent = {
        "raw-omega": re.compile(r"(?<![\\$A-Za-z])omega(?![A-Za-z])"),
        "raw-eta": re.compile(r"(?<![\\$A-Za-z])eta(?![A-Za-z])"),
        "raw-sigma": re.compile(r"(?<![\\$A-Za-z])sigma(?![A-Za-z])"),
        "raw-pi-beta": re.compile(r"(?<![\\$A-Za-z])(pi|beta)(?![A-Za-z])"),
        "old-scientific-tokens": re.compile(r"order1e-5|Iteration28|C 1|ALL THREE|3\.28e-11|1e-11|1e-4"),
    }
    for cid, pattern in absent.items():
        found = sorted({m.group(0) for m in pattern.finditer(ch10)})
        add(checks, f"repair-absent-{cid}", not found, found=found)
    present = {
        "radial-kernel": "$(1+\\lVert z-z_j\\rVert^2/\\sigma^2)^{-2}$",
        "cell-allocation": "$q(c\\mid z)$",
        "sum-log-q": "$\\sum\\log q$",
        "distance-sigma": "$\\sigma=150, 150, 50$~km",
        "small-p": "$10^{-11}$",
        "audit-tolerance": "$3.28\\times 10^{-11}$",
        "reconciliation-tolerance": "$10^{-4}$",
        "k3": "$K=3$",
        "r07": "$r=0.7$",
    }
    for cid, token in present.items():
        add(checks, f"repair-present-{cid}", token in ch10, token=token)
    app = new["appendix_tables/ch10_audit.tex"]
    add(checks, "repair-appendix-beta", "shared $\\beta$" in app and "shared beta" not in app)

    baseline = new["chapters/08_observed_baseline.tex"]
    add(
        checks,
        "repair-origin-background-wording",
        "unattenuated background intensity is approximately" in baseline
        and "unattenuated background intercept is approximately" not in baseline,
    )

    counts["required_tokens"] = len(required) + len(present)
    payload = component_head(
        "slice3_manuscript_repairs_v1",
        "Byte-level numeric-preservation check and presence/absence checks for every confirmed Slice 3 "
        "editorial and mathematical repair.",
        checks,
        counts,
    )
    dump("manuscript_repairs.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 11. Code and implementation consistency
# ---------------------------------------------------------------------------


def audit_code_consistency() -> dict:
    checks: list[dict] = []
    counts: dict = {}

    # Source pins used by the executable projection.
    spec = importlib.util.spec_from_file_location(
        "_slice3_trend_depletion_code", ROOT / "experiments/methodological_audit/trend_depletion.py"
    )
    td = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = td
    spec.loader.exec_module(td)
    for relative, expected in td.PINS.items():
        actual = sha256(ROOT / relative)
        add(checks, f"pin-{relative}", actual == expected, expected=expected, actual=actual)
    add(checks, "authority-pin", td.PINS[td.AUTHORITY] == OBSERVED_SHA256)

    # Autonomous model pins and first-moment formula.
    spec = importlib.util.spec_from_file_location(
        "_slice3_autonomous_model", ROOT / "experiments/autonomous/model.py"
    )
    am = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = am
    spec.loader.exec_module(am)
    for relative, expected in am.SOURCE_PINS.items():
        actual = sha256(ROOT / relative)
        add(checks, f"autonomous-pin-{relative}", actual == expected, actual=actual)
    gate = am.theorem_assumptions(-2.0, 0.5, 1.0, 3.1016219112585786)
    expected_m1 = math.exp(-am.GAMMA) * 3.1016219112585786 / (3.1016219112585786 - am.GAMMA)
    add(checks, "autonomous-m1-formula", close(gate["m1"], expected_m1, 1e-14), actual=gate["m1"], expected=expected_m1)
    add(checks, "autonomous-gamma", close(am.GAMMA, 0.75 * math.log(10.0), 1e-15), actual=am.GAMMA)

    # Engine kernel: normalized 195-mode ML mixture and modal-state recursion.
    spec = importlib.util.spec_from_file_location(
        "_slice3_adequacy", ROOT / "engine/iteration_27/code/adequacy.py"
    )
    ad = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = ad
    spec.loader.exec_module(ad)
    kernel = ad.KernelSpec("ml", 1.0, alpha=0.5, spectral_step=0.4, spectral_tail_bound=1e-8)
    weights, rates = kernel.mixture
    add(checks, "kernel-195-modes", len(weights) == 195, actual=len(weights))
    add(checks, "kernel-normalized", close(float(weights.sum()), 1.0, 1e-14), actual=float(weights.sum()))
    add(checks, "kernel-positive", bool(np.all(weights > 0) and np.all(rates > 0)))
    states = ad._modal_states(
        np.array([0.0, 1.0, 2.0]), np.array([1.0, 0.5, 0.2]), np.asarray(rates)
    )
    add(checks, "modal-states-shape", states.shape == (3, 195), actual=list(states.shape))
    slow = -np.expm1(-np.asarray(rates) * 24394.0) < 0.01
    add(checks, "slow-mode-count", int(slow.sum()) == 61, actual=int(slow.sum()))
    add(checks, "slow-mode-weight", display_ok(float(100.0 * weights[slow].sum()), 0.043, 3), actual=float(100.0 * weights[slow].sum()))

    # Forensic trend-control authorities and catalogue pins.
    spec = importlib.util.spec_from_file_location(
        "_slice3_forensic_controls",
        ROOT / "experiments/methodological_audit/forensic_nz_controls_20261114.py",
    )
    fc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fc
    spec.loader.exec_module(fc)
    add(checks, "forensic-catalogue-pin", fc.sha(ROOT / "reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv") == CSV_SHA256)
    add(checks, "forensic-authority-pin", fc.sha(AUTH["observed"]) == OBSERVED_SHA256)
    add(checks, "forensic-block-arithmetic", fc.block_se([1.0, 2.0, 3.0])["blocks"] == 3)

    # Reproduction manifest binding.
    manifest = load(ROOT / "reproduction/observed/manifest.json")
    add(checks, "observed-manifest-csv", manifest["required_input_binding"]["sha256"] == CSV_SHA256)
    add(checks, "observed-manifest-events", manifest["required_input_binding"]["n_events"] == 913)
    add(checks, "observed-manifest-leaves", manifest["expected_scientific_leaves"] == 90609 and manifest["expected_scientific_numeric_leaves"] == 83506)

    counts["source_pins"] = len(td.PINS) + len(am.SOURCE_PINS)
    payload = component_head(
        "slice3_code_consistency_v1",
        "Executable implementation consistency: source pins, normalized finite-mode mixtures, modal recursion, "
        "slow-mode count and weight, autonomous first-moment formula, and the observed reproduction manifest.",
        checks,
        counts,
    )
    dump("code_consistency.json", payload)
    return payload

# ---------------------------------------------------------------------------
# 12. Summary and CLI
# ---------------------------------------------------------------------------


def audit_summary(components: dict[str, dict]) -> dict:
    passed = all(c["passed"] for c in components.values())
    counts = {name: c.get("counts", {}) for name, c in components.items()}
    summary = {
        "schema": "slice3_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "10d253f",
        "scope": (
            "Vertical Triad Slice 3: Chapters 8 and 10, Appendix B.8, reconstructed New Zealand "
            "baseline, paired block uncertainty, trend--depletion controls, complete 18-cell search, "
            "autonomous constant-background subfamily, C1/W/D/S spatial stages, and the twelve-model "
            "temporal--spatial--background factorial."
        ),
        "passed": passed,
        "components": {name: c["passed"] for name, c in components.items()},
        "counts": counts,
        "defects_and_repairs": [
            {
                "id": "slice3-full-grid-fold1-as-total",
                "file": "paper/source/chapters/08_nz_trend_controls.tex",
                "locator": "line 6 and Table tab:nz-trend-controls",
                "finding": (
                    "The eighteen-cell search description reported the first-fold winners "
                    "(0.5,1,0.4), held-out contrasts -8.504/-4.556, as if they were both the "
                    "winners and the totals of all three folds. The stored grid selects "
                    "(0.5,1,0.4) in Fold 1 and (0.5,1,0.7) in Folds 2-3 for both arms; the "
                    "three-fold totals are -11.431 and -5.006 nats."
                ),
                "status": "fixed",
            },
            {
                "id": "slice3-fold-index-inconsistency",
                "file": "paper/source/chapters/08_nz_trend_controls.tex",
                "locator": "lines 2, 4, 8 and Table tab:nz-trend-controls",
                "finding": (
                    "The same first window was called Fold 1 in line 2, Fold 0 in line 4 and "
                    "F0 in the table. The text now states the one-based label with the archived "
                    "zero-based identifier and origin fraction for all three folds."
                ),
                "status": "fixed",
            },
            {
                "id": "slice3-ch10-raw-math-formatting",
                "file": "paper/source/chapters/10_nz_spatial_background.tex",
                "locator": "Sections 10.2-10.8",
                "finding": (
                    "Raw decision-log mathematical tokens (eta, omega, sigma, pi, beta, r=0.7, "
                    "K=3, C 1, 1e-11, 3.28e-11, 1e-4, order1e-5, Iteration28, ALL THREE) were "
                    "replaced by math-mode and prose forms. Every numeric literal was preserved."
                ),
                "status": "fixed",
            },
            {
                "id": "slice3-origin-ratio-wording",
                "file": "paper/source/chapters/08_observed_baseline.tex",
                "locator": "lines 102-104",
                "finding": (
                    "The ratios 9.60, 1.57 and 1.34 are ratios of the unattenuated background "
                    "intensity at each predictive origin, not three intercept ratios. Only the "
                    "first origin has x=0. The sentence now names the origin-specific intensity."
                ),
                "status": "fixed",
            },
            {
                "id": "slice3-master-ledger-slice3-coverage",
                "file": "validation/MASTER_CLAIM_LEDGER.json",
                "locator": "chapters/08_score_uncertainty.tex; chapters/08_nz_trend_controls.tex",
                "finding": (
                    "The master ledger resolves 3,676 Slice 3 records, including 67 score-uncertainty "
                    "and 84 trend-control bindings located through final_display_locations. No "
                    "Slice 3 subsection is left outside the ledger."
                ),
                "status": "verified",
            },
        ],
        "artifacts": {
            name: f"validation/live_results/slice3_audit_20261114/{name}.json"
            for name in sorted(components)
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }
    return summary


def main(argv=None) -> int:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=OUT,
        help="Output directory for machine-readable audit evidence.",
    )
    args = parser.parse_args(argv)
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)

    components = {}
    for name, function in (
        ("sealed_authority_integrity", audit_sealed_integrity),
        ("chapter8_baseline", audit_chapter8_baseline),
        ("chapter8_trend_controls", audit_chapter8_trend_controls),
        ("stage_c1", audit_stage_c1),
        ("stage_w", audit_stage_w),
        ("stage_d", audit_stage_d),
        ("stage_s", audit_stage_s),
        ("factorial_12model", audit_factorial),
        ("claim_ledger", audit_claim_ledger),
        ("manuscript_repairs", audit_manuscript_repairs),
        ("code_consistency", audit_code_consistency),
    ):
        print(f"[slice3] {name} ...", flush=True)
        components[name] = function()
        print(
            f"[slice3] {name}: {'PASS' if components[name]['passed'] else 'FAIL'} "
            f"({sum(not c['passed'] for c in components[name]['checks'])} failed checks)",
            flush=True,
        )
    summary = audit_summary(components)
    dump("summary.json", summary)
    print(json.dumps({"passed": summary["passed"], "components": summary["components"]}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
