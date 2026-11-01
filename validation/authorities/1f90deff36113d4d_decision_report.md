# Continuously tuned Omori and stress-inhibition decision

Continuously training-tuned Omori excitation improved held-out timing over the fixed ML baseline in all three primary windows. Stress inhibition still reduced aggregate held-out scores under the same E-selected Omori kernels. The primary matched orthogonal contrast lost 14.137174 nats across 612 targets, and the secondary jointly tuned inhibitory model lost 11.803237 nats. This is a negative result for the implemented bounded stress-depletion procedures, alongside a positive result for temporal-kernel tuning.

All 45 planned procedures and 360 prescribed starts completed; the independent raw-row audit reconciled 456 candidates and 360 solver returns and found stable near-optimal forecasts. Model selection used training NLL only. Magnitude scores are identical within each case, so every displayed timing difference is also the joint difference.

| Primary contrast | Fold 0 (203) | Fold 1 (155) | Fold 2 (254) | Total nats | Nats/event |
| --- | ---: | ---: | ---: | ---: | ---: |
| E_omori-E_ml | +2.448100 | +3.184277 | +6.573125 | +12.205503 | +0.019943632 |
| Iraw_matched-E_omori | -12.255451 | +0.175155 | -1.695409 | -13.775706 | -0.022509323 |
| Iorth_matched-E_omori | -12.616922 | +0.175158 | -1.695409 | -14.137174 | -0.023099957 |
| Iorth_joint-E_omori | -8.721921 | -0.353436 | -2.727880 | -11.803237 | -0.019286335 |

The matched orthogonal model won only Fold 1 by 0.175158 nats and lost Folds 0 and 2. The jointly tuned inhibitory model lost all three primary windows. Its 2.333937-nat aggregate improvement over matched orthogonal inhibition is secondary; it does not turn the inhibitory versus excitatory comparison positive.

For E_omori minus E_ml, the event-log-intensity gain was 17.242145 nats and the compensator contribution was -5.036642 nats, giving +12.205503. For matched orthogonal inhibition minus E_omori, the event contribution was -37.002313 and the compensator contribution +22.865140, leaving -14.137174. Lower exposure could not offset lost event intensity.

Training-selected primary E kernels were:

| Fold | c (days) | c (minutes) | p |
| --- | ---: | ---: | ---: |
| 0 | 0.014609483 | 21.038 | 1.146120531 |
| 1 | 0.020001973 | 28.803 | 1.194027340 |
| 2 | 0.006776502 | 9.758 | 1.152027670 |

These c and p estimates are interior to the prospectively fixed bounds. The short selected c values explain why the earlier coarse grid with minimum c=0.1 day did not adequately search this continuous family. This is a scale parameter of a heavy-tailed kernel, not an estimated physical recovery duration. Stress itself still uses the original fixed ML survival kernel; only triggering was continuously tuned.

Orthogonalization did not rescue the primary loss. In Fold 0 raw inhibition reached its raw d=2 upper boundary. Its selected point maps feasibly into orthogonal coordinates, while the orthogonal optimum maps back to raw d=2.114439 and lies outside the raw box. The orthogonal fit improves training NLL by only 0.005858 nats but loses a further 0.361471 test nats. In Folds 1 and 2 the selected points map feasibly both ways and their forecasts agree up to numerical optimization differences. Thus the small primary difference between raw and orthogonal procedures is explained by a changed bounded parameter domain, rather than a new unrestricted model space. Exposure orthogonality is not likelihood-score orthogonality.

The constant-background sensitivity fixes raw d=0 or detrended d_tilde=0 respectively. These are different restrictions; all selected mapped raw/orth constant-case points violate the destination constant restriction. Their contrast cannot be interpreted as pure reparameterization. The post-1980 variant changes the training window and its projection/nuisance estimates, while retaining full prior event history.

| Variant, same 612 targets | E_omori minus E_ml | Iraw matched minus E_omori | Iorth matched minus E_omori | Iorth joint minus E_omori |
| --- | ---: | ---: | ---: | ---: |
| primary | +12.205503 | -13.775706 | -14.137174 | -11.803237 |
| constant_background | +14.293030 | -14.246392 | -8.796918 | -8.281496 |
| post1980_training | +10.103221 | -18.137615 | -18.768698 | -13.850430 |

Omori excitation wins all three windows in each sensitivity variant. Every inhibitory aggregate remains negative. Constant-background detrended inhibition improves over raw inhibition by 5.449474 nats, but still loses 8.796918 nats against its matched excitatory comparator. The same test events are reused across variants and must not be pooled as 1,836 independent targets.

Within this bounded, regionally pooled fixed-productivity family, inhibitory failure therefore persists after replacing the inferior fixed ML trigger with continuously tuned Omori excitation. It cannot be attributed solely to that fixed-trigger choice or solely to the raw trend boundary. This does not establish that physical stress inhibition is absent, and it does not test continuous spatial stress or a joint spatial/temporal extension. The historical Iteration 27 Omori result uses a different nuisance recipe, including the Fold 0 productivity ratio and training magnitude estimator; the present gain is a new internally matched comparison, not a numerical reproduction of that historical score.

The catalogue and windows were previously inspected, and three chronological tests provide limited robustness evidence. No event-iid intervals, boundary Wilks claims, physical-causality conclusions or global-optimum certificate follow. S was designed and frozen before these outcomes; its launch is governed by correctness and resource admission, not this score direction.

Exact per-window scores, parameters, boundary flags and both-direction mapping diagnostics are in [summary.json](../results/analysis/summary.json). The independent raw-row reconciliation is in [observed_saved_audit_v1.json](../methods/observed_saved_audit_v1.json).
