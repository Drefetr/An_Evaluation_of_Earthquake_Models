# Original unit-mark narrow/short control audit

`summary.json` is the exact deterministic full-run summary. `pilot/` contains the first two paired reconstructions; `full/` reuses those exact four simulation outputs and adds eighteen further pairs. The complete roster therefore uses forty generator calls, not forty fitted model comparisons. No likelihood evaluation or optimizer campaign ran.

The [portable reconstruction package](../../../reproduction/synthetic/s2_unitmark/README.md) pins the original inputs and current generator. `input_recovery.json` distinguishes the original histories from missing original full-bank counters. `source_review.json` records the independent review before execution; `output_review.json` audits the completed evidence.

All twenty positive-strength histories have no rejected proposal and exactly equal their same-seed uninhibited counterpart within the current runtime. Historical file comparison has a separately declared floating-point tolerance; it is not falsely reported as byte equality across platforms. This pathwise result does not equate the generating probability laws.
