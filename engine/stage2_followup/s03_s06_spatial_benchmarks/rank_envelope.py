"""Per-origin conservative exchangeable extreme-rank envelope; no fitting."""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def envelope(vectors, names, alpha=0.05):
    x = np.asarray(vectors, dtype=float)
    if x.ndim != 2 or len(names) != x.shape[1] or len(set(names)) != len(names):
        raise ValueError('INVALID_SCHEMA')
    if len(x) < 2 or not np.isfinite(x).all() or not 0 < alpha < 1:
        raise ValueError('INVALID_VALUES')
    ranks, kept, excluded, seen = [], [], {}, {}
    for j, name in enumerate(names):
        col = x[:, j]
        if name == 'immigrant_exposure' or np.all(col == col[0]):
            excluded[name] = 'deterministic'
            continue
        ordered = np.sort(col)
        # Inclusive ranks make ties conservative; same rule for every curve.
        low = np.searchsorted(ordered, col, side='right')
        high = len(x) - np.searchsorted(ordered, col, side='left')
        rank = np.minimum(low, high)
        key = rank.tobytes()
        if key in seen:
            excluded[name] = 'identical_two_sided_ranks:' + seen[key]
            continue
        seen[key] = name
        ranks.append(rank)
        kept.append(j)
    if not ranks:
        return dict(p_value=1.0, reject=False, alpha=alpha,
                    retained_coordinates=[], excluded=excluded,
                    lower=[], upper=[], degenerate=True, curves=len(x))
    extreme = np.min(np.stack(ranks, axis=1), axis=1)
    p = float(np.count_nonzero(extreme <= extreme[0]) / len(x))
    # Curves with conservative global rank p > alpha define the envelope.
    ordered = np.sort(extreme)
    all_p = np.searchsorted(ordered, extreme, side='right') / len(x)
    retained = x[all_p > alpha][:, kept]
    return dict(p_value=p, reject=p <= alpha, alpha=alpha, curves=len(x),
                observed_extreme_rank=int(extreme[0]),
                retained_coordinates=[names[j] for j in kept], excluded=excluded,
                lower=np.min(retained, axis=0).tolist(),
                upper=np.max(retained, axis=0).tolist(), degenerate=False,
                method='inclusive two-sided pointwise ranks; minimum across coordinates; inclusive Monte Carlo rank across all curves')


def flatten(stats):
    names, values = [], []
    for key in sorted(stats):
        a = np.asarray(stats[key], dtype=float)
        if a.ndim == 0:
            names.append(key); values.append(float(a))
        elif a.ndim == 1:
            for i, value in enumerate(a):
                names.append(f'{key}[{i}]'); values.append(float(value))
        else:
            raise ValueError('INVALID_COORDINATE_DIMENSION')
    return names, values


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def campaign(manifest_path, observed_root, observed_jobs):
    manifest = load(manifest_path)
    if manifest['R'] != 999 or sorted(manifest['origins']) != [f'california_fold_{i}' for i in range(3)]:
        raise ValueError('PLANNED_DENOMINATOR')
    results, pins = {}, {str(manifest_path): digest(manifest_path)}
    for origin in manifest['origins']:
        obsbase = Path(observed_root) / origin
        observed = obsbase / 'scalars.json'
        obsreceipt_path = obsbase / 'receipt.json'
        obsreceipt = load(obsreceipt_path)
        obsjob_path = Path(observed_jobs) / (origin + '.json')
        obsjob = load(obsjob_path)
        state_path = manifest['state_bindings'][origin]['path']
        if (digest(state_path) != manifest['state_bindings'][origin]['sha256'] or
            digest(obsjob['state_npz']) != obsjob['state_sha256'] or
            obsreceipt['status'] != 'complete' or obsreceipt['scalars_sha256'] != digest(observed) or
            obsreceipt['case_id'] != origin or obsreceipt['mode'] != 'observed' or
            obsreceipt['binary_sha256'] != manifest['binary_sha256'] or
            obsreceipt['adapter_sha256'] != manifest['adapter_sha256'] or
            obsreceipt['input_state_sha256'] != obsjob['state_sha256'] or
            obsreceipt['job_sha256'] != digest(obsjob_path) or
            obsjob['mode'] != 'observed' or obsjob['case_id'] != origin):
            raise ValueError('OBSERVED_BINDING')
        with np.load(state_path, allow_pickle=False) as sim, np.load(obsjob['state_npz'], allow_pickle=False) as obs:
            if set(obs.files) != set(sim.files) | {'observed'}:
                raise ValueError('STATE_SCHEMA')
            if not all(np.array_equal(sim[k], obs[k]) for k in sim.files):
                raise ValueError('OBSERVED_SIMULATION_STATE_DIFFERENCE')
        for path in (state_path, obsjob['state_npz'], obsjob_path, obsreceipt_path):
            pins[str(path)] = digest(path)
        names, row = flatten(load(observed)['stats'])
        rows = [row]
        pins[str(observed)] = digest(observed)
        records = sorted((r for r in manifest['cases'] if r['case_id'] == origin), key=lambda r:r['index'])
        if [r['index'] for r in records] != list(range(999)):
            raise ValueError('MISSING_DUPLICATE_INDEX')
        for record in records:
            if digest(record['job_path']) != record['job_sha256']:
                raise ValueError('JOB_PIN')
            job = load(record['job_path'])
            if (job['case_id'] != origin or job['index'] != record['index'] or
                job['phase'] != 'production' or job['mode'] != 'simulate' or
                job['state_sha256'] != manifest['state_bindings'][origin]['sha256'] or
                job['binary_sha256'] != manifest['binary_sha256']):
                raise ValueError('JOB_IDENTITY')
            receipt_path = Path(record['receipt_path'])
            receipt = load(receipt_path)
            scalar_path = receipt_path.parent / 'scalars.json'
            if (receipt['status'] != 'complete' or receipt['case_id'] != origin or
                receipt['index'] != record['index'] or receipt['phase'] != 'production' or
                receipt['mode'] != 'simulate' or receipt['adapter_sha256'] != manifest['adapter_sha256'] or
                receipt['job_sha256'] != record['job_sha256'] or
                receipt['input_state_sha256'] != manifest['state_bindings'][origin]['sha256'] or
                receipt['binary_sha256'] != manifest['binary_sha256'] or
                receipt['scalars_sha256'] != digest(scalar_path)):
                raise ValueError('RECEIPT_BINDING')
            actual_names, row = flatten(load(scalar_path)['stats'])
            if actual_names != names or len(names) != 84:
                raise ValueError('VECTOR_SCHEMA')
            rows.append(row)
            pins[str(scalar_path)] = digest(scalar_path)
            pins[str(receipt_path)] = digest(receipt_path)
            pins[str(record['job_path'])] = digest(record['job_path'])
        result = envelope(rows, names)
        # The per-coordinate envelope is private; public output uses aggregate evidence.
        results[origin] = result
    return dict(schema='scientific_remediation_OC_rank_envelope_v1',
                status='computed_from_saved_vectors_not_full_raw_replay',
                retrospective=True, parameter_conditional=True,
                cross_origin_joint_test=False, simulated_paths=2997,
                full_raw_replay_completed_here=0, origins=results, input_pins=pins)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True); p.add_argument('--observed-root', required=True)
    p.add_argument('--observed-jobs', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args(); out = Path(a.output)
    if out.exists(): raise FileExistsError('APPEND_ONLY_OUTPUT')
    result = campaign(a.manifest, a.observed_root, a.observed_jobs)
    result['source_sha256'] = digest(__file__)
    out.write_text(json.dumps(result, indent=2, allow_nan=False))
    print(json.dumps({'status':result['status'], 'paths':result['simulated_paths'],
                      'p_values':{k:v['p_value'] for k,v in result['origins'].items()}}))
