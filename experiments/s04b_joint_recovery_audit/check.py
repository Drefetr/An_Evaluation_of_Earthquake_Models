"""Independent saved-output check for the explicit interrupted-optimizer recovery.

Only JSON, file bytes and scalar arithmetic are read. No experiment implementation,
likelihood, optimizer, generator, native library or producer summary is imported.
The unchanged independent case auditor checks the logical scientific result. The
additional checks below retain the failed physical attempt and account for the
replayed returns and restarted invocation separately.
"""
from pathlib import Path
import argparse
import datetime as dt
import json
import math
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from experiments.s04b_joint_audit import check as custody
from experiments.s04b_joint_nuisance_audit import audit as core

CHECKER_PATH = 'experiments/s04b_joint_recovery_audit/check.py'
CUSTODY_PATH = 'experiments/s04b_joint_audit/check.py'
CORE_PATH = 'experiments/s04b_joint_nuisance_audit/audit.py'
CUSTODY_SHA256 = '839c67fd3dca65294b457cb6511a66c1800fa422712fc13e302e4f4495ddaa13'
CORE_SHA256 = '47e38c68ff613f5dae1ac80da3713f03a673dc1a31553bf2a8ca3a27773231c3'
RECOVERY_PATH = 'experiments/s04b_joint_recovery/recovery_protocol.json'
read, sha, safe, require, AuditError = custody.read, custody.sha, custody.safe, custody.require, custody.AuditError


def exact(a, b, message):
    require(json.dumps(a, sort_keys=True, separators=(',', ':'), allow_nan=False) ==
            json.dumps(b, sort_keys=True, separators=(',', ':'), allow_nan=False), message)


def integer(value):
    require(type(value) is int and value >= 0, 'Nonnegative integer required')
    return value


def source_review(repo, path, pin):
    require(sha(path) == pin, 'Checker review bytes changed')
    review = read(path)
    require(review.get('passed') is True, 'Checker source review failed')
    pins = {CHECKER_PATH: sha(__file__), CUSTODY_PATH: CUSTODY_SHA256, CORE_PATH: CORE_SHA256}
    for relative, expected in pins.items():
        require(sha(safe(repo, relative)) == expected == review['reviewed_files_sha256'].get(relative),
                'Unreviewed checker dependency: ' + relative)
    return review, pins


def validate_review(review, index_pin, checker_pins, source_review_pin, *, pilot=False):
    require(review.get('passed') is True and review.get('index_sha256') == index_pin,
            'Prior review does not accept exact index')
    if review.get('review_kind') == 'automated_saved_output_check':
        require(not pilot, 'Standalone recovery pilot needs live independent review')
        require(review.get('live_agent_review') is False and review.get('live_agent_review_performed') is False
                and review.get('final_batch_agent_review_required') is True, 'Automated review attribution')
        require(review.get('checker_sources_sha256') == checker_pins and
                review.get('checker_source_review_sha256') == source_review_pin, 'Prior checker identity')
    else:
        require(review.get('reviewer') == '/root/continuation_cpu' and
                review.get('review_kind') == 'live_agent_saved_output_review' and
                review.get('live_agent_review') is True and
                not review.get('final_batch_agent_review_required', False), 'Genuine independent live review required')


def preserved_prefix(index, old, current, prior):
    require(index['cases'][:-1] == old['cases'] and index['attempts'][:-1] == old['attempts'],
            'Case or charged-attempt prefix changed')
    require(index['reviews'][:-1] == old['reviews'], 'Review prefix changed')
    for entry in old['cases']:
        for key in ('file', 'trace'):
            require(safe(current, entry[key]).read_bytes() == safe(prior, entry[key]).read_bytes(),
                    'Prior case/trace bytes changed')
    for entries in (old['attempts'], old['reviews']):
        for entry in entries:
            require(safe(current, entry['file']).read_bytes() == safe(prior, entry['file']).read_bytes(),
                    'Prior attempt/review bytes changed')
    for name in ('transition', 'training_resume', 'recovery_lineage'):
        directory = prior / name
        if directory.is_dir():
            for path in directory.rglob('*'):
                if path.is_file():
                    require(safe(current, path.relative_to(prior)).read_bytes() == path.read_bytes(),
                            'Carried lineage bytes changed')
    for relative, pin in old.get('recovery_execution_files', {}).items():
        require(sha(safe(current, relative)) == sha(safe(prior, relative)) == pin,
                'Prior physical recovery evidence changed')


def inspect_lineage(index, science, policy):
    p, transition = policy['predecessor'], index['recovery_transition']
    expected = {'recovery_lineage/failed_index.json': p['index_sha256'],
                'recovery_lineage/failed_case.json': p['case_sha256'],
                'recovery_lineage/failed_trace.jsonl': p['trace_sha256'],
                'recovery_lineage/failed_review.json': p['review_sha256'],
                'recovery_lineage/failed_result.json': p['result_sha256'],
                'recovery_lineage/failed_supervision.json': p['supervision_sha256'],
                'recovery_lineage/failed_admission.json': p['admission_sha256'],
                'recovery_lineage/failed_host.zip': p['archive_sha256']}
    require(transition['schema'] == 'joint_interrupted_optimizer_transition_v1' and
            transition['original_status'] == 'failed' and transition['files'] == expected,
            'Failed transition identity or evidence roster changed')
    require(transition['original_index_sha256'] == p['index_sha256'] and
            transition['protocol_sha256'] == index['recovery_protocol_sha256'] and
            transition['known_outer_overhead_seconds'] == p['known_outer_overhead_seconds'],
            'Recovery transition pins changed')
    for relative, pin in expected.items():
        require(sha(safe(science, relative)) == pin, 'Failed evidence bytes changed: ' + relative)
    failed = read(science / 'recovery_lineage/failed_index.json')
    disposition = read(science / 'recovery_lineage/failed_review.json')
    result = read(science / 'recovery_lineage/failed_result.json')
    require(disposition.get('passed') is False and disposition.get('audit_passed') is True and
            disposition.get('live_agent_review') is True and disposition['failed_index']['sha256'] == p['index_sha256'],
            'Failed attempt was relabelled as accepted')
    require(failed['last_attempt_passed'] is False and result['passed'] is False and
            len(failed['cases']) == 40 and len(failed['attempts']) == 41,
            'Original failed-prefix scope differs')
    require(index['cases'][:40] == failed['cases'] and index['attempts'][:41] == failed['attempts'] and
            index['reviews'][:len(failed['reviews'])] == failed['reviews'], 'Frozen failed prefix changed')
    require(failed['source_sha256'] == policy['predecessor_source_sha256'] and
            failed['budget']['total_seconds'] == p['original_index_charged_seconds'],
            'Original source/time charge differs')
    # The earlier training-only recovery remains a different, intact failure.
    original = index['original_failure']
    require(original == failed['original_failure'], 'Original training failure changed')
    require(index['transition'] == failed['transition'], 'Earlier allocation transition changed')
    for relative, pin in index['transition']['files'].items():
        require(sha(safe(science, relative)) == pin, 'Earlier allocation evidence changed')
    return failed


def inspect_charges(index, science, policy):
    p = policy['predecessor']
    entries = index['attempts']
    require(len(entries) == 41 + len(index['cases']) - 40, 'Recovery attempts/case count differs')
    require(len({v['attempt_id'] for v in entries}) == len(entries), 'Duplicate attempt charge')
    for position, entry in enumerate(entries):
        require(sha(safe(science, entry['file'])) == entry['sha256'], 'Attempt receipt changed')
        receipt = read(safe(science, entry['file']))
        require(receipt['attempt_id'] == entry['attempt_id'] and receipt['phase'] == entry['phase'] and
                receipt['wall_seconds'] == entry['seconds'] and math.isfinite(entry['seconds']) and entry['seconds'] >= 0,
                'Invalid charged attempt')
        if position == 40:
            require(receipt['passed'] is False and receipt['partial_case'] is not None,
                    'Original interrupted attempt disappeared')
        else:
            require(receipt['passed'] is True and receipt['status'] == 'batch_complete' and
                    receipt['partial_case'] is None, 'Unaccepted additional failed attempt')
        if position >= 41:
            slot = policy['fixed_slots'][position - 41]
            require(receipt['case_ids'] == [slot['case_id']] and receipt['phase'] == 'campaign' and
                    receipt['wall_seconds'] <= slot['wall_seconds'], 'Recovery slot/case/cap differs')
            require(receipt['source_sha256'] == index['source_sha256'] and
                    receipt['recovery_protocol_sha256'] == index['recovery_protocol_sha256'],
                    'Recovery charged source differs')
    total = math.fsum([index['original_failure']['prior_scientific_seconds'], *[v['seconds'] for v in entries]])
    pilot = math.fsum([index['original_failure']['prior_scientific_seconds'],
                      *[v['seconds'] for v in entries if v['phase'] == 'pilot']])
    core.close(total, index['budget']['total_seconds'], 'Total charge', 1e-8)
    core.close(pilot, index['budget']['pilot_seconds'], 'Original pilot charge', 1e-8)
    before = total - entries[-1]['seconds']
    remaining = sum(v['wall_seconds'] for v in policy['fixed_slots'][len(index['cases']) - 41:])
    bound = before + p['known_outer_overhead_seconds'] + remaining + 8*1800 + 1800
    require(bound <= 115200 and total <= 115200, 'Global recovery envelope exceeded')
    return {'total_seconds': total, 'pilot_seconds': pilot,
            'original_failed_attempt_seconds': entries[40]['seconds'],
            'known_outer_overhead_seconds': p['known_outer_overhead_seconds'],
            'conservative_remaining_admission_bound_seconds': bound,
            'past_unmeasured_workflow_overhead': 'unknown, not asserted zero'}


def counters(value):
    for key, row in value.items():
        require(len(key.split('|')) == 5, 'Unclassified physical evaluation')
        attempted = integer(row.get('attempted', 0))
        returned = integer(row.get('returned', 0))
        errors = integer(row.get('errors', 0))
        require(attempted == returned + errors, 'Physical evaluation balance')
    return value


def inspect_recovery_execution(science, report, policy):
    """Validate physical work separately; the original timeout is never removed."""
    original = read(science / 'recovery_lineage/failed_case.json')
    trace = [json.loads(line) for line in (science / 'recovery_lineage/failed_trace.jsonl').read_text().splitlines()]
    ends = {(v['model'], v['start_index'], v['method']): {k:x for k,x in v.items() if k not in ('event','model')}
            for v in trace if v['event'] == 'attempt_end'}
    require(len(trace) == 46 and len(ends) == 23, 'Original physical attempts differ')
    for arm in ('null', 'LI'):
        exact(report['fits'][arm], original['fits'][arm], 'Reused fit subtree changed')
        exact(report['training_checks'][arm], original['training_checks'][arm], 'Reused training check changed')
    arm = 'LIplus_immigrant'
    records = report['fits'][arm]['records']
    for start in range(5):
        actual = [r for r in records if r['start_index'] == start]
        require(len(actual) == 1, 'Completed optimizer repeated')
        exact(actual[0], ends[(arm, start, 'L-BFGS-B')], 'Replayed return changed')
    old_error = ends[(arm, 5, 'L-BFGS-B')]
    exact(next(r for r in records if (r['start_index'], r['method']) == (5, 'L-BFGS-B')),
          old_error, 'Original arithmetic failure payload changed')
    interrupted = ends[(arm, 5, 'Powell')]
    require(interrupted['error_type'] == 'TimeoutError' and interrupted['last_evaluation']['evaluation_count'] == 2040,
            'Original interrupted invocation changed')
    execution = read(science / 'recovery_execution.json')
    ledger = [json.loads(line) for line in (science / 'recovery_calls.jsonl').read_text().splitlines()]
    require(execution['schema'] == 'joint_partial_optimizer_recovery_calls_v1' and
            execution['exact_internal_optimizer_resume'] is False and execution['original_physical_attempts_retained'] == 23,
            'Recovery execution scope changed')
    require(execution['arm_calls'] == ['null','LI',arm,'LIplus_inclusive'] and
            execution['reused_complete_arms'] == ['null','LI'] and execution['replayed_successful_starts'] == list(range(5)),
            'Recovery reuse roster changed')
    exact(execution['original_interrupted_powell'], interrupted, 'Interrupted evidence changed')
    exact(execution['original_primary_error'], old_error, 'Original failure changed')
    require(execution['anchor_return_verified'] is True and execution['anchor_next_input_verified'] is True,
            'Unverified Powell anchors')
    require(ledger and ledger[0]['event'] == 'lineage' and ledger[0]['original_failed_physical_attempts'] == 23,
            'Missing physical lineage ledger')
    exact(ledger[0]['interrupted'], interrupted, 'Ledger failed invocation differs')
    reused = [v for v in ledger if v['event'] == 'reused_complete_arm']
    require([v['model'] for v in reused] == ['null','LI'] and all(v['optimizer_calls'] == 0 for v in reused),
            'Reused complete arms physically rerun')
    returns = [v for v in ledger if v['event'] == 'replayed_optimizer_return']
    require([v['start_index'] for v in returns] == list(range(5)), 'Replayed successful start roster')
    for v in returns:
        old = ends[(arm, v['start_index'], 'L-BFGS-B')]
        require(v['model'] == arm and v['method'] == 'L-BFGS-B' and v['actual_objective_calls'] == 0 and
                v['historical_nfev'] == old['nfev'] and v['historical_nit'] == old['nit'], 'False replay-call census')
    failures = [v for v in ledger if v['event'] == 'replayed_primary_error']
    require(len(failures) == 1 and failures[0]['actual_objective_calls'] == 0, 'Primary error replay count')
    exact(failures[0]['original_record'], old_error, 'Replayed error ledger differs')
    physical_starts = [v for v in ledger if v['event'] == 'physical_optimizer_start']
    physical_ends = [v for v in ledger if v['event'] == 'physical_optimizer_end']
    logical = [(m, r['start_index'], r['method']) for m in (arm,'LIplus_inclusive') for r in report['fits'][m]['records']]
    expected = [key for key in logical if not (key[0] == arm and (key[1] < 5 or key[1:] == (5,'L-BFGS-B')))]
    require([tuple(v) for v in execution['logical_optimizer_calls']] == logical, 'Logical invocation census differs')
    require([(v['model'],v['start_index'],v['method']) for v in physical_starts] == expected ==
            [(v['model'],v['start_index'],v['method']) for v in physical_ends], 'Physical invocation roster differs')
    for start, end in zip(physical_starts, physical_ends):
        key = (start['model'],start['start_index'],start['method'])
        saved = next(r for r in report['fits'][key[0]]['records'] if (r['start_index'],r['method']) == key[1:])
        exact(start['initial_parameters'], saved['initial_parameters'], 'New physical initial point changed')
        restart = key == (arm,5,'Powell')
        require(start['kind'] == end['kind'] == ('restarted_interrupted_invocation' if restart else 'new_optimizer_invocation'),
                'Physical restart misclassified')
        require(end['returned'] is (saved['status'] == 'returned'), 'Physical return disagrees with logical record')
        integer(end['completed_objective_returns'])
        if end['returned']:
            require(end['completed_objective_returns'] == saved['nfev'], 'Physical objective count differs from solver count')
        if restart:
            exact(start['options'], policy['recovery']['original_powell_options'], 'Powell restart budget changed')
            exact(start['initial_parameters'], interrupted['initial_parameters'], 'Powell restarted from last iterate')
            require(2041 <= end['completed_objective_returns'] <= 5000, 'Powell restarted prefix or cap differs')
        counters(end['actual_evaluations'])
    # Actual anchor payloads are retained, rather than relying solely on boolean assertions.
    anchors = [v for v in ledger if v['event'] == 'restart_return_anchor_verified']
    next_inputs = [v for v in ledger if v['event'] == 'restart_next_input_anchor_verified']
    require(len(anchors) == len(next_inputs) == 1 and anchors[0]['evaluation_count'] == 2040 and
            next_inputs[0]['evaluation_number'] == 2041, 'Anchor event roster differs')
    exact(anchors[0]['actual_evaluation'], {k:v for k,v in interrupted['last_evaluation'].items() if k != 'evaluation_count'},
          'Actual completed-return anchor differs')
    exact(next_inputs[0]['parameters'], interrupted['failed_evaluation_parameters'], 'Actual next-input anchor differs')
    counts = counters(execution['actual_evaluations'])
    physical_returns = {}
    for end in physical_ends:
        key=(end['model'],end['kind'])
        physical_returns[key]=physical_returns.get(key,0)+end['completed_objective_returns']
        for name,row in end['actual_evaluations'].items():
            require(name in counts and all(value <= counts[name].get(field,0) for field,value in row.items()),
                    'Cumulative physical counters regress')
    for (model,context),expected_returns in physical_returns.items():
        actual_returns=sum(row.get('returned',0) for key,row in counts.items()
                           if key.split('|')[1]==model and key.split('|')[3]==context)
        require(actual_returns==expected_returns, 'Final physical return counters disagree with optimizer ledger')
    require(report['recovery_provenance']['exact_internal_optimizer_resume'] is False and
            report['recovery_provenance']['original_partial_sha256'] == policy['predecessor']['case_sha256'] and
            report['recovery_provenance']['original_trace_sha256'] == policy['predecessor']['trace_sha256'],
            'Recovered report lost physical provenance')
    core.close(report['prior_training_attempt_seconds'],original['wall_seconds'],'Retained partial case time')
    core.close(report['wall_seconds'],report['current_attempt_wall_seconds']+original['wall_seconds'],
               'Recovered case cumulative wall time')
    return dict(original_physical_attempts=23, original_timeout_retained=True,
                reused_complete_fit_arms=2, replayed_completed_optimizer_returns=5, replayed_primary_errors=1,
                new_physical_optimizer_invocations=len(physical_starts), restarted_interrupted_invocations=1,
                actual_evaluations=counts, exact_internal_optimizer_resume=False,
                anchor_scope='The 2040th returned payload and next input match; unsaved intermediate evaluations are not independently established.')


def audit_saved(args):
    require(not sys.flags.optimize, 'Optimized Python is not admitted')
    repo, art, prior = map(lambda p: Path(p).resolve(), (args.repo,args.current,args.prior))
    science, prior_science = art/'science', prior/'science'
    require(bool(args.archive) == bool(args.archive_sha256), 'Archive/hash must be paired')
    if args.archive:
        custody.verify_archive(args.archive,args.archive_sha256,art)
    review, checker_pins = source_review(repo,args.checker_source_review,args.checker_source_review_sha256)
    conductor = read(art/'conductor_review.json')
    # Generic verifier checks each reviewed byte against both checkout and exact Git commit.
    require(conductor['reviewed_files_sha256'].get(CHECKER_PATH) == checker_pins[CHECKER_PATH], 'Recovery checker omitted from source map')
    custody.verify_reviewed_sources(repo,args.commit,conductor,review)
    config = read(args.config)
    policy = read(repo/RECOVERY_PATH)
    protocol = read(repo/'experiments/s04b_joint_nuisance/protocol.json')
    op = read(repo/'experiments/s04b_joint_execution/operational_protocol.json')
    index, result, admission = read(science/'index.json'), read(science/'result.json'), read(art/'admission.json')
    old = read(prior_science/'index.json')
    prior_review = read(args.prior_review)
    require(index['schema'] == 'joint_recovery_case_index_v2' and index['last_attempt_passed'] is True and
            index['partial_case'] is None and result['passed'] is True and result['status'] == 'batch_complete',
            'Failed or partial recovery cannot pass')
    require(sha(repo/RECOVERY_PATH) == index['recovery_protocol_sha256'] == result['recovery_protocol_sha256'] == admission['recovery_protocol_sha256'],
            'Recovery protocol identity differs')
    require(index['source_sha256'] == result['source_sha256'] == admission['source_sha256'], 'Recovery source identity differs')
    for path,pin in index['source_sha256'].items():
        require(sha(safe(repo,path)) == pin == conductor['reviewed_files_sha256'].get(path), 'Unreviewed recovery source: '+path)
    for path,pin in policy['predecessor_source_sha256'].items():
        require(sha(safe(repo,path)) == pin, 'Frozen scientific source changed')
    pins = read(repo/'experiments/s04b_joint_nuisance/input_pins.json')
    require(sha(repo/'experiments/s04b_joint_nuisance/input_pins.json') == protocol['input_pins_sha256'], 'Input manifest changed')
    for path,pin in pins.items():
        require(sha(safe(repo,path)) == pin, 'Scientific input changed: '+path)
    require(sha(repo/'experiments/s04b_joint_nuisance/protocol.json') == index['science_protocol_sha256'] == policy['scientific_protocol_sha256'], 'Science protocol changed')
    require(policy['shared_run']['config_sha256'] == sha(args.config) == admission['operational_run_config_sha256'] == conductor['operational_run_config_sha256'], 'Shared configuration changed')
    require(policy['shared_run']['run_id'] == config['run_id'] == admission['operational_run_id'] == conductor['operational_run_id'], 'Shared run differs')
    require(admission['mode'] == 'recovery_campaign' and admission['threads'] == 2 and admission['workers'] == 1, 'Recovery admission differs')
    require(admission['expires_utc'] == conductor['expires_utc'] and
            dt.datetime.fromisoformat(admission['expires_utc']) <= dt.datetime.fromisoformat(config['deadline_utc']), 'Expiry extended')
    require(policy['shared_run']['expires_utc'] == config['deadline_utc'], 'Protocol expiry changed')
    require(sha(prior_science/'index.json') == admission['prior_index_sha256'] and
            sha(args.prior_review) == admission['prior_review_sha256'], 'Prior admission identity differs')
    ids = [v['case_id'] for v in index['cases']]
    require(ids == policy['sequence'][:len(ids)] and 41 <= len(ids) <= 80 and len(ids) == len(set(ids)), 'Not exact original prefix')
    require(len(ids) == len(old['cases'])+1 and result['complete_cases'] == len(ids) and
            result['prior_case_count'] == len(old['cases']), 'Expected one new completed case')
    if len(old['cases']) == 40:
        require(sha(prior_science/'index.json') == policy['predecessor']['index_sha256'] and
                sha(args.prior_review) == policy['predecessor']['review_sha256'] and prior_review['passed'] is False and
                prior_review['audit_passed'] is True, 'Only exact reviewed failed predecessor is allowed')
    else:
        validate_review(prior_review,sha(prior_science/'index.json'),checker_pins,args.checker_source_review_sha256,pilot=len(old['cases'])==41)
    preserved_prefix(index,old,science,prior_science)
    carried = index['reviews'][-1]
    require(carried['sha256'] == sha(args.prior_review) and carried['accepted_index_sha256'] == sha(prior_science/'index.json') and
            safe(science,carried['file']).read_bytes() == Path(args.prior_review).read_bytes(), 'Carried exact disposition differs')
    failed = inspect_lineage(index,science,policy)
    charges = inspect_charges(index,science,policy)
    p = policy['predecessor']
    require(index['runtime'] == result['runtime'] and index['runtime']['essential'] == p['runtime_essential'] == old['runtime']['essential'], 'Original runtime changed')
    for key,path in (('library_sha256','build/attenuation.so'),('build_receipt_sha256','build/build_receipt.json')):
        require(index[key] == result[key] == admission[key] == p[key] == sha(art/path) == sha(prior/path), 'Original native/build changed')
    build = read(art/'build/build_receipt.json')
    require(build['passed'] is True and build['library_sha256'] == index['library_sha256'] and
            build['source_sha256'] == sha(repo/'experiments/s04b_joint_nuisance/attenuation.cpp'), 'Build receipt differs')
    slot = policy['fixed_slots'][len(ids)-41]
    require(result['requested_case'] == ids[-1] == slot['case_id'] and result['cases'] == [index['cases'][-1]] and
            admission['case_ids'] == conductor['case_ids'] == [ids[-1]] and admission['wall_seconds'] == slot['wall_seconds'], 'One-case fixed allocation changed')
    require(result['wall_seconds'] == index['attempts'][-1]['seconds'] and result['budget'] == index['budget'] and
            result['index_sha256'] == sha(science/'index.json') and result['admission_sha256'] == sha(art/'admission.json'), 'Result/index linkage differs')
    require(index['attempts'][-1]['attempt_id'] == admission['numerical_attempt_id'] == conductor['numerical_attempt_id'], 'Current attempt attribution differs')
    spec, supervision = read(art/'supervisor_spec.json'),read(art/'supervision/result.json')
    custody.verify_resource_spec(spec,conductor,admission,config)
    require(supervision['supervisor_sha256'] == sha(repo/'scripts/supervise_research.py') and
            supervision['spec_sha256'] == sha(art/'supervisor_spec.json') and supervision['execution_log_sha256'] == sha(art/'supervision/execution.log'), 'Supervision source/evidence differs')
    require(supervision['launched'] is True and supervision['status'] == 'passed' and supervision['returncode'] == 0 and
            supervision['stop_reason'] is None and not supervision['cleanup_errors'] and not supervision['survivors_after_cleanup'], 'Unclean/failed execution')
    require(result['wall_seconds'] <= supervision['execution_wall_seconds'] <= slot['wall_seconds'] and
            supervision['sampled_peak_tree_rss_bytes'] <= spec['rss_cap_bytes'] and
            supervision['minimum_sampled_host_available_bytes'] >= spec['host_headroom_bytes'], 'Resource gate failed')
    require(dt.datetime.fromisoformat(supervision['started_utc']) <= dt.datetime.fromisoformat(supervision['finished_utc']) <=
            dt.datetime.fromisoformat(admission['expires_utc']), 'Execution exceeded expiry')
    manifest = {v['case_id']:v for v in read(repo/'reproduction/synthetic/input_manifest.json')['s04b']['cases']}
    reports = []
    for position,entry in enumerate(index['cases']):
        report = read(safe(science,entry['file']))
        require(sha(safe(science,entry['file'])) == entry['sha256'] and
                sha(safe(science,entry['trace'])) == entry['trace_sha256'] == report['attempts_sha256'], 'Case/trace hash differs')
        require(entry['file'] == 'cases/'+ids[position]+'.json' and entry['trace'] == 'cases/'+ids[position]+'.attempts.jsonl', 'Case resource path differs')
        meta = manifest[ids[position]]
        for key in ('case_id','regime','seed','n_train','n_test'):
            require(report[key] == meta[key], 'Case/input metadata differs')
        core.inspect_case(report,protocol)
        core.inspect_trace(safe(science,entry['trace']),report)
        core.inspect_historical(report,meta,repo)
        expected_reused = 4 if position == 0 else 2 if position == 40 else 0
        require(entry['reused_fit_arms'] == expected_reused and entry['new_fit_arms'] == 4-expected_reused, 'Completed arm reuse census differs')
        reports.append(report)
    require(set(index['recovery_execution_files']) == {'recovery_calls.jsonl','recovery_execution.json'}, 'Physical evidence roster differs')
    for name,pin in index['recovery_execution_files'].items():
        require(sha(safe(science,name)) == pin, 'Physical evidence hash differs')
    require(reports[40]['recovery_provenance']['execution_files'] == index['recovery_execution_files'], 'Recovered case physical linkage differs')
    physical = inspect_recovery_execution(science,reports[40],policy)
    independent = core.aggregate(reports,protocol)
    counts = dict(completed_case_fit_arms=4*len(ids),completed_case_new_fit_arms=4*len(ids)-6,
                  completed_case_reused_fit_arms=6,completed_outcomes=5*len(ids))
    for key,value in counts.items():
        require(result[key] == value, 'Completed-work census differs: '+key)
    require(result['partial_fit_checkpoint'] is None and result['original_fixed_slot_status'] == 'failed', 'Original failure or partial classification changed')
    if len(ids)==80:
        require(result['scientific_completion'] is True and sha(science/'summary.json') == result['summary_sha256'], 'Missing full summary')
        core.compare_tree(read(science/'summary.json'),independent)
    else:
        require(result['scientific_completion'] is False, 'Partial prefix called complete')
    return dict(passed=True,review_kind='automated_saved_output_check',checker_author='/root/continuation_cpu',
        live_agent_review=False,live_agent_review_performed=False,final_batch_agent_review_required=True,
        index_sha256=sha(science/'index.json'),source_sha256=index['source_sha256'],source_commit=args.commit,
        artifact_sha256=args.archive_sha256,checker_sources_sha256=checker_pins,checker_source_review_sha256=args.checker_source_review_sha256,
        recovery_protocol_sha256=index['recovery_protocol_sha256'],prior_index_sha256=sha(prior_science/'index.json'),
        prior_review_sha256=sha(args.prior_review),complete_cases=len(ids),outcomes=5*len(ids),historical_floor_checks=6*len(ids),
        historical_comparison_rows=5*len(ids),verified_input_pins=len(pins),counts=counts,budget=index['budget'],
        resource_accounting=charges,physical_recovery=physical,attempt_census=core.attempt_census(reports,protocol),
        independent_summary=independent,scientific_completion=len(ids)==80,scientific_execution_in_audit=False,
        original_failed_attempt_passed=False,original_failed_index_sha256=policy['predecessor']['index_sha256'],
        supervision=dict(execution_wall_seconds=supervision['execution_wall_seconds'],sampled_peak_tree_rss_bytes=supervision['sampled_peak_tree_rss_bytes']),
        scope='Saved arithmetic and custody only; physical timeout remains retained separately from logical fit records. No likelihood/refit/generation calls.')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','current','prior','prior-review','config','commit','output','checker-source-review','checker-source-review-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--archive');parser.add_argument('--archive-sha256')
    args=parser.parse_args(argv);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        try:result=audit_saved(args)
        except Exception as error:
            result=dict(passed=False,review_kind='automated_saved_output_check',live_agent_review=False,
                        live_agent_review_performed=False,final_batch_agent_review_required=True,
                        scientific_execution_in_audit=False,error_type=type(error).__name__,error=str(error))
        stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(passed=result['passed'],receipt=str(output),receipt_sha256=sha(output))))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
