# Continuous-area spatial forecast decision

Continuous-area triggering substantially improved held-out point-location density forecasts relative to the projected cell-center lift, but did not improve regional event timing. Across the same 612 targets, E_cont minus E_lift gained 1,458.803884 joint nats (+2.383666477 nats/event), while losing 10.470041 timing nats. Most of the joint gain came from resolving locations within cells. Neither the zone-stress nor global-stress inhibitory extension supplied a meaningful incremental forecast gain.

All 42 planned procedures and 336 prescribed starts completed. The two selected E models per fold are aliases of existing selector results, not extra fits. The terminal independent raw-row audit replayed 384 candidates and 336 solver returns, reconstructed geometry and positive rectangle integrals independently, and found stable candidate forecasts. All 262 completed scientific outputs remained unchanged through the audit repair.

| Contrast | Fold 0 (203) | Fold 1 (155) | Fold 2 (254) | Total joint nats | Nats/event |
| --- | ---: | ---: | ---: | ---: | ---: |
| E_cont-E_lift | +549.866921 | +457.463557 | +451.473406 | +1458.803884 | +2.383666477 |
| E_cont-E_oldD_lift | +549.307187 | +462.729938 | +451.046777 | +1463.083902 | +2.390659970 |
| E_cont-E_global | +657.856745 | +614.999257 | +614.858124 | +1887.714125 | +3.084500205 |
| I_cont_zone-E_cont | +0.000032 | -0.211419 | -0.186526 | -0.397913 | -0.000650184 |
| I_cont_globalG-E_cont | +0.000032 | -0.000016 | -0.000004 | +0.000013 | +0.000000021 |
| E_lift-E_oldD_lift | -0.559734 | +5.266381 | -0.426630 | +4.280018 | +0.006993493 |

The continuous model wins joint point scores in all three windows against each excitatory comparator. Against E_lift, its timing differences are -3.163215, +0.705482 and -8.012308 nats; it improves timing in only Fold 1. The aggregate joint decomposition is:

| Component, E_cont minus E_lift | Nats |
| --- | ---: |
| Regional timing | -10.470041 |
| Conditional zone | -4.471988 |
| Conditional cell within zone | +21.333833 |
| Within-cell area logdensity | +1452.412080 |
| Magnitude | 0.000000 |
| Joint | +1458.803884 |

The corresponding point-event contribution is +1448.297321 nats and compensator contribution +10.506563, which reconcile to the joint gain because the common magnitude term cancels. This is evidence of improved conditional location prediction, predominantly inside the original coarse cells. It must not be reported as a 1,458.8-nat improvement in event timing. Normalized spatial triggering leaves the regional ground intensity unchanged at fixed nuisance parameters; the smaller timing differences arise through refitting those nuisance parameters to joint point likelihood.

Both families use actual unsnapped parent coordinates and the same equal-area projection, background density, six-point scale grid and square-kilometre area measure. The continuous model evaluates actual target points and analytically integrates each parent kernel over the rectangular domain. E_lift allocates parent mass at projected target-cell centers and spreads that mass uniformly within a cell. Its within-cell density is therefore fixed by cell area, whereas E_cont predicts subcell locations. The decomposition is proper: the within-cell term is an area logdensity, not a discrete probability.

| Fold | E_cont selected sigma (km) | E_lift selected sigma (km) | Zone-I eta | Global-I eta |
| --- | ---: | ---: | ---: | ---: |
| 0 | 5 | 150 | 0.000000000 | 0.000000000 |
| 1 | 15 | 150 | 0.068954189 | 0.000000000 |
| 2 | 15 | 5 | 0.021703682 | 0.000000000 |

The continuous scale is at the 5-km lower grid boundary in Fold 0 and at 15 km in Folds 1 and 2. The data and this finite grid do not identify a universal physical interaction length or support extrapolation below 5 km. Each family selects its own scale using training likelihood; E_cont versus E_lift is a comparison of complete selection procedures, rather than a fixed-scale-only geometric effect. The small near-optimal forecast spreads certify local forecast stability under the prescribed candidate pool, not unique identification of sigma.

Zone inhibition selects eta=0 in Fold 0 and small positive eta in Folds 1 and 2. Its aggregate change is -0.397913 joint nats (-0.000650184 per event), including -0.115282 timing nats. Fold 0 differs from E only by approximately 0.000032 nats at eta=0, a solver-scale tie; the other windows lose 0.211419 and 0.186526 nats. Global inhibition selects eta=0 in every fold. Its aggregate +0.000013 nats is below the 0.0001-nat reconciliation tolerance and is a numerical tie, not evidence of benefit. Both inhibition procedures use the same E_cont-selected sigma without reselection. Stress remains a raw three-zone or global temporal field, not a continuously resolved spatial stress field.

The sealed old C E_distance and E_global references were not refitted. They were lifted to point densities by dividing cell intensity by the exact projected cell area; their categorical joint totals subtract the same sum of test log-cell-areas. The independently checked lift identity puts every displayed contrast on the same km^-2 measure. E_cont gains 1,463.083902 nats over the old distance lift. The new E_lift gains only 4.280018 aggregate nats over that reference, winning one window. That latter contrast changes projection/target-center geometry, scale-grid range and fresh fitting, so it is not a pure metric effect. Neither comparison directly subtracts categorical and density likelihoods.

Two harness failures were retained and repaired in append-only epochs. First, six historical fit-file identity pins were missing although their identical model contents were already inside pinned old case JSON. The 14 completed first-case procedures and 112 starts were reused; only the remaining 28 procedures and 224 starts were newly run. Second, the independent old-anchor oracle recorded a unit diagnostic normalizer instead of the raw pi-weighted kernel sum. One diagnostic assignment was repaired; normalized masses, densities, likelihoods, gradients, fits, scores and tolerances were unchanged. A complete recovery-aware raw-row audit then passed. No completed start was refitted and no synthetic history was redrawn. Failed-attempt and audit wall time remain charged in final accounting.

This is retrospective evidence on a previously inspected catalogue and fixed finite domain. Isotropy is Euclidean in the declared cylindrical equal-area projection, not geodesic equivalence. The background remains nine-cell piecewise density, temporal excitation is fixed unit-scale ML with r=0.7, and no joint O/S model was fit. There are no event-iid intervals, Wilks boundary claims, physical-causality conclusions or universal bandwidth claims. The appropriate scientific conclusion is a strong location-density improvement for this continuous triggering procedure, with no accompanying timing improvement and no meaningful incremental inhibition gain.

Exact score and boundary tables are in [summary.json](../results/analysis/summary.json), with the terminal independent reconciliation in [observed_saved_audit_v3.json](../methods/observed_saved_audit_v3.json).
