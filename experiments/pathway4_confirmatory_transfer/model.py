"""Interior-scale EP+ space-time likelihood with both observation-domain
normalisations and the frozen attenuation profiles.

The ground-process intensity is

    lambda(t, z) = exp(a + d x(t)) b(z) + n sum_j kappa_j h(t - t_j) f(z - z_j)

with ``h`` Omori, ``f`` a magnitude-scaled inverse-power kernel and
``kappa_j = 0.3 exp(0.7 beta (m_j - M0))`` (continuous marks) or the archived
reported-lattice analogue in Japan.  The two normalisations are:

``plane``
    ``f`` is the full-plane density ``(q-1)/(pi sigma_j^2) (1 + r^2/sigma_j^2)^-q``;
    the compensator retains the exact in-domain mass ``M_j < 1``.

``rect``
    ``f`` is normalised on the nine-cell union D, ``f / M_j``; the compensator
    therefore integrates each parent to one.

All integrals use analytic derivatives.  Attenuation is a separate frozen
one-dimensional profile on the null backbone, following Pathway 3's
low-dimensional winner rule.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.special import logsumexp

from .geometry import Background, Region


# --------------------------------------------------------------------------- #
# data containers
# --------------------------------------------------------------------------- #

@dataclass
class EPView:
    """One fitted or scored window with its strict-past parent history."""

    region: Region
    background: Background
    T0: float
    start: float
    end: float
    parent_time: np.ndarray
    parent_excess: np.ndarray
    parent_xy: np.ndarray
    parent_fertility: np.ndarray
    event_time: np.ndarray
    event_excess: np.ndarray
    event_xy: np.ndarray
    event_x: np.ndarray
    M0: float = 4.0
    beta: float = 2.0
    leave_self_background: bool = False
    be: Optional[np.ndarray] = None
    lag: Optional[np.ndarray] = None
    past: Optional[np.ndarray] = None
    r2: Optional[np.ndarray] = None

    def __post_init__(self):
        self.parent_time = np.asarray(self.parent_time, dtype=float)
        self.parent_excess = np.asarray(self.parent_excess, dtype=float)
        self.parent_xy = np.asarray(self.parent_xy, dtype=float)
        self.parent_fertility = np.asarray(self.parent_fertility, dtype=float)
        self.event_time = np.asarray(self.event_time, dtype=float)
        self.event_excess = np.asarray(self.event_excess, dtype=float)
        self.event_xy = np.asarray(self.event_xy, dtype=float)
        self.event_x = np.asarray(self.event_x, dtype=float)

    def attach_history(self):
        if self.lag is not None:
            return self
        self.lag = self.event_time[:, None] - self.parent_time[None, :]
        self.past = self.lag > 0.0
        self.r2 = ((self.event_xy[:, None, :] -
                    self.parent_xy[None, :, :]) ** 2).sum(axis=2)
        return self

    def background_at_events(self):
        if self.be is None:
            self.be = self.background.evaluate(
                self.event_xy, leave_self=self.leave_self_background)
        return self.be


# --------------------------------------------------------------------------- #
# null EP+ model
# --------------------------------------------------------------------------- #

class EPModel:
    """Eight-coordinate interior-scale EP+ model for one window."""

    NAMES = ("a", "d", "n", "log_c", "p", "log_sigma0", "alpha_s", "q")

    def __init__(self, view: EPView, normalization: str = "plane"):
        if normalization not in ("plane", "rect"):
            raise ValueError("normalization must be plane or rect")
        self.view = view.attach_history()
        self.normalization = normalization
        self.be = view.background_at_events()

    # -- helpers ---------------------------------------------------------- #
    def _sigma2(self, x):
        return np.exp(2.0 * x[5] + 2.0 * x[6] * self.view.parent_excess)

    def _sigma(self, x):
        return np.exp(x[5] + x[6] * self.view.parent_excess)

    def _mass_and_log_derivatives(self, x):
        """In-domain plane-normalised mass and log derivatives (plane only)."""
        sigma = self._sigma(x)
        mass, dlog, dq = self.view.region.mass(
            self.view.parent_xy, sigma, float(x[7]))
        if np.any(mass <= 0) or not np.isfinite(mass).all():
            raise FloatingPointError("non-positive in-domain mass")
        # d log M / d log sigma0 and d log M / d alpha_s
        dlog_m_dlogsigma = dlog / mass
        dlog_m_dalpha = dlog_m_dlogsigma * self.view.parent_excess
        dlog_m_dq = dq / mass
        return mass, dlog_m_dlogsigma, dlog_m_dalpha, dlog_m_dq

    # -- event term ------------------------------------------------------- #
    def H(self, x, deriv: bool = True):
        a, d, n, lc, p, ls, alph, q = [float(v) for v in x[:8]]
        if not (p > 1.0 and q > 1.0 and n >= 0.0):
            raise FloatingPointError("outside kernel domain")
        c = math.exp(lc)
        sigma2 = np.exp(2.0 * ls + 2.0 * alph * self.view.parent_excess)
        lag, r2, past = self.view.lag, self.view.r2, self.view.past
        lag_pos = np.maximum(lag, 0.0)
        v = r2 / sigma2
        tl = np.log1p(lag_pos / c)
        sl = np.log1p(v)
        k = ((p - 1.0) / c * np.exp(-p * tl) *
             (q - 1.0) / (np.pi * sigma2) * np.exp(-q * sl) *
             self.view.parent_fertility * past)
        if self.normalization == "plane":
            ds = -2.0 + 2.0 * q * v / (1.0 + v)
            dq = 1.0 / (q - 1.0) - sl
        else:
            mass, dl, da, dq_m = self._mass_and_log_derivatives(x)
            k = k / mass[None, :]
            ds = (-2.0 + 2.0 * q * v / (1.0 + v)) - dl[None, :]
            dq = 1.0 / (q - 1.0) - sl - dq_m[None, :]
        h = k.sum(axis=1)
        if not deriv:
            return h
        grad = np.zeros((len(h), 8))
        grad[:, 2] = h
        grad[:, 3] = (k * (-1.0 + p * lag_pos / (c + lag_pos))).sum(axis=1)
        grad[:, 4] = (k * (1.0 / (p - 1.0) - tl)).sum(axis=1)
        grad[:, 5] = (k * ds).sum(axis=1)
        grad[:, 6] = (k * ds * self.view.parent_excess[None, :]).sum(axis=1)
        grad[:, 7] = (k * dq).sum(axis=1)
        return h, grad

    # -- exposure --------------------------------------------------------- #
    def exposure(self, x):
        a, d, n, lc, p, ls, alph, q = [float(v) for v in x[:8]]
        c = math.exp(lc)
        pt = self.view.parent_time
        lo = np.maximum(self.view.start - pt, 0.0)
        hi = self.view.end - pt
        valid = hi > 0.0
        ul = np.log1p(lo / c)
        uh = np.log1p(np.maximum(hi, 0.0) / c)
        tl = np.exp((1.0 - p) * ul)
        th = np.exp((1.0 - p) * uh)
        J = np.where(valid, tl - th, 0.0)
        Jc = np.where(valid,
                      (p - 1.0) * (tl * lo / (c + lo) -
                                   th * np.maximum(hi, 0.0) /
                                   (c + np.maximum(hi, 0.0))), 0.0)
        Jp = np.where(valid, -ul * tl + uh * th, 0.0)
        if self.normalization == "plane":
            mass, dlog_m_dlogsigma, dlog_m_dalpha, dlog_m_dq = \
                self._mass_and_log_derivatives(x)
        else:
            mass = np.ones(len(pt))
            dlog_m_dlogsigma = np.zeros(len(pt))
            dlog_m_dalpha = np.zeros(len(pt))
            dlog_m_dq = np.zeros(len(pt))
        kpJ = self.view.parent_fertility * J
        energy = float((kpJ * mass).sum())
        E_off = n * energy

        # exact exponential-trend background integral over the window
        length = self.view.end - self.view.start
        z = d * length / self.view.T0
        centre = (self.view.start + self.view.end) / self.view.T0 - 1.0
        if abs(z) < 1e-5:
            sinc = 1.0 + z * z / 6.0 + z ** 4 / 120.0
            corr = length / self.view.T0 * (z / 3.0 - z ** 3 / 45.0)
        else:
            sinc = math.sinh(z) / z
            corr = length / self.view.T0 * (1.0 / math.tanh(z) - 1.0 / z)
        B = math.exp(a + d * centre) * length * sinc
        E = B + E_off
        grad = np.zeros(8)
        grad[0] = B
        grad[1] = B * (centre + corr)
        grad[2] = energy
        grad[3] = n * float((self.view.parent_fertility * Jc * mass).sum())
        grad[4] = n * float((self.view.parent_fertility * Jp * mass).sum())
        grad[5] = n * float((kpJ * mass * dlog_m_dlogsigma).sum())
        grad[6] = n * float((kpJ * mass * dlog_m_dalpha).sum())
        grad[7] = n * float((kpJ * mass * dlog_m_dq).sum())
        return E, grad

    # -- objective -------------------------------------------------------- #
    def objective(self, x, deriv: bool = True):
        x = np.asarray(x, dtype=float)
        if x.shape != (8,):
            raise ValueError("eight-coordinate EP+ vector required")
        h, hg = self.H(x)
        mu = np.exp(x[0] + x[1] * self.view.event_x) * self.be
        lam = mu + x[2] * h
        if np.any(lam <= 0) or not np.isfinite(lam).all():
            raise FloatingPointError("non-positive event intensity")
        P = float(np.log(lam).sum())
        E, gE = self.exposure(x)
        nll = E - P
        if not deriv:
            return nll
        grad = gE.copy()
        grad[0] -= float(np.sum(mu / lam))
        grad[1] -= float(np.sum(mu * self.view.event_x / lam))
        grad[2] -= float(np.sum(h / lam))
        grad[3:] -= np.sum(x[2] * hg[:, 3:] / lam[:, None], axis=0)
        return nll, grad

    # -- scoring ---------------------------------------------------------- #
    def H_temporal(self, x):
        """Temporal marginal offspring rate without the spatial factor."""
        lc, p = float(x[3]), float(x[4])
        c = math.exp(lc)
        lag_pos = np.maximum(self.view.lag, 0.0)
        k = ((p - 1.0) / c * np.exp(-p * np.log1p(lag_pos / c)) *
             self.view.parent_fertility * self.view.past)
        return k.sum(axis=1)

    def scores(self, x):
        """Ground-process and decomposed scores for the attached window."""
        x = np.asarray(x, dtype=float)
        h = self.H(x, deriv=False)
        mu = np.exp(x[0] + x[1] * self.view.event_x) * self.be
        lam = mu + x[2] * h
        if np.any(lam <= 0) or not np.isfinite(lam).all():
            raise FloatingPointError("non-positive event intensity")
        P = float(np.log(lam).sum())
        E, _ = self.exposure(x)
        level = np.exp(x[0] + x[1] * self.view.event_x)
        temporal = level + x[2] * self.H_temporal(x)
        timing = float(np.sum(np.log(temporal)) - E)
        location = P - float(np.sum(np.log(temporal)))
        return dict(P=P, E=E, timing=timing, location=location,
                    ground_joint=P - E, n_events=int(len(lam)),
                    log_intensity=np.log(lam))

    def point_quantities(self, x):
        """Point intensity, background and triggering components at events."""
        h = self.H(x, deriv=False)
        mu = np.exp(x[0] + x[1] * self.view.event_x) * self.be
        return mu, x[2] * h, mu + x[2] * h


# --------------------------------------------------------------------------- #
# frozen attenuation profiles
# --------------------------------------------------------------------------- #

def _kernel_shape(v, kernel: str):
    if kernel == "mono":
        one = 1.0 + v
        return 1.0 / (one * one), 4.0 * v / (one * one * one)
    if kernel == "ann2":
        one = 1.0 + v
        one2 = one * one
        return 16.0 * v * v / (one2 * one2), \
            64.0 * v * v * (v - 1.0) / (one2 * one2 * one)
    raise ValueError("unknown attenuation kernel")


def wells_coppersmith_ell(excess, M0: float):
    """Subsurface rupture length in km from the absolute magnitude."""
    return 10.0 ** (-2.44 + 0.59 * (M0 + np.asarray(excess, dtype=float)))


class AttenuationProfile:
    """One frozen attenuation arm on a fixed EP+ null backbone.

    ``mono`` uses the epicentral kernel and an optional ``(ell0, psi)`` pair
    with rupture scaling.  ``ann2_wc`` uses Pathway 1's second-order annulus
    with the parameter-free Wells-Coppersmith scale and psi fixed at 5 days.
    """

    def __init__(self, model: EPModel, kernel: str, ell0_km: Optional[float],
                 psi_days: float, gamma: float, scaled: bool = True,
                 wc: bool = False, M0: float = 4.0):
        if kernel not in ("mono", "ann2"):
            raise ValueError("unknown kernel")
        self.model = model
        self.kernel = kernel
        self.ell0 = ell0_km
        self.psi = float(psi_days)
        self.gamma = float(gamma)
        self.scaled = bool(scaled)
        self.wc = bool(wc)
        self.M0 = float(M0)

    def _ell(self, excess):
        if self.wc:
            return wells_coppersmith_ell(excess, self.M0)
        if self.scaled:
            return self.ell0 * 10.0 ** (0.5 * np.asarray(excess))
        return np.full(len(excess), self.ell0)

    def G(self, x8, deriv: bool = True):
        """Event and node contraction of the attenuation kernel."""
        view = self.model.view
        lag, r2, past = view.lag, view.r2, view.past
        lag_pos = np.maximum(lag, 0.0)
        ell = self._ell(view.parent_excess)
        v = r2 / ell[None, :] ** 2
        K, dK = _kernel_shape(v, self.kernel)
        base = (view.parent_fertility[None, :] *
                np.exp(self.gamma * view.parent_excess[None, :] -
                       lag_pos / self.psi))
        k = base * K * past
        G = k.sum(axis=1)
        if not deriv:
            return G
        grad = np.stack([
            (k * (lag_pos / self.psi)).sum(axis=1),
            (k * view.parent_excess[None, :]).sum(axis=1),
            (base * dK * past).sum(axis=1),
        ], axis=1)  # [log psi, gamma, log ell0]
        return G, grad

    def G_nodes(self, t, xy):
        view = self.model.view
        lag = t[:, None] - view.parent_time[None, :]
        past = lag > 0.0
        lag_pos = np.maximum(lag, 0.0)
        r2 = ((xy[:, None, :] - view.parent_xy[None, :, :]) ** 2).sum(axis=2)
        ell = self._ell(view.parent_excess)
        v = r2 / ell[None, :] ** 2
        K, _ = _kernel_shape(v, self.kernel)
        base = (view.parent_fertility[None, :] *
                np.exp(self.gamma * view.parent_excess[None, :] -
                       lag_pos / self.psi))
        return (base * K * past).sum(axis=1)

def ann2_mass(region, xy, ell):
    """In-domain integral of ``16 v^2 / (1+v)^4`` with ``v=r^2/ell^2``."""
    ell = np.asarray(ell, dtype=float)
    m2 = region.mass(xy, ell, 2.0)[0]
    m3 = region.mass(xy, ell, 3.0)[0]
    m4 = region.mass(xy, ell, 4.0)[0]
    return 16.0 * np.pi * ell ** 2 * (m2 - m3 + m4 / 3.0)


def ann2_radius(u, ell):
    """Exact inverse CDF of the full-plane ann2 radial kernel."""
    q = np.clip(1.0 - np.asarray(u, dtype=float), 1e-15, 1.0) ** (1.0 / 3.0)
    v = q / np.maximum(1.0 - q, 1e-15)
    return np.asarray(ell, dtype=float) * np.sqrt(v)


def _kernel_nodes(t, xy, parents_t, parents_xy, parents_kp, parents_excess,
                  ell, psi, gamma, kernel):
    lag = t[:, None] - parents_t[None, :]
    past = lag > 0.0
    lag_pos = np.maximum(lag, 0.0)
    r2 = ((xy[:, None, :] - parents_xy[None, :, :]) ** 2).sum(axis=2)
    v = r2 / ell[None, :] ** 2
    K, _ = _kernel_shape(v, kernel)
    base = parents_kp[None, :] * np.exp(gamma * parents_excess[None, :] -
                                        lag_pos / psi)
    return (base * K * past).sum(axis=1)


def make_attenuation_nodes(model: EPModel, x8, ell, psi_days: float,
                           gamma: float, power: int = 13,
                           seed: int = 20261116):
    """Importance proposal proportional to the frozen ann2 attenuation field.

    Sampling the attenuation kernel itself removes the severe variance of a
    null-intensity proposal when ``psi`` is much shorter than the Omori tail.
    The proposal is the total ann2 field ``G``; its normalisation
    ``Z_G = sum_j kappa_j exp(gamma q_j) T_j S_j`` is known analytically.
    """
    view = model.view
    start, end = view.start, view.end
    ell = np.asarray(ell, dtype=float)
    if ell.shape != view.parent_time.shape:
        raise ValueError("ell vector must match the parent history")
    lo = np.maximum(start - view.parent_time, 0.0)
    hi = np.maximum(end - view.parent_time, 0.0)
    temporal_mass = np.where(hi > lo,
                             psi_days * -np.expm1(-(hi - lo) / psi_days), 0.0)
    spatial_mass = ann2_mass(view.region, view.parent_xy, ell)
    weight = (view.parent_fertility * np.exp(gamma * view.parent_excess) *
              temporal_mass * spatial_mass)
    good = weight > 0
    if not good.any():
        raise FloatingPointError("empty attenuation proposal")
    weight = weight / weight.sum()
    Z_G = float(np.sum(view.parent_fertility *
                       np.exp(gamma * view.parent_excess) *
                       temporal_mass * spatial_mass))
    from scipy.stats import qmc
    u = qmc.Sobol(4, scramble=True, seed=seed).random_base2(power)
    N = len(u)
    ix = np.searchsorted(np.cumsum(weight), np.minimum(u[:, 0], 1.0 - 1e-15))
    lo_ix, hi_ix = lo[ix], hi[ix]
    lag = -psi_days * np.log1p(-u[:, 1] *
                               (1.0 - np.exp(-(hi_ix - lo_ix) / psi_days)))
    radius = ann2_radius(u[:, 2], ell[ix])
    ang = 2.0 * np.pi * u[:, 3]
    t = view.parent_time[ix] + lo_ix + lag
    xy = view.parent_xy[ix] + radius[:, None] * np.c_[np.cos(ang), np.sin(ang)]
    keep = (t >= start) & (t < end) & view.region.inside(xy)
    t, xy = t[keep], xy[keep]
    if len(t) == 0:
        raise FloatingPointError("empty attenuation node set")
    b = view.background.evaluate(xy)
    h = _triggering_density(model, dict(t=t, xy=xy), x8)
    mu = np.exp(x8[0] + x8[1] * (2.0 * t / view.T0 - 1.0)) * b
    lam = mu + x8[2] * h
    G = _kernel_nodes(t, xy, view.parent_time, view.parent_xy,
                      view.parent_fertility, view.parent_excess,
                      ell, psi_days, gamma, "ann2")
    return dict(t=t, xy=xy, b=b, lam=lam, G_proposal=G, Z_G=Z_G,
                w=np.full(len(t), Z_G / len(t)),
                draws=N, inside=int(keep.sum()), proposal="ann2")


def _triggering_density(model: EPModel, prep, x8):
    a, d, n, lc, p, ls, alph, q = [float(v) for v in x8[:8]]
    c = math.exp(lc)
    view = model.view
    lag = prep["t"][:, None] - view.parent_time[None, :]
    past = lag > 0.0
    r2 = ((prep["xy"][:, None, :] - view.parent_xy[None, :, :]) ** 2).sum(axis=2)
    sigma2 = np.exp(2.0 * ls + 2.0 * alph * view.parent_excess)
    v = r2 / sigma2
    k = ((p - 1.0) / c * np.exp(-p * np.log1p(np.maximum(lag, 0.0) / c)) *
         (q - 1.0) / (np.pi * sigma2) * np.exp(-q * np.log1p(v)) *
         view.parent_fertility * past)
    return k.sum(axis=1)


def _attenuation_quantities(model: EPModel, x8, kernel: str,
                            ell0_km: Optional[float], psi_days: float,
                            gamma: float, nodes):
    profile = AttenuationProfile(model, kernel, ell0_km, psi_days, gamma,
                                 scaled=(ell0_km is not None),
                                 wc=(ell0_km is None),
                                 M0=getattr(model.view, "M0", 4.0))
    G_event = profile.G(x8, deriv=False)
    G_target = profile.G_nodes(nodes["t"], nodes["xy"])
    G_prop = np.maximum(nodes["G_proposal"], 1e-300)
    weighted = nodes["w"] * nodes["lam"]
    S = float(G_event.sum())
    g_exposure = float(np.sum(weighted * G_target / G_prop))
    return profile, S, G_target, G_prop, weighted, g_exposure


def test_attenuation_gain(model: EPModel, x8, kernel: str,
                          ell0_km: Optional[float], psi_days: float,
                          gamma: float, eta: float, nodes,
                          max_eta: float = 4.0):
    """Held-out attenuation contrast at a training-selected eta."""
    profile, S, G_target, G_prop, weighted, g_exposure = \
        _attenuation_quantities(model, x8, kernel, ell0_km, psi_days,
                                gamma, nodes)
    deficit = float(np.sum(weighted * -np.expm1(-eta * G_target) / G_prop))
    gain = float(deficit - eta * S)
    return dict(eta=float(eta), gain=gain, event_sum=S,
                exposure_integral=g_exposure,
                node_sum_exposure=float(weighted.sum()),
                kernel=kernel, ell0_km=ell0_km, psi_days=psi_days,
                gamma=gamma, wc=bool(ell0_km is None),
                proposal_Z_G=nodes.get("Z_G"))


def profile_attenuation(model: EPModel, x8, kernel: str,
                        ell0_km: Optional[float], psi_days: float,
                        gamma: float, nodes, eta_grid=None,
                        max_eta: float = 4.0):
    """Exact one-dimensional training profile on the frozen null backbone.

    The profile is the positive NLL gain ``deficit(eta) - eta*S``; it is
    concave with derivative ``sum(w*lambda*G*exp(-eta*G)) - S``.  The exact
    nested ``eta = 0`` state is selected whenever the null slope
    ``g_exposure - S`` is non-positive.
    """
    profile, S, G_target, G_prop, weighted, g_exposure = \
        _attenuation_quantities(model, x8, kernel, ell0_km, psi_days,
                                gamma, nodes)
    slope = g_exposure - S

    if eta_grid is None:
        eta_grid = np.linspace(0.0, max_eta, 81)

    def gain(eta):
        deficit = float(np.sum(weighted *
                               -np.expm1(-eta * G_target) / G_prop))
        return float(deficit - eta * S)

    def derivative(eta):
        return float(np.sum(weighted * np.exp(-eta * G_target) *
                            G_target / G_prop) - S)

    gains = np.array([gain(e) for e in eta_grid])
    if slope <= 0.0:
        eta_hat = 0.0
    else:
        lo, hi = 0.0, 1e-6
        while derivative(hi) > 0.0 and hi < max_eta:
            hi = min(2.0 * hi, max_eta)
        if derivative(hi) > 0.0:
            eta_hat = max_eta
        else:
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if derivative(mid) > 0:
                    lo = mid
                else:
                    hi = mid
            eta_hat = 0.5 * (lo + hi)
    return dict(eta=float(eta_hat), gain=float(gain(eta_hat)),
                slope_at_zero=float(slope), event_sum=S,
                exposure_integral=g_exposure,
                node_exposure_integral=float(weighted.sum()),
                eta_grid=[float(e) for e in eta_grid],
                profile=[float(v) for v in gains],
                kernel=kernel, ell0_km=ell0_km, psi_days=psi_days,
                gamma=gamma, wc=bool(ell0_km is None),
                proposal_Z_G=nodes.get("Z_G"))
