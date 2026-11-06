# Response to the methodological review of the 61aa599 edition

The review was supplied in the project conversation. This is a response and disposition record, not a verbatim review or a certificate of external peer review. Its substantive new experiment is now complete: the uninhibited background intercept was fitted on each of the 80 existing S04B training histories and frozen for test. The [full case outputs](../../validation/live_results/methodological_20261106/refitted_floor/result.json), [score decomposition](../../validation/live_results/methodological_20261106/refitted_floor_summary.json), and [protocol and executable](../../experiments/s04b_refitted_floor/README.md) are public. The [historical methodological edition review](../../validation/reviews/METHODOLOGICAL_EDITION_20261106.json) identifies production artifacts and internal review scopes separately.

## C1 — Narrow/short immigrant generation rarely thins these realizations

The original counters confirm 2,966 accepted immigrants, 1,120 accepted offspring and one rejected immigrant across the S4 histories. Nineteen of the twenty histories have no rejected proposal. The [generator and fitted-vector census](../../validation/live_results/methodological_20261106/synthetic_diagnostics.json) now makes this visible beside the reported outcomes.

The same-seed comparison requires the actual generator's random-draw rules. Its separate streams and unconditional consumption of immigrant acceptance uniforms imply identical accepted event rows, on these no-rejection paths, for a counterfactual execution with the same runtime and settings except zero inhibition. This is a source-backed coupling argument; no new counterfactual histories were simulated. It does not make the positive generating law a mathematically degenerate null or establish a detection probability from the twenty histories. The manuscript now distinguishes a nominal positive law from the weak realized separation in this bank.

## C2 — A fixed background can handicap the uninhibited comparator

The completed control addresses this directly. Only the uninhibited intercept `a` was fitted, within the existing `[-12,0]` box, on each original training window. Trend, excitation, spatial law, mark law and history were fixed. A concave scalar rate objective allowed exact endpoint checks or a bracketed root; no inhibition search was repeated. All 480 historical train/test floor comparisons passed. Every original raw/BIC decision and inhibited selected vector was retained.

| Matched broad/long comparison | Original mean gain | Mean gain against refitted floor | New wins |
|---|---:|---:|---:|
| Immigrant-only LI+, raw and gated | 48.3868 | 5.1631 | 19/20 |
| Total-intensity LI+, raw and gated | 53.2332 | 9.7367 | 18/20 |

These are held-out joint nats. The control substantially reduces the original advantages and therefore supports the reviewer's concern about comparator choice. The residual positive gains are the actual result of this sensitivity, not a foregone conclusion. All other regimes and procedures remain in the complete output. This comparison does not jointly refit the inhibited alternatives or reselect their gates. The output separates point contribution, nonnegative exposure `E`, signed exposure `C=-E` and marks; `delta_joint=delta_P+delta_C+delta_M`, with unchanged marks.

## C3 — Mark moments and score regularity need their actual assumptions

The [moment diagnostic](../../validation/live_results/methodological_20261106/moments.json) now evaluates the relevant exponential-mark expressions for the implemented temporal and spatial scalings. The spatial LI+ weighted second-moment condition fails. [Chapter 5](../../paper/source/chapters/05_inference.tex) supplies a separate first-parent argument for null-law divergence under its stated kernel and fresh-mark assumptions, rather than treating failure of a sufficient bound as a proof by itself. Total attenuation has a different score and corresponding moment obstruction.

The revised analysis also separates the exact null from fixed positive generating strength, where attenuation supplies the stated finite-bracket bounds. These bounds do not establish variance for an arbitrary selected, misspecified held-out score contrast, uniform behavior near zero, or the exact cause of a particular large loss. The paper retains the losses and the descriptive Monte Carlo summaries with those distinctions explicit. No saved adverse result was removed or explained away by the moment calculation.

## C4 — Boundary selection and eta-zero fits were under-described

All 240 original fit vectors and solver records are supplied. The new census reports selected parameter ranges, boundary counts and zero-strength cases. For S4 unit-mark LI, seventeen active selected fits hit a boundary; including the one zero-strength selected fit gives eighteen boundary cases. The matched immigrant candidate has fourteen boundary selections. Both exact equality and the declared native-coordinate tolerance are recorded.

The cited start that converges to zero inhibition has the appropriate one-sided objective derivative, while the stress-shape derivatives vanish on the zero-strength face. Another start reaches a better active objective and is selected by the original multi-start rule. That establishes start dependence and weak identification; it does not, by itself, prove a numerical optimizer defect or global optimality. The cited unit-mark candidate is also not the matched magnitude-scaled generating model. The obsolete description of the public evidence as only off-floor indicators has been replaced. Shared background/excitation coordinates were fixed; the prose no longer suggests these fits adjusted them.

## C5 — Autonomous family equivalence and practical stability scale

The current paper explicitly identifies the autonomous comparison as the same raw `d=0` conditional-intensity family as the earlier constant-background sensitivity. Both the training estimate of the magnitude rate beta and the optimization recipe changed: starts, solver settings, recovery and candidate accounting differ. The small change in score cannot be attributed to beta alone. Original and later results remain separately available.

The [stability diagnostic](../../validation/live_results/methodological_20261106/stability.json) makes the scale of the pinned finite-mixture certificate explicit. Under the stated criterion, **61**, not 72, modes decay by less than one percent across the observed horizon. Their normalized weight is also reported. The conservative theorem certificate supplies no useful mixing-time guarantee at that horizon; it does not estimate the actual process mixing rate or demonstrate that all those slow modes have a large empirical effect. The latent equilibrium-loading mapping is distinguished from stationary initialization of the event process.

## M1 — Rare quiet histories in the active-identification proof

[Chapter 4](../../paper/source/chapters/04_identifiability.tex) now writes the quiet-path survival probability and explains its decay when productivity grows exponentially with the mark. Every finite-mark history used by the proof has positive support, but these informative quiet histories can become extremely rare before the limiting argument identifies the full law. The result remains a restricted structural-identification proposition; it supplies no finite-catalogue estimation rate or frequency guarantee. Constant-productivity candidates do not inherit its unbounded-productivity step.

## M2 — Spatial construction and observation restrictions

[Chapter 2](../../paper/source/chapters/02_models.tex) now states the consequences of the common isotropic radius, omitted magnitude-dependent rupture extent and directional geometry, and cell-boundary jumps from reference-density weighting. It also distinguishes short-term aftershock incompleteness from the fitted attenuation laws. These changes describe the actual model construction; this edition did not fit a new physical stress-transfer model, a directional rupture model or a short-term-incompleteness observation law. The occurrence-score comparisons therefore remain comparisons of the declared procedures on recorded events.

## E1 — Repeated scope prose and editorial interruptions

The live manuscript consolidates common method scope in Chapter 6, reduces repeated memo-style descriptions of updates and addenda, and retains concise local reminders where table interpretation depends on them. Mathematical assumptions and distinct numerical procedures remain beside the relevant results. Historical documents preserve the wording of their own editions.

## E2 — Obsolete repository URLs

Eleven live manuscript links using the old repository name were replaced with the canonical repository name and the existing `61aa599` commit pin. This corrects the locations while preserving the cited historical file identity; it does not relabel a historical protocol as a newly executed one.

## E3 — Original executions, later replays and device-specific tests

No old California optimizer fit was rerun in this revision. The original completed fit and score records remain supplied, and their scope is distinguished from later cohort reconstruction or adapter checks in the [provenance map](../result_provenance.md). The new numerical work here is the scalar S04B comparator sensitivity described above.

The historical iteration-27 suite includes a CUDA/CPU comparison and needs a suitable separate installation and device. That prerequisite is not a dependency of the new CPU intercept control. The [validation guide](../../validation/README.md) lists all suite commands, and [current checks](../../validation/checks.json) report actual executed counts and skips separately from portable CI coverage. Source support for a compiler or device is not substituted for a recorded execution.

The original results and protected scientific authorities remain intact. New conclusions are tied to the completed sensitivity and explicit diagnostics; the existing F withdrawal remains in force. This response does not claim prospective confirmation, general parameter recovery, nominal test size or external academic acceptance.
