"""Persistent order16 refits and independent compiled replay of saved new states."""
import argparse,hashlib,importlib,importlib.util,json,math,os,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

REFINER=Path(__file__).with_name('refine_worker.py')
AUDIT=Path('/home/gpt/production_audit_policy_20261030T122335Z')
MODES=[('LI',0,0),('LIplus_immigrant',1,0),('LIplus_inclusive',1,1)]
KEYS=['parents','events','space','times','weights','meta']
TARGET=5*1024**3
PHASES={'order16_train','order16_test','order32_train','order32_test'}
SCORE_KEYS={('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')}
GATE_KEYS=['quadrature_gate','selection_gate','bic_gate','spread_gate','complete_starts_gate','training_replay_gate','training_selection_gate']
class ResourceNeed(RuntimeError):pass

def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):h.update(block)
 return h.hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load_refiner():
 spec=importlib.util.spec_from_file_location('immutable_refiner',REFINER);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def load_capture(root,phase):
 captures={x['phase']:x for x in read(root/'phase_progress.json')['phases']};capture=captures[phase];path=root/capture['path']
 if sha(path)!=capture['sha256']:raise ValueError('capture changed')
 with np.load(path,allow_pickle=False) as z:data={k:np.ascontiguousarray(z['arg_'+str(i)]) for i,k in enumerate(KEYS,4)}
 return data

class Persistent:
 def __init__(self,native,data,deadline):
  self.native=native;self.deadline=deadline;self.handle=native.create(data)
  if not self.handle:raise ArithmeticError('native create failed')
 def evaluate(self,p,plus,inclusive):
  if time.monotonic()>self.deadline:raise TimeoutError('refit budget exhausted')
  code,value=self.native.call(self.handle,p,int(plus),int(inclusive))
  if code or not np.isfinite(value).all():raise ArithmeticError('native objective failed')
  return value
 def close(self):
  if self.handle:self.native.lib.m02_free(self.handle);self.handle=None

def run_fits(c,native,data,out,deadline):
 obj=Persistent(native,data,deadline);fits={};states={}
 try:
  for name,plus,inclusive in MODES:
   with (out/(name+'_solver_returns_private.jsonl')).open('x') as stream:
    def checkpoint(record):stream.write(json.dumps(record,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
    fit=c.fit(obj,plus,inclusive,checkpoint)
   fits[name]=fit;write(out/(name+'_fit_private.json'),fit);unique={}
   for record in fit['records']+[r for r in fit['candidates'] if r['start']==-1]:
    if record.get('finite_feasible'):
     key=tuple(map(float,record['pars']));entry=unique.setdefault(key,dict(pars=list(key),returns=[]));entry['returns'].append(dict(start=record['start'],success=record['success'],method=record['method'],training_nll=record['nll']))
   states[name]=list(unique.values())
 finally:obj.close()
 return fits,states

def gates(fits,states,values,ntrain,ntest):
 quadrature=selection=bic=spread=complete=replay=training_selection=True;diagnostics=[];scores=[]
 for name,_,_ in MODES:
  fit=fits[name];lookup={tuple(s['pars']):i for i,s in enumerate(states[name])};sel=lookup[tuple(fit['selected']['pars'])];floor=lookup[tuple(fit['floor'])]
  t16=np.array(values['order16_train'][name])[:,0];t32=np.array(values['order32_train'][name])[:,0];v16=np.array(values['order16_test'][name])[:,0];v32=np.array(values['order32_test'][name])[:,0]
  delta=max(float(np.max(np.abs(t16-t32))),float(np.max(np.abs(v16-v32))));quadrature &= delta<=1e-4
  # Selection is made on order16 training only. Order32 assesses its uncertainty.
  best=float(min(t32));gap=float(t32[sel]-best);selection &= gap<=1e-4
  successful={r['start'] for r in fit['records'] if r.get('success') and r.get('finite_feasible')};done=fit['status']=='complete' and successful==set(range(8));complete &= done
  eligible=[r for r in fit['records'] if r.get('success') and r.get('finite_feasible')]+[dict(start=-1,pars=fit['floor'],nll=fit['floor_nll'])]
  original_winner=min(eligible,key=lambda r:(r['nll'],r['start']>=0,r['start']))
  training_choice=tuple(original_winner['pars'])==tuple(fit['selected']['pars']) and original_winner['nll']==fit['selected']['nll'];training_selection &= training_choice
  training_replay=max((abs(float(t16[lookup[tuple(r['pars'])]])-r['nll']) for r in fit['records'] if r.get('finite_feasible')),default=0.)
  training_replay=max(training_replay,abs(float(t16[floor])-fit['floor_nll']),abs(float(t16[sel])-fit['selected']['nll']));replay &= training_replay<=1e-7
  threshold=1.5*math.log(max(ntrain,1));b16=t16[floor]-t16[sel]>threshold;b32=t32[floor]-t32[sel]>threshold;bic &= bool(b16==b32)
  # Include all retained finite states, including failed solver returns.
  near=np.flatnonzero(t16<=t16[sel]+4e-4);width=float(np.ptp(v32[near])/max(1,ntest));spread &= width<.01
  diagnostics.append(dict(model=name,quadrature_max_nll_delta=delta,selected32_gap_to_best_retained=gap,selection_uncertainty_tolerance=1e-4,order16_exact_original_winner=bool(training_choice),complete_starts=done,bic_stable=bool(b16==b32),near_spread_per_event=width,training_replay_max_delta=training_replay))
  for gate in ['raw'] if name=='LI' else ['raw','BIC']:
   chosen=sel if gate=='raw' or b16 else floor;gain=float(v32[floor]-v32[chosen]);scores.append(dict(model=name,gate=gate,status='complete' if done else 'unknown_starts',gain=gain,win=gain>0,n_train=ntrain,n_test=ntest,off_floor=states[name][chosen]['pars'][0]>0,near_optimal_spread_per_event=width,selected_state_index=chosen))
 passed=bool(quadrature and selection and bic and spread and complete and replay and training_selection)
 return dict(passed=passed,status='converged' if passed else ('fit_incomplete' if not complete else 'refinement_required'),quadrature_gate=bool(quadrature),selection_gate=bool(selection),bic_gate=bool(bic),spread_gate=bool(spread),complete_starts_gate=bool(complete),training_replay_gate=bool(replay),training_selection_gate=bool(training_selection),models=diagnostics,results=scores)

def replay_saved(native,fitdir,phase,states,receipts,deadline):
 total={n:np.zeros((len(states[n]),6)) for n,_,_ in MODES}
 for receipt in receipts:
  path=fitdir/receipt['path']
  if sha(path)!=receipt['sha256']:raise ValueError('audit chunk changed')
  with np.load(path,allow_pickle=False) as z:data={k:np.ascontiguousarray(z[k]) for k in KEYS}
  obj=Persistent(native,data,deadline)
  try:
   jobs=[(n,p,i,j,s) for n,p,i in MODES for j,s in enumerate(states[n])]
   def call(job):
    n,p,i,j,s=job;return n,j,obj.evaluate(s['pars'],p,i)
   with ThreadPoolExecutor(max_workers=3) as pool:
    for n,j,value in pool.map(call,jobs):total[n][j]+=value
  finally:obj.close()
 return {n:v.tolist() for n,v in total.items()}

def compare_audit_values(cpu,gpu,states):
 """Coverage is evidence, including every retained state and every ABI output."""
 names={n for n,_,_ in MODES};rows=[]
 if set(cpu)!=PHASES or set(gpu)!=PHASES or set(states)!=names:raise ValueError('incomplete audit phase/model coverage')
 for phase in sorted(PHASES):
  if set(cpu[phase])!=names or set(gpu[phase])!=names:raise ValueError('incomplete audit model coverage')
  for name in sorted(names):
   a=np.array(cpu[phase][name]);b=np.array(gpu[phase][name]);shape=(len(states[name]),6)
   if not shape[0] or a.shape!=shape or b.shape!=shape:raise ValueError('incomplete audit state/output coverage')
   finite=bool(np.isfinite(a).all() and np.isfinite(b).all());nll=float(np.max(np.abs(a[:,0]-b[:,0]))) if finite else None
   passed=bool(finite and float(np.max(np.abs(a-b)))<=1e-8)
   rows.append(dict(phase=phase,model=name,passed=passed,nll_abs_delta=nll,max_abs_delta=float(np.max(np.abs(a-b))) if finite else None))
 return rows

def compare_scores(cpu,gpu):
 for rows in [cpu,gpu]:
  if len(rows)!=5 or {(x['model'],x['gate']) for x in rows}!=SCORE_KEYS:raise ValueError('incomplete or duplicate audit score coverage')
 a={(x['model'],x['gate']):x for x in cpu};b={(x['model'],x['gate']):x for x in gpu}
 return all(a[k]['win']==b[k]['win'] and a[k]['off_floor']==b[k]['off_floor'] and abs(a[k]['gain']-b[k]['gain'])<=2e-7 for k in SCORE_KEYS)

def verify_fit_pins(fitdir,pins):
 expected={'states.json'}|{n+suffix for n,_,_ in MODES for suffix in ['_fit_private.json','_solver_returns_private.jsonl']}
 if set(pins)!=expected:raise ValueError('incomplete new-fit artifact pins')
 for name,h in pins.items():
  if sha(fitdir/name)!=h:raise ValueError('new-fit artifact changed: '+name)
 for name,_,_ in MODES:
  fit=read(fitdir/(name+'_fit_private.json'));solver=[json.loads(line) for line in (fitdir/(name+'_solver_returns_private.jsonl')).read_text().splitlines() if line.strip()]
  if fit['records']!=solver:raise ValueError('solver checkpoint records mismatch')

def audit_event_counts(fitdir,phases):
 counts={}
 for phase in PHASES:
  receipt=phases[phase][0];path=fitdir/receipt['path']
  if sha(path)!=receipt['sha256']:raise ValueError('audit chunk changed')
  with np.load(path,allow_pickle=False) as z:counts[phase]=len(z['events'])
 if counts['order16_train']!=counts['order32_train'] or counts['order16_test']!=counts['order32_test']:raise ValueError('audit event count mismatch')
 return counts['order16_train'],counts['order16_test']

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['fit','audit'],required=True)
 for key in ['case-dir','output','base','lease-token']:p.add_argument('--'+key,required=True)
 p.add_argument('--seed',type=int,required=True);p.add_argument('--regime',type=int,required=True,choices=range(4,8));p.add_argument('--fit-dir');p.add_argument('--budget-seconds',type=float,default=3500);args=p.parse_args(argv)
 if not 0<args.budget_seconds<=7200:p.error('budget must be positive and <=7200s')
 if args.mode=='audit' and not args.fit_dir:p.error('audit requires --fit-dir')
 if os.environ.get('NUMERICAL_LEASE_TOKEN')!=args.lease_token:raise RuntimeError('numerical lease token missing')
 root=Path(args.case_dir).resolve();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False);base=Path(args.base).resolve();deadline=time.monotonic()+args.budget_seconds
 report=dict(mode=args.mode,status='running',passed=False,seed=args.seed,regime=args.regime,fit_order=16,validation_order=32,chunk_target_bytes=TARGET,scope='same-history order16 eight-start refit; order32 saved-state validation; no test-based fit selection',phases={},phase_values={},input_digests={})
 try:
  r=load_refiner();source=Path(__file__).resolve().parent;sys.path.insert(0,str(source));c=importlib.import_module('controls_campaign')
  if Path(c.__file__).resolve()!=source/'controls_campaign.py':raise ImportError('frozen controls source origin')
  sys.path.insert(0,str(AUDIT));Native=importlib.import_module('run_oracle').Native;dll=base/('cuda_engine/libm02_cuda.so' if args.mode=='fit' else 'cuda_engine/libm02_cpu.so');native=Native(dll)
  report['source_pins']={str(x):sha(x) for x in [Path(__file__),REFINER,AUDIT/'run_oracle.py',dll,base/'scientific_pilot/libradial.so',*sorted(source.glob('*.py'))]};report['original_pins']={x.name:sha(x) for x in (sorted(root.iterdir()) if root.exists() else []) if x.is_file()};report['original_digest']=digest(report['original_pins'])
  if args.mode=='fit':
   root.mkdir(parents=True,exist_ok=False)
   c.generate(args.seed,args.regime,root)
   write(root/'aggregate.json',dict(seed=args.seed,regime=args.regime))
   report['original_pins']={x.name:sha(x) for x in (sorted(root.iterdir()) if root.exists() else []) if x.is_file()};report['original_digest']=digest(report['original_pins'])
  original=read(root/'aggregate.json')
  if (original['seed'],original['regime'])!=(args.seed,args.regime):raise ValueError('original case identity mismatch')
  if args.mode=='fit':
   geometry=c.S.Geometry(str(base/'scientific_pilot/libradial.so'))
   with np.load(root/'generated_private.npz',allow_pickle=False) as z:rows=np.ascontiguousarray(z['rows'])
   report['generated_rows_sha256']=hashlib.sha256(rows.tobytes()).hexdigest();name=c.G.MATCHED_NAMES[args.regime-4];_,bg,eta,ell,psi=c.G.ROSTER[name];law=c.G.Law(name,args.seed,bg,eta,ell,psi);gm=c.G.fitting_metadata(law);pars=[law.a,law.d,law.n,np.log(law.c),law.p]
   def make_data(start,end,order):
    m=dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h'] or 10)
    a=c.canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],np.asarray(gm['rectangles']),np.asarray(gm['reference_pi']),np.asarray(gm['kde_xy']).reshape(-1,2),np.asarray(gm['kde_weight']),m,pars,geometry)
    return r.construct(c,a,m,pars,order)
   data=make_data(30,395,16);predicted=r.predicted_chunk_bytes(data);report['persistent_predicted_bytes']=predicted
   if predicted>TARGET:raise ResourceNeed('order16 train exceeds persistent5GiB target')
   fits,states=run_fits(c,native,data,out,deadline);write(out/'states.json',states);report['states_digest']=digest(states);report['new_fit_pins']={x.name:sha(x) for x in sorted(out.iterdir()) if x.name=='states.json' or x.name.endswith(('_fit_private.json','_solver_returns_private.jsonl'))};report['input_digests']['order16_train']=r.grid_digest(data);del data
   for phase,start,end in [('train',30,395),('test',395,760)]:
    m=dict(start=start,end=end,T0=760,beta=gm['beta'],sigma=gm['sigma_km'],bg_floor=gm['bg_floor'],kde_h=gm['kde_h'] or 10)
    a=c.canonical_arrays(rows[:,0],rows[:,1:3],rows[:,3],np.asarray(gm['rectangles']),np.asarray(gm['reference_pi']),np.asarray(gm['kde_xy']).reshape(-1,2),np.asarray(gm['kde_weight']),m,pars,geometry)
    for order in [16,32]:
     key='order'+str(order)+'_'+phase;data=r.construct(c,a,m,pars,order)
     values,receipts=r.evaluate_chunks(native,data,states,out,key,deadline,budget=TARGET);report['phase_values'][key]=values;report['phases'][key]=receipts;report['input_digests'][key]=r.grid_digest(data)
     if phase=='train':ntrain=len(data['events'])
     else:ntest=len(data['events'])
     write(out/'report.json',report);del data
   report.update(gates(fits,states,report['phase_values'],ntrain,ntest))
   report['next_action']='none' if report['passed'] else 'queue next finer training fit on same history; no redraw'
  else:
   fitdir=Path(args.fit_dir).resolve();gpu=read(fitdir/'report.json');verify_fit_pins(fitdir,gpu['new_fit_pins']);states=read(fitdir/'states.json')
   if (gpu['seed'],gpu['regime'])!=(args.seed,args.regime) or gpu['original_digest']!=report['original_digest'] or gpu['states_digest']!=digest(states):raise ValueError('audit identity binding mismatch')
   for path,h in gpu['source_pins'].items():
    if sha(path)!=h:raise ValueError('fit source binding changed')
   if set(gpu['phases'])!=PHASES or any(not v for v in gpu['phases'].values()):raise ValueError('incomplete saved phase/chunk coverage')
   for phase,receipts in gpu['phases'].items():
    values=replay_saved(native,fitdir,phase,states,receipts,deadline);report['phase_values'][phase]=values
   comparisons=compare_audit_values(report['phase_values'],gpu['phase_values'],states)
   fits={name:read(fitdir/(name+'_fit_private.json')) for name,_,_ in MODES}
   scores=gpu['results'];ntrain,ntest=audit_event_counts(fitdir,gpu['phases'])
   if any(x['n_train']!=ntrain or x['n_test']!=ntest for x in scores):raise ValueError('GPU score count mismatch')
   cpu_gates=gates(fits,states,report['phase_values'],ntrain,ntest);report.update(cpu_gates)
   score_decisions=compare_scores(cpu_gates['results'],scores)
   status_agreement=cpu_gates['status']==gpu['status'];gate_agreement=all(type(cpu_gates[k]) is bool and type(gpu[k]) is bool and cpu_gates[k]==gpu[k] for k in GATE_KEYS)
   computational=bool(all(x['passed'] for x in comparisons) and score_decisions and status_agreement and gate_agreement)
   scientific=bool(cpu_gates['passed'] and gpu['passed']);passed=bool(computational and scientific)
   verify_fit_pins(fitdir,gpu['new_fit_pins'])
   report.update(passed=passed,computational_passed=computational,scientific_passed=scientific,status=cpu_gates['status'] if computational else 'failed',scientific_status_agreement=status_agreement,scientific_gate_agreement=gate_agreement,cpu_scientific_gates=cpu_gates,comparisons=comparisons,score_decisions_passed=score_decisions,states_digest=digest(states),input_digests=gpu['input_digests'],new_fit_pins=gpu['new_fit_pins'],fit_report_sha256=sha(fitdir/'report.json'))
 except ResourceNeed as exc:report.update(status='resource_need',resource_need=str(exc));raise SystemExit(1)
 except BaseException as exc:report.update(status='failed',error_type=type(exc).__name__,error=str(exc));raise
 finally:write(out/'report.json',report)
 if not (report.get('computational_passed',False) if args.mode=='audit' else report['passed']):raise SystemExit(1)

if __name__=='__main__':main()
