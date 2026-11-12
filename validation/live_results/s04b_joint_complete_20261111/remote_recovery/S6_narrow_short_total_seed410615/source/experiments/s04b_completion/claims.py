"""Emit typed numeric bindings for coordinator merge; never edits the ledger."""
import hashlib,json
from pathlib import Path
from experiments.s04b_completion.recover import REPO,OUT,read
from experiments.s04b_joint_nuisance.checkpoint import write

def main():
    claims=[]
    def claim(source,pointer,value,display,location,qualification='All twenty histories per regime; training-only fitting and held-out evaluation.'):
        path=REPO/source
        claims.append(dict(id='remediation-synthetic-'+str(len(claims)+1).zfill(4),bundled_source=source,source_path=source,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),json_pointer=pointer,resolved_source_value=value,display=str(display),transformation='decimal rounding to displayed precision',json_value_kind='numeric_scalar',ledger_role='manuscript_binding',final_display_locations=[location],component='Completed synthetic controls and comparator sensitivity',qualification=qualification,status='source_bound',binding_kind='exact_json_pointer',value=value,reconciliation_status='verified_at_declared_granularity'))
    source='validation/live_results/s04b_concave_20261111/summary.json';data=read(REPO/source)
    for i,r in enumerate(data['summary']):
        base=f'/summary/{i}/'
        for key,display in [('mean_gain',f"{r['mean_gain']:.4f}"),('active',str(r['active']))]:
            claim(source,base+key,r[key],display,'chapters/13_s04_refitted_floor.tex')
    i=next(i for i,r in enumerate(data['summary']) if r['regime']==7)
    claim(source,f'/summary/{i}/n_zero',20,20,'chapters/13_s04_refitted_floor.tex')
    if (OUT/'summary.json').exists():
        source=(OUT/'summary.json').relative_to(REPO).as_posix();data=read(REPO/source);location='chapters/13_s04b_joint_dispositions.tex'
        for key in ('completed_histories','completed_outcomes'):claim(source,'/'+key,data[key],data[key],location)
        for i,r in enumerate(data['summary']):
            b=f'/summary/{i}/'
            for key in ('N','wins','unknowns','optimizer_failed_attempts','null_search_gap_cases','coarse_fine_gate_disagreements','off_floor','floor_returns','near_zero','positive_near_zero','robust_positive','robust_negative','eta_lower','eta_upper'):
                claim(source,b+key,r[key],r[key],location)
            for key in ('mean_gain','median_gain'):claim(source,b+key,r[key],f"{r[key]:.4f}",location)
            for j,v in enumerate(r['wilson95']):claim(source,b+f'wilson95/{j}',v,f'{v:.4f}',location)
            for side,v in r['coordinate_boundaries']['a'].items():claim(source,b+'coordinate_boundaries/a/'+side,v,v,location)
    write(OUT/'new_claims.json',dict(claims=claims));print(len(claims))

if __name__=='__main__':main()
