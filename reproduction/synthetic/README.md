# Synthetic inputs and CPU likelihood replay

This directory publishes the exact recovered synthetic histories, fitted vectors and seed mappings. S04B replay rebuilds integration nodes from event histories and evaluates the likelihood in compiled C++. The archived tables are comparison targets, not inputs to that likelihood calculation.

The bundle contains:

| Study | Published inputs |
|---|---|
| S04B | All 80 event histories, generator receipts, 240 model fits and solver traces, 2,005 retained state vectors, and expected scores. Four generating regimes have 20 fixed seeds each. |
| S01 | All 2,149 event histories: 999 reference, 1,000 null queries and 150 alternative queries; original seed, law, clock and role mappings; 152 saved generator recovery states; all 397 available Stage2 missing-only fit records; final hybrid-bank statistics. |

For the S04B and S01 packages above, `input_manifest.json` binds every listed data/source file by SHA-256 and records its original archive-relative path and hash. `exact_bytes` entries preserve original bytes. `portable_projection` entries remove obsolete machine paths and preserve the listed scientific content; their original file hashes remain available. The supplied data are generated synthetic records, not third-party earthquake catalogue records.

The [F/S01 continuation is withdrawn from the current paper](../../docs/F_followup.md): its original restricted-fit vectors and final-bank manifest have not been recovered. The included older history bank and 397 available fits do not establish a complete saved-state replay of those original F fits. `s01/bank.json` marks this explicitly per case. The original oracle-bank design is retained; this bundle does not turn it into fitted-null calibration.

The separate [unit-mark S2 reconstruction](s2_unitmark/README.md) supplies twenty original narrow/short histories and their paired positive/null generator check. Its own `manifest.json` and pilot/full commands cover that package; the S04B/S01 verification command below does not include it. No fitted procedure or score is recomputed by the S2 route.

## Run

Use Python 3.11 or newer with NumPy and SciPy (the repository's `requirements.txt` supplies tested package pins). A C++17 compiler is required for scoring: MSVC C++ Build Tools on Windows, or GCC/Clang on Linux/macOS. Windows installation discovery uses `vswhere`; alternatively use a developer shell or set `INHIBITORY_VCVARS` to `vcvars64.bat`. All compilers use FP64 without fast-math. No CUDA device is needed.

From the repository root, choose fresh output directories:

```text
python -B reproduction/synthetic/replay.py --mode verify --output build/synthetic_inputs
python -B reproduction/synthetic/replay.py --pilot --output build/s04b_pilot
python -B reproduction/synthetic/replay.py --output build/s04b_all80
```

To score separate histories concurrently, use explicitly bounded process workers:

```text
python -B reproduction/synthetic/replay.py --pilot --workers 4 --threads 1 --output build/s04b_parallel_pilot
python -B reproduction/synthetic/replay.py --workers 4 --threads 1 --output build/s04b_parallel_all80
```

The parent compiles the two libraries once. Each spawned worker loads its own CPU and geometry objects and writes a unique case report. No mutable native handle is shared across processes. Final score and summary rows retain the original roster order regardless of completion order. The default remains one worker with four evaluation threads; every configuration must satisfy `workers * threads <= 4`, and each worker has one BLAS thread. Multiple workers apply only to score mode. Run the fixed parallel pilot to measure its resource use before the full campaign.

The pilot always uses the first frozen seed in each regime: 410401, 410501, 410601 and 410701. `--case CASE_ID` can select a labelled subset; repeat it for multiple cases. Only a successful 80-case score run sets `full_campaign: true`. Every invocation writes `result.json` with a `passed` boolean and returns a nonzero exit code on failure. Build products, compiler logs, per-case numerical reports and newly computed scores/summaries remain in the output directory. Existing directories are refused.

Scoring defaults to four CPU evaluation threads, one BLAS thread, and a 256 MiB native chunk target per worker. Adjust `--threads` between 1 and 4 or `--chunk-mib` between 16 and 2048. Chunking partitions spatial integration only; it preserves all parents and nodes and counts event/mark/base terms once. No quadrature cache is needed or written. `--timeout-seconds` supplies one campaign deadline shared across workers and checked between phases/chunks. Individual native calls run to completion; an external scheduler can enforce a hard process-tree deadline. After a parallel failure the parent stops dispatching new cases, retains failed and already-running case outputs, and lists unstarted cases. Interrupted runs retain `passed: false` and completed case/phase checkpoints. Retry into a new directory after diagnosing the failure.

## What scoring checks

For each exact history, the code reconstructs order16 training quadrature and order32 held-out quadrature using the frozen smooth background and nuisance parameters. It evaluates the saved training-selected state and exact uninhibited floor for each of LI, LI+ immigrant and LI+ total. It checks the selected state's original training eligibility, both newly computed training NLLs, the strict BIC branch, both held-out NLLs, gains, wins and off-floor indicators. It then recomputes all 20 regime/procedure summary rows, including means, medians, descriptive MCSEs and Wilson intervals.

NLLs, gains and summaries must match within an absolute `1e-4` tolerance, with no relative tolerance. Counts, BIC branches and signs must agree exactly. Exact-floor ties yield zero through the same likelihood evaluation; small nonzero gains are never rounded into or out of wins. Rebuilt input-array digests are recorded alongside archived digests; compiler/platform quadrature rounding can differ while the declared numerical score tolerance still passes.

This mode recomputes likelihoods at saved fitted states. It does not rerun optimization or the original all-retained-state quadrature audit. All saved states and solver returns are published so those more expensive checks can be added independently. The original 5.2 GiB GPU peak is irrelevant to the default CPU replay's bounded chunks.

## Generator witness

```text
python -B reproduction/synthetic/replay.py --mode generate --pilot --output build/s04b_generation_pilot
```

This regenerates the same four fixed histories from the archived generator and seeds. It compares exact decompressed event-row bytes, final RNG state hashes and counters against the original receipts. It does not judge reproduction by compressed NPZ container bytes. Removing `--pilot` requests all 80 original seeds. No failed seed is replaced or retried automatically.

The original Linux run recorded NumPy 1.24.2 and SciPy 1.10.1. A different runtime can change floating-point or random-distribution behavior; any mismatch is reported as a failed exact generator reproduction, not silently reclassified as the historical history. The exact original histories remain available independently of this witness.

## Source and checks

`source/` preserves the accepted archived CPU likelihood, radial geometry, generator and quadrature modules. `native.py` adds portable compilation and ABI wiring. `replay.py` extracts the original constructor and spatial-chunking arithmetic into an explicit-input workflow. The protected `engine/`, authorities and provenance records are unchanged.

```text
python -B -m unittest discover -s tests -p test_reproduction_synthetic.py -v
```

These tests check exact input coverage, changed-file/path rejection, original training selection, and tiny compiled likelihood fixtures against the separately written direct-sum oracle. The fixtures cover exact floor, strict-past event ties, mark scaling, empty history, invalid parameters and chunk additivity. They do not run the scientific campaign.

### Completed eighty-history saved-state replay

The [completed replay records](completed_20261105.zip) retain all eighty accepted
case reports, the four interrupted first-attempt records, both execution/build
records, and the independent terminal audit. The first attempt stopped at its
wall limit after fifty accepted cases; its original `passed: false` header is
preserved. A separately recorded continuation completed the thirty missing
cases. Only the combined roster is labelled complete.

The combined evidence contains 400 score rows and twenty summary rows. Its
independent audit checked 960 saved-state likelihood comparisons, with maximum
absolute difference `3.956301952712238e-11`. Negative gains, floor choices, win
counts and active-fit classifications are retained. The score and summary files
are also available under `validation/reproductions/`.

[The archive manifest](completed_20261105.manifest.json) pins every member to its
original source hash and current public hash. All eighty accepted reports and
four interrupted reports are byte-exact. Operational account/project paths in
other records are normalized, with every changed string identified and numeric
equivalence checked. `archive:/` and `user-home:/` identify historical locations;
use the manifest's member mapping to locate the public record.

This is an executed likelihood/score replay at saved fitted states. It does not
claim fresh optimization, new simulation, original geometry-cache byte identity,
prospective confirmation or external peer review. Rebuilt geometry digests and
their original counterparts remain visible in the case reports. Derived
geometry payloads and native binaries are excluded; build/source/binary hashes
are retained.
