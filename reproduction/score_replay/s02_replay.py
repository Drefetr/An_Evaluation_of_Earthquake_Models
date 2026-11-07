"""Selected-state S02 raw-clock replay. No optimization or simulation."""
from pathlib import Path
import argparse
import ctypes
import csv
import datetime
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import shutil
import statistics
import sys
import time
import zipfile

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_name] = '2'
import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits

HERE = Path(__file__).resolve().parent / 's02'
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
PHASES = ('null', 'alternative')
METHODS = ('M1', 'M2')


def require(value, why):
    if not value:
        raise ValueError(why)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON ' + v)))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(temp, path)


def source_identity():
    files = [Path(__file__), ROOT/'engine/cpu_build.py', ROOT/'engine/stage2_followup/native_build.py']
    files += [p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py', '.cpp', '.json')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


def load_oracle():
    spec = importlib.util.spec_from_file_location('s02_archived_q01', HERE/'original/f_oracle_v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inputs:
    def __init__(self, protocol):
        self.root = ROOT/'reproduction/s02'
        require(sha(self.root/'manifest.json') == protocol['manifest_sha256'], 'S02 manifest changed')
        self.manifest = read(self.root/'manifest.json')
        archive = self.root/self.manifest['archive']['path']
        require(sha(archive) == protocol['archive_sha256'] == self.manifest['archive']['sha256'], 'S02 archive changed')
        self.zip = zipfile.ZipFile(archive)
        self.members = {m['path']: m for m in self.manifest['members']}
        require(len(self.zip.namelist()) == len(self.members) and set(self.zip.namelist()) == set(self.members), 'S02 member roster')
        self.cases = sorted(self.json('index.json')['cases'], key=lambda c: (c['forest'], c['h']))
        require([c['id'] for c in self.cases] == protocol['roster'] and len(self.cases) == 300, 'S02 catalogue roster')
        require({(c['forest'], c['h']) for c in self.cases} == {(i, h) for i in range(100) for h in (0., .5, .9)}, 'S02 paired forest roster')
        for copy in protocol['source_copies']:
            require(sha(HERE/copy['path']) == copy['sha256'] == self.members[copy['archive_member']]['sha256'], 'Archived source copy changed')
            require((HERE/copy['path']).read_bytes() == self.raw(copy['archive_member']), 'Archived source bytes differ')
        setting = self.json(protocol['fixed_law_member'])['law']
        fitted = setting['alternative_generating_fit']
        self.law = dict(T=float(setting['horizon_days']), coordinate=float(setting['coordinate_horizon_days']),
                        beta=float(setting['beta']), gamma=.75*math.log(10), n=.5, ratio=.7,
                        stress=fitted['stress'], trigger=fitted['trigger'])

    def raw(self, member):
        raw = self.zip.read(member)
        expected = self.members[member]
        require(len(raw) == expected['bytes'] and hashlib.sha256(raw).hexdigest() == expected['sha256'], 'Member bytes: ' + member)
        return raw

    def json(self, member):
        return json.loads(self.raw(member))

    def case(self, meta):
        raw = self.raw(meta['history'])
        require(hashlib.sha256(raw).hexdigest() == meta['history_sha256'], 'History/selected-state identity')
        table = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        require(len(table) == meta['generation']['events'] and meta['generation']['status'] == 'ok', 'Generation event count/status')
        data = {key: np.array([float(row[col]) for row in table], dtype=np.float64) for key, col in
                [('times', 'time_hi'), ('times_lo', 'time_lo'), ('event_gaps', 'event_gap'), ('excess', 'excess')]}
        require(all(np.isfinite(v).all() for v in data.values()), 'Nonfinite history')
        saved = self.json(meta['fit'])
        require(all(saved[k] == meta[k] for k in ('id', 'forest', 'h', 'history_sha256')), 'Fit identity')
        require(saved['status'] == 'complete' and len(saved['methods']) == 2 and {m['procedure'] for m in saved['methods']} == set(METHODS), 'Selected method roster')
        for method in saved['methods']:
            validate_selected(method, self.law)
        return data, saved

    def close(self):
        self.zip.close()


def validate_selected(method, law):
    ratio = .7 if method['procedure'] == 'M1' else 0.
    require(method['status'] == 'complete' and method['candidate_ratio'] == ratio, 'Historical method is incomplete/wrong ratio')
    require(all(c['passed'] is True for c in method['controls']), 'Historical selected numerical control failed')
    for phase in PHASES:
        state = method[phase]
        p = state['pars']
        require(len(p) == 4 and all(math.isfinite(v) for v in p), 'Selected vector')
        require(-12 <= p[0] <= 0 and -2 <= p[1] <= 2 and p[2] == .5 and 0 <= p[3] <= 3, 'Original selected parameter bounds/fixed n')
        require(phase != 'null' or p[3] == 0., 'Null is not eta0')
        require(state['ratio'] == ratio and state['trigger'] == law['trigger'] and math.isfinite(state['nll']), 'Candidate law/state mismatch')


class Extra:
    def __init__(self, native, oracle):
        self.native, self.oracle = native, oracle
        for name, arguments in [('s02_components', [ctypes.c_void_p, oracle.D, oracle.D]),
                                ('s02_direct_glr', [ctypes.c_void_p, oracle.D, oracle.D, oracle.D])]:
            function = getattr(native.lib, name)
            function.argtypes, function.restype = arguments, ctypes.c_int

    def components(self, state, parameters):
        p, out = self.oracle.arr(parameters), np.empty(5)
        if self.native.lib.s02_components(state.handle, self.oracle.ptr(p), self.oracle.ptr(out)):
            raise ArithmeticError(self.native.lib.qf_error().decode())
        return out

    def glr(self, state, null, alternative):
        zero, active, out = self.oracle.arr(null), self.oracle.arr(alternative), np.empty(3)
        if self.native.lib.s02_direct_glr(state.handle, self.oracle.ptr(zero), self.oracle.ptr(active), self.oracle.ptr(out)):
            raise ArithmeticError(self.native.lib.qf_error().decode())
        return out


def evaluate_selected(state, extra, parameters, expected_nll, mark, tolerance, identity_tolerance):
    value = state.evaluate(parameters)
    components = extra.components(state, parameters)
    p, exposure, immigrant, offspring, nodes = map(float, components)
    nll = float(value[0])
    require(np.isfinite(value).all() and np.isfinite(components).all() and exposure >= 0, 'Nonfinite/negative score')
    identity_delta = abs(nll - (exposure-p))
    require(identity_delta <= identity_tolerance, 'Component/NLL identity')
    require(abs(exposure-immigrant-offspring) <= identity_tolerance and nodes == float(value[5]), 'Exposure components/node count')
    delta = nll-expected_nll
    return dict(parameters=list(parameters), nll_ground=nll, expected_nll_ground=expected_nll, nll_delta=delta,
                absolute_nll_delta=abs(delta), tolerance=tolerance, passed=abs(delta) <= tolerance,
                P=p, E=exposure, C=-exposure, M=mark, timing=-nll, joint=-nll+mark,
                background_exposure=immigrant, triggering_exposure=offspring,
                nll_component_absolute_delta=identity_delta, gradient=list(map(float, value[1:5])), quadrature_nodes=int(nodes))


def run_case(meta, inputs, oracle, native, protocol, output, deadline, refined):
    started = time.monotonic()
    record = dict(case_id=meta['id'], forest=meta['forest'], h=meta['h'], passed=False, status='running', methods=[])
    path = output/(meta['id']+'.json')
    write(path, record)
    try:
        data, saved = inputs.case(meta)
        oracle.clock(data, inputs.law, 'paired')  # validate exact binary64 paired-clock semantics before allocating features
        mark = len(data['excess'])*math.log(inputs.law['beta'])-inputs.law['beta']*math.fsum(map(float, data['excess']))
        record.update(events=len(data['times']), source_members={name: inputs.members[name]['sha256'] for name in
                      [meta['history'], meta['fit'], meta['generation_config']]}, law=inputs.law, mark_score=mark)
        extra = Extra(native, oracle)
        for method_name in METHODS:
            require(time.monotonic() < deadline, 'Replay wall deadline')
            original = next(m for m in saved['methods'] if m['procedure'] == method_name)
            method = dict(procedure=method_name, ratio=protocol['candidate_ratios'][method_name], passed=False, status='running', states={})
            record['methods'].append(method); write(path, record)
            state, high = None, None
            try:
                state = native.state(data, inputs.law, 'paired', method['ratio'], 32, True)
                for phase in PHASES:
                    require(time.monotonic() < deadline, 'Replay wall deadline')
                    selected = original[phase]
                    method['states'][phase] = evaluate_selected(state, extra, selected['pars'], selected['nll'], mark,
                                                                protocol['tolerance'], protocol['component_identity_tolerance'])
                    method['states'][phase]['source_pointer'] = '/methods/'+str(saved['methods'].index(original))+'/'+phase
                    write(path, record)
                direct = extra.glr(state, original['null']['pars'], original['alternative']['pars'])
                subtract = 2*(method['states']['null']['nll_ground']-method['states']['alternative']['nll_ground'])
                expected = original['direct_contrast16']['statistic']
                method['glr'] = dict(value=float(direct[0]), point_delta=float(direct[1]), signed_compensator_delta=float(direct[2]),
                                     expected=expected, delta=float(direct[0])-expected, absolute_delta=abs(float(direct[0])-expected),
                                     nll_subtraction_control=subtract, subtraction_absolute_delta=abs(float(direct[0])-subtract),
                                     tolerance=protocol['tolerance'], source_pointer='/methods/'+str(saved['methods'].index(original))+'/direct_contrast16/statistic')
                method['selected'] = bool(direct[0] > .001 and original['alternative']['pars'][3] > 1e-6)
                method['expected_selected'] = bool(expected > .001 and original['alternative']['pars'][3] > 1e-6)
                method['selection_cutoff_distance'] = float(direct[0])-.001
                method['refinement'] = dict(status='not_run', reason='Protocol64 selected-state check is pilot-only')
                if refined:
                    require(time.monotonic() < deadline, 'Replay wall deadline')
                    # Release primary features before constructing order64 to bound memory.
                    state.close(); state = None
                    high = native.state(data, inputs.law, 'paired', method['ratio'], 64, True)
                    refined_rows = {}
                    for phase in PHASES:
                        require(time.monotonic() < deadline, 'Replay wall deadline')
                        value = high.evaluate(original[phase]['pars'])
                        difference = abs(float(value[0])-method['states'][phase]['nll_ground'])
                        refined_rows[phase] = dict(nll_ground=float(value[0]), absolute_32_64_delta=difference,
                                                   passed=difference <= protocol['tolerance'])
                    method['refinement'] = dict(status='executed', order=64, states=refined_rows,
                                                passed=all(r['passed'] for r in refined_rows.values()))
                method['passed'] = bool(all(r['passed'] for r in method['states'].values()) and
                                        method['glr']['absolute_delta'] <= protocol['tolerance'] and
                                        method['glr']['subtraction_absolute_delta'] <= protocol['tolerance'] and
                                        method['selected'] == method['expected_selected'] and
                                        (not refined or method['refinement']['passed']))
                method['status'] = 'complete' if method['passed'] else 'failed_numerical_comparison'
                write(path, record)
                require(method['passed'], 'Selected NLL/GLR/refinement/discrete-selection check failed')
            finally:
                if state: state.close()
                if high: high.close()
        record.update(passed=True, status='complete')
    except BaseException as exc:
        record.update(passed=False, status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        record['wall_seconds'] = time.monotonic()-started
        write(path, record)
    return record


def runtime_identity():
    import numpy._core._multiarray_umath as extension
    return dict(python=platform.python_version(), implementation=platform.python_implementation(), executable_sha256=sha(sys.executable),
                numpy=np.__version__, numpy_extension_sha256=sha(extension.__file__), architecture=platform.machine(), byteorder=sys.byteorder,
                numerical_libraries=sorted([dict(api=r['internal_api'], version=r['version'], sha256=sha(r['filepath']))
                                           for r in threadpool_info()], key=lambda r: (r['api'], r['sha256'])))


def check_admission(args, protocol):
    admission = read(args.admission)
    require(admission['passed'] is True and admission['independent_review_passed'] is True and admission['mode'] == args.mode, 'Missing reviewed admission')
    require(admission['source_sha256'] == source_identity() and admission['protocol_sha256'] == sha(HERE/'protocol.json'), 'Admitted source/protocol changed')
    token = os.environ.get('NUMERICAL_LEASE_TOKEN', '')
    require(token and hashlib.sha256(token.encode()).hexdigest() == admission['lease_token_sha256'], 'Numerical lease attestation')
    require(datetime.datetime.fromisoformat(admission['expires_utc']) > datetime.datetime.now(datetime.timezone.utc), 'Expired admission')
    expected = protocol['pilot'] if args.mode == 'pilot' else [c for c in protocol['roster'] if c not in protocol['pilot']]
    require(admission['case_ids'] == expected, 'Admitted ordered case roster')
    build = read(args.build_receipt)
    require(build['passed'] is True and build['source_sha256'] == sha(HERE/'components.cpp'), 'Native build source')
    require(build['dependencies_sha256'] == {p.relative_to(HERE).as_posix(): sha(p) for p in HERE.rglob('*.cpp')}, 'Native dependency bytes')
    require(sha(args.library) == build['library_sha256'] == admission['library_sha256'], 'Native binary identity')
    require(sha(args.build_receipt) == admission['build_receipt_sha256'], 'Build receipt identity')
    cap = protocol['resources'][args.mode+'_wall_cap_seconds']
    require(0 < admission['wall_seconds'] <= cap and admission['threads'] == 2, 'Resource admission')
    require(admission['sampled_process_tree_rss_cap_bytes'] == protocol['resources']['sampled_rss_cap_bytes'], 'Sampled memory admission')
    return admission


def completion_union(args, protocol, admission, result, output):
    require(args.pilot is not None, 'Completion requires reviewed pilot')
    pilot = Path(args.pilot).resolve()
    prior = read(pilot/'result.json')
    require(prior['passed'] is True and prior['mode'] == 'pilot' and prior['not_run_case_ids'] == [c for c in protocol['roster'] if c not in protocol['pilot']], 'Pilot coverage')
    require(prior['source_sha256'] == result['source_sha256'] and prior['runtime_essential'] == result['runtime_essential'] and
            prior['library_sha256'] == result['library_sha256'], 'Pilot/source/runtime identity')
    require(admission['pilot_result_sha256'] == sha(pilot/'result.json') and admission['pilot_output_review_passed'] is True, 'Pilot output review pin')
    require([r['case_id'] for r in prior['cases']] == protocol['pilot'], 'Pilot roster changed')
    rows = []
    for entry in prior['cases']:
        relative = Path(entry['file'])
        require(not relative.is_absolute() and len(relative.parts) == 1, 'Pilot case path')
        source = pilot/relative
        require(sha(source) == entry['sha256'], 'Pilot case hash')
        row = read(source)
        require(row['passed'] is True and row['case_id'] == entry['case_id'], 'Pilot row failed')
        shutil.copyfile(source, output/relative)
        result['cases'].append({**entry, 'source': 'exact pilot reuse'})
        rows.append(row)
    result['pilot_result_sha256'] = sha(pilot/'result.json')
    result['pilot_runtime_essential'] = prior['runtime_essential']
    return rows


def paired_statistics(values):
    require(len(values) == 100 and all(math.isfinite(x) for x in values), 'All100 paired forest units required')
    return dict(mean=statistics.mean(values), median=statistics.median(values), mcse=statistics.stdev(values)/10)


def table_comparisons(records, inputs, protocol):
    require(len(records) == 300 and len({r['case_id'] for r in records}) == 300 and all(r['passed'] for r in records), 'Full table roster')
    methods = {(r['forest'], r['h'], m['procedure']): m for r in records for m in r['methods']}
    require(len(methods) == 600, 'Complete method roster')
    original = inputs.json('reports/S02_SUMMARY.json')
    cross = inputs.json('reports/S02_PAIRED_CONTRASTS.json')
    cells = []
    def compare(table, member, pointer, field, actual, expected, decimals=6, discrete=False):
        tolerance = 0. if discrete else protocol['tolerance']
        delta = actual-expected
        cells.append(dict(table=table, archive_member=member, pointer=pointer+'/'+field, field=field,
                          recomputed=actual, expected=expected, delta=delta, absolute_delta=abs(delta), tolerance=tolerance,
                          passed=abs(delta) <= tolerance, displayed_rounding_matches=format(actual, '.'+str(decimals)+'f') == format(expected, '.'+str(decimals)+'f')))
    for index, expected in enumerate(original['table']):
        procedure, h = expected['procedure'], expected['h']
        rows = [methods[i, h, procedure] for i in range(100)]
        control = sorted(methods[i, 0., procedure]['glr']['value'] for i in range(100))
        threshold = control[math.ceil(.95*(len(control)-1))]
        selected = sum(m['selected'] for m in rows)
        above = sum(m['glr']['value'] > threshold for m in rows)
        z = statistics.NormalDist().inv_cdf(.975); denominator = 1+z*z/100
        centre = (selected/100+z*z/200)/denominator
        half = z*math.sqrt(selected/100*(1-selected/100)/100+z*z/(4*100**2))/denominator
        values = dict(selected=selected, empirical_h0_95threshold=threshold, above_empirical_threshold=above)
        for key, value in values.items():
            compare('tab:s02-completed', 'reports/S02_SUMMARY.json', '/table/'+str(index), key, value, expected[key], discrete=key != 'empirical_h0_95threshold')
        for k, value in enumerate((centre-half, centre+half)):
            compare('tab:s02-completed', 'reports/S02_SUMMARY.json', '/table/'+str(index)+'/wilson95', str(k), value, expected['wilson95'][k], decimals=3)
    for index, expected in enumerate(original['paired_glr_differences']):
        h, procedure = expected['h_minus0'], expected['procedure']
        if h == 0.: continue
        stats = paired_statistics([methods[i, h, procedure]['glr']['value']-methods[i, 0., procedure]['glr']['value'] for i in range(100)])
        for key, value in stats.items():
            compare('tab:s02-paired', 'reports/S02_SUMMARY.json', '/paired_glr_differences/'+str(index), key, value, expected[key])
    for index, expected in enumerate(cross['cross_procedure']):
        h = expected['h']
        stats = paired_statistics([methods[i, h, 'M2']['glr']['value']-methods[i, h, 'M1']['glr']['value'] for i in range(100)])
        for key in ('mean', 'mcse'):
            compare('unnumbered_label:within_forest_M2minusM1', 'reports/S02_PAIRED_CONTRASTS.json', '/cross_procedure/'+str(index)+'/glr', key, stats[key], expected['glr'][key])
    return dict(passed=all(row['passed'] for row in cells), cells=cells, maximum_absolute_delta=max(row['absolute_delta'] for row in cells),
                displayed_rounding_mismatches=[row for row in cells if not row['displayed_rounding_matches']],
                manuscript_sources=protocol['table_links'],
                scope='Reconstructed selected-state table statistics. Original1e-4 continuous replay tolerance; discrete counts exact. Display rounding mismatch is retained separately, never silently declared exact. Same-bank empirical thresholds remain descriptive.')


def run(args):
    output = Path(args.output).resolve()
    require(not output.is_relative_to(ROOT), 'Scientific output must be outside checkout')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = dict(mode=args.mode, passed=False, status='running', cases=[], scope='Raw paired-clock selected-state replay; no refit, generation or terminal-search replay')
    write(output/'result.json', result)
    inputs = None
    try:
        protocol = read(HERE/'protocol.json'); admission = check_admission(args, protocol)
        result.update(source_sha256=source_identity(), protocol_sha256=sha(HERE/'protocol.json'),
                      archive_sha256=protocol['archive_sha256'], admission_sha256=sha(args.admission),
                      numerical_attempt_id=admission['numerical_attempt_id'], library_sha256=sha(args.library),
                      build_receipt_sha256=sha(args.build_receipt), runtime_essential=runtime_identity(),
                      runtime_metadata=dict(platform=platform.platform(), python=sys.version),
                      resources=dict(threads=2, workers=1, sampled_rss_cap_bytes=protocol['resources']['sampled_rss_cap_bytes']))
        inputs = Inputs(protocol)
        oracle = load_oracle(); native = oracle.Native(args.library)
        records = completion_union(args, protocol, admission, result, output) if args.mode == 'completion' else []
        require(all(r['id'] in admission['case_ids'] for r in inputs.cases if r['id'] not in {x['case_id'] for x in records}) if args.mode == 'completion' else True, 'Completion roster union')
        deadline = min(started+admission['wall_seconds'], time.monotonic()+(datetime.datetime.fromisoformat(admission['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        lookup = {c['id']: c for c in inputs.cases}
        with threadpool_limits(limits=2):
            result['threadpools'] = [{k: v for k, v in r.items() if k != 'filepath'} for r in threadpool_info()]
            for case_id in admission['case_ids']:
                require(time.monotonic() < deadline, 'Replay wall deadline')
                result['active_case'] = case_id; write(output/'result.json', result)
                row = run_case(lookup[case_id], inputs, oracle, native, protocol, output, deadline, args.mode == 'pilot')
                records.append(row)
                result['cases'].append(dict(case_id=case_id, file=case_id+'.json', sha256=sha(output/(case_id+'.json')), source='new selected-state replay'))
                write(output/'result.json', result)
                print(json.dumps(dict(event='case_complete', case_id=case_id, passed=row['passed'], seconds=row['wall_seconds'])), flush=True)
                require(row['passed'], 'Failed replay retained; no replacement or zero conversion')
        require(time.monotonic() < deadline, 'Replay completed beyond wall deadline')
        require(len(records) == (6 if args.mode == 'pilot' else 300), 'Complete phase roster')
        if args.mode == 'completion':
            table = table_comparisons(records, inputs, protocol)
            write(output/'table_deltas.json', table); result['table_deltas_sha256'] = sha(output/'table_deltas.json')
            require(table['passed'], 'Table reconstruction discrepancy')
        require(time.monotonic() < deadline, 'Replay summary completed beyond wall deadline')
        result.update(passed=True, status='complete', full_complete=args.mode == 'completion',
                      catalogues=len(records), methods=2*len(records), selected_nlls=4*len(records), glrs=2*len(records),
                      new_catalogues=len(admission['case_ids']), maximum_absolute_nll_delta=max(s['absolute_nll_delta'] for r in records for m in r['methods'] for s in m['states'].values()),
                      maximum_absolute_glr_delta=max(m['glr']['absolute_delta'] for r in records for m in r['methods']))
        result.pop('active_case', None)
    except BaseException as exc:
        result.update(passed=False, status='failed', full_complete=False, error_type=type(exc).__name__, error=str(exc))
    finally:
        if inputs: inputs.close()
        result['wall_seconds'] = time.monotonic()-started
        protocol = read(HERE/'protocol.json')
        seen = {r['case_id'] for r in result['cases']}
        result['not_run_case_ids'] = [c for c in protocol['roster'] if c not in seen]
        result['failed_case_ids'] = [r['case_id'] for r in result['cases'] if not read(output/r['file'])['passed']]
        write(output/'result.json', result)
    return 0 if result['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='command', required=True)
    build = modes.add_parser('build'); build.add_argument('--output', required=True)
    execute = modes.add_parser('run'); execute.add_argument('--mode', choices=['pilot', 'completion'], required=True)
    for field in ('admission', 'library', 'build-receipt', 'output'):
        execute.add_argument('--'+field, required=True)
    execute.add_argument('--pilot')
    args = parser.parse_args(argv)
    if args.command == 'build':
        from engine.cpu_build import build_shared
        result = build_shared(HERE/'components.cpp', args.output, dependency_root=HERE)
        print(json.dumps(result, indent=2)); return 0 if result['passed'] else 1
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
