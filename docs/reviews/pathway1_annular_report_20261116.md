# Pathway 1 — Annular attenuation kernels and the California stress shadow

**Date:** 16 November 2026  
**Baseline commit:** `a9d7f9d`  
**Isolated code:** `experiments/pathway1_annular_attenuation/`  
**Isolated results:** `validation/live_results/pathway1_annular_20261116/`

## Question

Does replacing the epicentral-peaked kernel `(1+r^2/ell_j^2)^-2` with an
annular or trigger-core-shielded kernel make the null score slope positive
on the California training folds, and does the fitted annular attenuation
model improve held-out log score over the interior-scale EP+ baseline?

## Design

Four spatial attenuation profiles are compared at the same EP+ backbone:
the monotone epicentral kernel (`mono`), a first-order ring (`ann1`), a
second-order ring (`ann2`), and a trigger-core-shielded kernel (`shield`).
Each is tested with rupture-scaled `ell_j = ell0 10^(0.5 m_j)` and with
unscaled `ell_j = ell0`. The attenuation field multiplies the total
intensity by `exp(-eta G)`; the exact `eta=0` state is retained in every
search. The primary baseline is the relaxed interior-scale EP+ fit with
`sigma0 >= 0.05 km`; the bound-pinned 2 km EP+ fit is retained as a
completeness comparator.

All slopes and profile curves use analytic derivatives. Training
integrals use the frozen power-14 scrambled-Sobol proposal; held-out
checks use power 16. The compiled row contractions were verified against
independent NumPy formulas and central finite differences before any
optimization. Profile curves are concave in `eta`; a non-positive null
slope returns the exact boundary `eta_hat = 0`.

## Stage P1.1 — Null score slopes and eta profiles

The full grid is 2016 rows (2 baselines ×
4 kernels × 2 scalings × 7 × 6 scale pairs × 3 folds),
evaluated with the frozen `power=14` training proposal and the `power=16`
held-out proposal.

**Positive total-intensity null slopes:** 11 of
2016 rows. **Positive immigrant-only slopes:**
52 of 2016 rows.

The largest training profile gain among positive total-slope rows is
0.0370 nats; among positive immigrant-slope rows it is
0.0935 nats. Both are far below the project's 1.9207-nat
profile threshold, so the sign reversal is present in the primary quadrature
but scientifically negligible; the headline-state integration checks below
show that it is not quadrature-resolved.

| baseline | kernel | scaling | positive rows | best slope | best ell/psi | best train Δ | test Δ at eta-hat |
|---|---|---|---|---|---|---|---|
| interior | mono | scaled | 0 | -6436.33 | 2/1 | 0.00 | 0.00 |
| interior | mono | unscaled | 0 | -105.38 | 2/1 | 0.00 | 0.00 |
| interior | ann1 | scaled | 0 | -1531.22 | 50/1 | 0.00 | 0.00 |
| interior | ann1 | unscaled | 0 | -331.43 | 2/2 | 0.00 | 0.00 |
| interior | ann2 | scaled | 0 | -1000.88 | 50/1 | 0.00 | 0.00 |
| interior | ann2 | unscaled | 0 | -656.97 | 2/1 | 0.00 | 0.00 |
| interior | shield | scaled | 0 | -5337.22 | 2/1 | 0.00 | 0.00 |
| interior | shield | unscaled | 0 | -56.74 | 2/1 | 0.00 | 0.00 |
| bound_2km | mono | scaled | 0 | -5209.35 | 2/1 | 0.00 | 0.00 |
| bound_2km | mono | unscaled | 0 | -211.02 | 2/1 | 0.00 | 0.00 |
| bound_2km | ann1 | scaled | 0 | -1803.13 | 50/1 | 0.00 | 0.00 |
| bound_2km | ann1 | unscaled | 0 | -280.34 | 10/90 | 0.00 | 0.00 |
| bound_2km | ann2 | scaled | 0 | -1177.89 | 50/1 | 0.00 | 0.00 |
| bound_2km | ann2 | unscaled | 11 | 536.85 | 5/90 | 0.04 | 0.00 |
| bound_2km | shield | scaled | 0 | -4188.84 | 2/1 | 0.00 | 0.00 |
| bound_2km | shield | unscaled | 0 | -24.82 | 2/1 | 0.00 | 0.00 |

### Headline state (`ell0 = 15 km`, `psi = 5 d`)

| fold | baseline | kernel | scaling | event sum | exposure integral | total slope | immigrant slope |
|---|---|---|---|---|---|---|---|
| california_fold_0 | bound_2km | ann1 | scaled | 16432.46 | 11702.82 | -4729.64 | -596.29 |
| california_fold_0 | bound_2km | ann1 | unscaled | 36163.47 | 33479.52 | -2683.95 | -7.21 |
| california_fold_0 | bound_2km | ann2 | scaled | 11036.14 | 7847.69 | -3188.45 | -414.80 |
| california_fold_0 | bound_2km | ann2 | unscaled | 35874.17 | 31361.24 | -4512.93 | -9.37 |
| california_fold_0 | bound_2km | mono | scaled | 75313.90 | 59415.48 | -15898.42 | -543.99 |
| california_fold_0 | bound_2km | mono | unscaled | 23137.84 | 21965.14 | -1172.70 | -2.72 |
| california_fold_0 | bound_2km | shield | scaled | 48647.05 | 34771.73 | -13875.32 | -538.69 |
| california_fold_0 | bound_2km | shield | unscaled | 8911.09 | 8089.22 | -821.86 | -2.13 |
| california_fold_0 | interior | ann1 | scaled | 16432.46 | 12228.38 | -4204.08 | -407.59 |
| california_fold_0 | interior | ann1 | unscaled | 36163.47 | 30996.27 | -5167.21 | -6.35 |
| california_fold_0 | interior | ann2 | scaled | 11036.14 | 8172.00 | -2864.14 | -309.38 |
| california_fold_0 | interior | ann2 | unscaled | 35874.17 | 29421.54 | -6452.63 | -7.58 |
| california_fold_0 | interior | mono | scaled | 75313.90 | 59027.09 | -16286.81 | -310.02 |
| california_fold_0 | interior | mono | unscaled | 23137.84 | 20822.58 | -2315.26 | -2.77 |
| california_fold_0 | interior | shield | scaled | 57229.58 | 42549.00 | -14680.58 | -308.25 |
| california_fold_0 | interior | shield | unscaled | 12585.19 | 10628.40 | -1956.80 | -2.34 |
| california_fold_1 | bound_2km | ann1 | scaled | 16451.89 | 11658.17 | -4793.72 | -591.21 |
| california_fold_1 | bound_2km | ann1 | unscaled | 36235.60 | 33562.18 | -2673.42 | -5.87 |
| california_fold_1 | bound_2km | ann2 | scaled | 11041.43 | 7798.89 | -3242.54 | -397.76 |
| california_fold_1 | bound_2km | ann2 | unscaled | 35895.17 | 31361.56 | -4533.61 | -7.78 |
| california_fold_1 | bound_2km | mono | scaled | 75543.79 | 59260.39 | -16283.40 | -577.06 |
| california_fold_1 | bound_2km | mono | unscaled | 23345.95 | 21941.06 | -1404.88 | -2.04 |
| california_fold_1 | bound_2km | shield | scaled | 48376.02 | 34377.29 | -13998.73 | -571.69 |
| california_fold_1 | bound_2km | shield | unscaled | 8878.14 | 8026.74 | -851.39 | -1.66 |
| california_fold_1 | interior | ann1 | scaled | 16451.89 | 12101.41 | -4350.48 | -438.90 |
| california_fold_1 | interior | ann1 | unscaled | 36235.60 | 31238.25 | -4997.34 | -4.89 |
| california_fold_1 | interior | ann2 | scaled | 11041.43 | 8091.48 | -2949.94 | -325.08 |
| california_fold_1 | interior | ann2 | unscaled | 35895.17 | 29597.43 | -6297.74 | -5.45 |
| california_fold_1 | interior | mono | scaled | 75543.79 | 58727.43 | -16816.36 | -365.11 |
| california_fold_1 | interior | mono | unscaled | 23345.95 | 20893.83 | -2452.11 | -2.09 |
| california_fold_1 | interior | shield | scaled | 56860.79 | 41800.20 | -15060.59 | -363.36 |
| california_fold_1 | interior | shield | unscaled | 12499.91 | 10530.51 | -1969.40 | -1.80 |
| california_fold_2 | bound_2km | ann1 | scaled | 21649.10 | 16353.29 | -5295.81 | -715.06 |
| california_fold_2 | bound_2km | ann1 | unscaled | 52129.94 | 47424.47 | -4705.47 | -15.48 |
| california_fold_2 | bound_2km | ann2 | scaled | 15027.81 | 11386.98 | -3640.82 | -474.86 |
| california_fold_2 | bound_2km | ann2 | unscaled | 53682.16 | 46507.13 | -7175.02 | -22.84 |
| california_fold_2 | bound_2km | mono | scaled | 101080.00 | 80982.11 | -20097.89 | -739.17 |
| california_fold_2 | bound_2km | mono | unscaled | 32195.65 | 29205.28 | -2990.37 | -4.79 |
| california_fold_2 | bound_2km | shield | scaled | 56043.57 | 41150.16 | -14893.42 | -723.19 |
| california_fold_2 | bound_2km | shield | unscaled | 10867.67 | 9494.75 | -1372.92 | -4.03 |
| california_fold_2 | interior | ann1 | scaled | 21649.10 | 16860.90 | -4788.20 | -464.29 |
| california_fold_2 | interior | ann1 | unscaled | 52129.94 | 44698.11 | -7431.82 | -9.18 |
| california_fold_2 | interior | ann2 | scaled | 15027.81 | 11647.64 | -3380.17 | -342.91 |
| california_fold_2 | interior | ann2 | unscaled | 53682.16 | 43612.20 | -10069.96 | -12.38 |
| california_fold_2 | interior | mono | scaled | 101080.00 | 80669.39 | -20410.61 | -403.70 |
| california_fold_2 | interior | mono | unscaled | 32195.65 | 28822.68 | -3372.97 | -3.42 |
| california_fold_2 | interior | shield | scaled | 73056.75 | 55286.40 | -17770.35 | -400.43 |
| california_fold_2 | interior | shield | unscaled | 16941.34 | 14123.48 | -2817.86 | -3.02 |

The exact bound-pinned example reproduces the handoff: for fold 0, `mono`, scaled,
`ell0=15 km`, `psi=5 d`, the event sum is 75,313.903, the exposure integral is
59,415.479 and the null slope is −15,898.423 nats per unit eta.

The largest positive total-intensity slope anywhere in the grid is
536.85 at
`california_fold_1` / `bound_2km`
/ `ann2`
(unscaled),
`ell0=5 km`,
`psi=90 d`.

The interior-scale baseline has no positive total-intensity slope anywhere in the grid. Any positive rows are confined to the bound-pinned 2 km comparator and to narrow unscaled long-memory corners; they are disclosed here as a sensitivity, not as evidence at the interior baseline. Independent scrambles and a power-16/18 reference at the headline state differ from the primary slope by at most 302.24 nats (median 25.23), on slopes of order 10^3–10^4. The sign of the large negative slopes is therefore robust, but the small positive bound-pinned corner should not be read as a quadrature-resolved effect.

## Stage P1.2 — Full joint optimization

Twelve parameters `(a,d,n,log c,p,log sigma0,alpha_s,q,eta,log ell0,log psi,gamma)`
were optimized with analytic gradients from the exact interior/bound null and
the six prescribed positive starts. The exact `eta=0` state was retained as a
nested candidate. Selected positive eta rows: **0
of 24**; exact nested-null rows: **24
of 24**.

| kernel | selected eta>0 | nested null | training gain | test gain | attenuation gain |
|---|---|---|---|---|---|
| mono | 0 | 6 | 0.000 | 0.000 | 0.000 |
| ann1 | 0 | 6 | 0.000 | 0.000 | 0.000 |
| ann2 | 0 | 6 | 0.000 | 0.000 | 0.000 |
| shield | 0 | 6 | 0.000 | 0.000 | 0.000 |

Held-out scores use four independent `power=16` scrambles (`20261250..20261253`);
the standard error is the seed-to-seed standard deviation divided by sqrt(4).
The attenuation gain compares the selected state with its own `eta=0` state at
the same backbone, isolating the annular attenuation contribution from nuisance
re-estimation. The total gain compares the selected state with the EP+ baseline
state.
The bound-pinned jobs also found eta=0 backbones with lower training NLL (total 443.09 nats over 12 rows). These are nuisance relaxations of the 2 km bound, not attenuation effects: their eta is exactly zero and their attenuation contrast is identically zero. Their held-out gain is 36.13 nats in total (seeds 20261250–20261251).


| fold | baseline | kernel | eta | ell0 | psi | train gain | test gain | atten. gain | SE |
|---|---|---|---|---|---|---|---|---|---|
| california_fold_0 | bound_2km | ann1 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | bound_2km | ann2 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | bound_2km | mono | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | bound_2km | shield | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | interior | ann1 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | interior | ann2 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | interior | mono | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_0 | interior | shield | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | bound_2km | ann1 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | bound_2km | ann2 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | bound_2km | mono | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | bound_2km | shield | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | interior | ann1 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | interior | ann2 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | interior | mono | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_1 | interior | shield | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | bound_2km | ann1 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | bound_2km | ann2 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | bound_2km | mono | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | bound_2km | shield | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | interior | ann1 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | interior | ann2 | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | interior | mono | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |
| california_fold_2 | interior | shield | 0.0000 | 20.00 | 5.00 | 0.000 | 0.000 | 0.000 | 0.000 |

Paired calendar-block summaries of the attenuation contrast (total nats and
non-overlapping block-bootstrap 95% intervals; adjacent blocks are dependent,
so these are descriptive multi-scale sensitivities). Every interval is
identically zero because the selected state is the exact η = 0 null:

| fold | baseline | kernel | 90 d | 180 d | 365 d |
|---|---|---|---|---|---|
| california_fold_0 | bound_2km | ann1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | bound_2km | ann2 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | bound_2km | mono | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | bound_2km | shield | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | interior | ann1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | interior | ann2 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | interior | mono | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_0 | interior | shield | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | bound_2km | ann1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | bound_2km | ann2 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | bound_2km | mono | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | bound_2km | shield | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | interior | ann1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | interior | ann2 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | interior | mono | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_1 | interior | shield | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | bound_2km | ann1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | bound_2km | ann2 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | bound_2km | mono | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | bound_2km | shield | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | interior | ann1 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | interior | ann2 | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | interior | mono | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |
| california_fold_2 | interior | shield | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] | 0.00 [0.00, 0.00] |

Supplemental η = 0 nuisance refits of the bound-pinned baseline:

| fold | kernel | training gain | held-out gain |
|---|---|---|---|
| california_fold_0 | ann1 | 34.63 | 0.28 |
| california_fold_0 | ann2 | 34.63 | 0.28 |
| california_fold_0 | mono | 34.63 | 0.28 |
| california_fold_0 | shield | 34.63 | 0.28 |
| california_fold_1 | ann1 | 34.17 | 8.01 |
| california_fold_1 | ann2 | 34.17 | 8.01 |
| california_fold_1 | mono | 34.17 | 8.02 |
| california_fold_1 | shield | 34.17 | 8.01 |
| california_fold_2 | ann1 | 41.97 | 0.74 |
| california_fold_2 | ann2 | 41.97 | 0.74 |
| california_fold_2 | mono | 41.97 | 0.74 |
| california_fold_2 | shield | 41.97 | 0.74 |

## Stage P1.3 — Synthetic ann2 control bank

20 histories were generated under the ann2 law with the archived S8
chronological simulator, ETAS backbone and mark law. The achieved thinning
fraction is 25.34% (range
18.85–36.95%)
and the achieved test-event count is 98.2
(range 79.0–116.0).

| quantity | mean ± MCSE |
|---|---|
| mono-kernel held-out gain | -34.986 ± 27.067 (median -2.285, wins 6/20) |
| ann2-kernel held-out gain | -22.319 ± 17.472 (median -2.649, wins 9/20) |
| true-law oracle gain | 13.107 ± 2.218 (median 10.505, wins 20/20) |
| mono shortfall vs oracle | 48.094 ± 27.555 (median 14.193, wins 19/20) |
| ann2 shortfall vs oracle | 35.427 ± 18.025 (median 14.716, wins 19/20) |
| ann2 recovery fraction | -1.529 ± 0.906 (median -0.212, wins 9/20) |

The ann2 estimator beats the mono estimator in
11/20 histories and beats the null in
9/20; the mono estimator beats the null in
6/20.

The mean gains are dominated by one history whose two fitted estimators both
lose several hundred nats; the median is the robust summary. Read together, the
bank says that the ann2 shadow is detectable when the generating law is known
(20/20 positive oracle gains), but at
about 95 held-out events the need to estimate the attenuation coordinates
outweighs the kernel-shape benefit. The ann2 estimator is less bad than mono on
average but does not recover the oracle gain in the median history.

## Conclusion

The hypothesis is rejected at the interior-scale EP+ baseline. Replacing the
epicentral-peaked kernel with `ann1`, `ann2` or `shield` reduces the magnitude
of the negative total-intensity null slope but does not reverse its sign
anywhere in the interior grid. The immigrant-only channel does produce 52 small
positive slopes, but their largest training profile gain is 0.0935 nats, also
far below the 1.9207-nat threshold. The only positive total-intensity slopes are 11 rows at the
bound-pinned 2 km comparator, all `ann2` unscaled `ell0 = 5 km`; their training
profile gains are below 0.04 nats and the headline-state quadrature sensitivity
(up to 302 nats) is far larger than that gain, so they are not a resolved
stress-shadow detection.

The full 12-parameter joint search selects the exact nested η = 0 state in
24/24 rows, including the extra sensitivity start at the strongest positive
P1.1 corner. The held-out attenuation contrast and all 90/180/365-day block
intervals are therefore identically zero. The bound-pinned jobs do find η = 0
backbones with lower training NLL and a modest held-out gain, but these are
nuisance relaxations of the 2 km bound, not annular attenuation.

The synthetic bank sharpens the interpretation. When the true law is annular,
the oracle gain is +13.1 nats and positive in 20/20 histories, so the shadow is
detectable in principle. At about 95 held-out events, however, both fitted
estimators lose held-out score on average (mono −35.0, ann2 −22.3 nats), and the
ann2 estimator's median recovery of the oracle gain is negative. Estimation
variance, not kernel shape, is the binding constraint at this sample size.

The practical conclusion is that the California `eta = 0` result is not an
artifact of the epicentral peak. An annular or core-shielded stress shadow is
not supported by these training folds at the available resolution, and even a
correctly specified annular estimator would not be expected to improve
held-out score at the current test-event count.

## Independent audit

The independent audit **passed**. It checks sealed-file integrity, native
kernel formulas against a separate NumPy implementation, full objective
gradients against central finite differences for every kernel and scaling,
a stratified NumPy recomputation of the null slopes, profile concavity and
boundary logic, P1.2 selected-state consistency, and synthetic summary
arithmetic. The machine-readable receipt is `independent_audit.json`.

* Maximum full-objective gradient relative error: 6.23e-09.
* Maximum NumPy-recomputed null-slope relative error: 2.33e-14.
* Synthetic fast-grid versus frozen order-8 held-out joint difference:
  2.19e-05 nats.
* All 24 P1.2 selected states are within bounds and exactly equal to the
  baseline null state; the held-out recomputation check is therefore the
  exact zero contrast.

## Limitations

* The 90/180/365-day block intervals are paired calendar-block summaries;
  adjacent blocks are dependent under long memory, so they are descriptive
  multi-scale sensitivities rather than calibrated frequentist guarantees.
* The synthetic bank uses the archived S8 ETAS backbone, mark law and smooth
  background, not the California catalogue. It isolates kernel-shape
  estimation, not regional geology or catalogue-specific noise.
* The positive null slopes at the bound-pinned 2 km comparator occur in a
  narrow unscaled ann2 corner and carry training profile gains below 0.04
  nats. They are reported for completeness, not as evidence of a detectable
  stress shadow.
* The joint search is a declared finite multi-start search with the exact
  nested null retained; it does not claim global optimality.
* The attenuation coordinate `eta` is a statistical inhibition parameter, not
  a physical Coulomb stress measurement.

## Reproduction and custody

All writes are confined to
`experiments/pathway1_annular_attenuation/`,
`validation/live_results/pathway1_annular_20261116/` and this report. The native
source and binary hashes are pinned in
`build/pathway1_annular_20261116_joint/build_receipt.json`; all generated rows
carry the frozen source hash and baseline source hashes. No file under
`validation/authorities/` or a pre-existing `validation/live_results/`
subdirectory was modified.
