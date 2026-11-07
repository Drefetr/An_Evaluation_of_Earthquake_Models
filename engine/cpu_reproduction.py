"""Bounded CPU kernel acceptance; never launches a scientific campaign.

The 20 iteration-27 CPU tests consist of 19 unchanged historical assertions and
one explicitly named CPU16/CPU32 fit control. CUDA parity remains separate.
"""
from pathlib import Path
import argparse
import contextlib
import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import subprocess
import sys
import threading
import time
import traceback
import unittest

ROOT = Path(__file__).resolve().parents[1]
GPU_TEST = 'test_horizon_pilot.ActualSmallFitFixture.test_complete_small_cuda_CPU32_pair'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def iteration_suite():
    historical = list(flatten(unittest.TestLoader().discover(
        str(ROOT / 'engine/iteration_27/tests'))))
    excluded = [test.id() for test in historical if test.id() == GPU_TEST]
    if len(historical) != 20 or excluded != [GPU_TEST]:
        raise RuntimeError('Historical test roster changed; CPU equivalence mapping must be reviewed')
    retained = [test for test in historical if test.id() != GPU_TEST]
    counterpart = unittest.TestLoader().loadTestsFromName('engine.cpu_tests.test_iteration27_cpu')
    return unittest.TestSuite(retained + list(flatten(counterpart)))


def execute_suite(name, suite, expected, output):
    ids = [test.id() for test in flatten(suite)]
    if len(ids) != expected:
        raise RuntimeError(name + ' test count differs from the declared roster')
    started = time.perf_counter()
    with (output / (name + '.log')).open('w', encoding='utf-8') as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                skipped=len(result.skipped), unexpected_successes=len(result.unexpectedSuccesses),
                expected_failures=len(result.expectedFailures), test_ids=ids,
                passed=result.wasSuccessful() and result.testsRun == expected and not result.skipped,
                elapsed_seconds=time.perf_counter() - started,
                log_sha256=sha(output / (name + '.log')))


def run(output, stage='all', compiler=None, max_rss_gib=6., min_available_gib=2.):
    import psutil
    from engine.stage2_followup import native_build
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    stop = threading.Event()
    resources = dict(peak_process_tree_rss_bytes=0, minimum_available_bytes=None,
                     sample_seconds=.2, max_rss_bytes=int(max_rss_gib * 2**30),
                     minimum_required_available_bytes=int(min_available_gib * 2**30),
                     sampling_errors=[])
    def sample():
        process = psutil.Process()
        while not stop.is_set():
            try:
                rss = 0
                for child in [process] + process.children(recursive=True):
                    try:
                        rss += child.memory_info().rss
                    except psutil.NoSuchProcess:
                        # A compiler child can exit between enumeration/read.
                        continue
                resources['peak_process_tree_rss_bytes'] = max(resources['peak_process_tree_rss_bytes'], rss)
                available = psutil.virtual_memory().available
                resources['minimum_available_bytes'] = min(available, resources['minimum_available_bytes'] or available)
            except Exception as exc:
                resources['sampling_errors'].append(type(exc).__name__ + ': ' + str(exc))
                break
            stop.wait(resources['sample_seconds'])
    watcher = threading.Thread(target=sample, daemon=True)
    watcher.start()
    receipt = dict(schema='bounded_cpu_acceptance_v1', stage=stage, passed=False,
                   started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   platform=platform.platform(), machine=platform.machine(), python=sys.version,
                   logical_cpus=os.cpu_count(), physical_cpus=psutil.cpu_count(logical=False),
                   thread_environment={key: os.environ.get(key) for key in
                       ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')},
                   packages={name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'psutil')},
                   builds={}, suites={}, resources=resources,
                   cuda_parity=dict(status='not_run', historical_test_id=GPU_TEST,
                                    reason='Separate GPU requirement; no CPU result establishes CUDA equivalence'),
                   scientific_campaigns_executed=False)
    for label, command in [('commit', ['git', 'rev-parse', 'HEAD']),
                           ('working_tree', ['git', 'status', '--porcelain'])]:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        receipt[label] = result.stdout.strip() if result.returncode == 0 else None
    sources = sorted(p for p in (ROOT / 'engine').rglob('*') if p.is_file()
                     and p.suffix in ('.py', '.cpp', '.hpp', '.h'))
    receipt['source_sha256'] = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources}
    try:
        if stage in ('all', 'build', 'stage2'):
            for group in ('li', 'temporal', 's06'):
                receipt['builds'][group] = native_build.build(group, output / 'native' / group, compiler=compiler)
        if stage in ('all', 'stage2'):
            path = ROOT / 'engine/stage2_followup/tests/test_public_workflows.py'
            spec = importlib.util.spec_from_file_location('_cpu_stage2_tests', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.NativeFixtures.native_root = output / 'native'
            receipt['suites']['stage2'] = execute_suite('stage2', unittest.TestLoader().loadTestsFromModule(module), 8, output)
        if stage in ('all', 'iteration27'):
            receipt['suites']['iteration27_cpu'] = execute_suite('iteration27_cpu', iteration_suite(), 20, output)
        receipt['passed'] = all(item['passed'] for item in receipt['suites'].values())
    except Exception:
        receipt['error'] = traceback.format_exc()
    finally:
        stop.set()
        watcher.join()
        resources['within_limits'] = (resources['peak_process_tree_rss_bytes'] <= resources['max_rss_bytes']
                                     and not resources['sampling_errors']
                                     and resources['minimum_available_bytes'] is not None
                                     and resources['minimum_available_bytes'] >= resources['minimum_required_available_bytes'])
        receipt['passed'] = receipt['passed'] and resources['within_limits']
        receipt['elapsed_seconds'] = time.perf_counter() - started
        receipt['total_cpu_tests'] = sum(item['tests'] for item in receipt['suites'].values())
        (output / 'checks_cpu.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: receipt[key] for key in ('passed', 'stage', 'total_cpu_tests', 'elapsed_seconds')}))
    return 0 if receipt['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stage', choices=('all', 'build', 'stage2', 'iteration27'), default='all')
    parser.add_argument('--compiler')
    parser.add_argument('--max-rss-gib', type=float, default=6.)
    parser.add_argument('--min-available-gib', type=float, default=2.)
    args = parser.parse_args()
    return run(args.output, args.stage, args.compiler, args.max_rss_gib, args.min_available_gib)


if __name__ == '__main__':
    raise SystemExit(main())
