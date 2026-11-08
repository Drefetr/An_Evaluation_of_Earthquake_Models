# Retained wall failure and untouched continuation

This operational bridge retains the exact failed host-four archive and adds one
metadata-only `wall_time_failure` disposition for `S6_narrow_short_total_seed410615`.
The original fifty-five index records remain unchanged. The failed history has
no new held-out outcomes. Its raw `TimeoutError` and secondary wrapper error stay
in their original files; it is neither a finite solver-cap unknown nor a loss.

After independent source review, the metadata command is:

```sh
python -B -m experiments.s04b_wall_failure_continuation.transition --output /fresh/seal
```

It writes `index.json` and `result.json` and does not issue an execution admission
or independent acceptance. A separate live transition review must bind the sealed
index and original raw archive. The raw archive contains fifty-five records; it
does not contain the separately published fifty-six-record sealed index.

The source-reviewed author continuation uses:

```sh
python -B scripts/run_joint_wall_failure_continuation.py --admission /public/admission.json --output /fresh/output
```

Only unchanged fixed hosts five through eight are eligible. The private facade
reuses the frozen host loop and original numerical child command; its expanded
operational source map is distinct from the unchanged scientific driver map.
Each child requires the independent saved-output checker before progression;
each new host requires a live review. Any new technical failure stops. Neither
615 nor the permanent optimizer unknown 410518 can be retried by this route.

Host-five admission supplies `sealed_predecessor` with separate public path/hash
references for `index`, `review`, `raw_archive`, `raw_review`, plus the original
`raw_index_member` and `raw_index_sha256`. Later hosts use the preceding accepted
archive/index and `prior_host_overhead`: its execution ID, exact audited overhead,
review reference and archive reference. Each overhead is charged once against
the existing reservation. Nested science clocks are retained but not added again.
The known accounting baseline preserves the failed case's actual over-cap clock.

The workflow's `[wall-failure-continuation]` marker shares the existing active
numerical concurrency group. Original deadline, runtime, vendored native library,
memory/thread limits and case/host slots remain mandatory. This dated author
continuation is not the public reader's fresh-local fitting command.

Constructed controls (no native or model calls):

```sh
python -B -m unittest tests.test_joint_wall_failure_continuation tests.test_joint_wall_failure_launcher -v
```
