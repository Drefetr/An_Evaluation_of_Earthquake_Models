# Reproduction scope

Run commands from the repository root. Python 3.13 and `requirements.txt` describe the public CPU check/build environment. Optional CUDA and native research engines have separate requirements. A document rebuild, a fixed-history numerical check, and a scientific experiment are different operations.

Install Node.js 22 for the complete unit suite and website interaction checks.

## Checks and supported entry points

| Task | Inputs and command | Scope |
|---|---|---|
| Deterministic unit checks | `python -B -m unittest discover -s tests -v` | Fixed examples, source-verifier controls, and supported workflow checks; no full research campaign |
| Algebra, quadrature, and paired arithmetic | `python -B scripts/check_mathematics.py --output build/mathematics.json` | Declared deterministic identities and examples |
| Manuscript/source reconciliation | `python -B scripts/verify_claims.py` | Typed manuscript claims and separate source inventory against bundled authorities |
| Public payload/source pins | `python -B scripts/verify_repository.py` | Current manifest membership, hashes, extraction pins, and declared exclusions |
| Website interactions | `node website/check_interactions.cjs` | Generated site selectors and exported aggregate values; requires Node.js |
| Numerical APIs | [Code guide](code.md) | Reusable preserved modules; importing a module does not run its historical campaign |
| Stage 2 engines and runners | [Support matrix](../engine/stage2_followup/README.md) | Per-study source, build, input, and replay status |
| Frozen observed fitting | Install exact historical CSV per [data guide](data.md), then `python -B scripts/run_observed.py --output build/observed.json` | Explicit research workload; not part of routine checks |

The observed wrapper checks its frozen source bindings and exact external CSV. Its protocol retains a cooperative 1,800-second wall budget, one native numerical thread, all prescribed starts, and mandatory numerical controls. It can return incomplete on different hardware. It does not recreate every historical bounded-execution receipt or publication postprocessing step. A new run is not a byte-exact archival replay.

## Monograph and PDF checks

Install Tectonic 0.17.0 and the pinned Python dependencies. The builder compiles only the current unified `paper/source/main.tex`; it does not rebuild every historical supplement.

```sh
python -B scripts/build_paper.py --output build/paper
python -B scripts/validate_pdf.py --source-root paper --pdf build/paper/main.pdf --log build/paper/main.log --output build/pdf-qa
```

Use `--engine /path/to/tectonic`, `TECTONIC`, or `PATH` to select the compiler. Output directories must be new. `main.pdf` and `main.log` are written directly beneath `build/paper`. Production checks render pages and inspect references, figures, glyphs, and layout diagnostics; page images still require visual review. TeX resources and tool versions can change pagination and byte output.

## Figures, companion, and website

```sh
python -B scripts/make_figures.py --output build/figures
python -B scripts/rebuild_review_figures.py --output build/review_figures
python -B companion/build_guide.py --output build/companion
python -B website/build_site.py --output build/site --companion build/companion
```

The two figure tools have different retained scopes. `make_figures.py` regenerates the baseline figures from shipped aggregate inputs and declared algebra. `rebuild_review_figures.py` regenerates the subset revised during the later manuscript review. Neither is a complete regeneration route for all current Stage 2 figures. Compare their output with the shipped assets and inspect the documented inputs; the filename "review" identifies its historical purpose rather than a scientific experiment. PDF/PNG preview exports, including historical profile meshes, may remain in isolated build output. Only the 36 formats referenced by the shipped LaTeX sources are retained in `paper/figures/`, alongside the figure manifest. The review figure builder's `--install` promotes only those referenced formats and records the installed names in its output receipt; it does not restore unused PNG/SVG exports or the obsolete profile-mesh pair.

Companion and site builds use saved content and aggregate authorities. They do not rerun fitting, simulation, bootstrap, or catalogue acquisition. See [companion instructions](../companion/README.txt) and [website instructions](../website/README.md) for output layouts and preview commands.

## Generated artifacts

Builds use fresh output directories by default. `build_paper.py`, `rebuild_review_figures.py`, the companion builder, and the site builder provide explicit `--install` promotion. Installing changes tracked publication assets; inspect the result before updating the affected source bindings, check receipts, and current payload manifest. When revising figure inputs, generate and deliberately install the required figures before compiling the document that should include them.

After the accepted content and source bindings are consistent, refresh the current payload manifest explicitly with `python -B scripts/verify_repository.py --write-manifest`, then run ordinary verification again. This updates current membership; it must not replace preserved historical source identities.

The Pages workflow generates and checks a fresh, self-contained site bundle, publishes it at the root of `gh-pages`, and deploys the matching artifact through GitHub Actions. Its PDF copies stay in that deployment branch and artifact. The committed `website/site/` is a repository preview with relative links to the canonical monograph and guide instead of duplicate PDFs. Serve the repository root and open `/website/site/` to use those links; serve or deploy a generated `build/site/` for a standalone bundle. The corresponding `documents.json` distinguishes `repository_preview` from `self_contained_deployment` and records each document's actual paths and hashes. Site `--install` refreshes only the repository preview and requires canonical PDF sources in `paper/` and `companion/`. The site template `website/findings.html` and generated `website/site/findings.html` have different roles. Regeneration must keep authority-derived values consistent. A local build does not publish; accepted pushes to `main` trigger publication automatically, and the Pages workflow also supports manual runs from `main`.

## Historical evidence and unavailable replay inputs

The [historical archive index](../provenance/historical_archive.json) records removed preparation/control artifacts and their pinned baseline identities. Current check coverage is recorded in [validation documentation](../validation/README.md). Historical receipts describe their original source/PDF snapshot; they are not evidence that a later tree was checked.

The [F addendum](../paper/supplements/f_nuisance_addendum.pdf) is the October checkpoint. The later [S01 completion](F_followup.md) resolves the missing procedure cells and paired summaries. A standalone editable F addendum/replay directory is not included. Use the current monograph source and bundled authorities to inspect the completed presentation; do not infer that every saved F table or figure has a shipped standalone replay command.

Full historical synthetic/reference banks, catalogue records, private fitted vectors, caches, RNG/recovery lineage, and some original processing scripts are not distributed. Saved summaries and generating-law settings do not encode all of those inputs. New simulations or provider downloads require separately identified inputs and protocols. They must not be described as recovery of the retained historical bank or as untouched holdouts.
