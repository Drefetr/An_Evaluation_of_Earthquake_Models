# Guarded current S05 replay

`run_replay.py` supervises unchanged archived numerical sources. It supports
`controls`, `pilot`, `probe_oc`, `probe_ep` and `full`, under either `point` or
`temporal` scope. No build or scientific run occurred while preparing it.
Dependencies: Python, psutil 7.0.0 (tested host version), NumPy and SciPy.
The conductor owns build provenance, numerical-slot admission and execution.

Every invocation requires explicit external source-copy, DLL/shared-library,
materialized manifest, reviewed point-control wrapper, build receipt,
conductor admission and **new external output directory**:

```powershell
python -B reproduction/regional/run_replay.py --mode pilot --scope point --sources C:/new/s05_build --dll C:/new/s05_build/independent.dll --manifest C:/new/s05_inputs/S05/replay_manifest.json --point-controls reproduction/regional/point_controls.py --build-receipt C:/new/build.json --admission C:/new/pilot_admission.json --output C:/new/pilot_guard
```

The conductor supplies `NUMERICAL_LEASE_TOKEN` from the actual exclusive
numerical lease. An environment token alone is insufficient: the admission
binds an immutable lease snapshot and an active-owner record. The guard checks
their owner, lease ID, token digest, active/exclusive status and expiry before
launch and every 0.1 seconds. It does not freeze the mutable whole task ledger.

The admission schema is `s05_execution_admission_v1`, with `status:admitted`,
`mode`, `workers`, `phase_wall_limit_seconds`, `expires_utc`, `run_deadline_utc`,
`binding`, `lease`, and `prior`. All paths are explicit. The binding is the exact
dictionary returned by `bindings(args, reviewed_point_module)`: scope, current
guard and point-wrapper hashes, all eight archived source hashes, DLL hash,
materialized-manifest hash and build-receipt hash. The `lease` object contains
`snapshot_path`, `snapshot_sha256`, `active_path`, `owner`, `lease_id` and
`token_sha256`. Both lease records contain those identity values plus
`status:active`, `exclusive_numerical_slot:true`, and `expires_utc`. These records
must be issued by the conductor from the actual numerical-slot ledger; this
script does not create, reserve or infer a lease.

Each `prior` entry maps phase name to `{path,sha256}` for that phase's actual
guard `result.json`. Pilot/probes require `controls`; full requires controls,
the original six-case pilot and both fixed probes. Full also requires a pinned
`workload:{path,sha256}`, `resource_admitted:true`, and `resource_projection`
equal to the guard's recomputation from the actual pilot/probe receipts.
The conductor can use the pure `projection` helper before issuing admission.
No admission is inferred from a stale boolean, child exit status or score gain.

## Fixed calls and numerical gates

Controls run the archived control command, then the separately reviewed native
point controls for point scope. The two commands share one 180-second phase cap.
The original pilot uses index zero of each OC/EP × three-origin combination.
The fixed workload probes are OC/california_fold_0/74 and EP/california_fold_2/573.
Each probe imports exact frozen replay, calls `init`, selects one exact manifest
identity and invokes `one((row,scope))` inside its supervised child process.
No native-wrapper standalone CLI is used.

Full runs **all 5,994 rows from scratch**, with no `--reuse` and no injected
journal. Successful pilot + probes + full therefore make 6,002 actual row calls;
the separate control fixtures are not historical replay rows. Observed rows
are excluded. A full result must contain exactly 5,994 unique successful
identities under one scope and one binding, and its journal must agree with
its report. The guard checks component coverage, finite durations/errors,
the archived 1e-4 maximum-error gate and each current receipt hash. Exact count
and mark-sum checks remain inside the pinned archived `one` implementation;
the historical row format does not expose their separate residuals.

A zero exit code with `passed:false`, a missing report, any failed/duplicate/
unexpected row, a nonfinite value, source drift, lease loss or resource breach
produces `passed:false` and a nonzero guard exit. Actual child reports, journals,
stdout/stderr and supervision records are retained and hashed, including on
failure. There is no retry, imputation or post-result tolerance adjustment.

## Resource bounds

Controls, pilot and each probe have immutable 180-second caps and one worker.
Full point has 1,800 seconds; full temporal has 900 seconds; full workers are
declared before launch in the range 1..4. Every phase also stops before the
run deadline minus the 1,800-second publication reserve. BLAS/OpenMP are set to
one thread per child. A phase's sequential child calls share its remaining cap.

The process supervisor tracks PID plus creation time, all observed descendants,
whole-tree RSS, CPU time and available memory at 0.1-second intervals. It kills
only currently matching owned process identities at a limit/lease failure,
waits, and reports actual termination requests and surviving identities.
Residual children after a parent exits are treated as failure. This is sampled
process supervision, not a kernel allocator quota: a burst between samples can
exceed the threshold before detection. The archived process-pool parent keeps
its children attached while running; an unrelated deliberately detached process
is outside this runner's intended scientific child model.

The hard tree ceiling is 8 GiB. Before measurements, one-worker phases require
2 GiB startup reserve plus 4 GiB OS/other-work headroom. Full uses the reviewed
memory-v2 formula: `ceil(1.5*workers*P1)+max(128 MiB,16*manifest_bytes)`, with P1
the largest actual one-worker pilot/probe whole-tree peak. That projection must
fit 8 GiB and leave 4 GiB currently available. Headroom is also checked during
execution. No fixed 12 GiB available-memory prerequisite is imposed.

Time projection uses the pinned input-count workload, the worst observed
seconds/work-unit across the six pilot and two largest-input probe rows, and
`3*max(r*sumW/workers,r*maxW)`. The guard additionally reserves per-worker startup
of at least 30 seconds or the measured aggregate phase overhead, whichever is
larger. Full work includes all rows, including the pilot/probes again. This is
a conservative planning proxy; hard resource limits remain binding.

Fake-process/report tests (no DLL or scientific evaluation):

```powershell
python -B -m unittest discover -s reproduction/regional/tests -p test_replay_guard.py -v
```

Sampling failures fail closed. The supervisor retains the original exception, attempts cleanup in a finally path, and writes a failed supervision receipt. Descendants are killed only after PID and creation-time verification; the original Popen-owned root handle is the fallback when root metadata is inaccessible. Access-denied identities remain unverified, and failed descendant discovery is retained as uncertainty even if all known processes are gone. A zero known-survivor list does not certify discovery completeness. No scientific acceptance follows from these fake-process controls.

After root exit code zero, tracked helpers receive at most three seconds to become quiescent, within the original wall deadline. Every grace sample still checks process identity, descendant discovery, RSS/headroom and the numerical lease. Nonzero exits receive no grace. Residual or unverified processes, discovery errors, expired wall/lease limits and memory breaches still fail and enter the existing cleanup path. Grace timing is retained in the supervision receipt; cleanup time can follow the execution deadline. This is an operational Windows helper-exit correction, with no scientific or resource-limit relaxation.
