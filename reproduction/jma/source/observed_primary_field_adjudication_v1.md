# Reported-primary-field adjudication

This is an explicit, inspection-informed clarification before any model fit or score. The initial full scan and its frozen-v2 dispositions remain immutable. It retains 4,602 complete target records and 41,278 potentially eligible unresolved occurrences. No record or archive is redrawn or deleted, and the original private quarantine is retained.

The adopted scientific object is a selected **reported-record** process, with numeric reported primary M≥4.5 and an observed primary magnitude type in J/D/V/d/v. It is not the set of all physical earthquakes whose latent magnitude might exceed 4.5. JMA's [record specification](https://www.data.jma.go.jp/eqev/data/bulletin/data/format/hypfmt_e.html) identifies a blank magnitude type as undetermined.

Apply the following explicit observation restriction in a separate adjudication layer:

1. A completely blank primary magnitude field is `PRIMARY_MAGNITUDE_UNREPORTED`. It lacks a reported numeric category and does not meet the reported-M predicate. No numerical magnitude is imputed.
2. A blank primary magnitude-type field is `PRIMARY_TYPE_UNDETERMINED`. It does not meet the allowed observed-type predicate. No secondary magnitude or type is substituted.
3. Either documented nonqualifying observation condition can decide the row even when another field is also incomplete. Retain all associated issues and the original unresolved status for audit.
4. Nonblank unknown/invalid encodings are not automatically included in these two categories. A record with known qualifying primary M/type and another essential ambiguity remains separately unresolved until a documented correction or explicit unusable-record disposition is justified.

These reasons do not assert a physically small earthquake, physical non-detection, or harmless missingness. Year/zone/type/missingness summaries remain part of the observation limitations. The comparison is conditional on the specified complete reported-primary population and its observed history.

Run a deterministic local cause audit on every quarantined payload, reconciling hashes, original dispositions and these categories. Save aggregate counts and a private adjudication mapping; retain every original row. Independent review must verify that no qualifying complete target record is added or removed by this layer and report any remaining essential ambiguity. The magnitude threshold, allowed nonblank types, geography, depth, dates, folds and seven forecasting procedures stay fixed. The original 4,602 membership is not silently declared a complete physical-earthquake catalogue.

This amendment resolves observation qualification only. Raw framing, archive/member/UID integrity, civil time, geometry, duplication and complete occurrence denominators still require the independent saved-output audit. No field is fabricated and no original source-evidence flag is rewritten.
