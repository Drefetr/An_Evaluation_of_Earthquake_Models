# Observed fixed-backbone LI/LI+ held-out replay

All 51 required original state, fit, journal, preparation and quadrature files
were recovered byte-for-byte against the historical terminal report hashes.
The package retains the actual positive total-intensity parameter vectors and
all original training arrays. The executable roster evaluates the six held-out
phases: the original orders 16 and 32 for each California fold. It preserves the
recorded training winners and complexity-gate choices; it does not refit or
reselect them. The published comparison uses order 32.

For example, the total-intensity floor in the third fold is original state
index 8. Floor locations are identified from the exact saved vectors rather
than assumed to be index zero. Both the original state and selected-fit hashes
are retained in every projected state record.

`observed_replay.py` evaluates the same finite sums using FP64 CPU BLAS. At each
space/time node, the triggering field contracts the original normalized spatial
parent coefficients with the strict-past Omori weights. The stress field
contracts the original radial weights, including the declared magnitude factor,
with strict-past exponential decay. The unchanged quadrature weights then sum
the attenuated intensity. Event log intensities use stable log addition. At
zero inhibition strength, attenuation is exactly one, so the OC score is
evaluated directly. No nodes, weights, parameters, cutoffs or laws are changed.
The original CPU reference and its header are retained for source comparison;
this BLAS implementation is a distinct computational implementation, not a
claim of bit-identical accumulation or original optimizer execution.

The predeclared comparison allows the original observed quadrature/selection
tolerance of `1e-4` nats, with `1e-6` for the exact floor. This is separate from
manuscript rounding. Prepared baseline P, E, M, joint score and target count must
also agree with a fresh passed primary OC replay at the same cache, selected
state and original evaluator identities. Thus the saved baseline exposure in
the original preparation is independently checked against a new computation.
No timing/location split or gradient is manufactured by this joint-score
interface.

After independent source review and numerical-resource admission:

```text
python -B reproduction/score_replay/observed_replay.py --registry reproduction/score_replay/observed_fixedbackbone/registry.json --fresh-scores FRESH_OC_SCORES.json --admission ADMISSION.json --mode pilot --rows ROW_IDS.json --output NEW_PILOT
```

The fresh-score manifest uses the same `rows` mapping as the California block
route: each primary OC test row maps to `result_path` and its `sha256`. The
admission pins this manifest, source modules, input manifest, registry, ordered
roster, thread count and scratch budget. The pilot is the smallest original
positive-total held-out contraction workload, including the exact floor. It
must complete before a full resource admission. The original larger training
grids are supplied for custody and possible separately bounded work, and are
never silently included in this held-out execution.

Mandatory invented scalar controls check all three laws, zero/positive strength,
strict-past ties and split/full tile agreement. Every completed component is
written immediately and hash-pinned, including components retained before a
later failure. The launch records Python, NumPy and actual BLAS binary hashes
and thread limits; the external supervisor owns wall time, memory and cleanup.
All real-history scores remain pending until the separately admitted replay and
output audit finish.
