# Known-law likelihood and calibration replay

This reproduces the primary supplied-parameter experiment completed in iteration19: a signed likelihood ratio between the fixed uninhibited law and the fixed alternative with `eta = 0.4885010300470942`. Its original reported outcomes were 150 detections among 150 alternative histories and 50 rejections among 1,000 held-out null histories, calibrated against 999 separate null reference histories.

The statistic is the full-window ground log likelihood ratio, including the compensator and random event count. The same fixed exponential mark law cancels between the two hypotheses. All other nuisance parameters, the 195-mode normalized finite mixture, and the 24,394-day horizon are fixed at their original values. This is distinct from the F/S01 I00 procedure, which estimates eta while retaining supplied nuisance values. It is also distinct from a fitted-null bootstrap.

All 2,149 input histories already appear in `../synthetic/s01/histories/`; no duplicate bank is shipped here. `input_manifest.json` proves that the primary oracle's original catalogue hash, seed, identity and clock match each shared input. The exceptional paired-clock history is `null_0841`. The other 2,148 histories retain their original projected-clock convention. No event is shifted, merged or dropped.

The four files under `source/` are exact archived sources whose hashes match the original accepted iteration19 plan: the CPU likelihood, finite-mixture kernels, pure statistical analysis, and its checkpoint import dependency. The new `replay.py` only supplies portable paths, explicit inputs, bounded parallel execution, comparison checks and fresh output handling. The original iteration19 campaign used CUDA for quadrature; this implementation recomputes it on CPU using the original CPU authority.

## Run from the repository root

Python 3.11+, NumPy and SciPy are required; the repository requirements provide package pins. No compiler or CUDA device is required.

```text
python -B reproduction/oracle/replay.py --mode verify --output build/oracle_inputs
python -B reproduction/oracle/replay.py --pilot --output build/oracle_pilot
python -B reproduction/oracle/replay.py --case null_1292 --output build/oracle_large_case
python -B reproduction/oracle/replay.py --output build/oracle_all2149
```

Every output directory must be new. `--pilot` selects `null_0000`, `null_0841`, `null_0999` and `new_r000`: an ordinary reference, the paired-clock reference, a held-out null query and an alternative query. A pilot never reports calibrated rejection frequencies. The separately labelled `null_1292` resource probe contains 30,276 events; it remains part of the full roster regardless of the probe's outcome.

The default uses four worker processes with one BLAS thread each, a 900-second per-case soft deadline and a 10,800-second campaign soft deadline. Use `--workers 1..4`, `--case-timeout-seconds` and `--timeout-seconds` to configure a declared run. The original CPU benchmark took about 9–59 seconds on several histories and exceeded its old 120-second cap on the largest history. Measure the fixed pilot and largest case before committing to a full CPU runtime; the complete run may take hours.

Each worker uses at most 512 query nodes at once and fresh per-history modal state. No fitting, simulation, bank resampling or GPU evaluation occurs. `result.json` and per-case files retain progress and failures. After a failure the controller stops launching new cases and preserves results from already-running workers. A partial bank cannot produce a threshold or detection-frequency result. Deadlines are checked inside the accepted evaluator; an external scheduler can enforce a hard process-tree limit. Subsequent attempts use new output directories.

## Acceptance checks

For every history, the unchanged evaluator computes orders16 and32. Order64 is used only if `abs(L32-L16) > 1e-6`; it succeeds only when `abs(L64-L32) <= 1e-6`. The selected order must match the archived result. Each newly computed LR, event contribution, compensator reduction and auxiliary NLL must agree with the corresponding original result within absolute `1e-6`, with zero relative tolerance. Expected values are comparison targets, never likelihood inputs.

Only after every one of the 2,149 new scores passes does the original pure classifier rebuild all 1,150 query outcomes. Its point rank is `(1 + number of reference scores >= query score)/1000`. Ties use `>=`. The original numerical envelopes, at least `1e-6`, determine stable rejection, stable nonrejection or an unresolved decision. Every rank and sensitivity range must match, followed by exact counts and statuses; descriptive scalar calculations must agree within `1e-12` to accommodate library rounding.

`result.json` sets `passed: true` only when the requested run completes. `full_campaign: true` and `calibration_performed: true` require the complete matched-score bank and matched calibration. The saved fitted-detector result of57/150 is not recalculated or claimed by this adapter. The replay establishes computational access to the original known-law experiment; it does not make that experiment a test for unknown nuisance parameters.

## Tiny controls

```text
python -B -m unittest discover -s tests -p test_reproduction_oracle.py -v
```

The tests verify every source/input pin and the complete role/clock mapping. They compare tiny exponential and finite-mixture histories against independent direct-parent sums and adaptive scalar integration, check paired-clock strict history behavior, check ties and the rank boundary, and reject incomplete calibration banks. No stored campaign history is numerically evaluated by these tests.

## Completed raw-history replay

The 5 November 2026 execution recomputed all 2,149 histories and reproduced all 1,150 rank/envelope outcomes: 50 of 1,000 null queries and 150 of 150 alternative queries, with no unresolved decisions. An independent output audit checked 30,086 likelihood components; the largest difference from the historical components was approximately 4.55e-13. The original known-law interpretation is unchanged.

`completed_20261105.zip` retains every actual per-history JSON result plus `result.json` and `calibration.json`, without dropping failures or altering numbers. The [execution](../../validation/reproductions/oracle_full_execution_20261105.json) and [separate output review](../../validation/reproductions/oracle_full_review_20261105.json) pin this archive and describe their different scopes. The run took about 78 minutes with four workers on the recorded host.
