# Original nuisance-fit evidence

These are the original completed non-F studies reported in Chapter 7. They were recovered from existing runs; no fitting was repeated during packaging.

| Archive | Contents |
|---|---|
| historical_fit_package.zip | 6,747 selected-record projections from 6,597 unique original fit files: 2,149 level-only, 2,149 cases with eta-only and background-estimated methods, 2,149 fuller historical fits, and 300 paired fits. Also includes original analysis outputs, code/configuration, 150 old-arm paired histories and all 27 documentary source supplements. |
| historical_diagnostic_package.zip | All 20 exact original case outputs and pinned source files for the completed optimizer and raw-statistic diagnostics. |

The first archive contains exact selected JSON subtrees, each identified by the original file hash and JSON pointer. It does not claim to contain every original search trace. Its manifest identifies exact copied files separately from projections. The second archive preserves complete diagnostic case files. The primary history bank is already supplied under reproduction/synthetic/s01/histories and is linked by original catalogue hashes.

From the repository root, verify identities and archive contents:

    python -B reproduction/historical_fits/verify.py

To inspect the original records, extract into a fresh directory:

    python -m zipfile -e reproduction/historical_fits/historical_fit_package.zip build/historical_fits
    python -m zipfile -e reproduction/historical_fits/historical_diagnostic_package.zip build/historical_diagnostics

The source_availability.json register maps the manuscript's documentary keys S01–S27 to exact archive members. These source keys are distinct from the later S01–S06 follow-up studies. Archived code retains its original execution conventions; the command above verifies and exposes records, and does not launch an optimizer.

The F continuation used different restricted-fit states. Those original states were not recovered and have not been replaced by these earlier fits. Its [withdrawal](../../docs/F_followup.md) removes that continuation from the current manuscript while retaining the historical record.


The manifest count original_files_hashed counts source references checked. The 150 new-arm paired fits also occur in the historical fuller-fit bank; they are not additional independent fits or histories.
