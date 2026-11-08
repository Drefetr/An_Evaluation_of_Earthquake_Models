# Bounded optimizer exposure refinement

This is a separately versioned numerical amendment to the joint-nuisance
experiment. It does not modify the archived model, native library, fitter,
scientific protocol, or earlier results. Its source review and actual execution
evidence are separate from the earlier Task 3 Linux CPU reader acceptance.

During an actual training optimizer callback only, the adapter recognizes the
original evaluator's finite negative-full-exposure exception. At the identical
parameter vector it may use the original order-16 value **and** gradient if the
fine exposure is nonnegative and the original score and projected-gradient
quadrature tolerances both pass. Both packets, their comparison, timings, and
callback identity are retained. Other errors, floor evaluations, fresh returned
states, selected-state checks, and held-out scoring retain the original rules.
There is no clipping, renormalization, changed solver budget, or forced retry.

The first standalone case is the partial S6 history ending in seed410603.
Its three complete fit/check objects and four successful total-arm starts are
imported exactly from the pinned failed artifact. The new loop executes only
total-arm starts4–7 with the original bounds, options, primary/Powell sequence,
fresh checks, and selection rule. The previous failed start4 attempts remain
linked evidence. The 43 accepted complete histories are retained, and the
permanent seed410518 scientific unknown is never retried. Only the 35 untouched
histories follow a successfully completed and independently reviewed partial
pilot. A finite capped solver return can remain a scientific unknown; a technical
failure stops the host. No incomplete matrix is declared full scientific success.

## CPU execution

The dated continuation requires the exact Linux x86-64 native binary and runtime
recorded in `protocol.json`: CPython3.13.18, NumPy2.2.6, SciPy1.15.3, and the pinned
Python, extension, and OpenBLAS bytes. The original shared library and build
receipt are extracted from a public retained execution archive; no replacement
build, CUDA, MSVC, private directory, or GitHub credential is used. Version strings
alone do not replace the byte/runtime checks. The existing fresh-reader commands
remain separate; their earlier acceptance does not certify this amendment.

The reviewed launcher prepares the native files and public predecessor, creates
the child admissions, and starts the supervisor. With an actual source-reviewed
execution record and a fresh output directory outside the checkout:

```bash
export CONTINUATION_HOST_STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
python -B scripts/run_joint_exposure_refinement.py \
  --admission /tmp/reviewed-exposure-host.json \
  --output /tmp/exposure-host-01
```

The host's direct interface is also available:

```text
python -B -m experiments.s04b_exposure_refinement.host
  --admission FILE --output FRESH --prior-index FILE --prior-review FILE
  --config FILE --source-review FILE --checker-review FILE
  --library FILE --build-receipt FILE [--failed-prior EXTRACTED_ARTIFACT]
```

The first pilot retains the original cumulative case limits: at most1776 new
process-clock seconds and1806 new cleanup-inclusive supervised seconds, with the
prior failed execution charged once. Later cases keep their original slots.
Every host uses two threads, one case at a time, a6GiB process-tree memory cap,
the unchanged shared32-hour allocation, and the original expiry. These are dated
continuation limits, not a permanent fresh-run expiry or an unbounded refitting
interface. Every host boundary requires a live saved-output review; automated
child checks are labelled separately and never claim live agent acceptance.

Outputs retain the original case and logical attempt trace, a numerical-amendment
identity, `reuse_map.json`, `refinement_events.jsonl`, `execution_calls.jsonl`,
physical evaluation/optimizer counts, the supervisor receipt, and a compact
source-bound disposition index. Previous archives are linked rather than nested
into every output. Rejected nonfinite diagnostic operands use explicit JSON tags;
they never become accepted objective values.

Constructed controls require no native library or historical fit:

```bash
python -B -m unittest tests.test_joint_exposure_refinement \
  tests.test_joint_exposure_refinement_host
```
