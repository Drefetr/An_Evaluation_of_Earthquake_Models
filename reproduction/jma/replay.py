"""Reconstruct the published JMA cohort directly from original annual ZIPs.

No network, fitting, cached model features, or historical absolute paths are
required. Outputs must be new. Expected arrays are read only after reconstruction.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import sys
import time
import zipfile
import zlib

import numpy as np

try:
    from .source import parser, eligibility_v2 as eligibility, geometry_v1 as geometry, vectorized
except ImportError:
    from source import parser, eligibility_v2 as eligibility, geometry_v1 as geometry, vectorized

HERE = Path(__file__).resolve().parent
DAY = 8640000
UID_TAG = 'jma_static_row_uid_v1'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_file(path, expected_hash, expected_bytes=None):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required input: ' + path.name)
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise ValueError('Input size mismatch: ' + path.name)
    actual = sha256(path)
    if actual != expected_hash:
        raise ValueError('Input SHA-256 mismatch: ' + path.name)
    return actual


def relative_file(root, name):
    """Resolve only portable relative manifest names inside the supplied root."""
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name:
        raise ValueError('Unsafe manifest path')
    result = Path(root).joinpath(*rel.parts).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError('Manifest path escapes input root')
    return result


def dump(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def occurrence_uid(namespace, member_sha256, offset, payload):
    ph = hashlib.sha256(payload).hexdigest()
    raw = json.dumps([UID_TAG, namespace, member_sha256, int(offset), ph], separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest(), ph


def scalar_target(payload, ordinal, offset, ending, source_year, namespace, member_sha256, member_id):
    """Decode a selected occurrence with the independently preserved scalar code."""
    record = parser.parse_frame(parser.Frame(int(ordinal), int(offset), payload, ending))
    source = eligibility.SourceEvidence(member_jst_year=source_year, framing_verified=True,
                                        binding_sha256=member_sha256)
    disposition = eligibility.classify(record, source)
    # Physical completeness/datum flags are not fabricated. This command verifies
    # the recorded-row predicate and source year, rather than source-wide claims.
    if disposition.known_exclusions or disposition.unresolved_fields or 'SOURCE_JST_YEAR_MISMATCH' in disposition.source_holds:
        raise ValueError('Vector/scalar target-membership disagreement')
    uid, ph = occurrence_uid(namespace, member_sha256, offset, payload)
    return {
        'member_id': member_id, 'record_ordinal': int(ordinal), 'byte_offset': int(offset),
        'payload_sha256': ph, 'uid': uid, 'history_key_cs': disposition.history_key,
        'M_tenths': disposition.reported_tenths, 'latitude': float(record.latitude),
        'longitude': float(record.longitude), 'depth_km': float(record.numbers['depth'].value),
        'x_km': disposition.x_km, 'y_km': disposition.y_km, 'cell_id': disposition.cell,
        'zone_id': disposition.cell // 3, 'source_jst_year': source_year,
        'agency': record.codes['agency'], 'subsidiary': record.codes['subsidiary'],
        'determination': record.codes['determination'], 'primary_type': record.magnitude1.type_text,
    }


def adjudicate_unknowns(payload, decoded):
    """Preserve initial uncertainty, then apply the recorded-primary restriction."""
    blank_magnitude = (payload[:, 52:54] == 32).all(axis=1)
    blank_type = payload[:, 54] == 32
    initial_target = decoded['target']['status'] == 2
    initial_aux = decoded['aux']['status'] == 2
    nonqualifying = blank_magnitude | blank_type
    return {
        'blank_primary_magnitude': blank_magnitude,
        'blank_primary_type': blank_type,
        'initial_target_unknown': initial_target,
        'initial_auxiliary_unknown': initial_aux,
        'nonqualifying_reported_primary': nonqualifying,
        'remaining_target_unknown': initial_target & ~nonqualifying,
        'remaining_auxiliary_unknown': initial_aux & ~nonqualifying,
    }


def arrays_from_rows(rows):
    rows = sorted(rows, key=lambda r: (r['history_key_cs'], r['member_id'], r['record_ordinal']))
    keys = np.array([r['history_key_cs'] for r in rows], dtype=np.int64)
    magnitude = np.array([r['M_tenths'] for r in rows], dtype=np.int16)
    K = magnitude.astype(np.int64) - 45
    origins, ends = np.array([3652, 4748, 5844], dtype=np.int64), np.array([4748, 5844, 6940], dtype=np.int64)
    arrays = {
        'history_key_cs': keys, 't_days': keys / DAY, 'M_tenths': magnitude, 'K': K, 'Q': .1 * K,
        'xy_km': np.array([[r['x_km'], r['y_km']] for r in rows], dtype=np.float64).reshape(-1, 2),
        'latlon_deg': np.array([[r['latitude'], r['longitude']] for r in rows], dtype=np.float64).reshape(-1, 2),
        'depth_km': np.array([r['depth_km'] for r in rows], dtype=np.float64),
        'cell_id': np.array([r['cell_id'] for r in rows], dtype=np.int8),
        'zone_id': np.array([r['zone_id'] for r in rows], dtype=np.int8),
        'uid': np.array([r['uid'] for r in rows], dtype='S64'),
        'member_id': np.array([r['member_id'] for r in rows], dtype=np.int32),
        'record_ordinal': np.array([r['record_ordinal'] for r in rows], dtype=np.int64),
        'byte_offset': np.array([r['byte_offset'] for r in rows], dtype=np.int64),
        'strict_past_prefix_length': np.searchsorted(keys, keys, side='left').astype(np.int64),
        'warmup_mask': keys < 1826 * DAY,
        'fold_training_mask': (keys[None, :] >= 1826 * DAY) & (keys[None, :] < origins[:, None] * DAY),
        'fold_test_mask': (keys[None, :] >= origins[:, None] * DAY) & (keys[None, :] < ends[:, None] * DAY),
        'fold_origin_days': origins, 'fold_end_days': ends,
    }
    return rows, arrays


def compare_arrays(actual, expected_path):
    checks = {}
    with np.load(expected_path, allow_pickle=False) as expected:
        if set(expected.files) != set(actual):
            raise ValueError('Expected/reconstructed array-name mismatch')
        for name, value in actual.items():
            ref = expected[name]
            shape_dtype = value.shape == ref.shape and value.dtype == ref.dtype
            exact = shape_dtype and np.array_equal(value, ref)
            # sin/cos may differ in the last bits across platforms. All discrete
            # values, time keys, UIDs and fold masks must remain exactly equal.
            tolerance = 2e-11 if name == 'xy_km' else 0.0
            error = float(np.max(np.abs(value - ref))) if shape_dtype and value.dtype.kind == 'f' and value.size else None
            passed = bool(exact or (shape_dtype and name == 'xy_km' and np.all(np.isfinite(value)) and error <= tolerance))
            checks[name] = {'passed': passed, 'exact': bool(exact), 'shape': list(value.shape), 'dtype': str(value.dtype),
                            'maximum_absolute_error': error, 'absolute_tolerance': tolerance}
    return checks


def validate_zip(archive_path, archive):
    """Yield fully hash-checked source members without extracting filesystem paths."""
    verify_file(archive_path, archive['sha256'], archive['bytes'])
    with zipfile.ZipFile(archive_path) as zipped:
        info = zipped.infolist()
        expected = archive['members']
        if len(info) != len(expected) or len({m.filename.casefold() for m in info}) != len(info):
            raise ValueError('Unexpected or duplicate ZIP member')
        if {m.filename for m in info} != {m['name'] for m in expected}:
            raise ValueError('ZIP member roster mismatch')
        for member in expected:
            z = zipped.getinfo(member['name'])
            name = PurePosixPath(z.filename)
            if name.is_absolute() or '..' in name.parts or ':' in z.filename or '\\' in z.filename or z.flag_bits & 1 or ((z.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Unsafe ZIP member')
            if z.is_dir() != member['directory'] or z.file_size != member['uncompressed_bytes'] or z.compress_size != member['compressed_bytes'] or z.compress_type != member['compression_method'] or z.CRC != int(member['CRC32'], 16):
                raise ValueError('ZIP central metadata mismatch')
            data = zipped.read(z)
            if len(data) != member['uncompressed_bytes'] or hashlib.sha256(data).hexdigest() != member['sha256'] or f'{zlib.crc32(data):08x}' != member['CRC32']:
                raise ValueError('ZIP member content mismatch')
            if z.is_dir():
                raise ValueError('Content-only annual archive required')
            yield member, data


def replay(output, manifest_path=HERE / 'input_manifest.json', raw_dir=None):
    started = time.monotonic()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = {'schema': 'jma_raw_cohort_replay_v1', 'passed': False,
              'scope': 'Raw ZIP verification, full-record selection, selected-row scalar cross-check, projection, reported values, exact clocks and fold masks. No model fitting or forecast scoring.',
              'runtime': {'python': platform.python_version(), 'numpy': np.__version__}}
    try:
        manifest_path = Path(manifest_path).resolve()
        root = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        result['input_manifest_sha256'] = sha256(manifest_path)
        if manifest['schema'] != 'jma_public_input_manifest_v1' or [a['year'] for a in manifest['archives']] != list(range(2006, 2025)):
            raise ValueError('Expected the complete fixed 2006-2024 archive roster')
        namespace = manifest['historical_manifest_sha256']
        if len(namespace) != 64 or any(x not in '0123456789abcdef' for x in namespace):
            raise ValueError('Invalid historical UID namespace')
        expected_pin = manifest['expected_arrays']
        expected_path = relative_file(root, expected_pin['path'])
        verify_file(expected_path, expected_pin['sha256'], expected_pin['bytes'])
        summary_path = relative_file(root, manifest['expected_summary']['path'])
        verify_file(summary_path, manifest['expected_summary']['sha256'])
        saved_states = manifest['saved_states']
        verify_file(relative_file(root, saved_states['path']), saved_states['sha256'], saved_states['bytes'])
        rows, members, counts, reason_counts, adjudication_counts = [], [], Counter(), Counter(), Counter()
        member_id = 0
        quarantine_path = output / 'initial_quarantine.csv'
        with quarantine_path.open('x', encoding='utf-8', newline='') as stream:
            fields = ['member_id', 'member_name', 'record_ordinal', 'byte_offset', 'payload_sha256', 'uid',
                      'initial_target_unknown', 'initial_auxiliary_unknown', 'primary_magnitude_unreported',
                      'primary_type_undetermined', 'final_target_unknown', 'final_auxiliary_unknown']
            writer = csv.DictWriter(stream, fields)
            writer.writeheader()
            for archive in manifest['archives']:
                archive_path = relative_file(root, archive['path']) if raw_dir is None else relative_file(raw_dir, PurePosixPath(archive['path']).name)
                for member, data in validate_zip(archive_path, archive):
                    mode, stride, n, final, payload = vectorized.framing(data)
                    decoded = vectorized.decode(payload, archive['year'])
                    if not np.all(decoded['civil_ok']) or np.any(decoded['year_mismatch']):
                        raise ValueError('Invalid civil time or source-JST year mismatch')
                    counts['all_occurrences'] += n
                    summaries = {}
                    for label, prefix in [('target', 'target'), ('aux', 'auxiliary')]:
                        s = vectorized.aggregate_classification(decoded, label)
                        summaries[prefix] = s
                        for key, original in [('known_excluded', 'excluded'), ('row_predicate_passed', 'eligible'), ('unresolved_potentially_eligible', 'unresolved_potentially_eligible')]:
                            counts[prefix + '_' + key] += s[original]
                        if label == 'target':
                            reason_counts.update(s['primary_reasons'])
                    adjudicated = adjudicate_unknowns(payload, decoded)
                    for name in ['initial_target_unknown', 'initial_auxiliary_unknown', 'remaining_target_unknown', 'remaining_auxiliary_unknown']:
                        adjudication_counts[name] += int(adjudicated[name].sum())
                    adjudication_counts['target_nonqualifying_reported_primary'] += int((adjudicated['initial_target_unknown'] & adjudicated['nonqualifying_reported_primary']).sum())
                    uncertain = np.flatnonzero(adjudicated['initial_target_unknown'] | adjudicated['initial_auxiliary_unknown'])
                    for i in uncertain:
                        offset = int(i) * stride
                        raw = data[offset:offset + 96]
                        uid, ph = occurrence_uid(namespace, member['sha256'], offset, raw)
                        writer.writerow(dict(zip(fields, [member_id, member['name'], int(i), offset, ph, uid,
                            int(adjudicated['initial_target_unknown'][i]), int(adjudicated['initial_auxiliary_unknown'][i]),
                            int(adjudicated['blank_primary_magnitude'][i]), int(adjudicated['blank_primary_type'][i]),
                            int(adjudicated['remaining_target_unknown'][i]), int(adjudicated['remaining_auxiliary_unknown'][i])])) )
                    for i in np.flatnonzero(decoded['target']['status'] == 0):
                        offset = int(i) * stride
                        ending = data[offset + 96:offset + stride]
                        r = scalar_target(data[offset:offset + 96], i, offset, ending, archive['year'], namespace, member['sha256'], member_id)
                        if r['history_key_cs'] != int(decoded['key'][i]) or r['M_tenths'] != int(decoded['mag'][i]) or r['cell_id'] != int(decoded['cell'][i]) or not np.allclose([r['x_km'], r['y_km']], [decoded['x'][i], decoded['y'][i]], rtol=0, atol=2e-11):
                            raise ValueError('Vector/scalar selected-value disagreement')
                        rows.append(r)
                    members.append({'year': archive['year'], 'name': member['name'], 'sha256': member['sha256'],
                                    'framing': mode, 'final_terminator': final, 'source_records': n,
                                    'classification': summaries})
                    member_id += 1
        rows, arrays = arrays_from_rows(rows)
        with (output / 'catalogue_arrays.npz').open('xb') as stream:
            np.savez_compressed(stream, **arrays)
        with (output / 'catalogue.csv').open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, list(rows[0]) if rows else [])
            writer.writeheader()
            writer.writerows(rows)
        expected_summary = json.loads(summary_path.read_text())
        # The legacy C++/scalar processor called its scalar oracle on auxiliary
        # candidates as well; that implementation counter is not a cohort fact.
        expected_counts = {k: v for k, v in expected_summary['counts'].items() if k != 'authoritative_oracle_rows'}
        reason_counts['row_predicate_passed'] = counts['target_row_predicate_passed']
        reason_counts['unresolved_potentially_eligible'] = counts['target_unresolved_potentially_eligible']
        reason_counts = {k: v for k, v in reason_counts.items() if v}
        checks = compare_arrays(arrays, expected_path)
        count_match = dict(counts) == expected_counts
        reason_match = reason_counts == expected_summary['target_primary_reasons']
        adjudication_match = dict(adjudication_counts) == expected_summary['adjudication']
        uid_unique = len(set(r['uid'] for r in rows)) == len(rows)
        result.update(counts=dict(counts), target_primary_reasons=reason_counts,
                      adjudication=dict(adjudication_counts), members=members, array_checks=checks,
                      expected_counts_match=count_match, expected_exclusion_reasons_match=reason_match,
                      expected_adjudication_counts_match=adjudication_match,
                      selected_uid_unique=uid_unique, warmup_records=int(arrays['warmup_mask'].sum()),
                      fold_training_counts=arrays['fold_training_mask'].sum(axis=1).tolist(),
                      fold_test_counts=arrays['fold_test_mask'].sum(axis=1).tolist(),
                      selected_records_scalar_crosschecked=len(rows),
                      output_arrays_sha256=sha256(output / 'catalogue_arrays.npz'),
                      original_expected_arrays_sha256=expected_pin['sha256'],
                      initial_quarantine_sha256=sha256(quarantine_path),
                      historical_uid_namespace=namespace)
        result['passed'] = bool(count_match and reason_match and adjudication_match and uid_unique and
                                adjudication_counts['remaining_target_unknown'] == 0 and
                                all(c['passed'] for c in checks.values()))
        if not result['passed']:
            result['error'] = 'Reconstructed cohort differs from the published historical contract'
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    result['elapsed_seconds'] = time.monotonic() - started
    dump(output / 'result.json', result)
    return result


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--output', type=Path, required=True, help='New output directory; existing paths are refused')
    arg.add_argument('--manifest', type=Path, default=HERE / 'input_manifest.json')
    arg.add_argument('--raw-dir', type=Path, help='Optional directory containing the exact h2006.zip...h2024.zip files')
    args = arg.parse_args()
    try:
        result = replay(args.output, args.manifest, args.raw_dir)
    except FileExistsError:
        print('Output directory already exists; choose a fresh directory.', file=sys.stderr)
        return 2
    print(json.dumps({k: result[k] for k in ['passed', 'counts', 'warmup_records', 'fold_test_counts', 'error'] if k in result}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
