# Minimal public amended CPU reader

Add one public single-case fresh-fit entry point, `scripts/fit_joint_refined_cpu.py`, with focused tests and a short reader guide. Keep the active pilot, original numerical files, dated case driver/host/protocol and their acceptance records unchanged. This proposal is source-only; nothing described below has been implemented or executed.

## Public interface

After the already documented clone, Python3.13 virtualenv and `pip install -r requirements-cpu.txt`, a reader could run:

```sh
python -B scripts/fit_joint_refined_cpu.py fit \
  --case-id S6_narrow_short_total_seed410604 \
  --output ../reader-refined-410604 \
  --wall-seconds 2520 --rss-mib 6144 --headroom-mib 2048
```

This is a proposed command, not an existing command. It fits all four original arms on one supplied history, with all original starts, boxes, solver caps, selection, floor, fresh-return and held-out checks. The only numerical amendment is the reviewed optimizer-callback refinement. It generates no histories and imports no author prefix or partial candidate. Explicit selection is restricted to the original pinned80 histories; one-case execution avoids building another campaign scheduler. No repeat of a completed author fit is authorized by this design or needed for acceptance. Public readers' independent fresh studies remain separate from the authors' campaign.

Require finite positive local resource limits, a fresh external output directory and two numerical threads. Build the original attenuation.cpp through `engine.cpu_build.build_shared`, with strict compiler options, inside the existing process-tree supervisor. Record source/input/compiler/library/runtime identities and fail honestly on the existing numerical checks. A fresh local monotonic deadline includes setup/build; retain a finalization allowance without increasing optimizer limits. It has no dependency on the authors' expiry, lease, private directory or live-agent approval. Local integrity checks must explicitly state that they are not independent scientific acceptance.

A `--plan-only` preflight is useful but does not prove an actual fit. An optional verified native/build pair can avoid rebuilding during the author demonstration; ordinary fresh use builds locally. No macOS/GPU claim follows from LinuxCPU execution.

## Reuse numerical code directly

The new script needs one `execute_case(...)` helper used by both ordinary fresh mode and the optional author-envelope demonstration. The assembly is already present in case_driver.py:117-157:

1. Verify pinned scientific/amendment sources before imports; use the existing metadata-only amendment `verify_protocol()` and `legacy.verify_protocol()` for source/protocol checks, without calling the dated admission in ordinary fresh mode. Verify the exact supplied case through frozen.verify_inputs.
2. Construct `Adapter(science, output, partial=None, trace=None)` from the frozen amendment, `model.archived()`, and `model.Native(library)`.
3. With `threadpool_limits(2)` and `legacy.OrderedChunkScheduler()`, obtain `legacy.runner_with_scheduler(scheduler)`. Its private module/facade avoids mutating the process-wide model.
4. Apply the same four existing assembly hooks: wrap the private phase factory with adapter.wrap_phase; set runner.fit_arm and runner.fine_check to the existing adapter methods; delegate historical_floor through adapter.historical_floor. Then call the original runner.case_run once with resume=None.
5. Preserve the durable NumPy-aware case serialization, original attempt trace, refinement_events.jsonl, execution_calls.jsonl and empty reuse map. Reuse the original remaining case_driver.classify and legacy.verify_case for complete/finite-cap-unknown classification. Technical failures remain failures; unknowns have no fabricated test outcomes.

No likelihood, gradient, optimization loop, recurrence or quadrature code is copied. No partial_fit path is used. Only the short assembly/output orchestration is new. Fresh/floor/fine-check/held-out calls stay outside the optimizer callback context because the existing Adapter enforces that boundary. The new result identifies the numerical version, actual entrypoint and all imported source hashes; it must not claim the old dated case driver executed.

## Prove it on the next needed untouched history without duplicate fitting

If the current partial pilot succeeds and its independent audit passes, reserve410604 as the next untouched author case. Confirm its actual pending status at admission time; if already run, choose the next untouched original-roster history before execution, never refit a completed case for demonstration.

Use the very same new execute_case helper in the public CLI, with an optional genuine `--execution-record` and verified original native/build pair. This optional mode can reuse the current case_driver.admission validation as a function: the record carries the actual new entrypoint/source map, while all original author case, lease, runtime, binary, expiry and cap comparisons still apply. It is not an ordinary-reader prerequisite and cannot extend the author run.

For410604 the original author reservation remains2490 process-clock scientific seconds and2520 cleanup-inclusive supervised seconds, within the unchanged global32-hour allowance and Nov9 shared expiry. Record the whole author attempt exactly once; compile or reuse work is included honestly in its declared clocks. The author supervisor and independent checker remain mandatory, with zero prior fits reused and no repeat of43 accepted histories or410518. A technical failure/unknown is retained under the existing distinction; a successful CLI alone is not scientific acceptance.

There is one necessary integration gate: the existing refinement host/checker bind prior/current scientific_source_sha256 exactly. A new entrypoint cannot be inserted as though the old driver executed. Before using410604, source review must approve a narrow explicit reader-entrypoint transition and its exact source map in the outer integration and independent audit. Preserve the old numerical map and prior prefix byte-for-byte; bind the added entrypoint and reviewer record separately. Never accept blank maps, strip the reader from actual execution provenance, or weaken existing numerical checks. The public result can retain the same case/trace/amendment evidence layout, but its entrypoint identity must remain visible through the compact index and final report. This is an operational producer-identity amendment, not a new scientific recipe or an admission bypass. Do not modify the active pilot source or its frozen evidence.

The smallest implementation scope is the new reader script/tests/guide plus that narrowly reviewed one-case outer dispatch/index-identity integration and corresponding independent-checker acceptance. Do not add a second campaign scheduler, new authorization framework or duplicate evaluator. If the source transition cannot be reviewed before410604 must run, leave the author chain unchanged; demonstrate the reader on the next still-untouched history under a later explicit allocation. Do not silently relabel a replay as fresh-fit acceptance.

## Acceptance and useful controls

Source/constructed checks should show: fresh preflight succeeds with a clock after the shared expiry while author-envelope mode still rejects expiry; the same invented case produces identical original case outputs with the same adapter through both wrappers; complete/finite-cap-unknown/technical failure remain distinct; no completed-prefix or partial-resume loading in fresh mode; an original coarse exception outside an optimizer callback stays an exception; source/native/input mismatches and nonfinite limits reject before work; all logs/census and NumPy/nonfinite diagnostic serialization survive failure. Use the existing adapter controls rather than reimplement its mathematical tests.

Then one actual untouched-history Linux execution of this public command can establish a real amended fresh-case fit route, including source/native/runtime/caps and independent saved-output audit. If the demonstration uses the original native binary, report that fact: it proves the entrypoint and actual fit, while fresh local compilation is supported by the existing portable builder/source controls and needs its own explicit build evidence before claiming that combined path was exercised. Prefer building the exact source in the same bounded host if it reproduces the required author binary; otherwise retain the original binary rather than altering the author's native identity.

A known-failure-point or selected-state diagnostic is a valid smaller numerical demonstration of the amendment/scores, with no new optimizer call. It cannot establish actual fresh-fit execution. If only that route is run, the remaining acceptance step is still one source-reviewed public amended fresh fit on a genuinely untouched case under the original author constraints (or a separately declared reader study). Neither scope inherits the old Task3 acceptance automatically. No all80 fresh-run claim follows from a single-case demonstration.
