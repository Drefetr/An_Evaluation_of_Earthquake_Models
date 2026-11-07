# Joint background and temporal-excitation comparison

This experiment fits `(a, d, n, log c, p)` jointly in the uninhibited arm and
in each of three inhibited arms. The alternatives also fit `(eta, log ell,
log psi)`. The spatial density, mark law and productivity transform remain
fixed. It uses the existing 80 S04B histories and creates no new histories.

The [protocol](protocol.json) freezes the inputs, bounds, starts, numerical
checks and stopping rules before any real-history fit. The two primary
comparisons are S5 immigrant LI+ and S7 total LI+ against the new jointly
fitted null; all other rows are descriptive. The code is an implementation,
not evidence that the pilot or campaign has run. Completed execution and
independent output review belong in separate dated result directories.

There are 320 fit problems: one shared null and three alternatives for each
history, each with eight required starts and the same failure-only recovery
policy. Five raw/gated outputs give 400 comparison outcomes. New BIC decisions
use the new fine-order training scores and the original `1.5 log Ntrain`
threshold. The historical fit and gate states remain separate comparators.

Strict wins mean gain `> 0`. The separate `abs(gain) <= 1e-9` flag identifies
numerically small contrasts without redefining wins. An exact null return
uses the same stored null score and has exactly zero gain. Every eta-zero
alternative improving the selected null is flagged as a null-search gap;
such a contrast cannot be attributed to inhibition. A successful finite
multistart recipe is not a global optimum. Projected KKT norms are retained.

The 480 historical checks recompute the identical train/test uninhibited
floor for three model labels per history, against full-precision payloads at
`1e-9`. A separate 400 checks reconcile saved fixed/intercept-floor comparison
identities; those are not new inhibited likelihood replays. No rounded PDF
number is tested against this tolerance.

The likelihood and derivatives are described in [DERIVATION.md](DERIVATION.md).
The new C++ source streams the exposure calculation; it does not modify or
call the historical fixed-backbone native evaluator. NumPy matrix products
recompute the total-attenuation triggering fields as temporal parameters
change. Fixed quadrature nodes prevent omitted derivatives of moving grids.

From the repository root, build outside the checkout:

```powershell
python -B -m engine.cpu_build --source experiments/s04b_joint_nuisance/attenuation.cpp --dependency-root experiments/s04b_joint_nuisance --output C:/scratch/joint_native
python -B -m unittest discover -s tests -p test_s04b_joint_nuisance.py -v
```

The tests compile and execute only tiny constructed fixtures. They check
independent full-exposure quadrature, all eight likelihood derivatives,
strict-past ties, the exact null reduction and failure/gating accounting.
A C++17 compiler is required; the helper supports MSVC, GCC and Clang.

After independent source/protocol review, a conductor supplies an admission
JSON and the matching `JOINT_NUMERICAL_LEASE_TOKEN` environment value. The
token records a lease attestation; it is not an authenticated security boundary.
The admission binds the phase, protocol/input/source/library/build hashes,
numerical attempt, expiry, two numerical threads, wall allowance and sampled
process-tree RSS threshold. An external supervisor owns termination on the
wall/RSS limits; these are not an OS-enforced memory allocation limit.

```powershell
python -B experiments/s04b_joint_nuisance/run.py --phase pilot --library C:/scratch/joint_native/LIBRARY --build-receipt C:/scratch/joint_native/build_receipt.json --admission C:/scratch/pilot_admission.json --output C:/scratch/joint_pilot
python -B experiments/s04b_joint_nuisance/run.py --phase full --pilot C:/scratch/joint_pilot --library C:/scratch/joint_native/LIBRARY --build-receipt C:/scratch/joint_native/build_receipt.json --admission C:/scratch/full_admission.json --output C:/scratch/joint_full
```

Use the actual library filename returned by the build helper and fresh output
directories. Linux/macOS use the same commands with native paths. The pilot
contains the first seed of each regime plus the input-selected largest-work
case S6 seed 410605. Full execution verifies and reuses those five complete
reports and attempt logs, then fits the remaining 75. Essential runtime and
compiled-library identities must match; detailed kernel/platform metadata are
retained without requiring identical CI host kernels.

Each case retains inputs, all attempts, full selected vectors, training/fine
checks, original thinning counts and held-out P/E/C/M components. Failures,
unresolved starts and unstarted cases stay explicit. Only all 80 completed
cases can produce the 20-row summary. The S5/S7 count-suppressed strata remain
separate; small counts are not a structural nonidentification theorem. Wilson
intervals concern bounded win indicators, not mean gains or simultaneous
coverage. This is a conditional synthetic procedure comparison, not a test of
physical inhibition, general model utility or prospective forecasting skill.
