"""Conditional EP+ branching simulation and the eight pooled diagnostics.

The simulator follows the sequential branching algorithm of the archived EP+
pilot: immigrant thinning from ``Background.sample``, magnitude-scaled inverse
power offspring, Omori lags and the archived Gutenberg-Richter mark law.  The
diagnostic evaluator is a direct adaptation of the archived pure-Python
``original_full84`` Ux/Uy/ell formulas to the EP+ magnitude-scaled kernel.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from reproduction.regional.scoring_sources.original_full84 import (
    immigrant_integral, ks_uniform, line_integral, omori_interval)

from .geometry import Background, Region, radial_power_sample
from .model import EPModel


def _mark_sample(rng, beta, size):
    # continuous exponential GR above M0, density beta exp(-beta q)
    return -np.log1p(-rng.random(size)) / beta


def simulate_future(model: EPModel, x, rng: np.random.Generator,
                    max_events: int = 50000):
    """One conditional branching path on ``[start, end] x D``."""
    view = model.view
    a, d, n, lc, p, ls, alph, q = [float(v) for v in x[:8]]
    c = math.exp(lc)
    sigma0 = math.exp(ls)
    start, end, T0 = view.start, view.end, view.T0
    beta = view.beta
    # immigrant thinning
    x_end = 2.0 * end / T0 - 1.0
    x_start = 2.0 * start / T0 - 1.0
    x_max = max(x_start, x_end) if d > 0 else min(x_start, x_end)
    lam_max = math.exp(a + d * x_max)
    count = rng.poisson(lam_max * (end - start))
    if count > 0:
        t = rng.uniform(start, end, count)
        u = rng.random((count, 4))
        xy = view.background.sample(u, rng)
        accept = rng.random(count) < np.exp(a + d * (2.0 * t / T0 - 1.0)) / lam_max
        times = t[accept]
        xy = xy[accept]
        marks = _mark_sample(rng, beta, len(times))
        heap = [(float(times[i]), float(marks[i]), float(xy[i, 0]),
                 float(xy[i, 1])) for i in range(len(times))]
    else:
        heap = []
    # chronological branching
    heap.sort(key=lambda r: r[0])
    index = 0
    while index < len(heap) and len(heap) < max_events:
        t0, q0, x0, y0 = heap[index]
        index += 1
        kp = 0.3 * math.exp(0.7 * beta * q0)
        expected = n * kp
        if expected <= 0:
            continue
        n_off = rng.poisson(expected)
        if n_off == 0:
            continue
        lag = c * np.expm1(np.log1p(-rng.random(n_off)) / (1.0 - p))
        sigma = sigma0 * math.exp(alph * q0)
        radius = radial_power_sample(rng.random(n_off), sigma, q)
        angle = 2.0 * np.pi * rng.random(n_off)
        tt = t0 + lag
        xx = x0 + radius * np.cos(angle)
        yy = y0 + radius * np.sin(angle)
        keep = tt < end
        if not keep.any():
            continue
        tt, xx, yy = tt[keep], xx[keep], yy[keep]
        if model.normalization == "plane":
            inside = view.region.inside(np.c_[xx, yy])
            tt, xx, yy = tt[inside], xx[inside], yy[inside]
        else:
            # rect-normalised kernel: condition the plane spatial draw on D
            inside = view.region.inside(np.c_[xx, yy])
            while not inside.all():
                bad = ~inside
                m = int(bad.sum())
                radius_b = radial_power_sample(rng.random(m), sigma, q)
                angle_b = 2.0 * np.pi * rng.random(m)
                xx[bad] = x0 + radius_b * np.cos(angle_b)
                yy[bad] = y0 + radius_b * np.sin(angle_b)
                inside = view.region.inside(np.c_[xx, yy])
        if len(tt) == 0:
            continue
        marks = _mark_sample(rng, beta, len(tt))
        for i in range(len(tt)):
            if tt[i] < end:
                heap.append((float(tt[i]), float(marks[i]), float(xx[i]),
                             float(yy[i])))
        if index % 128 == 0:
            heap[index:] = sorted(heap[index:], key=lambda r: r[0])
    events = np.asarray(sorted(heap[:max_events], key=lambda r: r[0]),
                        dtype=float)
    if events.size == 0:
        return np.empty((0, 4))
    return events


def _line_integral_fast(lower, upper, horizontal, scale, q):
    """Branch-split line integral; avoids evaluating unused betainc branches."""
    if q == 2.0:
        return line_integral(lower, upper, horizontal, scale, q=2.0)
    from scipy.special import beta, betainc
    lo, hi, x = np.broadcast_arrays(np.asarray(lower, dtype=float),
                                    np.asarray(upper, dtype=float),
                                    np.asarray(horizontal, dtype=float))
    scale = np.asarray(scale, dtype=float)
    A = 1.0 + (x / scale) ** 2
    root = scale * np.sqrt(A)
    a = lo / root
    b = hi / root
    constant = 0.5 * beta(0.5, q - 0.5)

    def central(v):
        return constant * betainc(0.5, q - 0.5, v * v / (1.0 + v * v))

    def tail(v):
        return constant * betainc(q - 0.5, 0.5, 1.0 / (1.0 + v * v))

    value = np.empty_like(a)
    straddle = (a < 0.0) & (b > 0.0)
    if straddle.any():
        value[straddle] = central(-a[straddle]) + central(b[straddle])
    positive = a >= 0.0
    if positive.any():
        value[positive] = central(b[positive]) - central(a[positive])
    negative = b <= 0.0
    if negative.any():
        value[negative] = central(-a[negative]) - central(-b[negative])
    value = value * scale * A ** (0.5 - q)
    return np.where(hi > lo, value, 0.0)


def _strip_mass(x_events, region: Region, centers, scales, q: float,
                order: int = 8):
    """Mass of radial kernels in the left strip ``[x0, x_i] x [y0, y1]``.

    The strip mass is the one-dimensional integral over x of the analytic
    line integral in y.  A fixed Gauss-Legendre rule is used on each event's
    left interval.
    """
    from numpy.polynomial.legendre import leggauss
    z, w = leggauss(order)
    x0, x1, y0, y1 = region.bounds
    x_events = np.clip(np.asarray(x_events, dtype=float), x0, x1)
    half = (x_events - x0) / 2.0
    mid = (x_events + x0) / 2.0
    xq = mid[:, None] + half[:, None] * z[None, :]          # (N, order)
    dx = xq[:, None, :] - np.asarray(centers)[None, :, 0][:, :, None]
    lo = y0 - np.asarray(centers)[:, 1]
    hi = y1 - np.asarray(centers)[:, 1]
    val = _line_integral_fast(lo[None, :, None], hi[None, :, None], dx,
                              np.asarray(scales)[None, :, None], q)
    return half[:, None] * np.sum(val * w[None, None, :], axis=2)


def x_marginal_cdf(delta, scale, q):
    """Full-plane x-marginal CDF of the radial power kernel."""
    from scipy.special import betainc
    delta = np.asarray(delta, dtype=float)
    scale = np.asarray(scale, dtype=float)
    u = delta * delta / (scale * scale + delta * delta)
    fraction = betainc(0.5, q - 0.5, u)
    return 0.5 + 0.5 * np.sign(delta) * fraction


def _uniform_floor_masses(region: Region):
    """Uniform-floor mass helpers."""
    x0, x1, y0, y1 = region.bounds
    area = region.area

    def left_mass(x):
        xx = np.clip(x, x0, x1)
        return 0.05 * (xx - x0) * (y1 - y0) / area

    def full(x):
        inside = (x >= x0) & (x <= x1)
        return np.where(inside, 0.05 * (y1 - y0) / area, 0.0)

    def partial(x, y):
        inside = (x >= x0) & (x <= x1)
        yy = np.clip(y, y0, y1)
        return np.where(inside, 0.05 * (yy - y0) / area, 0.0)

    return left_mass, full, partial


def _reference_floor_masses(region: Region, pi):
    density = 0.05 * np.asarray(pi) / region.cell_areas

    def left_mass(x):
        out = np.zeros(len(x))
        for j, (cx0, cx1, cy0, cy1) in enumerate(region.rectangles):
            overlap = np.clip(np.minimum(x, cx1) - cx0, 0.0, None)
            out += density[j] * overlap * (cy1 - cy0)
        return out

    def full(x):
        out = np.zeros(len(x))
        for j, (cx0, cx1, cy0, cy1) in enumerate(region.rectangles):
            active = (x >= cx0) & (x <= cx1)
            out += np.where(active, density[j] * (cy1 - cy0), 0.0)
        return out

    def partial(x, y):
        out = np.zeros(len(x))
        for j, (cx0, cx1, cy0, cy1) in enumerate(region.rectangles):
            active = (x >= cx0) & (x <= cx1)
            yy = np.clip(y, cy0, cy1)
            out += np.where(active, density[j] * (yy - cy0), 0.0)
        return out

    return left_mass, full, partial


def diagnostics8(model: EPModel, x, events, order: int = 24):
    """Eight continuous conditional diagnostics for one realized path."""
    view = model.view
    region = view.region
    if events.ndim != 2 or events.shape[1] != 4:
        raise ValueError("events must be (n, 4)")
    events = events[np.argsort(events[:, 0])]
    a, d, n, lc, p, ls, alph, q = [float(v) for v in x[:8]]
    c = math.exp(lc)
    beta = view.beta
    start, end, T0 = view.start, view.end, view.T0
    pre = view.parent_time < start
    pre_t = view.parent_time[pre]
    pre_q = view.parent_excess[pre]
    pre_xy = view.parent_xy[pre]
    pre_kp = view.parent_fertility[pre]
    ev_t = events[:, 0]
    ev_q = events[:, 1]
    ev_xy = events[:, 2:]
    ev_kp = 0.3 * np.exp(0.7 * beta * ev_q)
    parent_t = np.r_[pre_t, ev_t]
    parent_q = np.r_[pre_q, ev_q]
    parent_xy = np.vstack([pre_xy, ev_xy]) if len(ev_xy) else pre_xy
    parent_kp = np.r_[pre_kp, ev_kp]
    parent_sigma = np.exp(ls + alph * parent_q)
    N = len(ev_t)
    if N == 0:
        return np.zeros(8)
    # parent in-domain mass for the compensator
    if model.normalization == "plane":
        mass, _, _ = region.mass(parent_xy, parent_sigma, q)
    else:
        mass = np.ones(len(parent_t))
    # temporal weights and full intensity at each event
    lag = ev_t[:, None] - parent_t[None, :]
    past = lag > 0.0
    lag_pos = np.maximum(lag, 0.0)
    temporal = (p - 1.0) / c * np.exp(-p * np.log1p(lag_pos / c)) * past
    weights = n * parent_kp[None, :] * temporal
    mu_level = np.exp(a + d * (2.0 * ev_t / T0 - 1.0))
    ground = mu_level + weights.sum(axis=1)
    bg = view.background.evaluate(ev_xy, leave_self=False)
    r2 = ((ev_xy[:, None, :] - parent_xy[None, :, :]) ** 2).sum(axis=2)
    v = r2 / parent_sigma[None, :] ** 2
    kplane = (q - 1.0) / (np.pi * parent_sigma[None, :] ** 2) * \
        np.exp(-q * np.log1p(v))
    if model.normalization == "plane":
        spatial = kplane
    else:
        spatial = kplane / mass[None, :]
    point = mu_level * bg + (weights * spatial).sum(axis=1)
    if np.any(point <= 0) or np.any(ground <= 0):
        raise FloatingPointError("non-positive diagnostic intensity")
    # compensator
    lo = np.maximum(start - parent_t, 0.0)
    hi = end - parent_t
    valid = hi > 0
    ul = np.log1p(lo / c)
    uh = np.log1p(np.maximum(hi, 0.0) / c)
    J = np.where(valid, np.exp((1.0 - p) * ul) -
                 np.exp((1.0 - p) * uh), 0.0)
    B = float(immigrant_integral(a, d, start, end, T0))
    E = B + float(n * np.sum(parent_kp * J * mass))
    # gap rescaled uniforms
    prev = np.r_[start, ev_t[:-1]]
    gap_lo = np.maximum(prev[:, None] - parent_t[None, :], 0.0)
    gap_hi = ev_t[:, None] - parent_t[None, :]
    gap_valid = gap_hi > 0.0
    gap_int = np.where(gap_valid,
                       np.exp((1.0 - p) * np.log1p(gap_lo / c)) -
                       np.exp((1.0 - p) * np.log1p(np.maximum(gap_hi, 0.0) / c)),
                       0.0)
    gap_bg = immigrant_integral(a, d, prev, ev_t, T0)
    gap_off = n * (gap_int @ parent_kp)
    Ugap = -np.expm1(-(gap_bg + gap_off))
    # background floor
    if view.background.floor_cell is None:
        left_mass, floor_full, floor_partial = _uniform_floor_masses(region)
    else:
        pi = view.background.floor_cell * region.cell_areas / 0.05
        left_mass, floor_full, floor_partial = _reference_floor_masses(region, pi)
    # background KDE CDF contributions
    train_xy = view.background.xy
    train_w = view.background.weights
    train_mass = view.background.mass
    train_x = x_marginal_cdf(ev_xy[:, None, 0] - train_xy[None, :, 0],
                             view.background.h, 2.0)
    dx = ev_xy[:, None, 0] - train_xy[None, :, 0]
    train_full = _line_integral_fast(region.bounds[2] - train_xy[None, :, 1],
                                     region.bounds[3] - train_xy[None, :, 1],
                                     dx, view.background.h, 2.0) / \
        (np.pi * view.background.h ** 2) / train_mass[None, :]
    train_partial = _line_integral_fast(region.bounds[2] - train_xy[None, :, 1],
                                        ev_xy[:, None, 1] - train_xy[None, :, 1],
                                        dx, view.background.h, 2.0) / \
        (np.pi * view.background.h ** 2) / train_mass[None, :]
    bg_x = (train_x * train_w[None, :]).sum(axis=1)
    bg_full = (train_full * train_w[None, :]).sum(axis=1)
    bg_partial = (train_partial * train_w[None, :]).sum(axis=1)
    # parent spatial CDF contributions
    parent_x = x_marginal_cdf(ev_xy[:, None, 0] - parent_xy[None, :, 0],
                              parent_sigma[None, :], q)
    if model.normalization == "plane":
        parent_x = parent_x * mass[None, :]
    parent_full = _line_integral_fast(region.bounds[2] - parent_xy[None, :, 1],
                                      region.bounds[3] - parent_xy[None, :, 1],
                                      ev_xy[:, None, 0] - parent_xy[None, :, 0],
                                      parent_sigma[None, :], q)
    parent_full = parent_full * (q - 1.0) / (np.pi * parent_sigma[None, :] ** 2)
    parent_partial = _line_integral_fast(region.bounds[2] - parent_xy[None, :, 1],
                                         ev_xy[:, None, 1] - parent_xy[None, :, 1],
                                         ev_xy[:, None, 0] - parent_xy[None, :, 0],
                                         parent_sigma[None, :], q)
    parent_partial = parent_partial * (q - 1.0) / (np.pi * parent_sigma[None, :] ** 2)
    if model.normalization != "plane":
        parent_full = parent_full / mass[None, :]
        parent_partial = parent_partial / mass[None, :]
    numerator_x = (mu_level * (left_mass(ev_xy[:, 0]) +
                               0.95 * bg_x) +
                   (weights * parent_x).sum(axis=1))
    denominator = (mu_level * (floor_full(ev_xy[:, 0]) +
                               0.95 * bg_full) +
                   (weights * parent_full).sum(axis=1))
    numerator = (mu_level * (floor_partial(ev_xy[:, 0], ev_xy[:, 1]) +
                             0.95 * bg_partial) +
                 (weights * parent_partial).sum(axis=1))
    ux = np.clip(numerator_x / ground, 0.0, 1.0)
    uy = np.clip(numerator / np.maximum(denominator, 1e-300), 0.0, 1.0)
    ell = np.log(point) - np.log(ground) + math.log(region.area)
    return np.array([
        E,
        float(np.log(ground).sum()),
        float(ks_uniform(Ugap)),
        float(np.mean((Ugap[1:] - 0.5) * (Ugap[:-1] - 0.5))) if N > 1 else 0.0,
        float(max(ks_uniform(ux), ks_uniform(uy))),
        abs(float(np.mean((ux - 0.5) * (uy - 0.5)))),
        float(np.mean(ell)),
        float(np.var(ell)),
    ])


COORDINATES = ("exposure", "time_event_logsum", "gap_ks", "gap_serial",
               "spatial_rosenblatt_ks_max", "spatial_rosenblatt_cross_abs",
               "location_dimensionless_log_mean",
               "location_dimensionless_log_variance")
