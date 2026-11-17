"""Forecast-admissible background clocks for Pathway 2.

The archived monograph law is the un-centred affine clock

    x_trend(t) = 2 t / T0 - 1,          B(t) = exp(a + d x_trend(t)),

normalised by the whole catalogue horizon T0.  This module implements the
three replacement laws required by the Pathway 2 handoff:

    T0  trend       un-centred affine clock (archived comparator)
    T1  stationary  d == 0; B(t) = exp(a)
    T2  clamp       x(t) = min{0, (t - origin) / (origin - train_start)}
    T3  orth        T2 clock and a training-orthogonalised depletion field
    DSTAR           T0 clock with d fixed at the generating value

The analytic background integral and its derivative with respect to d are
provided for every law.  The T2/T3 clock is zero at the forecast origin and
constant on the held-out window, so no historical drift is extrapolated.
"""
from __future__ import annotations

import math

import numpy as np

LAWS = ("T0", "T1", "T2", "T3", "DSTAR")
T0_DAYS = 24394.0


class BackgroundLaw:
    """One background-clock law on a fixed (training, test) split."""

    def __init__(self, kind: str, T0: float, origin: float | None = None,
                 train_start: float | None = None, d_fixed: float | None = None):
        if kind not in LAWS:
            raise ValueError("unknown background law " + kind)
        self.kind = kind
        self.T0 = float(T0)
        self.origin = None if origin is None else float(origin)
        self.train_start = None if train_start is None else float(train_start)
        if kind in ("T2", "T3"):
            if self.origin is None or self.train_start is None:
                raise ValueError("T2/T3 require origin and train_start")
            if not self.origin > self.train_start:
                raise ValueError("origin must be after train_start")
            self.scale = self.origin - self.train_start
        if kind == "DSTAR" and d_fixed is None:
            raise ValueError("DSTAR requires d_fixed")
        self.d_fixed = None if d_fixed is None else float(d_fixed)
        # Training-orthogonalisation coefficients, filled by ``orthogonalise``.
        self.orth_c = 0.0
        self.orth_k = 0.0

    # -- clock -----------------------------------------------------------
    def x(self, t):
        t = np.asarray(t, dtype=float)
        if self.kind in ("T0", "DSTAR"):
            return 2.0 * t / self.T0 - 1.0
        if self.kind == "T1":
            return np.zeros_like(t)
        # T2 / T3
        return np.minimum(0.0, (t - self.origin) / self.scale)

    def x_scalar(self, t: float) -> float:
        return float(self.x(np.asarray([t], dtype=float))[0])

    # -- analytic integral ----------------------------------------------
    def integral(self, a: float, d: float, lo: float, hi: float):
        """Return (int exp(a+d x) dt, d/dd of that integral) on [lo, hi]."""
        lo = float(lo)
        hi = float(hi)
        if not hi > lo:
            raise ValueError("empty background interval")
        if self.kind in ("T0", "DSTAR"):
            return _trend_integral(a, self.effective_d(d), lo, hi, self.T0)
        if self.kind == "T1":
            value = math.exp(a) * (hi - lo)
            return value, 0.0
        # T2 / T3: split at the forecast origin.
        value = 0.0
        derivative = 0.0
        if lo < self.origin:
            left = min(hi, self.origin)
            v, dv = _clamp_integral(a, d, lo, left, self.origin, self.scale)
            value += v
            derivative += dv
        if hi > self.origin:
            right_lo = max(lo, self.origin)
            value += math.exp(a) * (hi - right_lo)
            # x == 0 on this branch, so the d derivative vanishes.
        return value, derivative

    # -- depletion orthogonalisation -------------------------------------
    def orthogonalise(self, g_event, x_event, g_node=None, x_node=None, node_weight=None,
                      primary: str = "event"):
        """OLS projection of G on (1, x) over the training window.

        Both the event-row and the exposure-node projections are recorded.  The
        event rows are the primary design because the depletion field enters the
        likelihood through ``-eta G`` at observed events; raw exposure nodes are
        dominated by near-zero stress in empty space-time cells.  The node
        projection is retained as a sensitivity.
        """
        if primary not in ("event", "node"):
            raise ValueError("primary must be event or node")
        g_event = np.asarray(g_event, dtype=float)
        x_event = np.asarray(x_event, dtype=float)
        event_c, event_k = _ols(g_event, x_event, None)
        node_c = node_k = None
        if g_node is not None and x_node is not None and node_weight is not None:
            node_c, node_k = _ols(g_node, x_node, node_weight)
        if primary == "node" and node_c is None:
            raise ValueError("node projection requested without nodes")
        self.orth_c, self.orth_k = ((node_c, node_k) if primary == "node"
                                    else (event_c, event_k))
        self.projection = dict(
            kind=("training-exposure weighted OLS on quadrature nodes" if primary == "node"
                  else "training-event OLS"),
            c=float(self.orth_c), k=float(self.orth_k),
            event_c=float(event_c), event_k=float(event_k),
            node_c=None if node_c is None else float(node_c),
            node_k=None if node_k is None else float(node_k),
            event_correlation_before=_corr(g_event, x_event),
            event_correlation_after=_corr(
                g_event - (self.orth_c + self.orth_k * x_event), x_event),
        )
        return self.projection

    def deplete(self, g, x):
        if self.kind != "T3":
            return np.asarray(g, dtype=float)
        return np.asarray(g, dtype=float) - (self.orth_c + self.orth_k * np.asarray(x, dtype=float))

    def effective_d(self, d: float) -> float:
        if self.kind == "T1":
            return 0.0
        if self.kind == "DSTAR":
            return self.d_fixed
        return float(d)

    def describe(self) -> dict:
        return dict(kind=self.kind, T0=self.T0, origin=self.origin,
                    train_start=self.train_start, d_fixed=self.d_fixed,
                    orth_c=self.orth_c if self.kind == "T3" else None,
                    orth_k=self.orth_k if self.kind == "T3" else None)


def _trend_integral(a: float, d: float, lo: float, hi: float, T0: float):
    half = (hi - lo) / T0
    center = (lo + hi) / T0 - 1.0
    z = d * half
    if abs(z) < 1e-5:
        sinhc = 1.0 + z * z / 6.0 + z ** 4 / 120.0
        correction = half * (z / 3.0 - z ** 3 / 45.0)
    else:
        sinhc = math.sinh(z) / z
        correction = half * (1.0 / math.tanh(z) - 1.0 / z)
    value = math.exp(a + d * center) * (hi - lo) * sinhc
    return value, value * (center + correction)


def _clamp_integral(a: float, d: float, lo: float, hi: float,
                    origin: float, scale: float):
    """Integral on [lo, hi] with x = (t-origin)/scale, divided by exp(a)."""
    u0 = (lo - origin) / scale
    u1 = (hi - origin) / scale
    if abs(d) < 1e-12:
        return math.exp(a) * (hi - lo), math.exp(a) * scale * 0.5 * (u1 * u1 - u0 * u0)
    e0 = math.exp(d * u0)
    e1 = math.exp(d * u1)
    value = math.exp(a) * scale * (e1 - e0) / d
    derivative = math.exp(a) * scale * (
        (u1 * e1 - u0 * e0) / d - (e1 - e0) / (d * d)
    )
    return value, derivative


def _ols(y, x, weight):
    y = np.asarray(y, dtype=float).ravel()
    x = np.asarray(x, dtype=float).ravel()
    if weight is None:
        w = np.ones_like(y)
    else:
        w = np.asarray(weight, dtype=float).ravel()
    if y.shape != x.shape or w.shape != y.shape or len(y) < 2 or not np.isfinite(y).all():
        raise ValueError("invalid orthogonalisation design")
    sw = w.sum()
    if not sw > 0:
        raise ValueError("nonpositive orthogonalisation weight")
    mx = float((w * x).sum() / sw)
    my = float((w * y).sum() / sw)
    sxx = float((w * (x - mx) ** 2).sum())
    if sxx <= 1e-18:
        return my, 0.0
    sxy = float((w * (x - mx) * (y - my)).sum())
    k = sxy / sxx
    return my - k * mx, k


def _corr(a, b):
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    if len(a) < 2 or a.std() == 0.0 or b.std() == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def law_for_split(kind: str, start: float, origin: float, end: float,
                  T0: float, d_fixed: float | None = None) -> BackgroundLaw:
    return BackgroundLaw(kind, T0, origin=origin, train_start=start, d_fixed=d_fixed)
