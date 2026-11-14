# Slice 1 Mathematical, Proof, and Code Audit — 14 November 2026

**Baseline commit:** `d4539af50de91f36a00aaf357a65b875d80927d1`
**Scope:** Chapters 2–5, Appendix A.5–A.7, `scripts/check_mathematics.py`,
`experiments/methodological_audit/stability.py`,
`experiments/methodological_audit/moments.py`, and the paired bound JSON
authorities.
**Audit script:** `experiments/methodological_audit/slice1_math_audit_20261114.py`
**Audited supplement:** `validation/live_results/slice1_math_audit_20261114/`
**Acceptance record:** `validation/slice1_math_remediation_20261114.json`
**Pre-change snapshot:** `validation/slice1_prechange_snapshot_20261114.json` and
`.zip`

## 1. Executive summary

The Slice 1 triad check found one confirmed blocking defect and no additional
fatal proof or code discrepancy in the audited slice. The defect is the
`C_T^{\mathrm{tight}}` display added in the 14 November F6 remediation
(`paper/source/chapters/04_identifiability.tex`, old lines 201–231; the
corresponding legacy calculation was in `scripts/check_mathematics.py`).

The display added a quantity with units of days to a quantity with units of
inverse days:

\[
\frac{B_{\min}}{B_{\max}^2}+n h_{195}(u)
\qquad\text{with}\qquad
[B_{\min}/B_{\max}^2]=\mathrm{day},\quad [n h_{195}]=\mathrm{day}^{-1}.
\]

It also restored \(B_{\max}^2\) a second time in the coefficient
\(K_T^{\mathrm{tight}}=B_{\max}^2C_T^{\mathrm{tight}}m\mathcal B/[n(1-n)]\),
and it used a single-parent denominator inside a multi-event
Cauchy–Schwarz sum. The old numbers (\(C_T^{\mathrm{tight}}=0.10424015\),
\(K_T^{\mathrm{tight}}=0.0133269\), threshold \(12.2504\)) are retained only
as `withdrawn_legacy` audit records. They are not manuscript claims.

The repair replaces the display with:

1. a dimensionally exact **full-process clipped bound**
   \[
   D_{\mathrm{KL}}(P_\eta\Vert P_0)\le \mathcal B\min\{1,\eta^2K_T\},
   \qquad
   K_T=\frac{B_{\max}^2C_Tm\mathcal B}{n(1-n)},
   \]
   which is rigorous for unbounded marks but still equals one for
   \(\eta\ge\sqrt{2/K_T}=2.3362\times10^{-3}\); and
2. a dimensionally exact **one-event single-parent bound**
   \[
   \int_0^T\psi_1(u;\eta)\,\dif u
   \le B_{\max}^2\int_0^T
   \E_Q\!\left[
   \frac{\min\{\eta^2g(Q)^2\Phi_s(u)^2,1\}}
   {B_{\min}+n\kappa(Q)h_e(u)}
   \right]\dif u,
   \]
   whose numerical values are \(0.0015266\), \(0.0042328\), \(0.1867405\)
   and \(0.7883534\) at \(\eta=0.10,0.178,1.65,4\), first reaching one at
   \(\eta=4.6419\). The linearised coefficient is \(K_1=0.2416084\)
   (\(\sqrt{K_1/2}=0.3475690\)).

The one-event bound is non-vacuous throughout the fitted range, but it is
**not** a full-process multi-event bound. The earlier claim that retaining
\(B_{\min}\) makes the full-law bound non-vacuous throughout the fitted range
is explicitly withdrawn. This distinction is now stated in the chapter, the
abstract, Appendix A.7, the forensic response document, and the website
release note.

## 2. Confirmed defect: dimensional and Cauchy–Schwarz error

### 2.1 Exact locators

| Item | Old locator | Finding |
|---|---|---|
| Manuscript display | `paper/source/chapters/04_identifiability.tex`, old lines 201–231 | \(B_{\min}/B_{\max}^2+n h_{195}(u)\) is dimensionally inhomogeneous. |
| Legacy code | `scripts/check_mathematics.py`, old `visibility_bound_check()` | Computed `offset=background_min/background_max**2` and used `phi*phi/(offset+n*h)`. |
| Legacy JSON | `validation/live_results/forensic_remediation_20261114/mathematics_visibility.json` | Records the withdrawn values; sealed and left byte-for-byte unchanged. |
| Forensic response | `docs/reviews/forensic_audit_response_20261114.md`, line 59 | Repeated the withdrawn numbers; corrected with a withdrawal note. |
| Abstract | `paper/source/abstract.tex`, line 12 | Repeated the non-vacuous full-law claim; replaced. |

### 2.2 Dimensional proof

With \(B(t)=A e^{d x_{\mathrm{trend}}(t)}\),
\(B_{\min}=e^{a-|d|}\) and \(B_{\max}=e^{a+|d|}\) both have units
\(\mathrm{day}^{-1}\). Hence

\[
[B_{\min}/B_{\max}^2]
=\frac{\mathrm{day}^{-1}}{(\mathrm{day}^{-1})^2}
=\mathrm{day},
\qquad
[n h_{195}(u)]=\mathrm{day}^{-1}.
\]

The sum is invalid regardless of the numerical values. At the frozen NZ
reference, \(B_{\min}/B_{\max}^2=32.0011\) days, while
\(n h_{195}(0)\) is of order \(0.5\)–\(1\) day\(^{-1}\).

### 2.3 Double restoration of \(B_{\max}^2\)

The correct quadratic coefficient already contains \(B_{\max}^2\):

\[
K_T=\frac{B_{\max}^2C_Tm\mathcal B}{n(1-n)}.
\]

The legacy code set \(K_T^{\mathrm{tight}}=K_T C_T^{\mathrm{tight}}/C_T\),
which multiplies by \(B_{\max}^2\) again through \(K_T\). The legacy
\(C_T^{\mathrm{tight}}\) also divided \(B_{\min}\) by \(B_{\max}^2\) instead
of dividing the whole denominator by \(B_{\max}^2\). The net effect is not a
valid tightened bound; it is a different, dimensionally inconsistent
functional.

### 2.4 Multi-event Cauchy–Schwarz obstruction

Lemma 4.1 controls the multi-event ratio
\(G_s(t)^2/H_e(t)\), not a single term. If one tries to insert
\(B_{\min}\) into the denominator, the weighted Cauchy–Schwarz weights must be
applied to the full sum:

\[
\sum_i\left(B_{\min}+n\kappa_ih_i\right)
=N(t)B_{\min}+nH_e(t)
\ne B_{\min}+nH_e(t).
\]

For unbounded exponential marks, \(2\gamma>\beta\) gives
\(\E[g(Q)^2]=\infty\), while
\(m=\E[g(Q)^2/\kappa(Q)]=0.21606515<\infty\). The ratio denominator is
therefore essential. A single-parent denominator cannot replace it without a
new multi-event argument.

### 2.5 Legacy numbers (withdrawn, retained for audit traceability)

| Quantity | Legacy value | Status |
|---|---:|---|
| \(C_T^{\mathrm{tight}}\) | \(0.10424015\ \mathrm{days}^2\) | withdrawn |
| \(K_T^{\mathrm{tight}}\) | \(0.0133269\) | withdrawn |
| \(\sqrt{K_T^{\mathrm{tight}}/2}\) | \(0.08162996\) | withdrawn |
| Legacy \(\eta\) threshold | \(12.2504\) | withdrawn |
| Legacy bound at \(\eta=0.10\) | \(0.0081630\) | withdrawn |
| Legacy bound at \(\eta=1.65\) | \(0.1346894\) | withdrawn |

These values are reproduced in `visibility_correction.json` under
`legacy_withdrawn` so that the defect is auditable, but they are not used in
the manuscript.

## 3. Corrected mathematics

### 3.1 Full-process clipped bound

The exact entropy identity gives

\[
D_{\mathrm{KL}}(P_\eta\Vert P_0)
=\E_\eta\int_0^T\lambda_0
\{(1-\delta_\eta)\log(1-\delta_\eta)+\delta_\eta\}\,\dif t
\le
\E_\eta\int_0^T
\frac{B^2}{B+nH_e}\min\{\eta^2G_s^2,1\}\,\dif t.
\]

Pointwise,

\[
\frac{B^2}{B+nH_e}
\le B\min\left\{1,\frac{B_{\max}}{nH_e}\right\},
\]

so the integrand is at most
\(B\min\{1,\eta^2B_{\max}G_s^2/(nH_e)\}\). Jensen's inequality for the
concave minimum, Lemma 4.1, and
\(\E_\eta N(T)\le\mathcal B/(1-n)\) give

\[
D_{\mathrm{KL}}(P_\eta\Vert P_0)
\le\mathcal B\min\{1,\eta^2K_T\}.
\]

This is rigorous for the declared unbounded exponential marks. It is a
full-process statement, but it remains vacuous for
\(\eta\ge\sqrt{2/K_T}=2.3362\times10^{-3}\).

### 3.2 One-event single-parent bound

On a history with exactly one event at \(s<T\) and mark \(Q\), for
\(u=t-s\),

\[
G_s=g(Q)\Phi_s(u),\qquad H_e=\kappa(Q)h_e(u).
\]

The entropy integrand is bounded by

\[
\psi_1(u;\eta)
=\E_Q\!\left[
\frac{B(s+u)^2}{B(s+u)+n\kappa(Q)h_e(u)}
\min\{\eta^2g(Q)^2\Phi_s(u)^2,1\}\right].
\]

Since \(B_{\min}\le B(s+u)\le B_{\max}\),

\[
\psi_1(u;\eta)
\le B_{\max}^2\,
\E_Q\!\left[
\frac{\min\{\eta^2g(Q)^2\Phi_s(u)^2,1\}}
{B_{\min}+n\kappa(Q)h_e(u)}
\right].
\]

Units: \(B_{\max}^2\) is \(\mathrm{day}^{-2}\), the denominator is
\(\mathrm{day}^{-1}\), the numerator is dimensionless, and
\(\dif u\) is \(\mathrm{day}\). The integral is dimensionless.

The exact two-dimensional quadrature over \((u,Q)\) uses the implemented
195-mode pair and the declared exponential mark law. The \(Q\)-integrand
decays like \(e^{-(\beta(1+r)-2\gamma)Q}=e^{-1.3901Q}\); the numerical
cutoff at \(Q=80\) has a tail below \(10^{-48}\). Independent log-substitution
and partition quadratures agree to better than \(10^{-7}\) relative.

| \(\eta\) | \(\int_0^T\psi_1\,\dif u\) |
|---:|---:|
| 0.10 | 0.0015266 |
| 0.178 | 0.0042328 |
| 1.65 | 0.1867405 |
| 4.0 | 0.7883534 |

The one-event bound first reaches one at \(\eta=4.6418927\). Dropping the
clipping gives the linearised coefficient

\[
K_1=0.2416084,\qquad \sqrt{K_1/2}=0.3475690,
\]

with linear threshold \(\eta=2.8771265\).

### 3.3 Horizon dependence

For the untruncated exponential mark law, the inner mark expectation grows
like \(h_e(u)^{-s}\) with

\[
s=\frac{2\gamma-\beta}{r\beta}=0.3029.
\]

With \(h_e(u)\sim C u^{-1-\alpha}\) and
\(\Phi_s(u)^2\sim C'u^{-2\alpha}\), the single-parent integrand behaves like

\[
u^{-2\alpha+s(1+\alpha)}=u^{-0.5454},
\]

which is not integrable as \(T\to\infty\). The one-event integral is finite on
the declared horizon only because the horizon and \(\Phi_s\) cut off the
long-lag mass. This is why the one-event bound cannot be promoted to a
uniform full-process bound.

### 3.4 What is not claimed

- The one-event bound is not a bound on the full multi-event KL.
- The full-process finite quadratic bound remains \(K_T\) and remains vacuous
  in the fitted range.
- No new detection theorem, power result, or physical stress-shadow claim
  follows.
- The retained values are sufficient upper-bound quantities, not necessary
  detection thresholds.

A bounded-mark direct route was also checked. Bounding
\(G_s^2\) by a sum of squared parent contributions and keeping
\(B^2/(B+nH_e)\le B\) requires a multi-event second-moment constant
(\(\E N(T)^2\) or an equivalent pair-correlation bound). For the declared
subcritical productivity law, \(r=0.7\) gives
\(2r\beta>\beta\) and \(\E[\kappa(Q)^2]=\infty\), so that route does not
supply a finite full-process constant without an additional truncation of
\(\kappa\). Truncating both marks makes the constant finite but far larger
than the one-event coefficient; it was not promoted to a manuscript claim.

## 4. Chapter-by-chapter audit

### 4.1 Chapter 2 — models and observation laws

Checked:

- physical loading SDE and finite-mode flow;
- jump map \(\Delta Z_j=-g(M)\), \(\Delta U_j=\vartheta_j\kappa(M)\);
- finite mixture \(\Phi(t)=\sum_jw_je^{-\vartheta_jt}\),
  \(h=-\Phi'\), \(\Phi(0)=1\), \(\int h=1\);
- diagnostic intensity \(\lambda_\eta=B e^{-\eta G_s}+nH_e\);
- unit-mean productivity \(\E\kappa(Q)=1\) for
  \(\kappa=(1-r)e^{r\beta Q}\) under \(Q\sim\mathrm{Exp}(\beta)\);
- OC/FC/MC/EP/EP+/LI/LI+ spatial kernels and their normalisation;
- epicentral peak at \(r=0\), \(t=t_j^+\);
- master score identity and its crosswalk.

No additional defect found. The symbolic audit confirms
\(\E\kappa=1\), \(\Phi(0)=1\), \(\int h=1\), and the full-plane OC radial
mass \(\pi\sigma^2\). The frozen background values
\(B_{\min}=0.0123484944\), \(B_{\max}=0.0196437548\) and
\(\mathcal B=383.3495808\) match the reference authority.

### 4.2 Chapter 3 — stability and exact memory

Checked:

- Theorem 3.1 construction, Lyapunov function \(V=1+Y+cW\), generator
  \(\mathcal AV=-\sum_jw_j\vartheta_jy_j-\delta H+(m_1+cn)\Psi(X)\),
  \(\kappa_V=\vartheta_{\min}\min\{1,\delta/c\}\), \(D=\kappa_V+K_0\);
- non-circular order \(R=4D/\kappa_V\), then \(\epsilon\), then
  \(t_0\ge\log4/\vartheta_{\min}\);
- Doeblin constant: the saved certificate gives
  \(\log(\Lambda_Rt_0)\approx117.87\), hence
  \(e^{-\Lambda_Rt_0}=\exp(-1.54\times10^{51})\), consistent with the
  manuscript's order \(\exp(-3.5\times10^{50})\);
- stationary first-moment identities \(\pi(U_j)=n\Lambda\),
  \(\pi(Z_j)=(\rho-m_1\Lambda)/\vartheta_j\);
- Proposition 3.5 characteristic-function obstruction, unit marks
  \(\alpha\le1/2\), Pareto marks \(\alpha q\le1\);
- \(\operatorname{ess\,sup}X_\infty=+\infty\);
- Proposition 3.6 resolvent tail and the \(L\ge\gamma\) Lipschitz
  obstruction;
- exact transform check and fractional no-event path.

No additional defect found. `stability.py --verify` passes. The 195-mode
minimum rate is \(e^{-38.8}\), \(t_0=9.8283667623941\times10^{16}\) days,
and 61 modes decay by less than \(1\%\) over 24,394 days with normalized
weight \(0.0004293429\).

### 4.3 Chapter 4 — identifiability and visibility

Checked:

- zero-feedback nonidentification and singular closure;
- Proposition 4.2 restricted active identification, including the
  \(q\to\infty\) argument and the finite-mixture scale ratio;
- survival bound \(S_q(s,u)\le\exp\{-a_u\kappa(q)\}\);
- Lemma 4.1 weighted Cauchy–Schwarz;
- Proposition 4.4 entropy identity, first bound, and quadratic bound;
- corrected visibility bounds (Section 3 above);
- regional nonclosure Jensen algebra.

The weighted Cauchy–Schwarz identity is verified symbolically for two
summands. The finite-mixture ratio \(-h_e'(0)/h_e(0)\) is verified
symbolically. The regional example satisfies
\(B(1+e^{-\eta g})-2Be^{-\eta g/2}=B(1-e^{-\eta g/2})^2\).

### 4.4 Chapter 5 — inference and score geometry

Checked:

- full marked likelihood and strict pre-event history;
- Proposition 5.1 score bracket
  \(\E_\eta U_\eta^2\le B_{\max}^2C_T\E_\eta N(T)m/n\);
- exponential-mark ratio moment
  \(m=e^{-2\gamma}\beta/[(1-r)(\beta(1+r)-2\gamma)]=0.21606515\);
- divergence thresholds \(2\gamma>\beta\), \(2r\beta>\beta\),
  \(\beta(1+r)<2\gamma\);
- Proposition 5.2 amplitude profile and
  \(F_{aa}=\sum_ip_i^2+R\);
- Proposition 5.3 fixed-rule response
  \(p'(\eta)=\mathrm{Cov}_\eta(I,S_\eta)\) and the
  \(2\sqrt{\mathcal B p(1-p)}/(e\eta)\) envelope;
- fixed-path Gram residual fractions \(10.82\%\) and \(3.26\%\);
- `moments.py --check` and `product_derivative_checks()`.

No additional defect found. The score bracket inequality and the
positive-\(\eta\) envelope were checked on 2,000 random admissible
configurations. The reference Gram residual fractions
\(0.10821283\) and \(0.03264504\) match the manuscript.

### 4.5 Appendix A.5–A.7

Checked:

- A.5 score-field custody: canonical \(P,Q,E,C=-E,M\) semantics and the
  historical `timing_compensator` sign convention;
- A.6 historical theoretical notation: \(T_i,M_i,\Phi_s,h_e,X,B,G_s,H_e,
  \eta,n,\ell,F,A,a_{\mathrm{rel}},\beta_{\mathrm{rel}},\gamma,\alpha,\beta\);
- A.7 contribution classifications, including the corrected visibility row.

All labels referenced in Chapters 2–5 and Appendix A resolve within the
compiled manuscript tree. The score-field authority
`validation/authorities/score_field_semantics_v2.json` is present and hashed.

## 5. Code and JSON triangulation

### 5.1 `scripts/check_mathematics.py`

The visibility function was rewritten to:

- reproduce the legacy value only under `withdrawn_legacy`;
- perform a symbolic dimensional check (`offset` unit `day`,
  `n h` unit `day^{-1}`);
- compute the corrected full-process clipped threshold;
- compute `K_1`, its partition check, the four one-event values, and the
  clipping threshold;
- verify that the untruncated single-parent tail exponent is \(>-1\);
- retain all previous exact-transform, fractional-path, product-derivative,
  paired-MCSE, and stability checks.

New JSON keys include:

- `withdrawn_legacy`
- `one_event_single_parent.K_1_linear`
- `one_event_single_parent.sqrt_K_1_over_2`
- `one_event_single_parent.eta_linear_threshold`
- `one_event_single_parent.eta_clipped_threshold`
- `one_event_single_parent.clipped_bounds`
- `one_event_single_parent.tail_exponent_for_T_to_infinity`

### 5.2 `stability.py` and `moments.py`

- `python -B experiments/methodological_audit/stability.py --verify
  validation/live_results/methodological_20261106/stability.json` passes.
- `python -B experiments/methodological_audit/moments.py --check` passes.
- The saved 195-mode kernel, minimum rate, \(t_0\), slow-mode count,
  Doeblin certificate, and all exponential-mark moment rows agree with the
  independent recomputation.

### 5.3 Sealed authority integrity

The handoff described 356 pre-existing sealed JSON files. The pre-change
snapshot found **710** JSON files under the two sealed trees
(`validation/authorities/` and `validation/live_results/`). All 710 were
hashed before editing; all 710 remain byte-for-byte unchanged after the
remediation. The audit record is
`validation/live_results/slice1_math_audit_20261114/sealed_authority_integrity.json`.

No sealed authority was rewritten. The legacy
`mathematics_visibility.json` still contains the withdrawn values as a
historical record; the new audit supplement is additive.

## 6. Remediation ledger

### 6.1 Manuscript and documentation changes

| File | Change |
|---|---|
| `paper/source/chapters/04_identifiability.tex` | Replaced the dimensional display with the full-process clipped bound and the one-event single-parent bound; added the dimensional audit and scope withdrawal. |
| `paper/source/abstract.tex` | Replaced the non-vacuous full-law claim with the corrected one-event values and the full-process vacuity statement. |
| `paper/source/appendices.tex` | A.7 visibility row now states the one-event/full-process distinction. |
| `docs/reviews/forensic_audit_response_20261114.md` | F6 Pinsker paragraph now records the withdrawal and corrected values. |
| `website/document_metadata.json` | Release note and current-edition scope updated; PDF hash refreshed. |
| `scripts/check_mathematics.py` | Corrected visibility calculation and legacy audit record. |
| `validation/mathematics.json` | Regenerated from the corrected script. |
| `validation/MASTER_CLAIM_LEDGER.json` | Eleven corrected visibility displays added as explicit bindings. |

### 6.2 Claim-ledger changes

Eleven claims were added under IDs `slice1-visibility-*`, sourced from
`validation/live_results/slice1_math_audit_20261114/visibility_correction.json`:

- `0.0015266`, `0.0042328`, `0.1867405`, `0.7883534`, `4.6419`,
  `0.2416084`, `0.3475690` in Chapter 4;
- `1.53e-3`, `0.1867`, `0.7884`, `4.64` in the abstract.

`python -B scripts/verify_claims.py --write-receipts` passed, followed by a
read-only verification with 28,627 claims, 12,718 literal manuscript displays,
and zero failures.

### 6.3 Files deliberately not changed

- All 710 sealed JSON files under `validation/authorities/` and
  `validation/live_results/`.
- The historical forensic JSONs that record the old values; they remain
  byte-identical.
- The scientific experiment outputs, catalogue records, and fit states.

## 7. Build and acceptance evidence

Executed from `public_review_repository`:

```powershell
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B experiments/methodological_audit/slice1_math_audit_20261114.py --output validation/live_results/slice1_math_audit_20261114
python -B scripts/build_paper.py --output build/slice1_paper_v3 --install
python -B scripts/validate_pdf.py --source-root paper --pdf build/slice1_paper_v3/main.pdf --log build/slice1_paper_v3/main.log --output build/slice1_pdf_qa_v3
python -B companion/build_guide.py --output build/slice1_companion --install
python -B website/build_site.py --output build/slice1_site --companion build/slice1_companion --install
python -B scripts/verify_claims.py --write-receipts
python -B scripts/verify_claims.py
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s reproduction/regional/tests -v
python -B reproduction/regional/inputs.py verify
python -B -m unittest discover -s reproduction/s02 -p test_inputs.py -v
python -B reproduction/s02/inputs.py verify
python -B reproduction/historical_fits/verify.py
node website/check_interactions.cjs
python -B scripts/verify_repository.py
python -B ../export_review_slice.py --slice all
```

Results:

| Check | Result |
|---|---|
| Mathematical checks | pass |
| Slice 1 independent audit | pass; 710/710 sealed JSON unchanged |
| PDF build | 252 pages |
| PDF validation | 0 overfull boxes, 0 undefined references/citations, 0 missing glyphs |
| Companion build | pass |
| Website build | pass |
| Website interactions | 80 selector combinations pass |
| Main unit tests | 918 pass |
| Regional tests | 44 pass |
| S02 input tests | 6 pass |
| Regional inputs verify | pass |
| S02 inputs verify | pass |
| Historical fits verify | pass |
| Claim ledger | 28,627 claims, 0 failures |
| Repository manifest | refreshed and verified |

The installed PDF is `paper/manuscript_unified.pdf` with SHA-256
`4eae61331817385b168074140cb2b3145206c85e50d7fd42f5f4bc086fad1ca7`.

## 8. Residual limitations

1. The one-event bound is not a full-process bound. The unconditional KL
   expectation includes histories with several parents, and the denominator
   then contains \(nH_e=\sum_in\kappa_ih_i\), not one parent's
   \(n\kappa h_e\).
2. The full-process quadratic bound remains vacuous for
   \(\eta\ge2.3362\times10^{-3}\). No rigorous finite-horizon full-process
   tightening in the fitted range was found.
3. The single-parent integral diverges as \(T\to\infty\) for the untruncated
   exponential mark law; it is a finite-horizon statement.
4. The numerical quadrature is deterministic but uses the implemented
   195-mode spectral approximation; it is not an exact Mittag–Leffler
   evaluation.
5. The audit did not rerun catalogue fitting, simulation, or held-out
   evaluation. It checks the stated mathematical and code/JSON claims, not
   new empirical performance.
6. The handoff's sealed-file count (356) differs from the actual repository
   count (710). The larger actual set was preserved.

## 9. Verdict

The confirmed F6 visibility defect is fixed. The invalid formula and its
derived coefficient are withdrawn from the manuscript and the release
narrative. The replacement statements are dimensionally homogeneous,
mathematically proved, numerically checked, and explicitly scoped as
one-event or full-process. The sealed authorities are unchanged. The paper,
companion, website, claim ledger, and repository manifest rebuild and verify.

**Status: pass with the scope limitation stated above.** The one-event bound
is non-vacuous in the fitted range; the full-process bound is not.
