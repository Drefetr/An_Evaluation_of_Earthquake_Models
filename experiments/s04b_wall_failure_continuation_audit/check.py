"""Independent custody/transition audit; never execute a scientific producer.

The frozen amendment auditor checks each new saved scientific case. This module
independently checks the one retained wall failure, its metadata seal, the exact
untouched suffix, and the distinct operational source and resource accounting.
"""
import argparse
import copy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
CHECKER = 'experiments/s04b_wall_failure_continuation_audit/check.py'
PROTOCOL = 'experiments/s04b_wall_failure_continuation/protocol.json'
FROZEN = 'experiments/s04b_exposure_refinement_audit/check.py'
FROZEN_SHA = '43b87881ed19970e420a4db7e5325e45302fae7d87381483e2700f07065bfb02'
FAILURE = 'S6_narrow_short_total_seed410615'
FAILURE_REVIEW_SHA = '0ea5512e94d1c9bb2e0b42fca052621fd0f1072588685d970ed92b0de506e413'
DESIGN_REVIEW = 'validation/reproductions/continuation_20261107/wall_failure_continuation_design/independent_design_review.json'
DESIGN_REVIEW_SHA = '7d51090c2b6f7e3e47605cdc2f0449cc0a7715681500d9b7f6a9b2dfb8c9c0b7'
INDEX_SCHEMA = 'joint_exposure_refinement_operational_index_v1'
CHECKER_FILES = ('experiments/s04b_wall_failure_continuation_audit/__init__.py', CHECKER,
    'experiments/s04b_exposure_refinement_audit/__init__.py', FROZEN,
    'experiments/s04b_joint_remaining_audit/check.py', 'experiments/s04b_joint_audit/check.py',
    'experiments/s04b_joint_nuisance_audit/audit.py')
REQUIRED_HOST = {
    PROTOCOL, 'experiments/s04b_wall_failure_continuation/__init__.py',
    'experiments/s04b_wall_failure_continuation/transition.py',
    'experiments/s04b_wall_failure_continuation/host.py',
    'scripts/run_joint_wall_failure_continuation.py', '.github/workflows/joint-wall-failure-continuation.yml',
    'tests/test_joint_wall_failure_continuation.py', 'tests/test_joint_wall_failure_launcher.py'}
REQUIRED_PRODUCER = set(CHECKER_FILES) | REQUIRED_HOST | {
    'scripts/supervise_research.py', 'requirements.txt', 'requirements-cpu.txt'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if sha(REPO/FROZEN) != FROZEN_SHA:
    raise ValueError('Frozen independent scientific checker changed')
_spec = importlib.util.spec_from_file_location('wall_failure_frozen_saved_audit', REPO/FROZEN)
frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(frozen)
core, old, custody = frozen.core, frozen.old, frozen.custody
require, read, safe = frozen.require, frozen.read, frozen.safe


def decimal(value):
    require(not isinstance(value, bool) and isinstance(value, (str, int, float)), 'Invalid resource scalar')
    number = Decimal(str(value))
    require(number.is_finite() and number >= 0, 'Nonfinite/negative resource scalar')
    return number


def public_ref(repo, ref):
    require(set(ref) == {'path', 'sha256'} and isinstance(ref['path'], str) and
            ref['path'].startswith('validation/') and not ref['path'].startswith('validation/authorities/'),
            'Public live evidence reference required')
    path = safe(Path(repo), ref['path'])
    require(sha(path) == ref['sha256'], 'Public evidence bytes differ: '+ref['path'])
    return path


def scientific_sources(repo, policy):
    names = set(policy['source_sha256'])
    names.update('experiments/s04b_exposure_refinement/'+name for name in
                 ('__init__.py', 'adapter.py', 'partial_fit.py', 'case_driver.py', 'host.py', 'protocol.json'))
    return {name: sha(safe(Path(repo), name)) for name in sorted(names)}


def live(value, kind=None):
    frozen.live_review(value)
    require(value.get('scientific_completion') is False, 'Live review asserts scientific completion')
    if kind is not None:
        require(value.get('review_kind') == kind, 'Wrong live review scope')


def counts(records):
    values = [row['disposition'] for row in records]
    require(all(x in ('complete', 'scientific_unknown', 'wall_time_failure') for x in values),
            'Unclassified operational record')
    complete = values.count('complete'); unknown = values.count('scientific_unknown'); failed = values.count('wall_time_failure')
    require(failed == 1 and records[55]['case_id'] == FAILURE and records[55]['disposition'] == 'wall_time_failure',
            'Only the exact retained wall failure is admitted')
    return dict(processed_histories=len(records), complete_histories=complete, unknown_histories=unknown,
                wall_time_failure_histories=failed, unattempted_histories=80-len(records), computed_outcomes=5*complete)


def require_false_result(value):
    require(value.get('disposition') == 'technical_failure' and value.get('status') == 'failed' and
            all(value.get(key) is False for key in ('passed', 'scientific_passed', 'handled', 'disposition_valid', 'scientific_completion')),
            'Raw wall failure was made successful or handled')


def load_contract(repo, review_path, review_pin):
    repo = Path(repo)
    policy, science, design = frozen.load_contract(repo)
    op = read(repo/PROTOCOL)
    require(op['schema'] == 'joint_wall_failure_continuation_protocol_v1' and
            op['version'] == 'wall_failure_continuation_v1', 'Unknown operational continuation')
    require(op['numerical_protocol'] == dict(path=frozen.PROTOCOL_PATH, sha256=sha(repo/frozen.PROTOCOL_PATH)) and
            op['scientific_protocol'] == dict(path=frozen.SCIENCE_PATH, sha256=sha(repo/frozen.SCIENCE_PATH)),
            'Original numerical/scientific protocol identity differs')
    require(op['full_sequence'] == policy['full_sequence'] and op['case_ids'] == policy['full_sequence'][56:] and
            op['case_slots'] == policy['case_slots'][12:] and op['hosts'] == policy['resources']['future_hosts'][4:] and
            op['shared_run'] == policy['shared_run'] and op['original_native'] == policy['original_native'],
            'Fixed untouched roster, clocks or native identity changed')
    require(len(op['case_ids']) == 24 and [g['host'] for g in op['hosts']] == [5, 6, 7, 8] and
            op['failure']['case_id'] == op['full_sequence'][55] == FAILURE and
            [name for group in op['hosts'] for name in group['case_ids']] == op['case_ids'], 'Wrong operational suffix')
    require(sha(repo/DESIGN_REVIEW) == DESIGN_REVIEW_SHA and
            op['design_evidence'].get(DESIGN_REVIEW) == DESIGN_REVIEW_SHA, 'Accepted continuation design changed')
    accepted_design = read(repo/DESIGN_REVIEW)
    require(accepted_design['passed'] is True, 'Continuation design was not accepted')
    for name, pin in op['design_evidence'].items():
        require(sha(safe(repo, name)) == pin, 'Retained continuation design bytes differ')
    scientific = scientific_sources(repo, policy)
    require(op['core_source_sha256'] == scientific, 'Incomplete or substituted numerical core map')
    names = op['producer_source_paths']
    require(isinstance(names, list) and names == sorted(set(names)) and REQUIRED_HOST <= set(names),
            'Actual producer paths omitted, duplicated or unsorted')
    host_sources = dict(scientific)
    for name in names:
        pin = sha(safe(repo, name))
        require(name not in host_sources or host_sources[name] == pin, 'Conflicting host/core source identity')
        host_sources[name] = pin
    require(op['checker']['module'] == 'experiments.s04b_wall_failure_continuation_audit.check' and
            op['checker']['sources'] == list(CHECKER_FILES) and
            op['checker']['test'] == 'tests/test_joint_wall_failure_continuation_audit.py', 'Actual checker graph omitted')
    checker_pins = {name: sha(safe(repo, name)) for name in CHECKER_FILES}
    require(checker_pins[CHECKER] == sha(Path(__file__)) and checker_pins[FROZEN] == FROZEN_SHA,
            'Different independent checker executed')
    require(sha(review_path) == review_pin, 'Combined source review bytes differ')
    source_review = read(review_path)
    require(source_review['passed'] is True, 'Combined source review did not pass')
    live(source_review)
    graph = source_review['reviewed_files_sha256']
    required = REQUIRED_PRODUCER | set(host_sources) | {op['checker']['test']}
    require(required <= set(graph), 'Full operational source graph is not independently reviewed')
    for name, pin in graph.items():
        require(sha(safe(repo, name)) == pin, 'Reviewed source changed: '+name)
    require(all(graph.get(name) == pin for name, pin in {**host_sources, **checker_pins}.items()),
            'Actual host/checker source map differs from review')
    require(op['base']['review']['sha256'] == FAILURE_REVIEW_SHA and op['base']['records'] == 55,
            'The singular accepted failure/prefix audit changed')
    return op, policy, science, host_sources, scientific, checker_pins, source_review


def retained_failure(repo, op, policy, scientific):
    """Resolve exact raw ZIP55 independently; never create or alter a seal."""
    base, ref = op['base'], op['failure']
    review = read(public_ref(repo, base['review']))
    public_ref(repo, base['archive'])
    live(review, 'live_agent_saved_output_review')
    require(review['passed'] is False and review['audit_passed'] is True and
            review['disposition_valid'] is False and review['scientific_passed'] is False and
            review['artifact_sha256'] == base['archive']['sha256'] and review['index_sha256'] == base['index_sha256'] and
            review['index_path'] == base['index_member'] == 'host/index.json' and
            review['execution_id'] == ref['execution_id'], 'Raw failed host was relabeled or substituted')
    accepted = review['accepted_completed_prefix']
    require(accepted['audit_passed'] is True and accepted['processed_histories'] == 55 and
            accepted['complete_histories'] == 54 and accepted['permanent_unknown_histories'] == 1 and
            accepted['computed_outcomes'] == 270 and accepted['new_complete_cases'] == op['full_sequence'][51:55] and
            accepted['prior51_records_exact'] is True and accepted['prior5_public_producer_objects_exact'] is True,
            'Only the four genuine completed prefix additions may be reused')
    require(op['failure']['failure_census'] == review['failure'] and review['source_sha256'] == scientific,
            'Failure census/scientific source map differs')
    archive = frozen.Archives(repo)
    try:
        def member(name, pin):
            require(review['archive_members_sha256'].get(name) == pin, 'Unreviewed failed archive member: '+name)
            return archive.member(base['archive']['path'], base['archive']['sha256'], name, pin)
        raw_index = frozen.document(member(base['index_member'], base['index_sha256']))
        require(raw_index['passed'] is False and raw_index['scientific_completion'] is False and
                len(raw_index['records']) == 55 and len(raw_index['attempts']) == 11 and
                [r['case_id'] for r in raw_index['records']] == op['full_sequence'][:55] and
                raw_index['counts'] == old.expected_counts(raw_index['records']) == review['counts'],
                'Raw accepted prefix changed')
        require(raw_index['records'][40]['case_id'] == frozen.UNKNOWN and
                raw_index['records'][40]['disposition'] == 'scientific_unknown' and
                raw_index['records'][40]['outcomes'] == [] and
                len([r for r in raw_index['records'] if 'execution_producer' in r]) == 5,
                'Permanent unknown or prior public-reader identities lost')
        values = {key: member(ref[key+'_member'], ref[key+'_sha256']) for key in ('case', 'trace', 'result', 'supervision')}
        report, result, supervision = (frozen.document(values[key]) for key in ('case', 'result', 'supervision'))
        trace = frozen.records(values['trace'])
        require(result['report_sha256'] == ref['case_sha256'] == review['failure']['report_sha256'] and
                result['trace_sha256'] == ref['trace_sha256'] == report['attempts_sha256'] and
                ref['result_sha256'] == review['failure']['result_sha256'], 'Failed case/trace/result custody differs')
        prefix = ref['child_prefix']
        require(prefix == 'host/children/05_'+FAILURE and
                ref['case_member'] == prefix+'/science/'+result['report_file'] and
                ref['trace_member'] == prefix+'/science/'+result['trace_file'] and
                ref['result_member'] == prefix+'/science/result.json' and
                ref['supervision_member'] == prefix+'/supervision/result.json', 'Failed child member locators differ')
        admission = frozen.document(member(prefix+'/admission.json', result['admission_sha256']))
        spec = frozen.document(member(prefix+'/supervisor_spec.json', supervision['spec_sha256']))
        member(prefix+'/supervision/execution.log', supervision['execution_log_sha256'])
        require(admission['source_sha256'] == scientific and admission['case_id'] == FAILURE and admission['case_ids'] == [FAILURE] and
                admission['wall_seconds'] == spec['wall_cap_seconds'] == 2520 and admission['scientific_seconds'] == 2490 and
                result['allocation'] == next(s for s in policy['case_slots'] if s['case_id'] == FAILURE) and
                result['protocol_sha256'] == op['numerical_protocol']['sha256'], 'Failed case admission/caps changed')
        require(spec['command'][1:4] == ['-B', '-m', 'experiments.s04b_exposure_refinement.case_driver'] and
                spec['command'].count('--case-id') == 1 and spec['command'][spec['command'].index('--case-id')+1] == FAILURE and
                '--failed-prior' not in spec['command'], 'Failed execution source or untouched mode differs')
        require(spec['rss_cap_bytes'] == 6442450944 and spec['host_headroom_bytes'] == 2147483648 and
                supervision['sampled_peak_tree_rss_bytes'] <= 6442450944 and
                supervision['minimum_sampled_host_available_bytes'] >= 2147483648,
                'Failed case resource boundary differs')
        native = member('build/attenuation.so', policy['original_native']['library_sha256'])
        build = frozen.document(member('build/build_receipt.json', policy['original_native']['build_receipt_sha256']))
        require(frozen.hash_bytes(native) == result['library_sha256'] and build['passed'] is True and
                build['source_sha256'] == policy['source_sha256']['experiments/s04b_joint_nuisance/attenuation.cpp'] and
                build['library_sha256'] == result['library_sha256'], 'Failed actual binary/build identity differs')
        failure_semantics(report, result, trace, supervision, review, policy)
        return raw_index, report, result, supervision, review
    finally:
        archive.close()


def failure_semantics(report, result, trace, supervision, review, policy):
    """Check classification/physical evidence only; C's exact live audit owns math."""
    require_false_result(result)
    require(result['case_id'] == report['case_id'] == review['failure']['case_id'] == FAILURE and
            report['passed'] is False and report['status'] == 'unknown' and report['outcomes'] == [] and
            report['error_type'] == 'TimeoutError' and report['error'] == 'Joint experiment deadline',
            'Scientific wall interruption lost or relabeled')
    require(result['error_type'] == 'ValueError' and result['error'] == 'Case optimizer records differ from trace' and
            result['scientific_clock_cap_exceeded'] is True, 'Secondary wrapper error or exhausted clock lost')
    require(set(report['fits']) == {'null', 'LI', 'LIplus_immigrant'} and
            all(report['fits'][m]['passed'] is True for m in report['fits']) and
            set(report['training_checks']) == set(report['fits']) and
            all(row['phase'] == 'train' for row in report['floor_checks']) and len(report['floor_checks']) == 3,
            'Incomplete total arm was promoted or completed prefix lost')
    require('new_null_test' not in report and 'test_checks' not in report and
            result['phase_constructions'] == [dict(start=30, end=395, returned=True)],
            'Failure cannot acquire held-out evaluations')
    ends = [row for row in trace if row.get('event') == 'attempt_end']
    starts = [row for row in trace if row.get('event') == 'attempt_start']
    require(len(starts) == len(ends) == 29 and len(trace) == 58 and
            all(trace[2*i] == starts[i] and trace[2*i+1] == ends[i] for i in range(29)),
            'Failed physical trace pairing/count differs')
    for start, end in zip(starts, ends):
        require(all(start[key] == end[key] for key in ('model', 'start_index', 'method', 'initial_parameters')),
                'Failed physical trace pairing differs')
    require(sum(row['status'] == 'returned' for row in ends) == 27 and
            sum(row['status'] == 'exception' for row in ends) == 2 and
            result['actual_optimizer_attempts'] == 29 and result['reused_optimizer_attempts'] == 0,
            'Partial physical calls or failures were fabricated')
    require(ends[-1] == review['failure']['interrupted_record'] and ends[-1]['error_type'] == 'TimeoutError' and
            (ends[-1]['model'], ends[-1]['start_index'], ends[-1]['method']) == ('LIplus_inclusive', 3, 'L-BFGS-B'),
            'Wrong interrupted start or finite-cap substitution')
    total = [row for row in ends if row['model'] == 'LIplus_inclusive']
    require([row['start_index'] for row in total] == [0, 1, 2, 3] and
            all(row['status'] == 'returned' and row['success'] is True for row in total[:3]),
            'Unrun total suffix invented')
    require(review['failure']['held_out_calls'] == review['failure']['new_outcomes_available'] == 0 and
            review['failure']['unavailable_comparisons'] == 5 and review['failure']['reuse_count'] == 0,
            'Failure audit does not preserve all unavailable comparisons')
    require(result['source_sha256'] == review['source_sha256'] and
            result['runtime']['essential'] == policy['original_native']['runtime_essential'] and
            all(result[k] == policy['original_native'][k] for k in ('library_sha256', 'build_receipt_sha256')),
            'Failed scientific source/native/runtime identity differs')
    require(supervision['status'] == 'failed' and supervision['returncode'] == 1 and supervision['launched'] is True and
            supervision['stop_reason'] is None and supervision['survivors_after_cleanup'] == [] and
            supervision['cleanup_errors'] == [], 'Failure was an external stop or has surviving work')
    require(decimal(result['wall_seconds']) > Decimal(2490) and
            decimal(result['wall_seconds']) <= decimal(supervision['execution_wall_seconds']) <=
            decimal(supervision['wall_seconds_including_cleanup']) <= Decimal(2520),
            'Failed deadline/outer clocks differ; never clamp to a successful cap')
    require(decimal(result['wall_seconds']) == decimal(review['resource']['failed_scientific_seconds_not_indexed']) and
            decimal(supervision['wall_seconds_including_cleanup']) == decimal(review['resource']['failed_child_outer_seconds_not_indexed']),
            'Failed physical cost differs from live audit')


def failure_projection(op, report, result, supervision, review):
    ref = op['failure']
    source = dict(kind='host_execution', execution_id=ref['execution_id'])
    for name in ('case', 'trace', 'result', 'supervision'):
        require(ref[name+'_member'].startswith('host/'), 'Failed member is not host-relative')
        source[name+'_path'] = ref[name+'_member'][5:]
        source[name+'_sha256'] = ref[name+'_sha256']
    row = {key: copy.deepcopy(report[key]) for key in
        ('case_id', 'regime', 'seed', 'input_sha256', 'n_train', 'n_test', 'stratum', 'thinning',
         'fixed_spatial_mark_law', 'historical_comparisons')}
    row.update(disposition='wall_time_failure', scientific_passed=False, outcomes=[], source=source,
        reason_code='scientific_wall_limit', failure_review=op['base']['review'], raw_case_status=report['status'],
        raw_result_disposition=result['disposition'], primary_error=dict(type=report['error_type'], message=report['error']),
        secondary_error=dict(type=result['error_type'], message=result['error']), allocation=result['allocation'],
        failure_census=review['failure'], numerical_amendment=result['numerical_amendment'])
    attempt = dict(case_id=FAILURE, numerical_attempt_id=result['numerical_attempt_id'],
        host_execution_id=ref['execution_id'], seconds=result['wall_seconds'],
        outer_seconds=supervision['wall_seconds_including_cleanup'], result_sha256=ref['result_sha256'],
        supervision_sha256=ref['supervision_sha256'], actual_optimizer_attempts=result['actual_optimizer_attempts'],
        reused_optimizer_attempts=result['reused_optimizer_attempts'])
    return row, attempt


def equal(actual, expected, message):
    """Type-sensitive JSON equality, including null/false/zero distinctions."""
    require(json.dumps(actual, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False), message)


def accounting_policy(op, review, policy):
    resource = review['resource']; actual = op['accounting']
    baseline = decimal(resource['known_accounted_after_whole_host04_seconds'])
    consumed = decimal(resource['prior_workflow_overheads_outside_index_seconds']) + decimal(resource['whole_workflow_overhead_beyond_all_child_outer_seconds'])
    reserve = decimal(policy['resources']['future_host_overhead_seconds']) - consumed
    require(reserve >= 0 and actual['historical_unmeasured_setup_caveat'] is True and
            decimal(actual['sealed_known_seconds']) == baseline and
            decimal(actual['unconsumed_host_overhead_reserve_seconds']) == reserve and
            actual['global_cap_seconds'] == 115200 and actual['global_finalization_reserve_seconds'] == 1800,
            'Sealed budget basis/reservation was changed')
    for target, source in [('failure_scientific_seconds', 'failed_scientific_seconds_not_indexed'),
                           ('failure_outer_seconds', 'failed_child_outer_seconds_not_indexed'),
                           ('host04_overhead_seconds', 'whole_workflow_overhead_beyond_all_child_outer_seconds')]:
        require(decimal(actual[target]) == decimal(resource[source]), 'Sealed historical charge differs')
    require(decimal(resource['workflow_logged_seconds']) - decimal(resource['completed_new_indexed_outer_seconds']) ==
            decimal(resource['failed_child_outer_seconds_not_indexed']) + decimal(resource['whole_workflow_overhead_beyond_all_child_outer_seconds']) ==
            decimal(resource['charge_missing_from_completed_prefix_index_seconds']), 'Historical host cost double counted or omitted')


def budget(op, attempts, overheads):
    require(len(attempts) >= 12 and [r['case_id'] for r in attempts] == op['full_sequence'][44:44+len(attempts)] and
            len({r['numerical_attempt_id'] for r in attempts}) == len(attempts), 'Physical attempts skipped/repeated')
    suffix = attempts[12:]
    require([r['case_id'] for r in suffix] == op['case_ids'][:len(suffix)], 'Untouched suffix changed')
    science = Decimal(0); outer = Decimal(0)
    for row, slot in zip(suffix, op['case_slots']):
        elapsed, cleanup = decimal(row['seconds']), decimal(row['outer_seconds'])
        require(elapsed <= slot['scientific_seconds'] and elapsed <= cleanup <= slot['wall_seconds'] and
                type(row['actual_optimizer_attempts']) is int and row['actual_optimizer_attempts'] > 0 and
                type(row['reused_optimizer_attempts']) is int and row['reused_optimizer_attempts'] == 0,
                'Future child cap/reuse allowance changed')
        science += elapsed; outer += cleanup
    ids = [r['execution_id'] for r in overheads]
    require(len(ids) == len(set(ids)) and op['failure']['execution_id'] not in ids, 'Audited overhead repeated or charged host04 again')
    overhead = Decimal(0)
    for row in overheads:
        require(set(row) == {'execution_id', 'seconds', 'review', 'archive'} and decimal(row['seconds']) <= 1800,
                'Unexpected overhead identity/envelope')
        overhead += decimal(row['seconds'])
    basis = op['accounting']; baseline = decimal(basis['sealed_known_seconds'])
    reserve = decimal(basis['unconsumed_host_overhead_reserve_seconds']) - overhead
    remaining = sum(slot['wall_seconds'] for slot in op['case_slots'][len(suffix):])
    accounted = baseline + outer + overhead
    upper = accounted + remaining + reserve + basis['global_finalization_reserve_seconds']
    require(reserve >= 0 and upper <= basis['global_cap_seconds'], 'Shared resource allowance exceeded')
    return dict(sealed_known_seconds=str(baseline), future_scientific_seconds=str(science), future_outer_seconds=str(outer),
        audited_future_host_overhead_seconds=str(overhead), accounted_seconds=str(accounted),
        remaining_case_slots_seconds=remaining, unconsumed_host_overhead_reserve_seconds=str(reserve),
        global_finalization_reserve_seconds=basis['global_finalization_reserve_seconds'], upper_bound_seconds=str(upper),
        remaining_headroom_seconds=str(Decimal(basis['global_cap_seconds'])-upper), historical_unmeasured_setup_caveat=True)


def operational_ref(repo):
    return dict(path=PROTOCOL, sha256=sha(Path(repo)/PROTOCOL))


def sealed_expected(repo, op, raw, report, result, supervision, review, host_sources):
    row, attempt = failure_projection(op, report, result, supervision, review)
    value = copy.deepcopy(raw)
    value.update(schema=INDEX_SCHEMA, operational_continuation=operational_ref(repo), host_source_sha256=host_sources,
        records=raw['records']+[row], attempts=raw['attempts']+[attempt], audited_host_overheads=[],
        passed=False, scientific_completion=False,
        predecessor=dict(kind='audited_wall_failure_transition', raw_archive=op['base']['archive'], raw_review=op['base']['review'],
            raw_index_member=op['base']['index_member'], raw_index_sha256=op['base']['index_sha256']))
    value['counts'] = counts(value['records'])
    value['budget'] = budget(op, value['attempts'], [])
    return value


def inspect_overhead(repo, row, op, host_sources, preceding_group):
    audit = read(public_ref(repo, row['review']))
    public_ref(repo, row['archive'])
    live(audit, 'live_agent_saved_output_review')
    require(audit['passed'] is True and audit['audit_passed'] is True and audit['disposition_valid'] is True and
            audit['execution_id'] == row['execution_id'] and audit['artifact_sha256'] == row['archive']['sha256'] and
            audit['operational_continuation'] == operational_ref(repo) and audit['host_source_sha256'] == host_sources and
            audit['source_sha256'] == op['core_source_sha256'] and audit['index_path'] == 'host/index.json',
            'Prior overhead lacks the genuine operational host audit')
    require(decimal(row['seconds']) == decimal(audit['resource']['whole_workflow_overhead_beyond_all_child_outer_seconds']),
            'Overhead differs from the independently audited workflow charge')
    archive = frozen.Archives(repo)
    try:
        previous = frozen.document(archive.member(row['archive']['path'], row['archive']['sha256'], 'host/index.json', audit['index_sha256']))
    finally:
        archive.close()
    expected_len = 56 + sum(len(g['case_ids']) for g in op['hosts'] if g['host'] <= preceding_group['host'])
    require(len(previous['records']) == expected_len and
            [r['case_id'] for r in previous['records']] == op['full_sequence'][:expected_len] and
            [r['case_id'] for r in previous['records'][-len(preceding_group['case_ids']):]] == preceding_group['case_ids'] and
            all(r['source']['execution_id'] == row['execution_id'] for r in previous['records'][-len(preceding_group['case_ids']):]),
            'Audited overhead belongs to another group or unfinished host')
    equal(previous['counts'], audit['counts'], 'Prior workflow census differs')
    return audit


def inspect_sealed_predecessor(repo, refs, index, review, expected, op):
    require(set(refs) == {'index', 'review', 'raw_archive', 'raw_review', 'raw_index_member', 'raw_index_sha256'},
            'Separate sealed/raw predecessor references required')
    require(refs['raw_archive'] == op['base']['archive'] and refs['raw_review'] == op['base']['review'] and
            refs['raw_index_member'] == op['base']['index_member'] and refs['raw_index_sha256'] == op['base']['index_sha256'],
            'Raw ZIP55 custody differs from the seal')
    for key in ('index', 'review', 'raw_archive', 'raw_review'):
        public_ref(repo, refs[key])
    equal(read(safe(Path(repo), refs['index']['path'])), index, 'Public sealed index differs from supplied predecessor')
    equal(read(safe(Path(repo), refs['review']['path'])), review, 'Public transition review differs')
    equal(index, expected, 'The seal is not the exact raw55 plus one audited failure')
    live(review, 'live_operational_failure_transition_review')
    require('execution_id' not in review and review['passed'] is True and review['audit_passed'] is True and
            review['failure_accounting_valid'] is True and review['scientific_execution_passed'] is False and
            review['index_sha256'] == refs['index']['sha256'] and review['operational_continuation'] == operational_ref(repo) and
            review['raw_archive'] == op['base']['archive'] and review['raw_review'] == op['base']['review'] and
            review['raw_index_sha256'] == op['base']['index_sha256'],
            'Seal review impersonates an execution or does not bind both actual artifacts')


def inspect_index_prefix(index, expected, op, host_sources):
    require(index['schema'] == INDEX_SCHEMA and index['passed'] is False and index['scientific_completion'] is False and
            index['operational_continuation'] == expected['operational_continuation'], 'Wrong operational index/success scope')
    require(set(index) == set(expected), 'Operational index fields changed')
    for name in ('protocol_sha256', 'numerical_amendment_version', 'original_scientific_protocol_sha256',
                 'scientific_source_sha256', 'original_native', 'immutable_failure_reference',
                 'original_exposure_failure_reference', 'compatible_saved_prefix'):
        equal(index[name], expected[name], 'Historical numerical/source identity changed: '+name)
    equal(index['host_source_sha256'], host_sources, 'Actual expanded host source map is missing')
    equal(index['records'][:56], expected['records'], 'Old prefix, public producer or wall failure changed')
    equal(index['attempts'][:12], expected['attempts'], 'Old physical work/failed charge changed')
    require([r['case_id'] for r in index['records']] == op['full_sequence'][:len(index['records'])] and
            56 <= len(index['records']) <= 80 and len(index['records']) == 44+len(index['attempts']),
            'Exact operational roster changed')
    equal(index['counts'], counts(index['records']), 'Operational counts differ')
    equal(index['budget'], budget(op, index['attempts'], index['audited_host_overheads']), 'Operational accounting differs')


def inspect_transition(repo, current, index, prior, prior_review, prior_path, prior_review_path,
                       expected, op, policy, host_sources, checker_pins, review_pin, result, report):
    current = Path(current); host = current.parent.parent
    grant = read(host.parent/'admission.json')
    number = grant['batch_id']
    require(type(number) is int and 5 <= number <= 8 and grant['mode'] == 'exposure_refinement_host_batch' and
            grant['operational_mode'] == 'wall_failure_continuation' and
            grant['operational_continuation'] == operational_ref(repo), 'Unadmitted host or hidden operational implementation')
    group = op['hosts'][number-5]; name = result['case_id']
    require(name in group['case_ids'] and grant['case_ids'] == group['case_ids'] and
            set(grant['child_attempt_ids']) == set(group['case_ids']) and
            len(set(grant['child_attempt_ids'].values())) == len(group['case_ids']), 'Fixed group/attempt assignment changed')
    position = group['case_ids'].index(name)
    boundary = 56 + sum(len(g['case_ids']) for g in op['hosts'][:number-5])
    require(len(prior['records']) == boundary+position and result['numerical_attempt_id'] == grant['child_attempt_ids'][name],
            'Wrong fixed group boundary or repeated case')
    require(grant['source_sha256'] == host_sources and grant['scientific_source_sha256'] == op['core_source_sha256'] and
            grant['protocol_sha256'] == op['numerical_protocol']['sha256'] and
            grant['shared_run'] == op['shared_run'] and grant['expires_utc'] == op['shared_run']['expires_utc'] and
            grant['source_review_sha256'] == grant['checker_source_review_sha256'] == review_pin,
            'Admitted source, review or shared allowance differs')
    inspect_index_prefix(prior, expected, op, host_sources)
    inspect_index_prefix(index, expected, op, host_sources)
    equal(index['records'][:-1], prior['records'], 'Accepted predecessor records changed')
    equal(index['attempts'][:-1], prior['attempts'], 'Accepted predecessor physical work changed')
    require(index['predecessor']['index_sha256'] == sha(prior_path) and
            index['predecessor']['review_sha256'] == sha(prior_review_path), 'Actual predecessor bytes differ')
    overheads = copy.deepcopy(prior['audited_host_overheads'])
    if position == 0:
        require(grant['prior_index_sha256'] == sha(prior_path) and grant['prior_review_sha256'] == sha(prior_review_path),
                'External prior index/review was substituted')
        if number == 5:
            require(grant.get('prior_host_overhead') is None and grant['prior_archive_sha256'] == op['base']['archive']['sha256'],
                    'Host04 was charged again or raw archive changed')
            refs = grant['sealed_predecessor']
            inspect_sealed_predecessor(repo, refs, prior, prior_review, expected, op)
            equal(index['predecessor'], dict(kind='sealed_failure_transition', index_sha256=sha(prior_path),
                review_sha256=sha(prior_review_path), archive_sha256=None, index=refs['index'], review=refs['review'],
                raw_failure_archive=op['base']['archive']), 'Seal falsely attributed to a raw archive member')
        else:
            require(grant.get('sealed_predecessor') is None, 'Later host reused the seal instead of actual prior output')
            live(prior_review, 'live_agent_saved_output_review')
            require(prior_review['passed'] is True and prior_review['audit_passed'] is True and prior_review['disposition_valid'] is True and
                    prior_review['index_sha256'] == sha(prior_path) and prior_review['artifact_sha256'] == grant['prior_archive_sha256'],
                    'Missing genuine live prior-host output acceptance')
            row = grant['prior_host_overhead']
            require(row['review']['sha256'] == sha(prior_review_path) and row['archive']['sha256'] == grant['prior_archive_sha256'],
                    'Overhead not bound to actual prior host')
            equal(inspect_overhead(repo, row, op, host_sources, op['hosts'][number-6]), prior_review, 'Overhead review substituted')
            overheads.append(row)
            equal(index['predecessor'], dict(index_sha256=sha(prior_path), review_sha256=sha(prior_review_path),
                archive_sha256=grant['prior_archive_sha256']), 'Later actual archive custody differs')
    else:
        require(prior_review['review_kind'] == 'automated_saved_output_check' and prior_review['passed'] is True and
                prior_review['audit_passed'] is True and prior_review['disposition_valid'] is True and
                prior_review['live_agent_review'] is False and prior_review['live_agent_review_performed'] is False and
                prior_review['final_batch_agent_review_required'] is True and prior_review['scientific_completion'] is False and
                prior_review['checker_sources_sha256'] == checker_pins and prior_review['checker_source_review_sha256'] == review_pin and
                prior_review['index_sha256'] == sha(prior_path) and prior_review['operational_continuation'] == operational_ref(repo) and
                prior_review['case_id'] == group['case_ids'][position-1] and
                prior['records'][-1]['source']['execution_id'] == grant['numerical_attempt_id'],
                'Within-host check is missing, changed or falsely called live')
        equal(index['predecessor'], dict(index_sha256=sha(prior_path), review_sha256=sha(prior_review_path), archive_sha256=None),
              'Within-host predecessor falsely attributed to an archive')
    equal(index['audited_host_overheads'], overheads, 'Overhead charge omitted, duplicated or injected')
    require(len(overheads) == number-5, 'Overhead boundary roster differs')
    for row, previous_group in zip(overheads, op['hosts']):
        inspect_overhead(repo, row, op, host_sources, previous_group)
    source = index['records'][-1]['source']
    require(source['kind'] == 'host_execution' and source['execution_id'] == grant['numerical_attempt_id'], 'New physical execution identity differs')
    paths = dict(case_path=current/'science'/result['report_file'], trace_path=current/'science'/result['trace_file'],
                 result_path=current/'science/result.json', supervision_path=current/'supervision/result.json')
    for key, path in paths.items():
        require(source[key] == path.relative_to(host).as_posix() and source[key.replace('_path', '_sha256')] == sha(path),
                'New actual case source locator differs')
    projected = old.projection(report, result['disposition'], source)
    projected.update(numerical_amendment=result['numerical_amendment'], refinement_census=result['refinement_census'])
    if result['disposition'] == 'scientific_unknown':
        projected.update(unknown_origin='new_frozen_solver_cap', unknown_reason=result['unknown_reason'],
                         model_census=result['model_census'], terminal_solver_return=result['terminal_solver_return'])
    equal(index['records'][-1], projected, 'New compact record differs from audited saved case')
    supervisor = read(current/'supervision/result.json')
    attempt = dict(case_id=name, numerical_attempt_id=result['numerical_attempt_id'], host_execution_id=source['execution_id'],
        seconds=result['wall_seconds'], outer_seconds=supervisor['wall_seconds_including_cleanup'],
        result_sha256=source['result_sha256'], supervision_sha256=source['supervision_sha256'],
        actual_optimizer_attempts=result['actual_optimizer_attempts'], reused_optimizer_attempts=result['reused_optimizer_attempts'])
    equal(index['attempts'][-1], attempt, 'New physical-call/cost record differs')
    return index['budget']


def disposition_census(records, sequence):
    """Counts and eligibility only; no recomputed means or substituted scores."""
    by_id = {r['case_id']: r for r in records}
    output = []
    for regime in range(4, 8):
        planned = [name for name in sequence if name.startswith('S'+str(regime)+'_')]
        require(len(planned) == 20, 'Original regime denominator changed')
        complete = sum(by_id.get(name, {}).get('disposition') == 'complete' for name in planned)
        unknown = sum(by_id.get(name, {}).get('disposition') == 'scientific_unknown' for name in planned)
        failures = sum(by_id.get(name, {}).get('disposition') == 'wall_time_failure' for name in planned)
        for model, gate in core.OUTCOMES:
            output.append(dict(regime=regime, model=model, gate=gate, planned_histories=20, complete_histories=complete,
                optimizer_unknown_histories=unknown, wall_time_failure_histories=failures, not_run_histories=20-complete-unknown-failures,
                full_regime_eligible=complete == 20, score_summary_recomputed=False))
    return output


def audit_saved(args):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    repo, current = Path(args.repo).resolve(), Path(args.current).resolve()
    op, policy, science, host_sources, scientific, checker_pins, source_review = load_contract(
        repo, Path(args.checker_source_review), args.checker_source_review_sha256)
    config = read(args.config)
    require(sha(args.config) == op['shared_run']['config_sha256'], 'Original shared config changed')
    raw, failed_report, failed_result, failed_supervisor, failure_review = retained_failure(repo, op, policy, scientific)
    accounting_policy(op, failure_review, policy)
    expected = sealed_expected(repo, op, raw, failed_report, failed_result, failed_supervisor, failure_review, host_sources)
    candidate = read(current/'science/result.json')
    require(candidate['case_id'] in op['case_ids'] and candidate['case_id'] not in (FAILURE, frozen.UNKNOWN) and
            candidate['source_sha256'] == scientific, 'A retained case was retried or scientific producer was disguised')
    conductor = read(current/'conductor_review.json')
    equal(conductor['reviewed_files_sha256'], source_review['reviewed_files_sha256'], 'Conductor omitted the actual reviewed graph')
    result, report, unknown, work = frozen.inspect_current(current, repo, policy, science, config, args.commit, checker_pins, None)
    prior_path, prior_review_path = Path(args.prior).resolve(), Path(args.prior_review).resolve()
    prior, prior_review = read(prior_path), read(prior_review_path)
    index = read(current/'index.json')
    actual_budget = inspect_transition(repo, current, index, prior, prior_review, prior_path, prior_review_path,
        expected, op, policy, host_sources, checker_pins, args.checker_source_review_sha256, result, report)
    return dict(schema='joint_wall_failure_continuation_saved_output_check_v1', passed=True, audit_passed=True,
        disposition_valid=True, disposition=result['disposition'], scientific_passed=result['scientific_passed'],
        scientific_completion=False, original_full_success_gate_passed=False, original_publication_gate_satisfied=False,
        review_kind='automated_saved_output_check', live_agent_review=False, live_agent_review_performed=False,
        final_batch_agent_review_required=True, operational_continuation=operational_ref(repo),
        index_sha256=sha(current/'index.json'), source_sha256=scientific, host_source_sha256=host_sources,
        checker_sources_sha256=checker_pins, checker_source_review_sha256=args.checker_source_review_sha256,
        prior_index_sha256=sha(prior_path), prior_review_sha256=sha(prior_review_path), case_id=result['case_id'],
        report_sha256=result['report_sha256'], trace_sha256=result['trace_sha256'], counts=index['counts'], budget=actual_budget,
        unknown_census=unknown, failure_census=failure_review['failure'], refinement_and_reuse_census=work,
        independent_disposition_census=disposition_census(index['records'], op['full_sequence']),
        all_histories_attempted=len(index['records']) == 80, numerical_calls=0, optimizer_calls=0,
        scope='Saved-case mathematics and operational custody only; wall failure remains separate, with no score-summary recomputation.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'current', 'prior', 'prior-review', 'config', 'output', 'checker-source-review'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('commit', 'checker-source-review-sha256'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit_saved(args)
    except Exception as exc:
        result = dict(passed=False, audit_passed=False, disposition_valid=False, scientific_passed=False,
            scientific_completion=False, error_type=type(exc).__name__, error=str(exc), numerical_calls=0, optimizer_calls=0)
    require(not args.output.exists(), 'Audit output already exists')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    return 0 if result['audit_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
