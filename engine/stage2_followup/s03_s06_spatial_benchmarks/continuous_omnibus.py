"""Pooled-exchangeable continuous-coordinate omnibuses; local vectors stay local.
No chi-square/Fisher independence/asymptotic calibration is used.
"""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
COORDS=('exposure','time_event_logsum','gap_ks','gap_serial','spatial_rosenblatt_ks_max','spatial_rosenblatt_cross_abs','location_dimensionless_log_mean','location_dimensionless_log_variance')
RIDGE=1e-8
if __package__:
 from . import rank_envelope as RANK
else:
 import rank_envelope as RANK
RANK_SOURCE=Path(RANK.__file__)

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pooled_tests(x):
 x=np.asarray(x,float);assert x.shape==(1000,8) and np.isfinite(x).all()
 mean=x.mean(axis=0);sd=x.std(axis=0,ddof=1);assert np.all(sd>0),'DETERMINISTIC_CONTINUOUS_COORDINATE'
 z=(x-mean)/sd;cov=z.T@z/(len(x)-1);regularized=cov+RIDGE*np.eye(8)
 quadratic=np.einsum('ij,ji->i',z,np.linalg.solve(regularized,z.T))
 coordinate_p=np.empty_like(x);ties=[]
 for j in range(8):
  ordered=np.sort(x[:,j]);lo=np.searchsorted(ordered,x[:,j],side='right')/len(x);hi=(len(x)-np.searchsorted(ordered,x[:,j],side='left'))/len(x)
  coordinate_p[:,j]=np.minimum(1,2*np.minimum(lo,hi));ties.append(int(len(x)-len(np.unique(x[:,j]))))
 fisher=-np.log(coordinate_p).sum(axis=1)
 def report(scores):return dict(observed_statistic=float(scores[0]),pooled_upper_inclusive_p=float(np.count_nonzero(scores>=scores[0])/len(scores)),number_equal_observed=int(np.count_nonzero(scores==scores[0])),pooled_n=len(scores))
 return dict(quadratic=report(quadratic),fisher=report(fisher),coordinate_duplicate_counts=ties,observed_coordinate_two_sided_inclusive_p=coordinate_p[0].tolist(),covariance_condition_number=float(np.linalg.cond(regularized)),calibration='each statistic computed symmetrically on observed+999simulated rows; inclusive pooled upper rank; conservative under ties',ridge=RIDGE)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--oc-results',type=Path,required=True,help='Historical OC results root containing observed_producer_cost_v1 and production_v1')
 p.add_argument('--ep-results',type=Path,required=True,help='EP results root containing one folder per california_fold_N')
 p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);assert not out.exists()
 records=[];pins={}
 for model in ('OC','EP'):
  for fold in range(3):
   case=f'california_fold_{fold}'
   if model=='OC':
    base=a.oc_results;observed=base/'observed_producer_cost_v1'/case/'scalars.json';future=base/'production_v1'/case
   else:observed=a.ep_results/case/'observed/scalars.json';future=a.ep_results/case
   paths=[observed]+[future/str(i)/'scalars.json' for i in range(999)]
   values=[];counts=[];full_vectors=[];full_names=None
   for q in paths:
    s=read(q)['stats'];names,vec=RANK.flatten(s)
    if full_names is None:full_names=names
    assert names==full_names and len(names)==84
    full_vectors.append(vec);values.append([s[k] for k in COORDS]);counts.append(s['count']);pins[str(q)]=sha(q)
   env=RANK.envelope(full_vectors,full_names);minrank={k:env[k] for k in ('p_value','reject','observed_extreme_rank','excluded','method')};minrank['retained_coordinates']=len(env['retained_coordinates'])
   n=np.array(counts);lower=float(np.count_nonzero(n<=n[0])/1000);upper=float(np.count_nonzero(n>=n[0])/1000)
   records.append(dict(model=model,case_id=case,coordinates=list(COORDS),minimum_rank=minrank,conditional_N_test=dict(lower_inclusive=lower,upper_inclusive=upper,two_sided_inclusive=min(1,2*min(lower,upper))),**pooled_tests(values)))
 result=dict(schema='stage2_continuous_omnibus_v1',planned_origins=6,completed_origins=len(records),rows=records,method='descriptive continuous statistics; not guaranteed tie-free',source_sha256=sha(__file__),retained_minimum_rank_source_sha256=sha(RANK_SOURCE),input_manifest_sha256=hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest())
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(status='complete',origins=len(records),coordinates=8)))
if __name__=='__main__':main()
