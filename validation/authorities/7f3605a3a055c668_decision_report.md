# Magnitude-history robustness: bounded pilot decision report

Prepared 24 October 2026 NZDT. Run `magnitude_history_20261023T205716Z`.

The validated machinery is feasible, and the full bounded pilot completed: 20 independent timed forests, three magnitude-dependence scenarios, 60 catalogues and 120 resolved method outcomes. No planned outcome is missing.

Under the frozen descriptive rule, the primary fitted-background comparison preferred positive inhibition in 15/20 independent-mark controls, 17/20 moderate-dependence histories and 18/20 strong-dependence histories. However, both primary paired GLR-difference intervals span zero. This pilot does not establish a clear increase in likelihood evidence specifically caused by magnitude history, or explain previous observed-catalogue evidence.

A nested, unpenalized alternative can improve fit under an excitatory generator. The rule below resolves a positive fit preference near numerical tolerance; these frequencies are not calibrated false-positive rates and do not demonstrate failure of any advertised calibrated inhibition test.

## Frozen scientific target

The generator is a designed two-class MDFHP-form excitatory family with common Mittag-Leffler shape 0.5 and scale 1/day, total immigrant rate exp(-4.162108473051707), offspring mean 0.5 and empty prehistory over 24,394 days. Magnitude excess has marginal exponential rate 2.849401764894274, with bins [0,0.5) and [0.5,infinity). The gamma=0 productivity boundary and unbounded final bin are explicit extensions of the published fitted specification.

Class inheritance is P(i|j)=(1-h)*p_i+h*I(i=j), with h=0,0.5,0.9 and p equal to exponential bin probabilities. Every scenario has the same unmarked timing law and exact finite-window marginal magnitude law. At h=0 the marks are iid; at positive h class history affects subsequent magnitude probabilities. Each forest is paired across scenarios, so there are 20 independent replicate units, not 60.

The preserved six-start staged comparison supplies triggering, stress and mark-rate settings. Its primary procedure fits background level/trend and the inhibition alternative; its secondary procedure supplies the background. Supplied values are not true generator parameters. The independent-mark control is outside the old candidate because the productivity law differs, and exact Mittag-Leffler generation differs from its finite-mixture representation. These differences are common across h.

Selection was frozen as direct GLR > 0.001 and selected eta > 1e-6. No Wilks reference law, calibrated rejection cutoff, power ranking or physical-mechanism interpretation was used.

## Complete outcomes

| Procedure | Magnitude dependence | Selected / planned | Unknown | Wilson 95% interval | Median direct GLR |
|---|---|---:|---:|---|---:|
| Fitted background (primary) | Independent marks (h=0) | 15/20 | 0 | 53.1% to 88.8% | 1.2058 |
| Fitted background (primary) | Moderate (h=0.5) | 17/20 | 0 | 64.0% to 94.8% | 1.0534 |
| Fitted background (primary) | Strong (h=0.9) | 18/20 | 0 | 69.9% to 97.2% | 1.0523 |
| Supplied background (secondary) | Independent marks (h=0) | 6/20 | 0 | 14.5% to 51.9% | 0.0000 |
| Supplied background (secondary) | Moderate (h=0.5) | 6/20 | 0 | 14.5% to 51.9% | 0.0000 |
| Supplied background (secondary) | Strong (h=0.9) | 4/20 | 0 | 8.1% to 41.6% | 0.0000 |

All 20 cases per scenario resolved, so resolution-conditional and all-planned frequencies coincide here. Wilson intervals describe Monte Carlo selection frequencies under this rule. They do not calibrate the test. Missing-outcome bounds are retained in the machine-readable summary and are not confidence intervals.

![Selection frequencies and Monte Carlo intervals](pilot_selection_final.png)

## Paired changes from the independent-mark control

| Procedure | h | Mean selection change (percentage points) | Exploratory 95% paired bootstrap interval | Mean direct GLR change | Exploratory 95% paired bootstrap interval |
|---|---:|---:|---|---:|---|
| Fitted background | 0.5 | +10.0 | [+0.0, +25.0] | -0.16215 | [-0.84699, +0.35490] |
| Fitted background | 0.9 | +15.0 | [+0.0, +30.0] | +0.03089 | [-1.11473, +1.02980] |
| Supplied background | 0.5 | +0.0 | [+0.0, +0.0] | -0.01031 | [-0.03939, +0.01814] |
| Supplied background | 0.9 | -10.0 | [-25.0, +0.0] | -0.04043 | [-0.07339, -0.01235] |

Each contrast uses all 20 paired forests and the predeclared 20,000-resample skeleton bootstrap, seed 2026102499. These are exploratory percentile summaries, not confirmatory coverage guarantees. A zero or zero-touching interval is not proof of equivalence.

The primary selection frequency rises, but its median GLR does not increase and its paired mean GLR changes are small relative to their uncertainty. The secondary procedure moves in the opposite direction at strong persistence. These observations do not support a simple, procedure-independent claim that stronger magnitude history yields stronger inhibitory evidence.

The post-execution class-manipulation diagnostic is recorded separately in `methods/pilot_input_diagnostics.json`: observed parent-child same-class fractions were approximately 0.6304, 0.8207 and 0.9656, versus design expectations 0.6346, 0.8173 and 0.9635. This is a descriptive implementation diagnostic, not a new primary test; no event-iid uncertainty is asserted.

## Implementation and validation

The new numerical core is standalone C++17 with a base-R interface. The preserved Python estimator uses its original CUDA/FP64 primary route and declared failure-only recovery. Core special-function support is explicitly limited to temporal shape 0.5 or 1; unsupported shapes fail. No general contour implementation was silently substituted.

Validation evidence includes:

- Original released ml.m executed under GNU Octave 11.3.0 after one private copyright-preserving dispatch-byte change; all 78 checked shape/scale/time cases passed. Maximum absolute survival/ML discrepancy was 2.33e-15. This is a kernel reference bridge, not a full author-fit reproduction.
- Independent SciPy special-function/spectral-quadrature and high-precision Decimal checks on 84 kernel cases plus the saved clock fixtures. These mathematical audits used Python; R was tested separately as an end-to-end interface.
- Fixed-seed waiting-law checks on 120,000 variates across six shape/scale combinations, with declared CDF and 18 Laplace-transform checks.
- R 4.6.1 configuration/simulation/history/scoring round trip and malformed-input rejection checks. An initial unsupported-shape test-harness mutation failed to change its input; the failed receipt and corrected targeted rerun are retained, with no implementation change.
- Unchanged comparison smoke and six excluded timing cases; original starts, eta=0 candidate, quiet exposure, positive gaps, witnesses and 1e-4 numerical gates retained.
- Full saved-artifact source/input/seed/configuration/clock/checkpoint audit, followed by independent recomputation of all 120 outcome rows, six frequency cells and four paired contrasts.

All 360 mandatory optimizer records resolved through the original primary CUDA tier; no solver recovery was needed in the pilot. Local convergence remains distinct from a global optimum certificate. No event-cap or precision-gate failure occurred. The generator rejects excessive relative parent-child wait rounding above 1e-8 without redrawing, and retains incomplete constructions as ineligible for fitting. Finite two-double arithmetic is not arbitrary-precision path recovery.

## Resources, workers and preservation

The pilot used 977.383 seconds (16.29 minutes). Mean per-catalogue comparison wall time including process startup was 16.23 seconds; maximum was 29.84 seconds. New C++ generation across all 60 invocations used 2.207 measured wall seconds. These measurements are not a cross-language performance comparison.

The 20 forests contained 15,290 distinct event times, repeated across scenarios; per-forest counts ranged from 668 to 847. The run retained a single numerical-job slot and one numerical thread per job. Prior numerical reservation wall times were conservatively charged before allocating the remaining 6,638-second pilot ceiling. The pilot finished well within it.

A read-only sampler observed 47 of 60 comparison processes. Maximum observed process-reported peak working set was 892.1 MiB. PyTorch reported at most 146.9 MiB of allocated tensor memory; this excludes driver/context/desktop memory. The recorded 16 GiB target was not an enforced OS memory limit, and unsampled host peaks remain unknown.

Three native Codex supervisor instances were reused across domain assignments. Eight DeepSeek CLI leaves completed with matching reported deepseek/deepseek-flash startup evidence, zero startup failures and zero native fallbacks. The actual-start allowance was 24, with separate raw reservation accounting. The agreed startup retry delays were 30 seconds, 1 minute and 5 minutes; none were needed. Provider cost and complete token usage remain unknown. Agent count is not a quality or speedup claim.

Three source-review leaves required factual corrections, preserved in the review reconciliation. One general numerical draft was deferred, remained uncompiled/unaccepted and is excluded from the accepted code. Native source/methods review reconciled claims against code and independent calculations; AI review is not external peer review.

Original executable baseline: `3e76a174cf4f58ce601c6c9640c4d0c11168813f`. Accepted local source commit: `ae934318c1acf914da341f09072b1e59b0b1cc9c`. Source-only patch application was checked against the original baseline. Original checkout, sealed v4 outputs, historical aggregates and historical F counts remain unchanged. No experiments were merged into those historical denominators.

## Decision and next justified work

The feasibility and bounded descriptive pilot gates pass. The machinery can generate the intended history-dependent marks and apply the selected existing comparison reproducibly. The completed observation is that this narrow procedure can show positive inhibitory fit preference under a purely excitatory designed family, including its independent-mark control.

Whether accounting for magnitude history explains previous observed evidence remains unresolved. No correctly specified richer excitatory model was fitted in this cycle; known-law scoring controls are separate from fitting. There was no fresh null calibration, size-matched power comparison, observed-catalogue evaluation or held-out forecast comparison.

The next scientific stage should first define the claim and fit the competing excitatory family under a reviewed protocol, while separating common productivity misspecification from the history contrast. Any advertised rejection test then needs fresh calibration and independent evaluation banks reproducing nuisance fitting and selection. An observed-data comparison would require matched scoring targets/exposure and separate catalogue/completeness gates. No additional campaign was launched here.

## Reproducibility artifacts

- `pilot_protocol_frozen.json` and `receipts/pilot_freeze.json`: original immutable scientific plan and hash.
- `results/pilot/plan.json`, `registry.jsonl`, per-case histories/configs/raw comparisons and `outcomes.json`: every planned identity and outcome.
- `results/pilot_analysis/summary.json` and `method_outcomes.csv`: strict saved-output analysis.
- `methods/pilot_saved_artifact_audit.json` and `result_audit/statistical_recomputation.json`: independent saved-output and arithmetic checks.
- `reports/methods_and_limits.md`: full construction, estimand and interpretation details.
- `sources/source_manifest.json` and `reproduction_gaps.json`: source pins, versions, licences and exact-reproduction gaps.
- `reports/claim_register.json` and the separate final claim-review receipt: claim scope and acceptance.
- `delivery/magnitude_history_implementation.patch`: source-only implementation patch; full bundle includes synthetic outputs and review evidence.

The exact published supplement remains unavailable, the released Japan CSV is empty and unshipped historical banks cannot be reconstructed from summaries. The fixed author preprint is separately pinned. A private original-source reference copy, article archives, raw third-party catalogue rows, worker prompts/provider logs and the unaccepted general draft are excluded from the tidy delivery. Absolute frozen paths are preserved with a relocation map; relocating or rebuilding requires a separately recorded identity, not silent weakening of historical guards.
