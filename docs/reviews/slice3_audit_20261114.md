# Slice 3 forensic audit and remediation — 14 November 2026

**Baseline:** `10d253f`
**Scope:** Chapters 8 and 10, Appendix B.8, the reconstructed New Zealand
baseline, paired calendar-block uncertainty, trend–depletion collinearity
controls, the complete eighteen-cell \((\alpha,\tau,r)\) search, the autonomous
constant-background subfamily, and the \(C1\), \(W\), \(D\) and \(S\) spatial
stages together with the twelve-model temporal–spatial–background factorial.
**Disposition:** **Accepted with the repairs recorded below.** The recomputed
table cells, block standard errors, minimum detectable effects, eight
eighteen-cell winners, lift identity, stage decompositions and factorial
contrasts all agree with their bound authorities. The audit confirmed one
numerical-description defect in the trend-control prose, one fold-indexing
inconsistency, an origin-versus-intercept wording defect in Chapter 8, a
systematic raw-math formatting defect in Chapter 10, and one PDF page-builder
overfull box introduced by the repaired text; all five are repaired.

The independent evidence package is
`validation/live_results/slice3_audit_20261114/`. It contains twelve JSON
artifacts written by
`experiments/methodological_audit/slice3_audit_20261114.py`. The pre-change
byte snapshot is `validation/slice3_prechange_snapshot_20261114.{json,zip}`.

## 1. Non-negotiable custody result

All **737** pre-existing sealed JSON identities are byte-for-byte unchanged:
the 736 JSON files under `validation/authorities/` and
`validation/live_results/`, plus the Slice 2 acceptance record
`validation/slice2_remediation_20261114.json` that completes the roster. The
audit resolved every hash against the pre-change snapshot:

```text
snapshot records : 737
unchanged        : 737
changed          : 0
missing          : 0
```

The repaired publication files are outside that sealed set. The audit did not
fit a model, simulate a catalogue, rerun an optimizer, or regenerate a sealed
claim. The snapshot hash is `cb6ada67…` and the zip hash is `d5d56093…`.

## 2. Confirmed repairs

### 2.1 The eighteen-cell search reported the first-fold result as the three-fold total

**Locator:** `paper/source/chapters/08_nz_trend_controls.tex`, line 6, and
Table `tab:nz-trend-controls`.

The stored `full_grid` block in
`validation/live_results/forensic_remediation_20261114/nz_trend_controls.json`
contains eighteen \((\alpha,\tau,r)\) cells for each of three folds and each of
two arms. The winners are:

| Fold | Origin | Zero-\(d\) winner | Fixed-null-\(d\) winner | Zero-\(d\) held-out | Fixed-null held-out |
|---|---:|---|---|---:|---:|
| `fold_50` | 50% | `a0.5_t1_r0.4` | `a0.5_t1_r0.4` | −8.504027 | −4.555649 |
| `fold_65` | 65% | `a0.5_t1_r0.7` | `a0.5_t1_r0.7` | +0.000002 | +0.675456 |
| `fold_80` | 80% | `a0.5_t1_r0.7` | `a0.5_t1_r0.7` | −2.927149 | −1.125590 |

The three-fold sums are therefore

\[
-8.504027+0.000002-2.927149=-11.431174,
\qquad
-4.555649+0.675456-1.125590=-5.005784,
\]

which display as \(-11.431\) and \(-5.006\). The old sentence
“the full-grid held-out totals are \(-8.504\) and \(-4.556\)” mistook the
first-fold contrasts for the three-fold totals, and the old winner clause
“\((\alpha,\tau,r)=(0.5,1,0.4)\) for both arms” was true only in Fold 1.

The repaired sentence now states the per-fold winners and both sets of
quantities:

> selected the same per-fold winners as the single-start fixed-kernel
> controls: \((0.5,1,0.4)\) in Fold 1 (`F0`) and \((0.5,1,0.7)\) in Folds 2
> and 3 (`F1`, `F2`) for both arms. The corresponding first-fold held-out
> contrasts are \(-8.504\) and \(-4.556\) nats, and the three-fold full-grid
> totals are \(-11.431\) and \(-5.006\) nats.

The audit checks all 108 arm-by-cell-by-fold records, the two optimizer returns
and the exact \(\eta=0\) nested floor in every cell, and the argmin winner
identity. It also checks that the grid totals agree with the fixed-kernel
controls to better than \(10^{-4}\) nats; the largest difference is
\(4.0\times10^{-5}\) nats, so the “identical at displayed precision” statement
is correct for three- and four-decimal displays.

### 2.2 The same window was called Fold 1, Fold 0 and F0

**Locators:** `paper/source/chapters/08_nz_trend_controls.tex`, lines 2, 4, 8
and Table `tab:nz-trend-controls`.

The archived identifiers are zero-based (`F0`, `F1`, `F2` for `fold_50`,
`fold_65`, `fold_80`), while the prose used one-based labels. Line 2 called the
first window Fold 1, line 4 called the same window Fold 0, and the table used
F0. The repaired opening now defines all three windows explicitly:

> Fold 1 (`F0`, 50% origin), Fold 2 (`F1`, 65% origin) and Fold 3 (`F2`, 80%
> origin); the archived identifiers `F0`–`F2` are zero-based.

The table rows are labelled `1 (F0)`, `2 (F1)` and `3 (F2)`, and the caption
repeats the mapping. This removes the Fold 0/Fold 1 ambiguity without changing
any numeric literal.

### 2.3 The Chapter 10 decision-log formatting was not manuscript prose

**Locators:** `paper/source/chapters/10_nz_spatial_background.tex`, Sections
10.2–10.8, and `paper/source/appendix_tables/ch10_audit.tex`, line 555.

Thirty-six lines carried raw implementation tokens in text mode. The repairs
replace `eta`, `omega`, `sigma`, `pi`, `beta`, `r=.7`, `K=3`, `C 1`,
`q(c|z)`, `sum log q`, `(a,d,n,eta)`, `(1 + squared distance / sigma squared)
to power -2`, `order1e-5 or1e-6`, `1e-11`, `3.28e-11`, `1e-4`, `Iteration28`
and `ALL THREE` with the corresponding math-mode or prose forms. The exact
replacements include

\[
\eta,\quad \omega,\quad \sigma,\quad \pi,\quad \beta,\quad r=0.7,\quad
K=3,\quad C1,\quad q(c\mid z),\quad \sum\log q,
\]

\[
(a,d,n,\eta),\qquad
(1+\lVert z-z_j\rVert^2/\sigma^2)^{-2},\qquad
10^{-5},\quad 10^{-6},\quad 10^{-11},\quad 3.28\times10^{-11},\quad 10^{-4}.
\]

The audit checks the absence of every raw token by regular expression and the
presence of each replacement. It also proves that every pre-existing scalar
numeric literal survives the rewrite; the only apparent “removal”,
`150150` from the old comma pair `150,150`, is a tokenizer artefact and both
`150` literals are present in `$\sigma=150, 150, 50$~km`.

### 2.4 “Background intercept” was the background intensity at the origin

**Locator:** `paper/source/chapters/08_observed_baseline.tex`, lines 102–104.

The three ratios \(9.60\), \(1.57\) and \(1.34\) are

\[
\frac{B_{\mathrm{shared}}(t_{\mathrm{origin}})}
     {B_{\mathrm{ML}}(t_{\mathrm{origin}})}
=\exp\!\left\{a_s-a_m+(d_s-d_m)
\left(\frac{t_{\mathrm{origin}}}{t_{50\%}}-1\right)\right\},
\]

with exact values \(9.600634\), \(1.569157\) and \(1.336081\). Only the first
origin has \(x=0\), so only the first ratio is also an intercept ratio. The
sentence now says “unattenuated background intensity” rather than
“background intercept”; all three numbers and the “at the three predictive
origins” qualifier are preserved.

### 2.5 The repaired text introduced a PDF page-builder overfull box

**Locator:** `paper/source/chapters/10_nz_spatial_background.tex`, Figure 10.1
and the Section 10.10 location table.

The first rebuild after the prose repair produced

```text
Overfull \vbox (252.55814pt too high) has occurred while \output is active
```

on the page containing Figure 10.1 and the following table. The figure was
moved after the table (rather than before it); no content was deleted and no
number changed. The final build has 0 overfull horizontal boxes, 0 overfull
vertical boxes, 252 pages, and no undefined references or citations.

## 3. Chapter 8 baseline and score accounting

The audit recomputed the catalogue identity and the magnitude estimators from
`reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv`:

```text
CSV sha256       feacccb7…594fb3e
events           913
continuous beta  2.849401764894274
half-bin beta    2.494071218330174
per-fold beta    3.101621911, 3.149488208, 3.021907322
train events     301, 504, 659
test events      203, 155, 254  (612 total)
```

All fifteen rows of `paper/supplements/predictive_parameters.json` resolve to
the corresponding records in `e7fbc4fa4fae3da4_observed.json`; the nine
displayed predictive rows reproduce the table to its printed precision. The
second half of the table also reproduces exactly: \(\beta_{\rm train}=
3.101622,3.149488,3.021907\), \(r=0.4,0.7,0.7\), Omori
\(c=0.012995,0.020798,0.006972\) days and \(p=1.113368,1.198604,1.155845\).

The trend–depletion projection was recomputed from the raw times and excess
magnitudes with the archived modal recursion, not copied from the archived
JSON:

```text
intercept c_G          2.750747162169055
slope k_G              2.241739421456346
R^2                    0.149242749392832
weighted correlation   0.934064348001270
slow modes             61 of 195
slow-mode weight       0.0429343%
identity residual      3.55e-15
```

The saved held-out accounting is exact:

```text
Fold 1   dQ -33.715204660075   dC +17.197647207265   dL -16.517557452810
Fold 2   dQ  -1.785927107633   dC  +1.710649817082   dL  -0.075277290551
Fold 3   dQ  -4.430836124016   dC  +3.400811502583   dL  -1.030024621433
Total    dQ -39.931967891724   dC +22.309108526929   dL -17.622859364795
```

The Omori-minus-ML totals are \(+3.106623108531\),
\(+2.837707721132\) and \(+6.513790055984\), summing to
\(+12.458120885647\). The four first-block rows sum to
\(\Delta Q=-33.715204660075\), \(\Delta C=+17.197647207265\) and
\(\Delta\ell=-16.517557452810\), each row satisfying
\(\Delta\ell=\Delta Q+\Delta C\).

The 90-day paired intervals and sign-flip values are exactly
\([-25.525873,-7.458536]\), \(p=0.00104\);
\([-1.319989,1.214687]\), \(p=0.91248\); and
\([-2.087216,0.003814]\), \(p=0.05766\). The 180- and 365-day prose values
also resolve exactly: Fold 2 \([-1.109266,1.013824]\) and
\([-1.511308,1.323713]\); Fold 3 \([-2.185151,-0.091412]\) and
\([-2.149409,-0.225024]\), with annual \(p=0.015\).

The 914-event replacement audit is consistent with the prose: 241 numerical
magnitude differences, maximum absolute difference \(0.164143665\), shared
total \(-17.622859365\to-17.617975447\) with signed shift
\(+0.004883918\), Omori total \(12.458121\to12.441651\), and no fold sign
reversal.

## 4. Trend controls, eighteen-cell search and autonomous subfamily

All twelve rows of `tab:nz-trend-controls` reproduce the stored parameters,
training gains, \(\Delta Q\), \(\Delta C\) and \(\Delta\ell\). The pooled rows
are exact sums. All three rows of `tab:nz-own-mde` reproduce the
contrast-specific 90-, 180- and 365-day block standard errors and MDEs:

| Arm | SE\(_{90}\) | MDE\(_{95}\)(90) | z\(_{90}\) | MDE\(_{95}\)(180) | MDE\(_{95}\)(365) |
|---|---:|---:|---:|---:|---:|
| Free \(d\) | 4.712390 | 9.236284 | −3.739686 | 10.618718 | 13.035276 |
| Zero \(d\) | 2.763704 | 5.416861 | −4.136188 | 5.468944 | 5.869441 |
| Fixed null \(d\) | 1.395598 | 2.735372 | −3.586810 | 2.785593 | 3.037851 |

The clamped-clock counterfactual is \(-24.791220123\) in Fold 1 and
\(-26.898476699\) pooled, as displayed. The complete grid selects the winners
listed in Section 2.1 and reproduces the pooled totals
\(-11.431174\) and \(-5.005784\).

The autonomous table is exact at four decimals:

```text
Early   null -291.5675   inhibited -301.5859   gain -10.0184
Middle  null -170.2334   inhibited -170.2334   gain   0.0000
Late    null -523.5999   inhibited -526.5270   gain  -2.9272
Pooled                                       gain -12.9456
```

The audit also verifies the internal additivity
\(\text{full}=\text{ground}+\text{common mark}\), the ground identity
\(\text{ground}=\sum\log\lambda-\Lambda\), the selected-candidate argmin, all
prescribed starts, and the training quadrature gates. The middle-fold tie is a
\(-2.98\times10^{-6}\)-nat optimization difference, consistent with the
“small shared-coordinate optimization difference” caption.

## 5. Stage C1, W, D and S

### 5.1 C1

The five aggregate contrasts, fifteen per-fold rows and forty-five
zone-decomposition rows all reproduce. Exact identities verified for every
fold:

\[
\text{joint}=\text{event}+\text{compensator}
=\text{regional timing}+\text{conditional zone},
\]

with the three zone event, compensator and total arrays summing to the fold
values. The five aggregate joint values are \(349.786446432\),
\(364.573096341\), \(-3.399760657\), \(-18.186410566\) and
\(14.786649725\). The last is exactly the difference of the two inhibition
contrasts. The C1 selected \(\eta\) values are \(1.451113407,0.230848861,
0.116715431\) globally and \(0.374699463,0.517221754,0\) locally; the local
Fold 2 lower boundary is the only restrictive boundary hit.

### 5.2 W

The nine aggregate contrasts, twenty-seven window rows and eighty-one
target-region rows all reproduce. Every fold satisfies

\[
\text{joint}=\text{event}+\text{compensator}
=\text{regional timing}+\text{conditional zone}+\text{within-cell},
\]

and the target arrays sum to the fold event, compensator and joint values. The
\(\omega\)-invariance identity is verified algebraically: for parent zone \(j\)
and target zone \(k\),

\[
(1-\omega)\mathbf 1\{k=j\}+\omega\pi_k,
\qquad
\sum_k\bigl[(1-\omega)\mathbf 1\{k=j\}+\omega\pi_k\bigr]=1,
\]

so total excitation is \(nH_{\rm global}\) independent of \(\omega\) at fixed
remaining parameters. The audit checks the target-zone allocation sums for
\(\omega\in\{0,0.044,0.5,1\}\). The selected \(\omega\) values
\(0.046125,0.045172,0.044339\) and the free local/global \(\eta\) values all
reproduce.

### 5.3 D and the common-space bridge

The eight D aggregates, twenty-four window rows, 216 target-cell rows, seven
common-space aggregates and twenty-one bridge rows all reproduce. The bridge
is recomputed from the saved D and W forecasts plus the frozen training
\(q(c\mid z)\) allocation:

\[
E_{\text{ref}}=E_W+\sum\log q,\qquad
C_{\text{ref}}=C_W,\qquad
J_{\text{ref}}=J_W+\sum\log q.
\]

For every fold and every one of the seven D models, the stored common-space
event, compensator, timing, zone, within-cell and joint contrasts equal the
differences of the D candidate and this refined W reference to \(10^{-9}\).
The primary D gain is \(74.843795073\) nats, the local distance inhibition is
\(-2.275081\) nats, and the refined-W gains are \(64.290424\),
\(62.015343\) and \(61.299657\) nats. All nine cells retain proper
compensators; the target-cell arrays sum to the fold totals.

### 5.4 S and the projected cell-area lift

The six S aggregates, six decomposition rows and three selected-scale rows
reproduce. The aggregate decomposition is exact:

\[
-10.470041-4.471988+21.333833+1452.412080+0.000000
=1458.803884,
\]

and the point-event plus compensator split is
\(1448.297321+10.506563=1458.803884\). The projected cell areas from the
declared cylindrical equal-area geometry are

\[
214656.781,\ 214656.781,\ 214656.781,\
233213.240,\ 233213.240,\ 233213.240,\
249994.805,\ 249994.805,\ 249994.805\ \mathrm{km}^2,
\]

summing to \(2093594.476650\) km\(^2\). For each fold the old categorical D
score minus \(\sum_c n_c\log A_c\) equals the stored `E_oldD_lift` joint score
to \(10^{-9}\), and the stored `within_cell_density_logscore` equals
\(-\sum_c n_c\log A_c\). This is the exact lift identity claimed in the text;
it is not a comparison of categorical and density likelihoods.

## 6. Twelve-model factorial

The factorial audit covers 29 aggregate contrasts, 36 absolute arm-by-window
rows, six temporal contrasts, three location contrasts, and twelve bounded
sensitivity fits. Every aggregate equals the sum of its three folds, and every
row satisfies

\[
J=T+Z+C+W+M,\qquad J=E+C_{\text{comp}},
\]

where \(C_{\text{comp}}\) is the signed compensator gain. The combined Omori
continuous-location gains are \(1521.255407\) nats against the cell-background
lift comparator and \(1554.503812\) nats against the KDE-enriched lift
comparator, the latter \(2.540039\) nats per target. The twelve 1–2 km
sensitivity fits all lose joint score, with deltas from
\(-96.988003\) to \(-308.063524\) nats; their timing deltas are retained even
where they are positive. The selected baseline scales are 5, 15 and 15 km, and
the sealed Addendum III records the 15 km KDE bandwidth in all three windows.

The hierarchical reference obeys

\[
\pi_z=\frac{N_z}{N},\qquad
q(c\mid z)=\frac{N_c+1/2}{N_z+3/2},\qquad
b_{\rm ref}(z)=\frac{\pi_{z(c)}q(c\mid z(c))}{A_c},
\]

and the audit verifies \(\sum_z\pi_z=1\), \(\sum_{c\in z}q(c\mid z)=1\),
\(\int b_{\rm ref}=1\), the 0.05/0.95 background mixture, and the
column-stochastic lift weights. These are algebraic identities, not fitted
claims.

## 7. Claim ledger, code consistency and sealed custody

The refreshed master ledger contains 13,566 claims. Slice 3 accounts for
3,676 records that name one of the five Slice 3 sources: 156 in
`08_observed_baseline.tex`, 67 in `08_score_uncertainty.tex`, 84 in
`08_nz_trend_controls.tex`, 1,755 in `10_nz_spatial_background.tex` and 2,968
in `ch10_audit.tex`. All resolve against their bundled authorities; zero
current manuscript displays are missing. Ten withdrawn historical records are
authority-checked but excluded from current-display presence, matching
`scripts/verify_claims.py`.

The code audit rechecks the source pins used by the executable projection
(`trend_depletion.py`), the autonomous model (`model.py`), the forensic
controls, and the observed reproduction manifest. The pinned 195-mode ML
mixture has weights summing to one, the modal recursion returns the expected
\((n,195)\) state matrix, 61 modes decay by less than 1% over 24,394 days with
aggregate weight \(0.043\%\), and the autonomous first-moment formula gives
\(m_1=\eta e^{-\gamma}\beta/(\beta-\gamma)=0.4012234\) at
\(\eta=1,\beta=3.101622\).

## 8. Build, PDF QA and verification suite

The monograph was rebuilt with Tectonic 0.17.0 and installed as
`paper/manuscript_unified.pdf`:

```text
pages                 252
overfull hboxes       0
overfull vboxes       0
undefined references  0
undefined citations   0
missing figures       0
missing glyphs        0
replacement chars     0
edge text blocks      0
```

The only 23 underfull hboxes are inherited typing warnings, not production
failures. The PDF hash is `a855895b…`; the website metadata page count and hash
were refreshed before the site build.

The refreshed suite completed:

| Check | Result |
|---|---|
| `scripts/check_mathematics.py` | passed |
| `scripts/verify_claims.py` | passed (13,566 + 15,061 records) |
| main unit tests | 918 OK |
| regional unit tests | 44 OK |
| S02 input tests | 6 OK |
| regional inputs | passed |
| S02 inputs | passed |
| historical fits | passed |
| website interactions | passed (80 selector combinations) |
| repository verification | passed |
| review slices | 7 bundles exported |

## 9. Residual limitations

1. The audit recomputes saved quantities and deterministic algebra. It does
   not rerun the historical optimizers, simulate catalogues, or reconstruct
   every raw history.
2. The eighteen-cell search is verified from the stored per-cell records,
   including the exact nested floors and argmin selection; it is not refit.
3. The paired block intervals are conditional on the saved fits and the
   declared block geometry. Calendar blocks are not independent, and the
   sign-flip reference is not a randomization of independent earthquake
   sequences.
4. The lift identity is an exact projected-area arithmetic identity. It does
   not turn the old categorical scores into independent density forecasts.
5. The factorial comparisons reuse the same 612 historical targets and
   overlapping training histories. They remain retrospective fitted-procedure
   comparisons, not independent validation.
6. The 737-identity roster includes the Slice 2 acceptance record as the
   final pre-existing JSON identity; all 736 files under the two sealed roots
   are unchanged.

## 10. Artifact register

| Artifact | Path |
|---|---|
| Audit script | `experiments/methodological_audit/slice3_audit_20261114.py` |
| Pre-change snapshot | `validation/slice3_prechange_snapshot_20261114.json` |
| Pre-change zip | `validation/slice3_prechange_snapshot_20261114.zip` |
| Sealed integrity | `validation/live_results/slice3_audit_20261114/sealed_authority_integrity.json` |
| Chapter 8 baseline | `validation/live_results/slice3_audit_20261114/chapter8_baseline.json` |
| Trend controls | `validation/live_results/slice3_audit_20261114/chapter8_trend_controls.json` |
| Stage C1 | `validation/live_results/slice3_audit_20261114/stage_c1.json` |
| Stage W | `validation/live_results/slice3_audit_20261114/stage_w.json` |
| Stage D / common bridge | `validation/live_results/slice3_audit_20261114/stage_d.json` |
| Stage S / lift | `validation/live_results/slice3_audit_20261114/stage_s.json` |
| Factorial | `validation/live_results/slice3_audit_20261114/factorial_12model.json` |
| Claim ledger | `validation/live_results/slice3_audit_20261114/claim_ledger.json` |
| Manuscript repairs | `validation/live_results/slice3_audit_20261114/manuscript_repairs.json` |
| Code consistency | `validation/live_results/slice3_audit_20261114/code_consistency.json` |
| Summary | `validation/live_results/slice3_audit_20261114/summary.json` |
| Acceptance record | `validation/slice3_remediation_20261114.json` |
| Review slice | `../review_slices/slice_3_nz_baseline_and_spatial/` |
