"""Refine quadrature at frozen solver states; never generate or refit."""
import argparse,hashlib,importlib,json,math,os,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np

MODES=[('LI',0,0),('LIplus_immigrant',1,0),('LIplus_inclusive',1,1)]
KEYS=['parents','events','space','times','weights','meta']
DEFAULT_CHUNK_BYTES=5*1024**3
MAX_CHUNK_BYTES=6*1024**3

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def canonical_digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def grid_digest(data):
 h=hashlib.sha256()
 for key in KEYS:
  array=np.ascontiguousarray(data[key]);h.update(key.encode());h.update(str(array.dtype).encode());h.update(str(array.shape).encode());h.update(array.tobytes())
 return h.hexdigest()
def check_deadline(deadline):
 if time.monotonic()>deadline:raise TimeoutError('refinement soft budget exhausted')

def predicted_chunk_bytes(data):
 np_=len(data['parents']);ne=len(data['events']);ns=len(data['space']);nt=len(data['times'])
 return 8*(9*np_+10*ne+5*nt+nt*np_+ns*(9+2*np_+2*nt))+4*(nt+1)

def chunks(data,budget=DEFAULT_CHUNK_BYTES):
 """Exact native CUDA allocation admission; no spatial approximation."""
 if not 0<budget<=MAX_CHUNK_BYTES:raise ValueError('chunk target must be positive and <=6GiB')
 np_=len(data['parents']);nt=len(data['times']);ne=len(data['events'])
 shared=8*(9*np_+10*ne+5*nt+nt*np_)+4*(nt+1)
 perrow=8*(9+2*np_+2*nt)
 rows=(budget-shared)//max(1,perrow)
 if rows<1:raise MemoryError('shared temporal arrays exceed chunk admission')
 for start in range(0,len(data['space']),rows):
  item=dict(data);item['space']=np.ascontiguousarray(data['space'][start:start+rows]);item['meta']=data['meta'].copy()
  if start:item['events']=np.empty((0,6),dtype=np.float64);item['meta'][6:8]=0.
  yield start,item

def evaluate_chunks(native,data,states,out,phase,deadline,budget=DEFAULT_CHUNK_BYTES,workers=1):
 total={name:np.zeros((len(states[name]),6)) for name,_,_ in MODES};receipts=[]
 for ordinal,(start,item) in enumerate(chunks(data,budget)):
  check_deadline(deadline);path=out/(phase+'_chunk_'+str(ordinal)+'.npz');np.savez(path,**item)
  handle=native.create(item)
  if not handle:raise RuntimeError(native.lib.m02_integrated_error().decode())
  try:
   jobs=[(name,plus,inclusive,index,state) for name,plus,inclusive in MODES for index,state in enumerate(states[name])]
   def evaluate(job):
    name,plus,inclusive,index,state=job;check_deadline(deadline);code,value=native.call(handle,state['pars'],plus,inclusive)
    if code or not np.isfinite(value).all():raise ArithmeticError('chunk evaluation failed')
    return name,index,value
   if workers>1:
    with ThreadPoolExecutor(max_workers=workers) as pool:
     for name,index,value in pool.map(evaluate,jobs):total[name][index]+=value
   else:
    for job in jobs:
     name,index,value=evaluate(job);total[name][index]+=value
  finally:native.lib.m02_free(handle)
  receipts.append(dict(path=path.name,sha256=sha(path),space_start=int(start),counts=[len(item[k]) for k in KEYS[:4]],predicted_chunk_bytes=int(predicted_chunk_bytes(item))))
 return {k:v.tolist() for k,v in total.items()},receipts

def construct(c,a,m,pars,order):
 """Exact frozen Integrated constructor inputs, without its full native allocation."""
 plan_a=dict(rectangles=a['rectangles'],reference_pi=a['reference_pi'],kde_xy=a['kde_training_xy'],kde_weight=a['kde_weight'],kde_normalizer=a['kde_normalizers'],parent_xy=a['parent_xy'])
 plans,info=c._adaptive_area_space(plan_a,dict(bg_floor=m['bg_floor'],kde_h=m['kde_h']),[order],1e-8,20)
 plan=plans[order];xy=plan['space_xy'];b,cells=c.background(xy,a,m);areaweight=plan['space_weight']/b
 space=np.ascontiguousarray(np.column_stack([xy,areaweight,b,a['reference_pi'][cells]/a['cell_areas'][cells]]))
 times,weights=c.time_plan(a['parent_time'],m['start'],m['end'],np.exp(pars[3]),2*order)
 f=c.S.features(a,m,pars[3:5]);baseline=c.S.evaluate(f,pars[:3])[0]
 parents=np.ascontiguousarray(np.column_stack([a['parent_time'],a['parent_xy'],a['parent_excess'],a['parent_fertility'],a['parent_normalizer']]))
 events=np.ascontiguousarray(np.column_stack([a['event_time'],a['event_xy'],a['event_background_density'],pars[2]*f['hp'],a['reference_pi'][a['event_cell'].astype(int)]/a['cell_areas'][a['event_cell'].astype(int)]]))
 meta=np.array([*pars[:3],np.exp(pars[3]),pars[4],m['T0'],baseline['compensator'],f['marks'],m['sigma']])
 return dict(parents=parents,events=events,space=space,times=times,weights=weights,meta=meta)

def compare_inputs(new,old):
 rows={k:dict(shape_equal=new[k].shape==old[k].shape,exact=bool(np.array_equal(new[k],old[k])),allclose=bool(new[k].shape==old[k].shape and np.allclose(new[k],old[k],rtol=1e-13,atol=1e-14))) for k in KEYS}
 return dict(passed=all(v['allclose'] for v in rows.values()),arrays=rows)

def selection_report(states,fits,cache,oldcoarse,ntrain,ntest):
 rows=[];diagnostics=[];drift_pass=selection_pass=bic_pass=spread_pass=complete=True
 for name,_,_ in MODES:
  fit=fits[name];lookup={tuple(s['pars']):i for i,s in enumerate(states[name])};sel=lookup[tuple(fit['selected']['pars'])];floor=lookup[tuple(fit['floor'])]
  train=np.array(cache['train'][name])[:,0];test=np.array(cache['test'][name])[:,0];old=np.array(oldcoarse[name])[:,0]
  deltas=np.abs(train-old);drift_pass &= bool(np.all(deltas<=1e-4))
  eligible=[r for r in fit['records'] if r.get('success') and r.get('finite_feasible')]+[dict(start=-1,pars=fit['floor'])]
  # Same floor-first and start tie-breaking as frozen fit().
  winner=min(eligible,key=lambda r:(train[lookup[tuple(r['pars'])]],r['start']>=0,r['start']))
  winner_index=lookup[tuple(winner['pars'])];selection_pass &= winner_index==sel
  threshold=1.5*math.log(max(ntrain,1));old_bic=fit['floor_nll']-fit['selected']['nll']>threshold;new_bic=train[floor]-train[sel]>threshold;bic_pass &= bool(old_bic==new_bic)
  near=np.flatnonzero(train<=train[sel]+4e-4);width=float(np.ptp(test[near])/max(ntest,1));spread_pass &= width<.01
  starts_complete=fit['status']=='complete' and {r['start'] for r in eligible if r['start']>=0}==set(range(8));complete &= starts_complete
  diagnostics.append(dict(model=name,all_state_train_nll_max_drift=float(max(deltas)),selected_state_index=sel,refined_winner_index=winner_index,bic_stable=bool(old_bic==new_bic),near_spread_per_event=width,complete_starts=bool(starts_complete)))
  for gate in ['raw'] if name=='LI' else ['raw','BIC']:
   index=sel if gate=='raw' or new_bic else floor;gain=float(test[floor]-test[index]);rows.append(dict(model=name,gate=gate,status='complete' if starts_complete else 'unknown_starts',gain=gain,win=gain>0,n_train=ntrain,n_test=ntest,off_floor=states[name][index]['pars'][0]>0,near_optimal_spread_per_event=width,selected_state_index=index))
 return dict(train_drift_gate=bool(drift_pass),selection_gate=bool(selection_pass),bic_gate=bool(bic_pass),spread_gate=bool(spread_pass),complete_starts_gate=bool(complete),models=diagnostics,results=rows)

def main(argv=None):
 p=argparse.ArgumentParser()
 for key in ['case-dir','output','base','lease-token']:p.add_argument('--'+key,required=True)
 p.add_argument('--seed',type=int,required=True);p.add_argument('--regime',type=int,required=True,choices=range(4));p.add_argument('--backend',choices=['gpu','cpu'],required=True);p.add_argument('--verify-chunking',action='store_true');p.add_argument('--budget-seconds',type=float,default=895);p.add_argument('--chunk-bytes',type=int,default=DEFAULT_CHUNK_BYTES);args=p.parse_args(argv)
 if not 0<args.budget_seconds<=(1700 if args.backend=='cpu' else 895):p.error('budget must be positive and <=1700 CPU or <=895 GPU')
 if not 0<args.chunk_bytes<=MAX_CHUNK_BYTES:p.error('chunk target must be positive and <=6GiB')
 if os.environ.get('NUMERICAL_LEASE_TOKEN')!=args.lease_token:raise RuntimeError('numerical lease token missing')
 root=Path(args.case_dir).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);base=Path(args.base).resolve();deadline=time.monotonic()+args.budget_seconds
 report=dict(status='running',passed=False,seed=args.seed,regime=args.regime,backend=args.backend,phases=[],verify_chunking=args.verify_chunking,input_digests={},chunking_validation_passed=False,budget_seconds=args.budget_seconds,chunk_target_bytes=args.chunk_bytes,chunk_hard_max_bytes=MAX_CHUNK_BYTES,max_predicted_chunk_bytes=0,scope='frozen candidate-state quadrature validation; no order32 optimization or new draws')
 try:
  source=base/'scientific_pilot/source';sys.path.insert(0,str(source));c=importlib.import_module('controls_campaign')
  if Path(c.__file__).resolve()!=source/'controls_campaign.py':raise ImportError('frozen source origin')
  sys.path.insert(0,'/home/gpt/production_audit_policy_20261030T122335Z');Native=importlib.import_module('run_oracle').Native
  dll=base/('cuda_engine/libm02_cuda.so' if args.backend=='gpu' else 'cuda_engine/libm02_cpu.so');native=Native(dll)
  aggregate=read(root/'aggregate.json')
  if (aggregate['seed'],aggregate['regime'])!=(args.seed,args.regime):raise ValueError('case identity mismatch')
  generated=root/'generated_private.npz';report['generated_archive_sha256']=sha(generated)
  with np.load(generated,allow_pickle=False) as z:rows=np.ascontiguousarray(z['rows'])
  report['generated_rows_sha256']=hashlib.sha256(rows.tobytes()).hexdigest()
  names=['S0_uniform_null','S1_smooth_null','S2_narrow_short','S3_broad_long'];name=names[args.regime];_,bg,eta,ell,psi=c.G.ROSTER[name];law=c.G.Law(name,args.seed,bg,eta,ell,psi);gm=c.G.fitting_metadata(law);pars=[law.a,law.d,law.n,np.log(law.c),law.p]
  fits={name:read(root/(name+'_fit_private.json')) for name,_,_ in MODES};oldtrain=read(root/'fine_train_evaluations_private.json');states=oldtrain['states'];cache={};convergence=True
  report['states_digest']=canonical_digest(states);report['original_pins']={x.name:sha(x) for x in sorted(root.iterdir()) if x.is_file()};report['original_digest']=canonical_digest(report['original_pins'])
  captures={x['phase']:x for x in read(root/'phase_progress.json')['phases']};geometry=c.S.Geometry(str(base/'scientific_pilot/libradial.so'))
  for phase,start,end in [('train',30,395),('test',395,760)]:
   check_deadline(deadline);m=dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h'] or 10)
   a=c.canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],np.asarray(gm['rectangles']),np.asarray(gm['reference_pi']),np.asarray(gm['kde_xy']).reshape(-1,2),np.asarray(gm['kde_weight']),m,pars,geometry)
   oldvalues=read(root/('fine_'+phase+'_evaluations_private.json'))
   if oldvalues['states']!=states:raise ValueError('state identity mismatch')
   capture=root/captures['fine_'+phase]['path']
   if sha(capture)!=captures['fine_'+phase]['sha256']:raise ValueError('saved input hash mismatch')
   with np.load(capture,allow_pickle=False) as z:old={k:np.ascontiguousarray(z['arg_'+str(i)]) for i,k in enumerate(KEYS,4)}
   data16=construct(c,a,m,pars,16);equivalence=compare_inputs(data16,old)
   if not equivalence['passed']:raise ValueError('order16 reconstruction mismatch')
   entry=dict(phase=phase,order16_input_equivalence=equivalence,original_capture_sha256=sha(capture))
   if args.verify_chunking:
    v16,ch16=evaluate_chunks(native,data16,states,out,'order16_'+phase,deadline,budget=args.chunk_bytes,workers=3 if args.backend=='cpu' else 1);delta=max(float(np.max(np.abs(np.array(v16[n])-oldvalues['evaluations'][n]))) for n,_,_ in MODES);entry.update(chunk16_max_all_output_delta=delta,chunk16_passed=delta<=1e-8,order16_chunks=ch16);report['max_predicted_chunk_bytes']=max(report['max_predicted_chunk_bytes'],max(x['predicted_chunk_bytes'] for x in ch16))
    if delta>1e-8:raise ValueError('order16 chunk aggregation mismatch')
   del data16,old
   data32=construct(c,a,m,pars,32);report['input_digests'][phase]=grid_digest(data32);values,ch32=evaluate_chunks(native,data32,states,out,'order32_'+phase,deadline,budget=args.chunk_bytes,workers=3 if args.backend=='cpu' else 1);cache[phase]=values;report['max_predicted_chunk_bytes']=max(report['max_predicted_chunk_bytes'],max(x['predicted_chunk_bytes'] for x in ch32))
   delta=max(float(np.max(np.abs(np.array(values[n])[:,0]-np.array(oldvalues['evaluations'][n])[:,0]))) for n,_,_ in MODES);convergence &= delta<=1e-4
   entry.update(order32_chunks=ch32,max_order16_32_nll_delta=delta,converged=delta<=1e-4);report['phases'].append(entry);write(out/('order32_'+phase+'_evaluations_private.json'),dict(states=states,evaluations=values));write(out/'report.json',report)
   if phase=='train':ntrain=len(data32['events'])
   else:ntest=len(data32['events'])
   del data32,a
  coarse=read(root/'coarse_train_evaluations_private.json')
  if coarse['states']!=states:raise ValueError('coarse state identity mismatch')
  gates=selection_report(states,fits,cache,coarse['evaluations'],ntrain,ntest);report.update(gates);report['quadrature_gate']=bool(convergence)
  stable=all(gates[k] for k in ['train_drift_gate','selection_gate','bic_gate','spread_gate','complete_starts_gate']);report['passed']=bool(convergence and stable);report['status']='converged' if report['passed'] else ('unresolved' if not convergence else 'refit_required');report['phase_values']=cache;report['chunking_validation_passed']=bool(args.verify_chunking and all(x.get('chunk16_passed',False) for x in report['phases']))
  report['source_pins']={str(x):sha(x) for x in [Path(__file__),dll,base/'scientific_pilot/libradial.so',*sorted(source.glob('*.py')),Path('/home/gpt/production_audit_policy_20261030T122335Z/run_oracle.py')]};report['saved_case_pins']={str(x.name):sha(x) for x in root.glob('*.json')};report['state_values_paths']=['order32_train_evaluations_private.json','order32_test_evaluations_private.json']
 except BaseException as exc:report.update(status='failed',error_type=type(exc).__name__,error=str(exc));raise
 finally:write(out/'report.json',report)
 if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
