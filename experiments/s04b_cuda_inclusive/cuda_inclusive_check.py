"""Remote-only same-state inclusive GPU checks; never fit or select a model."""
import argparse,hashlib,json,math,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from experiments.s04b_cuda_inclusive.cuda_inclusive import build,InclusiveDeficit,sha
from experiments.s04b_joint_nuisance import model

ROOT=Path(__file__).resolve().parents[2]


def fixture(cpu,library):
    pt=np.array([.2,.7,1.1]);excess=np.array([.1,.3,.8]);times=np.array([.2,.4,.7,1.,1.1,2.])
    grid=dict(r2=np.array([[0.,1.,10.],[3.,5.,2.],[1.,0.,4.]]),coeff=np.array([[.1,.2,.3],[.4,.2,.1],[.2,.5,.3]]),
              area=np.array([.2,.3,.5]),b=np.array([.1,.2,.3]),t=times,w=np.array([.1,.2,.3,.4,.5,.6]))
    class Fixture:
        a=dict(parent_time=pt,parent_excess=excess);m=dict(T0=3.)
        check=lambda self:None
        plan=lambda self,order:grid
        def deficit(self,theta,name,order):
            lag=times[:,None]-pt[None,:]
            h=np.ascontiguousarray(grid['coeff']@np.concatenate([v.T for v in model.temporal(lag,theta[3],theta[4])],axis=1))
            return cpu.integrate(pt,np.exp(.75*math.log(10)*excess),grid['r2'],grid['area'],grid['b'],times,grid['w'],h,theta,3.)
    phase=Fixture();theta=np.array([-2.,.2,.35,math.log(.05),1.3,.4,math.log(10),math.log(2)])
    expected=phase.deficit(theta,'LIplus_inclusive',8);controls=[]
    for workspace in (200,1024**2):
        with InclusiveDeficit(phase,library,workspace) as adapter:
            actual=phase.deficit(theta,'LIplus_inclusive',8);receipt=adapter.receipt()
        error=float(np.max(abs(expected-actual)));assert error<1e-12
        controls.append(dict(workspace_bytes=workspace,max_absolute_error=error,tile_rows=receipt['contexts'][0]['tile_rows']))
    return dict(strict_past_equal_parent_times=True,cpu_reference=expected.tolist(),controls=controls)


def actual_phase(kind,cpu):
    modules=model.archived();G=modules['generator']
    if kind=='S5':
        manifest=json.loads((ROOT/'reproduction/synthetic/input_manifest.json').read_text())
        case=next(v for v in manifest['s04b']['cases'] if v['case_id']=='S5_broad_long_imm_seed410518')
        with np.load(ROOT/'reproduction/synthetic'/case['history']) as z:rows=z['rows'].copy()
        assert hashlib.sha256(rows.tobytes()).hexdigest()==case['rows_sha256']
        name=G.MATCHED_NAMES[case['regime']-4];_,background,eta,ell,psi=G.ROSTER[name]
        law=G.Law(name,case['seed'],background,eta,ell,psi);gm=G.fitting_metadata(law)
        return model.phase_from_rows(rows,gm,30,395,modules,cpu)
    from reproduction.synthetic.s8_moderate import TensorPhase
    from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler
    data=ROOT/'reproduction/synthetic/s8_moderate_total'
    record=next(r for r in json.loads((data/'receipts.json').read_text()) if r['seed']==410821)
    with np.load(data/'410821.npz') as z:rows=z['rows'].copy()
    original=model.phase_from_rows(rows,record['metadata'],30,395,modules,cpu)
    # The reference scheduler's normal immutable arithmetic stays in place.
    scheduler=OrderedChunkScheduler()
    phase=TensorPhase(original.a,original.m,modules,cpu,math.inf,scheduler=scheduler)
    phase._checker_scheduler=scheduler
    return phase


def run(cpu_library,output,kinds):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);library=build(output/'build');cpu=model.Native(cpu_library)
    result=dict(passed=False,scope='Remote same-state objective/all-eight-gradient validation and warm timing; no fit, test scoring or selection.',fixture=fixture(cpu,library),cases={})
    interior=np.array([math.log(.25),.2,.35,math.log(.05),1.3,.4,math.log(15),math.log(5)])
    floor=interior.copy();floor[5]=0
    extreme=np.array([-1.,1.,.8,math.log(.001),2.3,4.,math.log(5),math.log(1/24)])
    states=[floor,interior,extreme]
    for kind in kinds:
        phase=actual_phase(kind,cpu);reference={};cpu_times={}
        try:
            for order in (8,16):
                for i,theta in enumerate(states):
                    tick=time.perf_counter();reference[order,i]=phase.evaluate(theta,'LIplus_inclusive',order);cpu_times[order,i]=time.perf_counter()-tick
            checks=[]
            with InclusiveDeficit(phase,library) as backend:
                for order in (8,16,8):
                    for i,theta in enumerate(states):
                        tick=time.perf_counter();score,g=phase.evaluate(theta,'LIplus_inclusive',order);elapsed=time.perf_counter()-tick
                        expected,eg=reference[order,i];joint_error=abs(score['joint']-expected['joint']);gradient_error=float(np.max(abs(g-eg)))
                        scaled=float(np.max(abs(g-eg)/np.maximum(1.,abs(eg))))
                        assert joint_error<=1e-7 and scaled<=1e-7,(kind,order,i,joint_error,scaled)
                        checks.append(dict(order=order,state_index=i,parameters=theta.tolist(),joint_absolute_error=joint_error,
                          gradient_max_absolute_error=gradient_error,gradient_max_scaled_error=scaled,
                          cpu_score=expected,gpu_score=score,cpu_gradient=eg.tolist(),gpu_gradient=g.tolist(),cpu_seconds=cpu_times[order,i],gpu_seconds=elapsed))
                warm=[]
                for _ in range(3):
                    tick=time.perf_counter();phase.evaluate(interior,'LIplus_inclusive',8);warm.append(time.perf_counter()-tick)
                receipt=backend.receipt()
            tick=time.perf_counter();phase.evaluate(interior,'LIplus_inclusive',8);warm_cpu=time.perf_counter()-tick
            result['cases'][kind]=dict(comparisons=checks,backend=receipt,warm_gpu_seconds=warm,warm_cpu_seconds=warm_cpu,warm_speedup=warm_cpu/float(np.median(warm)))
            print(kind,'checks passed; warm speedup',result['cases'][kind]['warm_speedup'],flush=True)
        finally:
            if hasattr(phase,'_checker_scheduler'):phase._checker_scheduler.close()
    result.update(passed=True,cpu_library_sha256=sha(cpu_library),original_cpu_source_sha256=sha(ROOT/'experiments/s04b_joint_nuisance/attenuation.cpp'),
      objective_source_sha256=sha(ROOT/'experiments/s04b_joint_nuisance/model.py'),checker_sha256=sha(__file__))
    (output/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cpu-library',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cases',default='S8,S5');a=p.parse_args()
    with threadpool_limits(limits=1):run(a.cpu_library,a.output,a.cases.split(','))
