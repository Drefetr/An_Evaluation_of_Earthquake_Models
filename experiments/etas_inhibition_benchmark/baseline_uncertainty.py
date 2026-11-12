"""Paired block uncertainty for accepted EP+ versus archived EP; no fitting/GPU.

Uninhibited event intensities are evaluated at saved training estimates.
Regional trigger exposure and background exposure are analytic per block.
"""
from pathlib import Path
import argparse,hashlib,io,json,math,sys,time
import numpy as np
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from reproduction.score_replay.core import Inputs
from experiments.etas_inhibition_benchmark.run_frozen_gpu_20261111 import Region,Background,Model,inputs
from experiments.methodological_audit.score_uncertainty_cuda_frozen_v2_20261111 import edges,grouped,resample,pooled,temporal_bins,rectangle_mass

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2,allow_nan=False)+'\n').encode('utf-8'))

def new_exposure(model,x,block_edges):
    a,d,n,lc,p,ls,alpha,q=x[:8];c=math.exp(lc);mass=model.region.mass(model.radii,np.exp(ls+alpha*model.dm),q)[0];result=[]
    for lo,hi in zip(block_edges[:-1],block_edges[1:]):
        u=np.maximum(lo-model.pt,0);v=np.maximum(hi-model.pt,0)
        J=np.exp((1-p)*np.log1p(u/c))*(-np.expm1((1-p)*np.log1p((v-u)/(c+u))))
        center=(lo+hi)/model.m['T0']-1;z=d*(hi-lo)/model.m['T0'];s=1+z*z/6+z**4/120 if abs(z)<1e-5 else np.sinh(z)/z
        B=np.exp(a+d*center)*(hi-lo)*s;result.append(B+n*(model.kp*mass)@J)
    return np.asarray(result)

def run(output):
    begin=time.perf_counter();accepted=ROOT/'validation/live_results/etas_inhibition_benchmark_accepted_20261111';comparison=json.loads((accepted/'baseline_comparison.json').read_bytes());reference={r['case']:r for r in comparison['rows']}
    if not comparison['passed'] or sha(accepted/'summary.json')!=comparison['accepted_summary_sha256']:raise ValueError('unaccepted/mismatched baseline comparison')
    folder=ROOT/'reproduction/score_replay/california_benchmark';registry=json.loads((folder/'registry.json').read_bytes());roster={r['case']:r for r in registry['rows'] if r['phase']=='test' and r['procedure_key']=='EP'}
    files=[Path(__file__),ROOT/'experiments/etas_inhibition_benchmark/run_frozen_gpu_20261111.py',ROOT/'experiments/methodological_audit/score_uncertainty_cuda_frozen_v2_20261111.py',ROOT/'reproduction/score_replay/core.py'];pins={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    prepared=[]
    for case,row in sorted(roster.items()):
        state=Inputs(folder).json(row['state'])
        with np.load(io.BytesIO(Inputs(folder).read(row['cache'])),allow_pickle=False) as z:old={k:z[k].copy() for k in z.files if k!='metadata_json'};om=json.loads(str(z['metadata_json'].item()))
        train,tm,test,vm,_=inputs(case);fit=json.loads((accepted/case/'result.json').read_bytes());region=Region(train['rectangles']);bg=Background(train['event_xy'],region,tm['kde_bandwidth'],np.asarray(fit['background_weights']));model=Model(test,vm,bg)
        if model.native is not None:raise ValueError('this audit must use CPU reference formulas')
        for key in ('parent_time','parent_xy','parent_fertility','event_time','event_xy','rectangles'):
            if not np.array_equal(test[key],old[key]):raise ValueError('history mismatch '+case+' '+key)
        if any(vm[k]!=om[k] for k in ('start','end','T0','beta')):raise ValueError('forecast/mark measure mismatch')
        x=np.asarray(fit['null']['selected']['parameters']);lam,_=model.base_values(model.events,x);logpoint=np.log(lam)
        op=np.asarray(state['parameters']);s,q=np.exp(op[5]),op[6];M=rectangle_mass(old['parent_xy'],old['rectangles'],s,q);norm=M*np.pi*s*s/(q-1)
        r2=((old['event_xy'][:,None,:]-old['parent_xy'][None,:,:])**2).sum(axis=2);old['event_parent_density']=np.exp(-q*np.log1p(r2/s**2))/norm
        prepared.append((case,model,x,logpoint,old,om,op))
    report=dict(schema='paired_epplus_vs_original_ep_block_uncertainty_v1',passed=False,source_execution_sha256=pins,accepted_summary_sha256=sha(accepted/'summary.json'),baseline_comparison_sha256=sha(accepted/'baseline_comparison.json'),replicates=49999,block_days=[90,180,365],rows_by_block_days={},pooled_by_block_days={})
    for days in report['block_days']:
        rows=[]
        for case,model,x,logpoint,old,om,op in prepared:
            e=edges(om['start'],om['end'],days);newP=grouped(model.a['event_time'],logpoint,e);newE=new_exposure(model,x,e);oldP,oldE,_=temporal_bins(old,om,op,e);dp=newP-oldP;de=newE-oldE;score=dp-de;expected=reference[case]['gain'];error=abs(float(score.sum())-expected)
            if error>1e-6:raise ArithmeticError(('paired total does not match accepted comparison',case,days,float(score.sum()),expected))
            rows.append(dict(contrast='CA_EPplus_minus_original_EP',case=case,block_days=days,edges=e.tolist(),delta_P=dp.tolist(),delta_E=de.tolist(),block_scores=score.tolist(),expected_gain=expected,total_absolute_error=error,summary=resample(score)))
        report['rows_by_block_days'][str(days)]=rows;report['pooled_by_block_days'][str(days)]=pooled(rows)
        if abs(report['pooled_by_block_days'][str(days)]['total']-comparison['total_gain'])>1e-6:raise ArithmeticError('pooled total mismatch')
    for relative,expected in pins.items():
        if sha(ROOT/relative)!=expected:raise ValueError('audit source changed')
    report.update(passed=True,elapsed_seconds=time.perf_counter()-begin);write(output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with threadpool_limits(limits=1):r=run(a.output)
    print(json.dumps(dict(passed=r['passed'],elapsed_seconds=r['elapsed_seconds'],pooled=r['pooled_by_block_days'])))
