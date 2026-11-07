# Bounded recovery hosts

This is the dated operational wrapper for the separately reviewed recovery of
S5 seed 410518 and the remaining fixed joint-fit roster. It does not change the
scientific fit, starts, solver limits, bounds, quadrature or selection rules.
The original failed attempt, cumulative charge and completed fits remain intact.

The shared deadline is 9 November 2026 at 07:15 UTC. The original 32-hour
allowance remains unchanged. This wrapper is not the fresh-run reader command;
see `docs/reproduction_joint_cpu.md` for that separate interface.

## Fixed schedule

The policy pins the recovery protocol and the reviewed resource calculation.
It contains eight actual hosts with exact starting accepted-case counts
40, 41, 46, 51, 56, 61, 69 and 77. Their case counts are
1, 5, 5, 5, 5, 8, 8 and 3. Every remaining broad/long case has a 1,200-second
slot; dense cases retain 2,520 seconds. No case is reordered, replaced or
selected by its score. An interrupted or partly completed host cannot restart
automatically from its suffix under the same reservation.

Host 1 runs only the interrupted case. Its initial review must be the exact
pinned failure/partial-output audit: `audit_passed: true` does not turn its
`passed: false` scientific result into a success. The resulting automated
saved-output check cannot unlock host 2. Host 2 requires an actual live
independent review of the completed recovery pilot, with its exact index hash.

The full resource derivation is preserved in `evidence/resource_review.json`
and its accompanying report. Each host reserves 1,800 seconds outside its case
slots, including 600 seconds for upload, a 120-second check per child and 30
seconds for host finalization. The controller supervises the host for its
actual allocation minus the upload reserve, rather than granting every host
a generic four-hour window. The standalone pilot's execution window is 2,400
seconds; the largest host's is 13,800 seconds. Clock checks include controller
setup time through the supplied host start time.

## Invocation

The reviewed controller constructs the source-pinned admission and supervises
this command under the shared numerical lease:

```text
python -B -m experiments.s04b_joint_recovery_host.batch   --admission admission.json --prior previous_artifact   --prior-review exact_prior_review.json --config run_config.json   --checker-review checker_source_review.json   --failed-archive original_failure.zip --output fresh_host_directory
```

`--prior` retains `science/index.json` and the original `build/` directory.
`--failed-archive` is the original failed pilot archive required by the frozen
lineage, not a renamed predecessor or a replacement ZIP. All output directories
must be fresh and outside the checkout. The separately reviewed recovery driver
copies and verifies the cumulative case, attempt, review and failure records.
The wrapper preserves original library/build bytes for every child.

Each child runs under the existing process-tree supervisor with two numerical
threads, a sampled 6 GiB RSS cap and 2 GiB host headroom. Its saved result must
name exactly the requested completed case. A separately authored, source-pinned
checker then audits saved outputs before another child can begin. The checker
uses the unchanged scientific arithmetic auditor. Its receipt says
`automated_saved_output_check`, with no claim that a live reviewer has inspected
that child. Final live review remains required.

Any child failure, incomplete result, checker failure, cleanup uncertainty,
changed source/input/runtime identity or exhausted time window stops the host
and retains its current partial evidence. No automatic retry or extra search
opportunity is introduced. Exit zero alone is not scientific acceptance.

## Source controls

```text
python -B -m unittest discover -s tests -p test_joint_recovery_host.py -v
```

These tests use invented native bytes, fake child execution and saved fixture
records. They also check the real frozen policy metadata without evaluating any
historical history. They cover the mandatory live-pilot gate, exact host roster,
actual time windows, source-review pins, checker ordering, failure retention,
and refusal of partial-host automatic restarts.
