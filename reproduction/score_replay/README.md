# Saved-state score replay

These routes recompute likelihoods at the original selected parameter vectors. They do not rerun a parameter search, fit a new model, or generate replacement histories. Expected scores enter only after the evaluator returns its new components. Raw-feature reconstruction and cached-feature replay are identified separately in each registry and output row.

## Local Linux reader

Use a Linux host with Python 3.13 and a GNU or Clang C++ compiler. No GitHub token, private directory, CUDA installation, or MSVC is required. The original C++ sources are compiled locally with strict floating-point options; the observed fixed-backbone route uses CPU NumPy contractions without a native build. The inputs and published execution ZIPs are included in the checkout.

From the repository root:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-cpu.txt
python -B scripts/reproduce_cpu.py list
python -B scripts/reproduce_cpu.py run --route cached --phase pilot \
  --output ../reader-cached-pilot --wall-seconds 900 --rss-mib 6144 --headroom-mib 2048
```

The three resource limits are required. The wall allowance includes compilation and evaluation. The Linux supervisor samples process-tree RSS and available host memory, enforces the wall deadline, and checks descendant cleanup. Memory sampling is not a kernel allocation limit. The evaluator uses two numerical threads. Pilot limits cannot exceed the frozen pilot envelope. Outputs must use a new directory outside the checkout; an existing result is never overwritten.

Add `--plan-only` to check source, input, roster and published-dependency identities without compiling or evaluating a historical row. A plan directory is retained as evidence; use a different fresh directory for the actual run. `list` inspects locally published archives and their review pins; it does not perform a numerical replay.

| Route | Declared units | Evaluator/input scope |
|---|---:|---|
| `cached` | 510 rows | Original Chapter 9/10 selected states and cached features |
| `cached_supplement` | 140 rows | Additional training, engineering, reference and small-scale states |
| `productivity_profiles` | 84 rows | Full saved profile grid, including training support points |
| `california` | 60 rows | Primary and magnitude-threshold sensitivity cached states |
| `california_benchmark` | 12 rows | Original EP/N0 cached states; common mark term is stored in the cache |
| `jma` | 93 rows | Regional reconstruction at frozen states |
| `s03` | 24 rows | Original spatial-source/cached-state adapter |
| `s06_ca` | 60 rows | Episode-block reconstruction at frozen states |
| `original_li` | 38 rows | Original selected LI/OC procedures and raw-input reconstruction |
| `s04_original` | 80 histories | Original selected synthetic procedures; no history generation |
| `california_blocks` | 39 rows | Interval scores using retained, freshly replayed event arrays |
| `observed_fixedbackbone` | 6 fold-by-quadrature rows | Exact selected states and prepared quadrature, checked against freshly replayed OC |
| `s02` | 300 catalogues | Original paired-clock selected-state likelihoods |
| `initial_mark` | 60 catalogues | Initial mark-history selected-state likelihoods |

Counts are workload units, not independent samples. For registry routes, `--phase all` requests every row. `--phase completion` requests exactly the nonpilot rows and does not claim the pilot was rerun. `--phase subset --rows ordered_ids.json` requests a nonempty explicit list of registry IDs. Keep all attempt directories: a failed or interrupted attempt is evidence, not a result to erase. A later subset can recompute unresolved rows from scratch without changing their state, quadrature or tolerance. No partial run is labelled full coverage.

The author campaign's [accepted final coverage](../../validation/reproductions/score_replay_20261107/final_coverage/independent_review.json) reconciles the declared historical table roster from actual selected-state replays, retained earlier evidence and explicit metadata checks. That acceptance does not transfer to a reader's new run. No historical optimizer campaign was repeated. The [amended joint fitting command](../../experiments/s04b_refined_cpu_reader/README.md) is a separate fresh-fit operation with its own producer identity; it is not one of these score-replay routes.

S02 and initial-mark routes retain their original pilot/completion contract. Their local pilot inherits the exact source admission recorded in the hash-checked published pilot, not an endorsement of the new numerical output. Completion reuses a local pilot's actual library and reports and requires a separate output review:

```sh
python -B scripts/reproduce_cpu.py run --route s02 --phase pilot \
  --output ../reader-s02-pilot --wall-seconds 1800 --rss-mib 6144 --headroom-mib 2048
python -B scripts/reproduce_cpu.py run --route s02 --phase completion \
  --pilot-output ../reader-s02-pilot --pilot-review ../s02-pilot-review.json \
  --output ../reader-s02-completion --wall-seconds 14400 --rss-mib 6144 --headroom-mib 2048
```

The separately authored review must identify `reviewer` and `scope`, set `passed: true`, and pin the pilot's `science/result.json` with `result_sha256`. The reader does not generate this independent review. The frozen runner also requires identical source, runtime, numerical library and ordered pilot records. A failure of those conditions is retained; it does not authorize a refit or a relaxed tolerance.

The block and observed routes use locally published California pilot/completion ZIPs, bound to the public acceptance index and original output reviews. They do not fetch artifacts through GitHub or read private build paths. Their retained dependency records distinguish a saved benchmark mark scalar from a newly evaluated intensity. `california_mark_replay.py` provides a separate source-reviewed arithmetic route from the exact recovered cohort and saved beta to the common mark term; its execution and acceptance remain separate from the intensity replay.

## Reading results and coverage

`reader_result.json` records the actual supervision and scientific-result hashes, requested IDs, retained IDs and missing IDs. It succeeds only when the supervisor and requested scientific roster pass and every retained row matches its hash. `all_declared_rows_present` is separate from success on a subset. Partial row reports, compiler logs and supervisor samples remain on disk after failure. These are automated integrity and numerical checks, not independent scientific acceptance.

`coverage_plan.json` inventories 103 table containers. `table_links_regional.json` maps 933 score/count cells; the original S05 inventory adds 54 observed-score aliases. Cached-table links and route-specific `table_deltas.json` retain the remaining Chapter 9/10 arithmetic. The complete profile grid is needed to reconstruct sampled-support lists. The block pilot/completion union needs the separate hash-bound `finalize_blocks.py` aggregation before all partition contrasts are claimed. Implementation availability does not establish a table result: consult actual execution rosters and reconciled table deltas. A missing or failed row stays unresolved.

All 51 original observed fixed-backbone state and preparation files are present, including the positive total-intensity states. Training gate choices remain recorded choices; the held-out replay does not repeat selection. The original S05 all-path point checks are inventoried as already executed and are not automatically repeated. Existing Chapter 7/8 and S04B campaigns are outside this reader's replay roster.

`cached_field_crosswalk.json` maps original output to event log-intensity sum **P**, positive integrated intensity **E**, signed compensator **C = −E**, and mark score **M**. Timing and location remain distinct. Same-cache comparisons use the declared absolute tolerance against full-precision saved results; quadrature sensitivity and displayed rounding are separate checks. Source/input/build identities and the actual target count are checked before comparisons. A discrepancy remains a failed replay requiring diagnosis.

Constructed controls (no historical fits or score campaigns):

```sh
python -B -m unittest discover -s tests -p test_continuation_controller.py -v
python -B -m unittest discover -s tests -p test_california_mark_replay.py -v
python -B -m unittest discover -s tests -p test_score_replay.py -v
```

