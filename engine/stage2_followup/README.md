# Stage 2 (`S01`–`S06`) and `S04B` Follow-Up Source Implementations

This directory contains the C++ and Python implementations used in the completed bounded Stage 2 follow-up programme (`S01`–`S06`) and the matched-law `LI+` synthetic control extension (`S04B`), alongside the independent `Q01` verification oracles.

The historical `engine/iteration_*` tree and `engine/api.py` facade remain byte-pinned to `provenance/extraction_manifest.json`.

## Directory Layout

- **`s01_s02_temporal/`**:
  - `campaign.py`, `s01_aggregate.py`, `s01_bootstrap_report.py`: `S01` missing-only recovery and oracle-calibrated test summaries (Chapter 7, Section 7.12).
  - `s02_campaign.py`, `recursive_temporal.cpp`, `recursive_adapter.py`, `cached_stage2.cpp`, `contrast_v2.cpp`, `r_matched/`: `S02` matched-productivity ($r$-matched) MDFHP simulation, recursive temporal likelihood evaluation, and paired calibration contrasts (Chapter 9, Section 9.5).
- **`s03_s06_spatial_benchmarks/`**:
  - `spatial.py`, `radial.cpp`: `S03` four-arm spatial decomposition (`OC`, unweighted, `LOO` declustered background, and `EP`) across New Zealand and California (Chapter 11, Section 11.4).
  - `ep/adapter.py`, `ep/engine.cpp`, `calibration_campaign.py`, `continuous_omnibus.py`: `S05` all-path point-process conditional calibration for the `EP` benchmark and continuous omnibus diagnostics (Chapter 12, Section 12.15).
  - `s06/competitive.cpp`, `s06/core.cpp`, `s06/engine.py`, `s06/runner.py`: `S06` California five-episode causal-prefix backtest and JMA stationary-vs-trend background ablation (Chapter 11, Section 11.5).
- **`s04_s04b_local_inhibition/`**:
  - `architecture.hpp`, `engine.cpp`, `fixture.cpp`, `integrated.cpp`: Compiled continuous local-inhibition (`LI`, `LI+ immigrant`, and `LI+ total`) spatial-temporal likelihood and analytic gradient kernels.
  - `generator.py`, `controls_campaign.py`, `simulation.py`, `adapter.py`, `background.py`, `geometry_plan.py`, `build.py`, `summarize.py`: Exact Ogata thinning simulator (supporting unit-mark `LI`, magnitude-scaled `LI+ immigrant`, and total-intensity `LI+ total` generation via `strict_stress_plus`) and fixed-backbone fitting campaign (`Chapter 13`, Sections 13.11–13.12).
  - `refine_worker.py`, `refit_pipeline.py`, `refit_worker.py`: Persistent order-16 GPU training, order-32 quadrature verification, and concurrent 3-thread CPU anchor replay pipeline.
- **`q01_independent_oracles/`**:
  - `independent_f_oracle.cpp`, `independent_point_oracle_v4.cpp`, `tier2_ep_oracle.py`, `tier2_ep_pure_python.py`, `independent_li_oracle.py`, `q01_verify.py`: Independent `Q01` scientific and numerical replay oracles for `S01`–`S06` and `S04B`.
