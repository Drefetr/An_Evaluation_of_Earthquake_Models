# Annual score accounting: base-stage decision

26 October 2026. The accepted reconstruction shows that the three specified pooled score gains are unevenly distributed across the 15 annual UTC blocks. In 2019, 116 targets contribute 29.280597 timing nats, 392.773429 conditional-location nats and 7.979400 joint nats: **77.48%, 58.247% and 37.678% of their respective signed pooled gains**. These are three different comparisons; their gains and shares must not be added. This is descriptive accounting of already inspected outcomes, with no new independent empirical validation.

The [approved aggregates](../results/approved_aggregates_v1/aggregates.json) retain all 315 targets in the original windows [2011,2016), [2016,2021) and [2021,2026), with 79, 167 and 69 targets. Each score uses the original fitted state and full admissible past, including earlier observed events within a window. Annual boundaries partition event contributions and exposure integrals; they do not reset history. The marginal mark score is included once and cancels in the contrasts. No refitting, history deletion or target removal is involved. Per-target totals divide summed nats by the corresponding event count; pooled means use 315, rather than averaging annual or window means.

| Primary score and exact comparator (Omori_smooth_cont minus…) | Pooled gain, nats | Nats/target | 2019 signed share |
|---|---:|---:|---:|
| Timing: fixedML_smooth_cont | 37.790339 | 0.119969 | 77.48% |
| Conditional location: Omori_smooth_lift | 674.323522 | 2.140710 | 58.247% |
| Joint: commonML_smooth_cont | 21.177884 | 0.067231 | 37.678% |

All nine window-level primary values remain positive, although some annual contributions are negative.

| UTC window | Targets | Timing vs fixedML, nats (per target) | Location vs Omori lift, nats (per target) | Joint vs commonML, nats (per target) |
|---|---:|---:|---:|---:|
| [2011,2016) | 79 | 0.099084 (0.001254) | 91.803255 (1.162067) | 5.392213 (0.068256) |
| [2016,2021) | 167 | 32.722878 (0.195945) | 465.829993 (2.789401) | 10.609008 (0.063527) |
| [2021,2026) | 69 | 4.968377 (0.072005) | 116.690274 (1.691163) | 5.176663 (0.075024) |

The chronological table preserves every year and sign. Columns use the three distinct comparators above; all entries are primary contributions in nats. Rounded display values may not sum exactly to the unrounded totals.

| UTC year | Targets | Timing vs fixedML | Location vs Omori lift | Joint vs commonML |
|---|---:|---:|---:|---:|
| 2011 | 14 | -0.793154 | 3.799987 | 1.126779 |
| 2012 | 30 | 1.437855 | 71.410531 | 2.960125 |
| 2013 | 13 | -0.389569 | 3.706576 | -0.128884 |
| 2014 | 12 | -0.549005 | 7.993450 | 0.345606 |
| 2015 | 10 | 0.392957 | 4.892710 | 1.088588 |
| 2016 | 12 | 0.171398 | 11.782764 | 0.203358 |
| 2017 | 4 | -0.031771 | -0.196260 | 0.098685 |
| 2018 | 8 | 0.124995 | -0.468682 | 0.160320 |
| 2019 | 116 | 29.280597 | 392.773429 | 7.979400 |
| 2020 | 27 | 3.177659 | 61.938742 | 2.167244 |
| 2021 | 14 | 2.292431 | 32.673256 | 1.399970 |
| 2022 | 6 | -0.277276 | 0.515857 | 0.224872 |
| 2023 | 11 | 0.685377 | 16.446040 | 1.653336 |
| 2024 | 31 | 2.319217 | 66.551129 | 1.426416 |
| 2025 | 7 | -0.051373 | 0.503992 | 0.472070 |

The timing gain against fixedML decomposes into +40.898879 event-ground-log nats and -3.108539 exposure nats. Exposure is **minus integrated intensity**, so a higher integrated intensity contributes negatively. The location gain against Omori lift consists of +17.206741 zone, +3.514553 conditional-cell and +653.602228 within-cell-density nats. The joint gain against commonML consists of +18.749060 timing and +2.428824 conditional-location nats, with zero mark contrast. These decompositions belong to their named comparator; they cannot be combined into a single decomposition across the three rows.

The 2019 percentages use the predeclared signed-share definition: that year's primary contribution divided by its own contrast's signed pooled total. They are not event percentages or absolute shares. Negative annual contributions remain in each denominator. The figures and table describe where the realised score differences occur; they do not identify an episode's causal effect or a physical mechanism. There is no leave-block-out recalculation, deletion experiment, correlation analysis, p-value or new accuracy measure here.

The [base reconstruction acceptance](../reviews/base_reconstruction_acceptance_v1.json) and [sanitized reconciliation](../full_v1/reconciliation_sanitized.json) record all 60 arm rows, 45 contrast rows and 12 arm windows. All 2,097 identity checks passed; maximum production-versus-independent discrepancy was 1.1368683772161603e-13 nats, below the 1e-4 gate. The larger 3.9642412019702533e-7 pooled-approved discrepancy concerns comparison with rounded historical reference totals. Numerical agreement establishes reconstruction consistency, not forecast adequacy. Publication of these aggregates is separately bound by the [aggregate release](../design/aggregate_release_v1.json). The authoritative JSON SHA256 is `bf4d50b9ecefc5311b4ebb344d80e4c7990ed724459f9734794070a5063bee22`.

Earlier conclusions remain in force. The [competitive benchmark](../../competitive_benchmarks_20261025T065609Z/reports/decision_report.md) found OC below the separately fitted inverse-power ETAS procedure EP in joint score in every window, with pooled OC-minus-EP -51.051204763 nats. The [conditional diagnostic report](../../conditional_calibration_20261025T085151Z/reports/decision_report.md) found material count, temporal and spatial discrepancies for original OC alongside ordinary-looking coordinates. Concentration of realised gains neither reverses those comparisons nor establishes calibration, predictive accuracy or model adequacy. These inspected retrospective outcomes are not a fresh holdout.

This completes reporting of the accepted base block stage only. The Thread03 provenance/observation-law inventory and separately admitted sensitivity work remain pending. No manuscript change, procedure replacement or sensitivity conclusion follows from this report. The [plotter source](../implementation/plot_approved_blocks_v1.py) is ready for root execution and visual review; this authoring task did not render it.
