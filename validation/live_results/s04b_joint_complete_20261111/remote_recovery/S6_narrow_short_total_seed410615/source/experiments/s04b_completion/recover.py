"""Complete the two interrupted searches with the original scientific core.

Existing successful arms/starts are reused by their saved bytes. The interrupted
Powell start resumes at its last returned state with 15000 further evaluations.
No held-out scores participate in search or candidate selection.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='2'
import argparse,copy,hashlib,json,math,platform,shutil,time,zipfile
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import OptimizeResult
from threadpoolctl import threadpool_limits
from experiments.s04b_joint_execution import driver
from experiments.s04b_exposure_refinement.adapter import Adapter
from experiments.s04b_joint_nuisance import checkpoint

REPO=Path(__file__).resolve().parents[2]
OUT=Path(os.environ.get('S04B_COMPLETION_ROOT',REPO/'validation/live_results/s04b_joint_complete_20261111')).resolve()
read=driver.read

def evidence(ref,extracted=None):
    if extracted is not None:
        index=read(Path(extracted)/'index.json')
        key=hashlib.sha256((ref['path']+'::'+ref['member']).encode()).hexdigest()
        entry=index[key];assert entry['original_reference']==ref
        data=(Path(extracted)/entry['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest()==ref['member_sha256']
        return data
    path=REPO/ref['path']
    assert driver.sha(path)==ref['sha256']
    with zipfile.ZipFile(path) as z:data=z.read(ref['member'])
    assert hashlib.sha256(data).hexdigest()==ref['member_sha256']
    return data

def native_library(root=OUT):
    folder=Path(root)/'native'
    for name in (('joint.dll',) if os.name=='nt' else ('attenuation.so','joint.so')):
        path=folder/name
        if path.is_file():return path
    raise FileNotFoundError('Build the unchanged native source with experiments.s04b_completion.build_native')

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
            assert np.array_equal(np.asarray(successful['initial_parameters']),np.asarray(initial)), 'Reused start initial state differs'
            from experiments.s04b_joint_nuisance.fit import bounds as scientific_bounds
            assert bounds==scientific_bounds(self.science,name), 'Reused start box differs'
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

def run(case_id,wall=7200,*,output_root=None,saved_evidence=None,resume_from=None):
    root=Path(output_root).resolve() if output_root else OUT
    start=time.monotonic();out=root/'recovery'/case_id;out.mkdir(parents=True,exist_ok=False)
    sources={}
    for base in ('s04b_completion','s04b_joint_nuisance','s04b_joint_execution','s04b_exposure_refinement'):
        for path in sorted((REPO/'experiments'/base).iterdir()):
            if path.is_file() and path.suffix in ('.py','.cpp','.json'):
                relative=path.relative_to(REPO).as_posix();target=out/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target);sources[relative]=driver.sha(path)
    checkpoint.write(out/'request.json',dict(case_id=case_id,wall_seconds=wall,source_sha256=sources,resume_from=str(resume_from),saved_evidence=str(saved_evidence)))
    dispositions=read(REPO/'validation/live_results/joint_nuisance_dispositions_20261107/report.json')
    record=next(c for c in dispositions['case_dispositions'] if c['case_id']==case_id)
    prior=json.loads(evidence(record['evidence']['case'],saved_evidence));trace=[json.loads(v) for v in evidence(record['evidence']['trace'],saved_evidence).decode().splitlines()]
    resumed=None
    if resume_from:
        folder=Path(resume_from);p=folder/'cases'/(case_id+'.json');t=folder/'cases'/(case_id+'.attempts.jsonl')
        newer=read(p);assert newer['case_id']==case_id and newer['input_sha256']==prior['input_sha256']
        prior=newer;trace += [json.loads(v) for v in t.read_text().splitlines()]
        resumed=dict(report_sha256=driver.sha(p),trace_sha256=driver.sha(t),path=str(folder))
    science=read(driver.SCIENCE/'protocol.json');science['solver']['powell']['maxfev']=15000
    case=next(c for c in driver.frozen.verify_inputs(read(driver.SCIENCE/'protocol.json')) if c['case_id']==case_id)
    library=native_library(root);native=driver.model.Native(library);modules=driver.model.archived()
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
              library_sha256=driver.sha(library),native_source_sha256=driver.sha(driver.SCIENCE/'attenuation.cpp'),
              scientific_protocol_sha256=driver.sha(driver.SCIENCE/'protocol.json'),powell_maxfev=15000,
              prior_evidence=record['evidence'],resumed_training=resumed,source_sha256=sources,reused=adapter.reused,adapter=adapter.receipt())
    assert all(driver.sha(REPO/relative)==pin for relative,pin in sources.items()), 'Execution source changed during fitting'
    checkpoint.write(out/'result.json',meta)
    print(json.dumps(dict(case_id=case_id,passed=report['passed'],seconds=meta['seconds'],error=report.get('error'))),flush=True)
    return 0 if report['passed'] else 1

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--case-id',required=True);p.add_argument('--wall-seconds',type=float,default=7200)
    p.add_argument('--output-root',type=Path);p.add_argument('--saved-evidence',type=Path);p.add_argument('--resume-from',type=Path)
    a=p.parse_args(argv);return run(a.case_id,a.wall_seconds,output_root=a.output_root,saved_evidence=a.saved_evidence,resume_from=a.resume_from)
if __name__=='__main__':raise SystemExit(main())
