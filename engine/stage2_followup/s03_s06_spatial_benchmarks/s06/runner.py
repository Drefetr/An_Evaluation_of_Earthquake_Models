"""Resumable 36-procedure / 330-slot JMA forecast orchestration.

Run from the study directory with ``python -m source.research.jma_forecast_v1.runner``.
Only aggregate status is printed. Private event arrays and solver states stay local.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[_key]='1'
import argparse, json, math, sys, time
from contextlib import nullcontext
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from . import engine as E
ARMS=('FC','FL','MC','OC','OL','N0','EP')
COMPARISONS=(('OC_FC_timing','OC','FC','timing_logscore'),('OC_OL_location','OC','OL','conditional_location_logscore'),('OC_MC_joint','OC','MC','joint_logscore'),('FC_FL_location','FC','FL','conditional_location_logscore'),('OC_FL_joint','OC','FL','joint_logscore'),('OC_EP_joint','OC','EP','joint_logscore'),('OC_N0_joint','OC','N0','joint_logscore'))
REGISTERED_COMPARISONS=dict(zip((c[0] for c in COMPARISONS),('primary_timing','primary_location','context_freeML','context_spatial','complete_original','competitive_EP','context_N0')))
PROTOCOL=None
def verify_protocol(path=None):
    global PROTOCOL
    if path is not None:PROTOCOL=Path(path)
    if PROTOCOL is None:raise ValueError('--protocol is required for observed numerical execution')
    frozen=read(PROTOCOL);pins=frozen.get('artifact_pins')
    if not pins:raise ValueError('protocol artifact_pins must be nonempty')
    if isinstance(pins,dict):pins=[dict(path=p,sha256=h) for p,h in pins.items()]
    for pin in pins:
        target=Path(pin['path'])
        if not target.is_absolute():target=PROTOCOL.parent/target
        if E.sha(target)!=pin['sha256']:raise ValueError('frozen artifact changed: '+str(target))
    required={str(p.resolve()).lower() for p in E.HERE.iterdir() if p.suffix in ('.py','.cpp','.dll') or p.name=='build_receipt.json'}
    present={str((Path(p['path']) if Path(p['path']).is_absolute() else PROTOCOL.parent/p['path']).resolve()).lower() for p in pins}
    if not required<=present:raise ValueError('protocol must pin every current Python/C++/DLL source/runtime artifact')
    import scipy
    receipt=read(E.HERE/'build_receipt.json')
    if receipt['python']!=sys.version or receipt['numpy']!=np.__version__ or receipt['scipy']!=scipy.__version__:raise ValueError('pinned Python/numpy/scipy runtime mismatch')
    return frozen
def clean(x):
    if isinstance(x,np.ndarray):return clean(x.tolist())
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [clean(v) for v in x]
    if isinstance(x,float) and not math.isfinite(x):return {'nonfinite':str(x)}
    return x
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(clean(value),sort_keys=True,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)
def read(path):return json.loads(Path(path).read_text())
def load(pointer):
    pointer=Path(pointer);p=read(pointer)
    for key in ('arrays','array_metadata'):
        if E.sha(p[key]['path'])!=p[key]['sha256']:raise ValueError('immutable input '+key)
    with np.load(p['arrays']['path'],allow_pickle=False) as z:cat={k:z[k].copy() for k in z.files}
    t=cat['t_days'];keys=cat['history_key_cs'];K=cat['K'];xy=cat['xy_km'];cells=cat['cell_id']
    if not np.array_equal(t,keys/8640000) or np.any(np.diff(keys)<0) or np.any((np.diff(keys)>0)!=(np.diff(t)>0)):raise ValueError('exact clock/tie binding')
    if np.any(K<0) or not np.issubdtype(K.dtype,np.integer) or not np.array_equal(cat['Q'],K*.1):raise ValueError('reported lattice')
    expected=np.minimum(np.searchsorted(E.XEDGE,xy[:,0],side='right')-1,2)+3*np.minimum(np.searchsorted(E.YEDGE,xy[:,1],side='right')-1,2)
    if np.any(xy[:,0]<-600) or np.any(xy[:,0]>600) or np.any(xy[:,1]<-800) or np.any(xy[:,1]>800) or not np.array_equal(cells,expected):raise ValueError('fixed geometry')
    return cat,p
def ensure_cache(path,cat,nuis,start,end,sigma,family):
    path=Path(path)
    if not path.exists():
        a,m=E.features(cat,nuis,start,end,sigma,family);E.save_cache(path,a,m)
    else:
        _,m=E.load_cache(path)
        if (m['start'],m['end'],m['sigma_km'],m['family'],m['nuisance'])!=(float(start),float(end),float(sigma),family,nuis):raise ValueError('stale resumed cache')
    return path
def starts(arm,N,duration,prereq):
    a0=float(np.clip(math.log(.6*N/duration),-11.5,-.1));aP=float(np.clip(math.log(N/duration),-12,0))
    if arm in ('FC','FL'):return [[a0+off,d,n] for off in (0,-.5) for d in (-.2,.2) for n in (.2,.6)]
    if arm=='N0':return [[aP,d] for d in (-2,-1,-.5,-.2,.2,.5,1,2)]
    if arm=='MC':return [prereq['FC']+[math.log(t)] for t in (.001,.005,.02,.1,.5,1,5,20)]
    if arm in ('OC','OL'):
        pairs=((.0001,1.1),(.001,1.3),(.01,1.1),(.1,1.3),(1,1.7),(20,2.5),(.01,2.5),(.1,1.01))
        return [prereq['FC' if arm=='OC' else 'FL']+[math.log(c),p] for c,p in pairs]
    rows=((0,-.2,.2,.0001,1.1,2,1.1),(0,-.2,.6,.001,1.3,5,1.5),(0,.2,.2,.01,1.1,15,2),(0,.2,.6,.1,1.3,50,2.5),(-.5,-.2,.2,1,1.7,150,2),(-.5,-.2,.6,20,2.5,500,1.5),(-.5,.2,.2,.01,2.5,15,3),(-.5,.2,.6,.1,1.01,50,1.05))
    return [[a0+off,d,n,math.log(c),p,math.log(ell),q] for off,d,n,c,p,ell,q in rows]
def floors(arm,N,duration,prereq):
    aP=float(np.clip(math.log(N/duration),-12,0));p=[aP,0.] if arm=='N0' else [aP,0.,0.]
    if arm=='MC':p += [0.]
    if arm in ('OC','OL','EP'):p += [0.,1.3]
    if arm=='EP':p += [math.log(50),2.]
    result=[('constant_poisson',p)]
    if arm=='MC':result.append(('same_space_FC_tau1',prereq['FC']+[0.]))
    if arm=='EP':result.append(('fitted_N0',prereq['N0']+[0.,0.,1.3,math.log(50),2.]))
    return result
def compact(v):return {k:clean(x) for k,x in v.items() if k not in ('event_logs','event_conditional_cell_allocation')}
def registered_procedure_id(execution_id):
    if len(execution_id)>3 and execution_id[0]=='f' and execution_id[1].isdigit() and execution_id[2]=='_':
        fold=int(execution_id[1]);proc=execution_id[3:]
        template='SEL_FC_SIGMA'+str(int(E.SCALES[int(proc[4:])])) if proc.startswith('FC_s') else 'MAIN_'+proc
        return f'jma_fold_{fold}__{template}'
    return execution_id
FLOOR_LITERALS={'constant_poisson':'POISSON','same_space_FC_tau1':'NESTED_FC_TAU1','fitted_N0':'FITTED_N0'}
def fit(path,obj,arm,procedure_id,start_points,floor_points,deadline):
    path=Path(path);bd=E.bounds(arm)
    def feasible(x):return len(x)==len(bd) and np.isfinite(x).all() and all(lo<=v<=hi for v,(lo,hi) in zip(x,bd))
    def boundary_flags(x):return [dict(coordinate=i,lower=abs(v-lo)<=1e-7,upper=abs(v-hi)<=1e-7) for i,(v,(lo,hi)) in enumerate(zip(x,bd))]
    registered_id=registered_procedure_id(procedure_id)
    slots=[dict(slot_id=f'{procedure_id}.floor{i}',registered_slot_id=registered_id+':F_'+FLOOR_LITERALS[name],kind='floor',origin=name,start=clean(p),status='pending',attempts=[]) for i,(name,p) in enumerate(floor_points)]
    slots += [dict(slot_id=f'{procedure_id}.start{i}',registered_slot_id=registered_id+f':S{i:02d}',kind='start',start=clean(p),status='pending',attempts=[]) for i,p in enumerate(start_points)]
    if path.exists():r=read(path)
    else:
        r=dict(schema='jma_fit_procedure_v1',procedure_id=procedure_id,registered_procedure_id=registered_id,arm=arm,cache_path=str(obj.path.resolve()),cache_sha256=E.sha(obj.path),bounds=bd,slots=slots,status='pending',selected=None)
        write(path,r)
    prescribed=lambda seq:[(s['slot_id'],s.get('registered_slot_id'),s['kind'],s.get('origin'),s['start']) for s in seq]
    if r['cache_sha256']!=E.sha(obj.path) or r['procedure_id']!=procedure_id or r['arm']!=arm or clean(r['bounds'])!=clean(bd) or prescribed(r['slots'])!=prescribed(slots):raise ValueError('resumed procedure identity')
    for slot in r['slots']:
        if slot['status'] in ('complete','failed'):continue
        if time.time()>=deadline:r['status']='checkpoint_deadline';write(path,r);return r
        p=np.array(slot['start'],float)
        if not feasible(p):raise ValueError('prescribed infeasible start/floor, no clipping')
        if slot['kind']=='floor':
            rec=dict(candidate_id=slot['slot_id'],registered_candidate_id=slot['registered_slot_id'],slot_id=slot['slot_id'],kind='floor',x=p.tolist(),initial_x=p.tolist(),boundary_flags=boundary_flags(p),accepted=False)
            try:
                v=obj.evaluate(arm,p,detailed=True);f=obj.evaluate(arm,p,fine=True,detailed=True);delta=abs(v['joint_nll']-f['joint_nll']);rec.update(evaluation=compact(v),refined_evaluation=compact(f),evaluator_nll=v['joint_nll'],refined_nll=f['joint_nll'],initial_nll=v['joint_nll'],accepted=delta<=1e-4,reason='accepted' if delta<=1e-4 else 'refinement_disagreement')
            except Exception as exc:rec['reason']=repr(exc)
            slot['attempts'].append(rec);slot['status']='complete' if rec['accepted'] else 'failed';write(path,r);continue
        accepted=False
        for method,options in (('L-BFGS-B',dict(maxiter=200,maxfun=20000,maxls=200,ftol=1e-10,gtol=2e-6)),('Powell',dict(maxiter=400,maxfev=5000,xtol=1e-6,ftol=1e-10))):
            previous=[a for a in slot['attempts'] if a.get('method')==method]
            if previous and previous[-1].get('state')=='returned':
                if previous[-1]['accepted']:accepted=True;break
                continue
            if time.time()>=deadline:r['status']='checkpoint_deadline';write(path,r);return r
            for old in previous:
                if old.get('state')=='running':old.update(state='interrupted_no_return',reason='prior_process_interrupted')
            rec=dict(candidate_id=f"{slot['slot_id']}.{method}.{len(previous)}",registered_candidate_id=slot['registered_slot_id']+(':R_POWELL' if method=='Powell' else ''),slot_id=slot['slot_id'],kind='solver',method=method,options=options,initial_x=p.tolist(),accepted=False,state='running')
            slot['attempts'].append(rec);write(path,r);began=time.perf_counter()
            def target(x):
                if time.time()>=deadline:raise TimeoutError('stage deadline; resumable slot')
                v=obj.evaluate(arm,x);return v['joint_nll'],v['gradient']
            try:
                rec['initial_nll']=target(p)[0];write(path,r)
                opt=minimize((lambda x:target(x)[0]) if method=='Powell' else target,p,method=method,jac=None if method=='Powell' else True,bounds=bd,options=options)
                rec.update(x=opt.x.tolist(),solver_fun=float(opt.fun),solver_status=int(opt.status),solver_success=bool(opt.success),solver_message=str(opt.message),nfev=int(opt.nfev),nit=int(opt.nit),finite_feasible=bool(feasible(opt.x)),boundary_flags=boundary_flags(opt.x))
                if rec['finite_feasible']:
                    v=obj.evaluate(arm,opt.x,detailed=True);f=obj.evaluate(arm,opt.x,fine=True,detailed=True);rec.update(evaluation=compact(v),refined_evaluation=compact(f),evaluator_nll=v['joint_nll'],refined_nll=f['joint_nll'])
                    reasons=[]
                    if not opt.success:reasons.append('unsuccessful_solver')
                    if not math.isfinite(opt.fun) or abs(v['joint_nll']-opt.fun)>1e-7:reasons.append('solver_evaluator_disagreement')
                    if v['joint_nll']>rec['initial_nll']+1e-8:reasons.append('worse_than_start')
                    if abs(v['joint_nll']-f['joint_nll'])>1e-4:reasons.append('refinement_disagreement')
                    rec.update(accepted=not reasons,reason='accepted' if not reasons else ','.join(reasons))
                else:rec['reason']='nonfinite_or_infeasible'
                rec['state']='returned'
            except TimeoutError as exc:
                rec.update(state='interrupted_no_return',reason=str(exc),wall_seconds=time.perf_counter()-began);r['status']='checkpoint_deadline';write(path,r);return r
            except Exception as exc:rec.update(state='returned',reason=repr(exc))
            rec['wall_seconds']=time.perf_counter()-began;write(path,r)
            if rec['accepted']:accepted=True;break
        slot['status']='complete' if accepted else 'failed';write(path,r)
    eligible=[a for s in r['slots'] for a in s['attempts'] if a.get('accepted')]
    if eligible:
        best=min(eligible,key=lambda a:(a['evaluator_nll'],a['candidate_id']));r['selected']=best;r['winner_id']=best['candidate_id'];r['near_optimal_ids']=[a['candidate_id'] for a in eligible if a['evaluator_nll']<=best['evaluator_nll']+4e-4]
        r['selected']['boundary_flags']=[dict(coordinate=i,lower=abs(v-lo)<=1e-7,upper=abs(v-hi)<=1e-7) for i,(v,(lo,hi)) in enumerate(zip(best['x'],bd))]
    r['status']='complete' if all(s['status']=='complete' for s in r['slots']) else 'unknown_incomplete';write(path,r);return r
def annual_intervals(fold):
    # Fixed source-JST calendar years, equivalent literal UTC boundaries from epoch.
    epoch=datetime(2006,1,1,tzinfo=timezone.utc)
    # Windows are three calendar years; each source boundary is UTC+9 midnight.
    year=(2016,2019,2022)[fold]
    return [((datetime(y,1,1,tzinfo=timezone.utc)-epoch).days,(datetime(y+1,1,1,tzinfo=timezone.utc)-epoch).days,str(y)) for y in range(year,year+3)]
def score(path,cache,arm,x,obj=None):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        saved=read(path)
        if saved.get('status')=='complete' and (saved['cache_sha256']!=E.sha(cache) or saved['x']!=list(x) or saved['arm']!=arm or E.sha(saved['private_path'])!=saved['private_sha256']):raise ValueError('resumed forecast identity changed')
        return saved
    with (E.Objective(cache) if obj is None else nullcontext(obj)) as obj:
        v=obj.evaluate(arm,x,detailed=True);fine=obj.evaluate(arm,x,detailed=True,fine=True)
        if abs(v['joint_nll']-fine['joint_nll'])>1e-4:raise FloatingPointError('forecast refinement disagreement')
        private=path.with_suffix('.npz');np.savez(private,event_logs=v['event_logs'],event_conditional_cell_allocation=v['event_conditional_cell_allocation'],event_time=obj.a['event_time'],event_K=obj.a['event_K'],event_cell=obj.a['event_cell'],cell_integrated_intensity=v['cell_integrated_intensity'])
        counts=np.bincount(obj.a['event_cell'].astype(int),minlength=9);r=dict(schema='jma_forecast_score_v1',status='complete',arm=arm,x=x,cache_path=str(Path(cache).resolve()),cache_sha256=E.sha(cache),private_path=str(private.resolve()),private_sha256=E.sha(private),evaluation=compact(v),refined_evaluation=compact(fine),cell_observed=counts.tolist(),zone_observed=counts.reshape(3,3).sum(axis=1).tolist(),balance_N_minus_C=obj.ne-v['positive_C'],cell_conditional_residual=(counts-v['conditional_cell_allocation']).tolist(),zone_conditional_residual=(counts-v['conditional_cell_allocation']).reshape(3,3).sum(axis=1).tolist())
        write(path,r);return r
def run(args):
    verify_protocol(args.protocol);cat,pointer=load(args.pointer);out=Path(args.output);out.mkdir(parents=True,exist_ok=True);deadline=parse_deadline(args.deadline_utc)
    provenance=dict(schema='jma_forecast_run_v1',protocol_path=str(PROTOCOL.resolve()),protocol_sha256=E.sha(PROTOCOL),input_pointer=str(Path(args.pointer).resolve()),input_pointer_sha256=E.sha(args.pointer),array_sha256=pointer['arrays']['sha256'],build_receipt_sha256=E.sha(E.HERE/'build_receipt.json'),code_sha256={p.name:E.sha(p) for p in E.HERE.glob('*.py')},prescribed_procedures=36,prescribed_starts=288,prescribed_floors=42,prescribed_slots=330)
    if (out/'run.json').exists():
        if read(out/'run.json')!=provenance:raise ValueError('immutable run/code/input identity changed; use new output')
    else:write(out/'run.json',provenance)
    plan=[]
    for fold in range(3):
        for proc,arm in [(f'FC_s{i}','FC') for i in range(6)]+[(a,a) for a in ('FL','MC','OC','OL','N0','EP')]:
            nf=2 if arm in ('MC','EP') else 1
            registered_id=registered_procedure_id(f'f{fold}_{proc}');literals=['POISSON']+(['NESTED_FC_TAU1'] if arm=='MC' else ['FITTED_N0'] if arm=='EP' else [])
            slots=[dict(slot_id=f'f{fold}_{proc}.floor{i}',registered_slot_id=registered_id+':F_'+literal,kind='floor') for i,literal in enumerate(literals)]+[dict(slot_id=f'f{fold}_{proc}.start{i}',registered_slot_id=registered_id+f':S{i:02d}',kind='start') for i in range(8)]
            plan.append(dict(procedure_id=f'f{fold}_{proc}',registered_procedure_id=registered_id,arm=arm,fold=fold,slots=slots))
    if sum(len(p['slots']) for p in plan)!=330:raise AssertionError('complete denominator')
    if len({s['registered_slot_id'] for p in plan for s in p['slots']})!=330:raise AssertionError('canonical slot bijection')
    write(out/'schedule_plan.json',dict(schema='jma_330_slot_plan_v1',procedures=plan,prescribed_procedures=36,prescribed_starts=288,prescribed_floors=42,prescribed_slots=330))
    for fold in range(3):
        if time.time()>=deadline:return status(out,'checkpoint_deadline')
        npth=out/'nuisance'/f'f{fold}.json'
        if npth.exists():nuis=read(npth)
        else:nuis=E.nuisance(cat,fold);write(npth,nuis)
        prereq={};selected={};selectors=[];duration=E.ORIGINS[fold]-1826.
        schedule=[(f'FC_s{i}', 'FC',sigma,'continuous') for i,sigma in enumerate(E.SCALES)]+[(arm,arm,None,'lift' if arm in ('FL','OL') else 'competitive' if arm in ('N0','EP') else 'continuous') for arm in ('FL','MC','OC','OL','N0','EP')]
        for ordinal,(proc,arm,sigma,family) in enumerate(schedule):
            verify_protocol()
            if time.time()>=deadline:return status(out,'checkpoint_deadline')
            if sigma is None:
                if 'FC' not in selected:return status(out,'held_missing_complete_FC_selector')
                sigma=selected['FC']['sigma']
            cache=ensure_cache(out/'caches'/f'f{fold}_{proc}_train.npz',cat,nuis,1826.,E.ORIGINS[fold],sigma,family)
            if arm=='MC' and 'FC' not in prereq or arm=='OL' and 'FL' not in prereq or arm=='EP' and 'N0' not in prereq:return status(out,'held_incomplete_prerequisite')
            with E.Objective(cache) as obj:r=fit(out/'fits'/f'f{fold}_{proc}.json',obj,arm,f'f{fold}_{proc}',starts(arm,nuis['N'],duration,prereq),floors(arm,nuis['N'],duration,prereq),deadline)
            status(out,'running')
            if r['status']=='checkpoint_deadline':return status(out,'checkpoint_deadline')
            if arm=='FC':
                selectors.append(dict(ordinal=ordinal,sigma=sigma,procedure_id=r['procedure_id'],status=r['status'],selected=r['selected']))
                if len(selectors)==6:
                    if any(s['status']!='complete' for s in selectors):return status(out,'held_incomplete_sigma_selector')
                    winner=min(selectors,key=lambda s:(s['selected']['evaluator_nll'],s['ordinal'],s['selected']['candidate_id']));selected['FC']=winner;prereq['FC']=winner['selected']['x'];write(out/'nuisance'/f'f{fold}_sigma.json',dict(schema='jma_sigma_selector_v1',candidates=selectors,winner=winner,grid_edge=winner['ordinal'] in (0,5),selection='training_joint_nll_only'))
            else:
                if r['status']=='complete':selected[arm]=dict(sigma=sigma,procedure_id=r['procedure_id'],selected=r['selected']);prereq[arm]=r['selected']['x']
        write(out/'selected'/f'f{fold}.json',selected)
        if len(selected)!=7:return status(out,'held_incomplete_arm')
        for arm in ARMS:
            s=selected[arm];family='competitive' if arm in ('N0','EP') else 'lift' if arm in ('FL','OL') else 'continuous';sigma=s['sigma'];pars=s['selected']['x']
            windows=[(E.ORIGINS[fold],E.ENDS[fold],'full')]+[(float(a),float(b),label) for a,b,label in annual_intervals(fold)]
            for a,b,label in windows:
                if time.time()>=deadline:return status(out,'checkpoint_deadline')
                cache=ensure_cache(out/'caches'/f'f{fold}_{arm}_{label}.npz',cat,nuis,a,b,sigma,family)
                score(out/'scores'/f'f{fold}_{arm}_{label}.json',cache,arm,pars)
        # Every floor and every finite feasible solver return is forecasted,
        # including rejected returns. Selection was already frozen on training.
        stability=[]
        for proc,arm,sigma,family in schedule:
            r=read(out/'fits'/f'f{fold}_{proc}.json');sigma=E.SCALES[int(proc[-1])] if proc.startswith('FC_s') else selected['FC']['sigma'];cache=ensure_cache(out/'caches'/f'f{fold}_{proc}_nearopt_test.npz',cat,nuis,E.ORIGINS[fold],E.ENDS[fold],sigma,family);near=[]
            with E.Objective(cache) as forecast_obj:
                for slot in r['slots']:
                    for candidate in slot['attempts']:
                        if 'x' not in candidate or not np.isfinite(candidate['x']).all() or not all(lo<=v<=hi for v,(lo,hi) in zip(candidate['x'],E.bounds(arm))):continue
                        if time.time()>=deadline:return status(out,'checkpoint_deadline')
                        cid=candidate['candidate_id'];scorepath=out/'candidate_forecasts'/f'{cid}.json'
                        try:ss=score(scorepath,cache,arm,candidate['x'],obj=forecast_obj)
                        except Exception as exc:
                            write(scorepath,dict(schema='jma_forecast_score_v1',status='failed',candidate_id=cid,arm=arm,x=candidate['x'],error=repr(exc)));continue
                        if ss.get('status')=='complete' and cid in r.get('near_optimal_ids',[]):near.append(dict(candidate_id=cid,joint_logscore=ss['evaluation']['joint_logscore']))
            spread=(max(v['joint_logscore'] for v in near)-min(v['joint_logscore'] for v in near))/sum(cat['fold_test_mask'][fold]) if near else None
            stability.append(dict(procedure_id=r['procedure_id'],near_optimal=near,test_spread_per_target=spread,complete=len(near)==len(r.get('near_optimal_ids',[])),stable=len(near)==len(r.get('near_optimal_ids',[])) and spread is not None and spread<.01))
        write(out/'stability'/f'f{fold}_summary.json',stability)
    export_contrasts(out)
    failed_forecasts=[p for p in (out/'candidate_forecasts').glob('*.json') if read(p).get('status')!='complete']
    sensitivity=[row for fold in range(3) for row in read(out/'stability'/f'f{fold}_summary.json') if not row.get('stable')]
    return status(out,'unknown_failed_forecasts' if failed_forecasts else 'unknown_sensitivity' if sensitivity else 'complete')
def export_contrasts(out):
    rows=[]
    for fold in range(3):
        for label in ('full',)+tuple(y[2] for y in annual_intervals(fold)):
            scores={arm:read(out/'scores'/f'f{fold}_{arm}_{label}.json')['evaluation'] for arm in ARMS}
            for name,a,b,component in COMPARISONS:
                v={k:scores[a][k]-scores[b][k] for k in ('joint_logscore','timing_logscore','conditional_location_logscore','mark_logscore','P','G','positive_C','signed_negative_C','immigrant_exposure','offspring_exposure')};rows.append(dict(fold=fold,block=label,comparison=name,registered_comparison_id=REGISTERED_COMPARISONS[name],component=component,difference=v[component],n_events=scores[a]['n_events'],decomposition=v))
    pooled=[]
    for name,a,b,component in COMPARISONS:
        rr=[r for r in rows if r['comparison']==name and r['block']=='full'];N=sum(r['n_events'] for r in rr);v={k:sum(r['decomposition'][k] for r in rr) for k in rr[0]['decomposition']};pooled.append(dict(comparison=name,registered_comparison_id=REGISTERED_COMPARISONS[name],component=component,difference=v[component],n_events=N,per_target=v[component]/N if N else None,decomposition=v))
    write(out/'contrasts.json',dict(schema='jma_contrasts_v1',window_and_annual=rows,pooled=pooled))
def status(out,state):
    fits=list((out/'fits').glob('*.json')) if (out/'fits').exists() else [];rr=[read(p) for p in fits];slots=[s for r in rr for s in r['slots']];v=dict(status=state,procedures_materialized=len(rr),procedures_complete=sum(r['status']=='complete' for r in rr),slots_materialized=len(slots),slots_complete=sum(s['status']=='complete' for s in slots),slots_failed=sum(s['status']=='failed' for s in slots),prescribed_procedures=36,prescribed_slots=330,unmaterialized_slots=330-len(slots));write(out/'status.json',v)
    if (out/'schedule_plan.json').exists():
        saved={s['slot_id']:s['status'] for s in slots};plan=read(out/'schedule_plan.json');statuses={s['slot_id']:saved.get(s['slot_id'],'unknown_unexecuted') for p in plan['procedures'] for s in p['slots']};registered={s['registered_slot_id']:statuses[s['slot_id']] for p in plan['procedures'] for s in p['slots']};write(out/'slot_statuses.json',dict(schema='jma_complete_slot_status_v1',status=state,slots=statuses,registered_slots=registered))
    print(json.dumps(v),flush=True);return v
def parse_deadline(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp() if s else math.inf
def pilot(args):
    verify_protocol(args.protocol);cat,_=load(args.pointer);out=Path(args.output);out.mkdir(parents=True,exist_ok=True);fold=args.fold;began=time.perf_counter();nuis=E.nuisance(cat,fold);nuisance_seconds=time.perf_counter()-began;write(out/'nuisance.json',nuis);rows=[]
    for arm,family,params in [('FC','continuous',[-1.,0.,.3]),('MC','continuous',[-1.,0.,.3,math.log(.1)]),('MC','continuous',[-1.,0.,.3,math.log(1.)]),('OC','continuous',[-1.,0.,.3,math.log(.01),1.3]),('EP','competitive',[-1.,0.,.3,math.log(.01),1.3,math.log(5),1.5]),('EP','competitive',[-1.,0.,.3,math.log(.1),1.4,math.log(50),2.])]:
        began=time.perf_counter();cache=ensure_cache(out/f'{arm}_train.npz',cat,nuis,1826.,E.ORIGINS[fold],50.,family);cache_seconds=time.perf_counter()-began
        rows.append(dict(arm=arm,cache_build_seconds=cache_seconds,cache_bytes=cache.stat().st_size,cache_path=str(cache.resolve())))
        with E.Objective(cache) as obj:
            for i in range(2):
                began=time.perf_counter();v=obj.evaluate(arm,params);rows.append(dict(arm=arm,parameters=params,repetition=i,wall_seconds=time.perf_counter()-began,n_events=obj.ne,n_parents=obj.np,joint_nll=v['joint_nll'],cache_path=str(cache.resolve()),evaluation=compact(v)))
            if args.solver_steps and arm in ('MC','EP'):
                began=time.perf_counter();opt=minimize(lambda x:(lambda v:(v['joint_nll'],v['gradient']))(obj.evaluate(arm,x)),np.array(params),method='L-BFGS-B',jac=True,bounds=E.bounds(arm),options=dict(maxiter=args.solver_steps,maxfun=100,maxls=200,ftol=1e-10,gtol=2e-6));rows.append(dict(arm=arm,engineering_solver=True,maxiter=args.solver_steps,wall_seconds=time.perf_counter()-began,nfev=int(opt.nfev),nit=int(opt.nit),success=bool(opt.success),message=str(opt.message)))
        write(out/'pilot.json',dict(schema='jma_engineering_pilot_v1',fold=fold,training_only=True,registered_fit_slots_consumed=0,nuisance_seconds=nuisance_seconds,rows=rows))
    if args.pilot_fc_fit:
        cache=out/'FC_train.npz'
        with E.Objective(cache) as obj:
            began=time.perf_counter();fit(out/'pilot_FC_fit.json',obj,'FC','engineering_FC_50km',starts('FC',nuis['N'],E.ORIGINS[fold]-1826.,{}),floors('FC',nuis['N'],E.ORIGINS[fold]-1826.,{}),parse_deadline(args.deadline_utc));rows.append(dict(arm='FC',engineering_complete_eight_start_fit=True,wall_seconds=time.perf_counter()-began))
        write(out/'pilot.json',dict(schema='jma_engineering_pilot_v1',fold=fold,training_only=True,registered_fit_slots_consumed=0,nuisance_seconds=nuisance_seconds,rows=rows))
    print(json.dumps(dict(status='pilot_complete',measurements=len(rows),output=str(out.resolve()))))
def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('run','pilot'));p.add_argument('--pointer','--input-pointer',dest='pointer',required=True);p.add_argument('--output','--output-private',dest='output',required=True);p.add_argument('--protocol',required=True);p.add_argument('--deadline-utc');p.add_argument('--fold',type=int,default=0);p.add_argument('--solver-steps',type=int,default=0);p.add_argument('--pilot-fc-fit',action='store_true');args=p.parse_args();(run if args.mode=='run' else pilot)(args)
if __name__=='__main__':main()
