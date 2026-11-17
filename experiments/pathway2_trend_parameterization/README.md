# Pathway 2 — stationary, origin-clamped and training-orthogonalised backgrounds

This directory contains the isolated experiment for
`refinement_pathway_handoffs/PATHWAY_2_STATIONARY_AND_CLAMPED_TREND_HANDOFF.md`.

The archived background is the un-centred affine clock

\[
B(t)=\exp\{a+d\,x_{\rm trend}(t)\},\qquad x_{\rm trend}(t)=\frac{2t}{T_0}-1,
\]

normalised by the whole catalogue horizon. Three forecast-admissible laws are
implemented and applied symmetrically to the uninhibited and inhibited arms:

| id | background | free `d`? | future clock |
|---|---|---|---|
| `T0` | `exp(a + d (2t/T0 - 1))` | yes | positive, unbounded extrapolation |
| `T1` | `exp(a)` | no | zero |
| `T2` | `exp(a + d x_clamp(t))`, `x_clamp=min{0,(t-T_origin)/(T_origin-T_start)}` | yes | zero |
| `T3` | `T2` plus `R = G - (c + k x_clamp)` fitted on training event rows (node projection recorded as sensitivity) | yes | zero |
| `DSTAR` | conditional true-trend control, `d=0.2` | frozen | archived T0 clock |

## Files

| file | purpose |
|---|---|
| `background.py` | clock definitions, analytic background integrals and `d` derivatives, training orthogonalisation |
| `background_native.cpp` | isolated deficit recurrence with a per-node clock and optional orthogonalised depletion |
| `native.py` | MSVC/g++ build, hash receipt and `ctypes` wrapper |
| `synthetic.py` | S8/S04B phase wrapper, fast tensor-Gauss plan, reduced-parameter fits, conditional true-trend control |
| `run_s8.py` | Stage P2.1: 20-history S8 moderate control (T1/T2/T3/DSTAR) |
| `run_s04b.py` | Stage P2.2: 80-history S04B tail-outlier evaluation (T1/T2) |
| `run_nz.py` | Stage P2.3a: three New Zealand folds (T1/T2/T3) |
| `run_ca.py` | Stage P2.3b: interior California EP+ baseline (T1/T2/T3) |
| `audit_pathway2.py` | independent integral, native, gradient, replay, identity, cross-check and sealed-hash audit |
| `build_summary.py` | merge the four stages into `summary.json` |
| `make_report.py` | render `docs/reviews/pathway2_trend_report_20261116.md` |

## Reproduction

From the repository root:

```powershell
python -m experiments.pathway2_trend_parameterization.run_s8 --workers 6
python -m experiments.pathway2_trend_parameterization.run_s04b --workers 6
python -m experiments.pathway2_trend_parameterization.run_nz
python -m experiments.pathway2_trend_parameterization.run_ca --workers 2
python -m experiments.pathway2_trend_parameterization.audit_pathway2
python -m experiments.pathway2_trend_parameterization.build_summary
python -m experiments.pathway2_trend_parameterization.make_report
```

Outputs are written only to
`validation/live_results/pathway2_trend_controls_20261116/`. Native build
artefacts and run logs are written to `build/pathway2_trend_controls_20261116/`
so the published result tree stays free of ignored compiler output; the hash
receipt is retained at `build/pathway2_trend_controls_20261116/native/build_receipt.json`.
No sealed authority or pre-existing live-result file is written.

## Numerical conventions

* S8 fitting uses eight starts and the archived bounds; S04B uses four starts
  (the archived T0 state plus three protocol templates) to keep the 320-fit
  screening campaign tractable. The fitted recipe is recorded per case.
* Optimisation uses a frozen tensor-Gauss plan (12 or 10 spatial nodes per
  axis per cell, 8 or 6 log-panel time nodes per interval). Reported scores
  use the archived adaptive S8 plan or a high-order fast plan (20/24) in S04B.
  The maximum scored quadrature difference is recorded in the audit.
* The T0 replay reproduces every sealed S8 null and inhibited held-out score
  to floating-point tolerance.
* The New Zealand fits use the archived `PredictiveHistory` quadrature and hold
  the per-fold trigger/stress kernels and productivity ratio fixed, exactly as
  the sealed trend controls.
* The California EP+ evaluation imports the frozen Pathway 1 annular model,
  interior background weights and Sobol proposal; only the background clock
  and depletion residual are replaced.
