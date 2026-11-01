"""Saved-result-only hybrid provenance/calibration, no fitting on import/run."""
from campaign import HOME,save,sha
from pathlib import Path
import json,copy,random,hashlib,collections,time,argparse
import numpy as np
import calibration_arithmetic as arithmetic

def main():
 p=argparse.ArgumentParser();p.add_argument('--bootstrap',type=int,default=2000);a=p.parse_args()
 if a.bootstrap!=2000:raise ValueError('exact2000 required')
 data=json.loads((HOME/'INPUT_CASES.json').read_text());oldbank=Path(data['bank_path'])
 if sha(oldbank)!=data['bank_sha256']:raise ValueError('oldbank changed')
 bank=json.loads(oldbank.read_text());byid={r['id']:r for r in bank['rows']};changes=[];unknown=[]
 for role in ('reference','null_query','alternative_query'):
  for item in data['missing'][role]:
   f=HOME/'fits'/(item['id']+'.json');record=json.loads(f.read_text()) if f.exists() else {};methods={m['cell']:m for m in record.get('methods',[])}
   for cell in item['cells']:
    i=bank['cells'].index(cell)
    if byid[item['id']]['statistics'][i] is not None:raise ValueError('resolved overwrite prohibited')
    m=methods.get(cell,{})
    if m.get('status')=='complete':
     value=m['direct_contrast16']['statistic'];row=byid[item['id']];row['statistics'][i]=value
     row.setdefault('original_method_statuses',copy.deepcopy(row.get('method_statuses',{})));row.setdefault('stage2_new_sources',{})[cell]=dict(path=str(f),sha256=sha(f));row.setdefault('method_statuses',{})[cell]='complete'
     changes.append(dict(id=item['id'],role=role,cell=cell,new_result=str(f),sha256=sha(f),procedure='stage2_eight_start_missing_only'))
    else:unknown.append(dict(id=item['id'],role=role,cell=cell,status=m.get('status',record.get('status','unattempted'))))
 bank['stage2_hybrid_procedure']='saved controlled original methods plus authorized eight-start recovery for missing cells only';bank['stage2_changes']=changes;save(HOME/'S01_HYBRID_BANK_PRIVATE.json',bank)
 vectors={r:[byid[case]['statistics'] for case in bank['roles'][r]] for r in bank['roles']}
 base={r:arithmetic.calibrate(vectors['reference'],vectors[r],.05) for r in ('null_query','alternative_query')}
 save(HOME/'S01_CALIBRATION_PRIVATE.json',base);summary={}
 for role,result in base.items():
  summary[role]=dict(planned_queries=len(bank['roles'][role]),decisions={cell:dict(R=sum(v is True for v in result['decisions'][cell]),NR=sum(v is False for v in result['decisions'][cell]),U=sum(v is None for v in result['decisions'][cell])) for cell in bank['cells']},rejection_bounds=result['rejection_bounds'],interaction_bounds=result['interaction_bounds'],interaction=result['interaction'])
 rng=random.Random(202610190401);qrng={r:random.Random(seed) for r,seed in [('null_query',202610190402),('alternative_query',202610190403)]};acc={r:{mode:dict(means=[],mcse=[],statuses=[],bounds=[]) for mode in ('bank_only','bank_and_paired_query')} for r in base};began=time.perf_counter();completed=0
 for offset in range(0,2000,25):
  plans=[[rng.randrange(999) for _ in range(999)] for _ in range(25)];result={}
  for role in base:
   n=len(vectors[role]);queries=[[qrng[role].randrange(n) for _ in range(n)] for _ in range(25)];result[role]={}
   for mode,q in [('bank_only',None),('bank_and_paired_query',queries)]:
    value=arithmetic.summarize_resamples(vectors['reference'],vectors[role],plans,q,.05);result[role][mode]=value;target=acc[role][mode]
    target['means']+=value['point_mcse']['mean'];target['mcse']+=value['point_mcse']['mcse'];target['statuses']+=value['point_mcse']['status'];target['bounds'].append(value['interaction_bounds'])
  save(HOME/'bootstrap'/f'chunk_{offset:04d}.json',dict(offset=offset,replicates=25,reference_plan_sha256=hashlib.sha256(json.dumps(plans,separators=(',',':')).encode()).hexdigest(),results=result));completed+=25
 bootstrap={}
 for role in acc:
  bootstrap[role]={}
  for mode,val in acc[role].items():
   finite=[v for v in val['means'] if v is not None];bootstrap[role][mode]=dict(replicates=2000,status_counts=dict(collections.Counter(val['statuses'])),interaction_mean_quantiles={str(q):float(np.quantile(finite,q)) for q in (.025,.5,.975)} if len(finite)==2000 else None)
 controlled={r:{c:sum(row[i] is not None for row in vectors[r]) for i,c in enumerate(bank['cells'])} for r in vectors}
 geo=[];original=Path(data['old_run_root'])/'results/F_geometry_diagnostic06';targets={'new_r076','null_0945','null_1292','null_1322','null_1434'}
 protocol=json.loads((Path(data['old_run_root'])/'protocols/F_geometry_diagnostic06_frozen.json').read_text())['protocol']
 for binding in protocol['sample_plan']['case_bindings']:
  case=binding['id'];f=HOME/'meshes'/(case+'.json') if case in targets else original/(case+'.json');d=json.loads(f.read_text()) if f.exists() else {};rows=d.get('profile_rows',d.get('diagnostic',{}).get('profile_rows',[]));expected=d.get('planned_profile_rows',d.get('diagnostic',{}).get('planned_profile_rows',140));valid=len(rows)==expected and expected==140 and all(row.get('agreement_pass') is True for row in rows)
  geo.append(dict(id=case,source=str(f),sha256=sha(f) if f.exists() else None,rows=len(rows),expected=expected,complete=valid,origin='stage2_missing_mesh' if case in targets else 'original_completed_mesh'))
 save(HOME/'S01_MESH_MANIFEST.json',geo)
 final=dict(status='complete' if not unknown and all(v==len(vectors[r]) for r,counts in controlled.items() for v in counts.values()) and all(x['complete'] for x in geo) else 'partial',controlled_statistic_counts=controlled,new_controlled_cells=len(changes),unresolved_cells=len(unknown),planned_roles={r:len(v) for r,v in vectors.items()},calibration=summary,bootstrap=bootstrap,completed_bootstrap_replicates=completed,bootstrap_seconds=time.perf_counter()-began,complete_meshes=sum(x['complete'] for x in geo),planned_meshes=11,procedure='authorized hybrid original-resolved plus missing-only eight-start recovery; oracle bank retained; no nested plug-in recalibration')
 save(HOME/'S01_UNRESOLVED_PRIVATE.json',unknown);save(HOME/'S01_SUMMARY.json',final);print(json.dumps({'status':final['status'],'controlled_statistic_counts':controlled,'new_controlled_cells':len(changes),'unresolved_cells':len(unknown),'complete_meshes':final['complete_meshes'],'completed_bootstrap_replicates':completed}))
if __name__=='__main__':main()
