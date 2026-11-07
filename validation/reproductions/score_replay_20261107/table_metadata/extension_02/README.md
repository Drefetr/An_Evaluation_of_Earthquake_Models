This checkpoint covers all 119 table identity fields. It preserves the preceding 97 entries and their evidence links exactly, adding seven original-LI seed labels and fifteen observed-study fold labels from independently accepted selected-state replay records.

`independent_review.json` checks the new 22 entries and preservation of the preceding 97. `result.json` retains its original pre-review status; the separate review records the subsequent acceptance. These are metadata checks, not additional likelihood evaluations or complete Task 2 table acceptance.

The unchanged portable producer remains in `../extension_01/producer.py`. Run it from the repository root into a fresh external directory:

```text
python -B validation/reproductions/score_replay_20261107/table_metadata/extension_01/producer.py --repository . --output FRESH_EXTERNAL_DIRECTORY --public-folder validation/reproductions/score_replay_20261107/table_metadata/extension_02
```

The producer rederives 63 fields that were unresolved at its original 56-field baseline. This checkpoint retains its complete evidence, but appends only the 22 newly resolved entries to the preceding 97-entry crosswalk. `predecessor_comparison.json` verifies that the prior entries and their source values remain unchanged. `raw_producer_result.json` retains the unmerged producer output identity. Later changes to the accepted-execution index produce a new evidence snapshot rather than the same bytes.
