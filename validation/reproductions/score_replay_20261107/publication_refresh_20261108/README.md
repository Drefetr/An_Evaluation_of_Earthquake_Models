# Publication source-custody refresh

This package preserves the accepted r05 coverage and source-custody review for
103 historical table containers. The r02 review is preserved under evidence/.
The r05 change terminates the paragraph inside the local interline-penalty
group around the joint and following observed inputs. Removing the terminator
recovers the exact r04 parent; moving the end back recovers r03;
removing that wrapper recovers the exact accepted r02 parent source hash.
This package updates whole-source identities and locators
after publication prose changes; all historical table bodies, numeric mappings,
arithmetic results, tolerances and coverage table objects remain unchanged.

The retained scope is 78 mapped containers, 12 with prior evidence, and 13
requiring no additional likelihood execution under the frozen plan. It is not
103 fresh executions. The historical schema name `no_likelihood_required` does
not imply the absence of likelihood-valued fields: the Training NLL table still
has 36 reconciled fields. The 2,271 prior-scope and 204 no-additional-execution
fields remain explicitly `not_run` in this mapping pass. All 119 metadata fields
and four tiny display-rounding flags are preserved. S05 still covers 5,994 point
scores and 15 full 84-coordinate vector replays. The three new joint-disposition
tables have separate acceptance and are outside this historical census.

## Verify after installation

From the repository root, run:

```sh
python -B validation/reproductions/score_replay_20261107/publication_refresh_20261108/verify.py --repository .
```

The verifier checks every declared package payload, all 15 current manuscript
source hashes, six producer/parser hashes and the prior acceptance. It then runs
the existing pinned `coverage_report.py` on saved evidence in a temporary
directory and requires byte-identical coverage output. It performs no likelihood,
native, optimizer, model-generation or score-replay calls and does not modify
repository files. A source change requires a new reviewed custody refresh;
altering the pins is not a substitute for review.

`coverage_inputs.json` resolves its local resources as siblings and its unchanged
historical resources relative to the repository. The intended installation path
is recorded in `relocation_manifest.json`. The previous `final_coverage/` package
remains unchanged.

## Evidence and relocation

`independent_source_review.json` is the original accepted review, byte-for-byte.
`source_guard.json` and `assembly.json` retain their original preparation-stage
flags; later execution and review evidence establish the completed saved-arithmetic
check. They are not rewritten to claim later work happened during preparation.

`evidence/original_execution/` contains exact historical commands, execution
receipts and logs. Those records retain the original private machine paths for
provenance and are **not portable operational instructions**. Do not execute
their command arrays. Use the verification command above. Absolute paths inside
the unmodified source review likewise describe historical inspection locations;
they are not required to resolve this package.

`relocation_manifest.json` maps all 19 original package files to their new
locations without changing bytes. Its payload hashes include this README and
the verifier. `relocation_verification.json` records the actual metadata-only
relocation check and is separate from the original scientific acceptance.
