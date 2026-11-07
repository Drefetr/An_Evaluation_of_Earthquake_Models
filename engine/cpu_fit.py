"""Explicit CPU adaptation of the archived iteration-27 small-fit recipe.

The original engine/iteration_27/code/horizon_pilot.py remains byte-identical to
its historical source pin. Only execution backend selection and result labels
are adapted here; this is a bounded CPU16/CPU32 control, not GPU parity.
"""
from pathlib import Path
from dataclasses import asdict
import copy
import math
import sys
import time
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent
HISTORICAL_SOURCE_SHA256 = '4a8f120690a9a506d28ec2393baeff161e7edf8307463fca986d5fbaade7982b'


def fit_pair(arrays,law,config,context,deadline,*,backend='cpu'):
    # Explicit backend; the historical default remains CUDA. CPU is a separate
    # CPU16/CPU32 numerical-refinement route, never a claim of GPU parity.
    if backend not in ('cpu','cuda'):raise ValueError('backend must be cpu or cuda')
    if backend=='cuda' and context is None:raise ValueError('CUDA context required')
    if backend=='cpu' and context is not None:raise ValueError('CPU route does not accept a CUDA context')
    sys.path.insert(0,str(ROOT/'iteration_20/code'))
    from restricted_history import RestrictedHistory
    kernel=law.trigger;ratio=law.ratio;records=[];h=fine=None
    try:
        search_deadline=deadline-config['validation_reserve_seconds']
        h=RestrictedHistory(arrays,law,clock_mode='paired_clock',order=16,backend=backend,context=context,deadline=search_deadline)
        rate=float(np.clip(math.log(max(len(arrays['times']),1)/law.horizon*.5),-11.5,-.1))
        bounds=[(-12.,0.),(-2.,2.),(0.,.98),(0.,3.)]
        def start(point,indices,label):
            best=None;attempts=[];x0=np.asarray(point,dtype=float)
            for maxls in config['maxls_tiers']:
                then=time.perf_counter()
                def fun(x):
                    p=x0.copy();p[indices]=x;return h.objective(p,kernel,ratio,True,indices)
                try:
                    r=minimize(fun,x0[indices].copy(),jac=True,method='L-BFGS-B',bounds=[bounds[i] for i in indices],
                               options=dict(maxiter=config['maxiter'],maxls=maxls,ftol=1e-10,gtol=2e-6))
                    p=x0.copy();p[indices]=r.x;value=h.objective(p,kernel,ratio,False)
                    ok=bool(r.success and np.isfinite(p).all() and np.isfinite(value) and abs(value-r.fun)<1e-4 and value<=h.objective(x0,kernel,ratio,False)+1e-8)
                    attempts.append(dict(success=ok,optimizer_success=bool(r.success),message=str(r.message),pars=p.tolist(),nll=value,maxls=maxls,nit=int(r.nit),nfev=int(r.nfev),elapsed_seconds=time.perf_counter()-then))
                    if ok:best=dict(pars=p.tolist(),nll=value,trigger=asdict(kernel),ratio=ratio);break
                except Exception as exc:
                    attempts.append(dict(success=False,maxls=maxls,error=type(exc).__name__+': '+str(exc),elapsed_seconds=time.perf_counter()-then))
                    if time.perf_counter()>=search_deadline:break
            records.append(dict(label=label,start=x0.tolist(),free=indices,attempts=attempts,complete=best is not None))
            if best is None:raise RuntimeError('Unresolved prescribed solver '+label)
            return best
        nulls=[start([rate,0.,.35,0.],[0,1,2],'null0'),start([max(-12.,rate-.5),.1,.7,0.],[0,1,2],'null1')]
        null=min(nulls,key=lambda p:p['nll']);alts=[copy.deepcopy(null)]
        for eta in [0.,.2]:
            point=list(null['pars']);point[3]=eta;alts.append(start(point,[0,1,2,3],'alternative_eta_'+str(eta)))
        alternative=min(alts,key=lambda p:p['nll']);h.deadline=deadline
        c16=h.contrast(null,alternative);coarse_values=[h.objective(p['pars'],kernel,ratio,False) for p in [null,alternative]]
        mark=h.mark_nll_constant;h.close();h=None
        if context is not None:context.torch.cuda.empty_cache()
        fine=RestrictedHistory(arrays,law,clock_mode='paired_clock',order=32,backend='cpu',deadline=deadline)
        cpu_values=[fine.objective(p['pars'],kernel,ratio,False) for p in [null,alternative]];c32=fine.contrast(null,alternative)
        deltas=[abs(a-b) for a,b in zip(coarse_values,cpu_values)]
        complete=max(deltas)<1e-4 and abs(c16['statistic']-c32['statistic'])<1e-4 and all(abs(c['direct_minus_subtraction'])<1e-4 and c['statistic']>=-1e-4 for c in [c16,c32])
        for p in [null,alternative]:p['full_marked_nll']=p['nll']+mark
        return dict(complete=complete,status='complete' if complete else 'numerical_gate_failed',null=null,alternative=alternative,
                    contrast16=c16,contrast32=c32,selected_NLL16=coarse_values,selected_NLL32=cpu_values,deltas=deltas,records=records,
                    fixed_beta=law.beta,coordinate_horizon=law.coordinate,clock_mode='paired_clock',mark_nll_constant=mark,
                    search_backend=backend,validation_backend='cpu',comparison_scope='CUDA16/CPU32 parity and refinement' if backend=='cuda' else 'CPU16/CPU32 refinement only')
    except Exception as exc:
        return dict(complete=False,status='fit_unresolved',error=type(exc).__name__+': '+str(exc),records=records)
    finally:
        for obj in [h,fine]:
            if obj is not None:obj.close()
