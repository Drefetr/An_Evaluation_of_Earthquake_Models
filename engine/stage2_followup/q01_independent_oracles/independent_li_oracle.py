"""Independent fixed-backbone LI oracle. No production imports or automatic jobs.

Inputs are local raw rows (time_days,x_km,y_km,Q), primitive nuisance metadata,
and positive quadrature nodes/area weights. No producer B/H/G or normalization
cache is accepted. Returned states are private; callers publish aggregate errors
only. Numerical use requires the conductor's separate machine lease.
"""
from dataclasses import dataclass
import math
import numpy as np


class _Sum4:
    """Four Neumaier accumulators; bounded storage for a full node stream."""
    def __init__(self):
        self.total = np.zeros(4)
        self.correction = np.zeros(4)

    def add(self, values):
        for k, value in enumerate(values):
            old = self.total[k]
            new = old+value
            self.correction[k] += ((old-new)+value if abs(old) >= abs(value)
                                   else (value-new)+old)
            self.total[k] = new

    def result(self):
        return self.total+self.correction


@dataclass(frozen=True)
class Backbone:
    a: float
    d: float
    n: float
    c: float
    p: float
    beta: float
    sigma: float
    T: float
    start: float
    end: float
    bg_floor: float
    kde_h: float


def rectangle_masses(centres, rectangles, scale):
    """q=2 rational kernel integral, independently derived by divergence.

    K=s^4/(s^2+r^2)^2=(s^2/2)div[r/(s^2+r^2)]. Boundary
    fluxes are elementary arctangents. Long-double internal evaluation limits
    cancellation; positive-domain checks fail closed rather than clipping.
    """
    centres = np.asarray(centres, dtype=np.longdouble).reshape(-1, 2)
    rect = np.asarray(rectangles, dtype=np.longdouble).reshape(-1, 4)
    ss = np.longdouble(scale) ** 2
    if not np.isfinite(ss) or ss <= 0:
        raise ValueError('ORACLE_SCALE')
    out = np.empty((len(centres), len(rect)), dtype=float)
    for k, (xl, xh, yl, yh) in enumerate(rect):
        if not xl < xh or not yl < yh:
            raise ValueError('ORACLE_RECTANGLE')
        x0, x1 = xl-centres[:, 0], xh-centres[:, 0]
        y0, y1 = yl-centres[:, 1], yh-centres[:, 1]
        def flux(edge, low, high):
            den = np.sqrt(ss+edge*edge)
            # atan2 retains a small angular difference without subtracting
            # two nearly equal arctangents; high-low is strictly positive.
            angle = np.arctan2(den*(high-low), den*den+low*high)
            return edge/den*angle
        out[:, k] = ss/2*(flux(x1, y0, y1)-flux(x0, y0, y1)
                         +flux(y1, x0, x1)-flux(y0, x0, x1))
    if np.any(out <= 0) or not np.isfinite(out).all():
        raise ArithmeticError('ORACLE_NORMALIZATION_CANCELLATION')
    return out


def cell_index(xy, rectangles):
    """Use the frozen last-matching-cell boundary convention explicitly."""
    xy, rect = np.asarray(xy, float), np.asarray(rectangles, float)
    index = np.full(len(xy), -1, dtype=int)
    for k, (xl, xh, yl, yh) in enumerate(rect):
        mask = ((xy[:, 0] >= xl) & (xy[:, 0] <= xh)
                & (xy[:, 1] >= yl) & (xy[:, 1] <= yh))
        index[mask] = k
    if np.any(index < 0):
        raise ValueError('ORACLE_OUTSIDE_DOMAIN')
    return index


class RawOracle:
    def __init__(self, rows, rectangles, reference_pi, kde_xy, kde_weight, law):
        self.law = law
        raw = np.asarray(rows, float)
        self.rect = np.asarray(rectangles, float).reshape(-1, 4)
        self.pi = np.asarray(reference_pi, float)
        self.kxy = np.asarray(kde_xy, float).reshape(-1, 2)
        self.kw = np.asarray(kde_weight, float)
        if raw.ndim != 2 or raw.shape[1] != 4 or not np.isfinite(raw).all():
            raise ValueError('ORACLE_RAW_SCHEMA')
        if np.any(np.diff(raw[:, 0]) < 0) or np.any(raw[:, 3] < 0):
            raise ValueError('ORACLE_RAW_CHRONOLOGY')
        if not law.start < law.end or not law.T > 0 or not law.c > 0 or not law.p > 1:
            raise ValueError('ORACLE_BACKBONE')
        if not 0 <= law.bg_floor <= 1 or not law.beta > 0 or not law.sigma > 0:
            raise ValueError('ORACLE_BACKBONE')
        self.area = ((self.rect[:, 1]-self.rect[:, 0])
                     *(self.rect[:, 3]-self.rect[:, 2]))
        if (self.pi.shape != self.area.shape or np.any(self.pi < 0)
                or abs(math.fsum(self.pi)-1) > 1e-12):
            raise ValueError('ORACLE_REFERENCE')
        if (self.kw.shape != (len(self.kxy),) or np.any(self.kw < 0)
                or (len(self.kw) and abs(math.fsum(self.kw)-1) > 1e-12)
                or (law.bg_floor < 1 and not len(self.kw))):
            raise ValueError('ORACLE_KDE_WEIGHT')
        self.bref = self.pi/self.area
        self.rows = raw[raw[:, 0] < law.end].copy()
        self.targets = self.rows[self.rows[:, 0] >= law.start]
        cell_index(self.rows[:, 1:3], self.rect)
        self.Z = rectangle_masses(self.rows[:, 1:3], self.rect, law.sigma) @ self.bref
        self.KZ = rectangle_masses(self.kxy, self.rect, law.kde_h).sum(axis=1)
        self.kappa = .3*np.exp(.7*law.beta*self.rows[:, 3])
        if np.any(self.Z <= 0) or not np.isfinite(self.kappa).all():
            raise ArithmeticError('ORACLE_PARENT_DOMAIN')
        lo = np.maximum(law.start-self.rows[:, 0], 0.)
        hi = law.end-self.rows[:, 0]
        # Exact finite-interval Omori mass, no inherited exposure cache.
        J = np.exp((1-law.p)*np.log1p(lo/law.c)) * (
            -np.expm1((1-law.p)*np.log1p((hi-lo)/(law.c+lo))))
        z = law.d*(law.end-law.start)/law.T
        sinhc = 1+z*z/6+z**4/120 if abs(z) < 1e-5 else math.sinh(z)/z
        Bmass = (math.exp(law.a+law.d*((law.start+law.end)/law.T-1))
                 *(law.end-law.start)*sinhc)
        self.basecomp = Bmass+law.n*math.fsum(self.kappa*J)
        self.marks = len(self.targets)*math.log(law.beta)-law.beta*math.fsum(self.targets[:, 3])

    def background(self, xy):
        xy = np.asarray(xy, float)
        b = self.law.bg_floor*self.bref[cell_index(xy, self.rect)]
        for j, centre in enumerate(self.kxy):
            r2 = np.sum((xy-centre)**2, axis=1)
            b += ((1-self.law.bg_floor)*self.kw[j]/self.KZ[j]
                  /(1+r2/self.law.kde_h**2)**2)
        if np.any(b <= 0) or not np.isfinite(b).all():
            raise ArithmeticError('ORACLE_BACKGROUND')
        return b

    def fields(self, times, xy, pars, plus):
        """Direct parent sum; no recursion and no shared producer features.

        Paired time/location queries, bounded caller block. Derivatives are
        with respect to eta, log(ell), log(psi), as required by the optimizer.
        """
        eta, logell, logpsi = np.asarray(pars, float)
        ell, psi = math.exp(logell), math.exp(logpsi)
        t, xy = np.asarray(times, float), np.asarray(xy, float)
        lag = t[:, None]-self.rows[None, :, 0]
        past = lag > 0
        positive_lag = np.maximum(lag, 0.)
        r2 = np.sum((xy[:, None, :]-self.rows[None, :, 1:3])**2, axis=2)
        rho = r2/ell**2
        logstress = ((.75*math.log(10) if plus else 0)*self.rows[None, :, 3]
                     -positive_lag/psi-2*np.log1p(rho))
        stress = np.exp(logstress)*past
        G = stress.sum(axis=1)
        L = (stress*4*rho/(1+rho)).sum(axis=1)
        P = (stress*positive_lag/psi).sum(axis=1)
        temporal = ((self.law.p-1)/self.law.c
                    *np.exp(-self.law.p*np.log1p(positive_lag/self.law.c))*past)
        spatial = ((1+r2/self.law.sigma**2)**-2
                   *self.bref[cell_index(xy, self.rect), None]/self.Z[None, :])
        H = self.law.n*(temporal*spatial*self.kappa[None, :]).sum(axis=1)
        B = np.exp(self.law.a+self.law.d*(2*t/self.law.T-1))*self.background(xy)
        return B, H, G, L, P

    def evaluate(self, pars, plus, inclusive, space_xy, area_weights,
                 time_nodes, time_weights, block=128):
        """Full declared positive product rule. Keeps O(block*nparents) memory.

        area_weights must be actual dA weights; for the inherited calibrated
        rule they equal its frozen background-measure weights divided by b(s).
        That calibration is part of the declared numerical integration rule.
        """
        eta, le, lp = np.asarray(pars, float)
        if (not np.isfinite([eta, le, lp]).all() or not 0 <= eta <= 4
                or not math.log(5) <= le <= math.log(150)
                or not math.log(1/24) <= lp <= math.log(365)):
            raise ValueError('ORACLE_STRESS_BOUNDS')
        xy, aw = np.asarray(space_xy, float), np.asarray(area_weights, float)
        times, tw = np.asarray(time_nodes, float), np.asarray(time_weights, float)
        if (xy.shape != (len(aw), 2) or tw.shape != times.shape
                or np.any(aw <= 0) or np.any(tw <= 0) or block < 1
                or not np.isfinite(xy).all() or not np.isfinite(aw).all()
                or not np.isfinite(times).all() or not np.isfinite(tw).all()
                or np.any(times <= self.law.start) or np.any(times >= self.law.end)):
            raise ValueError('ORACLE_POSITIVE_QUADRATURE')
        integral_terms = _Sum4()
        for q, weight in zip(xy, aw):
            subtotal = np.zeros(4)
            for lo in range(0, len(times), block):
                t = times[lo:lo+block]
                B,H,G,L,P = self.fields(t, np.repeat(q[None, :], len(t), axis=0), pars, plus)
                A = B+H if inclusive else B
                wA = weight*tw[lo:lo+block]*A
                derivative_weight = -wA*np.exp(-eta*G)
                subtotal += [math.fsum(wA*(-np.expm1(-eta*G))),
                             math.fsum(derivative_weight*G),
                             math.fsum(derivative_weight*eta*L),
                             math.fsum(derivative_weight*eta*P)]
            integral_terms.add(subtotal)
        deficit, de, dl, dp = integral_terms.result()
        event_terms = _Sum4()
        for lo in range(0, len(self.targets), block):
            e = self.targets[lo:lo+block]
            B,H,G,L,P = self.fields(e[:, 0], e[:, 1:3], pars, plus)
            logB = self.law.a+self.law.d*(2*e[:,0]/self.law.T-1)+np.log(self.background(e[:,1:3]))
            logH = np.full(len(H), -np.inf)
            np.log(H, out=logH, where=H > 0)
            logpoint = (np.logaddexp(logB, logH)-eta*G if inclusive
                        else np.logaddexp(logB-eta*G, logH))
            fraction = np.ones(len(H)) if inclusive else np.exp(logB-eta*G-logpoint)
            event_terms.add([math.fsum(logpoint), math.fsum(-G*fraction),
                            math.fsum(-eta*L*fraction), math.fsum(-eta*P*fraction)])
        point, pe, pl, pp = event_terms.result()
        result = np.array([self.basecomp-deficit-point-self.marks,
                           de-pe, dl-pl, dp-pp, deficit, point])
        if not np.isfinite(result).all():
            raise ArithmeticError('ORACLE_NONFINITE_RESULT')
        return result


def log_time_rule(parent_times, start, end, c, order):
    """Independent construction of the frozen log-Omori positive time rule."""
    z, w = np.polynomial.legendre.leggauss(order)
    parent_times = np.asarray(parent_times, float)
    edges = sorted(set([start, end]+parent_times[(parent_times > start)
                                                & (parent_times < end)].tolist()))
    nodes, weights = [], []
    for left, right in zip(edges[:-1], edges[1:]):
        span = math.log1p((right-left)/c)
        v = span*(1+z)/2
        nodes.extend(left+c*np.expm1(v))
        weights.extend(c*span/2*np.exp(v)*w)
    return np.array(nodes), np.array(weights)


def aggregate_max_errors(reference, candidate):
    """Only this reduced record is suitable for model-facing numerical output."""
    a, b = np.asarray(reference, float), np.asarray(candidate, float)
    if a.shape != b.shape or a.shape[-1] != 6 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('ORACLE_COMPARISON_SCHEMA')
    delta = np.abs(a-b)
    return dict(states=int(np.prod(a.shape[:-1])), nll_maxabs=float(delta[...,0].max()),
                gradient_maxabs=float(delta[...,1:4].max()),
                deficit_maxabs=float(delta[...,4].max()), point_maxabs=float(delta[...,5].max()))
