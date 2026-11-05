# Original California fitting and scoring evidence

The original primary California and higher-threshold calculations are supplied as three archives. They contain completed original executions, rather than newly fitted replacements.

| Archive | Contents |
|---|---|
| `original_primary_california_20261025.zip` | Primary California cases, all 30 fit and 30 score records, 30 candidate registries, exact-floor/selector plans, original audits and frozen source modules. Also contains the separately labelled M4.5 candidate table at `m45/private_reporting/candidate_tables_v1.json`. |
| `original_california_benchmarks_20261025.zip` | The original six EP/N0 fit and score records, selected states and candidates, feature arrays, contracts, full audit and frozen source modules. |
| `original_california_m45_20261025.zip` | The separate higher-threshold sensitivity: all 30 fit and 30 score records, 30 registries, cases/plans, aggregate and annual accounting, original audits and source modules. |

`original_primary_california_20261025.manifest.json` maps all 664 members to their archive and historical source path. Every archive is below the GitHub per-file size limit. All 132 fit and score records match hashes in their original audit or seal records. The package also verifies 401 frozen source-module pins. Cases retain training/test windows, cohort identities and nuisance records; event histories are supplied by `../nzca/`. Fitted files retain candidates, solver slots, exact floors and selection rules. The `alias_fixedML_smooth_cont.json` files identify the training-selected fixed-ML spatial candidate. Rebuildable quadrature caches and redundant combined `summary_private` exports are omitted; their constituent records are included.

The primary cohort and the M4.5 sensitivity are different studies. In particular, the candidate-table hash printed in the appendix, `8ba55b42dae764c005e30bb3fe4200dbc7206d4a6f018aee2bc0760c5c50bb30`, identifies the original M4.5 table. Its public archive member substitutes portable placeholders for machine account roots. The manifest records both original and public hashes. Every numeric, Boolean and null field is preserved; other changes are confined to those path prefixes. Source strings containing `${PROJECT_ROOT}` or `${USER_HOME}` describe the original filesystem layout and require explicit relocation. Historical `private` labels and interim audit-status fields are retained as historical metadata; the associated later audit records and the current publication manifest establish the publication context.

The California provider inputs and cohort construction are in `../nzca/`. Original benchmark source modules are archived alongside the results and identified by the frozen protocols. This package does not claim another independent numerical replay. It closes the previous omission of original primary fitting states, candidate tables and score records; the separate S03/S05/S06 bundles and replay records keep their own coverage.
