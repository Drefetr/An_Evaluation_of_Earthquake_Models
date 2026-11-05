"""Independent saved-path closure. No producer imports, simulations or fitting."""
import os
for _k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[_k]='1'
import argparse,ctypes as C,hashlib,json,math,time,sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import native_wrapper as nw
import original_full84 as original
HERE=Path(__file__).resolve().parent
ORIGINS=tuple(f'california_fold_{i}' for i in range(3));INDICES=(0,249,499,749,998)
_native=None;_handles={};_dll=None;_mass_cache={};_mass_cache_bytes=0;_states={}
def need(x,s):
 if not x:raise ValueError(s)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sourcepins():return {n:sha(HERE/n) for n in ['replay.py','original_full84.py','native_wrapper.py','independent.cpp','temporal_extension.cpp']}
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def native():
 global _native
 if _native is None:
  _native=nw.Native(_dll);_native.lib.q01_temporal.argtypes=[C.c_void_p,C.c_int,nw.D,nw.D];_native.lib.q01_temporal.restype=C.c_int
 return _native
def init(dll):
 global _dll
 _dll=dll
def accelerated_mass(bounds,centers,scale,*,q=2.,verify=False):
 # A bounded independent in-process memo, keyed by exact input bytes; never
 # loads producer geometry/cache. Used only for invariant <=9-cell queries.
 global _mass_cache_bytes
 b,c=np.asarray(bounds,dtype=float),np.asarray(centers,dtype=float)
 cacheable=b.shape[-2:-1]==(9,) and b.size+c.size<200000
 key=hashlib.sha256(b.tobytes()+c.tobytes()+np.asarray([scale,q]).tobytes()+str((b.shape,c.shape)).encode()).digest() if cacheable else None
 if key in _mass_cache:return _mass_cache[key].copy()
 value=native().mass(b,c,float(scale),float(q))
 need(np.isfinite(value).all() and np.all(value>=0),'independent mass finite/nonnegative')
 if verify:
  expected=original._adaptive_mass_one
  shape=np.broadcast_shapes(b.shape[:-1],c.shape[:-1]);bb=np.broadcast_to(b,shape+(4,)).reshape(-1,4);cc=np.broadcast_to(c,shape+(2,)).reshape(-1,2)
  for k,v in enumerate(value.ravel()):
   exact=expected(bb[k],cc[k],scale,q)
   need(abs(v-exact)<=2e-8*abs(exact)+1e-14*scale*scale,'compiled/pure adaptive mass control')
 if cacheable and value.nbytes<=64*1024**2:
  if _mass_cache_bytes+value.nbytes>64*1024**2:_mass_cache.clear();_mass_cache_bytes=0
  _mass_cache[key]=value.copy();_mass_cache_bytes+=value.nbytes
 return value
def flatten(d):
 names=[];values=[]
 for k in sorted(d):
  a=np.asarray(d[k]);need(a.ndim<=1,'scalar vector');names.extend([k] if a.ndim==0 else [f'{k}[{i}]' for i in range(len(a))]);values.extend(a.ravel())
 return names,np.asarray(values,float)
def controls(dll,output):
 init(dll);begin=time.perf_counter();rows=[];pure=original.rectangle_mass
 for q in (1.05,1.4,2.,3.):
  state=dict(params=np.array([-2,.1,.2,.1,1.3,.4,.6,1,10,0,2,q]),rectangles=np.array([[x,x+1,y,y+1] for y in range(3) for x in range(3)],float),pi=np.ones(9)/9,training_xy=np.array([[.5,.5],[2.5,2.5]]),prehistory=np.array([[-1,.2,1.5,1.5]]),subblocks=np.linspace(0,2,6));events=np.array([[.5,.1,1.2,1.7],[1.5,.4,2.1,.7]])
  original.rectangle_mass=pure;a,ad=original.evaluate(state,events,batch_size=2)
  original.rectangle_mass=accelerated_mass
  try:b,bd=original.evaluate(state,events,batch_size=2)
  finally:original.rectangle_mass=pure
  na,va=flatten(a);nb,vb=flatten(b);need(na==nb and len(va)==84 and np.isfinite(vb).all(),'84 control schema');ve=float(np.max(abs(va-vb)));de=float(np.max(abs(ad-bd)));need(ve<=1e-7 and de<=1e-7,'full84 substitution equivalence')
  obj=native().state(state,'EP')
  try:
   ev=nw.array(events);v=np.empty(7);native().checked(native().lib.q01_temporal(obj.handle,len(ev),nw.ptr(ev),nw.ptr(v)))
   ref=[a['count'],events[:,1].sum(),a['immigrant_exposure'],a['trigger_exposure'],a['time_event_logsum'],a['mark_logscore'],a['timing_logscore']];te=float(np.max(abs(v-ref)));need(te<=1e-7,'temporal independent control')
  finally:obj.close()
  rows.append(dict(q=q,vector_error=ve,detail_error=de,temporal_error=te))
 # Duplicate times enforce strict-past: compare native temporal to original
 # orchestration at equal timestamps, rather than assuming previous-row past.
 events[1,0]=events[0,0];a,_=original.evaluate(state,events,batch_size=2);obj=native().state(state,'EP')
 try:
  ev=nw.array(events);v=np.empty(7);native().checked(native().lib.q01_temporal(obj.handle,2,nw.ptr(ev),nw.ptr(v)));need(abs(v[4]-a['time_event_logsum'])<=1e-7,'strictpast duplicate control')
 finally:obj.close()
 write(output,dict(passed=True,rows=rows,duplicate_timestamp_strictpast=True,dll_sha256=sha(dll),source_sha256=sha(__file__),source_pins=sourcepins(),wall_seconds=time.perf_counter()-begin,scope='Handcrafted independent geometry-substitution/full84 and raw temporal equivalence; not real saved-path acceptance'))
def manifest(path):
 d=read(path);need(d['passed'] is True and d['simulated_paths']==5994 and d['observed_vectors']==6,'terminal saved manifest')
 need(len(d['rows'])==6000 and {(x['model'],x['origin'],x['index']) for x in d['rows']}=={(m,o,i) for m in ('OC','EP') for o in ORIGINS for i in [-1,*range(999)]},'exact6000 roster')
 return d
def inputs(r,full84):
 base=Path(r['scalars']).parent;state=Path(r['state']);key=(str(state),r['state_sha256'])
 if key not in _states:
  need(sha(state)==r['state_sha256'],'state custody');_states[key]=nw.load_state(state)
 names=['receipt.json','scalars.json','private_path.npz']+(['private_detail.npz'] if full84 else [])
 for name in names:
  p=(base/name).resolve();need(sha(p)==r['artifacts'][str(p)],'artifact custody '+name)
 rec=read(base/'receipt.json');need(rec['status']=='complete' and rec['case_id']==r['origin'] and rec['index']==r['index'] and rec['mode']=='simulate' and rec['phase']=='production','terminal identity')
 need(rec['seed_records']==nw.expected_seed(r['model'],r['origin'],r['index']),'seed custody')
 with np.load(base/'private_path.npz',allow_pickle=False) as f:events=nw.array(f['events'])
 state_data=_states[key];need('observed' not in state_data,'no observed future in simulation state')
 return base,state_data,events,read(base/'scalars.json')['stats']
def one(task):
 r,scope=task;begin=time.perf_counter();identity=dict(model=r['model'],origin=r['origin'],index=r['index'],scope=scope)
 try:
  base,state,events,stats=inputs(r,scope=='full84')
  if scope=='full84':
   original.rectangle_mass=accelerated_mass;expected,detail=original.evaluate(state,events,batch_size=16)
   names,x=flatten(expected);other,y=flatten(stats);need(names==other and len(x)==84 and np.isfinite(x).all() and np.isfinite(y).all(),'full84 schema/finite')
   with np.load(base/'private_detail.npz',allow_pickle=False) as f:saved=f['detail'].copy()
   need(detail.shape==saved.shape and np.isfinite(saved).all(),'detail shape finite');delta=abs(x-y);scores=np.array(['logscore' in n or n=='time_event_logsum' for n in names]);scoremax=float(np.max(delta[scores],initial=0));othermax=float(np.max(delta[~scores],initial=0));cdf=float(np.max(abs(detail[:,2:4]-saved[:,2:4]),initial=0));logs=float(np.max(abs(detail[:,4:]-saved[:,4:]),initial=0));gaps=float(np.max(abs(detail[:,:2]-saved[:,:2]),initial=0))
   need(scoremax<=1e-4 and othermax<=1e-7 and cdf<=1e-8 and logs<=1e-4 and gaps<=1e-7,'full84 discrepancy')
   need(all(delta[i]==0 for i,n in enumerate(names) if n=='count' or n.startswith(('year_count[','cell_count['))),'exact allcounts')
   metrics=dict(coordinates=84,score_error=scoremax,other_error=othermax,cdf_error=cdf,event_log_error=logs,gap_error=gaps)
  else:
   key=(r['model'],r['state_sha256'])
   if key not in _handles:_handles[key]=native().state(state,r['model'])
   obj=_handles[key]
   if scope=='temporal':
    v=np.empty(7);native().checked(native().lib.q01_temporal(obj.handle,len(events),nw.ptr(events),nw.ptr(v)))
    expected=dict(count=v[0],immigrant_exposure=v[2],trigger_exposure=v[3],exposure=v[2]+v[3],time_event_logsum=v[4],mark_logscore=v[5],timing_logscore=v[6]);marksum=v[1]
   else:
    v=obj.evaluate(events);E=v[2]+v[3];expected=dict(count=v[0],immigrant_exposure=v[2],trigger_exposure=v[3],exposure=E,time_event_logsum=v[4],timing_logscore=v[4]-E,location_logscore=v[5]-v[4],mark_logscore=v[6],joint_logscore=v[7]);marksum=v[1]
   need(np.isfinite(list(expected.values())).all(),'raw finite outputs');errors={k:abs(float(stats[k])-float(x)) for k,x in expected.items()};need(all(math.isfinite(v) for v in errors.values()) and errors['count']==0 and max(errors.values())<=1e-4,'raw score discrepancy');need(abs(float(events[:,1].sum())-marksum)<=1e-10*max(1,abs(marksum)),'raw marksum')
   metrics=dict(recomputed_fields=list(expected),max_error=max(errors.values()),point_and_joint_recomputed=scope=='point')
  # Verify all artifacts actually read remained unchanged during evaluation.
  for name in ['receipt.json','scalars.json','private_path.npz']+(['private_detail.npz'] if scope=='full84' else []):
   path=(base/name).resolve();need(sha(path)==r['artifacts'][str(path)],'artifact drift after evaluation')
  return dict(**identity,passed=True,metrics=metrics,receipt_sha256=r['artifacts'][str((base/'receipt.json').resolve())],seconds=time.perf_counter()-begin)
 except Exception as e:return dict(**identity,passed=False,error=type(e).__name__+': '+str(e),seconds=time.perf_counter()-begin)
def run(a):
 need(os.environ.get('NUMERICAL_LEASE_TOKEN'),'shared root lease token required');d=manifest(a.manifest);control=read(a.controls);need(control['passed'] is True and control['dll_sha256']==sha(a.dll) and control['source_sha256']==sha(__file__) and control['source_pins']==sourcepins(),'controls pin')
 roster=[r for r in d['rows'] if r['index']>=0 and (a.scope!='full84' or (r['model']=='EP' and r['index'] in INDICES)) and (not a.pilot or r['index']==0)]
 expected=(3 if a.pilot else 15) if a.scope=='full84' else (6 if a.pilot else 5994);need(len(roster)==expected,'scope roster')
 output=Path(a.output);output.mkdir(parents=True,exist_ok=True);journal=output/'progress.jsonl';binding=dict(manifest_sha256=sha(a.manifest),dll_sha256=sha(a.dll),adapter_sha256=sha(__file__),source_pins=sourcepins(),scope=a.scope,pilot=a.pilot,planned=expected)
 if (output/'binding.json').exists():need(read(output/'binding.json')==binding,'resume exact binding')
 else:write(output/'binding.json',binding)
 prior=[json.loads(l) for l in journal.read_text().splitlines() if l.strip()] if journal.exists() else [];ids=lambda r:(r['model'],r['origin'],r['index'])
 if a.reuse and not journal.exists():
  reuse=read(Path(a.reuse)/'report.json');need(reuse['passed'] is True and not a.pilot and reuse['binding']['pilot'] is True,'reuse accepted pilot only')
  need(all(reuse['binding'][k]==binding[k] for k in ['manifest_sha256','dll_sha256','adapter_sha256','source_pins','scope']),'pilot same exact implementation/inputs/scope')
  prior=reuse['rows'];need(len(prior)==(3 if a.scope=='full84' else 6),'complete pilot reuse')
  with journal.open('x',encoding='utf-8') as f:
   for row in prior:f.write(json.dumps(row,allow_nan=False)+'\n')
  write(output/'pilot_reuse.json',dict(report_sha256=sha(Path(a.reuse)/'report.json'),rows=len(prior)))
 done={ids(r):r for r in prior};need(len(done)==len(prior) and all(r['passed'] for r in prior),'failed/duplicate rows require explicit review, not automatic replay')
 need(set(done)<={ids(r) for r in roster},'resume roster');pending=[(r,a.scope) for r in roster if ids(r) not in done];start=time.perf_counter()
 with ProcessPoolExecutor(max_workers=a.workers,initializer=init,initargs=(str(Path(a.dll).resolve()),)) as pool:
  futures=[pool.submit(one,t) for t in pending]
  with journal.open('a',encoding='utf-8') as f:
   for future in as_completed(futures):
    row=future.result();f.write(json.dumps(row,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno());done[ids(row)]=row
 need(sha(a.manifest)==binding['manifest_sha256'] and sha(a.dll)==binding['dll_sha256'] and sourcepins()==binding['source_pins'],'input implementation drift')
 for state,digest in {(r['state'],r['state_sha256']) for r in roster}:need(sha(state)==digest,'state drift after replay')
 rows=sorted(done.values(),key=lambda r:ids(r));passed=len(rows)==expected and all(r['passed'] for r in rows);write(output/'report.json',dict(passed=passed,binding=binding,complete=len(rows),failed=sum(not r['passed'] for r in rows),session_seconds=time.perf_counter()-start,rows=rows,scope_note='Independent raw temporal count/marks/exposure/time-event log recomputation; no spatial point/joint or84 assertion' if a.scope=='temporal' else 'Independent raw spatial point/joint plus temporal scores' if a.scope=='point' else 'All84 coordinates and all11 event-detail columns on15 predeclared EP paths; compiled independent geometry with original Python orchestration'))
 print(json.dumps(dict(passed=passed,complete=len(rows),planned=expected,session_seconds=time.perf_counter()-start)))
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True);c=sub.add_parser('controls');c.add_argument('--dll',required=True);c.add_argument('--output',required=True);a=sub.add_parser('run');a.add_argument('--scope',choices=['temporal','point','full84'],required=True);a.add_argument('--manifest',required=True);a.add_argument('--dll',required=True);a.add_argument('--controls',required=True);a.add_argument('--output',required=True);a.add_argument('--workers',type=int,choices=range(1,9),default=6);a.add_argument('--pilot',action='store_true');a.add_argument('--reuse');v=p.parse_args()
 if v.command=='controls':controls(v.dll,v.output)
 else:run(v)
if __name__=='__main__':main()
