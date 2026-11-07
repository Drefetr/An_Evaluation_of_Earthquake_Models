"""CPU likelihood replay of 60 initial mark-history cases; no fit or simulation."""
from pathlib import Path
import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import os
import statistics
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reproduction.score_replay import s02_replay as base
np = base.np
HERE = Path(__file__).resolve().parent/'initial_mark'
METHODS = ('known_known', 'background_estimated')
read, sha, write, require = base.read, base.sha, base.write, base.require


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_identity():
    files = [Path(__file__), ROOT/'reproduction/score_replay/s02_replay.py',
             ROOT/'engine/cpu_build.py', ROOT/'engine/stage2_followup/native_build.py']
    files += [p for p in base.HERE.rglob('*') if p.is_file() and p.suffix in ('.py', '.cpp')]
    files += [p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py', '.json')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(files)}


class Inputs:
    def __init__(self, protocol):
        require(sha(HERE/'input_manifest.json') == protocol['input_manifest_sha256'], 'Initial-mark manifest changed')
        self.manifest = read(HERE/'input_manifest.json')
        archive = HERE/self.manifest['archive']['path']
        require(sha(archive) == self.manifest['archive']['sha256'], 'Initial-mark archive changed')
        self.zip = zipfile.ZipFile(archive)
        self.members = {m['path']: m for m in self.manifest['members']}
        require(len(self.zip.namelist()) == len(self.members) and set(self.zip.namelist()) == set(self.members), 'Archive member roster')
        for relative, expected in self.manifest['source_sha256'].items():
            require(sha(HERE/'original'/relative) == expected, 'Original source changed: '+relative)
        self.contract = read(HERE/'original/research/magnitude_history/configs/staged_recipe.json')
        self.contract_hash = canonical(self.contract)
        setting = self.contract['law']; supplied = setting['alternative_generating_fit']
        self.saved_law = dict(a=supplied['pars'][0], d=supplied['pars'][1], n=supplied['pars'][2],
                              beta=setting['beta'], ratio=supplied['ratio'], horizon=setting['horizon_days'],
                              trigger=supplied['trigger'], stress=supplied['stress'], coordinate_horizon=setting['coordinate_horizon_days'])
        self.law = dict(T=self.saved_law['horizon'], coordinate=self.saved_law['coordinate_horizon'],
                        beta=self.saved_law['beta'], gamma=.75*math.log(10), n=self.saved_law['n'],
                        ratio=self.saved_law['ratio'], stress=self.saved_law['stress'], trigger=self.saved_law['trigger'])
        self.cases = self.manifest['cases']
        require([r['case_id'] for r in self.cases] == protocol['roster'] and len(self.cases) == 60, 'Sixty-case roster')
        require({(r['skeleton'], r['h']) for r in self.cases} == {(i, h) for i in range(20) for h in (0., .5, .9)}, 'Paired skeleton roster')

    def raw(self, name):
        data = self.zip.read(name); pin = self.members[name]
        require(len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256'], 'Member changed: '+name)
        return data

    def json(self, name):
        return json.loads(self.raw(name))

    def case(self, meta):
        raw = self.raw(meta['history']); saved = self.json(meta['comparison']); case = self.json(meta['case'])
        require(case['status'] == 'complete' and case['comparison_exit_code'] == 0 and
                saved['result']['complete'] is True and saved['result']['status'] == 'complete', 'Historical case incomplete')
        require(case['comparison_sha256'] == self.members[meta['comparison']]['sha256'], 'Comparison/case identity')
        require(case['history_sha256'] == saved['input_sha256'] == hashlib.sha256(raw).hexdigest(), 'Raw history/selection identity')
        require(all(case[k] == meta[k] for k in ('case_id', 'skeleton', 'h', 'time_seed', 'mark_seed')), 'Paired case identity')
        require(saved['adapter_sha256'] == self.manifest['source_sha256']['research/magnitude_history/comparison.py'], 'Original adapter identity')
        require(saved['supplied_law'] == self.saved_law and saved['contract_sha256'] == self.contract_hash, 'Supplied candidate law/contract changed')
        for name, digest in saved['engine_source_pins'].items():
            require(self.manifest['source_sha256']['engine/'+name] == digest, 'Original engine source identity')
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        require(len(rows) == meta['events'] == case['event_count'], 'Raw event count')
        data = {name: np.array([float(row[column]) for row in rows], dtype='<f8') for name, column in
                [('times', 'time_hi'), ('times_lo', 'time_lo'), ('event_gaps', 'event_gap'), ('excess', 'excess')]}
        require(all(np.isfinite(v).all() for v in data.values()), 'Nonfinite raw inputs')
        methods = saved['result']['methods']
        require(len(methods) == 2 and [m['id'] for m in methods] == list(METHODS), 'Original two-method roster')
        for method in methods:
            validate_selected(method, self.saved_law)
            binding = method['input_binding']
            require(binding['law'] == self.saved_law and binding['clock_mode'] == 'paired' and
                    binding['contract_sha256'] == self.contract_hash and binding['sources'] == saved['engine_source_pins'], 'Selected state input binding')
            require(canonical(binding) == method['binding_sha256'], 'Selected binding digest')
            require(set(binding['arrays']) == set(data), 'Bound input arrays')
            for name, array in data.items():
                pin = binding['arrays'][name]
                require(pin == dict(dtype=array.dtype.str, shape=list(array.shape), sha256=hashlib.sha256(array.tobytes()).hexdigest()), 'Raw-array binding: '+name)
            selected = next(r for r in case['methods'] if r['method'] == method['id'])
            require(selected['status'] == 'resolved' and selected['direct_glr'] == method['contrast16']['statistic'] and
                    selected['null_nll'] == method['null']['nll'] and selected['alternative_nll'] == method['alternative']['nll'] and
                    selected['eta'] == method['alternative']['pars'][3], 'Case/selected-record crosswalk')
        return data, saved

    def close(self):
        self.zip.close()


def validate_selected(method, law):
    require(method['id'] in METHODS and method['complete'] is True and method['status'] == 'complete', 'Incomplete original method')
    require(method['gates']['passed'] is True and len(method['selected_objectives']) == 2 and
            all(r['passed'] is True for r in method['selected_objectives']), 'Original selected checks failed')
    for phase in base.PHASES:
        state = method[phase]; p = state['pars']
        require(len(p) == 4 and all(math.isfinite(v) for v in p), 'Selected vector')
        require(-12 <= p[0] <= 0 and -2 <= p[1] <= 2 and p[2] == law['n'] and 0 <= p[3] <= 3, 'Original selected box/fixed n')
        require(phase != 'null' or p[3] == 0., 'Null eta is not zero')
        require(method['id'] != 'known_known' or p[:2] == [law['a'], law['d']], 'Known background changed')
        require(state['success'] is True and state['ratio'] == law['ratio'] and state['trigger'] == law['trigger'] and math.isfinite(state['nll']), 'Selected state law')


def run_case(meta, inputs, oracle, native, protocol, output, deadline, refine):
    started = time.monotonic(); path = output/(meta['case_id']+'.json')
    record = dict(case_id=meta['case_id'], skeleton=meta['skeleton'], h=meta['h'], passed=False, status='running', methods=[])
    write(path, record)
    state, high = None, None
    try:
        data, saved = inputs.case(meta); oracle.clock(data, inputs.law, 'paired')
        mark = len(data['excess'])*math.log(inputs.law['beta'])-inputs.law['beta']*math.fsum(map(float, data['excess']))
        record.update(events=len(data['times']), law=inputs.law, mark_score=mark,
                      source_members={meta[key]: inputs.members[meta[key]]['sha256'] for key in ('case', 'history', 'comparison')})
        require(time.monotonic() < deadline, 'Replay wall deadline')
        # Both methods share history, kernels and supplied productivity; construct once.
        state = native.state(data, inputs.law, 'paired', inputs.law['ratio'], 32, False)
        extra = base.Extra(native, oracle)
        for i, original in enumerate(saved['result']['methods']):
            method = dict(procedure=original['id'], passed=False, status='running', states={})
            record['methods'].append(method); write(path, record)
            for phase in base.PHASES:
                require(time.monotonic() < deadline, 'Replay wall deadline')
                selected = original[phase]
                row = base.evaluate_selected(state, extra, selected['pars'], selected['nll'], mark,
                                             protocol['tolerance'], protocol['component_identity_tolerance'])
                cpu = next(x for x in original['selected_objectives'] if x['phase'] == phase)['cpu32_nll']
                row.update(source_pointer='/result/methods/'+str(i)+'/'+phase, expected_original_cpu32_nll=cpu,
                           absolute_original_cpu32_delta=abs(row['nll_ground']-cpu))
                row['passed'] = bool(row['passed'] and row['absolute_original_cpu32_delta'] <= protocol['tolerance'])
                method['states'][phase] = row; write(path, record)
            direct = extra.glr(state, original['null']['pars'], original['alternative']['pars'])
            difference = 2*(method['states']['null']['nll_ground']-method['states']['alternative']['nll_ground'])
            expected = original['contrast16']['statistic']; original_cpu = original['contrast32']['statistic']
            method['glr'] = dict(value=float(direct[0]), point_delta=float(direct[1]), signed_compensator_delta=float(direct[2]),
                                expected=expected, expected_original_cpu32=original_cpu, delta=float(direct[0])-expected,
                                absolute_delta=abs(float(direct[0])-expected), absolute_original_cpu32_delta=abs(float(direct[0])-original_cpu),
                                nll_subtraction_control=difference, subtraction_absolute_delta=abs(float(direct[0])-difference),
                                tolerance=protocol['tolerance'], source_pointer='/result/methods/'+str(i)+'/contrast16/statistic')
            rule = protocol['selected_rule']; eta = original['alternative']['pars'][3]
            method.update(selected=bool(direct[0] > rule['glr_above'] and eta > rule['eta_above']),
                          expected_selected=bool(expected > rule['glr_above'] and eta > rule['eta_above']),
                          eta=eta, selection_cutoff_distance=float(direct[0])-rule['glr_above'],
                          refinement=dict(status='not_run', reason='Order64 check is pilot-only'))
            method['passed'] = bool(all(r['passed'] for r in method['states'].values()) and
                                    all(method['glr'][k] <= protocol['tolerance'] for k in
                                        ('absolute_delta', 'absolute_original_cpu32_delta', 'subtraction_absolute_delta')) and
                                    method['selected'] == method['expected_selected'])
            method['status'] = 'complete' if method['passed'] else 'failed_numerical_comparison'
            write(path, record); require(method['passed'], 'Selected NLL/GLR/discrete-selection replay failed')
        state.close(); state = None
        if refine:
            require(time.monotonic() < deadline, 'Replay wall deadline')
            high = native.state(data, inputs.law, 'paired', inputs.law['ratio'], 64, False)
            for method, original in zip(record['methods'], saved['result']['methods']):
                rows = {}
                for phase in base.PHASES:
                    require(time.monotonic() < deadline, 'Replay wall deadline')
                    value = float(high.evaluate(original[phase]['pars'])[0]); delta = abs(value-method['states'][phase]['nll_ground'])
                    rows[phase] = dict(nll_ground=value, absolute_32_64_delta=delta, passed=delta <= protocol['tolerance'])
                method['refinement'] = dict(status='executed', order=64, states=rows, passed=all(v['passed'] for v in rows.values()))
                method['passed'] = bool(method['passed'] and method['refinement']['passed'])
                write(path, record); require(method['passed'], 'Selected order32/64 check failed')
        record.update(passed=True, status='complete')
    except BaseException as exc:
        record.update(passed=False, status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        if state: state.close()
        if high: high.close()
        record['wall_seconds'] = time.monotonic()-started; write(path, record)
    return record


def bootstrap(values, specification):
    values = np.asarray(values, dtype=np.float64)
    require(len(values) == 20 and np.isfinite(values).all(), 'Twenty finite paired skeleton differences required')
    rng = np.random.default_rng(specification['seed'])
    means = values[rng.integers(0, len(values), size=(specification['resamples'], len(values)))].mean(axis=1)
    return dict(mean=float(values.mean()), percentile95=list(map(float, np.quantile(means, [.025, .975]))))


def table_comparisons(records, inputs, protocol):
    require(len(records) == 60 and {r['case_id'] for r in records} == set(protocol['roster']) and all(r['passed'] for r in records), 'Complete initial-mark table roster')
    methods = {(r['skeleton'], r['h'], m['procedure']): m for r in records for m in r['methods']}
    require(len(methods) == 120, 'Complete120-method table roster')
    expected = inputs.json('records/summary.json'); cells = []
    def compare(table, pointer, actual, target, discrete=False, decimals=6):
        delta = actual-target; tolerance = 0. if discrete else protocol['tolerance']
        cells.append(dict(table=table, archive_member='records/summary.json', pointer=pointer,
                          recomputed=actual, expected=target, delta=delta, absolute_delta=abs(delta), tolerance=tolerance,
                          passed=abs(delta) <= tolerance, displayed_rounding_matches=format(actual, '.'+str(decimals)+'f') == format(target, '.'+str(decimals)+'f')))
    for i, row in enumerate(expected['groups']):
        values = [methods[j, row['h'], row['method']] for j in range(20)]
        count = sum(m['selected'] for m in values); root = '/groups/'+str(i)
        compare('tab:pilot-frequency', root+'/selected', count, row['selected'], True)
        compare('tab:pilot-frequency', root+'/median_glr', statistics.median(m['glr']['value'] for m in values), row['median_glr'])
        compare('tab:pilot-frequency', root+'/median_eta', statistics.median(m['eta'] for m in values), row['median_eta'])
        z = 1.959963984540054; denominator = 1+z*z/20
        centre = (count/20+z*z/40)/denominator
        half = z*math.sqrt(count/20*(1-count/20)/20+z*z/(4*20**2))/denominator
        for k, v in enumerate((centre-half, centre+half)):
            compare('tab:pilot-frequency', root+'/wilson95_among_resolved/'+str(k), v, row['wilson95_among_resolved'][k], decimals=3)
    for i, row in enumerate(expected['paired_contrasts']):
        active = [methods[j, row['h_minus_control'], row['method']] for j in range(20)]
        control = [methods[j, 0., row['method']] for j in range(20)]
        for kind in ('selection', 'glr'):
            differences = [int(a['selected'])-int(b['selected']) if kind == 'selection' else a['glr']['value']-b['glr']['value'] for a, b in zip(active, control)]
            actual = bootstrap(differences, protocol['bootstrap']); name = 'paired_'+kind+'_difference'
            target = row[name]; root = '/paired_contrasts/'+str(i)+'/'+name
            compare('tab:pilot-paired', root+'/mean', actual['mean'], target['mean'], discrete=kind == 'selection')
            for k, value in enumerate(actual['percentile95']):
                compare('tab:pilot-paired', root+'/percentile95/'+str(k), value, target['percentile95'][k], discrete=kind == 'selection')
    return dict(passed=all(v['passed'] for v in cells), cells=cells, maximum_absolute_delta=max(v['absolute_delta'] for v in cells),
                displayed_rounding_mismatches=[v for v in cells if not v['displayed_rounding_matches']], manuscript_sources=protocol['table_links'],
                scope='Reconstructed original descriptive group/paired statistics, with original bootstrap seed/resample recipe. No new event histories, refits, or coverage claim; continuous tolerance1e-4 and discrete selections exact.')


def check_admission(args, protocol):
    a = read(args.admission)
    require(a['passed'] is True and a['independent_review_passed'] is True and a['mode'] == args.mode, 'Reviewed admission required')
    require(a['source_sha256'] == source_identity() and a['protocol_sha256'] == sha(HERE/'protocol.json'), 'Source/protocol admission')
    token = os.environ.get('NUMERICAL_LEASE_TOKEN', '')
    require(token and hashlib.sha256(token.encode()).hexdigest() == a['lease_token_sha256'], 'Numerical lease attestation')
    require(datetime.datetime.fromisoformat(a['expires_utc']) > datetime.datetime.now(datetime.timezone.utc), 'Expired admission')
    expected = protocol['pilot'] if args.mode == 'pilot' else [c for c in protocol['roster'] if c not in protocol['pilot']]
    require(a['case_ids'] == expected, 'Ordered case admission')
    build = read(args.build_receipt)
    require(build['passed'] is True and build['source_sha256'] == sha(base.HERE/'components.cpp'), 'Q01 component build source')
    require(build['dependencies_sha256'] == {p.relative_to(base.HERE).as_posix(): sha(p) for p in base.HERE.rglob('*.cpp')}, 'Q01 original dependency bytes')
    require(sha(args.library) == a['library_sha256'] == build['library_sha256'] and sha(args.build_receipt) == a['build_receipt_sha256'], 'Native/build identity')
    require(a['threads'] == 2 and 0 < a['wall_seconds'] <= protocol['resources'][args.mode+'_wall_cap_seconds'] and
            a['sampled_process_tree_rss_cap_bytes'] == protocol['resources']['sampled_rss_cap_bytes'], 'Resource admission')
    return a


def run(args):
    output = Path(args.output).resolve(); require(not output.is_relative_to(ROOT), 'Outputs must be external')
    output.mkdir(parents=True, exist_ok=False); started = time.monotonic(); inputs = None
    result = dict(mode=args.mode, passed=False, status='running', cases=[], scope='Initial mark-history selected likelihoods; no fit, generation or original optimizer replay')
    write(output/'result.json', result)
    try:
        p = read(HERE/'protocol.json'); a = check_admission(args, p); inputs = Inputs(p)
        result.update(source_sha256=source_identity(), protocol_sha256=sha(HERE/'protocol.json'), archive_sha256=inputs.manifest['archive']['sha256'],
                      admission_sha256=sha(args.admission), numerical_attempt_id=a['numerical_attempt_id'], library_sha256=sha(args.library),
                      build_receipt_sha256=sha(args.build_receipt), runtime_essential=base.runtime_identity(),
                      resources=dict(threads=2, workers=1, sampled_rss_cap_bytes=p['resources']['sampled_rss_cap_bytes']))
        records = base.completion_union(args, p, a, result, output) if args.mode == 'completion' else []
        oracle = base.load_oracle(); native = oracle.Native(args.library)
        deadline = min(started+a['wall_seconds'], time.monotonic()+(datetime.datetime.fromisoformat(a['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        lookup = {r['case_id']: r for r in inputs.cases}
        with base.threadpool_limits(limits=2):
            result['threadpools'] = [{k: v for k, v in r.items() if k != 'filepath'} for r in base.threadpool_info()]
            for case_id in a['case_ids']:
                require(time.monotonic() < deadline, 'Replay wall deadline')
                result['active_case'] = case_id; write(output/'result.json', result)
                row = run_case(lookup[case_id], inputs, oracle, native, p, output, deadline, args.mode == 'pilot'); records.append(row)
                result['cases'].append(dict(case_id=case_id, file=case_id+'.json', sha256=sha(output/(case_id+'.json')), source='new initial-mark selected-state replay'))
                write(output/'result.json', result)
                print(json.dumps(dict(event='case_complete', case_id=case_id, passed=row['passed'], seconds=row['wall_seconds'])), flush=True)
                require(row['passed'], 'Failed case retained; no replacement')
        require(len(records) == (6 if args.mode == 'pilot' else 60), 'Phase roster incomplete')
        if args.mode == 'completion':
            table = table_comparisons(records, inputs, p); write(output/'table_deltas.json', table)
            result['table_deltas_sha256'] = sha(output/'table_deltas.json'); require(table['passed'], 'Table reconstruction discrepancy')
        require(time.monotonic() < deadline, 'Final wall deadline')
        result.update(passed=True, status='complete', full_complete=args.mode == 'completion', catalogues=len(records), methods=2*len(records),
                      selected_nlls=4*len(records), glrs=2*len(records), new_catalogues=len(a['case_ids']),
                      maximum_absolute_nll_delta=max(v['absolute_nll_delta'] for r in records for m in r['methods'] for v in m['states'].values()),
                      maximum_absolute_glr_delta=max(m['glr']['absolute_delta'] for r in records for m in r['methods']))
        result.pop('active_case', None)
    except BaseException as exc:
        result.update(passed=False, full_complete=False, status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        if inputs: inputs.close()
        p = read(HERE/'protocol.json'); seen = {r['case_id'] for r in result['cases']}
        result['not_run_case_ids'] = [c for c in p['roster'] if c not in seen]
        result['failed_case_ids'] = [r['case_id'] for r in result['cases'] if not read(output/r['file'])['passed']]
        result['wall_seconds'] = time.monotonic()-started; write(output/'result.json', result)
    return 0 if result['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    builder = sub.add_parser('build'); builder.add_argument('--output', required=True)
    execute = sub.add_parser('run'); execute.add_argument('--mode', choices=['pilot', 'completion'], required=True)
    for field in ('admission', 'library', 'build-receipt', 'output'): execute.add_argument('--'+field, required=True)
    execute.add_argument('--pilot'); args = parser.parse_args(argv)
    if args.command == 'build': return base.main(['build', '--output', args.output])
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
