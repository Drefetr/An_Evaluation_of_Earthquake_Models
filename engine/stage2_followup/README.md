# Stage 2 and matched-law source implementations

This directory preserves numerical implementations for S01-S06, the S04B matched-law local-inhibition study, and independent Q01 checks. It includes reusable kernels and historical campaign recipes. The aggregate evidence in the manuscript is supplied separately from the private state arrays, history banks, frozen run plans and execution records needed by those recipes.

The cleanup does not rerun research or change reported findings. Exact missing source dependencies were recovered from the local research archive: `stage2_history.py`, `fit_adapter_v2.py`, `calibration_arithmetic.py`, and `rank_envelope.py`. Recovery identities and import adaptations are recorded in the repository provenance. Historical refit process wrappers were removed from the current tree; their original bytes remain in the baseline Git history.

## Supported scope

| Study | Reusable implementation and current checks | Inputs for the historical campaign | Replay status |
|---|---|---|---|
| S01: four-cell nuisance/calibration | `s01_s02_temporal/{recursive_adapter,fit_adapter_v2,stage2_history,calibration_arithmetic}.py`; cached native likelihood; handcrafted Poisson and unknown-reference controls | `INPUT_CASES.json`, original fitted-history/reference banks, missing-cell selections, meshes and frozen generating-law settings | Numerical modules are importable; `campaign.py`, `s01_aggregate.py` and `s01_bootstrap_report.py` preserve archive-specific recipes. Complete historical replay is unavailable from this checkout alone. |
| S02: matched-productivity temporal extension | `recursive_temporal.cpp`, `contrast_v2.cpp`, `cached_stage2.cpp`, `r_matched/` and adapters; native sources compile | `S02_STAGED_RECIPE.json`, original law/authority tree and registered generation/fitting plans | `s02_campaign.py` is a preserved campaign recipe, not an advertised turnkey replay. New generation/fitting is a research workload. |
| S03: spatial decomposition | `s03_s06_spatial_benchmarks/{spatial.py,radial.cpp}`; radial source is also used by LI | Case JSON, causal training/forecast caches, frozen nuisance parameters and EP fit records referenced by that JSON | Kernel/source and explicit-input CLI supplied. Per-event caches are external and are not reconstructed by aggregate tables. |
| S04/S04B: LI and LI+ | `s04_s04b_local_inhibition/` native likelihood/integration, geometry, generator and explicit-input fitting code; handcrafted C++ boundary/gradient fixture | Observed case/caches or registered synthetic law/runtime admission; frozen backbone parameters and quadrature plans | Native build and small controls supported. Campaign reproduction requires external registered inputs; it is not part of quick checks. One-off GPU worker/controller wrappers are retired. |
| S05: conditional calibration | `ep/adapter.py`, `ep/engine.cpp`, recovered `rank_envelope.py`, `continuous_omnibus.py`; EP library builds and version-loads | Exact observed/simulation states and manifests; OC/EP scalar results for omnibus calculations | EP adapter and explicit saved-results summaries supplied. `calibration_campaign.py` retains original `research_runs/` layout and is archival orchestration. |
| S06: competitive/JMA backtests | `s06/{core.cpp,competitive.cpp,engine.py,runner.py}`; native compilation and Python/native geometry ABI control | Registered protocol and data pointer JSON, exact catalogue, frozen source/selection pins, case caches | Supported module invocation and configurable binary location; full backtests require the original protocol/data, not included per-event arrays. |
| Q01: independent verification | `q01_independent_oracles/` compiled/Python implementations | Exact saved private fitted states, replay vectors, phase captures and source-binding manifests | Independent implementation source is supplied; original comprehensive replay cannot run from public aggregate evidence alone. |

`controls_campaign.py` contains scientific synthetic/negative controls. It is retained. The two EP oracle variants are distinct implementations, not accidental duplicates. Source files named `backup`, `review` or `control` are not automatically obsolete.

## Setup and bounded checks

Install the repository CPU requirements. Run from the repository root:

```sh
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.controls_campaign --help
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.continuous_omnibus --help
```

The five portable tests check imports, direct CLI help, build source paths, conservative unknown-reference arithmetic and tied ranks. Three additional native fixture tests run only when separately built libraries are provided. These checks do not simulate histories, fit models, bootstrap results or certify theorems.

For example, the recovered arithmetic can be used without any archive paths:

```python
from engine.stage2_followup.s01_s02_temporal.calibration_arithmetic import calibrate

answer = calibrate(
    [[0, 0, 0, 0], [None, None, None, None]],
    [[1, 1, 1, 1]],
    alpha=0.5,
)
assert answer["rank_intervals"]["I00"] == [[1 / 3, 2 / 3]]
```

Unknown references widen bounds; they are not silently replaced by zero.

## Native builds

The temporal, radial, LI and S06 source set currently targets **Windows x64/MSVC C++17**. Linux/macOS portability is not claimed for those Windows export declarations. Install the Visual Studio C++ build tools and Windows SDK, then use either a developer shell, automatic `vswhere` discovery, `INHIBITORY_VCVARS`, or an explicit `--vcvars` path. No Visual Studio edition/install path is hardcoded.

Each output directory must be new and outside `engine/stage2_followup`:

```sh
python -B -m engine.stage2_followup.native_build --group temporal --output build/native/temporal
python -B -m engine.stage2_followup.native_build --group spatial --output build/native/spatial
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.build --output build/native/li
python -B -m engine.stage2_followup.native_build --group s06 --output build/native/s06
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.ep.adapter build --compiler msvc --output build/native/ep/ep.dll
```

The LI command compiles the shared radial source from the sibling spatial directory. The temporal command produces `temporal_stage2.dll` and `mdfhp_cli.exe`. Builds write logs, source/binary hashes and receipts under their output paths; the shared builder does not execute resulting binaries. The EP builder loads its library to record the engine version but does not evaluate scientific state. EP also retains its existing GNU C++ route (`--compiler g++`); the cleanup verified the MSVC route only.

To run the three small native fixtures in PowerShell after the LI, temporal and S06 builds:

```powershell
$env:INHIBITORY_TEST_NATIVE_ROOT = (Resolve-Path build/native).Path
python -B -m unittest discover -s engine/stage2_followup/tests -v
```

The tests execute the LI handcrafted boundary/gradient fixture, a S06 spatial geometry ABI call, and a two-event Poisson temporal likelihood. They do not run campaigns.

## Explicit inputs and outputs

Use module invocation from the repository root to keep sibling imports unambiguous. Direct file invocation remains supported for the LI build, controls/summary CLIs, EP adapter and continuous omnibus.

Saved S05 scalar results can be summarized with:

```sh
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.continuous_omnibus --oc-results /path/to/OC/results --ep-results /path/to/EP/results --output build/continuous_omnibus.json
```

The OC root must contain `observed_producer_cost_v1/california_fold_N/scalars.json` and `production_v1/california_fold_N/INDEX/scalars.json`. The EP root must contain `california_fold_N/observed/scalars.json` and `california_fold_N/INDEX/scalars.json`. Each model needs folds 0-2 with observed plus 999 simulated scalar records; the original 84-coordinate schema and pooled denominator checks remain enforced. No catalogue or simulation is acquired by this command.

Other explicit-input CLI signatures, for users who already have the required private inputs:

```sh
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.spatial --case CASE.json --dll build/native/spatial/radial.dll --ep-fit EP_FIT.json --output build/spatial_case
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.controls_campaign --case CASE.json --dll build/native/li/integrated.dll --radial build/native/li/radial.dll --output build/li_case
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.summarize --root /path/to/completed/study --output build/study_summary.json
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.ep.adapter job --job JOB.json
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.s06.runner run --pointer POINTER.json --protocol PROTOCOL.json --output build/s06_run
```

These are research/state-consuming commands, not quick checks. Read their admission, source-hash, schema and failure rules before execution. Private case/cache files and manifests must agree exactly; do not replace missing historical inputs with newly selected data and call that exact reproduction. The S06 runner retains its registered JMA schema and should not be treated as a generic California runner.

Set `INHIBITORY_S06_NATIVE_DIR` to the S06 build directory. Historical temporal recipes can use `INHIBITORY_TEMPORAL_LIBRARY` and `INHIBITORY_MATCHED_CLI` for separately built binaries; setting those paths does not supply their missing run plans or authorize a changed source identity. Explicit new runs must record public source variants and retain historical pins separately.

See [historical source status](../HISTORICAL_SOURCES.md) for the older iteration launchers and optional missing backends.
