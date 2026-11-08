"""Independent saved-output check for the 39 untouched joint-fit histories.

No producer, likelihood, optimizer, feature constructor or simulator is imported.
An accepted disposition is not a successful scientific comparison.  Incomplete
planned 20-history strata have no mean, median, win fraction or Wilson interval.
"""
from pathlib import Path, PurePosixPath
import argparse
import datetime as dt
import importlib.util
import json
import math
import posixpath
import statistics
import sys
import zipfile

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
CHECKER_PATH = 'experiments/s04b_joint_remaining_audit/check.py'
CUSTODY_PATH = 'experiments/s04b_joint_audit/check.py'
CORE_PATH = 'experiments/s04b_joint_nuisance_audit/audit.py'
CUSTODY_SHA256 = '839c67fd3dca65294b457cb6511a66c1800fa422712fc13e302e4f4495ddaa13'
CORE_SHA256 = '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3'


def _module(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


custody = _module('remaining_custody', CUSTODY_PATH)
core = _module('remaining_independent_core', CORE_PATH)
require, read, sha, safe = custody.require, custody.read, custody.sha, custody.safe
ARMS = ('null', *core.MODELS)
UNKNOWN_CASE = 'S5_broad_long_imm_seed410518'
TOL = 1e-9


def trace_records(path, report):
    """Exact retained fit/trace identity, including an unresolved final arm."""
    require(sha(path) == report['attempts_sha256'], 'Attempt trace identity')
    actual = [json.loads(line, object_pairs_hook=custody.object_pairs,
                        parse_constant=lambda x: (_ for _ in ()).throw(custody.AuditError(x)))
              for line in Path(path).read_text(encoding='utf-8').splitlines()]
    expected = []
    for model in ARMS:
        if model not in report['fits']:
            continue
        for record in report['fits'][model]['records']:
            expected.append(dict(event='attempt_start', model=model,
                start_index=record['start_index'], method=record['method'],
                initial_parameters=record['initial_parameters'], status='running', success=False))
            expected.append(dict(event='attempt_end', model=model, **record))
    require(actual == expected, 'Trace does not exactly match saved fit records')
    return actual


def _returned(record, model, protocol):
    """Validate a finite returned point; the solver success flag remains decisive."""
    box = protocol['shared_bounds'] + ([] if model == 'null' else protocol['inhibition_bounds'])
    width = len(box)
    require(record['status'] == 'returned' and record['finite_feasible'] is True,
            'Unknown eligibility requires a finite returned solver state')
    require(type(record['solver_success']) is bool and type(record['success']) is bool,
            'Boolean solver flags required')
    require(len(record['parameters']) == len(record['gradient']) == 8, 'Full state dimension')
    core.sides(record['parameters'][:width], box)
    require(record['returned_parameters'] == record['parameters'][:width], 'Returned point changed')
    core.score(record['fresh_score'])
    core.number(record['returned_nll'])
    delta = abs(record['fresh_score']['nll'] - record['returned_nll'])
    require(record['fresh_nll_delta'] == delta, 'Original fresh-score discrepancy changed')
    require(record['success'] is (record['solver_success'] and delta <= TOL), 'Fresh-score/solver success inconsistent')
    for value in record['gradient']:
        core.number(value)
    require(record['projected_gradient'] == core.projected(record['parameters'][:width], record['gradient'][:width], box),
            'Returned projected gradient changed')
    require(record['boundaries'] == core.sides(record['parameters'][:width], box), 'Returned boundaries changed')
    require(type(record['nfev']) is int and record['nfev'] >= 0 and
            type(record['nit']) is int and record['nit'] >= 0, 'Invalid solver counters')
    if record['method'] == 'Powell':
        require(record['nfev'] <= protocol['solver']['powell']['maxfev'] and
                record['nit'] <= protocol['solver']['powell']['maxiter'], 'Original Powell cap exceeded')
    else:
        require(record['nit'] <= protocol['solver']['maxiter'], 'Original primary cap exceeded')


def inspect_unknown(report, protocol, phase_constructions, trace_path):
    """Narrow terminal scientific unknown: original finite capped Powell return.

    No arbitrary exception, missing state, quadrature failure, nonfinite return,
    timeout or partially scored history is accepted by this classifier.
    """
    require(report.get('passed') is False and report.get('status') == 'unknown', 'Unknown report status')
    require(report.get('error_type') == 'ValueError', 'Technical error is not scientific unknown')
    require(not report.get('training_selections_frozen', False), 'Unknown selected/scored after failure')
    require(report.get('outcomes') == [] and not report.get('test_checks') and
            'new_null_test' not in report and 'bic_threshold' not in report,
            'Unknown history contains held-out predictions')
    require(phase_constructions == [dict(start=30, end=395, returned=True)], 'Unknown had a non-training phase')
    fits = report['fits']
    models = [name for name in ARMS if name in fits]
    require(models and models == list(ARMS[:len(models)]) and set(fits) == set(models), 'Fit prefix changed')
    failed_model = models[-1]
    require(report['error'] == ('Unresolved null starts' if failed_model == 'null' else 'Unresolved alternative starts'),
            'Unknown error is not the original unresolved-start guard')
    checks = report.get('training_checks', {})
    require(set(checks) == set(models[:-1]), 'Training checks cross the unresolved arm')
    null = fits['null'].get('selected', {}).get('parameters')
    for model in models[:-1]:
        core.inspect_fit(fits[model], model, protocol, report['n_train'], null)
        box = protocol['shared_bounds'] + ([] if model == 'null' else protocol['inhibition_bounds'])
        core.inspect_training(checks[model], fits[model], box, protocol)
        if model != 'null':
            require(checks[model]['fine']['nll'] <= checks['null']['fine']['nll'] + TOL,
                    'Completed alternative fails original eligible-floor gate')
    failed = fits[failed_model]
    require(failed.get('passed') is False and failed.get('status') == 'unknown_starts' and
            failed.get('model') == failed_model and failed.get('required_starts') == 8,
            'No frozen unknown_starts return')
    require('selected' not in failed and 'selected_state_index' not in failed and 'null_search_gaps' not in failed,
            'Unknown fit was given an accepted selection')
    resolved = failed['resolved_starts']
    require(1 <= len(resolved) <= 8 and resolved == [True] * (len(resolved)-1) + [False], 'Unresolved-start prefix')
    terminal = len(resolved)-1
    require(failed['not_run_starts'] == list(range(terminal+1, 8)), 'Not-run starts changed')
    candidates = failed['candidates']
    require(len(candidates) == terminal+1 and [c['state_index'] for c in candidates] == list(range(terminal+1)),
            'Unresolved candidate was substituted or prior candidate missing')
    floor = candidates[0]
    require(floor['kind'] == ('historical_floor' if failed_model == 'null' else 'new_null_floor') and
            floor['start_index'] == -1, 'Eligible floor missing')
    if failed_model != 'null':
        require(floor['parameters'] == null, 'Eligible floor differs from completed new null')
    records = failed['records']
    consumed = []
    for index in range(terminal+1):
        attempts = [record for record in records if record['start_index'] == index]
        require(len(attempts) in (1, 2) and [r['method'] for r in attempts] == ['L-BFGS-B', 'Powell'][:len(attempts)],
                'Unknown fit solver order/budget changed')
        core.vector(attempts[0]['initial_parameters'], core.expected_start(protocol, report['n_train'], failed_model, index, null),
                    'Prescribed initial point changed')
        if len(attempts) == 2:
            primary = attempts[0]
            require(primary['success'] is False, 'Rescue after resolved primary')
            expected = primary['returned_parameters'] if primary.get('finite_feasible') and primary.get('parameters') is not None else primary['initial_parameters']
            require(attempts[1]['initial_parameters'] == expected, 'Rescue initial point changed')
        for record in attempts:
            if record['status'] == 'exception':
                require(record['success'] is False and record['error_type'] in
                        ('ArithmeticError', 'FloatingPointError', 'OverflowError', 'ZeroDivisionError'),
                        'Technical exception cannot become scientific unknown')
            elif record.get('finite_feasible'):
                _returned(record, failed_model, protocol)
            else:
                require(record['status'] == 'returned' and record['success'] is False and record['finite_feasible'] is False,
                        'Invalid intermediate failed return')
        if index < terminal:
            require(attempts[-1]['success'] is True, 'Earlier start did not resolve')
            final = attempts[-1]
            require(candidates[index+1] == dict(state_index=index+1, kind='optimizer', start_index=index,
                parameters=final['parameters'], score=final['fresh_score'], gradient=final['gradient']),
                'Completed candidate differs from successful solver record')
        else:
            require(len(attempts) == 2 and all(r['success'] is False for r in attempts), 'Terminal start did not exhaust original rescue')
            final = attempts[-1]
            _returned(final, failed_model, protocol)
            require(final['solver_success'] is False, 'Converged solver mislabeled unknown')
            require(final['fresh_nll_delta'] <= TOL, 'Capped return fails original fresh-score gate')
            limit = protocol['solver']['powell']
            require((final['solver_status'] == 1 and final['nfev'] == limit['maxfev']) or
                    (final['solver_status'] == 2 and final['nit'] == limit['maxiter']),
                    'Unknown requires the original explicit Powell cap return')
        consumed.extend(attempts)
    require(consumed == records, 'Extra or reordered optimizer attempts')
    for candidate in candidates:
        core.score(candidate['score'])
        require(len(candidate['parameters']) == len(candidate['gradient']) == 8, 'Candidate dimension')
        width = 5 if failed_model == 'null' else 8
        core.sides(candidate['parameters'][:width], protocol['shared_bounds'] + ([] if failed_model == 'null' else protocol['inhibition_bounds']))
        if failed_model == 'null':
            core.vector(candidate['parameters'][5:], [0., math.log(30), math.log(7)], 'Null inactive coordinates')
        for value in candidate['gradient']:
            core.number(value)
    require(len(report['floor_checks']) == 3 and {(v['phase'], v['model']) for v in report['floor_checks']} ==
            {('train', model) for model in core.MODELS}, 'Unknown historical floor roster')
    for row in report['floor_checks']:
        require(row['tolerance'] == TOL and row['absolute_delta'] == abs(row['actual_nll']-row['expected_nll']) <= TOL,
                'Historical floor failed')
    require(len(report['historical_comparisons']) == 5 and
            {(row['model'],row['gate']) for row in report['historical_comparisons']} == set(core.OUTCOMES) and
            all(row['passed'] is True for row in report['historical_comparisons']), 'Unknown historical comparator roster changed')
    trace_records(trace_path, report)
    return dict(failed_model=failed_model, unresolved_start=terminal, resolved_starts=terminal,
                not_run_starts=failed['not_run_starts'], not_run_models=list(ARMS[len(models):]),
                unknown_outcome_count=5, held_out_phase_count=0,
                optimizer_attempt_count=sum(len(fits[m]['records']) for m in models),
                terminal_solver_status=final['solver_status'], terminal_nfev=final['nfev'], terminal_nit=final['nit'])


def disposition_summary(dispositions, reports, sequence):
    """Full planned denominators; never turn unavailable outcomes into losses."""
    require(len(sequence) == 80 and len(set(sequence)) == 80, 'Planned roster must contain 80 distinct histories')
    by_id = {row['case_id']: row for row in dispositions}
    require(len(by_id) == len(dispositions) and list(by_id) == sequence[:len(by_id)], 'Processed dispositions are not an exact prefix')
    require(all(row['disposition'] in ('complete', 'scientific_unknown') for row in dispositions), 'Unaccepted disposition in prefix')
    require(set(reports) == {key for key, value in by_id.items() if value['disposition'] == 'complete'}, 'Available report roster mismatch')
    rows = []
    for regime in range(4, 8):
        planned = [key for key in sequence if key.startswith('S'+str(regime)+'_')]
        require(len(planned) == 20, 'Planned regime size changed')
        complete = [key for key in planned if key in reports]
        unknown = [key for key in planned if by_id.get(key, {}).get('disposition') == 'scientific_unknown']
        not_run = [key for key in planned if key not in by_id]
        for model, gate in core.OUTCOMES:
            outcomes = [next(row for row in reports[key]['outcomes'] if (row['model'], row['gate']) == (model, gate)) for key in complete]
            gains = [row['new_gain'] for row in outcomes]
            wins = sum(value > 0 for value in gains)
            full = len(complete) == 20
            rows.append(dict(regime=regime, model=model, gate=gate, planned_N=20,
                complete_N=len(complete), unknown_N=len(unknown), not_run_N=len(not_run),
                mean_gain=statistics.mean(gains) if full else None,
                median_gain=statistics.median(gains) if full else None,
                win_fraction=wins/20 if full else None, wilson95=core.interval(wins, 20) if full else None,
                wins=wins if full else None,
                summary_available=full))
    return rows


def verify_checker_review(repo, path, pin):
    require(sha(path) == pin, 'Checker source review changed')
    review = read(path)
    require(review.get('passed') is True, 'Checker source review did not pass')
    identities = {CHECKER_PATH: sha(HERE), CUSTODY_PATH: CUSTODY_SHA256, CORE_PATH: CORE_SHA256}
    for relative, expected in identities.items():
        require(sha(safe(repo, relative)) == expected, 'Checker dependency changed: '+relative)
        require(review['reviewed_files_sha256'].get(relative) == expected, 'Unreviewed checker dependency: '+relative)
    return identities


def recorded_path(recorded, remote_science, current):
    """Relocate recorded Linux child paths without requiring its old temp root."""
    remote_child = PurePosixPath(remote_science).parent
    require(remote_child.is_absolute() and PurePosixPath(recorded).is_absolute(), 'Expected recorded absolute child path')
    relative = posixpath.relpath(str(recorded), str(remote_child))
    path = (current / relative).resolve()
    require(path.is_relative_to(current.parents[2]), 'Recorded child path escapes retained artifact')
    return path


def inspect_current(current, repo, policy, science, config, commit, checker_pins):
    """Validate one supervised, untouched case independently of producer flags."""
    result = read(current/'science/result.json')
    admission = read(current/'admission.json')
    conductor = read(current/'conductor_review.json')
    require(result['schema'] == 'joint_remaining_case_result_v1' and
            result['handled'] is True and result['disposition_valid'] is True and
            result['status'] == 'terminal_disposition', 'Technical or incomplete case cannot advance')
    case_id = result['case_id']
    require(case_id in policy['case_ids'] and case_id != UNKNOWN_CASE, 'Previously attempted history cannot be repeated')
    require(admission['mode'] == 'untouched_remaining_case' and admission['case_id'] == case_id and
            admission['case_ids'] == [case_id], 'Admitted case differs')
    require(result['admission_sha256'] == sha(current/'admission.json'), 'Admission identity changed')
    require(result['source_sha256'] == admission['source_sha256'], 'Executed/admitted scientific sources differ')
    source_review_path = safe(repo, conductor['source_review_record'])
    require(sha(source_review_path) == conductor['source_review_sha256'] == conductor['host_source_review_sha256'],
            'Producer source-review identity changed')
    source_review = read(source_review_path)
    require(source_review.get('passed') is True and source_review.get('live_agent_review') is True,
            'Missing independent producer source approval')
    for relative, pin in result['source_sha256'].items():
        require(sha(safe(repo, relative)) == pin and conductor['reviewed_files_sha256'].get(relative) == pin and
                source_review['reviewed_files_sha256'].get(relative) == pin,
                'Unreviewed case-driver dependency: '+relative)
    # Existing custody helper compares the genuine review map to exact Git bytes.
    custody.verify_reviewed_sources(repo, commit, conductor, dict(reviewed_files_sha256={
        CUSTODY_PATH: CUSTODY_SHA256, CORE_PATH: CORE_SHA256}))
    for relative, pin in checker_pins.items():
        require(conductor['reviewed_files_sha256'].get(relative) == pin, 'Checker absent from execution source admission')
    require(result['protocol_sha256'] == admission['protocol_sha256'] == sha(repo/'experiments/s04b_joint_remaining/protocol.json'),
            'Remaining protocol identity changed')
    require(result['immutable_failure_reference'] == policy['immutable_failure_reference'], 'Permanent unknown lineage changed')
    require(result['runtime']['essential'] == policy['original_native']['runtime_essential'], 'Numerical runtime changed')
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(result[key] == admission[key] == policy['original_native'][key], 'Original native/build identity changed')
    require(result['numerical_attempt_id'] == admission['numerical_attempt_id'], 'Attempt identity changed')
    slot = next(row for row in policy['case_slots'] if row['case_id'] == case_id)
    require(result['allocation'] == slot and admission['wall_seconds'] == slot['wall_seconds'], 'Original case slot changed')
    require(admission['independent_review_passed'] is True and admission['external_supervision'] is True,
            'No independently reviewed numerical admission')
    require(admission['threads'] == 2 and admission['workers'] == 1 and
            admission['sampled_process_tree_rss_cap_bytes'] == 6442450944 and
            admission['minimum_host_free_bytes'] == 2147483648, 'Case resource admission changed')
    require(admission['operational_run_id'] == config['run_id'] == policy['shared_run']['run_id'] and
            admission['operational_run_config_sha256'] == policy['shared_run']['config_sha256'], 'Shared-run identity changed')
    expiry = dt.datetime.fromisoformat(admission['expires_utc'])
    require(expiry <= dt.datetime.fromisoformat(config['deadline_utc']), 'Expiry was extended')
    spec = read(current/'supervisor_spec.json')
    supervision = read(current/'supervision/result.json')
    require(spec['wall_cap_seconds'] == slot['wall_seconds'] and spec['rss_cap_bytes'] == 6442450944 and
            spec['host_headroom_bytes'] == 2147483648, 'Supervisor resource gates changed')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
        require(spec['env'].get(key) == '2', 'Numeric thread cap changed')
    argv = spec['command']
    require(argv[1:4] == ['-B', '-m', 'experiments.s04b_joint_remaining.case_driver'], 'Different supervised scientific entrypoint')
    def arg(name):
        require(argv.count(name) == 1, 'Missing/duplicate child argument '+name)
        return argv[argv.index(name)+1]
    remote_science = arg('--output')
    require(arg('--case-id') == case_id and recorded_path(remote_science, remote_science, current) == (current/'science').resolve() and
            recorded_path(arg('--admission'), remote_science, current) == (current/'admission.json').resolve(), 'Supervised case/output differs')
    library = recorded_path(arg('--library'), remote_science, current)
    build_path = recorded_path(arg('--build-receipt'), remote_science, current)
    require(sha(library) == result['library_sha256'] and sha(build_path) == result['build_receipt_sha256'], 'Actual supervised native bytes changed')
    build = read(build_path)
    require(build['passed'] is True and build['library_sha256'] == result['library_sha256'] and
            build['source_sha256'] == sha(repo/'experiments/s04b_joint_nuisance/attenuation.cpp'), 'Native build provenance changed')
    require(supervision['status'] == 'passed' and supervision['returncode'] == 0 and
            supervision['launched'] is True and supervision['stop_reason'] is None and
            not supervision['cleanup_errors'] and not supervision['survivors_after_cleanup'], 'Child was not cleanly completed')
    require(supervision['spec_sha256'] == sha(current/'supervisor_spec.json') and
            supervision['execution_log_sha256'] == sha(current/'supervision/execution.log') and
            supervision['supervisor_sha256'] == sha(repo/'scripts/supervise_research.py'), 'Supervision evidence changed')
    require(dt.datetime.fromisoformat(supervision['started_utc']) <= dt.datetime.fromisoformat(supervision['finished_utc']) <= expiry,
            'Child exceeded expiry')
    require(0 <= core.number(result['wall_seconds']) <= supervision['execution_wall_seconds'] <= slot['wall_seconds'] and
            supervision['sampled_peak_tree_rss_bytes'] <= 6442450944 and
            supervision['minimum_sampled_host_available_bytes'] >= 2147483648, 'Child resource gate failed')
    report_path = safe(current/'science', result['report_file'])
    trace_path = safe(current/'science', result['trace_file'])
    require(sha(report_path) == result['report_sha256'] and sha(trace_path) == result['trace_sha256'], 'Case/trace identity changed')
    report = read(report_path)
    roster = read(repo/'reproduction/synthetic/input_manifest.json')['s04b']['cases']
    case = next(row for row in roster if row['case_id'] == case_id)
    require(all(result['input_case'].get(key) == value for key, value in case.items()), 'Input case metadata changed')
    require(all(report.get(key) == case[key] for key in ('case_id', 'regime', 'seed', 'n_train', 'n_test')), 'Report case/count identity changed')
    require(report.get('prior_training_attempt_seconds') == 0 and report['current_attempt_wall_seconds'] == report['wall_seconds'] <= result['wall_seconds'],
            'Untouched history was resumed or wall time changed')
    require(result['original_case_status'] == report['status'] and result['original_case_error'] ==
            {key:report[key] for key in ('error_type', 'error') if key in report}, 'Original case status concealed')
    core.inspect_historical(report, case, repo)
    if result['disposition'] == 'complete':
        require(result['passed'] is True and result['scientific_passed'] is True and result['unknown_outcome_count'] == 0,
                'Complete case flags disagree')
        require(result['phase_constructions'] == [dict(start=30,end=395,returned=True),dict(start=395,end=760,returned=True)],
                'Complete phase roster changed')
        core.inspect_case(report, science)
        core.inspect_trace(trace_path, report)
        unknown = None
    else:
        require(result['disposition'] == 'scientific_unknown' and result['passed'] is False and
                result['scientific_passed'] is False and result['unknown_outcome_count'] == 5, 'Unknown flags disagree')
        unknown = inspect_unknown(report, science, result['phase_constructions'], trace_path)
        failed = report['fits'][unknown['failed_model']]
        require(result['terminal_solver_return'] == failed['records'][-1] and result['unknown_reason'] ==
                dict(error_type=report['error_type'], error=report['error'], arm_status=failed['status']), 'Unknown solver evidence changed')
    attempted = [model for model in ARMS if model in report['fits']]
    census = dict(attempted_models=attempted,
        completed_models=[model for model in attempted if report['fits'][model]['passed'] is True],
        not_run_models=list(ARMS[len(attempted):]),
        logical_optimizer_attempts=sum(len(report['fits'][model]['records']) for model in attempted),
        held_out_phase_constructed=len(result['phase_constructions']) == 2)
    if unknown:
        failed = report['fits'][unknown['failed_model']]
        census.update(unresolved_model=unknown['failed_model'], unresolved_start=unknown['unresolved_start'],
                      resolved_starts=failed['resolved_starts'], not_run_starts=failed['not_run_starts'])
    require(result['model_census'] == census, 'Model/start/not-run census changed')
    return result, report, unknown


def projection(report, disposition, source):
    """Only actually stored outputs enter the compact index."""
    fits = report['fits']
    return dict(case_id=report['case_id'], regime=report['regime'], seed=report['seed'],
                disposition=disposition, scientific_passed=disposition == 'complete', source=source,
                outcomes=report['outcomes'] if disposition == 'complete' else [],
                n_train=report['n_train'], n_test=report['n_test'], thinning=report['thinning'],
                optimizer_failed_attempts_by_arm={name:sum(record['success'] is False for record in fits[name]['records']) for name in ARMS if name in fits},
                null_search_gap_by_arm={name:bool(fits[name]['null_search_gaps']) for name in ARMS if name in fits and fits[name]['passed'] is True})


def initial_records(repo, policy, science, prior_path, prior_review_path):
    """Verify the one permitted failed predecessor and its immutable projections."""
    ref = policy['immutable_failure_reference']
    require(sha(prior_path) == ref['index_sha256'] and sha(prior_review_path) == ref['review_sha256'], 'Different initial failure predecessor')
    review = read(prior_review_path)
    require(review['passed'] is False and review['audit_passed'] is True and
            review['scientific_completion'] is False, 'Initial failure was relabelled success')
    archive = safe(repo, ref['archive'])
    require(sha(archive) == ref['archive_sha256'], 'Immutable failure archive changed')
    initial = read(prior_path)
    require(initial['last_attempt_passed'] is False and len(initial['cases']) == 40, 'Initial completed prefix changed')
    prefix = str(PurePosixPath(ref['index_member']).parent)
    rows = []
    with zipfile.ZipFile(archive) as saved:
        require(len(saved.namelist()) == len(set(saved.namelist())), 'Duplicate immutable archive member')
        def document(member, pin):
            value = saved.read(member)
            require(custody.h(value) == pin, 'Immutable archive member changed: '+member)
            return json.loads(value, object_pairs_hook=custody.object_pairs)
        require(saved.read(ref['index_member']) == Path(prior_path).read_bytes(), 'Initial index differs from archive')
        for entry in initial['cases']:
            member, trace_member = prefix+'/'+entry['file'], prefix+'/'+entry['trace']
            report = document(member, entry['sha256'])
            require(custody.h(saved.read(trace_member)) == entry['trace_sha256'], 'Original trace member changed')
            core.inspect_case(report, science)
            source = dict(kind='immutable_archive', archive_sha256=ref['archive_sha256'], case_member=member,
                          case_sha256=entry['sha256'], trace_member=trace_member, trace_sha256=entry['trace_sha256'])
            rows.append(projection(report, 'complete', source))
        failed = document(ref['case_member'], ref['case_sha256'])
        trace = saved.read(ref['trace_member'])
        require(custody.h(trace) == ref['trace_sha256'], 'Failed trace identity changed')
        events = [json.loads(line) for line in trace.splitlines()]
        last = {key:value for key,value in events[-1].items() if key not in ('event','model')}
        require(events[-1]['event'] == 'attempt_end' and events[-1]['model'] == 'LIplus_immigrant', 'Wrong original cap arm')
        require(last == review['failure']['capped_optimizer_record'] and last['start_index'] == 5 and
                last['success'] is False and last['solver_status'] == 1 and last['nfev'] == 5000 and last['nit'] == 22,
                'Original terminal cap evidence changed')
        _returned(last, 'LIplus_immigrant', science)
        require(failed['passed'] is False and failed['outcomes'] == [] and
                failed['error_type'] == 'KeyError' and failed['error'] == "'selected_state_index'" and
                not failed.get('training_selections_frozen', False), 'Original failed case changed')
        source = dict(kind='immutable_archive', archive_sha256=ref['archive_sha256'], case_member=ref['case_member'],
                      case_sha256=ref['case_sha256'], trace_member=ref['trace_member'], trace_sha256=ref['trace_sha256'])
        row = projection(failed, 'scientific_unknown', source)
        row.update(unknown_origin='audited_retained_failure',
            unknown_reason=dict(primary_status='unknown_starts', unresolved_model='LIplus_immigrant',
                unresolved_start=5, not_run_starts=[6,7], not_run_models=['LIplus_inclusive'],
                masking_error_type=failed['error_type'], masking_error=failed['error'], terminal_solver_return=last),
            model_census=review['execution_census'])
        rows.append(row)
    require([row['case_id'] for row in rows] == policy['full_sequence'][:41] and
            ref['complete_case_ids'] == policy['full_sequence'][:40] and rows[-1]['case_id'] == UNKNOWN_CASE,
            'Initial prefix or permanent unknown changed')
    return rows


def expected_counts(records):
    complete = sum(row['disposition'] == 'complete' for row in records)
    unknown = sum(row['disposition'] == 'scientific_unknown' for row in records)
    require(complete+unknown == len(records), 'Technical failure in accepted prefix')
    return dict(processed_histories=len(records), complete_histories=complete,
                unknown_histories=unknown, unattempted_histories=80-len(records), computed_outcomes=5*complete)


def inspect_budget(index, policy):
    ref = policy['immutable_failure_reference']
    attempts = index['attempts']
    ids = [row['case_id'] for row in attempts]
    require(ids == policy['case_ids'][:len(ids)], 'Case attempts were repeated, skipped or reordered')
    require(len({row['numerical_attempt_id'] for row in attempts}) == len(attempts), 'Numerical attempt reused')
    for row in attempts:
        require(0 <= core.number(row['seconds']) <= next(s['wall_seconds'] for s in policy['case_slots'] if s['case_id'] == row['case_id']),
                'Case attempt exceeds original slot')
    new_seconds = math.fsum(row['seconds'] for row in attempts)
    base = math.fsum(ref[key] for key in ('scientific_indexed_seconds','known_prior_outer_overhead_seconds',
        'operational_failure_charge_seconds','operational_diagnostic_charge_seconds','additional_workflow_overhead_seconds'))
    core.close(base, ref['accounted_base_seconds'], 'Initial budget reconciliation')
    core.close(ref['additional_workflow_overhead_seconds'] + ref['included_current_scientific_seconds'],
               ref['whole_workflow_bound_seconds'], 'Pilot04 cost was lost or double charged')
    remaining = sum(row['wall_seconds'] for row in policy['case_slots'][len(attempts):])
    accounted = base+new_seconds
    resource = policy['resources']
    reserve = resource['future_host_overhead_reserve_seconds']
    finalization = resource['global_finalization_reserve_seconds']
    expected = dict(base_scientific_indexed_seconds=ref['scientific_indexed_seconds'],
        new_case_seconds=new_seconds, scientific_indexed_seconds=ref['scientific_indexed_seconds']+new_seconds,
        known_prior_outer_overhead_seconds=ref['known_prior_outer_overhead_seconds'],
        operational_failure_charge_seconds=ref['operational_failure_charge_seconds'],
        operational_diagnostic_charge_seconds=ref['operational_diagnostic_charge_seconds'],
        pilot04_incremental_workflow_overhead_seconds=ref['additional_workflow_overhead_seconds'],
        accounted_seconds=accounted, remaining_case_slots_seconds=remaining,
        reserved_host_overhead_seconds=reserve, global_finalization_reserve_seconds=finalization,
        upper_bound_seconds=accounted+remaining+reserve+finalization)
    require(set(index['budget']) == set(expected), 'Budget fields changed')
    for key, value in expected.items():
        core.close(index['budget'][key], value, 'Budget differs: '+key)
    require(expected['upper_bound_seconds'] <= resource['campaign_aggregate_seconds'] == 115200,
            'Shared aggregate allowance exceeded')
    return expected


def inspect_transition(index, prior, prior_rows, prior_review, result, report, current, policy):
    require(index['schema'] == 'joint_remaining_index_v1' and index['passed'] is False and
            index['scientific_completion'] is False, 'Terminal unknown was relabelled full scientific success')
    require(index['original_native'] == policy['original_native'] and
            index['immutable_failure_reference'] == policy['immutable_failure_reference'], 'Immutable predecessor changed')
    require(index['records'][:-1] == prior_rows, 'Prior compact records changed')
    require([row['case_id'] for row in index['records']] == policy['full_sequence'][:len(index['records'])],
            'New record is not the next untouched history')
    expected_old_attempts = prior.get('attempts', []) if prior.get('schema') == 'joint_remaining_index_v1' else []
    require(index['attempts'][:-1] == expected_old_attempts, 'Prior attempt accounting changed')
    source = index['records'][-1]['source']
    host = current.parent.parent
    require(source['kind'] == 'host_execution', 'New case has no host evidence locator')
    paths = dict(case_path=current/'science'/result['report_file'], trace_path=current/'science'/result['trace_file'],
                 result_path=current/'science/result.json', supervision_path=current/'supervision/result.json')
    for field, path in paths.items():
        require(source[field] == path.relative_to(host).as_posix() and
                source[field.replace('_path','_sha256')] == sha(path), 'New evidence locator differs: '+field)
    expected = projection(report, result['disposition'], source)
    if result['disposition'] == 'scientific_unknown':
        expected.update(unknown_origin='new_frozen_solver_cap', unknown_reason=result['unknown_reason'],
                        model_census=result['model_census'], terminal_solver_return=result['terminal_solver_return'])
    require(index['records'][-1] == expected, 'New compact projection differs from actual saved case')
    attempt = dict(case_id=result['case_id'], numerical_attempt_id=result['numerical_attempt_id'],
                   host_execution_id=source['execution_id'], seconds=result['wall_seconds'], result_sha256=sha(current/'science/result.json'))
    require(index['attempts'][-1] == attempt, 'New attempt identity/accounting differs')
    require(index['counts'] == expected_counts(index['records']), 'Completed/unknown/not-run counts differ')
    return inspect_budget(index, policy)


def inspect_host_origin(index, prior, prior_review, result, grant, policy):
    """Bind compact locators to genuine parent admission, not to copied strings."""
    require(grant['mode'] == 'remaining_host_batch', 'Missing parent host admission')
    group = next(row for row in policy['actual_hosts'] if row['host'] == grant['batch_id'])
    require(grant['case_ids'] == group['case_ids'] and result['case_id'] in group['case_ids'], 'Case not in admitted fixed host')
    position = group['case_ids'].index(result['case_id'])
    host_id = grant['numerical_attempt_id']
    require(index['records'][-1]['source']['execution_id'] == index['attempts'][-1]['host_execution_id'] == host_id,
            'New evidence is attributed to a different host execution')
    require(grant['child_attempt_ids'][result['case_id']] == result['numerical_attempt_id'], 'Unadmitted child numerical attempt')
    require(index['host_source_sha256'] == grant['source_sha256'] and
            index['scientific_source_sha256'] == grant['scientific_source_sha256'] and
            index['protocol_sha256'] == grant['protocol_sha256'], 'Parent admitted source identity differs')
    if position == 0:
        require(index['predecessor']['index_sha256'] == grant['prior_index_sha256'] and
                index['predecessor']['review_sha256'] == grant['prior_review_sha256'], 'Parent predecessor differs')
        if grant['batch_id'] == 1:
            ref = policy['immutable_failure_reference']
            require(prior.get('schema') != 'joint_remaining_index_v1' and
                    grant['prior_index_sha256'] == ref['index_sha256'] and
                    grant['prior_review_sha256'] == ref['review_sha256'], 'Initial pilot must use exact failed04 predecessor')
        else:
            require(prior_review.get('review_kind') == 'live_agent_saved_output_review' and
                    prior_review.get('live_agent_review') is True, 'A new host requires actual independent live prior-host review')
    else:
        require(prior['records'][-1]['case_id'] == group['case_ids'][position-1] and
                prior['records'][-1]['source']['execution_id'] == host_id and
                prior_review.get('review_kind') == 'automated_saved_output_check',
                'Within-host continuation lacks its preceding checked child')
    return group


def audit_saved(args):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    repo, current = Path(args.repo).resolve(), Path(args.current).resolve()
    prior_path, prior_review_path = Path(args.prior).resolve(), Path(args.prior_review).resolve()
    config_path = Path(args.config).resolve()
    config = read(config_path)
    policy = read(repo/'experiments/s04b_joint_remaining/protocol.json')
    science = read(repo/'experiments/s04b_joint_nuisance/protocol.json')
    require(policy['schema'] == 'joint_remaining_protocol_v1' and
            policy['case_ids'] == policy['full_sequence'][41:] and len(policy['case_ids']) == 39 and
            policy['full_sequence'][40] == UNKNOWN_CASE, 'Only the original39 untouched histories are admitted')
    require(sha(config_path) == policy['shared_run']['config_sha256'] and
            config['deadline_utc'] == policy['shared_run']['expires_utc'], 'Shared limits changed')
    require(sha(repo/'experiments/s04b_joint_nuisance/protocol.json') == policy['scientific_protocol_sha256'], 'Original science protocol changed')
    input_path = repo/'experiments/s04b_joint_nuisance/input_pins.json'
    require(sha(input_path) == science['input_pins_sha256'], 'Input manifest changed')
    for relative, pin in read(input_path).items():
        require(sha(safe(repo, relative)) == pin, 'Input changed: '+relative)
    checker_pins = verify_checker_review(repo, Path(args.checker_source_review), args.checker_source_review_sha256)
    result, report, unknown = inspect_current(current, repo, policy, science, config, args.commit, checker_pins)
    index = read(current/'index.json')
    prior, review = read(prior_path), read(prior_review_path)
    predecessor = index['predecessor']
    require(predecessor['index_sha256'] == sha(prior_path) and predecessor['review_sha256'] == sha(prior_review_path),
            'Predecessor acceptance hashes differ')
    if prior.get('schema') == 'joint_remaining_index_v1':
        require(review.get('passed') is True and review.get('audit_passed') is True and
                review['index_sha256'] == sha(prior_path), 'Unaccepted compact predecessor')
        if review.get('review_kind') == 'automated_saved_output_check':
            require(review.get('live_agent_review') is False and review.get('live_agent_review_performed') is False and
                    review.get('final_batch_agent_review_required') is True and
                    review.get('checker_sources_sha256') == checker_pins and
                    review.get('checker_source_review_sha256') == args.checker_source_review_sha256,
                    'Prior automated check was changed or misattributed')
        else:
            require(review.get('review_kind') == 'live_agent_saved_output_review' and review.get('live_agent_review') is True,
                    'Missing live prior-host review')
        require(prior['protocol_sha256'] == index['protocol_sha256'] and
                prior['host_source_sha256'] == index['host_source_sha256'] and
                prior['scientific_source_sha256'] == index['scientific_source_sha256'], 'Prior source/protocol identity changed')
        prior_rows = prior['records']
    else:
        prior_rows = initial_records(repo, policy, science, prior_path, prior_review_path)
    require(index['protocol_sha256'] == result['protocol_sha256'] and
            index['scientific_source_sha256'] == result['source_sha256'], 'Index source/protocol identity differs')
    conductor = read(current/'conductor_review.json')
    for relative, pin in index['host_source_sha256'].items():
        require(sha(safe(repo, relative)) == pin and conductor['reviewed_files_sha256'].get(relative) == pin,
                'Index host source changed: '+relative)
    require('experiments/s04b_joint_remaining/host.py' in index['host_source_sha256'], 'Host source missing')
    budget = inspect_transition(index, prior, prior_rows, review, result, report, current, policy)
    host_grant = read(current.parents[2]/'admission.json')
    inspect_host_origin(index, prior, review, result, host_grant, policy)
    require(host_grant['shared_run'] == policy['shared_run'] and
            host_grant['expires_utc'] == policy['shared_run']['expires_utc'], 'Parent extended shared execution limits')
    local_prior = prior_path.is_relative_to(current.parent.parent)
    require(index['predecessor']['archive_sha256'] == (None if local_prior else host_grant.get('prior_archive_sha256')) and
            index['predecessor']['artifact_id'] == (None if local_prior else host_grant.get('prior_artifact_id')),
            'Predecessor archive reference misrepresents a local child index')
    complete = {row['case_id']:row for row in index['records'] if row['disposition'] == 'complete'}
    summary = disposition_summary(index['records'], complete, policy['full_sequence'])
    return dict(schema='joint_remaining_independent_saved_output_check_v1', passed=True, audit_passed=True,
        disposition_valid=True, disposition=result['disposition'], scientific_passed=result['scientific_passed'],
        scientific_completion=False, original_full_success_gate_passed=False,
        review_kind='automated_saved_output_check', live_agent_review=False, live_agent_review_performed=False,
        final_batch_agent_review_required=True, index_sha256=sha(current/'index.json'),
        source_sha256=index['scientific_source_sha256'], host_source_sha256=index['host_source_sha256'],
        checker_sources_sha256=checker_pins, checker_source_review_sha256=args.checker_source_review_sha256,
        prior_index_sha256=sha(prior_path), prior_review_sha256=sha(prior_review_path),
        report_sha256=result['report_sha256'], trace_sha256=result['trace_sha256'],
        case_id=result['case_id'], counts=index['counts'], budget=budget,
        unknown_census=unknown, independent_summary=summary,
        all_histories_attempted=len(index['records']) == 80,
        numerical_calls=0, optimizer_calls=0,
        scope='Saved-output arithmetic and custody only; terminal unknowns remain unavailable comparisons.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo','current','prior','prior-review','config','commit','output',
                 'checker-source-review','checker-source-review-sha256'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    require(not output.exists(), 'Checker output must be fresh')
    try:
        result = audit_saved(args)
    except Exception as exc:
        result = dict(passed=False, audit_passed=False, disposition_valid=False,
                      scientific_passed=False, scientific_completion=False,
                      review_kind='automated_saved_output_check', live_agent_review=False,
                      live_agent_review_performed=False, final_batch_agent_review_required=True,
                      error_type=type(exc).__name__, error=str(exc), numerical_calls=0, optimizer_calls=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return 0 if result['audit_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
