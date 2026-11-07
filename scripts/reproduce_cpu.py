"""Offline Linux reader entry point for frozen selected-state score replays.

Builds and evaluations run inside one externally supervised resource envelope.
Local integrity checks are not independent scientific acceptance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'reproduction/score_replay'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scripts'))
from run_continuation import materialize_fresh_scores

# Registry family, relative registry, build module, evaluation module.
ROUTES = {
    'cached': ('cached', 'cached_registry.json', 'build', 'replay'),
    'cached_supplement': ('cached', 'cached_supplement/cached_registry.json', 'build', 'replay'),
    'productivity_profiles': ('cached', 'productivity_profiles/cached_registry.json', 'build', 'replay'),
    'california': ('cached', 'california/registry.json', 'build', 'replay'),
    'california_benchmark': ('cached', 'california_benchmark/registry.json', 'build', 'replay'),
    'jma': ('regional', 'jma/registry.json', 'regional_build', 'regional_replay'),
    's03': ('regional', 's03/registry.json', 'regional_build', 'regional_replay'),
    's06_ca': ('regional', 's06_ca/registry.json', 'regional_build', 'regional_replay'),
    'original_li': ('li', 'original_li/registry.json', 'li_replay', 'li_replay'),
    's04_original': ('inhibition', 's04_original/registry.json', 'inhibition_build', 'inhibition_replay'),
    'california_blocks': ('blocks', 'california_blocks/registry.json', 'california_blocks_replay', 'california_blocks_replay'),
    'observed_fixedbackbone': ('observed', 'observed_fixedbackbone/registry.json', None, 'observed_replay'),
    's02': ('cases', 's02/protocol.json', 's02_replay', 's02_replay'),
    'initial_mark': ('cases', 'initial_mark/protocol.json', 'initial_mark_replay', 'initial_mark_replay'),
}
PUBLISHED = ROOT/'validation/reproductions/score_replay_20261107'
CLAIM_SCOPE = ('Automated local identity and numerical comparisons only. Published source/output '
               'reviews remain separately attributed; this run is not independent scientific acceptance.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def require(value, message):
    if not value: raise ValueError(message)


def inside(root, relative):
    path = (root/relative).resolve()
    require(not Path(relative).is_absolute() and path.is_relative_to(root.resolve()) and path != root.resolve(), 'Nonportable path')
    return path


def route_files(route):
    family, relative, builder, runner = ROUTES[route]
    registry = PACKAGE/relative
    proposal = registry.parent/('cached_pilot_proposal.json' if route == 'cached' else 'pilot_proposal.json')
    return family, registry, proposal, builder, runner


def result_archive_members(member):
    """Keep the declared ZIP prefix; never normalize or relocate its bytes."""
    require(isinstance(member, str) and member and '\\' not in member
            and ':' not in member and '\x00' not in member, 'Invalid science-result archive member')
    parts = member.split('/')
    require(all(part not in ('', '.', '..') for part in parts)
            and len(parts) >= 2 and parts[-2:] == ['science', 'result.json'],
            'Science-result member must be an exact portable science/result.json path')
    path = PurePosixPath(member)
    require(not path.is_absolute() and path.as_posix() == member, 'Noncanonical archive member')
    admission = (path.parent.parent/'admission.json').as_posix()
    return member, admission


def published_review(route, phase='pilot'):
    """Bind a local ZIP to an actual published review, without inventing one."""
    archive = PUBLISHED/route/(phase+'.zip')
    require(archive.is_file(), 'Published local execution ZIP is absent: '+str(archive))
    archive_hash = sha(archive)
    reviews = []
    index_pin = None
    index_path = PUBLISHED/'accepted_execution_index.json'
    index_result_hash = None
    result_member, admission_member = result_archive_members('science/result.json')
    if index_path.is_file():
        index = read(index_path)
        matches = [r for r in index['entries'] if r['route'] == route and r['phase'] == phase]
        require(len(matches) <= 1, 'Duplicate acceptance-index route/phase')
        if matches:
            entry = matches[0]
            require(entry.get('passed') is True and entry['archive'] == archive.relative_to(ROOT).as_posix()
                    and entry['archive_sha256'] == archive_hash, 'Acceptance-index archive mismatch')
            review_path = inside(ROOT, entry['review_path'])
            require(sha(review_path) == entry['review_sha256'], 'Acceptance-index review changed')
            review = read(review_path)
            require(review.get('passed') is True or review.get('status') in (
                'passed_independent_output_review', 'passed_independent_complete_registry_output_audit'), 'Referenced review is not passed')
            reviews.append(dict(path=entry['review_path'], sha256=entry['review_sha256'], scope=review.get('scope')))
            index_result_hash = entry['science_result_sha256']
            result_member, admission_member = result_archive_members(entry.get('science_result_member', 'science/result.json'))
            index_pin = dict(path=index_path.relative_to(ROOT).as_posix(), sha256=sha(index_path),
                             scope=index.get('scope', 'Published archive/review custody index'))
    for path in sorted((PUBLISHED/route).glob('*.json')):
        review = read(path)
        accepted = review.get('passed') is True or review.get('status') in (
            'passed_independent_output_review', 'passed_independent_complete_registry_output_audit')
        if accepted and review.get('artifact_sha256') == archive_hash:
            reviews.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), scope=review.get('scope')))
    require(reviews, 'No passed published review pins these archive bytes')
    with zipfile.ZipFile(archive) as source:
        require(len(source.namelist()) == len(set(source.namelist())), 'Duplicate archive member')
        require(result_member in source.namelist(), 'Declared science-result archive member is absent')
        result_bytes = source.read(result_member)
        result_hash = hashlib.sha256(result_bytes).hexdigest()
        require(index_result_hash is None or index_result_hash == result_hash, 'Acceptance-index result mismatch')
        result = json.loads(result_bytes)
        require(result.get('passed') is True, 'Published science result failed')
        for item in reviews:
            record = read(ROOT/item['path'])
            if 'result_sha256' in record:
                require(record['result_sha256'] == result_hash, 'Published result/review pin mismatch')
        admission = json.loads(source.read(admission_member)) if admission_member in source.namelist() else None
    return dict(archive=archive.relative_to(ROOT).as_posix(), sha256=archive_hash,
                reviews=reviews, acceptance_index=index_pin, result_sha256=result_hash,
                science_result_member=result_member, admission_member=admission_member if admission is not None else None,
                result=result, admission=admission)


def evidence_inventory():
    """Report retained outcomes separately from available implementation."""
    rows = []
    for route in ROUTES:
        family, path, proposal, _, _ = route_files(route)
        data = read(path)
        item = dict(route=route, source_available=True, registry=path.relative_to(ROOT).as_posix(),
                    registry_sha256=sha(path), declared_units=len(data['roster'] if family == 'cases' else data['rows']),
                    units='catalogues' if family == 'cases' else 'registry rows', executions=[])
        for archive in sorted((PUBLISHED/route).glob('*.zip')):
            try:
                record = published_review(route, archive.stem)
                actual = record['result']
                item['executions'].append(dict(archive=record['archive'], sha256=record['sha256'],
                    published_review_pins_pass=True, actual_mode=actual.get('mode'),
                    actual_requested_rows=actual.get('requested_rows'), actual_passed_rows=actual.get('passed_rows'),
                    actual_catalogues=actual.get('catalogues'), actual_full_complete=actual.get('full_complete'),
                    result_sha256=record['result_sha256'],science_result_member=record['science_result_member']))
            except (ValueError, KeyError) as exc:
                item['executions'].append(dict(archive=archive.relative_to(ROOT).as_posix(), sha256=sha(archive),
                                                published_review_pins_pass=False, reason=str(exc)))
        item['coverage_status'] = 'retained execution records; see their exact rosters' if item['executions'] else 'no published execution located'
        rows.append(item)
    return dict(scope=CLAIM_SCOPE, routes=rows, table_inventory='reproduction/score_replay/coverage_plan.json',
                table_rule='A passed row does not by itself establish every manuscript table. Table links and retained table_deltas are separate evidence.')


def make_plan(args):
    family, registry_path, proposal_path, builder, runner = route_files(args.route)
    registry = read(registry_path)
    case_route = family == 'cases'
    proposal = registry if case_route else read(proposal_path)
    roster = registry['roster'] if case_route else [r['id'] for r in registry['rows']]
    pilot = proposal['pilot'] if case_route else proposal['row_ids']
    require(roster and len(roster) == len(set(roster)), 'Registry roster is not unique')
    require(all(x in roster for x in pilot) and len(pilot) == len(set(pilot)), 'Invalid frozen pilot')
    require(not case_route or args.phase in ('pilot', 'completion'), 'Case routes require pilot or reviewed-pilot completion')
    selected = pilot if args.phase == 'pilot' else [r for r in roster if r not in pilot] if args.phase == 'completion' else roster
    if args.rows:
        require(not case_route and args.phase == 'subset', '--rows requires a registry route and --phase subset')
        selected = read(args.rows)
    require(args.phase != 'subset' or args.rows is not None, 'Subset requires an explicit ordered JSON row list')
    require(isinstance(selected, list) and selected and len(set(selected)) == len(selected) and set(selected) <= set(roster), 'Invalid requested roster')
    for name in ('wall_seconds', 'rss_mib', 'headroom_mib'):
        value = getattr(args, name)
        require(not isinstance(value, bool) and math.isfinite(value) and value > 0, 'Finite positive '+name+' required')
    caps = proposal['resources'] if case_route else proposal['caps']
    max_rss = caps['sampled_rss_cap_bytes'] if case_route else caps['process_tree_rss_bytes']
    min_head = caps.get('minimum_headroom_bytes', 2*2**30) if case_route else caps['minimum_host_available_bytes']
    require(args.rss_mib*2**20 <= max_rss and args.headroom_mib*2**20 >= min_head, 'Requested memory bounds exceed frozen envelope')
    if args.phase == 'pilot':
        require(args.wall_seconds <= caps['pilot_wall_cap_seconds' if case_route else 'wall_seconds'], 'Pilot exceeds frozen wall cap')
    if case_route:
        require(args.rss_mib*2**20 == max_rss and args.wall_seconds <= caps[args.phase+'_wall_cap_seconds'], 'Case resource contract changed')
    pins = {registry_path.relative_to(ROOT).as_posix(): sha(registry_path),
            'scripts/reproduce_cpu.py': sha(Path(__file__)), 'scripts/supervise_research.py': sha(ROOT/'scripts/supervise_research.py'),
            'scripts/run_continuation.py': sha(ROOT/'scripts/run_continuation.py')}
    if builder:
        for name in ('engine/cpu_build.py', 'engine/stage2_followup/native_build.py'):
            pins[name] = sha(ROOT/name)
    inherited = None
    if case_route:
        inherited = published_review(args.route)
        pins[inherited['archive']] = inherited['sha256']
        for item in inherited['reviews']: pins[item['path']] = item['sha256']
        if inherited['acceptance_index']:
            item = inherited['acceptance_index']; pins[item['path']] = item['sha256']
        prior_admission = inherited['admission']
        require(prior_admission and prior_admission.get('independent_review_passed') is True, 'Published source admission absent')
        for name, expected in prior_admission['source_sha256'].items():
            require(sha(inside(ROOT, name)) == expected, 'Published source identity changed: '+name)
            pins[name] = expected
    else:
        require(proposal['registry_sha256'] == sha(registry_path), 'Proposal/registry identity mismatch')
        manifest = registry_path.parent/'input_manifest.json'
        require(proposal['input_manifest_sha256'] == sha(manifest), 'Proposal/input identity mismatch')
        pins[manifest.relative_to(ROOT).as_posix()] = sha(manifest)
        pins[proposal_path.relative_to(ROOT).as_posix()] = sha(proposal_path)
        for name, expected in proposal['source_sha256'].items():
            path = inside(PACKAGE, name)
            require(sha(path) == expected, 'Frozen source changed: '+name)
            pins[path.relative_to(ROOT).as_posix()] = expected
    pilot_reuse = None
    if case_route and args.phase == 'completion':
        require(args.pilot_output and args.pilot_review, 'Completion requires --pilot-output and a separately authored --pilot-review')
        prior = args.pilot_output.resolve()
        review = read(args.pilot_review)
        require(read(prior/'reader_result.json').get('passed') is True
                and read(prior/'supervision/result.json').get('status') == 'passed', 'Local pilot supervision did not pass')
        require(review.get('passed') is True and review.get('result_sha256') == sha(prior/'science/result.json'), 'Pilot review does not pin actual local result')
        require(review.get('scope') and review.get('reviewer'), 'Pilot review must identify reviewer and scope')
        pilot_reuse = dict(directory=str(prior), review_path=str(args.pilot_review.resolve()), review_sha256=sha(args.pilot_review),
                          result_sha256=sha(prior/'science/result.json'), reader_sha256=sha(prior/'reader_result.json'),
                          supervision_sha256=sha(prior/'supervision/result.json'))
    require(args.pilot_output is None or pilot_reuse is not None, 'Pilot reuse is only for case completion')
    fresh = None
    if family in ('blocks', 'observed'):
        fresh = {}
        for route in ('california', 'california_benchmark') if family == 'blocks' else ('california',):
            for phase in ('pilot', 'completion'):
                record = published_review(route, phase)
                fresh[record['archive']] = record['sha256']
                pins[record['archive']] = record['sha256']
                for item in record['reviews']: pins[item['path']] = item['sha256']
                if record['acceptance_index']:
                    item = record['acceptance_index']; pins[item['path']] = item['sha256']
    return dict(schema='local_cpu_reader_request_v1', route=args.route, family=family,
                phase=args.phase, evaluator_mode=args.phase if args.phase in ('pilot', 'completion') else 'full',
                registry=registry_path.relative_to(ROOT).as_posix(), proposal=None if case_route else proposal_path.relative_to(ROOT).as_posix(),
                row_ids=selected, declared_roster=roster, pins=pins, inherited_published_source_review=inherited,
                pilot_reuse=pilot_reuse, fresh_artifacts_sha256=fresh,
                wall_seconds=args.wall_seconds, rss_cap_bytes=int(args.rss_mib*2**20), headroom_bytes=int(args.headroom_mib*2**20),
                builder=builder, runner=runner, scope=CLAIM_SCOPE, compilation_inside_wall_cap=True)


def execute_worker(request_path):
    """Only invoked as the child of the external Linux supervisor."""
    request = read(request_path); output = request_path.parent
    require(os.environ.get('CPU_READER_REQUEST_SHA256') == sha(request_path), 'Worker request identity mismatch')
    for name, expected in request['pins'].items():
        require(sha(inside(ROOT, name)) == expected, 'Launch source/input identity changed: '+name)
    family = request['family']; registry_path = ROOT/request['registry']; registry = read(registry_path)
    builder = PACKAGE/(request['builder']+'.py') if request['builder'] else None
    runner = PACKAGE/(request['runner']+'.py')
    mode = request['evaluator_mode']; rows = request['row_ids']; build = output/'build'
    admission = dict(passed=True, status='automated_local_integrity_checks_passed', scope=CLAIM_SCOPE,
                     mode=mode, row_ids=rows, numeric_threads=2, numerical_lease='local_reader_'+sha(request_path),
                     expires_utc=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=request['wall_seconds'])).isoformat())
    command = [sys.executable, '-B', str(runner)]
    if family == 'cases':
        inherited = request['inherited_published_source_review']['admission']
        if request['pilot_reuse']:
            build = Path(request['pilot_reuse']['directory'])/'build'
            require(sha(request['pilot_reuse']['review_path']) == request['pilot_reuse']['review_sha256'], 'Pilot review changed')
            require(sha(build.parent/'reader_result.json') == request['pilot_reuse']['reader_sha256']
                    and sha(build.parent/'supervision/result.json') == request['pilot_reuse']['supervision_sha256'], 'Pilot supervision evidence changed')
        else:
            subprocess.run([sys.executable, '-B', str(builder), 'build', '--output', str(build)], cwd=ROOT, check=True)
        receipt = build/'build_receipt.json'; library = build/'components.so'
        admission.update(independent_review_passed=inherited['independent_review_passed'],
            independent_review_basis=request['inherited_published_source_review']['reviews'],
            independent_review_scope='Inherited published source admission only; not this local numerical output',
            source_sha256=inherited['source_sha256'], protocol_sha256=sha(registry_path),
            case_ids=rows, threads=2, wall_seconds=request['wall_seconds'],
            sampled_process_tree_rss_cap_bytes=request['rss_cap_bytes'], numerical_attempt_id=admission['numerical_lease'],
            lease_token_sha256=hashlib.sha256(os.environ['NUMERICAL_LEASE_TOKEN'].encode()).hexdigest(),
            library_sha256=sha(library), build_receipt_sha256=sha(receipt))
        command += ['run', '--mode', mode, '--library', str(library), '--build-receipt', str(receipt)]
        if request['pilot_reuse']:
            admission.update(pilot_output_review_passed=True, pilot_result_sha256=request['pilot_reuse']['result_sha256'],
                             pilot_review_sha256=request['pilot_reuse']['review_sha256'])
            command += ['--pilot', str(Path(request['pilot_reuse']['directory'])/'science')]
    else:
        proposal = read(ROOT/request['proposal'])
        admission = dict(proposal, **admission)
        write(output/'rows.json', rows)
        command += ['--mode', mode, '--registry', str(registry_path), '--rows', str(output/'rows.json')]
        if builder:
            subprocess.run([sys.executable, '-B', str(builder)]+(['--build'] if family in ('li', 'blocks') else [])+
                           ['--registry', str(registry_path), '--output', str(build)], cwd=ROOT, check=True)
            libraries = read(build/'libraries.json')
            by_id = {r['id']: r for r in registry['rows']}
            used = ({by_id[r]['adapter'] for r in rows} if family == 'cached' else
                    {'core', 'competitive'} if family == 'regional' else {'cpu', 'radial'} if family == 'inhibition' else {'annual', 'sequence'})
            receipts = {'li': sha(libraries['library']['build_receipt_path'])} if family == 'li' else {
                key: sha(libraries['libraries'][key]['build_receipt_path']) for key in sorted(used)}
            admission.update(libraries_sha256=sha(build/'libraries.json'), build_receipts_sha256=receipts)
            command += ['--libraries', str(build/'libraries.json')]
        if family in ('blocks', 'observed'):
            by_id = {r['id']: r for r in registry['rows']}
            fresh = materialize_fresh_scores(request, output, {by_id[r]['fresh_score_row_id'] for r in rows}, require_arrays=family == 'blocks')
            admission['fresh_scores_sha256'] = sha(fresh)
            command += ['--fresh-scores', str(fresh)]
    write(output/'admission.json', admission)
    command += ['--admission', str(output/'admission.json'), '--output', str(output/'science')]
    write(output/'command.json', dict(command=command, scope=CLAIM_SCOPE))
    return subprocess.run(command, cwd=ROOT).returncode


def terminal_summary(request, output, returncode):
    supervisor_path = output/'supervision/result.json'; science_path = output/'science/result.json'
    supervision = read(supervisor_path) if supervisor_path.is_file() else {}
    science = read(science_path) if science_path.is_file() else {}
    entries = science.get('cases' if request['family'] == 'cases' else 'rows', [])
    key = 'case_id' if request['family'] == 'cases' else 'id'
    expected = request['declared_roster'] if request['family'] == 'cases' and request['phase'] == 'completion' else request['row_ids']
    found = [r.get(key) for r in entries]
    member_failures = []
    for name, expected_pin in request.get('pins', {}).items():
        try:
            require(sha(inside(ROOT, name)) == expected_pin, 'Source/input changed during run: '+name)
        except (ValueError, OSError) as exc:
            member_failures.append(str(exc))
    for entry in entries:
        try:
            relative = entry['file'] if request['family'] == 'cases' else entry['result']
            path = inside(output/'science', relative)
            require(sha(path) == entry['sha256'], 'Retained row hash mismatch')
            row = read(path)
            require(row.get('passed') is True and row.get(key) == entry.get(key), 'Retained row did not pass')
        except (ValueError, KeyError, OSError) as exc:
            member_failures.append(str(exc))
    passed = (returncode == 0 and supervision.get('status') == 'passed' and science.get('passed') is True
              and science.get('mode') == request.get('evaluator_mode', science.get('mode'))
              and len(found) == len(set(found)) and set(found) == set(expected) and not member_failures)
    return dict(passed=passed, scope=CLAIM_SCOPE, route=request['route'], phase=request['phase'],
                all_declared_rows_present=passed and set(found) == set(request['declared_roster']),
                numerical_output_reviewed_independently=False, result_sha256=sha(science_path) if science_path.is_file() else None,
                supervision_sha256=sha(supervisor_path) if supervisor_path.is_file() else None,
                requested_ids=request['row_ids'], retained_result_ids=found,
                missing_requested_ids=[r for r in request['row_ids'] if r not in found],
                member_failures=member_failures, partial_outputs_retained=True, request_sha256=sha(output/'request.json'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list', help='Inspect local published evidence; no numerical calls')
    run = sub.add_parser('run', help='Compile and replay under one Linux process supervisor')
    run.add_argument('--route', choices=sorted(ROUTES), required=True)
    run.add_argument('--phase', choices=('pilot', 'all', 'subset', 'completion'), default='pilot')
    run.add_argument('--rows', type=Path)
    run.add_argument('--output', type=Path, required=True)
    for name in ('wall-seconds', 'rss-mib', 'headroom-mib'): run.add_argument('--'+name, type=float, required=True)
    run.add_argument('--pilot-output', type=Path)
    run.add_argument('--pilot-review', type=Path)
    run.add_argument('--plan-only', action='store_true', help='Check identities and write request, without building/scoring')
    worker = sub.add_parser('_worker', help=argparse.SUPPRESS); worker.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'list':
        print(json.dumps(evidence_inventory(), indent=2)); return 0
    if args.command == '_worker': return execute_worker(args.request.resolve())
    output = args.output.resolve()
    require(not output.exists() and not output.is_relative_to(ROOT), 'Output must be a new directory outside the checkout')
    request = make_plan(args)
    if not args.plan_only: require(sys.platform.startswith('linux'), 'This supervised reader runs on Linux; plan-only is portable')
    output.mkdir(parents=True); write(output/'request.json', request)
    if args.plan_only:
        print(json.dumps(dict(status='planned_only', scientific_execution=False, output=str(output)))); return 0
    environment = {key: '2' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
    environment.update(CPU_READER_REQUEST_SHA256=sha(output/'request.json'), NUMERICAL_LEASE_TOKEN=secrets.token_hex(24))
    spec = dict(command=[sys.executable, '-B', str(Path(__file__).resolve()), '_worker', str(output/'request.json')],
                cwd=str(ROOT), output=str(output/'supervision'), env=environment,
                wall_cap_seconds=request['wall_seconds'], rss_cap_bytes=request['rss_cap_bytes'],
                host_headroom_bytes=request['headroom_bytes'], sample_seconds=.5)
    write(output/'supervisor_spec.json', spec)
    process = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/supervise_research.py'), str(output/'supervisor_spec.json')], cwd=ROOT)
    result = terminal_summary(request, output, process.returncode); write(output/'reader_result.json', result)
    print(json.dumps(result)); return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
