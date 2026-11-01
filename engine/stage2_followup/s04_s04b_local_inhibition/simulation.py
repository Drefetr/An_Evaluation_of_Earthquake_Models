"""Predictable thinning coordinator; provider owns compiled normalized kernels.

Provider contract: envelope(t, history, end) returns an upper bound on TOTAL
uninhibited intensity per unit area over [t,end) and all D until the next
accepted event. intensity(t,x,y,history) includes the requested inhibition.
sample_location(rng) is uniform over D with area provider.area_km2. Marks use
provider.sample_mark(rng). History entries are immutable (time,x,y,Q) tuples.
No branching-tree post-thinning is performed. No event rows are printed.
"""
import math

def simulate(provider,rng,start,end,prehistory,*,max_proposals):
    if not math.isfinite(start+end) or end<=start or max_proposals<1:raise ValueError('M02_SIM_WINDOW')
    area=float(provider.area_km2)
    if not math.isfinite(area) or area<=0:raise ValueError('M02_SIM_AREA')
    history=[tuple(row) for row in prehistory]
    if any(len(row)!=4 or not all(math.isfinite(v) for v in row) or row[0]>=start for row in history):raise ValueError('M02_SIM_PREHISTORY')
    history.sort();t=start;out=[];proposals=0
    while t<end:
        bound=float(provider.envelope(t,tuple(history),end))
        if not math.isfinite(bound) or bound<0:raise ArithmeticError('M02_SIM_ENVELOPE')
        if bound==0:break
        candidate=t+float(rng.exponential(1/(area*bound)))
        if candidate<=t:raise ArithmeticError('M02_SIM_CLOCK_PRECISION')
        if candidate>=end:break
        proposals+=1
        if proposals>max_proposals:return dict(status='unknown_proposal_budget',events=out,proposals=proposals)
        x,y=provider.sample_location(rng);value=float(provider.intensity(candidate,x,y,tuple(history)))
        if not math.isfinite(value) or value<0 or value>bound*(1+1e-12):raise ArithmeticError('M02_SIM_BOUND_VIOLATION')
        if float(rng.random())*bound<value:
            q=float(provider.sample_mark(rng))
            if not math.isfinite(q) or q<0:raise ArithmeticError('M02_SIM_MARK')
            row=(candidate,float(x),float(y),q);history.append(row);out.append(row)
        t=candidate
    return dict(status='resolved',events=out,proposals=proposals)
