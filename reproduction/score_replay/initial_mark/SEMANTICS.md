# Selected-state source crosswalk

The recovered `comparison.py` invoked the frozen iteration-21 staged fitter.
Its selected values were produced with iteration-20 `RestrictedHistory`, using
CUDA quadrature for optimization and CPU order32 checks for final validation.
All relevant source bytes are retained under `original/`; they are evidence,
not a request to run the original optimizer.

The new route uses the independent Q01 finite-mixture evaluator already bundled
for S02. The original C++ is unchanged. A separate C++ wrapper exposes point and
exposure components and a stable direct contrast. Initial-mark execution selects
the original 45 panel offsets, not the extra short-lag panels of the later S02
audit. It uses order32, with an order64 pilot sensitivity.

| Quantity | Original definition | New evaluation |
| --- | --- | --- |
| Clock | Two-double timestamps and authoritative positive gaps | Same four raw CSV arrays, checked against original dtype/shape/byte hashes |
| Stress | Pre-event finite-mode sum with mark `exp(gamma Q)/exp(gamma)` | Same positive mixture and strict pre-event recurrence |
| Trigger | Pre-event mixture derivative with mark `(1-r)exp(beta r Q)` | Same mixture, fixed `r=.7`, selected original `n` |
| Background | `exp(a+d(2t/T-1)-eta G)` | Original selected `a,d,eta`; analytic initial quiet interval and quadrature thereafter |
| Trigger exposure | Sum of productivity times integrated mixture derivative | Analytic finite-mixture exposure to the original horizon |
| Ground NLL | Exposure minus sum of log intensities; mark constant excluded | Same functional, independent scalar summation and stable log arithmetic |
| Mark score | Common fixed exponential density | `N log(beta)-beta sum(Q)`, separately labelled; not refitted |
| Direct GLR | Twice alternative-minus-null log likelihood | Point log-ratio plus signed compensator difference; checked against NLL subtraction |
| Operational selection | GLR strictly above `.001` and eta above `1e-6` | Same rule; every disagreement fails |

The independent implementation and compiler can round intermediate elementary
functions differently. The claim is agreement within the original `1e-4`
selected-state tolerance, not bitwise identity with CUDA, optimizer equivalence
or reproduction of the optimization trajectory. Original CPU32 values provide
a second saved comparison. Paired-clock tails and mixture weights are tested on
constructed sub-ULP-gap histories against the preserved CPU implementation.

Constructed controls also exercise the complete two-method adapter, component
signs, fixed-background and branching-scalar invariants, retained failures, and
the 60-case table aggregation against the original analysis code. They do not
score any archived history. The count-based pilot selection and all input/source
pins were frozen before historical numerical execution.
