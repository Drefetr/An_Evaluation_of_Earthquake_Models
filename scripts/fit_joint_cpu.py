"""Public Linux CPU joint-fit runner; local checks are not independent review."""
from __future__ import annotations

import time
PROCESS_STARTED = time.monotonic()
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PUBLISHED = ROOT/'validation/reproductions/joint_nuisance_20261107/continuation'
SCOPE = 'Automated local integrity and numerical checks; no independent or external output acceptance.'
SCHEMA = 'fresh_joint_cpu_index_v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def safe(root, relative):
    name = PurePosixPath(relative)
    require(isinstance(relative, str) and '\\' not in relative and not name.is_absolute()
            and '..' not in name.parts and ':' not in relative, 'Unsafe relative artifact path')
    path = (Path(root)/relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), 'Artifact escapes its directory')
    return path


def context():
    from experiments.s04b_joint_execution import driver
    return driver


def scientific_identity():
    legacy = context()
    op, science = legacy.verify_protocol()
    pins = dict(legacy.source_identity())
    pins.update({(legacy.SCIENCE/name).relative_to(ROOT).as_posix(): pin
                 for name, pin in legacy.frozen.source_identity().items()})
    for name in ('scripts/fit_joint_cpu.py', 'scripts/supervise_research.py', 'requirements.txt',
                 'engine/cpu_build.py', 'engine/stage2_followup/native_build.py',
                 'tests/test_s04b_joint_nuisance.py', 'tests/test_joint_parallel_chunks.py'):
        pins[name] = sha(ROOT/name)
    return op, science, pins


def make_delegate(scheduler):
    """Use the reviewed facade, with the frozen scientific functions unchanged."""
    return context().runner_with_scheduler(scheduler)


def published_selection(name):
    require(re.fullmatch(r'budgeted[0-9]+', name) is not None, 'Use a published budgetedNN basename')
    archive = PUBLISHED/(name+'.zip')
    review_path = PUBLISHED/(name+'_independent_review.json')
    review = read(review_path)
    require(review.get('passed') is True and review['artifact_sha256'] == sha(archive),
            'Published review does not bind these ZIP bytes')
    from experiments.s04b_joint_budgeted import driver as budgeted
    policy = budgeted.verify_protocol()
    require(review['source_sha256'] == budgeted.source_identity(), 'Published scientific/driver source changed')
    with zipfile.ZipFile(archive) as source:
        require(len(source.namelist()) == len(set(source.namelist())), 'Duplicate ZIP members')
        raw = source.read('science/index.json')
        index = json.loads(raw)
        result = json.loads(source.read('science/result.json'))
        require(hashlib.sha256(raw).hexdigest() == review['index_sha256'] == result['index_sha256'],
                'Published index identity changed')
        require(result['passed'] is True and index['schema'] == budgeted.SCHEMA
                and index['partial_case'] is None, 'Published predecessor is incomplete')
        count = len(index['cases'])
        require([r['case_id'] for r in index['cases']] == policy['sequence'][:count]
                and 5 <= count < len(policy['sequence']), 'Published prefix is invalid or already complete')
        slot = policy['fixed_slots'][count-5]
        require(slot['case_id'] == policy['sequence'][count], 'Published next slot differs')
        failure_pin = read(budgeted.legacy.SCIENCE/'checkpoint_repair.json')['failed_archive_sha256']
        require(hashlib.sha256(source.read('original_failure.zip')).hexdigest() == failure_pin,
                'Original failed-pilot archive identity changed')
    reviews = []
    base = ROOT/'validation/reproductions/continuation_20261107'
    for filename in ('joint_budgeted_driver_source_review.json', 'parallel_scheduler_source_review.json'):
        path = base/filename
        record = read(path)
        require(record.get('passed') is True, 'Published source review did not pass')
        pins = record['source_sha256']
        if isinstance(pins, str):
            pins = {'experiments/s04b_joint_execution/parallel_chunks.py': pins}
        for relative, pin in pins.items():
            require(sha(safe(ROOT, relative)) == pin, 'Published source review pin changed: '+relative)
        reviews.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)})
    return dict(name=name, archive=archive.relative_to(ROOT).as_posix(), archive_sha256=sha(archive),
                review=review_path.relative_to(ROOT).as_posix(), review_sha256=sha(review_path),
                index_sha256=review['index_sha256'], case_id=slot['case_id'], slot=slot,
                source_reviews=reviews, policy_sha256=sha(budgeted.HERE/'allocation_protocol.json'),
                historical_expires_utc=policy['shared_run']['expires_utc'], original_failure_sha256=failure_pin)


def restore_published(selection, output):
    archive = safe(ROOT, selection['archive'])
    require(sha(archive) == selection['archive_sha256'], 'Published archive changed after planning')
    destination = output/'published'
    destination.mkdir()
    with zipfile.ZipFile(archive) as source:
        require(len(source.namelist()) == len(set(source.namelist())), 'Duplicate ZIP member')
        for entry in source.infolist():
            target = safe(destination, entry.filename.rstrip('/'))
            require((entry.external_attr >> 16) & 0o170000 != 0o120000, 'ZIP symlink is unsupported')
            if not entry.filename.startswith(('science/', 'build/')) or entry.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
        original = source.read('original_failure.zip')
        require(hashlib.sha256(original).hexdigest() == selection['original_failure_sha256'],
                'Restored original failure identity differs')
        (output/'original_failure.zip').write_bytes(original)
    require(sha(destination/'science/index.json') == selection['index_sha256'], 'Restored index changed')
    shutil.copyfile(archive, output/'published_previous.zip')
    shutil.copytree(destination/'build', output/'build')
    return destination


def positive(value, name, zero=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
            and (value >= 0 if zero else value > 0), name+' must be finite and positive')


def execution_record(path, request):
    """Optional genuine conductor record; never manufacture an agent review."""
    record = read(path)
    require(request['mode'] == 'published_continuation', 'Execution records apply only to dated continuation')
    require(record['case_ids'] == [request['published']['case_id']]
            and record['wall_cap_seconds'] == request['wall_seconds']
            and record['rss_cap_bytes'] == request['rss_cap_bytes']
            and record['host_headroom_bytes'] == request['headroom_bytes'], 'Conductor case/resource record differs')
    require(record['prior_archive_sha256'] == request['published']['archive_sha256']
            and record['prior_index_sha256'] == request['published']['index_sha256'], 'Conductor predecessor pin differs')
    require(re.fullmatch(r'[0-9a-f]{64}', record['operational_run_config_sha256']) is not None,
            'Conductor configuration identity is missing')
    # The configuration hash is supplied attribution; resource fields and all
    # actual source/input-manifest bytes are checked here. No private config path.
    pins = record['reviewed_files_sha256']
    from experiments.s04b_joint_budgeted import driver as budgeted
    required = {**request['source_sha256'], **budgeted.source_identity()}
    require(all(pins.get(name) == pin for name, pin in required.items()), 'Conductor record misses current source/input pins')
    for name, pin in pins.items():
        require(sha(safe(ROOT, name)) == pin, 'Conductor reviewed file changed: '+name)
    expires = dt.datetime.fromisoformat(record['expires_utc'])
    require(dt.datetime.now(dt.timezone.utc) < expires <= dt.datetime.fromisoformat(request['published']['historical_expires_utc']),
            'Conductor record expired or extends the original run')
    attempt = record['numerical_attempt_id']
    require(isinstance(attempt, str) and attempt and all(c.isalnum() or c == '-' for c in attempt),
            'Conductor numerical attempt identity is invalid')
    return record


def plan(args):
    op, science, pins = scientific_identity()
    mode = 'published_continuation' if args.continue_published else 'fresh'
    require(not(args.resume and args.continue_published), 'Fresh resume and published continuation are distinct')
    selection = published_selection(args.continue_published) if args.continue_published else None
    wall = args.wall_seconds
    if selection:
        require(args.phase == 'all' and args.max_cases is None and args.compiler is None,
                'Published continuation executes exactly its next fixed case and original library')
        if wall is None:
            wall = selection['slot']['wall_seconds']
        require(wall == selection['slot']['wall_seconds'] and args.rss_mib == 6144 and args.headroom_mib == 2048,
                'Published continuation must retain the exact fixed wall/RSS/headroom limits')
        require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(selection['historical_expires_utc']),
                'Dated published continuation expired; use fresh mode for a new execution')
    positive(wall, 'wall-seconds')
    positive(args.rss_mib, 'rss-mib')
    positive(args.headroom_mib, 'headroom-mib', True)
    if args.max_cases is not None:
        require(args.max_cases > 0, 'max-cases must be positive')
    request = dict(schema='joint_cpu_reader_request_v1', mode=mode, phase=args.phase,
                   output=str(args.output.resolve()), wall_seconds=wall,
                   rss_cap_bytes=int(args.rss_mib*1024**2), headroom_bytes=int(args.headroom_mib*1024**2),
                   threads=2, workers=1, compiler=args.compiler, max_cases=args.max_cases,
                   attempt_id=str(uuid.uuid4()), source_sha256=pins, sequence=op['sequence'],
                   pilot=science['pilot'], scope=SCOPE, verification_kind='automated_local_integrity',
                   resume=str(args.resume.resolve()) if args.resume else None, published=selection)
    if args.resume:
        request['resume_reader_sha256'] = sha(args.resume/'reader_result.json')
        request['resume_index_sha256'] = sha(args.resume/'science/index.json')
    if args.execution_record:
        record = execution_record(args.execution_record, request)
        request.update(execution_record=str(args.execution_record.resolve()),
                       execution_record_sha256=sha(args.execution_record), attempt_id=record['numerical_attempt_id'])
    return request


def run_controls(output):
    controls = []
    for pattern in ('test_s04b_joint_nuisance.py', 'test_joint_parallel_chunks.py'):
        log = output/(pattern+'.log')
        with log.open('w', encoding='utf-8') as stream:
            process = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                      '-p', pattern, '-v'], cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        controls.append(dict(test=pattern, returncode=process.returncode, log=log.name, sha256=sha(log)))
        write(output/'controls.json', controls)
        require(process.returncode == 0, 'Constructed numerical controls failed: '+pattern)
    return controls


def copy_fresh_prefix(request, output, cases, runtime):
    legacy = context()
    parent = Path(request['resume'])
    require(sha(parent/'reader_result.json') == request['resume_reader_sha256']
            and sha(parent/'science/index.json') == request['resume_index_sha256'], 'Fresh resume changed')
    terminal = read(parent/'reader_result.json')
    require(terminal.get('resume_eligible') is True, 'Prior run lacks a complete, quiescent local prefix')
    require(terminal['index_sha256'] == request['resume_index_sha256']
            and terminal['supervision_sha256'] == sha(parent/'supervision/result.json'), 'Resume terminal pins differ')
    supervision = read(parent/'supervision/result.json')
    require(supervision['status'] == 'passed' and supervision['survivors_after_cleanup'] == [],
            'Prior process was not successfully stopped')
    index = read(parent/'science/index.json')
    require(index['schema'] == SCHEMA and index['partial_case'] is None, 'Partial fits cannot automatically resume')
    require(index['source_sha256'] == request['source_sha256'] and index['sequence'] == request['sequence'],
            'Fresh scientific/reader source or roster changed')
    require(index['runtime']['essential'] == runtime['essential'], 'Own-run runtime changed')
    require([r['case_id'] for r in index['cases']] == request['sequence'][:len(index['cases'])],
            'Own-run cases are not the unique complete prefix')
    lookup = {c['case_id']: c for c in cases}
    for entry in index['cases']:
        require(entry['file'] == 'cases/'+entry['case_id']+'.json'
                and entry['trace'] == 'cases/'+entry['case_id']+'.attempts.jsonl', 'Own-run case path differs')
        report = read(safe(parent/'science', entry['file']))
        legacy.verify_case(report, entry, lookup[entry['case_id']])
        require(report['attempts_sha256'] == entry['trace_sha256'], 'Own-run trace pin differs')
        for field, pin in (('file', 'sha256'), ('trace', 'trace_sha256')):
            legacy.copy_bound(parent/'science', output/'science', entry[field], entry[pin])
    for entry in index['attempts']:
        legacy.copy_bound(parent/'science', output/'science', entry['file'], entry['sha256'])
        receipt = read(safe(output/'science', entry['file']))
        require(receipt['attempt_id'] == entry['attempt_id'] and receipt['wall_seconds'] == entry['seconds'],
                'Own-run elapsed attempt receipt differs')
    require(len({e['attempt_id'] for e in index['attempts']}) == len(index['attempts'])
            and math.fsum(e['seconds'] for e in index['attempts']) == index['charged_scientific_seconds'],
            'Own-run elapsed accounting changed')
    require(sha(parent/'build/build_receipt.json') == index['build_receipt_sha256'], 'Own-run build receipt changed')
    shutil.copytree(parent/'build', output/'build')
    library = output/'build/attenuation.so'
    require(sha(library) == index['library_sha256'], 'Own-run native bytes changed')
    return index, library


def execute_fresh(request, output, started, deadline):
    legacy = context()
    op, science = legacy.verify_protocol()
    cases = legacy.frozen.verify_inputs(science)
    runtime = legacy.frozen.runtime_identity()
    folder = output/'science'
    folder.mkdir()
    (folder/'cases').mkdir()
    result = dict(schema='fresh_joint_cpu_result_v1', passed=False, status='preflight', scope=SCOPE,
                  cases=[], scientific_completion=False, source_sha256=request['source_sha256'])
    write(folder/'result.json', result)
    index = None
    active = None
    try:
        if request['resume']:
            index, library = copy_fresh_prefix(request, output, cases, runtime)
        else:
            from engine.cpu_build import build_shared
            build = build_shared(legacy.SCIENCE/'attenuation.cpp', output/'build', legacy.SCIENCE, request['compiler'])
            library = Path(build['library'])
            index = dict(schema=SCHEMA, source_sha256=request['source_sha256'], sequence=op['sequence'],
                         runtime=runtime, library_sha256=sha(library),
                         build_receipt_sha256=sha(output/'build/build_receipt.json'),
                         cases=[], attempts=[], partial_case=None, charged_scientific_seconds=0., scope=SCOPE)
        result['controls'] = run_controls(output)
        target = science['pilot'] if request['phase'] == 'pilot' else op['sequence']
        require([r['case_id'] for r in index['cases']] == target[:len(index['cases'])]
                and len(index['cases']) < len(target), 'No remaining case in requested phase')
        todo = target[len(index['cases']):]
        if request['max_cases'] is not None:
            todo = todo[:request['max_cases']]
        result['requested_case_ids'] = todo
        write(folder/'index.json', index)
        modules = legacy.model.archived()
        native = legacy.model.Native(library)
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=2), legacy.OrderedChunkScheduler() as scheduler:
            delegate = make_delegate(scheduler)
            for name in todo:
                require(time.monotonic() < deadline, 'Fresh execution wall limit reached')
                active = name
                index['partial_case'] = {'case_id': name, 'status': 'running'}
                write(folder/'index.json', index)
                case = next(c for c in cases if c['case_id'] == name)
                report = delegate.case_run(case, modules, native, science, folder/'cases', deadline, None)
                path = folder/'cases'/(name+'.json')
                trace = folder/'cases'/(name+'.attempts.jsonl')
                entry = dict(case_id=name, file='cases/'+path.name, sha256=sha(path),
                             trace='cases/'+trace.name, trace_sha256=sha(trace) if trace.exists() else None,
                             new_fit_arms=4, reused_fit_arms=0)
                require(report['passed'] is True, 'Incomplete fit retained; no replacement or automatic partial restart')
                legacy.verify_case(report, entry, case)
                index['cases'].append(entry)
                result['cases'].append(entry)
                index['partial_case'] = None
                active = None
                write(folder/'index.json', index)
                write(folder/'result.json', result)
        require(time.monotonic() < deadline, 'Fresh batch finished after its wall limit')
        if len(index['cases']) == len(op['sequence']) == 80:
            result['summary_sha256'] = legacy.final_summary(index, science, folder, deadline)
            result['scientific_completion'] = True
        result.update(passed=True, status='batch_complete', complete_cases=len(index['cases']),
                      phase_complete=len(index['cases']) == len(target))
    except BaseException as exc:
        result.update(passed=False, status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        if index is not None:
            if active:
                path = folder/'cases'/(active+'.json')
                index['partial_case'] = dict(case_id=active, file='cases/'+path.name,
                                            sha256=sha(path) if path.exists() else None, status='incomplete')
            elapsed = time.monotonic()-started
            relative = 'attempts/'+request['attempt_id']+'.json'
            receipt = dict(attempt_id=request['attempt_id'], wall_seconds=elapsed, passed=result['passed'],
                           scope='This fresh worker including checks/build; outer supervision also records full process lifetime.',
                           requested_case_ids=result.get('requested_case_ids', []))
            write(folder/relative, receipt)
            index['attempts'].append(dict(attempt_id=request['attempt_id'], seconds=elapsed,
                                         file=relative, sha256=sha(folder/relative)))
            index['charged_scientific_seconds'] = math.fsum(e['seconds'] for e in index['attempts'])
            write(folder/'index.json', index)
            result['index_sha256'] = sha(folder/'index.json')
        if time.monotonic() >= deadline:
            result.update(passed=False, status='deadline_exceeded', scientific_completion=False)
        result['wall_seconds'] = time.monotonic()-started
        write(folder/'result.json', result)
    return 0 if result['passed'] else 1


def execute_published(request, output, started):
    from experiments.s04b_joint_budgeted import driver as budgeted
    selection = published_selection(request['published']['name'])
    require(selection == request['published'], 'Published selection changed after planning')
    restored = restore_published(selection, output)
    review_path = safe(ROOT, selection['review'])
    library = output/'build/attenuation.so'
    receipt = output/'build/build_receipt.json'
    policy = budgeted.verify_protocol()
    deadline = min(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=request['wall_seconds']-(time.monotonic()-started)),
                   dt.datetime.fromisoformat(selection['historical_expires_utc']))
    admission = dict(mode='budgeted_campaign', source_sha256=budgeted.source_identity(),
                     allocation_protocol_sha256=sha(budgeted.HERE/'allocation_protocol.json'),
                     independent_review_passed=True, scheduler_review_passed=True, external_supervision=True,
                     source_review_attribution=selection['source_reviews'], output_review_claim=False,
                     numerical_attempt_id=request['attempt_id'], expires_utc=deadline.isoformat(),
                     lease_token_sha256=hashlib.sha256(os.environ['JOINT_NUMERICAL_LEASE_TOKEN'].encode()).hexdigest(),
                     threads=2, workers=1, sampled_process_tree_rss_cap_bytes=request['rss_cap_bytes'],
                     library_sha256=sha(library), build_receipt_sha256=sha(receipt),
                     prior_index_sha256=sha(restored/'science/index.json'), prior_review_sha256=sha(review_path),
                     case_id=selection['case_id'], case_ids=[selection['case_id']], wall_seconds=request['wall_seconds'],
                     transition_review_sha256=policy['transition_review_sha256'],
                     scope='Inherited published source review only; this new output has no independent review.')
    if request.get('execution_record'):
        path = Path(request['execution_record'])
        require(sha(path) == request['execution_record_sha256'], 'Conductor record changed after planning')
        record = execution_record(path, request)
        shutil.copyfile(path, output/'conductor_review.json')
        admission.update(operational_run_id=record['operational_run_id'],
                         operational_run_config_sha256=record['operational_run_config_sha256'],
                         conductor_admission_sha256=sha(output/'conductor_review.json'))
        admission['expires_utc'] = min(deadline, dt.datetime.fromisoformat(record['expires_utc'])).isoformat()
    else:
        write(output/'local_integrity.json', dict(scope=SCOPE, live_agent_review=False,
              source_sha256=request['source_sha256'], source_review_attribution=selection['source_reviews'],
              numerical_attempt_id=request['attempt_id'], case_ids=[selection['case_id']],
              wall_cap_seconds=request['wall_seconds'], rss_cap_bytes=request['rss_cap_bytes'],
              host_headroom_bytes=request['headroom_bytes'], expires_utc=admission['expires_utc']))
    write(output/'admission.json', admission)
    args = argparse.Namespace(admission=output/'admission.json', library=library, build_receipt=receipt,
                              prior_index=restored/'science/index.json', prior_review=review_path,
                              output=output/'science')
    return budgeted.run(args, started=started)


def worker(request_path):
    started = PROCESS_STARTED
    request = read(request_path)
    require(os.environ.get('JOINT_READER_REQUEST_SHA256') == sha(request_path), 'Reader request identity changed')
    for relative, pin in request['source_sha256'].items():
        require(sha(safe(ROOT, relative)) == pin, 'Reader source changed: '+relative)
    output = Path(request['output'])
    deadline = started+request['wall_seconds']
    if request['mode'] == 'published_continuation':
        return execute_published(request, output, started)
    require(request['mode'] == 'fresh', 'Unknown execution mode')
    return execute_fresh(request, output, started, deadline)


def terminal(request, output, code):
    supervision_path = output/'supervision/result.json'
    science_path = output/'science/result.json'
    supervision = read(supervision_path) if supervision_path.is_file() else {}
    science = read(science_path) if science_path.is_file() else {}
    index_path = output/'science/index.json'
    index = read(index_path) if index_path.is_file() else {}
    index_pin = sha(index_path) if index_path.is_file() else None
    passed = (code == 0 and supervision.get('status') == 'passed'
              and supervision.get('survivors_after_cleanup') == [] and science.get('passed') is True
              and index_pin is not None and science.get('index_sha256') == index_pin)
    return dict(schema='joint_cpu_reader_terminal_v1', passed=passed, mode=request['mode'], scope=SCOPE,
                resume_eligible=passed and request['mode'] == 'fresh' and index.get('partial_case') is None,
                scientific_completion=passed and science.get('scientific_completion') is True,
                complete_cases=len(index.get('cases', [])), index_sha256=index_pin,
                science_result_sha256=sha(science_path) if science_path.is_file() else None,
                supervision_sha256=sha(supervision_path) if supervision_path.is_file() else None,
                request_sha256=sha(output/'request.json'), partial_outputs_retained=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--phase', choices=('pilot', 'all'), default='all')
    run.add_argument('--resume', type=Path)
    run.add_argument('--continue-published', metavar='budgetedNN')
    run.add_argument('--execution-record', type=Path, help='Optional genuine conductor record for dated continuation; copied unchanged')
    run.add_argument('--wall-seconds', type=float)
    run.add_argument('--rss-mib', type=float, default=6144)
    run.add_argument('--headroom-mib', type=float, default=2048)
    run.add_argument('--max-cases', type=int, help='Stop after this many new complete cases; never an all-80 completion claim')
    run.add_argument('--compiler')
    run.add_argument('--plan-only', action='store_true')
    child = commands.add_parser('_worker', help=argparse.SUPPRESS)
    child.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    if args.command == '_worker':
        return worker(args.request)
    output = args.output.resolve()
    require(not output.exists() and not output.is_relative_to(ROOT), 'Output must be a fresh directory outside the checkout')
    require(args.plan_only or sys.platform.startswith('linux'), 'Supervised execution requires Linux; plan-only is portable')
    request = plan(args)
    output.mkdir(parents=True)
    write(output/'request.json', request)
    if args.plan_only:
        print(json.dumps(dict(status='planned_only', scientific_execution=False, output=str(output))))
        return 0
    environment = {k: '2' for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')}
    environment.update(JOINT_READER_REQUEST_SHA256=sha(output/'request.json'), JOINT_NUMERICAL_LEASE_TOKEN=secrets.token_hex(24))
    wall = request['wall_seconds']
    if request['published']:
        wall = min(wall, (dt.datetime.fromisoformat(request['published']['historical_expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds())
    if request.get('execution_record'):
        wall = min(wall, (dt.datetime.fromisoformat(read(request['execution_record'])['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds())
    positive(wall, 'remaining wall allowance')
    spec = dict(command=[sys.executable, '-B', str(Path(__file__).resolve()), '_worker', str(output/'request.json')],
                cwd=str(ROOT), output=str(output/'supervision'), env=environment,
                wall_cap_seconds=wall, rss_cap_bytes=request['rss_cap_bytes'],
                host_headroom_bytes=request['headroom_bytes'], sample_seconds=.5)
    write(output/'supervisor_spec.json', spec)
    process = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/supervise_research.py'), str(output/'supervisor_spec.json')], cwd=ROOT)
    result = terminal(request, output, process.returncode)
    write(output/'reader_result.json', result)
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
