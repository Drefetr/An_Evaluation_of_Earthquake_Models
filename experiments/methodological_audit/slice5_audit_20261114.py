#!/usr/bin/env python3
"""Independent Slice 5 mathematical, statistical, code, and manuscript audit.

Scope: Section 11.5 (magnitude-scaled ETAS ``EP+``), the self-declustered
2x2x2 component ablation, the interior ``sigma0`` relaxation and fixed-scale
profile, the twelve-parameter inhibited refit under ``sigma0 >= 0.05`` km, and
the California attenuation (``eta``) profiles.

The audit does three things that the archived receipts do not do for themselves:

1. It re-derives the displayed scalars from the bound JSON authorities, the
   stored per-fold rows, the LaTeX tables, and the executable Python code.
2. It re-verifies the divergence-theorem boundary integral and every analytic
   gradient against independent numerical quadrature / finite differences.
3. It recomputes the ``(a,d,n)``-profiled California attenuation curve at the
   same ``power=14`` Sobol resolution as the fixed-backbone curve and finds
   the exact ``brentq`` roots of both curves.  The archived coarse power=12
   PCHIP profile is thereby replaced by a resolution-matched profile and the
   envelope inequality ``eta_profiled >= eta_fixed`` is checked in every fold.

No sealed authority is rewritten.  The script only reads ``validation/`` and
writes its evidence package under ``validation/live_results/slice5_audit_20261114``.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import math
import platform
import re
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.optimize import brentq, minimize

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice5_audit_20261114"
SNAPSHOT = ROOT / "validation/slice5_prechange_snapshot_20261114.json"
SNAPSHOT_ZIP = ROOT / "validation/slice5_prechange_snapshot_20261114.zip"
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"

TEX = {
    "benchmark": ROOT / "paper/source/chapters/11_epplus_benchmark.tex",
    "ablation": ROOT / "paper/source/chapters/11_epplus_ablation.tex",
    "profiles": ROOT / "paper/source/chapters/11_epplus_eta_profiles.tex",
    "abstract": ROOT / "paper/source/abstract.tex",
}
SLICE5_TEX_FILES = {
    "chapters/11_epplus_benchmark.tex",
    "chapters/11_epplus_ablation.tex",
    "chapters/11_epplus_eta_profiles.tex",
    "abstract.tex",
}

AUTH = {
    "accepted": ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112",
    "summary": ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/summary.json",
    "baseline": ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_comparison.json",
    "uncertainty": ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_uncertainty/summary.json",
    "ablation_clean": ROOT / "validation/live_results/forensic_remediation_20261114/epplus_ablation.json",
    "sigma0_totals": ROOT / "validation/live_results/forensic_remediation_20261114/epplus_sigma0_totals.json",
    "relaxed_inhibited": ROOT / "validation/live_results/forensic_remediation_20261114/epplus_relaxed_inhibited.json",
    "eta_profiles": ROOT / "validation/live_results/forensic_remediation_20261114/eta_profiles.json",
    "track_b_ablation": ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/ablation.json",
    "track_b_relaxed": ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_relaxation.json",
    "track_b_frozen": ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_relaxation_frozen.json",
    "track_b_profile": ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_profile.json",
    "track_b_eta_archived": ROOT / "validation/live_results/track_b_controls_20261112/profiles_and_power/california_eta_profiles.json",
    "old_ep_benchmark": ROOT / "reproduction/score_replay/california_benchmark",
    "primary": ROOT / "reproduction/score_replay/california",
}

CASES = ("california_fold_0", "california_fold_1", "california_fold_2")
TARGETS = {"two_sided_95": -1.9207, "one_sided_95": -1.3528}
SCALE_PAIRS = ((10.0, 2.0), (15.0, 5.0), (20.0, 5.0), (50.0, 30.0))
SIGMA_GRID = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0)
EXPECTED_SEALED = 761

# Pre-edit values that the resolution-matched profile legitimately retires.
# They are recorded here so the numeric-preservation audit can distinguish an
# intentional repair from an accidental display loss.
ALLOWED_REMOVED = {
    "chapters/11_epplus_eta_profiles.tex": {
        1.1398e-4, 1.1187e-4, 9.2864e-5,
        8.1613e-5, 8.0085e-5, 6.6254e-5,
        8.8873e-4, 8.5332e-4, 5.8688e-4,
        6.9142e-4, 6.6052e-4, 4.3838e-4,
        -517.4, -514.2, -665.9, -95.7, -94.5, -124.9,
    },
    "chapters/11_epplus_ablation.tex": set(),
    "chapters/11_epplus_benchmark.tex": set(),
    "abstract.tex": set(),
}


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


def cell_number(cell: str):
    s = cell.strip().replace("$", "").replace("{", "").replace("}", "")
    s = s.replace("\\,", "").replace("\\ ", " ").replace("\\%", "%").replace("~", " ")
    s = s.replace("\\text{---}", "---").replace("\\pm", "").strip()
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


def parse_sci(cell: str):
    s = cell.replace("$", "").replace("{", "").replace("}", "").replace(" ", "")
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\\times10\^([+-]?\d+)", s)
    if not m:
        return None, None, None
    mantissa = float(m.group(1))
    exponent = int(m.group(2))
    decimals = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
    return mantissa * 10.0 ** exponent, decimals, exponent


def table_rows(path: Path, header: str) -> list[list[str]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if header in line]
    if not hits:
        raise ValueError(f"table header not found: {header!r} in {path.name}")
    rows = []
    for line in lines[hits[0] + 1:]:
        stripped = line.strip()
        if "\\end{tabular}" in stripped or "\\end{longtable}" in stripped:
            break
        if stripped.startswith("\\"):
            continue
        if "&" not in line:
            continue
        rows.append(split_latex_cells(line))
    return rows


# ---------------------------------------------------------------------------
# Frozen model loading
# ---------------------------------------------------------------------------

import experiments.etas_inhibition_benchmark.run_frozen_20261111 as RF  # noqa: E402
import experiments.etas_inhibition_benchmark.ablation_and_sigma0 as A  # noqa: E402
import experiments.methodological_audit.forensic_eta_profiles_20261114 as F_PROFILES  # noqa: E402


def accepted_record(case: str) -> dict:
    return load(AUTH["accepted"] / case / "result.json")


_CASE_CACHE: dict = {}


def load_case(case: str, power_train: int = 14, power_test: int = 16):
    key = (case, power_train, power_test)
    if key in _CASE_CACHE:
        return _CASE_CACHE[key]
    train, meta, test, test_meta, _ = RF.inputs(case)
    record = accepted_record(case)
    weights = np.asarray(record["background_weights"], dtype=float)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
    train_model = RF.Model(train, meta, background)
    test_model = RF.Model(test, test_meta, background)
    x0 = np.asarray(record["null"]["selected"]["parameters"], dtype=float)
    train_model.node_setup(x0, power=power_train, seed=20261111)
    test_model.node_setup(x0, power=power_test, seed=20261120)
    ctx = dict(record=record, train=train, meta=meta, test=test, test_meta=test_meta,
               weights=weights, region=region, background=background,
               train_model=train_model, test_model=test_model, x0=x0)
    _CASE_CACHE[key] = ctx
    return ctx


def at_eta(x, eta, ell, psi):
    y = np.asarray(x, dtype=float).copy()
    y[8] = eta
    y[9] = math.log(ell)
    y[10] = math.log(psi)
    return y


def five_point_gradient(model, x, inhibit: bool, indices, h: float = 2e-5):
    """Fourth-order central stencil; error O(h^4) plus O(eps*|f|/h)."""
    out = []
    coeffs = (1.0, -8.0, 8.0, -1.0)
    offsets = (-2.0, -1.0, 1.0, 2.0)
    for i in indices:
        total = 0.0
        for c, o in zip(coeffs, offsets):
            y = np.asarray(x, dtype=float).copy()
            y[i] += o * h
            total += c * float(model.objective(y, inhibit)[0])
        out.append(total / (12.0 * h))
    return np.asarray(out)


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
    checks = []
    add(checks, "sealed-count", record["sealed_json_count"] == EXPECTED_SEALED == len(sealed),
        expected=EXPECTED_SEALED, actual=record["sealed_json_count"])
    add(checks, "sealed-missing", not missing, missing=missing)
    add(checks, "sealed-changed", not changed, changed=changed)
    payload = component_head(
        "slice5_sealed_authority_integrity_v1",
        "Byte-level identity of every pre-existing JSON file under validation/authorities and "
        "validation/live_results plus the two prior Slice 4 record files.",
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
# 2. EP+ formulation, boundary integral, gradients, and benchmark contrast
# ---------------------------------------------------------------------------


def polar_mass(region, xy, scale, q, order=200):
    b = region.bounds
    corners = np.array([[b[0], b[2]], [b[1], b[2]], [b[1], b[3]], [b[0], b[3]]])
    angles = np.sort(np.mod(np.arctan2(corners[None, :, 1] - xy[:, None, 1],
                                      corners[None, :, 0] - xy[:, None, 0]), 2 * np.pi), axis=1)
    angles = np.c_[angles, angles[:, 0] + 2 * np.pi]
    z, w = leggauss(order)
    half = np.diff(angles) / 2
    theta = (angles[:, :-1] + half)[:, :, None] + half[:, :, None] * z
    co, si = np.cos(theta), np.sin(theta)
    rx = np.where(co > 0, (b[1] - xy[:, 0, None, None]) / co, (b[0] - xy[:, 0, None, None]) / co)
    ry = np.where(si > 0, (b[3] - xy[:, 1, None, None]) / si, (b[2] - xy[:, 1, None, None]) / si)
    radius = np.minimum(rx, ry)
    u = radius ** 2 / scale[:, None, None] ** 2
    weights = half[:, :, None] * w / (2 * np.pi)
    return np.sum(weights * (-np.expm1((1 - q) * np.log1p(u))), axis=(1, 2))


def audit_formulation() -> dict:
    checks, counts = [], {}
    mass_worst = 0.0
    mass_rows = 0
    slope_worst = 0.0
    grad_uninhibited_worst = 0.0
    grad_inhibited_worst = 0.0
    grad_scaled_worst = 0.0

    for case in CASES:
        ctx = load_case(case)
        model, region, x0 = ctx["train_model"], ctx["region"], ctx["x0"]
        scale = np.exp(x0[5] + x0[6] * model.dm)
        q = float(x0[7])
        mass, dmass, dq = region.mass(model.radii, scale, q)
        reference = polar_mass(region, model.pxy, scale, q)
        err = np.max(np.abs(mass - reference))
        mass_worst = max(mass_worst, err)
        mass_rows += len(mass)
        add(checks, f"mass-{case}", err < 1e-11, max_abs_error=err, parents=len(mass),
            min_mass=float(mass.min()), max_mass=float(mass.max()))

        h = 1e-6
        ds_fd = (region.mass(model.radii, scale * math.exp(h), q)[0]
                 - region.mass(model.radii, scale * math.exp(-h), q)[0]) / (2 * h)
        dq_fd = (region.mass(model.radii, scale, q + h)[0]
                 - region.mass(model.radii, scale, q - h)[0]) / (2 * h)
        ds_err = float(np.max(np.abs(dmass - ds_fd)))
        dq_err = float(np.max(np.abs(dq - dq_fd)))
        slope_worst = max(slope_worst, ds_err, dq_err)
        add(checks, f"mass-derivatives-{case}", ds_err < 1e-7 and dq_err < 1e-7,
            d_log_scale_max_abs=ds_err, d_q_max_abs=dq_err)

        for label, cls in (("plane", RF.Model), ("rect", A.RectModel)):
            other = cls(ctx["train"], ctx["meta"], ctx["background"])
            other.node_setup(x0, power=12, seed=20261111)
            value, gradient = other.objective(x0, True)
            fd = five_point_gradient(other, x0, True, range(12), h=5e-5)
            residual = np.abs(np.asarray(gradient) - fd)
            scaled = float(np.max(residual / np.maximum(1.0, np.abs(gradient))))
            grad_inhibited_worst = max(grad_inhibited_worst, scaled)
            add(checks, f"gradient-inhibited-{label}-{case}",
                scaled < 1e-7 and float(np.max(residual)) < 1e-3,
                max_abs=float(np.max(residual)), max_scaled=scaled)
        value, gradient = model.objective(x0, False)
        fd = five_point_gradient(model, x0, False, range(8), h=5e-5)
        residual = np.abs(np.asarray(gradient[:8]) - fd)
        grad_uninhibited_worst = max(grad_uninhibited_worst, float(np.max(residual)))
        add(checks, f"gradient-uninhibited-{case}", float(np.max(residual)) < 1e-7,
            max_abs=float(np.max(residual)))
        # The reported gradients are analytic; a second finite-difference check
        # at an interior perturbation makes the previous check local, not special.
        y = x0.copy()
        y[[1, 2, 3, 4, 6, 7]] += np.array([0.01, -0.01, 0.02, 0.01, 0.02, -0.05])
        value, gradient = model.objective(y, False)
        fd = five_point_gradient(model, y, False, range(8), h=5e-5)
        residual = np.abs(np.asarray(gradient[:8]) - fd)
        grad_scaled_worst = max(grad_scaled_worst, float(np.max(residual)))
        add(checks, f"gradient-uninhibited-interior-{case}", float(np.max(residual)) < 1e-7,
            max_abs=float(np.max(residual)))

    counts.update(parent_mass_rows=mass_rows, mass_max_abs_error=mass_worst,
                  mass_derivative_max_abs_error=slope_worst,
                  uninhibited_gradient_max_abs_error=grad_uninhibited_worst,
                  interior_gradient_max_abs_error=grad_scaled_worst,
                  inhibited_gradient_max_scaled_error=grad_inhibited_worst)

    # --- exact EP+ versus EP contrast (compare_baseline.py logic, read-only) ---
    from reproduction.score_replay.core import Inputs

    summary = load(AUTH["summary"])
    baseline = load(AUTH["baseline"])
    add(checks, "accepted-summary-passed", summary["passed"] is True)
    add(checks, "baseline-schema", baseline["schema"].startswith("epplus_vs_original_ep_checked_scores")
        and baseline["passed"] is True)
    add(checks, "baseline-summary-hash", baseline["accepted_summary_sha256"] == sha256(AUTH["summary"]))
    old_registry = load(AUTH["old_ep_benchmark"] / "registry.json")
    new_registry = load(AUTH["primary"] / "registry.json")
    gains = []
    for case in CASES:
        old_row = next(r for r in old_registry["rows"]
                       if r["phase"] == "test" and r["procedure_key"] == "EP" and r["case"] == case)
        new_row = next(r for r in new_registry["rows"]
                       if r["study"] == "primary_california" and r["case"] == case
                       and r["phase"] == "test" and r["procedure_key"] == "Omori_smooth_cont")

        def cache(folder, row):
            with np.load(__import__("io").BytesIO(Inputs(folder).read(row["cache"])), allow_pickle=False) as z:
                data = {k: z[k].copy() for k in z.files if k != "metadata_json"}
                meta = json.loads(str(z["metadata_json"].item()))
            return data, meta

        newdata, meta = cache(AUTH["primary"], new_row)
        olddata, oldmeta = cache(AUTH["old_ep_benchmark"], old_row)
        same = {k: bool(np.array_equal(newdata[k], olddata[k]))
                for k in ("parent_time", "parent_xy", "parent_fertility", "event_time",
                          "event_xy", "rectangles")}
        same.update({k: meta[k] == oldmeta[k] for k in ("start", "end", "T0", "beta")})
        state = Inputs(AUTH["old_ep_benchmark"]).json(old_row["state"])
        mark = float(len(newdata["event_time"]) * math.log(meta["beta"])
                     - meta["beta"] * newdata["event_excess"].sum())
        old = state["expected_components"]
        result = accepted_record(case)
        null_values = [-r["null"]["nll"] + mark for r in result["test_scores"]]
        row = next(r for r in baseline["rows"] if r["case"] == case)
        add(checks, f"baseline-history-{case}", all(same.values()), mismatches=[k for k, v in same.items() if not v])
        add(checks, f"baseline-mark-{case}", abs(mark - old["M"]) < 1e-8)
        add(checks, f"baseline-old-identity-{case}", abs(old["joint"] - (old["P"] - old["E"] + old["M"])) < 1e-8)
        add(checks, f"baseline-analytic-null-{case}", max(null_values) - min(null_values) < 1e-10)
        add(checks, f"baseline-row-{case}",
            close(null_values[0], row["new_joint_score"], 1e-12)
            and close(old["joint"], row["original_EP_joint_score"], 1e-12)
            and close(mark, row["common_mark_score"], 1e-12)
            and close(null_values[0] - old["joint"], row["gain"], 1e-12))
        gains.append(null_values[0] - old["joint"])
    total = float(sum(gains))
    counts["contrast_gains"] = [float(g) for g in gains]
    counts["contrast_total"] = total
    add(checks, "baseline-total", close(total, baseline["total_gain"], 1e-12),
        total=total, stored=baseline["total_gain"])
    add(checks, "baseline-rounded-gains",
        [round(g, 2) for g in gains] == [14.58, 30.69, 24.28], rounded=[round(g, 2) for g in gains])
    # manuscript tokens
    text = TEX["benchmark"].read_text(encoding="utf-8")
    for token in ("14.58, 30.69, and 24.28", "69.55~nats in total"):
        add(checks, f"benchmark-token-{token[:10]}", token in text, token=token)

    # --- paired calendar-block intervals ---
    uncertainty = load(AUTH["uncertainty"])
    spec = importlib.util.spec_from_file_location(
        "_slice5_resample", ROOT / "experiments/methodological_audit/score_uncertainty_cuda_frozen_v2_20261111.py")
    su = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = su
    spec.loader.exec_module(su)
    add(checks, "uncertainty-passed", uncertainty["passed"] is True)
    add(checks, "uncertainty-replicates", uncertainty["replicates"] == 49999)
    for days in ("90", "180", "365"):
        rows = uncertainty["rows_by_block_days"][days]
        for row in rows:
            fresh = su.resample(np.asarray(row["block_scores"], dtype=float))
            add(checks, f"block-resample-{days}-{row['case']}",
                close(fresh["total"], row["summary"]["total"], 1e-12)
                and all(close(a, b, 1e-10) for a, b in zip(fresh["ci95_total"], row["summary"]["ci95_total"]))
                and close(fresh["paired_sign_permutation_p"], row["summary"]["paired_sign_permutation_p"], 1e-12)
                and close(fresh["sign_test_p"], row["summary"]["sign_test_p"], 1e-12),
                blocks=fresh["blocks"], ci=fresh["ci95_total"])
        pooled = su.pooled(rows)
        stored = uncertainty["pooled_by_block_days"][days]
        add(checks, f"pooled-{days}",
            close(pooled["total"], stored["total"], 1e-12)
            and all(close(a, b, 1e-9) for a, b in zip(pooled["ci95_total"], stored["ci95_total"]))
            and close(pooled["paired_sign_permutation_p"], stored["paired_sign_permutation_p"], 1e-12)
            and close(pooled["sign_test_p"], stored["sign_test_p"], 1e-12),
            ci=pooled["ci95_total"], p=pooled["paired_sign_permutation_p"], blocks=pooled["blocks"])
        counts[f"pooled_{days}"] = dict(total=pooled["total"], ci=[float(x) for x in pooled["ci95_total"]],
                                        p=pooled["paired_sign_permutation_p"], blocks=pooled["blocks"])
    intervals = {"90": (32.239, 123.719, "0.00002"), "180": (32.153, 120.312, "0.00010"),
                 "365": (26.589, 122.164, "0.00452")}
    for days, (lo, hi, p) in intervals.items():
        stored = uncertainty["pooled_by_block_days"][days]
        add(checks, f"manuscript-interval-{days}",
            round(stored["ci95_total"][0], 3) == lo and round(stored["ci95_total"][1], 3) == hi
            and f"{stored['paired_sign_permutation_p']:.5f}" == p,
            ci=stored["ci95_total"], p=stored["paired_sign_permutation_p"])
    for token in ("[32.239,123.719]", "[32.153,120.312]", "[26.589,122.164]",
                  "p=0.00002", "p=0.00010", "p=0.00452"):
        add(checks, f"block-token-{token}", token in text, token=token)

    # --- benchmark table ---
    rows = table_rows(TEX["benchmark"], "Fold & $N_{\\rm train}$")
    for row, case in zip(rows, CASES):
        result = accepted_record(case)
        x = np.asarray(result["null"]["selected"]["parameters"], dtype=float)
        add(checks, f"benchmark-table-{case}",
            row[0] == f"F{CASES.index(case)}"
            and int(cell_number(row[1])) == result["n_train"]
            and int(cell_number(row[2])) == result["n_test"]
            and cell_ok(math.exp(x[5]), row[3], 3)
            and cell_ok(x[6], row[4], 3)
            and cell_ok(x[7], row[5], 3)
            and cell_ok(x[8], row[6], 6)
            and cell_ok(0.0, row[7], 4),
            cells=row, n_train=result["n_train"], n_test=result["n_test"],
            sigma0=math.exp(x[5]), alpha=x[6], q=x[7], eta=x[8])
    counts["benchmark_rows"] = len(rows)

    payload = component_head(
        "slice5_epplus_formulation_v1",
        "Divergence-theorem mass, analytic derivatives, plane/rectangle gradients, the exact "
        "EP+ minus EP contrast, and the paired calendar-block intervals.",
        checks, counts,
        notes=[
            "The finite-difference criterion is abs(residual) <= 1e-7 * max(1, |analytic gradient|). "
            "The eta coordinate of the inhibited gradient is O(1.7e4), so its absolute tolerance is 1.7e-3."
        ],
    )
    dump("epplus_formulation.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 3. Self-declustered 2x2x2 ablation and Shapley closure
# ---------------------------------------------------------------------------


def shapley_from_cells(values: dict, factors) -> dict:
    from itertools import combinations
    cells = {
        ("rect", False, False): values["A1"], ("plane", False, False): values["A2"],
        ("rect", True, False): values["A3"], ("plane", True, False): values["A4"],
        ("rect", False, True): values["A5"], ("plane", False, True): values["A6"],
        ("rect", True, True): values["A7"], ("plane", True, True): values["A8"],
    }
    names = list(factors)

    def value(subset):
        return cells[tuple(factors[name][0] if name in subset else factors[name][1] for name in names)]

    out = {}
    for name in names:
        total = 0.0
        others = [o for o in names if o != name]
        for size in range(len(others) + 1):
            for subset in combinations(others, size):
                weight = (math.factorial(size) * math.factorial(len(names) - size - 1)
                          / math.factorial(len(names)))
                total += weight * (value(set(subset) | {name}) - value(set(subset)))
        out[name] = float(total)
    return out


def audit_ablation(recompute: bool = False) -> dict:
    checks, counts = [], {}
    clean = load(AUTH["ablation_clean"])["clean_ablation"]
    archived = load(AUTH["track_b_ablation"])
    clean_rows = clean["rows"]
    totals = clean["totals"]

    # Table cells
    rows = table_rows(TEX["ablation"], "Arm & Norm.")
    expected = {
        "A0": [0.0, 0.0, 0.0, 0.0],
        "A1": archived["arms"]["A1"]["fold_gains"] + [archived["arms"]["A1"]["total_gain"]],
        "A2": archived["arms"]["A2"]["fold_gains"] + [archived["arms"]["A2"]["total_gain"]],
        "A3": [clean_rows["A3"][c]["gain_over_EP"] for c in CASES] + [totals["A3"]],
        "A4": [clean_rows["A4"][c]["gain_over_EP"] for c in CASES] + [totals["A4"]],
        "A5": archived["arms"]["A5"]["fold_gains"] + [archived["arms"]["A5"]["total_gain"]],
        "A6": archived["arms"]["A6"]["fold_gains"] + [archived["arms"]["A6"]["total_gain"]],
        "A7": [clean_rows["A7"][c]["gain_over_EP"] for c in CASES] + [totals["A7"]],
        "A8": [clean_rows["A8"][c]["gain_over_EP"] for c in CASES] + [totals["A8"]],
    }
    table_ok = True
    for row in rows:
        arm = row[0].strip()
        for actual, cell in zip(expected[arm], row[4:8]):
            table_ok &= cell_ok(actual, cell, 4)
        table_ok &= row[1].strip() in ("rect", "plane")
        table_ok &= row[2].strip() in ("unw", "decl")
        table_ok &= row[3].strip() in ("fixed", "free")
        add(checks, f"table-{arm}", all(cell_ok(a, c, 4) for a, c in zip(expected[arm], row[4:8])),
            cells=row[4:8], actual=expected[arm])
    add(checks, "table-row-count", len(rows) == 9, actual=len(rows))
    counts["table_rows"] = len(rows)

    # Totals are fold sums.
    for arm in ("A3", "A4", "A7", "A8"):
        s = sum(clean_rows[arm][c]["gain_over_EP"] for c in CASES)
        add(checks, f"fold-sum-{arm}", close(s, totals[arm], 1e-12), sum=s, stored=totals[arm])
    for arm in ("A0", "A1", "A2", "A5", "A6"):
        add(checks, f"archived-total-{arm}", close(totals[arm], archived["arms"][arm]["total_gain"], 1e-12))

    # Stored A8/A7 contrast.
    add(checks, "A7-A8-gap", close(totals["A8"] - totals["A7"], 0.00418, 5e-5),
        gap=totals["A8"] - totals["A7"])
    add(checks, "A8-total", close(totals["A8"], 69.55138526786914, 1e-12))

    # Shapley and sequential path.
    factors = {"normalization": ("plane", "rect"), "declustering": (True, False),
               "scaling": (True, False)}
    shapley = shapley_from_cells(totals, factors)
    joint_fit = totals["A1"] - totals["A0"]
    closure = totals["A8"] - totals["A0"]
    add(checks, "shapley-values",
        all(close(shapley[k], clean["shapley"][k], 1e-12) for k in shapley))
    add(checks, "shapley-rounded",
        {k: round(v, 3) for k, v in shapley.items()} ==
        {"normalization": 0.037, "declustering": 27.605, "scaling": 31.669})
    add(checks, "shapley-closure",
        close(joint_fit + sum(shapley.values()), closure, 1e-12),
        joint=joint_fit, sum=sum(shapley.values()), closure=closure,
        residual=joint_fit + sum(shapley.values()) - closure)
    add(checks, "shapley-zero-residual", abs(clean["closure_residual"]) < 1e-10)
    sequential = [totals["A1"] - totals["A0"], totals["A2"] - totals["A1"],
                  totals["A4"] - totals["A2"], totals["A8"] - totals["A4"]]
    add(checks, "sequential-values",
        all(close(a, b, 1e-12) for a, b in zip(sequential, clean["sequential_A0_A1_A2_A4_A8"])))
    add(checks, "sequential-rounded",
        [round(v, 3) for v in sequential] == [10.241, 0.089, 24.464, 34.757])
    add(checks, "sequential-closure", close(sum(sequential), closure, 1e-12))
    counts.update(joint_fit=joint_fit, closure=closure, shapley=shapley,
                  sequential=sequential, closure_residual=joint_fit + sum(shapley.values()) - closure)

    # Factorial table tokens.
    text = TEX["ablation"].read_text(encoding="utf-8")
    for token in ("27.605", "31.669", "0.037", "10.241", "69.547", "0.004"):
        add(checks, f"factorial-token-{token}", token in text, token=token)

    # Frozen-A8-weight reference.
    ref = clean["frozen_a8_weight_reference"]
    add(checks, "frozen-reference-total", close(ref["closure"], 69.55289384226876, 1e-12))
    add(checks, "frozen-declustering-inflation",
        close(ref["shapley"]["declustering"] - shapley["declustering"], 1.61796, 5e-4),
        difference=ref["shapley"]["declustering"] - shapley["declustering"])
    add(checks, "frozen-scaling-depression",
        close(ref["shapley"]["scaling"] - shapley["scaling"], -1.64343, 5e-4),
        difference=ref["shapley"]["scaling"] - shapley["scaling"])

    # --- code-level self-declustering audit ---
    source = (ROOT / "experiments/etas_inhibition_benchmark/forensic_ablation_20261114.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    self_decluster = ast.get_source_segment(source, funcs["self_decluster"])
    arm_job = ast.get_source_segment(source, funcs["arm_job"])
    neutral = ast.get_source_segment(source, funcs["neutral_starts"])
    run_clean = ast.get_source_segment(source, funcs["run_clean_ablation"])
    add(checks, "code-arms", all(a in source for a in ("A3", "A4", "A7", "A8")))
    add(checks, "code-neutral-starts", "math.log(5.0)" in neutral and "0.0" in neutral
        and "math.log(2.0)" in neutral and "math.log(15.0)" in neutral)
    add(checks, "code-self-decluster-five-step", "steps: int = 5" in self_decluster
        and "range(steps)" in self_decluster)
    add(checks, "code-neutral-first-iteration", "neutral_starts(scaled) if iteration == 0 else [x]" in self_decluster)
    add(checks, "code-own-normalization", 'cls = A.RectModel if normalization == "rect" else RF.Model' in self_decluster)
    add(checks, "code-no-imported-weights",
        "accepted_weights" not in self_decluster and "ACCEPTED" not in self_decluster
        and "ABLATION" not in self_decluster and "background_weights" not in self_decluster.split("return")[0])
    add(checks, "code-arm-job", "self_decluster(case, spec[\"normalization\"], spec[\"scaled\"])" in arm_job)
    add(checks, "code-no-a8-special-case",
        'if spec["id"] == "A8"' not in run_clean and "accepted_x" not in run_clean
        and "accepted_weights" not in run_clean)
    add(checks, "code-documented-no-a8-state",
        re.search(r"No arm\s+imports the accepted A8 weights", source) is not None)

    # Stored weights differ across declustered arms and from the accepted weights.
    weight_matrix = {}
    for case in CASES:
        accepted = np.asarray(accepted_record(case)["background_weights"], dtype=float)
        row = {}
        for arm in ("A3", "A4", "A7", "A8"):
            w = np.asarray(clean_rows[arm][case]["background_weights"], dtype=float)
            wn = w / w.sum()
            row[arm] = wn
            lineage = clean_rows[arm][case]["declustering"]
            add(checks, f"weights-normalized-{arm}-{case}",
                abs(wn.sum() - 1.0) < 1e-12
                and close(w.sum(), lineage[-1]["expected_immigrants"], 1e-10),
                normalized_sum=float(wn.sum()), prior_mass=float(w.sum()),
                expected_immigrants=lineage[-1]["expected_immigrants"])
            add(checks, f"weights-not-accepted-{arm}-{case}",
                float(np.max(np.abs(wn - accepted))) > 1e-9,
                max_difference=float(np.max(np.abs(wn - accepted))))
            add(checks, f"lineage-{arm}-{case}", len(lineage) == 5
                and close(lineage[-1]["expected_immigrants"], w.sum(), 1e-10))
        for a, b in (("A3", "A4"), ("A3", "A7"), ("A7", "A8"), ("A4", "A8")):
            add(checks, f"weights-distinct-{a}-{b}-{case}",
                float(np.max(np.abs(row[a] - row[b]))) > 1e-8)
        weight_matrix[case] = row
    counts["declustered_fold_rows"] = 4 * len(CASES)

    if recompute:
        import experiments.etas_inhibition_benchmark.forensic_ablation_20261114 as FA
        began = time.time()
        fresh = FA.run_clean_ablation(workers=3)
        differences = {}
        for arm in ("A3", "A4", "A7", "A8"):
            differences[arm] = {
                case: float(fresh["rows"][arm][case]["gain_over_EP"] - clean_rows[arm][case]["gain_over_EP"])
                for case in CASES}
        worst = max(abs(v) for arm in differences.values() for v in arm.values())
        add(checks, "recompute-all-declustered-arms", worst < 1e-6, worst_abs_difference=worst)
        counts["recomputed_arms_seconds"] = time.time() - began
        counts["recomputed_totals"] = fresh["totals"]
        counts["recomputed_differences"] = differences
        dump("ablation_recompute.json", dict(
            schema="slice5_ablation_recompute_v1", passed=worst < 1e-6,
            archived_totals=totals, recomputed_totals=fresh["totals"],
            per_fold_gain_differences=differences, worst_abs_difference=worst,
            elapsed_seconds=time.time() - began))
    else:
        saved_path = OUT / "ablation_recompute.json"
        if saved_path.is_file():
            saved = load(saved_path)
            differences = saved["per_fold_gain_differences"]
            worst = saved["worst_abs_difference"]
            add(checks, "recompute-all-declustered-arms", bool(saved["passed"]) and worst < 1e-6,
                worst_abs_difference=worst, source="saved ablation_recompute.json")
            counts["recomputed_arms_seconds"] = saved.get("elapsed_seconds")
            counts["recomputed_totals"] = saved["recomputed_totals"]
            counts["recomputed_differences"] = differences
            counts["recompute_source"] = "validation/live_results/slice5_audit_20261114/ablation_recompute.json"
        else:
            counts["recomputed_arms_seconds"] = None
            notes_recompute = ("A3/A4/A7/A8 were not re-fitted in this invocation; the archived rows "
                               "and code path were audited.")
    notes = [
        "A0 is the archived EP score. A1, A2, A5 and A6 do not use declustering and are retained from the archived ablation authority; the audit re-verifies their fold rows, totals and factorial cells.",
        "The declustered arms A3, A4, A7 and A8 each run a fresh five-step loop from the neutral three-start grid under their own normalization and scaling.",
    ]
    if not recompute and "recompute_source" not in counts:
        notes.append(notes_recompute)
    payload = component_head(
        "slice5_component_ablation_v1",
        "Nine-arm table, self-contained five-step declustering, exact 2x2x2 Shapley values, sequential path, and the frozen-A8-weight comparison.",
        checks, counts,
        notes=notes,
    )
    dump("component_ablation.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 4. Interior sigma0 relaxation, fixed-sigma0 profile, inhibited refit
# ---------------------------------------------------------------------------


def audit_sigma0() -> dict:
    checks, counts = [], {}
    relaxed = load(AUTH["track_b_relaxed"])
    frozen = load(AUTH["track_b_frozen"])
    profile = load(AUTH["track_b_profile"])
    inhibited = load(AUTH["relaxed_inhibited"])

    # Six relaxation rows.
    rows = table_rows(TEX["ablation"], "Fold/weights & $\\widehat\\sigma_0$")
    expected_rows = []
    for case in CASES:
        for norm in ("plane", "rect"):
            expected_rows.append((case, norm))
    table_expected = []
    for case in CASES:
        row = next(r for r in relaxed["rows"] if r["case"] == case and r["normalization"] == "plane")
        table_expected.append((row["sigma0"], row["alpha_s"], row["q"], row["gain_over_EP"]))
    for case in CASES:
        row = next(r for r in frozen["rows"] if r["case"] == case and r["normalization"] == "plane")
        table_expected.append((row["sigma0"], row["alpha_s"], row["q"], row["gain_over_EP"]))
    for row, actual in zip(rows, table_expected):
        ok = all(cell_ok(a, c, 3) for a, c in zip(actual, row[1:5]))
        add(checks, f"relaxation-table-{row[0]}", ok, cells=row[1:5], actual=actual)
    add(checks, "relaxation-table-count", len(rows) == 6, actual=len(rows))

    def split(payload):
        return {norm: [r for r in payload["rows"] if r["normalization"] == norm]
                for norm in ("plane", "rect")}

    relaxed_split, frozen_split = split(relaxed), split(frozen)
    totals = {
        "relaxed_plane": sum(r["gain_over_EP"] for r in relaxed_split["plane"]),
        "relaxed_rect": sum(r["gain_over_EP"] for r in relaxed_split["rect"]),
        "frozen_plane": sum(r["gain_over_EP"] for r in frozen_split["plane"]),
        "frozen_rect": sum(r["gain_over_EP"] for r in frozen_split["rect"]),
    }
    expected_totals = {"relaxed_plane": 77.0557339839778, "relaxed_rect": 77.05874171993219,
                       "frozen_plane": 78.584453, "frozen_rect": 78.51839026490643}
    counts.update(totals)
    for key, value in totals.items():
        add(checks, f"total-{key}", close(value, expected_totals[key], 2e-6), actual=value,
            expected=expected_totals[key])
    add(checks, "archived-double-count", close(relaxed["total_gain"], 154.11447570391, 1e-12),
        actual=relaxed["total_gain"])
    # The review brief's 154.053 / 76.997 figure is not in any sealed row.
    # Scan the pre-change roster only, so the audit's own explanatory note
    # cannot contaminate the check.
    all_text = ""
    for relative in load(SNAPSHOT)["sealed_json"]:
        path = ROOT / relative
        if path.is_file():
            all_text += path.read_text(encoding="utf-8-sig", errors="ignore")
    add(checks, "unsupported-154-053-absent", "154.053" not in all_text and "76.997" not in all_text)
    counts["archive_claim_154_053_present"] = "154.053" in all_text
    counts["archive_claim_76_997_present"] = "76.997" in all_text

    # Relaxed weights are redeclustered; frozen weights are the accepted EP+ weights.
    frozen_source = (ROOT / "experiments/etas_inhibition_benchmark/ablation_and_sigma0.py").read_text(encoding="utf-8")
    add(checks, "frozen-weights-use-accepted",
        "def relax_frozen_fold" in frozen_source
        and "weights = accepted_weights(case)" in frozen_source)
    for case in CASES:
        accepted = np.asarray(accepted_record(case)["background_weights"], dtype=float)
        rel = next(r for r in relaxed["rows"] if r["case"] == case and r["normalization"] == "plane")
        add(checks, f"relaxed-weights-changed-{case}",
            float(np.max(np.abs(np.asarray(rel["background_weights"]) - accepted))) > 1e-6)

    # Fixed-sigma0 profile: recompute every saved training NLL.
    worst_profile = 0.0
    interior = {}
    for norm in ("plane", "rect"):
        for case in CASES:
            entry = next(r for r in profile["rows"] if r["case"] == case and r["normalization"] == norm)
            model = A.RectModel if norm == "rect" else A.RF.Model
            train, meta, _, _, _ = A.RF.inputs(case)
            region = A.RF.Region(train["rectangles"])
            weights = np.asarray(accepted_record(case)["background_weights"], dtype=float)
            background = A.RF.Background(train["event_xy"], region, meta["kde_bandwidth"], weights)
            fit = model(train, meta, background)
            values = []
            for point in entry["curve"]:
                y = np.asarray(point["parameters"], dtype=float)
                value = float(fit.objective(y, False)[0])
                values.append(value)
                worst_profile = max(worst_profile, abs(value - point["training_nll"]))
            best_index = int(np.argmin(values))
            add(checks, f"profile-grid-{norm}-{case}",
                [p["sigma0_km"] for p in entry["curve"]] == list(SIGMA_GRID)
                and len(values) == 12
                and all(abs(v - p["training_nll"]) < 1e-6 for v, p in zip(values, entry["curve"])),
                worst=float(max(abs(v - p["training_nll"]) for v, p in zip(values, entry["curve"]))),
                best=entry["curve"][best_index]["sigma0_km"])
            interior[(norm, case)] = entry["curve"][best_index]["sigma0_km"]
            add(checks, f"profile-interior-{norm}-{case}",
                entry["curve"][best_index]["sigma0_km"] in (0.75, 1.0),
                sigma0=entry["curve"][best_index]["sigma0_km"])
    counts["profile_worst_recompute_error"] = worst_profile
    counts["profile_interior_sigma0"] = {f"{k[0]}:{k[1]}": v for k, v in interior.items()}

    # Manuscript profile table (plane rows only).
    profile_rows = table_rows(TEX["ablation"], "Fold & 0.05 & 0.10")
    for row, case in zip(profile_rows, CASES):
        entry = next(r for r in profile["rows"] if r["case"] == case and r["normalization"] == "plane")
        ok = all(abs(cell_number(c) - p["training_nll"]) <= 0.005 + 1e-9
                 for c, p in zip(row[1:13], entry["curve"]))
        add(checks, f"profile-table-{case}", ok, cells=row[1:13],
            values=[p["training_nll"] for p in entry["curve"]])

    # Inhibited refit under sigma0 >= 0.05.
    add(checks, "inhibited-passed", inhibited["passed"] is True)
    add(checks, "inhibited-all-eta-zero", inhibited["all_selected_eta_zero"] is True)
    fits = 0
    for row in inhibited["rows"]:
        case = row["case"]
        ctx = load_case(case)
        model = ctx["train_model"]
        add(checks, f"inhibited-starts-{case}", len(row["fits"]) == 4)
        for fit in row["fits"]:
            fits += 1
            z = np.asarray(fit["parameters"], dtype=float)
            add(checks, f"inhibited-eta-zero-{case}-{fit['label']}", abs(float(z[8])) < 1e-12,
                eta=float(z[8]))
            add(checks, f"inhibited-sigma0-{case}-{fit['label']}", float(np.exp(z[5])) >= 0.05 - 1e-12,
                sigma0=float(np.exp(z[5])))
            value = float(model.objective(z, True)[0])
            add(checks, f"inhibited-nll-{case}-{fit['label']}", abs(value - fit["nll"]) < 1e-6,
                recomputed=value, stored=fit["nll"])
            gradient = model.objective(z, True)[1]
            add(checks, f"inhibited-eta-gradient-{case}-{fit['label']}",
                float(gradient[8]) >= -1e-5, gradient_eta=float(gradient[8]))
        best = min(row["fits"], key=lambda r: r["nll"])
        add(checks, f"inhibited-selected-{case}",
            abs(best["nll"] - row["selected"]["nll"]) < 1e-12
            and abs(float(best["parameters"][8])) < 1e-12)
        add(checks, f"inhibited-paper-sigma0-{case}",
            round(float(np.exp(np.asarray(row["selected"]["parameters"])[5])), 3) ==
            {"california_fold_0": 0.828, "california_fold_1": 0.845,
             "california_fold_2": 0.827}[case])
        # Held-out gain at the selected state.
        test_model = ctx["test_model"]
        null_test = float(test_model.objective(ctx["x0"], False, True)["nll"])
        inhib_test = float(test_model.objective(np.asarray(row["selected"]["parameters"]), True, True)["nll"])
        add(checks, f"inhibited-test-gain-{case}",
            close(null_test - inhib_test, row["test_gain"], 1e-9),
            recomputed=null_test - inhib_test, stored=row["test_gain"])
    counts["inhibited_fits"] = fits
    counts["inhibited_sigma0"] = {r["case"]: float(np.exp(np.asarray(r["selected"]["parameters"])[5]))
                                  for r in inhibited["rows"]}

    payload = component_head(
        "slice5_sigma0_relaxation_v1",
        "Six relaxed-bound rows, the fixed-sigma0 training profile, the non-additivity of the plane and rectangle panels, and the twelve-parameter inhibited refit.",
        checks, counts,
        notes=[
            "The sealed Track B sigma0_relaxation.json records total_gain=154.11447570391, exactly the sum of the 77.056-nat plane panel and the 77.059-nat rectangle panel. No sealed JSON contains 154.053 or 76.997.",
        ],
    )
    dump("sigma0_relaxation.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 5. California eta profiles: exact power=14 roots, fixed and profiled
# ---------------------------------------------------------------------------


class ProfiledCurve:
    """Resolution-matched (a,d,n)-profiled EP+ attenuation curve at power=14.

    At fixed (c,p,sigma0,alpha_s,q,ell0,psi,gamma) the event and Sobol-node
    triggering sums H and the attenuation sums G do not depend on (a,d,n).
    Precomputing them once reduces every profile objective and analytic
    gradient to 1-D vector arithmetic.
    """

    def __init__(self, ctx: dict, scaled: bool, ell: float = 15.0, psi: float = 5.0):
        self.model = ctx["train_model"]
        self.x0 = ctx["x0"]
        xb = self.x0.copy()
        xb[8] = 0.0
        xb[9] = math.log(ell)
        xb[10] = math.log(psi)
        self.xb = xb
        self.ell, self.psi = ell, psi
        self.scaled = scaled
        e0, grad = self.model.exact_exposure(xb)
        self.AE = float(grad[2])
        self.B0 = float(grad[0])
        self.l, self.r, self.T = self.model.m["start"], self.model.m["end"], self.model.m["T0"]
        ev = self.model.events
        self.b_ev = np.asarray(ev["b"], dtype=float)
        self.xt_ev = 2 * ev["t"] / self.T - 1
        self.h_ev = self.model.H(ev, xb, False)
        self.G_ev = self.attenuation(ev, xb)
        hs, gs, ws, bs, xs = [], [], [], [], []
        data = self.model.nodes
        for start in range(0, len(data["t"]), 1024):
            raw = {k: v[start:start + 1024] for k, v in data.items()}
            z = self.model.prepare(raw["t"], raw["xy"], raw["b"])
            hs.append(self.model.H(z, xb, False))
            gs.append(self.attenuation(z, xb))
            ws.append(raw["w"])
            bs.append(raw["b"])
            xs.append(2 * raw["t"] / self.T - 1)
        self.h_n = np.concatenate(hs)
        self.g_n = np.concatenate(gs)
        self.w_n = np.concatenate(ws)
        self.b_n = np.concatenate(bs)
        self.xt_n = np.concatenate(xs)
        self.base = float(self.model.objective(self.x0, False, True)["nll"])
        if scaled:
            self.full_model = self.model
        else:
            self.full_model = F_PROFILES.UnscaledGModel(self.model.a, self.model.m, self.model.bg)
            self.full_model.node_setup(self.x0, power=14, seed=20261111)

    def attenuation(self, data, x):
        eta, le, lp, gamma = x[8:]
        psi = math.exp(lp)
        lag, r2, past = data["lag"], data["r2"], data["past"]
        if self.scaled:
            ell2 = np.exp(2 * le + np.log(10) * self.model.dm)
        else:
            ell2 = float(np.exp(2 * le))
        v = r2 / ell2
        k = np.exp(gamma * self.model.dm - lag / psi) * (1 + v) ** -2 * past
        return k.sum(axis=1)

    def B(self, a, d):
        l, r, T = self.l, self.r, self.T
        z = d * (r - l) / T
        center = (l + r) / T - 1
        if abs(z) < 1e-5:
            s = 1 + z * z / 6 + z ** 4 / 120
            corr = (r - l) / T * (z / 3 - z ** 3 / 45)
        else:
            s = np.sinh(z) / z
            corr = (r - l) / T * (1 / np.tanh(z) - 1 / z)
        return np.exp(a + d * center) * (r - l) * s, center + corr

    def nll_grad(self, v, eta):
        a, d, n = v
        Bt, corr = self.B(a, d)
        Be = np.exp(a + d * self.xt_ev) * self.b_ev
        lam = Be + n * self.h_ev
        dec = -np.expm1(-eta * self.g_n)
        Ln = np.exp(a + d * self.xt_n) * self.b_n + n * self.h_n
        deficit = float(self.w_n @ (Ln * dec))
        P = float(np.log(lam).sum())
        value = Bt + n * self.AE - deficit - P + eta * float(self.G_ev.sum())
        ga = Bt - float(self.w_n @ (np.exp(a + d * self.xt_n) * self.b_n * dec)) - float((Be / lam).sum())
        gd = (Bt * corr - float(self.w_n @ (np.exp(a + d * self.xt_n) * self.b_n * self.xt_n * dec))
              - float((Be * self.xt_ev / lam).sum()))
        gn = self.AE - float(self.w_n @ (self.h_n * dec)) - float((self.h_ev / lam).sum())
        return float(value), np.array([ga, gd, gn])

    def polish(self, v, eta, iterations: int = 8):
        """Newton refinement of the three profile coordinates on grad nll = 0."""
        v = np.asarray(v, dtype=float).copy()
        for _ in range(iterations):
            _, g = self.nll_grad(v, eta)
            if float(np.max(np.abs(g))) < 1e-10:
                break
            h = 1e-5
            jac = np.zeros((3, 3))
            for i in range(3):
                vp, vm = v.copy(), v.copy()
                vp[i] += h
                vm[i] -= h
                jac[:, i] = (self.nll_grad(vp, eta)[1] - self.nll_grad(vm, eta)[1]) / (2 * h)
            try:
                step = np.linalg.solve(jac, -g)
            except np.linalg.LinAlgError:
                break
            trial = v + step
            trial = np.clip(trial, [-12.0, -2.0, 1e-12], [0.0, 2.0, 0.98 - 1e-12])
            if not np.all(np.isfinite(trial)) or float(np.max(np.abs(trial - v))) > 0.05:
                break
            v = trial
        return v

    def optimize(self, eta, start):
        opt = minimize(lambda v: self.nll_grad(v, eta), np.asarray(start, dtype=float),
                       jac=True, bounds=[(-12.0, 0.0), (-2.0, 2.0), (0.0, 0.98)],
                       method="L-BFGS-B",
                       options=dict(maxiter=2000, maxls=200, ftol=1e-13, gtol=1e-9))
        v = self.polish(opt.x, eta)
        value, gradient = self.nll_grad(v, eta)
        bounds = [(-12.0, 0.0), (-2.0, 2.0), (0.0, 0.98)]
        hits = [i for i, (lo, hi) in enumerate(bounds)
                if min(abs(v[i] - lo), abs(v[i] - hi)) < 1e-9]
        return dict(v=v, nll=value, gradient=gradient, success=bool(opt.success),
                    nit=int(opt.nit), nfev=int(opt.nfev), bound_hits=hits)

    def fixed_root(self, target, upper=0.05):
        def f(eta):
            value, _ = self.nll_grad(self.x0[:3], eta)
            return (self.base - value) - target
        return float(brentq(f, 0.0, upper, xtol=1e-16, rtol=1e-15, maxiter=300))

    def profiled_root(self, target, upper=0.05):
        start = self.x0[:3].copy()

        def f(eta):
            nonlocal start
            result = self.optimize(eta, start)
            start = result["v"]
            return (self.base - result["nll"]) - target

        eta = float(brentq(f, 0.0, upper, xtol=1e-16, rtol=1e-15, maxiter=300))
        final = self.optimize(eta, start)
        gain = self.base - final["nll"]
        return dict(eta=eta, gain=float(gain), residual=float(gain - target),
                    nll=float(final["nll"]),
                    v=[float(x) for x in final["v"]], gradient=[float(x) for x in final["gradient"]],
                    bound_hits=final["bound_hits"], success=final["success"],
                    nit=final["nit"], nfev=final["nfev"])


def audit_eta_profiles() -> dict:
    checks, counts = [], {}
    stored = load(AUTH["eta_profiles"])
    archived_rows = {r["case"]: r for r in load(AUTH["track_b_eta_archived"])["rows"]}

    # --- fixed-backbone rows, recomputed at power=14 ---
    fixed = {}
    test_contrasts = {}
    for case in CASES:
        ctx = load_case(case)
        for ell, psi in SCALE_PAIRS:
            key = f"ell{ell:g}_psi{psi:g}"
            record = stored["cases"][case]["fixed_backbone"][key]
            archived = archived_rows[case]["fixed_backbone"][key]
            curve = ProfiledCurve(ctx, True, ell, psi)
            Ln0 = np.exp(curve.x0[0] + curve.x0[1] * curve.xt_n) * curve.b_n + curve.x0[2] * curve.h_n
            slope = float((curve.w_n @ (Ln0 * curve.g_n)) - curve.G_ev.sum())
            roots = {}
            for label, target in TARGETS.items():
                eta = curve.fixed_root(target)
                roots[label] = eta
                add(checks, f"fixed-root-{case}-{key}-{label}",
                    abs(eta - record["roots"][label]["eta"]) < 5e-13,
                    recomputed=eta, stored=record["roots"][label]["eta"],
                    difference=eta - record["roots"][label]["eta"])
            add(checks, f"fixed-slope-{case}-{key}",
                close(slope, record["training_score_slope_at_zero"], 1e-10),
                recomputed=slope, stored=record["training_score_slope_at_zero"])
            event_sum = float(curve.G_ev.sum())
            exposure = float(curve.w_n @ (Ln0 * curve.g_n))
            add(checks, f"fixed-sums-{case}-{key}",
                close(event_sum, record["event_sum_G"], 1e-9)
                and close(exposure, record["exposure_integral_lambda0_G"], 1e-9),
                event_sum=event_sum, exposure=exposure)
            if case == "california_fold_0" and key == "ell15_psi5":
                counts["fold0_event_sum"] = event_sum
                counts["fold0_exposure"] = exposure
                add(checks, "prose-fold0-sums",
                    round(event_sum, 1) == 75313.9 and round(exposure, 1) == 59415.5,
                    event_sum=event_sum, exposure=exposure)
            add(checks, f"fixed-identity-{case}-{key}",
                close(-slope, record["event_minus_exposure"], 1e-10),
                event_minus_exposure=record["event_minus_exposure"], negated_slope=-slope)
            # held-out contrast at eta=0.4
            test = ctx["test_model"]
            null_test = float(test.objective(ctx["x0"], False, True)["nll"])
            y = at_eta(ctx["x0"], 0.4, ell, psi)
            held = float(null_test - test.objective(y, True, True)["nll"])
            test_contrasts[(case, key)] = held
            add(checks, f"test-contrast-{case}-{key}",
                close(held, archived["s8_eta_test_gain"], 1e-8),
                recomputed=held, stored=archived["s8_eta_test_gain"])
            fixed[(case, key)] = dict(slope=slope, roots=roots, held=held,
                                      record=record, archived=archived, curve=curve)

    # --- archived profiled S8 held-out contrast and exact eta=0.4 recheck ---
    s8 = {}
    for case in CASES:
        ctx = load_case(case)
        row = stored["cases"][case]["profiled_s8_scale"]
        eta04 = next(r for r in row["curve"] if abs(r["eta"] - 0.4) < 1e-12)
        null_test = float(ctx["test_model"].objective(ctx["x0"], False, True)["nll"])
        stored_contrast = float(null_test - ctx["test_model"].objective(
            np.asarray(eta04["parameters"], dtype=float), True, True)["nll"])
        add(checks, f"s8-heldout-{case}", close(stored_contrast, row["s8_eta_test_gain"], 1e-9),
            recomputed=stored_contrast, stored=row["s8_eta_test_gain"])
        curve = ProfiledCurve(ctx, True, 15.0, 5.0)
        opt04 = curve.optimize(0.4, curve.x0[:3])
        y = curve.xb.copy(); y[:3] = opt04["v"]; y[8] = 0.4
        exact_contrast = float(null_test - ctx["test_model"].objective(y, True, True)["nll"])
        s8[case] = dict(archived_parameters=list(map(float, eta04["parameters"])),
                        archived_contrast=stored_contrast,
                        exact_profile_parameters=[float(x) for x in opt04["v"]],
                        exact_profile_bound_hits=opt04["bound_hits"],
                        exact_profile_contrast=exact_contrast,
                        difference=exact_contrast - row["s8_eta_test_gain"])
        print(f"[slice5] s8 {case}: archived {stored_contrast:.6f}, exact-profile {exact_contrast:.6f}",
              flush=True)
    counts["s8_profiled_contrasts"] = s8
    counts["s8_max_change"] = max(abs(v["difference"]) for v in s8.values())
    add(checks, "s8-rounding-stable",
        all(abs(v["difference"]) < 1e-2 for v in s8.values()),
        changes={k: v["difference"] for k, v in s8.items()})

    # --- fixed table (12 rows) ---
    rows = table_rows(TEX["profiles"], "Fold & $\\ell/\\psi$ (km, d)")
    table_ok = True
    for row, (case, (ell, psi)) in zip(rows, [(case, pair) for case in CASES for pair in SCALE_PAIRS]):
        key = f"ell{ell:g}_psi{psi:g}"
        rec = fixed[(case, key)]["record"]
        slope_cell = row[2]
        r1, d1, e1 = parse_sci(row[3])
        r2, d2, e2 = parse_sci(row[4])
        held = cell_number(row[5])
        ok = (abs(cell_number(slope_cell) - rec["training_score_slope_at_zero"]) <= 0.00005 + 1e-9
              and r1 is not None
              and abs(r1 - rec["roots"]["two_sided_95"]["eta"]) <= 0.5 * 10 ** (-d1) * 10 ** e1
              and r2 is not None
              and abs(r2 - rec["roots"]["one_sided_95"]["eta"]) <= 0.5 * 10 ** (-d2) * 10 ** e2
              and abs(held - fixed[(case, key)]["archived"]["s8_eta_test_gain"]) <= 0.00005 + 1e-9)
        table_ok &= ok
        add(checks, f"eta-table-{case}-{key}", ok, cells=row,
            roots=[rec["roots"]["two_sided_95"]["eta"], rec["roots"]["one_sided_95"]["eta"]])
    add(checks, "eta-table-count", len(rows) == 12, actual=len(rows))
    add(checks, "eta-table-all", table_ok)

    # --- exact resolution-matched profiled roots ---
    exact = {}
    envelope_worst = float("inf")
    residual_worst = 0.0
    full_model_worst = 0.0
    for case in CASES:
        ctx = load_case(case)
        exact[case] = {}
        for scaled in (True, False):
            tag = "scaled" if scaled else "unscaled"
            began = time.time()
            curve = ProfiledCurve(ctx, scaled, 15.0, 5.0)
            roots = {}
            for label, target in TARGETS.items():
                prof = curve.profiled_root(target)
                fixed_eta = curve.fixed_root(target, upper=0.05)
                # Full-model verification at the polished parameters.
                y = curve.xb.copy(); y[:3] = prof["v"]; y[8] = prof["eta"]
                full_nll = float(curve.full_model.objective(y, True, True)["nll"])
                full_model_worst = max(full_model_worst, abs(full_nll - prof["nll"]))
                gap = prof["eta"] - fixed_eta
                envelope_worst = min(envelope_worst, gap)
                residual_worst = max(residual_worst, abs(prof["residual"]))
                roots[label] = dict(profiled_eta=prof["eta"], fixed_eta=fixed_eta,
                                    gap=gap, gain=prof["gain"], residual=prof["residual"],
                                    parameters=prof["v"], gradient=prof["gradient"],
                                    bound_hits=prof["bound_hits"], success=prof["success"],
                                    nit=prof["nit"], nfev=prof["nfev"],
                                    full_model_nll=full_nll, fast_nll=prof["nll"])
                add(checks, f"envelope-{tag}-{case}-{label}", gap > 0,
                    profiled=prof["eta"], fixed=fixed_eta, gap=gap)
                add(checks, f"root-residual-{tag}-{case}-{label}", abs(prof["residual"]) < 1e-9,
                    residual=prof["residual"])
                add(checks, f"full-model-{tag}-{case}-{label}", abs(full_nll - prof["nll"]) < 1e-6,
                    full=full_nll, fast=prof["nll"])
            # eta=0.01 training gain for the caption
            opt01 = curve.optimize(0.01, curve.x0[:3])
            roots["eta_0.01"] = dict(gain=float(curve.base - opt01["nll"]),
                                     bound_hits=opt01["bound_hits"],
                                     parameters=[float(x) for x in opt01["v"]])
            exact[case][tag] = dict(roots=roots, seconds=time.time() - began)
            print(f"[slice5] profile {case} {tag}: "
                  f"{ {k: v['profiled_eta'] for k, v in roots.items() if isinstance(v, dict) and 'profiled_eta' in v} }",
                  flush=True)
    counts["envelope_worst_gap"] = envelope_worst
    counts["profiled_residual_worst"] = residual_worst
    counts["full_model_worst"] = full_model_worst
    add(checks, "envelope-all-positive", envelope_worst > 0, worst_gap=envelope_worst)
    add(checks, "residual-all", residual_worst < 1e-9, worst=residual_worst)
    add(checks, "full-model-all", full_model_worst < 1e-6, worst=full_model_worst)

    # Fixed-backbone unscaled and profiled-unscaled envelope values for the table.
    table_unscaled = {}
    for case in CASES:
        table_unscaled[case] = {
            tag: exact[case][tag]["roots"] for tag in ("scaled", "unscaled")}
    counts["exact_roots"] = {
        case: {tag: {label: value["profiled_eta"] for label, value in exact[case][tag]["roots"].items()
                      if isinstance(value, dict) and "profiled_eta" in value}
               for tag in ("scaled", "unscaled")}
        for case in CASES}
    counts["fixed_roots"] = {
        case: {tag: {label: value["fixed_eta"] for label, value in exact[case][tag]["roots"].items()
                      if isinstance(value, dict) and "fixed_eta" in value}
               for tag in ("scaled", "unscaled")}
        for case in CASES}
    counts["eta_0.01_gain"] = {
        case: {tag: exact[case][tag]["roots"]["eta_0.01"]["gain"] for tag in ("scaled", "unscaled")}
        for case in CASES}

    # --- unscaled table in the manuscript ---
    rows = table_rows(TEX["profiles"], "Fold & Scaled $\\eta^{97.5}_{\\rm upper}$")
    unscaled_ok = True
    for row, case in zip(rows, CASES):
        scaled95 = exact[case]["scaled"]["roots"]["two_sided_95"]["profiled_eta"]
        scaled95_one = exact[case]["scaled"]["roots"]["one_sided_95"]["profiled_eta"]
        unscaled95 = exact[case]["unscaled"]["roots"]["two_sided_95"]["profiled_eta"]
        unscaled95_one = exact[case]["unscaled"]["roots"]["one_sided_95"]["profiled_eta"]
        cells = [parse_sci(row[i]) for i in range(1, 5)]
        values = [scaled95, scaled95_one, unscaled95, unscaled95_one]
        ok = all(v is not None and abs(v - x) <= 0.5 * 10 ** (-d) * 10 ** e + 1e-18
                 for (v, d, e), x in zip(cells, values))
        unscaled_ok &= ok
        add(checks, f"unscaled-table-{case}", ok, cells=row[1:5], actual=values)
    add(checks, "unscaled-table-all", unscaled_ok)
    add(checks, "ridgecrest-length", close(stored["ridgecrest_ell_km"], 532.2, 2e-4),
        actual=stored["ridgecrest_ell_km"])

    # --- manuscript prose tokens ---
    text = TEX["profiles"].read_text(encoding="utf-8")
    for case in CASES:
        for tag in ("scaled", "unscaled"):
            for label in TARGETS:
                value = exact[case][tag]["roots"][label]["profiled_eta"]
                mantissa = value / 10 ** math.floor(math.log10(value))
                exponent = math.floor(math.log10(value))
                token = f"{mantissa:.4f}\\times10^{{{exponent}}}"
                if label == "two_sided_95":
                    add(checks, f"prose-token-{tag}-{case}", token in text, token=token)
    add(checks, "prose-fixed-15898", "15{,}898.4" in text)
    add(checks, "prose-event-sum", "75{,}313.9" in text)
    add(checks, "prose-exposure", "59{,}415.5" in text)

    payload = component_head(
        "slice5_eta_profiles_v1",
        "Twelve fixed-backbone profile rows, exact power=14 fixed and (a,d,n)-profiled brentq roots for the scaled and unscaled kernels, held-out S8 contrasts, and the envelope inequality.",
        checks, counts,
        notes=[
            "The profiled curve uses the same power=14 Sobol nodes and the same frozen importance weights as the fixed-backbone curve. Because H and G do not depend on (a,d,n), the profile objective is exact for the stored model.",
            "The archived profiled values were computed at power=12 with a seven-point PCHIP interpolation; they are superseded by the exact roots recorded here.",
        ],
    )
    payload["exact"] = {
        "cases": {
            case: {
                tag: {
                    "roots": {label: {k: v for k, v in value.items() if k != "parameters"}
                              for label, value in exact[case][tag]["roots"].items()},
                    "profile_parameters": {label: value["parameters"]
                                           for label, value in exact[case][tag]["roots"].items()
                                           if isinstance(value, dict) and "parameters" in value},
                    "seconds": exact[case][tag]["seconds"],
                } for tag in ("scaled", "unscaled")
            } for case in CASES
        },
    }
    payload["fixed_recomputation"] = {
        f"{case}|{key}": dict(slope=value["slope"],
                              two_sided_95=value["roots"]["two_sided_95"],
                              one_sided_95=value["roots"]["one_sided_95"],
                              held_out=value["held"])
        for (case, key), value in fixed.items()
    }
    # Deterministic, timestamp-free authority for the manuscript's profiled
    # roots.  The claim ledger binds the four-digit displays to this file, so
    # the hash is stable across audit reruns.
    authority = {
        "schema": "slice5_eta_profile_roots_v1",
        "method": "power=14 scrambled-Sobol nodes; (a,d,n)-profiled L-BFGS-B; exact brentq",
        "thresholds": dict(TARGETS),
        "scale": dict(ell0_km=15.0, psi_days=5.0),
        "kernels": {
            "scaled": "ell_j = 15 * 10^(0.5 (M_j - 4)) km",
            "unscaled": "ell_j = 15 km",
        },
        "cases": {
            case: {
                tag: {
                    label: {
                        "profiled_eta": float(f"{value['profiled_eta']:.12g}"),
                        "fixed_eta": float(f"{value['fixed_eta']:.12g}"),
                        "gap": float(f"{value['gap']:.12g}"),
                    }
                    for label, value in exact[case][tag]["roots"].items()
                    if isinstance(value, dict) and "profiled_eta" in value
                }
                for tag in ("scaled", "unscaled")
            }
            for case in CASES
        },
    }
    dump("eta_profile_roots_authority.json", authority)
    dump("eta_profiles_exact.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 6. Claim ledger
# ---------------------------------------------------------------------------


def audit_claim_ledger() -> dict:
    checks, counts = [], {}
    spec = importlib.util.spec_from_file_location("_slice5_verify_claims", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)
    receipt, ledgers, _ = vc.verify_ledgers(ROOT, authority_only=True)
    ledger = ledgers[0][1]
    claims = ledger["claims"]
    add(checks, "ledger-authority-resolution", receipt["passed"], failures=receipt["failures"][:10])
    slice5 = [c for c in claims
              if c.get("tex_file") in SLICE5_TEX_FILES
              or any(f in SLICE5_TEX_FILES for f in c.get("final_display_locations", []))]
    per_file = Counter()
    missing = []
    withdrawn = 0
    tex_numbers = {relative: vc.manuscript_numbers((ROOT / "paper/source" / relative).read_text(encoding="utf-8-sig"))
                   for relative in sorted(SLICE5_TEX_FILES)}
    all_numbers = {}

    def numbers_for(relative):
        if relative not in all_numbers:
            path = ROOT / "paper/source" / relative
            all_numbers[relative] = vc.manuscript_numbers(path.read_text(encoding="utf-8-sig"))
        return all_numbers[relative]

    for claim in slice5:
        files = [claim.get("tex_file")] if claim.get("tex_file") in SLICE5_TEX_FILES else []
        files += [f for f in claim.get("final_display_locations", []) if f in SLICE5_TEX_FILES]
        files = sorted(set(files))
        for relative in files:
            per_file[relative] += 1
        if claim.get("ledger_role") != "manuscript_binding":
            if claim.get("ledger_role") == "withdrawn_historical_result":
                withdrawn += 1
            continue
        if claim.get("display_format"):
            present = True
        else:
            wanted = vc.numeric_value(claim["display"])
            declared = sorted(set(
                ([claim["tex_file"]] if claim.get("tex_file") else [])
                + list(claim.get("final_display_locations", []))))
            present = any(wanted in numbers_for(f) for f in declared)
        if not present:
            missing.append({"id": claim["id"], "display": claim["display"], "files": files})
    add(checks, "ledger-slice5-display-presence", not missing, missing=missing[:20])
    hashes = receipt.get("source_hashes", {})
    stale = [relative for relative, expected in hashes.items()
             if (ROOT / relative).is_file() and sha256(ROOT / relative) != expected]
    add(checks, "ledger-custody-hashes", not stale, stale=stale[:20])
    add(checks, "ledger-slice5-files-tracked",
        all(f"paper/source/{relative}" in hashes for relative in SLICE5_TEX_FILES),
        tracked=len([r for r in SLICE5_TEX_FILES if f"paper/source/{r}" in hashes]))
    counts.update(slice5_claims=len(slice5), claims_by_file=dict(per_file),
                  missing_displays=len(missing), withdrawn_historical_records=withdrawn,
                  master_ledger_sha256=sha256(LEDGER),
                  custody_source_files=len(hashes))
    payload = component_head(
        "slice5_claim_ledger_v1",
        "Independent resolution of the master claim ledger and literal display presence for the four Slice 5 LaTeX sources.",
        checks, counts,
        notes=["The master ledger contains only six typed claims whose manuscript file is abstract.tex; the Slice 5 chapter displays are bound through the compact custody hash roster, not through per-number claims."],
    )
    payload["authority_receipt"] = {
        "passed": receipt["passed"], "counts": receipt["counts"], "failures": receipt["failures"][:20]}
    dump("claim_ledger.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 7. Manuscript state and numeric preservation
# ---------------------------------------------------------------------------


def scalar_literals(text: str, vc) -> set:
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
        text_value = str(value)
        if len(text_value) == 6 and text_value[:3] in present and text_value[3:] in present:
            values.discard(value)
    return values


def audit_manuscript() -> dict:
    checks, counts = [], {}
    with zipfile.ZipFile(SNAPSHOT_ZIP) as zf:
        old = {relative: zf.read(f"paper/source/{relative}").decode("utf-8")
               for relative in sorted(SLICE5_TEX_FILES)
               if f"paper/source/{relative}" in zf.namelist()}
    new = {relative: (ROOT / "paper/source" / relative).read_text(encoding="utf-8")
           for relative in sorted(SLICE5_TEX_FILES)}
    add(checks, "manuscript-source-snapshot", len(old) == len(SLICE5_TEX_FILES), actual=len(old))
    spec = importlib.util.spec_from_file_location("_slice5_verify_claims_manuscript", ROOT / "scripts/verify_claims.py")
    vc = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vc
    spec.loader.exec_module(vc)

    preservation = {}
    for relative in sorted(SLICE5_TEX_FILES):
        before = scalar_literals(old[relative], vc)
        after = scalar_literals(new[relative], vc)
        removed = sorted(str(v) for v in before - after)
        added = sorted(str(v) for v in after - before)
        allowed = [Decimal(str(v)) for v in ALLOWED_REMOVED[relative]]
        unexpected = []
        for text_value in removed:
            current = Decimal(text_value)
            if not any(abs(current - value) <= max(Decimal("1e-12"), abs(value) * Decimal("1e-9"))
                       for value in allowed):
                unexpected.append(text_value)
        preservation[relative] = dict(before=len(before), after=len(after),
                                      removed=removed, added=added,
                                      allowed_removed=sorted(str(v) for v in ALLOWED_REMOVED[relative]),
                                      unexpected=unexpected)
        add(checks, f"numeric-preservation-{relative}", not unexpected,
            removed=removed[:40], unexpected=unexpected[:20])
    counts["numeric_preservation"] = preservation

    # Required repaired tokens.
    profiles = new["chapters/11_epplus_eta_profiles.tex"]
    exact = load(OUT / "eta_profiles_exact.json")
    exact_cases = exact["exact"]["cases"]
    for case in CASES:
        for tag in ("scaled", "unscaled"):
            for label in TARGETS:
                value = exact_cases[case][tag]["roots"][label]["profiled_eta"]
                exponent = math.floor(math.log10(value))
                mantissa = value / 10 ** exponent
                token = f"{mantissa:.4f}\\times10^{{{exponent}}}"
                add(checks, f"required-{tag}-{case}-{label}", token in profiles, token=token)
    add(checks, "required-resolution-matched", "2^{14}" in profiles
        or "power=14" in profiles or "power$=$14" in profiles
        or "same quadrature resolution" in profiles)
    add(checks, "required-envelope-sentence", "envelope" in profiles.lower())
    add(checks, "required-exposure-values", "75{,}313.9" in profiles and "59{,}415.5" in profiles)
    add(checks, "required-ridgecrest", "532.2" in profiles)
    add(checks, "required-unscaled-ratio", "five to eight" in profiles or "eight times" in profiles)
    eta01 = exact["counts"]["eta_0.01_gain"]
    for case in CASES:
        for tag in ("scaled", "unscaled"):
            token = f"{round(eta01[case][tag], 1)}"
            add(checks, f"caption-eta01-{tag}-{case}", f"${token}$" in profiles, token=token)

    ablation = new["chapters/11_epplus_ablation.tex"]
    add(checks, "required-154-114", "154.114" in ablation)
    add(checks, "required-77-056", "77.056" in ablation)
    add(checks, "required-77-059", "77.059" in ablation)
    add(checks, "required-withdrawn-154-053", "154.053" in ablation and "76.997" in ablation)
    add(checks, "required-not-additive", "not additive" in ablation or "must not be added" in ablation)

    benchmark = new["chapters/11_epplus_benchmark.tex"]
    for token in ("14.58, 30.69, and 24.28", "69.55~nats in total",
                  "[32.239,123.719]", "[32.153,120.312]", "[26.589,122.164]",
                  "p=0.00002", "p=0.00010", "p=0.00452"):
        add(checks, f"benchmark-required-{token[:12]}", token in benchmark, token=token)

    # Abstract numbers against the authorities.
    abstract = new["abstract.tex"]
    clean = load(AUTH["ablation_clean"])["clean_ablation"]
    archived = load(AUTH["track_b_ablation"])
    tokens = {
        "69.55": clean["closure_A8_minus_A0"],
        "31.67": clean["shapley"]["scaling"],
        "27.60": clean["shapley"]["declustering"],
        "69.551": clean["closure_A8_minus_A0"],
        "29.22": archived["factorial"]["shapley"]["declustering"],
        "30.03": archived["factorial"]["shapley"]["scaling"],
        "0.06": archived["factorial"]["shapley"]["normalization"],
        "69.553": archived["factorial"]["closure_A8_minus_A0"],
        "1.62": archived["factorial"]["shapley"]["declustering"] - clean["shapley"]["declustering"],
        "1.64": clean["shapley"]["scaling"] - archived["factorial"]["shapley"]["scaling"],
        "77.06": 77.0557339839778,
        "78.58": 78.584453,
        "78.52": 78.51839026490643,
    }
    for token, value in tokens.items():
        add(checks, f"abstract-token-{token}", token in abstract, token=token, value=value)

    # No raw scientific notation in the repaired Slice 5 sources.
    for relative in ("chapters/11_epplus_eta_profiles.tex", "chapters/11_epplus_ablation.tex",
                     "chapters/11_epplus_benchmark.tex"):
        found = re.findall(r"(?<![\w.])[0-9]\.[0-9]+e[+-]?[0-9]+", new[relative])
        add(checks, f"no-raw-scientific-{relative}", not found, found=found[:10])

    counts["required_tokens"] = sum(1 for c in checks if c["id"].startswith("required-")
                                    or c["id"].startswith("benchmark-required-")
                                    or c["id"].startswith("abstract-token-"))
    payload = component_head(
        "slice5_manuscript_state_v1",
        "Byte-level numeric preservation, required repair tokens, abstract bindings, and absence of raw scientific notation in the four Slice 5 sources.",
        checks, counts,
    )
    dump("manuscript_state.json", payload)
    return payload


# ---------------------------------------------------------------------------
# 8. Summary and CLI
# ---------------------------------------------------------------------------


def audit_summary(components: dict[str, dict]) -> dict:
    passed = all(c["passed"] for c in components.values())
    counts = {name: c.get("counts", {}) for name, c in components.items()}
    return {
        "schema": "slice5_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "2088c56",
        "scope": (
            "Vertical Triad Slice 5: Section 11.5 magnitude-scaled ETAS (EP+), the "
            "self-declustered 2x2x2 component ablation, the interior sigma0 relaxation and "
            "fixed-sigma0 profile, the twelve-parameter inhibited refit under sigma0 >= 0.05 km, "
            "and the California eta profiles."
        ),
        "passed": passed,
        "components": {name: c["passed"] for name, c in components.items()},
        "counts": counts,
        "defects_and_repairs": [
            {
                "id": "slice5-eta-profile-envelope",
                "file": "paper/source/chapters/11_epplus_eta_profiles.tex",
                "locator": "line 2 and Table tab:california-eta-profiles-unscaled line 33",
                "finding": (
                    "The archived profiled (a,d,n) curve used power=12 Sobol nodes and a "
                    "seven-point PCHIP interpolation, while the fixed-backbone curve used "
                    "power=14 and exact brentq roots. The mismatch produced F0 "
                    "1.1398e-4 < 1.1414e-4, violating the envelope inequality "
                    "eta_profiled >= eta_fixed that follows from max_{a,d,n} l(a,d,n,eta) >= "
                    "l(a0,d0,n0,eta). The audit recomputes the profile at power=14 with the "
                    "same frozen importance weights and exact brentq roots. Every fold now "
                    "satisfies the inequality strictly."
                ),
                "status": "fixed",
            },
            {
                "id": "slice5-eta-profile-unscaled",
                "file": "paper/source/chapters/11_epplus_eta_profiles.tex",
                "locator": "Table tab:california-eta-profiles-unscaled and caption",
                "finding": (
                    "The archived unscaled ell=15 km roots were also coarse-grid PCHIP "
                    "values. They are replaced by exact power=14 brentq roots; the unscaled-"
                    "to-scaled ratio is restated as roughly six to eight rather than eight."
                ),
                "status": "fixed",
            },
            {
                "id": "slice5-sigma0-double-count-clarification",
                "file": "paper/source/chapters/11_epplus_ablation.tex",
                "locator": "line 4",
                "finding": (
                    "The manuscript stated only that the archived 154.114-nat total double-"
                    "counted the plane and rectangle panels. The sealed Track B rows give "
                    "77.056 (plane) and 77.059 (rectangle). The review brief's 154.053-nat "
                    "reading (77.056 + 76.997) is not present in any sealed authority and is "
                    "explicitly withdrawn in the repaired sentence."
                ),
                "status": "fixed",
            },
            {
                "id": "slice5-claim-ledger-rebinding",
                "file": "validation/MASTER_CLAIM_LEDGER.json",
                "locator": "claims track-b-20261112-287/288/289",
                "finding": (
                    "Three typed manuscript claims bound the displays 1.1398e-4, 1.1187e-4 "
                    "and 9.2864e-5 to the archived power=12 PCHIP roots. They are rebound to "
                    "the deterministic power=14 roots in "
                    "validation/live_results/slice5_audit_20261114/eta_profile_roots_authority.json "
                    "and the custody receipt is refreshed."
                ),
                "status": "fixed",
            },
        ],
        "artifacts": {
            name: "validation/live_results/slice5_audit_20261114/" + {
                "sealed_authority_integrity": "sealed_authority_integrity.json",
                "epplus_formulation": "epplus_formulation.json",
                "component_ablation": "component_ablation.json",
                "sigma0_relaxation": "sigma0_relaxation.json",
                "eta_profiles": "eta_profiles_exact.json",
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
    parser.add_argument("--only", default="",
                        help="Comma-separated component names; empty runs all components.")
    parser.add_argument("--recompute-arms", action="store_true",
                        help="Re-fit the four declustered arms in all three folds.")
    parser.add_argument("--summary-only", action="store_true",
                        help="Reassemble summary.json from the existing component JSONs.")
    args = parser.parse_args(argv)
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.summary_only:
        files = {
            "sealed_authority_integrity": "sealed_authority_integrity.json",
            "epplus_formulation": "epplus_formulation.json",
            "component_ablation": "component_ablation.json",
            "sigma0_relaxation": "sigma0_relaxation.json",
            "eta_profiles": "eta_profiles_exact.json",
            "claim_ledger": "claim_ledger.json",
            "manuscript_state": "manuscript_state.json",
        }
        components = {name: load(OUT / filename) for name, filename in files.items()}
        summary = audit_summary(components)
        dump("summary.json", summary)
        print(json.dumps({"passed": summary["passed"], "components": summary["components"]}, indent=2))
        return 0 if summary["passed"] else 1

    roster = (
        ("sealed_authority_integrity", audit_sealed_integrity),
        ("epplus_formulation", audit_formulation),
        ("component_ablation", lambda: audit_ablation(recompute=args.recompute_arms)),
        ("sigma0_relaxation", audit_sigma0),
        ("eta_profiles", audit_eta_profiles),
        ("claim_ledger", audit_claim_ledger),
        ("manuscript_state", audit_manuscript),
    )
    wanted = {x.strip() for x in args.only.split(",") if x.strip()}
    components = {}
    for name, function in roster:
        if wanted and name not in wanted:
            continue
        print(f"[slice5] {name} ...", flush=True)
        began = time.time()
        components[name] = function()
        print(f"[slice5] {name}: {'PASS' if components[name]['passed'] else 'FAIL'} "
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
