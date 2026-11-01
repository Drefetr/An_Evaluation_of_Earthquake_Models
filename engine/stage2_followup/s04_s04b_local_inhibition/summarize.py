"""Complete-case ledger and scalar tables; missing outputs remain unknown."""
import argparse,json,math,sys
from pathlib import Path
import numpy as np
if __package__:
 from ..s03_s06_spatial_benchmarks.spatial import read,write,sha
else:
 sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
 from engine.stage2_followup.s03_s06_spatial_benchmarks.spatial import read,write,sha
def wilson(k,n):
 if not n:return None
 z=1.959963984540054;p=k/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [mid-half,mid+half]
def summarize(root,output):
 root=Path(root);ledger=[];spatial=[];li=[];pins={}
 for region in ['CA','NZ']:
  for fold in range(3):
   p=root/'results'/f'S03_{region}_{fold}'/'aggregate.json'
   if not p.exists():ledger.append(dict(workstream='S03',region=region,fold=fold,status='unknown_missing'));continue
   a=read(p);pins[str(p)]=sha(p);ledger.append(dict(workstream='S03',region=region,fold=fold,status=a['status']))
   rows={r['arm']:r for r in a['results']}
   for left,right,label in [(1,2,'unweight'),(2,3,'LOO_training_estimator'),(2,4,'matched_EP_tail_scale')]:
    spatial.append(dict(region=region,fold=fold,contrast=label,n_test=rows[right]['n_test'],scores={k:rows[right]['scores'][k]-rows[left]['scores'][k] for k in ['timing','location','mark','joint','point','compensator']}))
 for regime in range(4):
  for ordinal in range(20):
   seed=410001+100*regime+ordinal;p=root/'results'/f'S04_R{regime}_S{seed}'/'aggregate.json'
   if not p.exists():ledger.append(dict(workstream='S04',regime=regime,seed=seed,status='unknown_missing'));continue
   a=read(p);pins[str(p)]=sha(p);ledger.append(dict(workstream='S04',regime=regime,seed=seed,status=a['status']))
   for row in a['results']:li.append(dict(regime=regime,seed=seed,**row,aggregate_status=a['status']))
 table=[]
 for regime in range(4):
  for model,gate in [('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')]:
   rows=[r for r in li if (r['regime'],r['model'],r['gate'])==(regime,model,gate)];valid=[r for r in rows if r['status']=='complete' and r['aggregate_status']=='pending_independent_audit'];values=np.array([r['gain'] for r in valid]);wins=sum(r['win'] for r in valid)
   table.append(dict(regime=regime,model=model,gate=gate,planned=20,resolved=len(valid),unknown=20-len(valid),wins=wins,win_rate_resolved=wins/len(valid) if valid else None,win_rate_bounds_full=[wins/20,(wins+20-len(valid))/20],wilson_resolved=wilson(wins,len(valid)),mean_resolved=float(values.mean()) if len(values) else None,median_resolved=float(np.median(values)) if len(values) else None,mean_mcse_resolved=float(values.std(ddof=1)/np.sqrt(len(values))) if len(values)>1 else None,off_floor_count=sum(r['off_floor'] for r in valid)))
 observed=[]
 for fold in range(3):
  p=root/'results'/f'S04_CA_{fold}'/'aggregate.json'
  if p.exists():pins[str(p)]=sha(p);observed.append(dict(fold=fold,**read(p)))
  else:observed.append(dict(fold=fold,status='unknown_missing'))
 write(output,dict(schema='stage2_M02_scalar_summary_v1',acceptance='pending_Q01_independent_raw_reconstruction',denominators=dict(S03_folds=6,S04_synthetic_datasets=80,S04_observed_folds=3),ledger=ledger,spatial_adjacent_contrasts=spatial,synthetic_table=table,observed=observed,pins=pins))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();summarize(a.root,a.output)
