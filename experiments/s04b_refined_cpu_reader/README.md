# Public amended Linux CPU fit

This entry point fits one supplied history using the explicitly versioned
`joint_exposure_refinement_v1` procedure. It calls the existing numerical
adapter, original fitter and likelihood, and reviewed ordered CPU scheduler.
It generates no histories and imports no author prefix, partial fit or selected
candidate. All original starts, solver caps, floor/fresh/selected-state checks
and held-out checks remain in force.

Use Linux x86-64, CPython 3.13 and the pinned CPU requirements. The default route
extracts the audited native library and original build receipt automatically
from the hash-pinned public ZIP. It needs no compiler, MSVC, CUDA, GitHub token,
private directory or manual native-library environment variable. This scope is
a bundled Linux CPU binary, not a fresh compilation or macOS/GPU equivalence.

```sh
git clone https://github.com/Drefetr/An_Evaluation_of_Earthquake_Models.git
cd An_Evaluation_of_Earthquake_Models
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-cpu.txt
python -B scripts/fit_joint_refined_cpu.py fit \
  --case-id S6_narrow_short_total_seed410606 \
  --output ../reader-refined-410606 \
  --wall-seconds 2520 --rss-mib 6144 --headroom-mib 2048
```

Choose an explicit history from `profile.json` and a new directory outside the
checkout. The three resource limits must be finite and positive; wall time must
exceed the 30-second finalization reserve. Setup, extraction and computation use
the same local clock. Memory is sampled across the process tree, not reserved by
the operating system. These caps are limits, not a promise the fit will finish.
`--plan-only` records an unexecuted request. Ordinary use has a fresh local clock
and remains usable after the authors' dated campaign expiry.

`result.json`, `cases/`, the optimizer trace, `refinement_events.jsonl`,
`execution_calls.jsonl`, `reuse_map.json`, `bundled_native.json`,
`reader_request.json`, `reader_result.json` and local supervision evidence are
retained in the output. The mandatory `execution_producer` on the case and result
separates the frozen numerical dependency map from the full actual entrypoint
map. Local integrity checks are not independent scientific acceptance.

A complete fit, a finite original solver-cap unknown and a technical failure
remain distinct. A handled unknown has `scientific_passed: false`, no invented
held-out outcomes and no all-history completion claim. It is not retried
automatically. Keep every attempt, including failures. The command is a genuine
fresh fit; a saved-state score replay would be a different, narrower operation.

## Optional contribution to the dated author campaign

An actual conductor may add `--execution-record child/admission.json`. This is a
separate strict envelope, not a prerequisite for ordinary use. It must identify
the actual reader producer and source review and satisfy the unchanged author
lease, original binary/runtime, resource limits and shared expiry. Invalid or
expired records fail rather than falling back to local mode. The same fit helper
runs; the outer author supervisor owns the sole fixed clock. Automatic native
extraction still occurs through this public command.

The full fixed host partition and independent output audit remain required
before a result joins that campaign. No completed author fit should be repeated
to demonstrate the reader. The old Task3 acceptance did not execute this later
amendment. Source/constructed tests and any later actual public-command execution
are separate evidence; neither a plan nor these controls is a fitted history:

```sh
python -B -m unittest tests.test_joint_refined_cpu_reader -v
```
