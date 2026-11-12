"""Append the checked baseline interval and emit semantic claim additions."""
from pathlib import Path
import argparse,ast,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts import verify_claims as V

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,text):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(re.sub(r'\r+\n','\n',text).replace('\r','\n').encode('utf-8'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=ROOT/'validation/live_results/etas_baseline_uncertainty_20261111/summary.json');p.add_argument('--fragment',type=Path,default=ROOT/'validation/live_results/etas_inhibition_benchmark_accepted_20261111/manuscript/11_epplus_benchmark.tex');a=p.parse_args();source=a.source.resolve();d=json.loads(source.read_bytes())
    if not d['passed'] or set(d['pooled_by_block_days'])!={'90','180','365'}:raise ValueError('incomplete paired baseline authority')
    for relative,expected in d['source_execution_sha256'].items():
        if sha(ROOT/relative)!=expected:raise ValueError('executed audit source changed')
    for rows in d['rows_by_block_days'].values():
        if len(rows)!=3 or any(r['total_absolute_error']>1e-6 for r in rows):raise ValueError('paired contrast total not verified')
    frozen=ROOT/'experiments/methodological_audit/score_uncertainty_cuda_frozen_v2_20261111.py';fn=next(n for n in ast.parse(frozen.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='resample');call=next(n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='quantile');levels=ast.literal_eval(call.args[1])
    output=source.parent/'manuscript';output.mkdir(exist_ok=True);typed=dict(passed=True,authority=source.relative_to(ROOT).as_posix(),authority_sha256=sha(source),pooled=d['pooled_by_block_days'],method=dict(block_days=d['block_days'],replicates=d['replicates'],confidence_percent=100*(levels[1]-levels[0])),postprocessing_source='experiments/etas_inhibition_benchmark/report_baseline_uncertainty.py',postprocessing_source_sha256=sha(Path(__file__)))
    typed_path=output/'typed_values.json';write(typed_path,json.dumps(typed,indent=2)+'\n')
    def interval(days):v=typed['pooled'][days]['ci95_total'];return f"$[{v[0]:.3f},{v[1]:.3f}]$"
    text=f"For this combined excitation improvement, the paired 90-day block calculation in Section~\\ref{{sec:block_score_uncertainty}} gives a 95\\% interval of {interval('90')}~nats ($p={typed['pooled']['90']['paired_sign_permutation_p']:.5f}$). The 180- and 365-day intervals are {interval('180')} and {interval('365')}~nats, with sign-flip values $p={typed['pooled']['180']['paired_sign_permutation_p']:.5f}$ and $p={typed['pooled']['365']['paired_sign_permutation_p']:.5f}$, respectively.\n"
    write(output/'11_epplus_baseline_uncertainty.tex',text)
    marker='% BEGIN EPPLUS BASELINE UNCERTAINTY\n';body=a.fragment.read_text(encoding='utf-8').split(marker)[0].rstrip()+'\n\n';write(a.fragment,body+marker+text+'% END EPPLUS BASELINE UNCERTAINTY\n')
    source_path=typed_path.relative_to(ROOT).as_posix();claims=[]
    def add(key,pointer,display,component):
        value=V.resolve(typed,pointer);c=dict(id='epplus-baseline-uncertainty-20261111-'+key,bundled_source=source_path,source_path=source_path,source_sha256=sha(typed_path),json_pointer=pointer,resolved_source_value=value,value=value,display=display,transformation='decimal rounding to displayed precision',json_value_kind='numeric_scalar',ledger_role='manuscript_binding',final_display_locations=['chapters/11_epplus_benchmark.tex'],component=component,status='source_bound',binding_kind='exact_json_pointer',reconciliation_status='verified_at_declared_granularity')
        if not V.equal_display(V.transformed(value,c,typed),c):raise ValueError('incorrect numeric display '+key)
        if V.numeric_value(display) not in V.manuscript_numbers(a.fragment.read_text()):raise ValueError('semantic display missing from generated fragment '+key)
        claims.append(c)
    for i,days in enumerate(('90','180','365')):
        add('block-days-'+days,'/method/block_days/'+str(i),days,'Baseline-comparison calendar block length in days')
        for j,side in enumerate(('lower','upper')):add(days+'-ci-'+side,'/pooled/'+days+'/ci95_total/'+str(j),f"{typed['pooled'][days]['ci95_total'][j]:.3f}",'Pooled EP+ minus original EP '+days+'-day interval '+side+' endpoint')
        add(days+'-signflip-p','/pooled/'+days+'/paired_sign_permutation_p',f"{typed['pooled'][days]['paired_sign_permutation_p']:.5f}",'Pooled EP+ minus original EP '+days+'-day paired sign-flip p-value')
    add('confidence','/method/confidence_percent','95','Percentile interval confidence level for the same imported resampling procedure')
    write(output/'ledger_claims.json',json.dumps(dict(claims=claims,postprocessed_authority_sha256=sha(typed_path),postprocessing_source_sha256=sha(Path(__file__))),indent=2)+'\n');print(json.dumps(dict(passed=True,claims=len(claims),ledger=str(output/'ledger_claims.json'),fragment=str(a.fragment))))

if __name__=='__main__':main()
