# Inhibitory earthquake models

Consolidated research monograph, plain-language companion, interactive findings explorer, and numerical implementation for **Stability, Identification, and Predictive Evaluation in Inhibitory and Spatial–Temporal Earthquake Models**.

The work studies restricted stability and identification results, nuisance sensitivity, spatial–temporal background and kernel extensions, competitive benchmarks (`OC`, `FC`, `MC`, `EP`), conditional calibration, and continuous local inhibition (`LI`, `LI+ immigrant`, `LI+ total`) across synthetic controls and regional earthquake catalogues (New Zealand, Southern California, and Japan). Predictive preference does not establish a physical inhibition mechanism, and no operational earthquake-forecasting service is claimed.

**Collaborators:** [Drefetr](https://github.com/Drefetr), [magna-nz](https://github.com/magna-nz); [Claude Opus 5.5](https://www.anthropic.com/claude-opus-5-5), [DeepSeek 4.1 Flash](https://www.deepseek.com/en/news/deepseek-v4-1-flash/), [Gemini 4.0 Argon](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon), [GPT 6.0 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), [GPT 6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

**AI assistance:** the bulk of the work was performed by AI agents. Claude Opus 5.5 and GPT 6.0 Astra developed the initial outline and specification; GPT 6.1 Sol coordinated GPT 6.1 Sol and DeepSeek 4.1 Flash subagents; GPT 6.0 Astra and Gemini 4.0 Argon provided review. AI review is distinct from independent external peer review. See [CONTRIBUTORS.md](CONTRIBUTORS.md).

## Primary documents and interactive explorer

- **[Unified Monograph (231 pages)](paper/manuscript_unified.pdf)**: Single-volume LaTeX edition consolidating the mathematical foundations, Addenda I–V, the completed Stage 2 (`S01`–`S06`) scientific programme, and the matched-law `LI+` synthetic control study (`S04B`).
- **[Plain-Language Companion Guide (8 pages)](companion/lay_guide_to_the_research.pdf)**: Illustrated non-technical overview ([HTML version](companion/lay_guide_to_the_research.html)).
- **[Interactive Research Website & Findings Explorer](website/site/index.html)**: Self-contained site and interactive explorer ([`website/README.md`](website/README.md); deployable via `.github/workflows/pages.yml`).
- **[Reviewer Guidance](REVIEWER_START_HERE.md)**: Scope, claim-ledger custody, and verification entry points for the scientific-completion edition.
- **Historical baseline editions**: [Earlier 64-page restricted manuscript](paper/manuscript.pdf), [explanatory supplement](paper/supplements/explanatory_supplement.pdf), and [F nuisance addendum](paper/supplements/f_nuisance_addendum.pdf).
- **Documentation**: [Code guide](docs/code.md), [Stage 2 & S04B implementations](engine/stage2_followup/README.md), [reproduction instructions](docs/reproducibility.md), [methods](paper/supplements/methods_supplement.md), [data sources and terms](docs/data.md), [limitations](docs/limitations.md), [change history](docs/changes.md), [contribution guidelines](CONTRIBUTING.md), and [citation metadata](CITATION.cff).

## Quick checks

Python 3.13 was used for the local preparation checks. From the repository root:

```sh
python -m venv .venv
# Activate the environment using your shell's usual command.
python -m pip install -r requirements.txt
python -B -m unittest discover -s tests -v
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
```

These checks run 49 deterministic unit tests (`test_public_core.py` and `test_verify_claims.py`), verify symbolic and quadrature identities, reconcile all 27,069 typed claim and documentary metadata records in `validation/MASTER_CLAIM_LEDGER.json` against the 140 bundled authorities and LaTeX chapter sources, and verify repository file hashes and privacy exclusions.

## Building the monograph, companion, figures, and website

Install Tectonic 0.17.0 from its [official releases](https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.17.0), then:

```sh
python -B scripts/build_paper.py --output build/paper
python -B scripts/validate_pdf.py build/paper/main.pdf --output build/paper_validation
python -B scripts/rebuild_review_figures.py
python -B companion/build_guide.py
python -B website/build_site.py
```

Use `--engine /path/to/tectonic` if needed. Output directories for `build_paper.py` must be new.

## Contents and reproduction scope

- `paper/` contains the 231-page unified monograph (`manuscript_unified.pdf`), LaTeX sources (`paper/source/`), all 55 figure PDFs/PNGs (`paper/figures/`), aggregate plotting inputs (`paper/data/`), and supplements (`paper/supplements/`).
- `companion/` and `website/` contain the 8-page plain-language guide and the static GitHub Pages bundle (`website/site/`).
- `engine/` contains the byte-pinned historical numerical modules (`engine/iteration_*`, verified against `provenance/extraction_manifest.json`) plus the Stage 2 (`S01`–`S06`) and `S04B` C++/Python implementations and independent `Q01` verification oracles (`engine/stage2_followup/`).
- `validation/` contains `MASTER_CLAIM_LEDGER.json` (27,069 records), the bundled authority files (`validation/authorities/`), study acceptances (`validation/acceptances/`), and release verification receipts.

Third-party per-event earthquake catalogue records and the earlier third-party 40-page manuscript PDF are excluded. Obtain external inputs independently under their providers' terms (`docs/data.md`).

## Licences

Project-owned software: **MIT**. Current monograph, companion guide, original figures, prose documentation, and project-derived result summaries: **CC BY 4.0**. These are separate scopes, not a blanket licence over third-party material. See [licence scope](LICENSES/README.md) and [third-party notices](THIRD_PARTY_NOTICES.md).
