# Independent recovery-resource review

**The resource design passes for a separately recorded 1,200-second cap for every remaining broad/long case, with dense-case caps unchanged at 2,520 seconds.** A standalone recovery pilot must pass independent review before later cases run. This is a finite allocation, not a completion guarantee or approval of implementation that has not yet been reviewed. The shared 32-hour allowance, 9 November 2026 07:15 UTC deadline, scientific recipe, and historical source/allocation bytes remain unchanged. No model, optimizer or native code ran during this review.

The failed index contains 40 completed cases and 41 uniquely identified charged attempts. Its 21,663.863217721 seconds reconcile exactly to the original failure plus all subsequent attempts. The latest failed attempt, 390.819406987 seconds, is already included. Preserve it once; neither subtract it nor add it twice. Reserve a new complete 1,200-second slot for the partial case without crediting its saved work back to the budget.

The exact remaining order is:

- S5 seeds 410518?410520: three broad cases, starting with the partial case.
- S6 seeds 410602?410604 and 410606?410620: eighteen dense cases.
- S7 seeds 410702?410720: nineteen broad cases.

All 40 exact IDs, original input identities, and cap assignments are specified in result.json. No ordering or eligibility decision uses a gain or other scientific outcome.

| Budget component | Seconds |
|---|---:|
| Indexed scientific charge, including the latest failure | 21,663.863217721 |
| Known, deduplicated outer-supervisor wall time | 21,714.885916780 |
| Observed outer-minus-indexed difference | 51.022699059 |
| Remaining case slots: 22 ? 1,200 + 18 ? 2,520 | 71,760 |
| Eight full host overhead reserves: 8 ? 1,800 | 14,400 |
| Additional finalization/publication reserve | 1,800 |
| Known outer time plus all future reserves | 109,674.885916780 |
| Remaining contingency within 115,200 seconds | 5,525.114083220 |

The 13 disjoint outer records cover the original failure, five resumed pilots, two single-case budgeted/public-reader executions, and five host batches. Nested supervisor copies and their child durations are not counted again. CI checkout, dependency installation, artifact transfers and any earlier unsupervised setup/build time are not completely measured by these records. The contingency must cover any additional time attributed to the campaign; these unmeasured costs are not asserted to be zero. The index itself measures scientific module-entry/persistence time, not every workflow operation.

## Host grouping and mandatory pilot

Preserve seven logical groups with case counts 6, 5, 5, 5, 8, 8, 3. Split the first group into a standalone one-case recovery pilot and its five-case remainder, giving these eight actual hosts:

| Host | Cases | Case-slot seconds | Role |
|---|---:|---:|---|
| 1 | 1 | 1,200 | Recover only S5 seed 410518 |
| 2 | 5 | 9,960 | Remaining first logical group, after pilot audit |
| 3 | 5 | 12,600 | Second logical group |
| 4 | 5 | 12,600 | Third logical group |
| 5 | 5 | 12,600 | Fourth logical group |
| 6 | 8 | 9,600 | Fifth logical group |
| 7 | 8 | 9,600 | Sixth logical group |
| 8 | 3 | 3,600 | Seventh logical group |

Every host has at most 12,600 case-slot seconds plus the unchanged 1,800-second overhead reserve under a 14,400-second outer cap. The reserve includes a 120-second checker for each case, 600 seconds for upload and 30 seconds for host finalization. At most eight cases leaves at least 210 seconds of preparation margin. Greedy grouping by case-slot time alone would produce a ten-case broad group: its checker/upload/finalization maxima exceed 1,800 seconds, so that grouping is rejected. Each case retains its 30-second startup/finalization allowance, leaving scientific reservations of 1,170 or 2,490 seconds.

No later case may launch until independent review accepts the actual standalone recovery output, its scientific gates, unchanged completed cases and starts, and retained failure/accounting lineage. After acceptance, skip the pilot's accepted prefix when executing the first group's remainder; never rerun it. All host and child launches must still fit their complete reserved windows before the unchanged shared deadline. Calendar slack at this review is recorded in result.json; queue delay is not assumed zero.

The 1,800-second broad alternative would require 84,960 future case-slot seconds. It fits scientific-only accounting, but indexed charge plus seven full host reserves would already be 119,223.863217721 seconds. It fails the conservative all-wall gate even before a separate recovery-pilot host. The accepted 1,200-second plan does not guarantee that any difficult solver invocation finishes.

## Recovery semantics and required implementation evidence

The partial record retains completed null and LI arms. Its trace retains immigrant starts 0?4, the start-5 L-BFGS-B arithmetic failure, and the start-5 Powell timeout after 2,040 completed objective evaluations. The inclusive arm has not run. The last point is not full Powell state: direction, line-search and continuation state are absent. Starting from that point with fresh limits would alter the search procedure.

An admissible administrative replay restarts only the unfinished Powell invocation from its exact original initial point, with the same options, bounds, runtime and native library, and the original 400-iteration/5,000-evaluation limits. This is not exact internal-state resume. Repeated evaluations of that unfinished deterministic trajectory remain charged; the original timeout stays recorded. They do not create an additional candidate or start. The implementation must establish:

1. A separately labelled, reviewed operational transition preserves the old allocation, source files, failed index/trace and all accepted case records. The old driver correctly rejects partial predecessors; do not relabel the failure as a pass.
2. Both completed arms and immigrant starts 0?4 are reused exactly. The completed L-BFGS-B failure at start 5 is preserved without repeating it. The resumed Powell invocation links to that same logical model/start/method.
3. The interrupted last point cannot enter the candidate set. Reconstruct the ordinary eight-start candidate set and original tie rule without duplicate or competing completed solutions.
4. Check the reproduced 2,040th completed objective evaluation, and the subsequent failed input where exposed, against retained checkpoint evidence before accepting an extended invocation. If exact equivalence is established another way, it needs a specific independent review. Any mismatch blocks continuation rather than triggering a tolerance change.
5. Execute only missing immigrant starts 6?7 and the not-run inclusive arm afterward. All original training, selected-state, quadrature, floor, BIC and test-order gates remain unchanged.
6. Carry all 41 prior attempt records and the original failure charge unchanged, then append the new recovery attempt. Enforce the exact remaining roster and uniform caps without outcome-based selection or cap redistribution.
7. Preserve two threads, one numerical job, sampled 6 GiB process-tree RSS and 2 GiB host headroom. Every timeout, unresolved start, numerical failure or cleanup uncertainty stops the campaign; no automatic retry.
8. Require the standalone recovery pilot's independent output acceptance before later hosts. Only all 80 genuinely accepted histories can support the final 400 outcomes and 480 floor-check summary.

The scientific protocol's original timeout policy stops without automatic recovery. The proposed explicit reviewed administrative transition retains that fact; it does not erase or reinterpret the failure. Exact reviewed hashes, input/output identities, accounting records and complete group memberships are in result.json.

Source references: `experiments/s04b_joint_budgeted/driver.py` (accepted_index, allocation, persist_attempt, run); `experiments/s04b_joint_host_batch/batch.py` (timing and supervised child gates); `experiments/s04b_joint_nuisance/fit.py` (starts, method loop, candidate selection); and the unchanged scientific `protocol.json`.
