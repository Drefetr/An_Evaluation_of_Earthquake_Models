# Explicit interrupted-invocation recovery

This is a separately reviewed operational transition for the fixed joint-nuisance
study. It leaves the original scientific functions, optimizer settings, ordered
CPU scheduler, earlier allocation policy and failed artifacts unchanged. Source
review is required before execution; this package itself is not a result.

The first call accepts only the exact failed index for
`S5_broad_long_imm_seed410518` and its independent partial-output review. It keeps
all forty completed cases and all charged attempts. Complete null and LI fit
objects are reused. The original `fit_arm` receives saved optimizer returns for
the five completed immigrant starts and the exact recorded primary error for
start five. Its unfinished Powell invocation restarts from the original initial
point with the original options. Starts six and seven and the total-intensity
arm then use the unchanged function. No completed optimizer trajectory repeats.

The original Powell internal state was not saved. This is an administrative
restart of that interrupted invocation, with its wasted work retained and
charged; it is not exact internal-state continuation. The actual saved return
at count 2,040 and next input at count 2,041 must agree exactly. The call ledger
retains both actual anchors. Unsaved intermediate points are not independently
certified by those two checks.

The frozen runner recomputes training-floor, eligible-floor, fresh-return and
selected-state support checks. These real evaluations are counted separately.
Reused successful records and null/LI training checks must remain exactly equal.
The ordinary `.attempts.jsonl` is a consolidated logical fit trace: some records
are copied, not freshly executed. `recovery_calls.jsonl` distinguishes those
replays from physical optimizer calls; `recovery_execution.json` records actual
evaluation counts. The immutable original timeout remains in `recovery_lineage/`
and in the cumulative charged-attempt index, separate from the logical fit
summary's optimizer-failure census.

## One-case command and admission

```sh
python -B -m experiments.s04b_joint_recovery.driver \
  --admission admission.json --library build/attenuation.so \
  --build-receipt build/build_receipt.json \
  --prior-index previous/science/index.json \
  --prior-review previous_independent_review.json \
  --output /absolute/fresh/science
```

The original binary and essential runtime are required. The first review is the
published `host_batch05_partial_review.json`: its `audit_passed` is true while
its scientific `passed` remains false. Later calls require an accepted new index
with schema `joint_recovery_case_index_v2`. The first successor requires an
explicit live independent review of the recovered pilot. A later failed or
partial attempt blocks continuation; there is no automatic retry switch.

`verify_protocol()` returns `recovery_protocol.json`; `source_identity()` returns
the new package plus every frozen predecessor source hash. A conductor admission
binds `mode: recovery_campaign`, those hashes, `recovery_protocol_sha256`, the
exact `prior_index_sha256` and `prior_review_sha256`, one `case_id` and identical
singleton `case_ids`, the fixed `wall_seconds`, numerical attempt/token
attestation, original native/build hashes, essential runtime, operational run
and config hashes, and expiry. It also requires `independent_review_passed`,
`scheduler_review_passed`, and `external_supervision` true; two threads, one
worker, 6 GiB sampled RSS and 2 GiB host headroom. Root owns the actual lease,
source-review receipts and supervising process. The token is an attestation,
not an authentication or OS resource-isolation mechanism.

The new policy gives all twenty-two remaining broad histories 1,200 seconds and
the eighteen narrow histories 2,520 seconds, each including thirty seconds of
startup/finalization allowance. Its eight fixed host groups start at completed
prefix lengths 40, 41, 46, 51, 56, 61, 69 and 77. The first is the standalone
recovery pilot. Uniform slots, all eight host allowances, known prior outer
overhead and a global finalization reserve fit the unchanged 32-hour aggregate.
This finite allocation is not a prediction that all cases will complete.
The original fixed-slot failure is never relabelled a pass.

A passing child writes `result.json` with `passed: true`,
`status: batch_complete`, one new `cases` entry and `index_sha256`. The index
retains original case, attempt and review bytes, the old allocation transition,
and an explicit `recovery_transition`. All eighty cases are required before the
unchanged scientific aggregator produces `summary.json`; final independent
review and publication acceptance remain separate.

Constructed controls (no saved-history objective calls):

```sh
python -B -m unittest discover -s tests -p test_joint_recovery.py -v
```
