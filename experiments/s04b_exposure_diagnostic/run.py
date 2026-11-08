"""Observe one failed training vector at the two original quadrature orders.

This command does not fit, construct a held-out phase, repair an objective, or
classify the failed research case as complete. Its passed flag describes only
whether the requested diagnostic observations were retained.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROCESS_STARTED = time.monotonic()


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),
        parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON '+v)))


def require(value, message):
    if not value:
        raise ValueError(message)


def safe(root, relative):
    p = (root/relative).resolve()
    require(not Path(relative).is_absolute() and p.is_relative_to(root.resolve()), 'Escaping path')
    return p


def json_value(value):
    """Explicit tags retain nonfinite observations without invalid JSON."""
    if hasattr(value, 'tolist'):
        return json_value(value.tolist())
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {'nonfinite': 'nan' if math.isnan(value) else ('+inf' if value > 0 else '-inf')}
    return value


def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(json_value(value), f, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temporary, path)


def source_identity():
    """Metadata only: no scientific module is imported here."""
    p = read(HERE/'protocol.json')
    paths = list(p['source_sha256'])+[x.relative_to(REPO).as_posix() for x in HERE.iterdir()
                                    if x.is_file() and x.suffix in ('.py', '.json')]
    return {relative: sha(safe(REPO, relative)) for relative in sorted(set(paths))}


def verify_protocol():
    """Validate frozen dependency/input identities before importing science."""
    p = read(HERE/'protocol.json')
    require(p['schema'] == 'joint_exposure_diagnostic_protocol_v1'
            and p['case_id'] == 'S6_narrow_short_total_seed410603'
            and p['model'] == 'LIplus_inclusive' and p['orders'] == [8, 16]
            and p['phase'] == dict(start=30, end=395), 'Wrong diagnostic scope')
    require(p['resources'] == dict(wall_seconds=300, threads=2, workers=1,
            sampled_process_tree_rss_cap_bytes=6442450944, minimum_host_free_bytes=2147483648),
            'Diagnostic resource bounds differ')
    require(len(p['theta']) == 8 and all(math.isfinite(v) for v in p['theta']), 'Invalid fixed vector')
    for kind in ('source_sha256', 'input_sha256'):
        for relative, expected in p[kind].items():
            require(sha(safe(REPO, relative)) == expected, 'Changed '+kind+': '+relative)
    prior = p['prior_archive']
    require(sha(safe(REPO, prior['path'])) == prior['sha256'], 'Failed archive differs')
    require(sha(safe(REPO, prior['review'])) == prior['review_sha256'], 'Failed audit differs')
    audit = read(safe(REPO, prior['review']))
    require(audit['audit_passed'] is True and audit['passed'] is False
            and audit['artifact_sha256'] == prior['sha256'], 'Failed predecessor status differs')
    return p


def prior_evidence(prior, protocol):
    for relative, expected in protocol['prior_files_sha256'].items():
        require(sha(safe(prior, relative)) == expected, 'Prior extracted member differs: '+relative)
    child = safe(prior, protocol['prior_child'])
    result = read(child/'science/result.json')
    case = read(child/'science/cases'/(protocol['case_id']+'.json'))
    records = case['fits'][protocol['model']]['records']
    pair = records[-2:]
    require(len(pair) == 2 and [r['method'] for r in pair] == ['L-BFGS-B', 'Powell']
            and all(r['start_index'] == 4 and r['initial_parameters'] == protocol['theta']
                    and r['status'] == 'exception' and r['error_type'] == 'ArithmeticError'
                    and r['error'] == 'Nonfinite or negative full exposure' for r in pair),
            'Failed initial vector/exception differs')
    require(result['passed'] is False and not result['disposition_valid']
            and not case['outcomes'] and case['status'] == 'unknown', 'Predecessor must remain failed')
    require(result['runtime']['essential'] == protocol['runtime_essential'], 'Pinned runtime differs')
    return result, case


def observed_original(phase, theta, order, model_module):
    """Read locals from the unmodified evaluator's actual frame on exception."""
    try:
        score, gradient = phase.evaluate(theta, 'LIplus_inclusive', order, True)
        return dict(returned=True, score=score, gradient=gradient,
                    scalars={k: score[k] for k in ('P', 'E', 'M', 'joint')},
                    finite={k: math.isfinite(score[k]) for k in ('P', 'E', 'M', 'joint')},
                    exposure_gate_passed=score['E'] >= -1e-9)
    except ArithmeticError as exc:
        tb = exc.__traceback__; locals_ = None
        while tb is not None:
            if tb.tb_frame.f_code is model_module.Phase.evaluate.__code__:
                locals_ = tb.tb_frame.f_locals
            tb = tb.tb_next
        scalars = {k: float(locals_[k]) for k in ('P', 'E', 'joint')
                   if locals_ is not None and k in locals_}
        scalars['M'] = float(phase.M)
        return dict(returned=False, error_type=type(exc).__name__, error=str(exc), scalars=scalars,
                    finite={k: math.isfinite(v) for k, v in scalars.items()},
                    exposure_gate_passed=math.isfinite(scalars.get('E', math.nan)) and scalars.get('E', -math.inf) >= -1e-9,
                    gradient=locals_.get('gradient') if locals_ is not None else None,
                    frame_observed=locals_ is not None)


class NativeObserver:
    """Return exactly the original native object, even if diagnostics fail."""
    def __init__(self, native, diagnostic, array_identity, output, deadline):
        self.native = native; self.diagnostic = diagnostic
        self.array_identity = array_identity; self.output = Path(output)
        self.deadline = deadline; self.lock = threading.Lock()
        self.order = None; self.grid = None; self.chunks = None

    def integrate(self, *prepared):
        started = time.monotonic(); r2 = prepared[2]
        start = (r2.ctypes.data-self.grid['r2'].ctypes.data)//self.grid['r2'].strides[0]
        record = dict(row_start=int(start), space_nodes=len(r2), order=self.order,
                      inputs={name: self.array_identity(value) for name, value in zip(
                          ('parent_time', 'marks', 'r2', 'area', 'background', 'times', 'weights', 'triggering', 'theta'), prepared[:9])},
                      horizon=prepared[9], native_return=None, diagnostic=None)
        try:
            value = self.native.integrate(*prepared)
            record['native_return'] = value.copy()
            record['native_seconds'] = time.monotonic()-started
            try:
                record['diagnostic'] = self.diagnostic(*prepared, deadline=self.deadline)
            except BaseException as exc:
                record['diagnostic_error'] = dict(type=type(exc).__name__, message=str(exc))
            return value
        except BaseException as exc:
            record['native_error'] = dict(type=type(exc).__name__, message=str(exc))
            raise
        finally:
            record['elapsed_seconds'] = time.monotonic()-started
            path = self.output/f'order{self.order}'/f'chunk_{start:06d}.json'
            with self.lock:
                write(path, record)
                self.chunks.append(record)


def run(args):
    out = Path(args.output).resolve(); prior = Path(args.prior).resolve()
    require(not out.exists() and not out.is_relative_to(REPO)
            and not out.is_relative_to(prior), 'Fresh external diagnostic output required')
    out.mkdir(parents=True)
    result = dict(schema='joint_exposure_diagnostic_result_v1', passed=False,
                  scientific_completion=False, fitting_performed=False, optimizer_calls=0,
                  held_out_evaluations=0, parameter_vectors_evaluated=0, orders=[], status='preflight')
    write(out/'result.json', result)
    try:
        require(args.wall_seconds == 300, 'Exactly the reviewed diagnostic cap is required')
        deadline = PROCESS_STARTED+args.wall_seconds
        p = verify_protocol(); old, saved = prior_evidence(prior, p)
        result.update(case_id=p['case_id'], theta=p['theta'], model=p['model'], phase=p['phase'],
                      source_sha256=source_identity(), protocol_sha256=sha(HERE/'protocol.json'),
                      input_sha256=p['input_sha256'], prior_files_sha256=p['prior_files_sha256'],
                      prior_archive=p['prior_archive'], resources=p['resources'],
                      original_case_remains_failed=True)
        require(datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(p['shared_run']['expires_utc']), 'Shared diagnostic window expired')
        # All dependency and input pins above are checked before scientific imports.
        for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
            os.environ[key] = '2'
        import numpy as np
        from threadpoolctl import threadpool_limits, threadpool_info
        from experiments.s04b_joint_execution import driver as legacy
        from experiments.s04b_joint_execution.parallel_chunks import ParallelPhase
        from .numerics import same_node_sums, combine_chunks, array_identity
        frozen, model = legacy.frozen, legacy.model
        runtime = frozen.runtime_identity()
        require(runtime['essential'] == p['runtime_essential'], 'Exact original runtime required')
        result['runtime'] = runtime
        library = safe(prior, 'build/attenuation.so'); build = read(safe(prior, 'build/build_receipt.json'))
        require(build['passed'] is True and build['source_sha256'] == p['source_sha256']['experiments/s04b_joint_nuisance/attenuation.cpp']
                and build['library_sha256'] == sha(library), 'Original native build provenance differs')
        result.update(library_sha256=sha(library), build_receipt_sha256=sha(prior/'build/build_receipt.json'))
        modules = model.archived()
        c = p['input_case']; root = REPO/'reproduction/synthetic'
        with np.load(root/c['history'], allow_pickle=False) as z:
            rows = z['rows'].copy()
        require(array_identity(rows)['sha256'] == c['rows_sha256'] and rows.ndim == 2 and rows.shape[1] == 4
                and np.isfinite(rows).all() and np.all(np.diff(rows[:, 0]) >= 0), 'Exact history array required')
        G = modules['generator']; name = G.MATCHED_NAMES[c['regime']-4]
        _, bg, eta, ell, psi = G.ROSTER[name]
        law = G.Law(name, c['seed'], bg, eta, ell, psi); gm = G.fitting_metadata(law)
        require(dict(**gm, productivity_ratio_r=law.r, spatial_kernel_exponent=2) == saved['fixed_spatial_mark_law'], 'Original fixed law differs')
        theta = np.asarray(p['theta'], dtype=float)
        native = model.Native(library)
        observer = NativeObserver(native, same_node_sums, array_identity, out, deadline)

        class ObservedPhase(ParallelPhase):
            def baseline(self, value):
                returned = super().baseline(value)
                grad = returned[2]
                self.baseline_observation = dict(E0=float(returned[1]), background=float(grad[0]),
                                                trigger=float(value[2]*grad[2]), gradient=grad.copy())
                return returned

            def deficit(self, value, name, order):
                observer.order = order; observer.grid = self.plan(order)
                returned = super().deficit(value, name, order)
                self.deficit_observation = returned.copy()
                return returned

        with threadpool_limits(limits=2), legacy.OrderedChunkScheduler() as scheduler:
            result['threadpools'] = threadpool_info()
            require(all(x['num_threads'] <= 2 for x in result['threadpools']), 'Thread cap differs')
            # Exactly one training phase; original factory then observed subclass.
            base = model.phase_from_rows(rows, gm, 30, 395, modules, observer, deadline)
            phase = ObservedPhase(base.a, base.m, modules, observer, deadline, scheduler=scheduler)
            result['phase_dimensions'] = dict(events=len(phase.a['event_time']), parents=len(phase.a['parent_time']))
            require(result['phase_dimensions']['events'] == c['n_train'], 'Training denominator differs')
            result.update(status='observing', parameter_vectors_evaluated=1)
            write(out/'result.json', result)
            for order in p['orders']:
                phase.check(); (out/f'order{order}').mkdir()
                observer.chunks = []
                phase.baseline_observation = None; phase.deficit_observation = None
                entry = dict(order=order, status='running', original_evaluation=None)
                result['orders'].append(entry); write(out/'result.json', result)
                observed = observed_original(phase, theta, order, model)
                entry.update(original_evaluation=observed, baseline=phase.baseline_observation,
                             original_deficit=phase.deficit_observation)
                write(out/f'order{order}'/'observation.json', entry)
                require(phase.baseline_observation is not None and phase.deficit_observation is not None,
                        'Original evaluation did not reach full exposure')
                grid = observer.grid
                entry['grid'] = {k: array_identity(v) for k, v in grid.items() if isinstance(v, np.ndarray)}
                entry['grid_dimensions'] = {k: grid[k] for k in ('space_nodes', 'time_nodes', 'parents', 'estimate')}
                entry['totals'] = combine_chunks(observer.chunks, phase.baseline_observation, phase.deficit_observation)
                require(entry['totals']['spatial_nodes'] == grid['space_nodes']
                        and entry['totals']['native_chunk_sum_matches_original_D'], 'Incomplete native chunk custody')
                entry['chunks'] = [{'path': f'order{order}/chunk_{r["row_start"]:06d}.json',
                                    'sha256': sha(out/f'order{order}'/f'chunk_{r["row_start"]:06d}.json')}
                                   for r in sorted(observer.chunks, key=lambda r: r['row_start'])]
                entry.update(status='observed', original_evaluator_call_count=1)
                write(out/f'order{order}'/'observation.json', entry); write(out/'result.json', result)
        require(time.monotonic() < deadline and [r['status'] for r in result['orders']] == ['observed', 'observed'], 'Incomplete/expired diagnostic')
        result.update(passed=True, status='diagnostic_complete', original_evaluator_calls=phase.evaluations,
                      original_native_calls=sum(len(r['chunks']) for r in result['orders']),
                      scope='Observed original outputs/exceptions plus independent same-node diagnostic sums. No objective replacement or scientific completion.')
    except BaseException as exc:
        result.update(passed=False, status='failed', error_type=type(exc).__name__, error=str(exc))
    finally:
        result['wall_seconds'] = time.monotonic()-PROCESS_STARTED
        write(out/'result.json', result)
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wall-seconds', type=int, default=300)
    return run(parser.parse_args())


if __name__ == '__main__':
    raise SystemExit(main())
