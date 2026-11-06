# Reviewer guide

Start with the [current unified monograph](paper/manuscript_unified.pdf), its [limitations](docs/limitations.md), and the study map below. This edition reports supported completed studies, including S04B controls; F and unexecuted prospective/horizon material have been withdrawn. Earlier PDFs remain available for comparison; their production receipts and unresolved counts do not describe the current edition by implication.

The [plain-language guide](companion/lay_guide_to_the_research.pdf) introduces the studies without equations. The [findings explorer files](website/site/findings.html) use accepted aggregates and retain separate study populations; use the [website instructions](website/README.md) to preview the site.

## Reproduce results from supplied inputs

The [recovered-input guide](reproduction/README.md) provides the original New Zealand catalogue, California annual files, Japanese source archives and projected-region predicate, plus the recovered simulation histories and available fitted states. Cohort reconstruction has been executed for all three regions. The complete frozen New Zealand fit has also rerun: all scientific values match the archived result. These executions are separate from the claim ledger's display checks.

```sh
python -B scripts/reproduce.py --study nz --output build/replay_nz
python -B scripts/reproduce.py --study california --output build/replay_california
python -B scripts/reproduce.py --study jma --output build/replay_jma
python -B scripts/reproduce_observed.py --output build/replay_observed
```

Read the [per-study provenance map](docs/result_provenance.md) before equating a supplied input or runner with a fresh score computation.

The [methodological review response](docs/reviews/methodological_review_response.md) records the latest changes. Its new numerical experiment is the [train-only S04B intercept control](experiments/s04b_refitted_floor/README.md): all 80 saved histories completed, with 480 historical floor comparisons and every original inhibited fit and gate retained. Matched broad/long mean gains fall to 5.1631 nats (immigrant, 19/20 wins) and 9.7367 nats (total, 18/20 wins). This sensitivity does not jointly refit the inhibited alternatives or establish nominal testing size. The supplied thinning, parameter-boundary and mark-moment diagnostics explain the study's actual generating and fitting conditions.

Use a fresh output directory for each command. The study guides describe optional provider downloads and the synthetic likelihood replays. A revised provider file fails the exact historical hash check; it is never silently substituted. Read each execution record for whether it reconstructs a cohort, refits a model, or recomputes a score.

## Historical follow-up study map

Current metadata identifies an open research edition and completed production checks. Historical internal reviews retain their original names and artifact hashes.

| Stream | Evidence in this edition | Interpretation and validation boundary |
|---|---|---|
| S01 / F | **Withdrawn from the current paper**; [historical internal review](validation/acceptances/S01_ACCEPTANCE.json) retained | Required original restricted-fit states could not be recovered. See the [withdrawal and archived sources](docs/F_followup.md). Earlier non-F results remain a separate supported study. |
| S02 | Matched and misspecified candidates on the paired forest bank; [acceptance](validation/acceptances/S02_ACCEPTANCE.json) | Same-bank threshold exceedances do not establish independent size control. |
| S03 | Four spatial arms across California and New Zealand; [acceptance](validation/acceptances/S03_ACCEPTANCE.json), [frozen-contract review](validation/acceptances/S03_FROZEN_CONTRACT_REVIEW.json) | Fitted-procedure contrasts are not a causal decomposition. New Zealand remains adaptively reused; training-only EP preparation is separately disclosed. |
| S04 | Expanded synthetic matrix and three observed California folds; [synthetic acceptance](validation/acceptances/S04_SYNTHETIC_ACCEPTANCE.json), [observed review](validation/acceptances/S04_OBSERVED_REVIEW.json) | Fixed-backbone comparisons; original unit-mark control law. Sampled numerical checks do not establish global optimization. Negative outcomes remain part of the evidence. |
| S04B | Matched LI+ generating controls; [historical acceptance](validation/acceptances/S04B_MATCHED_ACCEPTANCE.json), [complete saved-state replay](validation/reproductions/s04b_completed_replay_20261105.json), and [completed refitted-floor control](validation/live_results/methodological_20261106/refitted_floor_summary.json) | Original fits and gates remain fixed in the new comparator sensitivity. Thinning and all selected-vector diagnostics are supplied; active selection does not imply parameter recovery. Per-regime denominators and the stated synthetic interval/MC SE scopes remain operative. |
| S05 | All 2,997 EP futures; point-score reconstruction on all 5,994 OC/EP paths; fifteen full 84-coordinate EP replays; [closure review](validation/acceptances/S05_CLOSURE_REVIEW.json), [point review](validation/acceptances/S05_ALL_PATH_POINT_REVIEW.json) | Fixed-state conditional inference. Full PIT coverage is fifteen EP paths, not every future; no inferred CSEP L/M/S results. |
| S06 | California episode backtests and Japanese stationary/trend ablation; [acceptance](validation/acceptances/S06_ACCEPTANCE.json) | Retrospective roster, overlapping training, and saved-row validation do not establish prospective independent replication. |

The historical S04B integration and editorial-remediation reviews certify their original document bytes. The [current production review](validation/reviews/METHODOLOGICAL_EDITION_20261106.json) identifies the delivered manuscript, companion and site. It records internal artifact checks; the separately linked execution records describe numerical work. The [preceding reassessment review](validation/reviews/REASSESSMENT_CLARIFICATIONS_20261106.json) retains its earlier artifact identities. None of these records represents external academic acceptance.

Read each acceptance receipt for its actual roster, source identities, checks, and limits. Some historical references identify original research inputs outside this publication package. Accepted aggregate evidence is distinct from an independently reproducible raw experiment. Computational-agent review is distinct from independent external academic peer review.

## Trace a displayed value

The manuscript ledger `validation/MASTER_CLAIM_LEDGER.json` binds enumerated manuscript values and typed documentary metadata to bundled authorities. `validation/SOURCE_INVENTORY.json` retains additional numerical source inventory separately. The default verifier checks both. The [authority index](validation/authority_manifest.json) routes original identities to current bundled sources; documentary locators and explicit transformations explain the binding.

These checks establish declared source custody and numerical/display reconciliation. They do not prove that every manuscript claim was enumerated, every theorem is correct, or every raw numerical calculation was independently replayed. The [canonical reconciliation receipt](validation/numeric_reconciliation_receipt.json) and [current check record](validation/checks.json) have separate roles from scientific acceptance and visual artifact review.

The [historical archive index](provenance/historical_archive.json) identifies retired preparation/release/control records at their pinned baseline. The preserved [v4 source index](provenance/historical_v4_source_index.json) describes an earlier archive, rather than current checkout membership. `MANIFEST.json` identifies current payload bytes.

## Verify a checkout

After installing `requirements.txt`, run:

```sh
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s reproduction/regional/tests -v
python -B reproduction/regional/inputs.py verify
python -B -m unittest discover -s reproduction/s02 -p test_inputs.py -v
python -B reproduction/s02/inputs.py verify
python -B reproduction/historical_fits/verify.py
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m unittest discover -s engine/iteration_27/tests -v
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
node website/check_interactions.cjs
```

The main suite now includes recovered-input reconstruction, corruption rejection and replay checks. The [current check record](validation/checks.json) records the executed count separately for the main suite, the eight Stage 2 tests and the twenty iteration-27 tests. See the [test prerequisites and native setup](validation/README.md#check-a-checkout), including the separate CUDA requirement. Without native fixtures, Stage 2 passes five tests and skips three.

The website check needs Node.js; CI uses Node 22. To compile and inspect the current monograph with Tectonic 0.17.0:

```sh
python -B scripts/build_paper.py --output build/reviewer_paper
python -B scripts/validate_pdf.py --source-root paper --pdf build/reviewer_paper/main.pdf --log build/reviewer_paper/main.log --output build/reviewer_pdf_qa
```

Use fresh output directories. The build does not install its PDF by default, and automated production checks do not replace visual inspection. The [reproduction guide](docs/reproducibility.md) explains builds, promotion, and explicit research workloads. The [data guide](docs/data.md) and [Stage 2 support matrix](engine/stage2_followup/README.md) describe external inputs and execution limits. The recovered-input packages supply the regional source records, stated synthetic banks and available fitted states. Their guides distinguish original completed fits, later score replays and the explicitly withdrawn F continuation. Document rebuilding alone does not execute those scientific calculations.
