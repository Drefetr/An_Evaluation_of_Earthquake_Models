"""Stage2 local-only drivers. No work on import; all numerical entrypoints leased."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import argparse,hashlib,json,math,time,sys,random,subprocess
from dataclasses import asdict,replace
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
from scipy.optimize import minimize,brentq
from stage2_history import CachedHistory

HERE=Path(__file__).resolve().parent;HOME=HERE.parent
CELLS={'I00':([], [3]),'I10':([0],[0,3]),'I01':([1],[1,3]),'I11':([0,1],[0,1,3])}
BOUNDS={0:(-12.,0.),1:(-2.,2.),3:(0.,3.)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(path,d):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');os.replace(tmp,path)
def authorities(root):
 sys.path.insert(0,str(Path(root)/'research_f_continuation/engine'));from api import load
 old=load('restricted');s=json.loads((Path(root)/'research_f_continuation/paper/supplements/methods_settings.json').read_text())['synthetic_generating_law']
 law=old.law_from_setting(dict(beta=s['beta'],horizon=s['horizon_days'],coordinate_horizon=s['coordinate_horizon_days'],generating_fit=s['alternative_generating_fit']))
 return old,law
def history(root,binding):
 f=Path(root)/binding['files']['catalogue.npz']['path']
 if sha(f)!=binding['files']['catalogue.npz']['sha256']:raise ValueError('history pin changed')
 with np.load(f,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}
def make(arrays,law,old,clock,order,deadline):return CachedHistory(HERE/'temporal_stage2.dll',arrays,law,old.cpu,clock_mode=clock,order=order,deadline=deadline,cache_bytes=512*2**20)

def solve_method(h,higher,law,cell,deadline,starts=8):
 nf,af=CELLS[cell];base=np.array([law.a,law.d,law.n,0.]);records=[]
 def solve(start,free,phase,index):
  start=start.copy();bounds=[BOUNDS[i] for i in free]
  def full(x):p=start.copy();p[free]=x;return p
  def fun(x):
   answer=h.objective(full(x),law.trigger,law.ratio,True,free)
   if answer[0]<best[0]:best[:]=[float(answer[0]),np.asarray(x).copy()]
   return answer
  def val(x):
   value=h.objective(full(x),gradient=False)
   if value<best[0]:best[:]=[float(value),np.asarray(x).copy()]
   return value
  value=float(h.objective(start,gradient=False))
  if not free:return dict(pars=start.tolist(),nll=value,origin='fixed_null')
  x=start[free].copy();best=[value,x.copy()];terminal=None;success=False
  for tier,options in [('LBFGSB40',dict(maxiter=2000,maxls=40,ftol=1e-12,gtol=1e-7)),('LBFGSB200',dict(maxiter=2000,maxls=200,ftol=1e-12,gtol=1e-7)),('Powell',dict(maxiter=2000,maxfev=20000,ftol=1e-10,xtol=1e-7))]:
   if time.perf_counter()>=deadline:raise TimeoutError('case deadline')
   began=time.perf_counter()
   try:r=minimize(val if tier=='Powell' else fun,x,jac=False if tier=='Powell' else True,method='Powell' if tier=='Powell' else 'L-BFGS-B',bounds=bounds,options=options)
   except Exception as exc:
    saved_deadline=h.deadline;h.deadline=None
    try:terminal=full(best[1]);gradient=h.objective(terminal,gradient=True,free=free)[1];gn=float(np.max(abs(gradient)))
    finally:h.deadline=saved_deadline
    row=dict(phase=phase,start_index=index,tier=tier,success=False,message=type(exc).__name__+':'+str(exc),terminal_best_nll=float(best[0]),terminal_pars=terminal.tolist(),terminal_gradient_norm=gn)
    if getattr(h,'trace',None):
     with Path(h.trace).open('a') as f:f.write(json.dumps(row)+'\n')
    raise
   feasible=np.isfinite(r.x).all() and all(lo<=v<=hi for v,(lo,hi) in zip(r.x,bounds))
   fresh=float(h.objective(full(r.x),gradient=False)) if feasible else math.inf
   if math.isfinite(fresh) and fresh<best[0]:best[:]=[fresh,r.x.copy()]
   terminal=full(best[1]);grad=h.objective(terminal,gradient=True,free=free)[1]
   success=bool(r.success and feasible and math.isfinite(fresh) and fresh<=value+1e-8 and abs(fresh-float(r.fun))<=1e-4)
   records.append(dict(phase=phase,start_index=index,start=start.tolist(),free=free,tier=tier,success=success,solver_success=bool(r.success),message=str(r.message),evaluations=int(r.nfev),seconds=time.perf_counter()-began,terminal_best_nll=float(best[0]),terminal_gradient_norm=float(np.max(abs(grad))),terminal_pars=terminal.tolist()))
   if getattr(h,'trace',None):
    with Path(h.trace).open('a') as f:f.write(json.dumps(records[-1])+'\n')
   if success:return dict(pars=full(r.x).tolist(),nll=fresh,origin=tier)
   x=best[1].copy()
  return None
 nulls=[]
 offsets=[(0,0),(.2,.1),(-.2,-.1),(.5,.5),(-.5,-.5),(1,1),(-1,-1),(0,0)]
 for i,(da,dd) in enumerate(offsets if nf else [(0,0)]):
  p=base.copy()
  if 0 in nf:p[0]=np.clip(p[0]+da,-12,0)
  if 1 in nf:p[1]=np.clip(p[1]+dd,-2,2)
  r=solve(p,nf,'null',i)
  if r:nulls.append(r)
 if not nulls:return dict(cell=cell,status='unknown_null',attempts=records)
 null=min(nulls,key=lambda x:x['nll']);alts=[dict(null,origin='exact_null_floor')]
 for i,eta in enumerate((0.,.02,.05,.1,.2,.5,1.,2.)):
  p=np.array(null['pars']);p[3]=eta;r=solve(p,af,'alternative',i)
  if r:alts.append(r)
 alt=min(alts,key=lambda x:x['nll']);checks=[]
 for phase,r in [('null',null),('alternative',alt)]:
  r.update(trigger=asdict(law.trigger),ratio=law.ratio)
  v32=higher.objective(r['pars'],gradient=False);checks.append(dict(phase=phase,order16=r['nll'],order32=v32,absolute_difference=abs(v32-r['nll']),passed=abs(v32-r['nll'])<=1e-4))
 c16=h.contrast(null,alt);c32=higher.contrast(null,alt)
 enough=len(nulls)==(8 if nf else 1) and len(alts)==9
 passed=enough and all(c['passed'] for c in checks) and abs(c16['statistic']-c32['statistic'])<=1e-4 and all(abs(c['direct_minus_subtraction'])<=1e-4 and c['statistic']>=-1e-4 for c in (c16,c32))
 candidates=[x for x in alts if x['nll']<=alt['nll']+4e-4]
 return dict(cell=cell,status='complete' if passed else 'unknown_controls_or_solver',null=null,alternative=alt,attempts=records,controls=checks,direct_contrast16=c16,direct_contrast32=c32,near_optimal_candidates=candidates,prescribed_null_starts=8 if nf else 1,prescribed_alt_starts=8)

def fit_case(task):
 root,case,cells,out=task;data=json.loads((HOME/'INPUT_CASES.json').read_text());binding=data['bindings'][case];old,law=authorities(root);arrays=history(root,binding);began=time.perf_counter();deadline=began+7200
 if Path(out).exists():
  prior=json.loads(Path(out).read_text());return dict(id=case,status=prior.get('status','unknown'),seconds=prior.get('seconds'),reused_stage2_pilot=True,methods=len(prior.get('methods',[])))
 result=dict(id=case,phase='new_unresolved_only',methods=[],input_sha256=binding['files']['catalogue.npz']['sha256'],n_events=len(arrays['times']))
 h=h32=None
 try:
  h=make(arrays,law,old,binding['clock_mode'],16,deadline);h32=make(arrays,law,old,binding['clock_mode'],32,deadline)
  Path(out).parent.mkdir(parents=True,exist_ok=True);h.trace=str(Path(out).with_suffix('.attempts.jsonl'))
  result['cache_active']=[h.cache_active,h32.cache_active]
  for cell in cells:result['methods'].append(solve_method(h,h32,law,cell,deadline));save(out,result)
  result['status']='complete' if all(x['status']=='complete' for x in result['methods']) else 'partial'
 except Exception as e:result.update(status='unknown_exception',error=type(e).__name__+':'+str(e))
 finally:
  if h:h.close()
  if h32:h32.close()
 result['seconds']=time.perf_counter()-began;save(out,result)
 return dict(id=case,status=result['status'],seconds=result['seconds'],methods=len(result['methods']))

def equivalence(task):
 root,entry=task;old,law=authorities(root);arrays=history(root,entry['binding'])
 if sha(entry['record'])!=entry['record_sha256']:raise ValueError('saved control changed')
 record=json.loads(Path(entry['record']).read_text());deadline=time.perf_counter()+570;absolute=relative=feature_rel=0.;stats=[]
 for order in (16,32):
  before=old.RestrictedHistory(arrays,law,clock_mode=entry['binding']['clock_mode'],order=order,deadline=deadline,host_limit_bytes=1024*2**20);after=make(arrays,law,old,entry['binding']['clock_mode'],order,deadline)
  try:
   if not after.cache_active:raise MemoryError('control cache unavailable')
   for name in ('ge','gq','xe','xq','wq'):
    x=getattr(before,name);y=getattr(after,name);feature_rel=max(feature_rel,float(np.max(abs(x-y)/np.maximum(1.,abs(x)))) if len(x) else 0.)
   for method in record['methods']:
    if method['status']!='complete':continue
    for phase in ('null','alternative'):
     p=method[phase]['pars'];v,g=before.objective(p,law.trigger,law.ratio,True);u,j=after.objective(p)
     absolute=max(absolute,abs(v-u),float(np.max(abs(g-j))));relative=max(relative,abs(v-u)/max(1.,abs(v)),float(np.max(abs(g-j)/np.maximum(1.,abs(g)))))
    contrast=after.contrast(method['null'],method['alternative']);absolute=max(absolute,abs(contrast['statistic']-method['direct_contrast'+str(order)]['statistic']))
    if order==16:stats.append((method['cell'],contrast['statistic'],method['direct_contrast16']['statistic']))
  finally:before.close();after.close()
 inputs=json.loads((HOME/'INPUT_CASES.json').read_text());bank=json.loads(Path(inputs['bank_path']).read_text());references=[r['statistics'] for r in bank['rows'] if r['role']=='reference'];same=True
 def decision(value,index):
  known=[r[index] for r in references if r[index] is not None];lo=(1+sum(r>=value for r in known))/1000;hi=lo+(999-len(known))/1000
  return True if hi<=.05 else False if lo>.05 else None
 for cell,new,prior in stats:same=same and decision(new,list(CELLS).index(cell))==decision(prior,list(CELLS).index(cell))
 return dict(id=entry['id'],max_absolute_error=absolute,max_scaled_relative_error=relative,max_feature_scaled_relative_error=feature_rel,decisions_match=same,statistics=stats,status='passed' if absolute<=1e-4 and feature_rel<=1e-12 and same else 'failed')

def mesh(task):
 root,binding,out=task;old,law=authorities(root);arrays=history(root,binding);deadline=time.perf_counter()+7200;rows=[];h=h32=None
 try:
  h=make(arrays,law,old,binding['clock_mode'],16,deadline);h32=make(arrays,law,old,binding['clock_mode'],32,deadline)
  for d in np.unique(np.r_[np.linspace(-2,2,9),law.d]):
   for eta in np.unique(np.r_[np.linspace(0,3,13),.4885010300470942]):
    p=np.array([law.a,d,law.n,eta]);deriv=lambda a:h.objective([a,d,law.n,eta],gradient=True,free=[0])[1][0]
    if deriv(-12)>=0:a=-12.
    elif deriv(0)<=0:a=0.
    else:a=brentq(deriv,-12,0,xtol=1e-12)
    p[0]=a;v=h.objective(p,gradient=False);u=h32.objective(p,gradient=False)
    rows.append(dict(d=float(d),eta=float(eta),profile=dict(a=float(a),value=v),fresh_ground_objective=v,order32=u,absolute_difference=abs(v-u),agreement_pass=abs(v-u)<=1e-4))
  expected=len(np.unique(np.r_[np.linspace(-2,2,9),law.d]))*len(np.unique(np.r_[np.linspace(0,3,13),.4885010300470942]))
  result=dict(id=binding['id'],status='completed_mesh' if len(rows)==expected and all(x['agreement_pass'] for x in rows) else 'unknown_order_control',profile_rows=rows,planned_profile_rows=expected,n_events=len(arrays['times']))
 except Exception as e:result=dict(id=binding['id'],status='unknown_exception',error=str(e),profile_rows=rows)
 finally:
  if h:h.close()
  if h32:h32.close()
 save(out,result);return dict(id=binding['id'],status=result['status'],rows=len(rows))

def pool_run(function,tasks,workers):
 results=[]
 with ProcessPoolExecutor(max_workers=workers) as pool:
  jobs=[pool.submit(function,t) for t in tasks]
  for future in as_completed(jobs):
   value=future.result();results.append(value);print(json.dumps({k:v for k,v in value.items() if k!='statistics'}),flush=True)
 return results

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['controls','fits','meshes']);p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int);a=p.parse_args();data=json.loads((HOME/'INPUT_CASES.json').read_text())
 if a.stage=='controls':
  selection=json.loads((HOME/'CONTROL_SELECTION.json').read_text());results=pool_run(equivalence,[(str(a.root),x) for x in selection],a.workers);save(HOME/'CONTROLS_RESULT.json',dict(status='passed' if all(x['status']=='passed' for x in results) else 'failed',planned=20,completed=len(results),cases=results))
 elif a.stage=='fits':
  todo=[(str(a.root),x['id'],x['cells'],str(HOME/'fits'/f"{x['id']}.json")) for role in ('reference','null_query','alternative_query') for x in data['missing'][role]]
  todo.sort(key=lambda t:(data['bindings'][t[1]]['files']['catalogue.npz']['bytes'],t[1]))
  if a.limit:todo=todo[:a.limit]
  results=pool_run(fit_case,todo,a.workers);save(HOME/('FIT_PILOT_RESULT.json' if a.limit else 'FIT_CAMPAIGN_RESULT.json'),dict(completed=len(results),planned=len(todo),cases=results))
 else:
  geo=json.loads((HOME/'GEOMETRY_BINDINGS.json').read_text());tasks=[(str(a.root),b,str(HOME/'meshes'/f"{b['id']}.json")) for b in geo];results=pool_run(mesh,tasks,a.workers);save(HOME/'MESH_CAMPAIGN_RESULT.json',dict(planned=5,completed=len(results),cases=results))
if __name__=='__main__':main()
