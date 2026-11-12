"""Prospective CUDA training providers, KKT continuation, CPU final scoring."""
import argparse,copy,json,math,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from experiments.s04b_completion import recover
from experiments.s04b_completion.cuda_immigrant import ImmigrantDeficit,sha
from experiments.s04b_cuda_inclusive.cuda_inclusive import InclusiveDeficit
from experiments.s04b_joint_nuisance import fit,checkpoint

def run(args):
    root=args.output_root.resolve();case_out=root/'recovery'/args.case_id
    ic=json.loads(args.immigrant_controls.read_text());tc=json.loads(args.inclusive_controls.read_text())
    assert ic['passed'] and tc['passed']
    assert ic['backend']['library_sha256']==sha(args.immigrant_library)
    assert ic['backend']['adapter_sha256']==sha(Path(__file__).with_name('cuda_immigrant.py'))
    assert ic['backend']['source_sha256']==sha(Path(__file__).with_name('cuda_immigrant.cu'))
    for value in tc['cases'].values():
        assert value['backend']['library_sha256']==sha(args.inclusive_library)
        assert value['backend']['adapter_sha256']==sha(Path(__file__).parent.parent/'s04b_cuda_inclusive/cuda_inclusive.py')
        assert value['backend']['source_sha256']==sha(Path(__file__).parent.parent/'s04b_cuda_inclusive/cuda_inclusive.cu')
        assert value['backend']['chronology_dependency_sha256']==ic['backend']['source_sha256']
    assert ic['cpu_library_sha256']==tc['cpu_library_sha256']==sha(recover.native_library(root))
    baseline=recover.Recovery;receipts=[];polish_audits=[]
    def compare(gpu,cpu):
        delta=np.abs(np.asarray(gpu)-np.asarray(cpu));scaled=float(np.max(delta/np.maximum(1.,np.abs(cpu))))
        assert scaled<=1e-7,'CPU/CUDA mismatch'
        return dict(max_absolute_error=float(np.max(delta)),max_scaled_error=scaled)

    class JointRecovery(baseline):
        def gpu_cpu_checks(self,phase,name,theta,backend):
            actual=phase._phase;gpu={o:phase.evaluate(theta,name,o) for o in (8,16)}
            installed=actual.deficit;actual.deficit=backend.original
            try:
                cpu={o:phase.evaluate(theta,name,o) for o in (8,16)}
                checks=[]
                for order in (8,16):
                    gs,gg=gpu[order];cs,cg=cpu[order];error=abs(gs['joint']-cs['joint']);assert error<=1e-7
                    checks.append(dict(order=order,cpu_score=cs,gpu_score=gs,cpu_gradient=cg.tolist(),gpu_gradient=gg.tolist(),score_error=error,gradient_comparison=compare(gg,cg)))
                return checks,cpu
            finally:actual.deficit=installed

        def polish(self,phase,arm,science,checkpoint_fn,backend):
            name='LIplus_immigrant';box=fit.bounds(science,name)
            powell=next(r for r in reversed(arm['records']) if r['start_index']==5 and r['method']=='Powell' and r.get('success'))
            x=np.asarray(powell['parameters']);options=dict(maxiter=2000,ftol=1e-14,gtol=2e-6,maxls=200)
            for continuation in range(5):
                initial=x.copy();count=0
                record=dict(start_index=5,method='L-BFGS-B',continuation='post-Powell KKT polish',continuation_index=continuation,initial_parameters=initial.tolist(),options=options)
                checkpoint_fn(dict(event='attempt_start',model=name,**record))
                self.optimizer_calls.append((name,5,'L-BFGS-B-polish-'+str(continuation)))
                self.log('optimizer_start',model=name,**record)
                def objective(theta):
                    nonlocal count
                    count+=1;assert self.callback is None
                    self.callback=dict(phase=phase,model=name,start_index=5,method='L-BFGS-B',callback_index=count,theta=np.asarray(theta).tolist())
                    try:
                        score,g=phase.evaluate(theta,name,8);return score['nll'],g
                    finally:self.callback=None
                started=time.monotonic();result=minimize(objective,x,method='L-BFGS-B',jac=True,bounds=box,options=options)
                x=np.clip(np.asarray(result.x),np.asarray(box)[:,0],np.asarray(box)[:,1])
                checks,cpu=self.gpu_cpu_checks(phase,name,x,backend)
                norms={str(o):float(np.max(np.abs(fit.projected_gradient(x,cpu[o][1],box)))) for o in (8,16)}
                passed=all(v<=2e-6 for v in norms.values())
                score,g=phase.evaluate(x,name,8)
                record.update(status='returned',success=passed,solver_success=bool(result.success),solver_status=int(result.status),message=str(result.message),nfev=int(result.nfev),nit=int(result.nit),parameters=x.tolist(),returned_parameters=x.tolist(),returned_nll=float(result.fun),fresh_score=score,gradient=g.tolist(),fresh_nll_delta=abs(score['nll']-float(result.fun)),projected_gradient=fit.projected_gradient(x,g,box).tolist(),boundaries=fit.boundary(x,box),finite_feasible=True,CPU_projected_kkt=norms,wall_seconds=time.monotonic()-started)
                arm['records'].append(record);checkpoint_fn(dict(event='attempt_end',model=name,**record))
                self.log('optimizer_end',model=name,start_index=5,method='L-BFGS-B',continuation_index=continuation,returned=True,callback_attempts=count,callback_returns=count)
                audit=dict(continuation_index=continuation,passed=passed,CPU_projected_kkt=norms,checks=checks,record=record);polish_audits.append(audit)
                checkpoint.write(case_out/'start5_polish.json',dict(passed=passed,iterations=polish_audits,original_powell_record=powell))
                if passed:break
            assert passed,'S5 start5 KKT continuation did not reach 2e-6 on both CPU rules'
            index=next(i for i,c in enumerate(arm['candidates']) if c['start_index']==5)
            old=arm['candidates'][index]
            arm['candidates'][index]=dict(state_index=old['state_index'],kind='optimizer',start_index=5,parameters=x.tolist(),score=score,gradient=g.tolist(),polish_predecessor=old)
            chosen=min(arm['candidates'],key=lambda v:(v['score']['nll'],v['kind']=='optimizer',v['start_index']))
            arm.update(selected=chosen,selected_state_index=chosen['state_index'])
            floor=arm['candidates'][0]['score']['nll']
            arm['null_search_gaps']=[dict(state_index=c['state_index'],train_nll_improvement=floor-c['score']['nll']) for c in arm['candidates'] if c['parameters'][5]==0 and floor-c['score']['nll']>1e-9]
            return arm

        def fit_arm(self,phase,name,science,eligible,checkpoint_fn):
            if name not in ('LIplus_immigrant','LIplus_inclusive'):return super().fit_arm(phase,name,science,eligible,checkpoint_fn)
            actual=phase._phase
            cls,library=(ImmigrantDeficit,args.immigrant_library) if name=='LIplus_immigrant' else (InclusiveDeficit,args.inclusive_library)
            backend=cls(actual,library)
            def deficit(theta,model,order):
                answer=backend.deficit(theta,model,order)
                if model==name and self.callback is not None and not (case_out/'gpu_healthy.json').exists():
                    paired=compare(answer,backend.original(theta,model,order))
                    checkpoint.write(case_out/'gpu_healthy.json',dict(passed=True,model=name,order=order,parameters=np.asarray(theta).tolist(),comparison=paired,backend=backend.receipt()))
                return answer
            actual.deficit=deficit
            try:
                arm=super().fit_arm(phase,name,science,eligible,checkpoint_fn)
                if name=='LIplus_immigrant' and arm['passed']:arm=self.polish(phase,arm,science,checkpoint_fn,backend)
                if arm['passed']:
                    checks,_=self.gpu_cpu_checks(phase,name,arm['selected']['parameters'],backend)
                    arm['cpu_cuda_selected_checks']=checks
                receipts.append(backend.receipt());return arm
            finally:
                actual.deficit=backend.original;backend.close()

        def fine_check(self,phase,name,arm,science):
            if name in ('LIplus_immigrant','LIplus_inclusive'):return fit.fine_check(phase,name,arm,science)
            return super().fine_check(phase,name,arm,science)

    recover.Recovery=JointRecovery
    try:
        code=recover.run(args.case_id,args.wall_seconds,output_root=root,saved_evidence=args.saved_evidence,resume_from=args.resume_from)
        checkpoint.write(case_out/'cuda_provider.json',dict(passed=code==0,launcher_sha256=sha(__file__),immigrant_controls_sha256=sha(args.immigrant_controls),inclusive_controls_sha256=sha(args.inclusive_controls),provider='CUDA training deficits; original CPU selected checks and held-out scores',backends=receipts,start5_polish=polish_audits))
        return code
    finally:recover.Recovery=baseline

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case-id',required=True);p.add_argument('--wall-seconds',type=float,default=7200)
    for name in ('output-root','saved-evidence','resume-from','immigrant-library','inclusive-library','immigrant-controls','inclusive-controls'):p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(run(p.parse_args()))
