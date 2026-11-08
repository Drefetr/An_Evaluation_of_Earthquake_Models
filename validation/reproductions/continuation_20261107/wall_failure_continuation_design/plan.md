# Retain the wall failure; continue only untouched fixed hosts

Design only, against ROOT `1755fa5c7de5804fe436979aa434ce271ba43c19`.
No numerical source, input, fitted state or public file was changed or executed.

## Decision and fixed boundary

Use a small operational bridge around the existing frozen host loop. Seal one
explicit `wall_time_failure` record for `S6_narrow_short_total_seed410615` after
the exact accepted prefix; continue only original hosts five through eight. This
does not retry or resume that case, extend its cap, substitute a partial state,
or retry permanent unknown `S5_broad_long_imm_seed410518`. Future technical
failures still stop and require a separate decision; this is not automatic
failure-to-continuation handling.

C's terminal receipt `joint_exposure_refinement_host04_output_review.json`, SHA
`0ea5512e94d1c9bb2e0b42fca052621fd0f1072588685d970ed92b0de506e413`, accepts the
failure audit and four completed additions, not host execution success. The saved
index contains fifty-five records: fifty-four complete, the original optimizer
unknown, and two hundred seventy computed outcomes. Its bytes are retained.
The new sealed operational index appends only case 615: fifty-six processed,
fifty-four complete, one optimizer unknown, one wall failure and twenty-four
untouched. No new outcomes are added.

The exact public evidence is now retained at commit
`22278421ad83935dbe61641af5ff14304bb6efbc`, under
`validation/reproductions/joint_nuisance_20261107/continuation/`:
`exposure_refinement_host04_wall_failure.zip` (SHA
`d95f7321ca76c4f4a5044c4ad27ae967154511243c72daf13e32fa5b88a7be87`)
and `exposure_refinement_host04_wall_failure_review.json` (the C receipt above).
Implementation must bind these public paths, not the private downloaded copy.

The raw case report's `status: unknown` is accompanied by `TimeoutError: Joint
experiment deadline`; it is not evidence of a finite solver-cap unknown. The raw
driver result remains `technical_failure`, `passed: false`, `scientific_passed:
false`, `handled: false`, `disposition_valid: false`. Its secondary `ValueError:
Case optimizer records differ from trace` remains visible. No failed bytes or
flags are rewritten, even temporarily to pass an older checker.

## One sealed metadata transition

Add `experiments/s04b_wall_failure_continuation/{__init__.py,protocol.json,
transition.py,host.py}` and focused constructed tests. The small operational
protocol pins the unchanged exposure-refinement protocol/source graph, exact
host-four ZIP, C review, accepted prefix index, failed case/result/trace/log and
supervisor hashes. It identifies only this failure and the original remaining
host groups/caps. No new scientific protocol, general retry list or manifest
layer is needed.

`transition.py` provides a metadata-only sealing command. It verifies the exact
fifty-five records/attempts and C's accepted case IDs 611–614; preserves every old
record, including public-reader producer identity; appends the one audited failed
attempt and one compact failure record. New schema:
`joint_exposure_refinement_operational_index_v1`, with a hash-bound
`operational_continuation` reference. The failed record has:

- `disposition: wall_time_failure`, `scientific_passed: false`, `outcomes: []`;
- `reason_code: scientific_wall_limit`, exact case/regime/input identity and
  original host execution/member locators, plus the independent failure review;
- original primary/secondary errors, raw disposition/status, allocation and
  measured clocks, preserved as evidence rather than successful checks;
- completed arms null/LI/immigrant, trace-only total starts zero through two,
  interrupted total L-BFGS start three, later starts unrun, no held-out phase;
- actual twenty-nine physical attempts, twenty-seven returns and two exceptions,
  copied from C's audited census; no invented selected total candidate or zero
  failure counts for absent results.

The sealing receipt states `failure_accounting_valid: true` and
`scientific_execution_passed: false`; a separate live review accepts the exact
sealed index for continuation. C's raw failure receipt remains `passed: false`.
The transition itself cannot authorize execution. Its review must explicitly
bind both the raw artifact and sealed index, not relabel the failed host passed.

The new launcher must not use the old `prepare()` assumption that the predecessor
index is always `prior/host/index.json` inside `prior_archive`. The raw host-four
ZIP contains the fifty-five-record index; the sealed public JSON contains
fifty-six. Host-five admission therefore has an explicit `sealed_predecessor`
object with `index` and `review` public path/hash references, `raw_archive` and
`raw_review` references, and `raw_index_member`/`raw_index_sha256`. The launcher
checks all of them and passes the separate sealed JSON as `--prior-index` and
its transition review as `--prior-review`; it never overwrites the extracted raw
index. The original ZIP is not claimed to contain the sealed index.

The sealing review uses `review_kind: live_operational_failure_transition_review`,
has no new `execution_id` or fabricated execution result, and binds the exact
sealed index, raw archive/index, original failure review and bridge policy. The
first new candidate uses predecessor kind `sealed_failure_transition`, references
that separate index/review, and has `archive_sha256: null` plus an explicit
`raw_failure_archive` reference. Within-host and later-host predecessors retain
their ordinary actual index/archive semantics. This avoids a second apparent
live execution review for host four and ambiguous final-registry discovery.
Keep seal output hashes in its review/admission, not inside the policy that the
sealed output itself pins, so there is no hash cycle.

## Unchanged scientific execution with explicit orchestration identity

`host.py` privately wraps the existing `experiments.s04b_exposure_refinement.host.run`
code object, using the already-established private-facade pattern. No global
monkeypatch or copied numerical/group loop. The only replaced metadata functions
are `source_identity`, `next_cases`, `counts`, `budget`, `append_candidate`,
source-review and receipt validation. The private `source_identity` returns the
expanded actual orchestration map required by the frozen loop's admission check;
it does not replace the unchanged scientific driver's map. Reuse the original append implementation through a private function
namespace for its counts/budget calls, then explicitly emit the new index schema.
The original case-driver argv, admission, supervision, timing, loop order and
numerical driver remain unchanged.

Host five accepts only the exact independently reviewed sealed prefix. Hosts six
through eight require the normal genuine live audit of the immediately preceding
host; within-host checks remain automated and honestly labelled. Admission and
output carry the new operational host source map and continuation-policy hash;
`scientific_source_sha256` stays the actual unchanged case-driver map. Do not claim
the bridge ran as the frozen host or rewrite scientific source identities. Scope
the new bridge to these remaining groups; reject 615, 410518, prior completed IDs,
wrong host boundaries, duplicated attempts and different slots before launch.

Add `experiments/s04b_wall_failure_continuation_audit/check.py` and tests. It reuses
the existing `exposure_refinement_audit.check.inspect_current` for every new
complete or finite-cap-unknown child, with unchanged math, source, native, runtime,
phase and resource checks. It independently owns only the sealed-failure identity,
exact-prefix transition, new counts/budget and source-review attribution. It must
never feed the wall failure into `inspect_unknown` or the full-case trace/fit
correspondence checker. The old five-file mathematical checker remains pinned.
Root's dedicated launcher/admission needs only an explicit new host/checker source
gate, the sealed-predecessor input above, and dispatch target, retaining the same
CLI/resource/concurrency envelope. Use a new
`scripts/run_joint_wall_failure_continuation.py` and corresponding workflow;
do not edit the earlier launcher that is also pinned in the public-reader graph.

## Resource charge: include the failure, do not sum nested clocks

C measured whole workflow time as 5569.6788442 seconds. Completed child outer
times 2989.7187417619998 are already in the prefix. The missing charge is therefore
2579.9601024380002: failed cleanup-inclusive outer 2490.5780963780003 plus host
overhead 89.3820060599999. The failed science clock 2490.0270934919995 is diagnostic
accounting nested inside that outer time, not another charge. Its excess over the
2490 cap is retained as a failure, never rounded away or treated as a new allowance.
Do not additionally add the host supervisor's nested 5485.350758648 seconds.

Use C's known cumulative 37761.34182158000334 seconds as the sealed accounting
baseline. This already includes the failed child and host-four overhead exactly
once, and earlier known workflow overhead 297.50677369900034. Keep the original
unmeasured historical setup caveat. There is no new all-wall exactness claim.
The remaining original case slots total 35400 seconds. Keep the original 14400
host-overhead reservation conservatively: its known consumed part is
386.88877975900024, so unconsumed reserve is 14013.11122024099976. Retain the
1800 global finalization reserve. The conservative upper bound is
88974.45304182100310, below 115200 by 26225.54695817899690 seconds. This retains
unused past reserves rather than expanding any future host. C's alternative
binary-index reconciliation differs only by its separately retained tiny rounding
delta; safety decisions should use Decimal strings from the accepted audit.

The new budget function starts from this sealed known baseline, adds only future
child outer times, consumes their unchanged remaining slots, and records later
audited workflow overhead once against the existing reserve. Bind each overhead
record to a unique audited host execution ID and workflow/review hashes; reject
duplicates, replace reserved overhead with its actual charge once, and never
add nested child science separately. Future failure
still stops. The fixed failed-attempt row is validated by exact evidence rather
than the successful-case `seconds <= cap` predicate. Do not relax that predicate
for any new child. Shared deadline, numerical concurrency, memory, thread and
per-host clocks remain unchanged; admission must still have actual clock room.

Remaining groups are unchanged: host five 616–620 (12600 child / 14400 whole-host
seconds); six 410702–410709 and seven 410710–410717 (9600 / 11400 each); eight
410718–410720 (3600 / 5400). Original scientific caps, not these group sums, still
govern every fit: dense S6 remains 2490 scientific / 2520 outer, and broad S7
remains 1170 / 1200. This is a finite envelope, not a completion forecast.

## Minimal reporting additions

Keep `render_joint_nuisance_results.py` and the original all-success gate unchanged.
Add an explicit operational-continuation reference to the disposition registry.
In `build_joint_disposition_report.py`, extend `amendment_sources`,
`registry_sources`, `resolve_case` and the build loop only for the exact sealed
policy. The failed host supplies complete cases 611–614 through C's accepted
prefix; 615 is resolved separately from its audited failure evidence. It must not
pass `amended_computation`, full-case trace matching or successful supervision.
All ordinary old/amended/public-reader records keep their current checks.

Add the third disposition and a separate `failure_census`; do not append it to
optimizer `unknown_census`. Count wall failures explicitly, keep
`unresolved_technical_failures` nonzero, and distinguish audited terminal accounting
from successful execution. Emit exactly five unavailable slots for 615, with null
scores/gains/wins/intervals and the two original historical comparators unchanged.
The full original twenty-history requirement still controls every regime/procedure
summary; no complete-case mean, denominator change or counting failure as a loss.
Regime S6 comparisons are unavailable while this history is unresolved.

`render_joint_disposition_results.py`, final independent reporting acceptance,
`website/build_findings.py` and `website/findings.html` need additive failure-count
labels and preserved nulls. In particular, the website currently equates
scientific_unknown_histories with all unavailable histories; that headline must
separate optimizer unknowns and technical wall failures. The private final-registry
assembler must accept only the exact reviewed transition/failure registry branch,
not arbitrary `passed: false` hosts. Original report paths and historical metadata
remain; no scientific success or old all-success acceptance is produced.

## Required review/controls before admission

Test an invented exact seal and one next-child path through the real frozen
runner/host assembly boundary and independent checker, substituting only invented
numerical results. Test prior-record preservation; failure/unknown/zero relabeling;
wrong archive/result/trace; duplicate or omitted failed charge; over-cap future
child; retry of 615 or 410518; wrong fixed group; missing live boundary audit;
and actual new orchestration source-map omission. New failures must stop.

Reporting controls need the mixed original/reader/amended prefix plus one wall
failure, exactly four hundred planned slots, separate failure census and unavailable
full-regime statistics, including repinned malformed-evidence counterexamples.
Re-run existing successful and optimizer-unknown controls unchanged. No new fits
are needed to validate this metadata bridge. Require D design acceptance, separate
source acceptance of producer/checker/launcher, and an independent live review of
the sealed prefix before root issues a numerical lease for host five.
