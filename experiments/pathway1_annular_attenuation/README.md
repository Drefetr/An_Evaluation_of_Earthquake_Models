# Pathway 1 — annular / rupture-exterior attenuation kernels

This directory contains the isolated experiment for the Pathway 1 handoff
(`refinement_pathway_handoffs/PATHWAY_1_ANNULAR_STRESS_SHADOW_HANDOFF.md`).
It replaces the epicentral-peaked kernel

\[
K_{\rm mono}(r;\ell_j) = (1+r^2/\ell_j^2)^{-2}
\]

with kernels that vanish at `r = 0` and peak at `r ~ ell_j`:

| id | kernel | peak |
|---|---|---|
| `mono` | `(1+v)^-2` | `r = 0` |
| `ann1` | `6.75 v (1+v)^-3` | `v = 1/2` (`r = ell/sqrt(2)`) |
| `ann2` | `16 v^2 (1+v)^-4` | `v = 1` (`r = ell`) |
| `shield` | `[r^2/(sigma_j^2+r^2)] (1+v)^-2` | between the core and `ell` |

where `v = r^2/ell_j^2`, `ell_j = ell_0 10^{0.5 m_j}` (rupture-scaled) or
`ell_j = ell_0` (unscaled), and `sigma_j = sigma_0 exp(alpha_s m_j)`.

## Baselines

* **interior** — the relaxed `EP+` fit with `sigma_0 >= 0.05 km`
  (`validation/live_results/track_b_controls_20261112/epplus_ablation/sigma0_relaxation.json`,
  plane normalization). `sigma_0 = 0.8233, 0.8392, 0.8214 km` for folds 0/1/2.
* **bound_2km** — the bound-pinned `EP+` fit
  (`validation/live_results/etas_inhibition_benchmark_interior_20261112`).

Both use the same California caches, training/test events, background
estimator, mark measure and nested `eta = 0` candidate.

## Files

| file | purpose |
|---|---|
| `annular_native.cpp` | compiled row contractions for `H`, `G` and analytic derivatives; joint synthetic deficit integral |
| `native.py` | MSVC/g++ build, hash receipt and `ctypes` wrapper |
| `annular.py` | `AnnularModel`, baseline loading, profiles, block intervals |
| `run_diagnostics.py` | Stage P1.1 null slopes and `power=14` eta profiles |
| `run_joint.py` | Stage P1.2 12-parameter joint optimization and held-out scores |
| `synthetic.py` | S8-generator adapter, `SyntheticAnnular` evaluator |
| `run_synthetic.py` | Stage P1.3 20-history ann2 control bank |
| `audit_pathway1.py` | independent verification and `independent_audit.json` |

## Reproduction

From the repository root:

```powershell
python -m experiments.pathway1_annular_attenuation.run_diagnostics --workers 6 --threads 1
python -m experiments.pathway1_annular_attenuation.run_diagnostics --workers 6 --threads 1 --skip-integration
python -m experiments.pathway1_annular_attenuation.run_joint --workers 4 --threads 2
python -m experiments.pathway1_annular_attenuation.run_synthetic --stage all --workers 4
python -m experiments.pathway1_annular_attenuation.audit_pathway1
python -m experiments.pathway1_annular_attenuation.build_summary
python -m experiments.pathway1_annular_attenuation.make_report
```

Outputs are written only to
`validation/live_results/pathway1_annular_20261116/`. Build artefacts go to
`build/pathway1_annular_20261116_joint/`. No sealed authority or pre-existing
live-result file is written.

## Numerical conventions

* Training proposal: `power = 14`, seed `20261111`; held-out check:
  `power = 16`, seed `20261120` (plus independent scrambles
  `20261250..20261253` in P1.2).
* All gradients are analytic. The compiled rows are verified against
  independent NumPy formulas and central finite differences in
  `audit_pathway1.py`.
* `eta` profiles are concave; if the null slope is non-positive the exact
  boundary `eta_hat = 0` is retained. The exact `eta = 0` state is always an
  eligible nested candidate in P1.2.
