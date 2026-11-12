"""Validated immigrant-only CUDA training; original CPU selected/test checks.

Provider is fixed before fitting. Only the LI+ immigrant training deficit uses
CUDA. Other models and every held-out score use the original CPU evaluator.
"""
import argparse,hashlib,json,math,os,time
from pathlib import Path
import numpy as np
from experiments.s04b_completion import recover
from experiments.s04b_completion.cuda_immigrant import ImmigrantDeficit,sha
from experiments.s04b_joint_nuisance import checkpoint

def run(args):
    root=args.output_root.resolve();case_out=root/'recovery'/args.case_id
    controls=json.loads(args.controls.read_text());assert controls['passed']
    assert controls['backend']['library_sha256']==sha(args.gpu_library)
    assert controls['backend']['source_sha256']==sha(Path(__file__).with_name('cuda_immigrant.cu'))
    assert controls['backend']['adapter_sha256']==sha(Path(__file__).with_name('cuda_immigrant.py'))
    assert controls['cpu_library_sha256']==sha(recover.native_library(root))
    backends=[];holder={};selected_checks=[]
    original_runner=recover.driver.runner_with_scheduler
    original_recovery=recover.Recovery

    def paired(gpu,cpu):
        error=float(np.max(np.abs(np.asarray(gpu)-np.asarray(cpu))))
        scaled=float(np.max(np.abs(np.asarray(gpu)-np.asarray(cpu))/np.maximum(1.,np.abs(cpu))))
        assert scaled<=1e-7,'CPU/CUDA deficit mismatch'
        return dict(max_absolute_error=error,max_scaled_error=scaled)

    def runner(scheduler):
        value=original_runner(scheduler);factory=value.model.phase_from_rows
        def phase_factory(rows,gm,start,end,modules,native,deadline):
            phase=factory(rows,gm,start,end,modules,native,deadline)
            if (start,end)==(30,395):
                backend=ImmigrantDeficit(phase,args.gpu_library);backends.append(backend)
                def deficit(theta,name,order):
                    result=backend.deficit(theta,name,order)
                    adapter=holder.get('adapter')
                    if name=='LIplus_immigrant' and adapter is not None and adapter.callback is not None and not (case_out/'gpu_healthy.json').exists():
                        cpu=backend.original(theta,name,order);comparison=paired(result,cpu)
                        context={k:adapter.callback[k] for k in ('model','start_index','method','callback_index')}
                        checkpoint.write(case_out/'gpu_healthy.json',dict(passed=True,parameters=np.asarray(theta).tolist(),order=order,comparison=comparison,optimizer_context=context,backend=backend.receipt()))
                    return result
                phase.deficit=deficit
            return phase
        value.model.phase_from_rows=phase_factory;return value

    class CUDARecovery(original_recovery):
        def __init__(self,*values,**kwargs):
            super().__init__(*values,**kwargs);holder['adapter']=self
        def fine_check(self,phase,name,arm,science):
            if name!='LIplus_immigrant':return super().fine_check(phase,name,arm,science)
            actual=phase._phase;backend=next(b for b in backends if b.phase is actual)
            theta=arm['selected']['parameters']
            gpu={o:phase.evaluate(theta,name,o) for o in (8,16)}
            installed=actual.deficit;actual.deficit=backend.original
            try:
                cpu={o:phase.evaluate(theta,name,o) for o in (8,16)}
                checks=[]
                for order in (8,16):
                    gs,gg=gpu[order];cs,cg=cpu[order]
                    score_error=abs(gs['joint']-cs['joint']);grad=paired(gg,cg)
                    assert score_error<=1e-7,'CPU/CUDA selected score mismatch'
                    checks.append(dict(order=order,cpu_score=cs,gpu_score=gs,cpu_gradient=cg.tolist(),gpu_gradient=gg.tolist(),score_absolute_error=score_error,gradient_comparison=grad))
                selected_checks.extend(checks)
                result=super().fine_check(phase,name,arm,science)
                result['cpu_cuda_selected_checks']=checks
                return result
            finally:actual.deficit=installed

    recover.driver.runner_with_scheduler=runner;recover.Recovery=CUDARecovery
    try:
        code=recover.run(args.case_id,args.wall_seconds,output_root=root,saved_evidence=args.saved_evidence,resume_from=args.resume_from)
        receipts=[b.receipt() for b in backends]
        output=dict(passed=code==0,controls_sha256=sha(args.controls),launcher_sha256=sha(__file__),provider='CUDA LIplus_immigrant training deficit; original CPU selected validation and every test score',backends=receipts,selected_checks=selected_checks)
        checkpoint.write(case_out/'cuda_provider.json',output)
        return code
    finally:
        for backend in backends:
            backend.phase.deficit=backend.original
            backend.close()
        recover.driver.runner_with_scheduler=original_runner;recover.Recovery=original_recovery

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case-id',required=True);p.add_argument('--wall-seconds',type=float,default=7200)
    p.add_argument('--output-root',type=Path,required=True);p.add_argument('--saved-evidence',type=Path,required=True);p.add_argument('--resume-from',type=Path,required=True)
    p.add_argument('--gpu-library',type=Path,required=True);p.add_argument('--controls',type=Path,required=True)
    raise SystemExit(run(p.parse_args()))
