"""Compare accepted EP+ and archived EP scores after exact history/mark checks."""
from pathlib import Path
import argparse,hashlib,io,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reproduction.score_replay.core import Inputs

def load(folder,row):
    with np.load(io.BytesIO(Inputs(folder).read(row['cache'])),allow_pickle=False) as z:return {k:z[k].copy() for k in z.files if k!='metadata_json'},json.loads(str(z['metadata_json'].item()))

def main():
    p=argparse.ArgumentParser();p.add_argument('--accepted',type=Path,required=True);a=p.parse_args();root=a.accepted;raw=(root/'summary.json').read_bytes();summary=json.loads(raw)
    if not summary['passed']:raise ValueError('unaccepted new benchmark')
    ep=ROOT/'reproduction/score_replay/california_benchmark';oc=ROOT/'reproduction/score_replay/california';er=json.loads((ep/'registry.json').read_bytes());cr=json.loads((oc/'registry.json').read_bytes());rows=[]
    for row in er['rows']:
        if row['phase']!='test' or row['procedure_key']!='EP':continue
        case=row['case'];pr=next(r for r in cr['rows'] if r['study']=='primary_california' and r['case']==case and r['phase']=='test' and r['procedure_key']=='Omori_smooth_cont');newdata,meta=load(oc,pr);olddata,oldmeta=load(ep,row);state=Inputs(ep).json(row['state']);d=json.loads((root/case/'result.json').read_bytes())
        same={k:bool(np.array_equal(newdata[k],olddata[k])) for k in ('parent_time','parent_xy','parent_fertility','event_time','event_xy','rectangles')}
        same.update({key:meta[key]==oldmeta[key] for key in ('start','end','T0','beta')})
        if not all(same.values()):raise ValueError(('history mismatch',case,same))
        beta=meta['beta'];mark=float(len(newdata['event_time'])*math.log(beta)-beta*newdata['event_excess'].sum());old=state['expected_components']
        if abs(mark-old['M'])>1e-8 or abs(old['joint']-(old['P']-old['E']+old['M']))>1e-8:raise ValueError(('mark/score measure mismatch',case))
        null_values=[-r['null']['nll']+mark for r in d['test_scores']]
        if max(null_values)-min(null_values)>1e-10:raise ValueError('uninhibited score must be analytic')
        rows.append(dict(case=case,new_joint_score=null_values[0],original_EP_joint_score=old['joint'],gain=null_values[0]-old['joint'],common_mark_score=mark,beta=beta,identical_history_checks=same,original_EP_state_sha256=row['state']['sha256'],original_EP_cache_sha256=row['cache']['sha256'],primary_cache_sha256=pr['cache']['sha256']))
    if len(rows)!=3:raise ValueError('incomplete three-fold comparison')
    result=dict(schema='epplus_vs_original_ep_checked_scores_v1',passed=True,accepted_summary_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,total_gain=sum(r['gain'] for r in rows),comparison='Combined new magnitude scaling, training declustering and joint temporal/spatial fitting versus the archived EP procedure; same event/parent history, fertility and mark measure verified exactly.')
    (root/'baseline_comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
