# External data and snapshot identity

The exact reconstructed New Zealand, California and Japan catalogue inputs are bundled under `reproduction/`, with provider attribution, source hashes, parsers and selection rules. The replay commands rebuild the selected cohorts from raw records and compare full records and observation arrays. Document builds remain separate from these data and numerical replays; see the [replay guide](../reproduction/README.md).

## Provider access and attribution

| Region | Official access | Provider credit and terms |
|---|---|---|
| New Zealand | [GeoNet catalogue](https://www.geonet.org.nz/data/types/eq_catalogue), [WFS](https://wfs.geonet.org.nz/), [FDSN](https://service.geonet.org.nz/fdsnws/event/1/) | [Catalogue DOI](https://doi.org/10.21420/0S8P-TZ38), [GeoNet data policy](https://www.geonet.org.nz/policy) |
| Southern California | [SCEDC/SCSN annual ASCII catalogues](https://scedc.caltech.edu/eq-catalogs/), [format/search documentation](https://scedc.caltech.edu/eq-catalogs/catalog-search-help.html), [FDSN service](https://service.scedc.caltech.edu/fdsnws/event/1/) | [SCEDC citation policy](https://scedc.caltech.edu/about/citation.html), [dataset DOI](https://doi.org/10.7909/C3WD3xH1) |
| Japan | [JMA Seismological Bulletin](https://www.data.jma.go.jp/eqev/data/bulletin/index_e.html), [annual hypocentre archives and file format](https://www.data.jma.go.jp/eqev/data/bulletin/hypo_e.html) | [JMA legal notice](https://www.jma.go.jp/jma/en/copyright.html) and dataset-specific notices |

Use the provider's documented format and applicable terms; retain source citations and distinguish project-derived processing from provider products. Project MIT/CC BY 4.0 licences do not relicense third-party inputs. See [third-party notices](../THIRD_PARTY_NOTICES.md).

## New Zealand: exact reconstructed historical input

The reconstructed GeoNet WFS snapshot was retrieved on 15 October 2026. It is separate from the unavailable original catalogue of the earlier third-party manuscript. Its selected CSV has 913 events, 109,747 bytes, and SHA-256:

```text
feacccb7581d1c4c33f88874cd6b198c41639da6930a7fc35e46f910a594fb3e
```

Selection is 1960-01-01 inclusive to 2026-10-15 exclusive (UTC), event type `earthquake`, finite reported magnitude at least 5, longitude 165 to 180 degrees, latitude -48.5 to -33.5 degrees, and finite depth at most 40 km. The unknown-depth sentinel -9 km is excluded; other negative depths are retained. Magnitude types are not homogenised. Time uses 86,400-second days since 1960-01-01 UTC, without leap-second modelling; magnitude excess is M-5 and the horizon is 24,394 days.

[WFS snapshot metadata](../provenance/catalogue_snapshot_metadata.json) records selection, columns, and input identity. [FDSN metadata](../provenance/fdsn_snapshot_metadata.json) describes a separate interface/sensitivity input; the two services are not independent physical catalogues.

The exact selected CSV is bundled at `reproduction/nzca/expected/geonet_M5_shallow_1960_2026.csv`. Reconstruct it from the original WFS responses, then check and install the bundled copy for the frozen fitting entry point:

```sh
python -B scripts/reproduce.py --study nz --output build/replay_nz
python -B scripts/install_catalogue.py --check-only
python -B scripts/install_catalogue.py
python -B scripts/run_observed.py --check-inputs-only
```

The installer verifies its hash and row count, refuses to overwrite an existing input, and writes to the ignored location specified by `engine/iteration_27/configs/observed_frozen.json`. `run_observed.py` also verifies the frozen numerical source bindings. Actual fitting is an explicit separate workload; see [reproduction scope](reproducibility.md).

Historical acquisition/preparation sources are shipped at `engine/iteration_5/code/fetch_catalogue.py` and `prepare_catalogue.py`. The fetcher performs network requests and creates a fresh snapshot with provenance; the preparer validates frozen responses. Their fixed October cutoff describes the historical design. A new fetch is not guaranteed to recover the selected historical bytes, even with identical query dates. Consult their help/source and the [code support guidance](../engine/stage2_followup/README.md) before using them for a newly identified input.

## Southern California: reported preferred-magnitude cohort

The current regional results use preferred SCEDC/SCSN records. The archived source preparation retained 45 official files and selected 1,272 canonical unique records meeting reported M >=4.0, latitude 32 to 37 degrees, longitude -121 to -114 degrees, and depth -5 to 40 km. Of these, 106 records in 1981 to 1985 provide warmup parents; scored training starts in 1986. The three UTC half-open test windows [2011,2016), [2016,2021), and [2021,2026) contain 79, 167, and 69 targets, totalling 315. Later benchmark, calibration, and inhibition studies reuse these targets.

The source parser repair retained unused location-quality tokens as opaque metadata. It reused cached official files rather than dropping rejected model candidates or issuing a new source query. The separate M >=4.5 sensitivity changes the observation population and refits its procedures; its 87 targets are not additional independent records to add to 315. Exact source and selection discussion is in the [regional chapter](../paper/source/chapters/11_external_transfer_benchmarks.tex).

The [NZ/California bundle](../reproduction/nzca/README.md) includes all original annual files, losslessly compressed, and the historical parser and selection functions. `python -B scripts/reproduce.py --study california --output build/replay_california` reconstructs every canonical event object, original source token and source-line reference, as well as exclusion audits and chronological counts. The optional downloader uses the official SCEDC repository at commit `7105f6c1b861db46c3a8454984588f5b6a4a56e4` and rejects any hash mismatch. Catalogue reconstruction and refitting/scoring the regional models are separate stages.

The [California follow-up input package](../reproduction/regional/README.md) supplies all 5,994 S05 simulated futures, six observed futures and six frozen simulation states, together with seed receipts, the S03 four-arm fitted vectors and all 55 S06 fit records and their contracts. Input verification and materialization were executed and independently checked. The package includes the archived S05 point/temporal scoring source; model scoring is a separate computation from these input checks.

## Japan: JMA reported-primary complete-case cohort

The JMA study processed 19 local annual archives for source-JST years 2006 to 2024. The 4,019,138 source records yielded 4,602 usable study records. The target requires agency `J`, natural subsidiary `1`, determination `K`/`k`/`A`, primary magnitude type `J`/`D`/`V`/`d`/`v`, observed numeric primary reported M >=4.5, depth 0 to 60 km, and the study's fixed projected-region predicate. Primary and secondary magnitudes remain distinct. These reported-record conditions are not homogeneous Mw or proof of physical completeness.

The 496 records from 2006 to 2010 provide warmup only. Scored training begins in 2011; source-JST test windows 2016 to 2018, 2019 to 2021, and 2022 to 2024 contain 469, 348, and 460 records, totalling 1,277. Retain source-JST boundaries rather than silently replacing them with UTC calendar years. The [regional chapter](../paper/source/chapters/11_external_transfer_benchmarks.tex) explains the inspection-informed complete-case restriction and its limits.

The [JMA bundle](../reproduction/jma/README.md) contains all 19 original ZIPs, the fixed-width parser, the observed-primary adjudication, the projection and expected observation arrays. `python -B scripts/reproduce.py --study jma --output build/replay_jma` reconstructs the selected population from the raw archives. Missing or disallowed observed primary magnitude fields are retained in the diagnostic accounting; secondary magnitudes are not substituted.

The recovered projection is spherical cylindrical equal-area with radius 6371.0088 km, centred at latitude 37 degrees and longitude 138 degrees. With angles in radians, `x = R*cos(phi0)*(lambda-lambda0)` and `y = R*(sin(phi)-sin(phi0))/cos(phi0)`. The closed study rectangle is `x in [-600,600]` and `y in [-800,800]` km. Its three-by-three grid assigns internal boundaries to the north/east cell. Exact source-JST centisecond clocks, source-record identities, strict-past prefixes and fold masks are included in the replay checks. The predicate is now executable and inspectable rather than an unresolved archive reference.

## Synthetic histories and fitted states

The [synthetic bundle](../reproduction/synthetic/README.md) supplies the matched-generator S04B histories, generating settings, retained fitted states and CPU score-replay code. It also supplies the exact S01 history bank with its role, seed and clock mapping and the available later recovery fits. The F continuation is withdrawn because its original restricted-fit states could not be recovered. The separate original nuisance-fit evidence is supplied in [historical_fits](../reproduction/historical_fits/README.md). Rebuildable numerical caches are generated from these inputs instead of being prerequisites supplied through a private path.

## New inputs are new snapshots

Providers revise past records. Identical dates can yield different bytes, counts, magnitudes, or fits on a later download. Preserve raw bytes, retrieval metadata, format/parser identity, selection rules, and processed hashes for a new snapshot. A changed input needs a separately versioned protocol and should not be labelled exact historical recovery, a pristine as-issued holdout, or an independent replicate of reused targets.
