"""Write and hash-pin the Pathway 4 protocol before any test-window score.

This script reads only training-side fields of the California interior EP+
state file.  New Zealand and Japan test arrays are hashed as inputs but no
score is evaluated here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C


def _git_head():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def _sealed_manifest():
    paths = []
    for base in (ROOT / "validation/authorities", ROOT / "validation/live_results"):
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if "pathway4_confirmatory_20261116" in path.parts:
                continue
            paths.append(path)
    manifest = C.file_manifest(paths)
    body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return dict(files=len(paths), sha256=C.sha256_bytes(body))


def _ca_state_projection():
    d = C.read_json(C.CA_INTERIOR)
    rows = []
    for fold in range(3):
        row = next(r for r in d["rows"]
                   if r["case"] == f"california_fold_{fold}"
                   and r["normalization"] == "plane")
        rows.append(dict(
            case=row["case"], normalization=row["normalization"],
            parameters=[float(v) for v in row["parameters"][:8]],
            background_weights=[float(v) for v in row["background_weights"]],
            training_nll=float(row["training_nll"]),
            declustering=row["declustering"],
        ))
    body = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return dict(rows=rows, sha256=C.sha256_bytes(body))


def build_protocol():
    sources = {}
    for path in sorted((ROOT / "experiments/pathway4_confirmatory_transfer").glob("*.py")):
        sources[path.name] = C.sha256(path)
    ca_state = _ca_state_projection()
    protocol = {
        "schema": "pathway4_frozen_protocol_v1",
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "baseline_commit": _git_head(),
        "isolated_code": "experiments/pathway4_confirmatory_transfer/",
        "isolated_results": "validation/live_results/pathway4_confirmatory_20261116/",
        "guardrails": {
            "sealed_authorities_byte_identical": True,
            "protocol_precedes_every_nz_or_japan_test_score": True,
            "no_parameter_or_bound_changed_after_test_inspection": True,
            "common_measure_parity_target": 1e-8,
            "single_pass_fit_then_seal_then_score": True,
        },
        "sources": sources,
        "inputs": {
            "s03_registry_sha256": C.sha256(C.S03_REGISTRY),
            "s03_archive_sha256": C.sha256(C.S03_ARCHIVE),
            "jma_registry_sha256": C.sha256(C.JMA_REGISTRY),
            "jma_archive_sha256": C.sha256(C.JMA_ARCHIVE),
            "california_registry_sha256": C.sha256(C.CA_REGISTRY),
            "california_archive_sha256": C.sha256(C.CA_ARCHIVE),
            "california_archive_2_sha256": C.sha256(C.CA_ARCHIVE_2),
            "california_interior_state_source": str(
                C.CA_INTERIOR.relative_to(ROOT)).replace("\\", "/"),
            "california_interior_state_sha256": C.sha256(C.CA_INTERIOR),
            "california_training_state_projection_sha256": ca_state["sha256"],
        },
        "baseline_sealed_manifest": _sealed_manifest(),
        "model": {
            "intensity": "exp(a+d*x(t))*b(z) + n*sum_j kappa_j*h(t-t_j)*"
                         "f(z-z_j; sigma_j,q)",
            "trend_clock": "x(t)=2*t/T0-1; T0 is the archived catalogue horizon",
            "background": "five-percent floor plus training immigrant-probability "
                          "weighted elliptical KDE; five declustering steps; "
                          "leave-self-out during training; final weights frozen",
            "temporal_kernel": "h(u)=(p-1)/c*(1+u/c)**-p",
            "spatial_kernel": "inverse power (1+r^2/sigma^2)**-q with "
                              "sigma_j=sigma0*exp(alpha_s*(M_j-M0))",
            "normalizations": {
                "plane": "full-plane density; exact in-domain mass retained in "
                         "the compensator",
                "rect": "nine-cell union-normalised density; compensator "
                        "integrates each parent to one",
            },
            "parameter_names": C.PARAM_NAMES,
            "bounds": {
                "a": [-12.0, 0.0], "d": [-2.0, 2.0], "n": [0.0, 0.98],
                "log_c": [-9.210340371976184, 2.995732273553991],
                "p": [1.01, 2.5],
                "log_sigma0": [-2.995732273553991, 4.605170185988092],
                "alpha_s": [0.0, 2.0], "q": [1.05, 3.0],
            },
            "starts": {
                "generic": [-3.5, 0.0, 0.6, -4.605170185988091, 1.15,
                            1.6094379124341003, 0.5, 1.8],
                "diffuse": [-4.0, 0.2, 0.8, -3.912023005428146, 1.2,
                            0.6931471805599453, 0.8, 2.2],
                "region_archived_ep": "the archived EP selected (a,d,n) and "
                                      "temporal/spatial shape, with alpha_s=0",
            },
            "declustering_steps": 5,
            "optimizer": "L-BFGS-B with analytic gradients; multi-start on the "
                         "first training step; the exact nested null is always "
                         "an eligible candidate",
        },
        "arms": {
            "new_zealand": {
                "cohort": "S03 NZ_fold_0/1/2; 203/155/254 = 612 targets",
                "fits": [["plane", "T0"], ["plane", "T1"],
                         ["rect", "T0"], ["rect", "T1"]],
                "background_floor": "uniform 0.05/area (California EP+ recipe)",
                "attenuation": "plane arms only",
            },
            "japan": {
                "cohort": "JMA fold_0/1/2; 469/348/460 = 1,277 targets",
                "fits": [["plane", "T0"], ["plane", "T1"], ["rect", "T1"]],
                "background_floor": "uniform 0.05/area (California EP+ recipe)",
            },
            "attenuation": {
                "baseline_monotone": "mono kernel, (ell0,psi) in "
                                     "{(5,1),(15,5),(50,30)} km/d, "
                                     "gamma=0.75*log(10), one-dimensional eta "
                                     "profile on the frozen null backbone",
                "refined": "ann2 kernel, Wells-Coppersmith "
                           "ell_j=10**(-2.44+0.59*(M0+excess_j)) km, psi=5 d, "
                           "gamma=0.75*log(10), one-dimensional eta profile",
                "eta_bounds": [0.0, 4.0],
                "selection": "exact training eta=0 when the null slope is "
                             "non-positive; otherwise the concave profile root",
                "test_quadrature": "power 16, seeds 20261120 and 20261121",
            },
        },
        "scoring": {
            "components": {
                "P": "sum of log space-time intensity at targets",
                "E": "exact space-time compensator over the test window",
                "timing": "sum(log temporal marginal) - E",
                "location": "P - sum(log temporal marginal)",
                "joint": "P - E + common mark score",
            },
            "common_marks": "archived continuous (NZ/CA) and reported-lattice "
                            "(JMA) mark laws; the common mark score cancels in "
                            "EP+ minus EP/OC contrasts",
            "archived_comparators": {
                "new_zealand": "S03 arm 1 = OC and arm 4 = EP; authority "
                               "validation/authorities/*_m02_s03_nz_*_aggregate.json",
                "japan": "primary_jma/JMA_fold_*/OC/full and EP/full, plus the "
                         "nine annual partitions 2016-2024",
            },
            "contrast": "EP+ minus archived procedure on timing, location and "
                        "joint; positive favours EP+",
        },
        "california_conditional_calibration": {
            "frozen_states": "plane-normalised interior EP+ rows in "
                             "sigma0_relaxation.json; training-side fields only",
            "simulations_per_origin": 999,
            "origins": ["2011", "2016", "2021"],
            "algorithm": "sequential branching: Background.sample immigrant "
                         "thinning, Omori lags, magnitude-scaled inverse-power "
                         "offspring, exponential GR marks",
            "coordinates": ["exposure", "time_event_logsum", "gap_ks",
                            "gap_serial", "spatial_rosenblatt_ks_max",
                            "spatial_rosenblatt_cross_abs",
                            "location_dimensionless_log_mean",
                            "location_dimensionless_log_variance"],
            "pooled_tests": "archived symmetric observed+999 quadratic and "
                            "Fisher-type inclusive upper-rank statistics",
            "spatial_cdf": "exact branch-split line integrals in y and the "
                           "full-plane x-marginal CDF for the left strip; the "
                           "audit records the approximation",
            "archived_reference": "paper/source/chapters/12_s05_completed.tex "
                                  "Table tab:s05-completed",
        },
        "custody": {
            "protocol_sha256": "pinned in frozen_protocol_v1.sha256",
            "fit_seal": "validation/live_results/pathway4_confirmatory_20261116/"
                        "fit_seal.json",
            "audit": "experiments/pathway4_confirmatory_transfer/"
                     "audit_pathway4.py",
            "report": "docs/reviews/pathway4_confirmatory_report_20261116.md",
        },
    }
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=C.PROTOCOL)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("protocol already exists; refusing to overwrite the pin")
    protocol = build_protocol()
    C.write_json(args.output, protocol)
    digest = C.sha256(args.output)
    pin = args.output.with_suffix(".sha256")
    pin.write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(json.dumps(dict(protocol=str(args.output), sha256=digest,
                          sources=len(protocol["sources"]),
                          sealed_files=protocol["baseline_sealed_manifest"]["files"]),
                     indent=2))


if __name__ == "__main__":
    main()
