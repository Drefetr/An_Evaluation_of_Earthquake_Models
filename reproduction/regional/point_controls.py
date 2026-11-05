"""Fixed-input S05 point controls. No DLL is loaded or quadrature run on import."""
import argparse,hashlib,importlib.util,json,math,os,platform,time,warnings
from pathlib import Path
import numpy as np

COMPONENTS=('count','mark_sum','immigrant_exposure','trigger_exposure','event_log_ground','event_log_point','mark_logscore','joint_logscore')
ABS_TOL=1e-7;MARKSUM_TOL=1e-12;MASS_TOL=1e-9;REFERENCE_ERROR_LIMIT=1e-9
SOURCE_PINS={
 'replay.py':'53919c6055bd295d3db137543b26e923939c06637bf710daadffde9739e48bda',
 'native_wrapper.py':'8f1a6f5a9d84cb8d5b195f233fcc2ff0af1f1f92a5d16777c0569ddc49d07940',
 'original_full84.py':'b1b63a1730140acf57bd09967456c14dcaceaec9c48123076241b9a1a293ecd8',
 'independent.cpp':'fde2a01adeccd78b41668d01af5c9d1ebd5883735e96792aae18b4eefef71ec1',
 'temporal_extension.cpp':'00e4f68241b5229d705fd30f02271616171d1a2ef5b4ce19578a000ee2208805',
 'build.sh':'26913905bdf0f78ca3e2a469c5f735a46ece605ee5e7fcdf9981060409a60638',
 'build.cmd':'893406bcd7d15800895ecbdc01b0bd2624b592b4cbbc268dc6a58ee0a962bc9c',
 'PROTOCOL.md':'4f0622b4d57bfc489c4efa1cb151a1f43a70b4c5a8cecbd1e2bc265ed67830c1'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(value):
 if isinstance(value,np.ndarray):return safe(value.tolist())
 if isinstance(value,np.generic):return safe(value.item())
 if isinstance(value,float) and not math.isfinite(value):return {'nonfinite':'NaN' if math.isnan(value) else ('+Infinity' if value>0 else '-Infinity')}
 if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
 if isinstance(value,(list,tuple)):return [safe(v) for v in value]
 return value
def write(p,value):
 temporary=p.with_suffix(p.suffix+'.tmp');temporary.write_text(json.dumps(safe(value),indent=2,allow_nan=False)+'\n');os.replace(temporary,p)
def assess(actual,expected):
 actual=np.asarray(actual,float);expected=np.asarray(expected,float)
 if actual.shape!=(8,) or expected.shape!=(8,):return dict(passed=False,error='Expected eight ABI components',actual=safe(actual),expected=safe(expected))
 rows=[]
 for i,name in enumerate(COMPONENTS):
  finite=math.isfinite(float(actual[i])) and math.isfinite(float(expected[i]));delta=abs(float(actual[i]-expected[i])) if finite else None;tol=0. if i==0 else MARKSUM_TOL if i==1 else ABS_TOL
  rows.append(dict(component=name,actual=safe(actual[i]),expected=safe(expected[i]),absolute_error=delta,absolute_tolerance=tol,passed=finite and delta<=tol))
 return dict(passed=all(v['passed'] for v in rows),components=rows)
def retained_attempt(name,callback):
 """Run every declared case; preserve errors instead of suppressing its row."""
 begin=time.perf_counter()
 try:result=callback();return dict(name=name,**result,seconds=time.perf_counter()-begin)
 except Exception as exc:return dict(name=name,passed=False,error_type=type(exc).__name__,error=str(exc),seconds=time.perf_counter()-begin)
def fixtures():
 rectangles=np.array([[x,x+1,y0,y1] for y0,y1 in ((0,1),(1,3),(3,6)) for x in range(3)],float)
 pi=np.arange(1.,10.)/45.;train=np.array([[.25,.5],[2.5,5.5]])
 pre=np.array([[-.4,.2,0.,0.],[-.05,.5,3.-1e-8,1.]])
 events=np.array([[0.,.1,1.,1.],[.25,.2,0.,6.],[.25,.7,2.,3.],[.9,.4,3.,1e-8]])
 laws=[('OC',2.)]+[('EP',q) for q in (1.05,1.4,2.,3.)]
 result=[]
 for model,q in laws:
  base=np.array([-1.1,.15,.35,.4,1.4,.8,1.1,2.2,3.,0.,1.]+([q] if model=='EP' else []))
  for scenario in ('empty_no_history','empty_with_prehistory','zero_branching_boundaries','strict_past','single_at_start'):
   p=base.copy();history=pre.copy();future=events.copy()
   if scenario=='empty_no_history':history=np.empty((0,4));future=np.empty((0,4))
   elif scenario=='empty_with_prehistory':future=np.empty((0,4))
   elif scenario=='zero_branching_boundaries':p[1]=0.;p[2]=0.
   elif scenario=='single_at_start':history=np.empty((0,4));future=events[:1].copy()
   result.append(dict(name=f'{model}_q{q}_{scenario}',model=model,q=q,scenario=scenario,state=dict(params=p,rectangles=rectangles.copy(),pi=pi.copy(),training_xy=train.copy(),prehistory=history,subblocks=np.linspace(0,1,6)),events=future))
 return result

class CartesianReference:
 """Direct Cartesian integration, independent of archived polar mass routines."""
 def __init__(self):self.masses={};self.integrals=[];self.traces=[]
 def integral(self,function,lower,upper,label):
  from scipy.integrate import quad,IntegrationWarning
  record=dict(label=label,lower=lower,upper=upper,passed=False);self.integrals.append(record)
  try:
   with warnings.catch_warnings():
    warnings.simplefilter('error',IntegrationWarning)
    value,error=quad(function,lower,upper,epsabs=1e-12,epsrel=1e-12,limit=200)
   record.update(value=value,estimated_absolute_error=error)
   if not math.isfinite(value) or not math.isfinite(error) or error>REFERENCE_ERROR_LIMIT:raise ArithmeticError('Reference quadrature error/nonfinite: '+label)
   record['passed']=True;return value,error
  except Exception as exc:record.update(error_type=type(exc).__name__,error=str(exc));raise
 @staticmethod
 def kernel(x,y,center,scale,q):return (1+((x-center[0])/scale)**2+((y-center[1])/scale)**2)**(-q)
 def mass(self,rectangle,center,scale,q):
  key=tuple(float(x) for x in (*rectangle,*center,scale,q))
  if key in self.masses:return self.masses[key]
  x0,x1,y0,y1=rectangle;inner_errors=[]
  def outer(x):
   value,error=self.integral(lambda y:self.kernel(x,y,center,scale,q),y0,y1,'rectangle_inner_y')
   inner_errors.append(error);return value
  value,error=self.integral(outer,x0,x1,'rectangle_outer_x')
  total_error=error+(x1-x0)*max(inner_errors,default=0.)
  record=dict(label='rectangle_mass_combined_estimate',key=key,value=value,estimated_absolute_error=total_error,passed=math.isfinite(value) and value>0 and total_error<=REFERENCE_ERROR_LIMIT);self.integrals.append(record)
  if not record['passed']:raise ArithmeticError('Rectangle reference accuracy gate failed')
  self.masses[key]=value;return value
 @staticmethod
 def cell(point,rectangles):
  # Cartesian grid definition independent of the native inclusive-box loop.
  xedges=sorted(set(rectangles[:,0])|set(rectangles[:,1]));yedges=sorted(set(rectangles[:,2])|set(rectangles[:,3]));x,y=point
  if not(xedges[0]<=x<=xedges[-1] and yedges[0]<=y<=yedges[-1]):raise ValueError('Point outside reference region')
  ix=min(int(np.searchsorted(xedges,x,side='right'))-1,len(xedges)-2);iy=min(int(np.searchsorted(yedges,y,side='right'))-1,len(yedges)-2)
  return iy*(len(xedges)-1)+ix
 def evaluate(self,state,events,model,label):
  p=state['params'];a,d,n,c,power,scale,bandwidth,beta,T0,start,end=p[:11];spatial_q=float(p[11]) if model=='EP' else 2.
  rectangles=state['rectangles'];rho=state['pi']/((rectangles[:,1]-rectangles[:,0])*(rectangles[:,3]-rectangles[:,2]));training=state['training_xy'];pre=state['prehistory']
  mu=lambda t:math.exp(a+d*(2*t/T0-1))
  temporal=lambda lag:(power-1)/c*(1+lag/c)**(-power)
  productivity=lambda mark:n*.3*math.exp(.7*beta*mark)
  def normalizer(center,s,q,weighted):return math.fsum(self.mass(r,center,s,q)*(rho[j] if weighted else 1.) for j,r in enumerate(rectangles))
  background_z=[normalizer(x,bandwidth,2.,False) for x in training]
  def background(point):return .05*rho[self.cell(point,rectangles)]+.95*math.fsum(self.kernel(*point,x,bandwidth,2.)/z for x,z in zip(training,background_z))/len(training)
  allparents=np.concatenate((pre,events),axis=0);normalizers=[normalizer(row[2:],scale,spatial_q,model=='OC') for row in allparents]
  ground_logs=[];point_logs=[];event_trace=[]
  for event in events:
   t,mark,x,y=event;point=(x,y);ground_terms=[mu(t)];point_terms=[mu(t)*background(point)];used=[]
   for j,parent in enumerate(allparents):
    if not parent[0]<t:continue
    intensity=productivity(parent[1])*temporal(t-parent[0]);density=self.kernel(x,y,parent[2:],scale,spatial_q)/normalizers[j]
    if model=='OC':density*=rho[self.cell(point,rectangles)]
    ground_terms.append(intensity);point_terms.append(intensity*density);used.append(j)
   ground=math.fsum(ground_terms);point_intensity=math.fsum(point_terms);ground_logs.append(math.log(ground));point_logs.append(math.log(point_intensity));event_trace.append(dict(event=event,strict_past_indices=used,ground=ground,point=point_intensity,background_density=background(point)))
  B,_=self.integral(mu,start,end,label+':immigrant_exposure')
  exposures=[]
  for j,parent in enumerate(allparents):
   lower=max(start,float(parent[0]));upper=end
   if lower>=upper:exposures.append(0.);continue
   mass,_=self.integral(lambda t:temporal(t-parent[0]),lower,upper,label+f':parent_{j}_temporal_exposure');exposures.append(productivity(parent[1])*mass)
  trigger=math.fsum(exposures);N=len(events);marksum=math.fsum(float(row[1]) for row in events);markscore=N*math.log(beta)-beta*marksum;lg=math.fsum(ground_logs);lp=math.fsum(point_logs)
  expected=np.array([N,marksum,B,trigger,lg,lp,markscore,lp-B-trigger+markscore])
  self.traces.append(dict(name=label,events=event_trace,parent_normalizers=normalizers,parent_exposures=exposures,background_normalizers=background_z,expected=expected));return expected

def pin_sources(source_dir):
 actual={name:sha(source_dir/name) for name in SOURCE_PINS}
 if actual!=SOURCE_PINS:raise ValueError('Archived scoring source hash mismatch: '+json.dumps({k:dict(actual=actual[k],expected=v) for k,v in SOURCE_PINS.items() if actual[k]!=v},sort_keys=True))
 return actual
def load_native(source_dir,library):
 # Importing this adapter defines types only; Native below performs the load.
 spec=importlib.util.spec_from_file_location('_s05_point_controls_native',source_dir/'native_wrapper.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.Native(library)
def run(library,source_dir,output,build_receipt=None):
 library=Path(library).resolve();source_dir=Path(source_dir).resolve();output=Path(output).resolve()
 if output.is_relative_to(Path(__file__).resolve().parent):raise ValueError('Use a fresh external report path')
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x',encoding='utf-8') as f:f.write('{}\n')
 report=dict(schema='s05_independent_point_controls_v1',passed=False,status='started',scope='Tiny deterministic OC/EP point-evaluator controls only; no historical data, fitting or simulation',wrapper_sha256=sha(__file__),component_tolerance=ABS_TOL,mark_sum_tolerance=MARKSUM_TOL,count_tolerance=0.,mass_tolerance=MASS_TOL,reference_error_limit=REFERENCE_ERROR_LIMIT,point_cases=[],geometry_cases=[],runtime=dict(python=platform.python_version(),numpy=np.__version__,platform=platform.platform()),binary_source_binding='Library and exact source bytes pinned separately; conductor build receipt required to establish compilation provenance.')
 report.update(planned_point_cases=25,planned_geometry_cases=10,fixture_inputs=fixtures())
 ref=CartesianReference();begin=time.perf_counter();write(output,report)
 try:
  report['source_pins']=pin_sources(source_dir);report['library_sha256']=sha(library)
  if build_receipt is not None:report['build_receipt_sha256']=sha(build_receipt)
  import scipy
  report['runtime']['scipy']=scipy.__version__;write(output,report);native=load_native(source_dir,library)
  for model,q in [('OC',2.)]+[('EP',q) for q in (1.05,1.4,2.,3.)]:
   for center in ((0.,0.),(3.-1e-8,1.)):
    def geometry_case(model=model,q=q,center=center):
     rect=fixtures()[0]['state']['rectangles'];expected=np.array([ref.mass(r,center,.8,q) for r in rect]);actual=native.mass(rect,np.tile(center,(9,1)),.8,q);finite=bool(np.isfinite(actual).all());delta=np.abs(actual-expected)
     return dict(passed=finite and bool(np.all(delta<=MASS_TOL)),model=model,q=q,center=center,actual=actual,expected=expected,absolute_error=delta,absolute_tolerance=MASS_TOL)
    report['geometry_cases'].append(retained_attempt(f'{model}_q{q}_center{center}',geometry_case));report['reference_integrals']=ref.integrals;write(output,report)
  for fixture in fixtures():
   def point_case(fixture=fixture):
    expected=ref.evaluate(fixture['state'],fixture['events'],fixture['model'],fixture['name']);state=native.state(fixture['state'],fixture['model'])
    try:actual=state.evaluate(fixture['events'])
    finally:state.close()
    return dict(**assess(actual,expected),model=fixture['model'],q=fixture['q'],scenario=fixture['scenario'],state=fixture['state'],events=fixture['events'],native_point_evaluate_called=True)
   report['point_cases'].append(retained_attempt(fixture['name'],point_case));report['reference_integrals']=ref.integrals;report['reference_event_traces']=ref.traces;write(output,report)
  if sha(library)!=report['library_sha256'] or pin_sources(source_dir)!=report['source_pins'] or sha(__file__)!=report['wrapper_sha256']:raise ValueError('Implementation drift during controls')
  report['passed']=len(report['point_cases'])==25 and len(report['geometry_cases'])==10 and all(v['passed'] for v in report['point_cases']+report['geometry_cases'])
  report['status']='passed' if report['passed'] else 'failed'
 except Exception as exc:report.update(status='failed',error_type=type(exc).__name__,error=str(exc))
 finally:report['reference_integrals']=ref.integrals;report['reference_event_traces']=ref.traces;report['seconds']=time.perf_counter()-begin;write(output,report)
 return report
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--dll',type=Path,required=True);parser.add_argument('--sources',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--build-receipt',type=Path);args=parser.parse_args()
 report=run(args.dll,args.sources,args.output,args.build_receipt);print(json.dumps({'passed':report['passed'],'point_cases':len(report['point_cases']),'geometry_cases':len(report['geometry_cases']),'scope':report['scope']}));return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
