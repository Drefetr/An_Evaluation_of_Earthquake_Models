# Pathway 3 — low-dimensional and penalised attenuation

Isolated experiment for
`refinement_pathway_handoffs/PATHWAY_3_LOW_DIMENSIONAL_WELLS_COPPERSMITH_ATTENUATION_HANDOFF.md`.

The study asks whether the `-17.82`-nat finite-sample estimation loss between
the free eight-parameter inhibited fit (`+0.294` nats) and the S8 oracle
ceiling (`+16.43` to `+18.11` nats) can be recovered by:

* a stepwise degree-of-freedom ladder from the generating truth to the free fit;
* a 1D scalar `eta` profile on a three-point physical scale grid
  (`E_1D_Profile`);
* a scale-invariant `L1` / exponential-prior penalty on `eta`
  (`E_L1_Shrinkage`);
* within-training chronological split shrinkage (`E_Split_CV`);
* parameter-free Wells–Coppersmith rupture scaling
  `ell_j = 10^(-2.44 + 0.59 M_j)` km (`E_WC_Rupture`).

## Files

| file | purpose |
|---|---|
| `pathway3_native.cpp` | isolated deficit recurrence with an explicit per-parent scale, and annular row contractions with an explicit magnitude exponent |
| `native.py` | MSVC/g++ build, hash receipt and `ctypes` wrapper |
| `s8.py` | S8/S04B evaluator with a selectable clock, fast optimisation plan and archived-plan scoring |
| `estimators.py` | stationary null, `E_1D_Profile`, `E_L1_Shrinkage`, `E_Split_CV`, free 7D fit |
| `run_s8.py` | Stage P3.1 ladder and estimator comparison on 20 S8 histories |
| `run_banks.py` | Stage P3.2 S04B S4/S5/S6/S7 bank controls |
| `run_california.py` | Stage P3.3 California `E_WC_Rupture` with `mono` and `ann2` kernels |
| `run_nz.py` | Stage P3.3 New Zealand temporal 1D analogue and explicit WC scope note |
| `audit_pathway3.py` | independent replay, closures, native kernel checks and custody |
| `build_summary.py` | top-level `summary.json` and winner declaration |
| `make_report.py` | `docs/reviews/pathway3_low_dim_report_20261116.md` |

## Reproduction

From the repository root:

```powershell
python -m experiments.pathway3_low_dim_attenuation.run_s8 --workers 6 --resume
python -m experiments.pathway3_low_dim_attenuation.run_banks --workers 6 --resume
python -m experiments.pathway3_low_dim_attenuation.run_california --workers 3
python -m experiments.pathway3_low_dim_attenuation.run_nz
python -m experiments.pathway3_low_dim_attenuation.build_summary
python -m experiments.pathway3_low_dim_attenuation.audit_pathway3
python -m experiments.pathway3_low_dim_attenuation.make_report
```

Outputs are written only to
`validation/live_results/pathway3_low_dim_20261116/`, the report path above and
`build/pathway3_low_dim_20261116/native/`; the hash receipt is retained there.
No sealed authority or pre-existing live-result file is written.

## Numerical conventions

* S8 training window `[30, 395)` days, test window `[395, 760)` days.
* Optimisation uses a frozen tensor-Gauss plan (`12 x 12` spatial, `8` time
  nodes per panel). Reported scores use a `20 x 20` spatial, `24`-node time
  plan at order 16. The archived adaptive plan is used by the audit to replay
  selected states and to verify the oracle reconstruction.
* The stationary clock is `d = 0`; the archived trend clock is retained only
  for the oracle reconstruction and the archived free-8D comparator.
* The S8 scale grid is `(5 km, 1 d)`, `(15 km, 5 d)`, `(50 km, 30 d)`. The
  grid selection adds a `log 3` multiplicity term to the training criterion.
* The L1 penalty is `lambda * eta * mean(G_train)` for the primary arm and
  `lambda * eta * sum(G_train)` for the declared per-event sensitivity.
  `lambda` is selected on the second training half `[212.5, 395)`.
* The split-CV estimator fits on `[30, 212.5)`, chooses
  `alpha in {0, 0.25, 0.5, 0.75, 1}`, and re-balances `a` on `[30, 395)`.
* The exact `eta = 0` state is always an eligible nested candidate.
* California uses the sealed interior EP+ null, background weights and Sobol
  proposal from Pathway 1 / the sealed benchmark. The WC primary arm fixes
  `psi = 5 d`; the `psi`-free arms are sensitivity checks.
* New Zealand uses the sealed temporal predictive history. The spatial WC
  scale is not defined there; the temporal 1D profile is the declared analogue.

## Scope

* The S04 unit-mark `Uniform null` / `Smooth null` histories are not part of
  the reproducible S04B corpus and were not regenerated. The S4 bank, whose
  generator receipt records zero realised thinning, is the explicit S4
  zero-thinning null control.
* The New Zealand model has no epicentral-distance kernel, so `E_WC_Rupture`
  is reported as not defined there rather than approximated by a spatial
  model with no sealed comparator.
* Optimisation is multi-start L-BFGS-B on a smooth analytic objective. The
  results certify the executed recipe, not a global optimum.
* The declared winner is the highest-S8-gain estimator among those that remove
  at least 70% of the archived S4 zero-thinning mean loss. The S8-only winner is
  reported separately; it is not admissible under the S4 tail criterion.
