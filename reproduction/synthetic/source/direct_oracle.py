"""Independent small-fixture scalar M02 oracle. No execution on import.

Uses direct parent sums at every quadrature node, never the engine recurrence,
cached matrices, shared library, or production objective implementation.
Input layout follows the documented integrated ABI. Intended only for small
fixtures under the conductor's numerical lease, not production workloads.
"""
import math


def _logadd(a, b):
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    hi, lo = max(a, b), min(a, b)
    return hi + math.log1p(math.exp(lo-hi))


def evaluate(parents, events, space, times, weights, meta, params,
             plus=False, inclusive=False):
    """Return [NLL, d_eta, d_logell, d_logpsi, deficit, logpoints].

    All arrays are Python iterables; rows are parent[t,x,y,Q,kappa,Z],
    event[t,x,y,b,H,reference_b], space[x,y,area,b,reference_b].
    This reference accepts validated inputs; ABI rejection is tested separately.
    """
    a, d, n, c, power, horizon, basecomp, marks, sigma = meta
    eta, logell, logpsi = params
    ell, psi = math.exp(logell), math.exp(logpsi)
    gamma = .75*math.log(10.) if plus else 0.

    def fields(time, x, y):
        values, ls, ps = [], [], []
        for tp, xp, yp, q, _, _ in parents:
            lag = time-tp
            if lag <= 0:
                continue
            r2 = (x-xp)**2+(y-yp)**2
            one = 1+r2/(ell*ell)
            v = math.exp(gamma*q-lag/psi)/(one*one)
            values.append(v)
            ls.append(v*4*(one-1)/one)
            ps.append(v*lag/psi)
        return math.fsum(values), math.fsum(ls), math.fsum(ps)

    deficits, de, dl, dp = [], [], [], []
    for x, y, area, density, reference in space:
        for time, weight in zip(times, weights):
            h_terms = []
            for tp, xp, yp, _, kappa, z in parents:
                lag = time-tp
                if lag <= 0:
                    continue
                r2 = (x-xp)**2+(y-yp)**2
                spatial = math.exp(-2*math.log1p(r2/(sigma*sigma)))
                temporal = (power-1)/c*math.exp(-power*math.log1p(lag/c))
                h_terms.append(kappa*spatial*reference/z*temporal)
            background = math.exp(a+d*(2*time/horizon-1))*density
            trigger = n*math.fsum(h_terms)
            g, l, p = fields(time, x, y)
            exposure = weight*area*(background+(trigger if inclusive else 0))
            attenuated = exposure*math.exp(-eta*g)
            deficits.append(exposure*(-math.expm1(-eta*g)))
            de.append(-attenuated*g)
            dl.append(-attenuated*eta*l)
            dp.append(-attenuated*eta*p)

    points, pe, pl, pp = [], [], [], []
    for time, x, y, density, trigger, _ in events:
        g, l, p = fields(time, x, y)
        lb = a+d*(2*time/horizon-1)+math.log(density) if density>0 else -math.inf
        lh = math.log(trigger) if trigger>0 else -math.inf
        lp = _logadd(lb, lh)-eta*g if inclusive else _logadd(lb-eta*g, lh)
        if not math.isfinite(lp):
            raise ArithmeticError('nonfinite event log intensity')
        fraction = 1. if inclusive else (math.exp(lb-eta*g-lp) if density>0 else 0.)
        points.append(lp)
        pe.append(-g*fraction)
        pl.append(-eta*l*fraction)
        pp.append(-eta*p*fraction)
    deficit, point = math.fsum(deficits), math.fsum(points)
    out = [basecomp-deficit-point-marks,
           math.fsum(de)-math.fsum(pe), math.fsum(dl)-math.fsum(pl),
           math.fsum(dp)-math.fsum(pp), deficit, point]
    if not all(math.isfinite(v) for v in out):
        raise ArithmeticError('nonfinite oracle output')
    return out
