"""Metadata and append contract for a genuine public CPU entrypoint execution."""
from pathlib import Path
import copy
from experiments.s04b_exposure_refinement import host as frozen

REPO = frozen.REPO
PROFILE = 'experiments/s04b_refined_cpu_reader/profile.json'
CHECKER = 'experiments.s04b_refined_cpu_reader_audit.check'
CHECKER_FILES = ('experiments/s04b_refined_cpu_reader_audit/__init__.py',
                 'experiments/s04b_refined_cpu_reader_audit/check.py',
                 'experiments/s04b_exposure_refinement_audit/__init__.py',
                 'experiments/s04b_exposure_refinement_audit/check.py',
                 'experiments/s04b_joint_remaining_audit/check.py',
                 'experiments/s04b_joint_audit/check.py',
                 'experiments/s04b_joint_nuisance_audit/audit.py')
read, sha, write, require, safe = frozen.read, frozen.sha, frozen.write, frozen.require, frozen.safe


def producer(review):
    # Metadata-only functions; numerical imports occur in the public child.
    from experiments.s04b_refined_cpu_reader import producer as build
    return build(review)


def source_identity():
    from experiments.s04b_refined_cpu_reader import source_identity as identity
    return identity()


def check_source_reviews(admission, policy, source_path, checker_path):
    require(sha(source_path) == admission['source_review_sha256']
            and sha(checker_path) == admission['checker_source_review_sha256'], 'Source review bytes differ')
    for path in (source_path, checker_path):
        review = read(path)
        require(review.get('passed') is True and review.get('live_agent_review') is True,
                'New producer requires independent source review')
        for name, pin in source_identity().items():
            require(review['reviewed_files_sha256'].get(name) == pin, 'Unreviewed reader source: '+name)
    require(admission['source_sha256'] == frozen.source_identity()
            and admission['scientific_source_sha256'] == frozen.driver.source_identity(),
            'Frozen compatibility map changed')
    require(admission['reader_source_review'] == dict(path=Path(source_path).resolve().relative_to(REPO).as_posix(),
                                                    sha256=sha(source_path)), 'Reader source review reference differs')
    require(admission['execution_producer'] == producer(admission['reader_source_review']),
            'Actual producer identity changed')
    for name, pin in source_identity().items():
        require(admission['reviewed_files_sha256'].get(name) == pin, 'Conductor omitted reader source: '+name)
    for name, pin in admission['reviewed_files_sha256'].items():
        require(sha(safe(REPO, name)) == pin, 'Changed admitted source: '+name)
    return {name:sha(safe(REPO,name)) for name in CHECKER_FILES}


def child_admission(admission, policy, name, slot):
    require(slot['mode'] == 'untouched', 'Public reader cannot resume a partial fit')
    result = frozen.child_admission(admission, policy, name, slot)
    result.update(source_sha256=source_identity(), reader_source_review=admission['reader_source_review'],
                  execution_producer=admission['execution_producer'])
    return result


def append_candidate(policy, admission, previous, current, out, prior_index, prior_review, projection):
    """Append actual new producer evidence, never normalize it to an old driver."""
    actual = read(current/'science/result.json')
    expected = producer(admission['reader_source_review'])
    require(actual['schema'] == 'joint_refined_cpu_case_v1' and actual.get('handled') is True
            and actual.get('disposition_valid') is True and actual['status'] == 'terminal_disposition',
            'Missing terminal public-reader disposition')
    require(actual['execution_producer'] == expected and actual['source_sha256'] == source_identity(),
            'Public execution identity differs')
    name = actual['case_id']
    require(name == policy['full_sequence'][len(previous['records'])]
            and name != policy['partial_case_id']
            and actual['numerical_attempt_id'] == admission['child_attempt_ids'][name]
            and actual['protocol_sha256'] == admission['protocol_sha256'], 'Wrong reader case/attempt')
    require(actual['passed'] is actual['scientific_passed']
            and actual['passed'] is (actual['disposition'] == 'complete'), 'Unknown relabeled passed')
    case_path = safe(current/'science', actual['report_file'])
    trace_path = safe(current/'science', actual['trace_file'])
    require(sha(case_path) == actual['report_sha256'] and sha(trace_path) == actual['trace_sha256'],
            'Reader case/trace changed')
    report = read(case_path)
    require(report['case_id'] == name and report['execution_producer'] == expected
            and report['numerical_amendment'] == actual['numerical_amendment'], 'Case producer/amendment differs')
    for filename, key in [('reuse_map.json','reuse_map_sha256'),
                          ('refinement_events.jsonl','refinement_event_log_sha256'),
                          ('execution_calls.jsonl','execution_calls_sha256')]:
        require(sha(current/'science'/filename) == actual['numerical_amendment'][key], 'Reader evidence changed')
    reuse = read(current/'science/reuse_map.json')
    require(reuse['entries'] == [] and reuse['reused_optimizer_attempts'] == 0
            and actual['reused_optimizer_attempts'] == 0, 'Fresh reader reused a fit')
    source = dict(kind='host_execution', execution_id=admission['numerical_attempt_id'],
        case_path=case_path.relative_to(out).as_posix(), case_sha256=sha(case_path),
        trace_path=trace_path.relative_to(out).as_posix(), trace_sha256=sha(trace_path),
        result_path=(current/'science/result.json').relative_to(out).as_posix(), result_sha256=sha(current/'science/result.json'),
        supervision_path=(current/'supervision/result.json').relative_to(out).as_posix(),
        supervision_sha256=sha(current/'supervision/result.json'))
    row = projection(report, actual['disposition'], source)
    row.update(numerical_amendment=actual['numerical_amendment'], refinement_census=actual['refinement_census'],
               execution_producer=expected)
    if not actual['scientific_passed']:
        row.update(unknown_origin='new_frozen_solver_cap', unknown_reason=actual['unknown_reason'],
                   model_census=actual['model_census'], terminal_solver_return=actual['terminal_solver_return'])
    supervisor = read(current/'supervision/result.json')
    attempt = dict(case_id=name, numerical_attempt_id=actual['numerical_attempt_id'],
        host_execution_id=admission['numerical_attempt_id'], seconds=actual['wall_seconds'],
        outer_seconds=supervisor['wall_seconds_including_cleanup'], result_sha256=source['result_sha256'],
        supervision_sha256=source['supervision_sha256'], actual_optimizer_attempts=actual['actual_optimizer_attempts'],
        reused_optimizer_attempts=0)
    rows, attempts = previous['records']+[row], previous['attempts']+[attempt]
    local = Path(prior_index).resolve().is_relative_to(out.resolve())
    return dict(schema='joint_exposure_refinement_index_v1', protocol_sha256=admission['protocol_sha256'],
        numerical_amendment_version=policy['version'], original_scientific_protocol_sha256=policy['original_scientific_protocol_sha256'],
        # These are explicitly the frozen compatibility maps, not the new producer identity.
        host_source_sha256=admission['source_sha256'], scientific_source_sha256=admission['scientific_source_sha256'],
        original_native=policy['original_native'], immutable_failure_reference=policy['permanent_unknown'],
        original_exposure_failure_reference=policy['failed_case'], compatible_saved_prefix=policy['base'],
        records=rows, attempts=attempts, predecessor=dict(index_sha256=sha(prior_index), review_sha256=sha(prior_review),
          archive_sha256=None if local else admission['prior_archive_sha256']),
        budget=frozen.budget(policy,attempts), counts=frozen.counts(rows), passed=False, scientific_completion=False)


def check_receipt(path, index, pins, review_pin):
    frozen.check_receipt(path,index,pins,review_pin)
    review = read(path)
    require(review['execution_producer'] == read(index)['records'][-1]['execution_producer'],
            'Automated checker omitted actual producer')
