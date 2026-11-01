# External data and snapshot identity

Third-party event records are not distributed. Routine tests, aggregate figure generation, and document/site builds do not download catalogues. Scientific replay needs separately obtained inputs and the exact processing, observation, and fitting contracts for that study.

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

If you possess the exact selected historical CSV, check it before installing:

```sh
python -B scripts/install_catalogue.py /path/to/historical.csv --check-only
python -B scripts/install_catalogue.py /path/to/historical.csv
python -B scripts/run_observed.py --check-inputs-only
```

The installer verifies its hash and row count, refuses to overwrite an existing input, and writes to the ignored location specified by `engine/iteration_27/configs/observed_frozen.json`. `run_observed.py` also verifies the frozen numerical source bindings. Actual fitting is an explicit separate workload; see [reproduction scope](reproducibility.md).

Historical acquisition/preparation sources are shipped at `engine/iteration_5/code/fetch_catalogue.py` and `prepare_catalogue.py`. The fetcher performs network requests and creates a fresh snapshot with provenance; the preparer validates frozen responses. Their fixed October cutoff describes the historical design. A new fetch is not guaranteed to recover the selected historical bytes, even with identical query dates. Consult their help/source and the [code support guidance](../engine/stage2_followup/README.md) before using them for a newly identified input.

## Southern California: reported preferred-magnitude cohort

The current regional results use preferred SCEDC/SCSN records. The archived source preparation retained 45 official files and selected 1,272 canonical unique records meeting reported M >=4.0, latitude 32 to 37 degrees, longitude -121 to -114 degrees, and depth -5 to 40 km. Of these, 106 records in 1981 to 1985 provide warmup parents; scored training starts in 1986. The three UTC half-open test windows [2011,2016), [2016,2021), and [2021,2026) contain 79, 167, and 69 targets, totalling 315. Later benchmark, calibration, and inhibition studies reuse these targets.

The source parser repair retained unused location-quality tokens as opaque metadata. It reused cached official files rather than dropping rejected model candidates or issuing a new source query. The separate M >=4.5 sensitivity changes the observation population and refits its procedures; its 87 targets are not additional independent records to add to 315. Exact source and selection discussion is in the [regional chapter](../paper/source/chapters/11_external_transfer_benchmarks.tex).

Obtain raw annual data through the official SCEDC catalogue page, retaining provider format and snapshot identities. The complete historical acquisition/processing archive, all original file bytes, and every fitted-state/cache input are not bundled here. A current annual download or alternate FDSN representation must not silently substitute for those inputs. The provider access links identify where data are available; they are not a one-command replay of the archived study.

## Japan: JMA reported-primary complete-case cohort

The JMA study processed 19 local annual archives for source-JST years 2006 to 2024. The 4,019,138 source records yielded 4,602 usable study records. The target requires agency `J`, natural subsidiary `1`, determination `K`/`k`/`A`, primary magnitude type `J`/`D`/`V`/`d`/`v`, observed numeric primary reported M >=4.5, depth 0 to 60 km, and the study's fixed projected-region predicate. Primary and secondary magnitudes remain distinct. These reported-record conditions are not homogeneous Mw or proof of physical completeness.

The 496 records from 2006 to 2010 provide warmup only. Scored training begins in 2011; source-JST test windows 2016 to 2018, 2019 to 2021, and 2022 to 2024 contain 469, 348, and 460 records, totalling 1,277. Retain source-JST boundaries rather than silently replacing them with UTC calendar years. The [regional chapter](../paper/source/chapters/11_external_transfer_benchmarks.tex) explains the inspection-informed complete-case restriction and its limits.

Obtain the annual hypocentre ZIP files and their fixed-width format specification from JMA. Historical raw archive bytes, the complete parser/observation adjudication package, and all projection/cache-construction inputs are not supplied as a standalone replay route. Exact archived identities and the projected-region predicate must be recovered from the study's original protocols before claiming historical reproduction; neither a plotted map nor this selection summary defines a substitute processing contract. Consult the [Stage 2 support matrix](../engine/stage2_followup/README.md) for the supplied numerical components.

## New inputs are new snapshots

Providers revise past records. Identical dates can yield different bytes, counts, magnitudes, or fits on a later download. Preserve raw bytes, retrieval metadata, format/parser identity, selection rules, and processed hashes for a new snapshot. A changed input needs a separately versioned protocol and should not be labelled exact historical recovery, a pristine as-issued holdout, or an independent replicate of reused targets.
