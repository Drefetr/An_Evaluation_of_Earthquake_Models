"""Historical Stage2 EP campaign requiring original unshipped states/run plans.
Console emits only aggregate counts/timing; private state/path/detail never printed.
"""
from pathlib import Path
import argparse,hashlib,json,math,time,sys,os
from concurrent.futures import ProcessPoolExecutor
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
if __package__:
 from .ep.adapter import Engine,run_job,sha
else:
 sys.path.insert(0,str(HERE.parents[2]))
 from engine.stage2_followup.s03_s06_spatial_benchmarks.ep.adapter import Engine,run_job,sha
OLD=ROOT/'research_runs/conditional_calibration_20261025T085151Z'
BENCH=ROOT/'research_runs/competitive_benchmarks_20261025T065609Z/results/observed_v2'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False);f.write('\n')

def freeze_write(p,x):
 p=Path(p)
 if p.exists():assert read(p)==x,'FROZEN_RECEIPT_DRIFT'
 else:write(p,x)

def save_state(p,arrays):
 if p.exists():
  with np.load(p,allow_pickle=False) as z:assert set(z.files)==set(arrays) and all(np.array_equal(z[k],arrays[k]) for k in arrays),'STATE_DRIFT'
 else:np.savez_compressed(p,**arrays)

def prepare():
 out=HERE/'binding';out.mkdir(exist_ok=True); rows=[]
 for i in range(3):
  case=f'california_fold_{i}';folder=out/case;folder.mkdir(exist_ok=True)
  old=OLD/'inputs/observed_states_v1'/case/'state.npz';fitpath=BENCH/case/'fit_EP.json';nuispath=BENCH/case/'nuisance.json'
  fit=read(fitpath);nuis=read(nuispath);assert fit['complete'] and fit['model']=='independent_etas'
  with np.load(old,allow_pickle=False) as z:arrays={k:np.array(z[k],copy=True) for k in z.files}
  p=arrays['params'];pars=fit['selected']['pars'];assert len(pars)==7 and len(p)==11
  assert abs(nuis['beta']-p[7])<1e-12 and abs(nuis['kde_selection']['selected_bandwidth']-p[6])<1e-12
  assert np.max(abs(np.array(nuis['reference_pi'])-arrays['pi']))<1e-12
  # Existing EP pars are a,d,n,log(c),p,log(ell),q. All other arrays
  # retain precisely the original conditional forecast information set.
  p=np.r_[p,float(pars[6])];p[:5]=[pars[0],pars[1],pars[2],math.exp(pars[3]),pars[4]];p[5]=math.exp(pars[5]);arrays['params']=p
  obs=folder/'observed_state.npz';save_state(obs,arrays)
  del arrays['observed'];sim=folder/'simulation_state.npz';save_state(sim,arrays)
  row=dict(case_id=case,observed_state=str(obs),simulation_state=str(sim),observed_sha256=sha(obs),simulation_sha256=sha(sim),source_OC_state=str(old),source_OC_sha256=sha(old),fit_EP=str(fitpath),fit_EP_sha256=sha(fitpath),nuisance=str(nuispath),nuisance_sha256=sha(nuispath),score_EP=str(BENCH/case/'score_EP.json'),score_EP_sha256=sha(BENCH/case/'score_EP.json'))
  rows.append(row)
 freeze_write(out/'manifest.json',dict(schema='stage2_EP_binding_v1',cases=rows,binary_sha256=sha(HERE/'ep/ep.dll'),seed_phase='production',pilot_reuse='Production index 0 from each origin is a predeclared cost pilot reused once if successful; never redraw/reseed',denominator=2997))
 return rows

def job(row,index,mode):
 state=row['simulation_state'] if mode=='simulate' else row['observed_state']; path=HERE/'jobs'/row['case_id']/(f'{index}.json' if mode=='simulate' else 'observed.json')
 output=HERE/'results'/row['case_id']/(str(index) if mode=='simulate' else 'observed')
 data=dict(state_npz=state,state_sha256=sha(state),binary=str(HERE/'ep/ep.dll'),binary_sha256=sha(HERE/'ep/ep.dll'),output_dir=str(output),case_id=row['case_id'],phase='production',index=index,mode=mode)
 if not path.exists():write(path,data)
 else:assert read(path)==data,'JOB_DRIFT'
 return path

def execute(path):
 data=read(path);out=Path(data['output_dir']);receipt=out/'receipt.json'
 if receipt.exists():
  result=read(receipt)
  assert result['status']=='complete','PRIOR_FAILURE_REQUIRES_APPEND_ONLY_REPAIR'
  assert result['job_sha256']==sha(path) and result['input_state_sha256']==sha(data['state_npz']) and result['binary_sha256']==sha(data['binary']),'RESUME_IDENTITY'
  for key,name in (('path','private_path.npz'),('scalars','scalars.json'),('detail','private_detail.npz')):assert result[key+'_sha256']==sha(out/name),'RESUME_ARTIFACT'
 else:
  assert not out.exists(),'PARTIAL_OUTPUT_REQUIRES_RECONCILIATION'
  result=run_job(path)
 return dict(status=result['status'],case_id=result['case_id'],index=result['index'],wall_seconds=result['wall_seconds'],cpu_seconds=result['cpu_seconds'])

def pilot():
 rows=prepare();
 if (HERE/'pilot_receipt.json').exists():
  assert read(HERE/'pilot_receipt.json')['status']=='complete';return
 started=time.perf_counter();reports=[]
 for row in rows:
  result=execute(job(row,0,'observed'));assert result['status']=='complete'
  stats=read(HERE/'results'/row['case_id']/'observed/scalars.json')['stats'];score=read(row['score_EP'])['forecast']
  keys={'joint_logscore':'joint_logscore','timing_logscore':'timing_logscore','location_logscore':'conditional_location_logscore','mark_logscore':'mark_logscore','exposure':'integrated_intensity','time_event_logsum':'event_log_ground_intensity_sum'}
  differences={key:abs(stats[key]-score[value]) for key,value in keys.items()};assert max(differences.values())<=1e-4,'EP_ORIGIN_SCORE_RECONCILIATION'
  result=execute(job(row,0,'simulate'));reports.append(dict(**result,origin_score_max_abs_difference=max(differences.values())))
  freeze_write(HERE/f'pilot_progress_{len(reports)}.json',dict(complete=len(reports),planned=3))
 receipt=dict(status='complete',paths=reports,complete=3,planned=3,wall_seconds=time.perf_counter()-started,projected_production_cpu_seconds=sum(r['cpu_seconds'] for r in reports)*999,denominator=2997)
 freeze_write(HERE/'pilot_receipt.json',receipt);print(json.dumps(dict(status='complete',pilot_paths=3,wall_seconds=receipt['wall_seconds'])))

def production(workers):
 manifest=read(HERE/'binding/manifest.json');pilot=read(HERE/'pilot_receipt.json');assert pilot['status']=='complete'
 assert sha(HERE/'ep/ep.dll')==manifest['binary_sha256']
 paths=[]
 for row in manifest['cases']:
  assert sha(row['simulation_state'])==row['simulation_sha256']
  for i in range(1,999):paths.append(str(job(row,i,'simulate')))
 start=time.perf_counter();complete=0;failures=[];cpu=0
 with ProcessPoolExecutor(max_workers=workers) as pool:
  for result in pool.map(execute,paths,chunksize=1):
   complete+=1;cpu+=result['cpu_seconds']
   if result['status']!='complete':failures.append(result)
   if complete%30==0:print(json.dumps(dict(status='running',terminal_paths=complete+3,planned=2997)),flush=True)
 receipt=dict(status='complete' if not failures else 'incomplete',planned=2997,complete=complete+3-len(failures),failed=len(failures),failures=failures,wall_seconds=time.perf_counter()-start,cpu_seconds_excluding_pilot=cpu,workers=workers)
 write(HERE/'production_receipt.json',receipt);print(json.dumps({k:receipt[k] for k in ('status','planned','complete','failed','wall_seconds')}));return 0 if not failures else 1

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['pilot','production']);p.add_argument('--workers',type=int,default=6);a=p.parse_args()
 try:
  if a.phase=='pilot':pilot()
  else:raise SystemExit(production(a.workers))
 except Exception as exc:
  from datetime import datetime,timezone
  name='error_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json'
  write(HERE/name,dict(status='failed',phase=a.phase,error_type=type(exc).__name__,reason=str(exc),successful_paths_retained=True,automatic_retries=0))
  raise
