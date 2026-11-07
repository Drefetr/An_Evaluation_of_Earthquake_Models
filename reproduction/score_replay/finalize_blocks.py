"""Combine the exact California block replay roster without native evaluation.

An attempts manifest pins every terminal result, launch and control record, and
optionally its containing ZIP. Only retained actual partition rows enter the
original reducers. Historical references are used for comparisons afterwards.
This never builds, loads or invokes a native library or regenerates features.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import traceback
import types
import zipfile

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from reproduction.score_replay.core import Inputs, digest, resolve, write_new
from reproduction.score_replay.california_blocks_replay import (
    source_pins as scored_source_pins, compare_rows, numeric_delta, component_view)


def require_sha(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('missing/invalid SHA-256: '+label)
    return value


class Attempt:
    """Read only named, hash-bound members from one immutable attempt."""
    def __init__(self, root, spec):
        self.spec = spec
        if ('directory' in spec) == ('archive' in spec):
            raise ValueError('attempt requires exactly one directory or archive')
        self.archive = None
        self.directory = None
        if 'archive' in spec:
            path = Path(spec['archive'])
            self.archive = path.resolve() if path.is_absolute() else resolve(root, spec['archive'])
            if digest(self.archive.read_bytes()) != require_sha(spec.get('archive_sha256'), 'archive'):
                raise ValueError('attempt archive SHA mismatch')
        else:
            path = Path(spec['directory'])
            self.directory = path.resolve() if path.is_absolute() else resolve(root, spec['directory'])
        self.prefix = spec.get('prefix', '').strip('/')
        if self.prefix:
            self._name(self.prefix)

    @staticmethod
    def _name(value):
        if not isinstance(value, str) or not value or '\\' in value or ':' in value or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
            raise ValueError('unsafe attempt member')
        return value

    def read(self, name, sha):
        self._name(name)
        name = self.prefix+'/'+name if self.prefix else name
        if self.archive:
            with zipfile.ZipFile(self.archive) as stream:
                if sum(i.filename == name for i in stream.infolist()) != 1:
                    raise ValueError('missing or duplicate attempt member: '+name)
                raw = stream.read(name)
        else:
            raw = resolve(self.directory, name).read_bytes()
        if digest(raw) != require_sha(sha, name):
            raise ValueError('attempt member SHA mismatch: '+name)
        return json.loads(raw)


def terminal_roster(result, launch, expected_ids):
    """Require a complete successful stage, without accepting duplicate rows."""
    selected = launch.get('row_ids')
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected) or set(selected)-set(expected_ids):
        raise ValueError('invalid stage launch roster')
    if result.get('schema') != 'california_partition_replay_result_v1' or result.get('passed') is not True:
        raise ValueError('attempt is not a passed terminal block replay')
    if result.get('mode') != launch.get('mode') or launch.get('mode') not in ('pilot', 'completion', 'full'):
        raise ValueError('attempt mode mismatch')
    records = result.get('rows', [])
    if [r.get('id') for r in records] != selected:
        raise ValueError('terminal rows do not equal ordered launch roster')
    for key in ('requested_rows', 'completed_rows', 'passed_rows'):
        if type(result.get(key)) is not int or result[key] != len(selected):
            raise ValueError('terminal row count mismatch: '+key)
    if result.get('failed_rows') != 0:
        raise ValueError('failed stage rows')
    if any(r.get('passed') is not True or r.get('status') != 'replayed' for r in records):
        raise ValueError('non-passed stage row')
    return records


def require_union(roster, rows):
    expected = [r['id'] for r in roster]
    actual = [r['id'] for r in rows]
    if len(set(expected)) != len(expected) or len(set(actual)) != len(actual):
        raise ValueError('duplicate row in registry or attempt union')
    if set(actual) != set(expected):
        raise ValueError('incomplete/unexpected union: missing='+str(sorted(set(expected)-set(actual)))+' unexpected='+str(sorted(set(actual)-set(expected))))
    return {r['id']: r for r in rows}


def reducers_only(inputs, registry):
    """Import exact reducer/partition bytes; do not even import native wrappers."""
    package = '_california_blocks_finalizer_original'
    parent = types.ModuleType(package); parent.__path__ = []
    sys.modules[package] = parent
    out = {}
    for group in ('annual', 'sequence'):
        pkg = types.ModuleType(package+'.'+group); pkg.__path__ = []
        sys.modules[pkg.__name__] = pkg
        for name in (('partition.py', 'reducer.py') if group == 'sequence' else ('reducer.py',)):
            spec = registry['sources'][group][name]
            mod = types.ModuleType(pkg.__name__+'.'+name[:-3]); mod.__package__ = pkg.__name__
            mod.__file__ = 'original_source/'+spec['sha256']+'/'+name
            sys.modules[mod.__name__] = mod
            exec(compile(inputs.read(spec), mod.__file__, 'exec'), mod.__dict__)
        out[group] = mod
    return out


def validate_actual(report, row, inherited, tolerance):
    """Bind each retained calculation to the declared saved state and caches."""
    if report.get('id') != row['id'] or report.get('passed') is not True or report.get('status') != 'replayed':
        raise ValueError('row report identity/status mismatch')
    base, parent = inherited[row['source_registry']]
    source = next(r for r in parent['rows'] if r['id'] == row['fresh_score_row_id'])
    _, support_registry = inherited[row['support_registry']]
    support = next(r for r in support_registry['rows'] if r['id'] == row['support_row_id'])
    actual = report['actual']
    for key, value in [('state_sha256', source['state']['sha256']), ('cache_sha256', source['cache']['sha256']), ('support_cache_sha256', support['cache']['sha256'])]:
        if actual.get(key) != value:
            raise ValueError('row '+key+' mismatch')
    state = Inputs(base).json(source['state'])
    if actual.get('parameters') != state['parameters']:
        raise ValueError('row selected parameter mismatch')
    dependency = actual['fresh_dependency']
    if dependency.get('source_row_id') != source['id']:
        raise ValueError('fresh dependency identity mismatch')
    for key in ('result_sha256', 'native_arrays_sha256'):
        require_sha(dependency.get(key), 'fresh dependency '+key)
    values = actual['rows']
    if len(values) != row['expected_rows']:
        raise ValueError('retained partition count mismatch')
    expected_components = [component_view(v, row['kind']) for v in values]
    if actual.get('components') != expected_components:
        raise ValueError('retained component crosswalk mismatch')
    # This rechecks saved partition data, never a native/scientific evaluation.
    ref = Inputs(inherited['_blocks'][0]).json(row['expected'])
    expected = [r for r in ref['arm_blocks' if row['kind'] == 'annual' else 'rows'] if r['fold_id'] == row['fold'] and r['arm_id' if row['kind'] == 'annual' else 'arm'] == row['arm']]
    comparison = compare_rows(values, expected, row['kind'], tolerance)
    if not comparison['passed']:
        raise ValueError('retained partition reference mismatch')
    return values


def aggregate(inputs, registry, rows):
    reducers = reducers_only(inputs, registry)
    out = {}
    for group in ('primary_annual', 'm45_annual', 'sequence'):
        required = [r for r in registry['rows'] if r['group'] == group]
        absolute = [value for r in required for value in rows[r['id']]['actual']['rows']]
        if group == 'sequence':
            reducer = reducers['sequence']
            absolute += reducer.pool(absolute)
            reducer.conserve(absolute)
            contrasts = reducer.contrasts(absolute)
        else:
            contrasts = reducers['annual'].contrasts(absolute)
        # References enter only after all absolute rows and contrasts exist.
        ref = inputs.json(registry['references'][group])
        comparison = compare_rows(absolute, ref['rows' if group == 'sequence' else 'arm_blocks'], 'sequence' if group == 'sequence' else 'annual', registry['absolute_tolerance'])
        def key(r):
            return (r.get('fold_id'), r.get('range_id', r.get('block_id')), r.get('category'), r.get('episode_id'), r.get('candidate', r.get('contrast_id')), r.get('reference'))
        expected = ref['contrasts' if group == 'sequence' else 'contrast_blocks']
        expected_map = {key(r): r for r in expected}
        if len(expected_map) != len(expected) or len({key(r) for r in contrasts}) != len(contrasts) or set(map(key, contrasts)) != set(expected_map):
            raise ValueError('aggregate contrast roster mismatch')
        checks = [c for r in contrasts for c in numeric_delta(r, expected_map[key(r)], registry['absolute_tolerance'], str(key(r)))]
        out[group] = dict(passed=comparison['passed'] and all(c['passed'] for c in checks), absolute_rows=absolute, contrasts=contrasts, absolute_comparison=comparison, contrast_checks=checks)
    if {k: (len(v['absolute_rows']), len(v['contrasts'])) for k, v in out.items()} != {'primary_annual': (60, 45), 'm45_annual': (60, 45), 'sequence': (80, 64)}:
        raise ValueError('complete group counts differ from frozen scope')
    return out


def finalize(registry_path, attempts_path, output):
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    registry_raw = registry_path.read_bytes(); registry = json.loads(registry_raw)
    manifest_raw = attempts_path.read_bytes(); manifest = json.loads(manifest_raw)
    expected_pins = dict(registry_sha256=digest(registry_raw), input_manifest_sha256=digest((registry_path.parent/'input_manifest.json').read_bytes()), source_sha256=scored_source_pins())
    for key, value in expected_pins.items():
        if manifest.get(key) != value:
            raise ValueError('attempts manifest '+key+' mismatch')
    if len(registry['rows']) != 39:
        raise ValueError('not the frozen 39-row registry')
    inputs = Inputs(registry_path.parent)
    inherited = {'_blocks': (registry_path.parent, registry)}
    for name, spec in registry['source_registries'].items():
        base = registry_path.parent.parent
        inherited[name] = (resolve(base, spec['path']).parent, Inputs(base).json(spec))
    all_rows = []; receipt = []; labels = set(); row_receipts = []
    expected_ids = [r['id'] for r in registry['rows']]
    by_id = {r['id']: r for r in registry['rows']}
    for spec in manifest['attempts']:
        label = spec.get('label')
        if not isinstance(label, str) or not label or label in labels:
            raise ValueError('missing/duplicate attempt label')
        labels.add(label)
        attempt = Attempt(attempts_path.parent, spec)
        launch = attempt.read('launch.json', spec.get('launch_sha256'))
        result = attempt.read('result.json', spec.get('result_sha256'))
        controls = attempt.read('controls.json', spec.get('controls_sha256'))
        for key, value in expected_pins.items():
            if launch.get(key) != value:
                raise ValueError('launch '+key+' mismatch')
        if result.get('registry_sha256') != expected_pins['registry_sha256']:
            raise ValueError('result registry mismatch')
        for key in ('libraries_sha256', 'fresh_scores_sha256', 'admission_sha256'):
            require_sha(launch.get(key), 'launch '+key)
        if set(launch.get('build_receipts_sha256', {})) != {'annual', 'sequence'}:
            raise ValueError('missing interval build receipt pins')
        for key, value in launch['build_receipts_sha256'].items():
            require_sha(value, 'build '+key)
        if controls.get('passed') is not True or len(controls.get('rows', [])) != 3 or any(r.get('passed') is not True for r in controls['rows']):
            raise ValueError('mandatory analytic controls not passed')
        stage_rows = terminal_roster(result, launch, expected_ids)
        for entry in stage_rows:
            report = attempt.read(entry['result'], entry['sha256'])
            validate_actual(report, by_id[entry['id']], inherited, registry['absolute_tolerance'])
            all_rows.append(report)
            row_receipts.append(dict(id=entry['id'], attempt=label, path=entry['result'], sha256=entry['sha256'], fresh_dependency=report['actual']['fresh_dependency']))
        receipt.append(dict(label=label, result_sha256=spec['result_sha256'], launch_sha256=spec['launch_sha256'], controls_sha256=spec['controls_sha256'], archive_sha256=spec.get('archive_sha256'), rows=len(stage_rows), launch=launch))
    union = require_union(registry['rows'], all_rows)
    values = aggregate(inputs, registry, union)
    records = {}; evidence = {}
    for group, value in values.items():
        path = output/(group+'_aggregate.json'); write_new(path, value)
        spec = dict(path=path.name, sha256=digest(path.read_bytes()))
        records[group] = dict(spec, passed=value['passed'], absolute_rows=len(value['absolute_rows']), contrasts=len(value['contrasts']))
        evidence['california_blocks/'+group] = spec
    write_new(output/'regional_evidence_manifest.json', dict(records=evidence))
    result = dict(schema='california_partition_union_finalizer_v1', passed=all(v['passed'] for v in values.values()), full_registry=True, requested_rows=39, completed_rows=len(union), passed_rows=len(union), failed_rows=0, registry_sha256=expected_pins['registry_sha256'], input_manifest_sha256=expected_pins['input_manifest_sha256'], scored_source_sha256=expected_pins['source_sha256'], finalizer_sha256=digest(Path(__file__).read_bytes()), attempts_manifest_sha256=digest(manifest_raw), attempts=receipt, rows=row_receipts, aggregates=records, absolute_rows=200, contrasts=154, native_calls=0, scientific_evaluations=0, scope='Exact disjoint union of passed block replay attempts; original reducers applied to actual retained partition rows, without native evaluation, fitting, feature construction or generation.')
    write_new(output/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=Path(__file__).with_name('california_blocks')/'registry.json')
    parser.add_argument('--attempts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve()
    if output.exists():
        parser.error('output must be a new directory')
    try:
        result = finalize(args.registry.resolve(), args.attempts.resolve(), output)
    except Exception as exc:
        result = dict(passed=False, native_calls=0, scientific_evaluations=0, error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
        write_new(output/'result.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('rows', 'attempts')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
