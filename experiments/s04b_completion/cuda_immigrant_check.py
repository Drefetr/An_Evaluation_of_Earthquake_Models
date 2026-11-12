"""Remote-only bounded same-state controls and timings; no optimization."""
import argparse,json,math,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from experiments.s04b_completion.cuda_immigrant import build,ImmigrantDeficit,sha
from experiments.s04b_joint_nuisance import model

ROOT=Path(__file__).resolve().parents[2]


def run(cpu_library,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    gpu_library=build(output/'build');cpu=model.Native(cpu_library)
    pt=np.array([.2,.7,1.1]);excess=np.array([.1,.3,.8])
    grid=dict(r2=np.array([[0.,1.,10.],[3.,5.,2.],[1.,0.,4.]]),area=np.array([.2,.3,.5]),
              b=np.array([.1,.2,.3]),t=np.array([.2,.4,.7,1.,1.1,2.]),w=np.array([.1,.2,.3,.4,.5,.6]))
    class Fixture:
        a=dict(parent_time=pt,parent_excess=excess);m=dict(T0=3.)
        check=lambda self:None
        plan=lambda self,order:grid
        def deficit(self,theta,name,order):
            return cpu.integrate(pt,np.exp(.75*math.log(10)*excess),grid['r2'],grid['area'],grid['b'],grid['t'],grid['w'],None,theta,3.)
    phase=Fixture();theta=np.array([-2.,.2,.35,math.log(.05),1.3,.4,math.log(10),math.log(2)])
    fixture_expected=phase.deficit(theta,'LIplus_immigrant',8)
    with ImmigrantDeficit(phase,gpu_library):fixture_actual=phase.deficit(theta,'LIplus_immigrant',8)
    fixture_error=float(np.max(abs(fixture_actual-fixture_expected)))
    assert fixture_error<1e-12

    manifest=json.loads((ROOT/'reproduction/synthetic/input_manifest.json').read_text())
    case=next(v for v in manifest['s04b']['cases'] if v['case_id']=='S5_broad_long_imm_seed410518')
    with np.load(ROOT/'reproduction/synthetic'/case['history']) as z:rows=z['rows'].copy()
    assert __import__('hashlib').sha256(rows.tobytes()).hexdigest()==case['rows_sha256']
    modules=model.archived();G=modules['generator'];name=G.MATCHED_NAMES[case['regime']-4]
    _,background,eta,ell,psi=G.ROSTER[name];law=G.Law(name,case['seed'],background,eta,ell,psi)
    phase=model.phase_from_rows(rows,G.fitting_metadata(law),30,395,modules,cpu)
    # Actual capped Powell state and nearby/interior/null states; all eight
    # coordinates retain their original scientific interpretation.
    capped=np.array([-6.771909233336379e-7,1.9710617868132125,.5357150822094755,
        -1.6873743921348425,1.2374637435759526,3.9999999346747863,2.79520988984741,4.707680179188116])
    interior=capped.copy();interior[[0,1,2,3,4,5,6,7]]=[-2.,.3,.2,math.log(.05),1.7,.5,math.log(30),math.log(5)]
    floor=interior.copy();floor[5]=0
    states=[capped,interior,floor];cpu_values=[];cpu_seconds=[]
    for state in states:
        tick=time.perf_counter();cpu_values.append(phase.evaluate(state,'LIplus_immigrant',8));cpu_seconds.append(time.perf_counter()-tick)
    comparisons=[];gpu_seconds=[]
    with ImmigrantDeficit(phase,gpu_library) as backend:
        for i,state in enumerate(states):
            tick=time.perf_counter();actual,g=phase.evaluate(state,'LIplus_immigrant',8);elapsed=time.perf_counter()-tick
            gpu_seconds.append(elapsed);expected,eg=cpu_values[i]
            score_error=abs(actual['joint']-expected['joint'])
            gradient_error=float(np.max(abs(g-eg)));scaled=float(np.max(abs(g-eg)/np.maximum(1.,abs(eg))))
            assert score_error<=1e-7 and scaled<=1e-7
            comparisons.append(dict(state_index=i,parameters=state.tolist(),cpu_score=expected,gpu_score=actual,
                cpu_gradient=eg.tolist(),gpu_gradient=g.tolist(),joint_absolute_error=score_error,
                gradient_max_absolute_error=gradient_error,gradient_max_scaled_error=scaled,
                cpu_seconds=cpu_seconds[i],gpu_seconds=elapsed))
        warm=[]
        for i in range(3):
            tick=time.perf_counter();phase.evaluate(capped,'LIplus_immigrant',8);warm.append(time.perf_counter()-tick)
        receipt=backend.receipt()
    # Exclude initial spatial-plan construction from the speed comparison.
    tick=time.perf_counter();phase.evaluate(capped,'LIplus_immigrant',8);warm_cpu=time.perf_counter()-tick
    result=dict(passed=True,case_id=case['case_id'],scope='Same-state score/all-eight-gradient controls and warm evaluation timings only; no fit or test selection.',
        fixture=dict(strict_past_equal_parent_times=True,max_absolute_error=fixture_error,expected=fixture_expected.tolist(),actual=fixture_actual.tolist()),
        comparisons=comparisons,warm_cpu_seconds=warm_cpu,warm_gpu_seconds=warm,
        warm_speedup=warm_cpu/float(np.median(warm)),backend=receipt,
        cpu_library=str(cpu_library),cpu_library_sha256=sha(cpu_library),
        original_cpu_source_sha256=sha(ROOT/'experiments/s04b_joint_nuisance/attenuation.cpp'),
        objective_source_sha256=sha(ROOT/'experiments/s04b_joint_nuisance/model.py'),checker_sha256=sha(__file__))
    (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=True,warm_speedup=result['warm_speedup'],warm_cpu_seconds=warm_cpu,
                         warm_gpu_seconds=warm,max_joint_error=max(v['joint_absolute_error'] for v in comparisons)),indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cpu-library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with threadpool_limits(limits=1):run(a.cpu_library,a.output)
