# An Evaluation of Earthquake Models

Research code, a unified monograph, a plain-language guide, and an interactive findings explorer for **Stability, Identification, and Predictive Evaluation in Inhibitory and Spatial-Temporal Earthquake Models**.

The research studies restricted stability and identification, nuisance sensitivity, spatial and temporal extensions, competitive benchmarks (`OC`, `FC`, `MC`, `EP`), conditional calibration, and continuous local inhibition (`LI`, `LI+ immigrant`, `LI+ total`). The studies use synthetic controls and regional earthquake catalogues from New Zealand, Southern California, and Japan. Results depend on the specified model, observation law, and evaluation population. Predictive preference does not establish a physical inhibition mechanism; this repository does not provide an operational forecasting service.

This open research edition supplies recovered catalogue and simulation inputs, executable cohort reconstructions, and model replay tools. The unchanged New Zealand fitting recipe has been rerun from the recovered input and reproduces every scientific numerical field exactly. Complete known-law and matched-generator score replays have also passed, and a new autonomous finite-mode comparison supplies fitted states and held-out results for a subfamily covered by the stability theorem. Original California completion and nuisance-fit records are also supplied. The F continuation and unexecuted prospective/horizon material have been removed from the current paper, with an explicit historical archive.

## Read the research

- [Unified monograph](paper/manuscript_unified.pdf): the current edition of the mathematical analysis, completed regional comparisons and supported synthetic controls.
- [Plain-language guide](companion/lay_guide_to_the_research.pdf): an eight-page introduction, also available as [HTML](companion/lay_guide_to_the_research.html).
- [Research website and findings explorer](https://drefetr.github.io/An_Evaluation_of_Earthquake_Models/): the published site, served from the generated `gh-pages` bundle. See [local preview and deployment instructions](website/README.md).
- [Reviewer guide](REVIEWER_START_HERE.md): evidence, study scope, and verification entry points.

## Install and check

Install Python 3.13 and Node.js 22 before running the full check suite. Node is used by the website workflow tests as well as the separate interaction check. From the repository root:

```sh
python -m venv .venv
# Activate .venv using your shell's usual command.
python -m pip install -r requirements.txt
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s reproduction/regional/tests -v
python -B reproduction/regional/inputs.py verify
python -B -m unittest discover -s reproduction/s02 -p test_inputs.py -v
python -B reproduction/s02/inputs.py verify
python -B reproduction/historical_fits/verify.py
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
```

The complete check record combines the main suite, regional input controls, S02 input controls, Stage 2 native fixtures, and historical iteration-27 tests; [current check results](validation/checks.json) give each count separately. To run every suite without skips, first build the LI, temporal and S06 libraries using the [Windows x64/MSVC native-build instructions](engine/stage2_followup/README.md#native-builds). The iteration-27 suite also requires a separate CUDA-enabled PyTorch installation and a usable CUDA device; its small CUDA/CPU fit comparison has no CPU fallback. These optional GPU dependencies are not included in `requirements.txt`.

After building the native groups into `build/native/{li,temporal,s06}`, run the two additional suites from the repository root in PowerShell:

```powershell
$env:INHIBITORY_TEST_NATIVE_ROOT = (Resolve-Path build/native).Path
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m unittest discover -s engine/iteration_27/tests -v
```

Without `INHIBITORY_TEST_NATIVE_ROOT`, the Stage 2 command runs its five portable tests and skips its three native fixtures. The CPU CI configuration is therefore distinguished from the complete native/CUDA check record.

These commands check fixed numerical examples, claim/source bindings, and current payload hashes. They do not run the research campaigns, acquire external data, or establish exhaustive mathematical or scientific correctness. Claim verification covers both the manuscript ledger and the separate source inventory; [validation documentation](validation/README.md) explains their roles and current check records.

Run the website interaction check directly with:

```sh
node website/check_interactions.cjs
```

## Use the numerical code

The [replay guide](reproduction/README.md) provides commands that reconstruct all three regional cohorts from bundled raw records, refit the frozen NZ procedure, and recompute synthetic likelihoods. For example:

```sh
python -B scripts/reproduce.py --study nz --output build/replay_nz
python -B scripts/reproduce_observed.py --output build/replay_observed
```

The public loader exposes preserved numerical modules without launching campaign entry points. For example:

```python
import sys
sys.path.insert(0, "engine")
from api import load

weights, rates = load("kernels").KernelSpec("exp", 2.0).mixture
print(weights, rates)  # one exponential mode, rate 0.5
```

See the [code guide](docs/code.md) for the API and [Stage 2 support matrix](engine/stage2_followup/README.md) for native builds, inputs, and supported entry points. Preserved source availability does not imply that every historical campaign can be replayed from a checkout. Optional CUDA operations require an appropriate separate PyTorch installation and device.

## Build documents and the site

Install Tectonic 0.17.0 from its [official release](https://github.com/tectonic-typesetting/tectonic/releases/tag/tectonic%400.17.0). The Python build dependencies are in `requirements.txt`. Use fresh output directories:

```sh
python -B scripts/build_paper.py --output build/paper
python -B scripts/validate_pdf.py --source-root paper --pdf build/paper/main.pdf --log build/paper/main.log --output build/paper_validation
python -B companion/build_guide.py --output build/companion
python -B website/build_site.py --output build/site --companion build/companion
```

The monograph build uses the shipped figures. Use `--engine /path/to/tectonic` or `TECTONIC` if the compiler is not on `PATH`. PDF checks render pages and require visual inspection. Figure regeneration has separate scopes and output directories; see [reproduction instructions](docs/reproducibility.md).

Builds write isolated outputs by default. Their explicit `--install` options promote successful outputs to the tracked publication files. After an intentional promotion, review the changes and refresh the affected source bindings, validation receipts, and payload manifest. Builds and deployment copies are described in the [generated-artifact policy](docs/reproducibility.md#generated-artifacts).

## Repository map and reproduction limits

| Location | Purpose |
|---|---|
| `engine/` | Preserved historical modules, Stage 2 implementations, independent verification oracles, and support guidance |
| `reproduction/` | Recovered raw catalogues and simulation histories, parsers, fitted states and executable replays |
| `paper/` | Current monograph, LaTeX sources, figure assets, aggregate inputs, and historical supplements |
| `companion/`, `website/` | Editable guide/site sources and generated publication bundles |
| `scripts/`, `tests/` | Public build tools and bounded verification checks |
| `validation/` | Manuscript claims, separate source inventory, bundled authorities, study acceptances, and current check records |
| `provenance/` | Original source identities, public adaptations, and the historical archive index |
| `docs/` | Code, data, reproduction, provenance, review, and limitation guides |

Exact regional source records and selected simulation banks are now supplied under provider/project terms. Live downloads are hash-checked and cannot silently replace historical bytes. Some older fitted states and the earlier third-party 40-page manuscript remain unavailable; the [data guide](docs/data.md) and [replay guide](reproduction/README.md) identify what can actually be rebuilt.

Earlier documents remain available for historical comparison: the [restricted manuscript](paper/manuscript.pdf), [explanatory supplement](paper/supplements/explanatory_supplement.pdf), and [F nuisance addendum](paper/supplements/f_nuisance_addendum.pdf). The F addendum and S01 recovery are historical records of the [withdrawn continuation](docs/F_followup.md).

## Attribution, citation, and licences

Human collaborators: [Drefetr](https://github.com/Drefetr) and [magna-nz](https://github.com/magna-nz). Most of the work was performed with AI assistance. Model credits, roles, and review limitations are recorded in [CONTRIBUTORS.md](CONTRIBUTORS.md); AI review is distinct from independent external peer review. Use [CITATION.cff](CITATION.cff) for citation metadata.

Project-owned software is **MIT**. The current monograph, guide, original figures, prose documentation, and project-derived result summaries are **CC BY 4.0**. Third-party material retains its own terms. See [licence scope](LICENSES/README.md), [third-party notices](THIRD_PARTY_NOTICES.md), [change history](docs/changes.md), and [contribution guidelines](CONTRIBUTING.md).
