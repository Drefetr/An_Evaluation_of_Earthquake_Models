# S02 selected-state replay route

This route reconstructs the original finite-mixture likelihood from the 300
paired-clock CSVs in `reproduction/s02/completed_inputs_20261031.zip`. It evaluates
the recovered null and alternative vectors for M1 and M2: 1,200 selected ground
NLLs and 600 GLRs. It does not fit parameters, simulate histories, or replay the
9,606 historical optimizer attempts.

No historical result is produced merely by adding this route. A reviewed
numerical admission is required for execution. The six-case pilot is frozen in
`protocol.json`: forest 000 plus the largest-event forest 043, each at all three
persistence settings. The choice uses input counts, not score differences.
Completion reuses those exact six pilot reports and evaluates the remaining
294 cases. Forest 001, inspected in the historical audit, remains included in
the new all-300 roster; its old review is not treated as a new execution.

`original/` contains byte-exact archive members, mapped and hash-pinned in the
protocol. The archived `f_oracle_v2.py` supplies the paired clock and spectral
mixture. Its `public_law` function and historical command-line runner are not
used. The new runner reads the archived law directly and applies the executed
S02 override from `s02_campaign.py`: candidate reproduction is fixed at 0.5,
with productivity ratios 0.7 for M1 and 0 for M2. The earlier staged recipe alone
does not describe the executed candidate settings.

The compiled translation unit includes the unchanged original
`independent_f_oracle.cpp`. Separate read-only exports in `components.cpp` expose
event log-intensity sum P, positive exposure E, and a direct GLR. They do not
alter the original feature builder or likelihood/gradient exports. The direct
GLR uses event-log-intensity and stable compensator differences; subtraction of
full NLLs is retained as a separate numerical control. Raw signed GLRs are never
clamped to zero.

The original oracle excludes the common exponential mark-density constant:

- Ground NLL = E - P; timing score = P - E.
- C = -E; M = N log(beta) - beta sum(Q).
- The reported candidate joint score is P + C + M. M is fixed and cancels from
  the within-catalogue comparison. It is not a newly fitted magnitude forecast.
- `qf_evaluate` fields are NLL, da, dd, dn, deta, quadrature-node count. Gradients
  remain diagnostics, not global-optimum certificates.

The primary replay uses order 32, refined panels, and the original absolute
NLL/GLR tolerance of `1e-4`. All selected pilot points additionally receive an
order-64 sensitivity check. Completion uses order 32 for its new cases and
retains the pilot's order-64 records; it does not claim order-64 coverage of all
300 catalogues. P/E/NLL identities use a separately declared `1e-8` arithmetic
tolerance. The preserved paired time_hi/time_lo/event_gap fields retain positive
sub-ULP event separations; projecting them into tied single-double clocks is
not permitted.

From the repository root:

```text
python -B reproduction/score_replay/s02_replay.py build --output /external/s02-native
python -B reproduction/score_replay/s02_replay.py run --mode pilot --admission /external/reviewed-pilot.json --library /external/s02-native/components.so --build-receipt /external/s02-native/build_receipt.json --output /external/s02-pilot
```

Use the builder's actual receipt and platform-specific library path. A C++17
compiler is required; Linux can use g++ without MSVC or CUDA. The admission
binds the source map, protocol, binary, build receipt, numerical attempt, exact
case roster, two-thread budget and expiry, plus a lease-token hash. The external
supervisor must enforce wall time and sampled process-tree memory. Completion
uses `--mode completion --pilot /external/s02-pilot` and a new reviewed admission
pinning the pilot result and independent output review. No routine test or
package import launches this campaign.

Per-case JSON records are checkpointed before feature construction and after
each selected evaluation. Failed comparisons and interrupted partial files
remain visible; missing or failed cases cannot be accepted as a complete run.
The completed union emits per-cell deltas for all three Chapter 9 S02 tables,
with exact archive-member JSON pointers. Continuous summary comparisons retain
the original numerical tolerance; discrete counts must agree exactly. Any
display-rounding mismatch is separately reported, not hidden by that tolerance.
The empirical thresholds still use the same h=0 reference histories and remain
descriptive rather than independent calibration.

Constructed controls compile the real source and run the original 36 tiny
direct-sum/integral/gradient checks plus adapter, clock and custody controls:

```text
python -B -m unittest discover -s tests -p test_s02_score_replay.py -v
```

They evaluate no archived catalogue and do not constitute historical replay
acceptance. Fresh Linux execution and the scientific pilot require their own
dated records.
