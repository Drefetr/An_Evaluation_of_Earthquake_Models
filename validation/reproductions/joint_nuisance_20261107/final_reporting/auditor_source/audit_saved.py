"""Private, independent FINAL saved-operand audit. No scientific code is loaded.

The report builder/formatter and their aggregate implementation are never
imported. Existing separately authored case-audit functions are used only for
per-case arithmetic and amendment logs. Summary arithmetic below is independent.
CLI output is an automated check, NOT the later live reporting acceptance.
"""
import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import statistics
import zipfile

SCIENCE = 'experiments/s04b_joint_nuisance/protocol.json'
POLICY = 'experiments/s04b_joint_remaining/protocol.json'
AMENDMENT = 'experiments/s04b_exposure_refinement/protocol.json'
OPERATIONAL = 'experiments/s04b_wall_failure_continuation/protocol.json'
PROFILE = 'experiments/s04b_refined_cpu_reader/profile.json'
INPUTS = 'experiments/s04b_joint_nuisance/input_pins.json'
MANIFEST = 'reproduction/synthetic/input_manifest.json'
CHECKER = 'experiments/s04b_exposure_refinement_audit/check.py'
CORE = 'experiments/s04b_joint_nuisance_audit/audit.py'
UNKNOWN = 'S5_broad_long_imm_seed410518'
WALL = 'S6_narrow_short_total_seed410615'
PARTIAL = 'S6_narrow_short_total_seed410603'
MODELS = ('LI', 'LIplus_immigrant', 'LIplus_inclusive')
ARMS = ('null', *MODELS)
PROCEDURES = ((MODELS[0], 'raw'), (MODELS[1], 'raw'), (MODELS[1], 'BIC'),
              (MODELS[2], 'raw'), (MODELS[2], 'BIC'))
NULL_FIELDS = ('new_gain', 'new_win', 'near_zero', 'robust_positive', 'robust_negative',
    'off_floor', 'floor_return', 'parameters', 'selected_state_index', 'score',
    'new_null_score', 'delta', 'boundaries', 'training_gain', 'gate_active',
    'coarse_fine_gate_disagreement', 'null_search_gap_detected')
PINS = {
    SCIENCE: '8f31b9f28d830eeffa30bdbf3e0fcf1295087411869fa301b91333c95fa445e9',
    POLICY: '4c77737acf8801ccfd0db25bba3005b1c547562675d7ced5bc1b72f428c8f2cd',
    AMENDMENT: '9b419d004ee3a075abdc3059bcc06fa037281cf5af7ea031d0c209be5687c982',
    OPERATIONAL: '809dd264636b01e2ef6f4165a19595d8f8cf72ae188c428ba8b9dea27208211b',
    PROFILE: 'e55c5268760e3a56f50642dc3d3d14f7dc0b5185f7e7db63ed4379d40562959d',
    CHECKER: '43b87881ed19970e420a4db7e5325e45302fae7d87381483e2700f07065bfb02',
    CORE: '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3',
    'scripts/build_joint_disposition_report.py': 'e4cb8d2c489ceab645e9654d8029c487fe402bdf0dd20ca6a1aad3a4384eb780',
    'scripts/render_joint_disposition_results.py': '6c8446a8e9ab7194b8f45cc4099e46416f753581d9f105e2b76f2b394a6a7982',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def document(data):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key: '+key)
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))


def equal(a, b, label):
    require(json.dumps(a, sort_keys=True, allow_nan=False) ==
            json.dumps(b, sort_keys=True, allow_nan=False), label)


def number(x):
    require(type(x) in (int, float) and math.isfinite(x), 'Finite scalar required')
    return x


def close(a, b, label, tolerance=1e-9):
    require(abs(number(a)-number(b)) <= tolerance, label)


def compare(a, b, label='summary'):
    if isinstance(b, dict):
        require(isinstance(a, dict) and set(a) == set(b), label+' keys')
        for key in b:
            compare(a[key], b[key], label+'.'+key)
    elif isinstance(b, list):
        require(isinstance(a, list) and len(a) == len(b), label+' length')
        for i, (x, y) in enumerate(zip(a, b)):
            compare(x, y, label+'.'+str(i))
    elif type(b) is float:
        close(a, b, label)
    else:
        require(type(a) is type(b) and a == b, label+' exact scalar')


def member_name(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name,
            'Noncanonical relative path')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and str(p) == name.rstrip('/'),
            'Unsafe relative path')
    return name


class Saved:
    def __init__(self, repo):
        self.repo = Path(repo).resolve()
        self.pins, self.files, self.zips, self.members = {}, {}, {}, {}

    def path(self, name):
        member_name(name)
        path = (self.repo/name).resolve()
        require(path.is_relative_to(self.repo), 'Escaping repository')
        return path

    def raw(self, name, pin=None):
        if name not in self.files:
            self.files[name] = self.path(name).read_bytes()
        data = self.files[name]
        actual = digest(data)
        require(pin is None or actual == pin, 'File SHA mismatch: '+name)
        require(name not in self.pins or self.pins[name] == actual, 'Conflicting pin')
        self.pins[name] = actual
        return data

    def file(self, name, pin=None):
        return document(self.raw(name, pin))

    def reference(self, ref):
        require(set(ref) == {'path', 'sha256'}, 'Expected exact file reference')
        return self.file(ref['path'], ref['sha256'])

    def archive(self, ref):
        path = self.path(ref['path'])
        if ref['path'] not in self.pins:
            with path.open('rb') as stream:
                self.pins[ref['path']] = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(self.pins[ref['path']] == ref['sha256'], 'Archive SHA mismatch')
        if ref['sha256'] not in self.zips:
            z = zipfile.ZipFile(path)
            require(len(z.namelist()) == len(set(z.namelist())), 'Duplicate ZIP members')
            for info in z.infolist():
                member_name(info.orig_filename)
                member_name(info.filename)
            self.zips[ref['sha256']] = z
        return ref

    def member(self, ref, name, pin, lines=False, raw=False):
        self.archive(ref)
        member_name(name)
        key = ref['sha256'], name
        if key not in self.members:
            self.members[key] = self.zips[ref['sha256']].read(name)
        data = self.members[key]
        require(digest(data) == pin, 'ZIP member SHA mismatch: '+name)
        if raw:
            return data
        return [document(line) for line in data.splitlines() if line.strip()] if lines else document(data)

    def locator(self, ref, name, pin, pointer=''):
        return dict(path=ref['path'], sha256=ref['sha256'], member=name,
                    member_sha256=pin, json_pointer=pointer)

    def close(self):
        for z in self.zips.values():
            z.close()


def live(value, failed=False):
    require(value.get('live_agent_review') is True and
            value.get('live_agent_review_performed', True) is True and
            value.get('final_batch_agent_review_required', False) is False and
            value.get('live_independent_review', True) is True and
            value.get('audit_passed') is True and value.get('scientific_completion') is False and
            value.get('passed') is (not failed), 'Non-live/contradictory execution review')


def primary(regime, model, gate):
    return (regime, model, gate) in ((5, MODELS[1], 'raw'), (7, MODELS[2], 'raw'))


def boundary(theta, bounds):
    require(len(theta) == len(bounds) == 8, 'Boundary vector length')
    out = []
    for x, (lo, hi) in zip(theta, bounds):
        require(lo <= number(x) <= hi, 'Infeasible coordinate')
        out.append('lower' if abs(x-lo) <= 1e-8 else 'upper' if abs(x-hi) <= 1e-8 else None)
    return out


def wilson(wins, n):
    """Wilson center/radius form; builder uses independent quadratic roots."""
    require(type(wins) is int and type(n) is int and n > 0 and 0 <= wins <= n, 'Wilson count')
    z = 1.959963984540054
    p = wins/n
    denominator = 1+z*z/n
    center = (p+z*z/(2*n))/denominator
    radius = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return [max(0., center-radius), min(1., center+radius)]


def summarize(sequence, records, raw_cases, science):
    """Independent summaries. Never compute a subset's statistics as full20."""
    require(len(sequence) == len(set(sequence)) == 80 and set(records) == set(sequence), 'Not all eighty dispositions')
    output = []
    for regime in range(4, 8):
        planned = [key for key in sequence if records[key]['regime'] == regime]
        require(len(planned) == 20, 'Original regime roster differs')
        unavailable = [key for key in planned if records[key]['disposition'] != 'complete']
        for model, gate in PROCEDURES:
            stats = None
            if not unavailable:
                cases = [raw_cases[key] for key in planned]
                outcomes = [next(o for o in c['outcomes'] if (o['model'], o['gate']) == (model, gate)) for c in cases]
                gains = [0. if o['floor_return'] else number(o['score']['joint'])-number(o['new_null_score']['joint']) for o in outcomes]
                wins = sum(g > 0 for g in gains)
                sides = [boundary(o['parameters'], science['shared_bounds']+science['inhibition_bounds']) for o in outcomes]
                # Derive diagnostics from fit/state operands, never summary flags.
                floor = [c['fits'][model]['selected']['state_index'] == 0 or
                         (gate == 'BIC' and not (c['training_checks']['null']['fine']['nll']-
                          c['training_checks'][model]['fine']['nll'] > 1.5*math.log(max(c['n_train'], 1)))) for c in cases]
                disagreements = []
                for c in cases:
                    gain = lambda order: c['training_checks']['null'][order]['nll']-c['training_checks'][model][order]['nll']
                    threshold = 1.5*math.log(max(c['n_train'], 1))
                    disagreements.append((gain('coarse') > threshold) != (gain('fine') > threshold))
                stats = dict(regime=regime, model=model, gate=gate, N=20,
                    mean_gain=statistics.mean(gains), median_gain=statistics.median(gains), wins=wins,
                    wilson95=wilson(wins, 20), near_zero=sum(abs(g) <= 1e-9 for g in gains),
                    positive_near_zero=sum(0 < g <= 1e-9 for g in gains), robust_positive=sum(g > 1e-9 for g in gains),
                    robust_negative=sum(g < -1e-9 for g in gains), off_floor=sum(o['parameters'][5] > 0 for o in outcomes),
                    floor_returns=sum(floor), unknowns=0, a_boundary=sum(s[0] is not None for s in sides),
                    eta_lower=sum(s[5] == 'lower' for s in sides), eta_upper=sum(s[5] == 'upper' for s in sides),
                    null_search_gap_cases=sum(bool(c['fits'][model]['null_search_gaps']) for c in cases),
                    coarse_fine_gate_disagreements=sum(disagreements),
                    optimizer_failed_attempts=sum(r['success'] is False for c in cases for arm in ('null', model) for r in c['fits'][arm]['records']),
                    coordinate_boundaries={name: {side: sum(s[i] == side for s in sides) for side in ('lower', 'upper')} for i, name in enumerate(science['coordinates'])},
                    realized_thinning={name: sum(c['thinning'][name] for c in cases) for name in ('accepted_immigrants', 'rejected_immigrants', 'accepted_offspring', 'rejected_offspring')},
                    mean_training_events=statistics.mean(c['n_train'] for c in cases),
                    mean_test_events=statistics.mean(c['n_test'] for c in cases), primary=primary(regime, model, gate))
            output.append(dict(regime=regime, model=model, gate=gate, primary=primary(regime, model, gate),
                planned_histories=20, computed_histories=20-len(unavailable), unavailable_histories=len(unavailable),
                unavailable_case_ids=unavailable, statistics_available=not unavailable, full_regime=stats,
                unavailable_reason='incomplete_original_20_history_regime' if unavailable else None))
    return output


def check_slots(report, sequence, records, raw_cases, refs, historical):
    require(len(report['outcomes']) == 400, 'Exactly400 planned slots required')
    expected = []
    for key in sequence:
        record, case = records[key], raw_cases[key]
        if record['disposition'] == 'complete':
            require([(o['model'], o['gate']) for o in case['outcomes']] == list(PROCEDURES), 'Raw procedure roster')
            for i, raw in enumerate(case['outcomes']):
                gain = 0. if raw['floor_return'] else number(raw['score']['joint'])-number(raw['new_null_score']['joint'])
                require(raw['new_gain'] == gain and raw['new_win'] is (gain > 0) and raw['near_zero'] is (abs(gain) <= 1e-9), 'Saved strict sign definition')
                require(raw['robust_positive'] is (gain > 1e-9) and raw['robust_negative'] is (gain < -1e-9), 'Saved robust sign definition')
                comp = historical[(key, raw['model'], raw['gate'])]
                close(raw['historical']['fixed_floor_gain'], comp['fixed_floor_gain'], 'Fixed comparison changed')
                close(raw['historical']['intercept_only_gain'], comp['intercept_only_gain'], 'Intercept comparison changed')
                expected.append(dict(deepcopy(raw), id=key+'|'+raw['model']+'|'+raw['gate'], case_id=key,
                    regime=record['regime'], availability='computed', historical_comparators=comp,
                    source=dict(refs[key]['case'], json_pointer='/outcomes/'+str(i))))
        else:
            require(case['outcomes'] == [] and record['outcomes'] == [] and case['passed'] is False and
                    not case.get('test_checks') and 'new_null_test' not in case and 'bic_threshold' not in case and
                    not case.get('training_selections_frozen', False), 'Unavailable raw history contains held-out output')
            reason = 'scientific_wall_limit' if record['disposition'] == 'wall_time_failure' else 'original_optimizer_cap_unknown'
            for model, gate in PROCEDURES:
                row = dict.fromkeys(NULL_FIELDS)
                row.update(id=key+'|'+model+'|'+gate, case_id=key, regime=record['regime'], model=model, gate=gate,
                    availability='unavailable', reason_code=reason, source=refs[key]['case'], failure_evidence=refs[key],
                    historical_comparators=historical[(key, model, gate)])
                if record['disposition'] == 'scientific_unknown':
                    row['model_census'] = record['model_census']
                expected.append(row)
    equal(report['outcomes'], expected, 'Report slots differ from exact saved operands/null placement')
    return expected


def source_contract(saved, report, registry, index, science, policy):
    """Reconstruct the consumed source graph from fixed protocols/live reviews."""
    amref, opref, rdref = (registry[k] for k in ('numerical_amendment', 'operational_continuation', 'public_reader'))
    for key in ('source_review', 'sealed_index', 'sealing_review'):
        name = opref[key]['path']; path = saved.path(name); parts = PurePosixPath(name).parts
        require(len(parts) > 1 and parts[0] == 'validation' and parts[1].casefold() != 'authorities' and
                path.is_relative_to(saved.repo/'validation') and not path.is_relative_to(saved.repo/'validation'/'authorities'),
                'Operational reference must be canonical public evidence')
    require(amref['protocol']['path'] == AMENDMENT and opref['protocol']['path'] == OPERATIONAL and rdref['profile']['path'] == PROFILE, 'Version identity substituted')
    am = saved.reference(amref['protocol']); op = saved.reference(opref['protocol']); profile = saved.reference(rdref['profile'])
    reviews = [saved.reference(ref['source_review']) for ref in (amref, opref, rdref)]
    for review in reviews:
        require(review.get('passed') is True and review.get('live_agent_review') is True and
                review.get('live_agent_review_performed', True) is True and review.get('final_batch_agent_review_required', False) is False, 'Unaccepted source review')
    am_sources = dict(am['source_sha256'])
    for name in ('__init__.py', 'adapter.py', 'partial_fit.py', 'case_driver.py', 'host.py', 'protocol.json'):
        path = str(PurePosixPath(AMENDMENT).parent/name)
        am_sources[path] = reviews[0]['reviewed_files_sha256'][path]
    equal(am_sources, op['core_source_sha256'], 'Operational numerical core changed')
    equal(am_sources, profile['core_source_sha256'], 'Reader numerical core changed')
    equal(am_sources, index['scientific_source_sha256'], 'Final compatibility core changed')
    graphs = [(dict(am_sources), am['checker']['sources'], reviews[0]),
              (dict(am_sources), op['producer_source_paths']+op['checker']['sources']+[op['checker']['test'], 'requirements.txt', 'requirements-cpu.txt'], reviews[1]),
              (dict(am_sources), profile['producer_source_paths'], reviews[2])]
    for graph, extra, review in graphs:
        for name in extra:
            graph[name] = review['reviewed_files_sha256'][name]
        for name, pin in graph.items():
            require(review['reviewed_files_sha256'].get(name) == pin, 'Source review graph mismatch')
            saved.raw(name, pin)
    host_sources = dict(am_sources)
    host_sources.update({name: reviews[1]['reviewed_files_sha256'][name] for name in op['producer_source_paths']})
    equal(index['host_source_sha256'], host_sources, 'Actual operational host identity changed')
    producer_sources = {name: reviews[2]['reviewed_files_sha256'][name] for name in profile['producer_source_paths']}
    reader = dict(schema='joint_refined_cpu_producer_v1', kind='public_refined_cpu', entrypoint='scripts/fit_joint_refined_cpu.py',
        operation='fit', profile_reference=rdref['profile'], core_source_sha256=am_sources,
        producer_source_sha256=producer_sources, execution_source_sha256=am_sources | producer_sources, source_review=rdref['source_review'])
    base = am['base']; aref = dict(path=base['archive'], sha256=base['archive_sha256'])
    original = saved.member(aref, base['index_member'], base['index_sha256'])
    old_review = saved.file(base['review'], base['review_sha256'])
    live(old_review, True)
    equal(index['records'][:44], original['records'], 'Original43/unknown prefix changed')
    require(old_review['accepted_completed_case_ids'] == policy['full_sequence'][42:44], 'Failed old host accepted IDs changed')
    old_partial = saved.member(aref, am['failed_case']['case_member'], am['failed_case']['case_sha256'])
    raw = saved.member(op['base']['archive'], op['base']['index_member'], op['base']['index_sha256'])
    wall_review = saved.reference(op['base']['review']); live(wall_review, True)
    require(wall_review['accepted_completed_prefix']['new_complete_cases'] == policy['full_sequence'][51:55], 'Failed host4 complete prefix changed')
    sealed = saved.reference(opref['sealed_index']); sealed_review = saved.reference(opref['sealing_review'])
    require(sealed_review.get('passed') is True and sealed_review.get('audit_passed') is True and
        sealed_review.get('live_agent_review') is True and sealed_review.get('scientific_execution_passed') is False and
        sealed_review.get('scientific_completion') is False and 'execution_id' not in sealed_review and
        sealed_review.get('review_kind') == 'live_operational_failure_transition_review' and
        sealed_review['index_sha256'] == opref['sealed_index']['sha256'], 'Metadata seal confused with execution')
    equal(raw['records'], index['records'][:55], 'Raw55 prefix changed')
    equal(sealed['records'], index['records'][:56], 'Sealed56 prefix changed')
    require(len(raw['attempts']) == 11 and len(sealed['attempts']) == 12,
            'Historical amended-attempt boundary changed')
    equal(sealed['attempts'][:11], raw['attempts'], 'Sealing changed prior physical attempts')
    equal(index['attempts'][:12], sealed['attempts'], 'Sealed physical attempt prefix changed')
    require(len(raw['records']) == 55 and len(sealed['records']) == 56 and sealed['records'][55]['case_id'] == WALL and
            sealed['records'][55]['disposition'] == 'wall_time_failure', 'Raw/sealed boundary differs')
    return am, op, profile, reader, original, old_partial, wall_review, host_sources


def historical_operands(saved, registry, manifest, frozen):
    entries = registry['historical_comparators']
    require(len(entries) == 2 and {x['kind'] for x in entries} == {'fixed_floor', 'intercept_only'}, 'Both original comparators required')
    intercept_review = None
    for entry in entries:
        summary = saved.reference(entry['artifact']); review = saved.reference(entry['review'])
        if entry['kind'] == 'intercept_only':
            require(review['task_id'] == 'review_floor_results' and review['status'] == 'completed' and review['verdict'] == 'PASS_SAVED_OUTPUT_AUDIT', 'Wrong historical intercept review')
            result_path = 'validation/live_results/methodological_20261106/refitted_floor/result.json'
            result = saved.file(result_path, summary['result_sha256'])
            require(review['evidence_sha256']['numerical_continuation/full/result.json'] == summary['result_sha256'] and result['passed'] is True and result['phase'] == 'full', 'Historical full-result custody')
            intercept_review = review
        else:
            require(review.get('passed') is True or review.get('accepted') is True and review.get('final_scientific_accepted') is True, 'Historical fixed acceptance')
    rows = {}
    require(set(intercept_review['reviewed_case_sha256']) == {c['case_id']+'.json' for c in manifest.values()}, 'Historical reviewed80 roster')
    for key, c in manifest.items():
        old_path = 'reproduction/synthetic/'+c['expected']
        refit_path = 'validation/live_results/methodological_20261106/refitted_floor/'+key+'.json'
        fixed = saved.file(old_path, frozen[old_path]); refit = saved.file(refit_path, frozen[refit_path])
        require(intercept_review['reviewed_case_sha256'][key+'.json'] == frozen[refit_path], 'Historical case review SHA')
        require(fixed['seed'] == c['seed'] and fixed['regime'] == refit['regime'] == c['regime'] and refit['case_id'] == key, 'Historical history identity')
        require(len(fixed['results']) == len(refit['outcomes']) == 5, 'Historical five procedures')
        for model, gate in PROCEDURES:
            i, a = next((i, a) for i, a in enumerate(fixed['results']) if (a['model'], a['gate']) == (model, gate))
            j, b = next((j, b) for j, b in enumerate(refit['outcomes']) if (b['model'], b['gate']) == (model, gate))
            require(a['status'] == 'complete' and a['selected_state_index'] == b['selected_state_index'] and
                    a['win'] is (number(a['gain']) > 0) and b['new_win'] is (number(b['new_gain']) > 0), 'Historical selection/sign changed')
            close(a['gain'], b['original_gain'], 'Historical fixed gain identity')
            rows[(key, model, gate)] = dict(fixed_floor_gain=a['gain'], intercept_only_gain=b['new_gain'],
                fixed_floor=dict(path=old_path, sha256=frozen[old_path], json_pointer='/results/'+str(i)),
                intercept_only=dict(path=refit_path, sha256=frozen[refit_path], json_pointer='/outcomes/'+str(j)))
    return rows


def bind_physical_attempts(index, op, physical_evidence):
    """Bind the amended-index clock contract, not every historical clock alike.

    The first44 histories have no entries in this attempt list. Their charges
    remain in the exact reviewed baseline. The partial pilot entry is its NEW
    work only; the earlier failed attempt remains in that baseline. The wall
    failure retains its actual over-deadline duration rather than a capped or
    successful substitute. Public-reader entries use their worker result clock.
    """
    keys = op['full_sequence'][44:]
    require(len(index['records']) == 80 and [r['case_id'] for r in index['records']] == op['full_sequence'],
            'Resource roster must be the full original eighty')
    require([r['case_id'] for r in index['attempts']] == keys and set(physical_evidence) == set(keys),
            'Physical attempt/raw-evidence roster differs')
    require(len({r['numerical_attempt_id'] for r in index['attempts']}) == len(keys),
            'Physical numerical attempt duplicated')
    for record, attempt in zip(index['records'][44:], index['attempts']):
        key = record['case_id']; raw = physical_evidence[key]
        result, supervision = raw['result'], raw['supervision']; source = record['source']
        # raw.source is captured beside the independently hash-checked ZIP bytes.
        equal(raw['source'], source, 'Physical raw evidence/source association changed')
        require(result['case_id'] == key and isinstance(result['numerical_attempt_id'], str) and result['numerical_attempt_id'],
                'Physical result history/attempt identity differs')
        require(source['kind'] == 'host_execution', 'Physical attempt lacks actual host execution')
        expected = dict(case_id=key, numerical_attempt_id=result['numerical_attempt_id'],
            host_execution_id=source['execution_id'], seconds=result['wall_seconds'],
            outer_seconds=supervision['wall_seconds_including_cleanup'],
            result_sha256=source['result_sha256'], supervision_sha256=source['supervision_sha256'],
            actual_optimizer_attempts=result['actual_optimizer_attempts'],
            reused_optimizer_attempts=result['reused_optimizer_attempts'])
        equal(attempt, expected, 'Index attempt differs from bound result/supervision: '+key)


def audit_resources(report, index, final, op, entries, saved, physical_evidence):
    bind_physical_attempts(index, op, physical_evidence)
    value = report['resource_evidence']
    equal(value['index_budget'], index['budget'], 'Raw index budget rewritten')
    equal(value['indexed_host_overheads'], index['audited_host_overheads'], 'Indexed overhead copy changed')
    equal(value['final_live_resource'], final['resource'], 'Final live resource copy changed')
    equal(value['final_live_review'], dict(path=report['inputs']['index_review'],
        sha256=saved.pins[report['inputs']['index_review']], json_pointer='/resource'), 'Final resource locator')
    require(value['final_host_execution_id'] == final['execution_id'] == index['records'][-1]['source']['execution_id'], 'Final resource execution identity')
    overheads = index['audited_host_overheads']; ids = [r['execution_id'] for r in overheads]
    require(len(ids) == len(set(ids)) and final['execution_id'] not in ids and op['failure']['execution_id'] not in ids, 'Duplicate final/failed host overhead')
    suffix_host_ids = list(dict.fromkeys(r['source']['execution_id'] for r in index['records'][56:]))
    require(suffix_host_ids and suffix_host_ids[-1] == final['execution_id'] and
            op['failure']['execution_id'] not in suffix_host_ids, 'Operational suffix/final execution boundary differs')
    require(ids == suffix_host_ids[:-1], 'Missing, extra or reordered prior operational host overhead')
    overhead = Decimal(0)
    for row in overheads:
        entry, review = entries[row['execution_id']]
        equal(row['archive'], entry['archive'], 'Overhead archive substituted')
        equal(row['review'], entry['review'], 'Overhead review substituted')
        charge = Decimal(str(row['seconds']))
        require(charge.is_finite() and 0 <= charge <= 1800 and charge == Decimal(str(review['resource']['whole_workflow_overhead_beyond_all_child_outer_seconds'])), 'Unreviewed overhead charge')
        overhead += charge
    last = Decimal(str(final['resource']['whole_workflow_overhead_beyond_all_child_outer_seconds']))
    require(last.is_finite() and 0 <= last <= 1800, 'Final overhead exceeds reservation')
    suffix = index['attempts'][12:]
    require([r['case_id'] for r in index['attempts']] == op['full_sequence'][44:] and
            len({r['numerical_attempt_id'] for r in index['attempts']}) == len(index['attempts']), 'Physical attempts duplicated/missing')
    outer = sum((Decimal(str(r['outer_seconds'])) for r in suffix), Decimal(0))
    science = sum((Decimal(str(r['seconds'])) for r in suffix), Decimal(0))
    for row, slot in zip(suffix, op['case_slots']):
        require(0 <= Decimal(str(row['seconds'])) <= slot['scientific_seconds'] and
                Decimal(str(row['seconds'])) <= Decimal(str(row['outer_seconds'])) <= slot['wall_seconds'] and row['reused_optimizer_attempts'] == 0, 'Future case resource/reuse cap')
    basis = op['accounting']; baseline = Decimal(basis['sealed_known_seconds'])
    reserve = Decimal(basis['unconsumed_host_overhead_reserve_seconds'])-overhead
    accounted = baseline+outer+overhead
    upper = accounted+reserve+basis['global_finalization_reserve_seconds']
    expected = dict(sealed_known_seconds=str(baseline), future_scientific_seconds=str(science), future_outer_seconds=str(outer),
        audited_future_host_overhead_seconds=str(overhead), accounted_seconds=str(accounted), remaining_case_slots_seconds=0,
        unconsumed_host_overhead_reserve_seconds=str(reserve), global_finalization_reserve_seconds=basis['global_finalization_reserve_seconds'],
        upper_bound_seconds=str(upper), remaining_headroom_seconds=str(Decimal(basis['global_cap_seconds'])-upper), historical_unmeasured_setup_caveat=True)
    equal(index['budget'], expected, 'Independent final index budget differs')
    require(reserve >= last and upper <= 115200, 'Budget final overhead/reservation exceeds cap')
    return dict(index_accounted_seconds=str(accounted), final_overhead_not_indexed_seconds=str(last),
        known_with_final_host_overhead_seconds=str(accounted+last), conservative_reserved_upper_seconds=str(upper),
        historical_unmeasured_setup_caveat=True, overlapping_totals_added=False)


def source_preflight(repository):
    """Metadata-only readiness; no report/index/cohort access or acceptance."""
    repo = Path(repository).resolve()
    for name, pin in PINS.items():
        require(digest((repo/name).read_bytes()) == pin, 'Accepted source changed: '+name)
    return dict(status='source_contract_ready', sources=PINS, cohort_audited=False, scientific_calls=0)


def audit(repository, report_path):
    repo = Path(repository).resolve(); data = Path(report_path).read_bytes(); report = document(data)
    # Fixed source checks before imports, and fail before any case processing on a partial campaign.
    source_preflight(repo)
    require(report['schema'] == 'joint_nuisance_disposition_report_v1' and report['reporting_accepted'] is False and
        report['scientific_completion'] is False and report['original_publication_gate_satisfied'] is False and
        report['disposition_accounting_complete'] is True, 'Wrong final disposition flags')
    require(report['arithmetic_source_sha256'] == PINS[CORE], 'Report arithmetic source attribution changed')
    require(report['counts']['accepted_terminal_dispositions'] == 80 and report['counts']['pending_histories'] == 0, 'Final report not ready')
    saved = Saved(repo)
    try:
        paths = report['inputs']; require(set(paths) == {'index', 'registry', 'index_review'}, 'Input path keys')
        index, registry, final = (saved.file(paths[k]) for k in ('index', 'registry', 'index_review'))
        science = saved.file(SCIENCE, PINS[SCIENCE]); policy = saved.file(POLICY, PINS[POLICY])
        frozen = saved.file(INPUTS, science['input_pins_sha256']); manifest_doc = saved.file(MANIFEST, frozen[MANIFEST])
        # Additional independent historical operands are checked separately from
        # the formatter's exact consumed-source-pin set.
        for name, pin in frozen.items():
            with saved.path(name).open('rb') as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == pin, 'Frozen historical input changed: '+name)
        manifest = {r['case_id']: r for r in manifest_doc['s04b']['cases']}; sequence = policy['full_sequence']
        require(len(sequence) == len(set(sequence)) == len(manifest) == 80 and set(sequence) == set(science['roster']) == set(manifest), 'Frozen80 roster')
        require([r['case_id'] for r in index['records']] == sequence and index['passed'] is False and index['scientific_completion'] is False, 'Final index not exact80')
        live(final)
        require(final['all_histories_attempted'] is True and final['index_sha256'] == saved.pins[paths['index']] and final['counts'] == index['counts'], 'Final live review not bound to80')
        am, op, profile, producer, original, partial, wall_review, host_sources = source_contract(saved, report, registry, index, science, policy)
        am_sources = op['core_source_sha256']
        spec = importlib.util.spec_from_file_location('independent_final_saved_case_audit', repo/CHECKER)
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        # Only saved-case checks are reused; no aggregate helper is called anywhere.
        historical = historical_operands(saved, registry, manifest, frozen)
        equal(report['historical_comparators'], registry['historical_comparators'], 'Historical registry reference copy')
        archives, executions = {}, {}
        for entry in registry['archives']:
            ref = policy['immutable_failure_reference']
            equal(entry['archive'], dict(path=ref['archive'], sha256=ref['archive_sha256']), 'Immutable archive substituted')
            equal(entry['review'], dict(path=ref['review'], sha256=ref['review_sha256']), 'Immutable review substituted')
            review = saved.reference(entry['review']); live(review, True); saved.archive(entry['archive'])
            require(entry['archive']['sha256'] not in archives, 'Duplicate immutable archive')
            archives[entry['archive']['sha256']] = entry, review
        require(len(archives) == 1, 'One original immutable archive required')
        for entry in registry['executions']:
            key = entry['execution_id']; require(key and key not in executions, 'Duplicate execution registry entry')
            review = saved.reference(entry['review']); saved.archive(entry['archive'])
            live(review, review['passed'] is False)
            require(review['execution_id'] == key and review['artifact_sha256'] == entry['archive']['sha256'], 'Execution/archive review mismatch')
            executions[key] = entry, review
        records = {r['case_id']: r for r in index['records']}; raw_cases, locators, unknowns, failures, work = {}, {}, [], [], []
        physical_evidence = {}
        require(len(report['case_dispositions']) == 80 and [r['case_id'] for r in report['case_dispositions']] == sequence, 'Report disposition roster')
        used = set(); floor_count = 0
        for position, (key, entry_report) in enumerate(zip(sequence, report['case_dispositions'])):
            record = records[key]; source = record['source']; disposition = record['disposition']
            require(disposition in ('complete', 'scientific_unknown', 'wall_time_failure') and record['scientific_passed'] is (disposition == 'complete'), 'Wrong disposition flags')
            if position < 41:
                require(source['kind'] == 'immutable_archive', 'Original archive disguised')
                entry, review = archives[source['archive_sha256']]
                names = {k: source[k+'_member'] for k in ('case', 'trace')}
            else:
                require(source['kind'] == 'host_execution', 'Missing execution source')
                used.add(source['execution_id']); entry, review = executions[source['execution_id']]
                names = {k: entry['member_prefix']+source[k+'_path'] for k in ('case', 'trace', 'result', 'supervision')}
                require(key in review['checked_case_ids'] or key == WALL, 'Case not live reviewed')
                if review['passed'] is False and key != WALL:
                    permitted = review['accepted_completed_case_ids'] if 'accepted_completed_case_ids' in review else review['accepted_completed_prefix']['new_complete_cases']
                    require(disposition == 'complete' and key in permitted, 'Unaccepted failed-host case borrowed')
            archive = entry['archive']; values, refs = {}, {}
            for kind, name in names.items():
                values[kind] = saved.member(archive, name, source[kind+'_sha256'], lines=kind == 'trace')
                refs[kind] = saved.locator(archive, name, source[kind+'_sha256'])
            refs['independent_review'] = entry['review']
            if key == WALL:
                refs['sealing_review'] = registry['operational_continuation']['sealing_review']
            case = values['case']; result = values.get('result'); events = values['trace']
            if position >= 44:
                physical_evidence[key] = dict(result=result, supervision=values['supervision'], source=deepcopy(source))
            raw_cases[key], locators[key] = case, refs
            for field in ('case_id', 'seed', 'regime'):
                require(case[field] == record[field] == manifest[key][field] == entry_report[field], 'Case identity mismatch')
            equal(entry_report['evidence'], refs, 'Disposition evidence locators changed')
            require(entry_report['disposition'] == disposition and entry_report['scientific_passed'] is (disposition == 'complete'), 'Disposition report flags')
            expected_source = result['source_sha256'] if result else review['source_sha256']
            equal(entry_report['source_identity'], dict(scientific_protocol_sha256=PINS[SCIENCE], remaining_protocol_sha256=PINS[POLICY],
                native=policy['original_native'], executed_source_sha256=expected_source), 'Case source identity')
            if result:
                require(result['report_sha256'] == source['case_sha256'] and result['trace_sha256'] == source['trace_sha256'], 'Result/case trace pins')
                equal(result['source_sha256'], review['source_sha256'], 'Per-execution source graph')
                expected_sources = producer['execution_source_sha256'] if 'execution_producer' in record else am_sources if position >= 44 else original['scientific_source_sha256']
                equal(result['source_sha256'], expected_sources, 'Execution version disguise')
                equal(result['runtime']['essential'], policy['original_native']['runtime_essential'], 'Runtime changed')
                for field in ('library_sha256', 'build_receipt_sha256'):
                    require(result[field] == policy['original_native'][field], 'Native identity changed')
                if key != WALL:
                    require(result['handled'] is True and result['disposition_valid'] is True and result['disposition'] == disposition and
                        result['scientific_passed'] is (disposition == 'complete') and result['passed'] is (disposition == 'complete'), 'Raw result relabeled')
                    sup = values['supervision']
                    require(sup['status'] == 'passed' and sup['returncode'] == 0 and sup['stop_reason'] is None and not sup['cleanup_errors'] and not sup['survivors_after_cleanup'], 'Failed child supervisor')
                if position >= 56:
                    equal(review['host_source_sha256'], host_sources, 'Operational host source map')
                    equal(review['operational_continuation'], registry['operational_continuation']['protocol'], 'Operational live identity')
            if 'execution_producer' in record:
                for value in (record, case, result, review):
                    equal(value['execution_producer'], producer, 'Actual public entrypoint identity')
                equal(entry_report['public_reader']['execution_producer'], producer, 'Public producer report copy')
                parent = PurePosixPath(names['result']).parent
                request = saved.member(archive, str(parent/'reader_request.json'), result['reader_request_sha256'])
                bundle = saved.member(archive, str(parent/'bundled_native.json'), result['bundled_native_sha256'])
                equal(request['actual_command'], result['actual_command'], 'Actual public command copy')
                equal(entry_report['public_reader']['actual_command'], result['actual_command'], 'Reported public command')
                require(request['mode'] == result['execution_mode'] == 'author_envelope' and request['execution_producer'] == producer, 'Reader execution mode')
                equal(bundle, result['bundled_native'], 'Bundled native extraction receipt')
                equal(bundle, dict(profile['bundled_native'], library_path='native/attenuation.so', build_receipt_path='native/build_receipt.json'), 'Bundled native origin')
            else:
                require('execution_producer' not in case and (not result or 'execution_producer' not in result), 'Hidden public producer')
            if disposition == 'complete':
                helper.core.inspect_case(case, science)
                equal(entry_report['model_census'], dict(attempted_models=list(ARMS), completed_models=list(ARMS),
                    not_run_models=[], logical_optimizer_attempts=sum(len(case['fits'][arm]['records']) for arm in ARMS),
                    unsuccessful_logical_optimizer_attempts=sum(r['success'] is False for arm in ARMS for r in case['fits'][arm]['records'])), 'Complete logical fit census')
                equal(record['outcomes'], case['outcomes'], 'Compact complete outcomes')
                helper.trace_matches(saved.member(archive, names['trace'], source['trace_sha256'], raw=True), case)
            elif disposition == 'scientific_unknown':
                require(key != WALL and events[-1]['event'] == 'attempt_end', 'Unknown trace terminal')
                last = events[-1]; terminal = {k:v for k,v in last.items() if k not in ('event', 'model')}
                limits = science['solver']['powell']
                require(last['method'] == 'Powell' and last['status'] == 'returned' and last['finite_feasible'] is True and
                    last['success'] is False and last['solver_success'] is False and math.isfinite(last['returned_nll']) and
                    ((last['solver_status'] == 1 and last['nfev'] == limits['maxfev']) or
                     (last['solver_status'] == 2 and last['nit'] == limits['maxiter'])), 'Unknown is not original finite optimizer cap')
                if key == UNKNOWN:
                    require(position == 40 and record['unknown_origin'] == 'audited_retained_failure', 'Permanent unknown reclassified')
                    equal(terminal, review['failure']['capped_optimizer_record'], 'Permanent cap record')
                else:
                    require(result['unknown_outcome_count'] == 5 and case['error_type'] == 'ValueError' and case['error'] in ('Unresolved null starts', 'Unresolved alternative starts'), 'Technical failure disguised as unknown')
                    equal(terminal, result['terminal_solver_return'], 'Unknown solver return')
                unknowns.append(dict(case_id=key, reason_code='original_optimizer_cap_unknown', failed_model=last['model'], unresolved_start=last['start_index'], terminal_solver_return=terminal, model_census=record['model_census']))
                equal(entry_report['model_census'], record['model_census'], 'Reported unknown model census')
            else:
                require(key == WALL and position == 55 and result['handled'] is False and result['disposition_valid'] is False and
                    result['passed'] is False and result['scientific_passed'] is False and result['disposition'] == 'technical_failure' and
                    case['error_type'] == 'TimeoutError' and case['error'] == 'Joint experiment deadline' and
                    result['error_type'] == 'ValueError' and result['error'] == 'Case optimizer records differ from trace', 'Wall failure laundered')
                equal(review, wall_review, 'Failure review substitution')
                census = op['failure']['failure_census']; equal(record['failure_census'], census, 'Wall census copy'); equal(review['failure'], census, 'Wall census source')
                require(census['held_out_calls'] == 0 and census['new_outcomes_available'] == 0, 'Failure has outcomes')
                failures.append(dict(case_id=key, reason_code='scientific_wall_limit', disposition='wall_time_failure',
                    primary_error=dict(type=case['error_type'], message=case['error']), secondary_error=dict(type=result['error_type'], message=result['error']),
                    **{k:census[k] for k in ('physical_optimizer_attempts', 'successful_optimizer_returns', 'optimizer_exception_attempts', 'completed_arms', 'unfinished_arm', 'successful_trace_only_starts', 'interrupted_start', 'not_run_starts')},
                    held_out_calls=0, scientific_seconds=result['wall_seconds'], outer_seconds=values['supervision']['wall_seconds_including_cleanup'], evidence=refs))
            require((key != UNKNOWN or disposition == 'scientific_unknown') and (position >= 40 or disposition == 'complete'), 'Immutable disposition changed')
            helper.core.inspect_historical(case, manifest[key], repo)
            expected_floors = {(phase, model) for phase in (('train', 'test') if disposition == 'complete' else ('train',)) for model in MODELS}
            floors = case['floor_checks']; require(len(floors) == len(expected_floors) and {(r['phase'],r['model']) for r in floors} == expected_floors, 'Retained floor roster')
            for floor in floors:
                require(floor['tolerance'] == 1e-9, 'Floor tolerance changed')
                close(floor['actual_nll'], floor['expected_nll'], 'Saved historical floor')
                close(floor['absolute_delta'], abs(floor['actual_nll']-floor['expected_nll']), 'Floor delta')
            floor_count += len(floors)
            if position >= 44 and key != WALL:
                mode = 'partial' if key == PARTIAL else 'untouched'; meta = result['numerical_amendment']
                equal(meta, case['numerical_amendment'], 'Case amendment identity'); equal(meta, record['numerical_amendment'], 'Index amendment identity')
                parent = PurePosixPath(names['result']).parent
                reuse = saved.member(archive, str(parent/'reuse_map.json'), meta['reuse_map_sha256'])
                refinements = saved.member(archive, str(parent/'refinement_events.jsonl'), meta['refinement_event_log_sha256'], lines=True)
                calls = saved.member(archive, str(parent/'execution_calls.jsonl'), meta['execution_calls_sha256'], lines=True)
                pairs = helper.inspect_refinements(refinements, science)
                physical = helper.inspect_reused_values(case, partial, mode)
                counts, reuse_calls = helper.inspect_physical_calls(calls, physical, pairs, science, result['adapter'])
                helper.inspect_reuse_map(reuse, case, partial, mode, am, result['adapter'], reuse_calls)
                helper.inspect_support_counts(case, result['adapter'], mode, physical)
                computation = entry_report['computation']
                equal(computation['numerical_amendment'], meta, 'Reported amendment identity')
                require(computation['kind'] == ('amended_partial_resume' if mode == 'partial' else 'amended_untouched') and
                    computation['prior_failed_total_start4_attempts_retained'] == (2 if mode == 'partial' else 0), 'Reported reuse/old failure scope')
                require(counts['actual_optimizer_attempts'] == result['actual_optimizer_attempts'] == computation['actual_optimizer_attempts'] and
                        result['reused_optimizer_attempts'] == computation['reused_optimizer_attempts'] == (28 if mode == 'partial' else 0), 'Physical/reused census')
                equal(result['refinement_census'], dict(started=counts['refinement_started'], accepted=counts['refinement_accepted'], rejected=counts['refinement_rejected']), 'Refinement counts')
                equal(computation['refinement_census'], result['refinement_census'], 'Reported refinement counts')
                equal(computation['evaluation_census'], result['evaluation_census'], 'Reported physical evaluations')
                work.append(dict(case_id=key, **counts, reused_optimizer_attempts=result['reused_optimizer_attempts']))
        require(used == set(executions), 'Unused/unresolved execution registry entry')
        counts = Counter(r['disposition'] for r in records.values()); c, u, w = (counts[k] for k in ('complete', 'scientific_unknown', 'wall_time_failure'))
        require(c+u+w == 80 and u >= 1 and w == 1, 'Final accounting cardinality')
        expected_index = dict(processed_histories=80, complete_histories=c, unknown_histories=u, unattempted_histories=0, computed_outcomes=5*c, wall_time_failure_histories=w)
        equal(index['counts'], expected_index, 'Final terminal index counts')
        expected_counts = dict(planned_histories=80, accepted_terminal_dispositions=80, complete_histories=c, scientific_unknown_histories=u, pending_histories=0, unresolved_technical_failures=w, planned_outcomes=400, computed_outcomes=5*c, unavailable_outcomes=5*(u+w), regime_procedure_rows=20, wall_time_failure_histories=w)
        equal(report['counts'], expected_counts, 'Report census')
        equal(report['unknown_census'], unknowns, 'Optimizer unknown census')
        equal(report['failure_census'], failures, 'Technical wall failure census')
        check_slots(report, sequence, records, raw_cases, locators, historical)
        summary = summarize(sequence, records, raw_cases, science)
        compare(report['regime_summary'], summary)
        equal(report['complete_regimes'], [r for r in range(4,8) if all(v['disposition'] == 'complete' for v in records.values() if v['regime'] == r)], 'Full-regime eligibility')
        equal(report['coverage'], dict(verified_new_historical_comparison_rows=5*c, verified_retained_floor_checks=floor_count, preserved_fixed_floor_outcomes=400, preserved_intercept_only_outcomes=400), 'Coverage census')
        expected_campaign = dict(scientific_protocol_sha256=PINS[SCIENCE], remaining_protocol_sha256=PINS[POLICY], immutable_failure_reference_sha256=policy['immutable_failure_reference']['review_sha256'], numerical_amendment_protocol_sha256=PINS[AMENDMENT], numerical_amendment_source_review_sha256=registry['numerical_amendment']['source_review']['sha256'], operational_continuation_protocol_sha256=PINS[OPERATIONAL])
        equal(report['campaign_identity'], expected_campaign, 'Campaign identity')
        resources = audit_resources(report, index, final, op, executions, saved, physical_evidence)
        equal(report['source_pins'], saved.pins, 'Independently reconstructed source-pin roster differs')
        return dict(schema='independent_final_disposition_saved_check_v1', review_kind='automated_independent_disposition_saved_output_check',
            reporting_accepted=False, live_independent_review=False, final_live_review_required=True,
            disposition_accounting_complete=True, scientific_completion=False, original_publication_gate_satisfied=False,
            report_sha256=digest(data), campaign_identity=expected_campaign, counts=expected_counts,
            source_pins=saved.pins, independent_summary=summary, unknown_census=unknowns, failure_census=failures,
            independent_resource_reconciliation=resources, amendment_physical_work_census=work,
            complete_regimes=report['complete_regimes'], coverage=report['coverage'],
            scientific_calls=0, optimizer_calls=0, builder_imported=False, producer_imported=False, aggregate_helper_called=False,
            verified_frozen_historical_input_count=len(frozen),
            audit_source_sha256=digest(Path(__file__).read_bytes()), accepted_contract_sources=PINS,
            scope='Independent arithmetic over exact saved operands and bound live execution evidence. No likelihood/native/refit calls. This automated output requires subsequent live reviewer acceptance; incomplete regimes have no full-regime statistics.')
    finally:
        saved.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.resolve().is_relative_to(args.repository.resolve()), 'Fresh private output required')
    result = audit(args.repository, args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(args.output), sha256=digest(args.output.read_bytes()), counts=result['counts'], live_acceptance_issued=False)))


if __name__ == '__main__':
    main()
