# California M4.5 sensitivity decision report

The single predeclared M>=4.5 sensitivity retains positive pooled differences for the three specified comparisons: **13.249423 timing nats**, **184.776469 conditional-location nats** and **6.744097 joint nats**, over 87 targets. The corresponding per-target differences are 0.152292, 2.123867 and 0.077518 nats. The first window's joint comparison against common-scale ML is negative, at -0.626348 nats. Thus the pooled directions persist in this stricter population, while the joint advantage is not uniform across windows. These are three different comparisons, not quantities to add or a basis for selecting a new champion.

The [approved aggregate JSON](../results/approved_aggregates_v1.json) is the sole source of the sensitivity score tables below. Its SHA256 is `e93db40b7871acc7a0f03b78addc11a6e5e0fdb7f1703508d48ae5e253b9a62e`. Values in the tables are rounded to six decimals; the JSON retains full precision. Aggregate reporting follows a separate root release and independent raw-history reconstruction, rather than source review alone.

## Observation law and complete procedures

The threshold applies to the catalogue provider's preferred magnitude field, retaining its original mixture of magnitude types. It is not a homogenized moment-magnitude catalogue. The original M>=4 raw and canonical superset was verified first; a separate scenario file then selected `Decimal(raw magnitude token)>=Decimal('4.5')` and recomputed excess as `float(Decimal(raw magnitude token))-4.5`. The relative mark-bin cutoff remains 0.5, corresponding to an absolute boundary of M5.0 under the frozen binary64 operation. The [prospective protocol](../prospective_protocol_v1.md) and [frozen machine-readable protocol](../design/frozen_protocol_v1.json) specify the exact law.

The scenario contains 391 events, including 33 unscored warmup events. Training counts are 271, 287 and 340; the three fixed tests contain 16, 53 and 18 targets. The California domain, depth/type/time rules, equal-area geometry, strict earlier-parent rule, full eligible warmup and within-window history, r=0.7 and productivity formula remain unchanged. Every training window passes the unchanged event, zone and mark-bin eligibility gates.

The stricter threshold changes targets, parent histories, training populations, magnitude excesses and fitted nuisance quantities. Beta, hierarchical reference masses, KDE bandwidth and all model parameters were refitted from each scored training window only. Six fixedML continuous sigma selectors, the fixedML lifted prerequisite, commonML continuous and both Omori procedures were retained at each origin. The selected fixedML continuous arm aliases its training-winning selector; it is not an extra fit.

| Planned item | Planned | Completed or audited |
|---|---:|---:|
| Fitted procedures | 30 | 30 |
| Prescribed optimizer starts | 240 | 240 |
| Exact nested floors | 33 | 33 |
| Accepted candidate slots | 273 | 273 |
| Finite solver returns | Retain every feasible return | 240 |
| Model-window statuses including prerequisite | 15 | 15 complete |
| Retained primary-arm windows | 12 | 12 complete |
| Annual arm blocks / contrast blocks | 60 / 45 | 60 / 45 |
| Test targets | 16 / 53 / 18 | 87 total |

All eight starts, failure-only recovery rules, bounds, floors, nuisance searches and training-only selection rules are inherited. The whole first fold was the resource and correctness pilot; its accepted files were reused unchanged for the final denominator. Continuation used correctness and measured resource evidence, not score direction or rank. All candidate and finite-return forecasts were retained and audited, rather than only the four selected primary arms.

## Scores within the M4.5 population

Here OC denotes `Omori_smooth_cont`. Each primary row uses its named reference and component. Positive values mean OC scored higher on that component in this population. A nat is a log-score difference, not a percentage of correctly predicted events.

| Primary component and exact reference for OC minus reference | Pooled nats | Nats per target |
|---|---:|---:|
| Timing versus `fixedML_smooth_cont` | 13.249423 | 0.152292 |
| Conditional location versus `Omori_smooth_lift` | 184.776469 | 2.123867 |
| Joint versus `commonML_smooth_cont` | 6.744097 | 0.077518 |

| UTC window | Targets | Timing versus fixedML nats (per target) | Location versus Omori lift nats (per target) | Joint versus commonML nats (per target) |
|---|---:|---:|---:|---:|
| [2011,2016) | 16 | 0.077968 (0.004873) | 36.075692 (2.254731) | -0.626348 (-0.039147) |
| [2016,2021) | 53 | 11.741293 (0.221534) | 122.870533 (2.318312) | 6.141657 (0.115880) |
| [2021,2026) | 18 | 1.430162 (0.079453) | 25.830245 (1.435014) | 1.228788 (0.068266) |

Pooled means divide summed nats by 87. They do not average the three window means. All 12 primary-arm records and their full component scores remain in the approved JSON. For context, their pooled timing, location and joint totals are:

| Primary arm | Timing nats | Conditional-location nats | Joint nats |
|---|---:|---:|---:|
| `fixedML_smooth_cont` | -182.481890 | -803.122764 | -984.052721 |
| `commonML_smooth_cont` | -175.225364 | -803.571207 | -977.244638 |
| `Omori_smooth_cont` | -169.232467 | -802.820007 | -970.500541 |
| `Omori_smooth_lift` | -183.351046 | -987.596477 | -1169.395589 |

The timing contrast against fixedML comprises +14.762895 event-ground-log nats and -1.513472 exposure nats. Exposure contributes minus integrated intensity. The location contrast against Omori lift comprises +5.881781 zone, +2.472120 conditional-cell and +176.422568 within-cell-density nats. The joint contrast against commonML comprises +5.992897 timing and +0.751200 conditional-location nats. The common marginal mark score is included once and cancels in these contrasts. These decompositions belong to separate references and cannot be combined into a single contrast.

## Annual accounting

All 15 UTC years remain in the accounting. Annual boundaries partition event terms and exposure without resetting parent history. In 2019, 37 targets contribute 10.977080 timing nats, 112.007721 location nats and 5.288450 joint nats under the three distinct comparisons. Negative contributions elsewhere remain included.

| UTC year | Targets | Timing versus fixedML | Location versus Omori lift | Joint versus commonML |
|---|---:|---:|---:|---:|
| 2011 | 2 | -0.693040 | 1.606489 | -0.325730 |
| 2012 | 10 | 1.215152 | 34.711949 | 0.125733 |
| 2013 | 2 | -0.151209 | -0.171337 | -0.237623 |
| 2014 | 2 | -0.106284 | -0.071409 | -0.104797 |
| 2015 | 0 | -0.186651 | 0.000000 | -0.083930 |
| 2016 | 2 | -0.005887 | -0.106569 | 0.017104 |
| 2017 | 0 | -0.102727 | 0.000000 | -0.037390 |
| 2018 | 3 | 0.049658 | -0.141071 | -0.030889 |
| 2019 | 37 | 10.977080 | 112.007721 | 5.288450 |
| 2020 | 11 | 0.823168 | 11.110452 | 0.904382 |
| 2021 | 2 | -0.066946 | -0.215809 | -0.260059 |
| 2022 | 1 | -0.125996 | 0.366670 | 0.151796 |
| 2023 | 2 | -0.028005 | -0.134367 | -0.101869 |
| 2024 | 12 | 1.728755 | 25.902935 | 1.562646 |
| 2025 | 1 | -0.077647 | -0.089184 | -0.123725 |

The zero-target years 2015 and 2017 retain their full exposure. Their event-log, mark and location sums are zero, while the compensators still contribute to timing and joint scores. Per-target annual values are null in those years. Dropping them would change the declared score accounting.

The [annual contribution figure](figures_m45_v1/annual_primary_contributions_m4_m45_v1.png) shows every year and sign in separate M4 and M4.5 panels. The [window and pooled per-target figure](figures_m45_v1/window_primary_nats_per_target_m4_m45_v1.png) retains the negative early joint difference and the event-weighted pooled values. Test intervals are disjoint; dependence comes from expanding training histories, the shared revised catalogue and nested threshold populations. The panels are descriptive comparisons, not paired gains or independent replications. Matching SVG and PDF files are available alongside the PNGs. The [plot manifest](figures_m45_v1/plot_manifest_v1.json) lists source/input identities and output filenames; the [actual figure review](../report_figure_actual_review_v1.json) binds output byte hashes.

## Relation to the original M4 results

The [original M4 annual accounting](../../reports/block_decision_report_v1.md) uses 315 targets, with 79, 167 and 69 in its windows. Its primary pooled differences are shown separately below. The M4.5 results involve new training populations, histories, marks and refits, as well as fewer targets. Cross-threshold changes are therefore descriptive; subtracting these rows does not give a paired same-population score gain.

| Declared comparison | Original M4 nats (per 315 targets) | M4.5 nats (per 87 targets) |
|---|---:|---:|
| Timing OC versus fixedML | 37.790339 (0.119969) | 13.249423 (0.152292) |
| Location OC versus Omori lift | 674.323522 (2.140710) | 184.776469 (2.123867) |
| Joint OC versus commonML | 21.177884 (0.067231) | 6.744097 (0.077518) |

The pooled directional ordering is retained for these comparisons, but the sensitivity is not an independent replication. The same revised catalogue and overlapping, already inspected earthquake histories underlie both populations. The early joint difference against commonML is negative in M4.5 even though all original M4 primary window differences were positive.

## Numerical evidence and scientific limits

The [full actual audit acceptance](../full_actual_review_v1.json) binds all 30 procedures, 240 starts, 33 floors, 273 candidates, 240 finite solver returns, 103 saved report artifacts, 84 caches and the global plan. The maximum independent score error is 1.1226575225009583e-11 nats, below the 1e-4 gate. All 15 model-window statuses are complete under the inherited 16/32 and near-optimal stability checks. The [annual actual acceptance](../annual_actual_review_v1.json) binds all 60 arm blocks and 45 contrasts; maximum production-versus-independent discrepancy is 1.1368683772161603e-13 nats. The separate [root aggregate release](../design/root_aggregate_release_v1.json) authorizes the public table. Numerical agreement supports calculation consistency, not scientific calibration.

The complete local candidate, start, return, floor and training-selection tables are available at [private_reporting/candidate_tables_v1.json](../private_reporting/candidate_tables_v1.json), SHA256 `8ba55b42dae764c005e30bb3fe4200dbc7206d4a6f018aee2bc0760c5c50bb30`. They remain private local artifacts and are excluded from the review bundle; this report cites their location and byte identity without reproducing their contents.

There are only 87 targets, below the inherited descriptive reference of 100 total and 20 in each five-year window; the early and late windows contain 16 and 18. These pragmatic references are not power guarantees. No window, year or event was removed to meet them. The sensitivity retains the mixed preferred magnitudes and revised historical source; it does not establish uniform physical completeness, catalogue-measurement homogeneity or untouched holdout status.

The [earlier competitive benchmark](../../../competitive_benchmarks_20261025T065609Z/reports/decision_report.md) found original OC below the separately fitted inverse-power ETAS procedure EP on joint score in every original M4 window, with pooled OC-minus-EP -51.051204763 nats over 315 targets. The [conditional diagnostic study](../../../conditional_calibration_20261025T085151Z/reports/decision_report.md) found material count, timing and spatial discrepancies for original OC. It did not calibrate EP. This M4.5 sensitivity contains neither an EP comparison nor a new calibration experiment, and does not resolve those findings. Scores against different references cannot be added to infer an untested comparison.

No event-iid confidence interval, Wilks inference, causal triggering conclusion, physical range interpretation, calibration claim or new champion selection follows. The exact admitted objective DLL is unchanged, with historical compiler provenance unknown. This completes one retrospective observation-law sensitivity; it does not change the manuscript, frozen downstream procedure or operational registration.

The [final resource accounting](../../methods/final_resource_accounting_v1.json) records 33 terminal outer jobs and 3079.1245782 seconds in the numerical lease/envelope accounting, including three retained base-stage engineering jobs with nonzero exits. This is the declared accounting scope, not whole-project elapsed wall time, CPU time, provider usage or monetary cost. It includes the numerical controls, audits, export and rendering work; static review and reporting are distinct.
