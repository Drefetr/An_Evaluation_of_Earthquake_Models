# Public source and availability guide

Use the current [README](../README.md) and [reviewer guide](../REVIEWER_START_HERE.md) to navigate the unified edition. Manuscript source-supplement links route to Appendix A. Historical S/M identifiers and digests identify original authorities; they are not promises that every original file is included.

## Current review entry points

| Need | Public target | Scope |
|---|---|---|
| Mathematical arguments | [Monograph](../paper/manuscript_unified.pdf), [explanatory supplement](../paper/supplements/explanatory_supplement.pdf) | Stated proofs and explanatory steps; retain assumptions and limitations |
| Numerical modules | [Code guide](code.md), [Stage 2 support matrix](../engine/stage2_followup/README.md) | Preserved APIs and study-specific components; source availability differs from full replay support |
| Restricted likelihood | [Historical implementation](../engine/iteration_20/code/restricted_history.py) | Included numerical source |
| Frozen observed procedure | [Implementation](../engine/iteration_27/code/adequacy.py), [public protocol](../engine/iteration_27/configs/observed_frozen.json) | Source-bound implementation and declared operational adaptation; exact external CSV still required |
| Catalogue identity and access | [Data guide](data.md), [GeoNet metadata](../provenance/catalogue_snapshot_metadata.json) | Snapshot/selection metadata, provider access, and explicit input limits |
| Current displayed values | [Manuscript ledger](../validation/MASTER_CLAIM_LEDGER.json), [authority index](../validation/authority_manifest.json) | Enumerated bindings and source identities, not an exhaustive correctness certificate |
| Additional numerical provenance | [Source inventory](../validation/SOURCE_INVENTORY.json) | Inventory roles kept separate from manuscript claims |
| Scientific validation scope | [Study acceptances](../validation/acceptances/), [validation guide](../validation/README.md) | Declared numerical/visual rosters and current bounded checks |
| Earlier preparation records | [Historical archive index](../provenance/historical_archive.json) | Pinned baseline identities, rather than active release-control state |

## Historical S/M availability register

[source_availability.json](../paper/supplements/source_availability.json) records the historical S/M source register and public extraction mappings. The unchanged [v4 source index](../provenance/historical_v4_source_index.json) preserves the earlier archive's original paths and pins. These historical identifiers are separate from the later Stage 2 study labels S01–S06; they must not be used interchangeably.

Historical register entries labelled not distributed describe the original full file, even where selected aggregate fields or a later source representation are bundled elsewhere. In particular, a source hash or archival included_path does not by itself make the file a current public asset. S18 is a declared operational adaptation and S24 is a metadata extract. Current repository membership is recorded by `MANIFEST.json`; the current authority index routes the bundled evidence.

Useful retained summaries include [detection](../paper/data/detection.json), [pairing](../paper/data/paired.json), [prediction](../paper/data/prediction.json), [selected predictive parameters](../paper/supplements/predictive_parameters.json), and [temporal decomposition](../paper/data/temporal.json). They are saved result summaries and selected fields, not complete synthetic/reference banks, fitted-state lineage, or new history evaluations.

## F continuation and completed recovery

The [dated F addendum](../paper/supplements/f_nuisance_addendum.pdf) records the earlier incomplete checkpoint. The [current scope note](F_followup.md) and [completed S01 chapter](../paper/source/chapters/07_s01_completed.tex) describe the later missing-only recovery, resolved outcomes, and paired summaries. Historical fixed-eta results and continuation procedures remain distinct recipes.

A standalone editable F addendum and saved-output replay directory are not included. Current editable presentation and declared source bindings are in the monograph sources and ledgers. Raw history banks, catalogue rows, full bootstrap chunks, private fitted vectors, and operational investigation archives remain outside this publication package.
