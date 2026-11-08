# Saved-output numerical-amendment audit

This separate checker audits saved outputs of `joint_exposure_refinement_v1`.
It imports only standard-library code and hash-pinned independent saved-output
auditors. It never imports the producer, evaluates a likelihood, loads a native
library, fits a model, or changes the original full-success publication gate.

Run it against one completed child and its exact predecessor:

```text
python -B -m experiments.s04b_exposure_refinement_audit.check \
  --repo REPOSITORY --current HOST/children/CHILD \
  --prior PRIOR_INDEX --prior-review PRIOR_REVIEW \
  --config SHARED_CONFIG --commit REVIEWED_COMMIT --output FRESH_REVIEW \
  --checker-source-review SOURCE_REVIEW \
  --checker-source-review-sha256 SOURCE_REVIEW_SHA256
```

The host bounds this metadata/arithmetic check to its reviewed checker allowance.
The output must be fresh. Exit zero means the saved disposition audit passed;
the receipt remains an automated check requiring a subsequent live independent
host review. It never claims scientific completion or original full success.

The checker verifies the immutable archive and exact base projection, all saved
compatible complete cases, the permanent optimizer-cap unknown, and partial-case
reuse without presenting reused work as new physical calls. Each new refinement
must have a paired original negative-exposure exception and same-point fine
value/gradient operands satisfying the original numerical tolerances. Solver
recipes, original fresh/selected/test checks, explicit unknowns, logical versus
physical work counts, source/review custody and cumulative resource limits remain
separate checks. Original independent arithmetic is reused without substituting
an original source identity for the explicitly amended computation.

`tests/test_joint_exposure_refinement_audit.py` uses invented saved artifacts and
an explicitly invented trust root. Its complete/unknown CLI paths run the real
checker, including Git and archive custody; no validation function is mocked.
Repinned corruption controls exercise semantics beyond digest mismatch. The two
original fixture helpers are test dependencies, not new scientific calculations.
