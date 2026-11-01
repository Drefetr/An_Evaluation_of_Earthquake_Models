# Addendum IV: external comparisons, conditional calibration and regional transfer

**Retrospective scientific review draft | 29 October 2026 (Pacific/Auckland)**

## Abstract

The temporal and spatial forecast improvements in Addendum III survive some useful external comparisons, but their scope narrows when stronger benchmarks, conditional diagnostics and a third region are considered together. In California, Omori continuous (OC) improves timing over fixed-scale Mittag-Leffler continuous (FC) by 0.119969 nats per target and conditional location over Omori lifted (OL) by 2.140710, across 315 targets. OC also beats a separately refitted no-trigger procedure (N0), while a fitted inverse-power ETAS benchmark (EP) beats OC on joint score in every window, mainly through location. Conditional simulation of the original frozen OC forecast reveals material count, temporal and spatial discrepancies; it supplies no calibration result for EP. A higher-threshold sensitivity retains the primary directions, while annual and sequence accounting show marked concentration. Japan reproduces the continuous-versus-lifted location direction but reverses the Omori-versus-fixed-ML timing direction: its registered combined transfer criterion is not demonstrated. All archives had been inspected and revised; the comparisons are exploratory retrospective evidence, not pristine confirmation, physical causality or proof of forecast adequacy.

## 1. Question, status and relation to the preceding work

The question is how far the specific forecasting improvements reported in Addendum III travel when the region, comparator and diagnostic question change. There are four distinct questions: does a matched ablation retain its direction elsewhere; does the complete procedure beat serious alternatives; do its conditional probabilities resemble the recorded history; and where do the realised score differences occur? A positive answer to one does not answer the others.

[Addendum III](Addendum_III.md) found a large location-score advantage for continuous offspring geography over a cell-lift representation in New Zealand, and a smaller timing advantage for Omori decay over fixed-scale Mittag-Leffler decay within the continuous representation. Its 612 historical targets are context for the programme, not an additional denominator for any table below. The present addendum consolidates subsequent completed studies. [Addendum V](Addendum_V.md) separately reports the local-inhibition extension and its negative observed result. The original manuscript and Addenda I-III remain historical documents; these are new review drafts, not a claim that the manuscript itself has been updated.

The underlying analyses have numerical audits and computational-agent reviews. This editorial consolidation uses pinned accepted reports and aggregate exports; it performs no fit, simulation, new catalogue acquisition or live forecasting. Internal independent computational review and independent external academic inspection are different stages. External inspection remains pending.

## 2. Models, forecast object and score

### 2.1 Arm names and what each comparison changes

The abbreviations are local procedure names, not claims of new model families. All excitation arms share the declared training-only magnitude recipe with productivity exponent r = 0.7 and score the magnitude mark once.

| Arm | Temporal law | Offspring geography | Role |
| --- | --- | --- | --- |
| FC | Fixed-scale Mittag-Leffler | Continuous OC geography | Primary timing reference |
| FL | Fixed-scale Mittag-Leffler | Cell-lift | Spatial/context reference |
| MC | Free common-scale Mittag-Leffler | Continuous OC geography | Temporal context |
| OC | Omori | Continuous OC geography | Frozen target procedure |
| OL | Omori | Cell-lift | Primary location reference |
| EP | Omori ETAS adaptation | Unweighted inverse-power radial law | Competitive reference |
| N0 | No offspring excitation | Smooth background | Refitted no-trigger reference |
| LI | Omori plus immigrant attenuation | Continuous OC geography | Inhibition extension in V |

The continuous OC offspring density multiplies a radial factor by a fixed training-derived reference density and normalizes over the finite domain separately for each parent. A cell-lift uses target-cell-centre weights and spreads each cell's offspring mass uniformly inside it; actual parent coordinates remain in the calculation. Thus OC-OL is a particular within-domain representation comparison. Both retain smooth immigrant geography. EP instead uses a separately fitted, pure inverse-power offspring kernel, normalized with respect to projected area without OC's reference-density multiplier. OC-EP compares whole procedures with different spatial laws; it is not an isolated temporal-kernel experiment.

N0 fixes branching at zero and refits its own background time-rate parameters on training data. It is neither an OC fit with its trigger switched off afterwards nor a constant-Poisson numerical floor. LI attenuates only the immigrant component of OC; its full definition and exact zero-inhibition nesting are given in V.

### 2.2 Sequential conditional forecasting

At each origin, parameters and spatial nuisance choices use training data only and remain fixed during the test window. Every strictly earlier admissible observed event can enter the subsequent history, including earlier events in that test window. This scores a sequential conditional forecast. It does not supply the whole future catalogue at the origin, and it is not an issue-frozen nonhomogeneous Poisson forecast of the complete future path.

The finite domain, parent eligibility, exposure and projected-area measure are shared within each contrast. For an event intensity lambda(t,z), its regional ground intensity R(t), full space-time exposure E, and common magnitude-mark score M, define

```text
P = sum over targets of log lambda(t_i,z_i)
Q = sum over targets of log R(t_i)
E = integral over the full test time and domain of lambda(t,z)
C = -E, the signed exposure contribution
Timing score = Q + C = Q - E
Conditional-location score = P - Q
Joint score = P + C + M = P - E + M
            = Timing + Conditional location + M
```

Higher is better. In a difference between procedures, the signed exposure contribution is minus the difference in E. Quiet periods therefore contribute even when they contain no targets. Common mark differences cancel; a positive location difference is not a statement about magnitude forecasting. Nats are natural-log score units, not percentage accuracy, correlations, causal effects or an estimated percentage of predictable earthquakes. Pooled nats per target divide the sum of window differences by the sum of target counts, never the unweighted average of window means.

These symbols are the narrative convention throughout IV and V. The [source-field dictionary](../research_results/addenda_iv_v/provenance/score_field_semantics_v2.json) maps legacy labels without changing their values: LI's raw pooled key E denotes a point-logsum difference, while sequence timing_compensator denotes a positive exposure difference whose score contribution has the opposite sign. Neither raw name overrides the definitions above.

Primary timing means OC-FC timing; primary location means OC-OL conditional location. These rows use different references and cannot be added to manufacture a combined gain. A direct OC-FL joint contrast, where reported, is a separate comparison.

## 3. California: successful matched transfer with uneven contributions

### 3.1 Population and chronological windows

The repaired California source contains 1,272 canonical unique preferred SCEDC/SCSN records meeting reported M >= 4.0, latitude 32-37 degrees, longitude -121 to -114 degrees and depth -5 to 40 km. Of these, 106 records in 1981-1985 provide warmup parents. Scored training begins in 1986; expanding training prefixes contain 851, 930 and 1,097 targets. The three half-open UTC test windows contain 79, 167 and 69 targets. Their total is 315 unique held-out targets. Reappearance of this denominator in the benchmark, calibration, concentration and inhibition studies reflects reuse of those same targets, not new samples.

The schema repair retained an earlier stop and changed only acceptance of unused location-quality metadata as opaque printable tokens. All 45 cached official files were reused unchanged; no query, row removal, imputation or forecasting-engine change was needed. The 134 previously rejected occurrences were retained, and none was an M >= 4 model candidate. Independent reconstruction established equality of the previous model and diagnostic arrays. This establishes lossless handling within the verified snapshot, not universal source completeness or uninspected historical forecasting.

### 3.2 Primary results

| Window (targets) | OC-FC timing nats | Timing nats/target | OC-OL location nats | Location nats/target |
| --- | ---: | ---: | ---: | ---: |
| 2011-2016 (79) | +0.099084 | +0.001254 | +91.803255 | +1.162067 |
| 2016-2021 (167) | +32.722878 | +0.195945 | +465.829993 | +2.789401 |
| 2021-2026 (69) | +4.968377 | +0.072005 | +116.690274 | +1.691163 |
| Pooled (315) | +37.790339 | +0.119969 | +674.323522 | +2.140710 |

Both primary directions are positive in all three windows. Timing is nearly tied in the early window; the middle window supplies about 87% of the total timing difference. The timing pair also has a negative conditional-location difference in the middle window. Positive primary directions therefore do not imply uniformly improved components or a constant effect size.

Of the +674.323522 conditional-location nats, +653.602228 come from within-cell density. This is consistent with the distinction between a continuous density and uniform within-cell offspring mass. It does not establish a similarly large gain in allocation among broad zones or cells, nor general accuracy of individual event locations. Training selected both background bandwidth and inherited offspring scale at 5 km, the lower grid endpoint in every California fold. This is a boundary of the declared grid, not an identified physical interaction distance or proof of coordinate accuracy.

For context, OC-MC gains +21.177884 joint nats (+0.067231 per target), FC-FL gains +671.244340 location nats (+2.130934), and the direct OC-FL comparison gains +747.800021 joint nats (+2.373968). Each wins all three windows. Their reference arms and score components differ; these results are not additive.

![Figure 1. Matched timing and location comparisons in California and Japan.](addenda_iv_v/figures/v2/matched_regional_contrasts.png)

*Figure 1. Realised proper-score contrasts from the original California M >= 4 cohort (315 targets) and the JMA reported-primary M >= 4.5 complete-case cohort (1,277 records). Each panel has its own reference and horizontal scale. Timing compares OC with FC; conditional location compares OC with OL; joint compares OC with EP. Pooled diamonds divide summed window nats by the regional total. California uses UTC years and JMA source-JST years. Different-reference columns and geographies are not added. Related retrospective windows have no event-iid uncertainty intervals.*

The [California accepted report](../research_results/addenda_iv_v/curated_reports/CA-INITIAL.md) supplies source selection, repair chronology and complete comparison components.

## 4. Stronger benchmarks change the conclusion

OC substantially exceeds the genuinely refitted N0 procedure, but EP exceeds OC in each California window. The same 315 targets, common mark law and frozen OC states are used. EP was independently fitted using training data; it was not selected as a replacement downstream forecast after inspecting these scores.

| OC minus reference, pooled 315 | Joint nats | Timing nats | Location nats | Joint nats/target |
| --- | ---: | ---: | ---: | ---: |
| N0 | +1694.942967 | +894.845888 | +800.097080 | +5.380771 |
| EP | -51.051205 | +0.336250 | -51.387454 | -0.162067 |

OC-N0 joint, timing and location differences are positive in all three windows. This supplies a serious no-trigger predictive comparison that a numerical Poisson floor could not supply. Its middle window contributes about 77.49% of the joint gain. The comparison is between complete procedures with shared trained geography; it does not establish causal triggering or identify immigrant labels.

OC-EP joint differences are -6.288819, -31.742512 and -13.019873 nats. Conditional location loses in each window. The pooled timing difference is only +0.001067 nats per target, with a small middle-window loss; EP's joint advantage is mainly spatial. Therefore the finding that OC improves on OL cannot be promoted into superiority over the strongest evaluated spatial benchmark.

The decomposition also matters. Against EP, the point-event difference is -54.591677 nats, partly offset by a +3.540472 signed exposure contribution. Against N0, these are +1612.690857 and +82.252111. A point-only comparison would omit part of the forecasting question. All mark differences are zero.

![Figure 2. Timing and location components of OC relative to EP in California and Japan.](addenda_iv_v/figures/v2/ep_score_components.png)

*Figure 2. Pooled OC-minus-EP timing, conditional-location and joint differences, normalized separately by 315 California targets and 1,277 JMA records. Joint equals timing plus conditional location because mark differences are zero. California has a tiny timing edge; JMA has a timing loss. The larger location deficit accounts for most joint loss in both regions. EP is a separately fitted complete procedure; relative superiority establishes neither EP calibration nor an isolated temporal-kernel effect.*

The [competitive benchmark report](../research_results/addenda_iv_v/curated_reports/CA-BENCHMARK.md) is the numeric authority for this section. The LI replay in V is separately sourced and differs at floating-point scale; it does not replace these archived benchmark values.

## 5. Conditional diagnostics: useful discrimination without overall adequacy

### 5.1 What was calibrated

The completed conditional check targets original frozen OC alone. For each of its three origins, 999 complete branching-future paths were generated conditional on that origin's fixed fitted state, nuisance choices and original prehistory. Descendants can generate further descendants. All 2,997 paths completed; failed and unknown counts are zero. They are dependent-event paths under the model, not 2,997 independent earthquake samples. The observed-path exposure is a realised predictable compensator; it is not a Poisson future-count mean.

Each origin has 84 diagnostic coordinates, covering count, time gaps and dependence, spatial transforms and allocation, scores and subblocks. The full vector contains 252 coordinates. A coordinate's insertion interval is

```text
[(1 + number of simulated values strictly below observed)/1000,
 (1 + number of simulated values at or below observed)/1000].
```

The resolution is 0.001. Boundary ranks are finite reference comparisons, not zero probability or exact population tail probabilities. Ties can create wide intervals. This descriptive collection has no asserted omnibus significance test, and its coordinates are not separate unadjusted discoveries. Empirical reference intervals describe simulated catalogues, not confidence intervals for fitted parameters or scientific validity.

### 5.2 Discrepant and ordinary-looking results coexist

| Origin | Recorded count | Supplied simulated count interval | Count insertion interval | Selected diagnostic evidence |
| --- | ---: | --- | --- | --- |
| Early | 79 | 121-453 | [0.001, 0.001] | Gap KS, serial statistic and spatial KS exceed every reference |
| Middle | 167 | 90-398 | [0.704, 0.712] | Ordinary total hides yearly concentration and dependence |
| Late | 69 | 69-279 | [0.021, 0.028] | Marginal gap/spatial KS ordinary; dependence and variance discrepant |

Early count is below all 999 simulated counts. Its exposure and trigger exposure are also below all references. Its gap KS is 0.222245 and spatial Rosenblatt KS is 0.167335, each above every reference. Yet the time event-logsum insertion is 0.583, the censored terminal tail 0.111 and within-cell absolute maximum 0.187. The model does not fail every coordinate in the same way.

Middle total count looks ordinary, but the five yearly counts are 12, 4, 8, 116 and 27. Its subblock balance maximum has insertion 0.998; the gap serial statistic exceeds all references. Its conditional-location score insertion is 0.364 and within-cell density score 0.312, while spatial KS, cross dependence and allocation show discrepancies. A satisfactory-looking total or score coordinate does not settle concentration or dependence.

Late gap KS has insertion 0.676 and spatial KS 0.810, yet serial dependence has insertion 0.998, the spatial cross statistic 0.992, and dimensionless location variance exceeds every reference. Across origins, cell 4 observed counts 15, 7 and 8 are below conditional allocations 23.493717, 16.132286 and 14.770085. These allocations sum conditional probabilities at observed event times; they are not unconditional event-count means. Empty-cell ties require particular care: one zero count has insertion [0.001, 0.563], which cannot be summarized by its lower endpoint.

Raw score totals also depend on target count and density measure. Early total location and joint scores exceed all simulated totals while its count is below all simulated counts; this does not validate its probabilities. Immigrant exposure ties identically across paths within a fixed state by construction. Neither that deterministic tie nor count-dependent mark totals validates the underlying recipe.

### 5.3 Diagnostic scope

The evidence supports material count, temporal and spatial discrepancies for OC, alongside ordinary-looking coordinates. It does not support a broad adequacy claim. EP was never the target of this simulation exercise: EP's superior relative score supplies no EP calibration result. Fitting, selection, measurement and catalogue-revision uncertainty are excluded by fixing the state. Later training histories include earlier target periods; separate per-origin simulations do not define a coherent cross-origin joint null. Cross-window patterns remain descriptive. Heavy-tailed productivity has infinite second moment under the fixed mark recipe, and normal/CLT count inference is not used. A censored terminal tail is survival information, not an additional completed gap.

The [conditional diagnostic report](../research_results/addenda_iv_v/curated_reports/CA-CALIBRATION.md) and [current evidence index](../research_results/addenda_iv_v/current_evidence.json) retain the coordinate-level source and audit scope. All paths received identity/count/mark/exposure checks; independent full 84-coordinate raw replay covered nine paths, three prescribed indices per origin, not all 2,997 complete vectors.

## 6. Robustness and concentration answer narrower questions

### 6.1 A higher threshold retains directions under a changed observation law

The base annual accounting retains every event's original history and all exposure, including years with zero targets. It refits no base parameter. A separately admitted M >= 4.5 sensitivity rebuilds the population, eligible histories, training estimates, mark law and fitted procedures. Its 391-record population includes 33 warmup parents; training counts are 271, 287 and 340, and test counts 16, 53 and 18, totaling 87. Those 87 are a higher-threshold subset of the California history, not 87 additional independent records to add to 315.

| Primary comparison and component | M >= 4.0 nats/target (315) | M >= 4.5 nats/target (87) | M >= 4.5 total nats | Positive windows |
| --- | ---: | ---: | ---: | ---: |
| OC-FC timing | +0.119969 | +0.152292 | +13.249423 | 3/3 |
| OC-OL location | +2.140710 | +2.123867 | +184.776469 | 3/3 |
| OC-MC joint context | +0.067231 | +0.077518 | +6.744097 | 2/3 |

The first higher-threshold OC-MC joint difference is -0.626348 nats, and its OC-FC timing gain is only +0.077968 total nats. The two smaller test windows contain fewer than 20 targets. The threshold columns describe distinct complete procedures and target/parent laws; their difference is not a paired performance improvement or a threshold selection result. EP was not refitted or evaluated in this sensitivity, and no new calibration was performed.

Preferred magnitudes mix magnitude types and are not homogeneous moment magnitude. Count eligibility does not establish physical detection completeness. The source provides no defensible numerical location covariance or empirical location-error distribution; no perturbation law was invented from quality codes or decimal places. No independent alternate historical snapshot was admitted. The sensitivity therefore supports direction under one specified observation-law change, not general robustness to catalogue uncertainty.

### 6.2 Annual gains are concentrated

In the base analysis, calendar 2019 has 116 targets and contributes +29.280597 OC-FC timing nats, +392.773429 OC-OL location nats and +7.979400 OC-MC joint nats. At M >= 4.5, 37 targets in that year contribute +10.977080, +112.007721 and +5.288450 respectively. These are separate contrast/component columns. Negative annual contributions remain in the accepted tables.

Annual partitions preserve subsequent parent history. They do not estimate a counterfactual catalogue without a sequence. Their purpose is to locate realised score contributions, not to remove inconvenient years or create independent replications. The [robustness decision report](../research_results/addenda_iv_v/curated_reports/CA-ROBUSTNESS.md) records the full design and absent sensitivity laws.

### 6.3 One eligible active episode, with the complete complement retained

The finer sequence partition was chosen after annual inspection, including 2019. The frozen metadata rule marks regional time active when an admissible M >= 6 anchor at u satisfies u < t <= u + 30 days. Overlapping anchor windows merge globally before fold clipping; eligible prehistory is retained. This is a regional time partition, not a causal or spatial aftershock classification. The initial anchor belongs to the complement unless an earlier anchor already activates it.

Only one eligible episode intersects the scored test windows: a Ridgecrest-associated union lasting 31.406991204 days with 110 targets. The other 205 targets and 5,447.593008796 exposure days remain the complete complement. Thirteen anchors and ten global episodes occur in the admitted chronology, but nine episodes lie in pre-test history. They are not nine additional scored replications.

| Pooled category | Targets | OC-FC timing nats | OC-OL location nats | OC-MC joint nats |
| --- | ---: | ---: | ---: | ---: |
| Active period | 110 | +30.058155 | +375.944701 | +9.878145 |
| Complete complement | 205 | +7.732184 | +298.378821 | +11.299739 |
| Full original pool | 315 | +37.790339 | +674.323522 | +21.177884 |

The six-target calendar-2019 complement has -0.777558 timing nats and -1.898745 OC-MC joint nats, although its location contribution is positive. The annual timing and MC-context gains therefore arise in the active period. Across the full fifteen test years, all three contextual totals remain positive in the complement; concentration does not mean every contextual gain is confined to that episode.

The stronger reference still wins both partitions. OC-EP joint score is -18.372230 nats in the active period and -32.678975 in the complete complement. Its active timing difference is -0.806683 and location difference -17.565547. Complement timing is +1.142932, outweighed by -33.821907 location nats. All original parents and full-domain exposure remain in every score; event-only scoring would answer a different question. The [sequence audit report](../research_results/addenda_iv_v/curated_reports/CA-SEQUENCE.md) retains empty active rows, exact exposure accounting and the full partition.

## 7. Japan: spatial direction transfers, combined criterion does not

### 7.1 The reported-record target

The JMA analysis processes 19 local annual archives for source-JST years 2006-2024. Its 4,019,138 source records yield 4,602 usable study records. The target requires agency J, natural subsidiary 1, determination K/k/A, allowed primary magnitude types J/D/V/d/v, observed numeric primary reported M >= 4.5, depth 0-60 km and the fixed projected region. Primary and secondary magnitudes remain separate. This is an observed primary complete-case reported-record cohort, not homogeneous Mw, inferred latent magnitudes or proof of physical completeness.

Inspection identified 41,278 initially unresolved target observations: 41,277 with missing/undetermined primary information alone and one with an additional depth issue. An explicit, inspection-informed restriction requires numeric observed primary magnitude and an allowed primary type. It was documented and independently reviewed before fitting. Those records receive no assigned latent magnitude and are not asserted to be physically small. No complete target row was added, removed or modified by that clarification. One auxiliary depth-ambiguous subthreshold record remains unusable for diagnostics and has zero target, parent or beta-observation effect.

The 496 records in 2006-2010 supply warmup only. The following training prefixes and disjoint test windows use exact source-JST boundaries.

| Origin | Scored training years | Training records | Test years | Test records |
| --- | --- | ---: | --- | ---: |
| 2016 | 2011-2015 | 2,829 | 2016-2018 | 469 |
| 2019 | 2011-2018 | 3,298 | 2019-2021 | 348 |
| 2022 | 2011-2021 | 3,646 | 2022-2024 | 460 |

The total scored denominator is 1,277. These are revised local records; catalogue inspection and observation adjudication preclude a pristine as-issued holdout claim. The [JMA processing report](../research_results/addenda_iv_v/curated_reports/JMA-COHORT.md) gives the source restrictions and exact accounting.

### 7.2 Registered transfer and competitive context

The combined descriptive transfer rule requires both primary contrasts to exceed +0.0006 pooled total nats and each to be positive in at least two of three folds after audit pass. That threshold allows the declared numerical score tolerance; it is not a statistical significance boundary. The EP joint comparison is separate competitive context.

| Comparison and component | Total nats | Nats/record (1,277) | Direction in windows | Interpretation |
| --- | ---: | ---: | --- | --- |
| OC-FC timing | -58.593466 | -0.045884 | Negative 3/3 | Timing direction reverses |
| OC-OL location | +1905.743202 | +1.492360 | Positive 3/3 | Spatial direction transfers |
| OC-EP joint | -221.211492 | -0.173227 | Negative 3/3 | Strong reference still wins |
| OC-MC joint context | -49.194622 | -0.038524 | Negative 3/3 | No universal Omori preference |
| FC-FL location context | +1847.637387 | +1.446858 | Positive 3/3 | Spatial result also under FC |

The registered combined criterion is **not demonstrated**. OC-FC timing losses are approximately -19.9765, -12.8718 and -25.7452 nats. OC-OL location gains are approximately +619.711, +424.797 and +861.235. A large location total cannot compensate for a timing requirement with the wrong sign, and primary contrasts with different references must not be added.

EP exceeds OC jointly in all three windows. Conditional location accounts for 213.485907 of the 221.211492-nat deficit. OC also exceeds N0 on pooled joint score, but the strong-reference failure remains. These findings support a useful continuous-versus-lifted representation contrast while qualifying temporal transfer and overall competitive performance.

All background bandwidth selectors choose the lower 5 km endpoint, while FC spatial-scale selectors choose the interior 15 km value. The background trend slope reaches its lower bound for 7, 6 and 2 of seven models in the three folds. Results apply to the frozen grids and bounds; these choices do not identify physical length scales or measurement precision. The [JMA forecast report](../research_results/addenda_iv_v/curated_reports/JMA-FORECAST.md) retains full components, annual accounting and the registered decision.

## 8. Consolidated implications and limits

The completed evidence separates five conclusions. First, continuous offspring geography repeatedly improves conditional location relative to the declared cell-lift procedure, including California's higher-threshold sensitivity and the JMA reported-record cohort. Second, Omori's timing advantage over fixed-scale ML is conditional: positive in the original New Zealand/California comparisons, but negative in every JMA window. Third, excitation improves relative scores over a serious refitted no-trigger baseline, while EP beats OC on joint score in California and Japan, mainly through location. Fourth, OC's conditional diagnostics disclose material discrepancies, so relative gains are not adequate-probability certification. Fifth, California gains are uneven and concentrated, with only one eligible scored sequence period and substantial full-complement contributions.

The historical archives have been inspected, processed and revised; later studies adaptively reuse outcomes and related chronological windows. Frozen training/test calculations within a study do not erase that programme-level reuse. Overlapping training prefixes, earthquake dependence and small numbers of windows preclude event-iid confidence intervals and broad independent-replication claims. No Wilks inference, causal triggering claim, recovered immigrant law, physical stress range or absolute calibration result follows. Magnitude-type mixtures, reported-coordinate observation laws, finite-domain parent omissions, plug-in background estimates and grid/boundary choices remain material.

The New Zealand prospective programme is a separate readiness track. Its future data capture, issue policy and scoring horizon are distinct from these historical evaluations; this package contains no demonstrated issued-forecast results, scheduler activation or alerts. Neither the present transfer evidence nor the inhibition result in V backfills historical scores as future validation. A genuinely unused-data evaluation would answer a further question, not change what these inspected archives already show.

## Appendix A. Numerical custody and review scope

Numerical agreement supports the reported calculations; it does not independently replicate earthquake science. The California source repair accounted for 30 procedures and 240 starts. The separate benchmark audited all six new fit procedures and reconciled scores within 8.19e-11 nats. The higher-threshold sensitivity accounted for 30 procedures and 240 starts, reconciling within 1.13e-11 nats. The sequence audit retained all 315 targets and passed 7,128 component checks with maximum discrepancy 4.55e-13 nats. These are different validation rosters and are not independent research samples to add together.

JMA fitting resolved 36 procedures, 288 starts, 42 floors and 330 slots. Maximum independently reconstructed score disagreement was 1.82e-10 nats against a 1e-4-nat tolerance; maximum stored near-optimal spread was 3.75e-5 nats per record against a strict 0.01 gate. A retained atomic-save interruption was repaired by bounded filesystem retry, preserving completed states without refitting. Other historical failures and recoveries remain in the source reports. Multistart completion and near-optimal-set stability are not global optimization certificates or uncertainty intervals.

This writing cycle reproduces only aggregate display arithmetic and document/figure construction. The [current evidence index](../research_results/addenda_iv_v/current_evidence.json) routes the [source pins](../research_results/addenda_iv_v/source_pins_v2.json), [unchanged display scalars](../research_results/addenda_iv_v/releasable_results.json), source-specific field dictionary and complete claim bindings. The [readable scientific protocol subset](../research_results/addenda_iv_v/curated_protocols/scientific_protocol_subset_v2.json) supplies the LI law, clocks and full fitting contract used in V. The [review guide](Addenda_IV_V_review_guide.md) explains how to inspect this evidence and distinguishes source-reported research from current display reproduction. Raw catalogue rows, event caches and fitted vectors are excluded from the review package. This addendum remains a computationally reviewed editorial draft for independent external inspection.
