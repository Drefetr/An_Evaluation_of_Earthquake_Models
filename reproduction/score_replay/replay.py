"""Replay reviewed saved-state likelihood rows into a fresh output directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import sys
import time
import traceback

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from reproduction.score_replay import cached_native
from reproduction.score_replay.core import Inputs, compare, digest, pointer, write_new


def source_pins():
    root = Path(__file__).resolve().parent
    names = ('__init__.py', 'build.py', 'cached_native.py', 'core.py', 'inventory.py', 'replay.py')
    return {name: digest((root / name).read_bytes()) for name in names}


def checked_admission(path, registry_data, selected, mode):
    value = json.loads(path.read_text(encoding='utf-8'))
    if value.get('passed') is not True or value.get('mode') != mode:
        raise ValueError('source and scope admission is not passed for this mode')
    if value.get('registry_sha256') != digest(registry_data):
        raise ValueError('admission does not pin this registry')
    if value.get('source_sha256') != source_pins():
        raise ValueError('replay source differs from reviewed source pins')
    if value.get('row_ids') != selected:
        raise ValueError('requested ordered roster differs from admitted roster')
    return value


def run(registry_path, libraries_path, admission_path, output, row_ids, mode):
    if output.exists():
        raise FileExistsError('replay output must be a new directory')
    registry_data = registry_path.read_bytes()
    registry = json.loads(registry_data)
    rows = registry['rows']
    by_id = {row['id']: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError('duplicate registry row identity')
    selected = row_ids if row_ids is not None else list(by_id)
    if not selected or len(set(selected)) != len(selected):
        raise ValueError('roster must be nonempty and unique')
    if set(selected) - set(by_id):
        raise ValueError('roster includes an unknown row')
    admission = checked_admission(admission_path, registry_data, selected, mode)
    libraries_data = libraries_path.read_bytes()
    libraries = json.loads(libraries_data)
    if libraries.get('registry_sha256') != digest(registry_data):
        raise ValueError('library manifest belongs to a different registry')
    if admission.get('libraries_sha256') != digest(libraries_data):
        raise ValueError('libraries differ from the admitted build identities')
    input_manifest = registry_path.parent / 'input_manifest.json'
    if admission.get('input_manifest_sha256') != digest(input_manifest.read_bytes()):
        raise ValueError('input manifest differs from the admitted payload')
    used_adapters = sorted({by_id[row_id]['adapter'] for row_id in selected})
    receipt_hashes = {}
    for adapter_id in used_adapters:
        library = libraries['libraries'][adapter_id]
        receipt_data = Path(library['build_receipt_path']).read_bytes()
        receipt = json.loads(receipt_data)
        receipt_hashes[adapter_id] = digest(receipt_data)
        if (receipt_hashes[adapter_id] != library['build_receipt_sha256']
                or receipt != library['build_receipt'] or receipt.get('passed') is not True
                or receipt.get('source_sha256') != registry['adapters'][adapter_id]['native']['sha256']
                or receipt.get('library_sha256') != library['sha256']):
            raise ValueError('build receipt/source/binary identity mismatch')
    if admission.get('build_receipts_sha256') != receipt_hashes:
        raise ValueError('build receipt hashes differ from the admitted builds')
    threads = admission.get('numeric_threads')
    if isinstance(threads, bool) or threads not in (1, 2):
        raise ValueError('admission must require one or two numerical threads')
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = str(threads)
    import numpy
    from threadpoolctl import threadpool_info, threadpool_limits
    inputs = Inputs(registry_path.parent)
    output.mkdir(parents=True)
    write_new(output / 'launch.json', {
        'registry_sha256': digest(registry_data),
        'libraries_sha256': digest(libraries_data),
        'admission_sha256': digest(admission_path.read_bytes()),
        'source_sha256': source_pins(), 'row_ids': selected, 'mode': mode,
        'numerical_lease': admission.get('numerical_lease'),
        'input_manifest_sha256': digest(input_manifest.read_bytes()),
        'build_receipts_sha256': receipt_hashes,
        'runtime': {'python': sys.version, 'executable': sys.executable,
                    'platform': platform.platform(), 'numpy': numpy.__version__,
                    'numeric_threads': threads, 'native_evaluator_threads': 1},
        'thread_environment': {k: os.environ.get(k) for k in
            ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')},
    })
    started = time.monotonic()
    reports = []
    for index, row_id in enumerate(selected):
        row = by_id[row_id]
        row_output = output / 'rows' / f'{index:05d}'
        row_started = time.monotonic()
        record = {'id': row_id, 'status': 'failed', 'passed': False,
                  'phase': row['phase'], 'study': row['study'],
                  'feature_scope': row['feature_scope'], 'fit_scope': row['fit_scope']}
        try:
            adapter = registry['adapters'][row['adapter']]
            if adapter['kind'] != 'original_cached_native':
                raise ValueError('unsupported replay adapter kind')
            # The evaluator receives no expected-score value or reference pointer.
            with threadpool_limits(limits=threads):
                pools = threadpool_info()
                if any(pool['num_threads'] > threads for pool in pools):
                    raise RuntimeError('loaded numerical thread pool exceeds admission')
                actual = cached_native.evaluate(inputs, row, adapter,
                                                libraries['libraries'][row['adapter']], row_output)
                actual['threadpools'] = threadpool_info()
                if any(pool['num_threads'] > threads for pool in actual['threadpools']):
                    raise RuntimeError('evaluator loaded a numerical thread pool exceeding admission')
            expected = pointer(inputs.json(row['state']), row['expected_pointer'])
            comparison = compare(actual['components'], expected, row['absolute_tolerances'])
            record.update(actual=actual, comparison=comparison,
                          passed=comparison['passed'],
                          status='replayed' if comparison['passed'] else 'failed',
                          failure_interpretation=None if comparison['passed'] else
                          'Functional discrepancy requires identity/algorithm/tolerance diagnosis; no historical result is automatically withdrawn.')
        except Exception as error:
            record.update(error_type=type(error).__name__, error=str(error),
                          traceback=traceback.format_exc())
        record['elapsed_seconds'] = time.monotonic() - row_started
        write_new(row_output / 'result.json', record)
        reports.append({'id': row_id, 'passed': record['passed'], 'status': record['status'],
                        'result': (row_output / 'result.json').relative_to(output).as_posix(),
                        'sha256': digest((row_output / 'result.json').read_bytes()),
                        'elapsed_seconds': record['elapsed_seconds']})
        with (output / 'progress.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(reports[-1], allow_nan=False) + '\n')
            stream.flush()
    passed = all(r['passed'] for r in reports)
    result = {'schema': 'score_replay_result_v1', 'passed': passed,
              'mode': mode, 'requested_rows': len(selected), 'completed_rows': len(reports),
              'passed_rows': sum(r['passed'] for r in reports),
              'failed_rows': sum(not r['passed'] for r in reports),
              'full_registry': selected == list(by_id),
              'entire_task_complete': False,
              'scope': 'Only the named saved states and cached likelihood rows. No search, raw-feature reconstruction, catalogue generation or omitted table is certified.',
              'elapsed_seconds': time.monotonic() - started,
              'registry_sha256': digest(registry_data), 'rows': reports}
    write_new(output / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=Path(__file__).with_name('cached_registry.json'))
    parser.add_argument('--libraries', type=Path, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--rows', type=Path, help='JSON array of ordered row identifiers; default is complete registry')
    parser.add_argument('--mode', choices=('pilot', 'full', 'completion'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    row_ids = json.loads(args.rows.read_text(encoding='utf-8')) if args.rows else None
    result = run(args.registry.resolve(), args.libraries.resolve(), args.admission.resolve(),
                 args.output.resolve(), row_ids, args.mode)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
