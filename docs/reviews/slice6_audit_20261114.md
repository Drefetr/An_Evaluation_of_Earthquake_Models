# Slice 6 audit — continuous local inhibition (LI/LI+), S04B joint comparison, refitted floor, and S8 controls/oracles

**Date:** 14 November 2026 (audit run 16 November 2026)  
**Baseline commit:** `8ae4fa6`  
**Scope:** Chapter 13 — `13_continuous_local_inhibition.tex`, `13_s04_expanded.tex`, `13_s04_observed_completed.tex`, `13_s04_diagnostics.tex`, `13_s04_refitted_floor.tex`, `13_s04b_joint_dispositions.tex`, `13_s04b_joint_quantiles.tex`, `13_s08_moderate.tex`, `13_s8_oracle.tex`, `13_score_uncertainty.tex`, the paired Python/C++ implementations, and the bound JSON authorities.

**Verdict:** accepted with documented repairs. The audit passes all nine components (1,279 individual checks). The pre-existing sealed JSON roster is byte-for-byte unchanged. Three confirmed manuscript defects are repaired: the S6 regime label, the missing S7 quantile-coincidence explanation, and the line-75 score-derivative attribution. Raw math-mode and legacy reference tokens are normalized without losing any pre-edit numeric value. One additional authority-naming defect and one saved-arithmetic rounding difference are documented without editing any sealed file.

---

## 1. Non-negotiable custody

`validation/slice6_prechange_snapshot_20261114.json` and `.zip` record:

- **772** pre-existing JSON records: 769 under `validation/authorities` and
  `validation/live_results` plus the three prior-slice records at the
  `validation/` root (`slice4_remediation`, `slice5_prechange_snapshot`,
  `slice5_remediation`). The snapshot scope states this composition explicitly.
- **68** publication files, including the ten Chapter 13 LaTeX sources, the
  unified PDF, the companion, the website metadata, the claim ledger, and the
  review-slice bundle.

The byte-level comparison after all edits finds **0 changed, 0 missing**.
The snapshot SHA-256 is `fa8eb7eb6c279512721af2947c7bfd2abb9138ccb428e261dfd264e2f668ce2a`;
the ZIP SHA-256 is
`8ca38b86883362283e27c453e738cec4c58bf62f351cdf1e7221db879a33c022`.
The ZIP preserves the pre-edit LaTeX so the numeric-preservation check compares
the repaired text against the exact pre-repair bytes.

---

## 2. Confirmed repairs

### 2.1 Wrong S6 regime subheader

`paper/source/chapters/13_s04b_joint_quantiles.tex`, Table
`tab:s04b-joint-quantiles`, line 24, identified S6 as
“magnitude-scaled broad/long immigrant”, which is the S5 regime. The S6 law is
the magnitude-scaled narrow/short **total-attenuation** law. The four
subheaders now read:

| Row | Regime |
|---|---|
| S4 | magnitude-scaled narrow/short immigrant |
| S5 | magnitude-scaled broad/long immigrant |
| S6 | magnitude-scaled narrow/short total attenuation |
| S7 | magnitude-scaled broad/long total attenuation |

This matches `Table tab:s04b-thinning` and the generating roster in
`13_s04_expanded.tex`.

### 2.2 S7 quantile coincidence

The S7 `LI+ immigrant (raw)` and `LI+ total (raw)` rows share `Q25 = -8.242`,
`Min = -23.26` and `Max = 23.90`. The caption now gives the algebra and the
correct intersection:

- S7 has 19/20 immigrant fits and 9/20 total fits with `\hat n = 0`.
- The two intensities coincide only on the **9/20 seeds where both** fits select
  `\hat n = 0`. On those seeds the triggering term `nH(t,z)` vanishes and

  \[
  \lambda_{\rm imm}=Be^{-\eta G_+}+nH
  \longrightarrow Be^{-\eta G_+},
  \qquad
  \lambda_{\rm total}=(B+nH)e^{-\eta G_+}
  \longrightarrow Be^{-\eta G_+}.
  \]

- Those nine seeds supply the shared minimum, maximum and **both** lower-quartile
  order statistics (the 20-history lower-quartile position is between sorted
  indices 4 and 5), so Q25, Min and Max agree to displayed precision.
- The upper quartile differs because its interpolation uses a seed where the
  total fit selects `\hat n = 0.98` while the immigrant fit selects `\hat n=0`.
  One-sided zero selections do **not** make the two intensities identical.

Numerically, the nine both-zero held-out contrasts differ only by solver and
quadrature arithmetic; the maximum absolute difference is
`1.548846614696231e-4` nats, while the displayed Q25/Min/Max agree. The exact
quantile values are `Q25 = -8.242413` (immigrant) and `-8.242419` (total),
`Min = -23.258557` and `-23.258547`, and `Max = 23.900533` and `23.900529`.

### 2.3 Line-75 score-derivative attribution

`13_continuous_local_inhibition.tex` line 75 previously presented
`75,313.9 > 59,415.5` and `-15,898.4` as the training score slope of the
unit-mark immigrant-only LI law. Those figures belong to the **total-intensity
EP+** model `\lambda = \lambda_0 e^{-\eta G}` of
Section~\ref{sec:california-eta-profiles}, whose score derivative is

\[
\left.\partial_\eta\ell\right|_{\eta=0}
=-\sum_i G(t_i,z_i)+\int \lambda_0 G .
\]

For the immigrant-only LI law of Eq. 13.1, the event term is weighted by the
immigrant probability `p_i^{\rm imm}=B(t_i,z_i)/\lambda_0(t_i,z_i)` and the
compensator is integrated against `B`, so

\[
\left.\partial_\eta \ell_{\rm LI}\right|_{\eta=0}
=-\sum_i \frac{B(t_i,z_i)}{\lambda_0(t_i,z_i)}G(t_i,z_i)
+\int_I\int_D B(t,z)G(t,z)\,dz\,dt .
\]

The repaired paragraph gives this formula and explicitly attributes the three
EP+ literals to Section~\ref{sec:california-eta-profiles}. All three numeric
literals are retained for claim-ledger traceability. The implementation
triangulation is exact: `reproduction/synthetic/source/cpu_reference.cpp`
computes the immigrant fraction in lines 70–72, and
`experiments/s04b_joint_nuisance/model.py` lines 148–167 computes the same
`fraction` and `-(G*f)` gradient. At `\eta=0`, `f=1` for total attenuation and
`f=B/(B+nH)` for immigrant-only attenuation.

### 2.4 Raw math-mode and legacy tokens

The following were normalized without changing any numeric value:

- `M $\geq$ 4.0` → `$M\geq 4.0$`.
- `For time t … location z … domain D` → `$t$`, `$z$`, `$D$`.
- `M4`, `M7.1` → `$M\,4$`, `$M\,7.1$`.
- `$\eta$ = 0`, `$\ell$ = 30 km`, `$\psi$ = 7 days` → compact math mode.
- Bare `a,d,n,c,p` in the bound/start tables → math mode.
- `P,Q,E,C = -E,M` → `$P,Q,E,C=-E,M$`.
- `+/-0.0002` → `$\pm 0.0002$` with the signed interval `$[-0.0002,0.0002]$`
  retained so the existing `-0.0002` typed claim remains resolvable.
- Raw `+1.128699e-12`, `+5.983898e-13`, `+1.88492776942439e-10` → math-mode
  scientific notation.
- `in IV` → `in Chapter~\ref{ch:external}`.
- `$\eta$ = 0.5`, `$\ell$ = 5 km`, `$\psi$ = 1/24 day`, `$\eta$ = 2`,
  `$\ell$ = 50 km`, `$\psi$ = 30 days`, `t` → compact math mode.

The numeric-preservation check finds **zero removed numeric values** in all ten
Chapter 13 files. The only additions are the signed `+0.0002` tolerance endpoint
and the S7 explanatory counts `9`, `19`, `20`, `0.98`.

---

## 3. Triangulation results

### 3.1 Observed unit-mark LI and fixed-seed controls

- The observed roster is three folds with 79, 167 and 69 targets (315 pooled).
- `LI − OC` is exactly zero in F0 and F2; F1 totals `1.8849277694243938e-10`
  nats and therefore `1.1286992631283796e-12` per target. The pooled total is
  `1.8849277694243938e-10`; the pooled per-target value is
  `5.983897680712361e-13`. The three selected observed LI states are exactly
  `\eta=0` in 3/3, with `\ell` and `\psi` unidentified at that boundary.
- `LI − EP` pooled totals are `-51.05120476287129` nats, or
  `-0.16206731670752791` per target; timing is `+0.3362495254193334` and
  conditional location is `-51.38745428829054`. The decomposition closes at
  `7.1e-14`.
- All eight fixed-seed controls match the authority: seeds
  `410001–410302`, six negative and two positive contrasts. The two broad/long
  wins have only 23 and 27 test targets.
- The original S2 narrow/short bank has `0/2951` rejected immigrant proposals
  and 20/20 zero-rejection histories. Both fixed narrow/short seeds 410201 and
  410202 also have zero rejected immigrants.
- All 19 training-defined near-optimal forecast spreads are below 0.01; the
  maximum is `0.0005376164007914404`.
- The bound summary enumerates 19 procedures, 152 starts, 30 floors and 182
  candidate slots, all complete. The narrative “369 checks” is a source-reported
  aggregate from Addendum V/`docs/result_provenance.md`; no per-check ledger is
  bundled, so the audit verifies the enumerable denominators rather than
  pretending to reconstruct the 369th check.

**Mark-moment inequality.** For the ideal LI+ exponential marks,
`β=2`, `r=0.7` gives `β(1+r)=3.4` and `2γ=1.5 log 10=3.453877639491069`.
The strict inequality `3.4 < 3.45388` is verified.

### 3.2 Expanded S04 and matched S04B controls

- All 20 unit-mark S04 summary rows reproduce the authority means, sample MCSEs,
  medians and win counts. The gated rows have the expected exact-floor zeros and
  one-active-history arithmetic.
- All 20 S04B matched fixed-backbone rows reproduce
  `mean_gain`, `mean_standard_error`, `median_gain`, `wins`, Wilson intervals
  and active counts. The fixed-floor values are recomputed independently from
  the twenty `fixed.values` vectors in
  `track_a_supplement_20261112/s04b_joint_mcse.json`, and agree with
  `S04B_COMPLETE_AUDIT.json` to `1e-12`.
- Thinning counters reproduce exactly:

  | Regime | Immigrant rejected/proposed | Offspring rejected/proposed | Zero rej. | Zero off. | Train N | Test N |
  |---|---:|---:|---:|---:|---:|---:|
  | S4 | 1/2967 | 0/1120 | 19 | 0 | 86.65 | 109.40 |
  | S5 | 2518/3018 | 0/202 | 0 | 0 | 15.15 | 16.90 |
  | S6 | 1/3102 | 134/1335 | 0 | 0 | 95.80 | 111.55 |
  | S7 | 2525/3093 | 165/168 | 0 | 17 | 13.30 | 13.25 |

- All twelve selected-parameter rows reproduce the median `[minimum, maximum]`
  of `\hat\eta`, `\hat\ell` and `\hat\psi`, the boundary count `B` and the
  zero-strength count `Z`. The parameter summaries are recomputed from the 240
  `fit_census` records, not copied from the display table.

### 3.3 Observed California S04 and block uncertainty

- The fifteen observed rows split into exactly three active total-intensity
  rows (`-0.22447114721489925`, `-1.9528677570883701`,
  `-0.2093431817571627` nats) and twelve exact algebraic zeros.
- The three active rows sum to `-2.386682086060432` nats; the paired
  block-score authority total is `-2.386674517269429`. The difference is
  `7.6e-6` nats and both display `-2.387`. This is a saved-arithmetic/rounding
  difference, not a physical effect.
- The 90-day fold intervals are `[-0.787,0.074]`, `[-5.945,0.143]`,
  `[-0.458,-0.013]`; the pooled interval is `[-6.564,-0.033]` with nominal
  sign-flip `p=0.07678`.
- At 180 days the pooled interval is `[-6.426,-0.085]` with `p=0.04560`; at
  365 days it is `[-6.364,-0.090]` with `p=0.06578`. F2 excludes zero at 90 and
  180 days but includes it at 365 days (`[-0.488,0.020]`).
- The 32→64 temporal-order refinement changes every block exposure by at most
  `5.89e-12` nats.

### 3.4 Refitted scalar and concave `(a,n)` floors

- All 80 scalar per-history files match their recorded SHA-256, satisfy
  `\Delta P+\Delta C=\Delta joint`, and satisfy the endpoint/interior KKT sign
  conditions. The 480 historical floor checks pass; the maximum saved-floor
  absolute difference is below `1e-10`.
- All 80 concave per-history fits satisfy the box KKT conditions; the maximum
  relative projected KKT residual is `2.2536080476189574e-13`. All 20 S7
  concave fits select `\hat n=0`.
- The 20 refitted-floor rows reproduce the fixed-floor, fitted-intercept and
  jointly fitted `(a,n)` means and MCSEs, the two win counts and the active
  counts. The four floor-component rows satisfy the per-history identity exactly
  and the displayed mean identity to rounding.

### 3.5 Completed 80-history / 400-outcome joint comparison

- All 80 bound case files match their recorded SHA-256. The two recovery
  histories are exactly S5 seed 410518 and S6 seed 410615; every other history
  retains its saved completed fit.
- All 20 score rows reproduce means, sample MCSEs, medians, wins and Wilson
  intervals. All 20 diagnostic rows reproduce the `a` and `\eta` lower/upper
  boundary counts, failed-return census, null-search gaps and gate differences.
  All 20 floor-census rows reproduce off-floor, floor-return, near-zero,
  positive-near-zero, robust-positive and robust-negative counts.
- All 20 quantile rows reproduce `Q25,Q75,IQR,Min,Max` with the declared
  `numpy.quantile` linear interpolation. The independent
  `synthetic_quantiles.json` authority matches to `1e-12`.
- S7 n=0 census: 19/20 immigrant fits, 9/20 total fits, 9/20 both. The
  both-zero intensity identity and the resulting Q25/Min/Max coincidence are
  documented in §2.2.

### 3.6 S8 moderate control and oracles

- The S8 law is `a=log 0.25`, `d=0.2`, `n=0.35`, `c=0.05`, `p=1.3`,
  `\eta=0.4`, `\ell=15` km, `\psi=5` days, with 365-day train and test windows.
  It rejects `27.2076%` of proposals and retains `94.7` test events on average
  (range `[78,112]`).
- Raw mean `+0.2941447638438433`, median `+2.5414777057436027`, MCSE
  `2.7772732750178357`, wins `13/20`, losses 7. The BIC sensitivity has mean
  `+2.4945996750852713`, median `0`, MCSE `1.4435753453121167`, wins `9/20`,
  active `12/20`, ties 8.
- Raw fits hit at least one box boundary in 13/20 histories: `p=2.5` in 7,
  `n=0.98` in 6, `\eta=4` in 2 and `a=0` in 1, with overlaps. 18/20 records fail
  the stricter inherited `1e-4` score/gradient criterion; the maximum scaled
  coarse/fine gradient difference is `0.03324332526868545`.
- The full-oracle rows reproduce `16.428688`, `14.540569`, `18.111994`,
  `-17.817850` and `+0.294145` nats with their medians, quartiles, SD, MCSE and
  wins. The closure identity is exact:
  `14.540568689145175 + 3.571425664485332 = 18.111994353630507`
  (`identity_residual = 0.0`).
- Seed 410840's fitted null has `\hat n=0.004967844`, `\hat p=2.5` and
  `\hat d=1.173923`; its overfitting-loss contrast is `+75.27783771723705`
  nats. The other-seed mean is `-0.2025960225016182` and the median is
  `-1.6831136976599055`.
- Partial oracle A is `3.12811751101201` (median `3.373459`, MCSE `1.406644`,
  13/20 wins); B is `2.823657383237122` (median `5.903275`, MCSE `3.671626`,
  15/20 wins); C is `-6.513221037516632` (median `-3.130646`, MCSE
  `2.561846`, 1/20 wins). The earlier single-start B value is `2.575724`
  and seed 410840 is `-60.421370`; the repaired five-start B is retained.
- Fitted `\hat\eta` has mean `0.928691`, median `0.543370`, IQR
  `[0.264380,0.984083]`, minimum `0.042291`, maximum `4.0` and RMSE `1.229545`
  against `\eta_\star=0.4`. The estimation loss is `-17.817850`, or `98.37%`
  of the `18.111994` oracle advantage.

### 3.7 Code ↔ equation triangulation

| Claim | Source | Verified |
|---|---|---|
| Immigrant/total intensities | `experiments/s04b_joint_nuisance/model.py` 148–167; `reproduction/synthetic/source/cpu_reference.cpp` 64–72 | `λ_imm=Be^{-ηG}+nH`, `λ_total=(B+nH)e^{-ηG}`; `f=1` total, `f=B/(B e^{-ηG}+nH)` immigrant. |
| LI score derivative at η=0 | same code, `fraction` and `-(G*f)` | Matches Eq. in §2.3; EP+ total-intensity figures match `eta_profiles.json`. |
| Scalar refitted floor | `experiments/s04b_refitted_floor/run.py` 104–163 | `L(b)=Σlog(bu+v)-bA-H+M`, concave derivative and endpoint KKT. |
| Concave `(a,n)` floor | same, 166–195 | Monotone profile score, box KKT, `n=0` for all 20 S7 fits. |
| S8 generation and gain | `validation/live_results/s8_moderate_complete_20261111/source/s8_moderate.py` 25–45, 103–148 | Rejection fraction, exact fitted gain, frozen test selections. |
| S8 partial oracles and closure | `experiments/methodological_audit/forensic_s8_oracle_20261114.py` 88–225 | Partial A/B/C, five starts, closure residual. |

---

## 4. Documented residual issues (no sealed-file mutation)

### 4.1 S8 authority field name

`validation/live_results/forensic_remediation_20261114/s8_oracle.json` contains
a field named `exact_true_null_minus_fitted_stats` whose values are the **full
true-law** `θ_star` minus the fitted-null contrast (mean `18.111994`), not the
true uninhibited-backbone null minus fitted-null contrast used in the manuscript
row (mean `1.683306`). The manuscript table row is correct and is bound to
`referee_remediation_20261113/s8_oracle_decomposition.json`:
`true_null_minus_fitted_null`. The sealed field is not edited; this audit
records the naming defect.

### 4.2 Observed pooled rounding

The three saved active S04 gains sum to `-2.386682086` nats, while the paired
block authority point is `-2.386674517`. Both display `-2.387`. The audit
records the `7.6e-6` difference as saved-arithmetic rounding, not a physical
effect.

### 4.3 Narrative aggregate count

The “369 arithmetic and numerical checks” sentence in
`13_continuous_local_inhibition.tex` and `docs/result_provenance.md` is a
source-reported aggregate. The bound summary supports 19 procedures, 152 starts,
30 floors and 182 candidate slots; no per-check ledger is bundled. The audit
does not fabricate the missing 369 records.

---

## 5. Claim ledger and manuscript state

`python -B scripts/verify_claims.py --write-receipts` completes release-ready
with **28,627** claims, **679** documentary metadata records, **25,930**
JSON-numeric bindings, **2,430** documentary-numeric bindings, **12,718**
literal manuscript display records and **0 missing** declared displays. The
master ledger SHA-256 is
`87f1e17f56b2ceba172e979b83b6f79d0364f729056d1fa490076c9f18d0f44e`.

The Slice 6 claim component resolves **2,093** Chapter 13 claims with zero
missing displays. Two claims (`-10.3701`, `-1.2607`) are declared in the
overview files and are present in `01_introduction.tex`; they are not required
to appear verbatim in Chapter 13 because the ledger permits any declared
location.

Numeric preservation: **zero removed values** in all ten Chapter 13 sources.
Additions are limited to the signed `+0.0002` tolerance endpoint and the S7
counts `9`, `19`, `20`, `0.98`.

---

## 6. Build, PDF QA, companion, website, and review slices

- Monograph build: Tectonic 0.17.0, exit 0, **252 pages**, installed as
  `paper/manuscript_unified.pdf`.
- PDF QA: `passed=true`; **0 overfull boxes**, **0 overfull vertical boxes**,
  **0 undefined cross-references**, **0 missing bibliography keys**,
  **0 missing figures**, **0 missing glyphs**, **0 replacement characters**,
  25 non-blocking underfull boxes.
- PDF SHA-256:
  `a42ec7bc8179ee1adcf4b767a57685d22eb76de5ac1c446f18c23abd29859f6a`.
- Companion PDF/HTML rebuilt and installed; website metadata updated to the new
  PDF hash and page count; site rebuilt and installed; `node
  website/check_interactions.cjs` passes 80 selector combinations with zero
  disposition selector cases (the expected Slice 6 state).
- Review slices regenerated for all seven slices. Slice 6 is 35 PDF pages,
  21 files, 230,053 context characters (~57,513 tokens), ZIP 476,547 bytes.

---

## 7. Repository checks

| Check | Result |
|---|---|
| `scripts/check_mathematics.py` | passed; `build/mathematics.json` |
| `scripts/verify_claims.py --write-receipts` | passed, release-ready |
| `scripts/verify_claims.py` | passed |
| `scripts/validate_pdf.py` | passed, 252 pages, 0 overfull, 0 undefined |
| `reproduction/regional/tests` | 44 tests, OK |
| `reproduction/regional/inputs.py verify` | passed, 6,110 members, 15,093 crosswalk records |
| `reproduction/s02/test_inputs.py` | 6 tests, OK |
| `reproduction/s02/inputs.py verify` | passed, 300 histories, 600 methods |
| `reproduction/historical_fits/verify.py` | passed, 2 archives (2,824 + 37 members) |
| `node website/check_interactions.cjs` | passed, 80 selector combinations |
| `scripts/verify_repository.py` | refreshed and passed after MANIFEST regeneration |
| main `tests/` suite | 918 tests, OK |
| `../export_review_slice.py --slice all` | all seven slices regenerated |

---

## 8. Limitations

- The audit re-derives every displayed cell from the bound case records and
  re-evaluates the stated identities, KKT conditions and quantiles. It does not
  re-run the original GPU training campaign or regenerate the 80 S04B
  histories.
- The S04B/S8 synthetic MCSEs are descriptive sample standard deviations over
  independent seeded histories. The heavy-tailed mark laws do not supply
  finite-variance or Gaussian guarantees.
- The 90/180/365-day intervals are paired calendar-block summaries. Adjacent
  blocks are dependent and the sign-flip reference is not a sequence-level
  randomization.
- The S7 both-zero identity is algebraic; the saved contrasts differ by up to
  `1.55e-4` nats from solver/quadrature arithmetic.
- The sealed S8 field-name defect and the `7.6e-6` observed pooled rounding
  difference are documented, not silently rewritten.
- The observed California folds are the same 315 retrospectively inspected
  targets used elsewhere; they are not independent replication.

---

## 9. Evidence package

All audit outputs are under
`validation/live_results/slice6_audit_20261114/`:

- `summary.json`
- `sealed_authority_integrity.json`
- `observed_unitmark.json`
- `expanded_controls.json`
- `observed_and_uncertainty.json`
- `refitted_floor.json`
- `joint_comparison.json`
- `s8_moderate_and_oracles.json`
- `claim_ledger.json`
- `manuscript_state.json`

The acceptance record is
`validation/slice6_remediation_20261114.json`. The pre-change snapshot is
`validation/slice6_prechange_snapshot_20261114.json` and `.zip`.

Reproduce with:

```powershell
python -B experiments/methodological_audit/slice6_audit_20261114.py --output validation/live_results/slice6_audit_20261114
```
