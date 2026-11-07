# Saved productivity-profile score replay

The package retains all 42 original fixed-productivity grid optima, their six
byte-exact profile records and the original train/test feature caches. The 84
registry rows evaluate both intervals at those saved vectors; they do not repeat
the profile optimization or select new parameters. The original Python and C++
objective sources are unchanged and use the existing cached replay entry points.

After source review, build admission and the measured pilot gate:

```text
python -B reproduction/score_replay/build.py --registry reproduction/score_replay/productivity_profiles/cached_registry.json --output NEW_BUILD
python -B reproduction/score_replay/replay.py --registry reproduction/score_replay/productivity_profiles/cached_registry.json --libraries NEW_BUILD/libraries.json --admission ADMISSION.json --mode pilot --rows ROW_IDS.json --output NEW_PILOT
```

The frozen pilot covers the largest train/test cache in both original free-r
models, with deterministic endpoint tie-breaks. All other rows require the
separate completion admission. Inputs, selected states, expected scalar
references, source identities and the original support rule are pinned in the
registry and input manifest. The predeclared numerical comparison uses an
absolute micro-nat allowance, independently of display rounding.

For Appendix table `tab:a2-profile-support`, the complete seven-point training
grid is necessary to validate each sampled-support list, including an empty
list. The original rule includes a point when its training NLL is at most two
nats above the final selected training NLL. `profile_groups` maps each grid row
to that final selected row in `../cached_supplement/`; the selected test row is
in the original 510-row registry. Both operands must come from passed replay
outputs before a new support result is claimed. This is a descriptive sampled
profile, with no confidence-interval or coverage interpretation. No historical
score replay was performed while assembling this input package.
