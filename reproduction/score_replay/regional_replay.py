"""Rebuild regional features and rescore unchanged selected fitted vectors."""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, components, compare, digest, write_new


def source_pins():
    folder = Path(__file__).resolve().parent
    return {n: digest((folder/n).read_bytes()) for n in
            ('__init__.py', 'core.py', 'regional_build.py', 'regional_replay.py')}


def module_from_spec(inputs, spec, folder, prefix):
    path = inputs.materialize(spec, folder, '.py')
    loader = importlib.util.spec_from_file_location(prefix + spec['sha256'], path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


def arrays_from_bytes(data):
    import numpy as np
    with np.load(io.BytesIO(data), allow_pickle=False) as saved:
        return {key: saved[key].copy() for key in saved.files}


def compare_arrays(actual, expected, tolerances):
    import numpy as np
    report = {}
    for key, reference in expected.items():
        if key not in tolerances:
            raise ValueError('Missing predeclared array tolerance: ' + key)
        if key not in actual:
            report[key] = {'passed': False, 'reason': 'component_not_returned'}
            continue
        value = np.asarray(actual[key])
        reference = np.asarray(reference)
        if value.shape != reference.shape:
            report[key] = {'passed': False, 'reason': 'shape_mismatch',
                           'actual_shape': list(value.shape), 'expected_shape': list(reference.shape)}
            continue
        tolerance = tolerances[key]
        if not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError('Invalid array tolerance')
        if not np.isfinite(value).all() or not np.isfinite(reference).all():
            raise ValueError('Nonfinite native/reference array')
        maximum = float(np.max(np.abs(value - reference))) if value.size else 0.
        report[key] = {'passed': maximum <= tolerance, 'maximum_absolute_delta': maximum,
                       'absolute_tolerance': tolerance, 'shape': list(value.shape)}
    if not report:
        raise ValueError('No reference arrays were compared')
    return {'passed': all(v['passed'] for v in report.values()), 'fields': report}


def evaluate(inputs, registry, row, native_directory, output):
    """Expected score resources are not read by this function."""
    import numpy as np
    state = inputs.json(row['state'])
    pars = state['parameters']
    if not isinstance(pars, list) or not pars or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in pars):
        raise ValueError('Invalid selected parameter vector')
    if state['region'] != 'JMA':
        raise ValueError('Regional input constructor is not yet implemented for this region')
    catalogue = arrays_from_bytes(inputs.read(row['catalogue']))
    engine = module_from_spec(inputs, registry['engine_resources']['engine.py'], output/'source', 'regional_engine_')
    os.environ['INHIBITORY_S06_NATIVE_DIR'] = str(native_directory)
    # Only the fitted vector, raw event arrays, fixed nuisance law and declared
    # interval enter numerical construction. Original score totals never do.
    arrays, metadata = engine.features(catalogue, state['nuisance'], state['start'], state['end'],
                                       state['sigma'], state['family'])
    if metadata['n_events'] != row['n_events_expected']:
        raise ValueError('Reconstructed target count differs from original row')
    expected_identity = state['original_feature_metadata']['array_sha256']
    raw_keys = ('parent_time', 'event_time', 'parent_K', 'event_K', 'parent_cell',
                'event_cell', 'parent_xy', 'event_xy', 'event_x')
    for key in raw_keys:
        if metadata['array_sha256'].get(key) != expected_identity.get(key):
            raise ValueError('Raw/event feature identity differs: ' + key)
    cache_path = output / 'features.npz'
    engine.save_cache(cache_path, arrays, metadata)
    with engine.Objective(cache_path) as objective:
        if objective.ne != row['n_events_expected']:
            raise ValueError('Native target count differs from original row')
        raw = objective.evaluate(state['arm'], pars, fine=False, detailed=True)
    score = components(raw, row['observation_measure'])
    detailed = {k: v for k, v in raw.items() if isinstance(v, np.ndarray)}
    detailed.update(event_time=arrays['event_time'], event_K=arrays['event_K'],
                    event_cell=arrays['event_cell'])
    if not all(np.isfinite(v).all() for v in detailed.values()):
        raise ValueError('Nonfinite native component array')
    detailed_path = output/'native_components.npz'
    with detailed_path.open('xb') as stream:
        np.savez_compressed(stream, **detailed)
    return {'components': score, 'n_events': metadata['n_events'], 'parameters': pars,
            'state_sha256': row['state']['sha256'], 'catalogue_sha256': row['catalogue']['sha256'],
            'feature_cache_sha256': digest(cache_path.read_bytes()),
            'feature_array_sha256': metadata['array_sha256'],
            'original_feature_hash_matches': {k: h == expected_identity.get(k)
                                             for k, h in metadata['array_sha256'].items()},
            'raw_identity_keys_required_exact': list(raw_keys),
            'native_scalar_components': {k: float(v) for k, v in raw.items()
                                         if isinstance(v, (float, int))},
            'native_array_components': {'path': detailed_path.name,
                                         'sha256': digest(detailed_path.read_bytes())},
            'feature_scope': row['feature_scope'], 'fit_scope': row['fit_scope']}, detailed


def run(registry_path, libraries_path, admission_path, output, selected, mode):
    if output.exists():
        raise FileExistsError('Output must be a new directory')
    registry_bytes = registry_path.read_bytes()
    registry = json.loads(registry_bytes)
    by_id = {row['id']: row for row in registry['rows']}
    if len(by_id) != len(registry['rows']):
        raise ValueError('Duplicate row identities')
    selected = selected if selected is not None else list(by_id)
    if not selected or len(selected) != len(set(selected)) or set(selected) - set(by_id):
        raise ValueError('Invalid ordered roster')
    admission = json.loads(admission_path.read_text(encoding='utf-8'))
    libraries_bytes = libraries_path.read_bytes()
    libraries = json.loads(libraries_bytes)
    input_manifest_bytes = (registry_path.parent/'input_manifest.json').read_bytes()
    for field, actual in [('registry_sha256', digest(registry_bytes)),
                          ('libraries_sha256', digest(libraries_bytes)),
                          ('input_manifest_sha256', digest(input_manifest_bytes)),
                          ('source_sha256', source_pins()), ('row_ids', selected), ('mode', mode)]:
        if admission.get(field) != actual:
            raise ValueError('Admission mismatch: ' + field)
    if admission.get('passed') is not True or libraries.get('registry_sha256') != digest(registry_bytes):
        raise ValueError('Unaccepted source/registry/build identity')
    native_directory = Path(libraries['native_directory']).resolve()
    build_receipt_hashes = {}
    for name in ('core', 'competitive'):
        library = libraries['libraries'][name]
        path = Path(library['path']).resolve()
        receipt_data = Path(library['build_receipt_path']).read_bytes()
        receipt = json.loads(receipt_data)
        build_receipt_hashes[name] = digest(receipt_data)
        if (path.parent != native_directory or digest(path.read_bytes()) != library['sha256']
                or library['source_sha256'] != registry['engine_sha256'][name+'.cpp']
                or build_receipt_hashes[name] != library['build_receipt_sha256']
                or receipt != library['build_receipt'] or receipt.get('passed') is not True
                or receipt['source_sha256'] != library['source_sha256']
                or receipt['library_sha256'] != library['sha256']):
            raise ValueError('Native build identity mismatch: ' + name)
    if admission.get('build_receipts_sha256') != build_receipt_hashes:
        raise ValueError('Admission build receipts differ')
    threads = admission.get('numeric_threads')
    if isinstance(threads, bool) or threads not in (1, 2):
        raise ValueError('One or two numerical threads must be declared')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = str(threads)
    import numpy as np
    from threadpoolctl import threadpool_info, threadpool_limits
    inputs = Inputs(registry_path.parent)
    output.mkdir(parents=True)
    write_new(output/'launch.json', {'admission_sha256': digest(admission_path.read_bytes()),
              'registry_sha256': digest(registry_bytes), 'source_sha256': source_pins(),
              'libraries_sha256': digest(libraries_bytes), 'build_receipts_sha256': build_receipt_hashes,
              'row_ids': selected, 'mode': mode, 'numerical_lease': admission.get('numerical_lease'),
              'runtime': {'python': sys.version, 'executable': sys.executable, 'numpy': np.__version__,
                          'platform': platform.platform(), 'numeric_threads': threads,
                          'native_evaluator_threads': 1}})
    began = time.monotonic()
    reports = []
    aliases = registry.get('aliases', [])
    for index, row_id in enumerate(selected):
        row = by_id[row_id]
        target = output/'rows'/f'{index:05d}'
        target.mkdir(parents=True)
        start = time.monotonic()
        report = {'id': row_id, 'passed': False, 'status': 'failed'}
        try:
            with threadpool_limits(limits=threads):
                if any(v['num_threads'] > threads for v in threadpool_info()):
                    raise RuntimeError('Numerical thread cap exceeded')
                actual, detailed = evaluate(inputs, registry, row, native_directory, target)
                actual['threadpools'] = threadpool_info()
                if any(v['num_threads'] > threads for v in actual['threadpools']):
                    raise RuntimeError('Evaluator loaded an excessive numerical thread pool')
            # Reference totals and arrays are read only after fresh evaluation.
            reference = inputs.json(row['expected'])
            expected = components(reference['evaluation'], row['observation_measure'])
            if expected != row['expected_components']:
                raise ValueError('Registry reference projection differs from pinned original')
            comparison = compare(actual['components'], expected, row['absolute_tolerances'])
            array_comparison = compare_arrays(detailed, arrays_from_bytes(inputs.read(row['expected_arrays'])), row['array_tolerances'])
            alias_results = []
            for alias in aliases:
                if alias['replay_row'] != row_id:
                    continue
                other = components(inputs.json(alias['reference'])['evaluation'], row['observation_measure'])
                if other != alias['expected_components']:
                    raise ValueError('Alias reference projection differs')
                alias_results.append({'table_study': alias['table_study'], 'case': alias['case'],
                                      'arm': alias['arm'], 'trend': alias['trend'],
                                      'comparison': compare(actual['components'], other, row['absolute_tolerances'])})
            passed = comparison['passed'] and array_comparison['passed'] and all(v['comparison']['passed'] for v in alias_results)
            report.update(passed=passed, status='replayed' if passed else 'failed', actual=actual,
                          comparison=comparison, array_comparison=array_comparison, aliases=alias_results)
        except Exception as error:
            report.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        report['elapsed_seconds'] = time.monotonic()-start
        write_new(target/'result.json', report)
        record = {'id': row_id, 'passed': report['passed'], 'status': report['status'],
                  'result': (target/'result.json').relative_to(output).as_posix(),
                  'sha256': digest((target/'result.json').read_bytes()), 'elapsed_seconds': report['elapsed_seconds']}
        reports.append(record)
        with (output/'progress.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record)+'\n'); stream.flush()
    result = {'schema': 'regional_raw_score_replay_result_v1', 'passed': all(r['passed'] for r in reports),
              'requested_rows': len(selected), 'completed_rows': len(reports),
              'passed_rows': sum(r['passed'] for r in reports), 'mode': mode,
              'full_registry': selected == list(by_id), 'entire_task_complete': False,
              'elapsed_seconds': time.monotonic()-began, 'rows': reports,
              'scope': 'Raw numerical feature reconstruction and unchanged saved-state likelihoods for this exact registry only. No refits, nuisance reselection, simulation, or omitted-table completion.'}
    write_new(output/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('registry', 'libraries', 'admission', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--rows', type=Path)
    parser.add_argument('--mode', choices=('pilot', 'full', 'completion'), required=True)
    args = parser.parse_args()
    rows = json.loads(args.rows.read_text(encoding='utf-8')) if args.rows else None
    result = run(args.registry, args.libraries, args.admission, args.output, rows, args.mode)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
