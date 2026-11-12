"""One-worker S8 CUDA training epoch; original CPU selection audits and tests."""
import argparse,hashlib,json,os,shutil,time
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from reproduction.synthetic import s8_moderate as science
from experiments.s04b_cuda_inclusive.cuda_inclusive import InclusiveDeficit,sha
from experiments.s04b_completion.recover import native_library
from experiments.s04b_joint_nuisance import model,fit,checkpoint
from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler

def run(args):
    out=science.OUT;out.mkdir(parents=True,exist_ok=True)
    controls=json.loads(args.controls.read_text());assert controls['passed']
    for case in controls['cases'].values():
        assert case['backend']['library_sha256']==sha(args.library)
        assert case['backend']['adapter_sha256']==sha(Path(__file__).parent.parent/'s04b_cuda_inclusive/cuda_inclusive.py')
        assert case['backend']['source_sha256']==sha(Path(__file__).parent.parent/'s04b_cuda_inclusive/cuda_inclusive.cu')
    assert controls['cpu_library_sha256']==sha(native_library())
    source_paths=[Path(__file__),Path(science.__file__),Path(model.__file__),Path(fit.__file__),Path(__file__).parent.parent/'s04b_cuda_inclusive/cuda_inclusive.py',Path(__file__).parent.parent/'s04b_cuda_inclusive/cuda_inclusive.cu',Path(__file__).with_name('cuda_immigrant.cu')]
    pins={str(p):sha(p) for p in source_paths};snap=out/'source';snap.mkdir(exist_ok=True)
    for path in source_paths:shutil.copy2(path,snap/path.name)
    checkpoint.write(out/'epoch.json',dict(provider='CUDA total training deficit; original CPU selected checks and held-out scoring',source_sha256=pins,controls_sha256=sha(args.controls),library_sha256=sha(args.library),workers=1,threads=2))
    original_phase=science.TensorPhase;original_check=science.fit.fine_check;active={};all_backends=[]

    def compare(gpu,cpu):
        delta=np.abs(np.asarray(gpu)-np.asarray(cpu));scale=float(np.max(delta/np.maximum(1.,np.abs(cpu))))
        assert scale<=1e-7,'S8 CPU/CUDA gradient mismatch'
        return dict(max_absolute_error=float(np.max(delta)),max_scaled_error=scale)

    class GPUPhase(original_phase):
        def __init__(self,*values,**kwargs):
            super().__init__(*values,**kwargs);self.cuda_backend=None
            if self.m['start']==30:
                backend=InclusiveDeficit(self,args.library);self.cuda_backend=backend;all_backends.append(backend)
                def deficit(theta,name,order):
                    answer=backend.deficit(theta,name,order)
                    if name=='LIplus_inclusive' and theta[5]>0 and not (out/'gpu_healthy.json').exists():
                        cpu=backend.original(theta,name,order);paired=compare(answer,cpu)
                        checkpoint.write(out/'gpu_healthy.json',dict(passed=True,seed=active['seed'],order=order,parameters=np.asarray(theta).tolist(),comparison=paired,backend=backend.receipt()))
                    return answer
                self.deficit=deficit

    def selected_check(phase,name,arm,protocol):
        physical=phase.phase;backend=getattr(physical,'cuda_backend',None)
        if name!='LIplus_inclusive' or backend is None:return original_check(phase,name,arm,protocol)
        theta=arm['selected']['parameters'];orders=(phase.order,2*phase.order)
        gpu={o:physical.evaluate(theta,name,o) for o in orders};installed=physical.deficit;physical.deficit=backend.original
        try:
            cpu={o:physical.evaluate(theta,name,o) for o in orders};checks=[]
            for order in orders:
                gs,gg=gpu[order];cs,cg=cpu[order];error=abs(gs['joint']-cs['joint']);assert error<=1e-7
                checks.append(dict(order=order,cpu_score=cs,gpu_score=gs,cpu_gradient=cg.tolist(),gpu_gradient=gg.tolist(),score_error=error,gradient_comparison=compare(gg,cg)))
            result=original_check(phase,name,arm,protocol);result['cpu_cuda_selected_checks']=checks
            checkpoint.write(out/str(active['seed'])/'cuda_selected_checks.json',dict(passed=True,checks=checks,backend=backend.receipt()))
            if result['absolute_joint_delta']<=.01:
                physical.deficit=backend.original;backend.close();physical.cuda_backend=None
            else:physical.deficit=installed
            return result
        except BaseException:
            physical.deficit=installed;raise

    def audit_reuse(seed):
        folder=out/str(seed);value=science.read(folder/'result.json');record=next(r for r in science.read(science.DATA/'receipts.json') if r['seed']==seed)
        with np.load(science.DATA/(str(seed)+'.npz'),allow_pickle=False) as z:rows=z['rows'].copy()
        modules=model.archived();native=model.Native(native_library());name='LIplus_inclusive';theta=value['fits'][name]['selected']['parameters'];checks=[]
        with threadpool_limits(limits=2),OrderedChunkScheduler() as scheduler:
            for phase_name,start,end in [('train',30,395),('test',395,760)]:
                base=model.phase_from_rows(rows,record['metadata'],start,end,modules,native)
                phase=original_phase(base.a,base.m,modules,native,float('inf'),scheduler=scheduler)
                orders=(value['training_checks'][name]['fit_order'],2*value['training_checks'][name]['fit_order']) if phase_name=='train' else (value['test_order'],)
                for order in orders:
                    score,g=phase.evaluate(theta,name,order)
                    expected=value['inhibited_test'] if phase_name=='test' else value['training_checks'][name]['coarse' if order==orders[0] else 'fine']
                    error=abs(score['joint']-expected['joint']);assert error<=1e-7,'Original S8 state replay differs'
                    checks.append(dict(phase=phase_name,order=order,score=score,gradient=g.tolist(),joint_error=error))
        checkpoint.write(folder/'fresh_cpu_replay.json',dict(passed=True,original_result_sha256=sha(folder/'result.json'),input_sha256=sha(science.DATA/(str(seed)+'.npz')),checks=checks))

    science.TensorPhase=GPUPhase;science.fit.fine_check=selected_check;codes=[]
    try:
        for seed in science.read(science.DATA/'protocol.json')['seeds']:
            active['seed']=seed
            try:
                code=science.fit_seed(seed,args.resume_from)
                if code==0 and (out/str(seed)/'reuse.json').exists():audit_reuse(seed)
            except BaseException as exc:
                code=1;checkpoint.write(out/(str(seed)+'_failure.json'),dict(seed=seed,error_type=type(exc).__name__,error=str(exc)))
                print(json.dumps(dict(seed=seed,error_type=type(exc).__name__,error=str(exc))),flush=True)
            finally:
                for backend in all_backends:
                    backend.phase.deficit=backend.original;backend.close()
                all_backends.clear()
            codes.append(code);print(json.dumps(dict(seed=seed,returncode=code)),flush=True)
        assert all(sha(Path(path))==pin for path,pin in pins.items()),'S8 execution sources changed'
        if not any(codes):science.summarize()
        checkpoint.write(out/'epoch_result.json',dict(passed=not any(codes),returncodes=codes,source_sha256=pins))
        return int(any(codes))
    finally:
        science.TensorPhase=original_phase;science.fit.fine_check=original_check

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--controls',type=Path,required=True);p.add_argument('--resume-from',type=Path,required=True)
    raise SystemExit(run(p.parse_args()))
