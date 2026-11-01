# Historical numerical sources and entry points

`api.py` exposes fourteen preserved modules for kernels, simulation clocks, likelihood, restricted fitting, profiling, observed scoring and heterogeneity. Their numerical dependencies include `iteration_9/code/numerical_fit.py` and `iteration_6/code/checkpoint_io.py`. These source bytes remain bound by `provenance/extraction_manifest.json`; cleanup leaves the iteration sources in their existing paths.

The presence of a CLI file does not promise complete historical execution. `iteration_27/configs/observed_frozen.json` also binds many old launchers as source authorities. `scripts/run_observed.py` verifies those pins before running the separately documented observed workload. Removing or relocating apparently unused launchers would break that route's input validation.

| Entry points retained for source identity | Status |
|---|---|
| `iteration_19/code/run_full_cuda.py` | Original CUDA campaign orchestration; analysis/benchmark dependencies are absent. Not a supported public campaign. |
| `iteration_21/code/analyse_staged.py`, `analyse_full_staged.py`, `benchmark_staged.py`, `run_staged_full.py`, `iteration_21/run_full_staged.ps1` | Historical staged campaign and postprocessing. `analyse_staged.py` requires unshipped `iteration_17/code/analyse_oracle_v1_1.py`. Source preservation does not imply CLI replay works. |
| `iteration_26/code/calibrate_level_only.py`, `review_benchmark.py`, `run_level_calibration.py`, `iteration_26/run_level_calibration.ps1` | Historical calibration/review launchers; retain original frozen experiment inputs and execution rules. `level_only_fit.py` remains an API dependency. |
| `iteration_27/code/bounded_run.py`, `freeze_protocols.py`, `horizon_pilot.py` | Historical orchestration/protocol utilities retained in the frozen source inventory. These are not additional quickstart commands. |
| Optional `paired_history.py` GPU mode | References the unshipped `iteration_5_performance/gpu/cuda_history.py`. CPU/API import checks do not establish this optional backend is available. |

The acquisition scripts are also historical source authorities. Their embedded examples predate the `engine/` prefix; current root-relative invocation is:

```sh
python -B engine/iteration_5/code/fetch_catalogue.py --help
python -B engine/iteration_5/code/prepare_catalogue.py --help
```

Fetching is an explicit external-data operation. The fixed October 2026 cutoff documents the historical selection; a fresh provider response is a new snapshot and will not necessarily match the historical observed catalogue hash. Preparing verifies response hashes and records exclusions. See [data scope](../docs/data.md).

The Stage 2 one-off `refit_pipeline.py`, `refit_worker.py` and `refine_worker.py` were removed from the public working tree because they coupled original Linux worker paths, controller lease files and process scheduling to a particular run. They are recoverable at baseline commit `5fdd135d788c2350bf27fda7b817d2b7c324d7c6`; their historical identities are indexed in provenance. Reusable LI kernels, generation laws, gradients, fitting logic and scientific negative controls remain under [Stage 2](stage2_followup/README.md).
