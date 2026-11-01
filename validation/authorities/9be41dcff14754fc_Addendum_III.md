# Addendum III: temporal kernels, continuous locations and background geography

**Exploratory forecasting update | 25 October 2026 (Pacific/Auckland)**

## Abstract

A matched comparison of twelve earthquake forecasting models finds positive predictive evidence from continuous event locations and, within that representation, Omori temporal decay. The experiment reuses 612 historical targets across three chronological windows. A training-only kernel-density background reduces but does not remove the continuous-location advantage over a cell approximation: gains remain 2.326-2.369 nats per event across three temporal families. With that stronger background and continuous locations, Omori improves on fixed-scale Mittag-Leffler (ML) triggering by 15.474 joint-score nats, including 10.368 timing nats, with both components positive in every window. The fully combined procedure improves aggregate timing and location scores over its current matched coarse comparator; location prediction accounts for most of the gain. Negative temporal contrasts and losing 1-2 km sensitivity fits limit the interpretation. These are retrospective fitted-procedure comparisons, not independent confirmation, identification of physical triggering, or evidence for inhibition.

## 1. What this update changes

Addendum II reported negative exploratory results from shared-kernel magnitude-class history and free productivity estimation. The present addendum concerns a different question: whether temporal decay and finer spatial representation improve forecasts after a more flexible background geography is supplied. It does not reverse Addendum II's matched results or the original manuscript's restricted theoretical and inhibition conclusions. It also supplies none of the first background-nuisance companion's unresolved null outcomes and does not complete its calibration.

The original discussion proposed that a spatial conditional intensity should be examined with common observations, proper compensators and serious temporal benchmarks. Subsequent research explored those directions. This update reports the latest jointly fitted temporal-spatial/background experiment, rather than attempting to concatenate gains from separate historical runs. Its key contribution is a controlled comparison showing that the location improvement persists under a stronger background, while the temporal benefit depends on the spatial representation and comparator.

The Hawkes/ETAS and fractional-triggering literature already cited in the [manuscript bibliography](../paper/source/references.bib) supplies the modelling context. No novelty or reproduction claim for those model families is made here.

The authority is the sealed run `temporal_spatial_background_20261024T211225Z`, source commit `764f7e74576d71a3bd224990aa00491a533c13de`. This companion leaves the original manuscript and preceding addenda intact. [The decision report](../research_results/temporal_spatial_background/reports/decision_report.md) and [complete audited summary](../research_results/temporal_spatial_background/results/analysis/summary.json) provide the full comparison roster.

## 2. Matched design and scoring

The local GeoNet snapshot contains 913 events of magnitude at least 5.0. Training prefixes contain 301, 504 and 659 events; their disjoint test windows contain 203, 155 and 254 targets. Times are days since 1960-01-01 UTC, with horizon 24,394 days. All earlier observed events remain eligible parents. During a test window the forecast history updates with earlier observed test events, while fitted parameters and spatial nuisance estimates remain frozen. This is sequential conditional forecasting, not a single forecast of an entire future catalogue at the training cutoff.

The factorial crosses three temporal forms (fixed-scale ML, common free-scale ML, Omori), two immigrant-background representations (cell and KDE-enriched), and two offspring-location representations (continuous and cell-lift). All share fixed magnitude productivity parameter r = 0.7 and the same training-only conditional-bin magnitude-rate estimate. No new magnitude-productivity search is included.

For time t and projected location z, the conditional intensity has the form

```text
lambda(t,z) = exp[a + d X(t)] b_bg(z)
              + n sum_{j: t_j < t} kappa_j k_theta(t-t_j) s_sigma(z | z_j)
X(t) = 2t / 24394 - 1
```

Here kappa_j is the shared, training-calibrated magnitude-productivity weight of parent j. Both spatial densities integrate to one over the fixed nine-cell domain. Consequently the integrated regional rate is the background amplitude plus the normalized temporal offspring contribution. The joint marked log score includes point-event log intensity, the full space-time compensator and the common magnitude density. It decomposes exactly into timing, conditional zone, conditional cell, within-cell area density and magnitude terms. Higher score is better. All location scores use the same projected-area measure in square kilometres; a joint gain is not a percentage improvement in accuracy.

Continuous offspring density is proportional to a fixed training-derived reference density times the radial factor (1 + squared distance / sigma squared) to power -2, normalized separately for each actual parent. The lift comparator uses target-cell-centre weights and spreads each resulting cell mass uniformly inside that cell; it also retains actual parent coordinates. The radial factor is isotropic in the declared equal-area projection, but reference weighting and domain truncation make the full density generally anisotropic and piecewise smooth.

The KDE-enriched background mixes 95% training kernel density with a fixed 5% cell-density floor. Each kernel is separately normalized on the finite domain. Bandwidth selection uses spatial leave-one-out scores, removing exactly the scored row from both density and hierarchical counts. After selection the full-training plug-in density, including self-kernels, is frozen. It estimates observed event geography, not an identified immigrant distribution; in-sample fitting therefore includes nuisance reuse.

Fixed ML uses the pinned normalized 195-mode mixture at one day. Common ML estimates its scale over 0.001-20 days; Omori estimates c over 0.0001-20 days and p over 1.01-2.5. Temporal kernels have unit mass over all positive lags, with exact finite-window exposure rather than window renormalization. Spatial scale sigma is selected once per fold by the fixed-ML/cell-background/continuous baseline from 5, 15, 50, 150, 500 and 1500 km, then shared across all twelve primary procedures. Free parameters are refitted separately within each procedure. These are conditional shared-scale comparisons, not independent spatial optimization for every model. The [frozen protocol](../research_results/temporal_spatial_background/protocol_observed_v1.json) specifies bounds, starts and selection rules.

## 3. Temporal improvement is positive but conditional

Table 1 reports continuous-location comparisons. Differences are candidate minus reference, aggregated over the same 612 targets; nats/event is total gain divided by 612.

| Background and temporal contrast | Joint nats | Nats/event | Timing nats | Joint-positive windows |
| --- | ---: | ---: | ---: | ---: |
| Cell: common ML - fixed ML | -1.250002 | -0.002042 | +1.454602 | 2/3 |
| Cell: Omori - fixed ML | +67.965882 | +0.111055 | +23.419445 | 3/3 |
| Cell: Omori - common ML | +69.215884 | +0.113098 | +21.964843 | 3/3 |
| KDE-enriched: common ML - fixed ML | +5.616862 | +0.009178 | +9.652398 | 2/3 |
| KDE-enriched: Omori - fixed ML | +15.474231 | +0.025285 | +10.368176 | 3/3 |
| KDE-enriched: Omori - common ML | +9.857370 | +0.016107 | +0.715779 | 1/3 |

With the KDE-enriched background, Omori's joint gains over fixed ML are +0.687236, +0.845910 and +13.941085 nats; timing gains are +3.042197, +2.293691 and +5.032289. The timing improvement therefore survives the stronger background in each window, although most joint gain occurs in the third.

The comparison against common-scale ML is less consistent: joint differences are -1.091786, -5.559124 and +16.508279 nats. Moreover, under KDE-enriched background and cell-lift geography, Omori loses 10.186077 joint nats and 0.970870 timing nats to fixed ML. The evidence favours Omori over fixed ML within the continuous representation, not universal superiority of one kernel.

![Figure 1. Temporal comparisons across the three historical evaluation windows.](addendum_iii/figures/fig1_temporal.png)

## 4. The location improvement survives stronger background geography

Every continuous-minus-lift joint contrast wins all three windows under both backgrounds. Table 2 separates the spatial refinement from the effect of improving background geography.

| Temporal family | Continuous - lift, cell background (nats) | Continuous - lift, KDE-enriched background (nats) | KDE-enriched gain per event | KDE-enriched timing gain (nats) |
| --- | ---: | ---: | ---: | ---: |
| Fixed ML | +1453.289525 | +1424.124982 | +2.327002 | +16.545571 |
| Common ML | +1445.695714 | +1423.298295 | +2.325651 | +15.115146 |
| Omori | +1507.206261 | +1449.785291 | +2.368930 | +27.884617 |

The stronger background reduces the continuous-location advantage by 22.397419-57.420970 nats. It explains some of that advantage, but does not remove it within the declared models.

Location dominates the remaining improvement. For Omori with KDE-enriched background, the +1449.785291 joint nats comprise +27.884617 timing, +14.810114 conditional-zone, +18.815997 conditional-cell and +1388.274563 within-cell area-density nats. Magnitude differences are zero. The timing aggregate is positive despite two losing windows (+35.932611, -2.308009, -5.739984); this spatial result must not be presented as uniform timing success.

Changing background geography itself improves continuous-model joint scores by 85.740055, 92.606919 and 33.248405 nats for fixed ML, common ML and Omori. For Omori that background change loses 1.757274 timing nats. At fixed common parameters, normalized spatial changes leave total regional intensity unchanged; their fitted timing effects arise through refitting.

![Figure 2. Continuous-location improvements under both background representations, with location and timing distinguished.](addendum_iii/figures/fig2_spatial.png)

## 5. Combined procedure and scale sensitivity

Against the current matched fixed-ML/cell-background/lift comparator, Omori with continuous locations gains 1521.255407 joint nats using cell background, or 1554.503812 nats (2.540039 per event) using KDE-enriched background. The latter has +11.530195 timing nats and +1542.973617 net conditional-location nats; magnitude contributes zero. Joint gains are positive in all three windows, but timing changes are -2.961931, +4.108633 and +10.383493. These are direct fitted contrasts, not sums of earlier separate experiments. The previous sealed lift procedure selected its own sigma and is not the present shared-sigma comparator.

Training selected sigma values of 5, 15 and 15 km; KDE bandwidth was 15 km in all three windows. The first sigma lies at the primary grid's lower endpoint. Bounded sensitivity therefore retained separate fixed-ML/continuous fits at 1 and 2 km under both backgrounds. All twelve lost joint score against their primary reference, by 96.988003-308.063524 nats. Some improved timing while losing more location density. These sensitivity fits neither replace the primary models nor constitute an expanded-grid factorial.

![Figure 3. Joint-score losses from the declared 1 and 2 km sensitivity procedures.](addendum_iii/figures/fig3_sensitivity.png)

The catalogue has 910 distinct coordinate pairs among 913 events, with three repeated pairs. Serialized decimal places do not establish location accuracy; these results identify neither a physical interaction distance nor a universal optimal bandwidth.

## 6. Validation, scope and implications

All 63 observed procedures and 504 prescribed starts resolved, retaining 579 candidates and 75 exact floors. Including two fixed-seed engineering histories, totals are 87 procedures, 696 starts and solver returns, 803 candidates and 107 floors. Analytic gradients, finite differences, normalization, exact nesting and quadrature checks preceded observed fitting. An independent raw-history auditor reconciled saved scores to within 3.28e-11 nats, below the unchanged 1e-4 tolerance. Near-optimal forecast spread passed the declared gate. Neither multiple starts nor that gate certifies a global optimum.

One initial audit failed because a metadata assertion required exact binary equality between independently solved magnitude-rate estimates differing by six floating-point units. An append-only repair separated exact producer identity from the existing reconstruction tolerance. Independent numerical scores still used raw-derived values; all 326 scientific outputs remained unchanged, with no refits or replacement histories. [The audit review](../research_results/temporal_spatial_background/methods/final_master_audit_review.json) and [accounting](../research_results/temporal_spatial_background/reports/final_accounting.json) retain that failure and recovery. Raw catalogue rows and event-level caches remain local. This writing cycle reconciles reviewed saved aggregates; it does not repeat the fitting or raw-row audit. Computational-agent review is not external academic peer review.

The strongest supported conclusion is a positive retrospective forecasting ablation: finer offspring-location representation retains a large location-score advantage under a stronger background, while Omori adds a smaller timing improvement against fixed ML in the continuous model. Background and temporal comparisons also contain losses that prevent a blanket preference claim. Constant-Poisson floors are numerical witnesses, not an optimized no-trigger comparator, so this experiment does not establish that physical triggering is present or required. It does not test inhibition.

The same historical windows have been inspected repeatedly; overlapping training prefixes and dependent earthquake histories preclude event-iid confidence intervals or claims of independent replication. Proper held-out scoring does not remove this adaptive-reuse limitation. No Wilks inference, physical causality, immigrant-law recovery or universal scale claim follows. Continuous local inhibition and genuinely unused-data replication remain [design-only follow-ons](../research_results/temporal_spatial_background/design/followon_continuous_inhibition_and_replication.md). The current update supplies a bounded positive predictive finding while preserving those outstanding questions and all earlier manuscript conclusions in their original scope.
