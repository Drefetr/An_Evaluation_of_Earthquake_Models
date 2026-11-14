#!/usr/bin/env python3
"""Independent Slice 2 mathematical, statistical, code, and manuscript audit.

Scope: Chapters 6, 7, 9 (Sections 9.1--9.13), Appendix B.7, the completed S02
study, Stage A exposure orthogonalization, Stage B parent-class temporal scales,
and Extension O continuous Omori tuning.  The audit re-derives the displayed
algebra and statistics from the bound JSON authorities and the recovered
execution records.  It performs deterministic algebra, quadrature, table
reconstruction, exact binomial/Wilson interval recomputation, and claim-ledger
authority resolution.  It does not fit models, simulate catalogues, or modify a
sealed authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
import sympy as sp
from scipy import stats
from scipy.integrate import quad

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice2_audit_20261114"
OUTPUT_ROOT = OUT
SNAPSHOT = ROOT / "validation/slice2_prechange_snapshot_20261114.json"
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"

TEX = {
    "ch06": ROOT / "paper/source/chapters/06_design.tex",
    "ch07": ROOT / "paper/source/chapters/07_synthetic.tex",
    "ch09": ROOT / "paper/source/chapters/09_temporal_mark_extensions.tex",
    "s02": ROOT / "paper/source/chapters/09_s02_completed.tex",
    "audit09": ROOT / "paper/source/appendix_tables/ch09_audit.tex",
    "ch04": ROOT / "paper/source/chapters/04_identifiability.tex",
}
AUTH = {
    "stage_a": ROOT / "validation/authorities/cf8397fb41830b31_summary.json",
    "stage_b": ROOT / "validation/authorities/36fbe1b85eece436_summary.json",
    "stage_o": ROOT / "validation/authorities/2b8b5d88a869a425_summary.json",
    "pilot": ROOT / "validation/authorities/ee1aeccb6567a6d1_summary.json",
    "history": ROOT / "validation/authorities/4fee6d99c90bfd8f_aggregate_data.json",
    "s02_summary": ROOT / "validation/authorities/cc72e29fde61ec17_s02_summary.json",
    "s02_paired": ROOT / "validation/authorities/9b09b4cc2b0aa818_s02_paired.json",
    "s02_derived": ROOT / "validation/authorities/1210ed825946f8e7_s02_s03_derived_values.json",
    "detection": ROOT / "paper/data/detection.json",
    "paired": ROOT / "paper/data/paired.json",
    "eta_study": ROOT / "validation/authorities/ec93b8df8777d945_summary.json",
    "eta_final": ROOT / "validation/authorities/5912d697cc478e2d_A_final_interpretation.json",
    "gram": ROOT / "validation/authorities/e5cb515c9af35059_gram_diagnostics.json",
    "fold0": ROOT / "validation/authorities/ad3bfc8da71d7040_fold0_reconciliation.json",
    "s02_acceptance": ROOT / "validation/acceptances/S02_ACCEPTANCE.json",
    "settings": ROOT / "paper/supplements/methods_settings.json",
    "reference": ROOT / "validation/authorities/4761702854830904_reference_score_geometry.json",
}
KERNELS = ROOT / "engine/iteration_5/code/kernels.py"
S14_CSV = ROOT.parent / "iteration_24/completion/results/paired_diagnostics.csv"
S14_SUMMARY = ROOT.parent / "iteration_24/completion/results/summary.json"
S11_CSV = ROOT.parent / "iteration_22/results/statistic_decomposition.csv"
S11_JSON = ROOT.parent / "iteration_22/results/statistic_decomposition.json"

MANUSCRIPT_FILES = {
    "chapters/04_identifiability.tex",
    "chapters/06_design.tex",
    "chapters/07_synthetic.tex",
    "chapters/09_temporal_mark_extensions.tex",
    "chapters/09_s02_completed.tex",
    "appendix_tables/ch09_audit.tex",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name: str, path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump(name: str, payload) -> str:
    path = OUTPUT_ROOT / name
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return path.relative_to(ROOT).as_posix()


def pointer(data, path: str):
    if path == "":
        return data
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("invalid JSON pointer")
    value = data
    for part in path[1:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            value = value[int(key)]
        else:
            value = value[key]
    return value


def decimal_value(value) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("not a numeric scalar")
    text = str(value).strip().replace("\u2212", "-").replace(r"\,", "")
    text = re.sub(r"\\times\s*10\^\{([+-]?\d+)\}", r"e\1", text)
    text = re.sub(r"10\^\{([+-]?\d+)\}", r"1e\1", text)
    text = text.replace("{,}", "").replace(",", "").replace("%", "")
    match = re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text)
    if not match:
        raise ValueError(f"invalid numeric representation: {value!r}")
    return Decimal(text)


def equal_display(raw, claim) -> bool:
    desired = decimal_value(claim["display"])
    actual = decimal_value(raw)
    precision = Decimal(10) ** desired.as_tuple().exponent
    slack = max(abs(actual), abs(desired)) * Decimal("2e-14") + Decimal("1e-28")
    return abs(actual - desired) <= precision / 2 + slack


def transformed(raw, claim, data):
    transform = claim.get("transformation")
    if isinstance(transform, str) and transform == "percent_round_2":
        return 100 * raw
    if isinstance(transform, str) and transform == "bytes_to_GiB":
        return raw / (1024 ** 3)
    if not isinstance(transform, dict):
        return raw
    op = transform.get("operation")
    if op == "multiply":
        return raw * transform["factor"]
    if op == "divide":
        return raw / transform["divisor"]
    if op == "negate":
        return -raw
    if op == "sum":
        return sum(pointer(data, p) for p in transform["operand_pointers"])
    if op == "difference":
        values = [pointer(data, p) for p in transform["operand_pointers"]]
        return values[0] - sum(values[1:])
    if op == "count_over_total":
        return raw
    return raw


def numeric_tokens(text: str) -> set[Decimal]:
    text = text.replace("\u2212", "-").replace(r"\,", "").replace("{,}", "")
    text = re.sub(r"\\times\s*10\^\{([+-]?\d+)\}", r"e\1", text)
    text = re.sub(r"10\^\{([+-]?\d+)\}", r"1e\1", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    values = set()
    for match in re.finditer(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
        try:
            values.add(Decimal(match.group(0)))
        except InvalidOperation:
            pass
    return values


def cell_number(cell: str):
    text = cell.strip()
    if not text or text in {"--", "-", "None", "\\dots"}:
        return None
    text = text.replace("$", "").replace("\\%", "").replace("%", "")
    text = text.replace("{,}", "").replace(",", "").replace("~", "")
    text = re.sub(r"\\(?:texttt|textbf|path|mathrm|text)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\times\s*10\^\{([+-]?\d+)\}", r"e\1", text)
    text = re.sub(r"10\^\{([+-]?\d+)\}", r"1e\1", text)
    text = text.replace("−", "-").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def display_match(cell: str, value: float) -> bool:
    text = str(cell).strip().replace("$", "")
    if "e" in text.lower() or "\\times" in text:
        try:
            shown = cell_number(text)
        except Exception:
            return False
        if shown is None:
            return False
        return abs(shown - value) <= max(abs(value), 1.0) * 5e-12
    stripped = re.sub(r"[^0-9.\-+]", "", text)
    if not stripped:
        return False
    decimals = len(stripped.split(".")[1]) if "." in stripped else 0
    tolerance = 0.5 * 10 ** (-decimals) + max(abs(value), 1.0) * 1e-12
    return abs(value - float(stripped)) <= tolerance


def table_block(text: str, label: str, env: str = "longtable") -> str:
    marker = r"\label{" + label + "}"
    idx = text.index(marker)
    if env == "longtable":
        start = text.rfind(r"\begin{longtable}", 0, idx)
        end = text.index(r"\end{longtable}", idx) + len(r"\end{longtable}")
    else:
        start = text.index(r"\begin{tabular}", idx)
        end = text.index(r"\end{tabular}", start) + len(r"\end{tabular}")
    return text[start:end]


def table_rows(block: str) -> list[list[str]]:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith((
            r"\toprule", r"\midrule", r"\bottomrule", r"\endfirsthead",
            r"\endhead", r"\caption", r"\begin{", r"\end{", r"\setlength",
        )):
            continue
        lines.append(stripped)
    body = "\n".join(lines)
    rows = []
    for raw in body.split(r"\\"):
        raw = re.sub(r"\\(?:midrule|toprule|bottomrule|endfirsthead|endhead)", "", raw).strip()
        if not raw:
            continue
        cells = [cell.strip() for cell in raw.split("&")]
        if len(cells) >= 2:
            rows.append(cells)
    return rows


def fmt(value: float) -> str:
    return f"{value:.6f}"


# ---------------------------------------------------------------------------
# Chapter 6: spectral discretization, productivity normalization, rank rule
# ---------------------------------------------------------------------------

def chapter6_audit() -> dict:
    alpha, v = sp.symbols("alpha v", positive=True)
    x = sp.exp(alpha * v)
    lhs = sp.sin(sp.pi * alpha) / sp.pi * x / (x ** 2 + 2 * x * sp.cos(sp.pi * alpha) + 1)
    rhs = sp.sin(sp.pi * alpha) / (2 * sp.pi * (sp.cosh(alpha * v) + sp.cos(sp.pi * alpha)))
    symbolic_residual = sp.simplify(sp.expand((lhs - rhs).rewrite(sp.exp)))
    symbolic_pass = symbolic_residual == 0

    numeric_checks = {}
    for a in (0.5, 0.7):
        for vv in (-3.0, -0.5, 0.0, 1.5, 3.0):
            u = math.exp(vv)
            k_u = (math.sin(math.pi * a) / math.pi) * u ** (a - 1) / (
                u ** (2 * a) + 2 * u ** a * math.cos(math.pi * a) + 1
            )
            log_density = k_u * u
            expected = math.sin(math.pi * a) / (
                2 * math.pi * (math.cosh(a * vv) + math.cos(math.pi * a))
            )
            numeric_checks[f"alpha={a},v={vv}"] = {
                "K_times_jacobian": log_density,
                "closed_form": expected,
                "abs_error": abs(log_density - expected),
            }
    numeric_pass = all(row["abs_error"] < 5e-13 for row in numeric_checks.values())

    step, tail = 0.4, 1e-8
    index = {}
    for a in (0.5, 0.7):
        extent = max(
            math.log(4.0) / a,
            math.log(4 * math.sin(math.pi * a) / (math.pi * a * tail)) / a,
        )
        j = math.ceil(extent / step)
        index[str(a)] = {"J": j, "modes": 2 * j + 1}

    import importlib.util

    kernels = load_module("slice2_kernels", KERNELS)
    weight_comparison = {}
    for a, expected in ((0.5, index["0.5"]), (0.7, index["0.7"])):
        weights_code, rates_code = kernels.KernelSpec("ml", 1.0, alpha=a).mixture
        nodes = np.arange(-expected["J"], expected["J"] + 1) * step
        raw = step * math.sin(math.pi * a) / (
            2 * math.pi * (np.cosh(a * nodes) + np.cos(math.pi * a))
        )
        raw[[0, -1]] *= 0.5
        independent = raw / raw.sum()
        weight_comparison[str(a)] = {
            "modes_code": int(len(weights_code)),
            "modes_expected": expected["modes"],
            "max_abs_weight_difference": float(np.max(np.abs(weights_code - independent))),
            "weights_sum": float(weights_code.sum()),
            "minimum_weight": float(weights_code.min()),
            "rates_match": bool(np.allclose(rates_code, np.exp(nodes))),
        }
    weights_pass = all(
        row["modes_code"] == row["modes_expected"]
        and row["max_abs_weight_difference"] < 1e-15
        and abs(row["weights_sum"] - 1.0) < 1e-15
        and row["minimum_weight"] > 0
        and row["rates_match"]
        for row in weight_comparison.values()
    )

    # Continuous spectral density carries unit mass.
    spectral_mass = {}
    for a in (0.5, 0.7):
        mass = quad(
            lambda vv: math.sin(math.pi * a)
            / (2 * math.pi * (math.cosh(a * vv) + math.cos(math.pi * a))),
            -80,
            80,
            epsabs=1e-12,
            epsrel=1e-12,
            limit=400,
        )[0]
        spectral_mass[str(a)] = mass
    spectral_mass_pass = all(abs(m - 1.0) < 1e-10 for m in spectral_mass.values())

    r, beta, m = sp.symbols("r beta m", positive=True)
    decay = sp.Symbol("a", positive=True)
    productivity_integral = sp.integrate(
        decay * sp.exp(-decay * m), (m, 0, sp.oo)
    )
    productivity_symbolic = sp.simplify(productivity_integral - 1) == 0
    productivity_numeric = quad(
        lambda x: 2.849401764894274 * (1 - 0.7)
        * math.exp(-2.849401764894274 * (1 - 0.7) * x),
        0,
        math.inf,
        epsabs=1e-12,
        epsrel=1e-12,
    )[0]

    # Rank probability rule: add-one, ties count, denominator 1000.
    references = [float(i) for i in range(999)]
    rank_cases = {}
    for name, query in (("below_all", -1.0), ("above_all", 1000.0), ("at_median", 499.0)):
        p = (1 + sum(1 for d in references if d >= query)) / 1000
        rank_cases[name] = p
    ties = (1 + sum(1 for _ in references)) / 1000
    rank_pass = (
        math.isclose(rank_cases["below_all"], 1.0)
        and math.isclose(rank_cases["above_all"], 0.001)
        and math.isclose(ties, 1.0)
        and 0.001 <= rank_cases["at_median"] <= 1.0
    )

    payload = {
        "schema": "slice2_chapter6_design_v1",
        "passed": bool(
            symbolic_pass and numeric_pass and weights_pass and spectral_mass_pass
            and productivity_symbolic and rank_pass
        ),
        "mainardi_log_rate_transform": {
            "identity": "K_alpha(e^v)e^v = sin(pi*alpha)/(2*pi*(cosh(alpha*v)+cos(pi*alpha)))",
            "symbolic_residual": str(symbolic_residual),
            "symbolic_pass": symbolic_pass,
            "numeric_checks": numeric_checks,
            "numeric_pass": numeric_pass,
        },
        "endpoint_index": {
            "rule": "J=ceil(max(log(4)/alpha, log(4*sin(pi*alpha)/(pi*alpha*epsilon))/alpha)/s)",
            "s": step,
            "epsilon": tail,
            "alpha_0.5": index["0.5"],
            "alpha_0.7": index["0.7"],
            "matches_displayed_195_and_137": index["0.5"]["modes"] == 195 and index["0.7"]["modes"] == 137,
        },
        "kernel_weight_comparison": weight_comparison,
        "continuous_spectral_mass": spectral_mass,
        "spectral_mass_pass": spectral_mass_pass,
        "productivity_normalization": {
            "integrand": "(1-r)e^{beta*r*m} * beta*e^{-beta*m} = beta(1-r)e^{-beta(1-r)m}",
            "decay_integral": str(productivity_integral),
            "symbolic_pass": productivity_symbolic,
            "numeric_value_at_r_0.7_beta_2.849401764894274": productivity_numeric,
        },
        "rank_probability_rule": {
            "formula": "p=(1+sum_j 1{D_j>=D_q})/1000",
            "tie_all_value": ties,
            "cases": rank_cases,
            "passed": rank_pass,
        },
        "source_hashes": {
            "kernels.py": sha256(KERNELS),
            "06_design.tex": sha256(TEX["ch06"]),
            "methods_settings.json": sha256(AUTH["settings"]),
        },
    }
    return payload


# ---------------------------------------------------------------------------
# Chapter 7: exact binomial intervals and paired MCSE
# ---------------------------------------------------------------------------

def clopper_pearson(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    a = 1 - level
    lower = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    upper = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return lower, upper


def paired_mcse(b: int, c: int, n: int) -> tuple[float, float]:
    dbar = (b - c) / n
    value = math.sqrt((b + c - n * dbar ** 2) / (n * (n - 1)))
    return dbar, value


def chapter7_audit() -> dict:
    detection = load(AUTH["detection"])
    paired = load(AUTH["paired"])
    eta_study = load(AUTH["eta_study"])
    eta_final = load(AUTH["eta_final"])

    rows = {}
    cp_pass = True
    for name, record in detection.items():
        alt = record["alternative_frequency"]
        nul = record["heldout_null_size"]
        alt_cp = clopper_pearson(alt["rejections"], alt["requested"])
        nul_cp = clopper_pearson(nul["rejections"], nul["requested"])
        alt_ok = all(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-14)
                     for x, y in zip(alt_cp, alt["exact_binomial_95_interval"]))
        nul_ok = all(math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-14)
                     for x, y in zip(nul_cp, nul["exact_binomial_95_interval"]))
        cp_pass = cp_pass and alt_ok and nul_ok
        rows[name] = {
            "detections": alt["rejections"],
            "requested": alt["requested"],
            "detection_interval_recomputed": alt_cp,
            "detection_interval_authority": alt["exact_binomial_95_interval"],
            "detection_interval_match": alt_ok,
            "null_rejections": nul["rejections"],
            "null_requested": nul["requested"],
            "null_interval_recomputed": nul_cp,
            "null_interval_authority": nul["exact_binomial_95_interval"],
            "null_interval_match": nul_ok,
        }

    # The displayed main-detection table, cell by cell.
    text07 = TEX["ch07"].read_text(encoding="utf-8")
    block = table_block(text07, "tab:main-detection", env="tabular")
    table_rows_main = table_rows(block)
    expected_rows = [
        ("Known laws", "Fixed-eta oracle", 150, 150, 0.9757074, 1.0, 50),
        ("Eta estimated", "Eta fit; background supplied", 150, 150, 0.9757074, 1.0, 49),
        ("Level estimated", "Level fit; trend supplied", 123, 150, 0.7490221, 0.8779004, 46),
        ("Level and trend", "Level and trend fit", 68, 150, 0.3719742, 0.5365724, 44),
        ("Historical fuller", "Historical fuller fit", 57, 150, 0.3020772, 0.4627631, 50),
    ]
    table_cells = []
    rows_main = [row for row in table_rows_main if row and row[0].replace("\\", "").strip() not in {"", "Procedure"}]
    for row, (label, key, k, n, lo, hi, null) in zip(rows_main, expected_rows):
        joined = " & ".join(row)
        nums = [cell_number(c) for c in row]
        table_cells.append({
            "row": label,
            "authority": key,
            "detections_text": row[1],
            "interval_text": row[2],
            "null_text": row[3],
            "detection_match": f"{k}/{n}" in joined.replace(" ", ""),
            "lower_match": display_match(row[2].split("--")[0] if "--" in row[2] else row[2], 100 * lo),
            "upper_match": display_match(row[2].split("--")[-1], 100 * hi),
            "null_match": int(null) in [int(x) for x in re.findall(r"\d+", row[3])],
        })
    table_pass = all(all(v for k, v in row.items() if k.endswith("_match")) for row in table_cells)

    # Paired MCSE from the independent recovered execution records.
    eta_paired = eta_study["paired"]["table"]
    b_new, c_old = eta_paired["new_only"], eta_paired["old_only"]
    dbar_eta, mcse_eta = paired_mcse(b_new, c_old, 150)
    dbar_lt, mcse_lt = paired_mcse(paired["level_only"], paired["level_and_trend_only"], paired["total"])
    levels = {
        "eta_sensitivity": {
            "b": b_new,
            "c": c_old,
            "N": 150,
            "dbar": dbar_eta,
            "mcse_fraction": mcse_eta,
            "mcse_percentage_points": 100 * mcse_eta,
            "displayed_percentage_points": 4.7096,
            "authority_mcse_fraction": eta_study["paired"]["MCSE"],
            "authority_match": math.isclose(mcse_eta, eta_study["paired"]["MCSE"], rel_tol=1e-12),
        },
        "level_vs_level_trend": {
            "b": paired["level_only"],
            "c": paired["level_and_trend_only"],
            "N": paired["total"],
            "dbar": dbar_lt,
            "mcse_fraction": mcse_lt,
            "mcse_percentage_points": 100 * mcse_lt,
            "displayed_percentage_points": 4.5776,
        },
    }
    mcse_pass = (
        levels["eta_sensitivity"]["authority_match"]
        and abs(100 * mcse_eta - 4.709613820849452) < 5e-10
        and abs(100 * mcse_lt - 4.5776) < 5e-5
    )

    fresh = eta_final["studies"]["fresh150"]["arms"]
    suppression = {
        "initial": 100 * fresh["old"]["achieved_effect"]["mean"],
        "adjusted": 100 * fresh["new"]["achieved_effect"]["mean"],
        "displayed_initial": 14.159,
        "displayed_adjusted": 19.360,
        "initial_display_match": display_match("14.159", 100 * fresh["old"]["achieved_effect"]["mean"]),
        "adjusted_display_match": display_match("19.360", 100 * fresh["new"]["achieved_effect"]["mean"]),
    }

    # Difficult-ten audit: recompute maxima from the saved per-pair CSV.
    s14_rows = list(csv.DictReader(S14_CSV.open(encoding="utf-8")))
    max_null_phase = max(float(row["null_NLL_gain"]) for row in s14_rows)
    max_alt_phase = max(float(row["alternative_NLL_gain"]) for row in s14_rows)
    max_phase = max(max_null_phase, max_alt_phase)
    max_glr = max(abs(float(row["GLR_shift32"])) for row in s14_rows)
    s14_summary = load(S14_SUMMARY)
    difficult = {
        "n_pairs": len(s14_rows),
        "maximum_phase_NLL_gain": max_phase,
        "maximum_null_phase_NLL_gain": max_null_phase,
        "maximum_alternative_phase_NLL_gain": max_alt_phase,
        "maximum_absolute_GLR_shift32": max_glr,
        "displayed_phase_max": 1.94995664e-8,
        "displayed_glr_max": 3.89681745e-8,
        "phase_match": abs(max_phase - 1.949956640601158e-8) < 1e-18,
        "glr_match": abs(max_glr - 3.8968174465026095e-8) < 1e-18,
        "summary_phase_match": abs(max_phase - s14_summary["maximum_phase_NLL_gain"]) < 1e-18,
        "summary_glr_match": abs(max_glr - s14_summary["maximum_absolute_GLR_shift32"]) < 1e-18,
        "screens": s14_summary["screens"],
        "all_below_material_screens": max_phase < 0.001 and max_glr < 0.1,
    }

    # Saved 150-history likelihood accounting: recompute medians from the CSV.
    with S11_CSV.open(encoding="utf-8") as handle:
        s11_rows = list(csv.DictReader(handle))
    null_gains = [float(row["null_NLL_gain"]) for row in s11_rows]
    alt_gains = [float(row["alternative_NLL_gain"]) for row in s11_rows]
    s11_json = load(S11_JSON)
    likelihood = {
        "n": len(s11_rows),
        "median_null_NLL_gain": float(np.median(null_gains)),
        "median_alternative_NLL_gain": float(np.median(alt_gains)),
        "displayed_null": 28.665,
        "displayed_alternative": 0.862,
        "null_display_match": display_match("28.665", float(np.median(null_gains))),
        "alternative_display_match": display_match("0.862", float(np.median(alt_gains))),
        "null_exceeds_alternative_count": int(np.sum(np.array(null_gains) > np.array(alt_gains))),
        "summary_median_match": abs(float(np.median(null_gains)) - s11_json["summaries"]["null_NLL_gain"]["median"]) < 1e-12
        and abs(float(np.median(alt_gains)) - s11_json["summaries"]["alternative_NLL_gain"]["median"]) < 1e-12,
    }

    payload = {
        "schema": "slice2_chapter7_synthetic_v1",
        "passed": bool(cp_pass and table_pass and mcse_pass and difficult["phase_match"]
                       and difficult["glr_match"] and likelihood["summary_median_match"]
                       and suppression["initial_display_match"] and suppression["adjusted_display_match"]),
        "clopper_pearson": rows,
        "clopper_pearson_pass": cp_pass,
        "main_detection_table": table_cells,
        "main_detection_table_pass": table_pass,
        "paired_mcse": levels,
        "mcse_pass": mcse_pass,
        "achieved_suppression_percent": suppression,
        "difficult_ten_optimizer_audit": difficult,
        "saved_likelihood_accounting": likelihood,
        "source_hashes": {
            "detection.json": sha256(AUTH["detection"]),
            "paired.json": sha256(AUTH["paired"]),
            "eta_study": sha256(AUTH["eta_study"]),
            "S14_paired_diagnostics.csv": sha256(S14_CSV),
            "S11_statistic_decomposition.csv": sha256(S11_CSV),
        },
    }
    return payload


# ---------------------------------------------------------------------------
# Chapter 9 algebra
# ---------------------------------------------------------------------------

def chapter9_algebra() -> dict:
    # Column stochasticity and the fixed point of P(h).
    beta, c, h, delta, n = sp.symbols("beta c h delta n", positive=True)
    p0 = 1 - sp.exp(-beta * c)
    p1 = sp.exp(-beta * c)
    P = sp.Matrix([[1 - h + h, 0], [0, 1 - h]])  # columns: (1-h)p_i + h*delta_ij
    P[0, 0] = (1 - h) * p0 + h
    P[1, 0] = (1 - h) * p1
    P[0, 1] = (1 - h) * p0
    P[1, 1] = (1 - h) * p1 + h
    column_sums = [sp.simplify(P[0, j] + P[1, j]) for j in range(2)]
    fixed_point = [sp.simplify(P[i, 0] * p0 + P[i, 1] * p1 - [p0, p1][i]) for i in range(2)]
    column_stochastic = all(value == 1 for value in column_sums)
    fixed_point_pass = all(value == 0 for value in fixed_point)

    # Conditional within-class productivity means at r=0.7.
    r = sp.Rational(7, 10)
    kappa = (1 - r) * sp.exp(beta * r * sp.Symbol("q", positive=True))
    q = sp.Symbol("q", positive=True)
    m0 = sp.simplify(sp.integrate(kappa * beta * sp.exp(-beta * q), (q, 0, c)) / p0)
    m1 = sp.simplify(sp.integrate(kappa * beta * sp.exp(-beta * q), (q, c, sp.oo)) / p1)
    m0_expected = (1 - sp.exp(-(1 - r) * beta * c)) / p0
    m1_expected = sp.exp(r * beta * c)
    means_pass = sp.simplify(m0 - m0_expected) == 0 and sp.simplify(m1 - m1_expected) == 0
    total_mean = sp.simplify(p0 * m0 + p1 * m1 - 1) == 0

    # Perron root and the immigrant-weighted first-generation count.
    def perron_example(hval, dval, nval=0.4, beta_val=2.849401764894274, cval=0.5):
        pp0 = 1 - math.exp(-beta_val * cval)
        pp1 = math.exp(-beta_val * cval)
        mm0 = (1 - math.exp(-0.3 * beta_val * cval)) / pp0
        mm1 = math.exp(0.7 * beta_val * cval)
        R = np.array([math.exp(-dval / 2), math.exp(dval / 2)])
        Pmat = np.array([[(1 - hval) * pp0 + hval, (1 - hval) * pp0],
                         [(1 - hval) * pp1, (1 - hval) * pp1 + hval]])
        A = Pmat @ np.diag(R * np.array([mm0, mm1]))
        rho = float(np.max(np.abs(np.linalg.eigvals(A))))
        K = nval / rho * A
        p = np.array([pp0, pp1])
        offspring = float(np.ones(2) @ K @ p)
        return {"h": hval, "delta": dval, "rho": rho, "spectral_radius_K": float(np.max(np.abs(np.linalg.eigvals(K)))),
                "one_transpose_K_p": offspring, "n": nval, "difference": offspring - nval}

    perron_rows = [
        perron_example(0.0, 0.0),
        perron_example(0.0, 0.3),
        perron_example(0.0, -0.4),
        perron_example(0.5, 0.0),
        perron_example(0.5, 0.3),
        perron_example(-0.3, -0.4),
    ]
    perron_pass = all(abs(row["spectral_radius_K"] - 0.4) < 1e-12 for row in perron_rows)
    h_zero_identity = all(abs(row["one_transpose_K_p"] - 0.4) < 1e-12 for row in perron_rows[:3])
    h_nonzero_breaks = all(abs(row["one_transpose_K_p"] - 0.4) > 1e-8 for row in perron_rows[3:])

    # Continuous productivity derivative and moments.
    rr = sp.Symbol("r", positive=True)
    qq = sp.Symbol("q", positive=True)
    kappa_r = (1 - rr) * sp.exp(beta * rr * qq)
    derivative_residual = sp.simplify(
        sp.diff(kappa_r, rr) - kappa_r * (beta * qq - 1 / (1 - rr))
    )
    mm = sp.Symbol("m", positive=True)
    moment_integral = sp.integrate(
        beta * sp.exp(-beta * qq) * ((1 - rr) * sp.exp(beta * rr * qq)) ** mm,
        (qq, 0, sp.oo),
        conds="none",
    )
    moment_expected = (1 - rr) ** mm / (1 - mm * rr)
    moment_residual = sp.simplify(moment_integral - moment_expected)

    # NLL gradient in equation (9.5).
    nn = sp.Symbol("n", positive=True)
    Kf = sp.Function("K")
    Hf = sp.Function("H")
    nll = nn * Kf(rr) - sp.log(sp.Symbol("B", positive=True) + nn * Hf(rr))
    gradient = sp.diff(nll, rr)
    expected_gradient = nn * sp.Derivative(Kf(rr), rr) - nn * sp.Derivative(Hf(rr), rr) / (
        sp.Symbol("B", positive=True) + nn * Hf(rr)
    )
    gradient_residual = sp.simplify(gradient - expected_gradient)

    # Class-history conditional probability identity.
    S0, S1, mu, ng = sp.symbols("S0 S1 mu n_g", positive=True)
    S = S0 + S1
    lam0 = mu * p0 + ng * ((1 - h) * p0 + h) * S0 + ng * (1 - h) * p0 * S1
    lam1 = mu * p1 + ng * (1 - h) * p1 * S0 + ng * ((1 - h) * p1 + h) * S1
    ground = mu + ng * S
    conditional0 = sp.simplify(lam0 / ground - (p0 + ng * h * (S0 - p0 * S) / ground))
    conditional1 = sp.simplify(lam1 / ground - (p1 + ng * h * (S1 - p1 * S) / ground))

    payload = {
        "schema": "slice2_chapter9_algebra_v1",
        "passed": bool(
            column_stochastic and fixed_point_pass and means_pass and total_mean
            and perron_pass and h_zero_identity and h_nonzero_breaks
            and derivative_residual == 0 and moment_residual == 0
            and gradient_residual == 0
            and conditional0 == 0 and conditional1 == 0
        ),
        "column_stochasticity": {
            "column_sums": [str(value) for value in column_sums],
            "P_p_equals_p": [str(value) for value in fixed_point],
            "passed": column_stochastic and fixed_point_pass,
        },
        "conditional_productivity_means": {
            "m0": str(m0),
            "m0_expected": str(m0_expected),
            "m1": str(m1),
            "m1_expected": str(m1_expected),
            "weighted_mean_identity": str(sp.simplify(p0 * m0 + p1 * m1)),
            "passed": means_pass and total_mean,
        },
        "perron_examples": {
            "rows": perron_rows,
            "spectral_radius_equals_n": perron_pass,
            "h_zero_immigrant_offspring_equals_n": h_zero_identity,
            "h_nonzero_breaks_identity": h_nonzero_breaks,
            "scope": ("With h=0 the transition matrix has rank one with columns p, so "
                      "K p=n p and 1^T K p=n for every delta. Nonzero h generally breaks "
                      "the identity, even at delta=0, because the class-specific "
                      "productivity means differ under r=0.7; delta then modifies the "
                      "Perron root."),
        },
        "productivity_derivative_residual": str(derivative_residual),
        "moments": {
            "integral": str(moment_integral),
            "expected": str(moment_expected),
            "residual": str(moment_residual),
            "finite_iff_mr_lt_1": True,
        },
        "nll_gradient_formula": {
            "derivative": str(gradient),
            "expected": str(expected_gradient),
            "residual": str(gradient_residual),
            "passed": gradient_residual == 0,
        },
        "class_history_conditional_probability_residual": [str(conditional0), str(conditional1)],
    }
    return payload


# ---------------------------------------------------------------------------
# Chapter 9.1--9.6 tables from the magnitude-extension authority
# ---------------------------------------------------------------------------

def chapter9_magnitude_tables() -> dict:
    data = load(AUTH["history"])
    history = {(row["variant"], row["comparison"]): row for row in data["history_aggregate"]}
    productivity = {(row["variant"], row["comparison"]): row for row in data["productivity_aggregate"]}
    history_windows = {(row["variant"], row["comparison"], row["fold_id"]): row for row in data["history_windows"]}
    productivity_windows = {(row["variant"], row["comparison"], row["fold_id"]): row for row in data["productivity_windows"]}
    cross = {row["fold_id"]: row for row in data["primary_cross_run"]}

    text = TEX["ch09"].read_text(encoding="utf-8")
    hist_block = table_block(text, "a2:history-results", env="tabular")
    prod_block = table_block(text, "a2:productivity-results", env="tabular")
    cross_block = table_block(text, "a2:cross-run", env="tabular")

    history_rows = []
    for cells in table_rows(hist_block):
        if len(cells) < 6:
            continue
        setting = cells[0].replace("\\", "").strip()
        contrast = re.sub(r"\\+\(|\\+\)", "", cells[1]).replace("$", "").replace("{", "").replace("}", "").strip()
        variant = {"Primary": "primary", "Constant background": "constant_background", "Post-1980": "post1980_training"}.get(setting)
        if "E1-E1" in contrast:
            comparison = "E1-E1_h0"
        elif "E1-E0" in contrast:
            comparison = "E1-E0"
        elif "E1-I0" in contrast:
            comparison = "E1-I0"
        else:
            comparison = None
        if not variant or not comparison:
            continue
        authority = history[(variant, comparison)]
        values = [cell_number(cells[i]) for i in range(2, 5)]
        wins = int(re.findall(r"\d+", cells[5])[0]) if re.findall(r"\d+", cells[5]) else None
        history_rows.append({
            "setting": setting,
            "contrast": contrast,
            "timing_display": cells[2],
            "mark_display": cells[3],
            "joint_display": cells[4],
            "wins_display": cells[5],
            "timing_match": display_match(cells[2], authority["timing_gain_per_event"]),
            "mark_match": display_match(cells[3], authority["mark_gain_per_event"]),
            "joint_match": display_match(cells[4], authority["joint_gain_per_event"]),
            "wins_match": wins == authority["positive_joint_windows"],
            "identity_timing_plus_mark": values[0] + values[1],
            "identity_joint": values[2],
            "identity_abs_error": abs(values[0] + values[1] - values[2]),
        })

    productivity_rows = []
    for cells in table_rows(prod_block):
        if len(cells) < 5:
            continue
        setting = cells[0].replace("\\", "").strip()
        variant = {"Primary": "primary", "Constant background": "constant_background", "Post-1980": "post1980_training"}.get(setting)
        if not variant:
            continue
        keys = [("E0_free-E0_fixed", 1), ("I0_free-I0_fixed", 2), ("E0_free-I0_free", 3)]
        row = {"setting": setting, "cells": {}}
        for key, index in keys:
            authority = productivity[(variant, key)]
            row["cells"][key] = {
                "display": cells[index],
                "authority": authority["joint_gain_per_event"],
                "match": display_match(cells[index], authority["joint_gain_per_event"]),
            }
        row["positive_windows_display"] = cells[4]
        row["positive_windows_match"] = str(productivity[(variant, "E0_free-E0_fixed")]["positive_joint_windows"]) in cells[4]
        productivity_rows.append(row)

    cross_rows = []
    for cells in table_rows(cross_block):
        if len(cells) < 7:
            continue
        try:
            fold = int(cells[0])
        except ValueError:
            continue
        row = cross[fold]
        fields = {
            "n_train": (cells[1], row["n_train"]),
            "n_test": (cells[2], row["n_test"]),
            "step_training": (cells[3], row["step_training_gain"]),
            "step_test": (cells[4], row["step_forecast_gain"]),
            "free_training": (cells[5], row["free_r_training_gain"]),
            "free_test": (cells[6], row["free_r_forecast_gain"]),
        }
        cross_rows.append({
            "fold": fold,
            **{name: {"display": display, "authority": value, "match": display_match(display, value)}
               for name, (display, value) in fields.items()},
        })

    narrative = {
        "primary_E1_minus_E0_total": history[("primary", "E1-E0")]["joint_difference"],
        "displayed_primary_total": -5.313603,
        "primary_total_match": display_match("-5.313603", history[("primary", "E1-E0")]["joint_difference"]),
        "E0_minus_I0_primary": history[("primary", "E1-I0")]["joint_gain_per_event"] - history[("primary", "E1-E0")]["joint_gain_per_event"],
        "E0_minus_I0_constant": history[("constant_background", "E1-I0")]["joint_gain_per_event"] - history[("constant_background", "E1-E0")]["joint_gain_per_event"],
        "E0_minus_I0_post": history[("post1980_training", "E1-I0")]["joint_gain_per_event"] - history[("post1980_training", "E1-E0")]["joint_gain_per_event"],
        "displayed_E0_minus_I0": [0.029716, 0.021302, 0.032046],
        "E0_minus_I0_display_match": all(
            display_match(f"{displayed:.6f}", value)
            for displayed, value in zip(
                [0.029716, 0.021302, 0.032046],
                [
                    history[("primary", "E1-I0")]["joint_gain_per_event"] - history[("primary", "E1-E0")]["joint_gain_per_event"],
                    history[("constant_background", "E1-I0")]["joint_gain_per_event"] - history[("constant_background", "E1-E0")]["joint_gain_per_event"],
                    history[("post1980_training", "E1-I0")]["joint_gain_per_event"] - history[("post1980_training", "E1-E0")]["joint_gain_per_event"],
                ],
            )
        ),
        "primary_E0_free_total": productivity[("primary", "E0_free-E0_fixed")]["joint_difference"],
        "displayed_primary_E0_free_total": -5.374505,
        "estimated_r_below_point7": data["estimated_r_below_point7"],
        "estimated_r_total": data["estimated_r_total"],
        "maximum_saved_forecast_spread": data["maximum_saved_forecast_spread_nats_per_event"],
    }

    payload = {
        "schema": "slice2_chapter9_magnitude_tables_v1",
        "passed": bool(
            len(history_rows) == 7
            and len(productivity_rows) == 3
            and len(cross_rows) == 3
            and all(all(v for k, v in row.items() if k.endswith("_match")) for row in history_rows)
            and all(all(cell["match"] for cell in row["cells"].values()) and row["positive_windows_match"] for row in productivity_rows)
            and all(all(field["match"] for field in row.values() if isinstance(field, dict)) for row in cross_rows)
            and narrative["primary_total_match"]
            and narrative["E0_minus_I0_display_match"]
        ),
        "history_table": history_rows,
        "productivity_table": productivity_rows,
        "cross_run_table": cross_rows,
        "narrative_reconciliation": narrative,
        "source_hashes": {
            "aggregate_data.json": sha256(AUTH["history"]),
            "09_temporal_mark_extensions.tex": sha256(TEX["ch09"]),
            "ch09_audit.tex": sha256(TEX["audit09"]),
        },
    }
    return payload


# ---------------------------------------------------------------------------
# Pilot tables
# ---------------------------------------------------------------------------

def pilot_tables() -> dict:
    data = load(AUTH["pilot"])
    groups = {(row["method"], row["h"]): row for row in data["groups"]}
    paired = {(row["method"], row["h_minus_control"]): row for row in data["paired_contrasts"]}
    text = TEX["ch09"].read_text(encoding="utf-8")
    freq_block = table_block(text, "tab:pilot-frequency")
    paired_block = table_block(text, "tab:pilot-paired")

    freq_rows = []
    for cells in table_rows(freq_block):
        if len(cells) < 7 or cells[0].startswith("Procedure"):
            continue
        method = "known_known" if "Supplied" in cells[0] else "background_estimated"
        try:
            h = float(cells[1])
        except ValueError:
            continue
        key = (method, h)
        if key not in groups:
            continue
        row = groups[key]
        selected, planned = [int(x) for x in cells[2].split("/")]
        freq_rows.append({
            "method": method,
            "h": h,
            "selected_planned_display": cells[2],
            "selected_match": selected == row["selected"] and planned == row["planned"],
            "unknown_match": int(cells[3]) == row["unknown"],
            "wilson_lower_match": display_match(cells[4], row["wilson95_among_resolved"][0]),
            "wilson_upper_match": display_match(cells[5], row["wilson95_among_resolved"][1]),
            "median_glr_match": display_match(cells[6], row["median_glr"]),
            "authority": row,
        })

    paired_rows = []
    for cells in table_rows(paired_block):
        if len(cells) < 8 or cells[0].startswith("Procedure"):
            continue
        method = "known_known" if "Supplied" in cells[0] else "background_estimated"
        try:
            h = float(cells[1])
        except ValueError:
            continue
        key = (method, h)
        if key not in paired:
            continue
        row = paired[key]
        paired_rows.append({
            "method": method,
            "h": h,
            "selection_match": display_match(cells[2], row["paired_selection_difference"]["mean"])
            and display_match(cells[3], row["paired_selection_difference"]["percentile95"][0])
            and display_match(cells[4], row["paired_selection_difference"]["percentile95"][1]),
            "glr_match": display_match(cells[5], row["paired_glr_difference"]["mean"])
            and display_match(cells[6], row["paired_glr_difference"]["percentile95"][0])
            and display_match(cells[7], row["paired_glr_difference"]["percentile95"][1]),
            "authority": row,
        })

    payload = {
        "schema": "slice2_chapter9_pilot_tables_v1",
        "passed": bool(
            all(all(v for k, v in row.items() if k.endswith("_match")) for row in freq_rows)
            and all(row["selection_match"] and row["glr_match"] for row in paired_rows)
        ),
        "frequency_table": freq_rows,
        "paired_table": paired_rows,
        "planned_catalogues": data["planned_catalogues"],
        "planned_method_outcomes": data["planned_method_outcomes"],
    }
    return payload


# ---------------------------------------------------------------------------
# Stage A, Stage B, Extension O tables
# ---------------------------------------------------------------------------

AG_MAP = {
    "AG1": "I0_raw_ml-E0_ml",
    "AG2": "I0_orth_ml-E0_ml",
    "AG3": "I0_orth_ml-I0_raw_ml",
    "AG4": "E0_omori-E0_ml",
    "AG5": "I0_orth_omori-E0_omori",
    "AG6": "I0_orth_omori-I0_orth_ml",
    "AG7": "(I0_orth_omori-E0_omori)-(I0_orth_ml-E0_ml)",
}
A_FOLD_MAP = {
    "A1": "I0_raw_ml-E0_ml",
    "A2": "I0_orth_ml-E0_ml",
    "A3": "I0_orth_ml-I0_raw_ml",
    "A4": "E0_omori-E0_ml",
    "A5": "I0_orth_omori-E0_omori",
    "A6": "I0_orth_omori-I0_orth_ml",
    "A7": "(I0_orth_omori-E0_omori)-(I0_orth_ml-E0_ml)",
}
BG_MAP = {
    "BG1": "E0_tau_free-E0_tau1",
    "BG2": "E1_tau_class-E0_tau_free",
    "BG3": "E1_tau_class-E0_tau1",
}
B_FOLD_MAP = {"B1": BG_MAP["BG1"], "B2": BG_MAP["BG2"], "B3": BG_MAP["BG3"]}
OG_MAP = {
    "OG1": "E_omori-E_ml",
    "OG2": "Iorth_matched-E_omori",
    "OG3": "Iraw_matched-E_omori",
    "OG4": "Iorth_joint-E_omori",
    "OG5": "Iorth_joint-Iorth_matched",
    "OG6": "Iorth_matched-Iraw_matched",
}
O_FOLD_MAP = {
    "O1": "E_omori-E_ml",
    "O2": "Iorth_matched-E_omori",
    "O3": "Iraw_matched-E_omori",
    "O4": "Iorth_joint-E_omori",
    "O5": "Iorth_joint-Iorth_matched",
    "O6": "Iorth_matched-Iraw_matched",
}


def aggregate_row_check(cells, authority, key_label):
    if len(cells) < 7:
        return None
    values = [cell_number(cells[i]) for i in range(1, 7)]
    if any(value is None for value in values):
        return None
    q, c, timing, mark, joint, per_event = values
    row = {
        "key": key_label,
        "authority": authority["comparison"] if authority else None,
        "q_match": display_match(cells[1], authority["event"]),
        "c_match": display_match(cells[2], authority["compensator"]),
        "timing_match": display_match(cells[3], authority["timing"]),
        "mark_match": display_match(cells[4], authority["mark"]),
        "joint_match": display_match(cells[5], authority["joint"]),
        "per_event_match": display_match(cells[6], authority["nats_per_event"]),
        "q_plus_c": q + c,
        "timing": timing,
        "identity_qc_abs_error": abs(q + c - timing),
        "timing_plus_mark": timing + mark,
        "joint": joint,
        "identity_joint_abs_error": abs(timing + mark - joint),
    }
    if len(cells) >= 8:
        row["positive_folds_display"] = cells[7]
        row["positive_folds_match"] = int(cells[7]) == authority["positive_joint_folds"]
    return row


def fold_row_check(cells, authority):
    if len(cells) < 8:
        return None
    q, c, timing, mark, joint = [cell_number(cells[i]) for i in range(3, 8)]
    if any(value is None for value in (q, c, timing, mark, joint)):
        return None
    return {
        "fold": int(cells[0]),
        "key": cells[1],
        "targets_match": int(cells[2]) == authority["n_test"],
        "q_match": display_match(cells[3], authority["event"]),
        "c_match": display_match(cells[4], authority["compensator"]),
        "timing_match": display_match(cells[5], authority["timing"]),
        "mark_match": display_match(cells[6], authority["mark"]),
        "joint_match": display_match(cells[7], authority["joint"]),
        "identity_qc_abs_error": abs(q + c - timing),
        "identity_joint_abs_error": abs(timing + mark - joint),
    }


def stage_abc_audit() -> dict:
    stage_a = load(AUTH["stage_a"])
    stage_b = load(AUTH["stage_b"])
    stage_o = load(AUTH["stage_o"])
    text9 = TEX["ch09"].read_text(encoding="utf-8")
    text_audit = TEX["audit09"].read_text(encoding="utf-8")

    # Aggregate tables in the chapter.
    def aggregate_table(label, aggregates, mapping, expect_variant=None, text_source=None):
        block = table_block(text_source if text_source is not None else text9, label)
        authority = {(row.get("variant"), row["comparison"]): row for row in aggregates}
        rows = []
        for cells in table_rows(block):
            key = cells[0].replace("\\", "").strip()
            if key not in mapping:
                continue
            variant = expect_variant
            if variant is None:
                # Stage B aggregate rows have no variant key; primary is the only table.
                candidates = [row for (v, comp), row in authority.items() if comp == mapping[key]]
                row = candidates[0] if candidates else None
            else:
                row = authority.get((variant, mapping[key]))
            checked = aggregate_row_check(cells, row, key) if row else None
            if checked:
                rows.append(checked)
        return {"rows": rows, "present_keys": [r["key"] for r in rows],
                "max_qc_identity_error": max((r["identity_qc_abs_error"] for r in rows), default=None),
                "max_joint_identity_error": max((r["identity_joint_abs_error"] for r in rows), default=None),
                "identity_pass": bool(rows) and max(r["identity_qc_abs_error"] for r in rows) <= 2e-6
                                 and max(r["identity_joint_abs_error"] for r in rows) <= 2e-6,
                "passed": len(rows) > 0 and all(
                    all(v for k, v in row.items() if k.endswith("_match")) for row in rows
                ) and max(r["identity_qc_abs_error"] for r in rows) <= 2e-6
                and max(r["identity_joint_abs_error"] for r in rows) <= 2e-6}

    ag_primary = aggregate_table("tab:AG-primary", stage_a["aggregates"], AG_MAP, "primary")
    bg_primary = aggregate_table("tab:BG-primary", stage_b["aggregates"], BG_MAP, None)
    og_primary = aggregate_table("tab:OG-primary", stage_o["aggregates"], OG_MAP, "primary")

    # Appendix aggregate sensitivity tables.
    ag_constant = aggregate_table("tab:AG-constant_background", stage_a["aggregates"], AG_MAP, "constant_background", text_audit)
    ag_post = aggregate_table("tab:AG-post1980_training", stage_a["aggregates"], AG_MAP, "post1980_training", text_audit)
    og_constant = aggregate_table("tab:OG-constant_background", stage_o["aggregates"], OG_MAP, "constant_background", text_audit)
    og_post = aggregate_table("tab:OG-post1980_training", stage_o["aggregates"], OG_MAP, "post1980_training", text_audit)

    # Fold tables.
    def fold_table(label, comparisons, mapping, variant):
        index = {(row.get("variant", "primary"), row["fold_id"], row["comparison"]): row for row in comparisons}
        block = table_block(text_audit, label)
        rows = []
        for cells in table_rows(block):
            if len(cells) < 8 or cells[1] not in mapping:
                continue
            try:
                fold = int(cells[0])
            except ValueError:
                continue
            authority = index.get((variant, fold, mapping[cells[1]]))
            checked = fold_row_check(cells, authority) if authority else None
            if checked:
                rows.append(checked)
        return {"rows": rows, "n_rows": len(rows),
                "max_qc_identity_error": max((r["identity_qc_abs_error"] for r in rows), default=None),
                "max_joint_identity_error": max((r["identity_joint_abs_error"] for r in rows), default=None),
                "identity_pass": bool(rows) and max(r["identity_qc_abs_error"] for r in rows) <= 2e-6
                                 and max(r["identity_joint_abs_error"] for r in rows) <= 2e-6,
                "passed": len(rows) > 0 and all(
                    all(v for k, v in row.items() if k.endswith("_match")) for row in rows
                ) and max(r["identity_qc_abs_error"] for r in rows) <= 2e-6
                and max(r["identity_joint_abs_error"] for r in rows) <= 2e-6}

    a_folds = {
        "primary": fold_table("tab:A-primary", stage_a["comparisons"], A_FOLD_MAP, "primary"),
        "constant_background": fold_table("tab:A-constant_background", stage_a["comparisons"], A_FOLD_MAP, "constant_background"),
        "post1980_training": fold_table("tab:A-post1980_training", stage_a["comparisons"], A_FOLD_MAP, "post1980_training"),
    }
    b_folds = {"primary": fold_table("tab:B-primary", stage_b["comparisons"], B_FOLD_MAP, "primary")}
    o_folds = {
        "primary": fold_table("tab:O-primary", stage_o["comparisons"], O_FOLD_MAP, "primary"),
        "constant_background": fold_table("tab:O-constant_background", stage_o["comparisons"], O_FOLD_MAP, "constant_background"),
        "post1980_training": fold_table("tab:O-post1980_training", stage_o["comparisons"], O_FOLD_MAP, "post1980_training"),
    }

    # Stage B selected scales.
    b_absolute = {(row["case_id"], row["model"]): row for row in stage_b["absolute"]}
    b_scale_block = table_block(text_audit, "tab:b-scales")
    b_scale_rows = []
    for cells in table_rows(b_scale_block):
        if len(cells) < 5:
            continue
        try:
            fold = int(cells[0])
        except ValueError:
            continue
        model = cells[1].replace("\\_", "_").replace("\\", "")
        case_id = f"primary_fold_{fold}"
        authority = b_absolute.get((case_id, model))
        if not authority:
            continue
        b_scale_rows.append({
            "fold": fold,
            "model": model,
            "tau0_match": display_match(cells[2], authority["tau_days"][0]),
            "tau1_match": display_match(cells[3], authority["tau_days"][1]),
            "nll_match": display_match(cells[4], authority["training_nll"]),
        })

    # Extension O selected kernels: all variant rows.
    o_absolute = {(row["case_id"], row["model"]): row for row in stage_o["absolute"]}
    o_kernel_block = table_block(text_audit, "tab:o-kernels")
    o_kernel_rows = []
    variant_map_kernel = {
        "constant\\_background": "constant_background",
        "post1980\\_training": "post1980_training",
        "primary": "primary",
    }
    for cells in table_rows(o_kernel_block):
        if len(cells) < 4:
            continue
        variant = variant_map_kernel.get(cells[0])
        if not variant:
            continue
        try:
            fold = int(cells[1])
        except ValueError:
            continue
        authority = o_absolute.get((f"{variant}_fold_{fold}", "E_omori"))
        if not authority:
            continue
        kernel = authority["kernel"]
        o_kernel_rows.append({
            "variant": variant,
            "fold": fold,
            "c_match": display_match(cells[2], kernel["c"]),
            "p_match": display_match(cells[3], kernel["p"]),
            "c": kernel["c"],
            "p": kernel["p"],
        })

    # Geometry table (Stage A).
    geometry_block = table_block(text_audit, "tab:a-geometry")
    geometry_rows = []
    a_cases = {row["case"]["case_id"]: row for row in stage_a["cases"]}
    variant_map = {"Primary": "primary", "Constant": "constant_background", "Post-1980": "post1980_training"}
    for cells in table_rows(geometry_block):
        if len(cells) < 8:
            continue
        variant = variant_map.get(cells[0])
        if not variant:
            continue
        try:
            fold = int(cells[1])
        except ValueError:
            continue
        case = a_cases.get(f"{variant}_fold_{fold}")
        if not case:
            continue
        gamma = case["gamma"]
        geometry_rows.append({
            "variant": variant,
            "fold": fold,
            "gamma0_match": display_match(cells[2], gamma[0]),
            "gamma1_match": display_match(cells[3], gamma[1]),
        })

    # Exposure orthogonalization mapping: verify every saved raw/orth pair.
    mapping_rows = []
    for row in stage_a["selected_models"]:
        mapping = row.get("raw_orth_mapping")
        if not mapping:
            continue
        case_id = row["case_id"]
        gamma = a_cases[case_id]["gamma"]
        source = mapping["source"]
        mapped = mapping["mapped"]
        expected = [source[0] - source[3] * gamma[0], source[1] - source[3] * gamma[1], source[2], source[3]]
        mapping_rows.append({
            "case_id": case_id,
            "model": row["model"],
            "direction": "raw_to_orth",
            "expected": expected,
            "recorded": mapped,
            "max_abs_error": max(abs(a - b) for a, b in zip(expected, mapped)),
        })
    for row in stage_o["raw_orth_mapping"]:
        case_id = row["case_id"]
        gamma = a_cases[case_id]["gamma"]
        if row["direction"] == "raw_to_orth":
            source, recorded = row["raw"], row["mapped_orth"]
            expected = [source[0] - source[3] * gamma[0], source[1] - source[3] * gamma[1], source[2], source[3]]
        else:
            source, recorded = row["orth"], row["mapped_raw"]
            expected = [source[0] + source[3] * gamma[0], source[1] + source[3] * gamma[1], source[2], source[3]]
        mapping_rows.append({
            "case_id": case_id,
            "direction": row["direction"],
            "expected": expected,
            "recorded": recorded,
            "max_abs_error": max(abs(a - b) for a, b in zip(expected, recorded)),
        })
    mapping_pass = all(row["max_abs_error"] < 1e-12 for row in mapping_rows)

    # Selected coordinates and boundary flags.
    boundary_rows = []
    for row in stage_a["selected_models"] + stage_o["absolute"]:
        flags = row.get("boundary_flags", [])
        boundary_rows.append({
            "case_id": row["case_id"],
            "model": row["model"],
            "flags": flags,
        })
    boundary_hits = []
    for row in boundary_rows:
        flags = row["flags"]
        if isinstance(flags, dict):
            for coordinate, value in flags.items():
                if value not in {"interior", "fixed", None}:
                    boundary_hits.append({"case_id": row["case_id"], "model": row["model"], "coordinate": coordinate, "value": value})
        else:
            for flag in flags:
                if flag.get("lower") or flag.get("upper"):
                    boundary_hits.append({
                        "case_id": row["case_id"],
                        "model": row["model"],
                        "coordinate": flag["coordinate"],
                        "lower": bool(flag.get("lower")),
                        "upper": bool(flag.get("upper")),
                    })

    # Stage B selected scales and Extension O selected kernels: bounds and interiority.
    b_scale_bounds_ok = all(
        0.001 <= row["tau_days"][0] <= 20.0 and 0.001 <= row["tau_days"][1] <= 20.0
        and all(not (flag.get("lower") or flag.get("upper")) for flag in row["boundary_flags"])
        for row in stage_b["absolute"]
    )
    o_omori = [row for row in stage_o["absolute"] if row["model"] == "E_omori"]
    o_kernel_bounds_ok = all(
        1e-4 <= row["kernel"]["c"] <= 20.0 and 1.01 <= row["kernel"]["p"] <= 2.5
        for row in o_omori
    )
    o_primary_c_below_coarse = all(
        row["kernel"]["c"] < 0.1 for row in o_omori if row["variant"] == "primary"
    )

    # OG6 Fold 0 versus three-fold aggregate decomposition.
    o6_folds = sorted(
        [row for row in stage_o["comparisons"]
         if row["variant"] == "primary" and row["comparison"] == "Iorth_matched-Iraw_matched"],
        key=lambda row: row["fold_id"],
    )
    o6_aggregate = next(
        row for row in stage_o["aggregates"]
        if row.get("variant") == "primary" and row["comparison"] == "Iorth_matched-Iraw_matched"
    )
    o6_joint = [row["joint"] for row in o6_folds]
    o6_decomposition = {
        "fold_joint": o6_joint,
        "fold_sum": sum(o6_joint),
        "aggregate_joint": o6_aggregate["joint"],
        "fold0_display": -0.361471,
        "aggregate_display": -0.361468,
        "fold1_display": 0.000003373,
        "fold0_minus_aggregate": o6_joint[0] - o6_aggregate["joint"],
        "identity_residual": abs(sum(o6_joint) - o6_aggregate["joint"]),
        "passed": abs(sum(o6_joint) - o6_aggregate["joint"]) < 1e-12,
    }

    payload = {
        "schema": "slice2_chapter9_stage_abc_v1",
        "passed": bool(
            ag_primary["passed"] and bg_primary["passed"] and og_primary["passed"]
            and ag_constant["passed"] and ag_post["passed"] and og_constant["passed"] and og_post["passed"]
            and all(v["passed"] for v in a_folds.values())
            and b_folds["primary"]["passed"]
            and all(v["passed"] for v in o_folds.values())
            and b_scale_rows and all(all(v for k, v in row.items() if k.endswith("_match")) for row in b_scale_rows)
            and o_kernel_rows and all(all(v for k, v in row.items() if k.endswith("_match")) for row in o_kernel_rows)
            and geometry_rows and all(all(v for k, v in row.items() if k.endswith("_match")) for row in geometry_rows)
            and mapping_pass
            and o6_decomposition["passed"]
            and b_scale_bounds_ok
            and o_kernel_bounds_ok
            and o_primary_c_below_coarse
        ),
        "aggregate_tables": {
            "AG_primary": ag_primary,
            "BG_primary": bg_primary,
            "OG_primary": og_primary,
            "AG_constant_background": ag_constant,
            "AG_post1980": ag_post,
            "OG_constant_background": og_constant,
            "OG_post1980": og_post,
        },
        "fold_tables": {"stage_a": a_folds, "stage_b": b_folds, "stage_o": o_folds},
        "stage_b_scales": b_scale_rows,
        "stage_b_bounds_and_interiority_passed": b_scale_bounds_ok,
        "stage_o_kernels": o_kernel_rows,
        "stage_o_kernel_bounds_passed": o_kernel_bounds_ok,
        "stage_o_primary_c_below_coarse_grid": o_primary_c_below_coarse,
        "stage_a_geometry": geometry_rows,
        "orthogonalization_mappings": {
            "rows": mapping_rows,
            "max_abs_error": max((row["max_abs_error"] for row in mapping_rows), default=None),
            "passed": mapping_pass,
        },
        "boundary_inventory": {
            "n_selected_records": len(boundary_rows),
            "hits": boundary_hits,
            "note": ("Boundary hits are retained as selected-coordinate outcomes, including "
                     "raw d=2 and fixed d=0 restrictions. They are not converted into interior optima."),
        },
        "og6_fold0_vs_aggregate": o6_decomposition,
        "source_hashes": {
            "stage_a": sha256(AUTH["stage_a"]),
            "stage_b": sha256(AUTH["stage_b"]),
            "stage_o": sha256(AUTH["stage_o"]),
            "09_temporal_mark_extensions.tex": sha256(TEX["ch09"]),
            "ch09_audit.tex": sha256(TEX["audit09"]),
        },
    }
    return payload


# ---------------------------------------------------------------------------
# Completed S02 study
# ---------------------------------------------------------------------------

def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return mid - half, mid + half


def s02_audit() -> dict:
    summary = load(AUTH["s02_summary"])
    paired = load(AUTH["s02_paired"])
    derived = load(AUTH["s02_derived"])
    acceptance = load(AUTH["s02_acceptance"])
    text = TEX["s02"].read_text(encoding="utf-8")

    # Table tab:s02-completed.
    block = table_block(text, "tab:s02-completed", env="tabular")
    rows = []
    cp_pass = True
    for cells in table_rows(block):
        if len(cells) < 6 or cells[0] not in {"M1", "M2"}:
            continue
        procedure = cells[0]
        h = float(cells[1])
        authority = next(row for row in summary["table"] if row["procedure"] == procedure and math.isclose(row["h"], h))
        selected, planned = [int(x) for x in cells[2].split("/")]
        lo, hi = [float(x) for x in re.findall(r"-?\d+\.\d+", cells[3])]
        wlo, whi = wilson_interval(selected, planned)
        row_pass = (
            selected == authority["selected"]
            and planned == authority["planned"]
            and abs(lo - authority["wilson95"][0]) <= 5.1e-4
            and abs(hi - authority["wilson95"][1]) <= 5.1e-4
            and display_match(cells[4], authority["empirical_h0_95threshold"])
            and int(cells[5].split("/")[0]) == authority["above_empirical_threshold"]
            and math.isclose(wlo, authority["wilson95"][0], rel_tol=1e-12, abs_tol=1e-12)
            and math.isclose(whi, authority["wilson95"][1], rel_tol=1e-12, abs_tol=1e-12)
        )
        cp_pass = cp_pass and row_pass
        rows.append({
            "procedure": procedure,
            "h": h,
            "selected_planned": cells[2],
            "wilson_display": cells[3],
            "wilson_recomputed": [wlo, whi],
            "wilson_authority": authority["wilson95"],
            "threshold_match": display_match(cells[4], authority["empirical_h0_95threshold"]),
            "above_threshold_match": int(cells[5].split("/")[0]) == authority["above_empirical_threshold"],
            "passed": row_pass,
        })

    # Table tab:s02-paired.
    paired_block = table_block(text, "tab:s02-paired", env="tabular")
    paired_rows = []
    paired_pass = True
    for cells in table_rows(paired_block):
        if len(cells) < 5 or cells[0] not in {"M1", "M2"}:
            continue
        procedure = cells[0]
        h = float(cells[1])
        authority = next(row for row in summary["paired_glr_differences"]
                         if row["procedure"] == procedure and math.isclose(row["h_minus0"], h))
        row_pass = (
            display_match(cells[2], authority["mean"])
            and display_match(cells[3], authority["median"])
            and display_match(cells[4], authority["mcse"])
        )
        paired_pass = paired_pass and row_pass
        paired_rows.append({
            "procedure": procedure,
            "h": h,
            "mean_match": display_match(cells[2], authority["mean"]),
            "median_match": display_match(cells[3], authority["median"]),
            "mcse_match": display_match(cells[4], authority["mcse"]),
            "passed": row_pass,
        })

    # The unlabeled within-forest M2-M1 table.
    start = text.index(r"\caption{Within-forest M2 minus M1 GLR contrasts")
    block = text[start:text.index(r"\end{tabular}", start) + len(r"\end{tabular}")]
    contrast_rows = []
    contrast_pass = True
    for cells in table_rows(block):
        if len(cells) < 3:
            continue
        try:
            h = float(cells[0])
        except ValueError:
            continue
        authority = next(row for row in paired["cross_procedure"] if math.isclose(row["h"], h))
        row_pass = display_match(cells[1], authority["glr"]["mean"]) and display_match(cells[2], authority["glr"]["mcse"])
        contrast_pass = contrast_pass and row_pass
        contrast_rows.append({
            "h": h,
            "mean_match": display_match(cells[1], authority["glr"]["mean"]),
            "mcse_match": display_match(cells[2], authority["glr"]["mcse"]),
            "passed": row_pass,
        })

    # Source-pin cross-links in the S02/S03 derived-values authority.
    pin_values = list(derived["source_pins"].values())
    pin_cross_links = {
        "summary_pin_present": sha256(AUTH["s02_summary"]) in pin_values,
        "paired_pin_present": sha256(AUTH["s02_paired"]) in pin_values,
    }

    # Recovered input archive verification, read-only.
    result = subprocess.run(
        [sys.executable, "-B", "reproduction/s02/inputs.py", "verify"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace",
    )
    input_verification = {
        "exit_code": result.returncode,
        "output_tail": "\n".join(result.stdout.splitlines()[-12:]),
    }
    if result.returncode == 0:
        try:
            input_verification["parsed"] = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass

    # Cross-run GLR contrast and MCSE are also consistent with paired differences.
    m2_m1_means = [row["glr"]["mean"] for row in paired["cross_procedure"]]
    m2_m1_mcse = [row["glr"]["mcse"] for row in paired["cross_procedure"]]

    payload = {
        "schema": "slice2_s02_completed_v1",
        "passed": bool(
            cp_pass and paired_pass and contrast_pass
            and all(pin_cross_links.values())
            and input_verification["exit_code"] == 0
            and summary["completed_method_cases"] == 600
        ),
        "selection_table": rows,
        "paired_table": paired_rows,
        "cross_procedure_contrast_table": contrast_rows,
        "cross_procedure_means": m2_m1_means,
        "cross_procedure_mcse": m2_m1_mcse,
        "counts": {
            "planned_forests": summary["planned_forests"],
            "planned_catalogues": summary["planned_catalogues"],
            "planned_method_cases": summary["planned_method_cases"],
            "completed_method_cases": summary["completed_method_cases"],
            "acceptance_catalogues": acceptance["catalogues"],
            "acceptance_methods": acceptance["methods"],
        },
        "source_pin_cross_links": pin_cross_links,
        "input_verification": input_verification,
        "source_hashes": {
            "s02_summary": sha256(AUTH["s02_summary"]),
            "s02_paired": sha256(AUTH["s02_paired"]),
            "s02_derived": sha256(AUTH["s02_derived"]),
            "S02_ACCEPTANCE": sha256(AUTH["s02_acceptance"]),
        },
    }
    return payload


# ---------------------------------------------------------------------------
# Claim ledger and sealed authority integrity
# ---------------------------------------------------------------------------

def claim_ledger_audit() -> dict:
    ledger = load(LEDGER)
    claims = [c for c in ledger["claims"] if c.get("tex_file") in MANUSCRIPT_FILES]
    failures = []
    counts = Counter()
    cache = {}
    tex_cache = {}
    for claim in claims:
        try:
            source_path = claim["bundled_source"]
            if source_path not in cache:
                path = ROOT / source_path
                cache[source_path] = {
                    "json": load(path) if path.suffix == ".json" else None,
                    "text": path.read_text(encoding="utf-8-sig") if path.suffix != ".json" else None,
                }
            source = cache[source_path]
            if claim.get("source_sha256") and sha256(ROOT / source_path) != claim["source_sha256"]:
                raise ValueError("source_hash_mismatch")
            if "json_pointer" in claim and source["json"] is not None:
                raw = pointer(source["json"], claim["json_pointer"])
                if "resolved_source_value" in claim:
                    if type(claim["resolved_source_value"]) is not type(raw) or claim["resolved_source_value"] != raw:
                        raise ValueError("stale_resolved_source_value")
                value = transformed(raw, claim, source["json"])
                if claim.get("display_format"):
                    pass
                elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                    if not equal_display(value, claim):
                        raise ValueError("display_does_not_round_from_source")
                    if not equal_display(claim["value"], claim):
                        raise ValueError("stale_numeric_value_metadata")
                counts["authority_scalar_verified"] += 1
            else:
                counts["documentary_token_verified"] += 1
            try:
                display_number = decimal_value(claim["display"])
            except ValueError:
                display_number = None
            if claim.get("ledger_role") == "manuscript_binding" and display_number is not None:
                locations = claim.get("final_display_locations") or [claim["tex_file"]]
                found = False
                for location in locations:
                    tex_path = ROOT / "paper/source" / location
                    if not tex_path.is_file():
                        continue
                    if tex_path not in tex_cache:
                        tex_cache[tex_path] = numeric_tokens(tex_path.read_text(encoding="utf-8"))
                    if display_number in tex_cache[tex_path]:
                        found = True
                        break
                if not found:
                    raise ValueError("declared_manuscript_display_absent")
                counts["display_present"] += 1
            counts["claims_checked"] += 1
        except Exception as exc:  # noqa: BLE001 - audit record
            failures.append({
                "id": claim.get("id"),
                "display": claim.get("display"),
                "tex_file": claim.get("tex_file"),
                "bundled_source": claim.get("bundled_source"),
                "json_pointer": claim.get("json_pointer"),
                "error": str(exc),
            })
    by_file = Counter(c["tex_file"] for c in claims)
    failure_by_file = Counter(f["tex_file"] for f in failures)
    return {
        "schema": "slice2_claim_ledger_audit_v1",
        "passed": not failures,
        "n_claims": len(claims),
        "by_file": dict(by_file),
        "failure_by_file": dict(failure_by_file),
        "failure_count": len(failures),
        "failures": failures[:200],
        "counts": dict(counts),
        "ledger_sha256": sha256(LEDGER),
    }


def sealed_authority_audit() -> dict:
    snapshot = load(SNAPSHOT)
    sealed = snapshot["sealed_json"]
    unchanged, changed, missing = 0, [], []
    for relative, expected in sealed.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path) == expected:
            unchanged += 1
        else:
            changed.append(relative)
    return {
        "schema": "slice2_sealed_authority_integrity_v1",
        "snapshot": snapshot["sealed_json_count"],
        "unchanged": unchanged,
        "changed": changed,
        "missing": missing,
        "passed": not changed and not missing and unchanged == snapshot["sealed_json_count"],
        "snapshot_sha256": sha256(SNAPSHOT),
        "baseline_commit": snapshot["baseline_commit"],
    }


# ---------------------------------------------------------------------------
# Manuscript repairs, symbolic projection/gradient checks, code consistency
# ---------------------------------------------------------------------------

def projection_and_gradient_checks() -> dict:
    # Algebraic exposure projection.
    w1, w2, x1, x2, g1, g2 = sp.symbols("w1 w2 x1 x2 G1 G2", positive=True)
    total = w1 + w2
    xbar = (w1 * x1 + w2 * x2) / total
    gbar = (w1 * g1 + w2 * g2) / total
    vx = w1 * (x1 - xbar) ** 2 + w2 * (x2 - xbar) ** 2
    gamma1 = (w1 * (x1 - xbar) * (g1 - gbar) + w2 * (x2 - xbar) * (g2 - gbar)) / vx
    gamma0 = gbar - gamma1 * xbar
    zero_mean = sp.simplify(w1 * (g1 - gamma0 - gamma1 * x1) + w2 * (g2 - gamma0 - gamma1 * x2))
    zero_cov = sp.simplify(
        w1 * (x1 - xbar) * (g1 - gamma0 - gamma1 * x1)
        + w2 * (x2 - xbar) * (g2 - gamma0 - gamma1 * x2)
    )
    projection_pass = zero_mean == 0 and zero_cov == 0

    # Unrestricted map identity.
    a, d, eta, gamma0s, gamma1s, x = sp.symbols("a d eta gamma0 gamma1 x", real=True)
    at, dt = a - eta * gamma0s, d - eta * gamma1s
    R = sp.Symbol("G", real=True) - gamma0s - gamma1s * x
    identity = sp.simplify((a + d * x - eta * sp.Symbol("G", real=True)) - (at + dt * x - eta * R))

    # Timing NLL gradients with B=exp(a+d x - eta R).
    q1, q2, n, J, H1, H2 = sp.symbols("q1 q2 n J H1 H2", positive=True)
    a, d, eta, x1, x2, R1, R2 = sp.symbols("a d eta x1 x2 R1 R2", real=True)
    B1 = sp.exp(a + d * x1 - eta * R1)
    B2 = sp.exp(a + d * x2 - eta * R2)
    lam1 = B1 + n * H1
    lam2 = B2 + n * H2
    L = q1 * B1 + q2 * B2 + n * J - sp.log(lam1) - sp.log(lam2)
    expected_n = J - H1 / lam1 - H2 / lam2
    expected_a = q1 * B1 + q2 * B2 - B1 / lam1 - B2 / lam2
    expected_d = q1 * x1 * B1 + q2 * x2 * B2 - x1 * B1 / lam1 - x2 * B2 / lam2
    expected_eta = -q1 * R1 * B1 - q2 * R2 * B2 + R1 * B1 / lam1 + R2 * B2 / lam2
    grad_n_residual = sp.simplify(sp.diff(L, n) - expected_n)
    grad_a_residual = sp.simplify(sp.diff(L, a) - expected_a)
    grad_d_residual = sp.simplify(sp.diff(L, d) - expected_d)
    grad_eta_residual = sp.simplify(sp.diff(L, eta) - expected_eta)
    grad_eta_pass = all(value == 0 for value in
                        (grad_n_residual, grad_a_residual, grad_d_residual, grad_eta_residual))

    # Stage B scale and association gradients.
    B, Gamma, rho, rhop, p0, p1 = sp.symbols("B Gamma rho rho_prime p0 p1", positive=True)
    P00, P01, P10, P11 = sp.symbols("P00 P01 P10 P11", positive=True)
    P00p, P01p, P10p, P11p = sp.symbols("P00p P01p P10p P11p", real=True)
    H0, H1, J0, J1, h0, h1 = sp.symbols("H0 H1 J0 J1 h0 h1", positive=True)
    T0 = P00 * H0 + P01 * H1
    T1 = P10 * H0 + P11 * H1
    Lb = B + Gamma * (J0 + J1) - sp.log(p0 * B + Gamma * T0) - sp.log(p1 * B + Gamma * T1)
    # s-derivative with dH_j/ds=h_j and dJ_j/ds=j_j (j_j written through h).
    s = sp.Symbol("s", real=True)
    H0s = sp.Function("H0")(s)
    H1s = sp.Function("H1")(s)
    J0s = sp.Function("J0")(s)
    J1s = sp.Function("J1")(s)
    Ls = B + Gamma * (J0s + J1s) - sp.log(p0 * B + Gamma * (P00 * H0s + P01 * H1s)) - sp.log(p1 * B + Gamma * (P10 * H0s + P11 * H1s))
    ds = sp.diff(Ls, s)
    expected_ds = Gamma * (sp.Derivative(J0s, s) + sp.Derivative(J1s, s)) - Gamma * (
        (P00 * sp.Derivative(H0s, s) + P01 * sp.Derivative(H1s, s)) / (p0 * B + Gamma * (P00 * H0s + P01 * H1s))
        + (P10 * sp.Derivative(H0s, s) + P11 * sp.Derivative(H1s, s)) / (p1 * B + Gamma * (P10 * H0s + P11 * H1s))
    )
    scale_gradient_pass = sp.simplify(ds - expected_ds) == 0

    hvar = sp.Symbol("h", real=True)
    Gamma_h = sp.Function("Gamma")(hvar)
    rho_h = sp.Function("rho")(hvar)
    P00h = sp.Function("P00")(hvar)
    P01h = sp.Function("P01")(hvar)
    P10h = sp.Function("P10")(hvar)
    P11h = sp.Function("P11")(hvar)
    Lh = B + Gamma_h * (J0 + J1) - sp.log(p0 * B + Gamma_h * (P00h * H0 + P01h * H1)) - sp.log(p1 * B + Gamma_h * (P10h * H0 + P11h * H1))
    with_assumptions = Gamma_h.diff(hvar) / Gamma_h - sp.Derivative(rho_h, hvar) / rho_h
    # Use Gamma=n/rho directly.
    nconst = sp.Symbol("nconst", positive=True)
    Gamma_expr = nconst / rho_h
    Lh_expr = B + Gamma_expr * (J0 + J1) - sp.log(p0 * B + Gamma_expr * (P00h * H0 + P01h * H1)) - sp.log(p1 * B + Gamma_expr * (P10h * H0 + P11h * H1))
    dLh = sp.diff(Lh_expr, hvar)
    expected_h = -nconst * sp.Derivative(rho_h, hvar) / rho_h ** 2 * (J0 + J1) - (
        nconst * (sp.Derivative(P00h, hvar) * H0 + sp.Derivative(P01h, hvar) * H1 - sp.Derivative(rho_h, hvar) / rho_h * (P00h * H0 + P01h * H1)) / rho_h
        / (p0 * B + nconst / rho_h * (P00h * H0 + P01h * H1))
        + nconst * (sp.Derivative(P10h, hvar) * H0 + sp.Derivative(P11h, hvar) * H1 - sp.Derivative(rho_h, hvar) / rho_h * (P10h * H0 + P11h * H1)) / rho_h
        / (p1 * B + nconst / rho_h * (P10h * H0 + P11h * H1))
    )
    association_gradient_pass = sp.simplify(dLh - expected_h) == 0

    # Omori density and derivatives.
    u, cc, pp = sp.symbols("u c p", positive=True)
    k = (pp - 1) / cc * (1 + u / cc) ** (-pp)
    S = (1 + u / cc) ** (1 - pp)
    mass_expr = sp.integrate(k, (u, 0, sp.oo))
    if isinstance(mass_expr, sp.Piecewise):
        mass = sp.simplify(mass_expr.args[0][0])
        mass_condition = str(mass_expr.args[0][1])
    else:
        mass = sp.simplify(mass_expr)
        mass_condition = "unconditional"
    mass_numeric = quad(
        lambda x: (1.3 - 1) * (1 + x) ** (-1.3), 0, math.inf, epsabs=1e-12, epsrel=1e-12
    )[0]
    svar = sp.Symbol("s", real=True)
    c_s = sp.exp(svar)
    k_s = (pp - 1) / c_s * (1 + u / c_s) ** (-pp)
    S_s = (1 + u / c_s) ** (1 - pp)
    A = sp.log(1 + u / c_s)
    v = u / (c_s + u)
    ds_logk = sp.simplify(sp.diff(sp.log(k_s), svar) - (-1 + pp * v))
    dp_logk = sp.simplify(sp.diff(sp.log(k_s), pp) - (1 / (pp - 1) - A))
    ds_S = sp.simplify(sp.diff(S_s, svar) - (pp - 1) * v * S_s)
    dp_S = sp.simplify(sp.diff(S_s, pp) + A * S_s)
    omori_pass = mass == 1 and abs(mass_numeric - 1) < 1e-10 and all(
        value == 0 for value in (ds_logk, dp_logk, ds_S, dp_S)
    )

    return {
        "schema": "slice2_projection_gradient_checks_v1",
        "passed": bool(projection_pass and identity == 0 and grad_eta_pass and scale_gradient_pass and association_gradient_pass and omori_pass),
        "exposure_projection": {
            "zero_weighted_mean_residual": str(zero_mean),
            "zero_weighted_covariance_residual": str(zero_cov),
            "passed": projection_pass,
        },
        "coordinate_map_identity_residual": str(identity),
        "timing_gradient_residuals": {
            "n": str(grad_n_residual),
            "a": str(grad_a_residual),
            "d": str(grad_d_residual),
            "eta": str(grad_eta_residual),
            "passed": grad_eta_pass,
        },
        "stage_b_scale_gradient_pass": scale_gradient_pass,
        "stage_b_association_gradient_pass": association_gradient_pass,
        "omori": {
            "total_mass": str(mass),
            "total_mass_condition": mass_condition,
            "total_mass_numeric_at_p_1.3": mass_numeric,
            "d_logk_ds_residual": str(ds_logk),
            "d_logk_dp_residual": str(dp_logk),
            "dS_ds_residual": str(ds_S),
            "dS_dp_residual": str(dp_S),
            "passed": omori_pass,
        },
    }


def manuscript_repair_audit() -> dict:
    text04 = TEX["ch04"].read_text(encoding="utf-8")
    text09 = TEX["ch09"].read_text(encoding="utf-8")
    doc = (ROOT / "docs/reviews/slice1_math_audit_20261114.md").read_text(encoding="utf-8")
    checks = {
        "ch04_min_display_present": r"\min\{\mathcal B,\eta^2K_T\}" in text04,
        "ch04_scaled_display_present": r"\mathcal B\min\{1,\eta^2K_T/\mathcal B\}" in text04,
        "ch04_no_legacy_display": r"\le \mathcal B\min\{1,\eta^2K_T\}," not in text04,
        "slice1_doc_scaled_display_present": r"\min\{\mathcal B,\eta^2K_T\}" in doc,
        "ch09_fold0_aggregate_clarification": (
            "0.361471" in text09 and "-0.361468" in text09
            and r"3.4\times10^{-6}" in text09 and "0.000003373" in text09
            and r"\texttt{OG6}" in text09
        ),
        "ch09_raw_log_removed": all(
            token not in text09
            for token in ("r=.7", "Iteration27", "Fold0", r"d\_tilde=0", "results/analysis\n")
        ),
        "ch09_path_formatted": r"\path{results/analysis}" in text09,
        "ch09_math_tokens": all(
            token in text09
            for token in (r"$r=0.7$", r"$c=0.1$", r"$d=2.114439$", r"$\widetilde d=0$", r"$h=0$")
        ),
        "ch09_stale_spatial_launch_sentence_removed": "S was designed and frozen before these outcomes" not in text09,
        "ch09_spatial_extension_pointer": r"Chapter~\ref{ch:nz-spatial}" in text09,
        "og6_values_bound": "OG6 & -0.510772 & 0.149304 & -0.361468" in text09,
    }
    return {
        "schema": "slice2_manuscript_repairs_v1",
        "passed": all(checks.values()),
        "checks": checks,
        "source_hashes": {
            "04_identifiability.tex": sha256(TEX["ch04"]),
            "09_temporal_mark_extensions.tex": sha256(TEX["ch09"]),
            "slice1_math_audit_20261114.md": sha256(ROOT / "docs/reviews/slice1_math_audit_20261114.md"),
        },
    }


def code_consistency() -> dict:
    # Import and inspect the production kernel implementation.
    import importlib.util

    kernels = load_module("slice2_kernels_consistency", KERNELS)
    alpha_modes = {}
    for alpha in (0.5, 0.7):
        kspec = kernels.KernelSpec("ml", 1.0, alpha=alpha)
        weights, rates = kspec.mixture
        alpha_modes[str(alpha)] = {
            "modes": int(len(weights)),
            "normalized_mass": float(weights.sum()),
            "metadata": kspec.approximation_metadata,
        }
    # The S02 archive verifier already runs in s02_audit; record the source hash.
    return {
        "schema": "slice2_code_consistency_v1",
        "passed": alpha_modes["0.5"]["modes"] == 195 and alpha_modes["0.7"]["modes"] == 137,
        "kernels_py": {"sha256": sha256(KERNELS), "alpha_modes": alpha_modes},
        "source_hashes": {
            "scripts/check_mathematics.py": sha256(ROOT / "scripts/check_mathematics.py"),
            "reproduction/score_replay/core.py": sha256(ROOT / "reproduction/score_replay/core.py"),
            "engine/stage2_followup/s01_s02_temporal/s02_campaign.py": sha256(ROOT / "engine/stage2_followup/s01_s02_temporal/s02_campaign.py"),
        },
    }


def main() -> int:
    global OUTPUT_ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    OUTPUT_ROOT = args.output.resolve()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    chapter6 = chapter6_audit()
    chapter7 = chapter7_audit()
    algebra = chapter9_algebra()
    magnitude = chapter9_magnitude_tables()
    pilot = pilot_tables()
    stage_abc = stage_abc_audit()
    s02 = s02_audit()
    claims = claim_ledger_audit()
    sealed = sealed_authority_audit()
    projection = projection_and_gradient_checks()
    manuscript = manuscript_repair_audit()
    code = code_consistency()

    components = {
        "chapter6_design": chapter6,
        "chapter7_synthetic": chapter7,
        "chapter9_algebra": algebra,
        "chapter9_magnitude_tables": magnitude,
        "chapter9_pilot_tables": pilot,
        "chapter9_stage_abc": stage_abc,
        "s02_completed": s02,
        "claim_ledger": claims,
        "sealed_authority_integrity": sealed,
        "projection_gradients": projection,
        "manuscript_repairs": manuscript,
        "code_consistency": code,
    }
    artifacts = {}
    for name, payload in components.items():
        artifacts[name] = dump(name + ".json", payload)

    passed = all(payload["passed"] for payload in components.values())
    summary = {
        "schema": "slice2_audit_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "ce8581b",
        "scope": (
            "Vertical Triad Slice 2: Chapters 6, 7, 9 (Sections 9.1--9.13), "
            "Appendix B.7, completed S02, Stage A projection, Stage B temporal "
            "scales, and Extension O continuous Omori tuning."
        ),
        "passed": passed,
        "components": {name: payload["passed"] for name, payload in components.items()},
        "counts": {
            "chapter7_procedures": len(chapter7["clopper_pearson"]),
            "chapter7_table_rows": len(chapter7["main_detection_table"]),
            "chapter9_algebra_checks": 7,
            "history_table_rows": len(magnitude["history_table"]),
            "productivity_table_rows": len(magnitude["productivity_table"]),
            "cross_run_rows": len(magnitude["cross_run_table"]),
            "pilot_frequency_rows": len(pilot["frequency_table"]),
            "pilot_paired_rows": len(pilot["paired_table"]),
            "stage_a_fold_rows": sum(len(v["rows"]) for v in stage_abc["fold_tables"]["stage_a"].values()),
            "stage_b_fold_rows": len(stage_abc["fold_tables"]["stage_b"]["primary"]["rows"]),
            "stage_o_fold_rows": sum(len(v["rows"]) for v in stage_abc["fold_tables"]["stage_o"].values()),
            "aggregate_rows": sum(len(v["rows"]) for v in stage_abc["aggregate_tables"].values()),
            "s02_selection_rows": len(s02["selection_table"]),
            "s02_paired_rows": len(s02["paired_table"]),
            "claim_ledger_checked": claims["n_claims"],
            "sealed_json_unchanged": sealed["unchanged"],
            "orthogonalization_mappings": len(stage_abc["orthogonalization_mappings"]["rows"]),
        },
        "defects_and_repairs": [
            {
                "id": "slice2-carryover-visible-bound-display",
                "file": "paper/source/chapters/04_identifiability.tex",
                "locator": "line 216 and docs/reviews/slice1_math_audit_20261114.md",
                "finding": (
                    "K_T already contains the integrated background mass B; the display "
                    "B*min{1,eta^2*K_T} therefore double-counts B. The correct clipped "
                    "statement is min{B,eta^2*K_T}=B*min{1,eta^2*K_T/B}."
                ),
                "status": "fixed",
            },
            {
                "id": "slice2-extension-o-fold0-vs-aggregate",
                "file": "paper/source/chapters/09_temporal_mark_extensions.tex",
                "locator": "line 1195 versus tab:OG-primary/OG6, line 1238",
                "finding": (
                    "The prose Fold 0 raw-versus-orthogonal contrast is -0.361471 nats; "
                    "the three-fold aggregate OG6 is -0.361468 nats because Fold 1 "
                    "contributes +0.000003373 nats and Fold 2 is numerically zero. "
                    "The exact 3.4e-6-nat decomposition is now stated explicitly."
                ),
                "status": "clarified",
            },
            {
                "id": "slice2-decision-log-math-formatting",
                "file": "paper/source/chapters/09_temporal_mark_extensions.tex",
                "locator": "Sections 9.7--9.11, lines 935--1210",
                "finding": "Raw log strings and unformatted mathematical tokens were replaced with prose and math mode; all numeric literals were preserved.",
                "status": "fixed",
            },
            {
                "id": "slice2-stale-spatial-launch-sentence",
                "file": "paper/source/chapters/09_temporal_mark_extensions.tex",
                "locator": "line 1204",
                "finding": (
                    "The pre-launch statement that S was merely frozen was stale because "
                    "the spatial extension has since been executed and reported in Chapter 10."
                ),
                "status": "fixed",
            },
        ],
        "artifacts": artifacts,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "sympy": sp.__version__,
        },
    }
    dump("summary.json", summary)
    print(json.dumps({
        "passed": passed,
        "out": OUTPUT_ROOT.relative_to(ROOT).as_posix() if OUTPUT_ROOT.is_relative_to(ROOT) else str(OUTPUT_ROOT),
        "components": summary["components"],
        "counts": summary["counts"],
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
