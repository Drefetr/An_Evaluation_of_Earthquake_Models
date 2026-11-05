"""Q01 independent native raw-path audit; no producer imports or caches."""
from pathlib import Path
import argparse,ctypes as C,hashlib,json,math,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
HERE=Path(__file__).resolve().parent;RUN=HERE.parent;ROOT=RUN.parents[1]
D=C.POINTER(C.c_double)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def array(v):
 a=np.ascontiguousarray(v,dtype=np.float64);need(np.isfinite(a).all(),'NONFINITE_PRIVATE_INPUT');return a
def ptr(a):return a.ctypes.data_as(D)
class Native:
 def __init__(self,dll):
  self.path=Path(dll);self.lib=C.CDLL(str(self.path.resolve()));l=self.lib
  l.q01_error.restype=C.c_char_p;l.q01_mass.argtypes=[D,C.c_double,C.c_double,C.c_double,C.c_double];l.q01_mass.restype=C.c_double
  l.q01_create.argtypes=[C.c_int,D,C.c_int,D,D,D,D,C.c_int];l.q01_create.restype=C.c_void_p;l.q01_free.argtypes=[C.c_void_p]
  l.q01_evaluate.argtypes=[C.c_void_p,C.c_int,D,D];l.q01_evaluate.restype=C.c_int
  l.q01_mass_batch.argtypes=[C.c_int,D,D,C.c_double,C.c_double,D];l.q01_mass_batch.restype=C.c_int
  l.q01_line_batch.argtypes=[C.c_int,D,D,D,C.c_double,C.c_double,D];l.q01_line_batch.restype=C.c_int
 def checked(self,code):
  if code:raise ArithmeticError(self.lib.q01_error().decode('utf-8'))
 def mass(self,bounds,centers,scale,q):
  b,c=np.asarray(bounds,float),np.asarray(centers,float);shape=np.broadcast_shapes(b.shape[:-1],c.shape[:-1]);b=array(np.broadcast_to(b,shape+(4,))).reshape(-1,4);c=array(np.broadcast_to(c,shape+(2,))).reshape(-1,2);out=np.empty(len(b))
  for start in range(0,len(b),4096):
   stop=min(start+4096,len(b));self.checked(self.lib.q01_mass_batch(stop-start,ptr(b[start:stop]),ptr(c[start:stop]),scale,q,ptr(out[start:stop])))
  return out.reshape(shape)
 def line(self,lower,upper,horizontal,scale,q):
  low,high,x=np.broadcast_arrays(lower,upper,horizontal);shape=low.shape;low=array(low).ravel();high=array(high).ravel();x=array(x).ravel();out=np.empty(len(x))
  self.checked(self.lib.q01_line_batch(len(x),ptr(low),ptr(high),ptr(x),scale,q,ptr(out)));return out.reshape(shape)
 def state(self,state,model):return PointState(self,state,model)
class PointState:
 def __init__(self,native,state,model):
  self.native=native;self.parameters=array(state['params']);self.handle=None
  if model=='OC':need(self.parameters.shape==(11,),'OC_SCHEMA');self.parameters=np.r_[self.parameters,2.]
  else:need(self.parameters.shape==(12,),'EP_SCHEMA')
  train=array(state['training_xy']);pre=array(state['prehistory']);rect=array(state['rectangles']);pi=array(state['pi'])
  need(train.ndim==2 and train.shape[1]==2 and pre.ndim==2 and pre.shape[1]==4 and rect.shape==(9,4) and pi.shape==(9,),'STATE_SCHEMA')
  self.handle=native.lib.q01_create(len(train),ptr(train),len(pre),ptr(pre),ptr(rect),ptr(pi),ptr(self.parameters),int(model=='EP'))
  if not self.handle:raise ArithmeticError(native.lib.q01_error().decode())
 def evaluate(self,events):
  e=array(events);need(e.ndim==2 and e.shape[1]==4,'PATH_SCHEMA');o=np.empty(8);self.native.checked(self.native.lib.q01_evaluate(self.handle,len(e),ptr(e),ptr(o)));return o
 def close(self):
  if self.handle:self.native.lib.q01_free(self.handle);self.handle=None

def load_state(p):
 with np.load(p,allow_pickle=False) as f:return {k:f[k].copy() for k in f.files}
def paths(model,origin):
 if model=='EP':
  row=next(x for x in read(RUN/'M03/binding/manifest.json')['cases'] if x['case_id']==origin)
  return row['simulation_state'],[{'index':i,'job_path':str(RUN/'M03/jobs'/origin/(str(i)+'.json')),'receipt_path':str(RUN/'M03/results'/origin/str(i)/'receipt.json')} for i in range(999)]
 m=read(ROOT/'research_runs/conditional_calibration_20261025T085151Z/design/production_audit_job_v1.json')
 return m['state_bindings'][origin]['path'],sorted([x for x in m['cases'] if x['case_id']==origin],key=lambda r:r['index'])
def expected_seed(model,origin,index):
 master='Thread02|conditional_calibration_20261025T085151Z|'+('OC|v1' if model=='OC' else 'EP|scientific-remediation-v1');rows=[]
 for purpose in ('immigrant','prehistory-offspring','descendants','marks'):
  digest=hashlib.sha256(f'{master}|production|{origin}|{index}|{purpose}'.encode()).digest()
  rows.append(dict(purpose=purpose,sha256=digest.hex(),seed_words_uint32_be=[int.from_bytes(digest[i:i+4],'big') for i in range(0,16,4)]))
 return rows

def audit_origin(task):
 dll,model,origin,pilot,private=task;begin=time.perf_counter();native=Native(dll);state_path,records=paths(model,origin);need([r['index'] for r in records]==list(range(999)),'PLANNED_INDEX_MAP')
 state=load_state(state_path);need('observed' not in state,'SIMULATION_STATE_LEAKAGE');obj=native.state(state,model);summary=[];maxscore=0.;maxmark=0.;complete=0
 try:
  for r in records[:1] if pilot else records:
   index=r['index'];receipt_path=Path(r['receipt_path']);job_path=Path(r['job_path'])
   if not receipt_path.exists():summary.append({'index':index,'status':'missing'});continue
   receipt=read(receipt_path);job=read(job_path)
   need(receipt['job_sha256']==sha(job_path) and receipt['input_state_sha256']==sha(state_path),'JOB_STATE_BINDING')
   need(receipt['binary_sha256']==job['binary_sha256'] and receipt['case_id']==origin and receipt['index']==index and receipt['mode']=='simulate' and receipt['phase']=='production','RECEIPT_IDENTITY')
   need(receipt['seed_records']==expected_seed(model,origin,index),'SEED_IDENTITY')
   if receipt['status']!='complete':summary.append({'index':index,'status':'producer_'+receipt['status']});continue
   base=receipt_path.parent;path=base/'private_path.npz';scalar=base/'scalars.json'
   need(sha(path)==receipt['path_sha256'] and sha(scalar)==receipt['scalars_sha256'] and sha(base/'private_detail.npz')==receipt['detail_sha256'],'ARTIFACT_BINDING')
   with np.load(path,allow_pickle=False) as f:events=f['events'].copy()
   stats=read(scalar)['stats'];o=obj.evaluate(events);B=o[2];trigger=o[3];E=B+trigger;expected={'count':o[0],'immigrant_exposure':B,'trigger_exposure':trigger,'exposure':E,'time_event_logsum':o[4],'timing_logscore':o[4]-E,'location_logscore':o[5]-o[4],'mark_logscore':o[6],'joint_logscore':o[7]}
   differences={k:abs(float(stats[k])-float(v)) for k,v in expected.items()};need(differences['count']==0,'EXACT_COUNT');need(abs(float(events[:,1].sum())-o[1])<=1e-10*max(1,abs(o[1])),'MARK_SUM')
   score_error=max(v for k,v in differences.items() if k!='count');need(score_error<=1e-4,'RAW_POINT_SCORE_RECONSTRUCTION')
   mark_error=abs(float(stats['mark_logscore'])-(len(events)*math.log(state['params'][7])-state['params'][7]*math.fsum(events[:,1])))
   maxscore=max(maxscore,score_error);maxmark=max(maxmark,mark_error);complete+=1
   summary.append({'index':index,'status':'passed','path_sha256':sha(path),'maximum_absolute_score_error':score_error})
 finally:obj.close()
 p=Path(private)/(model+'_'+origin+'.json');need(not p.exists(),'APPEND_ONLY');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'model':model,'origin':origin,'planned':1 if pilot else 999,'cases':summary},indent=2)+'\n')
 return dict(model=model,origin=origin,planned=1 if pilot else 999,complete=complete,unknown=len(summary)-complete,max_absolute_score_error=maxscore,max_mark_log_identity_error=maxmark,wall_seconds=time.perf_counter()-begin,private_receipt_sha256=sha(p))

def fixtures(dll):
 from scipy.integrate import quad
 native=Native(dll);errors=[];checks=0
 for q in (1.05,1.4,2.,3.):
  for px,py,s in ((1.5,1.5,.02),(0,1.5,.02),(-.5,1.5,.1),(100,100,.02)):
   def cuts(c):return sorted({0.,3.,*[x for x in (c-s,c,c+s) if 0<x<3]})
   cx,cy=cuts(px),cuts(py)
   def f(x):return sum(quad(lambda y:math.exp(-q*math.log1p(((x-px)**2+(y-py)**2)/s**2)),a,b,epsabs=1e-30,epsrel=2e-10)[0] for a,b in zip(cy[:-1],cy[1:]))
   expected=sum(quad(f,a,b,epsabs=1e-30,epsrel=2e-10)[0] for a,b in zip(cx[:-1],cx[1:]));got=float(native.mass([0,3,0,3],[px,py],s,q));err=abs(got-expected)/expected;need(err<=2e-8,'POLAR_MASS_FIXTURE');errors.append(err);checks+=1
   expected_line=quad(lambda y:(1+((1.2-px)**2+(y-py)**2)/s**2)**-q,0,3,points=[x for x in (py-s,py,py+s) if 0<x<3],epsabs=1e-30,epsrel=2e-10)[0];got_line=float(native.line(-py,3-py,1.2-px,s,q));need(abs(got_line-expected_line)<=2e-8*expected_line,'INDEPENDENT_LINE_FIXTURE');checks+=1
 # Exact no-history/no-trigger count, mark and exposure identities on invented rows.
 state={'params':np.array([-2,0,0,.1,1.3,.4,.6,1,10,0,2,2]),'training_xy':np.array([[.5,.5],[2.5,2.5]]),'prehistory':np.empty((0,4)),'rectangles':np.array([[x,x+1,y,y+1] for y in range(3) for x in range(3)]),'pi':np.ones(9)/9}
 obj=native.state(state,'EP')
 try:
  o=obj.evaluate(np.array([[.5,.1,1.2,1.7],[1.5,.4,2.1,.7]]));need(o[0]==2 and abs(o[1]-.5)<1e-14 and abs(o[2]-2*math.exp(-2))<1e-14 and o[3]==0 and abs(o[6]+.5)<1e-14,'EMPTY_HISTORY_IDENTITIES');checks+=1
 finally:obj.close()
 return dict(passed=True,checks=checks,maximum_relative_mass_error=max(errors),scope='independent polar/line quadrature and empty-history fixtures; no scientific path validation')
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['fixtures','pilot','all']);p.add_argument('--dll',required=True);p.add_argument('--dll-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--workers',type=int,default=6);a=p.parse_args();need(sha(a.dll)==a.dll_sha256,'AUDITOR_BINARY_PIN');out=Path(a.output);need(not out.exists(),'APPEND_ONLY');start=time.perf_counter()
 if a.mode=='fixtures':result=fixtures(a.dll)
 else:
  tasks=[(a.dll,m,f'california_fold_{i}',a.mode=='pilot',str(out.with_suffix('.private'))) for m in ('OC','EP') for i in range(3)]
  with ProcessPoolExecutor(max_workers=a.workers) as pool:rows=list(pool.map(audit_origin,tasks))
  result=dict(status='passed' if all(x['complete']==x['planned'] for x in rows) else 'incomplete',rows=rows,planned_paths=6 if a.mode=='pilot' else 5994,complete_paths=sum(x['complete'] for x in rows),full_84_replays=0,scope='Tier1 independent raw count/mark/exposure/event-log sums, not full spatial/PIT replay')
 result.update(auditor_source_sha256=sha(__file__),native_source_sha256=sha(HERE/'independent_point_oracle_v2.cpp'),native_binary_sha256=sha(a.dll),wall_seconds=time.perf_counter()-start);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
