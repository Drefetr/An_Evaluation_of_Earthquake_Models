# Response to the independent reassessment of 12 November 2026

The reassessment identified five concrete defects after the earlier remediation. The earlier acceptance record covered selected checks rather than the documented full main suite. Its artifacts and exact claim ledger are preserved in [the pre-reassessment archive](../../paper/history/pre_reassessment_123503b6_20261112.zip). The current acceptance status and executed checks are recorded separately in [the reassessment record](../../validation/reassessment_20261112.json).

## 1. Final-resolution ETAS search

The corrected acceptance procedure constructs the exact fitted null, three fresh positive-strength starts `(eta, ell0, psi) = (0.05, 10, 2), (0.2, 20, 5), (0.5, 50, 30)`, and the previous terminal warm starts at every final quadrature resolution. Each start has its initial vector, actual objective evaluations and source identity recorded. Completion requires successful positive starts with verified first evaluations and actual interior evaluations; a list of terminal zero-strength vectors cannot satisfy that requirement.

The new bounded remote GPU execution completed all three folds at power 14. The nine positive starts made 6/19/21 interior evaluations in F0, 5/23/21 in F1, and 7/11/11 in F2. Every fold still selects zero strength with identical matched held-out scores. The baseline parameter vectors, background weights, source caches and saved held-out component vectors are exactly unchanged, so the baseline improvement and its earlier paired-block calculation carry forward through an explicit identity reconciliation. This reconciliation is not described as a new resampling campaign.

The [new execution](../../validation/live_results/etas_inhibition_benchmark_interior_20261112/summary.json), [trace census](../../validation/live_results/etas_inhibition_benchmark_interior_20261112/interior_start_audit.json) and [baseline identity reconciliation](../../validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_identity_reconciliation.json) preserve the evidence. Earlier execution results and source snapshots remain historical. Chapters 11 and 14 now identify full-plane normalization and regional leakage, in addition to magnitude scaling, background weighting and joint fitting, among the combined changes relative to archived EP.

## 2. Documented workflows and current reader materials

The public refined-reader entry point is restored to its exact baseline bytes. Recovery uses the separate module entry point `python -B -m experiments.s04b_completion.recover`. The added dispatch is preserved as a historical snapshot. The unreferenced pooling figure is archived outside the canonical figure directory, and canonical figure-manifest membership is corrected.

The eight-page guide is updated with the complete joint comparison, concave comparator, moderate-thinning control, strengthened ETAS benchmark and block uncertainty. The website publication path retains the original historical validators and adds a separately reviewed adapter that checks all 80 current case sources and independently reconstructs all 20 aggregate rows before publishing the completed view. Its rejection tests cover missing source-review pins, hash-consistent false aggregates, corrupt cases and rebound false gains. Neither historical validation nor the existing workflow assertions were weakened.

The [publication source review](../../validation/publication_refresh_20261112/joint_publication_review.json), [guide review](../../validation/publication_refresh_20261112/companion_review.json), preserved original reader materials and final workflow checks are linked from the current acceptance record. Installation updates the repository preview; it does not publish a site or push a branch.

## 3. Complete moderate-control reporting

The S8 table now includes raw and training-only BIC-gated rows. The raw row is unchanged. Direct computation from the twenty saved histories gives the gated mean **+2.4946 nats**, median **0**, sample MCSE **1.4436**, **9/20 wins**, and **12/20 active**. Eight gate returns are exact zeros. The reassessment's proposed median 0.1667 and MCSE 1.6627 are not reproduced: nine positive gains, three negative gains and eight zeros imply a zero median, and the direct sample calculation determines the MCSE.

The manuscript states that 13/20 raw fits reach a parameter boundary: seven at `p=2.5`, six at `n=0.98`, two at `eta=4`, and one at `a=0`, with overlapping counts. It also reports the 18/20 failures under the inherited stricter score/gradient check and the maximum scaled gradient discrepancy 0.03324. The pinned original protocol specifies **1e-4 for both stricter thresholds**; the reassessment's 1e-3 gradient threshold is a transcription error. S8's declared score-doubling rule remains 0.01 nat. No fit was rerun or retrospectively represented as passing the stricter rule.

The [supplementary authority](../../validation/live_results/reporting_supplement_20261112/supplement.json) and [independent audit](../../validation/live_results/reporting_supplement_independent_audit_20261112.json) bind the per-history gate decisions, boundary census, numerical flags and new displays. Previous scientific summaries remain byte-for-byte unchanged.

## 4. Bibliography and citations

The duplicate Zhuang--Ogata--Vere-Jones entry is removed. Both manuscript references use the existing `ZhuangOgataVereJones2002` key. The declustering and Wells--Coppersmith citations are parenthetical in the benchmark section and its generator. The compiled bibliography contains one entry for the declustering article.

## 5. Comparator win columns

The comparator table now reports separate **Wins (a)** and **Wins (a,n)** columns beside the corresponding mean contrasts. Counts are independently recomputed from all eighty paired histories. Existing inhibited fits and original gates are retained; this reporting change does not constitute another fitting campaign.
