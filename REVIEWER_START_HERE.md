# Reviewer guide

Start with the [current unified monograph](paper/manuscript_unified.pdf), its [limitations](docs/limitations.md), and the study map below. This edition distinguishes completed Stage 2 results, the S04B matched-law controls, and earlier historical checkpoints. Earlier PDFs remain available for comparison; their production receipts and unresolved counts do not describe the current edition by implication.

The [plain-language guide](companion/lay_guide_to_the_research.pdf) introduces the studies without equations. The [findings explorer files](website/site/findings.html) use accepted aggregates and retain separate study populations; use the [website instructions](website/README.md) to preview the site.

## Scientific completion map

| Stream | Evidence in this edition | Interpretation and validation boundary |
|---|---|---|
| S01 | Missing-only fit recovery, all profile meshes, paired interaction and bootstrap summaries; [acceptance](validation/acceptances/S01_ACCEPTANCE.json) | Oracle calibration is retained. Recovery does not uniformly refit every bank member or provide a fitted-null nested bootstrap. See the [F checkpoint/completion note](docs/F_followup.md). |
| S02 | Matched and misspecified candidates on the paired forest bank; [acceptance](validation/acceptances/S02_ACCEPTANCE.json) | Same-bank threshold exceedances do not establish independent size control. |
| S03 | Four spatial arms across California and New Zealand; [acceptance](validation/acceptances/S03_ACCEPTANCE.json), [frozen-contract review](validation/acceptances/S03_FROZEN_CONTRACT_REVIEW.json) | Fitted-procedure contrasts are not a causal decomposition. New Zealand remains adaptively reused; training-only EP preparation is separately disclosed. |
| S04 | Expanded synthetic matrix and three observed California folds; [synthetic acceptance](validation/acceptances/S04_SYNTHETIC_ACCEPTANCE.json), [observed review](validation/acceptances/S04_OBSERVED_REVIEW.json) | Fixed-backbone comparisons; original unit-mark control law. Sampled numerical checks do not establish global optimization. Negative outcomes remain part of the evidence. |
| S04B | Matched LI+ immigrant and total generating controls; [acceptance](validation/acceptances/S04B_MATCHED_ACCEPTANCE.json), [publication review](validation/acceptances/S04B_PUBLICATION_REVIEW.json), [visual review](validation/acceptances/S04B_VISUAL_REVIEW.json) | Per-regime history denominators and descriptive Monte Carlo SE, with fixed nuisance backbone. No general recovery, nominal-size, prospective, or physical-identification claim. |
| S05 | All 2,997 EP futures; point-score reconstruction on all 5,994 OC/EP paths; fifteen full 84-coordinate EP replays; [closure review](validation/acceptances/S05_CLOSURE_REVIEW.json), [point review](validation/acceptances/S05_ALL_PATH_POINT_REVIEW.json) | Fixed-state conditional inference. Full PIT coverage is fifteen EP paths, not every future; no inferred CSEP L/M/S results. |
| S06 | California episode backtests and Japanese stationary/trend ablation; [acceptance](validation/acceptances/S06_ACCEPTANCE.json) | Retrospective roster, overlapping training, and saved-row validation do not establish prospective independent replication. |

Read each acceptance receipt for its actual roster, source identities, checks, and limits. Some historical references identify original research inputs outside this publication package. Accepted aggregate evidence is distinct from an independently reproducible raw experiment. Computational-agent review is distinct from independent external academic peer review.

## Trace a displayed value

The manuscript ledger `validation/MASTER_CLAIM_LEDGER.json` binds enumerated manuscript values and typed documentary metadata to bundled authorities. `validation/SOURCE_INVENTORY.json` retains additional numerical source inventory separately. The default verifier checks both. The [authority index](validation/authority_manifest.json) routes original identities to current bundled sources; documentary locators and explicit transformations explain the binding.

These checks establish declared source custody and numerical/display reconciliation. They do not prove that every manuscript claim was enumerated, every theorem is correct, or every raw numerical calculation was independently replayed. The [canonical reconciliation receipt](validation/numeric_reconciliation_receipt.json) and [current check record](validation/checks.json) have separate roles from scientific acceptance and visual artifact review.

The [historical archive index](provenance/historical_archive.json) identifies retired preparation/release/control records at their pinned baseline. The preserved [v4 source index](provenance/historical_v4_source_index.json) describes an earlier archive, rather than current checkout membership. `MANIFEST.json` identifies current payload bytes.

## Verify a checkout

After installing `requirements.txt`, run:

```sh
python -B -m unittest discover -s tests -v
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
node website/check_interactions.cjs
```

The website check needs Node.js; CI uses Node 22. To compile and inspect the current monograph with Tectonic 0.17.0:

```sh
python -B scripts/build_paper.py --output build/reviewer_paper
python -B scripts/validate_pdf.py --source-root paper --pdf build/reviewer_paper/main.pdf --log build/reviewer_paper/main.log --output build/reviewer_pdf_qa
```

Use fresh output directories. The build does not install its PDF by default, and automated production checks do not replace visual inspection. The [reproduction guide](docs/reproducibility.md) explains builds, promotion, and explicit research workloads. The [data guide](docs/data.md) and [Stage 2 support matrix](engine/stage2_followup/README.md) describe external inputs and execution limits. Catalogue rows, complete histories, fitted vectors, and caches are not supplied; document rebuilding is not numerical study replay.
