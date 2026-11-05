# Rebuild the data and calculations

This directory supplies recovered original inputs and executable replays. The catalogue commands reparse provider records; the model commands evaluate likelihoods or refit models. Expected outputs are comparison targets, not replacements for these calculations.

Run from the repository root after installing `requirements.txt`. Every output directory must be new.

| Task | Command | Calculation |
|---|---|---|
| New Zealand cohort | `python -B scripts/reproduce.py --study nz --output build/replay_nz` | Original WFS responses to the exact selected CSV, with inclusion/exclusion accounting |
| California cohort | `python -B scripts/reproduce.py --study california --output build/replay_ca` | All original annual files to canonical records, source tokens, exclusions and fold membership |
| Japan cohort | `python -B scripts/reproduce.py --study jma --output build/replay_jma` | Original annual ZIPs to the reported-primary cohort, projected coordinates, clocks and fold arrays |
| Frozen NZ model fit | `python -B scripts/reproduce_observed.py --output build/replay_observed` | Complete unchanged fitting recipe and comparison of every scientific result field |
| Matched-generator S04B scores | `python -B scripts/reproduce.py --study s04b --output build/replay_s04b` | Rebuild quadrature from raw histories and recompute selected/floor training and held-out likelihoods |
| Primary known-law calibration | `python -B reproduction/oracle/replay.py --output build/replay_oracle` | Recompute signed likelihood ratios from all histories, then ranks and decisions only if the complete bank passes |

The model workloads can take substantially longer than catalogue reconstruction. The S04B and oracle guides provide fixed pilot commands, resource controls and precise numerical acceptance rules. A partial run remains partial; no missing case is treated as a non-rejection or silently replaced. `scripts/reproduce.py --study all --output NEW_DIRECTORY` combines the three cohort commands and S04B scores; the NZ optimizer and complete oracle bank are explicit separate workloads.

The executed NZ refit reproduced every scientific numerical field exactly, including complete search records and event-level diagnostics. The three regional cohort replays also passed. The complete known-law calibration replay recomputed all 2,149 raw histories and all 1,150 rank decisions, reproducing the historical outcomes. The completed S04B replay independently recomputed the selected and floor likelihoods for all 80 histories, reproduced all 400 procedure scores and all 20 published summary rows, and retained the interrupted first attempt alongside its completion. Dated execution records are in [`validation/reproductions/`](../validation/reproductions/); consult the actual case roster and completion status for subsequent numerical runs. A source review or a successful data verification mode does not assert that a full campaign was executed.

| Package | Supplied inputs and instructions |
|---|---|
| [NZ/California](nzca/README.md) | Losslessly compressed original responses and annual files, original selection functions, exact expected cohorts and optional hash-checked official retrieval |
| [Japan](jma/README.md) | Original ZIPs, recovered projection/parser/adjudication, expected arrays and saved fitted-state/score records |
| [California S03/S05/S06](regional/README.md) | All 5,994 conditional paths, seed records and fitted/nuisance states; guarded point replay with actual controls and eight pilot/probe rows. Full replay was not launched after its runtime gate failed. |
| [Observed NZ](observed/README.md) | Complete historical and new fit outputs, explicit identity checks, strict full-result comparator and fitting wrapper |
| [Synthetic S04B/S01](synthetic/README.md) | Exact histories, generating settings, seed/role/clock mappings, retained states and CPU geometry/likelihood implementation |
| [Known-law oracle](oracle/README.md) | Original likelihood and rank-calibration functions, exact per-case score targets and a portable process runner |

Original provider bytes remain identifiable after compression. Public variants remove operational machine paths while preserving numerical fields and recording original/public hash mappings. Rebuildable feature caches are outputs of these routes. The source inventories identify the older F restricted-fit states that remain missing; the supplied earlier fits are not substitutes for those states.

The scientific results retain their original populations and interpretation. Re-executing an inspected-data procedure does not create an untouched holdout, and known-law calibration does not become fitted-null composite calibration. These are different investigations from the reproducibility gap closed here. The earlier third-party manuscript's original dataset remains distinct from the recovered project reconstruction.

Provider credit and data terms are documented in each package and the [third-party notices](../THIRD_PARTY_NOTICES.md). The software and project-authored summaries retain the repository's existing licences.

A separate [autonomous-model comparison](../experiments/autonomous/README.md) implements a newly specified statistical subfamily that matches the finite-mode theorem. It is separate from reproducing historical results. Its fixed pilot and complete three-fold fit have now passed independent output review. The early and late folds lose held-out score; the middle fold selects zero inhibition. Complete fitted states and numerical outputs are supplied with the experiment.
