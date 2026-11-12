"""Complete the two interrupted searches with the original scientific core.

Existing successful arms/starts are reused by their saved bytes. The interrupted
Powell start resumes at its last returned state with 15000 further evaluations.
No held-out scores participate in search or candidate selection.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='2'
import argparse,copy,hashlib,json,math,platform,time,zipfile
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import OptimizeResult
from threadpoolctl import threadpool_limits
from experiments.s04b_joint_execution import driver
from experiments.s04b_exposure_refinement.adapter import Adapter
from experiments.s04b_joint_nuisance import checkpoint

REPO=Path(__file__).resolve().parents[2]
OUT=REPO/'validation/live_results/s04b_joint_complete_20261111'
read=driver.read

def evidence(ref):
    path=REPO/ref['path']
    assert driver.sha(path)==ref['sha256']
    with zipfile.ZipFile(path) as z:data=z.read(ref['member'])
    assert hashlib.sha256(data).hexdigest()==ref['member_sha256']
    return data

class Recovery(Adapter):
    def __init__(self,science,out,prior,trace):
        super().__init__(science,out,partial=None,trace=None)
        self.prior=prior;self.oldtrace=trace
        self.reused=[]
    def fit_arm(self,phase,name,science,eligible,checkpoint_fn):
        if name in self.prior['fits'] and self.prior['fits'][name]['passed']:
            arm=copy.deepcopy(self.prior['fits'][name]);self.arm_calls.append(name)
            actual=phase.evaluate(arm['selected']['parameters'],name,8)[0]
            assert abs(actual['joint']-arm['selected']['score']['joint'])<1e-7
            self.reused.append(dict(kind='complete_arm',model=name,selected_numerical_delta=actual['joint']-arm['selected']['score']['joint']))
            for row in self.oldtrace:
                if row['model']==name:checkpoint_fn(row)
            return arm
        return super().fit_arm(phase,name,science,eligible,checkpoint_fn)
    def optimizer(self,objective,initial,*,jac,bounds,method,options):
        current=self.current;name=current['model'];start=current['start_index']
        successful=next((v for v in self.oldtrace if v['event']=='attempt_end' and v['model']==name and v['start_index']==start and v['method']==method and v.get('success')),None)
        if successful:
            self.reused.append(dict(kind='successful_start',model=name,start=start,method=method))
            return OptimizeResult(x=np.array(successful['returned_parameters']),fun=successful['returned_nll'],success=True,status=successful['solver_status'],message='Reused exact successful optimizer return: '+successful['message'],nfev=successful['nfev'],nit=successful['nit'])
        # Resume the saved cap return rather than repeat its first 5000 calls.
        capped=next((v for v in self.oldtrace if v['event']=='attempt_end' and v['model']==name and v['start_index']==start and v['method']=='Powell' and v.get('nfev')==5000),None)
        if capped and method=='L-BFGS-B':
            self.reused.append(dict(kind='powell_resume_state',model=name,start=start,parameters=capped['returned_parameters'],prior_nfev=5000))
            return OptimizeResult(x=np.array(capped['returned_parameters']),fun=capped['returned_nll'],success=False,status=1,message='Pass saved Powell cap state to continuation',nfev=0,nit=0)
        return super().optimizer(objective,initial,jac=jac,bounds=bounds,method=method,options=options)
    def fine_check(self,phase,name,arm,science):
        if name in self.prior['fits'] and self.prior['fits'][name]['passed']:
            return copy.deepcopy(self.prior['training_checks'][name])
        return super().fine_check(phase,name,arm,science)

def run(case_id,wall=7200):
    start=time.monotonic();out=OUT/'recovery'/case_id;out.mkdir(parents=True,exist_ok=False)
    dispositions=read(REPO/'validation/live_results/joint_nuisance_dispositions_20261107/report.json')
    record=next(c for c in dispositions['case_dispositions'] if c['case_id']==case_id)
    prior=json.loads(evidence(record['evidence']['case']));trace=[json.loads(v) for v in evidence(record['evidence']['trace']).decode().splitlines()]
    science=read(driver.SCIENCE/'protocol.json');science['solver']['powell']['maxfev']=15000
    case=next(c for c in driver.frozen.verify_inputs(read(driver.SCIENCE/'protocol.json')) if c['case_id']==case_id)
    native=driver.model.Native(OUT/'native/joint.dll');modules=driver.model.archived()
    adapter=Recovery(science,out,prior,trace)
    with threadpool_limits(limits=2),driver.OrderedChunkScheduler() as scheduler:
        runner=driver.runner_with_scheduler(scheduler);factory=runner.model.phase_from_rows
        runner.model.phase_from_rows=lambda rows,gm,s,e,m,n,d:adapter.wrap_phase(factory(rows,gm,s,e,m,n,d),s,e)
        runner.fit_arm=adapter.fit_arm;runner.fine_check=adapter.fine_check
        old=runner.historical_floor
        runner.historical_floor=lambda *a:adapter.historical_floor(old,*a)
        (out/'cases').mkdir()
        report=runner.case_run(case,modules,native,science,out/'cases',start+wall,None)
    meta=dict(case_id=case_id,passed=report['passed'],seconds=time.monotonic()-start,wall_allowance_seconds=wall,
              platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
              library_sha256=driver.sha(OUT/'native/joint.dll'),native_source_sha256=driver.sha(driver.SCIENCE/'attenuation.cpp'),
              scientific_protocol_sha256=driver.sha(driver.SCIENCE/'protocol.json'),powell_maxfev=15000,
              prior_evidence=record['evidence'],reused=adapter.reused,adapter=adapter.receipt())
    checkpoint.write(out/'result.json',meta)
    print(json.dumps(dict(case_id=case_id,passed=report['passed'],seconds=meta['seconds'],error=report.get('error'))),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case-id',required=True);p.add_argument('--wall-seconds',type=float,default=7200)
    a=p.parse_args();raise SystemExit(run(a.case_id,a.wall_seconds))
