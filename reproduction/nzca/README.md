# New Zealand and California catalogue replay

This bundle reconstructs the actual project cohorts from original provider records. It contains the raw numerical responses, their byte hashes, the selection code, and the expected selected records. No access to a private archive is required. This command uses only Python's standard library and an unused output directory:

```powershell
python -B reproduction/nzca/replay.py --region all --output replay_nzca
```

Use `--region nz` or `--region california` to run either region separately. The command refuses an existing output path and exits nonzero if an input, selection, exclusion audit or expected output differs. `result.json` reports the verified raw hashes and actual replay results. Inputs are never overwritten. A failed run retains its outputs for inspection.

The New Zealand output includes the exact 913-event CSV used by the observed procedure and the separate 102-event prehistory. It applies the historically pinned preparation functions to the eight original WFS CSV chunks, then compares the entire generated CSV byte for byte. It also emits an event-level inclusion/exclusion ledger. The primary CSV is available directly at `expected/geonet_M5_shallow_1960_2026.csv`, SHA-256 `feacccb7581d1c4c33f88874cd6b198c41639da6930a7fc35e46f910a594fb3e`.

The California replay parses all 45 original annual files, including excluded records. It reproduces the historical exclusion and clock-status audits, preserves exact source tokens and line numbers, and compares all 1,272 ordered canonical event objects. It checks the 106-event warmup, the 79/167/69 primary target counts, and the separate 16/53/18 magnitude-at-least-4.5 sensitivity counts. The 315 primary targets are thus regenerated from provider records. `california/events.json` is the portable canonical cohort. Its wrapper excludes the historical machine paths; the event objects are unchanged.

This is catalogue reconstruction. Running this command does not fit a model or regenerate a reported log score. The prepared cohorts are the inputs for those subsequent numerical stages. The NZ material is the reconstruction acquired on 15 October 2026; it is not the unavailable older manuscript catalogue. California uses the revised official snapshot at commit `7105f6c1b861db46c3a8454984588f5b6a4a56e4`, rather than an archive of forecasts issued in real time.

## Inputs and source continuity

`input_manifest.json` contains only portable paths, original-byte SHA-256 values, compressed-file hashes, official URLs, acquisition dates where applicable, provider attribution and scientific selection metadata. It contains no captured HTTP headers or private machine paths. Original source files remain unchanged in the historical archive.

The `sources/` directory contains the original SCEDC parser and verbatim extracted functions from the original NZ preparer and California lane parser. Their original source-file hashes and the hashes of each extracted function are recorded in the manifest. Only the imports/constants and invocation wrapper were adapted for portable execution. The California functions preserve exact decimal boundary checks, microsecond timestamps, conflicts between duplicate IDs, opaque location-quality tokens and the unavailable-second-60 rule. Eligible events with unavailable clocks cause failure; they are never silently clamped. The source-named `private_parse_audit.json` and `raw_id_index.json` files emitted in the new output directory are ordinary replay diagnostics and contain public catalogue IDs.

The eight NZ numerical responses occupy 403,913 bytes before compression and 98,417 bytes in the bundled gzip files. The 45 California annual files occupy 70,225,177 bytes before compression and 18,918,327 bytes compressed. Gzip preserves the original provider bytes. No provider HTML, cookies, HTTP response headers, agent transcripts or private fitted vectors are included.

## Optional public retrieval

The offline bundle is sufficient. To independently retrieve the same source bytes:

```powershell
python -B reproduction/nzca/acquisition.py --region all --output downloaded_nzca
python -B reproduction/nzca/replay.py --region all --raw-input downloaded_nzca --output replay_downloaded_nzca
```

California URLs are pinned to the official immutable Git commit, and each response must match both SHA-256 and Git blob SHA-1. GeoNet URLs reproduce the original WFS queries, but the live catalogue can change. A changed or oversized response is retained with a `.rejected` suffix and causes a nonzero exit; it is never silently substituted for the historical snapshot. Both commands require new output directories. Retrieval uses HTTPS only and accepts only the named official source hosts.

## Attribution

GeoNet supplies the NZ earthquake catalogue. We acknowledge GeoNet and its sponsors; cite the [GeoNet Earthquake Catalogue](https://doi.org/10.21420/0S8P-TZ38). GeoNet content is licensed under [CC BY 3.0 New Zealand](https://creativecommons.org/licenses/by/3.0/nz/), subject to its [policy](https://www.geonet.org.nz/policy). The selection, excess-magnitude transformation and inclusion ledger are project processing.

California records come from the SCEDC/SCSN routine catalogue. Cite **SCEDC (2013), Southern California Earthquake Data Center. Caltech. Dataset.** [doi:10.7909/C3WD3xH1](https://doi.org/10.7909/C3WD3xH1), following the [SCEDC citation policy](https://scedc.caltech.edu/about/citation.html). The project licence does not relicense provider data, and neither provider endorses the model analysis. The California source is the [official pinned snapshot](https://github.com/SCEDC/SCEDC-catalogs/tree/7105f6c1b861db46c3a8454984588f5b6a4a56e4).

The small parser/integrity test suite can be run separately:

```powershell
python -B -m unittest discover -s tests -p test_reproduction_nzca.py -v
```

Those tests exercise malformed sources, hash failure, selection boundaries, missing magnitudes, timestamp rules, duplicate conflicts and output protection. The full raw-to-cohort replay remains the separate command above.
