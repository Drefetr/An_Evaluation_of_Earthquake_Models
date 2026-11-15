# Slice 5 audit — EP+ benchmark, 2×2×2 ablation, interior σ₀ relaxation, and California η-profiles

**Date:** 14 November 2026 (audit run 16 November 2026)
**Baseline commit:** `2088c56`
**Scope:** Section 11.5 — `11_epplus_benchmark.tex`, `11_epplus_ablation.tex`, `11_epplus_eta_profiles.tex`, `abstract.tex`, the frozen EP+ implementation, the Track B control scripts, the forensic remediation scripts, and the six bound JSON authorities.

**Verdict:** accepted with documented repairs. The audit passes every component. The sealed JSON roster (761 files) is byte-for-byte unchanged. One confirmed mathematical defect is repaired: the archived `(a,d,n)`-profiled California attenuation root was computed at a lower quadrature resolution than the fixed-backbone root, which violated the envelope inequality in Fold 0. The profile is now evaluated at the same `power=14` resolution with exact `brentq` roots in every fold.

---

## 1. Non-negotiable custody

`validation/slice5_prechange_snapshot_20261114.json` and `.zip` record:

- **761** pre-existing JSON files: 759 under `validation/authorities` and
  `validation/live_results` plus the two Slice 4 record files at the
  `validation/` root.
- **68** publication files, including the four Slice 5 LaTeX sources, the
  unified PDF, the companion, the website metadata, the claim ledger and the
  review-slice bundle.

The byte-level comparison after the audit finds **0 changed, 0 missing**.
The snapshot SHA-256 is recorded in `sealed_authority_integrity.json`; the ZIP
preserves the pre-edit LaTeX so the numeric-preservation check compares the
repaired text against the exact pre-repair bytes.

---

## 2. Confirmed defect: the envelope inequality in the profiled η-root

### 2.1 Statement

Write \(\ell_{\rm fixed}(\eta)=\ell(a_0,d_0,n_0,\eta)\) for the fixed
backbone and \(\ell_{\rm prof}(\eta)=\max_{a,d,n}\ell(a,d,n,\eta)\) for the
profile. Since the feasible set contains \((a_0,d_0,n_0)\),

\[
\ell_{\rm prof}(\eta)\ge \ell_{\rm fixed}(\eta)\quad\text{for every }\eta\ge0,
\qquad \ell_{\rm prof}(0)=\ell_{\rm fixed}(0).
\]

Both curves are strictly decreasing in \(\eta\) near the root. Therefore the
exact upper root must satisfy

\[
\eta^{\rm prof}_{\rm upper}\ \ge\ \eta^{\rm fixed}_{\rm upper}
\]

in every fold, kernel and cutoff.

### 2.2 What the archive did

`forensic_eta_profiles_20261114.py` computed the fixed-backbone root at
`power=14` (16,384 Sobol nodes) with exact Newton and `brentq` iterations, but
`profile_curve()` downgraded the profile to `power=12` (4,096 nodes), evaluated
only a seven-point grid, and interpolated with `PchipInterpolator`. In Fold 0,
scale pair \((15,5)\), the archived profile reported

\[
\eta^{\rm prof}_{97.5}=1.1398\times10^{-4}
<1.1414\times10^{-4}=\eta^{\rm fixed}_{97.5},
\]

which is impossible for an exact profile. The archived profiled values were
1.1398e-4, 1.11872e-4 and 9.28637e-5.

### 2.3 Why the resolution matters

At fixed \((c,p,\sigma_0,\alpha_s,q,\ell_0,\psi,\gamma)\), neither the event
triggering sums \(H_{\rm ev}\) nor the Sobol-node sums
\((H_{\rm nodes},G_{\rm nodes})\) depend on \((a,d,n)\). The audit precomputes
them once at `power=14` and reduces each profile objective and analytic gradient
to 1-D vector arithmetic. The profile is then solved to
`ftol=1e-13, gtol=1e-9`, polished by a Newton solve of the three gradient
equations, and rooted with `brentq` (`xtol=1e-16`, `rtol=1e-15`). The full model
objective is re-evaluated at every polished root; the worst mismatch between
the reduced and full objective is below \(10^{-6}\) nats.

### 2.4 Repaired exact roots (scaled kernel, \(\ell_0=15\) km, \(\psi=5\) d)

| Fold | Fixed 97.5% | Profiled 97.5% | Gap | Fixed 95% | Profiled 95% | Gap |
|---|---:|---:|---:|---:|---:|---:|
| F0 | 1.14142e-4 | **1.16375e-4** | +2.233e-6 | 8.16649e-5 | **8.28392e-5** | +1.174e-6 |
| F1 | 1.11754e-4 | **1.13730e-4** | +1.976e-6 | 7.98982e-5 | **8.09352e-5** | +1.037e-6 |
| F2 | 9.09637e-5 | **9.26409e-5** | +1.677e-6 | 6.49566e-5 | **6.58313e-5** | +8.746e-7 |

All six inequalities are strictly positive; the worst root residual is
\(5.8\times10^{-13}\) nats; the worst full-model mismatch is below \(10^{-6}\).
The repaired values are 2.1%, 1.7% and −0.24% from the archived coarse values.
The F2 profiled root moves slightly down but remains above the fixed root.

### 2.5 Repaired exact roots (unscaled kernel, \(\ell_j\equiv15\) km)

| Fold | Fixed 97.5% | Profiled 97.5% | Gap | Fixed 95% | Profiled 95% | Gap |
|---|---:|---:|---:|---:|---:|---:|
| F0 | 8.20771e-4 | **9.06859e-4** | +8.609e-5 | 6.44439e-4 | **7.06286e-4** | +6.185e-5 |
| F1 | 7.72049e-4 | **8.41843e-4** | +6.979e-5 | 5.99897e-4 | **6.48531e-4** | +4.863e-5 |
| F2 | 4.90916e-4 | **5.21362e-4** | +3.045e-5 | 3.67106e-4 | **3.85797e-4** | +1.869e-5 |

The unscaled-to-scaled ratio is 7.8, 7.4 and 5.6, so the caption's
"roughly five to eight times larger" replaces "about eight times". The
exact \(\eta=0.01\) training losses are −517.6/−514.4/−666.2 nats (scaled) and
−95.4/−94.3/−127.1 nats (unscaled), replacing the power=12 caption values.

### 2.6 Text and table changes

- `11_epplus_eta_profiles.tex` line 2 now reports the exact profiled roots and
  states the envelope inequality.
- `Table tab:california-eta-profiles-unscaled` now contains the exact scaled
  and unscaled profiled roots.
- The caption now carries the exact \(\eta=0.01\) losses and the corrected
  ratio.
- The fixed-backbone table `tab:california-eta-profiles` is unchanged; its 12
  rows, slopes and held-out contrasts all recompute at `power=14`/`power=16`.

---

## 3. EP+ formulation and the EP contrast

### 3.1 Boundary integral

`Region.mass` is verified against an independent 200-point polar
Gauss–Legendre quadrature split at the four corner rays over all parents in
each fold (957 + 1,036 + 1,203 = 3,196 parent evaluations). The worst absolute
mass difference is \(6.28\times10^{-12}\) (requirement \(<10^{-11}\)). The
analytic derivatives \(\partial_{\log\sigma}m_j\) and \(\partial_q m_j\) agree
with central finite differences to \(2.68\times10^{-10}\) absolute
(requirement \(<10^{-7}\)).

### 3.2 Analytic gradients

Both `RF.Model` (plane) and `A.RectModel` (rectangle) are checked at the
accepted uninhibited MLE and at an interior perturbation, with a fourth-order
five-point stencil:

| Model | Coordinates | Worst scaled error | Worst absolute error |
|---|---|---:|---:|
| plane, uninhibited | 8 | 3.19e-8 | 3.19e-8 |
| plane, inhibited | 12 | 4.10e-8 | 1.61e-4 (η coordinate, |g|≈1.67e4) |
| rectangle, uninhibited | 8 | 5.06e-8 | 5.06e-8 |
| rectangle, inhibited | 12 | 4.10e-8 | 1.61e-4 |

The criterion is `abs(residual) <= 1e-7 * max(1, |analytic|)`, which is the
meaningful scale for the η coordinate whose gradient is \(1.67\times10^4\).

### 3.3 EP+ minus EP

The read-only reimplementation of `compare_baseline.py` loads the archived EP
and primary California test caches, verifies identical event/parent histories,
fertility weights, temporal metadata and common mark scores, and recovers the
exact three-fold contrast:

\[
14.579482 + 30.691007 + 24.282404 = 69.552894\ \text{nats}.
\]

The manuscript's 14.58, 30.69, 24.28 and 69.55 are the correctly rounded
displays.

### 3.4 Paired calendar blocks

`replicate = 49,999` resamples of the 21/11/6 block scores in each fold
reproduce every stored interval and nominal sign-flip probability exactly:
\([32.239,123.719]\), \([32.153,120.312]\), \([26.589,122.164]\) with
\(p=0.00002,0.00010,0.00452\). The audit uses the same `resample`/`pooled`
functions as the frozen uncertainty authority and compares the 2.5/97.5
quantiles to \(10^{-9}\).

---

## 4. Self-declustered 2×2×2 ablation

### 4.1 Nine-arm table

All 36 table cells (9 arms × 3 folds + total) are reconstructed from
`epplus_ablation.json` and the archived ablation authority. The totals are:

| Arm | F0 | F1 | F2 | Total |
|---|---:|---:|---:|---:|
| A0 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| A1 | 5.0835 | 4.5498 | 0.6075 | 10.2408 |
| A2 | 5.1056 | 4.6368 | 0.5877 | 10.3302 |
| A3 | 11.1001 | 3.1047 | 20.6032 | 34.8080 |
| A4 | 11.0546 | 3.1770 | 20.5625 | 34.7941 |
| A5 | 5.6526 | 30.4042 | 2.7849 | 38.8417 |
| A6 | 5.6457 | 30.4627 | 2.7808 | 38.8892 |
| A7 | 14.6189 | 30.6297 | 24.2986 | 69.5472 |
| A8 | 14.5777 | 30.6913 | 24.2824 | 69.5514 |

### 4.2 Independent re-fit

The four declustered arms were re-fitted in all three folds with
`forensic_ablation_20261114.self_decluster` (five steps, neutral three-start
grid, own normalization and scaling). The recomputed totals and per-fold gains
are **bit-identical** to the archived rows: worst absolute gain difference
`0.0` over 12 arm-folds (384.6 s). This closes the cross-arm weight-leak
concern directly, not by inspection alone.

### 4.3 Code path

The AST/source audit confirms:

- `self_decluster` starts from `neutral_starts(scaled)` at iteration 0 and
  `[x]` thereafter, runs `range(steps)` with `steps=5`, chooses
  `A.RectModel` vs `RF.Model` from the arm's own normalization, and never
  reads `ACCEPTED`, `ABLATION` or an accepted weight vector.
- `arm_job` dispatches every arm to `self_decluster` with its own spec.
- `run_clean_ablation` contains no A8 fit special case, no accepted parameter
  vector and no accepted weight load.

The stored prior masses sum to the last declustering iteration's expected
immigrant count; the normalized A8 weights differ from the accepted A8 weights
by \(8\times10^{-8}\) to \(2\times10^{-7}\), which is the expected independent
convergence of the same fixed point, not an import.

### 4.4 Shapley closure

The exact three-player Shapley values over the balanced cube are

- normalization: **0.036771** nats,
- declustering: **27.604694** nats,
- scaling: **31.669094** nats,

with joint fitting \(A0\to A1=10.240826\). The closure is
\(10.240826+0.036771+27.604694+31.669094=69.551385\), residual \(0.0\).
The sequential path \(A0\to A1\to A2\to A4\to A8\) is
\(10.240826, 0.089351, 24.463931, 34.757277\), also closing on 69.551385.
The archived frozen-A8 decomposition is 29.222659, 30.025663 and 0.063747 on
69.552894; the leak inflated declustering by 1.617965 nats and depressed scaling
by 1.643431 nats, matching the manuscript's 1.62 and 1.64.

---

## 5. Interior σ₀ relaxation, profile, and inhibited refit

### 5.1 Six relaxed-bound rows

The two plane rows and two rectangle rows recompute to

| Panel | Redeclustered total | Frozen-weight total |
|---|---:|---:|
| plane | 77.055734 | 78.584453 |
| rectangle | 77.058742 | 78.518390 |

The sealed Track B `sigma0_relaxation.json` records
`total_gain=154.114476`, exactly the sum of the plane and rectangle panels.
The three plane scales are 0.823298, 0.839177 and 0.821351 km; the frozen
plane scales are 0.827692, 0.845160 and 0.826817 km. The manuscript's
0.823/0.839/0.821 and 0.828/0.845/0.827 are the correctly rounded displays.

### 5.2 Double-count clarification

The handoff asked for a clarification quoting a **154.053**-nat archived
six-row sum (77.056 plane + 76.997 rectangle). No file under
`validation/authorities` or `validation/live_results` contains either 154.053
or 76.997; the sealed Track B rows give 77.055734 and 77.058742. The repaired
sentence therefore states the sealed 154.114 total and explicitly withdraws
the unsupported 154.053/76.997 reading. The audit records
`archive_claim_154_053_present=false` and `archive_claim_76_997_present=false`.

### 5.3 Fixed-σ₀ profile

All 72 saved cells (3 folds × 12 grid points × 2 normalizations) are re-evaluated
at their stored parameter vectors; the worst NLL mismatch is `0.0` (exact).
The interior minimum is at **0.75 km** in all six fold/normalization panels,
not at the 0.05-km boundary or the old 2-km bound. The 36 plane cells in
`Table tab:sigma0-profile` all round correctly to the two displayed decimals.

### 5.4 Inhibited refit under σ₀ ≥ 0.05 km

All 12 fits (3 folds × {nested null, (0.05,10,2), (0.2,20,5), (0.5,50,30)})
converge, keep \(\sigma_0>0.05\) km, and return \(\hat\eta=0\) exactly. The
selected scales are 0.827773, 0.845170 and 0.826761 km (paper: 0.828, 0.845,
0.827). The η gradient at every zero solution is positive, so the boundary is
a local minimum of the bounded problem. The selected held-out gains recompute
from the power=16 test model to \(2.8\times10^{-1}\), 8.0088 and
\(7.4\times10^{-1}\) nats; these are not used in the manuscript's
positive-attenuation claims.

---

## 6. Claim ledger and manuscript state

### 6.1 Claim ledger

The master ledger resolves 13,566 claims and 679 documentary metadata records
with 0 failures in authority-only mode. The Slice 5 population is 418 claims
(140 abstract, 104 benchmark, 129 ablation, 50 profiles), 0 missing displays
and 56 withdrawn historical records. The compact custody roster tracks 42
compiled sources.

The three archived profiled-root claims
(`track-b-20261112-287/288/289`) originally bound 1.1398e-4, 1.1187e-4 and
9.2864e-5 to `eta_profiles.json`. They are rebound by
`scripts/rebind_slice5_claims_20261114.py` to the deterministic power=14
authority `validation/live_results/slice5_audit_20261114/eta_profile_roots_authority.json`.
`verify_claims.py --write-receipts` then refreshes the custody hashes and
presence records; the read-only verifier passes with 0 missing displays.

### 6.2 Numeric preservation

Comparing the pre-change ZIP with the repaired sources:

| Source | Numeric literals before | after | Intentional removals |
|---|---:|---:|---|
| abstract.tex | 129 | 129 | 0 |
| 11_epplus_benchmark.tex | 39 | 39 | 0 |
| 11_epplus_ablation.tex | 128 | 130 | 0 (two audit literals added) |
| 11_epplus_eta_profiles.tex | 92 | 93 | 18 archived profile values |

All 18 removals are in the documented replacement set (the six scaled profiled
roots, the six unscaled profiled roots, and the six power=12 η=0.01 caption
losses). No unrelated scalar was lost.

### 6.3 Abstract

The abstract's Slice 5 numbers are unchanged and re-verified: 69.55/69.551
closure, 31.67 scaling, 27.60 declustering, 0.04 normalization, 10.24 joint
fitting, the 29.22/30.03/0.06 frozen-A8 comparison on 69.553, the 1.62/1.64
attribution shifts, the 0.82–0.84 km interior scale, and the 77.06/78.58/78.52
relaxed totals. No abstract edit was required.

---

## 7. Build and independent verification

| Check | Result |
|---|---|
| `check_mathematics.py` | 0 |
| Paper build (Tectonic 0.17.0) | 252 pages, exit 0 |
| PDF QA | 0 overfull, 0 vertical overfull, 0 undefined refs/cites, 0 missing figures/glyphs, 0 replacement characters |
| Companion build | exit 0, installed |
| Website build | exit 0, installed; 80 selector combinations pass |
| Unit tests | see `validation/slice5_remediation_20261114.json` |
| Regional tests | 44 OK |
| Regional inputs | 6,110 members, 15,093 crosswalk records |
| S02 tests | 6 OK |
| S02 inputs | 300 histories, 600 methods |
| Historical fits | both archives pass |
| `verify_claims.py` | 0 failures, 12,718 display records |
| `verify_repository.py` | passes on the refreshed manifest |
| Review slices | 7 slices exported; Slice 5 now spans pp. 1–4 and 132–138 |

The PDF's Slice 5 pages were text-extracted and checked for the repaired
strings (`1.1638`, `9.0686`, `154.114`, `154.053`, `76.997`); the new unscaled
table is on p. 138, which is why the review-slice page range was extended from
132–137 to 132–138.

---

## 8. Residual limitations

- The audit re-fits the four declustered arms and re-evaluates every saved
  σ₀/profile and inhibited cell, but it does not re-run the original GPU
  training campaign for A1/A2/A5/A6 or the archived EP baseline. Those rows
  are verified against their sealed fold records and the executable
  definitions.
- The exact η-profile treats the frozen power=14 Sobol proposal as fixed. That
  is the same proposal used by the archived fixed-backbone curve; the
  profile therefore tests the likelihood, not proposal-resampling error.
- The \(`(a,d,n)`\) optimum at \(\eta=0.01\) and at \(\eta=0.4\) hits the
  \(n<0.98\) upper bound; the reported values are bounded-profile values.
- The exact η=0.4 profile changes the F0 held-out S8 contrast from the sealed
  archived −74.708 to −74.713 nats. The manuscript retains the sealed
  three-decimal value; the 0.006-nat sensitivity is recorded in
  `eta_profiles_exact.json` (`counts.s8_profiled_contrasts`).
- The 90/180/365-day intervals remain descriptive paired block summaries;
  adjacent blocks are dependent and the sign-flip reference is not a
  sequence-level randomization.
- The 154.053/76.997 figure in the review brief is not supported by any sealed
  authority. The manuscript now says so explicitly; the audit does not
  manufacture a row to match the brief.

---

## 9. Artifact index

All paths are relative to `public_review_repository`.

- `experiments/methodological_audit/slice5_audit_20261114.py` — audit and
  exact profile root-finder.
- `validation/live_results/slice5_audit_20261114/summary.json` — component
  verdicts and counts.
- `.../sealed_authority_integrity.json` — 761-file byte comparison.
- `.../epplus_formulation.json` — mass, derivatives, gradients, EP contrast,
  block intervals.
- `.../component_ablation.json` — 9-arm table, Shapley, sequential path, code
  path and weight checks.
- `.../ablation_recompute.json` — independent 12-arm-fold re-fit; all
  differences 0.0.
- `.../sigma0_relaxation.json` — six rows, 72 profile cells, 12 inhibited
  fits, double-count clarification.
- `.../eta_profiles_exact.json` — fixed and profiled roots, gaps, residuals,
  parameters, η=0.01 gains, S8 sensitivities.
- `.../eta_profile_roots_authority.json` — deterministic 12-vertex authority
  used by the claim ledger.
- `.../claim_ledger.json` — 418 Slice 5 claims, 0 missing.
- `.../manuscript_state.json` — numeric preservation and required tokens.
- `validation/slice5_prechange_snapshot_20261114.{json,zip}` — custody.
- `validation/slice5_remediation_20261114.json` — acceptance record.
- `scripts/snapshot_slice5_prechange_20261114.py` — snapshot builder.
- `scripts/rebind_slice5_claims_20261114.py` — three-claim rebinding.
- `scripts/build_slice5_acceptance_20261114.py` — acceptance writer.
