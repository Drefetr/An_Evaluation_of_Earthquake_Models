# Slice 7 Audit — Cross-Slice Synthesis, Contrast-Specific MDE Table, Reader Surfaces, and Custody

**Baseline:** `102a78a` (Slice 6 acceptance; `validation/slice6_remediation_20261114.json`)  
**Audit package:** `validation/live_results/slice7_audit_20261114/`  
**Acceptance record:** `validation/slice7_remediation_20261114.json`  
**Pre-change snapshot:** `validation/slice7_prechange_snapshot_20261114.json` / `.zip`  
**Verdict:** accepted with documented repairs; **782/782** pre-existing sealed JSON files byte-for-byte unchanged.

## 1. Scope

This slice closes the seven-part vertical-triad audit over the manuscript synthesis and custody surfaces:

- `paper/source/abstract.tex`, `01_introduction.tex`, `14_discussion_conclusion.tex`, `14_power_and_mde.tex`, `appendices.tex`;
- `README.md`, `REVIEWER_START_HERE.md`, `companion/guide_content.json`, `website/document_metadata.json`, `website/findings.html`;
- the rebuilt companion, website and review-slice bundles;
- `validation/MASTER_CLAIM_LEDGER.json`, `validation/numeric_reconciliation_receipt.json`, `scripts/verify_claims.py` and `scripts/verify_repository.py`.

The audit re-derives every MDE table cell from `mde_expanded.json`, `nz_trend_controls.json` and `japan_mde.json`; checks 92 canonical synthesis values and 312 enumerated manuscript claims across the five target LaTeX sources; checks the reader surfaces against the rebuilt PDF and website; and runs the adversarial verifier test bank. It does not re-run the original regional fits or synthetic campaigns.

## 2. Confirmed defects and repairs

### 2.1 New Zealand MDE row split

The single free-trend New Zealand row carried the free-, zero- and fixed-null-trend observed totals while displaying only the free-trend block scale. This made `−11.431` and `−5.006` nats appear to be judged against the 9.24-nat free-trend MDE, contradicting the repaired prose and the own-contrast table in Chapter 8.

`Table tab:mde` now has three explicit New Zealand rows:

| Trend arm | Observed | 90 d SE / MDE / per-event MDE | 180 d | 365 d |
|---|---:|---:|---:|---:|
| Free $d$ | −17.623 | 4.71 / 9.24 / 0.0151 | 5.42 / 10.62 / 0.0174 | 6.65 / 13.04 / 0.0213 |
| Zero $d$ | −11.431 | 2.76 / 5.42 / 0.0089 | 2.79 / 5.47 / 0.0089 | 2.99 / 5.87 / 0.0096 |
| Fixed null $d$ | −5.006 | 1.40 / 2.74 / 0.0045 | 1.42 / 2.79 / 0.0046 | 1.55 / 3.04 / 0.0050 |

The caption now states that the three rows share the 612 test events but not the block scale, and that the fixed-null loss must not be compared with the free-trend MDE. It also discloses that cells are rounded independently from the unrounded block quantities.

### 2.2 Inverted attenuation-MDE comparison

The old sentence said the completed EP+ gain is of the same order as its own MDE, “not the much larger attenuation MDE.” The 90-day EP+ MDE is **48.30** nats, while the California LI+ total-attenuation MDE is **3.82** nats. The attenuation MDE is therefore much smaller, not larger. The repaired sentence compares the EP+ gain with its own 48.30-nat MDE and the −2.39-nat LI+ contrast with its own 3.82-nat MDE.

### 2.3 SE/event versus MDE/event ambiguity

The old text presented `0.0077` and `0.0782` nat per event without identifying them. They are the 90-day block standard errors per event:

- `0.0077 = 4.712 / 612`;
- `0.0782 = 24.644 / 315`.

The corresponding per-event MDEs are `1.96 ×` those values: `0.0151` and `0.1533` nats/event, as printed in the final table column. The text now says this explicitly. It also now covers every contrast in the table: the California LI+ total deltas are 15.6/15.5/15.5%, and the California OC−EP deltas are 52.5/52.3/51.7%, in addition to the New Zealand, EP+, and Japan values.

### 2.4 Additional one-decimal corrections found by the audit

Independent recomputation of `δ = sqrt(2 MDE95 / Ntest)` found two pre-existing one-decimal display errors in the same sentence:

- zero-trend 365-day delta: `13.8496%` displays as **13.8%**, not 13.9%;
- fixed-null 180-day delta: `9.5411%` displays as **9.5%**, not 9.6%.

The values are corrected. These displays were not previously claimed in the ledger, so no historical claim was rewritten.

### 2.5 Reader-facing stale phrase and cross-surface synchronization

`README.md` and `website/findings.html` still said the New Zealand fixed-null loss was “below the 9.24-nat 90-day scale.” That is the pre-F1 comparison the manuscript withdrew. Both now state that −5.01 nats is **1.83 times its own 2.74-nat 90-day MDE** and **3.59 of its own block standard error**, with the zero-trend arm's 5.42-nat MDE also identified. `companion/guide_content.json` now lists all three New Zealand trend-arm scales; `website/document_metadata.json` records the rebuilt 253-page PDF and the split-row release note; the generated `website/site/findings.html` carries the same corrected notice.

### 2.6 Website title encoding

`website/document_metadata.json` stored the monograph title as `Spatialâ€“Temporal` (UTF-8 bytes for an en dash interpreted as Latin-1) rather than `Spatial–Temporal`. The corrupted title propagated to `website/site/index.html` and `website/site/documents.json`. The metadata title is now the correct en-dash form, the site was rebuilt, and the audit checks the title in metadata, the generated document inventory and the generated home page.

### 2.7 Additive claim bindings

The split rows and expanded perturbation sentence added 26 displays that were not enumerated claims. `scripts/bind_slice7_claims_20261114.py` appends deterministic bindings (`slice7-20261114-001` … `-026`) to `nz_trend_controls.json` and `mde_expanded.json`, including the abstract locations for the 5.42- and 2.74-nat MDEs. `scripts/verify_claims.py --write-receipts` then refreshed the compact display custody. No sealed authority was edited.

## 3. MDE-table arithmetic audit

`validation/live_results/slice7_audit_20261114/mde_table.json` records 21 block rows in 9 contrast groups:

- New Zealand free $d$, zero $d$, fixed null $d$ (3 × 3 blocks);
- California LI+ total, EP+ − EP, OC − EP (3 × 3 blocks);
- Japan OC − EP per three-year fold, three-fold sum, nine annual blocks (3 rows).

For every row the audit independently checks:

- the displayed `SE_B` against the bound block authority;
- `MDE95 = 1.96 SE_B` from the unrounded SE;
- `MDE95 / Ntest` from the unrounded MDE;
- the observed-total display;
- the fractional perturbation `delta = sqrt(2 MDE95 / Ntest)` for all nine 90-day (or Japan total) rows.

Additional identities:

- Japan three-fold sum: `3 × 8.15251 = 24.45753` nats;
- Japan annual blocks: `1.96 × 28.8298757 = 56.50656` nats;
- EP+ observed displays: `+69.551` bound-pinned and `+77.056` interior.

All 21 rows, all 9 delta recomputations and all 7 prose delta triplets pass. The audit also confirms that the superseded `13.9%` zero-trend and `9.6%` fixed-null displays are absent.

## 4. Cross-slice synthesis audit

`validation/live_results/slice7_audit_20261114/synthesis_consistency.json` checks 92 canonical values against the bound authorities, including:

- **Slice 1:** one-event clipped bounds `1.53 × 10^-3`, `0.00423`, `0.1867`, `0.7884`, and threshold `4.64`; 195-mode certificate quantities.
- **Slice 3:** New Zealand totals `17.62`, `11.43`, `5.01`; Fold-1 values `16.52`, `8.50`, `4.56`; own-contrast SEs/MDEs `1.396/2.735`, `2.786/3.038`, `2.764/5.417`; z-scores `−3.59`, `−4.14`.
- **Slice 4:** California LI+ `3.82`, EP+ `48.30`, OC−EP `43.35`, Japan `47.94` and `15.98`.
- **Slice 5:** EP+ `69.55`, Shapley closure `69.551`, contributions `31.67`, `27.60`, `10.24`, `0.04`; relaxed totals `77.06`, `78.58`, `78.52`; interior scales `0.82–0.84 km`.
- **Slice 6:** S8 fixed-null `16.43`, intercept `14.54`, joint-null `18.11` (MCSE `4.18`), overfitting sign `3.571`, seed-410840 `75.278`, partial oracles `3.13`, `2.824`, `6.513`, fitted eta `0.929` and range `0.042–4.000`, estimation-loss fraction `98.4%`.
- **Slice 7:** all nine contrast MDEs and the split-row values.

The audit also confirms that no target source contains the withdrawn `0.10424` tightening, the old `12.2504` threshold, the phrase “below the 9.24”, or the inverted “much larger attenuation” claim. Every one of the 312 enumerated manuscript bindings on the five target sources is present; the per-file counts are 130 (abstract), 33 (Chapter 1), 71 (Chapter 14), 87 (MDE subsection) and 31 (appendices).

## 5. Reader surfaces

`reader_surfaces.json` passes all 16 checks:

| Surface | Result |
|---|---|
| `README.md` | Own-contrast 2.74-nat and 5.42-nat language present; stale 9.24 phrase absent. |
| `REVIEWER_START_HERE.md` | Records the completed Slice 1–7 audits and the Slice 7 synthesis/custody scope. |
| `companion/guide_content.json` | Lists 9.24, 5.42 and 2.74 nats for the three New Zealand arms; no stale phrase. |
| `website/document_metadata.json` | SHA-256 and 253-page count match the installed PDF; release note names the split rows. |
| `website/findings.html` | Own-contrast MDE language present; stale phrase absent. |
| `website/site/findings.html` | Generated page matches the corrected source; no stale phrase. |
| `website/site/findings-data.json` | Present and consistent with the generated site bundle. |
| Website title encoding | Metadata, `documents.json` and `index.html` carry `Spatial–Temporal`, not the former `Spatialâ€“Temporal` mojibake. |

## 6. Custody and verifier audit

`custody_infrastructure.json` records:

- **42** compiled `.tex` files in `paper/source/`, all present in both `MASTER_CLAIM_LEDGER.json`'s `display_custody.source_hashes` and `numeric_reconciliation_receipt.json`'s `source_hashes`, with current byte hashes.
- **13,592** claims and **679** documentary metadata records in the master ledger; **28,653** total claim records after the separate source inventory; **12,744** literal manuscript display records; **172** distinct authorities; zero missing declared displays.
- **60** adversarial verifier tests pass (`tests/test_verify_claims.py`), including truncation, column-selection, duplicate-ID, stale-hash, compact-custody and withdrawal-roster cases.
- Repository source pins and authority bindings pass; manifest membership covers the payload (the six audit outputs are written after the coverage check and are covered by the final manifest refresh).
- **782/782** pre-existing sealed JSON files unchanged; the snapshot ZIP contains the snapshot JSON byte-for-byte and every recorded pre-change publication member.

## 7. Build and check results

| Check | Result |
|---|---|
| `scripts/check_mathematics.py` | exit 0; deterministic algebra and visibility checks pass |
| Paper build | Tectonic 0.17.0, exit 0, **253 pages** |
| PDF QA | passed; 0 overfull boxes, 0 overfull vertical boxes, 0 undefined references, 0 missing citations, 0 missing figures, 0 missing glyphs, 0 replacement characters, 25 underfull boxes |
| Companion build | exit 0; 12-page guide installed |
| Website build | exit 0; generated bundle installed |
| `verify_claims.py` | passed and release-ready |
| Main unit suite | **918 tests, OK** |
| Regional suite | **44 tests, OK** |
| S02 suite | **6 tests, OK** |
| Regional inputs | passed (6,110 members; 15,093 crosswalk records) |
| S02 inputs | passed (300 histories; 600 methods) |
| Historical fits | passed (2,824- and 37-member archives) |
| Website interactions | passed (80 selector combinations) |
| `verify_repository.py` | passed after final manifest refresh |
| Review slices | 7 bundles regenerated; Slice 7 is 36 PDF pages / 19 files, 401,277 ZIP bytes |

The page count increased from 252 to 253 because the expanded New Zealand block moved the conclusion and appendix by one page. The review-slice page ranges were shifted accordingly (Slice 1 appendix/bibliography, Slices 2–4 appendix ranges, and Slice 7 pp. 187–203).

## 8. Limitations

- The 90/180/365-day blocks are paired calendar-block summaries; adjacent blocks are dependent. The MDEs are descriptive dependence-scale sensitivities, not calibrated frequentist guarantees.
- Table cells are rounded independently from the unrounded block quantities, so a displayed rounded SE times 1.96 can differ from the displayed MDE in the last digit. The caption discloses this.
- The audit verifies the enumerated claims and a curated canonical set; it does not re-run the original regional fits or synthetic campaigns.
- The withdrawn tightened Pinsker display remains documented in `validation/live_results/slice1_math_audit_20261114/visibility_correction.json` for historical identity, but is absent from all reader-facing surfaces.
- Internal computational and artifact audits are not independent external academic peer review.

## 9. Artifacts

- Audit script: `experiments/methodological_audit/slice7_audit_20261114.py`
- Audit outputs: `validation/live_results/slice7_audit_20261114/` (`mde_table.json`, `synthesis_consistency.json`, `reader_surfaces.json`, `custody_infrastructure.json`, `sealed_authority_integrity.json`, `summary.json`)
- Ledger binding script: `scripts/bind_slice7_claims_20261114.py`
- Snapshot script: `scripts/snapshot_slice7_prechange_20261114.py`
- Acceptance builder: `scripts/build_slice7_acceptance_20261114.py`
- Rebuilt manuscript: `paper/manuscript_unified.pdf` (253 pages)
- Rebuilt companion and website: `companion/`, `website/site/`
- Regenerated review slices: `../review_slices/` (7 bundles)
