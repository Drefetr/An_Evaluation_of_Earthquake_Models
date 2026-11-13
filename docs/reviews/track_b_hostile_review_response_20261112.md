# Track B hostile-review response: targeted scientific controls

**Date:** 12 November 2026  
**Baseline:** `validation/track_a_remediation_20261112.json`  
**Pre-change snapshot:** `validation/track_b_prechange_snapshot_20261112.json`  
**Primary outputs:** `validation/live_results/track_b_controls_20261112/`  
**Independent audit:** `validation/live_results/track_b_controls_20261112/independent_track_b_audit.json`

## Scope and custody

Track B executes the bounded controls requested after Track A: the EP+ four-way
component ablation and interior spatial-scale study (B1), New Zealand Fold-1
trend/depletion controls (B2), and the S8 oracle ceiling, California attenuation
profiles and regional minimum detectable effects (B3). All calculations reuse
frozen caches, frozen fitted states and the existing CPU analytical, modal and
quadrature routines. No new simulation campaign was run.

The 316 pre-existing sealed JSON authorities named in the Track A custody record
are unchanged; 11 additional Track A supplement JSON files are also unchanged.
The complete roster is hash-pinned in
`validation/track_b_prechange_snapshot_20261112.json`. New derived summaries are
confined to `validation/live_results/track_b_controls_20261112/`.

## B1. The EP+ gain is mainly background and scaling, and the 2 km bound was binding

The accepted EP+ procedure gains 69.553 nats over archived EP. The nine-arm
ablation holds the histories, fertility weights and common mark measure fixed.
Its exact additive decomposition is:

| Component | Shapley contribution (nats) | Sequential contribution (nats) |
|---|---:|---:|
| Joint temporal–spatial fitting (A0 → A1) | 10.241 | 10.241 |
| Full-plane versus rectangle normalization | 0.064 | 0.089 |
| Five-step training declustering | 29.223 | 27.760 |
| Magnitude-scaled spatial kernels | 30.026 | 31.463 |
| **Total A8 − A0** | **69.553** | **69.553** |

The Shapley values average all orderings of the three procedural factors and
close exactly on the observed A8 − A0 gain. The rectangle-normalized analogue
A7 reaches 69.502 nats, so common-space normalization changes the total by
0.050 nats. The four-way “simultaneous changes” warning in the earlier abstract
is therefore too weak: the normalization change is negligible, while background
declustering and magnitude scaling account for almost the entire gain.

The accepted spatial scale hits the 2 km lower search bound in every fold.
Releasing the bound to 0.05 km selects interior values of 0.823, 0.839 and 0.821
km under full-plane normalization (0.823, 0.839 and 0.823 km under rectangle
normalization). Training declustering under the relaxed bound raises the
three-fold held-out gain to 77.056 nats; holding the accepted EP+ background
weights fixed raises it to 78.584 nats. The full fixed-σ₀ profile curves are in
`epplus_ablation/sigma0_profile.json` and Table `tab:sigma0-profile`. The earlier
2 km estimate was a search-box artefact, not a likelihood maximum. Held-out
gains at the interior optimum exceed those at 2 km in all three folds.

**Answer to Questions 4–5 and Concern 3.4.** The EP+ gain is not evidence for a
spatial-normalization effect. The dominant changes are the training-declustered
background and the magnitude-scaled kernel. The 2 km boundary was binding; the
interior optimum is near 0.8 km, and the accepted 69.553 nats understates the
relaxed-bound gain by roughly 7.5–9.0 nats.

## B2. New Zealand Fold 1: trend extrapolation, not a stable residual inhibition

Fold 1 contributes −16.518 of the −17.623-nat shared-attenuation deficit. The
matched controls are:

| Fold/control | a | d | n | η | Δℓ_train | ΔQ | ΔC | Δℓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| F0 free d (archived) | −2.197 | 1.790 | 0.482 | 1.647 | 2.731 | −33.715 | 17.198 | −16.518 |
| F0 fixed null d | −4.329 | −0.252 | 0.461 | 0.178 | 3.556 | — | — | −4.556 |
| F0 zero d | −4.064 | 0.000 | 0.464 | 0.357 | 3.292 | — | — | −8.504 |
| F1 free d (archived) | −3.842 | 0.493 | 0.503 | 0.212 | 0.303 | — | — | −0.075 |
| F1 fixed null d | −4.152 | 0.147 | 0.499 | 0.034 | 0.201 | — | — | +0.675 |
| F1 zero d | −4.241 | 0.000 | 0.499 | 0.000 | 0.200 | — | — | 0.000 |
| F2 free d (archived) | −4.103 | 0.128 | 0.473 | 0.105 | 0.144 | — | — | −1.030 |
| F2 fixed null d | −4.262 | −0.057 | 0.471 | 0.016 | 0.129 | — | — | −1.126 |
| F2 zero d | −4.213 | 0.000 | 0.472 | 0.043 | 0.114 | — | — | −2.927 |

The archived free-d scores reproduce the sealed order-32 values exactly
(maximum absolute error 0.0). For Fold 1, the zero-trend control removes 48.5%
of the deficit and leaves −8.504 nats; freezing the uninhibited null trend
removes 72.4% and leaves −4.556 nats. The positive fitted trend d = 1.790, not
depletion alone, accounts for most of the original loss. The clamped-clock
counterfactual (evaluating the archived fit with x(t) fixed at its training
endpoint) is not a refit and worsens the score to −24.791 nats; it is not used
for attribution.

The middle fold's zero-trend fit selects η = 0 and is tied at displayed
precision; the late fold retains a small positive strength. These two folds do
not support the same attribution as Fold 1. The autonomous d = 0 comparison in
Table `tab:autonomous-nz` remains a separate fitted procedure.

**Answer to Question 2 and Concern 3.1.** The Fold-1 loss is dominated by the
free linear trend extrapolating into x_trend > 0. A matched zero-trend or
fixed-null-trend control removes 48.5–72.4% of the deficit. The remaining
detrended residual is smaller but not zero; it is not evidence for a stable
physical inhibition effect.

## B3. S8 oracle ceiling, California η profiles and detectable effects

### S8 oracle ceiling

The true generating law uses η = 0.4, ℓ = 15 km and ψ = 5 days. Over the twenty
sealed histories, the mean held-out contrasts are:

| Contrast | Mean | Median | SD | MCSE | Wins |
|---|---:|---:|---:|---:|---:|
| True law vs fixed true-backbone null | 16.429 | 12.819 | 8.176 | 1.828 | 20/20 |
| True law vs refitted-intercept null | 14.541 | 11.630 | 8.187 | 1.831 | 20/20 |
| True law vs jointly fitted null | 18.112 | 12.865 | 18.700 | 4.182 | 19/20 |
| Fitted inhibited minus true law | −17.818 | −8.097 | 27.204 | 6.083 | 2/20 |
| Fitted inhibited minus fitted null | 0.294 | 2.541 | 12.420 | 2.777 | 13/20 |

The oracle knows the generating attenuation parameters but not the nuisance
backbone. Even after the uninhibited comparator refits all five backbone
parameters, the oracle gain averages 18.112 nats (MCSE 4.182). The fitted
procedure captures only 0.294 nats; its mean estimation loss relative to the
oracle is 17.818 nats (MCSE 6.083). The bottleneck is estimation of the three
extra attenuation parameters, not the absence of a true generating effect.

**Answer to Question 6 and Concern 3.2.** The S8 test bank has a real oracle
ceiling of about 18 nats against the fitted null, but the fitted procedure
captures about 0.3 nats. A non-significant fitted gain therefore does not mean
the generating effect is absent; it means the finite-history estimation problem
is severe.

### California η profiles

At the uninhibited training MLE, the EP+ training profile is extremely steep.
At the S8 scale pair (ℓ = 15 km, ψ = 5 d), the one-sided 95% profile upper bound
is approximately 3.6 × 10⁻⁵ (F0), 3.6 × 10⁻⁵ (F1) and 2.7 × 10⁻⁵ (F2) after
re-optimizing (a,d,n) at each fixed η. The fixed-backbone slices at ℓ = 10, 15,
20 and 50 km show the same qualitative result: the training data exclude η
above roughly 2 × 10⁻⁵ to 5 × 10⁻⁵ under this kernel. The held-out contrast at
the S8 value η = 0.4 is strongly negative in every fold (about −74.7, −10126.6
and −28.5 nats), because the EP+ stress kernel has a much larger amplitude than
the S8 generating kernel. The zero boundary is therefore strongly selected by
the California training windows, not a flat-direction artefact. These are
model-specific profile bounds, not physical stress-shadow limits.

**Answer to Concern 3.5 and the η-profile request.** The nested η = 0 selection
is backed by explicit training-profile curves and upper bounds. Under the EP+
kernel, even very small positive η is excluded by the California training data.

### Minimum detectable effects

The unified MDE table uses paired calendar-block scores for New Zealand and
California and a between-window standard error for Japan (three annual fold
totals; no 90/180/365-day block bootstrap is available for Japan).

| Region | N_test | Block (d) | SE_B (nats) | MDE95 (nats) | MDE95/event | Required δ |
|---|---:|---:|---:|---:|---:|---:|
| New Zealand | 612 | 90 | 4.712 | 9.236 | 0.0151 | 17.4% |
| New Zealand | 612 | 180 | 5.418 | 10.619 | 0.0174 | 18.6% |
| New Zealand | 612 | 365 | 6.651 | 13.035 | 0.0213 | 20.6% |
| California | 315 | 90 | 24.644 | 48.302 | 0.1533 | 55.4% |
| California | 315 | 180 | 24.173 | 47.379 | 0.1504 | 54.8% |
| California | 315 | 365 | 26.961 | 52.843 | 0.1678 | 57.9% |
| Japan | 1277 | annual fold SE | 8.153 | 15.979 | 0.0125 | 15.8% |

The EP+ gain of 69.553 nats is of the same order as one California 90-day MDE
(48.302 nats). The New Zealand −17.623-nat shared-attenuation loss exceeds the
New Zealand 90-day MDE by about a factor of two. The S8 raw mean of 0.294 nats is
far below its own MCSE of 2.777. These scales delimit what the negative and
positive summaries can detect; they do not convert a non-significant contrast
into evidence of physical absence.

**Answer to Question 1 and Concerns 3.1–3.2.** Regional resolving power differs
by roughly a factor of five between New Zealand and California. The completed
negative results are informative at the New Zealand scale, marginal at the
California EP+ scale, and weak at the S8 moderate-effect scale.

## Verification and custody

- `python -B experiments/etas_inhibition_benchmark/ablation_and_sigma0.py` wrote
  the ablation, relaxation and profile authorities.
- `python -B experiments/methodological_audit/nz_trend_controls.py` wrote the
  New Zealand control authority.
- `python -B experiments/methodological_audit/eta_profiles_and_power.py` wrote
  the S8 oracle, California profile and MDE authorities.
- `python -B experiments/methodological_audit/audit_track_b.py` independently
  recomputed objective values, held-out scores, factorial closure, profile
  points, block standard errors and sealed-authority hashes.
- The claim ledger, authority manifest, manifest, paper, companion and website
  are refreshed by the commands in `validation/track_b_remediation_20261112.json`.

## Remaining limitations

The block intervals and sign-flip references remain descriptive under long
memory and dependent calendar blocks. The S8 oracle uses the fitted likelihood
family and the known generating law; it is not an external forecast. The
California η profile is kernel-specific and does not identify a physical
stress-shadow amplitude. The Japan MDE uses a between-window standard error
from three annual folds, not a block bootstrap. The New Zealand archive is
adaptively reused; the controls reduce, but do not remove, that dependence.
