# Run the joint-nuisance study on Linux CPU

This page describes the original numerical procedure. The separately versioned [refined CPU reader](../experiments/s04b_refined_cpu_reader/README.md) uses the reviewed exposure-refinement adapter with the original fitter and scientific gates. Its default automatically extracts the audited Linux x86-64 native library and receipt; it needs no compiler, MSVC, CUDA, credentials or manual native-library environment setup. Use its documented clone, pinned dependency installation and `scripts/fit_joint_refined_cpu.py fit` command for a fresh single-history fit with finite reader-local limits after the author deadline. This is a fit, not saved-state score replay. Its optional author execution record imposes the unchanged dated author envelope, and actual outputs require their own independent review. The compiler-based original route below and its earlier bounded acceptance remain separate; neither demonstrates execution of the later amended reader.

`scripts/fit_joint_cpu.py` runs the existing joint-background and temporal-excitation
recipe on the supplied S04B histories. It uses the frozen fitting, likelihood,
quadrature, starts, bounds, gates and aggregation functions, with the reviewed
ordered CPU scheduler. It generates no new histories and does not repeat other
historical fitting campaigns. Local verification is automated integrity and
numerical checking; it does not imply independent or external review of your run.

Use a Linux machine with Python 3.13, a C++17 compiler (`g++` or `clang++`), and
enough memory for the selected limits. Python 3.13 with the pinned requirements
is the exercised project environment. From a complete checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -B scripts/fit_joint_cpu.py run --phase pilot \
  --output ../my-joint-pilot --wall-seconds 14400 --rss-mib 6144 --headroom-mib 2048
```

The output directory must be new and outside the checkout. The runner compiles
the unchanged C++ source locally, runs the existing constructed numerical controls,
and evaluates the fixed five-history pilot with two numerical threads and one
scientific worker. Build and fitting share the external process-tree wall/RSS
supervisor. RSS is sampled, not an operating-system memory reservation. Limits
are explicit user choices, not a promise that the requested work will finish.
`--plan-only` records a request without compiling or evaluating anything.

To continue your own successfully completed pilot through all original histories:

```sh
python -B scripts/fit_joint_cpu.py run --phase all --resume ../my-joint-pilot \
  --output ../my-joint-all --wall-seconds 115200 --rss-mib 6144 --headroom-mib 2048
```

Omit `--resume` to execute all 80 histories from scratch. Add `--max-cases N` to
stop after a specified number of new complete histories, then resume that output
in a new directory. The exact completed prefix, runtime, library, source, inputs,
case records and attempt traces are checked before reuse. No completed fit is
repeated. Partial or interrupted fits are retained and cannot be automatically
resumed: the reader rejects a partial prefix and never automatically falls back
to an older one. Keep every output, including failures; do not deliberately
select an older output to erase work already attempted.
Each invocation has a fresh local time allowance; earlier local attempt time is
also retained cumulatively. It does not inherit the authors' dated run expiry or
their original failed-attempt budget.

`reader_result.json` combines the actual child and supervisor status.
`science/result.json` describes this batch; `science/index.json` retains its
complete prefix and any partial case. Cases preserve all starts, fitted vectors,
training checks, held-out scores and original comparison checks. An all-history
`science/summary.json` appears only after all 80 histories and existing aggregate
checks pass. A successful pilot or bounded prefix is not all-history completion.
Logs, source/input/runtime identities, the actual build and supervision records
are retained beside them. The executable requires no GitHub credentials, CUDA,
MSVC or private author directories. After preparing a local wheelhouse, pip can
install the same requirements offline with `--no-index --find-links WHEELHOUSE`.

## Continue the dated published run instead

This separate mode performs the next pending case of the authors' published
execution. It reuses the exact original runtime and native binary; it is **not**
a fresh independent fitting run. Follow the exact Linux runtime installation in
[the execution guide](../experiments/s04b_joint_execution/EXECUTION.md#fresh-linux-checkout-and-exact-runtime).
The archive and its independent review must already be in the public checkout.
For the published six-case prefix:

```sh
python -B scripts/fit_joint_cpu.py run --continue-published budgeted06 \
  --output ../published-next-case
```

The command verifies and restores the local `budgeted06.zip` and its published
review, inherits their exact source review, constructs the ordinary local
execution records, and delegates to the unchanged dated budgeted driver. Its
one next case, fixed wall slot, two threads, one worker, 6144-MiB sampled RSS and
2048-MiB host headroom cannot be enlarged by this command. It retains the original
run's `2026-11-09T07:15:00+00:00` expiry; after that date, use fresh mode instead.
The original failed/partial attempts remain in the inherited index and are not
reset. This new output has no independent acceptance until separately reviewed.
No Actions token or private run directory is needed. Coordinate any contribution
to the same published study so another owner does not run the same pending case.
An actual conductor may supply `--execution-record RECORD.json` to attach a
genuine source/caps/attempt record; the reader checks its source, input-manifest,
predecessor and resource pins and copies it unchanged as `conductor_review.json`.
The configuration hash remains the conductor's supplied attribution. Ordinary
public use needs no such record and writes `local_integrity.json` with
`live_agent_review: false`. Neither path invents acceptance of the new output.

The new reader's constructed tests are:

```sh
python -B -m unittest discover -s tests -p test_joint_cpu_reader.py -v
```

These include an invented full-case numerical equivalence fixture and an
invented 80-case bookkeeping control. Neither constitutes an 80-history fresh
execution. Actual dated runs and their reviews must be reported separately.
