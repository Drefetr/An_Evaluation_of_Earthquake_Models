# Stage 2 and matched-law source implementations

This directory preserves numerical implementations for S01-S06, the S04B matched-law local-inhibition study, and independent Q01 checks. It includes reusable kernels and historical campaign recipes. Recovered inputs and explicit replay routes now live under [`reproduction/`](../../reproduction/README.md); the old campaign entry points do not automatically discover those packages.

The cleanup does not rerun research or change reported findings. Exact missing source dependencies were recovered from the local research archive: `stage2_history.py`, `fit_adapter_v2.py`, `calibration_arithmetic.py`, and `rank_envelope.py`. Recovery identities and import adaptations are recorded in the repository provenance. Historical refit process wrappers were removed from the current tree; their original bytes remain in the baseline Git history.

## Supported scope

| Study | Reusable implementation and current checks | Inputs for the historical campaign | Replay status |
|---|---|---|---|
| S01: four-cell nuisance/calibration | `s01_s02_temporal/{recursive_adapter,fit_adapter_v2,stage2_history,calibration_arithmetic}.py`; cached native likelihood; handcrafted Poisson and unknown-reference controls | Recovered histories in `reproduction/synthetic/`; F restricted fitted states remain unrecoverable | The F/S01 continuation was withdrawn. Source preservation does not reinstate those results. See `docs/F_followup.md`. |
| S02: matched-productivity temporal extension | `recursive_temporal.cpp`, `contrast_v2.cpp`, `cached_stage2.cpp`, `r_matched/` and adapters | Original histories, fitted states and traces in `reproduction/s02/` | The input verifier checks custody. `s02_campaign.py` remains an archive-specific campaign recipe; new fitting is a separate workload. |
| S03: spatial decomposition | `s03_s06_spatial_benchmarks/{spatial.py,radial.cpp}`; radial source is also used by LI | Recovered original fits/scores and scoring inputs in `reproduction/regional/` | Follow that package's explicit saved-state route and per-table execution status, not the old private-path campaign. |
| S04/S04B: LI and LI+ | `s04_s04b_local_inhibition/` likelihood/integration, geometry, generator and explicit-input fitting code; handcrafted C++ boundary/gradient fixture | S04B raw histories, generating settings, selected fits/gates in `reproduction/synthetic/`; recovered observed evidence in regional packages | S04B has an executed saved-state replay. Original S04 and observed runs have separately documented provenance; source availability does not assert fresh replay. |
| S05: conditional calibration | `ep/adapter.py`, `ep/engine.cpp`, recovered `rank_envelope.py`, `continuous_omnibus.py` | Recovered original records under `reproduction/regional/` | The original reconstruction covers all 5,994 point-score paths and fifteen full-vector EP paths. These are distinct audit layers, not 5,994 full-vector reruns. |
| S06: competitive/JMA backtests | `s06/{core.cpp,competitive.cpp,engine.py,runner.py}`; geometry ABI control | Provider bytes, projected arrays, original fitted-state/score records in `reproduction/jma/` and `reproduction/regional/` | Follow the current packages' explicit scoring routes. The old `runner.py` still expects its registered protocol/pointer schema. |
| Q01: independent verification | `q01_independent_oracles/` compiled/Python implementations | Exact saved private fitted states, replay vectors, phase captures and source-binding manifests | Independent implementation source is supplied; original comprehensive replay cannot run from public aggregate evidence alone. |

`controls_campaign.py` contains scientific synthetic/negative controls. It is retained. The two EP oracle variants are distinct implementations, not accidental duplicates. Source files named `backup`, `review` or `control` are not automatically obsolete.

## Setup and bounded checks

Install the repository CPU requirements. Run from the repository root:

```sh
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.controls_campaign --help
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.continuous_omnibus --help
```

The five Python tests check imports, direct CLI help, build source paths, conservative unknown-reference arithmetic and tied ranks. Three native fixture tests build actual libraries automatically into a fresh temporary directory when no explicit native root is supplied. A missing compiler fails the tests; it does not skip them. Compiler logs and source/binary receipts are retained at the printed path. These eight checks do not simulate histories, fit study models, bootstrap results or certify theorems.

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

The temporal, radial, LI and S06 build selects MSVC on Windows and a C++17 `CXX`, `g++` or `clang++` compiler on Linux/macOS. Export decoration and library suffixes are platform-aware; numerical formulas are unchanged. Windows can use a developer shell, automatic `vswhere` discovery, or an explicit `--vcvars` path. No Visual Studio edition/install path is hardcoded. Build support is distinct from an executed platform acceptance record: the [CPU guide](../../docs/cpu_reproduction.md) describes the fresh Linux CI and its retained results.

Each output directory must be new and outside `engine/stage2_followup`:

```sh
python -B -m engine.stage2_followup.native_build --group temporal --output build/native/temporal
python -B -m engine.stage2_followup.native_build --group spatial --output build/native/spatial
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.build --output build/native/li
python -B -m engine.stage2_followup.native_build --group s06 --output build/native/s06
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.ep.adapter build --compiler msvc --output build/native/ep/ep.dll
```

The LI command compiles the shared radial source from the sibling spatial directory. The temporal command produces `temporal_stage2` with `.dll`/`.so`/`.dylib` and `mdfhp_cli` with `.exe` on Windows. Builds write logs, source/binary hashes and receipts under their output paths; the shared builder does not execute resulting binaries. The EP builder loads its library to record the engine version but does not evaluate scientific state; its GNU C++ route uses `--compiler g++` and an explicit output path.

An optional locator reuses separately built libraries. It is no longer a prerequisite:

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

Other explicit-input CLI signatures, for users following the matching package's input contract (the example library suffixes below are Windows suffixes):

```sh
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.spatial --case CASE.json --dll build/native/spatial/radial.dll --ep-fit EP_FIT.json --output build/spatial_case
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.controls_campaign --case CASE.json --dll build/native/li/integrated.dll --radial build/native/li/radial.dll --output build/li_case
python -B -m engine.stage2_followup.s04_s04b_local_inhibition.summarize --root /path/to/completed/study --output build/study_summary.json
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.ep.adapter job --job JOB.json
python -B -m engine.stage2_followup.s03_s06_spatial_benchmarks.s06.runner run --pointer POINTER.json --protocol PROTOCOL.json --output build/s06_run
```

These are research/state-consuming commands, not quick checks. Read their admission, source-hash, schema and failure rules before execution. Case/cache files and manifests must agree exactly; do not replace missing historical inputs with newly selected data and call that exact reproduction. The S06 runner retains its registered JMA schema and should not be treated as a generic California runner.

S06 defaults to `build/native/s06`; `INHIBITORY_S06_NATIVE_DIR` optionally selects another build directory. Historical temporal recipes can use `INHIBITORY_TEMPORAL_LIBRARY` and `INHIBITORY_MATCHED_CLI` for separately built binaries; setting paths does not supply missing run plans or authorize a changed source identity. Explicit new runs record public source variants and retain historical pins separately.

See [historical source status](../HISTORICAL_SOURCES.md) for the older iteration launchers and optional missing backends.
