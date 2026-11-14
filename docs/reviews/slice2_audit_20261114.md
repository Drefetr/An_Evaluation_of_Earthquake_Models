# Slice 2 forensic audit and remediation — 14 November 2026

**Baseline:** `ce8581b`  
**Scope:** Chapters 6, 7 and 9 (Sections 9.1–9.13), Appendix B.7, the completed
S02 study, Stage A exposure orthogonalization, Stage B parent-class temporal
scales, and Extension O continuous Omori tuning.  
**Disposition:** **Accepted with the repairs recorded below.** No new
mathematical defect was found in the recomputed table cells, interval
calculations, projection maps, Perron normalizations, or S02 aggregates. The
audit did confirm one carry-over display defect from Slice 1 and three
editorial/clarity defects in Chapter 9; all four are repaired.

The independent evidence package is
`validation/live_results/slice2_audit_20261114/`. It contains 13 JSON artifacts
written by `experiments/methodological_audit/slice2_audit_20261114.py`. The
pre-change byte snapshot is
`validation/slice2_prechange_snapshot_20261114.{json,zip}`.

## 1. Non-negotiable custody result

All **724** pre-existing sealed JSON records under `validation/authorities/`
and `validation/live_results/`, plus the Slice 1 acceptance record that
completes the 724-record roster, are byte-for-byte unchanged. The audit
resolved every hash against the pre-change snapshot:

```text
snapshot records : 724
unchanged        : 724
changed          : 0
missing          : 0
```

The repaired publication files are outside that sealed set. The audit did not
fit a model, simulate a catalogue, rerun an optimizer, or regenerate a claim.

## 2. Confirmed repairs

### 2.1 Carry-over visible bound double-counted the background mass

**Locator:** `paper/source/chapters/04_identifiability.tex`, line 216, and
`docs/reviews/slice1_math_audit_20261114.md`.

The displayed full-process clipped bound was

\[
D_{\mathrm{KL}}(P_\eta\Vert P_0)\le \mathcal B\min\{1,\eta^2K_T\},
\qquad
K_T=\frac{B_{\max}^2C_Tm\mathcal B}{n(1-n)}.
\]

`K_T` already contains the integrated background mass
\(\mathcal B=\int_0^T B(t)\,\mathrm dt\). The first alternative of the minimum
is therefore already the bound \(\mathcal B\), not \(1\). The algebraically
correct display is

\[
D_{\mathrm{KL}}(P_\eta\Vert P_0)
\le \min\{\mathcal B,\eta^2K_T\}
= \mathcal B\min\{1,\eta^2K_T/\mathcal B\}.
\]

The proof is unchanged: pointwise,
\(B^2/(B+nH_e)\le B\min\{1,B_{\max}/(nH_e)\}\); the clipped integrand is at
most \(B\min\{1,\eta^2B_{\max}G_s^2/(nH_e)\}\); Jensen's inequality,
Lemma 4.1, and \(\E_\eta N(T)\le\mathcal B/(1-n)\) give
\(\min\{\mathcal B,\eta^2K_T\}\). The numerical threshold for the resulting
Pinsker **test-error** bound remains
\(\eta\ge\sqrt{2/K_T}=2.3362\times10^{-3}\); the entropy bound itself
saturates at \(\mathcal B\). Both the chapter and the Slice 1 response now
state that distinction.

### 2.2 Fold 0 versus the three-fold OG6 aggregate

**Locators:** `paper/source/chapters/09_temporal_mark_extensions.tex`,
line 1195, and `tab:OG-primary/OG6`, line 1238.

The Fold 0 raw-versus-orthogonal contrast is \(-0.361471\) nats. The OG6
three-fold aggregate is \(-0.361468\) nats. The exact source decomposition is

\[
-0.3614713466572539
+0.000003372599508
-0.000000000000114
= -0.36146797405785946.
\]

Thus Fold 1 contributes \(+0.000003373\) nats and Fold 2 is numerically zero.
The prose now identifies \(-0.361471\) as the Fold 0 value, \(-0.361468\) as the
OG6 aggregate, and states the \(3.4\times10^{-6}\)-nat reconciliation
explicitly. The originally suggested “\(+0.000001\) and \(+0.000002\)”
breakdown is not what the authority records; the audit uses the exact
\(+3.3726\times10^{-6}\) and \(-1.14\times10^{-13}\) values instead.

### 2.3 Decision-log and math-mode cleanup in Sections 9.7–9.11

The following raw tokens were replaced without changing any bound numeric
literal:

| Old form | Repaired form |
|---|---|
| `r=.7` | `$r=0.7$` |
| `Iteration27` | `Iteration~27` |
| `E0` | `$E_0$` |
| `Fold0` | `Fold~0` |
| `results/analysis` | `\path{results/analysis}` |
| `beta` | `$\beta$` |
| `h=0` | `$h=0$` |
| `tau=1` | `$\tau=1$~day` |
| `5.0$\leq$M<5.5` | `$5.0\le M<5.5$` |
| `M$\geq$5.5` | `$M\ge 5.5$` |
| `Tau` | `the scale $\tau$` |
| `Omori c` | `Omori $c$` |
| `B+(n/rho(h))(H0+H1)` | `$B+\{n/\rho(h)\}(H_0+H_1)$` |
| `d=2.114439` | `$d=2.114439$` |
| `d\_tilde=0` | `$\widetilde d=0$` |
| colon-separated Fold 0 log lines | complete sentences with the same values |

The OG6 row and all bound literals still satisfy the claim ledger. A direct
scan of the repaired section finds no remaining `r=.7`, `Iteration27`,
`Fold0`, or `d\_tilde=0` tokens.

### 2.4 Stale pre-launch sentence about the spatial extension

**Locator:** `paper/source/chapters/09_temporal_mark_extensions.tex`, line 1204.

The former sentence said that the spatial study “was designed and frozen
before these outcomes; its launch is governed by correctness and resource
admission.” That statement is stale because the spatial extension has since
been executed. It now points to the completed study in
Chapter~\ref{ch:nz-spatial} and explicitly says that the spatial results do not
follow from the Extension O score direction.

## 3. Independent recomputation

### 3.1 Chapter 6 — spectral discretization and mark moments

- The Mainardi log-rate identity
  \[
  K_\alpha(e^v)e^v=
  \frac{\sin(\pi\alpha)}{2\pi\{\cosh(\alpha v)+\cos(\pi\alpha)\}}
  \]
  was proved symbolically after rewriting \(\cosh\) in exponentials; the
  residual is exactly zero.
- The endpoint rule with \(s=0.4\), \(\varepsilon=10^{-8}\) gives
  \(J=97\Rightarrow195\) modes at \(\alpha=0.5\) and
  \(J=68\Rightarrow137\) modes at \(\alpha=0.7\).
- The independent weights agree with
  `engine/iteration_5/code/kernels.py` to machine precision
  (maximum absolute difference \(0.0\); normalized mass \(1.0\)).
- The continuous spectral log-density integrates to one
  (\(1.0000000000000002\) at \(\alpha=0.5\), \(1.0\) at \(\alpha=0.7\)).
- The productivity normalization is
  \(\int_0^\infty \beta(1-r)e^{-\beta(1-r)m}\,\mathrm dm=1\) for \(r<1\).
  The numerical check at \(r=0.7\), \(\beta=2.849401764894274\) returns
  \(1.0\).
- The add-one rank rule was checked on a 999-reference bank:
  below-all query \(=1.0\), above-all query \(=0.001\), all-ties \(=1.0\).

### 3.2 Chapter 7 — exact binomial and paired nuisance comparisons

All five detection rows and all five null rows reproduce the authority
intervals and the printed two-decimal endpoints:

| Procedure | Detections | Recomputed CP 95% | Null | Recomputed CP 95% |
|---|---:|---|---:|---|
| Known laws | 150/150 | 97.57–100% | 50/1000 | 3.73–6.54% |
| \(\eta\) estimated | 150/150 | 97.57–100% | 49/1000 | 3.65–6.43% |
| Level estimated | 123/150 | 74.90–87.79% | 46/1000 | 3.39–6.09% |
| Level and trend | 68/150 | 37.20–53.66% | 44/1000 | 3.21–5.86% |
| Historical fuller | 57/150 | 30.21–46.28% | 50/1000 | 3.73–6.54% |

The paired discordance MCSE was recomputed from the recovered execution
record, not from the prose:

\[
\widehat{\mathrm{MCSE}}
=\sqrt{\frac{b+c-N\bar D^2}{N(N-1)}}.
\]

For \((b,c,N)=(29,21,150)\), the result is \(4.7096138\) percentage points.
For \((61,6,150)\), it is \(4.5776098\) percentage points. The achieved
suppression values recompute to \(14.15866\%\) and \(19.35982\%\), displayed
as \(14.159\%\) and \(19.360\%\).

The difficult-ten audit maxima were recomputed from
`iteration_24/completion/results/paired_diagnostics.csv`:

- maximum phase NLL improvement \(=1.949956640601158\times10^{-8}\);
- maximum absolute CPU32 GLR change \(=3.8968174465026095\times10^{-8}\).

Both are below the declared \(0.001\) and \(0.1\) screens. The 150-history
median NLL gains were recomputed from
`iteration_22/results/statistic_decomposition.csv`:
\(28.6649818\) (null) and \(0.8622812\) (alternative), displayed as
\(28.665\) and \(0.862\). Background flexibility improved the null fit more
than the alternative fit in all 150 saved paths.

These are documentary/descriptive recomputations from saved execution
records. They do not rerun the historical optimizer or establish global
maxima.

### 3.3 Chapter 9 — class-history algebra and productivity

The audit verified, symbolically and numerically:

- \(\sum_iP_{ij}(h)=1\) for every source class and \(P(h)p=p\);
- \(m_0=(1-e^{-(1-r)\beta c})/p_0\),
  \(m_1=e^{r\beta c}\), and \(p_0m_0+p_1m_1=1\);
- for \(A_{ij}=P_{ij}R_jm_j\), \(\rho=\rho_{\mathrm{PF}}(A)\) and
  \(K=(n/\rho)A\) has spectral radius \(n\);
- \(\partial_r\kappa_r(q)=\kappa_r(q)(\beta q-1/(1-r))\);
- \(\E[\kappa_r(Q)^m]=(1-r)^m/(1-mr)\) for \(mr<1\), with divergence at
  \(mr\ge1\);
- the timing NLL gradient
  \(\partial_r\mathrm{NLL}=n\{K'(r)-\sum_i\partial_rH_r(t_i)/\Lambda(t_i)\}\);
- the class-history conditional probability identity
  \(\lambda_i/\Lambda=p_i+(n_gh/\Lambda)(S_i-p_iS)\).

A necessary qualification emerged from the Perron check. With \(h=0\), the
transition matrix has rank one with columns \(p\), so \(Kp=np\) and
\(\mathbf 1^\top Kp=n\) exactly for every fertility contrast \(\delta\).
With \(h\ne0\), the class-specific productivity means differ at \(r=0.7\),
so the identity generally fails even at \(\delta=0\); \(\delta\) then also
changes the Perron root. The manuscript statement—that fixing the Perron
radius does not fix the immigrant-weighted first-generation offspring
count—is correct. The checklist phrase “\(\delta\ne0\) or \(h\ne0\)” should
be read with this \(h=0\) exception.

### 3.4 Chapter 9 — saved tables

The audit parsed and recomputed every row of:

- `tab:pilot-frequency` (6 rows) and `tab:pilot-paired` (4 rows);
- `a2:history-results` (7 rows), `a2:productivity-results` (3 rows), and
  `a2:cross-run` (3 rows);
- `tab:AG-primary` (7 rows), `tab:BG-primary` (3 rows), and
  `tab:OG-primary` (6 rows);
- the Stage A, Stage B and Extension O appendix fold tables
  (63 + 9 + 54 rows), the Stage A sensitivity aggregate tables (14 rows),
  the Stage B scale table (9 rows), the Stage A geometry table (9 rows), and
  all 9 Extension O selected-kernel rows.

Every \(\Delta Q+\Delta C=\text{Timing}\) and
\(\text{Timing}+\Delta M=\text{Joint}\) identity holds to displayed
precision. The largest residual is the six-decimal rounding residual
\(1.0\times10^{-6}\) in the AG7 row; all fold-table residuals are at or below
that scale. All 63 saved raw-to-orthogonal and orthogonal-to-raw maps satisfy
\(\widetilde a=a-\eta\gamma_0\), \(\widetilde d=d-\eta\gamma_1\) (and the
inverse) with maximum absolute error \(0.0\).

The class-history tables reproduce the primary totals:
\(-5.313603\) nats for \(E1-E0\), and the three \(E0-I0\) contrasts
\(0.029716\), \(0.021302\), \(0.032046\) nats/event. The free-productivity
primary \(E0\) total is \(-5.374505\) nats. The 16/18 estimated \(r\) values
below 0.7 and the maximum saved forecast spread
\(9.03775\times10^{-5}\) nats/event also reproduce.

### 3.5 S02 completed study

The completed S02 tables reproduce:

- six selection rows with 100 resolved forests each (79, 85, 85, 75, 75, 69);
- the Wilson intervals recomputed directly from the score statistic
  \(z=1.959963984540054\);
- four paired GLR rows and three within-forest M2-minus-M1 contrasts;
- 100 paired forests, 300 catalogues, 600 completed method cases, and the
  acceptance record's 300/600 counts.

The S02/S03 derived-values authority pins both the S02 summary and paired
authorities by SHA-256. The recovered input archive verifies
300 histories, 600 methods, 9,606 retained attempts, 226,764 events, and 100
paired forests; no fitting or likelihood evaluation is performed by that
check.

### 3.6 Claim ledger and manuscript binding

The audit independently resolved **3,357** chapter/appendix claims in the
Slice 2 files against their bundled authorities:

```text
authority scalars verified : 2905
documentary tokens verified: 452
manuscript displays present: 2873
failures                   : 0
```

The refreshed full ledger (13,566 claims) also passes `verify_claims.py`;
the claim counts and `MASTER_CLAIM_LEDGER.json` hash are recorded in
`validation/numeric_reconciliation_receipt.json`.

## 4. Residual qualifications

1. The audit recomputed saved quantities; it did not rerun the historical
   optimizers, simulate new catalogues, or reconstruct every raw history.
   The S14 and S11 maxima/medians are recomputed from their saved execution
   tables.
2. Clopper–Pearson and Wilson intervals remain conditional on the realized
   reference banks, generators, procedures, and query histories. They do not
   add reference-bank uncertainty or repair adaptive procedure selection.
3. The displayed table identities are checked at six-decimal precision.
   Individual source values carry more digits; the small AG7 residual is a
   presentation-rounding artifact, not an authority inconsistency.
4. The spatial extension is a completed separate study. Its execution does
   not convert the Extension O score direction into a spatial validation.
5. No new null calibration, power calculation, or physical interpretation is
   introduced by this audit.

## 5. Build and acceptance evidence

- `scripts/check_mathematics.py --output build/mathematics.json`: passed.
- `scripts/build_paper.py --output build/slice2_paper --install`: Tectonic
  0.17.0, exit 0, 252 pages.
- `scripts/validate_pdf.py`: 0 overfull boxes, 0 overfull vertical boxes,
  0 undefined references or citations, 0 missing figures, 0 replacement
  characters, 0 edge text blocks; 24 underfull boxes; passed.
- `companion/build_guide.py --output build/slice2_companion --install`: passed.
- `website/build_site.py --output build/slice2_site --companion
  build/slice2_companion --install`: passed.
- `scripts/verify_claims.py --write-receipts` and the read-only rerun: passed.
- `unittest discover -s tests`: 918 tests, OK.
- `unittest discover -s reproduction/regional/tests`: 44 tests, OK.
- `unittest discover -s reproduction/s02 -p test_inputs.py`: 6 tests, OK.
- `reproduction/regional/inputs.py verify`, `reproduction/s02/inputs.py
  verify`, and `reproduction/historical_fits/verify.py`: all passed.
- `node website/check_interactions.cjs`: passed.
- `scripts/verify_repository.py --write-manifest` followed by the read-only
  check: 10,869 files, passed.
- `export_review_slice.py --slice all`: all seven bundles rebuilt.

The acceptance record is `validation/slice2_remediation_20261114.json`.
