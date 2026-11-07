"""Recompute pilot summaries from saved plan and terminal registry; never refit."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import numpy as np


def wilson(k,n):
    if n==0:return None
    z=1.959963984540054
    centre=(k/n+z*z/(2*n))/(1+z*z/n)
    half=z*math.sqrt((k/n)*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0,centre-half),min(1,centre+half)]


def bootstrap(values,seed=2026102499):
    values=np.asarray(values,dtype=float)
    if not len(values):return None
    rng=np.random.default_rng(seed)
    means=values[rng.integers(0,len(values),size=(20000,len(values)))].mean(axis=1)
    return dict(mean=float(values.mean()),percentile95=np.quantile(means,[.025,.975]).tolist(),
        paired_resolved_skeletons=len(values),resamples=20000,seed=seed,
        interpretation='Exploratory paired-resolved Monte Carlo summary; no confirmatory coverage claim.')


def analyse(folder,protocol,protocol_sha256):
    folder=Path(folder)
    manifest=json.loads((folder/'plan.json').read_text())
    if manifest['protocol_sha256']!=protocol_sha256:
        raise ValueError('Analysis protocol bytes differ from frozen run plan')
    plan=manifest['planned']
    planned_by_id={c['case_id']:c for c in plan}
    if len(planned_by_id)!=len(plan):raise ValueError('Duplicate planned case identity')
    terminal={}
    raw_registry=(folder/'registry.jsonl').read_text()
    registry_lines=raw_registry.splitlines()
    partial_last_line=False
    for index,line in enumerate(registry_lines):
        try:event=json.loads(line)
        except json.JSONDecodeError:
            if index==len(registry_lines)-1 and not raw_registry.endswith('\n'):
                partial_last_line=True
                continue
            raise
        if event['event']=='case_terminal':
            case_id=event['case_id']
            if case_id not in planned_by_id:raise ValueError('Unexpected terminal case identity: '+case_id)
            if case_id in terminal:raise ValueError('Duplicate terminal case identity: '+case_id)
            for name in ('skeleton','h','time_seed','mark_seed'):
                if event[name]!=planned_by_id[case_id][name]:raise ValueError('Terminal case definition differs: '+case_id)
            terminal[case_id]=event
    rows=[]
    rule=protocol['comparison']['operational_selection']
    for case in plan:
        saved=terminal.get(case['case_id'],{})
        methods={m['method']:m for m in saved.get('methods',[])}
        for method in ('known_known','background_estimated'):
            result=methods.get(method,{})
            resolved=result.get('status')=='resolved'
            rows.append(dict(case_id=case['case_id'],skeleton=case['skeleton'],h=case['h'],method=method,
                status='resolved' if resolved else 'unknown',reason=None if resolved else result.get('reason',saved.get('status','interrupted_or_unstarted')),
                direct_glr=result.get('direct_glr'),eta=result.get('eta'),
                selected=int(result['direct_glr']>rule['direct_glr_above'] and result['eta']>rule['eta_above']) if resolved else None,
                event_count=saved.get('event_count'),comparison_wall_seconds=saved.get('comparison_wall_seconds')))
    groups=[]
    strengths=protocol['generator']['history_strengths']
    for method in ('known_known','background_estimated'):
        for h in strengths:
            cell=[r for r in rows if r['method']==method and r['h']==h]
            resolved=[r for r in cell if r['status']=='resolved']; n=len(cell); k=sum(r['selected'] for r in resolved); u=n-len(resolved)
            groups.append(dict(method=method,h=h,planned=n,resolved=len(resolved),unknown=u,selected=k,
                selection_frequency_resolved=k/len(resolved) if resolved else None,
                unknown_outcome_bounds=[k/n,(k+u)/n],wilson95_among_resolved=wilson(k,len(resolved)),
                median_glr=float(np.median([r['direct_glr'] for r in resolved])) if resolved else None,
                median_eta=float(np.median([r['eta'] for r in resolved])) if resolved else None))
    paired=[]
    lookup={(r['method'],r['h'],r['skeleton']):r for r in rows}
    skeletons=sorted({r['skeleton'] for r in rows})
    for method in ('known_known','background_estimated'):
        for h in strengths[1:]:
            selection_delta=[];glr_delta=[];lower=[];upper=[]
            for s in skeletons:
                a=lookup[method,0.,s];b=lookup[method,h,s]
                ar=a['selected'];br=b['selected']
                lower.append((br if br is not None else 0)-(ar if ar is not None else 1))
                upper.append((br if br is not None else 1)-(ar if ar is not None else 0))
                if ar is not None and br is not None:
                    selection_delta.append(br-ar);glr_delta.append(b['direct_glr']-a['direct_glr'])
            paired.append(dict(method=method,h_minus_control=h,planned_pairs=len(skeletons),
                paired_resolved_skeletons=len(selection_delta),
                all_planned_selection_difference_bounds=[float(np.mean(lower)),float(np.mean(upper))],
                paired_selection_difference=bootstrap(selection_delta),paired_glr_difference=bootstrap(glr_delta)))
    summary=dict(schema_version=1,scope='Exploratory designed MDFHP-form misspecification stress; no nominal-size or causal inference.',
        pilot_protocol_status=protocol['status'],planned_catalogues=len(plan),planned_method_outcomes=len(rows),
        terminal_catalogues=len(terminal),groups=groups,paired_contrasts=paired,
        partial_last_registry_line=partial_last_line,
        input_hashes={'protocol':protocol_sha256,
            'plan':hashlib.sha256((folder/'plan.json').read_bytes()).hexdigest(),
            'registry':hashlib.sha256((folder/'registry.jsonl').read_bytes()).hexdigest(),
            'analysis_code':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        interval_caveat='Wilson intervals condition on resolution. Unknown bounds use every planned case and are not confidence intervals. Paired bootstrap uses resolved skeleton pairs only.',
        fitting_performed=False)
    return rows,summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True);p.add_argument('--protocol',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    protocol_bytes=Path(args.protocol).read_bytes()
    protocol=json.loads(protocol_bytes)
    for path,expected in protocol['artifact_pins'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen analysis/source artifact changed: '+path)
    import verify_saved
    raw_audit=verify_saved.audit(args.run,args.protocol,Path(__file__).parent/'configs/staged_recipe.json',Path(__file__).parent)
    rows,summary=analyse(args.run,protocol,hashlib.sha256(protocol_bytes).hexdigest())
    if raw_audit['registry_sha256']!=summary['input_hashes']['registry'] or raw_audit['plan_sha256']!=summary['input_hashes']['plan']:
        raise ValueError('Plan or registry changed between raw verification and analysis')
    summary['raw_artifact_audit']=raw_audit
    (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    with (out/'method_outcomes.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(output=str(out),planned_catalogues=summary['planned_catalogues'],terminal_catalogues=summary['terminal_catalogues'])))


if __name__=='__main__':main()
