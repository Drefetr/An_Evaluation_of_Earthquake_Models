# C5 stability and autonomous-family audit

Scope: read-only audit of baseline `61aa599` and current candidate sources. No optimizer, model likelihood, simulation, or replay was run. The standalone `audit_calculations.py` uses scalar algebra and already saved JSON values; `calculations.json` contains exact inputs, derived values, and source hashes. Other agents' current source edits were left intact.

## Disposition

| Assertion | Finding | Required action |
|---|---|---|
| The smallest mode rate makes the displayed proof certificate impractical | Substantially correct | Quantify the certificate in Chapter 3; distinguish a sufficient proof bound from actual convergence speed. |
| 72 modes decay less than one percent over the catalogue horizon | Incorrect | Correct to 61; show the index boundary and their small total normalized kernel weight. |
| The autonomous experiment introduces a new intensity family relative to Chapter 9 raw constant-background sensitivity | Incorrect | Identify the same family, with a new execution and a changed fitting recipe. Preserve both result records. |
| Beta alone accounts for the difference in pooled scores | Unsupported causal attribution | Explain beta's role, but also record changed optimizer starts, tolerances and candidate policies. Existing records do not isolate their separate contributions. |
| Equilibrium loading is confounded with the intercept | Correct under the specified equilibrium initialization and exponential link | State the exact mapping and distinguish non-equilibrium loading from the affine diagnostic trend. No new loading fit is required to correct this description. |

## Quantitative stability certificate

`engine/iteration_5/code/kernels.py:37–49` constructs the mixture. For alpha=.5, tau=1, step=.4 and tail bound=1e-8, its integer half-count is 97. Thus there are 195 modes with rates `exp(.4*j)` for j=-97,...,97. The minimum rate is `exp(-38.8)=1.4105032856773367e-17` per day. Its inverse is `7.089667994071994e16` days, or `1.9410453098075272e14` years using 365.25 days per year.

The manuscript's drift constant is `kappa_V=theta_min*min(1,delta/c)` (`03_stability.tex:73–92`), so it cannot exceed the minimum rate. Its synchronous construction requires `t0 >= log(4)/theta_min` (`:95–114`), at least `9.828366762394171e16` days or `2.6908601676643862e14` years. Since L>=1, the chosen local radius also satisfies epsilon<=`3.526258214193342e-18`.

The proof's small-set deficit is `.5*exp(-Lambda_R*t0)`, with `Lambda_R=barPsi+theta_max*R/c` (`:115–127`). Even replacing Lambda_R by the much smaller barPsi and t0 by its lower bound gives logarithmic deficits from about -1.36e15 to -1.78e15 for the six saved selected states. This verifies the review's warning about a negligible proof certificate, but not an exact universal `exp(-1e15)` contraction factor. The explicit admissible c/diameter examples in `calculations.json` are considerably more conservative. They are examples of this proof construction, not optimized constants or actual process rates. The theorem still supplies existence, uniqueness, finite first Lyapunov moment and asymptotic convergence; it does not give a useful practical burn-in or catalogue-scale uncertainty guarantee.

The slow-mode count follows `1-exp(-theta_j*24394)<.01`. Exactly **61** indices, -97 through -37, satisfy it. The boundary j=-37 decays 0.009072919115771733; j=-36 decays 0.013504959269522035. Reviewer index -26 instead decays 0.5240155010475867. The 61 slow modes have total normalized survival-kernel weight **0.00042934294645172454**. This weight is relevant to their contribution to Phi; it is not a universal bound on arbitrary initialized mode states, cumulative observed stress, or the mixing time. Neither raw mode count nor the poor worst-case proof constant establishes the actual process is physically inert.

## Exact family equivalence and protocol differences

The physical flow and jumps are explicit at `02_models.tex:17–31`; the mild solution is at `:56–63`. With rho=0, zero stress/excitation initial modes, b=1, g=eta*g_d and physical productivity=n*kappa_d, the conditional intensity is exactly

`lambda(t)=exp(a-eta*G(t))+n*H(t)`, with `h=-Phi'`.

This is the raw I0/E0 family in `09_temporal_mark_extensions.tex:457–465` with d fixed to zero. It is not the orthogonal constant-background restriction: fixing the detrended trend coordinate changes the raw family (`:1225`). The H/R reference and Stage A raw ML comparisons use the same fixed shared mixture, fixed r=.7 and same observed chronological windows. The Stage A authority `validation/authorities/cf8397fb41830b31_summary.json` gives the following direct saved-result comparison:

| Fold | Older conditional-bin beta | New global beta | Old raw I0−E0 gain | New inhibited−null gain |
|---|---:|---:|---:|---:|
| Early | 3.053780173208927 | 3.1016219112585786 | -10.010951711546568 | -10.018403133332754 |
| Middle | 2.997652889101673 | 3.1494882081661726 | 0.000006485573919690069 | -0.0000029768964395771036 |
| Late | 2.9359340507306295 | 3.021907322176272 | -3.0257284583281034 | -2.9271517016724147 |
| Pooled | | | -13.036673684300752 | -12.945557811901608 |

The older conditional-bin estimator maximizes `N log(beta)-beta(sumQ-Nhigh*c)-Nlow log(1-exp(-beta*c))`, whereas the new estimate is N/sumQ. Beta enters `(1-r)exp(beta*r*Q)`, so a beta change affects occurrence likelihood and not just the common mark term. Both common mark terms cancel within their respective inhibited-minus-null contrasts.

The original Stage A protocol is preserved at `work/addenda_synthesis_20261029T051520Z/study/research_results/stage_a/protocol_observed_v1.json`; its SHA is in `calculations.json`. The matching H protocol is `research_runs/magnitude_prediction_20261023T222049Z/observed_protocol.json`. They explicitly describe a changed nuisance/optimization protocol relative to earlier global-beta work.

| Procedure detail | Earlier H / raw Stage A | Executed autonomous protocol |
|---|---|---|
| Null starts | Eight: a0 or a0-.5, n=.1/.35/.65/.85 | Four: a0±.5, n=.2/.7 |
| Inhibited eta starts | 0,.1,.2,.4,.7,1,2,3 | 0,.02,.05,.1,.2,.5,1,2 |
| L-BFGS-B | maxiter200, ftol1e-10, gtol2e-6 | maxiter250, ftol1e-12, gtol1e-7 |
| Powell recovery | maxiter400, xtol1e-6 | maxiter500, xtol1e-7 |
| Candidate accounting | Exact floors and feasible mapped candidates; stable candidate IDs; forecast-spread diagnostics | Fitted-null floor; exact minimum with floor-first exact tie handling; no same mapped-candidate roster |
| Implementation | Compiled cached objective and its independent controls | Pinned iteration-27 Python objective and order16/32 controls |

Both retain the same a/n/eta boxes and training-only selection, and both require mandatory start completion. `experiments/autonomous/protocol.json`, `fit.py:32–86,98–126`, and `model.py:83–94` establish the newer policy. The middle-fold signed differences are numerical shared-coordinate differences at eta=0, not evidence of an inhibition effect. No controlled beta-only change was executed in this audit, so the relative attribution is unresolved and should not be asserted.

## Loading and intercept

For general rho, let `S=sum_j(w_j/theta_j)`. If `Z_j(0)=rho/theta_j` and initial excitation is zero, the mild solution gives `X(t)=rho*S-eta*G(t)`. The exponential link becomes `exp(a+b*rho*S-b*eta*G(t))`. With b fixed, only `a_eff=a+b*rho*S` is identified by this parameterization. The mapping `(a,rho) -> (a-b*Delta*S,rho+Delta)` leaves the conditional intensity unchanged when the initial modes are shifted consistently and parameters remain admissible. Canonical rho=0 removes this redundancy; it is not an empirical estimate of physical loading. If b is free, the stress-scale combination also needs attention; no claim of separate b/eta identification is made here.

For equal non-equilibrium initial modes `Z_j(0)=X0`, the deterministic stress is `X0*Phi(t)+rho*integral_0^t Phi(u)du`; for arbitrary modes it is the displayed weighted exponential sum plus the integral. It is generally not the affine diagnostic time coordinate. The equilibrium initialization is the event-free ODE equilibrium, not a draw from the stationary event-process law. These distinctions are already substantially correct in `experiments/autonomous/DERIVATION.md:30–42` and should be brought next to Chapter 8's empirical model mapping.

## Concrete edit map

1. **Chapter 3, after current line58:** add a short quantified paragraph stating minimum rate, the resulting lower scale required by the proof's t0 choice, the corrected slow-mode count and normalized weight, and explicitly deny interpreting these as actual mixing-time estimates. Retain the theorem and its assumptions. Source any new displayed scalars to `calculations.json` through the conductor's current live-result custody workflow; do not edit bundled authorities.
2. **Chapter 8, lines215–245 and271–275:** say this is a separately executed fit of the raw constant-background family also used in Chapter 9; add cross-references to the constant-background tables/protocol. Explain common mark law change and changed optimizer recipe. Do not describe it as a newly introduced model family or a beta-only experiment. Add the equilibrium-loading/intercept mapping and non-equilibrium distinction without expanding the scientific scope.
3. **`docs/result_provenance.md:10`:** replace “new restricted model comparison, not a replay of an older model” with “new execution of the same raw constant-background intensity family used in Chapter 9, under a separately specified nuisance and optimizer recipe; it does not reproduce the earlier fitted procedure.”
4. **`experiments/autonomous/README.md:5–9,44–47`:** remove “Existing historical results are neither changed nor represented as fits of this model,” which incorrectly denies the raw constant-background equivalence. Distinguish algebraic family from executed procedure and link the earlier tables and unchanged frozen protocol.
5. **`experiments/autonomous/DERIVATION.md:3–4`:** update the current explanatory note to acknowledge earlier raw constant-background family equivalence and the completed comparison. Keep the original frozen `protocol.json` bytes untouched. Add a short practical-bound cross-reference and retain the accurate loading/first-moment mapping.

No new model fitting, loading experiment, or withdrawal of these bounded negative results is required to implement these corrections. A genuine attribution of the score change solely to beta would require a separate controlled procedure comparison; the paper can resolve its present error by declining that unsupported attribution.
