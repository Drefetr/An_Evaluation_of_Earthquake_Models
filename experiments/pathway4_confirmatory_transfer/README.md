# Pathway 4 — single-pass frozen confirmation and cross-regional EP+ transfer

This package implements the confirmatory execution specified in
`refinement_pathway_handoffs/PATHWAY_4_SINGLE_PASS_CONFIRMATION_COHORT_HANDOFF.md`.

## Order of execution

1. `python -m experiments.pathway4_confirmatory_transfer.freeze_protocol`
   writes and hash-pins `frozen_protocol_v1.json`.  It reads no New Zealand or
   Japan test-window score.
2. `python -m experiments.pathway4_confirmatory_transfer.run_nz`
   fits the four New Zealand arms (`plane`/`rect` x `T0`/`T1`) and the frozen
   attenuation profiles.  `python -m ...run_jma --fold N` does the same for
   the three Japan arms (`plane` T0/T1 and `rect` T1).
3. `python -m experiments.pathway4_confirmatory_transfer.seal_fits`
   writes `fit_seal.json` after every fit exists.
4. `python -m ...score_nz` and `python -m ...score_jma` verify the seal, then
   open the test arrays and archived OC/EP totals.  No fit is changed at this
   stage.
5. `python -m ...run_ca_calibration` simulates the 999 conditional paths per
   California origin from the frozen interior-scale EP+ states.
6. `python -m ...audit_pathway4`, `python -m ...build_summary` and
   `python -m ...make_report` produce the independent audit, machine summary
   and report.

## Files

| file | role |
|---|---|
| `geometry.py` | nine-cell domain, exact in-domain radial mass, background KDE |
| `model.py` | eight-coordinate EP+ likelihood, `plane`/`rect` normalisations, frozen attenuation profiles |
| `data.py` | read-only NZ/JMA/CA adapters and archived comparator loaders |
| `fit.py` | five-step declustering, multi-start L-BFGS-B, bounds |
| `pipeline.py` | training-only arm execution and attenuation profiles |
| `forecast.py` | conditional branching simulation and the eight diagnostics |
| `freeze_protocol.py` | pre-execution protocol and hash pin |
| `seal_fits.py` | fit manifest seal |
| `score_nz.py`, `score_jma.py` | post-seal held-out scoring |
| `run_ca_calibration.py` | California conditional calibration |
| `audit_pathway4.py` | independent numerical and custody audit |
| `build_summary.py`, `make_report.py` | machine summary and report |

## Writes

Code and protocol: `experiments/pathway4_confirmatory_transfer/`.
Results: `validation/live_results/pathway4_confirmatory_20261116/`.
Report: `docs/reviews/pathway4_confirmatory_report_20261116.md`.

No file under `validation/authorities/` or a pre-existing `live_results`
subdirectory is written.
