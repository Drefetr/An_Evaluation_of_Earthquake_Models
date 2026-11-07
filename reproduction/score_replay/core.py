"""Custody, score semantics and comparisons shared by replay adapters.

Historical expected scores never enter an evaluator. They are compared only
after an evaluator has returned its new components.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import zipfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise ValueError('resource paths must be nonempty portable relative paths')
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or path == root.resolve() or root.resolve() not in path.parents:
        raise ValueError('resource path escapes its root')
    return path


def pointer(value, path: str):
    if path == '':
        return value
    if not path.startswith('/'):
        raise ValueError('JSON pointer must be empty or begin with slash')
    for part in path[1:].split('/'):
        key = part.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


class Inputs:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def read(self, spec: dict) -> bytes:
        if 'archive' in spec:
            archive = resolve(self.root, spec['archive'])
            member = spec['member']
            if member.startswith('/') or '\\' in member or '..' in Path(member).parts:
                raise ValueError('invalid archive member')
            with zipfile.ZipFile(archive) as source:
                if sum(i.filename == member for i in source.infolist()) != 1:
                    raise ValueError('missing or duplicate archive member')
                data = source.read(member)
        else:
            data = resolve(self.root, spec['path']).read_bytes()
        if digest(data) != spec['sha256']:
            raise ValueError('input SHA-256 mismatch')
        if 'bytes' in spec and len(data) != spec['bytes']:
            raise ValueError('input length mismatch')
        return data

    def json(self, spec: dict):
        return json.loads(self.read(spec).decode('utf-8-sig'))

    def materialize(self, spec: dict, output: Path, suffix: str) -> Path:
        if suffix not in ('.npz', '.py', '.cpp', '.json', '.csv'):
            raise ValueError('unsupported materialization suffix')
        data = self.read(spec)
        output.mkdir(parents=True, exist_ok=True)
        path = output / (spec['sha256'] + suffix)
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError('materialized input changed')
        else:
            with path.open('xb') as stream:
                stream.write(data)
        return path


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('nonfinite or nonnumeric score component: ' + name)
    return float(value)


def first(raw, names, *, required=True):
    for name in names:
        if name in raw:
            return finite(raw[name], name)
    if required:
        raise ValueError('missing evaluator field: ' + '/'.join(names))
    return None


def components(raw: dict, observation_measure: str) -> dict:
    """Crosswalk actual evaluator values; never copy a reference or invent M."""
    if observation_measure not in ('time_mark', 'time_zone_mark', 'time_cell_mark', 'space_time_mark'):
        raise ValueError('undeclared observation measure')
    exposure = first(raw, ('E', 'integrated_intensity', 'exposure', 'compensator'))
    if exposure < 0:
        raise ValueError('negative integrated intensity')
    marks = first(raw, ('M', 'mark_logscore', 'mark_score', 'marks', 'mark'))
    timing = first(raw, ('timing_logscore', 'regional_timing_logscore', 'timing'), required=False)
    point = first(raw, ('P', 'event_log_point_intensity_sum', 'event_log_intensity_sum', 'point'), required=False)
    if point is None and observation_measure == 'time_mark' and timing is not None:
        point = timing + exposure
    if point is None:
        raise ValueError('evaluator cannot determine event intensity sum')
    joint = point - exposure + marks
    reported_joint = first(raw, ('joint_logscore', 'full_joint_logscore', 'joint'), required=False)
    if reported_joint is None:
        nll = first(raw, ('joint_nll', 'raw_joint_nll', 'nll'), required=False)
        reported_joint = -nll if nll is not None else None
    if reported_joint is not None and abs(reported_joint - joint) > 1e-7:
        raise ValueError('evaluator joint decomposition disagrees')
    if observation_measure == 'time_mark':
        if timing is not None and abs(timing - (point - exposure)) > 1e-7:
            raise ValueError('temporal evaluator decomposition disagrees')
        location = None
    elif timing is not None:
        location = joint - timing - marks
    else:
        location = None
    return {'P': point, 'E': exposure, 'C': -exposure, 'M': marks,
            'timing': timing, 'location': location, 'joint': joint,
            'observation_measure': observation_measure}


def compare(actual: dict, expected: dict, absolute_tolerances: dict) -> dict:
    """Absolute functional checks, distinct from rounded manuscript displays."""
    fields = {}
    for key in ('P', 'E', 'C', 'M', 'timing', 'location', 'joint'):
        if expected.get(key) is None:
            continue
        if actual.get(key) is None:
            fields[key] = {'passed': False, 'reason': 'component_not_returned'}
            continue
        if key not in absolute_tolerances:
            raise ValueError('no predeclared tolerance for ' + key)
        tolerance = finite(absolute_tolerances[key], key + '_tolerance')
        if tolerance < 0:
            raise ValueError('negative tolerance')
        delta = finite(actual[key], key) - finite(expected[key], key)
        fields[key] = {'actual': actual[key], 'expected': expected[key],
                       'delta': delta, 'absolute_tolerance': tolerance,
                       'passed': abs(delta) <= tolerance}
    if not fields:
        raise ValueError('no comparable reference components')
    return {'passed': all(v['passed'] for v in fields.values()), 'fields': fields,
            'comparison': 'full_precision_original; absolute tolerance; rtol=0'}


def write_new(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
