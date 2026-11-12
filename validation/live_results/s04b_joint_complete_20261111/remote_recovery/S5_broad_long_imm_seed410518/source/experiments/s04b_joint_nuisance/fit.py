"""Identical bounded eight-start budgets for the new joint procedures."""
import math
import numpy as np
from scipy.optimize import minimize

MODELS=('LI','LIplus_immigrant','LIplus_inclusive')

def bounds(protocol,model):
    return protocol['shared_bounds']+([]if model=='null'else protocol['inhibition_bounds'])

def expand(x,model):
    return np.r_[x,[0.,math.log(30.),math.log(7.)]]if model=='null'else np.asarray(x,dtype=float)

def starts(protocol,N,model,null=None):
    a0=float(np.clip(math.log(.6*max(N,1)/365),-11.5,-.1));out=[]
    for i,(da,d,n,c,p)in enumerate(protocol['starts']['shared_templates']):
        shared=[float(np.clip(a0+da,-12,0)),d,n,math.log(c),p]
        if model=='null':out.append(shared)
        else:
            eta,ell,psi=protocol['starts']['inhibition_templates'][i]
            if i==0:shared=list(null[:5])
            out.append([*shared,eta,math.log(ell),math.log(psi)])
    return out

def projected_gradient(theta,gradient,box,tolerance=1e-8):
    p=np.asarray(gradient,dtype=float).copy()
    for i,(value,(lo,hi))in enumerate(zip(theta,box)):
        if value<=lo+tolerance and p[i]>0 or value>=hi-tolerance and p[i]<0:p[i]=0.
    return p

def boundary(theta,box,tolerance=1e-8):
    return [('lower'if abs(v-lo)<=tolerance else'upper'if abs(v-hi)<=tolerance else None)for v,(lo,hi)in zip(theta,box)]

def fit_arm(phase,model,protocol,eligible,checkpoint=lambda record:None,optimizer=minimize):
    box=bounds(protocol,model);dims=len(box);records=[];candidates=[]
    floor_score,floor_gradient=phase.evaluate(eligible,model,8)
    candidates.append(dict(state_index=0,kind='historical_floor'if model=='null'else'new_null_floor',start_index=-1,
                           parameters=list(map(float,eligible)),score=floor_score,gradient=floor_gradient.tolist()))
    seed_starts=starts(protocol,len(phase.a['event_time']),model,eligible)
    resolved=[];policy=protocol['solver']
    for index,initial in enumerate(seed_starts):
        current=np.asarray(initial,dtype=float);start_resolved=False
        for method in ('L-BFGS-B','Powell'):
            record=dict(start_index=index,method=method,initial_parameters=current.tolist(),status='running',success=False)
            checkpoint(dict(event='attempt_start',model=model,**record));last={};count=0;active=None
            def objective(x):
                nonlocal count,last,active
                full=expand(x,model);active=full.tolist()if np.isfinite(full).all()else None
                score,g=phase.evaluate(full,model,8,require_gradient=method=='L-BFGS-B');count+=1
                last=dict(parameters=full.tolist(),score=score,gradient=g.tolist()if np.isfinite(g).all()else None,evaluation_count=count)
                return score['nll'],g[:dims]
            options={k:policy[k]for k in ('maxiter','maxls','ftol','gtol')}if method=='L-BFGS-B'else policy['powell']
            try:
                result=optimizer(objective if method=='L-BFGS-B'else lambda x:objective(x)[0],current,
                                 jac=True if method=='L-BFGS-B'else False,bounds=box,method=method,options=options)
                x=np.asarray(result.x,dtype=float)
                finite=x.shape==(dims,)and np.isfinite(x).all()and np.isfinite(result.fun)and all(lo<=v<=hi for v,(lo,hi)in zip(x,box))
                record.update(status='returned',solver_success=bool(result.success),solver_status=int(result.status),message=str(result.message),
                              nfev=int(result.nfev),nit=int(result.nit),finite_feasible=bool(finite),
                              returned_parameters=x.tolist()if np.isfinite(x).all()else None,returned_nll=float(result.fun)if np.isfinite(result.fun)else None)
                if finite:
                    full=expand(x,model);fresh,g=phase.evaluate(full,model,8)
                    discrepancy=abs(fresh['nll']-float(result.fun))
                    record.update(parameters=full.tolist(),fresh_score=fresh,gradient=g.tolist(),fresh_nll_delta=discrepancy,
                                  projected_gradient=projected_gradient(x,g[:dims],box).tolist(),boundaries=boundary(x,box),
                                  success=bool(result.success and discrepancy<=1e-9))
                    current=x.copy()
                    if record['success']:
                        candidates.append(dict(state_index=len(candidates),kind='optimizer',start_index=index,parameters=full.tolist(),score=fresh,gradient=g.tolist()))
                        start_resolved=True
            except BaseException as exc:
                record.update(status='exception',error_type=type(exc).__name__,error=str(exc),last_evaluation=last,failed_evaluation_parameters=active)
                if not isinstance(exc,(ArithmeticError,FloatingPointError,OverflowError)):
                    records.append(record);checkpoint(dict(event='attempt_end',model=model,**record));raise
            records.append(record);checkpoint(dict(event='attempt_end',model=model,**record))
            if start_resolved:break
        resolved.append(start_resolved)
        if not start_resolved:
            return dict(status='unknown_starts',passed=False,model=model,records=records,candidates=candidates,resolved_starts=resolved,required_starts=8,not_run_starts=list(range(index+1,8)))
    selected=min(candidates,key=lambda v:(v['score']['nll'],v['kind']=='optimizer',v['start_index']))
    if selected['score']['nll']>floor_score['nll']+1e-9:raise ArithmeticError('Included feasible floor was worsened')
    gaps=[]
    if model!='null':
        gaps=[dict(state_index=c['state_index'],train_nll_improvement=floor_score['nll']-c['score']['nll'])for c in candidates
              if c['parameters'][5]==0 and floor_score['nll']-c['score']['nll']>1e-9]
    return dict(status='complete',passed=all(resolved),model=model,records=records,candidates=candidates,required_starts=8,
                selected_state_index=selected['state_index'],selected=selected,resolved_starts=resolved,
                null_search_gaps=gaps,meaning='Declared finite search completion, not global optimization')

def fine_check(phase,model,fit,protocol):
    state=fit['selected'];theta=state['parameters'];coarse,g=phase.evaluate(theta,model,8)
    fine,gf=phase.evaluate(theta,model,16);box=bounds(protocol,model);dims=len(box)
    pg=projected_gradient(theta[:dims],g[:dims],box);pf=projected_gradient(theta[:dims],gf[:dims],box)
    scaled=np.abs(pg-pf)/np.maximum(1.,np.maximum(np.abs(pg),np.abs(pf)))
    delta=abs(coarse['joint']-fine['joint']);gradient_delta=float(np.max(scaled,initial=0))
    passed=delta<=protocol['quadrature']['joint_absolute_tolerance']and gradient_delta<=protocol['quadrature']['selected_training_gradient_scaled_tolerance']and fine['E']>=0
    return dict(passed=bool(passed),coarse=coarse,fine=fine,absolute_joint_delta=delta,
                projected_gradient_coarse=pg.tolist(),projected_gradient_fine=pf.tolist(),
                projected_gradient_scaled_delta=gradient_delta,projected_kkt_infinity_norm=float(np.max(np.abs(pf),initial=0)),
                parameters=theta,selection='Coarse training selection retained, fine check only; no re-ranking or test selection')
