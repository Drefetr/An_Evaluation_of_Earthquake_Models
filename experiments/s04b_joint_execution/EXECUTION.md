# Separately bounded continuation driver

`driver.py` is code for a new operational envelope. It is not evidence that
continuation has run. Independent source/scheduler review, a new shared run,
a current numerical lease and external process-tree supervision are required
before any historical evaluation. The old scientific protocol, original
failed pilot and its incomplete status remain unchanged.

The [operational protocol](operational_protocol.json) pins the original
scientific code/inputs and audited scheduler. It permits at most four hours
of aggregate pilot time, 32 hours of aggregate campaign time, and four hours
per supervised batch, with two numerical threads, one scientific worker,
6 GiB sampled process-tree RSS and 2 GiB host headroom. The original failed
867.911497775 scientific seconds count in both aggregate allowances. These
new allowances do not retroactively pass the old 1,800-second pilot or its
unadmitted four-hour campaign envelope. The external run's earlier expiry
still takes precedence; no allowance is raised automatically.

The driver delegates `case_run`, fitting, fine checks, historical comparisons,
BIC decisions and final aggregation to a private import of the frozen runner.
Only that import's model facade substitutes `ParallelPhase`; the original
process-wide scientific module is never modified. The unchanged feature
constructor supplies its arrays and metadata. The original native binary and
essential runtime identities are required for first-case training reuse and
for all subsequent accepted-index continuation.

Initial invocation after admission:

```text
python -B experiments/s04b_joint_execution/driver.py --admission ADMISSION.json --library ORIGINAL_LIBRARY --build-receipt ORIGINAL_BUILD.json --resume-training FAILED/science --resume-review PARTIAL_REVIEW.json --resume-archive FAILED.zip --output NEW_OUTPUT
```

The first fixed pilot case must reuse its four independently reviewed frozen
training fits; the driver evaluates only its missing test phase. Other pilot
batches each contain one case, in the original fixed pilot order. Subsequent
invocations use an independently accepted index and its review:

```text
python -B experiments/s04b_joint_execution/driver.py --admission ADMISSION.json --library ORIGINAL_LIBRARY --build-receipt ORIGINAL_BUILD.json --prior-index PREVIOUS/index.json --prior-review INDEX_REVIEW.json --output NEW_OUTPUT
```

An index review must contain `passed: true` and the exact `index_sha256`.
The admission binds both that review's bytes and the index. Complete reports
and their attempt traces are checked and copied byte for byte into the new
output. Their fit calls are never repeated. The index is a fixed completed
prefix, so duplicate, reordered, substituted or phase-crossing batches fail.
Every output index is pending independent review; writing it does not grant
acceptance or permission for another batch.

The admission JSON requires:

- `independent_review_passed`, `scheduler_review_passed` and
  `external_supervision`, all true; `phase` is `pilot` or `campaign`.
- `source_sha256` from `driver.source_identity()` and
  `operational_protocol_sha256`; the protocol independently pins frozen code,
  inputs and scheduler bytes.
- `library_sha256`, `build_receipt_sha256`, `numerical_attempt_id`, an unexpired
  `expires_utc`, and `lease_token_sha256` matching the environment value
  `JOINT_NUMERICAL_LEASE_TOKEN`. The token is a conductor attestation, not an
  authenticated security boundary.
- `threads: 2`, `workers: 1`, `sampled_process_tree_rss_cap_bytes: 6442450944`,
  and positive `wall_seconds` within every remaining allowance.
- Exact next-prefix `case_ids` and positive `case_reservations_seconds`, with
  the same key set and total at most `wall_seconds`. Leave explicit startup
  and upload headroom; a reservation equal to the entire child wall allowance
  cannot fit after preflight. The driver stops before a case if its reservation
  no longer fits the remaining child time.
- For index continuation, `prior_index_sha256` and `prior_review_sha256`.
  For the original first case, the unchanged `training_resume` grant described
  in the frozen runner's README, including all five original evidence hashes.
- For campaign batches, `pilot_projection_review_passed: true` and
  `projection_sha256` of `driver.remaining_projection(...)`. This delegates
  the frozen input/plan workload proxy and factor of three to the five accepted
  pilot records. The remaining projection must fit the aggregate remainder,
  and each reservation must cover its corresponding projected case work.

For that projection, the first resumed case's stored `wall_seconds` includes
its original training-attempt time plus the new test phase. The global budget
separately charges the original attempt once and each new batch once; it does
not add the case's already inclusive projection cost a second time.

The supervisor must enforce the same wall/RSS/headroom settings outside the
driver. Native calls are not asynchronously interrupted inside Python; this
is sampled termination, not a hard operating-system allocation guarantee.
Use bounded CI jobs with unconditional artifact upload and enough service
headroom. The conductor must publish/verify each accepted artifact/index
before launching a later batch; this CLI does not upload artifacts itself.

Every admitted batch records actual elapsed time, including failure, in a
hashed attempt receipt. Prior receipts are rechecked and their time summed
with the original failure. A failed partial fit blocks automatic continuation
and requires a separate independently reviewed disposition; the driver never
silently discards/restarts it. Failure before a usable index, or a duplicated
attempt identifier, emits `unindexed_attempt_requires_conductor_accounting`;
the conductor must retain and charge that execution before any new admission.
Do not resume from an older index to omit a failed attempt. The external shared
task ledger remains authoritative for the latest execution history.

`batch_complete` certifies only the requested fixed prefix. All 80 accepted
cases are required before final aggregation can state scientific execution
completion: 320 distinct fit arms, 400 outcomes, 480 historical floor checks
and 400 historical comparison identities. The aggregate preserves the original
score/gating definitions and does not claim global optimization or inference.

Constructed controls, including native full-case serial/scheduled record
equivalence, first training reuse, complete-case reuse and failure/budget
handling, run with:

```text
python -B -m unittest discover -s tests -p test_joint_execution_driver.py -v
```
