# Addendum V: continuous local inhibition and consolidated implications

**Retrospective scientific review draft | 29 October 2026 (Pacific/Auckland)**

## Abstract

The registered continuous local-inhibition (LI) procedure selects exactly zero inhibition strength in all three previously inspected California test windows. Across the same 315 targets used in the preceding comparisons, LI is a numerical tie with matched Omori continuous (OC); its raw pooled positive difference is only 1.884928e-10 total nats and is not a predictive gain. The inverse-power ETAS benchmark (EP) remains better jointly in every window, mainly through conditional location. All eight fixed-seed controls are retained: LI loses to OC on both uniform-null, both smooth-null and both narrow/short-inhibition datasets, and wins on both broad/long-inhibition datasets. Two seeds per regime cannot estimate power or a false-positive rate, and the narrow/short losses prevent a claim that this procedure would reliably detect inhibition when present. At zero inhibition, range and memory are unidentified. These results concern a frozen statistical extension that attenuates only the immigrant component at recorded coordinates; they do not establish absence of physical inhibition, causal mechanisms, significance or global optimization.

## 1. Key question and review status

Does spatially local, temporary attenuation improve retrospective prediction beyond the matched OC procedure, and does the resulting procedure compete with EP? The question follows the positive continuous-location ablation in [Addendum III](Addendum_III.md) and the more qualified external, benchmark and diagnostic findings in [Addendum IV](Addendum_IV.md). It requires an actual likelihood with full exposure, a frozen fitting rule, matched references, retained negative controls and complete accounting. A term described as inhibition is not evidence that a physical stress-depletion mechanism has been identified.

The final source is the accepted local-inhibition completion, including its selected-state diagnostics, aggregate checker and preservation audits. This addendum consolidates those completed outputs. It does not repeat fitting or simulation, modify the manuscript or historical addenda, change the model after seeing the test scores, or activate a live forecast. Underlying independent computational review is distinct from external academic inspection; the latter remains pending for this package.

## 2. Recorded-event design and comparator definitions

### 2.1 Same California history, not a new sample

The observation law selects preferred California records with reported M >= 4.0, latitude 32-37 degrees, longitude -121 to -114 degrees and depth -5 to 40 km. The fixed source contains 1,272 unique events: 106 warmup parents in 1981-1985 and 1,166 evaluated records in 1986-2026. The latter comprise 851 initial training targets plus 315 subsequent test targets. Warmup is already included in 1,272; the counts must not be added a second time.

| Fold | Test window, UTC | Training targets | Test targets | Exposure days |
| --- | --- | ---: | ---: | ---: |
| F0 | 2011-2016 | 851 | 79 | 1,826 |
| F1 | 2016-2021 | 930 | 167 | 1,827 |
| F2 | 2021-2026 | 1,097 | 69 | 1,826 |
| Pooled test | 2011-2026 | Overlapping prefixes | 315 | 5,479 |

These are the same 315 targets in the California replication, benchmark, conditional diagnostic and concentration studies. Their repeated evaluation is not independent replication. The archive and earlier annual/sequence outcomes had already been inspected. Parameters and nuisance choices use training data, remain frozen in test, and histories update sequentially after each observed timestamp. Only strictly earlier eligible events enter excitation and inhibition; timestamp ties are processed as a batch, with no within-batch self- or mutual influence.

### 2.2 The references answer different questions

OC means Omori temporal triggering with the finite-domain continuous, reference-density-weighted offspring law and smooth immigrant background. EP means a separately fitted Omori ETAS adaptation whose inverse-power radial offspring density is normalized directly against projected area without OC's reference weighting. EP is an excitation model, not a Poisson model. LI-OC is the matched extension comparison. LI-EP compares complete competing procedures with different spatial excitation laws and does not isolate inhibition alone.

For completeness, the other abbreviations in the programme are FC (fixed-scale Mittag-Leffler continuous), FL (its cell-lift counterpart), OL (Omori cell-lift), MC (free common-scale Mittag-Leffler continuous) and N0 (a separately refitted smooth no-trigger procedure). Their primary contrasts are detailed in IV. A constant-Poisson candidate here is a numerical optimization floor, distinct from N0 and EP.

## 3. The continuous immigrant-inhibition model

### 3.1 Intensity and attenuation field

For time t and recorded projected location z in the fixed finite domain D, the model is

```text
lambda_LI(t,z) = exp[a + d X(t)] b_bg(z) exp[-eta G(t,z)]
                 + n H_OC(t,z)
X(t) = 2t/T0 - 1, with observed T0 = 16436 days
Observed t is days since 1981-01-01 00:00:00 UTC.

G(t,z) = sum over t_j < t of
         exp[-(t-t_j)/psi] * (1 + ||z-z_j||^2/ell^2)^(-2)
```

Here a and d govern immigrant amplitude/trend; b_bg is the inherited training-only background density; n scales excitation H_OC; eta is nonnegative inhibition strength; ell is its spatial range in kilometres; and psi is its memory in days. The observed clock uses the frozen timestamp convention and strict earlier-integer-timestamp parent rule, including tied batches. Synthetic controls have their own day-zero origin and normalization, specified in section 6.1. The stress mark multiplier is fixed to one: every eligible earlier recorded event contributes to G without magnitude weighting. No latent immigrant/offspring classification is required. Inhibition acts only on the immigrant term. It does not suppress H_OC, and it is not spatially renormalized. It therefore changes both local density and total immigrant rate. Renormalizing the inhibited density would define a different model.

More explicitly, the inherited excitation is a sum over all eligible strictly earlier parents:

```text
H_OC(t,z) = sum_j kappa_j k_O(t-t_j) s_sigma(z | z_j)
k_O(u) = (p-1) c^(p-1) / (u+c)^p, for u > 0
s_sigma(z | z_j) = b_ref(z) (1 + ||z-z_j||^2/sigma^2)^(-2) / Z_j
Z_j = integral over D of b_ref(v) (1 + ||v-z_j||^2/sigma^2)^(-2) dv
```

Here kappa_j is the shared training-calibrated magnitude-productivity weight, with fixed exponent r = 0.7; b_ref is the frozen training-derived reference geography. The background b_bg integrates to one on D. The temporal kernel integrates to one over all positive lags and each s_sigma integrates to one on D; exposures use the actual finite time window. The training-only smooth background, parent eligibility and inherited excitation nuisance choices follow the matched OC procedure. LI introduces no new background bandwidth or excitation spatial-scale search. The stress radial factor in G itself is not a normalized spatial probability density; it is an attenuation field inside the exponential.

At eta = 0, exp[-eta G] equals one everywhere and LI exactly nests OC when shared coordinates agree. All ell and psi choices then give the same law. Canonical ell = 30 km and psi = 7 days are display conventions at that boundary, not recovered scales. Even a positive procedure score difference at eta = 0 could arise from refitting shared coordinates through another optimization path; it would not establish active attenuation. The separate approved selected-state diagnostics are therefore essential to the conclusion below.

### 3.2 Frozen fitting and selection contract

The fitted coordinates are (a, d, n, log c, p, eta, log ell, log psi), where c and p parameterize the normalized Omori kernel. The physical bounds are fixed.

| Coordinate | Bound | Coordinate | Bound |
| --- | --- | --- | --- |
| a | [-12, 0] | d | [-2, 2] |
| n | [0, 0.98] | c | [0.0001, 20] days |
| p | [1.01, 2.5] | eta | [0, 4] |
| ell | [5, 150] km | psi | [1/24, 365] days |

Each main arm has eight prescribed starts. For LI fits only, shared a,d,n start from the accepted matched OC state. LI start 0 retains OC's c,p and eta = 0; the other LI starts use the fixed c,p,eta,ell,psi schedule below. Synthetic OC control fits use a separate frozen initialization rule, not their own subsequently accepted fit: a0 = clip(log(0.6 max(Ntrain,1)/365), -11.5, -0.1), d0 = 0.2 and n0 = 0.35, with eight prescribed c,p rows in synthetic_common/OC_start_fill. The [readable protocol subset](../research_results/addenda_iv_v/curated_protocols/scientific_protocol_subset_v2.json) gives both start schemes, floors, bounds and tolerances in full.

L-BFGS-B has maxiter 200, maxfun 20,000, maxls 200, ftol 1e-10 and gtol 2e-6. Bounded Powell is allowed only after failure of the declared first-method acceptance rule, from the same original start, with maxiter 400, maxfev 5,000, xtol 1e-6 and ftol 1e-10. These limits describe a bounded search, not a global optimization proof.

| LI start: c (days), p | eta | ell (km) | psi (days) |
| --- | ---: | ---: | ---: |
| 0: accepted OC c,p | 0 | 30 | 7 |
| 1: 0.0001, 1.1 | 0.1 | 5 | 1/24 |
| 2: 0.001, 1.3 | 0.3 | 15 | 0.25 |
| 3: 0.01, 1.1 | 0.7 | 50 | 7 |
| 4: 0.1, 1.3 | 1.5 | 150 | 30 |
| 5: 1, 1.7 | 3 | 5 | 365 |
| 6: 20, 2.5 | 4 | 150 | 1/24 |
| 7: 0.1, 1.01 | 0.5 | 30 | 365 |

Selection minimizes accepted training joint negative log likelihood. Exact ties prefer the OC floor, then the Poisson floor, then start and method ordinals. Held-out score does not select a candidate, method, computational epoch or seed. Candidates within 0.0004 training NLL units of the selected state receive the declared held-out spread check, requiring spread strictly below 0.01 nats per target. This is an admission/sensitivity diagnostic over the stored near-optimal set; it is neither an uncertainty interval nor permission to select the best test forecast.

The [readable protocol subset](../research_results/addenda_iv_v/curated_protocols/scientific_protocol_subset_v2.json) and [exact data-free case matrix copy](../research_results/addenda_iv_v/curated_protocols/LI_case_matrix_v1.json) expose the full start schedules, law, observation scope and selection rule; [source pins](../research_results/addenda_iv_v/source_pins_v2.json) bind their identities. The case matrix retains historical execution-status labels; final accepted completion receipts establish the results status. An earlier methods proposal is contextual, and the structured frozen case matrix is authoritative where it differs.

### 3.3 Proper scores and exposure

Write P for summed event log point intensity, Q for summed event log regional intensity, E for positive full-domain integrated intensity, C = -E for its signed score contribution and M for the common magnitude-mark score. Then

```text
Timing = Q + C = Q - E
Conditional location = P - Q
Joint = P + C + M = P - E + M
      = Timing + Conditional location + M
For LI minus reference R:
  Point-event difference = P_LI - P_R
  Signed exposure contribution = C_LI - C_R = E_R - E_LI
  Joint difference = Point-event difference + Signed exposure contribution
                     + Mark difference
```

All quiet-period and full-domain exposure is retained. Lower exposure can offset a worse event-intensity term; an event-only gain is insufficient. Within each arm, Q uses that arm's spatially integrated ground intensity under the fixed observed history, and all components use its same fitted state. Independently fitted arms can have different parameters. The shared conditional mark law is scored once and cancels in contrasts. Pooled scores sum all three window totals and divide by 315. These are nats of realised predictive log score, not percent accuracy, correlation, a physical effect size or evidence of calibration.

The [source-field dictionary](../research_results/addenda_iv_v/provenance/score_field_semantics_v2.json) distinguishes these narrative symbols from legacy aggregate keys. In particular, LI's raw pooled E field means the point-event logsum difference, not positive exposure; its raw C is the signed exposure contribution. Sequence timing_compensator instead stores positive exposure difference and enters the score negatively. Source keys and scalars remain unchanged.

## 4. Observed result: no selected inhibition and a numerical tie

All three selected LI fits have eta **exactly zero**. The procedure selects no active attenuation term in these observed windows. Its joint contrasts against OC are numerical ties under the prespecified inclusive +/-0.0002-total-nat descriptive threshold.

| Window | Targets | LI-OC joint nats/target | Selected eta | Interpretation |
| --- | ---: | ---: | ---: | --- |
| F0 | 79 | 0 | 0 | Numerical tie |
| F1 | 167 | +1.128699e-12 | 0 | Numerical tie |
| F2 | 69 | 0 | 0 | Numerical tie |
| Pooled | 315 | +5.983898e-13 | 0 in 3/3 | Numerical tie |

The raw pooled difference is +1.88492776942439e-10 total nats. Its tiny positive floating-point sign is retained for arithmetic traceability and is not a forecast improvement. The tie threshold concerns numerical comparison, not statistical significance. Exact model nesting and finite arithmetic are separate issues: the selected law has no inhibition, while independently evaluated saved score arithmetic may differ at roundoff scale.

The zero-strength boundary leaves ell and psi unidentified. Neither their canonical values nor bounds identify a physical inhibition footprint or duration. This result supports the narrower statement that the registered fitting procedure selected no active immigrant attenuation on this inspected recorded-coordinate history. It supplies no proof that earthquakes lack inhibition, no universal detection limit and no evidence of physical absence.

## 5. EP remains the stronger joint forecast

LI scores below EP in every observed window. Its pooled timing edge is tiny and mixed across windows; its larger conditional-location deficit accounts for the joint loss. All differences below are LI minus EP in nats per target.

| Window (targets) | Timing | Conditional location | Joint | Mark difference |
| --- | ---: | ---: | ---: | ---: |
| F0 (79) | +0.006244055 | -0.085849360 | -0.079605305 | 0 |
| F1 (167) | -0.001101051 | -0.188973874 | -0.190074925 | 0 |
| F2 (69) | +0.000389054 | -0.189082869 | -0.188693815 | 0 |
| Pooled (315) | +0.001067459 | -0.163134776 | -0.162067317 | 0 |

The exact source-reported pooled LI-EP joint difference is -51.0512047628713 total nats, or -0.162067316707528 per target. Its timing and conditional-location totals are +0.336249525419333 and -51.3874542882905. These are predictive components, not causal shares or a decomposition of physical immigrant versus offspring generation.

The separately archived OC-EP benchmark in IV differs slightly at floating-point scale from this replay. Each is reported under its own accepted source identity; substituting one for the other would obscure provenance. Neither EP's better relative score nor LI's exact nesting supplies a probability-calibration result. The completed conditional calibration concerned original OC only and found material discrepancies.

## 6. Every fixed-seed control, including the failures

### 6.1 Generating contract

Eight datasets, two seeds per regime, were fixed in advance. The null regimes have eta = 0. The narrow/short positive regime has eta = 0.5, ell = 5 km and psi = 1/24 day. The broad/long regime has eta = 2, ell = 50 km and psi = 30 days. At the null, ell/psi do not affect the law. The domain is 100 by 100 km; synthetic t is days since simulated history begins at day zero, with X(t) = 2t/760 - 1. Warmup ends at day 30, training at day 395 and test at day 760. The observed 16,436-day normalization is not used for these controls. Known nuisance/background inputs are fixed equally for paired OC/LI fits. Chronological thinning uses accepted-event ancestry and fixed PCG64DXSM streams, with original caps/failures attached to their seeds. No failed or inconvenient seed is redrawn.

The controls test the registered fitting procedure on these laws. They do not mimic every catalogue feature, location-error process or earthquake mechanism. The public control table is complete.

| Generating regime | Seed | Test targets | LI-OC joint nats | Nats/target |
| --- | ---: | ---: | ---: | ---: |
| Uniform null | 410001 | 116 | -148.647608 | -1.281445 |
| Uniform null | 410002 | 138 | -4.930159 | -0.035726 |
| Smooth null | 410101 | 128 | -4.489917 | -0.035077 |
| Smooth null | 410102 | 120 | -7.638775 | -0.063656 |
| Narrow/short inhibition | 410201 | 107 | -1.297391 | -0.012125 |
| Narrow/short inhibition | 410202 | 102 | -25.357970 | -0.248608 |
| Broad/long inhibition | 410301 | 23 | +2.242679 | +0.097508 |
| Broad/long inhibition | 410302 | 27 | +6.771012 | +0.250778 |

LI loses on six examples, including both positive narrow/short laws, and wins on the two broad/long examples. The first uniform-null loss is large and remains displayed. The broad/long examples contain only 23 and 27 test targets. Averaging these rows into a single success rate would discard the intentionally different laws and denominators.

![Figure 3. All eight prescribed LI-minus-OC fixed controls.](addenda_iv_v/figures/v2/li_fixed_controls.png)

*Figure 3. The full linear scale retains the large uniform-null loss. Every seed and test count remains labelled. Positive means LI scored better; the rows are fixed examples, not estimated success probabilities.*

### 6.2 What the controls do and do not show

Both broad/long wins show that the registered procedure can improve held-out score on those two fixed examples. Both narrow/short losses show why the observed zero-strength result cannot be read as a reliable absence test. A true positive term in the generating law need not improve this finite-sample fitted procedure's held-out score. Conversely, an active fitted term or better score would not identify a physical mechanism.

Two seeds per regime cannot estimate false-positive rate, power, parameter coverage or general recovery probability. Six losses do not prove absence of inhibition in the generating laws, and two wins do not establish reliable detection. Narrow/short failure does not locate a physical resolution threshold. The recorded-coordinate law has no admitted empirical location-error distribution; the engineering lower bound ell = 5 km is a model/search constraint, not a measurement-accuracy assertion.

## 7. Identifiability and consolidated scientific implications

At eta = 0 the likelihood does not depend on ell or psi. Thus zero-strength selection does not estimate a zero range or duration: it removes those coordinates from the law. The null also lies at the boundary of a constrained parameter space. Exact nesting alone justifies neither ordinary Wilks inference nor a universal half-chi-square reference. No significance, p-value or event-iid confidence interval is reported.

The finite multistart procedure is part of the estimand. Negative held-out differences are possible even for nested model families because training-defined selection and finite samples do not guarantee held-out superiority. The complete retained candidates and near-optimal checks reduce particular numerical concerns; they do not certify a global optimum or prove that no positive-inhibition state could ever perform better. The conclusion must stay about the registered procedure and this history.

Together with IV, the programme supports a qualified predictive conclusion. Continuous offspring geography improves location relative to the declared cell-lift procedure in the examined regional comparisons. Omori's timing advantage is conditional and reverses in Japan. OC and its zero-inhibition LI extension remain below EP jointly in California; EP also wins in Japan. OC's conditional count/time/space discrepancies remain unresolved, and EP has no completed calibration study here. California score gains are heterogeneous and concentrated in a single eligible scored sequence period while retaining positive contextual totals over the complete complement.

The new LI result adds a negative extension finding: no selected active inhibition and no predictive gain over matched OC in the observed windows. It does not overturn the earlier location ablation, reverse the serious-benchmark deficit, resolve calibration, recover physical labels or prove absence of a physical mechanism. The eight controls reinforce the need to distinguish procedural sensitivity from a physical absence claim.

All archives had been inspected and revised. Chronological test windows are related through overlapping training history and earthquake dependence, and the same California targets recur across studies. No pristine confirmation, broad independent sequence replication or causal conclusion follows. The prospective New Zealand programme remains readiness only; future capture, issuance and scoring are separate from these historical results. This addendum provides no issued-forecast outcomes, scheduling activation or publication decision.

## Appendix A. Numerical completion is a separate validation result

The completed roster contains 19 fit procedures: paired OC/LI fits for eight synthetic datasets plus three observed LI fits. It accounts for 152 prescribed starts and 30 floors, giving 182 final slots. Seventeen historical CPU fits were preserved; the two remaining observed fits completed with the admitted GPU provider. Nineteen score jobs replayed all candidates and finite feasible solver returns. These are computation denominators, not 19 empirical replications.

The 42 validation jobs comprise 38 procedure-phase audits, three paired sealed-reference jobs covering six comparator states, and a separate censored-attempt preservation audit. The earlier interrupted LI pool remains excluded from the final eligible pool and preserved separately; its partial success did not select the final computational epoch. Recovery changed execution machinery within the frozen scientific law and roster. No observed event was removed and no synthetic seed was replaced.

All 19 training-defined near-optimal spreads are below 0.01 nats per target; the largest is 0.00053761640079144. The exact aggregate checker passed 369 checks, with independent saved-output review and arithmetic reconstruction. Gradient statuses are fully accounted for. These checks support custody and numerical consistency under tested states, not universal gradient representability, scientific replication, physical scale recovery or global optimization.

## Appendix B. Evidence and reading guide

The [accepted scientific report](../research_results/addenda_iv_v/curated_reports/LI-OBSERVED.md) is the source for observed results, all controls and completion counts. The [computational provenance report](../research_results/addenda_iv_v/curated_reports/LI-PROVENANCE.md) preserves execution/recovery boundaries. The [current evidence index](../research_results/addenda_iv_v/current_evidence.json) routes the unchanged aggregate, source pins, complete claim bindings and field semantics. The [evidence catalogue](../research_results/addenda_iv_v/current_evidence.json), [readable protocol subset](../research_results/addenda_iv_v/curated_protocols/scientific_protocol_subset_v2.json) and [review guide](Addenda_IV_V_review_guide.md) supply the exact source identities, full scientific contract and inspection order.

Claim families LI-OBSERVED, LI-CONTROLS and LI-VALIDATION separate the scientific result, fixed examples and numerical evidence. CA-BENCHMARK and CA-CALIBRATION supply the earlier comparator/calibration context; OPS-READINESS supplies the separate future-operations boundary. Current figure arithmetic is reproduced from accepted scalars; underlying fits, simulations and audits remain source-reported. Raw records, event caches and fitted vectors remain outside the review bundle. External scientific inspection is pending.
