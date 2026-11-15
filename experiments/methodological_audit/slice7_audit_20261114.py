#!/usr/bin/env python3
"""Independent Slice 7 synthesis, MDE-table, reader-surface, and custody audit.

Scope: the final cross-slice synthesis (abstract, Chapter 1, Chapter 14 and its
contrast-specific MDE subsection, appendices, README, reviewer guide, companion
guide and website), the expanded New Zealand-free/zero/fixed MDE table, and the
claim-ledger / repository verifier infrastructure.

The audit re-derives every displayed MDE cell from the bound authorities,
recomputes the fractional rate perturbations, checks the cross-slice canonical
numbers and the absence of withdrawn or stale phrases, and verifies that every
pre-existing sealed JSON file is byte-for-byte unchanged.  It never edits a
sealed authority.  Its only outputs are under
``validation/live_results/slice7_audit_20261114``.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/slice7_audit_20261114"
SNAPSHOT = ROOT / "validation/slice7_prechange_snapshot_20261114.json"
SNAPSHOT_ZIP = ROOT / "validation/slice7_prechange_snapshot_20261114.zip"
EXPECTED_SEALED = 782

TEX = {
    "abstract": ROOT / "paper/source/abstract.tex",
    "introduction": ROOT / "paper/source/chapters/01_introduction.tex",
    "discussion": ROOT / "paper/source/chapters/14_discussion_conclusion.tex",
    "mde": ROOT / "paper/source/chapters/14_power_and_mde.tex",
    "appendices": ROOT / "paper/source/appendices.tex",
    "visibility": ROOT / "paper/source/chapters/04_identifiability.tex",
}
READERS = {
    "README": ROOT / "README.md",
    "reviewer": ROOT / "REVIEWER_START_HERE.md",
    "companion": ROOT / "companion/guide_content.json",
    "metadata": ROOT / "website/document_metadata.json",
    "findings": ROOT / "website/findings.html",
    "site_findings": ROOT / "website/site/findings.html",
    "site_data": ROOT / "website/site/findings-data.json",
}
AUTH = {
    "mde": ROOT / "validation/live_results/referee_remediation_20261113/mde_expanded.json",
    "nz": ROOT / "validation/live_results/forensic_remediation_20261114/nz_trend_controls.json",
    "japan": ROOT / "validation/live_results/forensic_remediation_20261114/japan_mde.json",
    "nz_totals": ROOT / "validation/live_results/referee_remediation_20261113/nz_trend_totals.json",
    "s8": ROOT / "validation/live_results/forensic_remediation_20261114/s8_oracle.json",
    "ablation": ROOT / "validation/live_results/forensic_remediation_20261114/epplus_ablation.json",
    "sigma0": ROOT / "validation/live_results/forensic_remediation_20261114/epplus_sigma0_totals.json",
    "visibility": ROOT / "validation/live_results/slice1_math_audit_20261114/visibility_correction.json",
    "joint": ROOT / "validation/live_results/s04b_joint_complete_20261111/summary.json",
    "s8mod": ROOT / "validation/live_results/s8_moderate_complete_20261111/reported_summary.json",
    "forensic": ROOT / "validation/forensic_remediation_20261114.json",
}
LEDGER = ROOT / "validation/MASTER_CLAIM_LEDGER.json"
RECEIPT = ROOT / "validation/numeric_reconciliation_receipt.json"
DISPLAY_REGRESSION = ROOT / "validation/manuscript_display_regression.json"
MANIFEST = ROOT / "MANIFEST.json"
TARGET_TEX = (
    "abstract.tex",
    "chapters/01_introduction.tex",
    "chapters/14_discussion_conclusion.tex",
    "chapters/14_power_and_mde.tex",
    "appendices.tex",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def dump(name: str, payload) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                    encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def close(a, b, tol: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def display_ok(actual: float, display: str, decimals: int) -> bool:
    want = float(display.replace("+", ""))
    tolerance = 0.5 * 10.0 ** (-decimals) + 1e-12 * max(1.0, abs(float(actual)))
    return abs(float(actual) - want) <= tolerance


def add(checks: list, cid: str, ok: bool, **detail):
    checks.append({"id": cid, "passed": bool(ok), **detail})
    return bool(ok)


def component(schema: str, scope: str, checks: list[dict], counts: dict, notes=None):
    return {
        "schema": schema,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "passed": all(c["passed"] for c in checks),
        "counts": counts,
        "checks": checks,
        "notes": notes or [],
    }


def norm(value: str) -> str:
    value = value.replace("\u2212", "-").replace("$", "").replace("{", "").replace("}", "")
    value = value.replace("~", " ").replace("\\,", "").replace("\\%", "%")
    value = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def contains(value: str, token: str) -> bool:
    return norm(token) in norm(value)


def parse_mde_rows() -> list[dict]:
    body = text(TEX["mde"])
    start = body.index("\\midrule", body.index("\\label{tab:mde}") - 3000)
    end = body.index("\\bottomrule", start)
    rows, label = [], None
    for raw in body[start:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("\\midrule") or line.startswith("\\addlinespace"):
            continue
        line = line.removesuffix("\\\\").strip()
        cells = [c.strip() for c in line.split("&")]
        if len(cells) != 7:
            raise ValueError(f"unexpected MDE table row: {raw!r}")
        if cells[0]:
            label = cells[0]
        block = cells[3]
        if not re.fullmatch(r"(?:90|180|365|3-year)", block):
            raise ValueError(f"unexpected block cell: {raw!r}")
        rows.append({
            "label": label,
            "n_test": int(cells[1]) if cells[1] else None,
            "observed": cells[2],
            "block": block,
            "se": cells[4],
            "mde": cells[5],
            "per_event": cells[6],
            "raw": raw.strip(),
        })
    return rows


def audit_mde_table() -> dict:
    checks, notes = [], []
    mde = read(AUTH["mde"])
    nz = read(AUTH["nz"])["full_grid"]["pooled"]
    japan = read(AUTH["japan"])["repaired"]
    rows = parse_mde_rows()
    add(checks, "mde.row_count", len(rows) == 21,
        detail={"rows": len(rows), "expected": 21,
                "groups": sorted({r["label"] for r in rows})})
    add(checks, "mde.group_count", len({r["label"] for r in rows}) == 9,
        detail={"groups": len({r["label"] for r in rows})})

    def group(name: str, n: int = 3) -> list[dict]:
        found = [r for r in rows if name in (r["label"] or "")]
        if len(found) != n:
            raise ValueError(f"expected {n} rows for {name!r}, got {len(found)}")
        return found

    groups = {
        "free": group("free $d$"),
        "zero": group("zero $d$"),
        "fixed": group("fixed null $d$"),
        "li": group("LI+"),
        "ep": group("EP+"),
        "oc": group("CA \\texttt{OC}"),
        "jp_fold": group("per 3-year fold", 1),
        "jp_sum": group("3-fold sum", 1),
        "jp_annual": group("9 annual blocks", 1),
    }

    def check_triplet(key: str, authority: dict, observed_display: str, n_test: int,
                      label: str, observed_value=None, per_event_n_test=None,
                      per_event_authority=None):
        for row in groups[key]:
            block = row["block"]
            if block == "3-year":
                block_key = "90" if key == "jp_fold" else "90"
                # Japan's fold/sum rows carry their own total fields, not a 3-year key.
                block_key = "90"
            else:
                block_key = block
            if per_event_authority is None:
                source = authority[block_key]
                se = source["se_total_nats"]
                m = source["mde95_total_nats"]
                per_event = source.get("mde95_nats_per_event")
                if per_event is None:
                    per_event = m / n_test
            else:
                se = None
                m = per_event_authority[block_key]["mde95_total_nats"]
                per_event = per_event_authority[block_key]["mde95_nats_per_event"]
            decimals_se = 2
            decimals_mde = 2
            decimals_per = 4
            se_display = f"{se:.{decimals_se}f}" if se is not None else row["se"]
            mde_display = f"{m:.{decimals_mde}f}"
            per_display = f"{per_event:.{decimals_per}f}"
            ok_se = (row["se"] == se_display) if se is not None else True
            ok_mde = row["mde"] == mde_display
            ok_per = row["per_event"] == per_display
            ok_close = close(m, 1.96 * se) if se is not None else close(
                m, per_event * (per_event_n_test or n_test))
            add(checks, f"mde.{key}.{block_key}.se", ok_se,
                detail={"row": row["label"], "block": block, "display": row["se"],
                        "expected": se_display, "value": se})
            add(checks, f"mde.{key}.{block_key}.mde", ok_mde,
                detail={"display": row["mde"], "expected": mde_display, "value": m})
            add(checks, f"mde.{key}.{block_key}.per_event", ok_per,
                detail={"display": row["per_event"], "expected": per_display, "value": per_event})
            add(checks, f"mde.{key}.{block_key}.identity", ok_close,
                detail={"mde": m, "one_point_nine_six_se": 1.96 * se if se is not None else None,
                        "per_event_n_test": per_event_n_test or n_test})
            if block == "90" or key in {"jp_fold", "jp_sum", "jp_annual"}:
                delta = math.sqrt(2.0 * m / (per_event_n_test or n_test))
                notes.append({"contrast": label, "block": block, "delta": delta,
                              "percent": 100.0 * delta})

    check_triplet("free", mde["contrasts"][0]["block_days"], "-17.623", 612, "NZ free d")
    check_triplet("zero", nz["zero_d"]["block_days"], "-11.431", 612, "NZ zero d")
    check_triplet("fixed", nz["fixed_null_d"]["block_days"], "-5.006", 612, "NZ fixed null d")
    check_triplet("li", mde["contrasts"][1]["block_days"], "-2.387", 315, "CA LI+ total")
    check_triplet("ep", mde["contrasts"][2]["block_days"], "+69.551", 315, "CA EP+ - EP")
    check_triplet("oc", mde["contrasts"][3]["block_days"], "-51.051", 315, "CA OC - EP")

    # Japan: per-fold and three-fold-sum rows share the fixed 3-year block label.
    for key, auth_key, observed, per_n in (
        ("jp_fold", "per_fold", "-73.737", japan["fold_mean_events"]),
        ("jp_sum", "three_fold_sum", "-221.212", 1277),
        ("jp_annual", "annual_nine_blocks", "-221.212", 1277),
    ):
        block = japan[auth_key]
        m = block["mde95_total_nats"]
        per = block["mde95_nats_per_event"]
        row = groups[key][0]
        add(checks, f"mde.{key}.mde", row["mde"] == f"{m:.2f}",
            detail={"display": row["mde"], "expected": f"{m:.2f}", "value": m})
        add(checks, f"mde.{key}.per_event", row["per_event"] == f"{per:.4f}",
            detail={"display": row["per_event"], "expected": f"{per:.4f}", "value": per})
        delta = math.sqrt(2.0 * m / block["n_events"])
        add(checks, f"mde.{key}.delta", close(delta, block["required_rate_perturbation"]),
            detail={"delta": delta, "authority": block["required_rate_perturbation"]})
        notes.append({"contrast": key, "block": row["block"], "delta": delta,
                      "percent": 100.0 * delta})

    # Observed-total displays and the caption's arithmetic.
    observed_expected = {
        "free": "-17.623", "zero": "-11.431", "fixed": "-5.006",
        "li": "-2.387", "oc": "-51.051",
    }
    for key, expected in observed_expected.items():
        observed = groups[key][0]["observed"].replace("$", "").strip()
        add(checks, f"mde.{key}.observed", observed == expected,
            detail={"display": groups[key][0]["observed"], "expected": expected})
    add(checks, "mde.ep.observed_bound", "+69.551" in groups["ep"][0]["observed"])
    add(checks, "mde.ep.observed_interior", "+77.056" in groups["ep"][0]["observed"])
    jp = mde["japan"]
    add(checks, "mde.japan.three_fold_identity",
        close(3.0 * jp["per_fold"]["se_total_nats"], jp["three_fold_sum"]["se_total_nats"]),
        detail={"three_times_fold_se": 3.0 * jp["per_fold"]["se_total_nats"],
                "sum_se": jp["three_fold_sum"]["se_total_nats"]})
    annual_se = 28.82987572487176
    add(checks, "mde.japan.annual_se",
        close(japan["annual_nine_blocks"]["mde95_total_nats"], 1.96 * annual_se, 1e-9),
        detail={"mde": japan["annual_nine_blocks"]["mde95_total_nats"],
                "one_point_nine_six_times_28_8299": 1.96 * annual_se})
    add(checks, "mde.caption.per_event_definition",
        "per-event values divide by $N_{\\rm test}$" in text(TEX["mde"]))
    add(checks, "mde.caption.rounding_disclosure",
        "rounded independently" in text(TEX["mde"]))

    return component(
        "slice7_mde_table_audit_v1",
        "Recompute every displayed cell of Table tab:mde from mde_expanded.json, "
        "nz_trend_controls.json and japan_mde.json, including the split New Zealand "
        "free/zero/fixed rows and the fractional perturbations.",
        checks,
        {"rows": len(rows), "contrast_groups": len({r["label"] for r in rows}),
         "block_rows": len(rows), "delta_rows": len(notes)},
        notes,
    )


def audit_synthesis() -> dict:
    checks, notes = [], []
    mde = read(AUTH["mde"])
    nz = read(AUTH["nz"])["full_grid"]["pooled"]
    nz_totals = read(AUTH["nz_totals"])
    japan = read(AUTH["japan"])["repaired"]
    s8 = read(AUTH["s8"])
    s8_ref = read(ROOT / "validation/live_results/referee_remediation_20261113/s8_oracle_decomposition.json")
    ablation = read(AUTH["ablation"])
    sigma0 = read(AUTH["sigma0"])
    vis = read(AUTH["visibility"])
    joint = read(AUTH["joint"])
    s8mod = read(AUTH["s8mod"])
    doc = {key: text(path) for key, path in TEX.items()}

    def canonical(cid: str, display: str, docs: tuple[str, ...], value=None,
                  decimals: int | None = None, note: str | None = None):
        ok = all(contains(doc[d], display) for d in docs)
        detail = {"display": display, "documents": list(docs)}
        if value is not None and decimals is not None:
            ok = ok and display_ok(value, display, decimals)
            detail.update({"value": value, "decimals": decimals})
        if note:
            detail["note"] = note
        add(checks, f"synthesis.{cid}", ok, **detail)

    # Abstract: Slice 3 New Zealand trend controls and own-MDE arithmetic.
    ft = nz_totals["fold1"]
    free_total = nz_totals["controls"]["free_d"]["totals"]["delta_joint"]
    free_fold1 = ft["free_d"]["delta_joint"]
    zero = nz_totals["controls"]["zero_d"]["totals"]["delta_joint"]
    fixed = nz_totals["controls"]["fixed_null_d"]["totals"]["delta_joint"]
    canonical("nz_total", "17.62", ("abstract",), value=abs(free_total), decimals=2)
    canonical("nz_fold1", "16.52", ("abstract",), value=abs(free_fold1), decimals=2)
    canonical("nz_fold1_fraction", "93.7", ("abstract",),
              value=100.0 * abs(free_fold1) / abs(free_total), decimals=1)
    canonical("nz_zero", "11.43", ("abstract",), value=abs(zero), decimals=2)
    canonical("nz_fixed", "5.01", ("abstract",), value=abs(fixed), decimals=2)
    canonical("nz_zero_fold1", "8.50", ("abstract",),
              value=abs(ft["zero_d"]["delta_joint"]), decimals=2)
    canonical("nz_fixed_fold1", "4.56", ("abstract",),
              value=abs(ft["fixed_null_d"]["delta_joint"]), decimals=2)
    canonical("nz_fixed_se90", "1.396", ("abstract",),
              value=nz["fixed_null_d"]["block_days"]["90"]["se_total_nats"], decimals=3)
    canonical("nz_fixed_mde90", "2.735", ("abstract",),
              value=nz["fixed_null_d"]["block_days"]["90"]["mde95_total_nats"], decimals=3)
    canonical("nz_fixed_z", "3.59", ("abstract",),
              value=abs(nz["fixed_null_d"]["block_days"]["90"]["z"]), decimals=2)
    canonical("nz_fixed_mde180", "2.786", ("abstract",),
              value=nz["fixed_null_d"]["block_days"]["180"]["mde95_total_nats"], decimals=3)
    canonical("nz_fixed_mde365", "3.038", ("abstract",),
              value=nz["fixed_null_d"]["block_days"]["365"]["mde95_total_nats"], decimals=3)
    canonical("nz_zero_se90", "2.764", ("abstract",),
              value=nz["zero_d"]["block_days"]["90"]["se_total_nats"], decimals=3)
    canonical("nz_zero_mde90", "5.417", ("abstract",),
              value=nz["zero_d"]["block_days"]["90"]["mde95_total_nats"], decimals=3)
    canonical("nz_zero_z", "4.14", ("abstract",),
              value=abs(nz["zero_d"]["block_days"]["90"]["z"]), decimals=2)

    # Abstract: Slice 5 EP+ synthesis.
    clean = ablation["clean_ablation"]
    canonical("ep_total", "69.55", ("abstract",),
              value=clean["totals"]["A8"], decimals=2)
    canonical("ep_shapley_closure", "69.551", ("abstract",),
              value=clean["closure_A8_minus_A0"], decimals=3)
    canonical("ep_scaling", "31.67", ("abstract",),
              value=clean["shapley"]["scaling"], decimals=2)
    canonical("ep_declustering", "27.60", ("abstract",),
              value=clean["shapley"]["declustering"], decimals=2)
    canonical("ep_joint", "10.24", ("abstract",),
              value=clean["shapley"]["joint_fit"] if "joint_fit" in clean["shapley"] else clean["joint_fit"],
              decimals=2)
    canonical("ep_normalization", "0.04", ("abstract",),
              value=clean["shapley"]["normalization"], decimals=2)
    canonical("ep_relaxed_plane", "77.06", ("abstract",),
              value=sigma0["relaxed"]["plane"]["total_gain"], decimals=2)
    canonical("ep_relaxed_frozen", "78.58", ("abstract",),
              value=sigma0["frozen"]["plane"]["total_gain"], decimals=2)
    canonical("ep_relaxed_rect", "78.52", ("abstract",),
              value=sigma0["frozen"]["rect"]["total_gain"], decimals=2)
    canonical("ep_interior_lo", "0.82", ("abstract",), value=0.8232978172578266, decimals=2)
    canonical("ep_interior_hi", "0.84", ("abstract",), value=0.839, decimals=2,
              note="Rounding target for the reported 0.821--0.839 km interval.")

    # Abstract and Chapter 14: Slice 6 S8 oracle synthesis.
    sign = s8["sign_correction"]
    stats = s8["archived_stats"]
    canonical("s8_fixed", "16.43", ("abstract",), value=stats["oracle_gain_vs_fixed"]["mean"], decimals=2)
    canonical("s8_intercept", "14.54", ("abstract",), value=stats["oracle_gain_vs_intercept"]["mean"], decimals=2)
    canonical("s8_joint", "18.11", ("abstract",), value=stats["oracle_gain_vs_joint_null"]["mean"], decimals=2)
    canonical("s8_mcse", "4.18", ("abstract",), value=stats["oracle_gain_vs_joint_null"]["mcse"], decimals=2)
    canonical("s8_sign", "3.571", ("abstract",), value=sign["mean_nats"], decimals=3)
    canonical("s8_seed", "75.278", ("abstract",), value=sign["seed_410840"]["contrast_value"], decimals=3)
    canonical("s8_other_mean", "0.203", ("abstract",), value=abs(sign["other_seed_mean"]), decimals=3)
    canonical("s8_median", "1.683", ("abstract",), value=abs(sign["median"]), decimals=3)
    canonical("s8_partial_a", "3.13", ("abstract",), value=s8["partial_oracle_a"]["gain_vs_joint_null"]["mean"], decimals=2)
    canonical("s8_partial_b", "2.824", ("abstract",), value=s8["partial_oracle_b"]["gain_vs_joint_null"]["mean"], decimals=3)
    canonical("s8_partial_b_median", "5.903", ("abstract",), value=s8["partial_oracle_b"]["gain_vs_joint_null"]["median"], decimals=3)
    canonical("s8_partial_c", "6.513", ("abstract",), value=abs(s8["partial_oracle_c"]["loss_vs_true"]["mean"]), decimals=3)
    canonical("s8_partial_c_median", "3.131", ("abstract",), value=abs(s8["partial_oracle_c"]["loss_vs_true"]["median"]), decimals=3)
    canonical("s8_fitted_mean", "0.929", ("abstract",), value=s8_ref["fitted_eta"]["mean"], decimals=3)
    canonical("s8_fitted_min", "0.042", ("abstract",), value=s8_ref["fitted_eta"]["minimum"], decimals=3)
    canonical("s8_fitted_max", "4.000", ("abstract",), value=s8_ref["fitted_eta"]["maximum"], decimals=3)
    canonical("s8_loss_fraction", "98.4", ("abstract",),
              value=100.0 * s8_ref["estimation_loss_fraction_of_oracle"], decimals=1)

    # Abstract and Chapter 14: Slice 7 contrast-specific MDE values.
    for cid, display, docs, raw in (
        ("mde_nz_free", "9.24", ("abstract",),
         mde["contrasts"][0]["block_days"]["90"]["mde95_total_nats"]),
        ("mde_nz_zero", "5.42", ("abstract",),
         nz["zero_d"]["block_days"]["90"]["mde95_total_nats"]),
        ("mde_nz_fixed", "2.74", ("abstract",),
         nz["fixed_null_d"]["block_days"]["90"]["mde95_total_nats"]),
        ("mde_ca_li", "3.82", ("abstract",),
         mde["contrasts"][1]["block_days"]["90"]["mde95_total_nats"]),
        ("mde_ca_ep", "48.30", ("abstract",),
         mde["contrasts"][2]["block_days"]["90"]["mde95_total_nats"]),
        ("mde_ca_oc", "43.35", ("abstract",),
         mde["contrasts"][3]["block_days"]["90"]["mde95_total_nats"]),
        ("mde_jp_sum", "47.94", ("abstract",),
         japan["three_fold_sum"]["mde95_total_nats"]),
        ("mde_jp_fold", "15.98", ("abstract",),
         japan["per_fold"]["mde95_total_nats"]),
        ("mde_jp_annual", "56.51", ("mde",),
         japan["annual_nine_blocks"]["mde95_total_nats"]),
    ):
        canonical(cid, display, docs, value=raw, decimals=2)

    # Introduction: completed joint controls and historical controls.
    canonical("intro_joint_imm", "10.3701", ("introduction",),
              value=abs(joint["summary"][6]["mean_gain"]), decimals=4)
    canonical("intro_joint_total", "1.2607", ("introduction",),
              value=abs(joint["summary"][18]["mean_gain"]), decimals=4)
    canonical("intro_joint_imm_wins", "10/20", ("introduction",))
    canonical("intro_joint_total_wins", "8/20", ("introduction",))
    canonical("intro_mod_reject", "27.2", ("introduction",),
              value=100.0 * s8mod["summary"]["generation"]["rejected_fraction"], decimals=1)
    canonical("intro_mod_events", "94.7", ("introduction",),
              value=s8mod["summary"]["generation"]["mean_test_events"], decimals=1)
    canonical("intro_mod_mean", "0.2941", ("introduction",),
              value=s8mod["summary"]["mean_gain"], decimals=4)
    canonical("intro_mod_wins", "13/20", ("introduction",))

    # Chapter 14: synthesis values.
    canonical("disc_ep_total", "69.55", ("discussion",), value=clean["totals"]["A8"], decimals=2)
    canonical("disc_relaxed", "77.06", ("discussion",),
              value=sigma0["relaxed"]["plane"]["total_gain"], decimals=2)
    canonical("disc_frozen", "78.58", ("discussion",),
              value=sigma0["frozen"]["plane"]["total_gain"], decimals=2)
    canonical("disc_scale_lo", "0.82", ("discussion",), value=0.8232978172578266, decimals=2)
    canonical("disc_scale_hi", "0.84", ("discussion",), value=0.839, decimals=2)
    canonical("disc_195_modes", "195", ("discussion",))
    canonical("disc_61_modes", "61", ("discussion",))

    # Appendices: custody and audit counts.
    for cid, display in (
        ("app_1999", "1,999"), ("app_3998", "3,998"), ("app_150", "150"),
        ("app_300", "300"), ("app_477", "477"), ("app_411", "411"),
        ("app_30", "30"), ("app_90", "90"), ("app_45", "45"),
        ("app_18", "18"), ("app_913", "913"),
    ):
        canonical(cid, display, ("appendices",))

    # Slice 1 one-event visibility correction, cited in the abstract and Ch 4.
    one = vis["one_event_single_parent"]
    canonical("vis_0_10", "1.53", ("abstract",), value=1000.0 * one["clipped_bounds"]["0.1"], decimals=2,
              note="Displayed as 1.53 x 10^-3.")
    canonical("vis_0_178", "0.00423", ("visibility",), value=one["clipped_bounds"]["0.178"], decimals=5)
    canonical("vis_1_65", "0.1867", ("abstract", "visibility"), value=one["clipped_bounds"]["1.65"], decimals=4)
    canonical("vis_4", "0.7884", ("abstract",), value=one["clipped_bounds"]["4.0"], decimals=4)
    canonical("vis_threshold", "4.64", ("abstract", "visibility"), value=one["eta_clipped_threshold"], decimals=2)

    # Stale or withdrawn reader tokens must not reappear.
    stale = ("0.10424", "12.2504", "below the 9.24", "9.24-nat 90-day",
             "much larger attenuation", "not the much larger")
    for token in stale:
        present = {key: token in value for key, value in doc.items()}
        add(checks, f"synthesis.stale.{re.sub(r'[^a-z0-9]+', '_', token)}",
            not any(present.values()), detail=present)

    # Every enumerated claim bound to the five target sources must reconcile.
    vc = load_verify_claims()
    receipt, ledgers, display_checks = vc.verify_ledgers(ROOT)
    target_paths = {f"paper/source/{relative}" for relative in TARGET_TEX}
    target_labels = set(TARGET_TEX)
    ledger = read(LEDGER)
    expected_target_ids = {
        c["id"] for c in ledger["claims"]
        if c.get("ledger_role") == "manuscript_binding"
        and set(c.get("final_display_locations", [])) & target_labels
    }
    target_claims = [c for c in display_checks
                     if set(c.get("source_files", [])) & target_paths]
    add(checks, "synthesis.claim_ledger_receipt_passed", receipt["passed"],
        detail={"failures": receipt["failures"][:10]})
    add(checks, "synthesis.claim_ledger_target_count",
        len(target_claims) == len(expected_target_ids),
        detail={"target_claims": len(target_claims),
                "expected": len(expected_target_ids)})
    add(checks, "synthesis.claim_ledger_target_present",
        all(c["present"] for c in target_claims),
        detail={"missing": [c["id"] for c in target_claims if not c["present"]][:20]})
    per_file = {}
    for target in TARGET_TEX:
        prefixed = f"paper/source/{target}"
        per_file[target] = sum(1 for c in target_claims if prefixed in c.get("source_files", []))
    notes.append({"claim_bindings_by_file": per_file,
                  "claim_receipt_counts": receipt["counts"]})
    return component(
        "slice7_synthesis_consistency_v1",
        "Cross-check canonical numbers in the abstract, Chapter 1, Chapter 14, "
        "appendices and the Slice 1 visibility statement against the bound "
        "authorities, and verify every enumerated claim on those sources.",
        checks,
        {"canonical_checks": len([c for c in checks if c["id"].startswith("synthesis.")]),
         "target_claims": len(target_claims), "claims_by_file": per_file},
        notes,
    )


def audit_readers() -> dict:
    checks, notes = [], []
    readme = text(READERS["README"])
    reviewer = text(READERS["reviewer"])
    guide = text(READERS["companion"])
    metadata = read(READERS["metadata"])
    findings = text(READERS["findings"])
    site_findings = text(READERS["site_findings"]) if READERS["site_findings"].is_file() else ""
    site_data = text(READERS["site_data"]) if READERS["site_data"].is_file() else ""
    site_index = text(ROOT / "website/site/index.html")
    site_documents = read(ROOT / "website/site/documents.json")

    add(checks, "readers.readme_own_mde",
        contains(readme, "1.83 times its own 2.74-nat 90-day minimum detectable effect")
        and contains(readme, "5.42-nat"))
    add(checks, "readers.reviewer_audits",
        contains(reviewer, "Slices 1--7")
        and contains(reviewer, "Slice 7 entry covers cross-slice synthesis"))
    add(checks, "readers.companion_split",
        contains(guide, "5.42 nats with zero trend")
        and contains(guide, "2.74 nats with fixed null trend")
        and contains(guide, "9.24 nats"))
    add(checks, "readers.findings_own_mde",
        contains(findings, "1.83 times its own 2.74-nat 90-day MDE")
        and contains(findings, "5.42-nat"))
    add(checks, "readers.site_findings_sync",
        contains(site_findings, "1.83 times its own 2.74-nat 90-day MDE")
        and contains(site_findings, "5.42-nat") if site_findings else False,
        detail={"site_findings_present": bool(site_findings)})
    stale = ("below the 9.24", "9.24-nat 90-day", "much larger attenuation", "0.10424")
    for name, value in (("readme", readme), ("reviewer", reviewer), ("companion", guide),
                        ("findings", findings), ("site_findings", site_findings),
                        ("site_data", site_data)):
        present = {token: token in value for token in stale}
        add(checks, f"readers.stale.{name}", not any(present.values()), detail=present)

    pdf = ROOT / "paper/manuscript_unified.pdf"
    add(checks, "readers.pdf_hash", metadata["document"]["sha256"] == sha256(pdf),
        detail={"metadata": metadata["document"]["sha256"], "actual": sha256(pdf)})
    try:
        import pymupdf
        with pymupdf.open(pdf) as document:
            pages = len(document)
    except Exception as exc:
        pages = None
        notes.append({"pdf_page_count_error": str(exc)})
    add(checks, "readers.pdf_pages", pages == metadata["document"]["pages"],
        detail={"metadata": metadata["document"]["pages"], "actual": pages})
    add(checks, "readers.release_note_split",
        contains(metadata.get("release_note", ""), "separate New Zealand free-, zero- and fixed-null-trend rows"))
    expected_title = "Diagnostic Exponential Rate Attenuation in Spatial\u2013Temporal Earthquake Models"
    add(checks, "readers.title_encoding",
        metadata["document"]["title"] == expected_title
        and site_documents.get("manuscript_title") == expected_title
        and expected_title in site_index
        and "\u00e2\u20ac\u201c" not in site_index,
        detail={"metadata": metadata["document"]["title"],
                "documents": site_documents.get("manuscript_title")})
    add(checks, "readers.findings_data_present", bool(site_data))
    return component(
        "slice7_reader_surfaces_v1",
        "Audit README, reviewer guide, companion JSON, website metadata and the "
        "generated findings page/data for canonical MDE language, stale phrases, "
        "PDF identity and cross-surface synchronization.",
        checks,
        {"surfaces": len(READERS), "stale_tokens": len(stale), "claims": len(checks)},
        notes,
    )


def load_verify_claims():
    spec = importlib.util.spec_from_file_location("_slice7_verify_claims", ROOT / "scripts/verify_claims.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_verify_repository():
    spec = importlib.util.spec_from_file_location("_slice7_verify_repository", ROOT / "scripts/verify_repository.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def audit_custody() -> dict:
    checks, notes = [], []
    vc = load_verify_claims()
    compiled = vc.compiled_tex_sources(ROOT)
    compiled_relative = sorted(p.relative_to(ROOT).as_posix() for p in compiled)
    add(checks, "custody.compiled_count", len(compiled_relative) == 42,
        detail={"compiled": len(compiled_relative)})

    ledger = read(LEDGER)
    receipt = read(RECEIPT)
    custody_hashes = ledger["display_custody"]["source_hashes"]
    add(checks, "custody.ledger_source_roster", set(custody_hashes) == set(compiled_relative),
        detail={"ledger": len(custody_hashes), "compiled": len(compiled_relative),
                "missing": sorted(set(compiled_relative) - set(custody_hashes))[:10],
                "extra": sorted(set(custody_hashes) - set(compiled_relative))[:10]})
    ledger_hash_errors = [relative for relative, digest in custody_hashes.items()
                          if not (ROOT / relative).is_file()
                          or sha256(ROOT / relative) != digest]
    add(checks, "custody.ledger_source_hashes", not ledger_hash_errors,
        detail={"errors": ledger_hash_errors[:10]})

    receipt_hashes = receipt["source_hashes"]
    add(checks, "custody.receipt_source_roster", set(receipt_hashes) == set(compiled_relative),
        detail={"receipt": len(receipt_hashes), "compiled": len(compiled_relative)})
    receipt_hash_errors = [relative for relative, digest in receipt_hashes.items()
                           if not (ROOT / relative).is_file()
                           or sha256(ROOT / relative) != digest]
    add(checks, "custody.receipt_source_hashes", not receipt_hash_errors,
        detail={"errors": receipt_hash_errors[:10]})
    add(checks, "custody.receipt_passed", receipt["passed"] and receipt["release_ready"],
        detail={"passed": receipt["passed"], "release_ready": receipt["release_ready"]})
    add(checks, "custody.receipt_counts",
        receipt["counts"].get("claims") == 28653
        and receipt["counts"].get("missing_declared_manuscript_displays") == 0,
        detail={"claims": receipt["counts"].get("claims"),
                "missing_displays": receipt["counts"].get("missing_declared_manuscript_displays")})
    add(checks, "custody.display_regression",
        read(DISPLAY_REGRESSION).get("passed") is True)
    add(checks, "custody.claim_ids_unique",
        len({c["id"] for c in ledger["claims"]}) == len(ledger["claims"]),
        detail={"claims": len(ledger["claims"])})
    add(checks, "custody.slice7_claims",
        sum(1 for c in ledger["claims"] if c["id"].startswith("slice7-20261114-")) == 26,
        detail={"slice7_claims": sum(1 for c in ledger["claims"]
                                     if c["id"].startswith("slice7-20261114-"))})

    # Adversarial verifier tests, run in a fresh subprocess.
    test = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests",
         "-p", "test_verify_claims.py", "-v"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    match = re.search(r"Ran (\d+) tests?", test.stdout)
    tests = int(match.group(1)) if match else None
    ok = test.returncode == 0 and bool(re.search(r"^OK\s*$", test.stdout, re.M))
    add(checks, "custody.adversarial_tests", ok,
        detail={"exit_code": test.returncode, "tests": tests,
                "tail": test.stdout.splitlines()[-6:]})
    notes.append({"adversarial_test_output": test.stdout.splitlines()[-25:]})

    # Current payload coverage: membership must match even before the final
    # manifest refresh.  Hash equality is checked separately by the acceptance
    # and final verify_repository run, because this audit is generated before
    # the acceptance record itself joins the manifest.
    vr = load_verify_repository()
    audit_prefix = OUT.relative_to(ROOT).as_posix() + "/"
    actual = {p.relative_to(ROOT).as_posix() for p in vr.payload_files(ROOT)
              if not p.relative_to(ROOT).as_posix().startswith(audit_prefix)}
    manifest = read(MANIFEST)
    expected = {row["path"] for row in manifest["files"]
                if not row["path"].startswith(audit_prefix)}
    add(checks, "custody.manifest_schema", manifest.get("schema") == "repository_payload_v2")
    add(checks, "custody.manifest_coverage", actual == expected,
        detail={"actual": len(actual), "manifest": len(expected),
                "audit_outputs_excluded": 6,
                "missing": sorted(expected - actual)[:10],
                "extra": sorted(actual - expected)[:10]})
    source_errors = vr.source_errors(ROOT)
    add(checks, "custody.repository_source_pins", not source_errors,
        detail={"errors": source_errors[:10]})

    return component(
        "slice7_verifier_custody_v1",
        "Verify compiled-source custody, the 26 additive Slice 7 claim bindings, "
        "the adversarial verifier test bank, and repository manifest/source pins.",
        checks,
        {"compiled_tex": len(compiled_relative), "claims": len(ledger["claims"]),
         "adversarial_tests": tests, "manifest_entries": len(expected),
         "payload_entries": len(actual)},
        notes,
    )


def audit_sealed_integrity() -> dict:
    snapshot = read(SNAPSHOT)
    checks = []
    changed, missing = [], []
    for relative, digest in snapshot["sealed_json"].items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
        elif sha256(path) != digest:
            changed.append(relative)
    add(checks, "sealed.count", snapshot["sealed_json_count"] == EXPECTED_SEALED,
        detail={"count": snapshot["sealed_json_count"], "expected": EXPECTED_SEALED})
    add(checks, "sealed.unchanged", not changed and not missing,
        detail={"changed": changed[:20], "missing": missing[:20],
                "changed_count": len(changed), "missing_count": len(missing)})
    add(checks, "sealed.snapshot_zip", sha256(SNAPSHOT_ZIP) == snapshot["zip_sha256"]
        if "zip_sha256" in snapshot else True)
    return component(
        "slice7_sealed_authority_integrity_v1",
        "Byte-level comparison of every pre-existing JSON authority and live result "
        "against the Slice 7 pre-change snapshot.",
        checks,
        {"snapshot": snapshot["sealed_json_count"], "unchanged":
         snapshot["sealed_json_count"] - len(changed) - len(missing),
         "changed": len(changed), "missing": len(missing),
         "snapshot_sha256": sha256(SNAPSHOT), "prechange_zip_sha256": sha256(SNAPSHOT_ZIP)},
    )


def audit_summary(components: dict[str, dict]) -> dict:
    passed = all(c["passed"] for c in components.values())
    return {
        "schema": "slice7_audit_summary_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": "102a78a",
        "scope": (
            "Vertical Triad Slice 7: cross-slice synthesis in the abstract, Chapter 1, "
            "Chapter 14 and appendices; the split New Zealand free/zero/fixed MDE table; "
            "reader-facing README, reviewer guide, companion and website synchronization; "
            "and claim-ledger / repository custody."
        ),
        "passed": passed,
        "components": {key: value["passed"] for key, value in components.items()},
        "counts": {key: value["counts"] for key, value in components.items()},
        "defects_and_repairs": [
            {
                "id": "slice7-nz-mde-row-split",
                "file": "paper/source/chapters/14_power_and_mde.tex",
                "locator": "Table tab:mde, rows 1-10",
                "finding": (
                    "The single free-d New Zealand row carried the zero-d and fixed-null-d "
                    "observed totals while displaying only the free-trend MDE scale, contradicting "
                    "the repaired prose and inviting a cross-arm comparison."
                ),
                "repair": (
                    "Split the row into free-, zero- and fixed-null-trend rows with their own "
                    "observed totals, 90/180/365-day block SEs, contrast-specific MDEs and "
                    "per-event MDEs; added a caption warning against comparing the fixed-null loss "
                    "with the free-trend MDE."
                ),
                "status": "fixed",
            },
            {
                "id": "slice7-attenuation-mde-direction",
                "file": "paper/source/chapters/14_power_and_mde.tex",
                "locator": "line 2",
                "finding": (
                    "The prose called the California LI+ attenuation MDE 'much larger' than the "
                    "EP+ MDE.  The 90-day LI+ MDE is 3.82 nats and the EP+ MDE is 48.30 nats, so "
                    "the inequality was inverted."
                ),
                "repair": (
                    "The text now compares the EP+ gain with its own 48.30-nat MDE and the "
                    "-2.39-nat LI+ contrast with its own much smaller 3.82-nat MDE."
                ),
                "status": "fixed",
            },
            {
                "id": "slice7-se-versus-mde-label",
                "file": "paper/source/chapters/14_power_and_mde.tex",
                "locator": "line 33",
                "finding": (
                    "The 0.0077 and 0.0782 nat-per-event figures were left unlabelled beside the "
                    "table's per-event MDE column (0.0151 and 0.1533), so a reader could read the "
                    "factor-1.96 difference as an arithmetic error.  The fractional-perturbation "
                    "sentence also omitted the California LI+ total and OC-EP contrasts."
                ),
                "repair": (
                    "Identified 0.0077=4.712/612 and 0.0782=24.644/315 as SE90/N_test, gave the "
                    "corresponding MDE95/N_test values 0.0151 and 0.1533, added the LI+ and OC-EP "
                    "delta ranges, and corrected the zero-365 (13.8%) and fixed-180 (9.5%) "
                    "one-decimal roundings."
                ),
                "status": "fixed",
            },
            {
                "id": "slice7-reader-stale-mde",
                "file": "README.md; website/findings.html; website/site/findings.html; companion/guide_content.json",
                "locator": "New Zealand trend-control paragraph / detection-scale note",
                "finding": (
                    "README and the findings explorer still said the fixed-null loss was 'below the "
                    "9.24-nat 90-day scale', the exact pre-F1 comparison that the manuscript "
                    "withdrew.  The companion guide listed only the free-trend New Zealand scale."
                ),
                "repair": (
                    "Replaced the stale phrase with the own-contrast 2.74-nat MDE and 3.59-SE "
                    "statement, added the zero-trend 5.42-nat scale to the companion, and refreshed "
                    "the website metadata release note and generated pages."
                ),
                "status": "fixed",
            },
            {
                "id": "slice7-claim-bindings",
                "file": "validation/MASTER_CLAIM_LEDGER.json; scripts/bind_slice7_claims_20261114.py",
                "locator": "display_custody and claims",
                "finding": (
                    "The new zero/fixed MDE cells and the expanded LI+/OC perturbation ranges "
                    "were not enumerated claim bindings; the abstract's zero/fixed MDEs were also "
                    "unbound."
                ),
                "repair": (
                    "Added 26 additive slice7-20261114 bindings, including the abstract locations "
                    "for the 5.42- and 2.74-nat MDEs, then refreshed the compact source hashes and "
                    "display-presence receipts."
                ),
                "status": "fixed",
            },
        ],
        "limitations": [
            "The 90/180/365-day blocks are paired calendar-block summaries; adjacent blocks are dependent, so nominal MDEs are descriptive multi-scale sensitivities rather than calibrated frequentist guarantees.",
            "Table cells are rounded independently from the unrounded block quantities; the displayed product of a rounded SE and 1.96 can differ from the displayed MDE in the last digit.",
            "The audit verifies the enumerated claim bindings and a curated canonical set; it does not re-run the original regional fits or synthetic campaigns.",
            "The Slice 1 tightened visibility display remains documented as withdrawn; the sealed computation is retained for historical identity but is not a current reader-facing claim.",
        ],
    }


def main(argv=None) -> int:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args(argv)
    OUT = args.output.resolve()
    OUT.mkdir(parents=True, exist_ok=False)
    mde = audit_mde_table()
    synthesis = audit_synthesis()
    readers = audit_readers()
    custody = audit_custody()
    sealed = audit_sealed_integrity()
    components = {
        "mde_table": mde,
        "synthesis_consistency": synthesis,
        "reader_surfaces": readers,
        "custody_infrastructure": custody,
        "sealed_authority_integrity": sealed,
    }
    dump("mde_table.json", mde)
    dump("synthesis_consistency.json", synthesis)
    dump("reader_surfaces.json", readers)
    dump("custody_infrastructure.json", custody)
    dump("sealed_authority_integrity.json", sealed)
    summary = audit_summary(components)
    dump("summary.json", summary)
    print(json.dumps({"passed": summary["passed"],
                      "components": summary["components"],
                      "counts": summary["counts"]}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
