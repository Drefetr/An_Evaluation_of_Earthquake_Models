"""Public single-case orchestration; all numerical work delegates to frozen code."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid
import zipfile

from . import REPO, PROFILE, ENTRYPOINT, read, sha, safe, require, verify_profile, source_identity, producer

THREAD_ENV = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')


def write(path, value):
    path = Path(path); temporary = path.with_name(path.name+'.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def positive(value, name):
    require(not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0, name+' must be finite and positive')
    return value


def platform_check(profile):
    expected = profile['supported_runtime']
    require(platform.system() == expected['system'] and platform.machine() == expected['architecture']
            and sys.byteorder == expected['byteorder'], 'Bundled native requires Linux x86_64 little-endian')
    require(platform.python_implementation() == expected['python_implementation']
            and list(sys.version_info[:2]) == expected['python_major_minor'], 'Use the documented CPython 3.13 runtime')


def package_check(profile, runtime):
    essential = runtime['essential']; expected = profile['supported_runtime']
    require(essential['numpy'] == expected['numpy'] and essential['scipy'] == expected['scipy'],
            'Install the pinned CPU NumPy/SciPy requirements')


def extract_native(profile, output):
    selected = profile['bundled_native']; archive = safe(REPO, selected['archive_reference']['path'])
    require(sha(archive) == selected['archive_reference']['sha256'], 'Bundled archive changed')
    folder = output/'native'; folder.mkdir(exist_ok=False)
    receipt = dict(selected, library_path='native/attenuation.so', build_receipt_path='native/build_receipt.json')
    with zipfile.ZipFile(archive) as source:
        for member_key, pin_key, path_key in [('library_member', 'library_sha256', 'library_path'),
                                               ('build_receipt_member', 'build_receipt_sha256', 'build_receipt_path')]:
            member = selected[member_key]; safe(output, member)
            require(source.namelist().count(member) == 1, 'Missing or duplicate native archive member')
            info = source.getinfo(member)
            require(not info.is_dir() and ((info.external_attr >> 16) & 0o170000) != 0o120000,
                    'Native archive member is not a regular file')
            data = source.read(member)
            require(hashlib.sha256(data).hexdigest() == selected[pin_key], 'Bundled native member changed')
            safe(output, receipt[path_key]).write_bytes(data)
    library = safe(output, receipt['library_path']); build = safe(output, receipt['build_receipt_path'])
    header = library.read_bytes()[:20]
    require(header[:6] == b'\x7fELF\x02\x01' and len(header) == 20
            and int.from_bytes(header[18:20], 'little') == 62, 'Bundled library is not Linux ELF64 x86_64')
    b = read(build)
    require(b['passed'] is True and b['library_sha256'] == receipt['library_sha256']
            and b['source_sha256'] == profile['core_source_sha256']['experiments/s04b_joint_nuisance/attenuation.cpp'],
            'Historical native build receipt differs')
    write(output/'bundled_native.json', receipt)
    return receipt, library, build


def plan(args, started, command):
    p = verify_profile(); platform_check(p)
    require(args.case_id in p['case_ids'], 'Case is not in the supplied original roster')
    wall = positive(args.wall_seconds, 'wall_seconds')
    require(wall > 30, 'Wall allowance must include the 30-second finalization reserve')
    rss = int(positive(args.rss_mib, 'rss_mib')*2**20)
    headroom = int(positive(args.headroom_mib, 'headroom_mib')*2**20)
    current = source_identity(); record = None; reference = None
    if args.execution_record is not None:
        record = read(args.execution_record)
        require(record['mode'] == 'exposure_refinement_case' and record['case_id'] == args.case_id
                and record['case_ids'] == [args.case_id] and record['source_sha256'] == current,
                'Author case/source identity differs')
        amendment = read(safe(REPO, p['amendment_protocol']['path']))
        slot = next(v for v in amendment['case_slots'] if v['case_id'] == args.case_id)
        require(slot['mode'] == 'untouched' and record['wall_seconds'] == wall == slot['wall_seconds']
                and record['scientific_seconds'] == wall-30 == slot['scientific_seconds'], 'Author slot changed')
        require(record['sampled_process_tree_rss_cap_bytes'] == rss == 6442450944
                and record['minimum_host_free_bytes'] == headroom == 2147483648, 'Author memory envelope changed')
        now = dt.datetime.now(dt.timezone.utc)
        require(now < dt.datetime.fromisoformat(record['expires_utc']) <= dt.datetime.fromisoformat(amendment['shared_run']['expires_utc']),
                'Author admission expired; no fallback to fresh mode')
        reference = record['reader_source_review']
        require(reference is not None, 'Author reader source review is required')
    identity = producer(reference)
    if record is not None:
        require(record['execution_producer'] == identity, 'Author execution producer differs')
    return dict(schema='joint_refined_cpu_request_v1', mode='author_envelope' if record is not None else 'fresh_local',
                case_id=args.case_id, output=str(args.output.resolve()), wall_seconds=wall, scientific_seconds=wall-30,
                rss_cap_bytes=rss, headroom_bytes=headroom, threads=2, workers=1, started_monotonic=started,
                created_utc=dt.datetime.now(dt.timezone.utc).isoformat(), attempt_id=str(uuid.uuid4()),
                source_sha256=current, execution_producer=identity, actual_command=command,
                execution_record=str(args.execution_record.resolve()) if record is not None else None,
                execution_record_sha256=sha(args.execution_record) if record is not None else None,
                verification_kind='automated_local_integrity', live_agent_review=False,
                scientific_completion=False)


def execute_case(request, profile, output, library, build, runtime, started, deadline):
    """Same numerical assembly for fresh and author modes; no likelihood/fit-loop copy."""
    from experiments.s04b_joint_execution import driver as legacy
    from experiments.s04b_joint_remaining import case_driver as classification
    from experiments.s04b_exposure_refinement.adapter import Adapter, same
    from threadpoolctl import threadpool_limits
    science = read(legacy.SCIENCE/'protocol.json')
    case = next(c for c in legacy.frozen.verify_inputs(science) if c['case_id'] == request['case_id'])
    modules = legacy.model.archived(); native = legacy.model.Native(library)
    adapter = Adapter(science, output, partial=None, trace=None)
    result = dict(schema='joint_refined_cpu_case_v1', case_id=request['case_id'], passed=False,
                  scientific_passed=False, handled=False, disposition_valid=False, scientific_completion=False,
                  disposition='technical_failure', status='running')
    try:
        (output/'cases').mkdir()
        with threadpool_limits(limits=2), legacy.OrderedChunkScheduler() as scheduler:
            runner = legacy.runner_with_scheduler(scheduler); factory = runner.model.phase_from_rows
            def phase_factory(rows, gm, start, end, modules, native, limit):
                return adapter.wrap_phase(factory(rows, gm, start, end, modules, native, limit), start, end)
            runner.model.phase_from_rows = phase_factory
            runner.fit_arm = adapter.fit_arm; runner.fine_check = adapter.fine_check
            original_floor = runner.historical_floor
            runner.historical_floor = lambda *values: adapter.historical_floor(original_floor, *values)
            report = runner.case_run(case, modules, native, science, output/'cases', deadline, None)
        path = output/'cases'/(case['case_id']+'.json')
        trace = output/'cases'/(case['case_id']+'.attempts.jsonl')
        durable = read(path); require(same(durable, report), 'Returned/durable case differs')
        report = durable  # Frozen serialization already normalizes NumPy scalars.
        require(not adapter.reuse_entries, 'Fresh reader cannot import author fits')
        reuse = dict(schema='joint_exposure_refinement_reuse_v1', mode='untouched', entries=[],
                     original_failure_reference=None, reused_optimizer_attempts=0,
                     prior_failed_total_start4_attempts_retained=0,
                     computation='Fresh fit; no author prefix or partial candidates imported')
        write(output/'reuse_map.json', reuse)
        amendment = dict(version=profile['numerical_version'], protocol_sha256=profile['amendment_protocol']['sha256'],
                         original_scientific_protocol_sha256=profile['scientific_protocol']['sha256'],
                         computation_kind='amended_untouched', reuse_map_sha256=sha(output/'reuse_map.json'),
                         refinement_event_log_sha256=sha(output/'refinement_events.jsonl'),
                         execution_calls_sha256=sha(output/'execution_calls.jsonl'), original_failure_reference=None)
        report['numerical_amendment'] = amendment
        report['execution_producer'] = request['execution_producer']; write(path, report)
        result.update(report_file='cases/'+path.name, report_sha256=sha(path), trace_file='cases/'+trace.name,
                      trace_sha256=sha(trace) if trace.exists() else None, numerical_amendment=amendment,
                      input_case=case, phase_constructions=adapter.phase_constructions)
        require(trace.exists(), 'No retained optimizer trace')
        disposition = classification.classify(report, case, science, classification.trace_records(trace), adapter.phase_constructions)
        if disposition['scientific_passed']:
            legacy.verify_case(report, {'case_id': case['case_id']}, case)
        result.update(disposition, handled=True, disposition_valid=True, status='terminal_disposition')
    except BaseException as exc:
        result.update(error_type=type(exc).__name__, error=str(exc), status='failed')
    finally:
        calls = adapter.receipt()
        result.update(adapter=calls, evaluation_census=calls['evaluation_census'],
                      refinement_census=dict(started=calls['refinement_started'], accepted=calls['refinement_accepted'], rejected=calls['refinement_rejected']),
                      actual_optimizer_attempts=len(calls['physical_optimizer_calls']), reused_optimizer_attempts=0)
    return result


def worker(request, output):
    result = dict(schema='joint_refined_cpu_case_v1', case_id=request['case_id'], passed=False, scientific_passed=False,
                  handled=False, disposition_valid=False, scientific_completion=False, disposition='technical_failure', status='preflight',
                  execution_mode=request['mode'], source_sha256=request['source_sha256'],
                  execution_producer=request['execution_producer'], actual_command=request['actual_command'],
                  reader_request_sha256=sha(output/'reader_request.json'))
    started = request['started_monotonic']; cap = request['scientific_seconds']; deadline = None
    write(output/'result.json', result)
    try:
        p = verify_profile(); platform_check(p)
        require(request['source_sha256'] == source_identity(), 'Reader source changed after planning')
        require(request['execution_producer'] == producer(request['execution_producer']['source_review']), 'Reader identity changed')
        for key in THREAD_ENV:
            os.environ[key] = '2'
        # Source map, native bytes and supported platform checked before science loads.
        native, library, build = extract_native(p, output)
        result.update(bundled_native=native, bundled_native_sha256=sha(output/'bundled_native.json'),
                      library_sha256=sha(library), build_receipt_sha256=sha(build),
                      protocol_sha256=p['amendment_protocol']['sha256'])
        from experiments.s04b_exposure_refinement import case_driver as dated
        from experiments.s04b_joint_execution import driver as legacy
        dated.verify_protocol(); legacy.verify_protocol()
        runtime = legacy.frozen.runtime_identity(); package_check(p, runtime)
        result['runtime'] = runtime
        deadline = started+cap
        if request['mode'] == 'author_envelope':
            path = Path(request['execution_record'])
            require(sha(path) == request['execution_record_sha256'], 'Author record changed after planning')
            args = SimpleNamespace(admission=path, case_id=request['case_id'], mode='untouched', library=library, build_receipt=build)
            current = dict(source_sha256=request['source_sha256'], protocol_sha256=p['amendment_protocol']['sha256'],
                           runtime=runtime, library_sha256=sha(library), build_receipt_sha256=sha(build))
            grant, slot, expiry = dated.admission(args, read(safe(REPO, p['amendment_protocol']['path'])), current)
            require(grant['reader_source_review'] == request['execution_producer']['source_review']
                    and grant['execution_producer'] == request['execution_producer'], 'Author execution producer differs')
            result.update(admission_sha256=sha(path), numerical_attempt_id=grant['numerical_attempt_id'], allocation=slot)
            deadline = min(deadline, time.monotonic()+(expiry-dt.datetime.now(dt.timezone.utc)).total_seconds())
        else:
            require(request['mode'] == 'fresh_local' and request['execution_record'] is None
                    and request['execution_producer']['source_review'] is None, 'Invalid local execution mode')
            result.update(numerical_attempt_id=request['attempt_id'], allocation={'wall_seconds': request['wall_seconds'], 'scientific_seconds': cap})
        require(time.monotonic() < deadline, 'Setup consumed the scientific clock')
        result.update(execute_case(request, p, output, library, build, runtime, started, deadline))
    except BaseException as exc:
        result.update(passed=False, scientific_passed=False, handled=False, disposition_valid=False,
                      disposition='technical_failure', status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        result['wall_seconds'] = time.monotonic()-started
        if result['wall_seconds'] > cap:
            result.update(passed=False, scientific_passed=False, handled=False, disposition_valid=False,
                          disposition='technical_failure', status='failed', scientific_clock_cap_exceeded=True)
        if deadline is not None and time.monotonic() >= deadline:
            result.update(passed=False, scientific_passed=False, handled=False, disposition_valid=False,
                          disposition='technical_failure', status='failed', finalization_deadline_exceeded=True)
        write(output/'result.json', result)
    return 0 if result['handled'] and result['disposition_valid'] else 1


def main(argv=None, process_started=None):
    started = time.monotonic() if process_started is None else process_started
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    fit = commands.add_parser('fit')
    fit.add_argument('--case-id', required=True); fit.add_argument('--output', type=Path, required=True)
    fit.add_argument('--execution-record', type=Path)
    for name in ('wall-seconds', 'rss-mib', 'headroom-mib'):
        fit.add_argument('--'+name, type=float, required=True)
    fit.add_argument('--plan-only', action='store_true')
    private = commands.add_parser('_worker', help=argparse.SUPPRESS); private.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    if args.operation == '_worker':
        require(os.environ.get('JOINT_REFINED_READER_REQUEST_SHA256') == sha(args.request), 'Worker request not supervised')
        request = read(args.request); return worker(request, Path(request['output']))
    output = args.output.resolve()
    require(not output.exists() and not output.is_relative_to(REPO), 'Use a fresh output outside the checkout')
    output.mkdir(parents=True)
    try:
        command = ([sys.executable]+list(sys.orig_argv[1:]) if argv is None
                   else [sys.executable, '-B', ENTRYPOINT]+list(argv))
        request = plan(args, started, command); write(output/'reader_request.json', request)
        if args.plan_only:
            write(output/'reader_result.json', {'status': 'planned_only', 'scientific_execution': False, 'source_sha256': request['source_sha256']})
            return 0
        if request['mode'] == 'author_envelope':
            # The genuine outer author supervisor owns the sole fixed wall clock.
            code = worker(request, output)
            write(output/'reader_result.json', dict(status='author_child_terminal', returncode=code,
                  scientific_result_sha256=sha(output/'result.json'), external_author_supervision_required=True,
                  live_agent_review=False, independent_output_acceptance=False))
            return code
        env = {key: '2' for key in THREAD_ENV}
        env['JOINT_REFINED_READER_REQUEST_SHA256'] = sha(output/'reader_request.json')
        remaining = request['wall_seconds']-(time.monotonic()-started)
        positive(remaining, 'remaining local wall allowance')
        spec = dict(command=[sys.executable, '-B', str(REPO/ENTRYPOINT), '_worker', str(output/'reader_request.json')],
                    cwd=str(REPO), output=str(output/'supervision'), env=env, wall_cap_seconds=remaining,
                    rss_cap_bytes=request['rss_cap_bytes'], host_headroom_bytes=request['headroom_bytes'], sample_seconds=.5)
        write(output/'supervisor_spec.json', spec)
        completed = subprocess.run([sys.executable, '-B', str(REPO/'scripts/supervise_research.py'), str(output/'supervisor_spec.json')], cwd=REPO)
        supervision = read(output/'supervision/result.json') if (output/'supervision/result.json').exists() else {}
        result = read(output/'result.json') if (output/'result.json').exists() else {}
        ok = completed.returncode == 0 and supervision.get('status') == 'passed' and supervision.get('survivors_after_cleanup') == [] and result.get('handled') is True and result.get('disposition_valid') is True
        write(output/'reader_result.json', dict(schema='joint_refined_cpu_terminal_v1', execution_passed=ok,
              scientific_passed=result.get('scientific_passed', False), scientific_completion=False,
              disposition=result.get('disposition', 'technical_failure'), live_agent_review=False,
              scope='Automated local execution/integrity; no independent scientific acceptance',
              scientific_result_sha256=sha(output/'result.json') if result else None,
              supervision_sha256=sha(output/'supervision/result.json') if supervision else None,
              request_sha256=sha(output/'reader_request.json'), wall_seconds=time.monotonic()-started))
        return 0 if ok else 1
    except BaseException as exc:
        write(output/'reader_result.json', dict(execution_passed=False, scientific_completion=False,
              error_type=type(exc).__name__, error=str(exc), live_agent_review=False))
        return 1
