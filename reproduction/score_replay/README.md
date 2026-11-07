# Saved-state score replay

This package separates input recovery, likelihood evaluation, and publication coverage. The initial cached registry supplies 510 selected training/test rows in ten Chapter 9/10 study groups. Additional registries cover the recovered regional, inhibition and profile inputs. The table inventory includes 103 table containers in the requested chapters and their appendix tables. Input/code availability is distinct from a passed execution or reconciled table: actual outcomes belong to the separately retained execution receipts and table deltas.

`coverage_plan.json` records all implementation routes, including the delegated S02 and initial mark-history routes. `table_links_regional.json` maps 933 score/count cells to actual replay outputs, and the S05 inventory adds 54 observed-score alias checks. The cached-table mapping and route-specific table deltas cover the remaining Chapter 9/10 arithmetic. The complete productivity profile grid is required for the sampled-support lists, not merely the displayed selected coefficient.

The observed fixed-backbone package now contains all 51 exact original state and preparation files, including the positive total-intensity fits. Its held-out replay retains recorded training gate choices and uses unchanged quadrature with CPU matrix contractions. Every identified input route is available; source review, empirical execution and output reconciliation remain separate gates. No pending row is silently counted as a successful replay.

The evaluator loads the original selected parameter vector and byte-exact cached features, builds the original native source with a recorded compiler, and evaluates the likelihood again. Expected scalar scores are compared after evaluation. This is cached-feature replay: it neither regenerates raw catalogue geometry nor reruns the original parameter search. `input_manifest.json` records original identities, historical seals or case-artifact pins where available, and the SHA-256 of every packaged resource. Projected state records identify their original JSON pointers. The original numerical source bytes and cached arrays are unchanged.

`cached_field_crosswalk.json` maps each engine's output to positive integrated intensity **E**, signed compensator **C = −E**, event log-intensity sum **P**, and mark score **M**. Timing and location remain distinct. Same-cache comparisons use a predeclared absolute tolerance of one micro-nat; original coarse/fine checks and displayed rounding are separate. A discrepancy remains a failed replay requiring diagnosis, not an automatic withdrawal of the historical finding.

The initial pilot proposal selects one ordinary test row and the largest stored cache for each of nine engines without consulting gain signs. No real-history execution is authorized by a proposal file. The conductor supplies a passed admission with exact source/registry/input/build identities, the ordered roster, numerical-thread cap and an actual numerical lease. Build and replay outputs must use fresh directories:

```text
python -B reproduction/score_replay/build.py --output build/score_replay_native
python -B reproduction/score_replay/replay.py --libraries build/score_replay_native/libraries.json --admission PATH_TO_REVIEWED_ADMISSION.json --rows PATH_TO_ORDERED_ROSTER.json --mode pilot --output build/score_replay_pilot
```

The runner validates the actual target count, compiler receipt, binary identity and thread limits; an external supervisor enforces wall time, process-tree memory and process cleanup. Every completed row receives a retained report and progress entry. `not_run`, `failed`, and interrupted rows cannot be promoted to completed coverage. The existing Chapter 7/8, S04B and refitted-intercept campaigns are outside this replay roster. The original S05 all-path point checks are inventoried as already executed and are not automatically repeated.

Tiny controls use invented scalar data and a fake adapter, not historical scores:

```text
python -B -m unittest discover -s tests -p test_score_replay.py -v
```
