"""Replay original unit-mark S04 selected states, without refits or generation.

The three historical completion stages keep their original train/test orders.
Only saved histories, fitted states and fixed laws enter the evaluator. Expected
scores are read afterwards. Timing/location splits were not exported by this
joint-intensity evaluator and are explicitly unavailable, never imputed.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import ctypes as C
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, digest, write_new

KEYS = ('parents', 'events', 'space', 'times', 'weights', 'meta')
MODES = [('LI', 0, 0), ('LIplus_immigrant', 1, 0), ('LIplus_inclusive', 1, 1)]
NAMES = ('S0_uniform_null', 'S1_smooth_null', 'S2_narrow_short', 'S3_broad_long')


def source_pins():
    folder = Path(__file__).resolve().parent
    return {name: digest((folder/name).read_bytes()) for name in
            ('__init__.py', 'core.py', 'inhibition_build.py', 'inhibition_replay.py')}


def scientific_modules(inputs, registry, folder):
    """Load exact original modules; no fitter/generator is invoked."""
    loaded, saved = {}, {}
    try:
        for name in ('spatial', 'geometry_plan', 'generator', 'controls_campaign'):
            resource = registry['source_resources'][name+'.py']
            path = inputs.materialize(resource, folder, '.py')
            alias = '_original_s04_' + name + '_' + resource['sha256']
            spec = importlib.util.spec_from_file_location(alias, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[alias] = module
            saved[name] = sys.modules.get(name)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            loaded[name] = module
    finally:
        for name, old in saved.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old
    return loaded['controls_campaign']


class Native:
    def __init__(self, path):
        self.lib = C.CDLL(str(path))
        self.ptr = C.POINTER(C.c_double)
        self.lib.m02_create.argtypes = [C.c_int]*4 + [self.ptr]*6
        self.lib.m02_create.restype = C.c_void_p
        self.lib.m02_integrated.argtypes = [C.c_void_p, C.c_int, C.c_int, self.ptr, self.ptr]
        self.lib.m02_integrated.restype = C.c_int
        self.lib.m02_free.argtypes = [C.c_void_p]
        self.lib.m02_free.restype = None
        self.lib.m02_integrated_error.restype = C.c_char_p

    def create(self, data):
        handle = self.lib.m02_create(*(len(data[k]) for k in KEYS[:4]),
                                     *(data[k].ctypes.data_as(self.ptr) for k in KEYS))
        if not handle:
            raise ArithmeticError(self.lib.m02_integrated_error().decode())
        return handle

    def evaluate(self, handle, pars, plus, inclusive):
        import numpy as np
        pars = np.ascontiguousarray(pars, dtype=np.float64)
        if pars.shape != (3,) or not np.isfinite(pars).all():
            raise ValueError('Invalid saved inhibition vector')
        result = np.empty(6, dtype=np.float64)
        status = self.lib.m02_integrated(handle, plus, inclusive,
                                        pars.ctypes.data_as(self.ptr), result.ctypes.data_as(self.ptr))
        if status or not np.isfinite(result).all():
            raise ArithmeticError(self.lib.m02_integrated_error().decode())
        return result

    def free(self, handle):
        self.lib.m02_free(handle)


def construct(c, rows, case, geometry, phase, order):
    """Original Integrated/refine_worker constructor, unchanged scalar laws."""
    import numpy as np
    name = NAMES[case['regime']]
    _, background, eta, ell, psi = c.G.ROSTER[name]
    law = c.G.Law(name, case['seed'], background, eta, ell, psi)
    gm = c.G.fitting_metadata(law)
    pars = [law.a, law.d, law.n, np.log(law.c), law.p]
    start, end = (30, 395) if phase == 'train' else (395, 760)
    m = dict(start=start, end=end, T0=760, beta=gm['beta'], sigma=gm['sigma_km'],
             bg_floor=gm['bg_floor'], kde_h=gm['kde_h'] or 10)
    a = c.canonical_arrays(rows[:, 0], rows[:, 1:3], rows[:, 3],
        np.asarray(gm['rectangles']), np.asarray(gm['reference_pi']),
        np.asarray(gm['kde_xy']).reshape(-1, 2), np.asarray(gm['kde_weight']), m, pars, geometry)
    plan_a = dict(rectangles=a['rectangles'], reference_pi=a['reference_pi'],
        kde_xy=a['kde_training_xy'], kde_weight=a['kde_weight'],
        kde_normalizer=a['kde_normalizers'], parent_xy=a['parent_xy'])
    plans, info = c._adaptive_area_space(plan_a,
        dict(bg_floor=m['bg_floor'], kde_h=m['kde_h']), [order], 1e-8, 20)
    plan = plans[order]
    xy = plan['space_xy']
    b, cells = c.background(xy, a, m)
    space = np.ascontiguousarray(np.column_stack([xy, plan['space_weight']/b, b,
        a['reference_pi'][cells]/a['cell_areas'][cells]]))
    times, weights = c.time_plan(a['parent_time'], m['start'], m['end'], np.exp(pars[3]), 2*order)
    features = c.S.features(a, m, pars[3:5])
    baseline = c.S.evaluate(features, pars[:3])[0]
    parents = np.ascontiguousarray(np.column_stack([a['parent_time'], a['parent_xy'],
        a['parent_excess'], a['parent_fertility'], a['parent_normalizer']]))
    events = np.ascontiguousarray(np.column_stack([a['event_time'], a['event_xy'],
        a['event_background_density'], pars[2]*features['hp'],
        a['reference_pi'][a['event_cell'].astype(int)]/a['cell_areas'][a['event_cell'].astype(int)]]))
    meta = np.array([*pars[:3], np.exp(pars[3]), pars[4], m['T0'],
                     baseline['compensator'], features['marks'], m['sigma']])
    return dict(parents=parents, events=events, space=space, times=times, weights=weights, meta=meta), info


def grid_digest(data):
    import hashlib
    import numpy as np
    result = hashlib.sha256()
    for key in KEYS:
        value = np.ascontiguousarray(data[key])
        result.update(key.encode()); result.update(str(value.dtype).encode())
        result.update(str(value.shape).encode()); result.update(value.tobytes())
    return result.hexdigest()


def chunks(data, budget):
    """Partition spatial integration, retaining base/event contributions once."""
    import numpy as np
    np_, ne, ns, nt = (len(data[k]) for k in KEYS[:4])
    shared = 8*(9*np_+10*ne+5*nt+nt*np_)+4*(nt+1)
    perrow = 8*(9+2*np_+2*nt)
    count = int((budget-shared)//max(1, perrow))
    if count < 1:
        raise MemoryError('Shared native features exceed the fixed chunk budget')
    for start in range(0, ns, count):
        item = dict(data)
        item['space'] = np.ascontiguousarray(data['space'][start:start+count])
        item['meta'] = data['meta'].copy()
        if start:
            item['events'] = np.empty((0, 6), dtype=np.float64)
            item['meta'][6:8] = 0.
        yield item


def selected_states(fit):
    eligible = [r for r in fit['records'] if r.get('success') and r.get('finite_feasible')]
    eligible.append(dict(start=-1, pars=fit['floor'], nll=fit['floor_nll']))
    winner = min(eligible, key=lambda r: (r['nll'], r['start'] >= 0, r['start']))
    if (fit['status'] != 'complete' or winner['pars'] != fit['selected']['pars']
            or winner['nll'] != fit['selected']['nll']
            or {r['start'] for r in eligible if r['start'] >= 0} != set(range(8))):
        raise ValueError('Saved training selection or complete-start identity differs')
    return fit['selected']['pars'], fit['floor']


def tiny_native_control(native):
    """Invented two-location control: full versus forced split, all modes."""
    import numpy as np
    data = dict(parents=np.array([[.2,0.,0.,.1,1.,1.]]),
        events=np.array([[1.,.2,.1,.1,.03,.1]]),
        space=np.array([[0.,0.,.5,.1,.1],[1.,1.,.5,.1,.1]]),
        times=np.array([.5,1.5]),weights=np.array([1.,1.]),
        meta=np.array([-2.,.1,.3,.05,1.3,2.,.8,-.2,10.]))
    # Same memory formula as chunks, chosen to force exactly one spatial row.
    shared=8*(9+10+5*2+2)+4*3
    budget=shared+8*(9+2+2*2)
    reports=[]
    for name,plus,inclusive in MODES:
        for eta in (0.,.4):
            pars=[eta,math.log(10),math.log(2)]
            handle=native.create(data)
            try: whole=native.evaluate(handle,pars,plus,inclusive)
            finally: native.free(handle)
            total=np.zeros(6); pieces=0
            for piece in chunks(data,budget):
                handle=native.create(piece)
                try: total+=native.evaluate(handle,pars,plus,inclusive)
                finally: native.free(handle)
                pieces+=1
            error=float(np.max(np.abs(total-whole)))
            floor_error=None
            if eta==0:
                event=data['events'][0]
                point=math.log(math.exp(data['meta'][0]+data['meta'][1]*(2*event[0]/data['meta'][5]-1))*event[3]+event[4])
                expected=data['meta'][6]-point-data['meta'][7]
                floor_error=abs(float(whole[0])-expected)
            passed=pieces==2 and error<=1e-12 and (floor_error is None or floor_error<=1e-12)
            reports.append(dict(model=name,eta=eta,pieces=pieces,maximum_split_delta=error,
                analytic_floor_nll_error=floor_error,absolute_tolerance=1e-12,passed=passed))
    return dict(passed=all(r['passed'] for r in reports),controls=reports,
        scope='Hand-authored one-parent/one-event/two-location example only; no historical likelihood.')


def joint_components(value, metadata):
    nll, _, _, _, deficit, point = map(float, value)
    exposure, marks = float(metadata[6])-deficit, float(metadata[7])
    joint = point-exposure+marks
    if not all(math.isfinite(x) for x in (joint, exposure, marks, point)) or abs(joint+nll)>1e-7:
        raise ValueError('Joint native decomposition failed')
    return dict(P=point, E=exposure, C=-exposure, M=marks, joint=joint,
                timing=None, location=None,
                split_scope='Original fixed-backbone native functional exports joint point intensity only; no ground-intensity split was evaluated.')


def evaluate_case(inputs, registry, case, c, native, geometry, threads, budget, folder):
    """Never reads the expected-score resource."""
    import numpy as np
    with np.load(io.BytesIO(inputs.read(case['history'])), allow_pickle=False) as saved:
        rows = np.ascontiguousarray(saved['rows'])
    if digest(rows.tobytes()) != case['rows_sha256']:
        raise ValueError('Raw history array identity differs')
    fits = {name: inputs.json(case['fits'][name]) for name, _, _ in MODES}
    jobs = [(name, plus, inclusive, label, pars) for name, plus, inclusive in MODES
            for label, pars in zip(('selected', 'floor'), selected_states(fits[name]))]
    phases = {}
    for phase in ('train', 'test'):
        data, geometry_info = construct(c, rows, case, geometry, phase, case['phase_orders'][phase])
        if len(data['events']) != case['n_'+phase]:
            raise ValueError('Reconstructed event count differs')
        totals = {(name, label): np.zeros(6) for name, _, _, label, _ in jobs}
        count = 0
        for piece in chunks(data, budget):
            handle = native.create(piece)
            try:
                def call(job):
                    name, plus, inclusive, label, pars = job
                    return name, label, native.evaluate(handle, pars, plus, inclusive)
                with ThreadPoolExecutor(max_workers=threads) as pool:
                    for name, label, value in pool.map(call, jobs):
                        totals[name, label] += value
            finally:
                native.free(handle)
            count += 1
        phases[phase] = dict(order=case['phase_orders'][phase], n_events=len(data['events']),
            input_digest=grid_digest(data), metadata=data['meta'].tolist(), geometry=geometry_info,
            space_nodes=len(data['space']), time_nodes=len(data['times']), chunks=count,
            models={name: {label: dict(parameters=pars, output=totals[name,label].tolist(),
                components=joint_components(totals[name,label], data['meta']))
                for label, pars in zip(('selected', 'floor'), selected_states(fits[name]))}
                for name, _, _ in MODES})
        write_new(folder/(phase+'.json'), phases[phase])
        del data
    return phases


def compare_case(actual, expected, case, registry):
    checks = []
    for phase in ('train', 'test'):
        a, e = actual[phase], expected['phases'][phase]
        if a['n_events'] != e['n_events'] or a['order'] != e['order']:
            raise ValueError('Original phase identity differs')
        for name, _, _ in MODES:
            for label in ('selected', 'floor'):
                value, reference = a['models'][name][label], e['selected'][name][label]
                if value['parameters'] != reference['parameters']:
                    raise ValueError('Selected original parameter identity differs')
                deltas = [float(x-y) for x, y in zip(value['output'], reference['output'])]
                tolerance = registry['floor_tolerance'] if label == 'floor' else registry['absolute_nll_tolerance']
                passed = (abs(deltas[0]) <= tolerance and abs(deltas[4]) <= registry['absolute_nll_tolerance']
                          and abs(deltas[5]) <= registry['absolute_nll_tolerance'])
                checks.append(dict(phase=phase, model=name, state=label, passed=passed,
                    output_deltas=deltas, nll_absolute_tolerance=tolerance,
                    gradient_scope='Gradient deltas retained as diagnostics, not score completion gates.'))
    comparisons = []
    for name, _, _ in MODES:
        train = actual['train']['models'][name]
        test = actual['test']['models'][name]
        active = train['floor']['output'][0]-train['selected']['output'][0] > 1.5*math.log(max(1, case['n_train']))
        for gate in (['raw'] if name == 'LI' else ['raw', 'BIC']):
            chosen = 'selected' if gate == 'raw' or active else 'floor'
            gain = test['floor']['output'][0]-test[chosen]['output'][0]
            original = next(r for r in expected['comparisons'] if (r['model'], r['gate']) == (name, gate))
            off_floor = test[chosen]['parameters'][0] > 0
            delta = gain-original['gain']
            passed = (abs(delta) <= registry['absolute_gain_tolerance'] and (gain > 0) == original['win']
                      and off_floor == original['off_floor'])
            comparisons.append(dict(model=name, gate=gate, gain=gain, original_gain=original['gain'],
                delta=delta, absolute_tolerance=registry['absolute_gain_tolerance'], passed=passed,
                win=gain > 0, numerical_near_zero=abs(gain)<=1e-9, off_floor=off_floor,
                training_gate_active=active, selected_state=chosen))
    return dict(passed=all(x['passed'] for x in checks+comparisons), checks=checks, comparisons=comparisons,
        original_input_digest_matches={phase: actual[phase]['input_digest']==expected['phases'][phase]['input_digest']
                                       for phase in ('train', 'test')},
        feature_hash_scope='Derived feature hashes recorded; scalar functional tolerances control cross-platform replay.')


def run(registry_path, libraries_path, admission_path, output, selected, mode):
    if output.exists():
        raise FileExistsError('Output must be new')
    raw = registry_path.read_bytes(); registry = json.loads(raw)
    by_id = {r['id']: r for r in registry['rows']}
    selected = selected if selected is not None else list(by_id)
    if len(by_id)!=len(registry['rows']) or not selected or len(set(selected))!=len(selected) or set(selected)-set(by_id):
        raise ValueError('Invalid fixed roster')
    admraw = admission_path.read_bytes(); admission = json.loads(admraw)
    libraw = libraries_path.read_bytes(); libraries = json.loads(libraw)
    for field, actual in [('registry_sha256', digest(raw)), ('libraries_sha256', digest(libraw)),
        ('input_manifest_sha256', digest((registry_path.parent/'input_manifest.json').read_bytes())),
        ('source_sha256', source_pins()), ('mode', mode), ('row_ids', selected)]:
        if admission.get(field) != actual:
            raise ValueError('Admission mismatch: '+field)
    if admission.get('passed') is not True or libraries.get('registry_sha256') != digest(raw):
        raise ValueError('Unaccepted replay/source identity')
    pins, paths = {}, {}
    for name, filename in [('cpu','cpu_reference.cpp'), ('radial','radial.cpp')]:
        lib = libraries['libraries'][name]; path = Path(lib['path']).resolve()
        receipt_raw = Path(lib['build_receipt_path']).read_bytes(); receipt = json.loads(receipt_raw)
        pins[name] = digest(receipt_raw)
        if (digest(path.read_bytes()) != lib['sha256'] or receipt != lib['build_receipt']
            or receipt.get('passed') is not True or pins[name] != lib['build_receipt_sha256']
            or receipt['source_sha256'] != registry['source_resources'][filename]['sha256']
            or receipt['library_sha256'] != lib['sha256']):
            raise ValueError('Native build identity differs: '+name)
        paths[name] = path
    if admission.get('build_receipts_sha256') != pins:
        raise ValueError('Admission build receipt mismatch')
    threads = admission.get('numeric_threads')
    if isinstance(threads,bool) or threads not in (1,2):
        raise ValueError('One or two numerical threads must be declared')
    budget = admission.get('chunk_bytes')
    if isinstance(budget,bool) or not isinstance(budget,int) or not 64*2**20 <= budget <= 1024*2**20:
        raise ValueError('Explicit chunk budget must be between64MiB and1GiB')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = str(threads)
    import numpy as np
    from threadpoolctl import threadpool_info, threadpool_limits
    inputs = Inputs(registry_path.parent); output.mkdir(parents=True)
    write_new(output/'launch.json', dict(admission_sha256=digest(admraw), registry_sha256=digest(raw),
        source_sha256=source_pins(), libraries_sha256=digest(libraw), build_receipts_sha256=pins,
        row_ids=selected, mode=mode, numerical_lease=admission.get('numerical_lease'),
        runtime=dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),
                     numeric_threads=threads,chunk_bytes=budget)))
    c = scientific_modules(inputs, registry, output/'source')
    native = Native(paths['cpu']); geometry = c.S.Geometry(paths['radial'])
    with threadpool_limits(limits=threads):
        controls=tiny_native_control(native)
    write_new(output/'tiny_controls.json',controls)
    if not controls['passed']:
        raise ArithmeticError('Hand-authored native split/floor controls failed')
    results = []; began = time.monotonic()
    for index, identity in enumerate(selected):
        case = by_id[identity]; folder=output/'rows'/f'{index:05d}'; folder.mkdir(parents=True)
        report = dict(id=identity,stage=case['stage'],passed=False,status='failed'); start=time.monotonic()
        try:
            with threadpool_limits(limits=threads):
                if any(v['num_threads']>threads for v in threadpool_info()):
                    raise RuntimeError('Numerical thread cap exceeded')
                actual = evaluate_case(inputs,registry,case,c,native,geometry,threads,budget,folder)
                if any(v['num_threads']>threads for v in threadpool_info()):
                    raise RuntimeError('A scientific module exceeded numerical thread cap')
            comparison = compare_case(actual,inputs.json(case['expected']),case,registry)
            report.update(passed=comparison['passed'],status='replayed' if comparison['passed'] else 'failed',
                comparison=comparison,history_sha256=case['history']['sha256'],
                state_sha256={n:s['sha256'] for n,s in case['fits'].items()},
                feature_scope=case['feature_scope'],fit_scope=case['fit_scope'])
        except Exception as error:
            report.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        report['phase_records']={phase:dict(path=(folder/(phase+'.json')).relative_to(output).as_posix(),
            sha256=digest((folder/(phase+'.json')).read_bytes())) for phase in ('train','test')
            if (folder/(phase+'.json')).is_file()}
        report['elapsed_seconds']=time.monotonic()-start
        write_new(folder/'result.json',report)
        row=dict(id=identity,passed=report['passed'],status=report['status'],
            result=(folder/'result.json').relative_to(output).as_posix(),
            sha256=digest((folder/'result.json').read_bytes()),elapsed_seconds=report['elapsed_seconds'])
        results.append(row)
        with (output/'progress.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(row)+'\n');stream.flush()
    result=dict(schema='original_s04_replay_result_v1',passed=all(r['passed'] for r in results),
        rows=results,requested_rows=len(selected),completed_rows=len(results),passed_rows=sum(r['passed'] for r in results),
        full_registry=selected==list(by_id),entire_task_complete=False,elapsed_seconds=time.monotonic()-began,
        controls_record=dict(path='tiny_controls.json',sha256=digest((output/'tiny_controls.json').read_bytes())),
        scope='Original selected/floor held-out joint-intensity scores and training BIC gates only; no refits, generation or optimizer-search replay.')
    write_new(output/'result.json',result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('registry','libraries','admission','output'):
        parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--rows',type=Path)
    parser.add_argument('--mode',required=True,choices=('pilot','full','completion'))
    args=parser.parse_args()
    selected=json.loads(args.rows.read_text(encoding='utf-8')) if args.rows else None
    result=run(args.registry,args.libraries,args.admission,args.output,selected,args.mode)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
    raise SystemExit(0 if result['passed'] else 1)
