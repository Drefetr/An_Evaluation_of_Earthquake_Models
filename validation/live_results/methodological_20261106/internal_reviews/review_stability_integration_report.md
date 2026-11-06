# Stability and refitted-floor integration review

Verdict: PASS_INTEGRATION_REVIEW for the pinned sources and saved-data displays. No repository edit, likelihood evaluation, fit, simulation or native build was performed by this reviewer. Claim-ledger integration, artifact rebuilding and rendered-page review remain separate.

## C5 mathematical scope and numerical certificate

The new Chapter 3 paragraph correctly describes the weakness of this particular proof certificate, without claiming that the actual process mixes slowly. Independently simplifying the pinned alpha=1/2 mixture formula gives 195 modes with rates exp(.4*j), j=-97,...,97. The smallest rate is exp(-38.8) per day. The proof's first coupling condition alone requires approximately 9.8283667623941e16 days, which displays correctly as 9.8284 times 10 to the positive 16th power.

The condition for less than one-percent decay over the declared horizon is j < -36.755604265449406. Exactly the indices -97 through -37 qualify: 61 modes. Their normalized survival-kernel weight is 0.00042934294645172454, displaying correctly as 0.00042934. The manuscript explicitly limits this weight to Phi; it does not misuse it as a bound on arbitrary initialized modes or accumulated stress.

The six saved-fit certificate examples in stability.json were independently checked against the theorem's c, delta, kappa_V, D, R, epsilon, diameter and no-jump smallness formulas. They are valid sufficient choices for the displayed argument. They do not optimize the proof constants, establish an actual mixing rate or extend the result to an infinite mixture. The portable diagnostic's read-only verification command passes.

Both historical protocol copies match the supplied manifest hashes and the original local source bytes. No protected source was modified.

## Autonomous family versus fitted procedure

The direct mode solution with zero loading and zero initialization is exactly
    lambda(t)=exp(a-eta*G(t))+n*H(t).
This is the earlier raw constant-background intensity family, not a new family. The orthogonal constant-background restriction is correctly kept separate.

With constant loading and event-free equilibrium initialization, the deterministic stress contribution is rho times sum(w_j/theta_j). Absorbing it into a_eff establishes loading/intercept confounding for the exponential link. Equal non-equilibrium initial modes instead contribute X0*Phi(t)+rho*integral_0^t Phi, generally not an affine trend. These initial-state conventions do not imply stationary initialization of the point process.

The old and new protocols use the same exact catalogue hash, chronological intervals, shared finite mixture, productivity ratio and parameter boxes. The copied historical protocol explicitly specifies the conditional-within-bin training magnitude-rate estimator. The later execution uses the unconditional exponential excess estimator and has different starts, tolerances, recovery and candidate accounting. The new prose correctly separates same intensity family from different fitted procedures and does not assign their score difference solely to beta.

All three old/new saved contrast pairs and pooled contrasts reconcile independently. The earlier pooled raw constant-background gain is -13.036673684300752; the later gain is -12.945557811901608. Their negative conclusions are retained.

## Refitted-floor summary and manuscript displays

The public full result and every public case report match the exact private files audited in review_floor_results. The new summary's floor component means, background exposures, intercept ranges and medians were independently recomputed from all eighty saved cases. Its twenty procedure-summary rows equal the previously audited run summary.

Every printed fixed-floor gain, refitted-floor gain and win count in all twenty rows of 13_s04_refitted_floor.tex matches its source under the displayed rounding. All twelve numeric component cells across four regimes also match. The abstract, Chapter 13 prose and Chapter 14 consistently state the matched broad/long residual gains 5.1631 and 9.7367 nats, with 19/20 and 18/20 wins.

The table caption explicitly handles the changed meaning of a win for the retained gates: an old fixed-floor return can beat the new train-fitted floor without selecting inhibition. The manuscript preserves the old gates and saved inhibited fits, says the new exercise fits only the comparator intercept and does not describe it as joint nuisance estimation. The larger fixed-floor gains and the remaining smaller gains are both reported.

The narrow/short immigrant claim of nineteen zero-rejection histories was checked against all twenty exact saved generator receipts and the diagnostic. This supports the stated weak realized control interpretation; it does not establish general inability to detect inhibition. The total-attenuation regime is correctly distinguished. The retained parameter summary supports the qualitative boundary-concentration statement.

## Summary-validator correction during review

The first summary implementation verified each available aggregate but did not require all twenty unique summary keys, and it reported 480 checks without verifying six unique phase/model checks per case. The current saved output was already correct, but a structurally incomplete input could have been labeled passed.

The conductor corrected this before final source pinning. The revised script verifies the exact eighty case/regime/seed identities, six distinct phase/model checks, five distinct procedure/gate outcomes and all twenty distinct summary keys. It derives the check count. Reaggregation changes only the summary's script hash.

Read-only --check passes on the actual saved package. Private structural controls also confirm that a complete copied package is accepted and that missing summary rows, historical checks or procedure outcomes are rejected even after the fixture report hash is updated. These controls perform only saved-JSON operations.

## Limits

This is an independent computational review of the integration, not human peer review or a second empirical campaign. Numerical bindings and final PDFs/site output are not certified here. Exact reviewed hashes, arithmetic discrepancies and the structural-control record accompany result.json.

