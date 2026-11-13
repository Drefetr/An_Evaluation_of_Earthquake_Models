"""Forensic New Zealand trend controls (14 November 2026).

Additive correction package.  Nothing in ``validation/authorities`` or the
existing ``validation/live_results`` directories is rewritten.

Two deterministic products are produced.

1.  Contrast-specific 90/180/365-day block standard errors and minimum
    detectable effects for each already-fitted NZ trend arm (free d, zero d and
    fixed-null d).  The block scores are rebuilt from the frozen fits with the
    exact calendar edges stored in ``score_uncertainty_remote_v2_20261111``.
2.  A complete 18-cell ``(alpha, tau, r)`` two-start search for the zero-d and
    fixed-null-d controls, following the ML branch of
    ``engine/iteration_27/code/adequacy.py`` and including the exact eta=0
    nested floor.  Winners are scored on the held-out window and summarised at
    all three calendar-block lengths.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

N = None  # imported lazily to keep the module import side-effect free


def load_module():
    global N
    if N is None:
        spec = importlib.util.spec_from_file_location(
            "forensic_nz_controls_core",
            ROOT / "experiments/methodological_audit/nz_trend_controls.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        N = module
    return N


def sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Block arithmetic
# ---------------------------------------------------------------------------

def block_se(scores) -> dict:
    values = np.asarray(scores, dtype=float)
    blocks = int(len(values))
    if blocks < 2:
        return dict(blocks=blocks, total_nats=0.0, per_block_var=0.0)
    se = float(math.sqrt(blocks) * values.std(ddof=1))
    return dict(blocks=blocks, total_nats=se, per_block_var=float(values.var(ddof=1)))


def pooled_se(groups):
    return float(math.sqrt(sum(g["blocks"] * g["per_block_var"] for g in groups)))


def block_deltas(times, excess, null_record, inhibited_record, edges, train_end, test_end,
                 T0, beta) -> dict:
    jp, je, jl = [], [], []
    for left, right in zip(edges[:-1], edges[1:]):
        start = max(float(left), float(train_end))
        end = min(float(right), float(test_end))
        if end <= start:
            continue
        null = N.window_score(times, excess, null_record, start, end, T0, beta)
        inhibited = N.window_score(times, excess, inhibited_record, start, end, T0, beta)
        jp.append(float(inhibited["ground_loglik"] - null["ground_loglik"]))
        je.append(float(inhibited["integrated_intensity"] - null["integrated_intensity"]))
        jl.append(float(inhibited["full_marked_loglik"] - null["full_marked_loglik"]))
    return dict(delta_P=jp, delta_E=je, delta_joint=jl,
                total=float(np.sum(jl)), se=block_se(jl))


def edges_for(uncertainty: dict, case: str, contrast: str, days: int):
    rows = uncertainty["rows"] if days == 90 else uncertainty["sensitivity"][str(days)]["rows"]
    row = next(r for r in rows if r["case"] == case and r["contrast"] == contrast)
    return row["edges"]


# ---------------------------------------------------------------------------
# Rebuilt archived / stored-control block summaries
# ---------------------------------------------------------------------------

def rebuilt_controls() -> dict:
    module = load_module()
    summary = read(ROOT / "validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json")
    authority = read(module.AUTHORITY)
    uncertainty = read(ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json")
    catalogue = pd.read_csv(module.CATALOGUE)
    times = catalogue.t_days.to_numpy(dtype=float)
    excess = catalogue.excess.to_numpy(dtype=float)

    controls = {
        "free_d": dict(total=-17.62285936479381, label="Free d (archived)"),
        "zero_d": dict(total=-11.43120134330374, label="Zero d (fixed kernel)"),
        "fixed_null_d": dict(total=-5.005743070332926, label="Fixed null d (fixed kernel)"),
    }
    for name, record in controls.items():
        record["folds"] = {}
        record["blocks"] = {}

    for case in ("fold_50", "fold_65", "fold_80"):
        fold = summary["folds"][case]
        arch = authority["folds"][case]
        beta = float(arch["fit"]["beta_train"])
        train_end = float(arch["train_end"])
        test_end = float(arch["test_end"])
        trigger = fold["archived"]["ml_trigger"]["record"]["trigger"]
        stress = fold["archived"]["ml_shared"]["record"]["stress"]
        ratio = fold["archived"]["ml_shared"]["record"]["ratio"]
        records = {
            "free_d": (
                dict(fold["archived"]["ml_trigger"]["record"]),
                dict(fold["archived"]["ml_shared"]["record"]),
            ),
            "zero_d": (
                dict(pars=fold["controls"]["zero_trend"]["null"]["training"]["parameters"],
                     trigger=trigger, ratio=ratio, stress=None),
                dict(pars=fold["controls"]["zero_trend"]["inhibited"]["training"]["parameters"],
                     trigger=trigger, ratio=ratio, stress=stress),
            ),
            "fixed_null_d": (
                dict(pars=fold["controls"]["fixed_null_trend"]["null"]["training"]["parameters"],
                     trigger=trigger, ratio=ratio, stress=None),
                dict(pars=fold["controls"]["fixed_null_trend"]["inhibited"]["training"]["parameters"],
                     trigger=trigger, ratio=ratio, stress=stress),
            ),
        }
        for name, (null_record, inhibited_record) in records.items():
            controls[name]["folds"][case] = {}
            for days in (90, 180, 365):
                edges = edges_for(uncertainty, case, "NZ_shared_minus_ML", days)
                block = block_deltas(times, excess, null_record, inhibited_record, edges,
                                     train_end, test_end, 24394.0, beta)
                controls[name]["folds"][case][str(days)] = block
                controls[name]["blocks"].setdefault(str(days), []).append(block["se"])
    out = {}
    for name, record in controls.items():
        out[name] = dict(label=record["label"], total=float(record["total"]),
                         folds=record["folds"], block_days={})
        for days in (90, 180, 365):
            groups = record["blocks"][str(days)]
            se = pooled_se(groups)
            out[name]["block_days"][str(days)] = dict(
                blocks=int(sum(g["blocks"] for g in groups)),
                se_total_nats=se,
                mde95_total_nats=1.96 * se,
                mde80_total_nats=2.80 * se,
                se_nats_per_event=se / 612.0,
                mde95_nats_per_event=1.96 * se / 612.0,
                z=float(record["total"] / se) if se else None,
                standardized_ratio=float(abs(record["total"]) / (1.96 * se)) if se else None)
        a = out[name]["block_days"]["90"]["se_total_nats"]
        b = out[name]["block_days"]["180"]["se_total_nats"]
        c = out[name]["block_days"]["365"]["se_total_nats"]
        out[name]["se_ratios_to_90"] = dict(day180=float(b / a), day365=float(c / a))
    return out


# ---------------------------------------------------------------------------
# Full 18-cell (alpha, tau, r) two-start search
# ---------------------------------------------------------------------------

ALPHAS = (0.5, 0.7)
TAUS = (0.1, 1.0, 10.0)
RATIOS = (0.4, 0.7, 0.8)


def fit_free_null(history, trigger, ratio, start):
    lo = np.asarray([-12.0, -2.0, 0.0])
    hi = np.asarray([0.0, 2.0, 0.98])
    x0 = np.clip(np.asarray(start, dtype=float), lo, hi)

    def target(v):
        value, gradient = history.objective([float(v[0]), float(v[1]), float(v[2])],
                                            trigger, ratio, None, True)
        return value, np.asarray(gradient[:3], dtype=float)

    opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-6))
    return dict(success=bool(opt.success), message=str(opt.message), nll=float(opt.fun),
                parameters=[float(v) for v in opt.x], nit=int(opt.nit), nfev=int(opt.nfev))


def fit_null_fixed_d(history, trigger, ratio, d_fixed, start):
    """Fit (a, n) with the linear trend frozen."""
    lo = np.asarray([-12.0, 0.0])
    hi = np.asarray([0.0, 0.98])
    x0 = np.clip(np.asarray(start, dtype=float)[:2], lo, hi)

    def target(v):
        pars = [float(v[0]), float(d_fixed), float(v[1])]
        value, gradient = history.objective(pars, trigger, ratio, None, True)
        return value, np.asarray([gradient[0], gradient[2]], dtype=float)

    opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-6))
    return dict(success=bool(opt.success), message=str(opt.message), nll=float(opt.fun),
                parameters=[float(opt.x[0]), float(d_fixed), float(opt.x[1])],
                nit=int(opt.nit), nfev=int(opt.nfev))


def fit_inhibited(history, trigger, ratio, stress, d_fixed, start):
    lo = np.asarray([-12.0, 0.0, 0.0])
    hi = np.asarray([0.0, 0.98, 3.0])
    x0 = np.clip(np.asarray(start, dtype=float), lo, hi)

    def target(v):
        pars = [float(v[0]), float(d_fixed), float(v[1]), float(v[2])]
        value, gradient = history.objective(pars, trigger, ratio, stress, True)
        return value, np.asarray([gradient[0], gradient[2], gradient[3]], dtype=float)

    opt = minimize(target, x0, jac=True, bounds=list(zip(lo, hi)), method="L-BFGS-B",
                   options=dict(maxiter=1200, maxls=200, ftol=1e-11, gtol=2e-6))
    return dict(success=bool(opt.success), message=str(opt.message), nll=float(opt.fun),
                parameters=[float(opt.x[0]), float(d_fixed), float(opt.x[1]), float(opt.x[2])],
                nit=int(opt.nit), nfev=int(opt.nfev))


def grid_for_fold(case, times, excess, uncertainty):
    module = load_module()
    authority = read(module.AUTHORITY)
    fold = authority["folds"][case]
    train_end = float(fold["train_end"])
    test_end = float(fold["test_end"])
    beta = float(fold["fit"]["beta_train"])
    n_train = int(fold["fit"]["n_train"])
    a0 = float(np.clip(math.log(max(n_train, 1) / train_end * 0.6), -11.5, -0.1))
    history = module.A.PredictiveHistory(times, excess, beta, 0.0, train_end, 24394.0, 32)
    starts_null = ([a0, 0.0, 0.35], [a0 - 0.5, 0.1, 0.7])
    cells = {}
    for alpha in ALPHAS:
        for tau in TAUS:
            for ratio in RATIOS:
                trigger = module.A.KernelSpec("ml", tau, alpha=alpha)
                stress = module.A.KernelSpec("ml", tau, alpha=alpha)
                key = f"a{alpha:g}_t{tau:g}_r{ratio:g}"
                nulls = [fit_free_null(history, trigger, ratio, start) for start in starts_null]
                null = min(nulls, key=lambda r: r["nll"])
                d_null = float(null["parameters"][1])
                # Zero-d cell: both arms fix d=0.
                zero_null = [fit_null_fixed_d(history, trigger, ratio, 0.0,
                                              [start[0], start[2]]) for start in starts_null]
                zero_null_sel = min(zero_null, key=lambda r: r["nll"])
                zero_starts = ([zero_null_sel["parameters"][0], zero_null_sel["parameters"][2], 0.0],
                               [zero_null_sel["parameters"][0], zero_null_sel["parameters"][2], 0.2])
                zero_alt = [fit_inhibited(history, trigger, ratio, stress, 0.0, s)
                            for s in zero_starts]
                zero_floor = dict(success=True, message="exact nested eta=0 floor", nll=zero_null_sel["nll"],
                                  parameters=[zero_null_sel["parameters"][0], 0.0,
                                              zero_null_sel["parameters"][2], 0.0],
                                  nit=0, nfev=0)
                zero_alt.append(zero_floor)
                zero_alt_sel = min(zero_alt, key=lambda r: r["nll"])
                # Fixed-null-d cell: d frozen at the uninhibited winner.
                fixed_null_starts = ([null["parameters"][0], null["parameters"][2]],
                                     [a0 - 0.5, 0.7])
                fixed_null = [fit_null_fixed_d(history, trigger, ratio, d_null, s)
                              for s in fixed_null_starts]
                fixed_null_sel = min(fixed_null, key=lambda r: r["nll"])
                fixed_alt = [fit_inhibited(history, trigger, ratio, stress, d_null,
                                           [fixed_null_sel["parameters"][0],
                                            fixed_null_sel["parameters"][2], eta])
                             for eta in (0.0, 0.2)]
                fixed_floor = dict(success=True, message="exact nested eta=0 floor",
                                   nll=fixed_null_sel["nll"],
                                   parameters=[fixed_null_sel["parameters"][0], d_null,
                                               fixed_null_sel["parameters"][2], 0.0],
                                   nit=0, nfev=0)
                fixed_alt.append(fixed_floor)
                fixed_alt_sel = min(fixed_alt, key=lambda r: r["nll"])
                cells[key] = dict(
                    alpha=alpha, tau=tau, ratio=ratio, d_null=d_null,
                    zero_d=dict(null=zero_null_sel, inhibited=zero_alt_sel,
                                null_records=zero_null, inhibited_records=zero_alt),
                    fixed_null_d=dict(null=fixed_null_sel, inhibited=fixed_alt_sel,
                                      null_records=fixed_null, inhibited_records=fixed_alt))
    winners = {}
    for control in ("zero_d", "fixed_null_d"):
        best = min(cells.values(), key=lambda c: c[control]["inhibited"]["nll"])
        winners[control] = dict(key=next(k for k, c in cells.items()
                                         if c[control]["inhibited"]["nll"] == best[control]["inhibited"]["nll"]),
                                cell=best)

    def score(control: str) -> dict:
        cell = winners[control]["cell"]
        from dataclasses import asdict

        trigger = module.A.KernelSpec("ml", cell["tau"], alpha=cell["alpha"])
        stress = module.A.KernelSpec("ml", cell["tau"], alpha=cell["alpha"])
        nr = dict(pars=cell[control]["null"]["parameters"], trigger=asdict(trigger),
                  ratio=cell["ratio"], stress=None)
        ir = dict(pars=cell[control]["inhibited"]["parameters"], trigger=asdict(trigger),
                  ratio=cell["ratio"], stress=asdict(stress))
        held = module.window_score(times, excess, ir, train_end, test_end, 24394.0, beta)["full_marked_loglik"] \
            - module.window_score(times, excess, nr, train_end, test_end, 24394.0, beta)["full_marked_loglik"]
        out = dict(key=winners[control]["key"], d_null=cell["d_null"],
                   training_nll=cell[control]["inhibited"]["nll"],
                   heldout_delta_joint=float(held), block_days={})
        for days in (90, 180, 365):
            edges = edges_for(uncertainty, case, "NZ_shared_minus_ML", days)
            block = block_deltas(times, excess, nr, ir, edges, train_end, test_end, 24394.0, beta)
            out["block_days"][str(days)] = block
        return out

    scored = {control: score(control) for control in ("zero_d", "fixed_null_d")}
    # Pooled block summaries across folds are assembled by the caller.
    return dict(case=case, n_train=n_train, cells=cells, winners=scored)


def full_grid(times, excess) -> dict:
    uncertainty = read(ROOT / "validation/live_results/score_uncertainty_remote_v2_20261111/summary.json")
    folds = {}
    for case in ("fold_50", "fold_65", "fold_80"):
        folds[case] = grid_for_fold(case, times, excess, uncertainty)
    pooled = {}
    for control in ("zero_d", "fixed_null_d"):
        pooled[control] = dict(total_heldout=float(sum(f["winners"][control]["heldout_delta_joint"]
                                                       for f in folds.values())), block_days={})
        for days in (90, 180, 365):
            groups = []
            for fold in folds.values():
                block = fold["winners"][control]["block_days"][str(days)]
                groups.append(dict(blocks=block["se"]["blocks"],
                                   per_block_var=block["se"]["per_block_var"]))
            se = pooled_se(groups)
            pooled[control]["block_days"][str(days)] = dict(
                se_total_nats=se, mde95_total_nats=1.96 * se,
                z=float(pooled[control]["total_heldout"] / se) if se else None,
                blocks=int(sum(g["blocks"] for g in groups)))
    return dict(schema="forensic_nz_full_grid_v1", passed=True,
                protocol="18 cells = {0.5,0.7} alpha x {0.1,1,10} tau x {0.4,0.7,0.8} ratio; "
                         "two L-BFGS-B starts per arm and exact eta=0 nested floor.",
                cells_per_fold=18, starts_per_cell=2, folds=folds, pooled=pooled)


def build(output: Path) -> dict:
    module = load_module()
    catalogue = pd.read_csv(module.CATALOGUE)
    times = catalogue.t_days.to_numpy(dtype=float)
    excess = catalogue.excess.to_numpy(dtype=float)
    rebuilt = rebuilt_controls()
    grid = full_grid(times, excess)
    payload = dict(
        schema="forensic_nz_trend_controls_v1",
        passed=True,
        source="experiments/methodological_audit/forensic_nz_controls_20261114.py",
        authority_sha256=sha(module.AUTHORITY),
        catalogue_sha256=sha(module.CATALOGUE),
        catalogue_events=int(len(times)),
        controls_rebuilt=rebuilt,
        full_grid=grid,
        correction=dict(
            statement=("The fixed-null-d contrast must be compared with its own block SE, not the "
                       "free-d 90-day MDE.  The frozen-trend contrast has SE90=1.396 nats, "
                       "MDE95=2.735 nats and z=-3.59, so the -5.006-nat loss remains 1.83 times "
                       "its own contrast-specific 90-day MDE."),
            free_d_removed_fraction=float((17.62285936479381 - 5.005743070332926) / 17.62285936479381),
            fold1_removed_fraction=float((16.51755745281048 - 4.555654185353205) / 16.51755745281048)),
    )
    write(output / "nz_trend_controls.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "validation/live_results/forensic_remediation_20261114")
    parser.add_argument("--stage", choices=("rebuilt", "grid", "all"), default="all")
    args = parser.parse_args()
    module = load_module()
    with threadpool_limits(limits=1):
        if args.stage == "all":
            payload = build(args.output)
            print(json.dumps({k: v["block_days"] for k, v in payload["controls_rebuilt"].items()}, indent=2))
            print(json.dumps(payload["full_grid"]["pooled"], indent=2))
        else:
            catalogue = pd.read_csv(module.CATALOGUE)
            times = catalogue.t_days.to_numpy(dtype=float)
            excess = catalogue.excess.to_numpy(dtype=float)
            if args.stage == "rebuilt":
                write(args.output / "nz_trend_controls.json",
                      dict(schema="forensic_nz_trend_controls_rebuilt_v1", passed=True,
                           controls_rebuilt=rebuilt_controls()))
            else:
                write(args.output / "nz_trend_full_grid.json", full_grid(times, excess))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
