"""Evaluate an original cached objective at its selected saved parameter vector."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

from .core import components, digest, pointer


def evaluate(inputs, row, adapter, library, output: Path):
    """No expected-score argument exists in this numerical interface."""
    state = inputs.json(row['state'])
    pars = pointer(state, row.get('parameter_pointer', '/parameters'))
    if not isinstance(pars, list) or not pars or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in pars):
        raise ValueError('selected parameters must be a finite numeric vector')
    module_path = inputs.materialize(adapter['python'], output / 'sources', '.py')
    cache_path = inputs.materialize(row['cache'], output / 'inputs', '.npz')
    library_path = Path(library['path']).resolve()
    if digest(library_path.read_bytes()) != library['sha256']:
        raise ValueError('numerical library SHA-256 mismatch')
    if library['source_sha256'] != adapter['native']['sha256']:
        raise ValueError('library was not built from the pinned evaluator source')
    module_spec = importlib.util.spec_from_file_location(
        'archived_score_' + adapter['python']['sha256'], module_path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    with module.Objective(cache_path, dll_path=library_path) as objective:
        count = getattr(objective, 'ne', None)
        if not isinstance(row.get('n_events_expected'), int) or row['n_events_expected'] < 0:
            raise ValueError('expected event count must be a declared nonnegative integer')
        if count != row['n_events_expected']:
            raise ValueError('evaluated event count differs from the original row')
        raw = objective.evaluate(row['model'], pars)
        result = components(raw, row['observation_measure'])
        result['n_events'] = count
    import numpy as np
    arrays = {name: value for name, value in raw.items() if isinstance(value, np.ndarray)}
    if any(not np.isfinite(value).all() for value in arrays.values()):
        raise ValueError('nonfinite detailed native component')
    array_record = None
    if arrays:
        array_path = output / 'native_components.npz'
        with array_path.open('xb') as stream:
            np.savez_compressed(stream, **arrays)
        array_record = {'path': array_path.name, 'sha256': digest(array_path.read_bytes()),
                        'fields': {name: {'shape': list(value.shape), 'dtype': str(value.dtype)}
                                   for name, value in arrays.items()}}
    return {'components': result, 'parameters': pars,
            'native_scalar_components': {name: float(value) for name, value in raw.items()
                                         if isinstance(value, (int, float))},
            'native_array_components': array_record,
            'state_sha256': row['state']['sha256'],
            'cache_sha256': row['cache']['sha256'],
            'python_source_sha256': adapter['python']['sha256'],
            'native_source_sha256': adapter['native']['sha256'],
            'library_sha256': library['sha256'],
            'evaluation_scope': 'original cached-feature likelihood at unchanged saved parameters'}
