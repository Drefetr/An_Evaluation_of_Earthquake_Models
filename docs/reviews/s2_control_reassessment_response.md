# Response to the independent reassessment of `516e5fd`

The remaining C1 omission was valid. The original unit-mark narrow/short controls had positive generating strength but no realized thinning. Their losses should not have been presented as missed recovery of a realized inhibitory effect. The abstract, Chapter 13 overview and initial-control discussion, original S04 interpretation, Chapter 14 conclusion, companion guide and website now make that distinction. Original score tables, fitted states and numerical displays are retained.

The [received reassessment](independent_reassessment_516e.md) is preserved as a historical review of its named commit. Its artifact hashes certify that earlier edition. The [current production review](../../validation/reviews/S2_CONTROL_EDITION_20261107.json) identifies the revised files.

## Executed evidence for the correction

The [portable S2 reconstruction package](../../reproduction/synthetic/s2_unitmark/README.md) supplies all twenty original S04 history arrays, the first two earlier generation receipts and event records, source identities and a frozen reconstruction protocol. The first two cases were checked as a pilot; the full run reused that exact evidence and processed the remaining eighteen cases. Each positive-strength history was paired with an otherwise identical, same-seed uninhibited run: forty generator calls in total, with no likelihood evaluation or optimizer refit.

The [complete result](../../validation/live_results/s2_control_20261107/full/result.json) and [deterministic summary](../../validation/live_results/s2_control_20261107/summary.json) establish:

| Quantity | Reconstructed value |
|---|---:|
| Original unit-mark narrow/short histories | 20 |
| Histories with no rejected proposals | 20 |
| Immigrant proposals | 2,951 |
| Rejected immigrants | 0 |
| Offspring proposals | 1,317 |
| Rejected offspring | 0 |
| Accepted events across complete histories | 4,268 |

Every positive/null pair has exactly equal float64 event rows, full event/ancestry records and common random-stream counters and state hashes within the reconstruction runtime. All original S04 arrays match the reconstructed rows under the predeclared absolute tolerance of `1e-9`, with exact shape, row order and phase counts. Maximum observed differences are `2.2737367544323206e-13` days, `1.4210854715202004e-14` km in either coordinate, and `2.220446049250313e-16` in excess magnitude. The first two earlier Windows event arrays reproduce exactly, as do their original counters, common random-stream identities and ancestry.

These are distinct identity claims. We do not describe the later historical arrays as bit-identical across runtimes. Exact positive/null coupling within a runtime does not equate the two generating probability laws. The revised manuscript retains the outcomes under the stated positive-strength law while removing the unsupported realized-signal interpretation.

One factual correction to the reassessment follows from this audit: its prose gives **1,123 offspring**. The original twenty histories and reconstruction give **1,317**. Its [captured S2 execution](supporting/reviewer_s2_execution.json) printed the immigrant total and rejection counts, not that offspring total. This counting correction does not alter the valid C1 objection or its resolution.

## Additional joint background/branching control

The reviewer's actual joint `(b,n)` command and completed aggregate output are [retained separately](supporting/516e_joint_floor/README.md). The training/test separation is visible in the code. The output reports an S7 floor improvement of `47.6077` nats and a branching-rate range rounded to `[0.0000, 0.0000]`; the review derives a remaining LI+ total gain of `5.6255` nats.

This is useful exploratory evidence about the residual fixed-branching comparator restriction. The captured command does not retain per-case estimates, optimizer success/KKT checks or full-precision aggregates. Its rounded output does not establish exact zero in every case. The separate complete eighty-case replay files reproduce the published intercept-only control, not this joint fit. We preserve the joint calculation with attribution rather than presenting it as a newly validated manuscript result. The manuscript continues to describe its comparator sensitivity explicitly as intercept-only.

No historical California fit, inhibitory optimizer campaign or score table was recomputed for this correction. The earlier C2–C5 and M1–M2 revisions remain in place. The finite-mode theorem's poor quantitative bound is a lack of a useful catalogue-horizon mixing certificate; it is not, by itself, a proof of actual nonstationarity or of a particular mixing time.

## Verification and independent recheck

The [current check record](../../validation/checks.json) lists executed suites and publication checks. The preceding check record is preserved separately. Original protected authorities and provenance, historical claim records and withdrawals remain unchanged; the new count-over-total bindings point to the executed S2 summary.

From the repository root, choose fresh output directories and run:

```powershell
python -B reproduction/synthetic/s2_unitmark/reconstruct.py --phase pilot --output C:/scratch/s2_pilot
python -B reproduction/synthetic/s2_unitmark/reconstruct.py --phase full --pilot C:/scratch/s2_pilot --output C:/scratch/s2_full --check-summary validation/live_results/s2_control_20261107/summary.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
```

The focused reassessment question is whether the corrected interpretation now follows from the complete original S2 roster and the supplied reconstruction evidence. Please distinguish that question from the separately attributed joint-floor sensitivity and from the previously resolved methodological findings.
