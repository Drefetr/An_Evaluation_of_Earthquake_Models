"""Reaggregate saved scalar-control outputs; no likelihood evaluation or fitting."""
from pathlib import Path
import argparse, hashlib, json, math, statistics

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def summarize(directory):
    directory=Path(directory)
    result=json.loads((directory/'result.json').read_text(encoding='utf-8'))
    if not result['passed'] or result['phase']!='full' or result['completed_cases']!=80:
        raise ValueError('Complete original fixed roster required')
    cases=[]
    for row in result['reports']:
        p=(directory/row['file']).resolve()
        if not p.is_relative_to(directory.resolve()) or sha(p)!=row['sha256']:
            raise ValueError('Changed or unsafe case report')
        case=json.loads(p.read_text(encoding='utf-8'))
        if not case['passed']:raise ValueError('Failed case')
        cases.append(case)
    regimes={4:'narrow_short_imm',5:'broad_long_imm',6:'narrow_short_total',7:'broad_long_total'}
    expected_cases={(f'S{regime}_{label}_seed{seed}',regime,seed)
                    for regime,label in regimes.items() for seed in range(410000+regime*100+1,410000+regime*100+21)}
    if len(cases)!=80 or {(c['case_id'],c['regime'],c['seed']) for c in cases}!=expected_cases:
        raise ValueError('Roster mismatch')
    models={'LI','LIplus_immigrant','LIplus_inclusive'}
    expected_checks={(phase,model) for phase in ('train','test') for model in models}
    procedures={('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')}
    for case in cases:
        checks=case['historical_floor_checks']
        if len(checks)!=6 or {(c['phase'],c['model']) for c in checks}!=expected_checks:
            raise ValueError('Historical floor check roster differs')
        if len(case['outcomes'])!=5 or {(o['model'],o['gate']) for o in case['outcomes']}!=procedures:
            raise ValueError('Procedure roster differs')
    expected_summary={(regime,model,gate) for regime in regimes for model,gate in procedures}
    if len(result['summary'])!=20 or {(r['regime'],r['model'],r['gate']) for r in result['summary']}!=expected_summary:
        raise ValueError('Summary roster differs')
    floors={}
    for regime in range(4,8):
        group=[c for c in cases if c['regime']==regime]
        if len(group)!=20:raise ValueError('Regime denominator differs')
        floors[str(regime)]={'N':len(group)}
        for key in ['P','E','C','M','joint']:
            floors[str(regime)]['mean_delta_'+key]=statistics.mean(c['phases']['test']['delta'][key] for c in group)
        floors[str(regime)]['mean_refitted_background_exposure']=statistics.mean(c['phases']['test']['refitted']['background_exposure'] for c in group)
        a=[c['fit']['a'] for c in group]
        floors[str(regime)].update(a_min=min(a),a_median=statistics.median(a),a_max=max(a))
    for row in result['summary']:
        outcomes=[o for c in cases if c['regime']==row['regime'] for o in c['outcomes'] if (o['model'],o['gate'])==(row['model'],row['gate'])]
        if len(outcomes)!=20 or sum(o['new_win'] for o in outcomes)!=row['wins']:raise ValueError('Outcome roster or wins differ')
        if not math.isclose(statistics.mean(o['new_gain'] for o in outcomes),row['mean_gain'],rel_tol=0,abs_tol=1e-12):raise ValueError('Mean differs')
    exposures=[c['phases']['test']['historical']['background_exposure'] for c in cases]
    if max(exposures)-min(exposures)>1e-10:raise ValueError('Fixed exposure changed')
    return {'schema':'s04b_refitted_floor_component_summary_v1','passed':True,
            'result_sha256':sha(directory/'result.json'),'script_sha256':sha(Path(__file__)),
            'cases':len(cases),'historical_floor_checks':sum(len(c['historical_floor_checks']) for c in cases),'fixed_background_test_exposure':statistics.mean(exposures),
            'floor_by_regime':floors,'procedure_summary':result['summary'],
            'max_saved_floor_absolute_difference':max(abs(v['delta']) for c in cases for v in c['historical_floor_checks']),
            'case_sha256':{row['file']:row['sha256'] for row in result['reports']}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--output',type=Path);g.add_argument('--check',type=Path)
    a=p.parse_args();d=summarize(a.input)
    if a.check:
        if d!=json.loads(a.check.read_text(encoding='utf-8')):raise SystemExit('Summary mismatch')
    else:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2);f.write('\n')
    print(json.dumps({'passed':True,'cases':d['cases'],'historical_floor_checks':d['historical_floor_checks']}))

if __name__=='__main__':main()

