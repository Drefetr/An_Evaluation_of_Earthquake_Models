#!/usr/bin/env python3
"""Append Pathway 1-4 summary and audit authorities to the public manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation/authority_manifest.json"

ENTRIES = [
    ("validation/live_results/pathway1_annular_20261116/summary.json",
     "Pathway 1 annular attenuation summary",
     ["experiments/pathway1_annular_attenuation/annular.py",
      "experiments/pathway1_annular_attenuation/run_joint.py",
      "experiments/pathway1_annular_attenuation/build_summary.py"]),
    ("validation/live_results/pathway1_annular_20261116/synthetic/summary.json",
     "Pathway 1 synthetic ann2 control-bank summary",
     ["experiments/pathway1_annular_attenuation/synthetic.py",
      "experiments/pathway1_annular_attenuation/run_synthetic.py"]),
    ("validation/live_results/pathway1_annular_20261116/independent_audit.json",
     "Pathway 1 independent computational audit",
     ["experiments/pathway1_annular_attenuation/audit_pathway1.py"]),
    ("validation/live_results/pathway2_trend_controls_20261116/summary.json",
     "Pathway 2 trend parameterisation summary",
     ["experiments/pathway2_trend_parameterization/synthetic.py",
      "experiments/pathway2_trend_parameterization/run_s8.py",
      "experiments/pathway2_trend_parameterization/build_summary.py"]),
    ("validation/live_results/pathway2_trend_controls_20261116/independent_audit.json",
     "Pathway 2 independent computational audit",
     ["experiments/pathway2_trend_parameterization/audit_pathway2.py"]),
    ("validation/live_results/pathway3_low_dim_20261116/summary.json",
     "Pathway 3 low-dimensional attenuation summary",
     ["experiments/pathway3_low_dim_attenuation/estimators.py",
      "experiments/pathway3_low_dim_attenuation/run_s8.py",
      "experiments/pathway3_low_dim_attenuation/build_summary.py"]),
    ("validation/live_results/pathway3_low_dim_20261116/independent_audit.json",
     "Pathway 3 independent computational audit",
     ["experiments/pathway3_low_dim_attenuation/audit_pathway3.py"]),
    ("validation/live_results/pathway4_confirmatory_20261116/summary.json",
     "Pathway 4 single-pass confirmatory transfer summary",
     ["experiments/pathway4_confirmatory_transfer/freeze_protocol.py",
      "experiments/pathway4_confirmatory_transfer/score_nz.py",
      "experiments/pathway4_confirmatory_transfer/score_jma.py",
      "experiments/pathway4_confirmatory_transfer/build_summary.py"]),
    ("validation/live_results/pathway4_confirmatory_20261116/fit_seal.json",
     "Pathway 4 pre-test fit-seal manifest",
     ["experiments/pathway4_confirmatory_transfer/seal_fits.py"]),
    ("validation/live_results/pathway4_confirmatory_20261116/independent_audit.json",
     "Pathway 4 independent computational audit",
     ["experiments/pathway4_confirmatory_transfer/audit_pathway4.py"]),
    ("validation/live_results/pathway4_confirmatory_20261116/nz_score_index.json",
     "Pathway 4 New Zealand score index",
     ["experiments/pathway4_confirmatory_transfer/score_nz.py"]),
    ("validation/live_results/pathway4_confirmatory_20261116/jma_score_index.json",
     "Pathway 4 Japan score index",
     ["experiments/pathway4_confirmatory_transfer/score_jma.py"]),
    ("validation/live_results/pathways_integration_20261117/derived_values.json",
     "Pathway 1-4 additive manuscript arithmetic (differences, ratios and sums)",
     ["scripts/bind_pathways_1_to_4_claims_20261117.py"]),
]


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    existing = {row["bundled_path"] for row in manifest}
    added = []
    for relative, scope, sources in ENTRIES:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit("missing authority: " + relative)
        if relative in existing:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append({
            "bundled_path": relative,
            "sha256": digest,
            "bytes": path.stat().st_size,
            "historical_bundled_path": relative,
            "historical_sha256": digest,
            "original_paths": sources,
            "transformation": "identity; isolated Pathway 1-4 result or audit artifact",
            "scope": scope,
        })
        added.append(relative)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": added, "authorities": len(manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
