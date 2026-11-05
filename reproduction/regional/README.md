# Recovered California inputs for S03, S05 and S06

This package supplies exact saved California scientific inputs, executable verification/materialization, and a guarded S05 point-score replay route. All 5,994 simulated paths are supplied. The dated current execution passed the native controls, the original six-case pilot and two predetermined largest-input probes. The full 5,994-row replay was not launched: its frozen runtime projection exceeded the full-run cap and remaining execution window. These are eight executed saved-path comparisons, not a completed full S05 replay or a new model fit.

NumPy is needed for input verification; scoring also requires SciPy and a C++17 compiler.

From the repository root:

```powershell
python -B reproduction/regional/inputs.py verify
python -B reproduction/regional/inputs.py extract --output C:/new/regional_inputs
python -B -m unittest discover -s reproduction/regional/tests -v
```

The output directory must be new. Extraction checks the entire payload before
writing. The verifier checks member hashes, the exact S05 identity roster,
NPZ shapes and finite values, prehistory separation, forecast bounds, raw event
counts, all four seed streams, 84-coordinate expected vectors, numerical-leaf
transformation fingerprints, S03 selected-arm coverage and S06 completed fits.
These are input checks, not an independent proof of scientific claims.

## Included inputs

- **S05:** all 5,994 simulated futures (OC and EP Ã— three origins Ã— 999), six
  observed futures and six frozen simulation states, byte-exact as NPZ files.
  `S05/records.jsonl` retains every seed receipt and expected scalar vector,
  plus the 2,997 OC job records explicitly pinned by the terminal manifest.
  Index -1 identifies the observed rows; their original receipts correctly
  retain `mode=observed,index=0` and their distinct observed-state identity.
  The supplied simulation states contain no observed future.
- **S03:** all 12 selected four-arm vectors and full returned fit records,
  fixed temporal and EP spatial coordinates, inherited EP fit, frozen
  nuisance/selection/case metadata, inherited Omori selected state, and source
  field pointers. The large earlier-model forecast arrays are omitted.
- **S06:** all 55 California fit records across five episodes, including
  supporting FC scale selectors and N0 floors; the exact case/nuisance/sigma
  contracts, episode roster and relevant constructor sources. The already
  recovered CA cohort is supplied separately by `reproduction/nzca`.

`source_crosswalk.jsonl` maps each output member or record fragment to its
original project-relative source path, SHA-256 and JSON pointer. Absolute
account paths become `archive:/...` provenance identifiers. Those identifiers
are not paths into the extracted tree. Original numerical values are preserved;
raw NPZ bytes are unchanged. The manifest pins all payload members and the
included scoring source. Original `private_` filenames describe historical
storage, not a personal-data category: the arrays are seismic or simulated
events and numerical model state.

## Current guarded replay and actual execution

Use [the guarded runner](REPLAY_GUARD.md) with [the public protocol](replay_protocol.json) and the byte-exact [workload record](workload.json). The runner requires current build/source/input bindings, an explicit numerical lease/admission, passing actual controls, the original pilot and both fixed probes. Full-run admission uses their measured resources. The full command is supported, but the dated execution below did not pass its runtime admission gate.

[The actual execution summary](../../validation/reproductions/s05_execution_20261105.json), [compact execution archive](s05_execution_20261105.zip) and [source/public hash manifest](s05_execution_20261105.manifest.json) retain the native point and geometry controls, all eight executed rows, source/compiler/DLL bindings, both failed builds and the failed full-run resource gate. Maximum declared score-field discrepancies passed the unchanged numerical tolerance. This scope covers the declared point/joint and temporal fields; it does not cover full84, generator reproduction, fitted-null calibration or fresh fitting.

The two earlier build attempts remain failed records. The first stopped for a lingering owned descendant; the second identified the wrapper's console host. The revised normal-exit guard permits a bounded quiescence grace inside the existing wall cap, with identity, lease and memory checks still active. The [operational amendment review](../../validation/reproductions/s05_guard_grace_review_20261105.json) records that change; no scientific source, tolerance or roster changed.

The [initial input-package README](README.initial_input_package.md) retains the original input-only description and historical command instructions. The archived scoring interface below is preserved separately from the current guarded route; it does not itself provide the guard's process, lease and complete-report checks.

## Archived S05 scoring interface

`scoring_sources/` contains the exact archived independent closure source and
build scripts. `inputs.py materialize-s05` reconstructs its expected per-path
layout and a new manifest with hashes for the transformed metadata:

Materialized receipts refresh their current state/path/scalar pins and retain
old pins under `materialization_provenance.historical_hash_fields`. The full
original receipt remains in `S05/records.jsonl`; omitted detail artifacts are
not presented as current outputs.

```powershell
python -B reproduction/regional/inputs.py materialize-s05 --output C:/new/s05_inputs
```

The resulting `S05/replay_manifest.json` can be consumed by the included
`scoring_sources/replay.py` for **temporal** or **point** scope. Its `passed`
field describes verified input materialization, not likelihood acceptance.
The commands below retain the initial input package's archived interface. The
dated bounded execution used the supervised route and evidence linked above. Copy the exact scoring sources to a fresh external
build directory first. The archived build scripts emit binaries beside their
sources, so invoke them from that copy:

```powershell
Copy-Item -LiteralPath reproduction/regional/scoring_sources -Destination C:/new/s05_build -Recurse
# Build with Visual Studio 2022 Community; binaries stay in the external copy:
cmd /c C:\new\s05_build\build.cmd
python -B C:/new/s05_build/replay.py controls --dll C:/new/s05_build/independent.dll --output C:/new/s05_controls.json
$env:NUMERICAL_LEASE_TOKEN = 'regional-s05-explicit-run'
python -B C:/new/s05_build/replay.py run --scope point --manifest C:/new/s05_inputs/S05/replay_manifest.json --dll C:/new/s05_build/independent.dll --controls C:/new/s05_controls.json --output C:/new/s05_point_pilot --workers 1 --pilot
```

On Linux, copy `scoring_sources` to a fresh external directory and invoke that
copy's `build.sh`; it builds `independent.so` beside the copied sources.
Substitute that filename in the replay command. The historical command supports
omitting `--pilot` for the full roster and `--reuse PILOT_DIRECTORY` to retain
completed pilot rows. Any run should first pass its source-bound controls and
a measured pilot. The environment token is the archived runner's explicit
execution guard, not evidence of review or scientific acceptance.

The optional `full84` scope needs omitted per-event detail files and is **not
supported by this minimal bundle**. All expected 84-coordinate scalar vectors
are retained, but the point scope independently recalculates only its declared
point/joint and temporal fields. Historical closure reported point/joint replay
of all 5,994 paths. The dated current eight-path execution does not establish a
fresh complete replay of that historical roster.

## Boundaries that remain

Seed identities alone do not establish bitwise generator reproduction. The
original OC/EP generator/build/RNG mapping needs separate review before claiming
regeneration. S03/S06 entry points historically consumed derived geometry
caches and absolute paths. Their source and exact fit/nuisance inputs are now
available; a portable geometry wrapper and independent score pilot are still
required. Archived constructor snapshots inside the payload are source
references, not turnkey commands after path normalization.

Heavy geometry caches, S05 per-event diagnostic arrays and S06 score arrays
are intentionally omitted because they are derived outputs. No fitted state,
simulation path or failure record was replaced by an older or different model.
