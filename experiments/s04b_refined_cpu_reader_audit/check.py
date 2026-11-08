"""Audit actual public-reader output without importing its numerical producer.

This entrypoint checks the separately identified reader and append interface.
The frozen independent amendment auditor supplies saved mathematical checks;
no old command, result schema or source identity is manufactured for it.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
CHECKER = 'experiments/s04b_refined_cpu_reader_audit/check.py'
PROFILE = 'experiments/s04b_refined_cpu_reader/profile.json'
ENTRYPOINT = 'scripts/fit_joint_refined_cpu.py'
FROZEN = 'experiments/s04b_exposure_refinement_audit/check.py'
FROZEN_SHA = '43b87881ed19970e420a4db7e5325e45302fae7d87381483e2700f07065bfb02'
CHECKER_FILES = ('experiments/s04b_refined_cpu_reader_audit/__init__.py', CHECKER,
    'experiments/s04b_exposure_refinement_audit/__init__.py', FROZEN,
    'experiments/s04b_joint_remaining_audit/check.py', 'experiments/s04b_joint_audit/check.py',
    'experiments/s04b_joint_nuisance_audit/audit.py')
REQUIRED_PRODUCER = set(CHECKER_FILES) | {
    PROFILE, ENTRYPOINT, 'experiments/s04b_refined_cpu_reader/__init__.py',
    'experiments/s04b_refined_cpu_reader/reader.py', 'experiments/s04b_refined_cpu_bridge/__init__.py',
    'experiments/s04b_refined_cpu_bridge/contract.py', 'experiments/s04b_refined_cpu_bridge/host.py',
    'scripts/run_joint_refined_cpu_host.py', 'scripts/run_joint_exposure_refinement.py', 'scripts/supervise_research.py',
    '.github/workflows/joint-refined-cpu.yml', 'requirements.txt', 'requirements-cpu.txt'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


if sha(REPO/FROZEN) != FROZEN_SHA:
    raise ValueError('Frozen independent amendment checker changed')
_spec = importlib.util.spec_from_file_location('public_reader_frozen_saved_audit', REPO/FROZEN)
frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(frozen)
core, old, custody = frozen.core, frozen.old, frozen.custody
require, read, safe = frozen.require, frozen.read, frozen.safe
ARMS = frozen.ARMS


def expected_core(repo, policy):
    """Reconstruct the unchanged dependency graph without importing a producer."""
    names = set(policy['source_sha256'])
    names.update('experiments/s04b_exposure_refinement/'+name for name in
        ('__init__.py', 'adapter.py', 'case_driver.py', 'host.py', 'partial_fit.py', 'protocol.json'))
    return {name: sha(safe(repo, name)) for name in sorted(names)}


def source_union(core_sources, producer_sources):
    overlap = set(core_sources).intersection(producer_sources)
    require(all(core_sources[name] == producer_sources[name] for name in overlap),
            'Producer source conflicts with a frozen core identity')
    return dict(core_sources, **producer_sources)


def inspect_producer(value, core_sources, producer_sources, profile_pin, review_reference):
    expected = dict(schema='joint_refined_cpu_producer_v1', kind='public_refined_cpu',
        entrypoint=ENTRYPOINT, operation='fit',
        profile_reference=dict(path=PROFILE, sha256=profile_pin),
        core_source_sha256=core_sources, producer_source_sha256=producer_sources,
        execution_source_sha256=source_union(core_sources, producer_sources),
        source_review=review_reference)
    require(value == expected, 'Actual reader producer/profile/source identity differs')
    return expected


def inspect_command(spec, current, case_id, slot, result, admission):
    argv = spec['command']
    require(isinstance(argv, list) and len(argv) >= 4 and all(isinstance(x, str) for x in argv) and
            argv[1] == '-B' and argv[3] == 'fit', 'Actual public reader command required')
    cwd = PurePosixPath(spec['cwd'])
    require(cwd.is_absolute() and '..' not in cwd.parts and
            argv[2] == str(cwd/ENTRYPOINT), 'Actual absolute public entrypoint differs from recorded checkout')
    tail = argv[4:]
    require(len(tail) % 2 == 0, 'Incomplete public reader arguments')
    keys = tail[::2]
    require(len(keys) == len(set(keys)) and set(keys) ==
            {'--case-id', '--output', '--execution-record', '--wall-seconds', '--rss-mib', '--headroom-mib'},
            'Unexpected, duplicate or missing public reader argument')
    arguments = dict(zip(keys, tail[1::2]))
    require(arguments['--case-id'] == case_id and
            float(arguments['--wall-seconds']) == slot['wall_seconds'] and
            float(arguments['--rss-mib']) == 6144 and float(arguments['--headroom-mib']) == 2048,
            'Public reader case/resource arguments differ')
    remote = arguments['--output']
    require(old.recorded_path(remote, remote, current) == (Path(current)/'science').resolve() and
            old.recorded_path(arguments['--execution-record'], remote, current) == (Path(current)/'admission.json').resolve(),
            'Actual reader output or author execution record differs')
    request_path = Path(current)/'science/reader_request.json'
    require(sha(request_path) == result['reader_request_sha256'], 'Reader request bytes changed')
    request = read(request_path)
    require(request['schema'] == 'joint_refined_cpu_request_v1' and request['mode'] == 'author_envelope' and
            request['actual_command'] == result['actual_command'] == argv and request['case_id'] == case_id and
            request['output'] == remote and request['execution_record'] == arguments['--execution-record'] and
            request['execution_record_sha256'] == sha(Path(current)/'admission.json') and
            request['source_sha256'] == result['source_sha256'] and
            request['execution_producer'] == result['execution_producer'], 'Actual reader request/command/producer differs')
    require(request['wall_seconds'] == slot['wall_seconds'] and request['scientific_seconds'] == slot['scientific_seconds'] and
            request['rss_cap_bytes'] == admission['sampled_process_tree_rss_cap_bytes'] and
            request['headroom_bytes'] == admission['minimum_host_free_bytes'] and
            request['threads'] == 2 and request['workers'] == 1 and
            request['live_agent_review'] is False and request['scientific_completion'] is False,
            'Reader request resource or review scope differs')
    return arguments


def load_contract(repo, review_path, review_pin):
    policy, science, design = frozen.load_contract(repo)
    profile = read(Path(repo)/PROFILE)
    require(profile['schema'] == 'joint_refined_cpu_reader_profile_v1' and
            profile['version'] == 'public_refined_cpu_v1' and profile['entrypoint'] == ENTRYPOINT and
            profile['operation'] == 'fit' and profile['numerical_version'] == policy['version'],
            'Unknown public reader profile')
    require(profile['amendment_protocol'] == dict(path=frozen.PROTOCOL_PATH, sha256=sha(Path(repo)/frozen.PROTOCOL_PATH)) and
            profile['scientific_protocol'] == dict(path=frozen.SCIENCE_PATH, sha256=sha(Path(repo)/frozen.SCIENCE_PATH)) and
            profile['case_ids'] == policy['full_sequence'], 'Reader changed original numerical protocol or roster')
    core_sources = expected_core(repo, policy)
    require(profile['core_source_sha256'] == core_sources, 'Reader changed frozen compatibility source graph')
    paths = profile['producer_source_paths']
    require(isinstance(paths, list) and paths == sorted(set(paths)) and REQUIRED_PRODUCER <= set(paths),
            'Reader producer graph is incomplete or duplicated')
    producer_sources = {name: sha(safe(repo, name)) for name in paths}
    require(sha(review_path) == review_pin, 'Reader source review bytes changed')
    review = read(review_path)
    require(review['passed'] is True, 'Reader source review did not pass')
    frozen.live_review(review)
    full = source_union(core_sources, producer_sources)
    require(all(review['reviewed_files_sha256'].get(name) == pin for name, pin in full.items()),
            'Reader source graph lacks exact independent review')
    pins = {name: sha(safe(repo, name)) for name in CHECKER_FILES}
    require(pins[CHECKER] == sha(HERE) and pins[FROZEN] == FROZEN_SHA, 'Different audit implementation executed')
    require(all(review['reviewed_files_sha256'].get(name) == pin for name, pin in pins.items()),
            'Independent audit dependency is unreviewed')
    reference = dict(path=Path(review_path).resolve().relative_to(Path(repo).resolve()).as_posix(), sha256=review_pin)
    require(reference['path'].startswith('validation/') and not reference['path'].startswith('validation/authorities/'),
            'Public live source review required')
    producer = inspect_producer(dict(schema='joint_refined_cpu_producer_v1', kind='public_refined_cpu',
        entrypoint=ENTRYPOINT, operation='fit', profile_reference=dict(path=PROFILE, sha256=sha(Path(repo)/PROFILE)),
        core_source_sha256=core_sources, producer_source_sha256=producer_sources,
        execution_source_sha256=full, source_review=reference), core_sources, producer_sources,
        sha(Path(repo)/PROFILE), reference)
    return policy, science, design, profile, producer, review, pins


def inspect_native(current, repo, result, profile, policy):
    root = Path(current)/'science'
    expected = dict(profile['bundled_native'], library_path='native/attenuation.so',
                    build_receipt_path='native/build_receipt.json')
    original = policy['permanent_unknown']
    require(expected['archive_reference'] == dict(path=original['archive'], sha256=original['archive_sha256']) and
            expected['review_reference'] == dict(path=original['review'], sha256=original['review_sha256']) and
            expected['library_member'] == original['library_member'] and
            expected['build_receipt_member'] == original['build_receipt_member'], 'Original bundled native source changed')
    require(result['bundled_native'] == expected and
            sha(root/'bundled_native.json') == result['bundled_native_sha256'] and
            read(root/'bundled_native.json') == expected, 'Bundled native extraction receipt differs')
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(expected[key] == result[key] == policy['original_native'][key], 'Original native identity changed')
    reference = expected['review_reference']
    review_path = safe(repo, reference['path'])
    require(sha(review_path) == reference['sha256'], 'Bundled native review bytes changed')
    review = read(review_path)
    require(review['audit_passed'] is True and review['live_agent_review'] is True and
            review['archive_sha256'] == expected['archive_reference']['sha256'], 'Bundled native archive lacks its genuine audit')
    saved = frozen.Archives(repo)
    try:
        archive = expected['archive_reference']
        for prefix in ('library', 'build_receipt'):
            raw = saved.member(archive['path'], archive['sha256'], expected[prefix+'_member'], expected[prefix+'_sha256'])
            local = safe(root, expected[prefix+'_path'])
            require(local.read_bytes() == raw, 'Extracted native bytes differ from public archive')
    finally:
        saved.close()
    build = read(safe(root, expected['build_receipt_path']))
    require(build['passed'] is True and build['library_sha256'] == result['library_sha256'] and
            build['source_sha256'] == policy['source_sha256']['experiments/s04b_joint_nuisance/attenuation.cpp'],
            'Bundled build provenance differs')


def inspect_current(current, repo, policy, science, profile, producer, source_review, checker_pins, config, commit, partial):
    current = Path(current)
    result, admission, conductor = (read(current/name) for name in
        ('science/result.json', 'admission.json', 'conductor_review.json'))
    require(result['schema'] == 'joint_refined_cpu_case_v1' and result['handled'] is True and
            result['disposition_valid'] is True and result['status'] == 'terminal_disposition' and
            result['scientific_completion'] is False and result['execution_mode'] == 'author_envelope',
            'Only a terminal, genuine author-envelope reader disposition can append')
    name = result['case_id']
    require(name in policy['case_ids'][2:] and name != frozen.UNKNOWN, 'Reader attempted a retained or partial history')
    slot = next(s for s in policy['case_slots'] if s['case_id'] == name)
    require(slot['mode'] == 'untouched' and result['allocation'] == slot, 'Reader allocation or fresh mode differs')
    require(result['execution_producer'] == admission['execution_producer'] == producer and
            result['source_sha256'] == admission['source_sha256'] == producer['execution_source_sha256'],
            'Actual/admitted public producer or full source map differs')
    reference = producer['source_review']
    require(admission['reader_source_review'] == reference and conductor['source_review'] == reference['path'] and
            conductor['source_review_sha256'] == conductor['host_source_review_sha256'] == reference['sha256'],
            'Reader source-review attribution differs')
    require(all(conductor['reviewed_files_sha256'].get(name) == pin
                for name, pin in producer['execution_source_sha256'].items()), 'Conductor omitted reader graph')
    custody.verify_reviewed_sources(repo, commit, conductor, source_review)
    require(all(conductor['reviewed_files_sha256'].get(name) == pin for name, pin in checker_pins.items()),
            'Conductor omitted actual checker graph')
    require(admission['mode'] == 'exposure_refinement_case' and admission['case_id'] == name and admission['case_ids'] == [name] and
            result['admission_sha256'] == sha(current/'admission.json') and
            result['numerical_attempt_id'] == admission['numerical_attempt_id'], 'Reader case/attempt admission differs')
    require(result['protocol_sha256'] == admission['protocol_sha256'] == admission['amendment_protocol_sha256'] ==
            sha(Path(repo)/frozen.PROTOCOL_PATH), 'Original amendment protocol differs')
    require(result['runtime']['essential'] == policy['original_native']['runtime_essential'], 'Original author runtime differs')
    require(all(result[key] == admission[key] == policy['original_native'][key]
                for key in ('library_sha256', 'build_receipt_sha256')), 'Author native/build admission differs')
    require(admission['independent_review_passed'] is True and admission['external_supervision'] is True and
            admission['wall_seconds'] == slot['wall_seconds'] and admission['scientific_seconds'] == slot['scientific_seconds'],
            'Original author review/supervision/caps changed')
    require(admission['threads'] == 2 and admission['workers'] == 1 and
            admission['sampled_process_tree_rss_cap_bytes'] == 6442450944 and admission['minimum_host_free_bytes'] == 2147483648,
            'Original author resource envelope differs')
    require(admission['operational_run_id'] == config['run_id'] == policy['shared_run']['run_id'] and
            admission['operational_run_config_sha256'] == policy['shared_run']['config_sha256'], 'Shared run changed')
    expiry = dt.datetime.fromisoformat(admission['expires_utc'])
    require(expiry <= dt.datetime.fromisoformat(config['deadline_utc']) and
            expiry <= dt.datetime.fromisoformat(policy['shared_run']['expires_utc']), 'Shared expiry extended')
    spec, supervisor = read(current/'supervisor_spec.json'), read(current/'supervision/result.json')
    inspect_command(spec, current, name, slot, result, admission)
    require(spec['wall_cap_seconds'] == slot['wall_seconds'] and spec['rss_cap_bytes'] == 6442450944 and
            spec['host_headroom_bytes'] == 2147483648, 'Actual reader supervisor caps differ')
    require(all(spec['env'].get(key) == '2' for key in
        ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')),
        'Reader numeric thread limit differs')
    require(supervisor['status'] == 'passed' and supervisor['returncode'] == 0 and supervisor['launched'] is True and
            supervisor['stop_reason'] is None and not supervisor['cleanup_errors'] and not supervisor['survivors_after_cleanup'],
            'Reader did not finish quiescently')
    require(supervisor['spec_sha256'] == sha(current/'supervisor_spec.json') and
            supervisor['execution_log_sha256'] == sha(current/'supervision/execution.log') and
            supervisor['supervisor_sha256'] == sha(Path(repo)/'scripts/supervise_research.py'), 'Reader supervision custody differs')
    require(dt.datetime.fromisoformat(supervisor['started_utc']) <= dt.datetime.fromisoformat(supervisor['finished_utc']) <= expiry,
            'Reader exceeded shared expiry')
    seconds, outer = core.number(result['wall_seconds']), core.number(supervisor['wall_seconds_including_cleanup'])
    require(0 <= seconds <= slot['scientific_seconds'] and seconds <= supervisor['execution_wall_seconds'] <= outer <= slot['wall_seconds'] and
            supervisor['sampled_peak_tree_rss_bytes'] <= 6442450944 and supervisor['minimum_sampled_host_available_bytes'] >= 2147483648,
            'Reader exceeded original scientific/outer/memory caps')
    inspect_native(current, repo, result, profile, policy)
    report, unknown, work = inspect_saved_math(current, repo, result, policy, science, partial)
    return result, report, unknown, work


def inspect_saved_math(current, repo, result, policy, science, partial):
    """Original saved arithmetic on actual operands, without schema substitution."""
    root = Path(current)/'science'
    report_path, trace_path = safe(root, result['report_file']), safe(root, result['trace_file'])
    require(sha(report_path) == result['report_sha256'] and sha(trace_path) == result['trace_sha256'],
            'Reader report or trace bytes changed')
    report = read(report_path)
    require(report['execution_producer'] == result['execution_producer'], 'Case producer attribution differs')
    name = result['case_id']
    source_case = next(c for c in read(Path(repo)/'reproduction/synthetic/input_manifest.json')['s04b']['cases'] if c['case_id'] == name)
    require(all(result['input_case'].get(k) == v for k, v in source_case.items()) and
            all(report.get(k) == source_case[k] for k in ('case_id', 'regime', 'seed', 'n_train', 'n_test')),
            'Reader history/input denominator differs')
    require(report['current_attempt_wall_seconds'] == report['wall_seconds'] <= result['wall_seconds'] and
            report['prior_training_attempt_seconds'] == 0, 'Fresh reader claimed imported physical work')
    core.inspect_historical(report, source_case, repo)
    if result['disposition'] == 'complete':
        require(result['passed'] is True and result['scientific_passed'] is True and result['unknown_outcome_count'] == 0 and
                result['phase_constructions'] == [dict(start=30, end=395, returned=True), dict(start=395, end=760, returned=True)],
                'Complete reader phase/acceptance flags differ')
        core.inspect_case(report, science)
        frozen.trace_matches(trace_path.read_bytes(), report)
        unknown = None
    else:
        require(result['disposition'] == 'scientific_unknown' and result['passed'] is False and
                result['scientific_passed'] is False and result['unknown_outcome_count'] == 5,
                'Technical failure cannot be a cap unknown')
        unknown = old.inspect_unknown(report, science, result['phase_constructions'], trace_path)
        arm = report['fits'][unknown['failed_model']]
        require(result['terminal_solver_return'] == arm['records'][-1] and result['unknown_reason'] ==
                dict(error_type=report['error_type'], error=report['error'], arm_status=arm['status']),
                'Unknown terminal evidence differs')
    names = [m for m in ARMS if m in report['fits']]
    census = dict(attempted_models=names, completed_models=[m for m in names if report['fits'][m]['passed']],
        not_run_models=list(ARMS[len(names):]), logical_optimizer_attempts=sum(len(report['fits'][m]['records']) for m in names),
        held_out_phase_constructed=len(result['phase_constructions']) == 2)
    if unknown:
        arm = report['fits'][unknown['failed_model']]
        census.update(unresolved_model=unknown['failed_model'], unresolved_start=unknown['unresolved_start'],
                      resolved_starts=arm['resolved_starts'], not_run_starts=arm['not_run_starts'])
    require(result['model_census'] == census and result['reused_optimizer_attempts'] == 0,
            'Fresh reader logical/reused census differs')
    work = frozen.inspect_amendment(current, report, result, policy, science, partial)
    return report, unknown, work


def inspect_transition(index, prior, prior_review, base, result, report, current, policy, producer, checker_pins):
    """Append the actual reader record without changing the accepted prefix."""
    core_sources = producer['core_source_sha256']
    for value in (prior, index):
        require(value['schema'] == 'joint_exposure_refinement_index_v1' and value['passed'] is False and
                value['scientific_completion'] is False and value['protocol_sha256'] == result['protocol_sha256'] and
                value['host_source_sha256'] == value['scientific_source_sha256'] == core_sources,
                'Frozen core compatibility index/source map changed')
        require(value['numerical_amendment_version'] == policy['version'] and
                value['original_scientific_protocol_sha256'] == policy['original_scientific_protocol_sha256'] and
                value['original_native'] == policy['original_native'] and
                value['immutable_failure_reference'] == policy['permanent_unknown'] and
                value['original_exposure_failure_reference'] == policy['failed_case'] and
                value['compatible_saved_prefix'] == policy['base'], 'Retained original lineage changed')
    require(index['records'][:-1] == prior['records'] and index['records'][:44] == base['records'] and
            index['attempts'][:-1] == prior['attempts'], 'Accepted prior prefix or old work changed')
    require([r['case_id'] for r in index['records']] == policy['full_sequence'][:len(index['records'])] and
            len(index['records']) == 44+len(index['attempts']), 'Reader skipped/repeated a planned history')
    require(prior['records'][44]['case_id'] == frozen.PARTIAL and prior['records'][44]['disposition'] == 'complete',
            'Mandatory partial pilot is not an accepted complete predecessor')
    current = Path(current); host = current.parent.parent
    row = index['records'][-1]; source = row['source']
    require(source['kind'] == 'host_execution', 'Reader result lacks actual host custody')
    paths = dict(case_path=current/'science'/result['report_file'], trace_path=current/'science'/result['trace_file'],
        result_path=current/'science/result.json', supervision_path=current/'supervision/result.json')
    for key, path in paths.items():
        require(source[key] == path.relative_to(host).as_posix() and source[key.replace('_path', '_sha256')] == sha(path),
                'Reader append source locator differs: '+key)
    expected = old.projection(report, result['disposition'], source)
    expected.update(numerical_amendment=result['numerical_amendment'], refinement_census=result['refinement_census'],
                    execution_producer=producer)
    if result['disposition'] == 'scientific_unknown':
        expected.update(unknown_origin='new_frozen_solver_cap', unknown_reason=result['unknown_reason'],
                        model_census=result['model_census'], terminal_solver_return=result['terminal_solver_return'])
    require(row == expected, 'Reader compact record/producer differs from actual saved output')
    supervisor = read(current/'supervision/result.json')
    attempt = dict(case_id=result['case_id'], numerical_attempt_id=result['numerical_attempt_id'],
        host_execution_id=source['execution_id'], seconds=result['wall_seconds'],
        outer_seconds=supervisor['wall_seconds_including_cleanup'], result_sha256=source['result_sha256'],
        supervision_sha256=source['supervision_sha256'], actual_optimizer_attempts=result['actual_optimizer_attempts'],
        reused_optimizer_attempts=0)
    require(index['attempts'][-1] == attempt and index['counts'] == old.expected_counts(index['records']) and
            prior['counts'] == old.expected_counts(prior['records']), 'Reader work/count projection differs')
    grant = read(host.parent/'admission.json')
    batch = grant['batch_id']
    require(type(batch) is int and batch == 3, 'Reader author group is ineligible')
    group = policy['resources']['future_hosts'][batch-1]
    require(group['host'] == batch and grant['mode'] == 'exposure_refinement_host_batch' and
            grant['case_ids'] == group['case_ids'] and result['case_id'] in group['case_ids'] and
            set(grant['child_attempt_ids']) == set(group['case_ids']) and
            len(set(grant['child_attempt_ids'].values())) == len(group['case_ids']), 'Reader changed fixed host partition')
    position = group['case_ids'].index(result['case_id'])
    preceding = sum(len(g['case_ids']) for g in policy['resources']['future_hosts'][:batch-1])
    require(len(prior['records']) == 44+preceding+position, 'Reader stranded or skipped a fixed host boundary')
    require(source['execution_id'] == grant['numerical_attempt_id'] and
            result['numerical_attempt_id'] == grant['child_attempt_ids'][result['case_id']], 'Unadmitted reader attempt')
    require(grant['source_sha256'] == grant['scientific_source_sha256'] == core_sources and
            grant['protocol_sha256'] == result['protocol_sha256'] and grant['execution_producer'] == producer and
            grant['reader_source_review'] == producer['source_review'], 'Parent core/actual producer identity differs')
    if position == 0:
        require(index['predecessor'] == dict(index_sha256=grant['prior_index_sha256'],
            review_sha256=grant['prior_review_sha256'], archive_sha256=grant['prior_archive_sha256']),
            'Whole-group predecessor differs from admission')
        frozen.live_review(prior_review)
        require(prior_review['review_kind'] == 'live_agent_saved_output_review' and prior_review['passed'] is True and
                prior_review['audit_passed'] is True and prior_review['artifact_sha256'] == grant['prior_archive_sha256'],
                'Reader group lacks a genuine accepted predecessor host')
    else:
        require(index['predecessor']['archive_sha256'] is None and
                prior['records'][-1]['case_id'] == group['case_ids'][position-1] and
                prior['records'][-1]['source']['execution_id'] == grant['numerical_attempt_id'] and
                prior['records'][-1]['execution_producer'] == producer,
                'Within-group predecessor or actual producer differs')
        require(prior_review['review_kind'] == 'automated_saved_output_check' and prior_review['passed'] is True and
                prior_review['audit_passed'] is True and prior_review['live_agent_review'] is False and
                prior_review['live_agent_review_performed'] is False and prior_review['final_batch_agent_review_required'] is True and
                prior_review['checker_sources_sha256'] == checker_pins and
                prior_review['checker_source_review_sha256'] == producer['source_review']['sha256'] and
                prior_review['execution_producer'] == producer,
                'Within-group actual checker receipt is missing or misattributed')
    require(grant['shared_run'] == policy['shared_run'] and grant['expires_utc'] == policy['shared_run']['expires_utc'],
            'Reader parent extended shared limits')
    frozen.inspect_budget(prior, policy)
    return frozen.inspect_budget(index, policy)


def audit_saved(args):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    repo, current = Path(args.repo).resolve(), Path(args.current).resolve()
    policy, science, design, profile, producer, review, checker_pins = load_contract(
        repo, Path(args.checker_source_review), args.checker_source_review_sha256)
    require(sha(args.config) == policy['shared_run']['config_sha256'], 'Shared configuration changed')
    config = read(args.config)
    base, partial = frozen.initial_evidence(repo, policy, science, design)
    result, report, unknown, work = inspect_current(current, repo, policy, science, profile, producer,
        review, checker_pins, config, args.commit, partial)
    prior_path, prior_review_path = Path(args.prior).resolve(), Path(args.prior_review).resolve()
    prior, prior_review, index = read(prior_path), read(prior_review_path), read(current/'index.json')
    require(index['predecessor']['index_sha256'] == sha(prior_path) and
            index['predecessor']['review_sha256'] == sha(prior_review_path) and
            prior_review['index_sha256'] == sha(prior_path) and prior_review['scientific_completion'] is False,
            'Actual prior bytes and review do not agree')
    budget = inspect_transition(index, prior, prior_review, base, result, report, current, policy, producer, checker_pins)
    complete = {r['case_id']:r for r in index['records'] if r['disposition'] == 'complete'}
    summary = old.disposition_summary(index['records'], complete, policy['full_sequence'])
    return dict(schema='joint_refined_cpu_independent_saved_output_check_v1', passed=True, audit_passed=True,
        disposition_valid=True, disposition=result['disposition'], scientific_passed=result['scientific_passed'],
        scientific_completion=False, original_full_success_gate_passed=False, original_publication_gate_satisfied=False,
        review_kind='automated_saved_output_check', live_agent_review=False, live_agent_review_performed=False,
        final_batch_agent_review_required=True, index_sha256=sha(current/'index.json'),
        source_sha256=producer['execution_source_sha256'], core_source_sha256=producer['core_source_sha256'],
        host_source_sha256=index['host_source_sha256'], execution_producer=producer,
        checker_sources_sha256=checker_pins, checker_source_review_sha256=args.checker_source_review_sha256,
        prior_index_sha256=sha(prior_path), prior_review_sha256=sha(prior_review_path),
        report_sha256=result['report_sha256'], trace_sha256=result['trace_sha256'], case_id=result['case_id'],
        counts=index['counts'], budget=budget, unknown_census=unknown,
        refinement_and_reuse_census=work, independent_summary=summary,
        all_histories_attempted=len(index['records']) == 80, numerical_calls=0, optimizer_calls=0,
        scope='Actual public-reader custody and saved arithmetic only; exact core compatibility is separate from actual producer identity.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo','current','prior','prior-review','config','commit','output','checker-source-review','checker-source-review-sha256'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    require(not output.exists(), 'Audit output must be fresh')
    try:
        result = audit_saved(args)
    except Exception as exc:
        result = dict(passed=False, audit_passed=False, disposition_valid=False, scientific_passed=False,
            scientific_completion=False, original_full_success_gate_passed=False,
            review_kind='automated_saved_output_check', live_agent_review=False, live_agent_review_performed=False,
            final_batch_agent_review_required=True, error_type=type(exc).__name__, error=str(exc),
            numerical_calls=0, optimizer_calls=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(result, indent=2, allow_nan=False)+'\n').encode())
    return 0 if result['audit_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
