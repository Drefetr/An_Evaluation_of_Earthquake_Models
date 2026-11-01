# Validation and evidence

This directory separates current manuscript bindings, additional numerical source inventory, scientific acceptance evidence, and bounded check results. Historical preparation/release receipts are indexed in [provenance/historical_archive.json](../provenance/historical_archive.json); their original hashes and baseline locations remain available without presenting them as current validation.

## What each record establishes

| Record | Role |
|---|---|
| `MASTER_CLAIM_LEDGER.json` | Enumerated manuscript bindings and typed documentary metadata, with explicit source hashes, locators, and transformations |
| `SOURCE_INVENTORY.json` | Additional numerical source inventory, kept separate from claims of manuscript support |
| `authorities/`, `authority_manifest.json` | Bundled scientific sources and their historical/public identities |
| `acceptances/` | Study-specific scientific and artifact reviews; read each receipt's validation coverage and limitations |
| `numeric_reconciliation_receipt.json` | Canonical claim/source reconciliation receipt; default verification checks bindings without rewriting it |
| `checks.json` | Actual current bounded check coverage and results, with the recorded snapshot and execution scope |

The default verifier checks both ledgers. Source inventory records are not automatically manuscript claims. A verified hash establishes source identity, while numerical reconciliation checks declared values/transformations. Neither establishes exhaustive theorem correctness, completeness of all manuscript claims, causal identification, or independent raw replay of every experiment.

## Check a checkout

From the repository root after installing `requirements.txt` and Node.js 22 (also used by the workflow tests):

```sh
python -B -m unittest discover -s tests -v
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
node website/check_interactions.cjs
```

Node.js is required for the last command. [Reproduction instructions](../docs/reproducibility.md) distinguish these checks from document builds and scientific workloads. Generated PDF production checks still need visual inspection. Stage 2 import/build fixtures cover only the supported components identified in the [support matrix](../engine/stage2_followup/README.md).

## Historical receipts and source changes

October baseline receipts described earlier manuscript/supplement editions and a smaller test suite. Final-release build receipts describe their original compiler, source, and PDF bindings. They are historical evidence rather than a fresh check of the current tree. Earlier privacy scans likewise do not cover later additions by implication.

Publication variants, path migration, or deduplication can change public source bytes without changing scientific values. Preserve original identities and record the transformed bytes, then update dependent ledger hashes, documentary locators, authority mappings, site/companion bindings, and receipts together. Current repository membership is authoritative in `MANIFEST.json`; historical archive indexes and source inventories have different scopes.

Event records, full simulation/reference banks, private fitted vectors, and execution caches remain external inputs. Scientific acceptance, source reconciliation, document production, and external academic peer review are separate forms of evidence.
