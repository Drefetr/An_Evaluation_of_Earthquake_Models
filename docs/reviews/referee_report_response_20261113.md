# Referee report response: M1–M4, M7–M9 and Minor 1–7

**Date:** 13 November 2026  
**Baseline:** `dcf2559` (`validation/track_b_remediation_20261112.json`)  
**Pre-change snapshot:** `validation/referee_prechange_snapshot_20261113.json` (with `.zip` archive)  
**Primary outputs:** `validation/live_results/referee_remediation_20261113/`  
**Independent audit:** `validation/live_results/referee_remediation_20261113/independent_audit.json`  
**Acceptance record:** `validation/referee_remediation_20261113.json`

## Scope and custody

This response is additive. All 339 pre-existing sealed JSON files under
`validation/authorities/` and the six named live-result directories are
byte-identical to the pre-change snapshot. No new calculation rewrites a sealed
authority. The supplement contains four deterministic products and one summary:

| File | Contents |
|---|---|
| `mde_expanded.json` | five contrast-specific MDE rows at 90/180/365 days |
| `s8_oracle_decomposition.json` | partial oracles, estimation-loss closure, fitted-$\hat\eta$ census |
| `synthetic_quantiles.json` | exact Q25/Q50/Q75/IQR/min/max for the S04B, S8 and oracle tables |
| `nz_trend_totals.json` | exact three-fold New Zealand trend-control totals |
| `summary.json` | key results and input hashes |

The independent audit recomputes every derived scalar from the sealed
authorities, replays the partial-oracle held-out scores and checks the sealed
hash roster (588 checks, all passed).

## M2 — Contrast-specific MDEs

The former `Table tab:mde` labelled three rows only by region. It is replaced by
an expanded table that names the exact scored contrast. `CA_EPplus_minus_original_EP`
is now separated from `CA_LIplus_total_minus_floor` and `CA_OC_minus_EP`.

| Contrast | $N_{\rm test}$ | Observed $\Delta\ell$ | 90-day $\mathrm{SE}_B$ | 90-day $\mathrm{MDE}_{95}$ |
|---|---:|---:|---:|---:|
| NZ shared $-$ ML | 612 | $-17.623$ free $d$; $-11.431$ zero $d$; $-5.006$ fixed null $d$ | 4.712 | 9.236 |
| CA `LI+` total $-$ floor | 315 | $-2.387$ | 1.948 | 3.819 |
| CA `EP+` $-$ `EP` | 315 | $+69.553$ bound; $+77.056$ interior | 24.644 | 48.302 |
| CA `OC` $-$ `EP` | 315 | $-51.051$ | 22.116 | 43.347 |
| Japan `OC` $-$ `EP`, per fold | 1277 | $-73.737$ | 8.153 | 15.979 |
| Japan `OC` $-$ `EP`, 3-fold sum | 1277 | $-221.212$ | 24.458 | 47.938 |

The 48.30-nat value is therefore attached to `EP+` minus `EP`, not to California
attenuation generally. The California `LI+` total scale is 3.819 nats by the
repository's independent-block definition; the pooled percentile half-width is
3.265 nats, close to the referee's $\approx3.29$ and subject to the unstable 2.5%
bootstrap quantile. The Japan per-fold and 3-fold-sum entries are now both
reported. `block_inference_qualification` states that contiguous blocks are
dependent and that the Japanese entries are not calendar-block estimates.

## M4 and Minor 2 — Exact S8 oracle decomposition

The $+18.11$-nat contrast is now correctly described as the **full true
generating law $\theta_\star$ minus the jointly fitted five-parameter null
$\hat\theta_0(H_{\rm train})$**, not as an oracle that omits the nuisance
backbone. The decomposition is explicit:

| Quantity | Mean (nats) | Interpretation |
|---|---:|---|
| $\theta_\star$ vs fixed true-backbone $\theta_{\star,0}$ | 16.429 | exact generating attenuation effect |
| $\theta_\star$ vs intercept-refitted true backbone | 14.541 | backbone location held at truth |
| $\theta_\star$ vs jointly fitted $\hat\theta_0$ | 18.112 | actual comparator |
| $\ell(\hat a,\theta_{\star,0,-a})-\ell(\hat\theta_0)$ | 3.571 | comparator's own four-parameter estimation gain |
| $\ell(\theta_{\star,0})-\ell(\hat\theta_0)$ | 1.683 | direct null-backbone estimation loss |
| Partial oracle A: true $(\eta,\ell,\psi)$, fitted backbone, refit $a$ | 3.128 | isolates attenuation knowledge |
| Partial oracle B: refit $(a,d,n,c,p)$ at true attenuation | 2.576 | tests backbone estimation separately |

The identity $14.541+3.571=18.112$ closes exactly. The fitted $\hat\eta$ census
is mean 0.929, median 0.543, IQR $[0.264,0.984]$, min 0.042, max 4.000 and RMSE
1.230 against $\eta_\star=0.4$. Estimation loss of 17.818 nats is 98.4% of the
18.112-nat oracle advantage.

## M3 and Minor 7 — Three-fold New Zealand trend totals

The abstract and `08_nz_trend_controls.tex` now report the three-fold totals
alongside Fold 1:

| Control | Fold 1 $\Delta\ell$ | 3-fold $\Delta\ell$ |
|---|---:|---:|
| Free $d$ | $-16.518$ | $-17.623$ |
| Zero $d$ | $-8.504$ | $-11.431$ |
| Fixed null $d$ | $-4.556$ | $-5.006$ |
| Clamped clock (not a refit) | $-24.791$ | $-26.898$ |

The fixed-null three-fold residual is smaller than the 9.236-nat 90-day
$\mathrm{MDE}_{95}$ and the 10.619-nat 180-day value. The table now has a
`Pooled` block. The stored clamped records expose only the joint contrast, so the
manuscript cites the reproduced $-26.898$-nat joint total and the $-24.791$-nat
Fold-1 total; the Q/C split is not used as evidence.

## M1, M8, M9 and Minor 4–6 — Framing and non-Gaussian summaries

- The phrase “statistically detectable” is removed from `abstract.tex` and the
  conclusion. The abstract now states that none of the tested recipes improves
  held-out log score and that the three mechanisms responsible are background-trend
  collinearity with cumulative depletion, nested zero-attenuation selection and
  finite-sample estimation loss.
- Median and IQR columns are added to the S8 raw/BIC and oracle tables, and a new
  S04B quantile table (`tab:s04b-joint-quantiles`) reports Q25/Q75/IQR/min/max for
  all twenty rows. The captions state that null second moments diverge in the
  heavy-tailed mark regime, so medians and IQRs are primary and sample MCSEs are
  descriptive.
- The reused New Zealand observed-table captions are prefixed with “Exploratory
  chronological comparison on the adaptively reused 612-event archive”.
- The 12 algebraic-zero California boundary rows are partitioned into their own
  table, separate from the 3 active `LI+ total raw` rows.

## Minor 1, M7 and Minor 3 — Precision, range and unified EP+ presentation

- `0.82–0.85 km` is corrected to `0.82–0.84 km` (0.821–0.839 km) in the abstract,
  ablation chapter, discussion, README, reviewer guide, companion and website.
- The abstract introduces `EP+` once, with its Shapley decomposition
  (30.03 scaling, 29.22 declustering, 10.24 joint fitting, 0.06 normalization)
  and its interior-scale relaxation (77.06 redeclustered, 78.58 frozen, versus
  69.55 at the binding 2 km bound) in one place.
- Narrative floats in `08_observed_baseline.tex` are rounded to 3 decimal places
  (2.849, 2.494, 0.164, −17.623, −17.618, +0.005). Full precision remains in the
  bound JSON authorities.
- The 913/914-event agreement is stated to test query and export consistency only
  and to provide zero evidence of physical catalogue completeness.

## Verification

The independent audit passed 588 checks with zero failures. The monograph
compiles to 247 pages with 0 overfull boxes, 0 undefined references or citations
and 0 missing figures. The companion and site were rebuilt from the updated
content JSON. `MASTER_CLAIM_LEDGER.json` was refreshed with 22 additive bindings
and the superseded 0.85 km abstract display was removed.

## Residual limitations

These remain procedure-level results. Dependent calendar blocks, adaptive reuse
of the 612-event New Zealand archive and the single generating law of the S8 bank
limit what any of these summaries can establish. None of the controls converts a
non-significant or nested contrast into evidence of physical absence.
