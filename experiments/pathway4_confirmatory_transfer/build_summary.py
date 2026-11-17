"""Build the machine-readable Pathway 4 summary from sealed scores."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C
from experiments.pathway4_confirmatory_transfer import data

COMPONENTS = ("timing", "location", "joint")


def _sum(rows, key):
    out = {c: 0.0 for c in COMPONENTS}
    for row in rows:
        if key in row and row[key] is not None:
            for c in COMPONENTS:
                out[c] += float(row[key][c])
    return out


def _arm_rows(rows, norm, trend):
    return [r for r in rows if r["normalization"] == norm and r["trend"] == trend]


def build_nz():
    rows = C.read_json(C.OUT / "nz_score_index.json")["rows"]
    arms = {}
    for norm, trend in (("plane", "T0"), ("plane", "T1"),
                        ("rect", "T0"), ("rect", "T1")):
        sub = _arm_rows(rows, norm, trend)
        arms[f"{norm}_{trend}"] = dict(
            attenuation_available=any(r.get("refined") for r in sub),
            folds=[dict(fold=r["fold"], n_test=r.get("n_test"),
                        ep_minus_ep=r["ep_minus_ep"],
                        ep_minus_oc=r["ep_minus_oc"],
                        refined=r.get("refined"),
                        mono=r.get("mono")) for r in sub],
            totals=dict(
                ep_minus_ep=_sum(sub, "ep_minus_ep"),
                ep_minus_oc=_sum(sub, "ep_minus_oc"),
                refined_minus_ep={c: sum(
                    float(r["refined"]["minus_ep"][c])
                    for r in sub if r.get("refined")) for c in COMPONENTS},
                refined_minus_oc={c: sum(
                    float(r["refined"]["minus_oc"][c])
                    for r in sub if r.get("refined")) for c in COMPONENTS},
                mono_minus_ep={c: sum(
                    float(r["mono"]["minus_ep"][c])
                    for r in sub if r.get("mono")) for c in COMPONENTS},
                mono_minus_oc={c: sum(
                    float(r["mono"]["minus_oc"][c])
                    for r in sub if r.get("mono")) for c in COMPONENTS},
            ),
        )
    archived = {f"NZ_fold_{f}": data.nz_archived_comparators(f) for f in range(3)}
    return dict(targets=612, folds=3, arms=arms, archived=archived)


def build_jma():
    rows = C.read_json(C.OUT / "jma_score_index.json")["rows"]
    arms = {}
    for norm, trend in (("plane", "T0"), ("plane", "T1"), ("rect", "T1")):
        sub = _arm_rows(rows, norm, trend)
        blocks = {}
        for r in sub:
            for year, entry in r.get("blocks", {}).items():
                blocks.setdefault(year, []).append(entry)
        annual = {}
        for year, entries in sorted(blocks.items()):
            annual[year] = dict(
                n_arms=len(entries),
                n_test=int(entries[0]["n_test"]),
                ep_minus_ep=_sum(entries, "ep_minus_ep"),
                ep_minus_oc=_sum(entries, "ep_minus_oc"),
                refined_minus_ep={c: sum(
                    float(e["refined_attenuation"]["minus_ep"][c])
                    for e in entries if e.get("refined_attenuation"))
                    for c in COMPONENTS},
                refined_minus_oc={c: sum(
                    float(e["refined_attenuation"]["minus_oc"][c])
                    for e in entries if e.get("refined_attenuation"))
                    for c in COMPONENTS},
            )
        arms[f"{norm}_{trend}"] = dict(
            attenuation_available=any(r.get("refined") for r in sub),
            folds=[dict(fold=r["fold"], n_test=r.get("n_test"),
                        ep_minus_ep=r["ep_minus_ep"],
                        ep_minus_oc=r["ep_minus_oc"],
                        refined=r.get("refined"),
                        mono=r.get("mono")) for r in sub],
            totals=dict(
                ep_minus_ep=_sum(sub, "ep_minus_ep"),
                ep_minus_oc=_sum(sub, "ep_minus_oc"),
                refined_minus_ep={c: sum(
                    float(r["refined"]["minus_ep"][c])
                    for r in sub if r.get("refined")) for c in COMPONENTS},
                refined_minus_oc={c: sum(
                    float(r["refined"]["minus_oc"][c])
                    for r in sub if r.get("refined")) for c in COMPONENTS},
                mono_minus_ep={c: sum(
                    float(r["mono"]["minus_ep"][c])
                    for r in sub if r.get("mono")) for c in COMPONENTS},
                mono_minus_oc={c: sum(
                    float(r["mono"]["minus_oc"][c])
                    for r in sub if r.get("mono")) for c in COMPONENTS},
            ),
            annual_blocks=annual,
            annual_totals=dict(
                ep_minus_ep={c: sum(v["ep_minus_ep"][c]
                                    for v in annual.values()) for c in COMPONENTS},
                ep_minus_oc={c: sum(v["ep_minus_oc"][c]
                                    for v in annual.values()) for c in COMPONENTS},
                refined_minus_ep={c: sum(v["refined_minus_ep"][c]
                                         for v in annual.values()) for c in COMPONENTS},
            ),
        )
    archived = {f"JMA_fold_{f}": data.jma_archived(f)["full"]
                for f in range(3)}
    return dict(targets=1277, folds=3, annual_blocks=9, arms=arms,
                archived=archived)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=C.OUT / "summary.json")
    args = parser.parse_args()
    audit_path = C.OUT / "independent_audit.json"
    audit = C.read_json(audit_path) if audit_path.exists() else None
    ca_path = C.OUT / "california" / "summary.json"
    california = C.read_json(ca_path) if ca_path.exists() else None
    seal = C.read_json(C.OUT / "fit_seal.json")
    protocol = C.read_json(C.PROTOCOL)
    summary = dict(
        schema="pathway4_confirmatory_summary_v1",
        generated_on="2026-11-17",
        isolated_paths=dict(
            code="experiments/pathway4_confirmatory_transfer/",
            results="validation/live_results/pathway4_confirmatory_20261116/",
            report="docs/reviews/pathway4_confirmatory_report_20261116.md"),
        baseline_commit=protocol.get("baseline_commit"),
        protocol_sha256=seal.get("protocol_sha256"),
        fit_seal_manifest_sha256=seal.get("manifest_sha256"),
        new_zealand=build_nz(),
        japan=build_jma(),
        california=california,
        attenuation_scope=dict(
            confirmatory="refined ann2/Wells-Coppersmith arm with its own "
                         "self-normalised importance field",
            mono_baseline="sensitivity only; the ann2 importance field has "
                          "lighter tails than the mono kernel, so the mono "
                          "held-out contrast is not used in the confirmatory "
                          "conclusion",
        ),
        audit=None if audit is None else dict(
            passed=audit.get("passed"),
            checks=[dict(name=c["name"], passed=c["passed"])
                    for c in audit.get("checks", [])]),
        passed=bool(audit and audit.get("passed") and california is not None),
    )
    C.write_json(args.output, summary)
    print(json.dumps(dict(passed=summary["passed"],
                          protocol_sha256=summary["protocol_sha256"]), indent=2))


if __name__ == "__main__":
    main()
