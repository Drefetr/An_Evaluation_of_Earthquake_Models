# Final custody and integration review

**PASS within the assigned source, payload and saved-log scope.** This is an internal computational-agent review, not external human peer review or final release authorization. The conductor's production-review record and its metadata link were finalized during this review and their publication/source pins match. The final repository manifest remains a downstream conductor gate. This review does not require a circular pin of itself.

The read-only audit used baseline `61aa599cd023f2441a6a0c6af9aa4b6fe9eda3e5`. It did not run any fit, simulation, native build, scientific replay or full test suite. The executable `audit.py` only reads sources, saved JSON, PDFs and execution logs; its detailed identities and checks are in `audit_results.json`.

## Preserved custody and new bindings

- All 11,303 original claim records compare exactly, field for field, with the baseline. All 679 documentary metadata records and the withdrawal records also compare exactly.
- All 141 tracked files under `validation/authorities/` and `provenance/` compare byte for byte with the baseline; those paths have no pending Git changes.
- All 144 original authority-manifest rows compare exactly. The five additions are live diagnostic/result sources. Every one of the 149 current manifest entries has the recorded hash and byte size.
- Each of the 264 new claims resolves its JSON pointer to the stated value, matches its source hash, and rounds to its displayed precision. The one explicit sum transformation is checked separately. Every declared destination contains its display, including the combined scientific-notation display. The current reconciliation receipt matches the ledger and all recorded manuscript source hashes and reports zero missing declared displays.
- During this review, an actual UTF-8/Windows-default-decoding corruption was found in legacy textual fields. It changed characters in original comparator/locator/semantic metadata without changing scientific numbers. The conductor restored original claim and documentary records from baseline UTF-8 bytes, retained all 264 additions, and refreshed the receipts. The exact baseline comparisons above independently verify the repair. The failed refresh attempt and subsequent successful checks remain recorded.

## Publication agreement

All 20 refitted-comparator table rows and four signed-component rows agree with the saved summary. The abstract, discussion and response give the matched broad/long values 5.1631 nats with 19/20 wins and 9.7367 with 18/20 wins. The companion's rounded values are 5.16 and 9.74. The procedure and table text distinguish the original fixed floor, new training-fitted intercept, retained inhibited states, and unchanged gates; a gated old-floor win against the new floor is not described as selected inhibition.

The generated site's 20 refitted rows equal the saved summary exactly. Its embedded data equals the delivered JSON, and the remaining findings HTML equals the template. The site guide body equals the companion body; the added navigation and stylesheet do not change content. All listed findings sources and all 30 companion source pins match. The site distinguishes descriptive Monte Carlo standard errors and bounded win-indicator intervals from inference about mean gains, calibrated power or physical mechanisms.

The paper is 229 pages with SHA-256 `d5993d49e43ca9ed136eff474dcd4446c09488e49ed7f4f9f2fdbadf7c04d904`; the guide is eight pages with SHA-256 `69ade2f0844cd97cf2b8c614636bf55bd897bb826ff8e9090aac82169bd224cf`. Text extraction contains the current gains and win counts. PDF image/layout review belongs to the separate visual review; this audit did not repeat it.

Compared with this agent's preceding stability/integration review, the reviewed source pins changed only for the shortened Chapter 8 paragraphs and the Chapter 13 refitted-floor table placement. The Chapter 8 shortening preserves the equilibrium-loading/intercept confounding, non-equilibrium-history distinction, exploratory/reused-observation status and lack of full joint nuisance estimation. The Chapter 13 values were rechecked above. No mathematical proof authored by this agent is being independently certified by this final custody review.

The documentation and per-study provenance map distinguish original completed campaigns, later saved-state recomputations, recovered inputs and the new scalar-fit control. They do not claim a new California optimizer or full regional scoring campaign in this revision. They retain the F withdrawal and do not promote historical production reviews to the identity of the new PDFs. The current metadata link pins the new internal production record, and every publication, site-file and manuscript-source hash in that record matches the current payload.

## Recorded checks and regional fixture repair

Hash-pinned execution logs show 195 main tests, 44 regional input/control tests, six S02 input tests, eight Stage 2 tests, and 20 historical iteration-27 tests: **273 passed, zero failures, errors or skips**. The saved site-interaction log reports 70 selector combinations. These are inspected execution records, not suites rerun by this reviewer. The commands and native/CUDA prerequisites are separately documented; the complete local total is not attributed to portable CI. The exact preceding `checks.json` is retained and hash-pinned. Preliminary failed executions are retained separately rather than erased.

The regional change is confined to `reproduction/regional/tests/test_replay_guard.py`. Seven normal-exit grace cases now supply deterministic process identities, lifetimes and monotonic time while invoking the actual, unchanged `supervise()` implementation. The cases still assert delayed clean helper exit, cleanup after the grace deadline, original wall-cap enforcement, nonzero root exit, lease loss, memory breach and identity failure. Faults must actually be injected after the supervisor observes root exit. The fixtures assert no survivors and exact tracked identities; they strengthen the wall-cap and kill-request assertions. Existing real-process discovery/cleanup and sampling-failure tests remain. `reproduction/regional/run_replay.py` is byte-identical to baseline.

The `.gitattributes` additions preserve the byte identities of two already-reviewed diagnostic scripts with terminal blank lines and the exact new evidence/log directories with captured compiler whitespace. They do not rewrite scientific evidence or alter runtime behavior.

## Remaining conductor gates

1. Retain this completed review evidence and finish the conductor's corresponding custody record.
2. Refresh and verify repository membership/hashes and perform the final publication-link checks on the resulting payload.

The `checked_snapshot_sha256` fields identify the metadata/check snapshots observed during this review; they are not a requirement that the conductor's downstream gate-status fields remain pending. All fixed source and artifact identities are recorded separately in `reviewed_sha256`.
