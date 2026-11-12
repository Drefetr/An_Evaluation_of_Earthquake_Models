"""Independent saved-output custody and KKT audit of the concave comparator."""
import hashlib,json,platform
from pathlib import Path
from experiments.s04b_refitted_floor import run
def main():
    cases,pins,work=run.verify_inputs()
    out=run.REPO/'validation/live_results/s04b_concave_20261111'
    reports=[run.read(out/(c['case_id']+'.json')) for c in cases]
    assert all(r['fit']['relative_projected_kkt']<=1e-8 for r in reports)
    s7=[r for r in reports if r['regime']==7];assert len(s7)==20 and all(r['fit']['n']==0 for r in s7)
    summary=run.read(out/'summary.json');v=next(v for v in summary['summary'] if (v['regime'],v['model'],v['gate'])==(7,'LIplus_inclusive','raw'))
    assert abs(v['mean_gain']-5.625500286218216)<1e-9
    receipt=dict(passed=True,checked_histories=80,s7_n_zero=20,max_relative_projected_kkt=max(r['fit']['relative_projected_kkt'] for r in reports),
                 source_sha256={p:run.sha(run.REPO/p) for p in ('experiments/s04b_refitted_floor/run.py','experiments/s04b_completion/audit_concave.py')},
                 pinned_inputs_checked=pins,summary_sha256=run.sha(out/'summary.json'),platform=platform.platform(),python=platform.python_version(),numpy=run.np.__version__,scipy=run.scipy.__version__)
    run.write(out/'audit.json',receipt);print({k:v for k,v in receipt.items() if k not in ('pinned_inputs_checked','source_sha256')})
if __name__=='__main__':main()
