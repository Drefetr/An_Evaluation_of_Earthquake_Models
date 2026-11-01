# JMA forecast findings

This JMA result reproduces the spatial direction but reverses the timing direction. OC loses 58.593466 timing nats to FC (-0.045884 nats per record), while gaining 1905.743202 conditional-location nats over OL (+1.492360 per record). Each direction holds in all three windows. The registered combined timing-and-location transfer criterion is therefore not demonstrated.

EP also beats OC on joint score in all three windows: OC–EP is -221.211492 nats (-0.173227 per record). The conditional-location component accounts for 213.485907 nats of that deficit. The continuous spatial procedures beat their respective cell-lift alternatives, including FC–FL under the fixed temporal kernel; this spatial result does not establish superiority over the stronger EP reference.

**Reporting status:** `audited_pass`; independent audit status `pass`.

The target is the recorded JMA primary cohort at reported magnitude M>=4.5. This analysis does not establish physical completeness, homogeneous Mw, pristine/as-issued holdout forecasts, causality, calibrated probabilities, or event-iid confidence intervals.

## Registered comparisons

- **Timing:** OC versus FC, using timing log score.
- **Location:** OC versus OL, using conditional location log score.
- **Joint context:** OC versus EP, using the joint score.

The combined descriptive transfer rule uses the primary OC-FC timing and OC-OL conditional-location contrasts. Each must exceed 6e-4 total pooled nats (allowing 1e-4 nat for each of two arm scores across three folds) and be positive in at least two of three folds, after audit pass. OC-EP joint score is a separate competitive-context comparison.

Combined descriptive transfer assessment: **not_demonstrated**.

## Pooled frozen comparisons

| Comparison | Component | Pooled delta nats | Delta nats/target | Fold 0 delta | Fold 1 delta | Fold 2 delta | N |
|---|---|---:|---:|---:|---:|---:|---:|
| OC_FC_timing | timing_logscore | -58.5935 | -0.0458837 | -19.9765 | -12.8718 | -25.7452 | 1277 |
| OC_OL_location | conditional_location_logscore | 1905.74 | 1.49236 | 619.711 | 424.797 | 861.235 | 1277 |
| OC_MC_joint | joint_logscore | -49.1946 | -0.0385236 | -22.8544 | -5.63338 | -20.7069 | 1277 |
| FC_FL_location | conditional_location_logscore | 1847.64 | 1.44686 | 589.61 | 411.737 | 846.29 | 1277 |
| OC_FL_joint | joint_logscore | 1777.98 | 1.39231 | 554.925 | 384.497 | 838.558 | 1277 |
| OC_EP_joint | joint_logscore | -221.211 | -0.173227 | -74.7591 | -59.1334 | -87.319 | 1277 |
| OC_N0_joint | joint_logscore | 3262.47 | 2.55479 | 912.194 | 460.219 | 1890.05 | 1277 |

Event-count reconciliation: full windows have N=469, 348, 460 (total 1277); each arm matches within fold, and the annual rows sum to the same fold totals.

Annual rows use the nine registered source-JST calendar years. The full-window and annual score tables include P, G, positive C, signed negative C, immigrant and offspring exposures, mark/joint/timing/location components, observed target counts, N-C, and conditional allocation residual summaries. These are saved-score aggregates; they are not event-level output.

## Audit and optimizer stability

Audit status: `pass`. Forecast interpretation remains pending or inconclusive unless the independent audit passes. The fit summary retains the prescribed 36 procedures, 288 starts, 42 floors, 330 slots and aggregate failure/recovery/return counts. Near-optimal sensitivity must also resolve before claiming an audited result.

## Limits

The analysis is an observational, within-JMA forecast comparison on the recorded cohort. It does not support causal claims or calibrated probability statements. No event-iid uncertainty intervals are reported.

## Reproduction and execution

The held-out windows are 2016–2018 (469 records), 2019–2021 (348 records), and 2022–2024 (460 records), using the source-JST calendar. Pooled score differences are divided by all 1,277 records.

All 36 procedures, 288 starts and 42 floors resolved (330 prescribed slots). All 288 L-BFGS-B returns passed the saved acceptance checks; no Powell solver recovery was needed.

The initial and resumed forecast launches together took 49.44 minutes, including fitting and score exports. The independent audit took 45.12 minutes. Both used one numerical thread; setup and preliminary controls are outside those times.

A Windows atomic-save interruption was repaired with a bounded filesystem-only retry. Seven completed procedures were reused byte-for-byte, and one fully written floor was restored without reevaluation. The original failed execution and recovery evidence remain preserved. The scientific code, data, start schedule and selection rule were unchanged.

See [the reading guide](reading_the_comparison.md), [aggregate JSON](../results/forecast_findings_v1.json), [selected model parameters](../results/selected_parameters.csv), [independent audit](../reviews/saved_output_audit_v1.json), and [original frozen scientific protocol](../protocol_observed_v1.json). The input and source identities are recorded in the protocols and the run manifest.

## Numerical and boundary scope

The largest independently reconstructed score disagreement is 1.81899e-10 nats (required tolerance 1e-4). The largest near-optimal forecast spread is 3.74731e-05 nats per record (strict limit 0.01). All 36 stability checks passed.

All three training bandwidth selectors chose 5 km, the lower grid boundary; all FC spatial-scale selectors chose 15 km, an interior grid value. The selected background slope d reaches its lower bound in 7, 6 and 2 of seven models in folds 0, 1 and 2. The comparison applies to these frozen grids and bounds. The selected ranges and bandwidths do not establish physical interaction scales or measurement accuracy. See the selected-parameter table for the model-level estimates and boundary flags.

This is predictive, descriptive evidence for the recorded cohort. It supplies no physical-causality or calibration claim. The independent audit supports the numerical results; it does not remove the source and model limitations.
