# Completed autonomous finite-mode comparison

This directory supplies the executed exploratory comparison and its reproducible implementation. Its
constant-background likelihood is exactly an autonomous finite-mode model,
conditional on the mark and first-moment assumptions in [DERIVATION.md](DERIVATION.md).
It reuses unchanged hash-pinned likelihood and kernel sources. Existing
historical results are neither changed nor represented as fits of this model.

The null fits a,n with eta=0. The inhibited arm fits a,n,eta and always includes
the exact fitted null floor. Both fix d=0, the shared finite mixture and r=.7.
The common beta estimate uses only each fold's training marks. A failed
positive-inhibition moment gate, incomplete optimizer roster, numerical
disagreement or timeout produces a retained failed result rather than a
substitute model. No p-values or significance claim are produced.

After the recorded independent source, mapping and protocol review, the
following commands reproduce the first-fold pilot and then the full
three-fold experiment. Each output directory must be new and outside sources.

```powershell
python -B experiments/autonomous/fit.py --pilot --output C:/path/to/new_pilot
python -B experiments/autonomous/fit.py --output C:/path/to/new_full_run
```

Inputs are the exact recovered `reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv`
(SHA-256 in `protocol.json`); `--data PATH` accepts the same bytes elsewhere.
Requirements are Python, NumPy, SciPy and threadpoolctl. The wrapper limits BLAS
to one thread. The first fold has a 600-second budget; the full roster has an
1800-second budget, with at most 600 seconds per fold. Deadlines are checked
between objective calls and phases, so one in-flight call may finish after a
deadline; this is not an OS hard timeout. The conductor should enforce any
strict external wall limit. Histories each declare a 512 MB geometry limit.

`result.json` records every optimizer attempt, accepted/failure status, selected
fit vectors, training criteria, first- and higher-moment conditions, order
16/32 controls, event log intensities, interval compensators, final tail,
common mark score and held-out paired gains. The mark score is common to both
arms, so their full marked-score difference is an occurrence-score difference.
Only a complete three-fold run gets a pooled gain. A passed pilot has
`complete:false`. Negative gains remain ordinary successful outcomes.

These folds have already been inspected in earlier work. This is a newly
specified exploratory comparison, not a prospective or untouched validation.
It does not compare magnitude forecasts or jointly estimate their mark law.

Tiny deterministic controls, without data fitting or simulation:

```powershell
python -B -m unittest discover -s tests -p test_autonomous_bridge.py -v
```

## Executed comparison

The fixed first-fold pilot and full three-fold fit have completed and passed independent output review. The early and late held-out gains are negative; the middle fold selects zero inhibition and has only a numerical shared-coordinate difference. The pooled inhibited-minus-null gain is -12.9456 nats. Complete returned states, event logs, compensators, numerical controls, the pilot and execution records are in [the live result](../../validation/live_results/autonomous_20261105/result.json) and [output review](../../validation/live_results/autonomous_20261105/output_review.json). The original protocol retains its pre-execution status as historical intent; these dated records establish actual execution.
