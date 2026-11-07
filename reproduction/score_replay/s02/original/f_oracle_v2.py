"""Q01 independent raw-history finite-mixture audit; no production imports."""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,math,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
HERE=Path(__file__).resolve().parent;RUN=HERE.parent;ROOT=RUN.parents[1];D=C.POINTER(C.c_double)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,why):
 if not x:raise ValueError(why)
def arr(v):
 a=np.ascontiguousarray(v,dtype=np.float64);need(np.isfinite(a).all(),'FINITE_INPUT');return a
def ptr(a):return a.ctypes.data_as(D)
def mixture(spec):
 if spec['kind']=='exp':return np.ones(1),np.array([1/float(spec['tau'])])
 need(spec['kind']=='ml','FINITE_MIXTURE_ONLY');alpha=float(spec.get('alpha',.5));step=float(spec.get('spectral_step',.4));tail=float(spec.get('spectral_tail_bound',1e-8));need(0<alpha<1 and step>0 and tail>0,'MIXTURE_DOMAIN')
 coefficient=4*math.sin(math.pi*alpha)/(math.pi*alpha);extent=max(math.log(4)/alpha,math.log(coefficient/tail)/alpha);count=math.ceil(extent/step);v=np.arange(-count,count+1)*step
 weight=step*math.sin(math.pi*alpha)/(2*math.pi*(np.cosh(alpha*v)+math.cos(math.pi*alpha)));weight[[0,-1]]*=.5
 return arr(weight/weight.sum()),arr(np.exp(v)/float(spec['tau']))
def public_law(s02=False):
 if s02:s=read(RUN/'M01/S02_STAGED_RECIPE.json')['law']
 else:s=read(ROOT/'research_f_continuation/paper/supplements/methods_settings.json')['synthetic_generating_law']
 f=s['alternative_generating_fit'];return dict(T=float(s['horizon_days']),coordinate=float(s['coordinate_horizon_days']),beta=float(s['beta']),gamma=.75*math.log(10),n=.5 if s02 else float(f['pars'][2]),ratio=float(f['ratio']),stress=f['stress'],trigger=f['trigger'])
def clock(data,law,mode):
 hi=arr(data['times']);Q=arr(data['excess']);need(hi.ndim==1 and Q.shape==hi.shape and np.all(Q>=0),'HISTORY_SHAPE')
 if mode in ('projected','original_projected_clock'):
  need(np.all(np.diff(hi)>0) and (not len(hi) or hi[-1]<law['T']),'PROJECTED_CHRONOLOGY');return hi,np.zeros(len(hi)),arr(np.diff(np.r_[0,hi,law['T']])),Q,False
 need(mode in ('paired','paired_clock'),'CLOCK_MODE');lo=arr(data['times_lo']);gap=arr(data['event_gaps']);need(lo.shape==hi.shape and gap.shape==hi.shape and np.all(gap>0),'PAIRED_SHAPE')
 for i in range(len(hi)):
  oldhi,oldlo=(hi[i-1],lo[i-1]) if i else (0.,0.);represented=math.fsum((float(hi[i]),-float(oldhi),float(lo[i]),-float(oldlo)));allowance=4*(math.ulp(float(lo[i]))+math.ulp(float(oldlo))+math.ulp(represented)+math.ulp(float(gap[i])))
  need(represented>0 and abs(represented-gap[i])<=allowance and abs(lo[i])<=4*math.ulp(float(hi[i])),'PAIRED_CANONICAL_CLOCK')
 remaining=math.fsum((law['T'],-float(hi[-1]),-float(lo[-1]))) if len(hi) else law['T'];need(remaining>0,'TERMINAL_EXPOSURE');return hi,lo,arr(np.r_[gap,remaining]),Q,True
class Native:
 def __init__(self,dll):
  self.lib=C.CDLL(str(Path(dll).resolve()));l=self.lib;l.qf_error.restype=C.c_char_p
  l.qf_create.argtypes=[C.c_int,D,D,D,D,C.c_int,D,D,C.c_int,D,D,C.c_int,D,C.c_int,C.c_int]+[C.c_double]*6;l.qf_create.restype=C.c_void_p
  l.qf_evaluate.argtypes=[C.c_void_p,D,D];l.qf_evaluate.restype=C.c_int;l.qf_free.argtypes=[C.c_void_p]
 def state(self,data,law,mode,ratio,order=32,refined=True):return State(self,data,law,mode,ratio,order,refined)
class State:
 def __init__(self,native,data,law,mode,ratio,order,refined):
  hi,lo,gap,Q,paired=clock(data,law,mode);sw,sr=mixture(law['stress']);tw,tr=mixture(law['trigger']);base=np.geomspace(1e-6,1e5,23);offsets=np.sort(np.r_[base,np.sqrt(base[:-1]*base[1:])]);offsets=np.unique(np.r_[np.geomspace(1e-12,1e-6,7),offsets]) if refined else offsets;offsets=arr(offsets);self.native=native;self.handle=None
  self.handle=native.lib.qf_create(len(hi),ptr(hi),ptr(lo),ptr(gap),ptr(Q),len(sw),ptr(sw),ptr(sr),len(tw),ptr(tw),ptr(tr),len(offsets),ptr(offsets),order,int(paired),law['T'],law['coordinate'],law['beta'],law['gamma'],ratio,1536*2**20)
  if not self.handle:raise ArithmeticError(native.lib.qf_error().decode())
 def evaluate(self,p):
  p=arr(p);need(p.shape==(4,),'PARAMETER_SHAPE');out=np.empty(6)
  if self.native.lib.qf_evaluate(self.handle,ptr(p),ptr(out)):raise ArithmeticError(self.native.lib.qf_error().decode())
  return out
 def close(self):
  if self.handle:self.native.lib.qf_free(self.handle);self.handle=None

def projected(gradient,pars,free):
 bounds={0:(-12,0),1:(-2,2),3:(0,3)};out=[]
 for k in free:
  v=float(gradient[k]);lo,hi=bounds[k]
  if (pars[k]<=lo+1e-10 and v>=0) or (pars[k]>=hi-1e-10 and v<=0):v=0
  out.append(abs(v))
 return max(out,default=0.)
def audit_case(task):
 dll,binding,case,cells,pilot,private=task;begin=time.perf_counter();native=Native(dll);law=public_law();file=ROOT/binding['files']['catalogue.npz']['path'];need(sha(file)==binding['files']['catalogue.npz']['sha256'],'RAW_HISTORY_PIN')
 with np.load(file,allow_pickle=False) as z:data={k:z[k].copy() for k in z.files}
 saved_path=RUN/'M01/fits'/(case+'.json');need(saved_path.exists(),'MISSING_CASE');saved=read(saved_path);need(saved['input_sha256']==sha(file),'FIT_INPUT_IDENTITY');need(len(saved['methods'])==len({m['cell'] for m in saved['methods']}),'DUPLICATE_METHOD')
 state=native.state(data,law,binding['clock_mode'],law['ratio'],32,True);high=native.state(data,law,binding['clock_mode'],law['ratio'],64,True) if pilot else None
 checked=0;maxnll=maxgrad=projectedmax=quadmax=0.;complete=0;unknown=0;details=[]
 try:
  for cell in cells:
   matches=[m for m in saved['methods'] if m['cell']==cell]
   if not matches or matches[0]['status']!='complete':unknown+=1;details.append({'cell':cell,'status':'producer_unknown'});continue
   m=matches[0];free_null={'I00':[],'I10':[0],'I01':[1],'I11':[0,1]}[cell];required_null=8 if free_null else 0
   records=m['attempts'];need(sum(r['success'] and r['phase']=='null' for r in records)==required_null and sum(r['success'] and r['phase']=='alternative' for r in records)==8,'PRESCRIBED_STARTS')
   # A failed numerical tier may legitimately recover within its prescribed start.
   for phase,total in [('null',required_null),('alternative',8)]:
    groups={i:[r for r in records if r['phase']==phase and r['start_index']==i] for i in range(total)}
    need({r['start_index'] for r in records if r['phase']==phase}==set(range(total)),'START_INDEX_MAP')
    for sequence in groups.values():
     expected_tiers=['LBFGSB40','LBFGSB200','Powell'];need(1<=len(sequence)<=3 and [r['tier'] for r in sequence]==expected_tiers[:len(sequence)],'RECOVERY_TIER_ORDER')
     need(sequence[-1]['success'] and not any(r['success'] for r in sequence[:-1]),'START_NOT_RECOVERED_OR_EXTRA_TIERS')
   need(all(c['passed'] for c in m['controls']),'FAILED_QUADRATURE_PROMOTED')
   values={}
   for phase in ('null','alternative'):
    p=m[phase]['pars'];need(p[2]==law['n'] and -12<=p[0]<=0 and -2<=p[1]<=2 and 0<=p[3]<=3,'FIXED_N_BOUNDS');v=state.evaluate(p);err=abs(v[0]-m[phase]['nll']);need(err<=1e-4,'INDEPENDENT_NLL');maxnll=max(maxnll,err);values[phase]=v[0];checked+=1
    if high:delta=abs(high.evaluate(p)[0]-v[0]);quadmax=max(quadmax,delta);need(delta<=1e-4,'REFINED_32_64')
   glr=2*(values['null']-values['alternative']);err=abs(glr-m['direct_contrast16']['statistic']);need(err<=1e-4,'INDEPENDENT_GLR');maxnll=max(maxnll,err)
   for record in records:
    p=record['terminal_pars'];v=state.evaluate(p);err=abs(v[0]-record['terminal_best_nll']);need(err<=1e-4,'RETAINED_CANDIDATE_NLL');maxnll=max(maxnll,err);gradient=v[1:5];free=record['free'];gn=max(abs(float(gradient[k])) for k in free);norm_delta=abs(gn-record['terminal_gradient_norm'])/(1+abs(record['terminal_gradient_norm']));maxgrad=max(maxgrad,norm_delta);projectedmax=max(projectedmax,projected(gradient,p,free));checked+=1
   complete+=1;details.append({'cell':cell,'status':'audited','independent_glr':glr})
 finally:
  state.close()
  if high:high.close()
 path=Path(private)/(case+'.json');need(not path.exists(),'APPEND_ONLY');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({'case':case,'methods':details,'source_fit_sha256':sha(saved_path),'history_sha256':sha(file)},indent=2)+'\n')
 return dict(planned_methods=len(cells),complete_methods=complete,unknown_methods=unknown,audited_saved_points=checked,n_events=len(data['times']),maximum_absolute_nll_glr_error=maxnll,maximum_gradient_norm_scaled_discrepancy=maxgrad,maximum_projected_gradient_diagnostic=projectedmax,refined32_64_maximum_nll_difference=quadmax,wall_seconds=time.perf_counter()-begin,private_receipt_sha256=sha(path))

def fixtures(dll):
 from scipy.integrate import quad
 native=Native(dll);law=dict(T=3.,coordinate=3.,beta=2.,gamma=.75*math.log(10),n=.5,ratio=.2,stress={'kind':'exp','tau':.3},trigger={'kind':'exp','tau':.7});cases=[('projected',dict(times=np.array([]),excess=np.array([]))),('projected',dict(times=np.array([.2,1.,2.]),excess=np.array([0.,.1,.2]))),('paired',dict(times=np.array([1.,1.,2.]),times_lo=np.array([0.,1e-20,0.]),event_gaps=np.array([1.,1e-20,1.]),excess=np.array([.1,.2,.3])))];maxerr=maxfd=0.;checks=0
 for mode,data in cases:
  state=native.state(data,law,mode,.2,32,True)
  try:
   hi,lo,gap,Q,paired=clock(data,law,mode);stress=np.exp(law['gamma']*Q)/math.exp(law['gamma']);prod=.8*np.exp(.4*Q)
   for p in ([-2,.1,.5,0],[-1.9,.12,.45,.2],[-2,0,0,0]):
    a,d,n,eta=p;value=state.evaluate(p);event=0;trigger=0;integrals=[]
    for i in range(len(hi)):
     ages=[math.fsum((float(hi[i]),-float(hi[j]),float(lo[i]),-float(lo[j]))) for j in range(i)];G=math.fsum(stress[j]*math.exp(-age/.3) for j,age in enumerate(ages));H=math.fsum(prod[j]/.7*math.exp(-age/.7) for j,age in enumerate(ages));x=2*(hi[i]+lo[i])/3-1;event+=np.logaddexp(a+d*x-eta*G,math.log(n*H) if n*H>0 else -math.inf);trigger+=prod[i]*(-math.expm1(-math.fsum((3.,-float(hi[i]),-float(lo[i])))/.7))
    edges=[0.,*[float(t) for t in hi],3.];edges=sorted(set(edges))
    def f(t):
     G=math.fsum(stress[j]*math.exp(-(t-hi[j]-lo[j])/.3) for j in range(len(hi)) if t>hi[j]+lo[j]);return math.exp(a+d*(2*t/3-1)-eta*G)
    integral=math.fsum(quad(f,l,r,epsabs=1e-12,epsrel=1e-12)[0] for l,r in zip(edges[:-1],edges[1:]));expected=integral+n*trigger-event;err=abs(value[0]-expected);maxerr=max(maxerr,err);need(err<=1e-8,'DIRECT_SMALL_HISTORY_NLL')
    for k in (0,1,3):
     step=1e-5;up=np.array(p,float);dn=up.copy();up[k]+=step
     if k==3 and eta==0:fd=(-3*value[0]+4*state.evaluate(up)[0]-state.evaluate(np.array(p,float)+np.eye(4)[k]*2*step)[0])/(2*step)
     else:dn[k]-=step;fd=(state.evaluate(up)[0]-state.evaluate(dn)[0])/(2*step)
     e=abs(fd-value[k+1])/(1+abs(fd));maxfd=max(maxfd,e);need(e<=1e-6,'FINITE_DIFFERENCE');checks+=1
    checks+=1
  finally:state.close()
 return dict(passed=True,checks=checks,maximum_direct_nll_error=maxerr,maximum_scaled_finite_difference_error=maxfd,scope='handcrafted direct sums/adaptiveintegral/emptyhistory/pairedtinydifferences;no scientificcampaign')
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['fixtures','pilot','all']);p.add_argument('--dll',required=True);p.add_argument('--dll-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--workers',type=int,default=6);a=p.parse_args();need(sha(a.dll)==a.dll_sha256,'AUDITOR_BINARY_PIN');out=Path(a.output);need(not out.exists(),'APPEND_ONLY');begin=time.perf_counter()
 if a.mode=='fixtures':result=fixtures(a.dll)
 else:
  inputs=read(RUN/'M01/INPUT_CASES.json');todo=[(x['id'],x['cells']) for role in ('reference','null_query','alternative_query') for x in inputs['missing'][role]]
  if a.mode=='pilot':small=read(RUN/'M01/FIT_PILOT_RESULT.json')['cases'];large=read(RUN/'M01/LARGE_FIT_PILOT_RESULT.json')['cases'];chosen={r['id'] for r in small+large};todo=[t for t in todo if t[0] in chosen];need(len(todo)==3,'THREE_STRATA')
  tasks=[(a.dll,inputs['bindings'][case],case,cells,a.mode=='pilot',str(out.with_suffix('.private'))) for case,cells in todo]
  with ProcessPoolExecutor(max_workers=a.workers) as pool:rows=list(pool.map(audit_case,tasks))
  result=dict(planned_histories=len(todo),audited_histories=len(rows),planned_methods=sum(x['planned_methods'] for x in rows),complete_methods=sum(x['complete_methods'] for x in rows),unknown_methods=sum(x['unknown_methods'] for x in rows),maximum_absolute_nll_glr_error=max(x['maximum_absolute_nll_glr_error'] for x in rows),maximum_gradient_norm_scaled_discrepancy=max(x['maximum_gradient_norm_scaled_discrepancy'] for x in rows),maximum_projected_gradient_diagnostic=max(x['maximum_projected_gradient_diagnostic'] for x in rows),refined32_64_maximum_nll_difference=max(x['refined32_64_maximum_nll_difference'] for x in rows),worker_summaries=rows,scope='independent rawhistory selectedandretainedcandidate reconstruction;projectedgradient diagnostic not automaticKKTcertificate')
 result.update(auditor_source_sha256=sha(__file__),native_source_sha256=sha(HERE/'independent_f_oracle.cpp'),native_binary_sha256=sha(a.dll),wall_seconds=time.perf_counter()-begin);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
