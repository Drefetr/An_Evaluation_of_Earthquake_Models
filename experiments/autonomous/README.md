# Completed autonomous finite-mode comparison

The [current execution index](execution_index.json) binds the unchanged frozen protocol to the completed full result, execution record and internal output review. The protocol's original `proposed_unexecuted_requires_independent_review` status records intent before execution; it is not the current experiment status. Its bytes remain unchanged because the completed result records their exact hash.

This directory supplies the executed exploratory comparison and its reproducible implementation. Its
constant-background likelihood is exactly an autonomous finite-mode model,
conditional on the mark and first-moment assumptions in [DERIVATION.md](DERIVATION.md).
It reuses unchanged hash-pinned likelihood and kernel sources. This is the same
raw constant-background intensity family used in the Chapter 9 sensitivity
study, with a separately specified nuisance and optimization recipe. The
earlier results remain fits of that family; this execution does not reproduce
their fitted procedure. The orthogonal constant-background restriction is a
different restriction and is not identified with this raw family.

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

## Relation to the earlier constant-background fit

The earlier raw ML inhibited-minus-null aggregate is -13.036674 nats; this
execution gives -12.945558 nats before the manuscript's displayed rounding.
Both use the same data, chronological folds, shared 195-mode kernel, fixed
productivity ratio and parameter boxes. The earlier beta is estimated
conditionally within magnitude bins; this execution uses N_train/sum(Q_train).
Beta enters productivity, so changing it can affect occurrence scores even
though the common mark term cancels from each paired contrast.

| Fitting choice | Earlier raw constant-background procedure | This execution |
|---|---|---|
| Null starts | Eight: a0 or a0-.5, n=.1/.35/.65/.85 | Four: a0-.5 or a0+.5, n=.2/.7 |
| Inhibited eta starts | 0,.1,.2,.4,.7,1,2,3 | 0,.02,.05,.1,.2,.5,1,2 |
| L-BFGS-B | maxiter200, ftol1e-10, gtol2e-6 | maxiter250, ftol1e-12, gtol1e-7 |
| Powell recovery | maxiter400, xtol1e-6 | maxiter500, xtol1e-7 |
| Candidate accounting | Exact floors and feasible mapped candidates in Stage A; stable candidate IDs and forecast-spread diagnostics | Fitted-null floor, exact minimum and floor-first exact ties |

The complete [historical protocols](../methodological_audit/stability_sources/manifest.json)
and unchanged [executed protocol](protocol.json) retain the remaining settings.
The different search recipes prevent attributing the score difference solely
to beta without a controlled comparison. None was performed for this note.

The finite-mode proof gives no useful catalogue-scale mixing guarantee for
this mixture. Its slowest-rate certificate is a sufficient theoretical bound,
not an estimate of actual process relaxation. The [derivation](DERIVATION.md)
explains the mode-weight and loading/intercept distinctions. The portable
diagnostic uses only scalar algebra and saved records, requires the Python
standard library, and never imports the likelihood engine:

```powershell
python -B experiments/methodological_audit/stability.py --verify validation/live_results/methodological_20261106/stability.json
python -B experiments/methodological_audit/stability.py --output build/new_stability_diagnostic.json
```

The output file in the second command must not exist. All inputs are local
public files with checked hashes; historical machine paths in the exact
protocol copies are documentary metadata, not execution dependencies.


Tiny deterministic controls, without data fitting or simulation:

```powershell
python -B -m unittest discover -s tests -p test_autonomous_bridge.py -v
```

## Executed comparison

The fixed first-fold pilot and full three-fold fit have completed and passed independent output review. The early and late held-out gains are negative; the middle fold selects zero inhibition and has only a numerical shared-coordinate difference. The pooled inhibited-minus-null gain is -12.9456 nats. Complete returned states, event logs, compensators, numerical controls, the pilot and execution records are in [the live result](../../validation/live_results/autonomous_20261105/result.json) and [output review](../../validation/live_results/autonomous_20261105/output_review.json). The original protocol retains its pre-execution status as historical intent; these dated records establish actual execution.
