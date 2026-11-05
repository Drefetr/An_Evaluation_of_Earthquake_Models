# Completed S02 inputs and original fit records

This package supplies the original 300 catalogues, 600 fitted method cases, all 600 saved attempt traces (9,606 recorded attempts), actual generation configurations, score summaries, contracts, original review reports and source files. It packages the completed October campaign; no new simulation, fit or likelihood replay was performed during recovery.

From the repository root, verify the complete payload or extract it into a new directory:

```text
python -B reproduction/s02/inputs.py verify
python -B reproduction/s02/inputs.py extract --output build/s02_original_inputs
```

These commands need only Python's standard library. They check every member hash, the exact 100-forest by three-persistence roster, generation seeds, history counts, coupled time/parent skeletons, fitted identities and selected-state finiteness. They do not import a scientific module.

`index.json` maps every forest/persistence case to its exact CSV, configuration, fitted outputs and attempt traces. `fits/` retains the full original method records, including selected null/alternative vectors, recorded attempts, direct contrasts and numerical controls. `reports/` contains the original 600-row analysis and published summaries. `audits/` contains the historical saved-record inspection and the separate three-catalogue/six-method numerical sample. `contracts/` retains the generation/recovery and fit amendments. Source and original/public SHA-256 mappings are in `manifest.json`; only machine-root path strings were normalized to `workspace:` or `machine_user:`. Scientific numeric values and retained failures were not changed. CSVs, configurations and scientific source files are byte-exact.

The authoritative executed candidate settings are implemented in the supplied `source/research_runs/scientific_stage2_resume_20261031T205913Z/temporal/source/s02_campaign.py`, `campaign.py` and their pinned dependencies. The inherited `S02_STAGED_RECIPE.json` contains earlier nuisance-ladder metadata; it is not sufficient by itself to describe S02. The actual S02 wrapper fixes candidate reproduction to 0.5, compares productivity ratios 0.7 and 0, and uses the declared strengthened starts. The generation configurations record the actual caps and parameters for each retained history. All original generation/recovery manifests and amendments are included.

The archived runner `resume_s02.py` and build source are supplied for inspection and future controlled execution from a fresh reconstructed workspace. They expect the original relative workspace layout and an explicitly compiled temporal library. This package's verification command does not compile or launch them. The C++ matched generator source and the preserved `research_f_continuation/engine` dependencies are included under `source/`; no large compiled cache is needed to inspect the completed records.

Historical validation covered all saved records and independently recomputed three predeclared catalogues/six methods. It was not an independent replay of all 600 fits. The original attempt traces record best-visited states rather than every raw optimizer-terminal vector; the package preserves what was actually recorded. Same-bank empirical thresholds remain descriptive, and the original exact-memory generator versus finite-mixture candidate distinction remains part of the scientific contract.
