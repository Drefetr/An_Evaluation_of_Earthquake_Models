"""Launch the reviewed exposure amendment without changing frozen fit sources.

Admissions bind source and execution scope; they are not authentication tokens.
Every predecessor is an exact public archive with a separate live output review.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'experiments/s04b_exposure_refinement'
CHECKER = 'experiments/s04b_exposure_refinement_audit'
EVIDENCE = 'validation/reproductions/continuation_20261107/exposure_refinement_design'
SHARED = 'validation/reproductions/continuation_20261107/shared_run_config.json'
FAILED_ARCHIVE = 'validation/reproductions/joint_nuisance_20261107/continuation/remaining_host02_exposure_failure.zip'
FAILED_ARCHIVE_SHA = '9319b3669c5fda81fab941038913a0c3bc7178c506441af4f244b7e64c228b88'
FAILED_REVIEW = 'validation/reproductions/joint_nuisance_20261107/continuation/remaining_host02_exposure_failure_review.json'
FAILED_REVIEW_SHA = 'aa43adfe5c2ffcf3c0056887066899b9cd4ac33bb6631a7f345860be99855343'
DESIGN_SHA = 'da10a9b046925426f9b7fb4370be0961697dd6c81ca58539201ba361dd7e2758'
RESOURCES_SHA = 'e20f857ca92147c2a4710e915ac13fbd9c997a6de1ffdca52fc338c61365bd14'


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def inside(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Nonportable evidence path')
    pure = PurePosixPath(relative)
    path = (root/relative).resolve()
    if pure.is_absolute() or '..' in pure.parts or not path.is_relative_to(root.resolve()):
        raise ValueError('Evidence path escapes its root')
    return path


def require(value, message):
    if not value:
        raise ValueError(message)


def mandatory_sources():
    paths = {'scripts/run_joint_exposure_refinement.py', '.github/workflows/joint-exposure-refinement.yml',
        'scripts/supervise_research.py', 'tests/test_joint_exposure_refinement_launcher.py',
        'requirements.txt', 'requirements-cpu.txt', SHARED,
        EVIDENCE+'/independent_design_review.json', EVIDENCE+'/resources.json'}
    for directory in (PACKAGE, CHECKER):
        require((ROOT/directory).is_dir(), 'Amendment implementation is missing')
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*')
                     if p.is_file() and p.suffix in ('.py','.json'))
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_joint_exposure_refinement*.py'))
    return paths


def validate(review):
    require(review.get('schema') == 'joint_exposure_refinement_admission_v1'
            and review.get('independent_source_review') == 'passed'
            and review.get('scientific_completion') is False,
            'A separately reviewed numerical amendment is required')
    require(isinstance(review.get('numerical_attempt_id'),str) and review['numerical_attempt_id'],
            'Numerical attempt identity is missing')
    require(int(os.environ.get('GITHUB_RUN_ATTEMPT','1')) == 1, 'No automatic workflow retries')
    require(sha(ROOT/EVIDENCE/'resources.json') == RESOURCES_SHA
            and sha(ROOT/EVIDENCE/'independent_design_review.json') == DESIGN_SHA,
            'Reviewed design or resource identity changed')
    shared, resources = read(ROOT/SHARED), read(ROOT/EVIDENCE/'resources.json')
    require(sha(ROOT/SHARED) == review['shared_config_sha256']
            and review['expires_utc'] == shared['deadline_utc'] == resources['deadline_utc'],
            'The shared budget/deadline cannot be extended')
    batch = review['batch_id']
    require(type(batch) is int and 1 <= batch <= 8, 'Unknown fixed host')
    group = resources['future_hosts'][batch-1]
    require(review['case_ids'] == group['case_ids']
            and review['whole_host_upper_seconds'] == group['whole_host_upper_seconds']
            and review['wall_cap_seconds'] == group['whole_host_upper_seconds']-600,
            'Host scope or resource allowance changed')
    require(review.get('rss_cap_bytes') == 6442450944 and review.get('host_headroom_bytes') == 2147483648,
            'Memory envelope changed')
    require(set(review['child_attempt_ids']) == set(group['case_ids'])
            and len(set(review['child_attempt_ids'].values())) == len(group['case_ids']),
            'Child attempt roster is incomplete or duplicated')
    left = (dt.datetime.fromisoformat(review['expires_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()
    require(left >= group['whole_host_upper_seconds'], 'Insufficient remaining shared deadline')
    source_path = inside(ROOT,review['source_review'])
    require(sha(source_path) == review['source_review_sha256'], 'Source review changed')
    source = read(source_path)
    pins = review['reviewed_files_sha256']
    require(source.get('passed') is True and source.get('live_agent_review') is True
            and source.get('reviewed_files_sha256') == pins, 'Exact combined source review is required')
    require(mandatory_sources().issubset(pins), 'Incomplete amendment source coverage')
    for relative, expected in pins.items():
        require(sha(inside(ROOT,relative)) == expected, 'Reviewed source changed: '+relative)
    prior_path, prior_review = inside(ROOT,review['prior_archive']), inside(ROOT,review['prior_review'])
    require(sha(prior_path) == review['prior_archive_sha256'] and sha(prior_review) == review['prior_review_sha256'],
            'Predecessor execution or live review changed')
    prior_audit = read(prior_review)
    require(prior_audit.get('audit_passed') is True and prior_audit.get('live_agent_review') is True,
            'Predecessor lacks a live independent output audit')
    require(prior_audit.get('artifact_sha256') == review['prior_archive_sha256'],
            'Predecessor audit does not bind this exact execution archive')
    if batch == 1:
        require(review['prior_archive'] == FAILED_ARCHIVE and review['prior_archive_sha256'] == FAILED_ARCHIVE_SHA
                and review['prior_review'] == FAILED_REVIEW and review['prior_review_sha256'] == FAILED_REVIEW_SHA,
                'Partial pilot requires the exact retained failure')
    else:
        require(prior_audit.get('disposition_valid') is True and prior_audit.get('index_sha256') == review['prior_index_sha256'],
                'Continuation requires the accepted compact predecessor')
    # All reviewed bytes are checked before importing any producer module.
    sys.path.insert(0,str(ROOT))
    from experiments.s04b_exposure_refinement import host, case_driver
    for identities in (host.source_identity(),case_driver.source_identity()):
        require(all(pins.get(name) == value for name,value in identities.items()),
                'Imported dependency is outside source review')
    return group, host, case_driver


def extract(archive_path, destination):
    with zipfile.ZipFile(archive_path) as saved:
        names = saved.namelist()
        require(len(names) == len(set(names)), 'Duplicate archive entry')
        for name in names:
            if name.endswith('/'):
                continue
            target = inside(destination,name)
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as stream:
                stream.write(saved.read(name))


def remaining_window(review, group, started):
    """Measure again immediately before launch, including the final pin check."""
    elapsed=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(started)).total_seconds()
    require(elapsed >= 0, 'Host start lies in the future')
    wall=review['wall_cap_seconds']-elapsed
    require(wall >= group['case_outer_seconds']+120*len(group['case_ids'])+30,
            'Complete case/check/finalization slots do not fit this host')
    return wall


def prepare(review, output, started):
    group, host, driver = validate(review)
    elapsed = (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(started)).total_seconds()
    require(0 <= elapsed < 1170-120*len(group['case_ids']), 'Setup exhausted the fixed host preparation margin')
    prior = output/'prior'
    extract(inside(ROOT,review['prior_archive']),prior)
    index_path = inside(prior,'host/index.json')
    require(sha(index_path) == review['prior_index_sha256'], 'Predecessor compact index changed')
    old = read(ROOT/'experiments/s04b_joint_remaining/protocol.json')
    ref = old['immutable_failure_reference']
    original = inside(ROOT,ref['archive'])
    require(sha(original) == ref['archive_sha256'], 'Original native archive changed')
    build = output/'build'; build.mkdir()
    with zipfile.ZipFile(original) as saved:
        for key,name,pin in [('library_member','attenuation.so',old['original_native']['library_sha256']),
                             ('build_receipt_member','build_receipt.json',old['original_native']['build_receipt_sha256'])]:
            require(saved.namelist().count(ref[key]) == 1,'Missing or duplicate native member')
            raw = saved.read(ref[key]); require(hashlib.sha256(raw).hexdigest() == pin,'Native identity changed')
            (build/name).write_bytes(raw)
    token = secrets.token_hex(32)
    source_path = inside(ROOT,review['source_review'])
    protocol_sha = sha(ROOT/PACKAGE/'protocol.json')
    admission = dict(mode='exposure_refinement_host_batch',source_sha256=host.source_identity(),
        scientific_source_sha256=driver.source_identity(),protocol_sha256=protocol_sha,amendment_protocol_sha256=protocol_sha,
        scientific_protocol_sha256=old['scientific_protocol_sha256'],shared_run=old['shared_run'],
        batch_id=review['batch_id'],case_ids=review['case_ids'],child_attempt_ids=review['child_attempt_ids'],
        numerical_attempt_id=review['numerical_attempt_id'],lease_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        prior_index_sha256=sha(index_path),prior_review_sha256=review['prior_review_sha256'],
        prior_archive_sha256=review['prior_archive_sha256'],expires_utc=review['expires_utc'],
        host_started_utc=started,execution_window_seconds=review['wall_cap_seconds'],
        rss_cap_bytes=review['rss_cap_bytes'],host_headroom_bytes=review['host_headroom_bytes'],
        library_sha256=sha(build/'attenuation.so'),build_receipt_sha256=sha(build/'build_receipt.json'),
        source_review_sha256=sha(source_path),checker_source_review_sha256=sha(source_path),
        host_batch_source_review_passed=True,checker_source_review_passed=True,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        reviewed_files_sha256=review['reviewed_files_sha256'],conductor_review=review)
    write(output/'admission.json',admission)
    command=[sys.executable,'-B','-m','experiments.s04b_exposure_refinement.host',
        '--admission',str(output/'admission.json'),'--output',str(output/'host'),
        '--prior-index',str(index_path),'--prior-review',str(inside(ROOT,review['prior_review'])),
        '--config',str(ROOT/SHARED),'--source-review',str(source_path),'--checker-review',str(source_path),
        '--library',str(build/'attenuation.so'),'--build-receipt',str(build/'build_receipt.json')]
    if review['batch_id']==1:
        command += ['--failed-prior',str(prior)]
    wall=remaining_window(review,group,started)
    env={name:'2' for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
    env.update(PYTHONDONTWRITEBYTECODE='1',JOINT_NUMERICAL_LEASE_TOKEN=token,NUMERICAL_LEASE_TOKEN=token)
    return dict(command=command,cwd=str(ROOT),output=str(output/'supervision'),env=env,
        wall_cap_seconds=wall,rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,sample_seconds=.5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    require(sys.platform.startswith('linux'),'Use the declared Linux numerical runtime')
    started=os.environ['CONTINUATION_HOST_STARTED_UTC']
    output=args.output.resolve()
    require(not output.is_relative_to(ROOT),'Outputs must be outside the checkout')
    output.mkdir(parents=True,exist_ok=False)
    review=read(args.admission); write(output/'conductor_review.json',review)
    spec=prepare(review,output,started)
    group,_,_=validate(review)
    spec['wall_cap_seconds']=remaining_window(review,group,started)
    write(output/'supervisor_spec.json',spec)
    return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/supervise_research.py'),
                           str(output/'supervisor_spec.json')],cwd=ROOT).returncode


if __name__=='__main__':
    raise SystemExit(main())
