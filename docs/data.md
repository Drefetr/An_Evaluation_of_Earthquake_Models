# External data and snapshot identity

No third-party event records are included. Tests, figure generation and paper compilation never download data.

Start with [GeoNet catalogue documentation](https://www.geonet.org.nz/data/types/eq_catalogue), [WFS](https://wfs.geonet.org.nz/), [FDSN](https://service.geonet.org.nz/fdsnws/event/1/) and the [catalogue DOI](https://doi.org/10.21420/0S8P-TZ38). Read the [provider terms and attribution policy](https://www.geonet.org.nz/policy) before use. Dataset-specific terms remain authoritative.

The historical reconstructed WFS snapshot was retrieved 2026-10-15. Selection: 1960-01-01 inclusive to 2026-10-15 exclusive; earthquake event type; magnitude >=5; longitude 165..180; latitude -48.5..-33.5; finite depth <=40 km excluding -9 km unknown-depth sentinel; other negative depths retained. Native magnitudes/scales were not homogenised. Time is days since 1960-01-01 UTC with 86,400 seconds/day and no leap-second modelling. Magnitude excess is M-5. The observation window is 24,394 days; 913 events were selected.

Exact processed CSV: 109747 bytes; SHA256 `feacccb7581d1c4c33f88874cd6b198c41639da6930a7fc35e46f910a594fb3e`. The historical source archive recorded selection metadata and a separate FDSN identity. Those metadata files are not included at those paths in this monograph-only package. The catalogue count above describes the historical selected archive, not the held-out denominators in the later regional studies. The interfaces are not independent physical catalogues.

The acquisition scripts and guarded catalogue installer belonged to the earlier engine archive; they are not bundled here. This package supports rebuilding and checking the monograph from its aggregate authorities, not reacquiring or rerunning the scientific catalogues. See [reviewer guidance](../REVIEWER_START_HERE.md) for the available commands and the scope of the preserved historical source index.

A provider can revise past events: a fresh download with identical dates need not reproduce historical bytes, counts or fits. Historical snapshot recovery is not guaranteed from the live provider. A new snapshot requires a separately versioned protocol; it must not silently replace the inspected historical data or be labelled an untouched holdout.
