# Historical score-table coverage

All 103 declared historical containers have their required evidence: 78 reconcile mapped replay fields, 12 retain separately scoped prior replay evidence, and 13 require no additional likelihood execution under the frozen plan. All 119 identity/count metadata fields are checked. No required numeric fields are unresolved, failed or unreplayable.

The four exact-display rounding differences remain in `coverage.json` and `result.json`; they pass the unchanged declared functional tolerances and are not relabelled as exact printed equality. Individual field-level `not_run` statuses in the prior-scope and no-new-execution categories do not claim fresh computation. These are frozen-plan execution classifications, not assertions that those tables contain no likelihood values: `ch09_audit:table:14` includes Training NLL and all its 36 numeric fields actually reconcile. The separate new joint-fit tables are outside this historical roster.

`coverage_inputs.json` pins all inputs. Its local delta paths use the manifest directory; other evidence uses repository-relative paths. The same manifest was validated after relocation and produced byte-identical coverage. All previous incomplete checkpoints and failed source/operational attempts remain retained elsewhere. No likelihood, fit, generator or native objective ran during this assembly. Independent review is required before this staged package is promoted.

From the repository root, choose a fresh output filename:

```sh
python -B reproduction/score_replay/coverage_report.py --repository . --evidence validation/reproductions/score_replay_20261107/final_coverage/coverage_inputs.json --output fresh_coverage.json
```

The arithmetic producers are `reconcile_cached_tables.py` and `reconcile_regional_tables.py` in the same source directory; exact source and evidence hashes are retained in the input manifest and result. Final manuscript provenance edits require the separate source-custody refresh described by the publication workflow; this package does not assert coverage of future source edits.
