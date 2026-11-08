# An Evaluation of Earthquake Models

Research code, a unified monograph, a plain-language guide, and an interactive findings explorer for **Stability, Identification, and Predictive Evaluation in Inhibitory and Spatial-Temporal Earthquake Models**.

The research studies restricted stability and identification, nuisance sensitivity, spatial and temporal extensions, competitive benchmarks (`OC`, `FC`, `MC`, `EP`), conditional calibration, and continuous local inhibition (`LI`, `LI+ immigrant`, `LI+ total`). The studies use synthetic controls and regional earthquake catalogues from New Zealand, Southern California, and Japan. Results depend on the specified model, observation law, and evaluation population. Predictive preference does not establish a physical inhibition mechanism; this repository does not provide an operational forecasting service.

This open research edition supplies recovered catalogue and simulation inputs, executable cohort reconstructions, and model replay tools. The unchanged New Zealand fitting recipe has been rerun from the recovered input and reproduces every scientific numerical field exactly. Complete known-law and matched-generator score replays have also passed, and a separately executed constant-background fit supplies a reproducible comparison within the autonomous finite-mode family. This is the same conditional intensity family as the earlier constant-background sensitivity, with a different fitting recipe. The stability theorem supplies no useful catalogue-horizon mixing bound for the pinned kernel. Original California completion and nuisance-fit records are also supplied. The F continuation and unexecuted prospective/horizon material have been removed from the current paper, with an explicit historical archive.

The later [selected-state score campaign](reproduction/score_replay/README.md) has also recomputed the declared historical extension and regional scores. Its [independent table-coverage report](validation/reproductions/score_replay_20261107/final_coverage/independent_review.json) distinguishes fresh likelihood evaluations, retained earlier replays and metadata checks. Original optimizer searches were not repeated; exact-display rounding differences remain recorded. A separate [publication coverage check](validation/reproductions/score_replay_20261107/publication_refresh_20261108/independent_source_review.json) binds these retained results to the current manuscript source.

The [per-study provenance map](docs/result_provenance.md) identifies recovered original results, later recomputations and available execution routes.

The joint temporal-backbone comparison has now attempted all 80 original histories: 78 completed, one reached an unresolved optimizer cap, and one exceeded its fixed wall allocation. Both arms fit `(a,d,n,c,p)` on training data; spatial and mark laws stay fixed. Against the jointly refitted uninhibited comparator, matched raw broad/long total inhibition has mean gain -1.2607 nats with 8/20 wins (95% Wilson win-fraction interval [0.2188, 0.6134]). Full-regime summaries for broad/long immigrant and narrow/short total generation remain unavailable. The [complete disposition report](validation/live_results/joint_nuisance_dispositions_20261107/report.json) retains 390 computed comparisons and 10 unavailable slots, alongside the historical comparators. It is not an 80-success experiment.

The methodological revision adds a completed train-only background-intercept control on all 80 existing S04B histories. Against that refitted uninhibited comparator, the matched broad/long immigrant procedure gains 5.1631 joint nats on average with 19/20 wins, and the matched total-intensity procedure gains 9.7367 with 18/20 wins. These gains are substantially smaller than the original fixed-background contrasts. The original inhibited fits and gates are unchanged; this is a comparator sensitivity, not joint nuisance estimation. See the [complete results and executable control](experiments/s04b_refitted_floor/README.md), [point-by-point review response](docs/reviews/methodological_review_response.md), and [current edition review](validation/reviews/JOINT_NUISANCE_DISPOSITION_EDITION_20261108.json).

The subsequent control audit corrects the interpretation of the original unit-mark narrow/short histories: none of their proposed events was rejected. Their retained losses concern histories coupled exactly to the uninhibited process, rather than missed recovery of a realized inhibitory effect. See the [reassessment response](docs/reviews/s2_control_reassessment_response.md) and [reproduction package](reproduction/synthetic/s2_unitmark/README.md).

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

The complete check record combines the main suite, regional input controls, S02 input controls, Stage 2 native fixtures, and historical iteration-27 tests; [current check results](validation/checks.json) give each count separately. The historical full execution used Windows/MSVC native builds. The current Stage 2 command automatically builds the LI, temporal and S06 native fixtures when no native root is configured; GNU/Clang C++17 is supported on Linux and MSVC on Windows. A missing compiler fails the command rather than skipping fixtures. See the [native-build instructions](engine/stage2_followup/README.md#native-builds). The iteration-27 suite also requires a separate CUDA-enabled PyTorch installation and a usable CUDA device; its small CUDA/CPU fit comparison has no CPU fallback. These optional GPU dependencies are not included in `requirements.txt`.

After building the native groups into `build/native/{li,temporal,s06}`, run the two additional suites from the repository root in PowerShell:

```powershell
$env:INHIBITORY_TEST_NATIVE_ROOT = (Resolve-Path build/native).Path
python -B -m unittest discover -s engine/stage2_followup/tests -v
python -B -m unittest discover -s engine/iteration_27/tests -v
```

Earlier Stage 2 runs without `INHIBITORY_TEST_NATIVE_ROOT` passed five portable tests and skipped three native fixtures. The current command instead builds those fixtures automatically in a fresh temporary directory and retains compiler receipts; an explicit native root reuses supplied libraries. The CPU check record remains distinct from the historical CUDA-inclusive execution.

A separate [public CPU route](docs/cpu_reproduction.md) has now been [executed on a fresh Linux checkout](validation/reproductions/cpu_20261107/checkout02_independent_review.json). It requires a C++17 compiler but no MSVC, CUDA or private folders on Linux. This bounded acceptance does not claim macOS execution or GPU parity; it leaves the historical GPU-inclusive suite above distinct. Run its core CPU roster into a fresh directory:

```sh
python -B -m engine.cpu_reproduction --stage all --output build/cpu_acceptance
```

This executes eight Stage 2 tests and twenty iteration-27 CPU tests: nineteen unchanged non-GPU assertions plus one labelled CPU counterpart. The Stage 2 tests overlap the standalone suite; do not count them twice.

These commands check fixed numerical examples, claim/source bindings, and current payload hashes. They do not run the research campaigns, acquire external data, or establish exhaustive mathematical or scientific correctness. Claim verification covers both the manuscript ledger and the separate source inventory; [validation documentation](validation/README.md) explains their roles and current check records.

Run the website interaction check directly with:

```sh
node website/check_interactions.cjs
```

## Use the numerical code

For selected-state likelihood replay, use the [public score reader](reproduction/score_replay/README.md). Its commands require explicit finite resource limits and fresh output directories. The [CPU guide](docs/cpu_reproduction.md) provides the dependency and compiler requirements.

For a fresh fit using the separately versioned amended joint procedure, see the [refined CPU reader](experiments/s04b_refined_cpu_reader/README.md). It automatically extracts the audited Linux x86-64 native library and receipt, without a compiler, MSVC, CUDA, credentials or manual native-library environment setup. Ordinary use has fresh finite local limits and no inherited author expiry; the optional author record imposes a separate dated envelope. Source review and local checks do not constitute independent acceptance of fitted outputs. The earlier CPU acceptance and the C++17 core build route remain distinct.

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
