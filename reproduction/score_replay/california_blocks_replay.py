"""Replay calendar/sequence scores from fresh event scores and saved states.

The original interval arithmetic and Python reducers are preserved. The annual
kernel's private validation helper is renamed in its compiled copy to avoid a
glibc name collision; its original bytes and both source hashes are retained. Expected
historical scores are opened only after current rows have been calculated.
"""
from __future__ import annotations
import argparse
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
import time
import traceback
import types

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, digest, resolve, write_new


def source_pins():
    base = Path(__file__).parent
    return {n: digest((base/n).read_bytes()) for n in
            ('__init__.py', 'core.py', 'california_blocks_replay.py')}


def load_modules(inputs, registry):
    package = '_original_california_partitions'
    parent = types.ModuleType(package); parent.__path__ = []
    sys.modules[package] = parent
    result = {}
    for group in ('annual', 'sequence'):
        pkg = types.ModuleType(package+'.'+group); pkg.__path__ = []
        sys.modules[pkg.__name__] = pkg
        result[group] = {}
        names = ['partition.py', 'native.py', 'reducer.py'] if group == 'sequence' else ['native.py', 'reducer.py']
        for name in names:
            spec = registry['sources'][group][name]
            mod = types.ModuleType(pkg.__name__+'.'+name[:-3])
            mod.__file__ = 'original_source/'+spec['sha256']+'/'+name
            mod.__package__ = pkg.__name__
            sys.modules[mod.__name__] = mod
            exec(compile(inputs.read(spec), mod.__file__, 'exec'), mod.__dict__)
            result[group][name[:-3]] = mod
    return result


def portable_interval_source(kind, raw):
    """Rename only the private validator; never change numerical expressions."""
    if kind != 'annual':
        return raw, dict(kind='unchanged', original_sha256=digest(raw), compiled_sha256=digest(raw))
    declaration = b'void finite(double v) { check(std::isfinite(v)); }'
    if raw.count(declaration) != 1 or b'require_finite' in raw:
        raise ValueError('Unrecognized annual validation helper')
    adapted, count = re.subn(rb'(?<![A-Za-z0-9_:])finite(?=\s*\()', b'require_finite', raw)
    if count < 2 or adapted.replace(b'require_finite', b'finite') != raw:
        raise ValueError('Annual helper rename changed more than its identifier')
    return adapted, dict(kind='private_validator_identifier_rename', original_sha256=digest(raw),
                         compiled_sha256=digest(adapted), replacements=count,
                         reason='Avoid ambiguity with the glibc global finite(double) declaration')


def build(registry_path, output):
    from engine.cpu_build import build_shared
    raw = registry_path.read_bytes(); registry = json.loads(raw)
    if output.exists(): raise FileExistsError(output)
    output.mkdir(parents=True)
    inputs = Inputs(registry_path.parent); libraries = {}
    for kind, spec in registry['native_libraries'].items():
        original = inputs.materialize(spec, output/'sources'/kind, '.cpp')
        adapted, portability = portable_interval_source(kind, original.read_bytes())
        source = original
        if adapted != original.read_bytes():
            source = original.with_name('portable_'+original.name)
            with source.open('xb') as stream: stream.write(adapted)
        receipt = build_shared(source, output/'build'/kind, dependency_root=source.parent)
        binary = Path(receipt['library'])
        rp = output/'build'/kind/'build_receipt.json'
        libraries[kind] = dict(path=str(binary), sha256=digest(binary.read_bytes()),
            source_sha256=spec['sha256'], portability=portability, build_receipt_path=str(rp.resolve()),
            build_receipt_sha256=digest(rp.read_bytes()), build_receipt=receipt)
    record = dict(schema='california_partition_libraries_v1', passed=True,
                  registry_sha256=digest(raw), source_sha256=source_pins(), libraries=libraries)
    write_new(output/'libraries.json', record)
    return record


def checked_fresh(entry, source_row, adapter):
    """Require an actual passed replay at the same state/cache/source identity."""
    import numpy as np
    path = Path(entry['result_path']).resolve(); data = path.read_bytes()
    if digest(data) != entry['sha256']: raise ValueError('fresh row result SHA mismatch')
    report = json.loads(data)
    if report.get('passed') is not True or report.get('status') != 'replayed' or report.get('id') != source_row['id']:
        raise ValueError('fresh source row is not a passed replay of the required identity')
    actual = report['actual']
    for name, expected in [('state_sha256', source_row['state']['sha256']),
                           ('cache_sha256', source_row['cache']['sha256']),
                           ('native_source_sha256', adapter['native']['sha256']),
                           ('python_source_sha256', adapter['python']['sha256'])]:
        if actual.get(name) != expected: raise ValueError('fresh source '+name+' mismatch')
    if actual['components']['n_events'] != source_row['n_events_expected']:
        raise ValueError('fresh source target count mismatch')
    array = actual['native_array_components']
    array_path = resolve(path.parent, array['path']); raw = array_path.read_bytes()
    if digest(raw) != array['sha256']: raise ValueError('fresh native array SHA mismatch')
    with np.load(io.BytesIO(raw), allow_pickle=False) as f:
        logs = {k: f['event_log_'+k+'_intensity'].copy() for k in ('point','cell','zone','ground')}
    n = source_row['n_events_expected']
    if any(a.shape != (n,) or not np.isfinite(a).all() for a in logs.values()):
        raise ValueError('fresh native event arrays shape/finite mismatch')
    return logs, actual, dict(result_sha256=digest(data), native_arrays_sha256=digest(raw),
                             source_row_id=source_row['id'])


def cache_arrays(inputs, spec):
    import numpy as np
    with np.load(io.BytesIO(inputs.read(spec)), allow_pickle=False) as f:
        metadata = json.loads(str(f['metadata_json'].item()))
        arrays = {k: f[k].copy() for k in f.files if k != 'metadata_json'}
    return arrays, metadata


def numeric_delta(actual, expected, tolerance, path=''):
    """Compare historical numerical components, including arrays/per-event ratios."""
    checks = []
    if isinstance(expected, dict):
        for key, value in expected.items():
            if key in ('selected_candidate_id',): continue
            if key not in actual:
                if isinstance(value, (dict,list,int,float)) and not isinstance(value,bool):
                    raise ValueError('missing current field '+path+'/'+key)
                continue
            checks.extend(numeric_delta(actual[key], value, tolerance, path+'/'+key))
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected): raise ValueError('comparison shape '+path)
        for i, (a,b) in enumerate(zip(actual,expected)):
            checks.extend(numeric_delta(a,b,tolerance,path+'/'+str(i)))
    elif isinstance(expected, (int,float)) and not isinstance(expected,bool):
        if isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isfinite(actual):
            raise ValueError('nonfinite/missing current numeric '+path)
        delta = abs(float(actual)-float(expected))
        limit = 0.0 if isinstance(expected,int) else tolerance
        checks.append(dict(field=path,actual=actual,expected=expected,delta=delta,tolerance=limit,passed=delta<=limit))
    elif expected is None:
        if actual is not None: raise ValueError('null semantic mismatch '+path)
    elif path.rsplit('/',1)[-1] in ('membership_sha256','range_id','category','episode_id','block_id','start_utc','end_utc'):
        if actual != expected: raise ValueError('partition identity mismatch '+path)
    return checks


def component_view(row, kind):
    if kind == 'annual':
        ground=row['event_ground_log']; E=row['integrated_intensity']; M=row['mark_logscore']
        location=row['conditional_location_logscore']; timing=row['timing_logscore']; joint=row['joint_logscore']
    else:
        ground=row['timing_event']; E=row['timing_compensator']; M=row['inherited_mark']
        location=row['conditional_location']; timing=row['timing']; joint=row['joint']
    return dict(P=ground+location,E=E,C=-E,M=M,timing=timing,location=location,joint=joint)


def evaluate_row(inputs, registry, row, inherited, fresh, modules, engines):
    import numpy as np
    package, parent = inherited[row['source_registry']]
    source = next(r for r in parent['rows'] if r['id']==row['fresh_score_row_id'])
    support_package, support_registry = inherited[row['support_registry']]
    support = next(r for r in support_registry['rows'] if r['id']==row['support_row_id'])
    support_inputs = Inputs(support_package); source_inputs = Inputs(package)
    state = source_inputs.json(source['state'])
    arrays, meta = cache_arrays(support_inputs, support['cache'])
    primary_arrays, primary_meta = cache_arrays(source_inputs, source['cache'])
    for key in ('event_time','parent_time'):
        if not np.array_equal(arrays[key], primary_arrays[key]): raise ValueError('support cache chronology mismatch')
    for key in ('beta','T0','start','end','n_events','n_parents'):
        if meta[key] != primary_meta[key]: raise ValueError('support nuisance mismatch '+key)
    if meta['n_events'] != row['n_events_expected']: raise ValueError('row target count mismatch')
    logs, actual, dependency = checked_fresh(fresh['rows'][source['id']], source, parent['adapters'][source['adapter']])
    if actual['parameters'] != state['parameters']: raise ValueError('fresh selected parameters mismatch')
    pars = state['parameters']; beta=meta['beta']; model=source['model']
    engine = engines[row['kind']]; fold=row['fold']; arm=row['arm']
    if row['kind']=='annual':
        reducer=modules['annual']['reducer']
        identity=dict(arm_id=arm,logical_arm_window_id=f'california_fold_{fold}__arm_{arm}')
        current_state=dict(event_time=arrays['event_time'],event_excess=arrays['event_excess'],logs=logs,beta=beta,identity=identity)
        results=[]
        for block in reducer.blocks(fold):
            exposure=engine.evaluate(model,pars,arrays['parent_time'],arrays['parent_excess'],beta,
                block['start_day'],block['end_day'],meta['T0'],arrays['mixture_weights'],arrays['mixture_rates'],
                arrays['background_cell_mass'],arrays['parent_cell_mass'].ravel())
            results.append(reducer.reduce_block(current_state,block,exposure))
        if sum(r['target_count'] for r in results)!=meta['n_events']: raise ValueError('annual count conservation')
        for name, key in [('P',None),('E','integrated_intensity'),('M','mark_logscore'),('timing','timing_logscore'),('location','conditional_location_logscore'),('joint','joint_logscore')]:
            value=math.fsum(component_view(r,'annual')[name] if key is None else r[key] for r in results)
            if abs(value-actual['components'][name])>registry['absolute_tolerance']: raise ValueError('fresh full-score annual conservation '+name)
    else:
        reducer=modules['sequence']['reducer']; partition=modules['sequence']['partition']
        cat=inputs.json(registry['catalogue']); cat=cat.get('events') if isinstance(cat,dict) else cat
        times=[partition.origin_us(r['origin_time_utc']) for r in cat]; magnitudes=[float(r['magnitude']) for r in cat]
        anchors=sorted(set(t for t,m in zip(times,magnitudes) if m>=6.)); episodes=partition.episodes(anchors)
        start=partition.origin_us(f'{2011+5*fold}-01-01T00:00:00Z'); end=partition.origin_us(f'{2016+5*fold}-01-01T00:00:00Z')
        selected=[i for i,t in enumerate(times) if start<=t<end]
        event_us=[times[i] for i in selected]; event_mag=[magnitudes[i] for i in selected]; event_ids=[cat[i]['event_id'] for i in selected]
        if len(selected)!=meta['n_events'] or max(abs(partition.day(t)-a) for t,a in zip(event_us,arrays['event_time']))>2e-12:
            raise ValueError('catalogue/fresh cache target chronology mismatch')
        if not np.array_equal(np.asarray(event_mag)-4.0,arrays['event_excess']): raise ValueError('catalogue mark identity mismatch')
        definitions=partition.rows_for_range(f'fold_{fold}',start,end,event_us,event_mag,episodes,anchors)
        definitions+=partition.episode_rows(fold,start,end,event_us,episodes,anchors)
        if fold==1:
            definitions+=partition.rows_for_range('calendar_2019',partition.origin_us('2019-01-01T00:00:00Z'),partition.origin_us('2020-01-01T00:00:00Z'),event_us,event_mag,episodes,anchors)
        def integral(a,b):
            return engine.evaluate('EP' if arm=='EP' else model,pars,arrays['parent_time'],arrays['parent_excess'],beta,
                partition.day(a),partition.day(b),meta['T0'],arrays['mixture_weights'],arrays['mixture_rates'])
        matrix=np.column_stack([logs[k] for k in ('point','cell','zone','ground')])
        results=[reducer.reduce_row(d,fold,arm,event_ids,event_mag,matrix,arrays['event_excess'],beta,integral) for d in definitions]
        reducer.conserve(results)
        total=next(r for r in results if r['range_id']==f'fold_{fold}' and r['category']=='total')
        for name,value in component_view(total,'sequence').items():
            if abs(value-actual['components'][name])>registry['absolute_tolerance']: raise ValueError('fresh full-score sequence conservation '+name)
    if len(results)!=row['expected_rows']: raise ValueError('partition row count mismatch')
    return dict(rows=results,components=[component_view(r,row['kind']) for r in results],fresh_dependency=dependency,
                state_sha256=source['state']['sha256'],cache_sha256=source['cache']['sha256'],support_cache_sha256=support['cache']['sha256'],parameters=pars)


def compare_rows(current, expected, kind, tolerance):
    fields=('fold_id','arm_id','block_id') if kind=='annual' else ('fold_id','arm','range_id','category','episode_id')
    index={tuple(r.get(k) for k in fields):r for r in expected}
    if len(index)!=len(expected) or len(current)!=len(expected): raise ValueError('reference roster differs')
    checks=[]
    for row in current:
        key=tuple(row.get(k) for k in fields)
        if key not in index: raise ValueError('partition key absent from reference')
        checks.extend(numeric_delta(row,index[key],tolerance,str(key)))
    return dict(passed=all(c['passed'] for c in checks),comparisons=len(checks),max_absolute_delta=max((c['delta'] for c in checks),default=0.),checks=checks)


def tiny_controls(modules, engines):
    """Hand-authored one-parent controls; not a historical replay."""
    weights=[1/195]*195; rates=[1.]*195; mass=[1/9]*9
    rows=[]
    for model,pars in [('E_fixed',[-2.,0.,.4]),('E_free',[-2.,0.,.4,0.]),('E_omori',[-2.,0.,.4,0.,1.5])]:
        expected_trigger=.3*((1-math.exp(-2)) if model!='E_omori' else (1-3**(-.5)))
        expected=2*math.exp(-2)+.4*expected_trigger
        annual=engines['annual'].evaluate(model,pars,[0.],[0.],2.,0.,2.,10.,weights,rates,mass,mass)
        sequence=engines['sequence'].evaluate(model,pars,[0.],[0.],2.,0.,2.,10.,weights,rates)
        parts=[engines['sequence'].evaluate(model,pars,[0.],[0.],2.,a,b,10.,weights,rates) for a,b in [(0.,1.),(1.,2.)]]
        checks=[abs(annual['integrated_intensity']-expected),abs(sequence['integrated_intensity']-expected),abs(sum(x['integrated_intensity'] for x in parts)-expected),abs(sum(annual['cell_integrated_intensity'])-expected)]
        rows.append(dict(model=model,deltas=checks,passed=max(checks)<=1e-12))
    if not all(r['passed'] for r in rows): raise ValueError('hand-authored interval controls failed')
    return dict(passed=True,scope='three hand-authored analytic interval controls and interval/cell additivity',rows=rows)


def run(registry_path,libraries_path,fresh_path,admission_path,output,row_ids,mode):
    if output.exists(): raise FileExistsError(output)
    rb=registry_path.read_bytes(); registry=json.loads(rb); rows={r['id']:r for r in registry['rows']}
    selected=list(rows) if row_ids is None else row_ids
    if not selected or len(set(selected))!=len(selected) or set(selected)-set(rows): raise ValueError('invalid selected roster')
    admission=json.loads(admission_path.read_bytes()); lb=libraries_path.read_bytes(); libraries=json.loads(lb)
    fb=fresh_path.read_bytes(); fresh=json.loads(fb); ib=(registry_path.parent/'input_manifest.json').read_bytes()
    for key,value in [('passed',True),('mode',mode),('registry_sha256',digest(rb)),('source_sha256',source_pins()),('row_ids',selected),('libraries_sha256',digest(lb)),('input_manifest_sha256',digest(ib)),('fresh_scores_sha256',digest(fb))]:
        if admission.get(key)!=value: raise ValueError('admission mismatch '+key)
    if libraries.get('registry_sha256')!=digest(rb) or libraries.get('source_sha256')!=source_pins(): raise ValueError('library manifest source mismatch')
    inputs=Inputs(registry_path.parent);receipts={}
    for kind,library in libraries['libraries'].items():
        data=Path(library['build_receipt_path']).read_bytes(); receipt=json.loads(data);receipts[kind]=digest(data)
        _, portability = portable_interval_source(kind, inputs.read(registry['native_libraries'][kind]))
        if (receipts[kind]!=library['build_receipt_sha256'] or receipt!=library['build_receipt'] or receipt.get('passed') is not True or library.get('portability')!=portability or library['source_sha256']!=registry['native_libraries'][kind]['sha256'] or receipt['source_sha256']!=portability['compiled_sha256'] or receipt['library_sha256']!=library['sha256'] or digest(Path(library['path']).read_bytes())!=library['sha256']): raise ValueError('interval build receipt mismatch')
    if admission.get('build_receipts_sha256')!=receipts: raise ValueError('build admission mismatch')
    threads=admission.get('numeric_threads')
    if isinstance(threads,bool) or threads not in (1,2): raise ValueError('thread cap missing')
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]=str(threads)
    import numpy as np
    from threadpoolctl import threadpool_limits,threadpool_info
    inherited={};base=registry_path.parent.parent
    for name,spec in registry['source_registries'].items():
        r=Inputs(base).json(spec);inherited[name]=(resolve(base,spec['path']).parent,r)
    output.mkdir(parents=True);started=time.monotonic()
    write_new(output/'launch.json',dict(registry_sha256=digest(rb),source_sha256=source_pins(),input_manifest_sha256=digest(ib),libraries_sha256=digest(lb),fresh_scores_sha256=digest(fb),admission_sha256=digest(admission_path.read_bytes()),build_receipts_sha256=receipts,row_ids=selected,mode=mode,runtime=dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),numeric_threads=threads,native_evaluator_threads=1)))
    modules=load_modules(inputs,registry);engines={k:modules[k]['native'].Exposure(v['path'],v['sha256']) for k,v in libraries['libraries'].items()}
    write_new(output/'controls.json',tiny_controls(modules,engines)); reports=[];calculated={}
    with threadpool_limits(limits=threads):
        if any(x['num_threads']>threads for x in threadpool_info()):raise RuntimeError('numeric thread limit')
        for index,row_id in enumerate(selected):
            row=rows[row_id]; tick=time.monotonic();rp=output/'rows'/f'{index:05d}'/'result.json'
            report=dict(id=row_id,passed=False,status='failed',feature_scope=row['feature_scope'])
            try:
                actual=evaluate_row(inputs,registry,row,inherited,fresh,modules,engines)
                report['actual']=actual
                reference=inputs.json(row['expected'])
                expected=[r for r in reference['arm_blocks' if row['kind']=='annual' else 'rows'] if r['fold_id']==row['fold'] and r['arm_id' if row['kind']=='annual' else 'arm']==row['arm']]
                comparison=compare_rows(actual['rows'],expected,row['kind'],registry['absolute_tolerance'])
                report.update(comparison=comparison,passed=comparison['passed'],status='replayed' if comparison['passed'] else 'failed')
                if report['passed']:calculated[row_id]=actual['rows']
            except Exception as exc:report.update(error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
            report['elapsed_seconds']=time.monotonic()-tick;write_new(rp,report)
            reports.append(dict(id=row_id,passed=report['passed'],status=report['status'],result=rp.relative_to(output).as_posix(),sha256=digest(rp.read_bytes()),elapsed_seconds=report['elapsed_seconds']))
            with (output/'progress.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(reports[-1],allow_nan=False)+'\n')
    aggregates={};aggregate_pass=True
    for group in ('primary_annual','m45_annual','sequence'):
        required=[r for r in registry['rows'] if r['group']==group]
        if not all(r['id'] in calculated for r in required):continue
        absolute=[v for r in required for v in calculated[r['id']]]
        ref=inputs.json(registry['references'][group])
        if group=='sequence':
            reducer=modules['sequence']['reducer'];absolute+=reducer.pool(absolute);reducer.conserve(absolute);contrasts=reducer.contrasts(absolute)
            comparison=compare_rows(absolute,ref['rows'],'sequence',registry['absolute_tolerance'])
        else:
            contrasts=modules['annual']['reducer'].contrasts(absolute)
            comparison=compare_rows(absolute,ref['arm_blocks'],'annual',registry['absolute_tolerance'])
        # Exact deterministic roster/order is produced by the original reducers.
        def key(r):return (r.get('fold_id'),r.get('range_id',r.get('block_id')),r.get('category'),r.get('episode_id'),r.get('candidate',r.get('contrast_id')),r.get('reference'))
        expected_map={key(r):r for r in ref['contrasts' if group=='sequence' else 'contrast_blocks']}
        if len(expected_map)!=len(contrasts):raise ValueError('aggregate contrast roster mismatch')
        checks=[]
        for r in contrasts:checks.extend(numeric_delta(r,expected_map[key(r)],registry['absolute_tolerance'],str(key(r))))
        passed=comparison['passed'] and all(x['passed'] for x in checks)
        record=dict(passed=passed,absolute_rows=absolute,contrasts=contrasts,absolute_comparison=comparison,contrast_checks=checks)
        path=output/(group+'_aggregate.json');write_new(path,record);aggregates[group]=dict(path=path.name,sha256=digest(path.read_bytes()),passed=passed,absolute_rows=len(absolute),contrasts=len(contrasts));aggregate_pass &= passed
    passed=all(x['passed'] for x in reports) and aggregate_pass
    full=selected==list(rows)
    if full and len(aggregates)!=3:passed=False
    result=dict(schema='california_partition_replay_result_v1',passed=passed,mode=mode,full_registry=full,requested_rows=len(selected),completed_rows=len(reports),passed_rows=sum(x['passed'] for x in reports),failed_rows=sum(not x['passed'] for x in reports),entire_task_complete=False,registry_sha256=digest(rb),elapsed_seconds=time.monotonic()-started,rows=reports,aggregates=aggregates,scope='Calendar and causal sequence partitions using fresh passed event-score arrays and freshly evaluated original interval kernels; unchanged selected states, no fitting or feature regeneration.')
    write_new(output/'result.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registry',type=Path,default=Path(__file__).with_name('california_blocks')/'registry.json');p.add_argument('--output',type=Path,required=True);p.add_argument('--build',action='store_true');p.add_argument('--libraries',type=Path);p.add_argument('--fresh-scores',type=Path);p.add_argument('--admission',type=Path);p.add_argument('--rows',type=Path);p.add_argument('--mode',choices=['pilot','full','completion'])
    args=p.parse_args()
    if args.build:result=build(args.registry.resolve(),args.output.resolve())
    else:
        if not all([args.libraries,args.fresh_scores,args.admission,args.mode]):p.error('replay requires libraries, fresh-scores, admission and mode')
        result=run(args.registry.resolve(),args.libraries.resolve(),args.fresh_scores.resolve(),args.admission.resolve(),args.output.resolve(),json.loads(args.rows.read_text()) if args.rows else None,args.mode)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','libraries')}));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
