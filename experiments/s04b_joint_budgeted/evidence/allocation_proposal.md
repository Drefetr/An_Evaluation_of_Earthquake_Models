# Proposed finite allocation after failed runtime forecast

Status: private proposal only; not implemented, admitted or executed. The old
global projection remains failed. The current 32-hour aggregate and four-hour
batch limits remain unchanged. Scientific source, optimizer recipe, quadrature,
gates, case order and accepted artifacts remain unchanged.

## Why the forecast fails

The retained five-case index is `19f6e808bc992049ced819ce20e69ab4e543e04ccffed04587ffb75d9d2aebf8`.
It charges 3,321.086780193 seconds, including the original failed training time
once. The original forecast requests 4,176,267.2304257513 further seconds against
111,878.913219807 available. Reapplying the same cubic formula separately within
each generating regime still requests 147,116.81131997576 seconds. Neither gate
passes; neither number should be relabelled as feasible.

`run.py:266–273` defines the proxy as a common spatial-nodes/parent ratio times
`128*(targets+1)*(parents+1)^2`. Its maximum elapsed/proxy rate is the sparse S7
pilot and is 57.482892 times the smallest dense-pilot rate. That ratio is not a
machine throughput constant. The C++ attenuation loop (`attenuation.cpp:32–66`)
precomputes time decays and then visits parents once and time nodes once per
spatial node: immigrant-inhibition work is proportional to
`space_nodes*(parents+time_nodes)`, not the triple product. The inclusive arm also
forms the BLAS product in `model.py:123–131`, so it does incur the parent product.
The null arm does not use the spatial attenuation integral. Summing their elapsed
times and applying one cubic rate conflates these distinct costs and fixed
optimizer/serialization work. Function counts also vary across the fixed starts.

Spatial nodes are not proportional to parent counts across regimes: the fine
training grids contain 19,712 nodes for the 12-parent sparse S7 pilot and 28,160
nodes for the 146-parent dense sentinel. The global ratio extrapolates sparse-grid
overhead into dense cases. Training dominates repeated optimization, whereas the
proxy treats training and single test scoring similarly. These facts explain
why the forecast is unsuitable; they do not prove a replacement forecast.

## Finite execution opportunity, not a prediction

Freeze the remaining 75 cases in the existing exact order. Allocate one case
per externally supervised job:

| Input regime | Remaining cases | Fixed job wall cap | Basis |
|---|---:|---:|---|
| Narrow/short S4 and S6 | 37 | 2,520 s | Twice the largest dense pilot case time, rounded upward to a whole minute |
| Broad/long S5 and S7 | 38 | 420 s | Four times the largest broad pilot case time, rounded upward to a whole minute |

The largest dense pilot took 1,249.202341456 seconds. It was selected before fits
as the largest training target-parent product. The largest remaining dense
product is 17,640, below its 20,002. The largest broad pilot took 90.143154298
seconds; the largest remaining broad training product is 700 versus the pilot
maximum 238, motivating a larger allocation multiplier for that group. These
are explicit budget choices informed by input sizes and runtime, not calibrated
tail bounds. There is no assurance that every case will finish.

The slots total `37*2520 + 38*420 = 109200` seconds. Added to every charged prior
attempt, the maximum is 112,521.086780193 seconds, leaving 2,678.913219807 seconds
inside the unchanged 115,200-second campaign cap. Every slot is far below the
14,400-second per-job cap. Each slot includes startup, source/input checks,
scientific work and output writing; reserve its final 30 seconds in the
pre-start feasibility check. The external supervisor still bounds the complete
child lifetime. CI provisioning and queue time must also fit the existing
shared-run expiry; they are not asserted to be included in the scientific index.

At admission, require the sum of all unspent fixed slots plus actual charged
time to fit the aggregate remainder. Do not inflate later caps by silently
redistributing savings. Retain the two-thread, one-worker, 6-GiB sampled RSS,
2-GiB headroom and current run-expiry constraints. A timeout, failed numerical
gate or partial fit remains unresolved and stops progression. No replacement,
automatic retry, discarded work or cap increase is permitted. Any later
disposition requires its own explicit review. Completion still requires all 80
accepted cases and every original scientific check.

## Explicit operational transition and ownership sketch

Use a separate package, `experiments/s04b_joint_budgeted/`, with
`allocation_protocol.json`, `driver.py` and an execution guide, plus
`tests/test_joint_budgeted_driver.py`. Adding files inside the old execution
package would change its glob-based source identity, so leave that package and
both old protocols intact.

The new protocol must pin: the old scientific and execution source manifests;
the accepted five-case index and independent review; original native binary and
build receipt; essential runtime; failed global projection; this saved arithmetic
and its source; and every fixed remaining case/slot. State plainly that this is
allocation after a failed forecast, not passage of the original gate.

For first transition, validate/copy the exact old accepted index using the old
`accepted_index` helper and actual old identity, then create an explicitly new
index schema. Archive the old index and its source metadata unchanged; retain
its source pins under predecessor provenance instead of pretending the new
operational driver created those records. Record the new execution source and
allocation manifest separately. Copy all five case/trace files, attempt receipts,
reviews and original training-resume evidence byte for byte. Later new indexes
require their own exact independent reviews and complete fixed-prefix/charged-
attempt validation. The transition archive itself must remain hash-bound and
copied across later batches.

Reuse the unchanged `verify_case`, `charged`, `copy_bound`,
`runner_with_scheduler`, `fit_census` and final scientific aggregation helpers
where appropriate. Do not monkeypatch the old projection or claim that its
`pilot_projection_review_passed` gate is true. Only the new driver selects the
explicit allocation gate. Exactly one next case is delegated to the same
scientific `case_run`; every completed fit remains reused rather than repeated.

Root's minimal controller change is a separate named stage, such as
`joint-budgeted-case`: download the exact accepted predecessor artifact, reuse
the original native/build bytes, pin the new protocol/source review, supply one
next case and its frozen wall cap, and invoke the new driver under the unchanged
Linux supervisor. Existing stages remain unchanged. Keep `science/**`, admission,
transition evidence, index and supervisor outputs in artifact upload. The
workflow adds the new constructed driver controls to the existing scheduler and
process-lifetime preflight.

Proposed CLI (the same form for the one-time transition and subsequent indexes):

```text
python -B experiments/s04b_joint_budgeted/driver.py --admission ADMISSION.json --library ORIGINAL_COMPONENT_LIBRARY --build-receipt ORIGINAL_BUILD.json --prior-index ACCEPTED/index.json --prior-review ACCEPTED_REVIEW.json --output FRESH_EXTERNAL_DIRECTORY
```

The admission binds `mode: budgeted_campaign`, `independent_review_passed`,
`scheduler_review_passed`, `external_supervision`, new `source_sha256`,
`allocation_protocol_sha256`, `prior_index_sha256`, `prior_review_sha256`,
`library_sha256`, `build_receipt_sha256`, unique `numerical_attempt_id`,
`expires_utc`, `lease_token_sha256`, `threads: 2`, `workers: 1`,
`sampled_process_tree_rss_cap_bytes: 6442450944`, a single `case_id` and its exact
`wall_seconds` from the fixed allocation roster. The same existing environment
lease-token attestation is sufficient. The first old-schema input additionally
requires the separately reviewed `transition_review_sha256`; its allowed index,
old source, failed-projection and runtime/native pins are already frozen in the
new allocation protocol. There is no `pilot_projection_review_passed: true` flag.
The controller must not infer the new mode from the old phase automatically.

Before execution, independent review should test exact transition/case/trace
reuse, rejection of changed source/runtime/native, ordering and duplicate
cases, cumulative/all-remaining-slot accounting, wrong slot caps, failure/partial
retention, no repetition of pilot fits, and truthful all-80 completion status.
No scientific numerical controls need be weakened or substituted.

Evidence: `joint_runtime_projection_analysis.json` contains all 80 input hashes,
five report hashes/dimensions/function counts, both failed projections, the
75-case fixed slot roster and full budget arithmetic. Its analysis imports no
likelihood evaluator, optimizer or native library. No outcome sign or fitted
score was used to choose a slot or order.
