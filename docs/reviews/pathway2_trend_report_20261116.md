# Pathway 2 — stationary, origin-clamped and orthogonalised background laws

**Date:** 16 November 2026  
**Baseline commit:** `a9d7f9d`  
**Code:** `experiments/pathway2_trend_parameterization/`  
**Results:** `validation/live_results/pathway2_trend_controls_20261116/`

## Headline

- **S8, seed 410840.** The archived T0 overfitting loss is `3.571` nats on average (maximum `75.278`, seed 410840). Under T1/T2/T3 the mean is `-3.216` / `-3.409` / `-3.409` and the maximum is `20.510` / `10.065` / `10.065`. Seed 410840 falls from `75.278` to `2.579` / `10.065` / `10.065`.
- **S8 estimation loss.** The mean falls from `-17.818` nats under T0 to `-9.785` / `-9.231` / `-9.043` under T1/T2/T3. The median held-out gain is `2.541` under T0, `0.341` under T1, `2.596` under T2 and `1.777` under T3.
- **S04B tails are not trend-driven.** The worst archived-T0 case `S4_narrow_short_imm_seed410415` has T0 `-592.90` nats and remains `-593.00` / `-590.08` under T1/T2.
- **New Zealand.** T1 improves the three-fold shared-attenuation deficit from `-17.623` to `-11.431` nats, while T2/T3 give `-26.899` / `-26.899`. On Fold 1 the clamped arms reproduce the sealed non-refit counterfactual because the training likelihood is invariant to the clamp.
- **California EP+.** The interior total gain is `77.056` nats under T0 and `87.739` / `79.405` / `79.405` under T1/T2/T3.

## 1. Question and definitions

The archived background is `B(t) = exp(a + d x_trend(t))` with `x_trend(t) = 2t/T0 - 1`. Because `x_trend` is normalised by the whole catalogue horizon, early training windows sit on the negative branch and the held-out window sits on the positive branch. A positive fitted `d` is therefore extrapolated exponentially. The Pathway 2 handoff replaces this clock with three forecast-admissible laws, applied identically to the uninhibited and inhibited arms:

| id | clock / background | free trend? |
|---|---|---|
| T0 | `2t/T0 - 1` (archived) | yes |
| T1 | stationary, `d = 0` | no |
| T2 | `x_clamp(t) = min{0, (t - T_origin)/(T_origin - T_start)}` | yes, but zero future |
| T3 | T2 clock plus training-orthogonalised `G` | yes, but zero future |
| D* | conditional true-trend control, `d = 0.2` | frozen at truth |

Primary contrasts: the uninhibited comparator overfitting loss `l_test(a_hat, theta_star,0,-a) - l_test(theta_hat_0)`, the inhibited estimation loss `l_test(theta_hat_1) - l_test(theta_star)`, and the paired held-out gain `l_test(theta_hat_1) - l_test(theta_hat_0)`.

## 2. Guardrails and numerical checks

All writes are confined to the isolated code and result paths. The audit re-hashes every pre-existing `validation/authorities/` and `validation/live_results/` file against `MANIFEST.json`; no sealed file was modified. The T0 replay reproduces every sealed S8 null and inhibited held-out score; the analytic background integrals are checked against adaptive quadrature; the native deficit recurrence is checked against a direct NumPy fixture with and without orthogonalisation; and all eight analytic gradients are checked against central finite differences.

**Audit verdict:** PASS (11 checks; failed: none).

## 3. S8 moderate control (20 histories)

| arm | overfitting loss | estimation loss | held-out gain | BIC-gated gain | gate active | eta RMSE |
|---|---|---|---|---|---|---|
| T0 | 3.571 | -17.818 | 0.294 | 2.495 | 12/20 | 1.230 |
| T1 | -3.216 | -9.785 | 1.539 | 0.983 | 3/20 | 0.888 |
| T2 | -3.409 | -9.231 | 1.901 | 2.126 | 12/20 | 1.232 |
| T3 | -3.409 | -9.043 | 2.089 | 1.696 | 12/20 | 1.200 |
| DSTAR | -5.959 | -5.505 | 3.077 | 0.563 | 4/20 | 1.199 |

The BIC gate uses the archived `1.5 log N_train` threshold on the fine training scores and returns the exact null when the threshold is not met. It is a sensitivity, not a replacement for the raw contrast: under it T0/T2/T3 retain 12/20 active alternatives with gated mean gains of 2.50/2.13/1.70 nats, while T1 activates only 3/20 and its gated mean falls to 0.98. T1's raw advantage is therefore concentrated in fits that the BIC gate would not select.

Fitted `eta` recovery against `eta_star = 0.4`: T0 mean 0.929, median 0.543, IQR [0.264, 0.984], RMSE 1.230; T1 mean 0.546, median 0.108, IQR [0.041, 0.678], RMSE 0.888; T2 mean 0.925, median 0.537, IQR [0.265, 0.987], RMSE 1.232; T3 mean 0.944, median 0.601, IQR [0.277, 0.984], RMSE 1.200; DSTAR mean 0.743, median 0.148, IQR [0.104, 0.618], RMSE 1.199. T1 has the lowest RMSE but a strongly zero-inflated median; T2/T3 track the archived T0 distribution.

Paired changes against T0 (mean, MCSE):

| arm | d overfitting | MCSE | d estimation | MCSE | d gain | MCSE |
|---|---|---|---|---|---|---|
| T1 | -6.787 | 3.837 | 8.032 | 6.323 | 1.245 | 3.075 |
| T2 | -6.980 | 3.299 | 8.587 | 5.161 | 1.607 | 2.176 |
| T3 | -6.980 | 3.299 | 8.775 | 5.068 | 1.795 | 2.058 |
| DSTAR | -9.531 | 3.924 | 12.313 | 5.919 | 2.783 | 2.577 |

**Seed 410840.** T0 overfitting loss `75.278`, estimation loss `-119.828`. Under T1/T2/T3 the overfitting loss is `2.579` / `10.065` / `10.065` and the estimation loss is `-9.487` / `-17.452` / `-17.452`.

Maximum T0 replay discrepancy: null train `1.14e-13`, null test `2.27e-13`, inhibited test `1.63e-10` nats.

**Trade-off.** T1 has the best mean overfitting and estimation losses and the best eta RMSE, but its worst single-seed overfitting loss is `20.510` nats (seed 410825) and its median held-out gain is only `0.341`. T2/T3 have a slightly worse mean but a smaller worst case (`10.065` on seed 410840) and a median gain close to the archived T0 value. The choice therefore depends on whether the criterion is the mean, the median or the worst case.

## 4. S04B tail-outlier evaluation (80 histories)

| regime | law | mean | median | min | q05 | q25 | q95 | n<-50 | n<-100 |
|---|---|---|---|---|---|---|---|---|---|
| 4 | T0 | -41.910 | -4.149 | -592.905 | -103.290 | -23.759 | 6.762 | 2 | 1 |
| 4 | T1 | -44.332 | -4.967 | -592.998 | -114.264 | -26.099 | 0.154 | 2 | 1 |
| 4 | T2 | -44.421 | -4.696 | -590.083 | -129.136 | -24.595 | 0.128 | 2 | 2 |
| 5 | T0 | -18.013 | -3.495 | -118.236 | -84.591 | -25.130 | 5.733 | 3 | 1 |
| 5 | T1 | -16.519 | -0.742 | -119.122 | -89.003 | -12.952 | 3.566 | 2 | 1 |
| 5 | T2 | -17.034 | -0.261 | -116.622 | -87.279 | -22.817 | 5.040 | 3 | 1 |
| 6 | T0 | -30.473 | -2.192 | -178.402 | -167.636 | -15.499 | 1.711 | 4 | 3 |
| 6 | T1 | -22.374 | -1.386 | -189.904 | -150.858 | -4.149 | 1.830 | 3 | 2 |
| 6 | T2 | -35.027 | -1.886 | -221.589 | -198.027 | -13.880 | 1.662 | 4 | 3 |
| 7 | T0 | -1.261 | -1.257 | -23.259 | -21.887 | -8.242 | 17.111 | 0 | 0 |
| 7 | T1 | 4.316 | 5.648 | -3.124 | -2.547 | 0.913 | 9.627 | 0 | 0 |
| 7 | T2 | 3.357 | 4.101 | -7.053 | -3.591 | -1.976 | 12.537 | 0 | 0 |

Worst archived-T0 cases and their refitted gains:

| case | regime | T0 | T1 | T2 |
|---|---|---|---|---|
| S4_narrow_short_imm_seed410415 | 4 | -592.90 | -593.00 | -590.08 |
| S6_narrow_short_total_seed410606 | 6 | -178.40 | -5.23 | -221.59 |
| S6_narrow_short_total_seed410607 | 6 | -167.07 | -189.90 | -196.79 |
| S6_narrow_short_total_seed410608 | 6 | -141.17 | -148.80 | -171.74 |
| S5_broad_long_imm_seed410504 | 5 | -118.24 | -119.12 | -116.62 |
| S5_broad_long_imm_seed410510 | 5 | -82.82 | -87.42 | -85.73 |
| S4_narrow_short_imm_seed410420 | 4 | -77.52 | -89.07 | -104.88 |
| S6_narrow_short_total_seed410602 | 6 | -63.36 | -56.47 | -58.19 |

The largest archived tail, `S4_narrow_short_imm_seed410415`, is `-592.90` nats under T0, `-593.00` under T1 and `-590.08` under T2. Its selected inhibition coordinates are essentially identical across the three laws. The S4/S5 tails are therefore not background-trend extrapolation events; they are inhibition-parameter overfitting. T1 repairs the S6 case `S6_narrow_short_total_seed410606` from -178.40 to -5.23 nats, but worsens several other S6 tails, and T2 worsens that same case to -221.59. The regime-level means improve under T1 for S6 and S7, but the extreme negative tail survives.

The archived fitted trend is essentially uncorrelated with the held-out gain across the 80 histories (null `d`: `0.051`; inhibited `d`: `-0.016`). The ten worst T0 gains also span both signs of `d`. This is direct evidence that the tail is not a trend-extrapolation effect.

## 5. New Zealand three-fold controls

| fold | T0 free d | T1 stationary | T2 clamp | T3 orth+clamp |
|---|---|---|---|---|
| fold_50 | -16.518 | -8.504 | -24.791 | -24.791 |
| fold_65 | -0.075 | 0.000 | 0.267 | 0.267 |
| fold_80 | -1.030 | -2.927 | -2.374 | -2.374 |
| total | -17.623 | -11.431 | -26.899 | -26.899 |

The sealed fixed-null and zero-trend controls are `-5.006` and `-11.431` nats. T1 coincides with the sealed zero-trend fit. On Fold 1 the T2 and T3 values coincide with the sealed clamped counterfactual because, with `T0 = 2 T_origin`, the clamped clock is identical to the archived clock on the training window; the training likelihood cannot identify the test-window level, so a refit returns the same maximum-likelihood state.

## 6. California interior EP+ baseline

| fold | T0 | T1 | T2 | T3 | T1-T0 | T2-T0 | T3-T0 |
|---|---|---|---|---|---|---|---|
| california_fold_0 | 14.046 | 20.239 | 15.665 | 15.665 | 6.193 | 1.619 | 1.619 |
| california_fold_1 | 38.365 | 42.682 | 39.079 | 39.079 | 4.317 | 0.714 | 0.714 |
| california_fold_2 | 24.645 | 24.818 | 24.661 | 24.661 | 0.173 | 0.016 | 0.016 |

Totals: T0 `77.056`, T1 `87.739`, T2 `79.405`, T3 `79.405` nats.

All three folds select `eta_hat = 0` on the training attenuation profile at the fixed `(ell0, psi)` grid, so the T3 residualisation has no inhibited-arm effect; the T2 and T3 rows are identical by construction. The T0 evaluator reproduces the sealed interior plane-normalised test joint score exactly (offset 0.0 on every fold); the interior total gain is 77.056 nats, distinct from the bound-pinned 69.55-nat total. The paired law differences are on the same fixed Sobol proposal.

## 7. Interpretation

- **T1 removes the trend channel entirely.** It eliminates the fitted `d` and the trend--depletion collinearity, and it is the only synthetic arm that cannot manufacture a positive future slope. Its cost is a misspecified background when the generating trend is real.
- **T2 and T3 remove future extrapolation but not in-sample trend fitting.** They are therefore forecast-admissible. They do not uniformly improve held-out performance: on S8 the paired gain change is mixed, and on New Zealand Fold 1 the clamped arm is worse than the archived free trend because the positive extrapolation was, in that sample, beneficial. This is a negative result for the hypothesis that clamping alone recovers the loss.
- **The S04B tail outliers** are the clearest test. T1 and T2 are compared with the archived T0 tails at the same 80 histories and the same fixed spatial/mark laws.
- **California EP+** improves under T1 by several nats on every fold, while T2/T3 give smaller improvements. The improvement is a null-backbone effect, not an attenuation effect, because the profile selects zero attenuation in all folds.

## 8. What changed against the handoff expectation

1. **The S8 blow-up hypothesis is supported.** Seed 410840's +75.28-nat overfitting loss is a trend-extrapolation event. Removing the positive future clock collapses it to +2.58 (T1), +10.07 (T2/T3) and +1.10 (conditional true trend). The mean S8 estimation loss falls by 8.0-8.8 nats. Under the BIC gate, however, T1 activates only 3/20 alternatives and its gated mean gain falls to 0.98, while T2 retains 12/20 and a gated mean of 2.13. T2 is the best compromise between tail control and gate-supported gain.
2. **The S04B tail hypothesis is not supported for the largest S4/S5 outliers.** The worst case (`S4_narrow_short_imm_seed410415`, -592.90 nats) is -593.00 under T1 and -590.08 under T2. Its fitted inhibition parameters are essentially unchanged across laws. Those tails are inhibition-parameter overfitting, not background-trend extrapolation. T1 does repair most of the S6 and S7 median, but not the single worst S6 case.
3. **The New Zealand clamped counterfactual is not merely a non-refit illustration.** On Fold 1, `T0 = 2 T_origin`, so the clamped clock is identical to the archived clock on the training window. The training likelihood is invariant and the refit returns the same state: the proper T2 fit is the -24.791-nat counterfactual. T1 is the only law that improves the three-fold New Zealand deficit.
4. **California EP+ favours T1, not T2.** The interior total gain rises from 77.06 to 87.74 nats under T1, but only to 79.40 under T2/T3. The attenuation profile selects eta=0 in every fold, so T3 is observationally identical to T2 there.

## 9. Caveats

1. The S8/S04B refits use a frozen tensor-Gauss fast plan for optimisation and the archived adaptive plan (S8) or a high-order fast plan (S04B) for the reported scores. The maximum scored quadrature difference is recorded in the audit and the S8 summary.
2. The S8 true-trend control is conditional: an unrestricted `d = 0.2` refit develops a `p -> 2.5, n -> 0` overfitting ridge on several histories (seed 410821 is documented in `s8/full_dstar_diagnostic.json`), so the control fixes the archived T0 trigger nuisance in both arms. The unrestricted-refit instability is itself a finite-sample finding.
3. The New Zealand fits hold the archived per-fold trigger/stress kernels and productivity ratio fixed, as in the sealed trend controls. They are not a new kernel search.
4. The California EP+ evaluation uses one fixed Sobol test proposal and a three-point `(ell0, psi)` profile grid. The T0 evaluator reproduces the sealed interior baseline exactly on that proposal; the absolute interior total is 77.056 nats, not the bound-pinned 69.55-nat total.
5. These are conditional synthetic and regional procedure comparisons, not physical inhibition claims, global optima or prospective forecast validation.

## 10. Appendix: S8 per-history contrasts

| seed | T0 over | T0 est | T0 gain | T1 over | T1 est | T1 gain | T2 over | T2 est | T2 gain | T3 over | T3 est | T3 gain |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 410821 | -6.10 | -2.00 | 6.47 | -5.61 | -8.96 | 0.00 | -5.70 | -2.23 | 6.65 | -5.70 | -1.91 | 6.97 |
| 410822 | 19.51 | -23.48 | 1.28 | -4.93 | -1.76 | -1.44 | -0.08 | -12.65 | -7.48 | -0.08 | -13.85 | -8.68 |
| 410823 | -6.12 | 1.15 | 0.97 | -5.33 | -0.52 | 0.09 | -6.87 | -13.35 | -14.27 | -6.87 | 0.19 | -0.73 |
| 410824 | 0.18 | -13.55 | -6.97 | -3.63 | -2.19 | 0.59 | -4.69 | -2.64 | -0.93 | -4.69 | -2.67 | -0.95 |
| 410825 | 15.21 | -34.50 | 6.64 | 20.51 | -46.44 | 0.00 | 5.02 | -23.38 | 7.56 | 5.02 | -24.20 | 6.75 |
| 410826 | -2.18 | -0.41 | 7.32 | -1.14 | -13.30 | -4.52 | -2.50 | 0.49 | 7.91 | -2.50 | 0.63 | 8.05 |
| 410827 | 3.26 | -9.50 | 4.30 | -3.01 | -7.55 | -0.02 | 1.21 | -5.44 | 6.31 | 1.21 | -4.83 | 6.92 |
| 410828 | -4.38 | -4.64 | -0.81 | -5.15 | -1.15 | 1.90 | -4.53 | -5.11 | -1.43 | -4.53 | -5.77 | -2.09 |
| 410829 | -13.84 | -4.26 | 11.15 | -18.24 | -7.17 | 3.84 | -15.00 | -3.11 | 11.14 | -15.00 | -3.41 | 10.84 |
| 410830 | 15.99 | -44.83 | -10.24 | -4.38 | -2.21 | 12.01 | 0.22 | -26.07 | -7.26 | 0.22 | -26.92 | -8.10 |
| 410831 | -10.70 | 0.87 | 12.13 | -6.80 | -11.49 | 3.66 | -10.70 | 0.87 | 12.13 | -10.70 | 0.86 | 12.12 |
| 410832 | -6.09 | -20.26 | -17.60 | -6.62 | -0.75 | 1.37 | -6.25 | -10.66 | -8.16 | -6.25 | -10.83 | -8.33 |
| 410833 | -1.18 | -4.37 | -1.25 | -1.11 | -2.36 | 0.84 | -5.65 | -1.39 | -2.74 | -5.65 | -1.65 | -3.00 |
| 410834 | -4.17 | -8.08 | 0.33 | -6.49 | -6.37 | -0.28 | -6.09 | -3.47 | 3.03 | -6.09 | -3.39 | 3.10 |
| 410835 | 6.94 | -27.33 | 3.80 | 3.12 | -18.22 | 9.09 | 1.23 | -20.73 | 4.68 | 1.23 | -22.27 | 3.15 |
| 410836 | 6.13 | -8.11 | 16.83 | 2.16 | -28.93 | -7.95 | 3.88 | -7.79 | 14.90 | 3.88 | -11.02 | 11.67 |
| 410837 | 1.25 | -7.33 | 4.60 | -0.19 | -16.50 | -6.02 | -4.23 | -4.28 | 2.16 | -4.23 | -5.99 | 0.45 |
| 410838 | -6.36 | -1.03 | 13.51 | -2.21 | -4.32 | 14.36 | -6.35 | -1.12 | 13.44 | -6.35 | -1.02 | 13.54 |
| 410839 | -11.21 | -24.88 | -8.33 | -17.85 | -6.04 | 3.88 | -11.16 | -25.10 | -8.50 | -11.16 | -25.39 | -8.79 |
| 410840 | 75.28 | -119.83 | -38.27 | 2.58 | -9.49 | -0.62 | 10.06 | -17.45 | -1.10 | 10.06 | -17.45 | -1.10 |

## 11. Reproduction

```powershell
python -m experiments.pathway2_trend_parameterization.run_s8 --workers 6
python -m experiments.pathway2_trend_parameterization.run_s04b --workers 6
python -m experiments.pathway2_trend_parameterization.run_nz
python -m experiments.pathway2_trend_parameterization.run_ca --workers 2
python -m experiments.pathway2_trend_parameterization.audit_pathway2
python -m experiments.pathway2_trend_parameterization.build_summary
python -m experiments.pathway2_trend_parameterization.make_report
```

All commands are run from the repository root. No sealed authority or pre-existing live-result file is written.

