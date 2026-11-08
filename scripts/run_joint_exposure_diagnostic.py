"""Supervise one independently reviewed training-vector diagnostic, without fits."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CASE = 'S6_narrow_short_total_seed410603'
ARCHIVE = 'validation/reproductions/joint_nuisance_20261107/continuation/remaining_host02_exposure_failure.zip'
ARCHIVE_SHA = '9319b3669c5fda81fab941038913a0c3bc7178c506441af4f244b7e64c228b88'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def local(name):
    path = (ROOT/name).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Source path escapes repository')
    return path


def validate(review):
    if (review.get('case_id') != CASE or review.get('orders') != [8, 16] or
            review.get('parameter_vectors') != 1 or review.get('optimizer_calls') != 0 or
            review.get('held_out_calls') != 0 or review.get('wall_cap_seconds') != 300 or
            review.get('scientific_completion') is not False or
            review.get('independent_source_review') != 'passed'):
        raise ValueError('Diagnostic scope differs from the reviewed single training vector')
    if not isinstance(review.get('numerical_attempt_id'), str) or not review['numerical_attempt_id']:
        raise ValueError('A recorded numerical attempt is required')
    shared_path = ROOT/'validation/reproductions/continuation_20261107/shared_run_config.json'
    shared = read(shared_path)
    if sha(shared_path) != review['shared_run_config_sha256'] or review['expires_utc'] != shared['deadline_utc']:
        raise ValueError('Shared budget/deadline identity changed')
    remaining = (dt.datetime.fromisoformat(review['expires_utc']) - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if remaining < 300:
        raise ValueError('Insufficient deadline for the full diagnostic allowance')
    if int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')) != 1:
        raise ValueError('A retry requires separate review and admission')
    if review.get('archive') != ARCHIVE or review.get('archive_sha256') != ARCHIVE_SHA:
        raise ValueError('Wrong failed execution archive')
    if sha(ROOT/ARCHIVE) != ARCHIVE_SHA:
        raise ValueError('Failed execution archive changed')
    source_path = local(review['source_review'])
    if sha(source_path) != review['source_review_sha256']:
        raise ValueError('Independent source review changed')
    source_review = read(source_path)
    pins = review['source_sha256']
    if (source_review.get('passed') is not True or source_review.get('live_agent_review') is not True or
            source_review.get('source_sha256') != pins):
        raise ValueError('Independent review does not cover this exact source map')
    required = {'scripts/run_joint_exposure_diagnostic.py',
        '.github/workflows/joint-exposure-diagnostic.yml', 'scripts/supervise_research.py',
        'experiments/s04b_exposure_diagnostic/__init__.py',
        'experiments/s04b_exposure_diagnostic/run.py', 'experiments/s04b_exposure_diagnostic/protocol.json',
        'tests/test_joint_exposure_diagnostic.py', 'tests/test_joint_exposure_diagnostic_launcher.py',
        'requirements-cpu.txt', 'requirements.txt',
        'validation/reproductions/continuation_20261107/shared_run_config.json'}
    if not required.issubset(pins):
        raise ValueError('Incomplete diagnostic source coverage')
    for name, expected in pins.items():
        if sha(local(name)) != expected:
            raise ValueError('Diagnostic source changed: '+name)
    # Reviewed source hashes are checked before importing the diagnostic module.
    sys.path.insert(0, str(ROOT))
    from experiments.s04b_exposure_diagnostic import run
    identities = run.source_identity()
    if not all(pins.get(name) == value for name, value in identities.items()):
        raise ValueError('Scientific dependencies are not covered by source review')
    return pins


def plan(review, output):
    validate(review)
    prior = output/'prior'
    with zipfile.ZipFile(ROOT/ARCHIVE) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        for name in names:
            if name.endswith('/'):
                continue
            destination = (prior/name).resolve()
            if not destination.is_relative_to(prior.resolve()):
                raise ValueError('Archive member escapes diagnostic input directory')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(archive.read(name))
    return dict(command=[sys.executable, '-B', '-m', 'experiments.s04b_exposure_diagnostic.run',
        '--prior', str(prior), '--output', str(output/'science'), '--wall-seconds', '300'],
        cwd=str(ROOT), output=str(output/'supervision'),
        env={key:'2' for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')},
        wall_cap_seconds=300, rss_cap_bytes=6442450944, host_headroom_bytes=2147483648, sample_seconds=0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise ValueError('Use the declared Linux runtime')
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Diagnostic output must be outside checkout')
    output.mkdir(parents=True, exist_ok=False)
    review = read(args.admission)
    write(output/'admission.json', review)
    spec = plan(review, output)
    write(output/'supervisor_spec.json', spec)
    validate(review)
    return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/supervise_research.py'),
                           str(output/'supervisor_spec.json')],cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
