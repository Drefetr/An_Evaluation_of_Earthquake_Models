"""Independently count final-power positive-start trace evaluations; no model calls."""
from pathlib import Path
import argparse,hashlib,json,math

PRESETS=[(.05,10.,2.),(.2,20.,5.),(.5,50.,30.)]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit(directory):
    summary=json.loads((directory/'summary.json').read_bytes())
    if not summary['passed'] or not summary['all_final_power_interior_start_coverage_passed']:raise ValueError('unaccepted corrected epoch')
    rows=[]
    for fold in range(3):
        folder=directory/f'california_fold_{fold}';case=json.loads((folder/'result.json').read_bytes());final=case['training_rounds'][-1];power=final['training_power'];traces=folder/'training_traces'/f'power_{power}';protocol=json.loads((traces/'start_protocol.json').read_bytes())
        positive=[s for s in protocol['starts'] if s['role']=='prescribed_positive']
        if len(positive)!=3:raise ValueError('missing prescribed interior starts')
        records={r['start_label']:r for r in final['inhibited']['records']};starts=[]
        for spec,(eta,ell,psi) in zip(positive,PRESETS):
            initial=spec['initial_parameters']
            if initial[:8]!=final['construction_null_parameters'][:8] or initial[8]!=eta or abs(math.exp(initial[9])-ell)>1e-10 or abs(math.exp(initial[10])-psi)>1e-10:raise ValueError('incorrect prescribed start')
            record=records[spec['label']];binding=record['evaluation_trace'];path=traces/(spec['label']+'.evaluations.jsonl');raw=path.read_bytes();evaluations=[json.loads(line) for line in raw.splitlines()]
            if not record['success'] or not evaluations or sha(path)!=binding['trace_sha256']:raise ValueError('failed or changed trace')
            if evaluations[0]['parameters']!=initial:raise ValueError('optimizer did not evaluate the prescribed initial vector')
            interior=0
            for i,e in enumerate(evaluations):
                if e['evaluation']!=i or e['training_power']!=power or not e['inhibit'] or e['details'] or not math.isfinite(e['nll']):raise ValueError('invalid completed optimizer objective record')
                interior+=e['parameters'][8]>0
            if len(evaluations)!=binding['completed_objective_evaluations'] or interior!=binding['interior_objective_evaluations'] or not interior:raise ValueError('evaluation census mismatch')
            starts.append(dict(label=spec['label'],initial_eta=eta,initial_ell=ell,initial_psi=psi,initial_nll=evaluations[0]['nll'],returned_eta=record['parameters'][8],returned_nll=record['nll'],optimizer_success=record['success'],completed_objective_evaluations=len(evaluations),interior_objective_evaluations=interior,trace_sha256=sha(path)))
        rows.append(dict(case=case['case'],training_power=power,required_positive_starts=3,verified_positive_starts=len(starts),positive_starts=starts,selected_eta=case['inhibited']['selected']['parameters'][8],test_gain=case['test_gain_mean']))
    result=dict(schema='independent_etas_interior_trace_census_v1',passed=True,summary_sha256=sha(directory/'summary.json'),auditor_source_sha256=sha(Path(__file__)),scope='Independent JSONL parsing and counts; no trust in recorded coverage booleans or counters without recounting, no fitting or likelihood calls.',rows=rows)
    (directory/'interior_start_audit.json').write_bytes((json.dumps(result,indent=2)+'\n').encode('utf-8'));return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);a=p.parse_args();r=audit(a.directory);print(json.dumps(r))
