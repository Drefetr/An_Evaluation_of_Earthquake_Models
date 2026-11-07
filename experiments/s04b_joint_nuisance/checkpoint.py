"""Strict JSON persistence and validation of one reviewed frozen-training resume."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import numpy as np


def scalar(value):
    """Convert representable NumPy types without masking nonfinite/unknown values."""
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating) and value.dtype.itemsize <= 8:
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f'Unsupported JSON value: {type(value).__name__}')


def dumps(value, **kwargs):
    return json.dumps(value, default=scalar, allow_nan=False, **kwargs)


def write(path, value):
    """Validate before opening a unique temporary file; preserve the last checkpoint."""
    path = Path(path)
    payload = dumps(value, indent=2) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                prefix=path.name + '.', suffix='.tmp', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical_training(report, keys):
    return dumps({key: report[key] for key in keys}, sort_keys=True,
                 separators=(',', ':')).encode('utf-8')


def validate_training(report, trace, policy):
    """Pure custody/structure checks; no objective, gradient, selection or fit call."""
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    require(report['case_id'] == policy['case_id'], 'Wrong resume case')
    require(report['training_selections_frozen'] is True, 'Training was not frozen')
    require(not report['passed'] and not report['outcomes'], 'Resume is not an unfinished test phase')
    require(set(report['fits']) == {'null', 'LI', 'LIplus_immigrant', 'LIplus_inclusive'}, 'Incomplete four-arm resume')
    require(set(report['training_checks']) == set(report['fits']), 'Missing training checks')
    require(len(report['floor_checks']) == 3 and all(v['phase'] == 'train' for v in report['floor_checks']), 'Invalid train-floor checks')
    require(len(report['historical_comparisons']) == 5, 'Missing historical comparisons')
    for name, fitted in report['fits'].items():
        require(fitted['passed'] is True and fitted['required_starts'] == 8
                and fitted['resolved_starts'] == [True] * 8, 'Unresolved training starts')
        require(report['training_checks'][name]['passed'] is True, 'Failed selected training check')
        require(report['training_checks'][name]['parameters'] == fitted['selected']['parameters'], 'Selected state mismatch')
        require(fitted['selected'] == fitted['candidates'][fitted['selected_state_index']], 'Selected candidate mismatch')
    require(digest(trace) == policy['attempts_sha256'], 'Changed training trace')
    require(hashlib.sha256(canonical_training(report, policy['training_payload_keys'])).hexdigest()
            == policy['training_payload_canonical_sha256'], 'Changed frozen training payload')
    return report
