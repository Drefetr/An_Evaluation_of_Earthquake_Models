# Diagnostic Exponential Rate Attenuation in Spatial–Temporal Earthquake Models

*Stability, identification and predictive evaluation of point-process models.* 14 November 2026 edition. Research code, a unified monograph, a plain-language guide and a findings explorer for specified diagnostic exponential rate-attenuation extensions. These isotropic point kernels do not implement directional Coulomb stress, receiver-fault geometry or rate-and-state friction.

Human authors: [Drefetr](https://github.com/Drefetr) and [magna-nz](https://github.com/magna-nz). Correspondence and corrections: [repository issues](https://github.com/Drefetr/An_Evaluation_of_Earthquake_Models/issues). [CONTRIBUTORS.md](CONTRIBUTORS.md) records extensive AI assistance and human publication responsibility.

## At a glance

- **What this is:** an open research edition: code, a unified monograph, a plain-language guide and a findings explorer for diagnostic exponential rate-attenuation point-process models.
- **What it is not:** an operational forecasting service. Predictive preference does not establish a physical inhibition mechanism.
- **Headline pattern:** in the completed observed-catalogue tests, the tested rate-attenuation additions lose to matched excitation models or select zero strength. These are procedure-level findings, not physical falsification.
- **Status:** AI-assisted work offered for independent review; AI review is distinct from external academic peer review (see [limitations](docs/limitations.md) and [CONTRIBUTORS.md](CONTRIBUTORS.md)).
- **Where to start:** the [plain-language guide](companion/lay_guide_to_the_research.pdf) for a non-technical overview, the [unified monograph](paper/manuscript_unified.pdf) for the full analysis, or the [reviewer guide](REVIEWER_START_HERE.md) to verify claims.

The research studies restricted stability and identification, nuisance sensitivity, spatial and temporal extensions, competitive benchmarks (`OC`, `FC`, `MC`, `EP`), conditional calibration, and continuous local inhibition (`LI`, `LI+ immigrant`, `LI+ total`). The studies use synthetic controls and regional earthquake catalogues from New Zealand, Southern California, and Japan. Results depend on the specified model, observation law, and evaluation population. Predictive preference does not establish a physical inhibition mechanism; this repository does not provide an operational forecasting service.

This open research edition supplies recovered catalogue and simulation inputs, executable cohort reconstructions, and model replay tools. The unchanged New Zealand fitting recipe has been rerun from the recovered input and reproduces every scientific numerical field exactly. Complete known-law and matched-generator score replays have also passed, and a separately executed constant-background fit supplies a reproducible comparison within the autonomous finite-mode family. This is the same conditional intensity family as the earlier constant-background sensitivity, with a different fitting recipe. The stability theorem supplies no useful catalogue-horizon mixing bound for the pinned kernel. Original California completion and nuisance-fit records are also supplied. The F continuation and unexecuted prospective/horizon material have been removed from the current paper, with an explicit historical archive.

The later [selected-state score campaign](reproduction/score_replay/README.md) has also recomputed the declared historical extension and regional scores. Its [independent computational table-coverage report](validation/reproductions/score_replay_20261107/final_coverage/independent_review.json) distinguishes fresh likelihood evaluations, retained earlier replays and metadata checks. Original optimizer searches were not repeated; exact-display rounding differences remain recorded. A separate [publication coverage check](validation/reproductions/score_replay_20261107/publication_refresh_20261108/independent_source_review.json) binds these retained results to the current manuscript source.

The [per-study provenance map](docs/result_provenance.md) identifies recovered original results, later recomputations and available execution routes.

The [editorial and statistical-framing acceptance record](validation/track_a_remediation_20261112.json) binds the current diagnostic framing, derived reporting, complete test roster and refreshed publication artifacts. The [preceding reassessment](validation/reassessment_20261112.json) and [earlier remediation](validation/remediation_20261111.json) retain their own historical artifact identities and check scopes.

The plain-language guide and findings explorer are updated for the completed 14 November edition. The joint-comparison view includes all 80 histories and 400 outcomes; the guide also explains the concave comparator, moderate control, stronger ETAS benchmark and paired calendar-block uncertainty.

The joint temporal-backbone comparison is complete on all **80 original histories and 400 held-out outcomes**. Both arms fit `(a,d,n,c,p)` on training data, with common spatial and mark laws. Matched broad/long immigrant attenuation averages about **-10.4 nats** (sample MCSE **8.6**; 10/20 wins), with about 17 test events per history. Matched broad/long total attenuation averages about **-1.3 nats** (MCSE **2.6**; 8/20 wins), with about 13 test events per history. [Derived MCSE and event counts](validation/live_results/track_a_supplement_20261112/s04b_joint_mcse.json) accompany the unchanged scientific outcomes. The [completed summary](validation/live_results/s04b_joint_complete_20261111/summary.json) includes every history; original interrupted attempts remain historical evidence. The manuscript's three joint tables have no unavailable cells.

The [concave training-only background/branching control](experiments/s04b_refitted_floor/README.md) also covers all 80 histories. All 20 S7 histories select zero branching, reducing the intercept-only residual from +9.7367 to +5.6255 nats before the joint temporal refit reverses it. The comparator table shows active fits beside wins, distinguishing attenuation from returns to a fixed floor.

The [moderate-thinning control](validation/live_results/s8_moderate_complete_20261111/reported_summary.json) completes 20 fresh histories, rejecting 27.21% of proposals and retaining 94.7 test events on average. Its raw mean joint-fit gain is about **+0.29 nats**, with Monte Carlo standard error **2.78** and 13/20 wins. Independent computational [joint-control](validation/live_results/s04b_joint_complete_independent_audit_20261111.json) and [moderate-control](validation/live_results/s8_moderate_complete_independent_audit_20261111.json) audits verify the complete result custody and declared numerical checks.

The [current reporting supplement](validation/live_results/reporting_supplement_20261112/supplement.json) adds the moderate control's training-only BIC row, parameter boundaries, stricter numerical-check flags and both comparator win columns. Its [independent computational audit](validation/live_results/reporting_supplement_independent_audit_20261112.json) verifies these additions. This later training-BIC-gated sensitivity applied to frozen S8 fits has mean about +2.49 nats, median zero, MCSE 1.44, 9/20 wins and 12/20 active fits.

A stronger ETAS procedure gains about **69.55 nats** over archived EP while changing four ingredients together: magnitude-scaled offspring distance, immigrant-weighted background, joint fitting and full-plane normalization with regional leakage. All three fitted spatial scales reach the 2 km lower bound. Its matched attenuation extension selects the zero-strength boundary; identical scored states then give exactly zero held-out contrasts by nesting, not a power or physical-absence test. [Accepted benchmark](validation/live_results/etas_inhibition_benchmark_interior_20261112/summary.json); [baseline uncertainty](validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_uncertainty/summary.json).

**Component-ablation and sensitivity controls decompose that gain and test its boundaries.** A nine-arm ablation attributes about **29.22 nats** to training-declustered background weighting, **30.03 nats** to magnitude-scaled spatial kernels, **10.24 nats** to joint temporal–spatial fitting and **0.06 nats** to full-plane versus rectangle normalization; the Shapley contributions close exactly on 69.553 nats. Relaxing the binding 2 km lower bound to 0.05 km selects interior scales of **0.82–0.84 km** (0.821–0.839 km) and raises the three-fold plane-normalized gain to **77.06 nats** with redeclustered background weights (**78.58 nats** with the accepted weights held fixed), against **69.55 nats** at the binding bound; the rectangle panel gives 77.06 and 78.52 nats and is not additive. In New Zealand, fixing the background trend at zero reduces the three-fold shared-attenuation deficit from **−17.62 nats** to **−11.43 nats** (Fold 1: −8.50), and fixing it at the null trend reduces it to **−5.01 nats** (Fold 1: −4.56), below the **9.24-nat** 90-day minimum detectable effect. In the S8 moderate bank, the full true generating law including the true nuisance backbone beats the fixed true-backbone null by **16.43 nats** (the exact generating attenuation effect), beats the intercept-refitted true backbone by **14.54 nats**, and beats the jointly fitted five-parameter null by **18.11 nats** (MCSE 4.18); the last exceeds the second by **3.57 nats** because the five-parameter fitted null overfits: the held-out contrast is a **+3.571-nat loss** for the fitted comparator, driven by seed 410840 (other-seed mean -0.203, median -1.683). Fixing the true attenuation on a fitted backbone yields only **3.13 nats**, and fitted **η̂** has mean **0.929** and range **[0.042, 4.000]** against the generating 0.4. The fitted procedure captures **0.29 nats**; mean estimation loss is **17.82 nats**, erasing about 98% of the oracle advantage. At 90-day blocks the contrast-specific MDE is **9.24 nats** for New Zealand shared attenuation, **3.82 nats** for California `LI+` total attenuation (3.27 by the pooled percentile interval, against −2.39 observed), **48.30 nats** for California `EP+` minus `EP` (against +69.55 bound-pinned and +77.06 interior), **43.35 nats** for California `OC` minus `EP`, and **47.94 nats** for the three-fold Japan `OC` minus `EP` total (**15.98 nats** per three-year fold; **56.51 nats** for the nine annual JMA blocks). See the [EP+ ablation and σ₀ study](validation/live_results/track_b_controls_20261112/epplus_ablation/), [New Zealand trend controls](validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json), [S8 oracle and power summaries](validation/live_results/track_b_controls_20261112/profiles_and_power/), the [additive referee-remediation supplement](validation/live_results/referee_remediation_20261113/), the [14 November forensic remediation package](validation/live_results/forensic_remediation_20261114/), the [forensic disposition](docs/reviews/forensic_audit_response_20261114.md), and the [independent computational audit](validation/live_results/track_b_controls_20261112/independent_track_b_audit.json).

[Paired calendar-block uncertainty](validation/live_results/score_uncertainty_remote_v2_20261111/summary.json) is supplied at 90, 180 and 365 days for the specified New Zealand and California contrasts. Long-memory dependence and block exchangeability are not established. Treat these as descriptive sensitivity summaries across block lengths and folds; nominal sign-flip references are not calibrated significance tests.

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

The complete check record combines the main suite, regional input controls, S02 input controls, Stage 2 native fixtures, and historical iteration-27 tests; [current scientific-controls check results](validation/track_b_remediation_20261112.json) give the actual roster and each count separately; [checks.json](validation/checks.json) preserves a differently scoped historical record. The historical full execution used Windows/MSVC native builds. The current Stage 2 command automatically builds the LI, temporal and S06 native fixtures when no native root is configured; GNU/Clang C++17 is supported on Linux and MSVC on Windows. A missing compiler fails the command rather than skipping fixtures. See the [native-build instructions](engine/stage2_followup/README.md#native-builds). The iteration-27 suite also requires a separate CUDA-enabled PyTorch installation and a usable CUDA device; its small CUDA/CPU fit comparison has no CPU fallback. These optional GPU dependencies are not included in `requirements.txt`.

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

For a fresh fit using the separately versioned amended joint procedure, see the [refined CPU reader](experiments/s04b_refined_cpu_reader/README.md). It automatically extracts the audited Linux x86-64 native library and receipt, without a compiler, MSVC, CUDA, credentials or manual native-library environment setup. Ordinary use has fresh finite local limits and no inherited author expiry; the optional author record imposes a separate dated envelope. Source review and bounded checks document the interface; each new fitted output needs its own computational audit. The earlier CPU acceptance and the C++17 core build route remain distinct.

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
