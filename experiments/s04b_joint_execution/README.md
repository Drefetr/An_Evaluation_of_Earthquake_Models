# Candidate ordered parallel chunk scheduler

This is an inactive implementation candidate. The frozen joint-fit runner
does not import it. It creates no histories, runs no fitting campaign and
does not change the original numerical or resource protocol.

`parallel_chunks.OrderedChunkScheduler` preserves the existing 256-row
spatial chunks. For total-intensity attenuation, it prepares two consecutive
H/Hc/Hp chunks using the same separate NumPy matrix products with two BLAS
threads. Preparation is sequential and finishes before either native call
starts. It then calls the unchanged `Native.integrate` on the pair through
two worker threads. All calls finish before their nine-vectors are added in
the original spatial order and before the next BLAS preparation. A final
odd/partial chunk follows the same rule. Immigrant-only arms use the same
scheduling with no triggering-matrix product.

The C++ evaluator and its ABI are unchanged. Its work vectors are local and
its error string is thread-local; the existing Python native wrapper calls
the evaluator and reads that error in the same worker. A process-wide lock
rejects concurrent evaluations through multiple scheduler instances. At most
two native calls run, and neither overlaps BLAS preparation. Every failure
waits for submitted work to finish before returning. A second chunk can have
started when the first fails; the whole objective still fails, with the first
error in original chunk order. No failure becomes a score or optimizer retry.

At most two H/Hc/Hp chunk buffers are retained for a pair, adding one buffer
relative to the serial implementation: at most `256 * n_time * 3 * 8` bytes.
The shared job list is cleared before the next pair, including after errors.
This is an additional-array bound, not a hard operating-system memory limit;
the conductor's process-tree memory and wall supervision remain necessary.

`ParallelPhase` overrides only `deficit`; the point likelihood, gradients,
unattenuated exposure, grids, temporal field calculation, native evaluator,
fitting recipe and gates are inherited or called unchanged. The scheduler
must be closed (prefer its context manager). For constructed use:

```python
with OrderedChunkScheduler() as scheduler:
    phase = ParallelPhase(arrays, metadata, modules, native,
                          scheduler=scheduler, deadline=deadline)
    score, gradient = phase.evaluate(theta, model_name, order)
```

Run the constructed controls from the repository root:

```text
python -B -m unittest discover -s tests -p test_joint_parallel_chunks.py -v
```

They compile the unchanged native source and compare serial/candidate
objective components, eight-coordinate gradients and native deficit vectors
byte for byte in the same runtime. Coverage includes zero and positive eta,
all three inhibited models, both quadrature orders, even/odd/partial chunks,
changing temporal coordinates, exact original reduction order, concurrency,
native error propagation and failure during the second job submission.
These are small invented inputs, not timing benchmarks or scientific runs.

Expected benefit is at most approximately twofold for parallelizable native
recurrence time. The sequential matrix products, preparation, fitting and
other work receive no such benefit; total acceleration has not been measured.
The original pilot's measured elapsed time and resource failure history must
remain in any continuation. Before activation, independently review this
source and its exact-byte controls on the intended runtime, then freeze a
separately labelled execution/resource amendment with the unchanged fixed
roster, fit budgets, tolerances and outcomes. Do not reset the old pilot cap
or claim full-campaign feasibility from these fixtures.
