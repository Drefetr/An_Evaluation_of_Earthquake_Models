"""Training-only weighted LOO and declustering orchestration.

The kernel provider computes normalized finite-domain component densities in
compiled code. Arrays remain local. This uses expected immigrant weights,
not a stochastic declustered realization; cite it as a Zhuang-inspired variant.
"""
import numpy as np
from scipy.optimize import minimize_scalar

GRID=(.5,1,2,3,5,10,15,25,50)
def loo_logscore(components,weights,reference_density,floor=.05):
    k=np.asarray(components,float);w=np.asarray(weights,float);b=np.asarray(reference_density,float)
    if k.shape!=(len(w),len(w)) or b.shape!=w.shape or len(w)<2:raise ValueError('M02_LOO_SHAPE')
    if not np.isfinite(k).all() or np.any(k<0) or not np.isfinite(w).all() or np.any(w<0) or not np.isfinite(b).all() or np.any(b<=0) or not 0<floor<1:raise ValueError('M02_LOO_DOMAIN')
    z=w.sum()-w
    if np.any(z<=0):raise ValueError('M02_LOO_EMPTY_WEIGHT')
    density=floor*b+(1-floor)*(k@w-k.diagonal()*w)/z
    if np.any(density<=0) or not np.isfinite(density).all():raise ValueError('M02_LOO_DENSITY')
    return float(w@np.log(density))

def select_bandwidth(provider,weights,reference_density):
    # provider(h) returns normalized target-by-component training density;
    # target identity equals component identity along the diagonal.
    cache={}
    def objective(logh):
        h=float(np.exp(logh));key=float(logh)
        if key not in cache:cache[key]=-loo_logscore(provider(h),weights,reference_density)
        return cache[key]
    candidates=[(float(np.log(h)),objective(np.log(h))) for h in GRID]
    # Optimize every adjacent interval, not one arbitrary unimodal bracket.
    for lo,hi in zip(GRID[:-1],GRID[1:]):
        fit=minimize_scalar(objective,bounds=(np.log(lo),np.log(hi)),method='bounded',options={'xatol':1e-8})
        if fit.success:candidates.append((float(fit.x),float(fit.fun)))
    best=min(candidates,key=lambda v:(v[1],v[0]))
    return dict(bandwidth=float(np.exp(best[0])),objective=best[1],candidates=candidates)

def decluster(provider,reference_density,refit,*,max_iterations=100,tolerance=1e-6):
    weights=np.ones(len(reference_density));trace=[]
    for iteration in range(max_iterations):
        bandwidth=select_bandwidth(provider,weights,reference_density)
        # refit is strictly training-only and must retain its eight starts/floor;
        # B/H are predictable fitted intensities at training events.
        B,H,receipt=refit(bandwidth['bandwidth'],weights.copy())
        B=np.asarray(B,float);H=np.asarray(H,float)
        if B.shape!=weights.shape or H.shape!=weights.shape or not np.isfinite(B+H).all() or np.any(B<0) or np.any(H<0) or np.any(B+H<=0):raise ValueError('M02_DECLUSTER_INTENSITY')
        updated=B/(B+H);change=float(np.max(abs(updated-weights)));trace.append(dict(iteration=iteration,bandwidth=bandwidth,change=change,fit_receipt=receipt));weights=updated
        if change<tolerance:return dict(status='converged',weights=weights,trace=trace)
    return dict(status='unknown_iteration_limit',weights=weights,trace=trace)
