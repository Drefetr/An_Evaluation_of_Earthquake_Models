# Scientific interpretation: W

W supports a small training-estimated global redistribution component in the otherwise local excitation model for zone prediction. It does not support an incremental inhibitory extension or a direct timing benefit from the mixing weight. All 27 case fits and 216 prescribed starts completed; the independent raw-row audit passed, checking 279 candidates and 216 solver returns. Reported differences use 612 targets and common magnitude scores cancel.

## Excitation mixing improves the joint score through zone prediction

Free-omega excitation improves on purely local excitation by 10.553372 joint nats (+0.017244071 nats/event), positive in all three held-out windows: +2.293398, +8.176718 and +0.083256 nats. Its conditional-zone gain is +13.789492 nats, while regional timing worsens by 3.236121 nats. Timing differences are +0.865688, -0.561462 and -3.540347 nats. The joint improvement should therefore be described as a categorical-zone forecast improvement with a net timing cost.

Selected excitation omega values are 0.046125, 0.045172 and 0.044339. These are weights on a globally redistributed trigger component; they are not literal cross-zone offspring probabilities. The globally redistributed component can also return to the parent's own zone, so a parent's actual cross-zone allocation is omega*(1-pi_parent_zone). No physical transfer rate is identified by these fitted routing weights.

The free model's training NLL gains against omega0 are approximately 2.163997, 4.867366 and 13.271381 nats. Exact completed endpoint floors preserve the nested training comparison, and all prescribed starts and near-optimal forecast checks passed. Three similar estimates from overlapping training prefixes do not provide an independent replication or confidence interval for a physical mixing parameter.

Free excitation beats global excitation by 360.339778 joint nats (+0.588790487 nats/event), with +361.747747 conditional-zone nats and -1.407969 timing nats. This chiefly retains the large spatial prediction benefit already seen in C1, with an additional modest gain over the strictly local endpoint.

## Omega has no direct timing effect

For either fixed stress choice and the same remaining parameters,

    sum_z lambda_z = sum_z pi_z exp(a+d*x-eta*Gstress_z) + n*Hglobal.

Omega cancels because excitation allocation is column-stochastic. This holds for E and both local/global-stress I families. Ground likelihood and total compensator are omega-invariant at fixed (a,d,n,eta). The observed timing changes arise indirectly because full time-zone training refits those other coordinates. They do not overturn the shared-kernel timing-invariance result or establish direct improvement in event timing from cross-zone redistribution.

## Matched free inhibition remains negative

With omega free in both matched models, local-stress inhibition loses 3.637297 joint nats (-0.005943296 nats/event) against excitation: -2.292422 timing and -1.344875 conditional-zone nats. Fold differences are +0.087297, -3.232617 and -0.491977 nats. Even the small Fold 0 joint gain combines worse timing (-0.704286) with better zone prediction (+0.791583). Regional timing is worse in all three windows.

Global-stress inhibition loses 12.887727 joint nats (-0.021058377 nats/event): -11.593479 timing and -1.294248 zone nats. Fold differences are -11.191948, +0.639379 and -2.335157 nats. Most of its aggregate loss remains in Fold 0. Local-stress inhibition outperforms global-stress inhibition in the free-omega comparison by 9.250429 nats, positive in two windows, but neither improves on matched excitation overall.

The selected free local-stress eta values are 0.281470, 0.579390 and 0.059749, with omega near 0.044-0.045. Free global-stress eta values are 0.910443, 0.133890 and 0.162321; their omega values are 0.068905, 0.048547 and 0.046997. These are fitted constrained prediction coordinates under different stress histories, not directly comparable physical stress strengths or a causal explanation of the losses.

## The factorial endpoints prevent a blanket localization claim

At fixed local excitation (omega0), global-stress inhibition loses only 1.005026 aggregate nats, whereas local-stress inhibition loses 3.399764 nats. Thus local stress is not uniformly the better stress choice. The global-stress eta is 0.068165 in Fold 0 and exactly zero in Folds 1 and 2; its tiny positive score differences in those latter windows are numerical ties, not meaningful forecast wins.

At fixed global excitation (omega1), local-stress eta is exactly zero in all three windows. Its aggregate score difference from excitation is -0.000031725 nats, below the 0.0001-nat saved-score reconciliation tolerance, and should be treated as a nested numerical tie. Global-stress inhibition at that same excitation endpoint loses 18.186431 nats, including -16.988727 in Fold 0.

The factorial result is an interaction among excitation routing, stress choice and joint nuisance refitting. It does not justify a universal statement that localizing stress rescues inhibition. Much of the earlier local-versus-global improvement is attributable to excitation routing and conditional-zone forecasting. The raw positive-window counters in the audit retain arithmetic signs; eta0 differences of order1e-5 or1e-6 are not scientific evidence for an inhibitory gain.

## Proper exposure and conclusion

All score contrasts include complete zone compensators. For example, Fold 0 free-local-inhibition versus free excitation has an event contribution of -2.002970 nats and a compensator contribution of +2.090266, giving +0.087297. Event penalties alone would give the wrong sign. No cell-within-zone score is present in this three-zone W stage; its full score is timing plus conditional zone plus common magnitude.

The delimited result favors free-omega excitation for categorical-zone forecasting among the declared W procedures, while the incremental local/global inhibitory alternatives remain negative overall. There is no direct omega timing effect, physical stress-transfer claim, event-iid confidence interval, Wilks boundary inference or global-optimum certificate.

D's model support, smoothing, distance grid, synthetic laws and selection rules were frozen before W outcomes. This interpretation changes none of them. Its launch depends on engineering correctness and the protected resource/audit reserves, not on a positive W result. The same held-out events will be reused in D, rather than forming a fresh independent validation catalogue.

Evidence: results/W/analysis/summary.json; methods/W_observed_saved_audit.json; protocol_W_observed.json; reports/W_decision_report.md. No new fit, source modification or extension was performed for this interpretation.
