"""Run one admitted five-evaluation diagnostic; never fit or score held-out data."""
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
CASE = 'S5_broad_long_imm_seed410518'
PREFIX = 'host/children/05_' + CASE


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def plan(review, output):
    if (review['case_id'] != CASE or review['max_support_evaluations'] != 5 or
            review['optimizer_calls'] != 0 or review['held_out_calls'] != 0 or
            review['wall_cap_seconds'] != 60 or review['scientific_completion'] is not False):
        raise ValueError('Diagnostic scope differs from the five frozen training evaluations')
    if review['independent_source_review'] != 'passed':
        raise ValueError('Diagnostic source has not been independently reviewed')
    if dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(review['expires_utc']):
        raise ValueError('Expired diagnostic admission')
    if int(os.environ.get('GITHUB_RUN_ATTEMPT', '1')) != 1:
        raise ValueError('A retry requires a new admission')
    required = {'scripts/run_joint_support_diagnostic.py',
                '.github/workflows/joint-support-diagnostic.yml',
                'experiments/s04b_joint_recovery/support_diagnostic.py',
                'tests/test_joint_support_diagnostic.py',
                'scripts/supervise_research.py',
                'requirements-cpu.txt', 'requirements.txt'}
    sys.path.insert(0, str(ROOT))
    from experiments.s04b_joint_recovery import driver
    required.update(driver.source_identity())
    pins = review['source_sha256']
    if not required.issubset(pins):
        raise ValueError('Incomplete diagnostic source coverage')
    for name, expected in pins.items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or sha(path) != expected:
            raise ValueError('Diagnostic source changed: ' + name)
    archive = (ROOT/review['archive']).resolve()
    if not archive.is_relative_to(ROOT) or sha(archive) != review['archive_sha256']:
        raise ValueError('Original failed archive changed')
    with zipfile.ZipFile(archive) as saved:
        names = saved.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        for name in names:
            if name.startswith(PREFIX + '/') and not name.endswith('/'):
                dest = (output/'prior'/name).resolve()
                if not dest.is_relative_to((output/'prior').resolve()):
                    raise ValueError('Unsafe archive member')
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open('xb') as stream:
                    stream.write(saved.read(name))
    command = [sys.executable, '-B', '-m',
               'experiments.s04b_joint_recovery.support_diagnostic',
               '--prior', str(output/'prior'/PREFIX),
               '--output', str(output/'science'), '--wall-seconds', '60']
    return dict(command=command, cwd=str(ROOT), output=str(output/'supervision'),
                env={key: '2' for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                     'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')},
                wall_cap_seconds=60, rss_cap_bytes=6442450944,
                host_headroom_bytes=2147483648, sample_seconds=0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        raise ValueError('Use the declared Linux runtime for this diagnosis')
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Output must be outside the checkout')
    output.mkdir(parents=True, exist_ok=False)
    review = read(args.admission)
    write(output/'admission.json', review)
    spec = plan(review, output)
    write(output/'supervisor_spec.json', spec)
    return subprocess.run([sys.executable, '-B', str(ROOT/'scripts/supervise_research.py'),
                           str(output/'supervisor_spec.json')], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
