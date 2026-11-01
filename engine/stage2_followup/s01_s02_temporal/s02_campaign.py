"""Historical r0 paired forest campaign; requires original unshipped run plans."""
if __package__:
 from . import campaign as core
 from .campaign import HOME,HERE,save,sha,make,solve_method,pool_run
else:
 import campaign as core
 from campaign import HOME,HERE,save,sha,make,solve_method,pool_run
import json,math,argparse,subprocess,time,os
from pathlib import Path
from dataclasses import replace
import numpy as np

def law(root):
 old,_=core.authorities(root);s=json.loads((HOME/'S02_STAGED_RECIPE.json').read_text())['law']
 return old,replace(old.law_from_setting(dict(beta=s['beta'],horizon=s['horizon_days'],coordinate_horizon=s['coordinate_horizon_days'],generating_fit=s['alternative_generating_fit'])),n=.5)
def arrays(path):
 d=np.atleast_1d(np.genfromtxt(path,delimiter=',',names=True,dtype=float))
 return dict(times=np.array(d['time_hi']),times_lo=np.array(d['time_lo']),event_gaps=np.array(d['event_gap']),excess=np.array(d['excess']))
def generate(root):
 output=HOME/'s02_histories';output.mkdir(exist_ok=False);rows=[];baseline={};began=time.perf_counter()
 for i in range(100):
  for h in (0.,.5,.9):
   case=f's{i:03d}_h{str(h).replace(".","p")}';target=output/(case+'.csv');config=output/(case+'.cfg');seed=2033000000+100*i
   mapping=dict(horizon=24394.,mu=.01557468447327252,reproduction=.5,beta=.5,c=1.,persistence=h,magnitude_rate=2.849401764894274,m0=5.,cutoff=.5,max_events=5000,productivity_ratio=0.)
   config.write_text(''.join(k+'='+format(v,'.17g')+'\n' for k,v in mapping.items()))
   proc=subprocess.run([str(os.environ.get('INHIBITORY_MATCHED_CLI',HERE/'r_matched/mdfhp_cli.exe')),'simulate',str(config),str(target),str(seed),str(seed+10000000)],capture_output=True,text=True,timeout=30)
   status=json.loads(proc.stdout) if proc.stdout.strip() else dict(status='unknown_cli',error=proc.stderr)
   row=dict(id=case,forest=i,h=h,time_seed=seed,mark_seed=seed+10000000,path=str(target),history_sha256=sha(target) if target.exists() else None,generation=status,returncode=proc.returncode)
   if proc.returncode==0 and status.get('status')=='ok':
    data=np.atleast_1d(np.genfromtxt(target,delimiter=',',names=True,dtype=float));skeleton=np.column_stack([data[k] for k in ('time_hi','time_lo','event_gap','event_id','parent_id','generation')]).tobytes();import hashlib
    identity=hashlib.sha256(skeleton).hexdigest();baseline.setdefault(i,identity);row['coupled_skeleton_match']=identity==baseline[i]
    if not row['coupled_skeleton_match']:row['generation']['status']='unknown_coupling_failure'
   rows.append(row);save(HOME/'S02_GENERATION_MANIFEST.json',dict(planned=300,completed=len(rows),cases=rows,seconds=time.perf_counter()-began))
 print(json.dumps(dict(planned=300,completed=len(rows),successful=sum(x['generation']['status']=='ok' for x in rows),seconds=time.perf_counter()-began)))

def fit(task):
 root,row=task;out=HOME/'s02_fits'/(row['id']+'.json')
 if out.exists():
  p=json.loads(out.read_text());return dict(id=row['id'],status=p.get('status'),reused=True)
 result=dict(id=row['id'],forest=row['forest'],h=row['h'],history_sha256=row['history_sha256'],methods=[]);began=time.perf_counter();deadline=began+3600
 if row['generation'].get('status')!='ok':result.update(status='unknown_generation');save(out,result);return dict(id=row['id'],status=result['status'])
 if sha(row['path'])!=row['history_sha256']:raise ValueError('generated input changed')
 data=arrays(row['path']);old,supplied=law(root)
 for method,r in [('M1',.7),('M2',0.)]:
  h=h32=None
  try:
   current=replace(supplied,ratio=r);h=make(data,current,old,'paired',16,deadline);h32=make(data,current,old,'paired',32,deadline)
   out.parent.mkdir(parents=True,exist_ok=True);h.trace=str(out.with_suffix('.'+method+'.attempts.jsonl'))
   answer=solve_method(h,h32,current,'I11',deadline);answer['procedure']=method;answer['candidate_ratio']=r;result['methods'].append(answer)
  except Exception as e:result['methods'].append(dict(procedure=method,status='unknown_exception',error=type(e).__name__+':'+str(e)))
  finally:
   if h:h.close()
   if h32:h32.close()
  save(out,result)
 result['status']='complete' if len(result['methods'])==2 and all(m['status']=='complete' for m in result['methods']) else 'partial';result['seconds']=time.perf_counter()-began;save(out,result)
 return dict(id=row['id'],status=result['status'],seconds=result['seconds'])

def wilson(k,n):
 z=1.959963984540054;den=1+z*z/n;mid=(k/n+z*z/(2*n))/den;half=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/den
 return [mid-half,mid+half]
def summarize():
 manifest=json.loads((HOME/'S02_GENERATION_MANIFEST.json').read_text());rows=[];lookup={};table=[];paired=[]
 for case in manifest['cases']:
  file=HOME/'s02_fits'/(case['id']+'.json');result=json.loads(file.read_text()) if file.exists() else {}
  for proc in ('M1','M2'):
   m=next((x for x in result.get('methods',[]) if x['procedure']==proc),{})
   resolved=m.get('status')=='complete';glr=m.get('direct_contrast16',{}).get('statistic') if resolved else None;eta=m.get('alternative',{}).get('pars',[None]*4)[3] if resolved else None
   row=dict(forest=case['forest'],h=case['h'],procedure=proc,resolved=resolved,glr=glr,eta=eta,selected=bool(glr>.001 and eta>1e-6) if resolved else None);rows.append(row);lookup[proc,case['h'],case['forest']]=row
 for proc in ('M1','M2'):
  null=[lookup[proc,0.,i]['glr'] for i in range(100)];threshold=float(np.quantile(null,.95,method='higher')) if all(v is not None for v in null) else None
  for h in (0.,.5,.9):
   group=[lookup[proc,h,i] for i in range(100)];n=sum(x['resolved'] for x in group);k=sum(x['selected'] is True for x in group)
   table.append(dict(procedure=proc,h=h,planned=100,resolved=n,unknown=100-n,selected=k,selection_proportion=k/100 if n==100 else None,selection_bounds=[k/100,(k+100-n)/100],wilson95=wilson(k,n) if n else None,wilson_scope='all100' if n==100 else 'conditional_resolved_only',empirical_h0_95threshold=threshold,threshold_scope='same100_h0_descriptive_not_independent_calibration',above_empirical_threshold=sum(x['glr']>threshold for x in group if x['resolved']) if threshold is not None else None))
   differences=[lookup[proc,h,i]['glr']-lookup[proc,0.,i]['glr'] for i in range(100) if lookup[proc,h,i]['resolved'] and lookup[proc,0.,i]['resolved']]
   paired.append(dict(procedure=proc,h_minus0=h,planned_pairs=100,complete_pairs=len(differences),mean=float(np.mean(differences)) if differences else None,median=float(np.median(differences)) if differences else None,mcse=float(np.std(differences,ddof=1)/math.sqrt(len(differences))) if len(differences)>1 else None))
 save(HOME/'S02_PRIVATE_ANALYSIS_ROWS.json',rows)
 save(HOME/'S02_SUMMARY.json',dict(status='complete' if all(r['resolved'] for r in rows) else 'partial',planned_forests=100,planned_catalogues=300,planned_method_cases=600,completed_method_cases=sum(r['resolved'] for r in rows),table=table,paired_glr_differences=paired,interpretation='Productivity comparison at r0 generator with common candidate n=.5; M1 r=.7 replication arm strengthens starts and changes original supplied n≈.501775 to.5 in both arms. h0 thresholds descriptive empirical on same100, no independent calibration; exactML generator/finite195-mode candidate mismatch remains disclosed.'))
 print(json.dumps(dict(planned_method_cases=600,completed_method_cases=sum(r['resolved'] for r in rows))))

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['generate','fit','summary']);p.add_argument('--root',type=Path,required=True);p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int);a=p.parse_args()
 if a.stage=='generate':generate(a.root)
 elif a.stage=='summary':summarize()
 else:
  cases=json.loads((HOME/'S02_GENERATION_MANIFEST.json').read_text())['cases'];cases=cases[:a.limit] if a.limit else cases
  result=pool_run(fit,[(str(a.root),x) for x in cases],a.workers);save(HOME/('S02_FIT_PILOT_RESULT.json' if a.limit else 'S02_FIT_CAMPAIGN_RESULT.json'),dict(planned=len(cases),completed=len(result),cases=result))
if __name__=='__main__':main()
