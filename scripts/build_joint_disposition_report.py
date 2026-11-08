"""Build a separate, saved-output-only report after all 80 dispositions are audited.

This does not issue acceptance, run a scientific checker, fit a model, or install
publication files. Inputs are public repository-relative JSON paths. The registry
schema is ``joint_disposition_execution_registry_v1``: ``archives`` contain
``archive`` and ``review`` {path, sha256} references; ``executions`` additionally
contain execution_id and member_prefix (normally ``host/``). Historical comparator
entries contain kind (fixed_floor/intercept_only), artifact and review references.
The genuine live final index review binds the index hash and its actual counts.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import zipfile

try:
    from scripts.render_joint_nuisance_results import (PROCEDURES, PRIMARY, LABELS,
        require, sha, read, safe, numeric, integer, close)
except ModuleNotFoundError:  # Direct CLI invocation.
    from render_joint_nuisance_results import (PROCEDURES, PRIMARY, LABELS,
        require, sha, read, safe, numeric, integer, close)

SCIENCE = 'experiments/s04b_joint_nuisance/protocol.json'
POLICY = 'experiments/s04b_joint_remaining/protocol.json'
MANIFEST = 'reproduction/synthetic/input_manifest.json'
INPUT_PINS = 'experiments/s04b_joint_nuisance/input_pins.json'
CORE = 'experiments/s04b_joint_nuisance_audit/audit.py'
CORE_SHA256 = '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3'
ARMS = ('null', *LABELS)
UNKNOWN_CASE = 'S5_broad_long_imm_seed410518'
REPORT_SCHEMA = 'joint_nuisance_disposition_report_v1'
NULL_FIELDS = ('new_gain', 'new_win', 'near_zero', 'robust_positive', 'robust_negative',
               'off_floor', 'floor_return', 'parameters', 'selected_state_index',
               'score', 'new_null_score', 'delta', 'boundaries', 'training_gain',
               'gate_active', 'coarse_fine_gate_disagreement', 'null_search_gap_detected')


def document(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key: '+key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+value)))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def member_name(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name,
            'Unsafe archive member')
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and
            str(path) == name.rstrip('/'), 'Unsafe archive member')
    return name


def live_review(review, failure=False):
    require(review.get('live_agent_review') is True and
            review.get('live_agent_review_performed', True) is True and
            review.get('review_kind') == ('live_agent_failure_and_partial_output_review' if failure
                                         else 'live_agent_saved_output_review') and
            review.get('final_batch_agent_review_required', False) is False and
            review.get('audit_passed') is True and review.get('scientific_completion') is False,
            'A completed live independent disposition review is required')
    require(review.get('passed') is (not failure), 'Review execution/failure flags differ')


class Evidence:
    """Resolve public bytes, pin every operand, and never extract ZIP members."""
    def __init__(self, repository):
        self.repository = Path(repository).resolve()
        self.pins = {}
        self.archives = {}
        self.members = {}

    def file(self, relative, expected=None):
        path = safe(self.repository, relative)
        actual = sha(path)
        require(expected is None or actual == expected, 'Source hash differs: '+relative)
        self.pins[relative] = actual
        return read(path)

    def reference(self, reference):
        require(set(reference) == {'path', 'sha256'}, 'Expected path/sha256 reference')
        return self.file(reference['path'], reference['sha256'])

    def archive(self, reference):
        path = safe(self.repository, reference['path'])
        actual = sha(path)
        require(actual == reference['sha256'], 'Archive hash differs')
        self.pins[reference['path']] = actual
        if actual not in self.archives:
            with zipfile.ZipFile(path) as saved:
                names = saved.namelist()
                require(len(names) == len(set(names)), 'Duplicate archive member')
                for info in saved.infolist():
                    member_name(info.orig_filename)
                    member_name(info.filename)
            self.archives[actual] = path
        return actual

    def member(self, archive, name, expected, as_json=True):
        member_name(name)
        key = (archive, name)
        if key not in self.members:
            with zipfile.ZipFile(self.archives[archive]) as saved:
                self.members[key] = saved.read(name)
        data = self.members[key]
        require(digest(data) == expected, 'Archive member hash differs: '+name)
        return document(data) if as_json else data

    def locator(self, archive, name, expected, pointer=''):
        return dict(path=self.archives[archive].relative_to(self.repository).as_posix(),
                    sha256=archive, member=name, member_sha256=expected, json_pointer=pointer)


def arithmetic():
    """Import only the unchanged independent standard-library arithmetic module."""
    path = Path(__file__).resolve().parents[1]/CORE
    require(sha(path) == CORE_SHA256, 'Independent arithmetic utility changed')
    spec = importlib.util.spec_from_file_location('disposition_arithmetic', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def registry_sources(evidence, registry, policy):
    require(registry.get('schema') == 'joint_disposition_execution_registry_v1', 'Unknown registry schema')
    archives, executions = {}, {}
    ref = policy['immutable_failure_reference']
    for entry in registry['archives']:
        pin = evidence.archive(entry['archive'])
        require(pin not in archives, 'Duplicate archive registry identity')
        require(entry['archive'] == dict(path=ref['archive'], sha256=ref['archive_sha256']) and
                entry['review'] == dict(path=ref['review'], sha256=ref['review_sha256']),
                'Immutable archive or review was substituted')
        review = evidence.reference(entry['review'])
        live_review(review, failure=True)
        require(review['archive_sha256'] == pin, 'Live review does not bind archive')
        archives[pin] = (entry, review)
    require(set(archives) == {ref['archive_sha256']}, 'Immutable prefix archive missing')
    for entry in registry['executions']:
        execution = entry['execution_id']
        require(isinstance(execution, str) and execution and execution not in executions,
                'Duplicate or empty execution identity')
        pin = evidence.archive(entry['archive'])
        prefix = entry['member_prefix']
        require(prefix.endswith('/'), 'Archive member prefix must end in slash')
        member_name(prefix)
        review = evidence.reference(entry['review'])
        live_review(review)
        require(review['artifact_sha256'] == pin and review['execution_id'] == execution,
                'Live review does not bind execution archive')
        ids = review['checked_case_ids']
        require(len(ids) == len(set(ids)) and set(ids) <= set(policy['case_ids']),
                'Live host review case roster differs')
        executions[execution] = (entry, review)
    return archives, executions


def projection(report):
    fits = report['fits']
    return dict(case_id=report['case_id'], regime=report['regime'], seed=report['seed'],
        n_train=report['n_train'], n_test=report['n_test'], thinning=report['thinning'],
        optimizer_failed_attempts_by_arm={name: sum(record['success'] is False for record in fits[name]['records'])
                                         for name in ARMS if name in fits},
        null_search_gap_by_arm={name: bool(fits[name]['null_search_gaps']) for name in ARMS
                               if name in fits and fits[name]['passed'] is True})


def resolve_case(evidence, record, archives, executions, policy):
    source = record['source']
    if source['kind'] == 'immutable_archive':
        require(source['archive_sha256'] in archives, 'Unregistered immutable archive')
        entry, review = archives[source['archive_sha256']]
        archive = source['archive_sha256']
        case_member, trace_member = source['case_member'], source['trace_member']
        other = {}
    else:
        require(source['kind'] == 'host_execution' and source['execution_id'] in executions,
                'Unregistered host execution')
        entry, review = executions[source['execution_id']]
        require(record['case_id'] in review['checked_case_ids'], 'Case lacks live host review')
        archive, prefix = entry['archive']['sha256'], entry['member_prefix']
        for field in ('case_path', 'trace_path', 'result_path', 'supervision_path'):
            member_name(source[field])
        case_member, trace_member = prefix+source['case_path'], prefix+source['trace_path']
        other = {}
        for key in ('result', 'supervision'):
            member = prefix+source[key+'_path']
            value = evidence.member(archive, member, source[key+'_sha256'])
            other[key] = value
            other[key+'_reference'] = evidence.locator(archive, member, source[key+'_sha256'])
        result = other['result']
        require(result.get('schema') == 'joint_remaining_case_result_v1' and result.get('handled') is True and
                result.get('disposition_valid') is True and result.get('status') == 'terminal_disposition' and
                result['case_id'] == record['case_id'] and result['disposition'] == record['disposition'] and
                result['scientific_passed'] is record['scientific_passed'], 'Case result disposition differs')
        require(result['report_sha256'] == source['case_sha256'] and
                result['trace_sha256'] == source['trace_sha256'], 'Result does not bind case and trace')
        require(result['protocol_sha256'] == evidence.pins[POLICY] and
                result['immutable_failure_reference'] == policy['immutable_failure_reference'],
                'Result protocol or immutable lineage differs')
        native = policy['original_native']
        require(result['runtime']['essential'] == native['runtime_essential'] and
                all(result[key] == native[key] for key in ('library_sha256', 'build_receipt_sha256')),
                'Original runtime/native identity differs')
        supervision = other['supervision']
        require(supervision.get('status') == 'passed' and supervision.get('returncode') == 0 and
                supervision.get('launched') is True and supervision.get('stop_reason') is None and
                supervision.get('cleanup_errors') == [] and supervision.get('survivors_after_cleanup') == [],
                'Technical supervision failure cannot be terminal science')
    report = evidence.member(archive, case_member, source['case_sha256'])
    trace = evidence.member(archive, trace_member, source['trace_sha256'], as_json=False)
    events = [document(line) for line in trace.splitlines()]
    require(events and all(isinstance(event, dict) for event in events), 'Missing attempt trace')
    refs = dict(case=evidence.locator(archive, case_member, source['case_sha256']),
                trace=evidence.locator(archive, trace_member, source['trace_sha256']),
                independent_review=entry['review'])
    for key in ('result', 'supervision'):
        if key in other:
            refs[key] = other[key+'_reference']
    return report, events, refs, review, other.get('result')


def unknown_census(record, report, events, review, result, policy):
    require(record['scientific_passed'] is False and report.get('passed') is False and
            report.get('outcomes') == [] and record.get('outcomes') == [] and
            not report.get('test_checks') and 'new_null_test' not in report and
            'bic_threshold' not in report and not report.get('training_selections_frozen', False),
            'Unknown contains held-out score or accepted selection')
    last = events[-1]
    require(last.get('event') == 'attempt_end' and last.get('success') is False and
            last.get('solver_success') is False and last.get('method') == 'Powell' and
            last.get('status') == 'returned' and last.get('finite_feasible') is True,
            'Unknown is not an original finite capped optimizer return')
    limits = policy['_science']['solver']['powell']
    require((last['solver_status'] == 1 and last['nfev'] == limits['maxfev']) or
            (last['solver_status'] == 2 and last['nit'] == limits['maxiter']),
            'Unknown did not exhaust an original optimizer cap')
    numeric(last['returned_nll'])
    terminal = {key: value for key, value in last.items() if key not in ('event', 'model')}
    if record['case_id'] == UNKNOWN_CASE:
        require(terminal == review['failure']['capped_optimizer_record'] and
                record['unknown_origin'] == 'audited_retained_failure', 'Immutable failure evidence differs')
        require(record['model_census'] == review['execution_census'], 'Immutable failure census differs')
        census = record['model_census']
    else:
        require(report.get('status') == 'unknown' and report.get('error_type') == 'ValueError' and
                report.get('error') in ('Unresolved null starts', 'Unresolved alternative starts'),
                'Technical failure cannot become scientific unknown')
        failed = report['fits'][last['model']]
        require(failed.get('passed') is False and failed.get('status') == 'unknown_starts' and
                'selected' not in failed and 'selected_state_index' not in failed,
                'Failed arm has an accepted selection')
        require(result is not None and result['passed'] is False and result['unknown_outcome_count'] == 5 and
                result['terminal_solver_return'] == terminal and
                result['phase_constructions'] == [dict(start=30, end=395, returned=True)],
                'Unknown result contains held-out phase or different terminal evidence')
        require(record.get('unknown_origin') == 'new_frozen_solver_cap' and
                record.get('terminal_solver_return') == terminal and
                record.get('unknown_reason') == result['unknown_reason'], 'Compact unknown evidence differs')
        census = result['model_census']
        require(record['model_census'] == census and census['held_out_phase_constructed'] is False,
                'Unknown model/start census differs')
    return dict(case_id=record['case_id'], reason_code='original_optimizer_cap_unknown',
                failed_model=last['model'], unresolved_start=last['start_index'],
                terminal_solver_return=terminal, model_census=deepcopy(census))


def historical(evidence, cases, registry, frozen):
    """Preserve both original 400-row comparators, including unknown new cases."""
    entries = registry['historical_comparators']
    require(len(entries) == 2 and {entry['kind'] for entry in entries} == {'fixed_floor', 'intercept_only'},
            'Both unchanged historical comparators are required')
    for entry in entries:
        evidence.reference(entry['artifact'])
        review = evidence.reference(entry['review'])
        require(review.get('passed') is True or (review.get('accepted') is True and
                review.get('final_scientific_accepted') is True), 'Historical acceptance missing')
    rows = {}
    for case in cases:
        expected_path = 'reproduction/synthetic/'+case['expected']
        old_path = 'validation/live_results/methodological_20261106/refitted_floor/'+case['case_id']+'.json'
        require(expected_path in frozen and old_path in frozen, 'Historical operands absent from frozen input pins')
        expected, old = evidence.file(expected_path, frozen[expected_path]), evidence.file(old_path, frozen[old_path])
        require(old['case_id'] == case['case_id'] and old['regime'] == case['regime'] and
                expected['regime'] == case['regime'] and expected['seed'] == case['seed'],
                'Historical case identity differs')
        expected_rows, old_rows = expected['results'], old['outcomes']
        for collection in (expected_rows, old_rows):
            require(len(collection) == 5 and {(r['model'], r['gate']) for r in collection} == set(PROCEDURES),
                    'Historical comparator roster differs')
        for model, gate in PROCEDURES:
            i = next(i for i, value in enumerate(expected_rows) if (value['model'], value['gate']) == (model, gate))
            j = next(i for i, value in enumerate(old_rows) if (value['model'], value['gate']) == (model, gate))
            original, intercept = expected_rows[i], old_rows[j]
            require(original['status'] == 'complete' and close(original['gain'], intercept['original_gain']) and
                    original['selected_state_index'] == intercept['selected_state_index'],
                    'Historical fixed-floor comparison changed')
            for gain, win in ((original['gain'], original['win']), (intercept['new_gain'], intercept['new_win'])):
                require(type(win) is bool and win == (numeric(gain) > 0), 'Historical strict win differs')
            rows[(case['case_id'], model, gate)] = dict(
                fixed_floor_gain=original['gain'], intercept_only_gain=intercept['new_gain'],
                fixed_floor=dict(path=expected_path, sha256=evidence.pins[expected_path], json_pointer=f'/results/{i}'),
                intercept_only=dict(path=old_path, sha256=evidence.pins[old_path], json_pointer=f'/outcomes/{j}'))
    return entries, rows


def build(repository, paths):
    """Return (report, source pins); does not write or manufacture acceptance."""
    require(set(paths) == {'index', 'registry', 'index_review'}, 'Index, registry and final index review required')
    evidence = Evidence(repository)
    for relative in paths.values():
        require(relative.startswith('validation/') and not relative.startswith('validation/authorities/'),
                'Public live disposition inputs required')
    index, registry, final = (evidence.file(paths[key]) for key in ('index', 'registry', 'index_review'))
    science, policy, manifest = (evidence.file(path) for path in (SCIENCE, POLICY, MANIFEST))
    frozen = evidence.file(INPUT_PINS, science['input_pins_sha256'])
    require(frozen[MANIFEST] == evidence.pins[MANIFEST], 'Frozen input manifest identity differs')
    require(policy['scientific_protocol_sha256'] == evidence.pins[SCIENCE] and
            index['protocol_sha256'] == evidence.pins[POLICY], 'Frozen protocol identity differs')
    sequence = policy['full_sequence']
    require(len(sequence) == len(set(sequence)) == len(science['roster']) == 80 and set(sequence) == set(science['roster']),
            'Exactly the frozen eighty histories are required')
    failure = policy['immutable_failure_reference']
    require(sequence[:40] == failure['complete_case_ids'] and sequence[40] == failure['case_id'] == UNKNOWN_CASE and
            sequence[41:] == policy['case_ids'], 'Original 40 + 1 + 39 partition differs')
    cases = {case['case_id']: case for case in manifest['s04b']['cases']}
    require(len(cases) == len(manifest['s04b']['cases']) == 80 and set(cases) == set(sequence) and
            Counter(case['regime'] for case in cases.values()) == Counter({r:20 for r in range(4, 8)}),
            'Frozen input manifest roster differs')
    require(index.get('schema') == 'joint_remaining_index_v1' and index.get('passed') is False and
            index.get('scientific_completion') is False and
            [record['case_id'] for record in index['records']] == sequence, 'Final compact disposition index required')
    require(index['original_native'] == policy['original_native'] and
            index['immutable_failure_reference'] == failure, 'Index immutable identities differ')
    live_review(final)
    for count in index['counts'].values():
        integer(count)
    for count in final['counts'].values():
        integer(count)
    require(final['index_sha256'] == evidence.pins[paths['index']] and final['counts'] == index['counts'] and
            final.get('all_histories_attempted') is True, 'Live final index review does not bind all eighty dispositions')
    archives, executions = registry_sources(evidence, registry, policy)
    comparator_refs, old = historical(evidence, [cases[key] for key in sequence], registry, frozen)
    reports, dispositions, outcomes, unknowns = {}, [], [], []
    used_executions = set()
    historical_checks = floor_checks = 0
    for n, record in enumerate(index['records']):
        case_id, disposition = record['case_id'], record['disposition']
        require(disposition in ('complete', 'scientific_unknown') and
                record['scientific_passed'] is (disposition == 'complete'), 'Unaccepted terminal disposition')
        source = record['source']
        require(source['kind'] == ('immutable_archive' if n < 41 else 'host_execution'),
                'Original prefix/source partition changed')
        if n < 40:
            require(disposition == 'complete', 'Immutable complete prefix changed')
        if n == 40:
            require(disposition == 'scientific_unknown' and all(source[key] == failure[key] for key in
                    ('archive_sha256', 'case_member', 'case_sha256', 'trace_member', 'trace_sha256')),
                    'Permanent unknown cannot become complete or change source')
        if n >= 41:
            used_executions.add(source['execution_id'])
        report, events, refs, review, result = resolve_case(evidence, record, archives, executions, policy)
        if result:
            require(result['source_sha256'] == index['scientific_source_sha256'], 'Executed scientific source identity differs')
        for key, value in projection(report).items():
            require(record[key] == value, 'Compact projection differs from saved case: '+key)
        require(all(report[key] == cases[case_id][key] for key in ('case_id', 'regime', 'seed')),
                'Case manifest identity differs')
        entry = dict(case_id=case_id, regime=report['regime'], seed=report['seed'], disposition=disposition,
                     scientific_passed=disposition == 'complete', evidence=refs,
                     source_identity=dict(scientific_protocol_sha256=evidence.pins[SCIENCE],
                         remaining_protocol_sha256=evidence.pins[POLICY], native=policy['original_native'],
                         executed_source_sha256=result['source_sha256'] if result else review['source_sha256']))
        if disposition == 'complete':
            require(report.get('passed') is True and report.get('status') == 'complete' and
                    record['outcomes'] == report['outcomes'], 'Complete source or projection differs')
            require(len(report['outcomes']) == 5 and
                    [(r['model'], r['gate']) for r in report['outcomes']] == PROCEDURES, 'Five computed slots required')
            comparisons = report['historical_comparisons']
            require(len(comparisons) == 5 and {(r['model'], r['gate']) for r in comparisons} == set(PROCEDURES) and
                    all(r['passed'] is True for r in comparisons), 'Historical comparison roster differs')
            historical_checks += len(comparisons)
            reports[case_id] = report
            entry['model_census'] = dict(attempted_models=list(ARMS), completed_models=list(ARMS),
                not_run_models=[], logical_optimizer_attempts=sum(len(report['fits'][a]['records']) for a in ARMS),
                unsuccessful_logical_optimizer_attempts=sum(v for v in record['optimizer_failed_attempts_by_arm'].values()))
            for i, row in enumerate(report['outcomes']):
                gain = numeric(row['new_gain'])
                require(row['new_win'] is (gain > 0) and row['near_zero'] is (abs(gain) <= 1e-9),
                        'Strict win and near-zero definitions differ')
                derived = 0. if row['floor_return'] else numeric(row['score']['joint'])-numeric(row['new_null_score']['joint'])
                require(gain == derived, 'Gain differs from exact saved score subtraction')
                comparator = old[(case_id, row['model'], row['gate'])]
                require(close(row['historical']['fixed_floor_gain'], comparator['fixed_floor_gain']) and
                        close(row['historical']['intercept_only_gain'], comparator['intercept_only_gain']),
                        'Saved historical comparator differs')
                outcomes.append(dict(deepcopy(row), id=case_id+'|'+row['model']+'|'+row['gate'], case_id=case_id,
                    regime=report['regime'], availability='computed', historical_comparators=comparator,
                    source=dict(refs['case'], json_pointer=f'/outcomes/{i}')))
        else:
            census = unknown_census(record, report, events, review, result, dict(policy, _science=science))
            unknowns.append(census)
            entry.update(reason_code=census['reason_code'], model_census=census['model_census'])
            for model, gate in PROCEDURES:
                outcomes.append(dict.fromkeys(NULL_FIELDS) | dict(id=case_id+'|'+model+'|'+gate,
                    case_id=case_id, regime=report['regime'], model=model, gate=gate, availability='unavailable',
                    reason_code=census['reason_code'], source=refs['case'], failure_evidence=refs,
                    model_census=census['model_census'], historical_comparators=old[(case_id, model, gate)]))
        floors = report['floor_checks']
        expected_floors = {(phase, model) for phase in (('train', 'test') if disposition == 'complete' else ('train',))
                           for model in LABELS}
        require(len(floors) == len(expected_floors) and {(row['phase'], row['model']) for row in floors} == expected_floors,
                'Actually retained floor-check roster differs')
        for floor in floors:
            require(floor['tolerance'] == 1e-9 and close(floor['actual_nll'], floor['expected_nll']) and
                    close(floor['absolute_delta'], abs(floor['actual_nll']-floor['expected_nll'])), 'Floor check failed')
        floor_checks += len(floors)
        dispositions.append(entry)
    require(used_executions == set(executions), 'Extraneous or unresolved execution registry entries')
    c, u = len(reports), len(unknowns)
    require(c+u == 80 and u >= 1 and len(outcomes) == 400, 'Disposition accounting is incomplete')
    expected_counts = dict(processed_histories=80, complete_histories=c, unknown_histories=u,
                           unattempted_histories=0, computed_outcomes=5*c)
    require(index['counts'] == expected_counts, 'Index counts differ from accepted saved bytes')
    core = arithmetic()
    summary = []
    for regime in range(4, 8):
        planned = [key for key in sequence if cases[key]['regime'] == regime]
        available = [key for key in planned if key in reports]
        unavailable = [key for key in planned if key not in reports]
        # The independent helper accepts smaller groups; this exact-ID guard is mandatory.
        full = core.aggregate([reports[key] for key in planned], science) if set(available) == set(planned) else []
        for model, gate in PROCEDURES:
            stats = next((row for row in full if (row['model'], row['gate']) == (model, gate)), None)
            require(stats is None or stats['N'] == 20, 'Incomplete regime reached aggregate')
            summary.append(dict(regime=regime, model=model, gate=gate, primary=(regime, model, gate) in PRIMARY,
                planned_histories=20, computed_histories=len(available), unavailable_histories=len(unavailable),
                unavailable_case_ids=unavailable, statistics_available=stats is not None, full_regime=stats,
                unavailable_reason=None if stats else 'incomplete_original_20_history_regime'))
    counts = dict(planned_histories=80, accepted_terminal_dispositions=80, complete_histories=c,
        scientific_unknown_histories=u, pending_histories=0, unresolved_technical_failures=0,
        planned_outcomes=400, computed_outcomes=5*c, unavailable_outcomes=5*u, regime_procedure_rows=20)
    return dict(schema=REPORT_SCHEMA, reporting_accepted=False, disposition_accounting_complete=True,
        scientific_completion=False, original_publication_gate_satisfied=False,
        campaign_identity=dict(scientific_protocol_sha256=evidence.pins[SCIENCE],
            remaining_protocol_sha256=evidence.pins[POLICY], immutable_failure_reference_sha256=failure['review_sha256']),
        inputs=paths, counts=counts, case_dispositions=dispositions, outcomes=outcomes, regime_summary=summary,
        unknown_census=unknowns, historical_comparators=comparator_refs,
        complete_regimes=[r for r in range(4, 8) if all(key in reports for key in sequence if cases[key]['regime'] == r)],
        coverage=dict(verified_new_historical_comparison_rows=historical_checks,
                      verified_retained_floor_checks=floor_checks, preserved_fixed_floor_outcomes=400,
                      preserved_intercept_only_outcomes=400),
        source_pins=evidence.pins, arithmetic_source_sha256=CORE_SHA256,
        scope='Saved outputs only. Full-regime statistics require all original 20 histories; unknowns stay unavailable.'), evidence.pins


def write_report(repository, paths, output):
    output = Path(output).resolve()
    require(not output.is_relative_to(Path(repository).resolve()) and not output.exists(),
            'Fresh external report file required; publication installation is separate')
    report, _ = build(repository, paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return dict(report_sha256=sha(output), reporting_accepted=False, scientific_completion=False,
                counts=report['counts'], scientific_calls=0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    for name in ('index', 'registry', 'index-review'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    print(json.dumps(write_report(args.repository, {key:getattr(args, key) for key in
        ('index', 'registry', 'index_review')}, args.output), indent=2))
