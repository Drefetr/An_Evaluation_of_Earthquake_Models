"""Candidate scheduling-only acceleration; never activated by the frozen runner.

The native ABI, 256-row chunks, per-chunk BLAS inputs and ordered reduction
are unchanged. Two BLAS preparations finish before either native call starts.
Only one phase/evaluation may own a scheduler at a time.
"""
from concurrent.futures import ThreadPoolExecutor, wait
import math
import threading
import numpy as np
from threadpoolctl import threadpool_limits
from experiments.s04b_joint_nuisance import model as frozen

_PROCESS_EVALUATION_LOCK = threading.Lock()


class OrderedChunkScheduler:
    chunk_rows = 256
    native_workers = 2

    def __init__(self):
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='joint-native')
        self._lock = _PROCESS_EVALUATION_LOCK
        self._closed = False

    def __enter__(self):
        if self._closed:
            raise RuntimeError('Scheduler is closed')
        return self

    def __exit__(self, *exception):
        self.close()

    def close(self):
        # Block until the current native batch has quiesced, even on failure.
        with self._lock:
            if not self._closed:
                self._closed = True
                self._pool.shutdown(wait=True, cancel_futures=False)

    def deficit(self, phase, theta, name, order):
        if not self._lock.acquire(blocking=False):
            raise RuntimeError('Scheduler already belongs to an evaluation')
        try:
            if self._closed:
                raise RuntimeError('Scheduler is closed')
            with threadpool_limits(limits=2):
                return self._deficit(phase, theta, name, order)
        finally:
            self._lock.release()

    @staticmethod
    def _invoke(native, prepared, index):
        return native.integrate(*prepared[index])

    def _deficit(self, phase, theta, name, order):
        if phase.native is None:
            raise ValueError('Native integral required for inhibited law')
        grid = phase.plan(order)
        t = grid['t']
        inclusive = name == 'LIplus_inclusive'
        plus = name != 'LI'
        marks = np.exp((.75 * math.log(10) if plus else 0) * phase.a['parent_excess'])
        key = (order, float(theta[3]), float(theta[4]))
        if inclusive:
            if phase._temporal.get('key') != key:
                lag = t[:, None] - phase.a['parent_time'][None, :]
                phase._temporal = dict(key=key, value=np.concatenate(
                    [v.T for v in frozen.temporal(lag, theta[3], theta[4])], axis=1))
            temporal_fields = phase._temporal['value']
        total = np.zeros(9)
        for batch_start in range(0, len(grid['b']), 512):
            # These products are exactly the original separate 256-row BLAS calls.
            # No native work is submitted until both preparations have finished.
            prepared = []
            for start in range(batch_start, min(batch_start + 512, len(grid['b'])), 256):
                phase.check()
                sl = slice(start, start + 256)
                h = np.ascontiguousarray(grid['coeff'][sl] @ temporal_fields) if inclusive else None
                prepared.append((phase.a['parent_time'], marks, grid['r2'][sl],
                    grid['area'][sl], grid['b'][sl], t, grid['w'], h, theta, phase.m['T0']))
            futures = []
            try:
                for index in range(len(prepared)):
                    # Native.integrate invokes the C function and reads its
                    # thread-local error text within this same worker thread.
                    futures.append(self._pool.submit(self._invoke, phase.native, prepared, index))
                # Finish the entire batch before summation or new BLAS work.
                wait(futures)
                for future in futures:
                    total += future.result()
            finally:
                # Submission/worker failures never leave background native work
                # active when returning to the caller or starting another batch.
                wait(futures)
                # Worker items reference the shared list, not individual h
                # buffers. Clearing it releases both buffers before preparation
                # of the next pair, even if an idle worker retains its item.
                prepared.clear()
                h = None
        return total


class ParallelPhase(frozen.Phase):
    """Opt-in candidate Phase; all other likelihood code is inherited unchanged."""
    def __init__(self, *args, scheduler, **kwargs):
        super().__init__(*args, **kwargs)
        self.scheduler = scheduler

    def deficit(self, theta, model, order):
        return self.scheduler.deficit(self, theta, model, order)
