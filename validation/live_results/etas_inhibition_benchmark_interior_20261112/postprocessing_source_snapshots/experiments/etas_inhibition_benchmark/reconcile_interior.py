"""Carry forward baseline statistics only after exact fitted-state identity checks.

This is postprocessing: it performs no fits, likelihood integrations or bootstrap
sampling. Prior accepted authorities remain unchanged. Every carried statistic
names its original authority and the new acceptance to which identity binds it.
"""
from pathlib import Path
import argparse,copy,hashlib,json
ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2,allow_nan=False)+'\n').encode('utf-8'))

def reconcile(new):
    old=ROOT/'validation/live_results/etas_inhibition_benchmark_accepted_20261111'
    uncertainty=ROOT/'validation/live_results/etas_baseline_uncertainty_20261111/summary.json'
    ns,os=read(new/'summary.json'),read(old/'summary.json');audit=read(new/'interior_start_audit.json')
    if not ns['passed'] or not ns['all_final_power_interior_start_coverage_passed'] or not audit['passed'] or audit['summary_sha256']!=sha(new/'summary.json'):raise ValueError('new positive-start acceptance is not independently audited')
    if not os['passed']:raise ValueError('old authority incomplete')
    rows=[]
    keys=('parameter_names','bounds','n_train','n_test','background_weights','background_bandwidth_km','background_floor','declustering_initialization_sha256','spatial','inhibition','source_cache_sha256')
    for i in range(3):
        rel=Path(f'california_fold_{i}')/'result.json';a,b=read(new/rel),read(old/rel)
        checks={key:a[key]==b[key] for key in keys}
        checks['all_null_parameter_coordinates']=a['null']['selected']['parameters']==b['null']['selected']['parameters']
        checks['all_heldout_null_components']=[r['null'] for r in a['test_scores']]==[r['null'] for r in b['test_scores']]
        if not all(checks.values()):raise ValueError(('baseline fit changed; fresh block integration required',str(rel),checks))
        rows.append(dict(case=a['case'],checks=checks,new_result_sha256=sha(new/rel),prior_result_sha256=sha(old/rel),maximum_null_parameter_change=0.,maximum_test_null_component_change=0.))
    c=read(old/'baseline_comparison.json');u=read(uncertainty)
    if not c['passed'] or c['accepted_summary_sha256']!=sha(old/'summary.json') or not u['passed'] or u['accepted_summary_sha256']!=sha(old/'summary.json') or u['baseline_comparison_sha256']!=sha(old/'baseline_comparison.json'):raise ValueError('prior baseline statistics lineage mismatch')
    for path,expected in u['source_execution_sha256'].items():
        if sha(ROOT/path)!=expected:raise ValueError('original analytic uncertainty source changed '+path)
    lineage=dict(statistics_recomputed=False,reason='All baseline coordinates, background weights/settings, source caches and saved held-out component vectors are exactly identical. The original paired block scores and resampling authority therefore apply without rerunning computation.',prior_accepted_summary=(old/'summary.json').relative_to(ROOT).as_posix(),prior_accepted_summary_sha256=sha(old/'summary.json'),prior_baseline_comparison=(old/'baseline_comparison.json').relative_to(ROOT).as_posix(),prior_baseline_comparison_sha256=sha(old/'baseline_comparison.json'),prior_uncertainty=uncertainty.relative_to(ROOT).as_posix(),prior_uncertainty_sha256=sha(uncertainty),new_accepted_summary=(new/'summary.json').relative_to(ROOT).as_posix(),new_accepted_summary_sha256=sha(new/'summary.json'),identity_rows=rows,postprocessing_source=Path(__file__).relative_to(ROOT).as_posix(),postprocessing_source_sha256=sha(Path(__file__)))
    nc=copy.deepcopy(c);nc.update(schema='epplus_vs_original_ep_checked_scores_identity_reconciled_v2',accepted_summary_sha256=sha(new/'summary.json'),identity_reconciliation=lineage,comparison='Combined magnitude scaling, probability-weighted background, joint fitting and spatial normalization versus archived EP. Archived EP normalizes each parent kernel on the observation rectangle; the new model normalizes on the full plane and retains regional offspring leakage. Identical history, fertility and mark measures were verified in the prior comparison and exact unchanged baseline identities are verified here.')
    write(new/'baseline_comparison.json',nc)
    nu=copy.deepcopy(u);nu.update(schema='paired_epplus_vs_original_ep_block_uncertainty_identity_reconciled_v2',accepted_summary_sha256=sha(new/'summary.json'),baseline_comparison_sha256=sha(new/'baseline_comparison.json'),identity_reconciliation=lineage)
    write(new/'baseline_uncertainty'/'summary.json',nu)
    receipt=dict(passed=True,baseline_comparison=new.joinpath('baseline_comparison.json').relative_to(ROOT).as_posix(),baseline_comparison_sha256=sha(new/'baseline_comparison.json'),block_uncertainty=new.joinpath('baseline_uncertainty/summary.json').relative_to(ROOT).as_posix(),block_uncertainty_sha256=sha(new/'baseline_uncertainty/summary.json'),lineage=lineage)
    write(new/'baseline_identity_reconciliation.json',receipt);return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,required=True);a=p.parse_args();print(json.dumps(reconcile(a.directory.resolve())))
