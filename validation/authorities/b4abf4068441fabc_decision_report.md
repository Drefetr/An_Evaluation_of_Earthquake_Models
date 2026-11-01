# California sequence score audit

The fixed partition confirms that the three previously reported 2019 contextual gains concentrate in one Ridgecrest-associated regional period. It does **not** reverse the stronger benchmark comparison: the OC-minus-EP joint difference is -18.372230095 nats during the active period and -32.678974668 nats over the complete complement. The pooled difference remains -51.051204763 nats (-0.162067317 per target). Conditional location accounts for most of this loss.

Only one eligible episode intersects the test windows in this admitted catalogue/domain. Its 110 targets occur over 2,713,564,040,000 microseconds, or 31.406991204 days: overlapping thirty-day anchor windows extend the union beyond thirty days. All test-year active exposure is this episode. The remaining 205 targets and 5,447.593008796 days are retained. The admitted chronology contains thirteen anchors and ten global episodes, but nine episodes belong to pre-test history; they are not additional scored sequence replications. Episode 9 is the unique Ridgecrest-associated episode under the frozen metadata rule. No other test-period episode is available for a sequence-to-sequence comparison.

For calendar 2019, the active period contributes +30.058155064 timing nats against fixedML, +375.944700694 location nats against OL, and +9.878145249 joint nats against commonML. The six-target 2019 complement contributes -0.777558252, +16.828728374 and -1.898745079 nats respectively. Thus the positive 2019 timing and commonML joint totals arise in the active period, with negative complement contributions; most of the 2019 location gain also occurs there. Across all fifteen test years, each contextual primary difference remains positive in the complement: +7.732184195 timing, +298.378821253 location and +11.299739148 joint nats. Concentration in 2019 does not mean that every pooled contextual gain is confined to that episode.

The original fifteen selected model states, five arms, three folds and 315 M≥4.0 targets are unchanged. Every score retains all original admissible parents and the original full spatial domain. There was no refit, candidate reselection, history deletion, event cap or pilot numerical reuse. OC denotes `Omori_smooth_cont`; EP is the independently fitted inverse-power ETAS reference; fixedML denotes `fixedML_smooth_cont`; OL is `Omori_smooth_lift`; commonML is `commonML_smooth_cont`.

The active indicator is defined by any admitted M≥6 anchor at u with u<t≤u+30 days, including eligible prehistory. Integer UTC membership, strict-past ties and global merging precede fold clipping. The initial anchor is in the complement unless an earlier anchor already activates its timestamp. One of the two test anchor targets is active and one is in the complement. Anchor event-only subset diagnostics remain private and independently audited; only their counts are released. These are regional time periods, not classifications of spatial or causal aftershocks.

**Complete coverage.** Counts below are common to every arm and contrast. Fold windows are half-open; calendar 2019 and pooled rows repeat portions of the original folds for reporting and must not be added to them. Exposure days are displayed to nine decimals; the approved JSON retains exact integer microseconds. Empty active rows in the early and late folds have zero exposure and zero totals, with null per-target means. The implementation also retains positive-exposure zero-target rows when present; none of the observed episode rows has that form.

| Reporting range / category | Targets | Anchor targets | Exposure days |
|---|---:|---:|---:|
| 2011-2016 / Active | 0 | 0 | 0.000000000 |
| 2011-2016 / Complement | 79 | 0 | 1826.000000000 |
| 2011-2016 / Total | 79 | 0 | 1826.000000000 |
| 2016-2021 / Active | 110 | 1 | 31.406991204 |
| 2016-2021 / Complement | 57 | 1 | 1795.593008796 |
| 2016-2021 / Total | 167 | 2 | 1827.000000000 |
| 2021-2026 / Active | 0 | 0 | 0.000000000 |
| 2021-2026 / Complement | 69 | 0 | 1826.000000000 |
| 2021-2026 / Total | 69 | 0 | 1826.000000000 |
| Calendar 2019 / Active | 110 | 1 | 31.406991204 |
| Calendar 2019 / Complement | 6 | 1 | 333.593008796 |
| Calendar 2019 / Total | 116 | 2 | 365.000000000 |
| Pooled 2011-2026 / Active | 110 | 1 | 31.406991204 |
| Pooled 2011-2026 / Complement | 205 | 1 | 5447.593008796 |
| Pooled 2011-2026 / Total | 315 | 2 | 5479.000000000 |
| 2016-2021 / Episode 9 (Ridgecrest) | 110 | 1 | 31.406991204 |

**Primary comparison: OC minus EP.** All terms are nats; larger is better for OC. Timing = ground-event term - positive integrated intensity E. The exposure column is therefore −ΔE, not ΔE. Joint = timing + conditional location + inherited mark; the mark contrast is exactly zero in every row. The full regional compensator is retained independently of the target count. Displayed values are rounded to nine decimals from the accepted full-precision JSON.

| Range / category | Ground-event Δ | Exposure contribution −ΔE | Timing Δ | Location Δ | Joint Δ | Joint Δ/target |
|---|---:|---:|---:|---:|---:|---:|
| 2011-2016 / Active | +0.000000000 | +0.000000000 | +0.000000000 | +0.000000000 | +0.000000000 | null |
| 2011-2016 / Complement | -1.064622768 | +1.557903123 | +0.493280355 | -6.782099452 | -6.288819097 | -0.079605305 |
| 2011-2016 / Total | -1.064622768 | +1.557903123 | +0.493280355 | -6.782099452 | -6.288819097 | -0.079605305 |
| 2016-2021 / Active | -0.872592079 | +0.065909253 | -0.806682826 | -17.565547269 | -18.372230095 | -0.167020274 |
| 2016-2021 / Complement | -0.679833552 | +1.302640826 | +0.622807275 | -13.993089629 | -13.370282354 | -0.234566357 |
| 2016-2021 / Total | -1.552425631 | +1.368550079 | -0.183875551 | -31.558636898 | -31.742512449 | -0.190074925 |
| 2021-2026 / Active | +0.000000000 | +0.000000000 | +0.000000000 | +0.000000000 | +0.000000000 | null |
| 2021-2026 / Complement | -0.587174150 | +0.614018871 | +0.026844721 | -13.046717939 | -13.019873217 | -0.188693815 |
| 2021-2026 / Total | -0.587174150 | +0.614018871 | +0.026844721 | -13.046717939 | -13.019873217 | -0.188693815 |
| Calendar 2019 / Active | -0.872592079 | +0.065909253 | -0.806682826 | -17.565547269 | -18.372230095 | -0.167020274 |
| Calendar 2019 / Complement | -0.071315734 | +0.390295314 | +0.318979580 | -2.116996329 | -1.798016750 | -0.299669458 |
| Calendar 2019 / Total | -0.943907813 | +0.456204567 | -0.487703246 | -19.682543598 | -20.170246844 | -0.173881438 |
| Pooled 2011-2026 / Active | -0.872592079 | +0.065909253 | -0.806682826 | -17.565547269 | -18.372230095 | -0.167020274 |
| Pooled 2011-2026 / Complement | -2.331630469 | +3.474562820 | +1.142932351 | -33.821907020 | -32.678974668 | -0.159409633 |
| Pooled 2011-2026 / Total | -3.204222548 | +3.540472073 | +0.336249525 | -51.387454288 | -51.051204763 | -0.162067317 |
| 2016-2021 / Episode 9 (Ridgecrest) | -0.872592079 | +0.065909253 | -0.806682826 | -17.565547269 | -18.372230095 | -0.167020274 |

The pooled timing difference is only +0.336249525 nats (+0.001067459 per target): -3.204222548 event-ground nats plus +3.540472073 exposure nats. The active period has a small timing loss (-0.806682826) as well as a location loss (-17.565547269); its lower OC compensator provides only +0.065909253 nats. In the complement, a +1.142932351 timing difference is outweighed by -33.821907020 location nats. OC is below EP on total joint score in every original fold, within calendar 2019, and in both pooled categories. An event-only comparison would omit the exposure contribution and would answer a different question.

**Three contextual comparisons.** Each column has its own reference and primary component; the columns must never be added. Parentheses divide that row's summed nats by that row's target count. Pooled means use the summed original-fold scores divided by 315, 110 or 205 as appropriate; they do not average fold means. All sixteen reporting rows per contrast are retained, including the sole episode and both empty active rows.

| Range / category | OC−fixedML timing: nats (per target) | OC−OL location: nats (per target) | OC−commonML joint: nats (per target) |
|---|---:|---:|---:|
| 2011-2016 / Active | +0.000000000 (null) | +0.000000000 (null) | +0.000000000 (null) |
| 2011-2016 / Complement | +0.099084005 (+0.001254228) | +91.803254519 (+1.162066513) | +5.392213175 (+0.068255863) |
| 2011-2016 / Total | +0.099084005 (+0.001254228) | +91.803254519 (+1.162066513) | +5.392213175 (+0.068255863) |
| 2016-2021 / Active | +30.058155064 (+0.273255955) | +375.944700694 (+3.417679097) | +9.878145249 (+0.089801320) |
| 2016-2021 / Complement | +2.664723302 (+0.046749532) | +89.885292282 (+1.576934952) | +0.730862724 (+0.012822153) |
| 2016-2021 / Total | +32.722878366 (+0.195945379) | +465.829992976 (+2.789401156) | +10.609007973 (+0.063526994) |
| 2021-2026 / Active | +0.000000000 (null) | +0.000000000 (null) | +0.000000000 (null) |
| 2021-2026 / Complement | +4.968376888 (+0.072005462) | +116.690274452 (+1.691163398) | +5.176663249 (+0.075024105) |
| 2021-2026 / Total | +4.968376888 (+0.072005462) | +116.690274452 (+1.691163398) | +5.176663249 (+0.075024105) |
| Calendar 2019 / Active | +30.058155064 (+0.273255955) | +375.944700694 (+3.417679097) | +9.878145249 (+0.089801320) |
| Calendar 2019 / Complement | -0.777558252 (-0.129593042) | +16.828728374 (+2.804788062) | -1.898745079 (-0.316457513) |
| Calendar 2019 / Total | +29.280596812 (+0.252418938) | +392.773429068 (+3.385977837) | +7.979400169 (+0.068787932) |
| Pooled 2011-2026 / Active | +30.058155064 (+0.273255955) | +375.944700694 (+3.417679097) | +9.878145249 (+0.089801320) |
| Pooled 2011-2026 / Complement | +7.732184195 (+0.037717972) | +298.378821253 (+1.455506445) | +11.299739148 (+0.055120679) |
| Pooled 2011-2026 / Total | +37.790339259 (+0.119969331) | +674.323521946 (+2.140709593) | +21.177884396 (+0.067231379) |
| 2016-2021 / Episode 9 (Ridgecrest) | +30.058155064 (+0.273255955) | +375.944700694 (+3.417679097) | +9.878145249 (+0.089801320) |

**Absolute pooled arm accounting.** The common target counts are 110 active, 205 complement and 315 total. These totals preserve the shared mark law once; contrast marks cancel. The closed aggregate also contains all fold, calendar-2019 and episode arm components, zone/cell/within-cell splits, exposures and per-target means.

| Arm / pooled category | Ground-event sum | Positive E | Timing | Conditional location | Mark | Joint |
|---|---:|---:|---:|---:|---:|---:|
| OC / Active | +451.279601588 | +69.960547415 | +381.319054173 | -796.930791629 | -3.899138947 | -419.510876403 |
| OC / Complement | -447.826953842 | +298.942177507 | -746.769131348 | -2069.601458524 | +0.113243545 | -2816.257346327 |
| OC / Total | +3.452647747 | +368.902724922 | -365.450077175 | -2866.532250153 | -3.785895402 | -3235.768222730 |
| EP / Active | +452.152193667 | +70.026456668 | +382.125736999 | -779.365244361 | -3.899138947 | -401.138646308 |
| EP / Complement | -445.495323373 | +302.416740327 | -747.912063700 | -2035.779551504 | +0.113243545 | -2783.578371659 |
| EP / Total | +6.656870295 | +372.443196995 | -365.786326700 | -2815.144795865 | -3.785895402 | -3184.717017967 |
| fixedML / Active | +424.214370841 | +72.953471732 | +351.260899109 | -793.603858831 | -3.899138947 | -446.242098669 |
| fixedML / Complement | -461.660601615 | +292.840713928 | -754.501315543 | -2074.107449411 | +0.113243545 | -2828.495521410 |
| fixedML / Total | -37.446230774 | +365.794185660 | -403.240416434 | -2867.711308243 | -3.785895402 | -3274.737620079 |
| OL / Active | +426.452950532 | +54.629531543 | +371.823418989 | -1172.875492323 | -3.899138947 | -804.951212281 |
| OL / Complement | -417.533182279 | +353.640495229 | -771.173677508 | -2367.980279776 | +0.113243545 | -3139.040713739 |
| OL / Total | +8.919768253 | +408.270026772 | -399.350258519 | -3540.855772099 | -3.785895402 | -3943.991926020 |
| commonML / Active | +440.199252278 | +73.917986263 | +366.281266016 | -791.771148720 | -3.899138947 | -429.389021652 |
| commonML / Complement | -455.378304069 | +295.102099395 | -750.480403464 | -2077.189925556 | +0.113243545 | -2827.557085475 |
| commonML / Total | -15.179051791 | +369.020085657 | -384.199137448 | -2868.961074276 | -3.785895402 | -3256.946107126 |

**Evidence and numerical scope.** All fifteen planned states completed; failed and missing states are zero. Independent raw-row reconstruction and saved-output comparison cover eighty arm rows and sixty-four contrast rows. All 7,128 component checks passed; maximum absolute discrepancy was 4.547473508864641e-13 nats against the 1e-4-nat gate. Production and independent scientific controls passed 161 and 101 checks, the exporter passed twelve controls, and eleven projection controls preceded 3,888 actual private-to-public projection checks with zero error and maximum difference zero. The projection retained every approved row while omitting anchor event-only scores, raw vectors, timestamps, membership hashes, source/event/fit IDs and fitted parameters.

The full production, independent reconstruction and comparison inner stages took 114.116648, 192.479349 and 0.0297049 seconds respectively. Together these inner stages took 306.6257019 seconds (5.11 minutes), including scientific admission rather than pure C++ work. They are evaluation/reconstruction times, not fitting times. The [final execution summary](../resources/final_execution_summary_v1.json) records thirteen serialized jobs, all terminal with exit zero and empty containment: summed controller-invocation elapsed time, including pin verification, was 1,937.50426364 seconds (32.29 minutes), while summed lease wall time was 984.0494395 seconds (16.40 minutes). These different boundaries must not be added. The job totals include the build, fixtures, pilots, full evaluation, export/projection checks and figure; they are not total project time, CPU time or a speedup measure. Provider/native latency, token use and monetary cost are unknown. External review used the observed `deepseek/deepseek-flash` route; backend 4.1 authentication remains unknown, and no raw data was shared. Jobs were serialized under the canonical machine lease with six numerical-library thread settings of one, fresh empty bytecode prefixes, successful child exits and proved-empty Windows Job Objects. Memory accounting sums individual parent/direct-conhost working-set peaks; it is not a simultaneous process-tree maximum, and the admission estimate is not a hard Job Object memory cap.

A reporting worker changed the frozen artifact contract outside its assigned scope. The full-v1 constructor rejected the changed input pin **before scientific launch**. The unauthorized bytes were preserved and the exact original SHA-256 restored; separately identified full-v2 jobs then succeeded under unchanged scientific pins. No model was refitted, no denominator changed, no pilot result was reused and no fine outcome was released through this incident.

**Interpretation and programme boundary.** Annual results, including 2019, were already inspected before the finer partition was chosen. This is a retrospective exploratory accounting exercise, not a new holdout, independent sequence replication, significance test, event-iid uncertainty calculation or calibration result. Relative proper-score differences do not establish absolute forecast adequacy. The prior [competitive benchmark](../../competitive_benchmarks_20261025T065609Z/reports/decision_report.md) still favors EP overall, and prior [conditional diagnostics](../../conditional_calibration_20261025T085151Z/reports/decision_report.md) found material OC count, timing and spatial discrepancies. This audit resolves where the specified realised gains occur; it does not resolve those calibration limitations or establish physical causation.

The original M≥4.0 scope is complete. No M4.5 extension, new model selection, live forecast, alert, scheduler activation or manuscript edit follows. Threads 04/06 remain separately gated and Thread05 remains readiness only. The existing roadmap can use this concentration finding alongside EP's superiority and OC's calibration discrepancies without treating the inspected period as future validation.

Evidence: [frozen specification](../design/partition_spec_v2.json), [scientific design](../design/sequence_design_v2.md), [accepted aggregate](../results/approved_aggregates_v2.json), [aggregate release](../reviews/aggregate_release_acceptance_v1.json), [independent audit](../full/compare_v1/audit_sanitized.json), [full evidence review](../reviews/full_evidence_review_v1.json), [projection verification](../reporting/projection_verified_v1.json), [claim register](claim_register.json), [137-file pinned source snapshot](../source_snapshot/manifest.json), [comparison figure](figures/sequence_comparisons.png) ([PDF](figures/sequence_comparisons.pdf), [SVG](figures/sequence_comparisons.svg)), [review bundle](../review_bundle.zip), and [sibling seal](../../sequence_score_audit_20261025T193331Z_seal.sha256). Source commit: `2f6524cbbec5d8d44f5148c70c0bc8241922dfca`. Authority SHA-256: `5859402683dc2db06555e23b238079a35eb6220273c85774f27c73071632c778`. Approved aggregate SHA-256: `682a9c7ecf12bc8c20174da3d48f8822ac8257dbd0b2984a37c9163c94fb2d89`. The figure, review bundle and seal are conductor-owned packaging outputs.
