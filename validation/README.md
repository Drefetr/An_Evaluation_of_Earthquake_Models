# Validation and evidence

Current production and test coverage are recorded in [Track A acceptance](track_a_remediation_20261112.json). The [preceding completed reassessment](reassessment_20261112.json) remains an exact record of its own edition. November 7–8 production reviews identify historical PDF, guide and site bytes and must not be treated as current checks.

This repository evaluates diagnostic exponential rate attenuation in specified point-process models. It does not validate a directional Coulomb stress or rate-and-state model. Internal independent computational audits and saved-output artifact audits have separately stated coverage; they are not independent external academic peer review.

## What each record establishes

| Record | Role |
|---|---|
| `MASTER_CLAIM_LEDGER.json` | Enumerated manuscript values and documentary metadata, with source hashes, locators, transformations and display custody |
| `SOURCE_INVENTORY.json` | Additional numerical source inventory, separate from literal manuscript support |
| `authority_manifest.json`, `authorities/` | Bundled historical scientific authorities and their original/public identities |
| `live_results/s04b_joint_complete_20261111/summary.json` | Complete 80-history/400-outcome joint temporal-backbone comparison |
| `live_results/s04b_joint_complete_independent_audit_20261111.json` | Independent computational audit of source custody, complete arithmetic and the original presentation |
| `live_results/track_a_supplement_20261112/` | Additive sample Monte Carlo errors, explicit train/test event counts and verified presentation over unchanged scientific outcomes |
| `live_results/s04b_concave_20261111/`, `live_results/reporting_supplement_20261112/` | Training-only concave comparator; derived raw/BIC, boundary and win-column reporting |
| `live_results/s8_moderate_complete_20261111/` | Complete moderate synthetic campaign, with its distinct declared numerical rule |
| `live_results/etas_inhibition_benchmark_interior_20261112/` | Corrected final ETAS acceptance with positive-strength interior starts and its source-bound baseline comparison |
| `live_results/score_uncertainty_remote_v2_20261111/` | Accepted paired block contributions/resampling, distinct from rejected calendar-mapping predecessors |
| `reproductions/`, `remote_runs/` | Executed reconstructions, fresh fits, saved-state replays and runtime/source identities, each with its own scope |
| `acceptances/`, `reviews/` | Dated internal scientific-computation and artifact records; names do not imply journal acceptance |
| `numeric_reconciliation_receipt.json`, `manuscript_display_regression.json` | Current enumerated claim, source and display reconciliation |
| `checks.json` and `checks_before_*.json` | Differently scoped historical test executions, not a substitute for the current Track A roster |
| `track_a_prechange_snapshot_20261112.json`, `withdrawals/` | Preserved pre-edit artifacts, sealed-result identities and explicit historical claim withdrawals |

The [reviewer guide](../REVIEWER_START_HERE.md) maps every current study to its entry point. The old [78-history disposition report](live_results/joint_nuisance_dispositions_20261107/report.json) is a historical checkpoint, not the current 80-history result. Existing sealed scientific JSON, original protocol identities and source epochs are preserved; presentation changes have additive derived supplements and new reviews.

## Source identity is not scientific verification

The default verifier checks both ledgers. A source hash establishes identity; arithmetic checks establish the declared numerical transformation; display custody establishes the enumerated occurrence in the compiled LaTeX input tree. These checks do not establish semantic completeness, theorem correctness, causal identification, calibrated statistical testing or replay of every raw calculation.

Withdrawn claims retain their original records and authority checks but no longer count as current displays. A missing display cannot be silently withdrawn by refreshing a receipt. Current display-source changes require deliberate review and explicit `scripts/verify_claims.py --write-receipts`; ordinary verification is read-only.

Fresh scientific execution, saved-state likelihood replay, saved-output artifact audit and document production are different activities. The [provenance map](../docs/result_provenance.md) and [selected-state replay coverage](reproductions/score_replay_20261107/final_coverage/independent_review.json) distinguish them. Original historical optimizer searches were not repeated by the later score-replay campaign.

The observed 90-, 180- and 365-day block summaries hold fitted states fixed. Long-memory dependence and exchangeability conditions are not established by their implementation checks. Intervals are descriptive sensitivity summaries; nominal sign-flip references are not calibrated significance tests. Compare all block lengths, fold consistency and score components. A training-selected zero attenuation state gives exactly zero held-out contrast by nesting; it is not a power or physical-absence test.

## Check a checkout

From the repository root after installing `requirements.txt` and Node.js 22:

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

The current Track B record reports actual command exit codes, test counts, control outputs and artifact identities; the Track A record remains the editorial/statistical baseline. Counts from separate suites are not the count of the main command alone. These bounded checks do not launch the full research campaigns. In the thesis handoff workspace, intensive fitting, simulation and large likelihood contractions must use the configured remote host under `AGENTS.md`; credentials remain outside repository payloads.

Optional Stage 2 tests automatically build their native fixtures when no native root is configured. A GNU/Clang C++17 compiler is supported on Linux and MSVC on Windows; a missing compiler is an error rather than a silent skip. An explicit `INHIBITORY_TEST_NATIVE_ROOT` reuses supplied libraries. See [native-build instructions](../engine/stage2_followup/README.md#native-builds).

```powershell
$env:INHIBITORY_TEST_NATIVE_ROOT = (Resolve-Path build/native).Path
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m unittest discover -s engine/iteration_27/tests -v
```

The historical iteration-27 GPU assertion requires a separate CUDA-enabled PyTorch installation and usable GPU, with no CPU fallback. The separately executed [Linux CPU route](../docs/cpu_reproduction.md) and its [fresh-checkout computational audit](reproductions/cpu_20261107/checkout02_independent_review.json) have a different roster. The [refined fit reader](../experiments/s04b_refined_cpu_reader/README.md) uses its bundled audited Linux library without a compiler; source review, constructed controls and acceptance of an actual fresh fit are distinct.

## Build and inspect documents

Use fresh output directories and do not install artifacts during a read-only review:

```sh
python -B scripts/make_figures.py --output build/reviewer_figures
python -B scripts/build_paper.py --output build/reviewer_paper
python -B scripts/validate_pdf.py --source-root paper --pdf build/reviewer_paper/main.pdf --log build/reviewer_paper/main.log --output build/reviewer_pdf_qa
python -B companion/build_guide.py --output build/reviewer_companion
python -B website/build_site.py --output build/reviewer_site
node website/check_interactions.cjs build/reviewer_site
```

Production checks need visual inspection of the final page images. Accepted PDF identities and page counts are promoted together with guide/site metadata only after review. A current presentation overlay may bind a new table to an unchanged scientific result; it must verify the old table's archived identity and the new derived numerical supplement without rewriting the old computational audit.

Historical receipts retain their original hashes, source paths, test coverage and unresolved states. They are not promoted to current validation by implication. `MANIFEST.json` identifies current repository membership; [historical archive indexes](../provenance/historical_archive.json) describe preserved earlier editions.
