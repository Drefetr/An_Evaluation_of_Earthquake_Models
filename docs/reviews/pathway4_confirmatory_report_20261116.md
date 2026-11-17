# Pathway 4 — single-pass frozen confirmation and cross-regional EP+ transfer

**Date:** 17 November 2026  
**Isolated code:** `experiments/pathway4_confirmatory_transfer/`  
**Isolated results:** `validation/live_results/pathway4_confirmatory_20261116/`  
**Protocol SHA-256:** `32e0403db9180d9c909ba1a7a8aef1260525a58652dff2cf4cbd7b9f3812f64a`  
**Fit-seal manifest SHA-256:** `06aa8df56f5e9af650d8c6aeb2f0ff15ed60e4a25ca87d90d408aca600e20dcf`

## 1. Design and single-pass custody

The Pathway 1–3 winning refinements were frozen in
`frozen_protocol_v1.json` **before** any New Zealand or Japan test-window
score was evaluated.  The protocol fixes the interior-scale EP+ likelihood
(`sigma_0 >= 0.05 km`, `alpha_s in [0,2]`, five-step training
immigrant-probability KDE declustering), both observation-domain
normalisations, the stationary `d = 0` and free-trend `d` arms, the frozen
monotone and annular-Wells–Coppersmith attenuation profiles, all parameter
bounds, starts and the test score decomposition.  Training fits were written
and hash-sealed in `fit_seal.json`; only then did `score_nz.py`,
`score_jma.py` and the California calibration script open test arrays or
archived score totals.  The independent audit reports
**PASS**.

**Protocol custody note.** An initial freeze was written, then invalidated
**before any New Zealand or Japan test-window score was evaluated** because a
sign/root-search error in the one-dimensional attenuation profile was found
and corrected.  The initial protocol and its twelve superseded New Zealand
fits are retained as
`frozen_protocol_v1_superseded_20261116.*` and `superseded_fits_20261116/`.
The operative protocol is the SHA-256 above; the audit verifies that it
predates every sealed fit and that no test score entered either freeze or the
correction.

## 2. New Zealand (612 targets)

EP+ minus archived procedure, in nats.  Positive favours EP+.

| arm | fold | n | EP+ - EP timing | EP+ - EP location | EP+ - EP joint | EP+ - OC joint |
|---|---|---:|---:|---:|---:|---:|
| plane_T0 | 0 | 203 | +8.381 | +22.886 | +31.267 | +49.517 |
| plane_T0 | 1 | 155 | +2.741 | +31.066 | +33.808 | +67.047 |
| plane_T0 | 2 | 254 | +5.162 | +31.269 | +36.431 | +35.214 |
| **plane_T0 total** | 0-2 | 612 | +16.285 | +85.221 | +101.506 | +151.778 |
| plane_T1 | 0 | 203 | +11.095 | +22.381 | +33.476 | +51.726 |
| plane_T1 | 1 | 155 | +3.638 | +31.427 | +35.065 | +68.304 |
| plane_T1 | 2 | 254 | +10.859 | +31.947 | +42.806 | +41.588 |
| **plane_T1 total** | 0-2 | 612 | +25.591 | +85.755 | +111.346 | +161.618 |
| rect_T0 | 0 | 203 | +4.213 | +28.468 | +32.681 | +50.931 |
| rect_T0 | 1 | 155 | +0.961 | +32.481 | +33.442 | +66.681 |
| rect_T0 | 2 | 254 | -2.407 | +38.035 | +35.628 | +34.410 |
| **rect_T0 total** | 0-2 | 612 | +2.767 | +98.984 | +101.750 | +152.023 |
| rect_T1 | 0 | 203 | +6.995 | +27.894 | +34.890 | +53.139 |
| rect_T1 | 1 | 155 | +1.839 | +32.856 | +34.695 | +67.935 |
| rect_T1 | 2 | 254 | +3.400 | +38.589 | +41.989 | +40.772 |
| **rect_T1 total** | 0-2 | 612 | +12.235 | +99.339 | +111.574 | +161.846 |

The primary stationary, full-plane arm gives a three-fold EP+ minus EP joint
contrast of **+111.346 nats** and EP+ minus OC of
**+161.618 nats**.
The free-trend arm gives EP+ minus EP **+101.506**
nats.  The two normalisations and trend laws are separate fitted procedures;
their differences are not a variance decomposition.

## 3. Japan (1,277 targets)

| arm | fold | n | EP+ - EP timing | EP+ - EP location | EP+ - EP joint | EP+ - OC joint |
|---|---|---:|---:|---:|---:|---:|
| plane_T0 | 0 | 469 | +13.774 | +130.402 | +144.177 | +218.936 |
| plane_T0 | 1 | 348 | +14.914 | +88.482 | +103.396 | +162.529 |
| plane_T0 | 2 | 460 | +33.840 | +80.512 | +114.352 | +201.671 |
| **plane_T0 total** | 0-2 | 1,277 | +62.528 | +299.397 | +361.925 | +583.136 |
| plane_T1 | 0 | 469 | -7.227 | +142.797 | +135.571 | +210.330 |
| plane_T1 | 1 | 348 | -16.187 | +95.022 | +78.834 | +137.968 |
| plane_T1 | 2 | 460 | +13.869 | +92.637 | +106.506 | +193.825 |
| **plane_T1 total** | 0-2 | 1,277 | -9.545 | +330.456 | +320.911 | +542.123 |
| rect_T1 | 0 | 469 | -12.297 | +149.639 | +137.342 | +212.101 |
| rect_T1 | 1 | 348 | -19.402 | +100.083 | +80.682 | +139.815 |
| rect_T1 | 2 | 460 | +6.332 | +99.324 | +105.656 | +192.975 |
| **rect_T1 total** | 0-2 | 1,277 | -25.366 | +349.046 | +323.679 | +544.891 |

The primary stationary, full-plane arm gives a three-fold EP+ minus EP joint
contrast of **+320.911 nats** and EP+ minus OC of
**+542.123** nats.
The free-trend arm gives EP+ minus EP
**+361.925** nats.

### Annual blocks (2016–2024)

| arm | year | n | EP+ - EP joint | EP+ - OC joint | refined - EP joint |
|---|---|---:|---:|---:|---:|
| plane_T0 | 2016 | 201 | +54.660 | +92.240 | n/a |
| plane_T0 | 2017 | 125 | +38.797 | +53.257 | n/a |
| plane_T0 | 2018 | 143 | +50.720 | +73.440 | n/a |
| plane_T0 | 2019 | 106 | +33.338 | +40.536 | n/a |
| plane_T0 | 2020 | 111 | +37.496 | +61.342 | n/a |
| plane_T0 | 2021 | 131 | +32.563 | +60.651 | n/a |
| plane_T0 | 2022 | 140 | +42.752 | +67.707 | n/a |
| plane_T0 | 2023 | 126 | +41.616 | +70.575 | n/a |
| plane_T0 | 2024 | 194 | +29.984 | +63.390 | n/a |
| **plane_T0 total** | 2016-2024 | 1,277 | +361.925 | +583.136 | n/a |
| plane_T1 | 2016 | 201 | +48.717 | +86.297 | n/a |
| plane_T1 | 2017 | 125 | +32.958 | +47.418 | n/a |
| plane_T1 | 2018 | 143 | +53.896 | +76.615 | n/a |
| plane_T1 | 2019 | 106 | +27.307 | +34.505 | n/a |
| plane_T1 | 2020 | 111 | +27.037 | +50.884 | n/a |
| plane_T1 | 2021 | 131 | +24.490 | +52.579 | n/a |
| plane_T1 | 2022 | 140 | +42.881 | +67.836 | n/a |
| plane_T1 | 2023 | 126 | +40.951 | +69.909 | n/a |
| plane_T1 | 2024 | 194 | +22.674 | +56.080 | n/a |
| **plane_T1 total** | 2016-2024 | 1,277 | +320.911 | +542.123 | n/a |
| rect_T1 | 2016 | 201 | +49.141 | +86.721 | n/a |
| rect_T1 | 2017 | 125 | +33.178 | +47.638 | n/a |
| rect_T1 | 2018 | 143 | +55.023 | +77.742 | n/a |
| rect_T1 | 2019 | 106 | +27.860 | +35.059 | n/a |
| rect_T1 | 2020 | 111 | +28.100 | +51.946 | n/a |
| rect_T1 | 2021 | 131 | +24.722 | +52.810 | n/a |
| rect_T1 | 2022 | 140 | +42.423 | +67.378 | n/a |
| rect_T1 | 2023 | 126 | +41.337 | +70.295 | n/a |
| rect_T1 | 2024 | 194 | +21.896 | +55.302 | n/a |
| **rect_T1 total** | 2016-2024 | 1,277 | +323.679 | +544.891 | n/a |

The annual rows are descriptive blocks of the same fitted state; they are not
independent replications.

## 4. Frozen attenuation recipe

The baseline arm profiles the monotone kernel over the three declared
`(ell_0, psi)` pairs; the refined arm uses Pathway 1's `ann2` kernel with the
parameter-free Wells–Coppersmith scale and `psi = 5 d`, `gamma = 0.75 log 10`.
Both are exact one-dimensional profiles on the frozen EP+ null backbone with
the exact nested `eta = 0` state.

| cohort | arm | training eta (refined) | test refined gain | test refined - EP joint | training eta (mono) |
|---|---|---:|---:|---:|---:|
| NZ | plane_T0 | 0.001, 0.000, 0.000 | -9.712, +0.000, -32.294 | +59.500 | 0.001, 0.000, 0.000 |
| NZ | plane_T1 | 0.001, 0.000, 0.000 | -9.680, +0.000, -31.142 | +70.524 | 0.001, 0.000, 0.000 |
| JMA | plane_T0 | 0.000, 0.000, 0.000 | +0.000, +0.000, +0.000 | +361.925 | 0.000, 0.000, 0.000 |
| JMA | plane_T1 | 0.000, 0.000, 0.000 | +0.000, +0.000, +0.000 | +320.911 | 0.000, 0.000, 0.000 |

The **refined ann2/Wells–Coppersmith arm is the confirmatory attenuation
test**: its importance field is the ann2 kernel itself, so its profile and
held-out contrast are self-normalised.  The **mono baseline** uses the ann2
kernel as an importance field for its compensator; because the mono kernel has
heavier tails, its held-out contrast is a declared sensitivity only and is
not used in the confirmatory conclusion.  The mono training etas are reported
for completeness, not as a detection.

The refined arms' three-fold joint contrasts versus archived EP are
**+70.524 nats** (NZ) and **+320.911 nats** (JMA).  Relative
to the EP+ null backbone the attenuation gains are
**-40.822 nats** (NZ) and **+0.000 nats** (JMA).
A zero gain means the training profile selected the exact nested `eta = 0`
boundary; the attenuation refinement is then observationally identical to the
EP+ null backbone, not evidence for a physical stress shadow.

## 5. California conditional calibration of interior-scale EP+

999 sequential branching paths per origin were simulated from the frozen
interior-scale EP+ states.  The observed vector plus the 999 simulated vectors
form the symmetric pool for the eight-coordinate quadratic and Fisher-type
omnibus statistics.

| origin | n | count p | quadratic p | Fisher p | archived OC (N/quad/Fisher) | archived EP (N/quad/Fisher) |
|---|---:|---:|---:|---:|---|---|
| 2011 | 79 | 0.004 | 0.010 | 0.002 | 0.002/0.004/0.001 | 0.002/0.004/0.002 |
| 2016 | 167 | 0.452 | 0.004 | 0.006 | 0.594/0.003/0.004 | 0.698/0.005/0.006 |
| 2021 | 69 | 0.266 | 0.101 | 0.166 | 0.056/0.007/0.012 | 0.036/0.009/0.008 |

- origin 2011: conditional count p=0.004, quadratic p=0.010, Fisher p=0.002.
- origin 2016: conditional count p=0.452, quadratic p=0.004, Fisher p=0.006.
- origin 2021: conditional count p=0.266, quadratic p=0.101, Fisher p=0.166.

The refinement repairs the 2021 origin's continuous omnibus (quadratic
p=0.101, Fisher p=0.166) but the 2011 and 2016 origins remain rejected at the
five-percent level.  The conditional count behaviour improves at 2016 relative
to archived EP (0.452 versus 0.698), at 2021 (0.266 versus 0.036) but not at
2011 (0.004 versus 0.002).

These are conditional, within-origin tests.  They do not integrate parameter
uncertainty and are not a joint cross-origin rejection.

## 6. Independent audit

| check | result |
|---|---|
| protocol_hash_pin | pass |
| fit_seal_protocol_hash | pass |
| fit_seal_manifest | pass |
| fit_source_pins | pass |
| protocol_precedes_every_fit | pass |
| fit_sources_never_read_test_scores | pass |
| fit_artifact_protocol_conformance | pass |
| common_measure_identity | pass |
| archived_score_replay | pass |
| rectangle_mass_vs_independent_quadrature | pass |
| analytic_gradients | pass |
| sealed_authority_custody | pass |
| california_conditional_calibration | pass |

The audit verifies the protocol pin, the fit seal, training-only source
separation, exact common-measure identity of parent histories, fertility
weights, rectangles and event arrays, exact archived-score replay, rectangle
mass against independent quadrature, analytic gradients against central finite
differences, sealed-authority custody and the California frozen-state replay.

## 7. Interpretation and limitations

* The confirmatory execution is single-pass: the New Zealand and Japan fits
  were sealed before any test-window score was read.  No parameter, bound,
  bandwidth or declustering step was changed afterwards.
* EP+ is a separately fitted procedure.  Its contrast with archived EP or OC
  measures the whole procedure, not an isolated physical mechanism.  In Japan
  the stationary-arm joint gain is a location-channel gain (+330.5 nats)
  partly offset by a small timing loss (-9.545 nats);
  in New Zealand both channels are positive.
* The attenuation arms are frozen one-dimensional profiles on the EP+ null
  backbone.  They are not a new joint twelve-parameter search; the protocol
  declares this low-dimensional design following Pathway 3's winner rule.
* On Japan the productivity coordinate `n` sits at its 0.98 upper bound in
  every stationary and free-trend fit, and the fold-0 free-trend arm also pins
  `d` at the -2 lower bound.  These are constrained boundary solutions; the
  reported contrasts describe the fitted constrained procedure, not an
  unconstrained optimum.
* The California calibration is conditional on the fitted state and history.
  The pooled statistics are descriptive within-origin tests, not CSEP
  L/M/S tests, and non-rejection is not proof of model correctness.
* New Zealand's 612 targets remain a reused archive cohort; this execution
  removes the *adaptive procedure-selection* concern but not the reuse of the
  events themselves.
