# Unit-mark S2 history reconstruction

This package reconstructs the fixed original S04 narrow/short histories (seeds
410201–410220) and checks each against a paired, same-seed uninhibited history.
It does not fit parameters or evaluate likelihoods. The primary references are
the 20 original arrays in `histories/`, containing 4,268 events. Counter totals
are derived from reconstruction, rather than assumed from reviewer prose.

`manifest.json` pins all inputs and the public generator. Case entries record
original history paths; source records retain original hashes. The first two earlier receipts preserve all fields
except machine-specific artifact paths, which become basenames; the manifest
records both original and public hashes. Their event JSONL files and all 20
NPZ histories are byte-exact copies. `source/` retains the original generator
and an exact original driver function excerpt. The earlier JSONL and later
S04 arrays differ by at most two ULP in a few floating fields; both are retained.

From the repository root, with Python and NumPy installed:

```powershell
python -B reproduction/synthetic/s2_unitmark/reconstruct.py --phase pilot --output C:/scratch/s2_pilot
python -B reproduction/synthetic/s2_unitmark/reconstruct.py --phase full --pilot C:/scratch/s2_pilot --output C:/scratch/s2_full
```

Choose fresh output directories outside this package. The full phase verifies
and copies all pilot artifacts, then runs the remaining 18 paired cases: 40
generator calls in total. It requires the same code, inputs and runtime as the
pilot. No replacement seeds, optimizers, native libraries or model scoring are
used. The frozen `protocol.json` defines the row tolerance, exact counter/RNG
checks, conditional coupling check and sequential resource limits. The
generator enforces its existing caps and a smaller deadline; this script does
not claim an operating-system memory limit.

Every case retains positive/null rows, complete event records, counters, RNG
state hashes and counters, acceptance-margin diagnostics and comparison results. Failures stop
the run and retain partial evidence. Zero rejection is checked as a realized
same-stream coupling; it does not make the positive and null probability laws
equal. The margin observer consumes no extra random draws.

A successful full run writes deterministic `summary.json`; environment,
timing and source identities are in `result.json`. Add `--check-summary PATH`
to the full command to require exact summary bytes. Publication records are
kept separately under `validation/live_results/s2_control_20261107/`, with the
edition review at `validation/reviews/S2_CONTROL_EDITION_20261107.json`.
