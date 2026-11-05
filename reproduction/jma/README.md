# JMA raw-to-cohort reproduction

This package contains the original 19 JMA annual hypocentre ZIPs used by the
study, the explicit geographic/observation selection, the selected historical
arrays, and recovered fitted states and score outputs. The ZIPs total
107,921,679 bytes; they contain 4,019,138 records from source-JST years 2006–2024.

From the repository root, using Python 3.10 or later and NumPy 1.24 or later:

```powershell
python -B reproduction/jma/replay.py --output build/jma_replay
```

The output directory must not already exist. The command needs no download,
compiler, GPU, private path, feature cache or fitted state. It checks every
compressed and decompressed source hash, then reconstructs the selected cohort
from the raw bytes. It compares all 20 resulting arrays with the original
expected arrays and exits nonzero on any mismatch. `result.json` contains
`passed`, counts, each array comparison and the source-member results.
`catalogue.csv`, `catalogue_arrays.npz` and `initial_quarantine.csv` are retained
for inspection even when a later comparison fails.

The expected results are 4,602 selected records, 496 warmup records, expanding
training counts 2,829/3,298/3,646 and test counts 469/348/460 (1,277 total).
Every selected occurrence is independently decoded with the preserved scalar
parser after complete-array screening by the recovered vector parser.
Integers, UIDs, reported magnitudes, time keys, masks and array dtypes must match
exactly. Projected coordinates allow only 2e-11 km absolute difference for
platform variation in `sin`/`cos`; exact equality is reported separately.

`--raw-dir DIRECTORY` can point to another local copy of the same `h2006.zip`
through `h2024.zip` files. Changed current-provider downloads are rejected by
the historical hashes. `input_manifest.json` gives the official URLs, sizes,
compressed/member hashes, CRCs and source lineage. All 19 original ZIPs are
included here, so downloading current catalogue revisions is unnecessary.

## Selection and projection

The predicate is agency `J`; natural subsidiary `1`; determination `K/k/A`;
primary magnitude type `J/D/V/d/v`; reported primary M >= 4.5; depth 0–60 km;
valid source-JST origin in 2006–2024; and the following projected rectangle.
Primary and secondary magnitude fields remain distinct.

For latitude phi and longitude lambda in radians, use spherical cylindrical
equal-area coordinates with R = 6371.0088 km, phi0 = 37 degrees and
lambda0 = 138 degrees:

```
x = R*cos(phi0)*(lambda-lambda0)
y = R*(sin(phi)-sin(phi0))/cos(phi0)
```

Keep x in [-600,600] and y in [-800,800] km, with closed outer boundaries.
The 3-by-3 grid uses x edges [-600,-200,200,600] and y edges
[-800,-800/3,800/3,800]. Internal edges belong to north/east cells.
`source/geometry_v1.py` defines the exact geometry; `source/FORMAT.md` describes
fixed-width parsing and missing/invalid value handling.

Epoch is 2005-12-31 15:00 UTC, or 2006-01-01 00:00 JST. Integer time keys use
8,640,000 centiseconds/day. Warmup ends at day 1826; scored training begins
there. Fold origins are days 3652/4748/5844 and ends 4748/5844/6940. All windows
are half-open. K = primary magnitude in tenths minus 45, and Q = 0.1 K.

The original scan marked 41,278 target and 41,279 auxiliary occurrences as
potentially eligible but unresolved. The separate, preserved
`source/observed_primary_field_adjudication_v1.md` excludes records with missing
primary magnitude or undetermined primary type from the observed-primary
population. This resolves all target ambiguities without changing the 4,602
selected records; one auxiliary depth ambiguity remains. The replay writes
every original uncertain locator, payload hash, UID and both initial/final
statuses. Known exclusions, observation exclusions and unresolved values are
reported separately. No missing value or secondary magnitude is substituted.

## Historical identities and fitted-state recovery

Historical UIDs use SHA-256 of compact UTF-8 JSON:

```
["jma_static_row_uid_v1", historical_manifest_sha256,
 member_sha256, byte_offset, payload_sha256]
```

The old acquisition-manifest digest is a preserved namespace, explicitly stored
in `input_manifest.json`. It is not the digest of the new portable manifest.
The historical manifest contained local machine paths; those bytes are not
distributed or needed to compute UIDs. Source ZIP/member hashes are preserved.
`source_crosswalk.json` maps historical relative source identifiers and hashes
to public files, recording every extraction or editorial transformation.

`inputs/saved_states.zip` contains 1,118 historical artifacts: original
36-procedure fit records, all nuisance and selected states, selected and
candidate event-score arrays, complete slot rosters, and S06 JMA fixed-trend
fits/outputs. `saved_states_manifest.json` records every member's original and
public hash. Numeric values are preserved; absolute machine-path references in
JSON were replaced with `historical/` archive identifiers. These identifiers
describe lineage and are not runtime inputs. Feature caches are omitted because
the published engine can rebuild them from the now-public arrays and nuisance
states.

The raw replay command checks the saved-state bundle's identity but does not
refit models or recompute forecasting scores. The recipe in `scoring_recipe.json`
specifies how to use the existing engine, recovered states and regenerated
cohort for a separate numerical replay. The old protocol/build hashes remain
historical identities; a rebuilt numerical environment requires its own runtime
record. This package does not claim that storing a fitted vector verifies the
likelihood evaluated at that vector.

Run the handcrafted regression controls with:

```powershell
python -B -m unittest discover -s tests -p test_reproduction_jma.py -v
```

## Source acknowledgement

Source: **Japan Meteorological Agency, Seismological Bulletin of Japan,
hypocentre data**, annual files 2006–2024, obtained 26 October 2026 from the
[official archive](https://www.data.jma.go.jp/eqev/data/bulletin/hypo_e.html).
The annual ZIPs are unmodified provider files. Projection, selection,
observation adjudication, array construction and model fits are this project's
processing and must not be represented as JMA's own products or endorsement.

JMA's [terms](https://www.jma.go.jp/jma/en/copyright.html) apply the
[Public Data License 1.0](https://www.digital.go.jp/en/resources/open_data/public_data_license_v1.0)
unless specifically indicated otherwise. Preserve source acknowledgement and
identify edited/processed content. Provider terms and any applicable third-party
notices govern the provider data; the repository's code licence does not replace
them.
