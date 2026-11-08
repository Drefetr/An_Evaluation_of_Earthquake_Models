# Validation and evidence

This directory separates current manuscript bindings, additional numerical source inventory, dated internal scientific and artifact review records, and bounded check results. Historical preparation/release receipts are indexed in [provenance/historical_archive.json](../provenance/historical_archive.json); their original hashes and baseline locations remain available without presenting them as current validation.

## What each record establishes

| Record | Role |
|---|---|
| `MASTER_CLAIM_LEDGER.json` | Enumerated manuscript bindings and typed documentary metadata, with explicit source hashes, locators, and transformations |
| `SOURCE_INVENTORY.json` | Additional numerical source inventory, kept separate from claims of manuscript support |
| `authorities/`, `authority_manifest.json` | Bundled scientific sources and their historical/public identities |
| `acceptances/` | Historical internal reviews; their filenames do not represent journal acceptance |
| `reviews/`, `reproductions/` | Current artifact checks and actual recovered-input execution records, with separate scope and identities |
| `live_results/methodological_20261106/` | Current thinning/fit-vector and analytic diagnostics, plus all 80 newly executed train-only S04B intercept fits and their score decomposition |
| `numeric_reconciliation_receipt.json` | Canonical claim/source reconciliation receipt; default verification checks bindings without rewriting it |
| `checks.json` | Actual current bounded check coverage and results, with the recorded snapshot and execution scope |
| `checks_before_remediation_20261105.json` | Exact historical `checks.json` bytes from commit `1226fc3`; retained prior coverage, not current-edition validation |

The default verifier checks both ledgers. Source inventory records are not automatically manuscript claims. A verified hash establishes source identity, while numerical reconciliation checks declared values/transformations. Neither establishes exhaustive theorem correctness, completeness of all manuscript claims, causal identification, or independent raw replay of every experiment.

Explicit [withdrawals](withdrawals/CLAIM_WITHDRAWALS_20261105.json) preserve retired records exactly against the archived baseline ledger. The verifier still checks their authority and arithmetic, but excludes them from current display counts. Current bindings must point into the compiled LaTeX input tree. Receipt refresh cannot automatically withdraw a missing claim.

The manuscript ledger stores shared TeX source hashes and the fixed verification method once in `display_custody`. Each claim keeps its matching files and a digest binding its identity, displayed value, and declared locations. Ordinary verification recomputes every binding against current source bytes and rejects stale or missing custody. The display-regression receipt summarizes the verified ledger hashes, counts, and sources without copying the per-claim records. Explicit `scripts/verify_claims.py --write-receipts` migrates or refreshes this representation after deliberate source review.

The ledger's `current_edition` identifies this revision and its withdrawal registry. The older `edition` and `closure_revision` fields retain their original ledger-migration meaning. The [result provenance map](../docs/result_provenance.md) records scientific execution separately.

The [selected-state replay coverage review](reproductions/score_replay_20261107/final_coverage/independent_review.json) records completed historical score replays separately from source/display custody. It distinguishes newly reconciled fields, retained prior replay evidence and scopes requiring no additional likelihood execution. Original optimizer campaigns were not repeated, and small exact-display differences remain explicitly flagged under the unchanged functional tolerances.

The [refitted-floor summary](live_results/methodological_20261106/refitted_floor_summary.json) derives from the [complete execution](live_results/methodological_20261106/refitted_floor/result.json), including 480 historical train/test floor checks and 80 retained case reports. Its new fit changes only the uninhibited background intercept; all original inhibited states and gates remain unchanged. [Source and run instructions](../experiments/s04b_refitted_floor/README.md) and the [methodological response](../docs/reviews/methodological_review_response.md) distinguish this executed sensitivity from saved-record diagnostics and analytic calculations. Neither a passed numerical comparison nor a finite fixed-strength bracket bound establishes general parameter recovery or a calibrated distribution for selected held-out losses.

The [unit-mark narrow/short audit](../reproduction/synthetic/s2_unitmark/README.md) binds the original histories and their realized-thinning check. It supplements the earlier S04B census without changing its records or repeating fitted procedures.

## Check a checkout

From the repository root after installing `requirements.txt` and Node.js 22 (also used by the workflow tests):

```sh
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s reproduction/regional/tests -v
python -B reproduction/regional/inputs.py verify
python -B -m unittest discover -s reproduction/s02 -p test_inputs.py -v
python -B reproduction/s02/inputs.py verify
python -B reproduction/historical_fits/verify.py
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
node website/check_interactions.cjs
```

The [current check record](checks.json) gives separate executed counts for the main suite, regional input, point-control and process-supervision tests, eight Stage 2 tests (five portable and three native fixtures), six S02 input-control tests, and twenty historical iteration-27 tests. The main suite includes the other supplied replay packages. The total is not the count of the first command alone. The historical full execution used Windows/MSVC native builds. The current Stage 2 command automatically builds the LI, temporal and S06 fixtures when no native root is configured; Linux uses GNU/Clang C++17 and Windows uses MSVC. A missing compiler fails rather than skipping the fixtures. See the [native-build instructions](../engine/stage2_followup/README.md#native-builds). The iteration-27 suite also requires a separate CUDA-enabled PyTorch installation and a usable CUDA device; its small CUDA/CPU fit comparison has no CPU fallback. These optional GPU dependencies are not included in `requirements.txt`.

The separate [CPU route](../docs/cpu_reproduction.md) has a [bounded fresh-Linux execution review](reproductions/cpu_20261107/checkout02_independent_review.json). Its numerical kernel and public-reader checks require a C++17 compiler on Linux, without MSVC or CUDA. It does not claim execution of the historical GPU assertion, macOS acceptance, or a fresh all-history scientific campaign.

The separately versioned [refined joint-fit reader](../experiments/s04b_refined_cpu_reader/README.md) uses a bundled audited Linux x86-64 native library with automatic extraction. It does not need a local compiler. Its [source review](reproductions/continuation_20261107/joint_refined_cpu_combined_source_review.json), constructed controls and actual output reviews have separate scopes. Fresh-local finite limits do not use the authors' expiry; the optional author record retains the dated envelope. The older CPU acceptance does not execute or certify this later reader.

After building the native groups into `build/native/{li,temporal,s06}`, run the two additional suites from the repository root in PowerShell:

```powershell
$env:INHIBITORY_TEST_NATIVE_ROOT = (Resolve-Path build/native).Path
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m unittest discover -s engine/iteration_27/tests -v
```

Without `INHIBITORY_TEST_NATIVE_ROOT`, the Stage 2 command runs its five portable tests and skips its three native fixtures. That portable result does not establish the full native test coverage. CI runs the portable subset; the recorded local execution separately identifies native and CUDA prerequisites.

Node.js is required for the website interaction check. [Reproduction instructions](../docs/reproducibility.md) distinguish these checks from document builds and scientific workloads. Generated PDF production checks still need visual inspection. Stage 2 import/build fixtures cover only the supported components identified in the [support matrix](../engine/stage2_followup/README.md).

The [current production review](reviews/S2_CONTROL_EDITION_20261107.json) pins the delivered manuscript, companion and repository site. `website/document_metadata.json` pins that review record. The [preceding reassessment](reviews/REASSESSMENT_CLARIFICATIONS_20261106.json), earlier editorial reviews and S04B reviews retain their original artifact identities. These are internal production records, not external peer review.

## Historical receipts and source changes

The [pre-closure checks](checks_before_closure_20261105.json) preserve the exact preceding completed-replay edition. Current checks record evidence recovery, explicit withdrawals and the rebuilt publication. The [closure record](reproductions/evidence_closure_20261105.json) links the recovered original computations and separate independent package reviews. Earlier replay attempts, including the later S05 adapter runtime-gate refusal, retain their own scope; the original completed S05 execution is now supplied.

The [pre-remediation check snapshot](checks_before_remediation_20261105.json) preserves the complete `validation/checks.json` from commit `1226fc3b42209afa629ff94063d9c3c5f74e1098`, including `isolated_builds`, `source_migration_review`, `compact_metadata` and `asset_payload`. Its original snapshot statements and byte-savings figures describe that earlier repository state. The `historical_checks` reference in current `checks.json` pins this preserved record; those results are not silently promoted to current coverage.

October baseline receipts described earlier manuscript/supplement editions and a smaller test suite. Final-release build receipts describe their original compiler, source, and PDF bindings. They are historical evidence rather than a fresh check of the current tree. Earlier privacy scans likewise do not cover later additions by implication.

Publication variants, path migration, or deduplication can change public source bytes without changing scientific values. Preserve original identities and record the transformed bytes, then update dependent ledger hashes, documentary locators, authority mappings, site/companion bindings, and receipts together. Current repository membership is authoritative in `MANIFEST.json`; historical archive indexes and source inventories have different scopes.

The recovered-input packages now supply the original regional event records, declared synthetic/reference banks and available fitted vectors. See [the reproduction index](../reproduction/README.md) for executed routes, original states still missing and caches rebuilt from raw inputs. Scientific acceptance, source reconciliation, document production, and external academic peer review are separate forms of evidence.
