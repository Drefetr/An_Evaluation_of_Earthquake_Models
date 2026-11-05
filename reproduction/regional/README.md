# Original regional computations and recovered inputs

The original S05 independent reconstruction **completed all 5,994 OC/EP point-score paths and all fifteen predeclared EP full-vector checks** on 1 November 2026. Their reports, durable journals, source bindings and unchanged pilot reuse are supplied in [the original-completion archive](original_completion_20261101.zip), with [member/source hashes](original_completion_20261101.manifest.json) and [a recovery audit](../../validation/reproductions/original_regional_completion_audit_20261105.json). These are existing completed computations, not new fits or another replay campaign.

The archive also supplies all original S03 four-arm fit/score records across the six California and New Zealand folds, and the exact fifteen S05 event-detail inputs. [The separate S06 score archive](original_s06_scores_20261101.zip) supplies the original California selected and candidate score JSON/NPZ files; its [manifest](original_s06_scores_20261101.manifest.json) and [recovery record](../../validation/reproductions/s06_saved_score_recovery_20261105.json) bind every file. The five-episode S06 fits and their full returned starts were already in the input payload. Japan's primary and S06 fits, nuisance states and selected/candidate scores are in [the JMA package](../jma/README.md).

## Verify or materialize inputs

NumPy is required for these input checks. No model is fitted, simulated or scored by these commands:

```powershell
python -B reproduction/regional/inputs.py verify
python -B reproduction/regional/inputs.py extract --output C:/new/regional_inputs
python -B reproduction/regional/inputs.py materialize-s05 --full84 --output C:/new/s05_inputs
python -B -m unittest discover -s reproduction/regional/tests -v
```

Output directories must be new. Verification checks payload/member hashes, the exact S05 roster, NPZ schemas and finite values, prehistory separation, forecast bounds, event counts, all four seed streams, expected scalar vectors, source/output numerical fingerprints and completed fit coverage. Materialization preserves original receipt identities under `materialization_provenance` and writes current hashes for the extracted files.

The `--full84` option additionally verifies the original-completion archive and installs the exact event-detail arrays for EP indices 0, 249, 499, 749 and 998 in each origin. It cross-checks their original state, raw path, scalar and receipt identities, eleven-column detail schema and detail hash. The resulting 6,000-row `S05/replay_manifest.json` supports the archived temporal, point and fifteen-path full84 input scopes. Its `passed` field certifies input checks, not a new execution of the model.

## Included scientific records

- **S05:** all 5,994 simulated futures, six observed futures and six frozen simulation states as exact NPZ bytes; every original seed receipt and expected 84-coordinate vector; the 2,997 retained OC job records; all completed original point/full84 reports and journals; and the fifteen full84 event-detail inputs. Observed rows use index -1 in the manifest while preserving the original observed receipt's index and state identity.
- **S03:** the input payload supplies the twelve California fitted arms and their nuisance/selection contracts. The original-completion archive adds all twenty-four California/New Zealand fitted-arm records, returned starts, selected vectors and held-out/near-optimal score records.
- **S06 California:** all 55 fit records across five episodes, including scale selectors and floors; case, nuisance, bandwidth and episode contracts; and all 1,040 original selected/candidate score files in the separate score archive. This includes every reported FC, MC, OC and EP full/active/complement score.
- **Japan:** the separate JMA package supplies the original provider records, region predicate, 36 primary fit records, 168 selected-score files, 660 candidate forecast files, and the three S06 fold packages.

The source crosswalks retain original hashes and identify any machine-root path normalization. Scientific numeric fields are unchanged, and NPZ arrays are copied byte-for-byte. Historical path identifiers are provenance locators rather than paths to a private installation. Large geometry caches are reproducible derived inputs; the original selected states and completed score outputs are supplied directly.

## Archived executable scoring interface

`scoring_sources/` retains the exact original independent closure source. A reader choosing to repeat its numerical checks needs SciPy and a C++17 compiler. Build in a fresh external copy so generated binaries stay outside the publication source:

```powershell
Copy-Item -LiteralPath reproduction/regional/scoring_sources -Destination C:/new/s05_build -Recurse
cmd /c C:\new\s05_build\build.cmd
python -B C:/new/s05_build/replay.py controls --dll C:/new/s05_build/independent.dll --output C:/new/s05_controls.json
$env:NUMERICAL_LEASE_TOKEN = 'regional-s05-explicit-run'
python -B C:/new/s05_build/replay.py run --scope full84 --manifest C:/new/s05_inputs/S05/replay_manifest.json --dll C:/new/s05_build/independent.dll --controls C:/new/s05_controls.json --output C:/new/s05_full84_pilot --workers 1 --pilot
```

Omitting `--pilot` selects the original full scope: fifteen paths for `full84`, or all 5,994 simulated paths for `point`/`temporal`. `--reuse` accepts a completed pilot with identical current source/input bindings. It cannot reuse an old report with different materialized metadata hashes. On Linux, use the external copy's `build.sh` and substitute `independent.so`. The original protocol and actual completed reports define the scientific scope; the environment token is only the archived command's explicit execution guard.

Full84 means all 84 coordinates and eleven event-detail columns on the fifteen predeclared EP paths. It does not mean spatial-PIT reconstruction on every simulated future. All-path point scope reconstructs its declared timing, spatial point/location, common-mark and joint score fields.

## Later optional check retained as history

The separate 5 November check passed its native controls, six pilot cases and two large-input probes. Its newly imposed conservative runtime gate declined another full replay. That later eight-case check does not supersede or invalidate the completed 1 November campaign. Its [summary](../../validation/reproductions/s05_execution_20261105.json), [archive](s05_execution_20261105.zip) and [manifest](s05_execution_20261105.manifest.json) remain intact, including both failed compiler-process attempts and the failed resource admission.

[The guarded runner](REPLAY_GUARD.md), [its protocol](replay_protocol.json), [workload record](workload.json) and [operational grace review](../../validation/reproductions/s05_guard_grace_review_20261105.json) document that later optional route. Its fixed resource envelope is not a claim that the original scientific work remains unfinished. The [initial input-package README](README.initial_input_package.md) is retained as historical packaging documentation.
