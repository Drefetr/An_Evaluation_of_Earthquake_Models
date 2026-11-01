# Stage B decision report

Allowing one common Mittag-Leffler timescale improves pooled event-timing forecasts in all three retained windows. Additional parent-class timescales give a small positive aggregate gain, but improve only one window against the common-scale model. The predeclared association gate therefore fails, and no observed h model was fitted. This is a completed gated investigation, not a negative result for the unexecuted h branch.

## Audited comparisons

All nine observed fit procedures and 72 prescribed starts completed. The independent raw-row audit reconciled 90 candidates and 72 solver returns, with no failed finite solver returns. The two fixed-seed engineering histories also completed eight procedures/64 starts, including the optional h engine. Near-optimal forecast stability and source/input integrity gates passed.

The 612 targets occur in disjoint chronological windows containing 203, 155 and 254 events; their training prefixes overlap. All three observed models use fixed r=0.7, the same training-only beta per case, h=0 and the same magnitude density. Mark differences cancel up to floating-point roundoff, so timing and joint gains coincide.

| Candidate minus reference | Event contribution | Compensator contribution | Timing/joint nats | Nats/event | Positive windows |
| --- | ---: | ---: | ---: | ---: | ---: |
| Common free tau minus tau=1 | +4.405481 | +2.978194 | +7.383674 | +0.012064827 | 3/3 |
| Parent-class tau minus common tau | +5.297977 | -4.290144 | +1.007833 | +0.001646786 | 1/3 |
| Parent-class tau minus tau=1 | +9.703458 | -1.311951 | +8.391507 | +0.013711613 | 2/3 |

Here E is the ground event-log-intensity contrast and C is the baseline-minus-candidate compensator, so E+C equals timing. Timing plus the conditional-mark contrast equals joint score. These are event-weighted sums divided by 612, rather than unweighted averages of fold rates.

| Fold | Targets | Common minus tau=1 | Class minus common | Fitted common tau (days) | Class-0 tau | Class-1 tau |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 203 | +0.077011 | -0.467963 | 0.931796 | 0.863412 | 0.987068 |
| 1 | 155 | +3.053767 | +2.860470 | 0.826384 | 1.770186 | 0.539459 |
| 2 | 254 | +4.252896 | -1.384674 | 0.402085 | 1.352711 | 0.228245 |

The common-scale gain is consistent across these windows, although Fold 0's gain is only 0.077011 nats. The class-specific aggregate is positive, not a net loss. Its inconsistency against the stronger common-scale comparator is the reason the next branch stops. Winning two windows against the fixed tau=1 baseline is not the declared gate.

## Scale and selection limits

All selected parameters are interior to their prescribed bounds. The allowed tau range was 0.001 to 20 days, including subhour values, but none of the observed fitted scales is subhour. There is no lower-bound truncation explanation for these selected estimates and no bound expansion was performed.

Class 0 means 5.0<=M<5.5 and class 1 means M>=5.5. The kernels attach to the parent's class. The fitted ordering changes: class 0 is faster in Fold 0 but slower in Folds 1 and 2. These fits do not establish a stable physical magnitude ordering of aftershock timescales. Tau is a normalized-kernel scale, not a finite aftershock-duration cutoff, and is not interchangeable with Omori c.

Training NLL improves under exact nested floors. The additional class-specific training gains against the common model are approximately 0.012055, 1.867655 and 5.248592 nats, yet two held-out windows lose. Neither training improvement nor passing near-optimal forecast checks certifies physical scale identification or a global optimizer.

## Optional association branch

The prospective rule required class-specific h=0 timing to exceed common-scale timing by more than 0.0001 total nats in at least two windows, after complete fitting, independent audit and forecast stability. Only Fold 1 qualifies. The audited gate is false: zero of the conditional three observed h procedures/24 starts were executed. The h code, derivatives and synthetic engineering were validated before observing this decision; engineering validation is not observed evidence for or against association.

The optional mathematical family preserves the legacy Perron normalization. With parent-class kernels, summing the column-stochastic transition matrix still gives ground intensity B+(n/rho(h))(H0+H1). Association h adds no new direct temporal shape conditional on observed parent history; its scalar n/rho effect is already an excitation-amplitude coordinate. At fixed effective amplitude, timing is invariant to h, while conditional mark probabilities can change. No target-class kernels or post-gate model family were introduced.

## Historical Omori reference

The immutable historical Omori total is -990.170063 joint nats. The new fixed-scale, common-scale and class-scale procedures have raw joint totals of approximately -984.684158, -977.300484 and -976.292651. Their raw differences from historical Omori are +5.485905, +12.869579 and +13.877412 nats, respectively.

These are descriptive cross-procedure comparisons, not matched kernel-only gains. Historical selected productivity ratios are [0.4,0.7,0.7], whereas B fixes 0.7 throughout; only Fold 0 has that productivity mismatch. All three historical beta estimates use a different global-MLE convention. Beta also enters productivity weights, so this difference affects timing as well as magnitude scores. Historical Omori also used its own continuous shape/scale selection.

For common free tau, the raw historical difference splits into +10.389214 timing and +2.480366 magnitude nats. Magnitude terms therefore cannot be cancelled across those recipes. The matched B free-scale gain remains +7.383674 nats; the larger historical difference cannot be attributed solely to freeing tau. No prior Omori fit was rerun or overwritten, and no new matched Omori model was fitted.

## Delimited conclusion

The supported result is a modest, consistent timing gain from a common free ML scale in this bounded pooled procedure. Parent-class scales add a smaller positive aggregate but fail the predeclared across-window continuation criterion. Optional h remains untested on observed data.

This retains the original regional B design despite earlier spatial results; it is not a combined spatial-temporal validation or an independently replicated catalogue. All windows were previously examined. No physical causality, event-iid confidence interval, Wilks boundary inference, global-optimum certificate, alternative bounds or automatic further study is warranted.

Evidence: results/analysis/summary.json and base_summary.json; results/analysis/timing_gate.json; methods/observed_saved_audit_v1.json; reports/claim_register.json; reports/branch_decision.json; design/historical_omori_bridge.json. The final methods review binds their exact hashes.
