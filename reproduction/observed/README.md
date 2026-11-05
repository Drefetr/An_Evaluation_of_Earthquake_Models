# Refit and compare the frozen New Zealand observed procedure

The completed 5 November 2026 refit reproduced all **83,506 scientific numeric fields** in the original saved result exactly. This comparison covers complete optimizer records, fitted parameters, selected models, event-level likelihood contributions, residual increments, censored exposure and numerical controls. It does not merely compare rounded table scores.

Run the complete fitting route once from the repository root, using an unused output directory:

```powershell
python -B scripts/reproduce_observed.py --output build/observed_reproduction
```

The wrapper verifies the bundled 913-event CSV and every source pin, installs the CSV only if the ignored engine input is absent, invokes the unchanged `scripts/run_observed.py` once, and compares its completed result with the full historical result. Existing inputs are hash-checked and never overwritten. Existing output directories are refused. The numerical procedure retains its original folds, grid, starts, failure recovery, controls and cooperative 1,800-second budget. A failed or incomplete fit returns nonzero and retains its logs and progress output. The budget is not a proved hard wall-clock cap.

The numerical dependencies are those used by the existing engine: Python, NumPy, SciPy, pandas and threadpoolctl. The wrapper requests one native thread. The successful recorded run used Python 3.13.4, NumPy 2.2.6, SciPy 1.15.3 and pandas 2.3.3. Other environments may produce different optimizer trajectories; the comparator reports those differences and fails exact-reproduction acceptance rather than silently treating a close final score as equivalent.

To inspect the already completed result without another model fit:

```powershell
python -B reproduction/observed/compare.py --output build/observed_saved_comparison.json
```

To compare another completed `observed.json`, use `--actual PATH` with the comparator, or `scripts/reproduce_observed.py --compare-existing PATH --output NEW_DIRECTORY`. Comparison-only execution does not refit or reinstall the catalogue.

## What is preserved and checked

`historical_observed.json.gz` decompresses to the **original complete historical output**, 3,570,617 bytes, SHA-256 `e7fbc4fa4fae3da4f8880695064798a8ebfc9342ab09303073f7afd7334439d8`. `replayed_observed_20261105.json.gz` contains the complete actual refit output, SHA-256 `ea1c853b7d88226e60aa07f5ea1cf78b4712bb558c5b8690b1276b42c3b60f18`. Both are lossless copies, with no scientific fields or unsuccessful optimizer attempts removed. Neither payload contains absolute machine paths or credentials.

Each of the three folds retains 159 prescribed search records and five selected model families. All 90,609 non-exempt leaf values match, including 83,506 numeric values. `comparison_20261105.json` is the independently generated comparison; `execution_20261105.json` records the actual completed run, its input, protocol, source hashes and environment. The actual fit process exited zero and completed in approximately 298 seconds including process startup/teardown.

`manifest.json` enumerates the exact JSON pointers permitted to vary. The 986 timing fields must still exist as finite nonnegative numbers. Started/completed times must be valid chronological UTC instants. Environment keys must remain present, and native thread count must remain one. The historical protocol hash differs from the public distribution protocol hash because of the already recorded packaging adaptations; the comparator requires the exact known current protocol and verifies all 33 of its source pins. Runtime source hashes, input byte identity and array identities are checked separately and are never free-form exceptions.

Every remaining field is compared for exact type, dictionary keys, list order/length and value. Missing folds, omitted optimizer records, extra fields, altered controls, altered event contributions or changed parameters fail. The report includes all difference paths and the maximum absolute numeric difference. No statistical tolerance is used to assert optimizer equivalence. An existing report cannot be overwritten.

The result concerns this frozen fitted procedure on the previously inspected NZ reconstruction. Replaying it does not create a new untouched holdout or validate a physical inhibition mechanism. The separate `reproduction/nzca/` command reconstructs the input CSV from the original public provider bytes.

Run the small comparator and integrity controls with:

```powershell
python -B -m unittest discover -s tests -p test_observed_replay.py -v
```
