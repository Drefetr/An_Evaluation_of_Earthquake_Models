"""CPU raw-history replay of the original fully specified-law oracle test."""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import sys
import time

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np
import scipy

HERE=Path(__file__).resolve().parent
_MODULES=None
TOLERANCE=1e-6
EXPECTED_IDS=[f'null_{i:04d}' for i in range(1999)]+[f'new_r{i:03d}' for i in range(150)]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def local_path(relative):
    path=(HERE/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(HERE):raise ValueError('Oracle bundle path escape')
    return path


def history_path(relative):
    path=(HERE.parent/relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(HERE.parent/'synthetic/s01/histories'):
        raise ValueError('History path outside exact shared S01 bank')
    return path


def verify_inputs(manifest):
    if [r['id'] for r in manifest['cases']]!=EXPECTED_IDS:raise ValueError('Frozen oracle cohort/order differs')
    if sha(HERE.parent/'synthetic/s01/bank.json')!=manifest['source_synthetic_bank_sha256']:
        raise ValueError('Synthetic bank mapping changed')
    seen=set()
    for f in manifest['files']:
        if f['path'] in seen:raise ValueError('Duplicate source/expected file')
        seen.add(f['path']);path=local_path(f['path'])
        if path.stat().st_size!=f['bytes'] or sha(path)!=f['sha256']:raise ValueError('Oracle input hash differs: '+f['path'])
    paired=[]
    for index,case in enumerate(manifest['cases']):
        role='reference' if index<999 else ('null_query' if index<1999 else 'alternative_query')
        if case['role']!=role:raise ValueError('Oracle reference/query role differs')
        if case['clock_mode']=='paired_clock':paired.append(case['id'])
        p=history_path(case['history'])
        if p.stat().st_size!=case['history_bytes'] or sha(p)!=case['history_sha256']:raise ValueError('Raw history bytes changed: '+case['id'])
    if paired!=['null_0841']:raise ValueError('Exceptional paired clock mapping differs')
    return dict(histories=2149,reference=999,null_query=1000,alternative_query=150,paired_ids=paired,history_mapping_exact=True)


def _load(alias,path):
    spec=importlib.util.spec_from_file_location(alias,path)
    module=importlib.util.module_from_spec(spec);sys.modules[alias]=module;spec.loader.exec_module(module)
    return module


def load_modules():
    """Load exact accepted sources with their original relative source tree."""
    global _MODULES
    if _MODULES is not None:return _MODULES
    saved={k:sys.modules.get(k) for k in ('kernels','checkpoint_io')}
    try:
        sys.modules['kernels']=_load('_oracle_replay_frozen_kernels',HERE/'source/iteration_5/code/kernels.py')
        sys.modules['checkpoint_io']=_load('_oracle_replay_frozen_checkpoints',HERE/'source/iteration_6/code/checkpoint_io.py')
        cpu=_load('_oracle_replay_frozen_cpu',HERE/'source/iteration_17/code/oracle_likelihood.py')
        stats=_load('_oracle_replay_frozen_statistics',HERE/'source/iteration_17/code/analyse_oracle_v1_1.py')
        _MODULES=cpu,stats
    finally:
        for key,value in saved.items():
            if value is None:sys.modules.pop(key,None)
            else:sys.modules[key]=value
    return _MODULES


def law_setting(protocol):
    law=protocol['phase1']['law']
    return dict(beta=law['beta'],horizon=law['horizon_days'],coordinate_horizon=law['coordinate_horizon_days'],generating_fit=law['alternative_generating_fit'])


def close(actual,expected,name):
    if not math.isfinite(actual) or abs(actual-expected)>TOLERANCE:
        raise ArithmeticError(f'{name}: {actual!r} differs from {expected!r} by more than {TOLERANCE}')


def score_worker(case,protocol,output,case_timeout):
    """Fresh modal state on each call; only immutable kernels cached by source."""
    began=time.perf_counter();path=Path(output)/(case['id']+'.json')
    result=dict(id=case['id'],seed=case['seed'],role=case['role'],clock_mode=case['clock_mode'],history_sha256=case['history_sha256'],passed=False,status='running')
    write(path,result)
    try:
        cpu,stats=load_modules();stats.validate_protocol(protocol)
        law=cpu.law_from_setting(law_setting(protocol))
        source=history_path(case['history'])
        if sha(source)!=case['history_sha256']:raise ValueError('History changed after preflight')
        with np.load(source,allow_pickle=False) as z:arrays={k:z[k] for k in z.files}
        payload=cpu.score_refined(arrays,law,clock_mode=case['clock_mode'],eta=protocol['phase1']['law']['alternative_eta'],tolerance=TOLERANCE,deadline=began+case_timeout,chunk_nodes=512)
        result['evaluation']=payload
        if not payload['complete'] or not payload['refinement_passed']:raise ArithmeticError('Frozen refinement gate failed')
        expected=read(local_path(case['expected']))
        if payload['selected_order']!=expected['selected_order']:raise ArithmeticError('Selected refinement order changed')
        checks=[]
        for order,values in payload['evaluations'].items():
            original=expected['evaluations'][order]
            for key in ('n_events','eta','beta_fixed','clock_mode','order','stress_modes','trigger_modes'):
                if values[key]!=original[key]:raise ValueError('Frozen evaluation identity differs: '+key)
            for key in ('log_lr','event_log_ratio_sum','compensator_reduction','nll0','nll1','analytic_baseline_compensator','unit_trigger_compensator'):
                close(values[key],original[key],case['id']+'/'+order+'/'+key)
                checks.append(dict(order=int(order),field=key,absolute_delta=abs(values[key]-original[key])))
        result.update(passed=True,status='complete',checks=checks,log_lr=payload['result']['log_lr'],refinement_error=payload['selected_refinement_difference'])
    except Exception as exc:
        result.update(status='failed',error_type=type(exc).__name__,error=str(exc))
    finally:
        result['elapsed_seconds']=time.perf_counter()-began;write(path,result)
    return {k:result[k] for k in ('id','passed','status','elapsed_seconds')}


def calibrate(records,expected):
    """No threshold or frequency is reported for an incomplete replay bank."""
    if set(records)!=set(EXPECTED_IDS) or any(not r['passed'] for r in records.values()):
        raise ValueError('Full matching 2149-score bank required before calibration')
    _,stats=load_modules()
    values={cid:stats.score_pair(r['log_lr'],r['refinement_error']) for cid,r in records.items()}
    references=[values[cid] for cid in EXPECTED_IDS[:999]]
    old={r['id']:r for r in expected['outcomes']};outcomes=[]
    for cid in EXPECTED_IDS[999:]:
        row=dict(id=cid,**stats.classify(values[cid],references))
        if row!=old[cid]:raise ArithmeticError('Saved rank/envelope decision differs: '+cid)
        outcomes.append(row)
    method=dict(reference_requested=999,reference_complete=True,reference_resolved=999,
                heldout_null_size=stats.tally([r['reject'] for r in outcomes[:1000]]),
                alternative_power=stats.tally([r['reject'] for r in outcomes[1000:]]))
    def compare(value,target):
        if isinstance(value,dict):
            if set(value)!=set(target):raise ArithmeticError('Calibration fields differ')
            for key in value:compare(value[key],target[key])
        elif isinstance(value,list):
            if len(value)!=len(target):raise ArithmeticError('Calibration vector size differs')
            for v,t in zip(value,target):compare(v,t)
        elif isinstance(value,float):
            if not math.isfinite(value) or abs(value-target)>1e-12:raise ArithmeticError('Calibration descriptive scalar differs')
        elif value!=target:raise ArithmeticError('Calibration count/status differs')
    compare(method,expected['method'])
    return dict(method=method,outcomes=outcomes,reference_50th_largest_score=sorted((v[0] for v in references),reverse=True)[49],threshold_rule='Point rejection requires query strictly greater than this reference boundary; final decisions also use the frozen numerical sensitivity envelopes.',scope='Known fixed simple laws and realized reference bank; no F fitted-eta or composite-null calibration.')


def run_cases(selected,protocol,args,output,result,started):
    iterator=iter(selected);running={};stopped=False
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        def launch():
            nonlocal stopped
            remaining=args.timeout_seconds-(time.perf_counter()-started)
            if remaining<=0:stopped=True;result['stop_reason']='campaign_deadline';return False
            case=next(iterator,None)
            if case is None:return False
            future=pool.submit(score_worker,case,protocol,str(output),min(args.case_timeout_seconds,remaining))
            running[future]=case['id'];return True
        for _ in range(args.workers):
            if not launch():break
        result['active_ids']=list(running.values());write(output/'result.json',result)
        while running:
            done,_=wait(running,return_when=FIRST_COMPLETED)
            for future in done:
                cid=running.pop(future)
                try:case=future.result()
                except Exception as exc:case=dict(id=cid,passed=False,status='worker_error',error=str(exc))
                result['cases'].append(case)
                if not case['passed']:stopped=True;result['stop_reason']='case_failure'
                print(json.dumps(dict(event='case_complete',**case)),flush=True)
            result['active_ids']=list(running.values());write(output/'result.json',result)
            if not stopped:
                for _ in range(len(done)):
                    if not launch():break
    result['active_ids']=[]
    return not stopped and len(result['cases'])==len(selected) and all(r['passed'] for r in result['cases'])


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['score','verify'],default='score')
    group=p.add_mutually_exclusive_group();group.add_argument('--pilot',action='store_true');group.add_argument('--case',action='append',dest='cases')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--timeout-seconds',type=float,default=10800)
    p.add_argument('--case-timeout-seconds',type=float,default=900)
    args=p.parse_args(argv)
    if not 1<=args.workers<=4 or min(args.timeout_seconds,args.case_timeout_seconds)<=0:p.error('Workers must be1..4 and deadlines positive')
    output=args.output.resolve()
    if output.is_relative_to(HERE) or output.is_relative_to(HERE.parent/'synthetic'):p.error('Output must be outside immutable reproduction inputs')
    output.mkdir(parents=True,exist_ok=False);began=time.perf_counter()
    result=dict(schema='known_law_cpu_replay_result_v1',passed=False,mode=args.mode,full_campaign=False,calibration_performed=False,cases=[],
                runtime=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform()),
                scope='Fixed-law raw-history likelihoods only; no optimization or generation; F fitted-eta and composite-null tests are separate.')
    write(output/'result.json',result)
    try:
        manifest=read(HERE/'input_manifest.json');result['input_manifest_sha256']=sha(HERE/'input_manifest.json')
        result['input_verification']=verify_inputs(manifest)
        requested=manifest['pilot_cases'] if args.pilot else args.cases
        if requested is not None and (len(requested)!=len(set(requested)) or set(requested)-set(EXPECTED_IDS)):raise ValueError('Unknown/duplicate selected case')
        selected=[r for r in manifest['cases'] if requested is None or r['id'] in requested]
        result['selected_cases']=[r['id'] for r in selected]
        result['selection_label']='all2149' if requested is None else ('fixed_four_case_pilot' if args.pilot else 'explicit_subset')
        write(output/'result.json',result)
        if args.mode=='verify':result['passed']=True
        else:
            passed=run_cases(selected,read(HERE/'protocol.json'),args,output,result,began)
            if not passed:raise ArithmeticError('Incomplete or failed raw-history replay; calibration withheld')
            if len(selected)==2149:
                records={cid:read(output/(cid+'.json')) for cid in EXPECTED_IDS}
                summary=calibrate(records,read(HERE/'expected_calibration.json'));write(output/'calibration.json',summary)
                result.update(full_campaign=True,calibration_performed=True)
            result['passed']=True
    except Exception as exc:result.update(error_type=type(exc).__name__,error=str(exc))
    finally:
        result['elapsed_seconds']=time.perf_counter()-began;write(output/'result.json',result)
    print(json.dumps({k:result[k] for k in ('passed','mode','full_campaign','calibration_performed','elapsed_seconds')}),flush=True)
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
