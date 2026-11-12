"""Remote GPU/CPU objective and twelve-gradient controls, plus speed comparison."""
from pathlib import Path
import argparse,hashlib,json,sys,time,platform
import numpy as np
from scipy.optimize._numdiff import approx_derivative
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from experiments.etas_inhibition_benchmark.run_frozen_gpu_20261111 import Region,Background,Model,write
from experiments.etas_inhibition_benchmark.gpu_native import build as gpu_build,Native as GpuNative
from experiments.etas_inhibition_benchmark.native import build as cpu_build,Native as CpuNative

def fixture(parents=3,events=3,power=8):
    rng=np.random.default_rng(20261207);region=Region(np.array([[0.,100.,0.,100.]]));xy=rng.uniform(5,95,size=(parents,2));t=np.linspace(.2,9.,parents)
    query=xy.copy() if parents==events else rng.uniform(5,95,size=(events,2));et=t.copy() if parents==events else np.linspace(.2,9.9,events)
    a=dict(parent_time=t,parent_excess=rng.uniform(0,1,size=parents),parent_xy=xy,parent_fertility=rng.uniform(.3,1,size=parents),parent_exposure_lo=np.zeros(parents),parent_exposure_hi=10-t,event_time=et,event_xy=query)
    model=Model(a,dict(start=0.,end=10.,T0=10.,training_start=0.),Background(xy,region,5))
    x=np.array([-2.,.1,.5,np.log(.1),1.3,np.log(5.),.5,1.7,.2,np.log(20.),np.log(5.),1.]);model.node_setup(x,power)
    return model,x

def run(output):
    gpu_path=gpu_build(ROOT/'build/etas_benchmark_gpu_20261111');cpu_path=cpu_build(ROOT/'build/etas_benchmark_native_20261111'/platform.system());gpu=GpuNative(gpu_path);cpu=CpuNative(cpu_path,threads=2)
    controls=[]
    for eta in (0.,.2):
        model,x=fixture();x[8]=eta;nv,ng=model.objective(x,True);model.native=gpu;gv,gg=model.objective(x,True)
        fd=approx_derivative(lambda p:model.objective(p,True)[0],x,method='3-point').ravel()
        controls.append(dict(eta=eta,objective_error=abs(gv-nv),gradient_error=float(np.max(abs(gg-ng))),finite_difference_error=float(np.max(abs(gg-fd)))))
    model,x=fixture(512,1024,10);nv,ng=model.objective(x,True);model.native=gpu;gv,gg=model.objective(x,True)
    controls.append(dict(case='representative_pair_count',parents=512,events=1024,objective_error=abs(gv-nv),gradient_error=float(np.max(abs(gg-ng)))))
    timings={}
    for label,backend in [('compiled_cpu',cpu),('cuda',gpu)]:
        model.native=backend;model.objective(x,True);samples=[]
        for _ in range(3):
            tick=time.perf_counter();model.objective(x,True);samples.append(time.perf_counter()-tick)
        timings[label]=dict(samples=samples,median=float(np.median(samples)))
    passed=all(c['objective_error']<1e-8 and c['gradient_error']<1e-8 and c.get('finite_difference_error',0)<1e-5 for c in controls)
    sources=[Path(__file__),Path(__file__).with_name('gpu_native.py'),Path(__file__).with_name('gpu_pairs.cu'),Path(__file__).with_name('run_frozen_gpu_20261111.py')]
    report=dict(passed=passed,controls=controls,timings=timings,gpu_speedup=timings['compiled_cpu']['median']/timings['cuda']['median'],source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},gpu_library_sha256=hashlib.sha256(gpu_path.read_bytes()).hexdigest(),cpu_library_sha256=hashlib.sha256(cpu_path.read_bytes()).hexdigest())
    gpu.close();write(output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with threadpool_limits(limits=1):r=run(a.output)
    print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
