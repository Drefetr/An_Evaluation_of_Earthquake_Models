"""Thin adapter for the preserved, six-start staged comparison.

No source changes to the historical engine. This is a new misspecification
stress study, not a historical replay or a calibrated inhibition test.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for _name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_name]='1'

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
from api import load
STAGED=load('staged')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def law_for_contract(contract):
    law=contract['law']
    return STAGED.law_from_setting(dict(beta=law['beta'],horizon=law['horizon_days'],
        coordinate_horizon=law['coordinate_horizon_days'],generating_fit=law['alternative_generating_fit']))


class CpuMetrics:
    def cuda_metrics(self,*args):
        return dict(actual_backend='cpu',cuda_measurement='not_applicable',tokens=None,cost=None)


class CpuStagedCase(STAGED.StagedCase):
    """Backend variation; inherited legacy CUDA field names are not measurements."""
    def gpu_history(self):
        return self.cpu16_history()


def compare(arrays,contract,*,backend='cuda',seconds=120,progress=None):
    law=law_for_contract(contract)
    deadline=time.perf_counter()+seconds
    began=time.perf_counter()
    context=None
    result=None
    if backend=='cuda':
        context=STAGED.CudaOracleContext()
        try:
            result=STAGED.fit_case(arrays,law,clock_mode='paired',contract=contract,
                deadline=deadline,context=context,progress_callback=progress)
        finally:
            context.close()
    elif backend=='cpu':
        stage=CpuStagedCase(arrays,law,clock_mode='paired',contract=contract,
            deadline=deadline,context=CpuMetrics(),progress_callback=progress)
        result=dict(complete=False,status='partial',methods=[],records=[],planned_optimizer_calls=6)
        try:
            for method_id in STAGED.METHODS:
                stage.optimize_method_gpu(method_id)
                method=stage.validate_method_cpu(method_id)
                result['methods'].append(method)
                if not method['complete']:
                    result['status']='unresolved_validation'
                    break
            result['complete']=len(result['methods'])==2 and all(m['complete'] for m in result['methods'])
            if result['complete']: result['status']='complete'
        except Exception as exc:
            result.update(status='time_cap' if isinstance(exc,TimeoutError) else 'unresolved',error=type(exc).__name__+': '+str(exc))
        finally:
            result['records']=stage.records
            result['optimized_methods']=list(stage.optimized.values())
            result['prescribed_optimizer_calls']=len(stage.records)
            stage.close()
    else:
        raise ValueError('Unknown backend')
    return dict(schema_version=1,study='designed MDFHP-form excitatory misspecification stress',
        actual_backend=backend,elapsed_seconds=time.perf_counter()-began,
        adapter_sha256=sha256(__file__),contract_sha256=STAGED.canonical_hash(contract),
        engine_source_pins=STAGED.source_pins(),supplied_law=asdict(law),
        report_names={'known_known':'supplied_background','background_estimated':'fitted_background'},
        legacy_field_notice=('CPU variation retains inherited primary_cuda40/cuda16_nll/cuda_metrics names solely for unchanged validators; actual execution is CPU.' if backend=='cpu' else None),
        result=STAGED.clean(result))


def load_csv(path):
    data=np.genfromtxt(path,delimiter=',',names=True,dtype=float)
    data=np.atleast_1d(data)
    names=set(data.dtype.names or ())
    hi='times_hi' if 'times_hi' in names else 'time_hi'
    lo='times_lo' if 'times_lo' in names else 'time_lo'
    gap='event_gaps' if 'event_gaps' in names else 'event_gap'
    return dict(times=np.asarray(data[hi]),times_lo=np.asarray(data[lo]),
        event_gaps=np.asarray(data[gap]),excess=np.asarray(data['excess']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history',required=True)
    p.add_argument('--contract',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['cuda','cpu'],default='cuda')
    p.add_argument('--seconds',type=float,default=120)
    args=p.parse_args()
    output=Path(args.output)
    if output.exists():raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    events=output.with_suffix('.events.jsonl')
    if events.exists():raise FileExistsError(events)
    def progress(event):
        with events.open('a',encoding='utf-8') as f:
            f.write(json.dumps(STAGED.clean(event),allow_nan=False)+'\n')
    result=compare(load_csv(args.history),json.loads(Path(args.contract).read_text()),
        backend=args.backend,seconds=args.seconds,progress=progress)
    result['input_sha256']=sha256(args.history)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),backend=args.backend,complete=result['result']['complete'],
        status=result['result']['status'],elapsed_seconds=result['elapsed_seconds'])))


if __name__=='__main__':main()
