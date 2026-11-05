# JMA fixed-width parsing contract

The original scalar parser uses 31 fixed-width fields in each 96-byte payload.
The portable replay checks every member against its pinned hash and validates
its complete framing before interpreting records. It supports packed96, LF96
and CRLF96 framing without discarding malformed tails. This particular snapshot
contains LF96 members.

The official specifications are
https://www.data.jma.go.jp/eqev/data/bulletin/data/format/fmthyp_e.html and
https://www.data.jma.go.jp/eqev/data/bulletin/data/format/hypfmt_e.html.
Historical documentation retrieval hashes are retained in
`documentation_pins_v1.json`; response bodies are not runtime inputs.

The following table is reproduced from the archived parser description. Slices
are zero-based and half-open.

| Local field | Slice | Format |
|---|---|---|
|agency|0:1|A1|
|year|1:5|I4|
|month|5:7|I2|
|day|7:9|I2|
|hour|9:11|I2|
|minute|11:13|I2|
|second|13:17|F4.2|
|origin_error|17:21|F4.2|
|latitude_degrees|21:24|I3|
|latitude_minutes|24:28|F4.2|
|latitude_error|28:32|F4.2|
|longitude_degrees|32:36|I4|
|longitude_minutes|36:40|F4.2|
|longitude_error|40:44|F4.2|
|depth|44:49|F5.2 or I3,2X|
|depth_error|49:52|F3.2|
|magnitude1|52:54|F2.1|
|magnitude_type1|54:55|A1|
|magnitude2|55:57|F2.1|
|magnitude_type2|57:58|A1|
|travel_table|58:59|A1|
|location_method|59:60|A1|
|subsidiary|60:61|A1|
|maximum_intensity|61:62|A1|
|damage|62:63|A1|
|tsunami|63:64|A1|
|district|64:65|I1|
|region|65:68|I3|
|region_name|68:92|A24|
|stations|92:95|I3|
|determination|95:96|A1|

## Numerical and observation rules

I fields use ASCII integers with outer spaces. F fields use integer coefficients
at the specified implicit decimal scale. Explicit decimal points, internal
blanks, non-ASCII numeric bytes and partially blank fractions remain unresolved.
Fully blank values are missing, not zero. Fully absent fraction bytes preserve
coarse precision; coarse integer depth is usable only under location method 2.

Origin times use fixed JST=UTC+9 and integer centiseconds. Invalid civil dates
and leap-second 60 are rejected for this fixed cohort, with no timestamp jitter.
Nonnegative degree/minute coordinates are exact rational degrees before the
declared spherical equal-area projection. Negative-degree composition remains
unresolved; no coordinate is invented. Opaque region-name bytes are unused.

Primary and secondary magnitudes remain separate. No secondary substitution or
common-magnitude-scale conversion occurs. The scalar numeric parser recognizes
the documented negative examples A0/A9/B0/C0; eligibility recognizes any ABC-digit
negative-sign family as below both positive thresholds. Unknown encodings stay
unresolved. Numeric values alone do not establish eligibility.

The wrapper applies the explicit reported-record predicate and preserves all
initially unresolved target/auxiliary locators in `initial_quarantine.csv`.
The separate observed-primary adjudication excludes missing primary magnitudes
or undetermined primary types from the reported-primary cohort; it does not
impute their physical magnitudes. One auxiliary-only depth ambiguity remains.

`tests/test_reproduction_jma.py` exercises handcrafted records. The public
replay command scans the complete original annual files and compares all
reconstructed target arrays, UIDs and cohort counts with the preserved results.
Snapshot locators are not persistent provider earthquake identifiers.
