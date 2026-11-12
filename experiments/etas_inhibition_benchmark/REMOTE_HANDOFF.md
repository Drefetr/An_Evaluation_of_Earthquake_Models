# Remote execution handoff

Intensive local work stopped on user instruction on 12 November 2026. The final
remote paired uncertainty computation and three-fold benchmark acceptance are
complete. All numerical and source-identity gates passed.

## Preserved evidence

* `validation/live_results/score_uncertainty_remote_v2_20261111/summary.json`
  is the completed nine-fold-row authority, including pooled contrasts,
  90/180/365-day sensitivity and all numerical/source guards. The validated
  typed manuscript values and chapter fragments are in its `manuscript/`
  subdirectory; `custody_download.json` binds the downloaded remote bytes.
* `validation/live_results/etas_inhibition_benchmark_accepted_20261111/summary.json`
  is the accepted three-fold magnitude-scaled benchmark authority. All three
  attenuation fits select the common zero-amplitude state, so their matched
  contrasts are exactly zero. `baseline_comparison.json` verifies identical
  forecast windows, rectangles, parent/event histories, fertility and mark
  measure before comparing the new excitation fit with the archived EP scores.

* `validation/live_results/score_uncertainty_final_20261111/nz.json` and
  `ca.json` contain completed exact 90-day block allocations. NZ inhibited
  background panels were split at calendar boundaries; CA analytic exposure
  was evaluated at the same boundaries. Their total contrasts reproduce saved
  scores to `1e-6` nats. The interrupted job had not completed the local
  inhibition contractions or published its final summary and sensitivities.
* `validation/live_results/etas_inhibition_benchmark_20261111/california_fold_0/result.json`
  is an initial pilot only. All four null and inhibited starts returned success.
  The selected inhibition amplitude is zero. A `3.2e-6` nat difference arises
  from separate numerical nuisance polishing and is a floor return. This
  pilot is an initializer, not an accepted result, and its launcher source was
  edited while it ran. The acceptance runner recomputes all final likelihoods,
  optimizer returns and scores from its explicitly saved parameter values.
* `controls.json` in that pilot root passed the 12-parameter finite-difference
  gradient control (maximum error `6.0e-10`), independent Cartesian regional
  mass controls (maximum discrepancy `4.8e-14`) and exact nested-floor controls.
  The new native chronological row contractions matched the NumPy objective
  exactly and its gradient to `1.2e-13` on the actual first training fold.
  These controls do not certify an unfinished fit.

## Dependencies

Use Python 3.11--3.13 with the pinned packages in `requirements-remote.txt` and a
C++17 compiler. Linux native compilation uses `g++`, OpenMP, `-O2`,
`-fno-fast-math` and `-ffp-contract=off`. The Windows builder discovers MSVC and
uses `/fp:strict /openmp`. Native compilation is automatic and emits a source,
command and binary-hash receipt under `build/etas_benchmark_native_20261111/`.
No historical Windows DLL is required on Linux.

Run from the bundle/repository root. Install into the remote execution
environment; these commands are not authorizations to resume intensive work
on the local workstation. Use fresh output directory names for a new execution;
the example paths below identify the retained historical runs.

```sh
python -m pip install -r experiments/etas_inhibition_benchmark/requirements-remote.txt
python -B experiments/etas_inhibition_benchmark/verify.py --output validation/remote_controls.json
```

## Complete the benchmark

The completed first-fold pilot can seed the final acceptance runner. Folds 1
and 2 need initial fits. These independent commands can run in parallel if
remote CPU and memory permit. Set native thread counts to the remote job
allocation, preserving one BLAS thread.

```sh
python -B experiments/etas_inhibition_benchmark/run_frozen_gpu_20261111.py --backend cuda --case california_fold_1 --power 13 --check-power 16 --output validation/live_results/etas_inhibition_benchmark_20261111
python -B experiments/etas_inhibition_benchmark/run_frozen_gpu_20261111.py --backend cuda --case california_fold_2 --power 13 --check-power 16 --output validation/live_results/etas_inhibition_benchmark_20261111
```

The case outputs occupy separate subdirectories; if running them concurrently,
give each command a separate parent output and collect its case subdirectory
under the common pilot parent before acceptance, so launcher summaries do not
compete. The acceptance command below expects all three case subdirectories.

```sh
python -B experiments/etas_inhibition_benchmark/accept.py --backend cuda --model-source run_frozen_gpu_20261111.py --pilot validation/live_results/etas_inhibition_benchmark_20261111 --output validation/live_results/etas_inhibition_benchmark_accepted_20261111
```

Acceptance reoptimizes the matched null and inhibited arms from the saved
training states, with the common training-only weighted background. Failed
starts are retried. Required starts must all succeed. The integration proposal
is frozen during each training optimization. Independent scrambled-Sobol
training checks use eight times as many draws; integration power rises and the
fit repeats until training ordering and numerical precision gates pass.
Independent held-out integration repeats until its standard error is at most
`min(0.02, 0.01 max(1, |gain|))` nats. Zero-amplitude returns receive a common
polished null parameter vector, so the score contrast is exactly zero.
Source hashes are recorded before execution and checked again afterwards.

## Complete uncertainty

```sh
python -B experiments/methodological_audit/score_uncertainty_cuda_frozen_v2_20261111.py --device cuda --output validation/live_results/score_uncertainty_remote_v2_20261111
```

This recomputes the three exact original inhibition spatial quadratures, saving
their time marginals so 90-, 180- and 365-day paired resampling reuse the same
completed contractions. It retains empty blocks and the final no-event
exposure. Event terms and integrated-rate terms are paired before resampling.
The pooled contrasts resample within disjoint folds. Each interval and
permutation/sign test uses 49,999 replicates with saved seeds; these are
conditional score comparisons for fitted procedures, not physical mechanism
tests or refitting uncertainty. `summary.json` is written only after every
requested contrast and sensitivity has completed and source identity passes.

The CUDA path uses native binary64 CUDA kernels and cuBLAS `Dgemm`, with the
original complete spatial and temporal grids, exponential attenuation and
score-sum comparison retained. It requires no PyTorch or CuPy. It compiles for
the RTX 2080 (`sm_75`) and selects `g++-11` when available for CUDA 11.8
compatibility; `CUDA_HOST_CXX` can name another supported compiler. Scalar
fast-math/FMA contraction is disabled. A tiny strict-past fixture and split/full
tile comparison must pass to `1e-12` before any historical grid is evaluated.
The final original-score sum check remains `1e-5` nats. Set `--device cpu` for
the NumPy reference contractions when explicitly authorized on a suitable host.

The completed v2 uncertainty run preserves the original logarithmic event-gap
temporal map. It reconstructs the original unsplit nodes/weights, verifies
original-grid score custody, and then compares calendar-split temporal orders
32 and 64. All original-grid comparisons passed `1e-5` nats; all refined block
changes were below `6e-12` nats. The earlier v1 CUDA launcher incorrectly
interpreted the log-Gauss nodes as linear Gauss nodes and was rejected by its
score-custody guard. Its partial output is not accepted evidence.

The GPU benchmark row adapter separately passed null and active full-objective
and all twelve gradient comparisons against the NumPy reference. Its largest
representative-fixture gradient discrepancy was `1.1e-11`; the centered
finite-difference discrepancy was below `7.5e-10`. The measured end-to-end
objective speedup over the compiled two-thread CPU adapter on the occupied VM
was 1.87. `gpu_controls.py` records those controls, timings and source/binary
hashes. `remote_campaign.py` runs the two missing pilots and final acceptance
sequentially in one exclusive GPU lane, with stage PIDs and exit receipts.

Only completed, accepted final artifacts should populate manuscript tables.
