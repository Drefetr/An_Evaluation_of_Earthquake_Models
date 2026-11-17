"""Pathway 1 annular attenuation kernels and likelihood machinery.

The frozen EP+ model, data caches and background estimator are imported from
``experiments/etas_inhibition_benchmark/run_frozen_20261111.py``. This module
only adds the annular attenuation field G_K, its analytic derivatives, and the
diagnostic/profile utilities. It never edits a sealed authority.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "experiments/etas_inhibition_benchmark/run_frozen_20261111.py"
ACCEPTED = ROOT / "validation/live_results/etas_inhibition_benchmark_interior_20261112"
RELAX = ROOT / "validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_relaxation.json"
KERNELS = ("mono", "ann1", "ann2", "shield")
BASELINES = ("interior", "bound_2km")
ETA_GRID = (0.0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.4, 0.8, 1.5, 2.5, 4.0, 6.0, 10.0)
ELL_GRID_KM = (2.0, 5.0, 10.0, 15.0, 20.0, 35.0, 50.0)
PSI_GRID_DAYS = (1.0, 2.0, 5.0, 15.0, 30.0, 90.0)


def _load_frozen():
    spec = importlib.util.spec_from_file_location("pathway1_frozen", FROZEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RF = _load_frozen()


def sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_baseline(case: str, baseline: str):
    """Return (12-coordinate null state, background weights, source metadata)."""
    if baseline == "interior":
        data = read_json(RELAX)
        row = next(r for r in data["rows"] if r["case"] == case and r["normalization"] == "plane")
        x = np.asarray(row["parameters"], dtype=float)
        weights = np.asarray(row["background_weights"], dtype=float)
        meta = dict(
            baseline="interior",
            source=str(RELAX.relative_to(ROOT).as_posix()),
            source_sha256=sha256(RELAX),
            sigma0_km=float(np.exp(x[5])),
            training_nll=float(row["training_nll"]),
            test_joint_score=float(row["test_joint_score"]),
            normalization=row["normalization"],
        )
        return x, weights, meta
    if baseline == "bound_2km":
        result = read_json(ACCEPTED / case / "result.json")
        x = np.asarray(result["null"]["selected"]["parameters"], dtype=float)
        weights = np.asarray(result["background_weights"], dtype=float)
        comparison = read_json(ACCEPTED / "baseline_comparison.json")
        comparison_row = next(r for r in comparison["rows"] if r["case"] == case)
        meta = dict(
            baseline="bound_2km",
            source=str((ACCEPTED / case / "result.json").relative_to(ROOT).as_posix()),
            source_sha256=sha256(ACCEPTED / case / "result.json"),
            sigma0_km=float(np.exp(x[5])),
            training_nll=float(result["null"]["selected"]["nll"]),
            test_joint_score=float(comparison_row["new_joint_score"]),
            normalization="plane",
        )
        return x, weights, meta
    raise ValueError("unknown baseline " + baseline)


class AnnularModel(RF.Model):
    """Frozen EP+ model with a selectable spatial attenuation field G_K."""

    def __init__(self, *args, native, kernel="mono", scaled=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.ann_native = native
        self.kernel = kernel
        self.scaled = bool(scaled)
        self.node_data = None
        self._native_threads = getattr(native, "threads", 1)

    def freeze_nodes(self):
        if self.nodes is None:
            raise RuntimeError("node_setup must be called before freeze_nodes")
        self.node_data = self.prepare(self.nodes["t"], self.nodes["xy"], self.nodes["b"])
        self.node_data["w"] = np.asarray(self.nodes["w"], dtype=float)

    def _rows(self, data, x, need_h=True, need_g=True):
        return self.ann_native.rows(
            data,
            self.dm,
            self.kp,
            x,
            kernel=self.kernel,
            scaled=self.scaled,
            need_h=need_h,
            need_g=need_g,
        )

    def values_from_out(self, data, x, out):
        """lambda0 and its derivative from one native row contraction."""
        h = out[:, 0]
        hg = out[:, 1:6]
        xt = 2.0 * data["t"] / self.m["T0"] - 1.0
        B = np.exp(x[0] + x[1] * xt) * data["b"]
        lam = B + x[2] * h
        dlam = np.zeros((len(lam), 12))
        dlam[:, 0] = B
        dlam[:, 1] = B * xt
        dlam[:, 2] = h
        dlam[:, 3] = x[2] * hg[:, 0]
        dlam[:, 4] = x[2] * hg[:, 1]
        dlam[:, 5] = x[2] * hg[:, 2]
        dlam[:, 6] = x[2] * hg[:, 3]
        dlam[:, 7] = x[2] * hg[:, 4]
        return lam, B, h, dlam

    def G(self, data, x):
        """Attenuation field G and five derivatives.

        Columns: d/dlogell0, d/dlogpsi, d/dgamma, d/dlogsigma0, d/dalpha_s.
        The last two vanish except for the shield kernel.
        """
        out = self._rows(data, x, need_h=False, need_g=True)
        return out[:, 6], np.stack(
            [out[:, 7], out[:, 8], out[:, 9], out[:, 10], out[:, 11]], axis=1
        )

    def _event_out(self, x):
        return self._rows(self.events, x, need_h=True, need_g=True)

    def objective(self, x, inhibit=False, details=False):
        x = np.asarray(x, dtype=float)
        out = self._event_out(x)
        lam, B, h, dlam = self.values_from_out(self.events, x, out)
        if np.any(lam <= 0) or not np.isfinite(lam).all():
            raise ArithmeticError("nonpositive event intensity")
        P = float(np.log(lam).sum())
        E, grad = self.exact_exposure(x)
        grad = np.asarray(grad, dtype=float).copy()
        grad -= np.sum(dlam / lam[:, None], axis=0)
        deficit = 0.0
        attenpoint = 0.0
        if details and inhibit and x[8] == 0.0:
            return dict(ground_point=P, exposure=E, uninhibited_exposure=E,
                        attenuation_deficit=0.0, nll=float(E - P))
        if inhibit:
            G = out[:, 6]
            gG = out[:, 7:12]
            attenpoint = float(x[8] * G.sum())
            grad[8] += G.sum()
            grad[9] += x[8] * gG[:, 0].sum()
            grad[10] += x[8] * gG[:, 1].sum()
            grad[11] += x[8] * gG[:, 2].sum()
            grad[5] += x[8] * gG[:, 3].sum()
            grad[6] += x[8] * gG[:, 4].sum()
            data = self.node_data
            if data is None:
                raise RuntimeError("missing frozen integration proposal")
            for j in range(0, len(data["t"]), 2048):
                raw = {k: v[j:j + 2048] for k, v in data.items()}
                nout = self._rows(raw, x, need_h=True, need_g=True)
                L, LB, _h, dL = self.values_from_out(raw, x, nout)
                g = nout[:, 6]
                dg = nout[:, 7:12]
                atten = np.exp(-x[8] * g)
                dec = -np.expm1(-x[8] * g)
                w = raw["w"]
                deficit += float(w @ (L * dec))
                grad -= np.sum(dL * (w * dec)[:, None], axis=0)
                grad[8] -= float(w @ (L * atten * g))
                grad[9] -= float(np.sum(dg[:, 0] * (w * L * atten * x[8])))
                grad[10] -= float(np.sum(dg[:, 1] * (w * L * atten * x[8])))
                grad[11] -= float(np.sum(dg[:, 2] * (w * L * atten * x[8])))
                grad[5] -= float(np.sum(dg[:, 3] * (w * L * atten * x[8])))
                grad[6] -= float(np.sum(dg[:, 4] * (w * L * atten * x[8])))
        value = float(E - deficit - P + attenpoint)
        if details:
            return dict(ground_point=float(P - attenpoint), exposure=float(E - deficit),
                        uninhibited_exposure=float(E), attenuation_deficit=float(deficit),
                        nll=value)
        return value, grad


def new_native(threads=1, kernel="mono", scaled=True):
    from experiments.pathway1_annular_attenuation.native import Native, DEFAULT_OUTPUT, build

    library = build(DEFAULT_OUTPUT)
    native = Native(library, threads=threads, kernel=kernel, scaled=scaled)
    # The frozen Model.node_setup uses Model.H; point it at the compiled H rows.
    RF.NATIVE = native
    return native


def build_models(case, baseline, native, train_power=14, test_power=16,
                 train_seed=20261111, test_seed=20261120, kernel="mono", scaled=True):
    import_errors = []
    train, tm, test, vm, rows = RF.inputs(case)
    x0, weights, meta = load_baseline(case, baseline)
    region = RF.Region(train["rectangles"])
    background = RF.Background(train["event_xy"], region, tm["kde_bandwidth"], weights)
    train_model = AnnularModel(train, tm, background, native=native, kernel=kernel, scaled=scaled)
    train_model.node_setup(x0, power=train_power, seed=train_seed)
    train_model.freeze_nodes()
    test_model = AnnularModel(test, vm, background, native=native, kernel=kernel, scaled=scaled)
    test_model.node_setup(x0, power=test_power, seed=test_seed)
    test_model.freeze_nodes()
    return dict(train=train, test=test, tm=tm, vm=vm,
                x0=x0, weights=weights, meta=meta, background=background,
                region=region, train_model=train_model, test_model=test_model,
                import_errors=import_errors)


def _profile_total(eta, S, wL, G):
    eta = np.asarray(eta, dtype=float)
    out = np.empty(len(eta))
    for i, e in enumerate(eta):
        out[i] = -e * S + float(wL @ (-np.expm1(-e * G)))
    return out


def _profile_immigrant(eta, Bb_e, nH_e, G_e, wB, G_n):
    """Immigrant-only profile: event term over events, exposure over nodes."""
    eta = np.asarray(eta, dtype=float)
    out = np.empty(len(eta))
    for i, e in enumerate(eta):
        lam_e = Bb_e * np.exp(-e * G_e) + nH_e
        out[i] = float(np.sum(np.log(lam_e / (Bb_e + nH_e)))) + float(
            wB @ (-np.expm1(-e * G_n))
        )
    return out


def _root_increasing(func, upper=50.0):
    """Bisect a concave profile derivative that is positive at zero."""
    lo = 0.0
    hi = 1e-6
    while func(hi) > 0 and hi < upper:
        hi *= 2.0
    if func(hi) <= 0:
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if func(mid) > 0:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)
    return upper


def stage_summary(model, x, eta_grid=ETA_GRID, need_arrays=False):
    """Event sums, exposure integrals, null slopes and profiles at one state."""
    x = np.asarray(x, dtype=float)
    out_e = model._event_out(x)
    lam_e, B_e, h_e, _ = model.values_from_out(model.events, x, out_e)
    G_e = out_e[:, 6]
    Bb_e = B_e
    nH_e = lam_e - B_e
    S_total = float(G_e.sum())
    S_imm = float(np.sum(Bb_e / lam_e * G_e))
    wL = []
    wB = []
    G_n = []
    Bb_n = []
    nH_n = []
    A_total = 0.0
    A_imm = 0.0
    data = model.node_data
    for j in range(0, len(data["t"]), 2048):
        raw = {k: v[j:j + 2048] for k, v in data.items()}
        nout = model._rows(raw, x, need_h=True, need_g=True)
        L, LB, _h, _ = model.values_from_out(raw, x, nout)
        g = nout[:, 6]
        w = raw["w"]
        wL.append(w * L)
        wB.append(w * LB)
        G_n.append(g)
        Bb_n.append(LB)
        nH_n.append(L - LB)
        A_total += float(w @ (L * g))
        A_imm += float(w @ (LB * g))
    wL = np.concatenate(wL)
    wB = np.concatenate(wB)
    G_n = np.concatenate(G_n)
    Bb_n = np.concatenate(Bb_n)
    nH_n = np.concatenate(nH_n)
    slope_total = A_total - S_total
    slope_imm = A_imm - S_imm
    grid = np.asarray(eta_grid, dtype=float)
    prof_total = _profile_total(grid, S_total, wL, G_n)
    prof_imm = _profile_immigrant(grid, Bb_e, nH_e, G_e, wB, G_n)

    def dtotal(e):
        return -S_total + float(wL @ (G_n * np.exp(-e * G_n)))

    def dimm(e):
        lam_e = Bb_e * np.exp(-e * G_e) + nH_e
        return (
            -float(np.sum(Bb_e * G_e * np.exp(-e * G_e) / lam_e))
            + float(wB @ (G_n * np.exp(-e * G_n)))
        )

    if slope_total > 0:
        eta_total = _root_increasing(dtotal)
        delta_total = float(_profile_total([eta_total], S_total, wL, G_n)[0])
    else:
        eta_total = 0.0
        delta_total = 0.0
    if slope_imm > 0:
        eta_imm = _root_increasing(dimm)
        delta_imm = float(_profile_immigrant([eta_imm], Bb_e, nH_e, G_e, wB, G_n)[0])
    else:
        eta_imm = 0.0
        delta_imm = 0.0
    result = dict(
        event_sum=float(S_total), exposure_integral=float(A_total),
        score_slope_total=float(slope_total),
        event_sum_immigrant=float(S_imm), exposure_integral_immigrant=float(A_imm),
        score_slope_immigrant=float(slope_imm),
        eta_hat_train_total=float(eta_total), delta_train_max_total=float(delta_total),
        eta_hat_train_immigrant=float(eta_imm), delta_train_max_immigrant=float(delta_imm),
        eta_grid=[float(v) for v in grid],
        profile_train_total=[float(v) for v in prof_total],
        profile_train_immigrant=[float(v) for v in prof_imm],
        query_eta_total=float(eta_total), query_eta_immigrant=float(eta_imm),
    )
    if need_arrays:
        result["_arrays"] = dict(S_total=S_total, S_imm=S_imm, wL=wL, wB=wB,
                                 G_n=G_n, Bb_n=Bb_n, nH_n=nH_n,
                                 Bb_e=Bb_e, nH_e=nH_e, G_e=G_e, lam_e=lam_e)
    return result


def mark_logscore(case):
    """Common exponential-mark log score on the held-out events."""
    _train, _tm, test, vm, _rows = RF.inputs(case)
    beta = float(vm["beta"])
    excess = np.asarray(test["event_excess"], dtype=float)
    return float(len(excess) * math.log(beta) - beta * excess.sum())


def attenuation_blocks(model, x, block_days):
    """Total-intensity attenuation contrast by calendar block.

    The event term is -eta G at each held-out event and the exposure term is
    \\int lambda0 (1-exp(-eta G)) over the frozen quadrature nodes. Their sum is
    exactly the held-out attenuation gain at the same test proposal.
    """
    x = np.asarray(x, dtype=float)
    eta = float(x[8])
    out_e = model._event_out(x)
    G_e = out_e[:, 6]
    edges = np.r_[np.arange(model.m["start"], model.m["end"], block_days), model.m["end"]]
    event_blocks = np.histogram(model.events["t"], bins=edges, weights=-eta * G_e)[0]
    exposure_blocks = np.zeros(len(edges) - 1)
    data = model.node_data
    for j in range(0, len(data["t"]), 2048):
        raw = {k: v[j:j + 2048] for k, v in data.items()}
        nout = model._rows(raw, x, need_h=True, need_g=True)
        L, _B, _h, _dL = model.values_from_out(raw, x, nout)
        g = nout[:, 6]
        contrib = raw["w"] * L * (-np.expm1(-eta * g))
        exposure_blocks += np.histogram(raw["t"], bins=edges, weights=contrib)[0]
    block_scores = event_blocks + exposure_blocks
    return dict(
        block_days=int(block_days),
        edges=[float(v) for v in edges],
        event_blocks=[float(v) for v in event_blocks],
        exposure_blocks=[float(v) for v in exposure_blocks],
        block_scores=[float(v) for v in block_scores],
        total=float(block_scores.sum()),
    )


def block_uncertainty(model, x, block_days=(90, 180, 365)):
    from experiments.methodological_audit.score_uncertainty_cuda_frozen_v2_20261111 import resample

    out = {}
    for days in block_days:
        blocks = attenuation_blocks(model, x, days)
        out[str(days)] = dict(blocks=blocks, resample=resample(blocks["block_scores"]))
    return out


def heldout_profile(model, x, eta_total, eta_imm, need_arrays=False):
    """Delta held-out score at the two training-selected eta values."""
    x = np.asarray(x, dtype=float)
    out_e = model._event_out(x)
    lam_e, B_e, h_e, _ = model.values_from_out(model.events, x, out_e)
    G_e = out_e[:, 6]
    S_total = float(G_e.sum())
    S_imm = float(np.sum(B_e / lam_e * G_e))
    if eta_total == 0.0 and eta_imm == 0.0:
        return dict(delta_test_total=0.0, delta_test_immigrant=0.0,
                    test_event_sum=S_total, test_event_sum_immigrant=S_imm)
    A_total = 0.0
    A_imm = 0.0
    parts = []
    data = model.node_data
    for j in range(0, len(data["t"]), 2048):
        raw = {k: v[j:j + 2048] for k, v in data.items()}
        nout = model._rows(raw, x, need_h=True, need_g=True)
        L, LB, _h, _ = model.values_from_out(raw, x, nout)
        g = nout[:, 6]
        w = raw["w"]
        parts.append((w, L, LB, L - LB, g))
    w = np.concatenate([p[0] for p in parts])
    L = np.concatenate([p[1] for p in parts])
    LB = np.concatenate([p[2] for p in parts])
    nH = np.concatenate([p[3] for p in parts])
    G_n = np.concatenate([p[4] for p in parts])
    delta_total = float(_profile_total([eta_total], S_total, w * L, G_n)[0])
    delta_imm = float(
        _profile_immigrant([eta_imm], B_e, lam_e - B_e, G_e, w * LB, G_n)[0]
    )
    result = dict(delta_test_total=delta_total, delta_test_immigrant=delta_imm,
                  test_event_sum=float(S_total), test_event_sum_immigrant=float(S_imm))
    if need_arrays:
        result["_arrays"] = dict(w=w, L=L, LB=LB, nH=nH, G_n=G_n,
                                 G_e=G_e, lam_e=lam_e, B_e=B_e)
    return result
