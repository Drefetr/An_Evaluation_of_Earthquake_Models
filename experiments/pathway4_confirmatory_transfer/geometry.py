"""Observation-domain geometry and the training-declustered background KDE.

The observation domain D is the union of the nine archived cells.  In both
regions the nine cells tile the Cartesian bounding rectangle exactly, so the
divergence-theorem boundary integral over the bounding rectangle is the exact
in-domain mass of a radial kernel.  The mass routine returns the integral of
the *unnormalised* kernel ``(1 + r^2 / scale^2) ** -q`` together with its
derivatives with respect to ``scale`` and ``q``.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from numpy.polynomial.legendre import leggauss


def boundary_mass(bounds, xy, scale, q: float, order: int = 32):
    """Plane-normalised radial-kernel mass over a rectangle.

    Returns the integral of ``(q - 1) / (pi * scale^2) * (1 + r^2/scale^2)^-q``
    over the rectangle, plus derivatives with respect to ``log(scale)`` and
    ``q``.  For a rectangle that contains the whole plane limit this tends to
    one; the value is therefore the in-domain plane-normalised mass.
    """
    xy = np.asarray(xy, dtype=float)
    if xy.ndim != 2 or xy.shape[1] != 2:
        raise ValueError("kernel centres must be (n, 2)")
    scale = np.broadcast_to(np.asarray(scale, dtype=float), (len(xy),)).copy()
    if np.any(scale <= 0) or not np.isfinite(scale).all():
        raise ValueError("positive finite kernel scales required")
    if not (np.isfinite(q) and q > 1.0):
        raise ValueError("kernel exponent must exceed one")
    b = np.asarray(bounds, dtype=float)
    if b.shape != (4,):
        raise ValueError("rectangle must be (x0, x1, y0, y1)")
    z, w = leggauss(order)
    mass = np.zeros(len(xy))
    dlog = np.zeros(len(xy))
    dq = np.zeros(len(xy))
    for axis, edge in ((0, b[0]), (0, b[1]), (1, b[2]), (1, b[3])):
        other = 1 - axis
        lo = b[2 * other] - xy[:, other]
        hi = b[2 * other + 1] - xy[:, other]
        cuts = np.clip(scale[:, None] * np.array([-10.0, -1.0, -0.1, 0.0,
                                                  0.1, 1.0, 10.0]),
                       lo[:, None], hi[:, None])
        cuts = np.sort(np.c_[lo, cuts, hi], axis=1)
        half = np.diff(cuts) / 2.0
        centre = (cuts[:, :-1] + cuts[:, 1:]) / 2.0
        v = centre[:, :, None] + half[:, :, None] * z
        dist = np.abs(edge - xy[:, axis])
        r2 = dist[:, None, None] ** 2 + v ** 2
        u = r2 / scale[:, None, None] ** 2
        logu = np.log1p(u)
        tail = np.exp((1.0 - q) * logu)
        den = 2.0 * np.pi * np.maximum(r2, 1e-300)
        weight = dist[:, None, None] * half[:, :, None] * w
        mass += np.sum(weight * (-np.expm1((1.0 - q) * logu)) / den,
                       axis=(1, 2))
        dlog += np.sum(weight * (-2.0 * (q - 1.0) * np.exp(-q * logu) /
                                 (2.0 * np.pi * scale[:, None, None] ** 2)),
                       axis=(1, 2))
        dq += np.sum(weight * tail * logu / den, axis=(1, 2))
    return mass, dlog, dq


class Region:
    def __init__(self, rectangles):
        self.rectangles = np.asarray(rectangles, dtype=float)
        if self.rectangles.shape != (9, 4):
            raise ValueError("nine-cell rectangle schema")
        r = self.rectangles
        self.bounds = np.array([r[:, 0].min(), r[:, 1].max(),
                                r[:, 2].min(), r[:, 3].max()], dtype=float)
        self.area = float((self.bounds[1] - self.bounds[0]) *
                          (self.bounds[3] - self.bounds[2]))
        self.cell_areas = ((r[:, 1] - r[:, 0]) * (r[:, 3] - r[:, 2]))
        if not np.isclose(self.cell_areas.sum(), self.area, rtol=0, atol=1e-6):
            raise ValueError("nine cells do not tile the bounding rectangle")

    def inside(self, xy):
        b = self.bounds
        xy = np.asarray(xy, dtype=float)
        return ((xy[:, 0] >= b[0]) & (xy[:, 0] <= b[1]) &
                (xy[:, 1] >= b[2]) & (xy[:, 1] <= b[3]))

    def labels(self, xy):
        """Nine-cell labels with north/east ownership of shared edges."""
        xy = np.asarray(xy, dtype=float)
        r = self.rectangles
        valid = ((xy[:, None, 0] >= r[None, :, 0]) &
                 (xy[:, None, 0] <= r[None, :, 1]) &
                 (xy[:, None, 1] >= r[None, :, 2]) &
                 (xy[:, None, 1] <= r[None, :, 3]))
        if not np.all(valid.any(axis=1)):
            raise ValueError("point outside the nine-cell union")
        return np.max(np.where(valid, np.arange(9)[None, :], -1), axis=1)

    def mass(self, xy, scale, q: float, order: int = 32):
        """Plane-normalised radial-kernel mass over D and its derivatives."""
        return boundary_mass(self.bounds, xy, scale, q, order)

    def cell_mass(self, xy, scale, q: float = 2.0, order: int = 32):
        """Plane-normalised mass of each kernel inside each of the nine cells."""
        xy = np.asarray(xy, dtype=float)
        scale = np.broadcast_to(np.asarray(scale, dtype=float), (len(xy),))
        out = np.empty((len(xy), 9))
        for j, rect in enumerate(self.rectangles):
            out[:, j] = boundary_mass(rect, xy, scale, q, order)[0]
        return out

    def union_area(self):
        return float(self.cell_areas.sum())


class Background:
    """Elliptical (power-two) KDE with a five-percent floor.

    The density is normalised on D.  Training evaluation can use the exact
    leave-one-out density by excluding the self weight.  ``floor_mode`` selects
    the California EP+ uniform floor (``0.05 / area``) or the archived EP
    nine-cell reference floor (``0.05 * pi_cell / area_cell``).
    """

    def __init__(self, xy, region: Region, h: float, weights=None,
                 reference_pi=None, floor_mode: str = "uniform"):
        self.xy = np.asarray(xy, dtype=float)
        self.region = region
        self.h = float(h)
        if floor_mode not in ("uniform", "reference"):
            raise ValueError("floor_mode must be uniform or reference")
        if floor_mode == "reference":
            if reference_pi is None:
                raise ValueError("reference floor needs cell reference mass")
            pi = np.asarray(reference_pi, dtype=float)
            if pi.shape != (9,) or np.any(pi <= 0) or abs(pi.sum() - 1) > 1e-10:
                raise ValueError("invalid reference cell mass")
            self.floor_cell = 0.05 * pi / region.cell_areas
        else:
            self.floor_cell = None
        self.floor_mode = floor_mode
        if weights is None:
            weights = np.ones(len(self.xy))
        w = np.asarray(weights, dtype=float)
        if w.shape != (len(self.xy),) or np.any(w < 0) or w.sum() <= 0:
            raise ValueError("invalid background weights")
        self.weights = w / w.sum()
        self.mass = region.mass(self.xy, np.full(len(self.xy), self.h), 2.0)[0]
        if np.any(self.mass <= 0):
            raise ValueError("non-positive KDE rectangle mass")

    def _floor(self, xy):
        if self.floor_cell is None:
            return np.full(len(xy), 0.05 / self.region.area)
        return self.floor_cell[self.region.labels(xy)]

    def evaluate(self, xy, leave_self: bool = False):
        xy = np.asarray(xy, dtype=float)
        floor = self._floor(xy)
        out = []
        for j in range(0, len(xy), 1024):
            r2 = ((xy[j:j + 1024, None, :] - self.xy[None, :, :]) ** 2).sum(axis=2)
            kernel = (1.0 / (np.pi * self.h ** 2) *
                      (1.0 + r2 / self.h ** 2) ** -2.0 / self.mass)
            if leave_self:
                ix = np.arange(j, min(j + 1024, len(xy)))
                kernel[np.arange(len(ix)), ix] = 0.0
                den = 1.0 - self.weights[ix]
                value = (kernel @ self.weights) / den
            else:
                value = kernel @ self.weights
            out.append(floor[j:j + 1024] + 0.95 * value)
        return np.concatenate(out)

    def sample(self, u, rng: Optional[np.random.Generator] = None):
        """Inverse-CDF component choice with rejection inside D."""
        if rng is None:
            rng = np.random.default_rng(11737)
        u = np.asarray(u, dtype=float)
        b = self.region.bounds
        xy = np.empty((len(u), 2))
        floor = u[:, 0] < 0.05
        xy[floor] = np.c_[b[0] + u[floor, 2] * (b[1] - b[0]),
                          b[2] + u[floor, 3] * (b[3] - b[2])]
        ix = np.searchsorted(np.cumsum(self.weights),
                             np.clip((u[~floor, 0] - 0.05) / 0.95, 0.0,
                                     1.0 - 1e-15))
        r = self.h * np.sqrt(u[~floor, 2] /
                             np.maximum(1.0 - u[~floor, 2], 1e-15))
        ang = 2.0 * np.pi * u[~floor, 3]
        v = self.xy[ix] + r[:, None] * np.c_[np.cos(ang), np.sin(ang)]
        bad = ~self.region.inside(v)
        while bad.any():
            uu = rng.random((int(bad.sum()), 2))
            rr = self.h * np.sqrt(uu[:, 0] / (1.0 - uu[:, 0]))
            aa = 2.0 * np.pi * uu[:, 1]
            v[bad] = self.xy[ix[bad]] + rr[:, None] * np.c_[np.cos(aa), np.sin(aa)]
            bad = ~self.region.inside(v)
        xy[~floor] = v
        return xy


def radial_power_sample(u, scale, q):
    """Inverse CDF for ``(1 + r^2/scale^2) ** -q`` on the full plane."""
    r2 = scale ** 2 * np.expm1(np.log1p(-np.asarray(u)) / (1.0 - q))
    return np.sqrt(r2)
