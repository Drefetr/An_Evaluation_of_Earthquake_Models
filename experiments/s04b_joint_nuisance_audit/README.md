# Independent joint-comparison output audit

This standard-library-only auditor reads retained Task 1 records. It does not
import the experiment package, run an optimizer, evaluate a likelihood, or
generate a history. Its independent aggregation uses the stored component
scores and parameter vectors, rather than the experiment's summary routine.

```text
python -B experiments/s04b_joint_nuisance_audit/audit.py \
  --results /external/joint-pilot \
  --protocol experiments/s04b_joint_nuisance/protocol.json \
  --admission /external/joint-admission.json \
  --build-receipt /external/attenuation.build.json \
  --library /external/attenuation.so \
  --output /external/independent-pilot-audit
```

Use the actual retained admission, build receipt, binary and result paths.
Output must be a new directory. A full audit additionally requires
`--pilot /external/joint-pilot`. Paths in receipts may describe a different
machine; binary and receipt identities are verified from the supplied files.
The experiment source and all pinned input bytes must be available locally.

The pilot accepts exactly the five protocol cases (25 outcome rows and 30
historical floor checks), and always reports `full_complete: false`. The full
audit requires the entire 80-case roster, 400 outcomes, 480 historical floor
checks, 400 historical comparison identities, and exact reuse of the five pilot
cases and their attempt traces. Missing, failed, unknown or substituted cases
fail acceptance. The historical comparison identities are not claimed as new
inhibited likelihood evaluations.

Checks include the prescribed training starts and bounded solver recovery;
eligible floors; candidate minimization and exact tie selection; training-only
fine-score gates; selected coarse/fine consistency; exact floor returns;
strict positive wins with separate near-zero counts; signed P+C+M decomposition;
all-coordinate boundaries; failed, capped and rescue attempts; generation
thinning counters; and each historical comparison against the original saved
records. Wilson intervals are pointwise intervals for bounded win indicators,
not simultaneous coverage or intervals for mean log-score gain.

Source, input, build, admission, case, trace, summary and pilot-reuse hashes are
checked. Runtime and resource fields are consistency-checked recorded evidence;
the external supervisor's resource receipt and source review remain separate
acceptance requirements. This audit cannot establish that recorded gradients
or scores were scientifically computed correctly, nor that a training freeze
record alone proves the absence of test leakage. Those require the reviewed
execution path and, where appropriate, independent numerical replay.

Constructed corruption controls:

```text
python -B -m unittest discover -s tests -p test_joint_output_audit.py -v
```

These controls use fabricated records and opaque non-executable library/history
fixtures. They perform no scientific computation and are not additional
earthquake-model experiments.
