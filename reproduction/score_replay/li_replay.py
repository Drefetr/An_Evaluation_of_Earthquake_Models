"""Rebuild raw features and replay the original19 LI/OC selected procedures."""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback
import types

if __package__ in (None, ''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, components, compare, digest, resolve, write_new


def source_pins():
    folder=Path(__file__).resolve().parent
    return {n:digest((folder/n).read_bytes()) for n in ('__init__.py','core.py','li_replay.py')}


def materialize_source(inputs,registry,folder):
    folder.mkdir(parents=True,exist_ok=False)
    for relative,spec in registry['source_resources'].items():
        path=resolve(folder,relative);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(inputs.read(spec))
    return folder


def build(registry_path,output):
    from engine.cpu_build import build_shared
    if output.exists():raise FileExistsError('Build directory must be new')
    raw=registry_path.read_bytes();registry=json.loads(raw);inputs=Inputs(registry_path.parent)
    output.mkdir(parents=True);folder=materialize_source(inputs,registry,output/'source')
    receipt=build_shared(folder/registry['native_source'],output/'native',dependency_root=folder)
    path=Path(receipt['library']);rp=output/'native/build_receipt.json'
    result=dict(registry_sha256=digest(raw),library=dict(path=str(path),sha256=digest(path.read_bytes()),
        source_sha256=registry['source_resources'][registry['native_source']]['sha256'],
        build_receipt=receipt,build_receipt_path=str(rp.resolve()),build_receipt_sha256=digest(rp.read_bytes())))
    write_new(output/'libraries.json',result);return result


def load_engine(folder):
    prefix='_saved_li_replay'
    for name,relative in [(prefix,''),(prefix+'.continuous_local_inhibition','continuous_local_inhibition'),
                          (prefix+'.local_inhibition_experiment','local_inhibition_experiment')]:
        package=types.ModuleType(name);package.__path__=[str(folder/relative)];sys.modules[name]=package
    name=prefix+'.local_inhibition_experiment.engine'
    spec=importlib.util.spec_from_file_location(name,folder/'local_inhibition_experiment/engine.py')
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def tiny_control(engine,dll,folder):
    """Invented one-event Poisson/LI controls, never a fitted/history sample."""
    import numpy as np
    folder.mkdir()
    rect=np.array([[10*x,10*(x+1),10*y,10*(y+1)] for y in range(3) for x in range(3)],float)
    raw=dict(parent_time=np.array([1.]),parent_xy=np.array([[5.,5.]]),parent_excess=np.array([.2]),
        rectangles=rect,reference_pi=np.full(9,1/9),kde_xy=np.empty((0,2)),kde_weight=np.empty(0),
        metadata_json=np.array(json.dumps(dict(beta=2.,sigma=10.,kde_h=10.,bg_floor=1.,T0=3.,r=.7,start=0.,end=3.))))
    path=folder/'one_event.npz'
    with path.open('xb') as stream:np.savez_compressed(stream,**raw)
    pars=[-2.,0.,0.,math.log(.05),1.3];li=pars+[0.,math.log(10),math.log(2)]
    with engine.Objective(path,dll_path=str(dll),order=8,fine_order=16,spatial_tol=1e-8) as obj:
        null=obj.evaluate('OC',pars,detailed=True,value_only=True)
        floor=obj.evaluate('LI',li,detailed=True,value_only=True)
        positive=obj.evaluate('LI',pars+[.4,*li[-2:]],detailed=True,value_only=True)
        fine=obj.evaluate('LI',pars+[.4,*li[-2:]],detailed=True,value_only=True,fine=True)
    expected=dict(P=-2.-math.log(900.),E=3*math.exp(-2.),M=math.log(2.)-.4)
    actual=components(null,'space_time_mark');control=compare(actual,expected,{k:1e-10 for k in expected})
    floor_delta=max(abs(float(null[k]-floor[k])) for k in
                    ('joint_nll','timing_logscore','conditional_location_logscore','integrated_intensity'))
    fine_delta=abs(positive['joint_nll']-fine['joint_nll'])
    passed=(control['passed'] and floor_delta<=1e-10 and fine_delta<=1e-4
        and positive['integrated_intensity']<null['integrated_intensity']
        and abs(positive['event_log_point_intensity_sum']-null['event_log_point_intensity_sum'])<=1e-10)
    return dict(passed=bool(passed),analytic_null=control,floor_maximum_delta=floor_delta,
        positive_eta_coarse_fine_nll_delta=fine_delta,
        scope='One invented event: analytic normalized Poisson law, exact LI floor, strict-past unchanged event term and positive attenuation, coarse/fine score agreement.')


def evaluate(inputs,row,engine,dll,folder):
    """Raw observations and selected state only; expected resource not read."""
    import numpy as np
    state=inputs.json(row['state']);pars=state['parameters'];model=state['model']
    expected_dim=8 if model=='LI' else 5
    if len(pars)!=expected_dim or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in pars):
        raise ValueError('Invalid original selected vector')
    path=inputs.materialize(row['raw'],folder/'inputs','.npz')
    kwargs=state['objective_kwargs']
    if set(kwargs)-{'order','fine_order','space_scheme','spatial_tol','near_width','tile_width'}:
        raise ValueError('Unexpected original objective option')
    # eta-zero scales vanish identically. Use the original engine's exact OC
    # branch, preserving the original full selected vector in the output.
    shortcut=model=='LI' and pars[5]==0.
    evaluated_model='OC' if shortcut else model
    evaluated_pars=pars[:5] if shortcut else pars
    with engine.Objective(path,dll_path=str(dll),**kwargs) as obj:
        if obj.metadata['ne']!=row['n_events_expected']:
            raise ValueError('Raw reconstruction event count differs')
        feature_hashes={k:digest(np.ascontiguousarray(v).tobytes()) for k,v in obj.a.items()}
        scores={phase:obj.evaluate(evaluated_model,evaluated_pars,detailed=True,value_only=True,fine=phase=='fine')
                for phase in ('coarse','fine')}
        meta={k:v for k,v in obj.metadata.items() if k not in ('raw_source','raw_binding')}
    arrays={};result={}
    for phase,raw in scores.items():
        result[phase]=dict(components=components(raw,'space_time_mark'),
            native_scalars={k:float(v) for k,v in raw.items() if isinstance(v,(int,float)) and math.isfinite(v)})
        for key,value in raw.items():
            if isinstance(value,np.ndarray) and 'gradient' not in key:
                if not np.isfinite(value).all():raise ValueError('Nonfinite native score array')
                arrays[phase+'__'+key]=value
    p=folder/'native_components.npz'
    with p.open('xb') as stream:np.savez_compressed(stream,**arrays)
    result.update(parameters=pars,model=model,evaluated_model=evaluated_model,exact_eta_zero_shortcut=shortcut,
        shortcut_scope='Same selected intensity; inhibition-scale derivatives not requested.' if shortcut else None,
        n_events=row['n_events_expected'],raw_sha256=row['raw']['sha256'],state_sha256=row['state']['sha256'],
        feature_array_sha256=feature_hashes,metadata=meta,
        native_arrays=dict(path=p.name,sha256=digest(p.read_bytes())),
        gradient_scope='Not evaluated or certified: value_only=True, original unresolved-gradient caveats retained.')
    return result,arrays


def compare_result(actual,arrays,reference,row):
    import numpy as np
    checks={};array_checks={}
    for phase in ('coarse','fine'):
        checks[phase]=compare(actual[phase]['components'],components(reference[phase],'space_time_mark'),row['absolute_tolerances'])
        # These are actual original per-event field values, not reconstructed
        # from their aggregate. Unavailable historical arrays are listed.
        for name in ('event_logs','event_log_point_intensity','event_log_cell_intensity',
                     'event_log_zone_intensity','event_log_ground_intensity','cell_integrated_intensity'):
            key=phase+'__'+name
            if name not in reference[phase]:continue
            expected=np.asarray(reference[phase][name]);value=arrays.get(key)
            shape_ok=value is not None and value.shape==expected.shape
            error=float(np.max(np.abs(value-expected))) if shape_ok and value.size else 0. if shape_ok else None
            tolerance=row['event_log_absolute_tolerance']
            array_checks[key]=dict(passed=shape_ok and error<=tolerance,maximum_absolute_delta=error,
                                   absolute_tolerance=tolerance,shape=list(expected.shape))
    return dict(passed=all(x['passed'] for x in list(checks.values())+list(array_checks.values())),
                scalar_comparisons=checks,array_comparisons=array_checks)


def run(registry_path,libraries_path,admission_path,output,selected,mode):
    if output.exists():raise FileExistsError('Output must be new')
    raw=registry_path.read_bytes();reg=json.loads(raw);by_id={r['id']:r for r in reg['rows']}
    selected=list(by_id) if selected is None else selected
    if len(by_id)!=len(reg['rows']) or not selected or len(set(selected))!=len(selected) or set(selected)-set(by_id):
        raise ValueError('Invalid original row roster')
    ar=admission_path.read_bytes();adm=json.loads(ar);lr=libraries_path.read_bytes();libs=json.loads(lr)
    for key,value in [('registry_sha256',digest(raw)),('libraries_sha256',digest(lr)),
        ('input_manifest_sha256',digest((registry_path.parent/'input_manifest.json').read_bytes())),
        ('source_sha256',source_pins()),('mode',mode),('row_ids',selected)]:
        if adm.get(key)!=value:raise ValueError('Admission mismatch: '+key)
    if adm.get('passed') is not True or libs['registry_sha256']!=digest(raw):raise ValueError('Unaccepted source')
    lib=libs['library'];dll=Path(lib['path']).resolve();rb=Path(lib['build_receipt_path']).read_bytes();receipt=json.loads(rb)
    if (digest(dll.read_bytes())!=lib['sha256'] or receipt!=lib['build_receipt'] or receipt.get('passed') is not True
        or digest(rb)!=lib['build_receipt_sha256'] or receipt['library_sha256']!=lib['sha256']
        or receipt['source_sha256']!=reg['source_resources'][reg['native_source']]['sha256']
        or adm.get('build_receipts_sha256')!={'li':digest(rb)}):raise ValueError('Native identity mismatch')
    threads=adm.get('numeric_threads')
    if isinstance(threads,bool) or threads not in (1,2):raise ValueError('Require one or two threads')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]=str(threads)
    import numpy as np
    from threadpoolctl import threadpool_info,threadpool_limits
    output.mkdir(parents=True);inputs=Inputs(registry_path.parent)
    source=materialize_source(inputs,reg,output/'source');engine=load_engine(source)
    write_new(output/'launch.json',dict(admission_sha256=digest(ar),registry_sha256=digest(raw),source_sha256=source_pins(),
        libraries_sha256=digest(lr),build_receipts_sha256={'li':digest(rb)},mode=mode,row_ids=selected,
        numerical_lease=adm.get('numerical_lease'),runtime=dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),numeric_threads=threads)))
    with threadpool_limits(limits=threads):control=tiny_control(engine,dll,output/'tiny')
    write_new(output/'tiny_controls.json',control)
    if not control['passed']:raise ArithmeticError('Invented native controls failed')
    results=[];began=time.monotonic()
    for index,identity in enumerate(selected):
        row=by_id[identity];folder=output/'rows'/f'{index:05d}';folder.mkdir(parents=True)
        report=dict(id=identity,passed=False,status='failed');start=time.monotonic()
        try:
            with threadpool_limits(limits=threads):
                if any(v['num_threads']>threads for v in threadpool_info()):raise RuntimeError('Thread cap exceeded')
                actual,arrays=evaluate(inputs,row,engine,dll,folder)
                if any(v['num_threads']>threads for v in threadpool_info()):raise RuntimeError('Loaded library thread cap exceeded')
            checks=compare_result(actual,arrays,inputs.json(row['expected']),row)
            report.update(actual=actual,comparison=checks,passed=checks['passed'],status='replayed' if checks['passed'] else 'failed',
                          feature_scope=row['feature_scope'],fit_scope=row['fit_scope'])
        except Exception as exc:
            report.update(error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        report['elapsed_seconds']=time.monotonic()-start;write_new(folder/'result.json',report)
        record=dict(id=identity,passed=report['passed'],status=report['status'],result=(folder/'result.json').relative_to(output).as_posix(),
                    sha256=digest((folder/'result.json').read_bytes()),elapsed_seconds=report['elapsed_seconds']);results.append(record)
        with (output/'progress.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(record)+'\n');stream.flush()
    result=dict(schema='original_li_replay_result_v1',passed=all(x['passed'] for x in results),rows=results,
        requested_rows=len(selected),completed_rows=len(results),passed_rows=sum(x['passed'] for x in results),
        full_registry=selected==list(by_id),entire_task_complete=False,elapsed_seconds=time.monotonic()-began,
        controls_record=dict(path='tiny_controls.json',sha256=digest((output/'tiny_controls.json').read_bytes())),
        scope='Unchanged selected19-procedure training/test states with original coarse/fine scores; no refitting, simulation, optimizer-search or all-gradient certification.')
    write_new(output/'result.json',result);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',action='store_true')
    for name in ('registry','output'):parser.add_argument('--'+name,required=True,type=Path)
    for name in ('libraries','admission','rows'):parser.add_argument('--'+name,type=Path)
    parser.add_argument('--mode',choices=('pilot','full','completion'));args=parser.parse_args()
    if args.build:build(args.registry,args.output.resolve())
    else:
        if args.libraries is None or args.admission is None or args.mode is None:parser.error('Replay requires libraries, admission and mode')
        selected=json.loads(args.rows.read_text(encoding='utf-8')) if args.rows else None
        result=run(args.registry,args.libraries,args.admission,args.output,selected,args.mode)
        print(json.dumps({k:v for k,v in result.items() if k!='rows'}));raise SystemExit(0 if result['passed'] else 1)
