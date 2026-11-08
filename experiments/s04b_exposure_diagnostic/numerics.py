"""Diagnostic sums only. Nothing in this module feeds the frozen objective."""
from __future__ import annotations
import hashlib
import math
import time
import numpy as np


def array_identity(value):
    a = np.ascontiguousarray(value)
    return dict(shape=list(a.shape), dtype=a.dtype.str,
                sha256=hashlib.sha256(a.tobytes()).hexdigest())


def add_compensated(total, correction, value):
    """Kahan reduction along time, separately for each spatial row/channel."""
    y = value-correction
    new = total+y
    correction[:] = (new-total)-y
    total[:] = new


def same_node_sums(pt, marks, r2, area, background, times, weights, triggering,
                   theta, horizon, deadline=math.inf):
    """Mirror the native strict-past recurrence; retain positive integrands.

    NumPy elementwise transcendentals and compensated reductions are diagnostic
    alternatives, not claims of bitwise native equivalence. No grid is changed.
    Native H is the already prepared value block of the original BLAS product.
    """
    pt, marks, r2, area, background, times, weights, triggering, theta = (
        np.asarray(v, dtype=float) for v in
        (pt, marks, r2, area, background, times, weights, triggering, theta))
    ns, np_ = r2.shape
    nt = len(times)
    if (theta.shape != (8,) or not np.isfinite(theta).all() or nt == 0
            or triggering.shape != (ns, 3*nt) or len(pt) != np_
            or marks.shape != (np_,) or area.shape != (ns,)
            or background.shape != (ns,) or weights.shape != (nt,)
            or np.any(np.diff(pt) < 0) or np.any(np.diff(times) < 0)
            or not np.all(weights > 0) or not np.all(area > 0)
            or not np.all(background > 0) or horizon <= 0):
        raise ValueError('Invalid same-node diagnostic dimensions/order/weights')
    a, d, n, _, _, eta, logell, logpsi = theta
    ell, psi = math.exp(logell), math.exp(logpsi)
    if n < 0 or eta < 0 or ell <= 0 or psi <= 0:
        raise ValueError('Invalid diagnostic attenuation coordinates')
    # Same scalar time-line construction and strict-past condition as C++.
    pr = np.zeros(np_); pd = np.zeros(np_)
    qr = np.zeros(nt); qd = np.zeros(nt); ends = np.zeros(nt, dtype=int)
    clock = min(pt[0], times[0]) if np_ else times[0]
    consumed = 0
    for i, t in enumerate(times):
        if i % 256 == 0 and time.monotonic() >= deadline:
            raise TimeoutError('Diagnostic wall limit')
        while consumed < np_ and pt[consumed] < t:
            if pt[consumed] < clock:
                raise ValueError('Unordered diagnostic parents')
            pr[consumed] = (pt[consumed]-clock)/psi
            pd[consumed] = math.exp(-pr[consumed])
            clock = pt[consumed]; consumed += 1
        ends[i] = consumed; qr[i] = (t-clock)/psi
        qd[i] = math.exp(-qr[i]); clock = t
    ratio = r2/(ell*ell)
    radial = marks[None, :]/((1+ratio)*(1+ratio))
    G = np.zeros(ns); j = 0
    # Channels: Q0 background/trigger, Qa background/trigger, D background/trigger.
    sums = np.zeros((6, ns)); corrections = np.zeros_like(sums)
    absolute = np.zeros_like(sums); abs_corrections = np.zeros_like(sums)
    min_term = math.inf; min_G = math.inf; max_G = -math.inf
    min_H = math.inf; max_H = -math.inf; attenuation_zeros = 0
    nonfinite_terms = 0; negative_terms = 0
    for i, t in enumerate(times):
        if i % 64 == 0 and time.monotonic() >= deadline:
            raise TimeoutError('Diagnostic wall limit')
        while j < ends[i]:
            G *= pd[j]; G += radial[:, j]; j += 1
        G *= qd[i]
        B = math.exp(a+d*(2*t/horizon-1))*background
        H = triggering[:, i]
        w = area*weights[i]
        attenuation = np.exp(-eta*G)
        lost = -np.expm1(-eta*G)
        WB, WH = w*B, w*n*H
        terms = np.stack((WB, WH, WB*attenuation, WH*attenuation,
                          WB*lost, WH*lost))
        add_compensated(sums, corrections, terms)
        add_compensated(absolute, abs_corrections, np.abs(terms))
        nonfinite_terms += int(np.count_nonzero(~np.isfinite(terms)))
        negative_terms += int(np.count_nonzero(terms < 0))
        attenuation_zeros += int(np.count_nonzero(attenuation == 0))
        min_term = min(min_term, float(np.min(terms)))
        min_G = min(min_G, float(np.min(G))); max_G = max(max_G, float(np.max(G)))
        min_H = min(min_H, float(np.min(H))); max_H = max(max_H, float(np.max(H)))
    # fsum only reduces each already compensated spatial-row total.
    values = [math.fsum(row) for row in sums]
    absolutes = [math.fsum(row) for row in absolute]
    channels = ('Q0_background', 'Q0_trigger', 'Qa_background', 'Qa_trigger',
                'D_background', 'D_trigger')
    result = dict(zip(channels, values))
    result.update(Q0=math.fsum(values[:2]), Qa=math.fsum(values[2:4]),
                  D=math.fsum(values[4:]), absolute_term_sums=dict(zip(channels, absolutes)),
                  space_nodes=ns, time_nodes=nt, parents=np_, terms_per_channel=ns*nt,
                  nonfinite_terms=nonfinite_terms, negative_terms=negative_terms,
                  minimum_term=min_term, minimum_G=min_G, maximum_G=max_G,
                  minimum_H=min_H, maximum_H=max_H, attenuation_underflow_count=attenuation_zeros,
                  reduction='float64 per-spatial-row Kahan over time, math.fsum over space; diagnostic only')
    result['node_identity_residual'] = result['D']-(result['Q0']-result['Qa'])
    return result


def combine_chunks(chunks, baseline, original_deficit):
    ordered = sorted(chunks, key=lambda r: r['row_start'])
    if not ordered or any(r.get('native_return') is None or r.get('diagnostic') is None for r in ordered):
        raise ValueError('Incomplete diagnostic chunks')
    expected_start = 0
    for row in ordered:
        if row['row_start'] != expected_start:
            raise ValueError('Duplicated or missing spatial chunk')
        expected_start += row['space_nodes']
    keys = ('Q0_background', 'Q0_trigger', 'Qa_background', 'Qa_trigger', 'D_background', 'D_trigger')
    total = {key: math.fsum(r['diagnostic'][key] for r in ordered) for key in keys}
    for prefix in ('Q0', 'Qa', 'D'):
        total[prefix] = math.fsum((total[prefix+'_background'], total[prefix+'_trigger']))
    D = float(original_deficit[0]); E0 = float(baseline['E0'])
    # Explicit binary64 left fold, matching frozen NumPy `total += chunk`.
    # Python 3.12+ sum(float) can use a different summation algorithm.
    native_ordered = 0.
    for row in ordered:
        native_ordered += float(row['native_return'][0])
    E = E0-D; correction = E0-total['Q0']
    total.update(E0=E0, E0_background=baseline['background'], E0_trigger=baseline['trigger'],
                 original_D=D, original_E=E, quadrature_correction=correction,
                 positive_node_reconstruction=total['Qa']+correction,
                 native_minus_compensated_D=D-total['D'],
                 native_minus_compensated_D_scope='Includes elementwise/transcendental and reduction differences; not isolated summation error.',
                 original_deficit_identity_residual=D-(total['Q0']-total['Qa']),
                 diagnostic_node_identity_residual=total['D']-(total['Q0']-total['Qa']),
                 spatial_nodes=expected_start, chunks=len(ordered),
                 terms_per_channel=sum(r['diagnostic']['terms_per_channel'] for r in ordered),
                 absolute_term_sums={k: math.fsum(r['diagnostic']['absolute_term_sums'][k] for r in ordered) for k in keys},
                 native_chunk_ordered_sum=native_ordered)
    total['full_identity_residual'] = E-(total['Qa']+correction-total['original_deficit_identity_residual'])
    total['native_chunk_sum_matches_original_D'] = total['native_chunk_ordered_sum'] == D
    count = total['terms_per_channel']; eps = np.finfo(float).eps
    total['summation_scale_only'] = dict(terms=count, epsilon=eps,
        gamma_n=count*eps/(1-count*eps) if count*eps < 1 else None,
        scope='Reduction scale only; excludes elementwise, BLAS, transcendental and quadrature error. Not an error certificate.')
    return total
