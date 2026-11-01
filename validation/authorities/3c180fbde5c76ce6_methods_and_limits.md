# Methods and interpretation limits

This note was prepared from the frozen pilot protocol and completed source/numerical reviews while the pilot was running. It contains no pilot outcome summaries. The frozen protocol, source manifests, raw case artifacts and final independent audit take precedence over narrative shorthand.

## Scientific target

The experiment asks whether history dependence in earthquake magnitudes can change the existing staged procedure's preference for inhibition under a purely excitatory generating law. It is an exploratory misspecification stress test. The changing experimental factor is persistence of magnitude classes, with the untyped event-time law and each event's marginal continuous magnitude distribution held fixed within the designed family.

For scenario `h` and planned independent skeleton `s`, let G(s,h) be the procedure's resolved direct likelihood-ratio statistic and eta(s,h) its selected inhibition parameter. The frozen descriptive preference indicator equals 1 when `G` exceeds `0.001` and `eta` exceeds `1e-6`. These thresholds define an operational preference; they are not calibrated significance cutoffs. The primary contrasts compare the preference indicator and continuous statistic at positive `h` with the matched baseline at `h = 0` on the same skeleton.

Every scenario's planned denominator is retained. Resolved-only frequencies estimate a resolution-conditional descriptive quantity, with its denominator stated. If `k` cases select inhibition and `u` cases are unknown out of `N` planned cases, the all-planned selection frequency is bounded by `[k/N, (k+u)/N]`. These are missing-outcome accounting bounds, not confidence intervals. Continuous-statistic summaries based on resolved cases remain conditional summaries; missing continuous values are not replaced by zero.

## Designed excitatory generator

Use excess magnitude `Q = M - M0`, mark rate `b`, bin cutoff `a` and probabilities `p0 = 1 - exp(-ba)`, `p1 = exp(-ba)`. The bins are `[0,a)` and `[a,infinity)`. The frozen pilot uses a common normalized Mittag-Leffler waiting density `k`, generator branching mean `n_g` in `(0,1)`, total immigrant rate `mu` and empty prehistory on a fixed observation window `[0,T]`. Its receiving/source matrix is

`P(i|j)=(1-h)*p_i+h*1{i=j}`

and its ground component intensities are

`lambda_i(t)=mu*p_i+n_g*sum_(j:t_j<t) P(i|J_j)*k(t-t_j)`.

All terms are nonnegative. Each event can increase class intensities but cannot make a negative contribution to an absolute class intensity. The conditional class probabilities can nevertheless fall or rise because they are ratios of those intensities.

The frozen persistence values are `h = 0`, `0.5` and `0.9`. The actual pilot kernel has Mittag-Leffler shape `0.5` and scale `1` in days. The independent compiled core supports only shape `0.5` and `1`; support for another shape is not claimed. Here `b` is the continuous mark rate and `n_g` is the generator branching mean. They are distinct from similarly named shape/productivity parameters in the preserved comparison engine.

## Why the marginal marks and timing law match exactly

Generate the untyped Poisson immigration/branching forest first: immigration has rate `mu`, every node has Poisson(n_g) offspring, and independent positive offspring delays have density `k`. Its counts, genealogy and times do not depend on class labels. Give each immigrant a class drawn from `p`, and each child a class drawn from its parent's column of `P`.

The columns of `P` sum to 1, and `P*p = p` when `p` is a column vector. Conditional on any fixed untyped timed forest, every root has marginal `p`; induction along every genealogical edge gives the same marginal for every node. Chronological indexing and fixed-window censoring depend only on the untyped forest. Therefore every chronological event also has marginal `p`, including conditional on the entire untyped time skeleton and its event count. This is a finite-window statement; no stationarity or burn-in argument is needed.

Given the selected class, draw Q from Exp(b) conditional on its bin. The mixture of those conditional densities with weights `p` is exactly `b*exp(-bQ)` on `[0,infinity)`. Thus every scenario has the same exponential one-event marginal law. At `h = 0`, class draws are independent of the complete untyped skeleton and of other class draws; the continuous marks are iid exponential. At positive `h` the marks generally depend on labelled history even though each one-event marginal is unchanged.

In particular, writing S_i(t) for the sum of kernel contributions from prior class `i` events and `S = sum_i S_i`,

`Lambda(t)=sum_i lambda_i(t)=mu+n_g*S(t)`

and

`lambda_i(t)/Lambda(t)=p_i+(n_g*h/Lambda(t))*(S_i(t)-p_i*S(t))`.

The total timing intensity is independent of `h` and labels; the conditional class probability generally is not. Label-dependent selection, such as conditioning on a particular observed class count, need not preserve the marginal argument. Nor are positive-`h` class counts multinomial simply because every node has marginal `p`.

## Pairing and experimental unit

The plan contains 20 independent untyped skeletons, each labelled under all three persistence scenarios. There are 60 scenario catalogues but 20 independent replicate blocks. Pairing shares the untyped skeleton and fixed per-node random inputs, while each scenario generates its own conditional labels and within-bin magnitudes. One fixed iid mark sequence must not be reused as the observed marks in every scenario.

Separate time and mark pseudorandom streams, their exact implementation, the compiler and runtime are pinned. Equal seeds in another language or standard-library implementation are not asserted to reproduce the same streams. Uncertainty for persistence contrasts resamples skeleton blocks. Resolved-only paired contrasts state the number of paired-resolved skeletons; all-planned bounds additionally retain unknown preference indicators. Pilot intervals are exploratory Monte Carlo summaries, not confirmatory coverage certification.

## Existing comparison and its narrower scope

The frozen primary procedure estimates background level and trend together with the inhibition alternative, while retaining the staged procedure's supplied triggering, stress and mark-rate settings. Its prescribed starts comprise two null fits followed by two alternative starts from the selected null. A secondary supplied-background procedure uses two inhibition starts. The supplied-background label does not mean its nuisance settings are true generating parameters.

This source-bound six-start staged comparison is narrower than the historical full kernel/productivity searches, the separate later nuisance continuation or the observed-catalogue fitting recipe. Results must identify this exact procedure. They cannot be substituted into historical counts, reference banks or claims about the larger searches. Solver starts, explicit `eta = 0` eligibility, subset floors, failure-only recovery and original numerical controls remain part of the procedure. Local optimization is not a global optimum certificate.

The `h = 0` scenario is the experiment's independence baseline, not an in-model null-size experiment for the old procedure. The generator has `gamma = 0` magnitude productivity, while the old candidate intensities depend on prior continuous marks through their productivity and stress transforms. Exact Mittag-Leffler generation and the old finite-mixture representation also remain distinct. These mismatches are common to the persistence scenarios; the paired persistence contrast isolates the change in magnitude history within this deliberately specified stress family, without establishing correct specification at `h = 0`.

The primary comparison uses the same realized continuous marks and exposure for its excitatory and inhibitory candidates. A common mark-density term can cancel within that paired comparison, but marks still enter subsequent candidate intensities. Dropping a common density term does not justify discarding the marks. No comparison of raw continuous densities with discrete bin masses is made, and no held-out forecast-score claim follows from these fitted-statistic preferences.

## Exposure, numerical validation and reproduction

The synthetic window is fixed independently of the first and last events. The likelihood retains initial quiet exposure, every positive event gap and the final no-event interval. Saved two-part timestamps and positive gaps define ordering, including cases where a lossy binary64 projection ties. The generator reports a precision failure when its declared parent-child wait-error gate is exceeded; it does not redraw a wait, jitter an event or replace a magnitude to force completion. Resource caps and unresolved mandatory solver states stay explicit unknown outcomes.

The computational route combines an independently implemented C++ generator/numerical core, an R interface and the preserved Python comparison machinery with its declared CUDA/FP64 primary route and existing failure-only recovery. It is not a full rewrite of the historical engine. Independent mathematical/spectral-quadrature, saved-clock and waiting-law controls have separate evidence and declared finite scopes.

An additional reference bridge ran the original released ml.m in GNU Octave. A private byte-preserving copy changed only the C++ dispatch switch to select its original language implementation; the copyright notice and original clone were retained. Fixed-input survival and kernel calculations were compared against the new independent core. This is executable original-source validation without MATLAB, not reproduction of the original MATLAB optimizer, all fitted examples or every numerical regime.

The exact author preprint is separately pinned from the version of record. The exact published supplement remains unavailable in this run, the released Japan CSV contains no event rows, and historical banks excluded from the existing public package remain unavailable. Those gaps constrain exact-reproduction claims; they do not authorize reconstructing historical inputs by guesswork. Third-party source copies and raw catalogue material are not covered by a blanket project licence and remain outside a tidy public payload unless their terms are established.

## What this pilot cannot establish

`gamma = 0` is a boundary/limiting case of the released positive-productivity fitting transform. The unbounded final magnitude bin extends the article's finite upper magnitude support. The accurate model label is a designed MDFHP-form excitatory stress family with matched exponential marginal marks, not an exact recovered author fit or the entire MDFHP family.

No correctly specified richer excitatory model is fitted in this bounded pilot. A changed inhibitory preference would demonstrate a vulnerability or response of the selected old procedure under this generator; it would not establish that an estimated MDFHP practically absorbs the effect in observed data. Conversely, a small or unresolved contrast would be limited to this family, sample budget and fitting procedure; it would not rule out other magnitude-history mechanisms.

There is no fresh null calibration, size-matched power comparison, observed-catalogue evaluation, causal intervention or physical inhibition identification. Pointwise checks cannot establish uniform performance over nuisance parameters. No combined inhibitory MDFHP, general exact-memory stability theorem, exhaustive novelty claim or external-publication conclusion is asserted. Final claims require terminal saved outputs, complete failure accounting and independent review.

## Evidence map

- `pilot_protocol_frozen.json`: estimand, scenarios, sample plan, comparison contract, resources, analysis and exclusions.
- `sources/model_mapping.md`, `methods/construction_review.md`, `sources/ds16_cross_review.json`: source equations and independently reviewed finite-window construction.
- `sources/source_manifest.json`, `sources/reproduction_gaps.json`: exact source identities, versions, licences and missing assets.
- `sources/octave_reference/source_copy_identity.json`, `sources/octave_reference/comparison_report.json`, `sources/octave_reference/terminal_receipt.json`: private original-source Octave bridge.
- `sources/methods_independent_controls_cross_review.json`, `methods/independent_controls_receipt.json`: independent numerical controls and their scope.
- `methods/final_pilot_protocol_review.json`, `methods/freeze_confirmation.json`: pre-pilot protocol review and identity confirmation.

The final report should add terminal result and independent saved-output audit references. This note deliberately leaves the pilot outcome interpretation open.
