# Initial mark-history selected-state replay

This route recovers the original 60 early mark-history cases: 20 paired timed
forests at each of three mark-dependence settings. Each case retains the exact
CSV, selected comparison, terminal case record and generator log. The archive
also contains the frozen protocol, plan, terminal registry and original summary.
`input_manifest.json` pins every member and the unchanged source copies.

This is separate from the later S02 experiment and from the magnitude-prediction
engineering supplement. It evaluates 240 selected ground negative
log-likelihoods and 120 direct likelihood-ratio contrasts across 120 method
pairs. It performs no fit, optimizer restart, event generation or witness search.
Neither successful input verification nor passing constructed controls claims
that these historical likelihoods have been executed.

The original candidate branching scalar is `0.5017751599706763`, and the fixed
productivity ratio is `0.7` in both methods. Those values must not be replaced by
the later S02 values. `known_known` preserves the supplied background;
`background_estimated` evaluates its recovered fitted background. Both retain
their original selected inhibition strength and finite-mixture laws.

## Execution

The platform C++17 compiler builds the previously reviewed Q01 source and the
separate component wrapper from the S02 replay package. No MSVC or CUDA is needed
on a Linux host with `g++` installed. This route does not import PyTorch or claim
GPU execution.

```text
python -B reproduction/score_replay/initial_mark_replay.py build --output /external/native
python -B reproduction/score_replay/initial_mark_replay.py run --mode pilot --admission /external/admission.json --library /external/native/components.so --build-receipt /external/native/build_receipt.json --output /external/pilot
python -B reproduction/score_replay/initial_mark_replay.py run --mode completion --pilot /external/pilot --admission /external/completion-admission.json --library /external/native/components.so --build-receipt /external/native/build_receipt.json --output /external/completion
```

The conductor supplies a source-reviewed admission and numerical lease and runs
the command under process-tree supervision. Outputs must be outside the
checkout. The six-case pilot was chosen from input counts before any new score:
all three settings for the first forest and the forest with the most events.
Completion evaluates the remaining 54 cases and reuses the reviewed six-case
pilot exactly; it does not repeat those likelihood evaluations.

Every selected NLL is compared with both the saved CUDA16 result and its saved
original CPU32 check. Every direct GLR is compared with both corresponding
historical contrasts. The original absolute tolerance is `1e-4`; operational
selection decisions must match exactly. A pilot-only order64 check measures
quadrature sensitivity. Common exponential-mark scores are reported separately
from the historical ground NLL. `P + C + M = joint` and `C = -E` are checked.

The complete union reconstructs `tab:pilot-frequency` and `tab:pilot-paired` in
Chapter 9, including the original seeded paired bootstrap arithmetic. Continuous
table discrepancies and display-rounding discrepancies are distinct outputs.
Unknown, failed and unstarted cases remain visible and fail full acceptance.
This replay does not establish nominal test size, parameter recovery,
prospective validity or physical inhibition.

See [SEMANTICS.md](SEMANTICS.md) for the source crosswalk and the boundary of the
CPU equivalence claim.
