# Scientific interpretation of C1

C1 supports localizing excitation for time-zone prediction, but does not support adding local stress inhibition to that localized excitation model. All three folds, four models, 12 case fits and 96 prescribed starts completed. The independent raw-row audit passed, reconciling 114 candidates and 96 solver returns; saved near-optimal forecasts passed the declared stability gate. The catalogue and historical authorities were preserved.

## Separate timing from zone prediction

On the 612 held-out targets, local excitation beats global excitation by 349.786446 joint nats (+0.571546481 nats/event), positive in all three folds. Of this gain, 347.958257 nats comes from conditional-zone prediction and only 1.828190 nats from regional timing. Joint gains are +105.104546, +119.000978 and +125.680922 nats; timing differences are -2.083237, +1.797562 and +2.113864. The strong joint result therefore concerns predicting which of three fixed latitude bands receives the next event. It is not evidence of a comparably large improvement in event timing or of continuous-location forecast skill.

At the same parameters, local E0 and global E0 have exactly the same regional ground intensity and compensator. Their conditional-zone factors differ, so selecting each by full time-zone training NLL produces different fitted parameters and modestly different timing forecasts. The observed timing difference does not contradict the fixed-parameter identity.

Local inhibition also beats global inhibition strongly: +364.573096 joint nats (+0.595707674 nats/event), including +17.936860 regional-timing and +346.636237 conditional-zone nats. Both joint and timing differences are positive in all three folds. This comparison includes both localized triggering and localized stress, and the poor globally inhibited baseline. It does not establish the value of inhibition beyond a matched local excitation model.

## The matched inhibition result remains negative

Adding local inhibition to local excitation loses 3.399761 joint nats (-0.005555164 nats/event): -2.077741 regional timing and -1.322020 conditional zone. Fold differences are -0.207862, -3.191896 and approximately zero (-0.000003) nats. The last difference is below the 0.0001-nat score-reconciliation tolerance and the selected eta is exactly zero; it should be described as a numerical tie rather than a substantive third forecast loss.

The local inhibitory fit lowers training NLL by approximately 0.112071, 1.061892 and zero nats in Folds 0-2, respectively, yet none yields a substantive held-out gain. These are modest training improvements of a nested bounded fitting procedure, not evidence for a nonzero physical depletion parameter.

Global inhibition loses 18.186411 nats (-0.029716357 nats/event). The difference of matched inhibition contrasts is therefore +14.786650 nats (+0.024161193 nats/event): localization makes the inhibitory penalty much less severe, while the local incremental inhibition contrast remains negative. This descriptive difference is positive in Folds 0 and 2, negative in Fold 1. It is not a causal difference-in-differences design.

## Fold 0 and proper exposure accounting

Fold 0's global inhibitory contrast is -16.988735 nats, decomposed into -33.904743 event and +16.916008 compensator nats. The matched local inhibitory contrast is -0.207862 nats: -3.000762 event and +2.792900 compensator nats. Regional timing improves from a -16.988735 global inhibitory penalty to a -0.831697 local inhibitory penalty; the local conditional-zone contribution is +0.623835 nats.

The proper Fold 0 local inhibitory score differences by zone are +0.289381 south, -0.141682 central and -0.355561 north. Their sum gives -0.207862. Across all three folds, the matched local inhibitory differences are negative in each zone: -1.199738, -1.134201 and -1.065822 nats. These are full zone contrasts with their own valid integrated exposures, not event-only geographical summaries.

The large local-versus-global joint gains cannot be reduced to a positive event term everywhere. For example, Fold 0 local E0 has a negative central-zone event contrast (-2.324219 nats), offset by a +17.184730 compensator contribution, giving a +14.860511 central-zone total. Quiet exposure and all-zone compensators are essential to the result.

## Parameters and historical reconciliation

The selected global eta values are 1.451113, 0.230849 and 0.116715; local eta values are 0.374699, 0.517222 and 0. Local eta is smaller in Folds 0 and 2 but larger in Fold 1. There is no uniform shrinkage result. Local and global stress histories also differ in scale and composition, so eta alone is not a directly comparable measure of physical stress strength. No selected coordinate hits a restrictive box boundary except the local eta=0 boundary in Fold 2.

The fresh global inhibitory contrasts reproduce Stage A's global raw contrasts to numerical precision: Fold 0 shifts by about 1e-11 nats, Fold 1 by +0.000013869 and Fold 2 by -0.000009878. Fixed-parameter global reduction was independently verified; these tiny separately optimized fit shifts are not failures of that identity. Historical Iteration28's -16.517557 Fold 0 contrast belongs to its own fitted/nuisance recipe and remains a separate authority.

The old five-degree cell crosswalk regroups event log-intensity ratios only. C1 defines three zone intensities, without a within-zone cell probability model; consequently cell compensators and cell full likelihoods are undefined. Proper zone compensators remain separate. Historical cell event penalties are retained with their source hashes and are not spliced into new denominators.

## Delimited conclusion

The useful result is strong retrospective categorical-zone prediction from localized triggering, with a small mixed-sign timing benefit for local E0. Localizing the whole inhibitory procedure largely removes the catastrophic global inhibition penalty, but the matched local inhibitory extension still adds no held-out value. This supports retaining E0_local as the better of these declared local procedures; it does not demonstrate physical stress inhibition or identify a causal spatial mechanism.

The result applies to three predeclared latitude bands, omega=0, fixed r=0.7 and the retained ML law on one previously examined regional catalogue. Training-only pi and beta were frozen for test; observed history updated predictably. No event-iid confidence interval, Wilks boundary test, global-optimum certificate, new partition, kernel search, C2 or other model stage follows from this review.

Evidence: results/analysis/summary.json; methods/observed_saved_audit.json; results/analysis/historical_reconciliation.json; results/analysis/cell_event_crosswalk.json; design/spatial_zone_counts.json; protocol_observed_v1.json. This interpretation introduces no numerical refit or pinned-source change.
