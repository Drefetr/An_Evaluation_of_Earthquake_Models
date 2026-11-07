# California calendar and causal sequence score replay

This route evaluates the original interval compensator kernels at unchanged
selected states. It combines those newly calculated exposures with **freshly
replayed** event intensities from the California cached and EP benchmark routes.
Original archived score vectors are never numerical operands. The original
reducers and integer-microsecond causal partition definitions are bundled without
source changes, alongside exact reference projections and original SHA identities.

The registry has 39 state/partition jobs: 24 annual states and 15 sequence states.
The complete output contains 120 annual absolute rows, 90 annual contrasts,
80 sequence absolute rows (including 15 pooled rows), and 64 sequence contrasts.
Calendar 2019 and the retrospective causal-origin S06 year are separate analyses;
the latter belongs to `../s06_ca/`, not this partition route.

Build and replay, after source and resource review:

```text
python -B reproduction/score_replay/california_blocks_replay.py --build --output NEW_BUILD
python -B reproduction/score_replay/california_blocks_replay.py --libraries NEW_BUILD/libraries.json --fresh-scores FRESH_SCORES.json --admission ADMISSION.json --mode pilot --rows ROW_IDS.json --output NEW_PILOT
```

`FRESH_SCORES.json` contains a `rows` mapping from each required cached row ID to
`{"result_path": "path/to/actual/row/result.json", "sha256": "..."}`. Each report
must have passed at exactly the registry's state, cache and evaluator identities;
its retained native event arrays must also hash-match. Admission pins this input
manifest, the registry, source modules, original input manifest, libraries, build
receipts, ordered row roster and numeric thread cap. Omit `--rows` for the complete
registry only after measured pilot admission. `not_run` and partial runs are not
completion. Output directories must be new.

The original full-precision components, integer memberships and count identities
are compared after evaluation. Absolute numerical tolerance is one micro-nat,
below the original reconciliation tolerance; integer counts and partition hashes
must match exactly. Every output row also exposes P, positive E, signed C, M,
timing, location and joint score. Passing this cached-feature route does not
reproduce the original parameter search or regenerate spatial features.
