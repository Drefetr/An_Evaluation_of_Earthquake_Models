"""Independent S02 all-return finite-mixture raw-CSV audit; no production imports."""
from pathlib import Path
import argparse,json,time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from f_oracle_v2 import Native,public_law,sha,read,need,projected,HERE,RUN

def one(task):
 dll,row,refined,private=task;begin=time.perf_counter();file=Path(row['path']);need(sha(file)==row['history_sha256'],'RAW_CSV_PIN');d=np.atleast_1d(np.genfromtxt(file,delimiter=',',names=True,dtype=float));data=dict(times=d['time_hi'],times_lo=d['time_lo'],event_gaps=d['event_gap'],excess=d['excess']);fitfile=RUN/'M01/s02_fits'/(row['id']+'.json');saved=read(fitfile);need(saved['history_sha256']==sha(file),'FIT_HISTORY');need(len(saved['methods'])==2 and {m['procedure'] for m in saved['methods']}=={'M1','M2'},'PROCEDURE_MAP');native=Native(dll);law=public_law(True);maximum=0.;quad=0.;points=0;unknown=0;details=[];proj=0.
 for m in saved['methods']:
  name=m['procedure'];ratio=.7 if name=='M1' else 0.;need(m.get('candidate_ratio',ratio)==ratio,'RATIO');
  if m['status']!='complete':unknown+=1;details.append(dict(procedure=name,status='producer_unknown'));continue
  records=m['attempts'];need(all(c['passed'] for c in m['controls']),'CONTROL_FAILED')
  for phase in ('null','alternative'):
   need({r['start_index'] for r in records if r['phase']==phase}==set(range(8)),'EIGHT_START_MAP')
   for index in range(8):
    seq=[r for r in records if r['phase']==phase and r['start_index']==index];need(1<=len(seq)<=3 and [r['tier'] for r in seq]==['LBFGSB40','LBFGSB200','Powell'][:len(seq)] and seq[-1]['success'] and not any(r['success'] for r in seq[:-1]),'PRESCRIBED_RECOVERY')
  state=native.state(data,law,'paired',ratio,32,True);high=native.state(data,law,'paired',ratio,64,True) if refined else None
  try:
   own={}
   for phase in ('null','alternative'):
    p=m[phase]['pars'];need(phase!='null' or p[3]==0.,'NULL_ETA_FLOOR');need(p[2]==.5 and -12<=p[0]<=0 and -2<=p[1]<=2 and 0<=p[3]<=3,'FIXED_N_BOUNDS');v=state.evaluate(p);error=abs(v[0]-m[phase]['nll']);need(error<=1e-4,'INDEPENDENT_NLL');maximum=max(maximum,error);own[phase]=v[0];points+=1
    if high:delta=abs(high.evaluate(p)[0]-v[0]);quad=max(quad,delta);need(delta<=1e-4,'REFINED32_64')
   error=abs(2*(own['null']-own['alternative'])-m['direct_contrast16']['statistic']);need(error<=1e-4,'INDEPENDENT_GLR');maximum=max(maximum,error)
   for r in records:
    v=state.evaluate(r['terminal_pars']);error=abs(v[0]-r['terminal_best_nll']);need(error<=1e-4,'ALL_RETURN_NLL');maximum=max(maximum,error);proj=max(proj,projected(v[1:5],r['terminal_pars'],r['free']));points+=1
  finally:
   state.close()
   if high:high.close()
  details.append(dict(procedure=name,status='raw_reconstructed'))
 p=Path(private)/(row['id']+'.json');p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(dict(history_sha256=sha(file),fit_sha256=sha(fitfile),procedures=details),f,indent=2)
 return dict(planned_procedures=2,audited_procedures=2-unknown,unknown=unknown,audited_points=points,maximum_absolute_error=maximum,refined32_64_maximum=quad,projected_gradient_diagnostic=proj,wall_seconds=time.perf_counter()-begin,private_receipt_sha256=sha(p))
def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--dll',required=True);p.add_argument('--dll-sha256',required=True);p.add_argument('--output',required=True);p.add_argument('--limit',type=int);p.add_argument('--workers',type=int,default=2);a=p.parse_args();need(sha(a.dll)==a.dll_sha256,'ORACLE_BINARY');m=read(a.manifest);rows=m['cases'];need(len(rows)==300 and {(r['forest'],r['h']) for r in rows}=={(i,h) for i in range(100) for h in (0.,.5,.9)},'FIXED300_ROSTER');need(all(r['time_seed']==2033000000+100*r['forest'] and r['mark_seed']==2033000000+100*r['forest']+10000000 for r in rows),'REGISTERED_SEED_MAP');rows=rows[:a.limit] if a.limit else rows;out=Path(a.output);need(not out.exists(),'APPEND_ONLY');begin=time.perf_counter()
 with ProcessPoolExecutor(max_workers=a.workers) as pool:result=list(pool.map(one,[(a.dll,r,bool(a.limit),str(out.with_suffix('.private'))) for r in rows]))
 report=dict(schema='Q01_S02_raw_allreturn_audit_v1',status='complete' if not any(r['unknown'] for r in result) else 'partial',catalogues=len(rows),planned_procedures=2*len(rows),audited_procedures=sum(r['audited_procedures'] for r in result),audited_points=sum(r['audited_points'] for r in result),maximum_absolute_error=max(r['maximum_absolute_error'] for r in result),maximum_refined32_64_difference=max(r['refined32_64_maximum'] for r in result),wall_seconds=time.perf_counter()-begin,rows=result,manifest_sha256=sha(a.manifest),auditor_sha256=sha(__file__),scope='Independent finite195mode likelihood from rawCSV; allfinite terminalreturns; projectedgradientsdiagnosticnotKKTglobalproof')
 with out.open('x') as f:json.dump(report,f,indent=2)
 print(json.dumps({k:v for k,v in report.items() if k!='rows'}))
if __name__=='__main__':main()
