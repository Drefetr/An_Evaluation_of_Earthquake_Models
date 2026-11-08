"""One untouched history using the frozen scientific runner; no prefix copying.

Exit zero means a durable, explicitly classified disposition. A solver-budget
unknown remains passed=false; technical failures never count as that disposition.
"""
from __future__ import annotations
import time
PROCESS_STARTED = time.monotonic()
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from experiments.s04b_joint_execution import driver as legacy
from threadpoolctl import threadpool_limits
frozen, model = legacy.frozen, legacy.model
read, sha, write, require = legacy.read, legacy.sha, legacy.write, legacy.require
MODELS = ('null', 'LI', 'LIplus_immigrant', 'LIplus_inclusive')


def same(left, right):
    return legacy.checkpoint.dumps(left, sort_keys=True, separators=(',', ':')) == legacy.checkpoint.dumps(right, sort_keys=True, separators=(',', ':'))


def source_identity():
    pins = legacy.source_identity()
    pins.update({p.relative_to(REPO).as_posix(): sha(p) for p in sorted(legacy.SCIENCE.iterdir())
                 if p.is_file() and p.suffix in ('.py', '.cpp', '.json')})
    for p in (Path(__file__), HERE/'__init__.py', HERE/'protocol.json'):
        pins[p.relative_to(REPO).as_posix()] = sha(p)
    return pins


def verify_protocol():
    policy = read(HERE/'protocol.json')
    op, science = legacy.verify_protocol()
    require(policy['schema'] == 'joint_remaining_protocol_v1', 'Wrong remaining-case protocol')
    require(policy['scientific_protocol_sha256'] == sha(legacy.SCIENCE/'protocol.json'), 'Scientific protocol changed')
    require(policy['full_sequence'] == op['sequence'] and policy['case_ids'] == op['sequence'][41:]
            and len(policy['case_ids']) == len(set(policy['case_ids'])) == 39, 'Only the untouched remaining roster is eligible')
    require([r['case_id'] for r in policy['case_slots']] == policy['case_ids'], 'Remaining slot order changed')
    for slot in policy['case_slots']:
        cap = 2520 if slot['case_id'].startswith(('S4_', 'S6_')) else 1200
        require(slot['wall_seconds'] == cap and slot['scientific_seconds'] == cap-30, 'Original remaining slot changed')
    return policy


def trace_records(path):
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    require(len(rows) % 2 == 0, 'Incomplete optimizer trace')
    for start, end in zip(rows[::2], rows[1::2]):
        require(start['event'] == 'attempt_start' and end['event'] == 'attempt_end', 'Unpaired optimizer trace')
        require(all(start[k] == end[k] for k in ('model', 'start_index', 'method', 'initial_parameters')), 'Optimizer trace identity differs')
    return rows


def classify(report, case, science, trace, phase_constructions):
    """Classify only original successful results or finite exhausted-search returns."""
    require(report['case_id'] == case['case_id'], 'Wrong case result')
    require([(r['start'], r['end']) for r in phase_constructions] in
            [[(30, 395)], [(30, 395), (395, 760)]], 'Unexpected phase construction roster')
    require(all(r['returned'] is True for r in phase_constructions), 'Phase construction failed')
    fits = report['fits']
    attempted = list(fits)
    require(attempted == list(MODELS[:len(attempted)]), 'Scientific arm order differs')
    ends = [r for r in trace if r['event'] == 'attempt_end']
    expected = [dict(model=name, **record) for name in attempted for record in fits[name]['records']]
    actual = [{k: v for k, v in row.items() if k != 'event'} for row in ends]
    require(same(actual, expected), 'Case optimizer records differ from trace')
    census = dict(attempted_models=attempted,
                  completed_models=[name for name in attempted if fits[name]['passed'] is True],
                  not_run_models=list(MODELS[len(attempted):]),
                  logical_optimizer_returns=len(ends),
                  held_out_phase_constructed=len(phase_constructions) == 2)
    if report.get('passed') is True:
        require(report['status'] == 'complete' and attempted == list(MODELS)
                and report.get('training_selections_frozen') is True and len(report['outcomes']) == 5
                and census['held_out_phase_constructed'], 'Incomplete successful result')
        return dict(disposition='complete', scientific_passed=True, passed=True,
                    model_census=census, unknown_outcome_count=0)
    require(report.get('passed') is False and report['status'] == 'unknown'
            and report.get('error_type') == 'ValueError' and attempted, 'Not a frozen solver-budget unknown')
    name = attempted[-1]
    require(report.get('error') == ('Unresolved null starts' if name == 'null' else 'Unresolved alternative starts'),
            'Different scientific or technical failure')
    require(not report.get('training_selections_frozen', False) and not report['outcomes']
            and 'new_null_test' not in report and not report.get('test_checks')
            and 'test' not in report.get('plan_dimensions', {}) and not census['held_out_phase_constructed'],
            'Unknown training result contains held-out work')
    for previous in attempted[:-1]:
        arm = fits[previous]
        require(arm['passed'] is True and arm['status'] == 'complete'
                and arm['resolved_starts'] == [True]*8 and report['training_checks'][previous]['passed'] is True,
                'Earlier arm is not complete')
    arm = fits[name]
    require(arm['passed'] is False and arm['status'] == 'unknown_starts'
            and arm['required_starts'] == 8 and 'selected' not in arm and 'selected_state_index' not in arm,
            'Unknown arm contract changed')
    failed_start = len(arm['resolved_starts'])-1
    require(0 <= failed_start < 8 and arm['resolved_starts'] == [True]*failed_start+[False]
            and arm['not_run_starts'] == list(range(failed_start+1, 8)), 'Unknown start census differs')
    last = arm['records'][-1]
    require(last['start_index'] == failed_start and last['method'] == 'Powell'
            and last['status'] == 'returned' and last['success'] is False
            and last['solver_success'] is False and last['finite_feasible'] is True,
            'Unknown is not a finite unsuccessful original Powell return')
    limits = science['solver']['powell']
    require(type(last['nfev']) is int and type(last['nit']) is int
            and 0 < last['nfev'] <= limits['maxfev'] and 0 <= last['nit'] <= limits['maxiter']
            and ((last['solver_status'] == 1 and last['nfev'] == limits['maxfev'])
                 or (last['solver_status'] == 2 and last['nit'] == limits['maxiter'])),
            'Original Powell evaluation/iteration limit not established')
    fresh = abs(last['fresh_score']['nll']-last['returned_nll'])
    require(math.isfinite(fresh) and fresh <= 1e-9 and last['fresh_nll_delta'] == fresh,
            'Unsuccessful return fails original fresh-score check')
    box = frozen.bounds(science, name)
    require(len(last['returned_parameters']) == len(box) and len(last['parameters']) == len(last['gradient']) == 8
            and all(math.isfinite(v) for v in last['parameters']+last['gradient'])
            and all(math.isfinite(v) and lo <= v <= hi for v, (lo, hi) in zip(last['returned_parameters'], box))
            and same(last['parameters'][:len(box)], last['returned_parameters']), 'Nonfinite or infeasible terminal state')
    score = last['fresh_score']
    require(all(math.isfinite(score[k]) for k in ('P', 'E', 'C', 'M', 'joint', 'nll'))
            and score['E'] >= -1e-9 and score['C'] == -score['E']
            and score['joint'] == score['P']-score['E']+score['M'] and score['nll'] == -score['joint'],
            'Terminal score identity differs')
    require(len(arm['records']) >= 2 and arm['records'][-2]['start_index'] == failed_start
            and arm['records'][-2]['method'] == 'L-BFGS-B' and arm['records'][-2]['success'] is False,
            'Missing preceding original primary attempt')
    census.update(unresolved_model=name, unresolved_start=failed_start,
                  resolved_starts=arm['resolved_starts'], not_run_starts=arm['not_run_starts'])
    return dict(disposition='scientific_unknown', scientific_passed=False, passed=False,
                model_census=census, unknown_outcome_count=5, terminal_solver_return=last,
                unknown_reason=dict(error_type=report['error_type'], error=report['error'], arm_status=arm['status']))


def check_admission(args, policy, current):
    a = read(args.admission)
    require(a['mode'] == 'untouched_remaining_case' and a['case_id'] == args.case_id
            and a['case_ids'] == [args.case_id] and args.case_id in policy['case_ids'], 'Wrong admitted untouched case')
    require(a['source_sha256'] == current['source_sha256'] and a['protocol_sha256'] == current['protocol_sha256'], 'Source/protocol admission differs')
    require(a['independent_review_passed'] is True and a['external_supervision'] is True, 'Source review and external supervision required')
    require(a['operational_run_id'] == policy['shared_run']['run_id']
            and a['operational_run_config_sha256'] == policy['shared_run']['config_sha256'], 'Shared-run identity differs')
    expiry = datetime.datetime.fromisoformat(a['expires_utc'])
    require(datetime.datetime.now(datetime.timezone.utc) < expiry <= datetime.datetime.fromisoformat(policy['shared_run']['expires_utc']), 'Expired admission')
    slot = next(r for r in policy['case_slots'] if r['case_id'] == args.case_id)
    require(a['wall_seconds'] == slot['wall_seconds'], 'Admitted fixed slot differs')
    require(a['threads'] == 2 and a['workers'] == 1 and a['sampled_process_tree_rss_cap_bytes'] == 6442450944
            and a['minimum_host_free_bytes'] == 2147483648, 'Resource admission differs')
    token = os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN', '')
    require(token and hashlib.sha256(token.encode()).hexdigest() == a['lease_token_sha256'], 'Numerical lease attestation differs')
    original = policy['original_native']
    require(current['runtime']['essential'] == original['runtime_essential'], 'Original essential runtime differs')
    for key in ('library_sha256', 'build_receipt_sha256'):
        require(current[key] == original[key] == a[key], 'Original native/build bytes differ')
    build = read(args.build_receipt)
    require(build['passed'] is True and build['source_sha256'] == sha(legacy.SCIENCE/'attenuation.cpp')
            and build['library_sha256'] == current['library_sha256'], 'Original build provenance differs')
    return a, slot


def run(args, started=None):
    started = PROCESS_STARTED if started is None else started
    out = Path(args.output).resolve()
    require(not out.is_relative_to(REPO) and not out.exists(), 'Fresh external output directory required')
    out.mkdir(parents=True);(out/'cases').mkdir()
    result = dict(schema='joint_remaining_case_result_v1', case_id=args.case_id, passed=False,
                  scientific_passed=False, handled=False, disposition_valid=False,
                  disposition='technical_failure', status='preflight', phase_constructions=[])
    write(out/'result.json', result)
    deadline = None
    try:
        policy = verify_protocol();science = read(legacy.SCIENCE/'protocol.json')
        current = dict(source_sha256=source_identity(), protocol_sha256=sha(HERE/'protocol.json'),
                       runtime=frozen.runtime_identity(), library_sha256=sha(args.library),
                       build_receipt_sha256=sha(args.build_receipt))
        result.update(current, admission_sha256=sha(args.admission))
        admission, slot = check_admission(args, policy, current)
        result.update(numerical_attempt_id=admission['numerical_attempt_id'], allocation=slot,
                      immutable_failure_reference=policy['immutable_failure_reference'])
        deadline = min(started+slot['wall_seconds'], time.monotonic()+
            (datetime.datetime.fromisoformat(admission['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        cases = frozen.verify_inputs(science)
        case = next(r for r in cases if r['case_id'] == args.case_id)
        result['input_case'] = case
        modules = model.archived();native = model.Native(args.library)
        require(deadline-time.monotonic() >= slot['scientific_seconds'], 'Startup consumed fixed scientific reservation')
        scientific_deadline = min(deadline, time.monotonic()+slot['scientific_seconds'])
        with threadpool_limits(limits=2), legacy.OrderedChunkScheduler() as scheduler:
            delegate = legacy.runner_with_scheduler(scheduler)
            factory = delegate.model.phase_from_rows
            def observed_factory(rows, gm, start, end, modules, native, deadline=math.inf):
                entry = dict(start=start, end=end, returned=False)
                result['phase_constructions'].append(entry);write(out/'result.json', result)
                phase = factory(rows, gm, start, end, modules, native, deadline)
                entry['returned'] = True;write(out/'result.json', result)
                return phase
            delegate.model.phase_from_rows = observed_factory
            result['status'] = 'running';write(out/'result.json', result)
            report = delegate.case_run(case, modules, native, science, out/'cases', scientific_deadline, None)
        path = out/'cases'/(args.case_id+'.json');trace = out/'cases'/(args.case_id+'.attempts.jsonl')
        require(path.is_file() and same(read(path), report), 'Returned case differs from durable original bytes')
        result.update(report_file='cases/'+path.name, report_sha256=sha(path),
                      trace_file='cases/'+trace.name, trace_sha256=sha(trace) if trace.exists() else None,
                      original_case_status=report['status'],
                      original_case_error={k:report[k] for k in ('error_type','error') if k in report})
        require(trace.exists(), 'No optimizer trace; primary failure is retained in the case report')
        disposition = classify(report, case, science, trace_records(trace), result['phase_constructions'])
        if disposition['scientific_passed']:
            legacy.verify_case(report,dict(case_id=args.case_id),case)
        result.update(disposition, handled=True, disposition_valid=True, status='terminal_disposition')
    except BaseException as exc:
        result.update(passed=False, scientific_passed=False, handled=False, disposition_valid=False,
                      disposition='technical_failure', status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        result['wall_seconds'] = time.monotonic()-started
        write(out/'result.json', result)
        if deadline is not None and time.monotonic() >= deadline:
            result.update(passed=False, scientific_passed=False, handled=False, disposition_valid=False,
                          disposition='technical_failure', status='failed', finalization_deadline_exceeded=True)
            result['wall_seconds'] = time.monotonic()-started;write(out/'result.json', result)
    return 0 if result['handled'] and result['disposition_valid'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-id', required=True)
    for name in ('library', 'build-receipt', 'admission', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
