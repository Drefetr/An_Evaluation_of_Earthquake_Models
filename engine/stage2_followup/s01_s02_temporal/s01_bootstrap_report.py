"""Approved aggregate projection of exactly2000 retained bootstrap replicas."""
from pathlib import Path
import json,hashlib,math,collections
HOME=Path(__file__).resolve().parent.parent
CELLS=('I00','I10','I01','I11');ROLES=('null_query','alternative_query');MODES=('bank_only','bank_and_paired_query')
def quantiles(values):
 if len(values)!=2000 or not all(type(v) in (int,float) and math.isfinite(v) for v in values):raise ValueError('complete finite2000values required')
 x=sorted(values);out={}
 for q in (.025,.5,.975):
  h=(len(x)-1)*q;i=int(h);out[str(q)]=x[i]+(h-i)*(x[min(i+1,len(x)-1)]-x[i])
 return out
def main():
 accum={r:{m:dict(rates={c:{'lower':[],'upper':[]} for c in CELLS},interaction={'lower':[],'upper':[]},statuses=[]) for m in MODES} for r in ROLES};inputs=[];expected=0
 for path in sorted((HOME/'bootstrap').glob('chunk_*.json')):
  raw=path.read_bytes();d=json.loads(raw)
  if d['offset']!=expected or d['replicates']!=25:raise ValueError('bootstrapgap/overlap')
  inputs.append(dict(name=path.name,sha256=hashlib.sha256(raw).hexdigest()));expected+=25
  for role in ROLES:
   for mode in MODES:
    source=d['results'][role][mode];target=accum[role][mode]
    if tuple(source['cells'])!=CELLS or source['replicates']!=25 or source['query_mode']!=('fixed' if mode=='bank_only' else 'paired_resample'):raise ValueError('caseaxes changed')
    if any(len(source['rejection_bounds'][c][e])!=25 for c in CELLS for e in ('lower','upper')) or any(len(source['interaction_bounds'][e])!=25 for e in ('lower','upper')) or len(source['point_mcse']['status'])!=25:raise ValueError('chunkarray length')
    for cell in CELLS:
     for endpoint in ('lower','upper'):target['rates'][cell][endpoint]+=source['rejection_bounds'][cell][endpoint]
    for endpoint in ('lower','upper'):target['interaction'][endpoint]+=source['interaction_bounds'][endpoint]
    target['statuses']+=source['point_mcse']['status']
 if expected!=2000:raise ValueError('exact2000replicates required')
 summary={}
 for role in ROLES:
  summary[role]={}
  for mode,source in accum[role].items():
   for c in CELLS:
    if any(not 0<=l<=u<=1 for l,u in zip(source['rates'][c]['lower'],source['rates'][c]['upper'])):raise ValueError('invalidratebounds')
   if any(not -2<=l<=u<=2 for l,u in zip(source['interaction']['lower'],source['interaction']['upper'])):raise ValueError('invalidinteractionbounds')
   summary[role][mode]=dict(rejection_endpoint_quantiles={c:{e:quantiles(values) for e,values in endpoints.items()} for c,endpoints in source['rates'].items()},interaction_endpoint_quantiles={e:quantiles(values) for e,values in source['interaction'].items()},point_mcse_status_counts=dict(collections.Counter(source['statuses'])))
 result=dict(planned_replicates=2000,completed_replicates=expected,bootstrap=summary,chunk_inputs=inputs,interpretation='Exploratory shared-bank and paired-query resampling sensitivity, type7 quantiles; unknown endpoints retained; no nominal coverage guarantee and authorized hybrid procedure disclosed.')
 (HOME/'S01_BOOTSTRAP_SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(completed_replicates=expected,chunk_count=len(inputs),interaction_statuses={r:{m:summary[r][m]['point_mcse_status_counts'] for m in MODES} for r in ROLES})))
if __name__=='__main__':main()
