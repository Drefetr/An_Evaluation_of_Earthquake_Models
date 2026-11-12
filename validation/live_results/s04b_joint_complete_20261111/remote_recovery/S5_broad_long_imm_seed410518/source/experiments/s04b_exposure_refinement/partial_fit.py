"""Explicit original-semantics suffix for the sole reviewed partial total fit.

Completed prefix objects are imported, not fake optimizer returns. The original
attempt loop/fresh checks/final selection remain source-parity tested.
"""
import copy
import numpy as np
from experiments.s04b_joint_nuisance.fit import bounds, starts, expand, projected_gradient, boundary
from .adapter import require, same

def resume_partial_fit(phase,model,protocol,eligible,partial,checkpoint,optimizer):
    require(model=='LIplus_inclusive','Only the reviewed total partial arm can resume')
    box=bounds(protocol,model);dims=len(box)
    records=copy.deepcopy(partial['records'][:4]);candidates=copy.deepcopy(partial['candidates'])
    require(len(records)==4 and len(candidates)==5 and partial['resolved_starts']==[True]*4+[False], 'Wrong partial prefix')
    floor_score=copy.deepcopy(candidates[0]['score'])
    require(candidates[0]['kind']=='new_null_floor' and same(candidates[0]['parameters'],list(map(float,eligible))), 'Eligible floor changed')
    seed_starts=starts(protocol,len(phase.a['event_time']),model,eligible)
    for i,record in enumerate(records):
        require(record['start_index']==i and record['method']=='L-BFGS-B' and record['success'] is True and same(record['initial_parameters'],np.asarray(seed_starts[i],dtype=float).tolist()),'Reused initial point/record differs')
    require(same(partial['records'][4]['initial_parameters'],np.asarray(seed_starts[4],dtype=float).tolist()) and same(partial['records'][5]['initial_parameters'],np.asarray(seed_starts[4],dtype=float).tolist()),'Failed start4 original point differs')
    resolved=[True]*4;policy=protocol['solver']
    for index,initial in list(enumerate(seed_starts))[4:]:
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
