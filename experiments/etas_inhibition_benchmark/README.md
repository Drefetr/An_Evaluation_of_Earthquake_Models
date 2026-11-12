# Magnitude-scaled ETAS attenuation benchmark

The current accepted authority is
`validation/live_results/etas_inhibition_benchmark_interior_20261112/summary.json`.
The earlier `etas_inhibition_benchmark_accepted_20261111` authority is preserved
with its source snapshots and is superseded by this final-resolution interior
start search.

Both arms use the same training-only probability-weighted background and jointly
fit the temporal and magnitude-scaled spatial nuisance parameters. The spatial
kernel is normalized on the full plane, with its regional mass retained in the
compensator. The archived EP comparator instead normalizes each parent kernel
on the finite observation rectangle; their score contrast combines this
normalization change with magnitude scaling, background weighting and joint
fitting. The shadow-radius magnitude exponent is a statistical design choice,
not a physical Coulomb stress calculation.

At every final integration power, `accept.py` searches the fitted null, the
three fresh starts `(eta, ell_km, psi_days) = (.05,10,2), (.2,20,5), (.5,50,30)`,
and the retained terminal warm states. Each fresh start takes all nuisance
coordinates from the fitted null. `acceptance_protocol.py` forwards the
unchanged frozen-model objective and saves the exact initial vector and every
completed objective evaluation. The independent `audit_interior.py` recounts
the JSONL records, verifies their hashes and initial vectors, and requires
actual positive-eta evaluations and optimizer success for all three starts.

All three accepted folds select eta=0, giving exactly zero attenuation
contrast. The initial objective values, complete parameter vectors, terminal
states, actual interior-evaluation counts and trace hashes are in
`interior_start_audit.json` and the per-fold `training_traces` directories.

Run the scientific calculation on the dedicated remote compute host, from its
repository root (the CUDA backend requires the native CUDA build environment):

```sh
python -B experiments/etas_inhibition_benchmark/accept.py \
  --backend cuda --model-source run_frozen_gpu_20261111.py \
  --pilot validation/live_results/etas_gpu_pilot_states_20261111 \
  --output validation/live_results/etas_inhibition_benchmark_interior_NEW_EPOCH \
  --wall-seconds 1200
```

Use a fresh output directory. The wall budget is cooperative; frozen execution
sources are pinned before work and checked at completion. No credentials are
stored in the repository. `source_snapshot_manifest.json` preserves the actual
executed sources, and `download_custody.json` verifies every downloaded remote
output against its remote SHA256.

The two tiny local controls exercise start construction and objective tracing
without fitting or loading a scientific catalogue:

```sh
python -B -m unittest tests.test_etas_acceptance_starts -v
```

Postprocessing commands (replace `EPOCH` with the accepted output directory):

```sh
python -B experiments/etas_inhibition_benchmark/audit_interior.py --directory EPOCH
python -B experiments/etas_inhibition_benchmark/reconcile_interior.py --directory EPOCH
python -B experiments/etas_inhibition_benchmark/report.py --source EPOCH/summary.json --output EPOCH/manuscript
python -B experiments/etas_inhibition_benchmark/report_baseline_uncertainty.py --source EPOCH/baseline_uncertainty/summary.json --fragment EPOCH/manuscript/11_epplus_benchmark.tex --id-prefix epplus-baseline-uncertainty-interior-20261112
python -B experiments/etas_inhibition_benchmark/ledger_interior.py --directory EPOCH
```

`reconcile_interior.py` carries the earlier baseline comparison and block
uncertainty forward only after exact equality of all baseline coordinates,
background weights and settings, input cache hashes, and all saved held-out
components. It fails if any change, requiring a fresh comparison and block
calculation. Its new authority explicitly preserves the original statistical
lineage and states that no resampling was repeated. The comparison remains
+69.5528938423 nats, with 90/180/365-day paired intervals and sign-flip values
in `baseline_uncertainty/summary.json`.

The generated manuscript fragment, typed authorities and ledger claims are
supplements for coordinator review. The generators never edit the canonical
manuscript or MASTER ledger. `claim_replacement_mapping.json` names the old
claim IDs replaced by the new accepted authority.
