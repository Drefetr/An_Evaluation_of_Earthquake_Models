"""Execute a conductor-reviewed continuation stage on a fresh Linux runner.

An admission is a source/scope attestation, not an authentication mechanism.
No results are promoted to manuscript claims by this controller.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def inside(base, relative):
    path = (base / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(base.resolve()):
        raise ValueError('Path outside declared directory')
    return path


def replay_paths(review):
    package = ROOT / 'reproduction/score_replay'
    registry = inside(ROOT, review.get('registry', 'reproduction/score_replay/cached_registry.json'))
    proposal = inside(ROOT, review.get('proposal', 'reproduction/score_replay/cached_pilot_proposal.json'))
    if not registry.is_relative_to(package) or proposal.parent != registry.parent:
        raise ValueError('Replay registry/proposal must share a declared package directory')
    return package, registry, proposal


def replay_roster(review, proposal, registry):
    phase = review['stage'].split('-')[1]
    selected = review['row_ids']
    by_id = {row['id']: row for row in registry['rows']}
    if len(by_id) != len(registry['rows']):
        raise ValueError('Duplicate registry identity')
    if not selected or len(selected) != len(set(selected)) or set(selected)-by_id.keys():
        raise ValueError('Invalid reviewed replay roster')
    pilot = proposal['row_ids']
    if not pilot or len(pilot) != len(set(pilot)) or set(pilot)-by_id.keys():
        raise ValueError('Invalid proposed pilot roster')
    if phase == 'pilot' and selected != pilot:
        raise ValueError('Pilot differs from the predeclared source-review roster')
    if phase == 'completion':
        if review.get('pilot_output_review_passed') is not True:
            raise ValueError('Replay completion requires an independently accepted pilot')
        if selected != [r for r in by_id if r not in pilot]:
            raise ValueError('Completion must cover exactly the non-pilot rows')
    if phase not in ('pilot', 'completion'):
        raise ValueError('Unknown replay phase')
    return selected, by_id


def mandatory_sources(stage, review=None):
    paths = {'scripts/run_continuation.py','scripts/supervise_research.py',
             'scripts/tests/test_supervise_research_linux.py',
             'tests/test_continuation_controller.py',
             'engine/cpu_build.py','engine/stage2_followup/native_build.py',
             '.github/workflows/research-continuation.yml','requirements.txt','requirements-cpu.txt'}
    if stage in ('joint-pilot','joint-full'):
        paths.add('tests/test_s04b_joint_nuisance.py')
        package = ROOT/'experiments/s04b_joint_nuisance'
        paths.update(p.relative_to(ROOT).as_posix() for p in package.iterdir()
                     if p.is_file() and p.suffix in ('.py','.cpp','.json'))
    elif stage in ('cached-pilot','cached-completion','regional-pilot','regional-completion'):
        prefix = 'reproduction/score_replay/'
        package, registry, proposal = replay_paths(review or {})
        names = ('__init__.py','core.py','regional_build.py','regional_replay.py') if stage.startswith('regional-') else (
            '__init__.py','build.py','cached_native.py','core.py','inventory.py','replay.py')
        paths.update(prefix+name for name in names)
        paths.update(p.relative_to(ROOT).as_posix() for p in (registry, proposal, registry.parent/'input_manifest.json'))
        paths.update(prefix+name for name in ('protocol.json','cached_field_crosswalk.json'))
    else:
        raise ValueError('Unknown bounded continuation stage')
    return paths


def prior_artifact(review, output):
    artifact_id = int(review['pilot_artifact_id'])
    repository = 'Drefetr/An_Evaluation_of_Earthquake_Models'
    url = f'https://api.github.com/repos/{repository}/actions/artifacts/{artifact_id}/zip'
    request = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
        'Accept': 'application/vnd.github+json'})
    archive = output / 'prior_artifact.zip'
    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
            if redirected is not None:
                redirected.remove_header('Authorization')
            return redirected
    opener = urllib.request.build_opener(SafeRedirect())
    with opener.open(request, timeout=120) as response, archive.open('xb') as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)
    if sha(archive) != review['pilot_archive_sha256']:
        raise ValueError('Prior artifact identity differs from reviewed artifact')
    destination = output / 'prior'
    destination.mkdir()
    with zipfile.ZipFile(archive) as source:
        names = [i.filename for i in source.infolist()]
        if len(names) != len(set(names)) or sum(i.file_size for i in source.infolist()) > 2**30:
            raise ValueError('Invalid prior-artifact member roster or size')
        for info in source.infolist():
            inside(destination, info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Artifact symlinks are not accepted')
        source.extractall(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise RuntimeError('This production controller requires the reviewed Linux supervisor')
    review = read(args.admission)
    if review['independent_source_review'] != 'passed':
        raise ValueError('Independent source review has not passed')
    stage = review['stage']
    missing = mandatory_sources(stage, review)-review['reviewed_files_sha256'].keys()
    if missing:
        raise ValueError('Incomplete reviewed-source coverage: '+str(sorted(missing)))
    if int(os.environ.get('GITHUB_RUN_ATTEMPT','1')) != review['allowed_github_run_attempt']:
        raise ValueError('Workflow retry requires a fresh conductor numerical admission')
    for relative, expected in review['reviewed_files_sha256'].items():
        if sha(inside(ROOT, relative)) != expected:
            raise ValueError('Reviewed source changed: ' + relative)
    now = dt.datetime.now(dt.timezone.utc)
    expires = dt.datetime.fromisoformat(review['expires_utc'])
    if now >= expires:
        raise ValueError('Expired numerical admission')
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Production output must be outside checkout')
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'conductor_review.json', review)
    token = secrets.token_hex(32)
    environment = {key: '2' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS',
                   'MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['JOINT_NUMERICAL_LEASE_TOKEN'] = token
    os.environ.update(environment)
    prior = prior_artifact(review, output) if 'pilot_artifact_id' in review else None
    # Download credentials are unnecessary in compilers or numerical children.
    os.environ.pop('GITHUB_TOKEN', None)
    if stage in ('joint-pilot', 'joint-full'):
        package = ROOT / 'experiments/s04b_joint_nuisance'
        sys.path.insert(0, str(package))
        import run as joint
        if prior:
            build = inside(prior, review['pilot_build_directory'])
        else:
            from engine.cpu_build import build_shared
            build = output / 'build'
            build_shared(package / 'attenuation.cpp', build, dependency_root=package)
        receipt = build / 'build_receipt.json'
        library = build / 'attenuation.so'
        phase = stage.split('-')[1]
        admission = dict(phase=phase, independent_review_passed=True,
                        expires_utc=review['expires_utc'], source_sha256=joint.source_identity(),
                        protocol_sha256=sha(package/'protocol.json'), input_pins_sha256=sha(package/'input_pins.json'),
                        lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                        library_sha256=sha(library), build_receipt_sha256=sha(receipt),
                        threads=2, sampled_process_tree_rss_cap_bytes=review['rss_cap_bytes'],
                        wall_seconds=review['wall_cap_seconds'], numerical_attempt_id=review['numerical_attempt_id'])
        command = [sys.executable,'-B',str(package/'run.py'),'--phase',phase,
                   '--output',str(output/'science'),'--library',str(library),
                   '--build-receipt',str(receipt),'--admission',str(output/'admission.json')]
        if prior:
            admission.update(pilot_result_sha256=review['pilot_result_sha256'],
                             pilot_output_review_passed=review['pilot_output_review_passed'])
            command += ['--pilot',str(inside(prior,review['pilot_science_directory']))]
    elif stage in ('cached-pilot', 'cached-completion', 'regional-pilot', 'regional-completion'):
        package, registry_path, proposal_path = replay_paths(review)
        regional = stage.startswith('regional-')
        proposal = read(proposal_path)
        registry = read(registry_path)
        selected, by_id = replay_roster(review, proposal, registry)
        build = output / 'build'
        subprocess.run([sys.executable,'-B',str(package/('regional_build.py' if regional else 'build.py')),
                        '--registry',str(registry_path),'--output',str(build)],cwd=ROOT,check=True)
        libraries = read(build/'libraries.json')
        phase = stage.split('-')[1]
        used = {'core','competitive'} if regional else {by_id[row]['adapter'] for row in selected}
        write(output/'rows.json',selected)
        admission = dict(proposal, passed=True, status='reviewed_workflow_admission', mode=phase, row_ids=selected,
                         numerical_lease=review['numerical_attempt_id'],
                         libraries_sha256=sha(build/'libraries.json'), expires_utc=review['expires_utc'], numeric_threads=2,
                         build_receipts_sha256={k:sha(libraries['libraries'][k]['build_receipt_path']) for k in sorted(used)})
        command = [sys.executable,'-B',str(package/('regional_replay.py' if regional else 'replay.py')),'--mode',phase,
                   '--registry',str(registry_path),
                   '--libraries',str(build/'libraries.json'),'--admission',str(output/'admission.json'),
                   '--rows',str(output/'rows.json'),'--output',str(output/'science')]
    else:
        raise ValueError('Unknown bounded continuation stage')
    write(output/'admission.json',admission)
    remaining = (expires-dt.datetime.now(dt.timezone.utc)).total_seconds()
    if remaining < review['wall_cap_seconds']:
        raise ValueError('Lease expires before entire approved stage allowance')
    spec = dict(command=command,cwd=str(ROOT),output=str(output/'supervision'),env=environment,
                wall_cap_seconds=review['wall_cap_seconds'],rss_cap_bytes=review['rss_cap_bytes'],
                host_headroom_bytes=review['host_headroom_bytes'],sample_seconds=.5)
    write(output/'supervisor_spec.json',spec)
    result = subprocess.run([sys.executable,'-B',str(ROOT/'scripts/supervise_research.py'),
                             str(output/'supervisor_spec.json')],cwd=ROOT)
    return result.returncode


if __name__ == '__main__':
    sys.path.insert(0,str(ROOT))
    raise SystemExit(main())
