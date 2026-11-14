# Forensic audit response, 14 November 2026

**Baseline:** `e8db032` (`validation/referee_remediation_20261113.json`).

**Scope.** This is an additive correction package for the five computational/statistical errors and three theory/custody gaps identified in the forensic audit of the 13 November Track B / referee-remediation commit. All new numerical outputs are under `validation/live_results/forensic_remediation_20261114/`. The pre-change bytes of every sealed authority and every pre-existing live-result JSON are recorded in `validation/forensic_prechange_snapshot_20261114.json` and `.zip`; the independent audit re-hashes all of them and finds no change.

## F1 — New Zealand trend controls

The archived comparison used the free-trend 90-day MDE against the fixed-null contrast. That is the wrong noise scale. Rebuilding the paired calendar-block scores from the exact 90-, 180- and 365-day edges gives:

| Control | Δℓ (nats) | SE₉₀ | MDE₉₅(90) | z₉₀ | MDE₉₅(180) | MDE₉₅(365) |
|---|---:|---:|---:|---:|---:|---:|
| Free d | −17.623 | 4.712 | 9.236 | −3.74 | 10.619 | 13.035 |
| Zero d | −11.431 | 2.764 | 5.417 | −4.14 | 5.469 | 5.869 |
| Fixed null d | −5.006 | 1.396 | 2.735 | −3.59 | 2.786 | 3.038 |

The fixed-null loss is 1.83 times its own 90-day MDE and −3.59 of its own standard errors. Freezing \(d=d_{\rm null}\) shrinks \(\hat\eta\) (Fold 0: 1.647 → 0.178) and the block scale together, so the detrended loss is not “below its own detection scale”. The full 18-cell \((\alpha,\tau,r)\) two-start search with an exact \(\eta=0\) floor selects the same winners and leaves the held-out totals unchanged: zero-d −11.431, fixed-null-d −5.006.

Evidence: `nz_trend_controls.json`; manuscript Chapters 8 and 14, abstract, README, companion and website.

## F2 — California EP+ η profiles

`interpolate_bound()` used a linear secant between \(\eta=0\) and \(\eta=0.01\), where the profile has already fallen by hundreds to thousands of nats. The corrected calculation evaluates \(\partial_\eta\ell|_{\eta=0}\) analytically and finds both the two-sided 95 % / one-sided 97.5 % cutoff (−1.9207) and the one-sided 95 % cutoff (−1.3528) by Newton and `brentq`. At the S8 scale pair (15 km, 5 d) the F0 roots are \(1.1414\times10^{-4}\) and \(8.1665\times10^{-5}\), not the archived \(3.63\times10^{-5}\). The profiled curve is re-based on the uninhibited MLE \(x_0=\hat\psi(0)\), and the held-out contrast is re-based on the same \(x_0\). The corrected F0–F2 held-out contrasts are −74.708, −10118.507 and −27.189 nats (archived corrupted values −73.759, −10119.528, −25.748).

The unscaled \(\ell=15\) km profile gives two-sided roots \(8.887\times10^{-4}\), \(8.533\times10^{-4}\), \(5.869\times10^{-4}\), about eight times the rupture-scaled values. The scaled \(M7.1\) Ridgecrest range is 532.2 km; the unscaled range is 15 km. The event-weighted attenuation sum in California Fold 0 is 75,313.9 versus an exposure integral of 59,415.5, forcing \(\partial_\eta\ell|_0=-15{,}898.4\).

Evidence: `eta_profiles.json`; manuscript Chapter 11.

## F3 — S8 oracle decomposition

The sign of the partial-oracle contrast was inverted in the prose. \(\ell_{\rm test}(\hat a,\theta_{\star,0,-a})-\ell_{\rm test}(\hat\theta_0)=+3.571\) means the five-parameter training-fitted null comparator scores **worse** on held-out data by 3.571 nats — an overfitting loss, not an estimation gain. Seed `410840` contributes a 75.278-nat loss; across the other 19 seeds the mean is −0.203 and the 20-seed median is −1.683 nats.

Partial oracle B is rerun from five starts (fitted backbone, intercept-refitted true backbone, true generating backbone, two neutral interior starts): mean 2.824 nats, median 5.903, 15/20 wins. Partial oracle C combines the true generating backbone (and its intercept-refitted version) with each history's fitted \((\hat\eta,\hat\ell,\hat\psi)\): mean held-out loss −6.513 nats, median −3.131, 1/20 wins.

Evidence: `s8_oracle.json`; manuscript Chapter 13, abstract, README, companion and website.

## F4 — Japan MDE arithmetic and annual blocks

The archived per-event arithmetic omitted the 1.96 factor and divided the per-fold MDE by the three-fold event count. Corrected values:

- three-fold sum: \(47.93676/1277=0.03754\) nats per event, \(\delta=27.40\%\);
- per three-year fold: \(15.97892/(1277/3)=0.03754\), \(\delta=27.40\%\);
- nine annual JMA blocks pooled within folds: \(\mathrm{SE}_{365}=28.82988\), \(\mathrm{MDE}_{95}=56.50656\), \(0.04425\) nats per event, \(\delta=29.75\%\).

The three folds are 2016–2018, 2019–2021 and 2022–2024, not three annual fold totals. The nine annual `OC−EP` joint blocks are the genuine annual contrasts.

Evidence: `japan_mde.json`; manuscript Chapter 14.

## F5 — Clean EP+ ablation and relaxed σ₀

A3, A4, A7 and A8 now each run their own five-step training-declustering loop under their own normalization and scaling, starting from the neutral three-start grid; no arm imports A8's accepted weights or post-declustering state. The self-declustered decomposition is 27.605 nats for declustering, 31.669 for scaling, 10.241 for joint fitting and 0.037 for normalization, closing on 69.551 nats. The archived frozen-A8-weight decomposition was 29.223, 30.026, 10.241 and 0.064 on 69.553 nats; the cross-arm leak inflated declustering by about 1.62 nats and depressed scaling by about 1.64 nats.

The archived relaxed-sigma0 total double-counted the plane and rectangle panels. The separate totals are plane 77.056, rectangle 77.059 (redeclustered) and plane 78.584, rectangle 78.518 (frozen weights). Refitting the full twelve-parameter inhibited model under \(\sigma_0\ge0.05\) km from the nested null and the three prescribed positive starts returns \(\hat\eta=0\) in every fold and start, with interior \(\hat\sigma_0=0.828, 0.845, 0.827\) km. The zero-strength boundary is therefore not a 2 km search-box artefact.

Evidence: `epplus_ablation.json`, `epplus_sigma0_totals.json`, `epplus_relaxed_inhibited.json`; manuscript Chapter 11 and abstract.

## F6 — Tightened Pinsker bound, Doeblin constant, epicentral geometry and custody

**Pinsker.** The background-discarded bound is \(C_T=2.8662509\times10^6\) days², \(K_T=3.6644466\times10^5\), threshold \(2.3362\times10^{-3}\). The F6 ``tightened'' display \(C_T^{\rm tight}=\int\Phi^2/(B_{\min}/B_{\max}^2+nh)\) and its \(K_T^{\rm tight}=0.0133269\) are withdrawn by the Slice 1 audit: \(B_{\min}/B_{\max}^2\) has units of days while \(nh\) has units of inverse days, and \(B_{\max}^2\) was already restored in \(K_T\). The corrected full-process clipped bound is \(\mathcal B\min\{1,\eta^2K_T\}\), still vacuous above \(2.3362\times10^{-3}\). A dimensionally exact one-event single-parent bound gives 0.0015266 at \(\eta=0.10\), 0.0042328 at \(\eta=0.178\), 0.1867405 at \(\eta=1.65\) and 0.7883534 at \(\eta=4\), first reaching one at \(\eta=4.6419\); it is not a full-process bound. See \texttt{docs/reviews/slice1\_math\_audit\_20261114.md}.

**Doeblin.** \(R=4D/\kappa_V\propto e^{38.8}\) and \(t_0\ge\log4/\vartheta_{\min}\) give \(\Lambda_R t_0\sim e^{116.4}\). The empty-interval probability \(e^{-\Lambda_R t_0}\) is of order \(\exp(-3.5\times10^{50})\), so the displayed minorization coefficient is positive but numerically indistinguishable from zero. The theorem is a qualitative certificate at this scale.

**Epicentral peak.** The unimodal kernel \((1+\|z-z_j\|^2/\ell_j^2)^{-2}e^{-(t-t_j)/\psi}\) is radially monotone and peaks at the parent epicentre and origin time. Positive \(\eta\) therefore suppresses the modelled rate most strongly inside the active aftershock zone, not in an annulus or a signed off-fault lobe. The California Fold 0 sums (75,313.9 event-weighted versus 59,415.5 exposure-integrated) make this explicit.

**Custody and dates.** `scripts/verify_claims.py` now records every literal input in the compiled manuscript tree, including `13_s04b_joint_quantiles.tex`. The S4–S7 subheaders carry descriptive regime names and mean training/test counts. The edition date is 14 November 2026 across `main.tex`, companion, website metadata, findings page, README and `REVIEWER_START_HERE.md`.

## Acceptance evidence

- `python -B experiments/methodological_audit/forensic_remediation_20261114.py --output validation/live_results/forensic_remediation_20261114`: all component outputs written.
- `python -B experiments/methodological_audit/audit_forensic_remediation_20261114.py --input validation/live_results/forensic_remediation_20261114`: **190 checks, 0 failures**, including root residuals below \(10^{-6}\), per-event MDE identities, Shapley closure, separate plane/rect totals, and sealed-snapshot integrity.
- `python -B scripts/build_paper.py ... --install`; `validate_pdf.py`: 252 pages, 0 overfull boxes, 0 undefined references/citations, 0 missing glyphs.
- `companion/build_guide.py`: 12 pages, HTML/PDF section counts consistent; workflow test passes.
- `website/build_site.py`; `node website/check_interactions.cjs`: passed (80 selector combinations).
- `scripts/verify_claims.py --write-receipts`: passed, release-ready, 0 missing declared manuscript displays.
- `scripts/verify_repository.py --write-manifest`: 10,828 files, passed.
- `unittest discover -s tests`: 918 tests OK; regional: 44 OK; S02: 6 OK; regional and S02 input verifiers passed; historical-fit verifier passed.

**Disposition.** Corrected and accepted as an additive forensic remediation. The sealed authorities and the 345-file pre-change sealed roster are unchanged. The corrected results supersede the affected 13 November prose and tables; the archived referee-remediation files remain intact as historical evidence.
