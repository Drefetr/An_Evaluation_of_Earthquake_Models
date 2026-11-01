"""Frozen four-arm spatial evaluation. Private arrays never emitted to stdout."""
import argparse,ctypes as C,hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize,minimize_scalar
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def load(p):
 with np.load(p,allow_pickle=False) as f:return {k:f[k].copy() for k in f.files if k!='metadata_json'},json.loads(str(f['metadata_json'].item()))
def cache_paths(model):return {**model['cache_paths'],**model.get('forecast_cache_paths',{})}
class Geometry:
 def __init__(self,dll):
  self.lib=C.CDLL(str(Path(dll).resolve()));ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
  self.lib.cb_rectangle.argtypes=[ptr,C.c_double,C.c_double,C.c_double,C.c_double,ptr];self.lib.cb_rectangle.restype=C.c_int
 def masses(self,xy,rect,scale,q):
  out=np.empty((len(xy),len(rect)));v=np.empty(3)
  for j,(x,y) in enumerate(xy):
   for k,r in enumerate(rect):
    if self.lib.cb_rectangle(np.ascontiguousarray(r),x,y,scale,q,v):raise ArithmeticError('RADIAL_NORMALIZATION')
    out[j,k]=v[0]
  if np.any(out<=0) or not np.isfinite(out).all():raise ArithmeticError('RADIAL_MASS')
  return out
def density(query,parents,scale,q,Z):
 d2=((query[:,None,:]-parents[None,:,:])**2).sum(axis=2)
 return np.exp(-q*np.log1p(d2/scale**2))/Z[None,:]
def bandwidth(a,m,g):
 xy=a['kde_training_xy'];pi=a['reference_pi'];area=a['cell_areas'];cells=a['kde_training_cells'].astype(int);rows=[]
 # Floor reference is frozen training-only; kernel identity alone excluded.
 for h in [.5,1,2,3,5,10,15,25,50,150,500,1500]:
  F=g.masses(xy,a['rectangles'],h,2);K=density(xy,xy,h,2,F.sum(axis=1));np.fill_diagonal(K,0)
  b=.05*pi[cells]/area[cells]+.95*K.sum(axis=1)/(len(xy)-1)
  rows.append(dict(h=h,loo=float(np.log(b).sum())))
 return max(rows,key=lambda r:(r['loo'],-r['h']))['h'],rows
def prepare(a,m,g,arm,h,ep_spatial,*,training=False):
 out={k:v.copy() for k,v in a.items()};scale,q=ep_spatial if arm==4 else (m['sigma'],2)
 F=g.masses(a['parent_xy'],a['rectangles'],scale,q)
 b=a['reference_pi']/a['cell_areas'];mult=b if arm==1 else np.ones(9);Z=F@mult
 out['parent_cell_mass']=F*mult[None,:]/Z[:,None]
 out['event_parent_density']=density(a['event_xy'],a['parent_xy'],scale,q,Z)*(b[a['event_cell'].astype(int),None] if arm==1 else 1)
 if arm==3:
  kxy=a['kde_training_xy'];KF=g.masses(kxy,a['rectangles'],h,2);KZ=KF.sum(axis=1)
  out['background_cell_mass']=.05*a['reference_pi']+.95*np.mean(KF/KZ[:,None],axis=0)
  K=density(a['event_xy'],kxy,h,2,KZ)
  if training:
   # Kernel identities follow exactly the training event order in the sealed cache.
   if len(K)!=len(kxy) or not np.array_equal(a['event_xy'],kxy):raise ValueError('LOO_IDENTITY_BINDING')
   np.fill_diagonal(K,0);smooth=K.sum(axis=1)/(len(kxy)-1)
  else:smooth=K.mean(axis=1)
  out['event_background_density']=.05*b[a['event_cell'].astype(int)]+.95*smooth
 return out
def features(a,m,temporal):
 c=np.exp(temporal[0]);p=temporal[1];lag=a['event_time'][:,None]-a['parent_time'][None,:];positive=lag>0
 safe=np.maximum(lag,0);K=(p-1)/c*np.exp(-p*np.log1p(safe/c))*positive*a['parent_fertility'][None,:]
 hp=(K*a['event_parent_density']).sum(axis=1);hg=K.sum(axis=1)
 lo=a['parent_exposure_lo'];hi=a['parent_exposure_hi'];J=np.exp((1-p)*np.log1p(lo/c))*(-np.expm1((1-p)*np.log1p((hi-lo)/(c+lo))))
 exposure=float(J@a['parent_fertility'])
 return dict(b=a['event_background_density'],x=a['event_x'],hp=hp,hg=hg,exposure=exposure,start=m['start'],end=m['end'],T0=m['T0'],marks=float(len(hp)*np.log(m['beta'])-m['beta']*a['event_excess'].sum()))
def evaluate(f,pars):
 a,d,n=pars;half=(f['end']-f['start'])/f['T0'];center=(f['start']+f['end'])/f['T0']-1;z=d*half
 if abs(z)<1e-5:s=1+z*z/6+z**4/120;ds=half*(z/3-z**3/45)
 else:s=np.sinh(z)/z;ds=half*(1/np.tanh(z)-1/z)
 B=np.exp(a+d*center)*(f['end']-f['start'])*s;mu=np.exp(a+d*f['x']);point=mu*f['b']+n*f['hp'];ground=mu+n*f['hg'];comp=B+n*f['exposure']
 lp=np.log(point).sum();lg=np.log(ground).sum();grad=np.array([B-np.sum(mu*f['b']/point),B*(center+ds)-np.sum(f['x']*mu*f['b']/point),f['exposure']-np.sum(f['hp']/point)])
 return dict(nll=float(comp-lp-f['marks']),timing=float(lg-comp),location=float(lp-lg),mark=f['marks'],joint=float(lp-comp+f['marks']),compensator=float(comp),point=float(lp)),grad
def fit(f,initial):
 b=[(-12,0),(-2,2),(0,.98)];records=[]
 starts=[[float(np.clip(initial[0]+da,-12,0)),d,n] for da in [0,-.5] for d in [-.2,.2] for n in [.2,.6]]
 def floor_at(d):
  half=(f['end']-f['start'])/f['T0'];center=(f['start']+f['end'])/f['T0']-1;z=d*half
  integral=(f['end']-f['start'])*np.exp(d*center)*(np.sinh(z)/z if abs(z)>1e-8 else 1+z*z/6)
  a=float(np.clip(np.log(max(len(f['x']),1)/integral),-12,0));return [a,float(d),0]
 floor_fit=minimize_scalar(lambda d:evaluate(f,floor_at(d))[0]['nll'],bounds=(-2,2),method='bounded',options={'xatol':1e-12})
 floor=min([floor_at(floor_fit.x),floor_at(-2),floor_at(2)],key=lambda p:evaluate(f,p)[0]['nll'])
 for i,s in enumerate(starts):
  fun=lambda x:(evaluate(f,x)[0]['nll'],evaluate(f,x)[1])
  o=minimize(fun,s,jac=True,bounds=b,method='L-BFGS-B',options=dict(maxls=200,maxiter=400,ftol=1e-12,gtol=1e-7))
  records.append(dict(start=i,method='L-BFGS-B',success=bool(o.success),pars=o.x.tolist(),nll=float(o.fun)))
  if not o.success:
   o=minimize(lambda x:evaluate(f,x)[0]['nll'],o.x,bounds=b,method='Powell',options=dict(maxiter=400,ftol=1e-12,xtol=1e-8))
   records.append(dict(start=i,method='Powell',success=bool(o.success),pars=o.x.tolist(),nll=float(o.fun)))
 candidates=[r for r in records if r['success']];candidates+=[dict(start=-1,method='floor',success=True,pars=floor,nll=evaluate(f,floor)[0]['nll'])]
 selected=min(candidates,key=lambda r:(r['nll'],r['start']>=0,r['start']));complete=len({r['start'] for r in candidates if r['start']>=0})==8
 return dict(status='complete' if complete else 'unknown_starts',selected=selected,records=records,candidates=candidates)
def fit_ep_training(a,m,temporal,dll,initial):
 lib=C.CDLL(str(Path(dll).resolve()));ptr=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
 lib.cb_create.argtypes=[C.c_int,C.c_int]+[ptr]*13;lib.cb_create.restype=C.c_void_p
 lib.cb_eval.argtypes=[C.c_void_p,C.c_int,ptr,C.c_int,ptr,ptr,C.c_void_p];lib.cb_eval.restype=C.c_int;lib.cb_destroy.argtypes=[C.c_void_p]
 names=['parent_time','parent_xy','parent_fertility','parent_exposure_lo','parent_exposure_hi','event_time','event_xy','event_x','event_cell','event_background_density','background_cell_mass','rectangles']
 arrays=[np.ascontiguousarray(a[n],dtype=np.float64) for n in names];marks=len(a['event_time'])*np.log(m['beta'])-m['beta']*a['event_excess'].sum();meta=np.array([m['start'],m['end'],m['T0'],marks])
 h=lib.cb_create(len(a['event_time']),len(a['parent_time']),*arrays,meta)
 if not h:raise ArithmeticError('EP_TRAIN_CREATE')
 b=[(-12,0),(-2,2),(0,.98),(np.log(2),np.log(500)),(1.05,3)];records=[]
 def objective(x):
  p=np.ascontiguousarray([*x[:3],*temporal,*x[3:]],float);o=np.empty(28);grad=np.empty(7)
  if lib.cb_eval(h,1,p,7,o,grad,None):raise ArithmeticError('EP_TRAIN_EVALUATION')
  return float(o[0]),grad[[0,1,2,5,6]].copy()
 try:
  for i,(ell,q) in enumerate([(2,1.1),(5,1.5),(15,2),(50,2.5),(150,1.1),(500,1.5),(15,3),(150,2)]):
   s=[*initial[:3],np.log(ell),q];o=minimize(objective,s,jac=True,bounds=b,method='L-BFGS-B',options=dict(maxls=200,maxiter=300,ftol=1e-11,gtol=2e-6));records.append(dict(start=i,method='L-BFGS-B',success=bool(o.success),pars=[*o.x[:3],*temporal,*o.x[3:]],nll=float(o.fun)))
   if not o.success:
    o=minimize(lambda x:objective(x)[0],o.x,bounds=b,method='Powell',options=dict(maxiter=400,ftol=1e-11));records.append(dict(start=i,method='Powell',success=bool(o.success),pars=[*o.x[:3],*temporal,*o.x[3:]],nll=float(o.fun)))
  valid=[r for r in records if r['success']];return dict(selected=min(valid,key=lambda r:r['nll']),records=records,status='complete' if len({r['start'] for r in valid})==8 else 'unknown_starts')
 finally:lib.cb_destroy(h)
def run(case_path,out,dll,ep_fit):
 begun=time.perf_counter();case=read(case_path);oc=case['models']['Omori_smooth_cont'];pars=oc['selected']['pars'];g=Geometry(dll)
 caches=cache_paths(oc);train,tm=load(caches['train16']);test,vm=load(caches['test16']);h=tm['kde_bandwidth'];selection='inherited training-only LOO-selected bandwidth; unchanged';results=[];private=[]
 if ep_fit:
  ep=read(ep_fit)['selected']['pars']
 else:
  trained=fit_ep_training(train,tm,pars[3:5],dll,pars);ep_fit=Path(out)/'ep_training_private.json';write(ep_fit,trained)
  if trained['status']!='complete':raise ArithmeticError('NZ_EP_TRAINING_INCOMPLETE')
  ep=trained['selected']['pars']
 ep_spatial=(float(np.exp(ep[5])),float(ep[6]))
 for arm in range(1,5):
  tr=prepare(train,tm,g,arm,h,ep_spatial,training=True);te=prepare(test,vm,g,arm,h,ep_spatial);tf=features(tr,tm,pars[3:5]);vf=features(te,vm,pars[3:5]);f=fit(tf,pars[:3]);forecast=evaluate(vf,f['selected']['pars'])[0]
  near=[dict(candidate=c,forecast=evaluate(vf,c['pars'])[0]) for c in f['candidates'] if c['nll']<=f['selected']['nll']+4e-4]
  spread=(max(c['forecast']['joint'] for c in near)-min(c['forecast']['joint'] for c in near))/max(1,len(test['event_time']))
  control=None
  if arm==1:
   control=dict(density_maxabs=float(np.max(abs(te['event_parent_density']-test['event_parent_density']))),mass_maxabs=float(np.max(abs(te['parent_cell_mass']-test['parent_cell_mass']))),nll_samepars_delta=abs(evaluate(vf,pars[:3])[0]['nll']-evaluate(features(test,vm,pars[3:5]),pars[:3])[0]['nll']))
   if control['density_maxabs']>1e-10 or control['mass_maxabs']>1e-10 or control['nll_samepars_delta']>1e-4:raise ArithmeticError('BASELINE_CACHE_RECONCILIATION')
  results.append(dict(arm=arm,status=f['status'],n_test=len(test['event_time']),scores=forecast,bandwidth_km=h if arm==3 else tm['kde_bandwidth'],near_optimal_spread_per_event=spread,control=control))
  private.append(dict(arm=arm,fit=f,near_optimal_forecasts=near,ep_spatial_source=str(ep_fit),ep_spatial=ep_spatial,temporal_mark_source=str(case_path),temporal=pars[3:5],train_cache=caches['train16'],test_cache=caches['test16'],forecast=forecast))
 out=Path(out);write(out/'private.json',dict(case_path=str(case_path),case_sha256=sha(case_path),selection=selection,results=private));write(out/'aggregate.json',dict(schema='s03_fourarm_v1',case_id=case['case']['case_id'],results=results,wall_seconds=time.perf_counter()-begun,status='complete' if all(x['status']=='complete' for x in results) else 'unknown'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--output',required=True);p.add_argument('--dll',required=True);p.add_argument('--ep-fit');a=p.parse_args();run(a.case,a.output,a.dll,a.ep_fit)
