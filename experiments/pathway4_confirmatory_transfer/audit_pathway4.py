"""Independent audit of the Pathway 4 single-pass confirmation cohort."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C, data
from experiments.pathway4_confirmatory_transfer.fit import BOUNDS, FREE_ORDER
from experiments.pathway4_confirmatory_transfer.geometry import Region
from experiments.pathway4_confirmatory_transfer.model import EPModel
from experiments.pathway4_confirmatory_transfer import scoring as S
from reproduction.regional.scoring_sources.original_full84 import _mass_order


def _array_sha(a):
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def _check(name, passed, detail=None):
    return dict(name=name, passed=bool(passed), detail=detail or {})


def _sealed_manifest():
    snapshot_path = ROOT / "validation/pathways_prechange_snapshot_20261117.json"
    snapshot = C.read_json(snapshot_path)
    expected = dict(snapshot["baseline_782"])
    for relative in snapshot["slice7_audit_additions"]:
        expected[relative] = snapshot["sealed_json"][relative]
    missing, changed, current = [], [], {}
    for relative, digest in expected.items():
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        actual = C.sha256(path)
        current[relative] = actual
        if actual != digest:
            changed.append(relative)
    body = json.dumps(current, sort_keys=True, separators=(",", ":")).encode()
    return dict(files=len(expected), verified=len(current), missing=missing,
                changed=changed, sha256=C.sha256_bytes(body),
                snapshot_sha256=C.sha256(snapshot_path))


def audit_common_measures():
    detail = {}
    worst = 0.0
    # ---- New Zealand: parent/event/fertility/domain identity vs cache pins
    for fold in range(3):
        rows, a, m = data.load_nz_cache(fold)
        pins = m["array_sha256"]
        checks = {
            "parent_time": a["parent_time"], "parent_excess": a["parent_excess"],
            "parent_xy": a["parent_xy"], "parent_fertility": a["parent_fertility"],
            "event_time": a["event_time"], "event_excess": a["event_excess"],
            "event_xy": a["event_xy"], "event_cell": a["event_cell"],
            "rectangles": a["rectangles"], "reference_pi": a["reference_pi"],
            "kde_training_xy": a["kde_training_xy"],
        }
        fold_detail = {}
        for key, value in checks.items():
            if key not in pins:
                continue
            ok = _array_sha(value) == pins[key]
            fold_detail[key] = ok
            if not ok:
                worst = max(worst, 1.0)
        detail[f"NZ_fold_{fold}"] = fold_detail
    # ---- Japan: feature identity vs the archived state metadata
    cat = data.load_jma_catalogue_arrays()
    for fold in range(3):
        state = data.load_jma_state(fold)
        nu = state["nuisance"]
        meta = state["original_feature_metadata"]
        pins = meta["array_sha256"]
        origin = float(cat["fold_origin_days"][fold])
        end = float(cat["fold_end_days"][fold])
        test = cat["fold_test_mask"][fold]
        parent = cat["t_days"] < end
        arrays = {
            "parent_time": cat["t_days"][parent],
            "parent_xy": cat["xy_km"][parent],
            "parent_K": cat["K"][parent].astype(float),
            "parent_cell": cat["cell_id"][parent].astype(float),
            "parent_fertility": data._jma_fertility(cat, nu)[parent],
            "parent_exposure_lo": np.maximum(origin - cat["t_days"][parent], 0.0),
            "parent_exposure_hi": end - cat["t_days"][parent],
            "event_time": cat["t_days"][test],
            "event_xy": cat["xy_km"][test],
            "event_K": cat["K"][test].astype(float),
            "event_cell": cat["cell_id"][test].astype(float),
            "event_x": 2.0 * cat["t_days"][test] / float(nu["T0"]) - 1.0,
            "rectangles": cat["rectangles"],
            "reference_pi": np.asarray(nu["reference_pi"]),
            "kde_training_xy": cat["xy_km"][data._jma_training_mask(cat, fold)],
        }
        fold_detail = {}
        for key, value in arrays.items():
            if key not in pins:
                continue
            ok = _array_sha(value) == pins[key]
            fold_detail[key] = ok
            if not ok:
                worst = max(worst, 1.0)
        detail[f"JMA_fold_{fold}"] = fold_detail
    return _check("common_measure_identity", worst == 0.0,
                  dict(maximum_relative_error=worst, families=detail))


def audit_archived_score_replay():
    rows = {}
    worst = 0.0
    # NZ arm 4 (EP) replay
    import math as _m
    for fold in range(3):
        r = data.nz_registry_rows(fold)[4]
        st = json.loads(data._zip_member(data.S03_REGISTRY.parent /
                                         r["state"]["archive"],
                                         r["state"]["member"]))
        a0, d0, n0 = st["parameters"]
        lc, p = st["temporal"]
        scale, q = st["ep_spatial"]
        x = np.array([a0, d0, n0, lc, p, _m.log(scale), 0.0, q])
        train = data.nz_train_view(fold, weights=None, floor_mode="reference")
        test = data.nz_test_view(fold, train.background)
        model = EPModel(test, "rect")
        s = model.scores(x)
        mark = S.mark_score_continuous(test.event_excess, test.beta)
        arch = data.nz_archived_comparators(fold)["ep"]
        for key, value in (("timing", s["timing"]), ("location", s["location"]),
                           ("joint", s["ground_joint"] + mark),
                           ("mark", mark)):
            delta = abs(value - arch[key])
            worst = max(worst, delta)
            rows[f"NZ_fold_{fold}_{key}"] = delta
    # JMA EP full replay
    for fold in range(3):
        state = data.load_jma_state(fold)
        p = state["parameters"]
        x = np.array([p[0], p[1], p[2], p[3], p[4], p[5], 0.0, p[6]])
        cat = data.load_jma_catalogue_arrays()
        train = data.jma_train_view(fold, cat=cat, weights=None,
                                    floor_mode="reference")
        test = data.jma_test_view(fold, train.background, cat=cat)
        model = EPModel(test, "rect")
        s = model.scores(x)
        mark = S.mark_score_lattice(test.event_excess, test.beta)
        arch = data.jma_archived(fold, cat=cat)["full"]["EP"]
        arch_mark = float(arch["joint"] - arch["P"] + arch["E"])
        for key, value in (("timing", s["timing"]), ("location", s["location"]),
                           ("joint", s["ground_joint"] + mark),
                           ("mark", mark)):
            reference = arch_mark if key == "mark" else arch[key]
            delta = abs(value - reference)
            worst = max(worst, delta)
            rows[f"JMA_fold_{fold}_{key}"] = delta
    # California interior EP+ replay
    d = C.read_json(C.CA_INTERIOR)
    for fold in range(3):
        row = next(r for r in d["rows"]
                   if r["case"] == f"california_fold_{fold}"
                   and r["normalization"] == "plane")
        x = np.asarray(row["parameters"][:8], dtype=float)
        train = data.ca_train_view(fold, weights=row["background_weights"],
                                   floor_mode="uniform")
        model = EPModel(train, "plane")
        nll = model.objective(x, deriv=False)
        test = data.ca_test_view(fold, train.background)
        tmodel = EPModel(test, "plane")
        s = tmodel.scores(x)
        mark = S.mark_score_continuous(test.event_excess, test.beta)
        for key, value, reference in (
                ("training_nll", nll, row["training_nll"]),
                ("test_joint", s["ground_joint"] + mark,
                 row["test_joint_score"]),
                ("mark", mark, row["common_mark_score"])):
            delta = abs(value - reference)
            worst = max(worst, delta)
            rows[f"CA_fold_{fold}_{key}"] = delta
    return _check("archived_score_replay", worst < 1e-8,
                  dict(maximum_absolute_delta=worst, deltas=rows))


def audit_rectangle_mass():
    rng = np.random.default_rng(20261116)
    worst = 0.0
    for fold in range(3):
        _rows, a, _m = data.load_nz_cache(fold)
        region = Region(a["rectangles"])
        pts = rng.uniform([region.bounds[0], region.bounds[2]],
                          [region.bounds[1], region.bounds[3]], size=(12, 2))
        for q in (1.2, 1.64, 2.0, 2.5):
            for scale in (5.0, 30.0):
                mass, _, _ = region.mass(pts, np.full(len(pts), scale), q)
                unnorm = mass * np.pi * scale ** 2 / (q - 1.0)
                ref = _mass_order(region.rectangles[None, :, :],
                                  pts[:, None, :], scale, 96, q).sum(axis=1)
                worst = max(worst, float(np.max(np.abs(unnorm - ref) /
                                               np.maximum(ref, 1e-300))))
    return _check("rectangle_mass_vs_independent_quadrature", worst < 1e-9,
                  dict(maximum_relative_error=worst))


def audit_gradients():
    worst = 0.0
    cases = []
    v = data.nz_train_view(0)
    for norm in ("plane", "rect"):
        model = EPModel(v, norm)
        x = np.array([-4.3, 0.0, 0.4, -3.4, 1.29, 1.24, 0.56, 1.55])
        _, g = model.objective(x)
        for k in range(8):
            e = np.zeros(8)
            e[k] = 1e-6
            fd = (model.objective(x + e, deriv=False) -
                  model.objective(x - e, deriv=False)) / 2e-6
            rel = abs(g[k] - fd) / max(1.0, abs(fd))
            worst = max(worst, rel)
            cases.append(dict(region="NZ", normalization=norm, coordinate=k,
                              analytic=float(g[k]), finite_difference=float(fd),
                              relative_error=float(rel)))
    v = data.jma_train_view(0, cat=data.load_jma_catalogue_arrays())
    for norm in ("plane", "rect"):
        model = EPModel(v, norm)
        x = np.array([-1.1, 0.0, 0.7, -3.0, 1.3, math.log(15.0), 0.5, 1.6])
        _, g = model.objective(x)
        for k in range(8):
            e = np.zeros(8)
            e[k] = 1e-6
            fd = (model.objective(x + e, deriv=False) -
                  model.objective(x - e, deriv=False)) / 2e-6
            rel = abs(g[k] - fd) / max(1.0, abs(fd))
            worst = max(worst, rel)
            cases.append(dict(region="JMA", normalization=norm, coordinate=k,
                              analytic=float(g[k]), finite_difference=float(fd),
                              relative_error=float(rel)))
    return _check("analytic_gradients", worst < 1e-5,
                  dict(maximum_relative_error=worst, cases=cases))


def audit_source_single_pass():
    fit_sources = ["run_nz.py", "run_jma.py", "pipeline.py", "fit.py", "model.py"]
    forbidden = ["nz_test_view", "jma_test_view", "nz_archived",
                 "jma_archived", "nz_mark_score", "jma_mark_score"]
    hits = {}
    for name in fit_sources:
        text = (ROOT / "experiments/pathway4_confirmatory_transfer" / name).read_text(
            encoding="utf-8")
        hits[name] = [token for token in forbidden if token in text]
    passed = all(not v for v in hits.values())
    return _check("fit_sources_never_read_test_scores", passed,
                  dict(forbidden=forbidden, hits=hits))


def audit_fit_artifacts(seal):
    problems = []
    for rel in seal["files"]:
        payload = C.read_json(C.ROOT / rel)
        if any(str(k).startswith("test_") for k in payload):
            problems.append(f"{rel}: test key")
        if payload.get("declustering") is None or len(payload["declustering"]) != 5:
            problems.append(f"{rel}: declustering steps")
        if len(payload.get("background_weights", [])) != payload.get("n_train"):
            problems.append(f"{rel}: background weight count")
        for key, value in payload.get("parameter_summary", {}).items():
            lo, hi = BOUNDS[key]
            if not (lo - 1e-9 <= value <= hi + 1e-9):
                problems.append(f"{rel}: {key} outside bounds")
        if payload.get("normalization") == "plane":
            profiles = payload.get("attenuation_profiles", {}) or {}
            if profiles.get("status") != "complete":
                problems.append(f"{rel}: missing attenuation profile")
            else:
                for key in profiles.get("mono_grid", {}):
                    eta = profiles["mono_grid"][key]["eta"]
                    if not (0.0 <= eta <= 4.0 + 1e-9):
                        problems.append(f"{rel}: eta outside bounds")
    return _check("fit_artifact_protocol_conformance", not problems,
                  dict(problems=problems, files=len(seal["files"])))


def audit_calibration():
    path = C.OUT / "california" / "summary.json"
    if not path.exists():
        return _check("california_conditional_calibration", False,
                      dict(reason="summary missing"))
    summary = C.read_json(path)
    problems = []
    for fold, row in summary.get("folds", {}).items():
        if abs(row.get("model_test_joint_delta", 0.0)) > 1e-8:
            problems.append(f"fold {fold}: frozen-state replay delta")
    return _check("california_conditional_calibration", not problems,
                  dict(problems=problems, folds=summary.get("folds")))


def audit_fit_source_pins(seal, protocol):
    names = ("model.py", "geometry.py", "data.py", "fit.py", "pipeline.py",
             "run_nz.py", "run_jma.py")
    problems = []
    detail = {}
    for name in names:
        path = ROOT / "experiments/pathway4_confirmatory_transfer" / name
        current = C.sha256(path)
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        detail[name] = dict(current=current,
                            protocol=protocol.get("sources", {}).get(name),
                            fit_seal=seal.get("source_pins", {}).get(rel))
        if detail[name]["protocol"] != current:
            problems.append(f"{name}: protocol source hash")
        if detail[name]["fit_seal"] != current:
            problems.append(f"{name}: fit-seal source hash")
    return _check("fit_source_pins", not problems,
                  dict(problems=problems, sources=detail))


def audit_protocol_timing(seal, protocol):
    import datetime as dt
    created = dt.datetime.fromisoformat(protocol["created_utc"])
    times = []
    for rel in seal["files"]:
        payload = C.read_json(C.ROOT / rel)
        times.append(dt.datetime.fromisoformat(payload["created_utc"]))
    earliest = min(times)
    superseded_protocol = (
        ROOT / "experiments/pathway4_confirmatory_transfer/"
               "frozen_protocol_v1_superseded_20261116.json").exists()
    superseded_fits = (C.OUT / "superseded_fits_20261116").exists()
    return _check(
        "protocol_precedes_every_fit", created <= earliest,
        dict(protocol_created=protocol["created_utc"],
             earliest_fit=earliest.isoformat(),
             superseded_protocol_present=superseded_protocol,
             superseded_fits_present=superseded_fits,
             note="The superseded first freeze and its pre-scoring NZ fits "
                  "are retained as an audit trail; no NZ/Japan test score was "
                  "read before the operative freeze."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=C.PROTOCOL)
    parser.add_argument("--output", type=Path,
                        default=C.OUT / "independent_audit.json")
    args = parser.parse_args()
    checks = []
    protocol_sha = C.sha256(args.protocol)
    pin = args.protocol.with_suffix(".sha256").read_text(
        encoding="utf-8").strip().split()[0]
    checks.append(_check("protocol_hash_pin", pin == protocol_sha,
                         dict(protocol_sha256=protocol_sha, pin=pin)))
    seal_path = C.OUT / "fit_seal.json"
    seal = C.read_json(seal_path)
    checks.append(_check("fit_seal_protocol_hash",
                         seal.get("protocol_sha256") == protocol_sha,
                         dict(seal=seal.get("protocol_sha256"))))
    verify_error = None
    try:
        S.verify_fit_seal(seal_path, args.protocol)
    except Exception as exc:
        verify_error = f"{type(exc).__name__}: {exc}"
    checks.append(_check("fit_seal_manifest", verify_error is None,
                         dict(error=verify_error,
                              files=len(seal.get("files", {})),
                              manifest_sha256=seal.get("manifest_sha256"))))
    protocol = C.read_json(args.protocol)
    checks.append(audit_fit_source_pins(seal, protocol))
    checks.append(audit_protocol_timing(seal, protocol))
    checks.append(audit_source_single_pass())
    checks.append(audit_fit_artifacts(seal))
    checks.append(audit_common_measures())
    checks.append(audit_archived_score_replay())
    checks.append(audit_rectangle_mass())
    checks.append(audit_gradients())
    baseline = _sealed_manifest()
    checks.append(_check("sealed_authority_custody",
                         not baseline["missing"] and not baseline["changed"],
                         dict(files=baseline["files"], verified=baseline["verified"],
                              missing=baseline["missing"], changed=baseline["changed"],
                              snapshot_sha256=baseline["snapshot_sha256"])))
    checks.append(audit_calibration())
    result = dict(
        schema="pathway4_independent_audit_v1",
        passed=all(c["passed"] for c in checks),
        protocol_sha256=protocol_sha,
        checks=checks,
        scope="numerical replay, common-measure identity, rectangular mass, "
              "analytic gradients, fit sealing, single-pass source separation, "
              "sealed-authority custody and conditional-calibration replay",
    )
    C.write_json(args.output, result)
    print(json.dumps(dict(passed=result["passed"],
                          checks=[(c["name"], c["passed"]) for c in checks]),
                     indent=2))


if __name__ == "__main__":
    main()
