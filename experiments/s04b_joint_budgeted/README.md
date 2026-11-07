# Fixed allocations after the failed runtime forecast

This is an explicit operational transition for the existing 80-history joint
nuisance study. The original global forecast and a stratified version both
exceed the available budget; their failures are retained under `evidence/`.
This package does not assert that a replacement forecast passes. It offers each
remaining case a fixed, supervised execution opportunity within the unchanged
32-hour aggregate budget. A case that cannot finish stops the sequence.

The five accepted pilot cases and all their fit, trace, attempt, review and
original training-resume bytes are reused. The scientific code, eight starts
per arm, bounds, optimizer settings, quadrature, gates, exact case order and
native library remain unchanged. The new driver delegates one new case to the
existing scientific `case_run` through the previously reviewed ordered scheduler.
It never repeats a completed case or automatically retries a partial case.

`allocation_protocol.json` fixes 37 remaining narrow/short jobs at 2,520 seconds
and 38 broad/long jobs at 420 seconds. Their 109,200 seconds plus the already
charged 3,321.086780193 seconds fit within 115,200 seconds. These are engineering
allocations informed by input sizes and pilot runtimes, not probabilistic runtime
bounds or an assurance of completion. Unused time does not enlarge later slots.
Each cap includes startup and serialization. Thirty seconds of that cap are an
explicit startup/finalization allowance; the scientific delegate receives at
most the cap minus thirty seconds. The complete process, including imports,
must run under the external supervisor. Sampled RSS termination is not an OS
allocation limit. Killed-process time and unpersisted work remain the conductor's
responsibility; they cannot be removed from the aggregate budget.

Run the constructed controls, which import no scientific evaluator calls and
load no native library:

```text
python -B -m unittest discover -s tests -p test_joint_budgeted_driver.py -v
```

After independent source review and a separate numerical admission:

```text
python -B experiments/s04b_joint_budgeted/driver.py --admission ADMISSION.json --library ORIGINAL_ATTENUATION_LIBRARY --build-receipt ORIGINAL_BUILD.json --prior-index ACCEPTED/index.json --prior-review ACCEPTED_REVIEW.json --output FRESH_EXTERNAL_DIRECTORY
```

The original exact Linux runtime and published-artifact restoration procedure
are documented in [the execution guide](../s04b_joint_execution/EXECUTION.md).
The original `attenuation.so` and build receipt are copied from the accepted
artifact, not rebuilt. This command is only the child: the reviewed supervisor
must enforce the supplied fixed slot, two threads, one worker, 6-GiB sampled
process-tree RSS threshold, host headroom and shared-run expiry. The root
controller supplies the lease-token attestation and source review. It must not
set the old `pilot_projection_review_passed` flag.

The controller calls `verify_protocol()` to obtain the allocation dictionary
and `source_identity()` to obtain repository-relative source hashes. Admissions
use `mode: budgeted_campaign`, the complete `source_sha256` map,
`allocation_protocol_sha256`, exact prior index/review and original native/build
hashes, `independent_review_passed`, `scheduler_review_passed`,
`external_supervision`, a unique `numerical_attempt_id`, `expires_utc`,
`lease_token_sha256`, `threads: 2`, `workers: 1`,
`sampled_process_tree_rss_cap_bytes: 6442450944`, one `case_id`, and its exact
`wall_seconds`. An optional `case_ids` must equal `[case_id]`. Operational run
and configuration fields remain conductor attestations. The first transition
also requires the frozen `transition_review_sha256`.
The allocation protocol pins the unchanged shared-run expiry,
`2026-11-09T07:15:00+00:00`; the child rejects any admission beyond it, and the
supervisor must enforce that same or an earlier expiry.

The first transition validates the original index using the original driver's
actual source identity. It then records a distinct `joint_budgeted_case_index_v2`
schema and new source identity. Its `transition/` directory preserves the old
index, independent review, failed forecast and allocation evidence byte for
byte. Subsequent batches must preserve that directory and the exact accepted
prefix, satisfy independent review of the parent index, and charge all unique
attempts plus the original failure exactly once. No old artifact is relabelled
as having been produced by the new driver.
The original reviews prefix and the complete `training_resume/` directory are
mandatory. Its provenance bytes and evidence are checked against both the frozen
protocol and the first accepted case's recorded resume provenance.

A successful one-case result has `passed: true`, `status: batch_complete`, one
new entry in `cases`, and the hash of `index.json`. This is not full scientific
completion. Full completion requires all 80 accepted cases, the original
scientific checks and final 400-outcome aggregation. Any failure, interruption,
partial checkpoint or late final serialization produces a failed result and
blocks automatic progression. If the supervisor kills the child before it can
write, the retained supervisor/ledger record must be reconciled before any
further admission. No historical case has been executed by this source package's
constructed controls.
