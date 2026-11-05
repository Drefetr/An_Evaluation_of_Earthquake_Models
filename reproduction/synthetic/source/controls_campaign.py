"""Fixed-backbone LI+ observed/control execution; private arrays stay local."""
import argparse,ctypes as C,json,time,os
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
import spatial as S
from geometry_plan import _adaptive_area_space
import generator as G
LIVE_NATIVE_BYTES=0
def time_plan(t,start,end,c,order):
 z,w=np.polynomial.legendre.leggauss(order);edges=np.unique(np.r_[start,t[(t>start)&(t<end)],end]);nodes=[];weights=[]
 for lo,hi in zip(edges[:-1],edges[1:]):
  # log panels resolve the Omori singularity immediately after every event.
  L=np.log1p((hi-lo)/c);u=L*(z+1)/2;nodes.extend(lo+c*np.expm1(u));weights.extend(c*np.exp(u)*L/2*w)
 return np.ascontiguousarray(nodes),np.ascontiguousarray(weights)
def background(query,a,m):
 r=a['rectangles'];x=query[:,0];y=query[:,1];cells=np.zeros(len(query),int)
 for k,(xl,xh,yl,yh) in enumerate(r):cells[(x>=xl)&(x<=xh)&(y>=yl)&(y<=yh)]=k
 b=m['bg_floor']*a['reference_pi'][cells]/a['cell_areas'][cells]
 for k in range(0,len(a['kde_training_xy']),256):
  xy=a['kde_training_xy'][k:k+256];Z=a['kde_normalizers'][k:k+256]
  if len(xy):b+=(1-m['bg_floor'])*S.density(query,xy,m['kde_h'],2,Z)@a['kde_weight'][k:k+256]
 return b,cells
class Integrated:
 def __init__(self,a,m,pars,dll,order):
  global LIVE_NATIVE_BYTES
  self.handle=None
  self.lib=C.CDLL(str(Path(dll).resolve()));ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
  self.lib.m02_create.argtypes=[C.c_int]*4+[ptr]*6;self.lib.m02_create.restype=C.c_void_p
  self.lib.m02_integrated.argtypes=[C.c_void_p,C.c_int,C.c_int,ptr,ptr];self.lib.m02_integrated.restype=C.c_int
  self.lib.m02_free.argtypes=[C.c_void_p];self.lib.m02_integrated_error.restype=C.c_char_p
  plan_a=dict(rectangles=a['rectangles'],reference_pi=a['reference_pi'],kde_xy=a['kde_training_xy'],kde_weight=a['kde_weight'],kde_normalizer=a['kde_normalizers'],parent_xy=a['parent_xy'])
  pm=dict(bg_floor=m['bg_floor'],kde_h=m['kde_h']);plans,info=_adaptive_area_space(plan_a,pm,[order],1e-8,20)
  plan=plans[order];xy=plan['space_xy'];b,cells=background(xy,a,m);areaweight=plan['space_weight']/b
  space=np.ascontiguousarray(np.column_stack([xy,areaweight,b,a['reference_pi'][cells]/a['cell_areas'][cells]]))
  times,weights=time_plan(a['parent_time'],m['start'],m['end'],np.exp(pars[3]),2*order)
  f=S.features(a,m,pars[3:5]);baseline=S.evaluate(f,pars[:3])[0]
  parents=np.ascontiguousarray(np.column_stack([a['parent_time'],a['parent_xy'],a['parent_excess'],a['parent_fertility'],a['parent_normalizer']]))
  events=np.ascontiguousarray(np.column_stack([a['event_time'],a['event_xy'],a['event_background_density'],pars[2]*f['hp'],a['reference_pi'][a['event_cell'].astype(int)]/a['cell_areas'][a['event_cell'].astype(int)]]))
  meta=np.array([*pars[:3],np.exp(pars[3]),pars[4],m['T0'],baseline['compensator'],f['marks'],m['sigma']])
  self.meta=dict(space_nodes=len(space),time_nodes=len(times),estimated_native_bytes=int(16*len(space)*len(times)+16*len(space)*len(parents)+8*len(times)*len(parents)),space_plan=info)
  if LIVE_NATIVE_BYTES+self.meta['estimated_native_bytes']>12_000_000_000:raise MemoryError('INTEGRATION_MEMORY_ADMISSION')
  self.handle=self.lib.m02_create(len(parents),len(events),len(space),len(times),parents,events,space,times,weights,meta)
  if not self.handle:raise ArithmeticError('INTEGRATION_CREATE')
  LIVE_NATIVE_BYTES+=self.meta['estimated_native_bytes']
 def evaluate(self,p,plus,inclusive):
  p=np.ascontiguousarray(p,float);out=np.empty(6)
  if self.lib.m02_integrated(self.handle,int(plus),int(inclusive),p,out):raise ArithmeticError(self.lib.m02_integrated_error().decode())
  return out
 def close(self):
  global LIVE_NATIVE_BYTES
  if self.handle:self.lib.m02_free(self.handle);self.handle=None;LIVE_NATIVE_BYTES-=self.meta['estimated_native_bytes']
def fit(obj,plus,inclusive,checkpoint=None):
 bounds=[(0,4),(np.log(5),np.log(150)),(np.log(1/24),np.log(365))];records=[];floor=np.array([0,np.log(30),np.log(7)]);floor_nll=float(obj.evaluate(floor,plus,inclusive)[0])
 starts=[(0,30,7),(.1,5,1/24),(.3,15,.25),(.7,50,7),(1.5,150,30),(3,5,365),(4,150,1/24),(.5,30,365)]
 for i,(eta,ell,psi) in enumerate(starts):
  def fun(x):
   v=obj.evaluate(x,plus,inclusive);return float(v[0]),v[1:4].copy()
  initial=np.array([eta,np.log(ell),np.log(psi)]);current=initial.copy()
  for method in ['L-BFGS-B','Powell']:
   record=dict(start=i,method=method,initial_pars=current.tolist(),success=False,finite_feasible=False)
   try:
    o=minimize(fun if method=='L-BFGS-B' else lambda x:fun(x)[0],current,jac=True if method=='L-BFGS-B' else False,bounds=bounds,method=method,options=dict(maxls=200,maxiter=200,ftol=1e-10,gtol=2e-6) if method=='L-BFGS-B' else dict(maxiter=400,maxfev=5000,ftol=1e-10,xtol=1e-6))
    finite=bool(np.isfinite(o.x).all() and np.isfinite(o.fun) and all(lo<=v<=hi for v,(lo,hi) in zip(o.x,bounds)))
    record.update(success=bool(o.success and finite),finite_feasible=finite,solver_success=bool(o.success),solver_status=int(o.status),message=str(o.message),nfev=int(o.nfev),nit=int(o.nit),pars=o.x.tolist() if np.isfinite(o.x).all() else None,nll=float(o.fun) if np.isfinite(o.fun) else None)
    if finite:current=o.x.copy()
   except Exception as exc:record.update(error_type=type(exc).__name__,error_code=str(exc))
   records.append(record)
   if checkpoint:checkpoint(record)
   if record['success']:break
 valid=[r for r in records if r['success'] and r['finite_feasible']];valid.append(dict(start=-1,method='floor',success=True,finite_feasible=True,pars=floor.tolist(),nll=floor_nll));winner=min(valid,key=lambda r:(r['nll'],r['start']>=0,r['start']))
 return dict(status='complete' if len({r['start'] for r in valid if r['start']>=0})==8 else 'unknown_starts',selected=winner,candidates=valid,records=records,floor_nll=floor_nll,floor=floor.tolist())
def canonical_arrays(t,xy,q,rect,pi,kxy,kw,meta,pars,geometry):
 area=(rect[:,1]-rect[:,0])*(rect[:,3]-rect[:,2]);keep=t<meta['end'];t=t[keep];xy=xy[keep];q=q[keep];target=t>=meta['start'];cells=np.zeros(len(t),int)
 for k,(xl,xh,yl,yh) in enumerate(rect):cells[(xy[:,0]>=xl)&(xy[:,0]<=xh)&(xy[:,1]>=yl)&(xy[:,1]<=yh)]=k
 F=geometry.masses(xy,rect,meta['sigma'],2);bref=pi/area;Z=F@bref;ec=cells[target];a=dict(parent_time=t,parent_xy=xy,parent_excess=q,parent_fertility=.3*np.exp(meta['beta']*.7*q),parent_normalizer=Z,parent_exposure_lo=np.maximum(meta['start']-t,0),parent_exposure_hi=meta['end']-t,event_time=t[target],event_xy=xy[target],event_x=2*t[target]/meta['T0']-1,event_cell=ec,event_excess=q[target],reference_pi=pi,cell_areas=area,rectangles=rect,kde_training_xy=kxy,kde_weight=kw)
 a['event_parent_density']=S.density(xy[target],xy,meta['sigma'],2,Z)*bref[ec,None]
 a['kde_normalizers']=geometry.masses(kxy,rect,meta['kde_h'],2).sum(axis=1) if len(kxy) else np.empty(0)
 a['event_background_density']=background(xy[target],a,meta)[0]
 return a
def generate(seed,regime,out):
 names={i+4:n for i,n in enumerate(G.MATCHED_NAMES)};_,bg,eta,ell,psi=G.ROSTER[names[regime]]
 law=G.Law(names[regime],seed,bg,eta,ell,psi);limits=G.Limits(wall_seconds=600);budget=G.Budget(limits);streams=G.ScalarStreams(seed,limits,budget);sim=G._Simulator(law,limits,budget,streams)
 try:sim.run()
 except BaseException as exc:
  rows=np.array([[e.time,e.x,e.y,e.Q] for e in sim.history],float).reshape(-1,4);np.savez_compressed(Path(out)/'generated_partial_private.npz',rows=rows)
  S.write(Path(out)/'generator_failure_private.json',dict(seed=seed,regime=regime,error_type=type(exc).__name__,snapshot=G.private_failure_snapshot(sim,failure_code=getattr(exc,'code',type(exc).__name__))))
  raise
 rows=np.array([[e.time,e.x,e.y,e.Q] for e in sim.history],float).reshape(-1,4);np.savez_compressed(Path(out)/'generated_private.npz',rows=rows)
 S.write(Path(out)/'generator_receipt.json',dict(seed=seed,regime=regime,law=law.case_id,counters=G.asdict(sim.counts),rng=streams.snapshot(),status='complete'))
 meta=G.fitting_metadata(law);return rows,meta,[law.a,law.d,law.n,np.log(law.c),law.p]
def run(output,dll,radial,case=None,seed=None,regime=None,pilot=False):
 began=time.perf_counter();out=Path(output);out.mkdir(parents=True,exist_ok=False);g=S.Geometry(radial);arrays=[];metas=[]
 if case:
  c=S.read(case);oc=c['models']['Omori_smooth_cont'];pars=oc['selected']['pars']
  for phase in ['train16','test16']:
   a,m=S.load(S.cache_paths(oc)[phase]);a['kde_weight']=np.full(len(a['kde_training_xy']),1/len(a['kde_training_xy']));m.update(bg_floor=.05,kde_h=m['kde_bandwidth']);arrays.append(a);metas.append(m)
 else:
  rows,gm,pars=generate(seed,regime,out);rect=np.array(gm['rectangles']);pi=np.array(gm['reference_pi']);kxy=np.array(gm['kde_xy']).reshape(-1,2);kw=np.array(gm['kde_weight'])
  for start,end in [(30,395),(395,760)]:
   m=dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h'] or 10)
   arrays.append(canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],rect,pi,kxy,kw,m,pars,g));metas.append(m)
 private=[];summary=[]
 # Compile plan+fixed H once per phase/order, shared by all three models.
 coarse=[Integrated(a,m,pars,dll,8) for a,m in zip(arrays,metas)]
 try:
  if pilot:
   fine=[Integrated(a,m,pars,dll,16) for a,m in zip(arrays,metas)];checks=[]
   try:
    for name,plus,inclusive in [('LI',False,False),('LIplus_immigrant',True,False),('LIplus_inclusive',True,True)]:
     for p in [[0,np.log(30),np.log(7)],[.5,np.log(5),np.log(1/24)],[2,np.log(50),np.log(30)]]:
      values=[]
      for co,fi in zip(coarse,fine):
       v=co.evaluate(p,plus,inclusive);vf=fi.evaluate(p,plus,inclusive);errors=[]
       for j in range(3):
        if p[j]==0:continue
        x=np.array(p);y=np.array(p);x[j]+=1e-5;y[j]-=1e-5
        fd=(co.evaluate(x,plus,inclusive)[0]-co.evaluate(y,plus,inclusive)[0])/2e-5;errors.append(abs(float(fd-v[1+j])))
       values.append(dict(nll_order_delta=abs(float(v[0]-vf[0])),gradient_maxabs=max(errors,default=0)))
      checks.append(dict(model=name,eta=p[0],checks=values))
    S.write(out/'pilot_aggregate.json',dict(schema='s04_integration_pilot_v1',checks=checks,coarse_plans=[o.meta for o in coarse],fine_plans=[o.meta for o in fine],wall_seconds=time.perf_counter()-began,seed=seed,regime=regime))
   finally:
    for o in fine:o.close()
   return
  for name,plus,inclusive in [('LI',False,False),('LIplus_immigrant',True,False),('LIplus_inclusive',True,True)]:
   with (out/(name+'_solver_returns_private.jsonl')).open('x',encoding='utf-8') as stream:
    def checkpoint(record):stream.write(json.dumps(record,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
    fitted=fit(coarse[0],plus,inclusive,checkpoint)
   S.write(out/(name+'_fit_private.json'),fitted)
   N=len(arrays[0]['event_time']);threshold=1.5*np.log(max(N,1));near=[r for r in fitted['candidates'] if r['nll']<=fitted['selected']['nll']+4e-4];forecasts=[dict(candidate=r,evaluation=coarse[1].evaluate(r['pars'],plus,inclusive).tolist()) for r in near]
   for gate in ['raw'] if name=='LI' else ['raw','BIC']:
    winner=fitted['selected'] if gate=='raw' or fitted['floor_nll']-fitted['selected']['nll']>threshold else dict(pars=fitted['floor'],nll=fitted['floor_nll'])
    test=coarse[1].evaluate(winner['pars'],plus,inclusive);floor=coarse[1].evaluate(fitted['floor'],plus,inclusive);gain=float(floor[0]-test[0])
    summary.append(dict(model=name,gate=gate,status=fitted['status'],gain=gain,win=bool(gain>0),n_train=N,n_test=len(arrays[1]['event_time']),off_floor=bool(winner['pars'][0]>0)))
    private.append(dict(model=name,gate=gate,fit=fitted,selected=winner,test=test.tolist(),near_forecasts=forecasts,threshold=threshold))
  fine=[Integrated(a,m,pars,dll,16) for a,m in zip(arrays,metas)];reconstruction=[];passed=True;spread_passed=True;evaluation_cache={}
  try:
   def replay(obj,phase,order,p,plus,inclusive):
    key=(phase,order,tuple(map(float,p)),plus,inclusive)
    if key not in evaluation_cache:evaluation_cache[key]=obj.evaluate(p,plus,inclusive)
    return evaluation_cache[key]
   for record,row in zip(private,summary):
    plus=record['model']!='LI';inclusive=record['model']=='LIplus_inclusive';states=[r for r in record['fit']['records'] if r.get('finite_feasible')]+[r for r in record['fit']['candidates'] if r['start']==-1];checks=[]
    for state in states:
     for phase,(co,fi) in enumerate(zip(coarse,fine)):
      v=replay(co,phase,8,state['pars'],plus,inclusive);vf=replay(fi,phase,16,state['pars'],plus,inclusive);delta=abs(float(v[0]-vf[0]));passed=passed and delta<=1e-4
      checks.append(dict(candidate=state['start'],method=state['method'],solver_success=state['success'],phase=phase,coarse=v.tolist(),fine=vf.tolist(),delta_nll=delta))
    test=replay(fine[1],1,16,record['selected']['pars'],plus,inclusive);floor=replay(fine[1],1,16,record['fit']['floor'],plus,inclusive);gain=float(floor[0]-test[0]);row.update(gain=gain,win=bool(gain>0));record['fine_test']=test.tolist()
    near=[r for r in record['fit']['candidates'] if r['nll']<=record['fit']['selected']['nll']+4e-4];forecasts=[float(replay(fine[1],1,16,r['pars'],plus,inclusive)[0]) for r in near]
    spread=(max(forecasts)-min(forecasts))/max(1,len(arrays[1]['event_time']));row['near_optimal_spread_per_event']=spread;spread_passed=spread_passed and spread<.01
    reconstruction.append(dict(model=record['model'],gate=record['gate'],checks=checks,near_optimal_spread_per_event=spread))
   S.write(out/'private.json',dict(parameters=pars,results=private,reconstruction=reconstruction,plans=[o.meta for o in coarse],fine_plans=[o.meta for o in fine],case=case,seed=seed,regime=regime,source_contract='fixed_backbone',quadrature_convergence=bool(passed)))
   S.write(out/'aggregate.json',dict(schema='s04_fixed_backbone_v1',status='pending_independent_audit' if passed and spread_passed and all(r['status']=='complete' for r in summary) else 'unknown_numerical_gate',quadrature_gate=bool(passed),forecast_spread_gate=bool(spread_passed),seed=seed,regime=regime,results=summary,wall_seconds=time.perf_counter()-began))
  finally:
   for o in fine:o.close()
 finally:
  for o in coarse:o.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--dll',required=True);p.add_argument('--radial',required=True);p.add_argument('--case');p.add_argument('--seed',type=int);p.add_argument('--regime',type=int);p.add_argument('--pilot',action='store_true');a=p.parse_args();run(a.output,a.dll,a.radial,a.case,a.seed,a.regime,a.pilot)
