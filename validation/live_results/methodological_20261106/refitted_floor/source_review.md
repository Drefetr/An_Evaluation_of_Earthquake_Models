# Independent source review: S04B refitted floor

Verdict: PASS for the reviewed protocol and source, conditional on the conductor running the deterministic controls and enforcing the declared numerical lease before actual scoring. This review did not run fixtures, native builds, original-history scores or fits. It is computational source review, not human peer review or an empirical result.

The author declared the implementation frozen, including run.py SHA-256 a91c6e9d8337e5b5856bd21e13e73da33e3f538718117f81bd53e91be8d4207a. The reviewer recomputed this and all five reviewed file identities. The frozen protocol is a1794b96655812cc83291f56f6f3fe58a51baca98d96aa2de089ebcc8c9d7a29. All ten referenced source pins match the checkout. Both Python sources parse; the test file contains nineteen deterministic test methods. Parsing is not execution.

## Mathematical and scientific checks

- The rate parameter is b=exp(a), with the fixed inherited box a in [-12,0]. The objective is sum log(b*u+v)-b*A-H+M. Its derivative is decreasing, strictly so with a positive target count and positive u. With zero targets it is decreasing linear, and the lower endpoint is the unique bounded optimum. The endpoint signs, bracketed root, relative derivative check and training non-worsening check implement the frozen concave optimization problem.
- The background integral uses the correct midpoint/sinh formula and continuous small-trend expansion. The fixed spatial background is normalized: the declared reference probabilities sum to one, the smooth component uses normalized radial kernels and fixed weights, and no KDE is refitted from test events. Trigger exposure is the original normalized spatial Omori exposure.
- Score signs are correct: E is nonnegative exposure, C=-E, joint=P-E+M=P+C+M. Reconstruction from saved NLL and point values uses E=NLL+P+M, not a subtraction of signed C. Refitted-minus-historical changes satisfy deltaJoint=deltaP+deltaC+deltaM and deltaC=-deltaE.
- The mark term is fixed and cancels exactly in the new floor contrast. The timing/location decomposition agrees with the archived spatial.evaluate formula, which is called as a control at both historical and selected intercepts.
- The fitting loop creates and completes the scalar training fit before constructing/scoring test features. Hash/count inspection reads complete histories beforehand but does not evaluate a test objective for selection. Later test events enter history only after their occurrence; this is the declared sequential conditional score.
- canonical_arrays retains all earlier prehistory parents and only parents with time below the phase end. spatial.features uses lag>0, excluding equal-time and future events from event intensities. The exposure intervals and target masks implement the same left-closed/right-open phases as the protocol.
- The old inhibited fits are never rerun, and the runner does not call the archived inhibitory quadrature, generator, fit or Integrated routines. It loads the existing radial rectangle integrator only for spatial normalization.
- Every case checks both phases against all three original model floors, giving six historical comparisons. The new formula is independently compared at the component level with the archived spatial.evaluate function. These controls assess the new scalar procedure, not the historical optimizers' global optimality.
- Saved training selection is validated from the archived candidate records. The gate uses the original training gain and original threshold. The original selected state index and off-floor indicator must match, and no gate is recomputed against the refitted floor.
- The new procedure contrast is savedProcedureTestJoint minus refittedFloorTestJoint. It is checked against oldGain minus floorScoreChange. This preserves the historical score numerator and isolates the comparator sensitivity.

## Custody, roster and execution boundaries

The runner pins the exact protocol hash, checks all listed source files including the input manifest, then hashes the required history/state/fit/expected files against the frozen manifest. Decompressed row hashes and phase counts are checked. The radial library hash/name must match its build receipt, and the receipt's radial.cpp identity must equal the pinned source. The radial source has no local custom-header dependency requiring a further build-source pin.

The pilot is the first fixed seed in each regime. Full execution requires the same source/input/protocol/native identity, four passed reports whose hashes match, exact seed/case/regime identities and six historical checks per reused report. The four pilot cases are copied unchanged and removed from the remaining roster. Consequently successful full execution contains eighty distinct scalar fits, not eighty plus four.

The initial review questioned the time-projection fields. The author corrected them before freezing the reviewed hash: remaining projection is three times the worst pilot time/workload ratio times remaining workload, plus measured pilot setup time. Total projection adds actual pilot wall time once. The full deadline subtracts pilot wall time from the unchanged total cap. This implements the protocol's conservative admission rule.

The program enforces elapsed-time checks at case/phase boundaries and samples its own RSS. It does not implement a hard OS memory cap, process-tree kill or authenticated lease. The README and output fields say so. Actual process-tree memory enforcement, compiler accounting, conductor deadline and quiescence remain required external execution-supervisor responsibilities.

Fresh output directories are required. Per-case and run records start with passed=false. Caught errors retain the partial case, error and failed-case hash, and return nonzero; no replacement case or completed aggregate is produced. A forced external termination may retain the last checkpoint rather than execute the Python exception handler, which is why the supervisor must record its own terminal state. Full aggregate construction requires the complete roster with passed case records.

Per-case identity paths and decompressed row hashes are linked to the top-level run's full input hash map and source/native identity. This is a package-level custody chain; a case file alone is not a standalone attestation of all source bytes. Python/NumPy/SciPy versions are recorded but are not an independently frozen dependency lock.

## Fixtures reviewed, not executed

The nineteen tests cover closed-form no-trigger/interior cases; both endpoint cases and zero targets; signs and decomposition; derivative monotonicity; invalid features and bounds; the zero-trend integral; strict equal-time exclusion; archived formula agreement; missing/duplicate/changed roster cases; path escapes; changed protocol and wrong native receipt; failed admission, existing outputs and incomplete aggregation.

The conductor must run these controls under the reserved numerical task and then inspect actual pilot controls/resource records before authorizing the remainder. This source review alone does not assert any pilot or full campaign result.

