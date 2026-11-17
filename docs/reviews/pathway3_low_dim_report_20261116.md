# Pathway 3 — low-dimensional and penalised attenuation estimators

**Scope:** `experiments/pathway3_low_dim_attenuation/` and
`validation/live_results/pathway3_low_dim_20261116/`. The sealed authorities
and all pre-existing live-result files are read-only.

**Date:** 2026-11-17. **Baseline commit:** `a9d7f9d`.

## 1. Executive summary

- The S8 oracle ceiling is reproduced exactly: truth / fixed-null /
  refit-intercept deltas are at most `6.7e-07` / `0.0e+00` /
  `0.0e+00` nats.
- No single freed group explains the 17.8-nat loss. Estimating only (a, eta)
  on the true backbone recovers `17.05`; freeing the scale costs
  `1.76`, freeing the backbone at a fixed scale costs `1.72`, and
  the three-point grid costs `0.85`. The remaining `12.42`
  nats appear only in the joint eight-parameter fit (`0.29`). The
  scale-eta ridge is visible in the eta RMSE jump from `0.176` to
  `1.159`; re-estimating the backbone at a fixed scale keeps the eta
  RMSE at `0.206`.
- The pre-declared winner is the **`E_L1_Shrinkage`** estimator. The S8-only
  ranking would choose `E1D_Profile_3p` (`12.72` nats), but it fails the
  S4 zero-thinning tail: its S4 mean is `-29.32` nats with a
  `-451.82`-nat worst case. Under the admissibility rule (at least 70%
  of the archived S4 loss removed), `E_L1_Shrinkage` is the best admissible
  estimator, with a mean S8 gain of `11.43` nats against the archived
  joint null (`63.1%` of the oracle signal) and a mean gain of
  `3.11` nats against its own stationary null. It removes
  `76.9%` of the archived S4 loss and `82.0%` of the S6
  loss.
- The +16.43/+18.11 ceiling is **not** fully recovered by any three-point scale
  grid; the residual gap is the cost of learning the scale and the trigger
  backbone on 90-120 training events.
- On the S4 zero-realised-thinning bank the winner produces
  `2/20` positive held-out gains (rate `10.0%`, Wilson95
  `[0.028, 0.301]`) and a mean attenuation-specific gain of `-9.666` nats.
  The archived raw eight-parameter S4 gain is `-41.91` nats.
- Wells-Coppersmith rupture scaling selects **zero attenuation** on all three
  California folds for both kernels: the training score slope at eta = 0 is
  negative. The WC scale (0.8-13 km at M4-M6) is far below the empirically
  selected EP+ attenuation scale. This is a clean negative result, not a
  detection.
- New Zealand: the sealed predictive model is temporal-only, so a spatial WC
  scale is not defined. The temporal 1-D profile improves the three-fold
  attenuation deficit from `-17.62` to `-16.02` nats but remains
  negative.

## 2. What was tested

### 2.1 Stepwise degree-of-freedom ladder (S8, 20 histories)

The ladder starts at the full generating truth and frees one parameter group
at a time. Free-8D is the archived eight-parameter joint fit. Two additional
rungs separate the stationary clock from the scale and trigger coordinates:
the seven-parameter stationary free fit and the WC sensitivity.

| rung | mean gain vs archived null | median | MCSE | wins | mean gain vs stationary null | mean eta | eta RMSE | nested |
|---|---|---|---|---|---|---|---|---|
| Step 1: fixed true backbone, fit (a, eta) at (ell*, psi*) | 17.05 | 12.52 | 4.08 | 20/20 | 8.73 | 0.39 | 0.176 | 0/20 |
| Step 2: fixed true backbone, fit (a, eta, ell, psi) | 15.28 | 11.34 | 4.23 | 18/20 | 6.97 | 0.78 | 1.159 | 0/20 |
| Step 3a: stationary null backbone, profile (a, n, eta) at true scale | 13.56 | 9.60 | 3.97 | 18/20 | 5.25 | 0.36 | 0.206 | 0/20 |
| Step 3b: stationary null backbone, (a, n, eta) with 3-scale selection | 12.72 | 9.60 | 4.07 | 16/20 | 4.40 | 0.72 | 1.159 | 0/20 |
| E1D_Profile_2p: (a, eta) + 3-scale selection | 11.74 | 7.80 | 3.78 | 17/20 | 3.43 | 0.60 | 1.160 | 0/20 |
| E1D_Profile_3p: (a, n, eta) + 3-scale selection | 12.72 | 9.60 | 4.07 | 16/20 | 4.40 | 0.72 | 1.159 | 0/20 |
| E_Split_CV: chronological split shrinkage | 11.23 | 7.44 | 3.69 | 17/20 | 2.92 | 0.49 | 0.993 | 2/20 |
| E_L1_Shrinkage: split-selected lambda | 11.43 | 7.79 | 3.68 | 17/20 | 3.11 | 0.57 | 1.163 | 2/20 |
| Free 7-parameter stationary fit | 11.80 | 9.82 | 4.21 | 15/20 | 3.49 | 0.92 | 1.226 | 0/20 |
| E_WC_Rupture sensitivity on S8 | 3.40 | 2.61 | 5.72 | 16/20 | -4.91 | 2.33 | 2.602 | 0/20 |
| Archived free 8-parameter fit | 0.29 | 2.54 | 2.78 | 13/20 | -8.02 | 0.93 | 1.230 | 0/20 |

`gain_vs_archived_joint_null` is the held-out joint score relative to the
archived jointly fitted five-parameter null. `gain_vs_stationary_null` uses the
nested stationary null, so it isolates the attenuation contrast from the d = 0
background change. `eta RMSE` is against eta* = 0.4. `nested` counts exact
eta-hat = 0 returns.

The ladder closes exactly against the sealed estimation loss:

| gap | nats |
|---|---|
| truth -> Step 1 (estimate a, eta) | 1.067 |
| Step 1 -> Step 2 (free ell, psi) | 1.765 |
| Step 2 -> Step 3a (stationary null fit of a, n, c, p; profile a, n at true scale) | 1.718 |
| Step 3a -> E1D_Profile_3p (three-point scale selection) | 0.846 |
| E1D_Profile_3p -> archived Free-8D (joint 8-parameter fit) | 12.422 |
| **total truth -> archived Free-8D** | **17.818** |
| sealed estimation-loss magnitude | 17.818 |
| closure residual | 0.000000 |

The largest single term is the last one: the step from the three-parameter
low-dimensional estimator to the archived eight-parameter joint fit. The
first four steps (intercept-plus-eta, scale, backbone and grid selection)
account for essentially all of the `5.40`-nat gap between the truth
and `E1D_Profile_3p`; the joint free fit accounts for the remaining
`12.42`-nat jump. This is why fixing the scale helps far more than
shrinking `eta` alone.

### 2.2 Estimators

| id | training-only rule | parameters |
|---|---|---|
| `E_1D_Profile` | fit (a, eta) or (a, n, eta) at each of (5,1), (15,5), (50,30) km/d; select by training likelihood plus a log 3 multiplicity term | 2 or 3 |
| `E_L1_Shrinkage` | penalise l_train - lambda * eta * mean(G_train); lambda in {0.5, 1, 2}, selected on the second training half; a per-event penalty is a declared sensitivity | 2 |
| `E_Split_CV` | fit on [30, 212.5); choose alpha in {0, 0.25, 0.5, 0.75, 1} on [212.5, 395); re-balance a on the full training window | 2 |
| `E_WC_Rupture` | fix ell_j = 10^(-2.44 + 0.59 M_j) km and gamma = 0.75 log 10; fit (a, eta) or (a, n, eta), optionally profiling psi | 2-4 |

Every estimator receives only the training phase. The held-out phase is used
only by the final scoring call.

## 3. S8 results

Three facts stand out.

1. **The fixed-backbone scale cost.** Moving from Step 1 to Step 2
   (`17.05` to `15.28` nats) costs `1.76` nats. That is the
   price of estimating (ell, psi) rather than fixing them at the generating
   values.
2. **The backbone cost is comparable.** Moving from the true backbone to the
   stationary fitted backbone costs `1.72` nats. The archived free
   eight-parameter fit then loses the remaining `13.27` nats. The two
   channels are of similar size; no single freed group explains the whole
   estimation loss.
3. **The three-point grid is a real constraint.** `E1D_Profile_2p` and
   `E1D_Profile_3p` are `11.74` and `12.72` nats against the
   archived null. The 3D (a, n, eta) variant beats the 2D (a, eta) variant on
   the mean and median because profiling `n` recovers part of the backbone
   cost; the eta RMSE is essentially unchanged (1.159 vs 1.160) because the
   scale-selection ridge dominates it. Freeing the scale (Step 2) is different:
   it raises the eta RMSE from 0.176 to 1.159, which is the finite-sample
   identifiability ridge described in the handoff.

The winner declared by the pre-declared admissibility rule (highest mean S8
gain among estimators that remove at least 70% of the archived S4 loss) is
**`E_L1_Shrinkage`**. The full ranking, including the S8-only admissible screen,
is:

| rank | estimator | mean S8 gain vs stationary null | median | MCSE | eta RMSE | nested | S4 mean | S4 positive | admissible |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `E1D_Profile_3p` | 4.404 | 5.273 | 1.326 | 1.159 | 0/20 | -29.32 | 10.0% | no |
| 2 | `E1D_Profile_2p` | 3.432 | 3.240 | 1.225 | 1.160 | 0/20 | -18.79 | 15.0% | no |
| 3 | `E_L1_Shrinkage` | 3.114 | 2.968 | 1.013 | 1.163 | 2/20 | -9.67 | 10.0% | yes |
| 4 | `E_Split_CV` | 2.917 | 1.924 | 1.005 | 0.993 | 2/20 | -9.18 | 10.0% | yes |

## 4. S04B bank controls

| bank | N | archived raw gain mean | archived raw median | winner mean | winner median | positive gains | eta > 0 | mean eta |
|---|---|---|---|---|---|---|---|---|
| S4 narrow/short immigrant (zero realised thinning) | 20 | -41.91 | -4.15 | -9.67 | -0.32 | 2/20 (10.0%) | 13/20 | 0.086 |
| S5 broad/long immigrant | 20 | -18.01 | -3.49 | -17.21 | 0.00 | 10/20 (50.0%) | 18/20 | 0.499 |
| S6 narrow/short total | 20 | -30.47 | -2.19 | -5.50 | 0.00 | 7/20 (35.0%) | 14/20 | 0.078 |
| S7 broad/long total | 20 | -1.26 | -1.26 | 6.09 | 6.06 | 20/20 (100.0%) | 20/20 | 1.746 |

`raw replay` is the archived uninhibited-to-inhibited contrast recomputed under
the same evaluator. The S4 bank has zero realised thinning in its generator
receipt: it is the S4 zero-thinning null control. The S6 bank is the primary
positive total-intensity control; S5 and S7 are secondary positive banks. The
winner returns the exact null on 7/20 S4 histories and near-zero on most of the
remainder, but a few large negative outliers dominate the mean; it reduces the
S4 and S6 mean losses by `76.9%` and `82.0%`, while
retaining a positive mean on S7. The unscreened `E1D_Profile_3p` arm has a much
worse S4 tail (`-29.32` mean, `-451.82` minimum); that failure is
the reason the admissibility screen is part of the winner rule. The raw S4/S6
losses are dominated by inhibition-coordinate overfitting, not by the
background clock; the stationary null removes the clock channel separately.
The generator counters sharpen the interpretation: S4 rejects 1 immigrant and
no offspring (zero realised thinning), S6 rejects `134` of
`1,335` offspring proposals (`10.0%`), and
S7 rejects `165` of `168` (`98.2%`). S6 is
therefore a weak realised-thinning control, while S7 is the strong positive
control and the only bank where every estimator retains a positive mean.

## 5. California: Wells-Coppersmith rupture scaling

The WC scale is fixed at

    ell_j = 10^(-2.44 + 0.59 M_j) km,      gamma = 0.75 log 10,

with M0 = 3 for these catalogues, so ell0 = 0.214 km and the exponent is 0.59.
The primary arm estimates (a, eta) at psi = 5 d on the sealed interior EP+
backbone. `WC_a_n_eta` also profiles n; the `psi` variants profile the
relaxation time.

| kernel | arm | mean gain vs null | median | mean eta | mean psi (d) | eta = 0 |
|---|---|---|---|---|---|---|
| `mono` | `mono_WC_eta` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `mono` | `mono_WC_a_eta` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `mono` | `mono_WC_a_n_eta` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `mono` | `mono_WC_a_eta_psi` | 0.000 | 0.000 | 0.000 | 3.35 | 2/3 |
| `mono` | `mono_WC_a_n_eta_psi` | 0.000 | 0.000 | 0.000 | 3.35 | 2/3 |
| `ann2` | `ann2_WC_eta` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `ann2` | `ann2_WC_a_eta` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `ann2` | `ann2_WC_a_n_eta` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `ann2` | `ann2_WC_a_eta_psi` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |
| `ann2` | `ann2_WC_a_n_eta_psi` | 0.000 | 0.000 | 0.000 | 5.00 | 3/3 |

`gain_vs_null` is the held-out joint score relative to the arm's own nested
null on the same frozen test proposal. The quadrature check re-scores every
selected state on an independent seed; the maximum absolute delta is
`0.00` nats. The training slope at eta = 0 is negative for both kernels
(-801 nats per unit eta for `mono`, -6753 for `ann2` on fold 0), so the exact
eta-hat = 0 boundary is the correct training solution. The WC scale is
substantially smaller than the 15-50 km scale selected by the free EP+
attenuation fit; this is the scientific content of the negative result.

## 6. New Zealand: scope and temporal analogue

The sealed New Zealand predictive model is a temporal renewal/Omori mixture
with `times` and `excess` only; it has **no epicentral-distance kernel**. A
Wells-Coppersmith rupture length is therefore undefined in that model. This is
recorded as a scope limitation, not silently replaced. The temporal analogue of
`E_1D_Profile` holds the archived trigger and stress kernels fixed and
estimates (a, eta) or (a, n, eta) with d = 0.

| arm | fold_50 | fold_65 | fold_80 | total | mean eta |
|---|---|---|---|---|---|
| `E1D_Profile_2p` (temporal analogue) | -11.64 | 0.00 | -4.28 | -15.92 | 0.131 |
| `E1D_Profile_3p` (temporal analogue) | -11.69 | 0.00 | -4.33 | -16.02 | 0.133 |
| `E_L1_Shrinkage` (temporal analogue) | -10.07 | 0.00 | 0.00 | -10.07 | 0.102 |
| Stationary full (a, n, eta) | -11.69 | 0.00 | -4.33 | -16.02 | n/a |
| Archived free-d comparator | -16.52 | -0.08 | -1.03 | -17.62 | n/a |

The temporal profile improves the free-d deficit by roughly `1.60`
nats but does not turn it positive. `E_L1_Shrinkage` is the best New Zealand
arm (`-10.07` nats, `7.56` nats better than the archived
free-d comparator): it zeros the unsupported attenuation on folds 65 and 80 and
removes `1.63` nats of the fold-50 loss. This is consistent with
Pathway 2's T1 result: removing the trend clock helps, but the residual
attenuation contrast is not supported out of sample on these three folds.

## 7. Audit

| check | status |
|---|---|
| `sealed_custody` | pass |
| `source_pins` | pass |
| `wells_coppersmith_scale` | pass |
| `native_annular_rows` | pass |
| `native_deficit_fixture` | pass |
| `s8_archived_plan_replay` | pass |
| `s8_gain_closures` | pass |
| `s8_l1_kkt` | pass |
| `training_only_reproduction` | pass |
| `s04b_bank_audit` | pass |
| `california_wc_audit` | pass |
| `nz_scope_and_closure` | pass |
| `top_level_summary` | pass |
| `static_training_only_source` | pass |

The audit re-hashes the sealed inputs, checks tracked-file custody with git,
recomputes every S8 arm on the archived adaptive plan for two seeds (including
the worst-case seed 410840), re-derives the gain and joint decompositions,
checks the L1 KKT conditions, verifies the native annular rows against an
independent NumPy formula and central finite differences, verifies the joint
deficit against a direct recurrence, and checks the S04B and California
closures. The maximum archived-plan vs reported S8 score delta is recorded in
`independent_audit.json`.

## 8. Limitations

1. **S04 unit-mark null banks.** The named `Uniform null` and `Smooth null`
   S04 histories are not part of the reproducible S04B corpus; they belong to
   the earlier unit-mark fixed-backbone study. They were not regenerated or
   relabelled. The S4 bank (zero realised thinning) is the explicit
   S4 zero-thinning control. This is a scope reduction relative to the handoff.
2. **New Zealand WC.** The sealed NZ model has no distance kernel, so
   `E_WC_Rupture` cannot be evaluated there. The temporal 1-D profile is the
   declared analogue.
3. **Local optima.** The fits use multi-start L-BFGS-B on a smooth analytic
   objective. The exact eta = 0 state is always an eligible candidate. The
   results certify the executed recipe, not a global optimum.
4. **Quadrature plan.** Optimisation uses a frozen tensor-Gauss plan; reported
   scores use a 20x20 spatial and 24-node time plan at order 16. The audit
   replays the archived adaptive plan and records the deltas. The truth at
   order 32 is evaluated on the same plan and reproduces the sealed oracle.
5. **Finite-sample scale.** The grid has three points. A denser or continuous
   scale profile would change the exact trade-off and is outside the
   pre-declared design.

## 9. Reproduction

```powershell
python -m experiments.pathway3_low_dim_attenuation.run_s8 --workers 6 --resume
python -m experiments.pathway3_low_dim_attenuation.run_banks --workers 6 --resume
python -m experiments.pathway3_low_dim_attenuation.run_california --workers 3
python -m experiments.pathway3_low_dim_attenuation.run_nz
python -m experiments.pathway3_low_dim_attenuation.build_summary
python -m experiments.pathway3_low_dim_attenuation.audit_pathway3
python -m experiments.pathway3_low_dim_attenuation.make_report
```

## Appendix: S8 per-history contrasts

| seed | Step 1 | Step 2 | E1D-2p | E1D-3p | L1 | Free-8D | Free-8D eta |
|---|---|---|---|---|---|---|---|
| 410821 | 8.57 | 6.69 | 3.03 | 6.11 | 3.07 | 6.47 | 0.72 |
| 410822 | 22.96 | 19.21 | 24.02 | 19.51 | 24.29 | 1.28 | 0.87 |
| 410823 | 2.74 | -0.12 | -1.44 | -2.04 | -0.72 | 0.97 | 0.12 |
| 410824 | 6.16 | 5.42 | 8.12 | 8.56 | 8.11 | -6.97 | 0.21 |
| 410825 | 38.04 | 39.72 | 31.98 | 26.78 | 17.85 | 6.64 | 0.28 |
| 410826 | 8.20 | 7.46 | 2.63 | 6.17 | 2.62 | 7.32 | 0.29 |
| 410827 | 13.54 | 13.55 | 10.49 | 9.98 | 10.46 | 4.30 | 0.55 |
| 410828 | 2.94 | 3.29 | 3.44 | -1.40 | 3.41 | -0.81 | 1.36 |
| 410829 | 12.88 | 14.66 | 12.50 | 12.50 | 12.50 | 11.15 | 4.00 |
| 410830 | 28.52 | 25.20 | 20.80 | 25.49 | 26.71 | -10.24 | 1.31 |
| 410831 | 10.87 | 11.86 | 6.62 | 10.97 | 6.44 | 12.13 | 0.18 |
| 410832 | 0.45 | -8.47 | -7.08 | -7.76 | -6.02 | -17.60 | 0.04 |
| 410833 | 1.66 | 2.21 | -1.57 | -2.49 | -1.48 | -1.25 | 0.71 |
| 410834 | 7.53 | 7.79 | 4.77 | 4.01 | 4.75 | 0.33 | 0.37 |
| 410835 | 27.74 | 23.88 | 9.67 | 12.93 | 9.67 | 3.80 | 4.00 |
| 410836 | 25.41 | 21.81 | 9.64 | 14.50 | 9.62 | 16.83 | 1.61 |
| 410837 | 12.16 | 10.82 | 7.49 | 9.23 | 7.48 | 4.60 | 0.53 |
| 410838 | 13.57 | 13.32 | 3.88 | 8.21 | 3.93 | 13.51 | 0.87 |
| 410839 | 15.50 | 5.42 | 13.57 | 12.57 | 13.52 | -8.33 | 0.44 |
| 410840 | 81.48 | 81.92 | 72.32 | 80.50 | 72.32 | -38.27 | 0.10 |
