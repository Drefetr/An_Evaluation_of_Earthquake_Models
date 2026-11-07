"""Recompute the shared exponential mark score from the exact SCEDC cohort.

No intensity evaluator, fit, native library, generation, or beta estimation.
The archived benchmark stores M as a scalar; this separate check reconstructs
it from the recovered event magnitudes and the unchanged saved beta.
"""
from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from reproduction.score_replay.core import Inputs, digest, pointer

PINS = {
    'reproduction/nzca/expected/california_events.json': 'da07f2853671b330fa3d93157d5d84f8713392fd6071b549df46a293c6e7b14e',
    'reproduction/nzca/cohort_contract_california.json': 'dbddca525d1287f249a050e0381ec39961547b3586a7c954ca5ec234d24bcceb',
    'reproduction/score_replay/california/registry.json': 'ffbc58f806c6d9db15d0c629a2c88c762936bae778ef28268e5b26588a346f99',
    'reproduction/score_replay/california_benchmark/registry.json': '570b3684477ae6dfa91a80a113132617d7adbb5e4c2619be7252ac52c983d0df',
}
EPOCH = dt.datetime(1981, 1, 1, tzinfo=dt.timezone.utc)
ABSOLUTE_TOLERANCE = 1e-6  # Unchanged cached-functional comparison tolerance.


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return digest(Path(path).read_bytes())


def source_pins():
    return {name: sha(ROOT/name) for name in (
        'reproduction/score_replay/california_mark_replay.py',
        'reproduction/score_replay/core.py')}


def select_events(events, start, end, threshold):
    """Original UTC/[start,end) selection and recorded magnitude arithmetic."""
    require(math.isfinite(start) and math.isfinite(end) and start < end, 'Invalid window')
    require(threshold in (4., 4.5), 'Undeclared magnitude threshold')
    selected = []
    previous = None
    seen = set()
    for event in events:
        stamp = dt.datetime.fromisoformat(event['origin_time_utc'].replace('Z', '+00:00'))
        require(stamp.utcoffset() == dt.timedelta(0), 'Non-UTC event')
        t = (stamp-EPOCH).total_seconds()/86400
        eid = event['event_id']
        key = (t, eid)
        require(previous is None or key >= previous, 'Cohort order changed')
        require(eid not in seen, 'Duplicate cohort event identity')
        seen.add(eid); previous = key
        magnitude = float(event['magnitude'])
        if threshold == 4.5:
            token = Decimal(event['source_tokens']['magnitude'])
            require(float(token) == magnitude, 'Recorded magnitude/token disagree')
            eligible = token >= Decimal('4.5')
            excess = float(token)-4.5
        else:
            eligible = magnitude >= 4.
            excess = magnitude-4.
        require(math.isfinite(magnitude), 'Nonfinite magnitude')
        if eligible and start <= t < end:
            selected.append(dict(event_id=eid, time=t, excess=excess))
    return selected


def mark_score(excesses, beta):
    require(isinstance(beta, (int, float)) and not isinstance(beta, bool)
            and math.isfinite(beta) and beta > 0, 'Invalid saved beta')
    require(all(math.isfinite(q) and q >= 0 for q in excesses), 'Invalid magnitude excess')
    return len(excesses)*math.log(beta)-beta*math.fsum(excesses)


def raw_mark(events, metadata, threshold):
    selected = select_events(events, metadata['start'], metadata['end'], threshold)
    value = mark_score([x['excess'] for x in selected], metadata['beta'])
    return selected, value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def run(admission_path, output):
    import numpy as np
    require(not output.exists(), 'Output must be a fresh directory')
    admission = json.loads(admission_path.read_bytes())
    require(admission.get('passed') is True, 'Reviewed arithmetic admission required')
    require(admission.get('source_sha256') == source_pins(), 'Source admission mismatch')
    require(admission.get('inputs_sha256') == PINS, 'Input admission mismatch')
    for name, expected in PINS.items():
        require(sha(ROOT/name) == expected, 'Changed input: '+name)
    events = json.loads((ROOT/'reproduction/nzca/expected/california_events.json').read_bytes())
    groups = {}
    for group in ('california', 'california_benchmark'):
        base = ROOT/'reproduction/score_replay'/group
        groups[group] = (base, json.loads((base/'registry.json').read_bytes()))
    roster = [r['id'] for _, registry in groups.values() for r in registry['rows']]
    require(admission.get('row_ids') == roster and len(set(roster)) == len(roster), 'Exact row admission mismatch')
    output.mkdir(parents=True)
    write(output/'launch.json', dict(source_sha256=source_pins(), inputs_sha256=PINS,
          admission_sha256=sha(admission_path), row_ids=roster,
          scope='Saved-beta mark arithmetic from recovered cohort; no native/intensity evaluation or fitting'))
    results = []; primary = {}
    for group, (base, registry) in groups.items():
        inputs = Inputs(base)
        for row in registry['rows']:
            report = dict(id=row['id'], passed=False)
            try:
                with np.load(io.BytesIO(inputs.read(row['cache'])), allow_pickle=False) as cache:
                    metadata = json.loads(cache['metadata_json'].item())
                    threshold = 4.5 if row['study'] == 'california_m45' else 4.
                    if threshold == 4.5:
                        require(metadata.get('scenario_minimum_magnitude') == '4.5'
                                and metadata.get('scenario_excess_arithmetic') == 'float(Decimal(raw_magnitude_token))-4.5', 'M4.5 recipe identity')
                    selected, actual = raw_mark(events, metadata, threshold)
                    times = np.asarray([x['time'] for x in selected], dtype=np.float64)
                    excess = np.asarray([x['excess'] for x in selected], dtype=np.float64)
                    require(len(selected) == row['n_events_expected'] == metadata['n_events'], 'Target count mismatch')
                    require(np.array_equal(times, cache['event_time']), 'Raw event order/time mismatch')
                    key = (row['case'], row['phase'])
                    if group == 'california':
                        require(np.array_equal(excess, cache['event_excess']), 'Raw/cached magnitude excess mismatch')
                        if threshold == 4.:
                            identity = (metadata['beta'], cache['event_time'].tobytes(), cache['event_xy'].tobytes(), cache['event_cell'].tobytes())
                            if key in primary:
                                require(primary[key] == identity, 'Primary procedures use different event/mark law')
                            primary[key] = identity
                    else:
                        require(primary[key] == (metadata['beta'], cache['event_time'].tobytes(), cache['event_xy'].tobytes(), cache['event_cell'].tobytes()), 'Benchmark/primary event membership or beta differs')
                    report.update(actual_M=actual, saved_beta=metadata['beta'], n_events=len(selected),
                        magnitude_threshold=threshold, cache_sha256=row['cache']['sha256'],
                        time_array_sha256=digest(times.tobytes()), excess_array_sha256=digest(excess.tobytes()),
                        event_ids_sha256=digest(json.dumps([x['event_id'] for x in selected], separators=(',', ':')).encode()),
                        benchmark_membership_matches_primary=group == 'california_benchmark')
                    # Reference scalar is first read after independent magnitude arithmetic.
                    state = inputs.json(row['state'])
                    expected = pointer(state, row['expected_pointer'])['M']
                    delta = actual-expected
                    if group == 'california_benchmark':
                        require(metadata['marks'] == expected, 'Cached mark/reference mismatch')
                    report.update(expected_M=expected, delta=delta, absolute_tolerance=ABSOLUTE_TOLERANCE,
                                  passed=abs(delta) <= ABSOLUTE_TOLERANCE)
            except Exception as exc:
                report.update(error_type=type(exc).__name__, error=str(exc))
            path = output/'rows'/f'{len(results):05d}.json'; write(path, report)
            results.append(dict(id=row['id'], passed=report['passed'], path=path.relative_to(output).as_posix(), sha256=sha(path)))
    result = dict(passed=all(r['passed'] for r in results), requested_rows=len(roster), completed_rows=len(results),
                  rows=results, scope='Common M only; historical intensity outputs remain separately classified')
    write(output/'result.json', result)
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    return run(args.admission.resolve(), args.output.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
