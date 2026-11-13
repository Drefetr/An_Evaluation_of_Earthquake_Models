# Reviewer guide

**Diagnostic Exponential Rate Attenuation in Spatial–Temporal Earthquake Models**
*Stability, identification and predictive evaluation of point-process models*

This monograph evaluates specified statistical rate-attenuation extensions on historical earthquake catalogues and synthetic histories. Their isotropic point kernels do not model directional Coulomb stress, receiver-fault geometry or rate-and-state friction. A selected zero-strength boundary is a result of a fitted procedure; its exactly nested zero held-out contrast is neither a power calculation nor a test of physical absence.

The current joint temporal-backbone comparison is complete: **80 histories and 400 procedure outcomes**, with all four regimes represented. The [completed summary](validation/live_results/s04b_joint_complete_20261111/summary.json) and [independent computational audit](validation/live_results/s04b_joint_complete_independent_audit_20261111.json) supersede the display of the [78-history disposition checkpoint](validation/live_results/joint_nuisance_dispositions_20261107/report.json). The checkpoint remains historical evidence; its ten unavailable slots do not describe this edition.

Start with the [current monograph](paper/manuscript_unified.pdf), [plain-language guide](companion/lay_guide_to_the_research.pdf), [findings explorer](website/site/findings.html), and [scientific-controls acceptance record](validation/track_b_remediation_20261112.json); the [editorial and statistical-framing acceptance record](validation/track_a_remediation_20261112.json) remains the editorial/statistical baseline. The [preceding reassessment](validation/reassessment_20261112.json) identifies the earlier completed edition; November 7–8 production records certify their own historical artifact bytes only. [Chapter 6](paper/source/chapters/06_design.tex) supplies the common study-scope and inference conventions, and [result provenance](docs/result_provenance.md) records computational execution.

Human authors are identified by their reported handles, [Drefetr](https://github.com/Drefetr) and [magna-nz](https://github.com/magna-nz). Correspondence and corrections can be raised through [repository issues](https://github.com/Drefetr/An_Evaluation_of_Earthquake_Models/issues). The extensive AI assistance is disclosed in [CONTRIBUTORS.md](CONTRIBUTORS.md). Internal computational or saved-output artifact audits are not independent external academic peer review.

## Current study and evidence map

| Study | Current evidence | What was executed |
|---|---|---|
| Joint S04B comparison | [80-history summary](validation/live_results/s04b_joint_complete_20261111/summary.json), [computational audit](validation/live_results/s04b_joint_complete_independent_audit_20261111.json), [additive MCSE/event-count supplement](validation/live_results/track_a_supplement_20261112/s04b_joint_mcse.json) | The two remaining recovery histories were completed; all 400 held-out outcomes are source-bound. Both arms fit `(a,d,n,c,p)` on training data. Historical completed fits are retained separately from recovered computations. |
| Intercept and branching controls | [intercept-only execution](validation/live_results/methodological_20261106/refitted_floor_summary.json), [concave `(b,n)` comparator](validation/live_results/s04b_concave_20261111/summary.json), [reporting supplement](validation/live_results/reporting_supplement_20261112/supplement.json) | Training-only uninhibited refits on all 80 histories; saved inhibited fits and original gates stay fixed. Both comparator win counts are shown. All 20 S7 refits select zero branching. |
| Moderate attenuation control | [20-history result](validation/live_results/s8_moderate_complete_20261111/reported_summary.json), [raw/BIC and diagnostic supplement](validation/live_results/reporting_supplement_20261112/supplement.json), [computational audit](validation/live_results/s8_moderate_complete_independent_audit_20261111.json) | Joint training fits on fresh analysis histories under a law fixed after separate count-only calibration. Raw and training-gated results, boundary hits, and the difference from the stricter inherited numerical gate are disclosed. |
| Magnitude-scaled ETAS and attenuation | [final interior-start acceptance](validation/live_results/etas_inhibition_benchmark_interior_20261112/summary.json), [start audit](validation/live_results/etas_inhibition_benchmark_interior_20261112/interior_start_audit.json), [baseline comparison](validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_comparison.json) | Positive-strength starts were executed at the final training integration rule. The stronger baseline changes magnitude-dependent spatial scale, immigrant-weighted background, joint fitting and full-plane normalization with regional leakage. Its spatial scale reaches the 2 km lower bound in all folds. |
| Component-ablation and sensitivity controls | [EP+ nine-arm ablation and σ₀ study](validation/live_results/track_b_controls_20261112/epplus_ablation/), [New Zealand trend controls](validation/live_results/track_b_controls_20261112/nz_trend_controls/summary.json), [S8 oracle, η profiles and MDEs](validation/live_results/track_b_controls_20261112/profiles_and_power/), [additive referee-remediation supplement](validation/live_results/referee_remediation_20261113/), [independent computational audit](validation/live_results/track_b_controls_20261112/independent_track_b_audit.json) | Deterministic CPU refits on frozen caches: a balanced 2×2×2 EP+ ablation, relaxed and profiled spatial scale, matched zero-trend and fixed-null-trend New Zealand controls, the S8 oracle ceiling, California η profile bounds and contrast-specific minimum detectable effects. The 13 November supplement adds the exact five-contrast MDE table, partial S8 oracle decomposition, three-fold trend totals and non-Gaussian quantiles. No sealed authority was modified. |
| Observed score uncertainty | [accepted block contributions and resampling](validation/live_results/score_uncertainty_remote_v2_20261111/summary.json), [computational audit](validation/live_results/score_uncertainty_independent_audit_20261111.json), [ETAS baseline blocks](validation/live_results/etas_inhibition_benchmark_interior_20261112/baseline_uncertainty/summary.json) | New paired event-minus-exposure calculations on fixed fitted states at 90-, 180- and 365-day scales. These are descriptive dependence-scale summaries; nominal sign-flip references are not calibrated tests for long-memory, nonexchangeable sequences. Read all block lengths and fold consistency together. |
| Stability, identification and visibility | [deterministic checks](scripts/check_mathematics.py), [numerical results](validation/live_results/mathematics_remediation_20261111.json) | Algebra and numerical bounds were checked separately from fitting. The finite-mode stability certificate gives no useful catalogue-horizon mixing time; ideal-law identification is not finite-catalogue power. |
| Historical regional and simulation studies | [study provenance](docs/result_provenance.md), [reproduction index](reproduction/README.md), [selected-state replay coverage](validation/reproductions/score_replay_20261107/final_coverage/independent_review.json) | Recovered original records and later score replays have distinct identities. A selected-state score replay recomputes likelihoods without repeating the original optimizer search. F continuation results remain withdrawn. |

The three Californian observed attenuation selections return the exact fitted null in the stronger ETAS comparison. The zero test contrasts follow from identical scored states. They do not establish that a different attenuation family, fitting box or physical mechanism is absent. The moderate synthetic row likewise does not establish reliable recovery: its raw mean is small relative to its sample Monte Carlo standard error, and both raw and gated procedures retain adverse outcomes.

## Distinguish execution modes

- **Fresh execution:** a newly fitted model or generated history, with its own source epoch, training rule, initial states and resource record. The current recovery, concave comparator, moderate control and corrected ETAS acceptance have explicit records.
- **Saved-state score replay:** a fresh likelihood evaluation at retained fitted parameters. The historical optimizer searches were not repeated by the replay campaign.
- **Historical record or display reconstruction:** inspection, arithmetic or rendering from supplied records. A runnable entry point or a checked hash does not imply a fresh scientific run.
- **Document production:** PDF, figure, guide and website builds. These execute no research campaign.

The [regional reconstruction](reproduction/regional/README.md), [New Zealand fit](reproduction/observed/README.md), [selected-state replay](reproduction/score_replay/README.md), [concave comparator](experiments/s04b_refitted_floor/README.md), and [refined single-history fit reader](experiments/s04b_refined_cpu_reader/README.md) describe their separate interfaces. Recovery is invoked through `python -B -m experiments.s04b_completion.recover`; the historically reviewed public fit-reader script is unchanged. In this handoff workspace, intensive fitting, simulation and likelihood contraction must use the dedicated remote setup under `AGENTS.md`. Do not launch those workloads as part of document validation.

## Trace a displayed value

`validation/MASTER_CLAIM_LEDGER.json` contains enumerated manuscript bindings and documentary metadata. `validation/SOURCE_INVENTORY.json` is a separately identified numerical inventory. The [authority manifest](validation/authority_manifest.json) and explicit withdrawal records preserve historical identities; `MANIFEST.json` describes current payload bytes. The default claim verifier checks both ledgers without rewriting receipts.

Hashes establish identity, while arithmetic and display checks establish the declared transformations and locations. They do not establish that every substantive claim is enumerated or correct. Read an internal computational audit for its actual inputs, independently implemented checks, replay coverage and omissions. None of these records represents journal acceptance or external human verification.

## Verify a checkout

After installing `requirements.txt` and Node.js 22, these bounded commands check the current payload and deterministic mathematics:

```sh
python -B scripts/check_mathematics.py --output build/reviewer_mathematics.json
python -B scripts/verify_claims.py
python -B scripts/verify_repository.py
node website/check_interactions.cjs
```

The complete main and input-check roster is:

```sh
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s reproduction/regional/tests -v
python -B reproduction/regional/inputs.py verify
python -B -m unittest discover -s reproduction/s02 -p test_inputs.py -v
python -B reproduction/s02/inputs.py verify
python -B reproduction/historical_fits/verify.py
```

See [validation instructions](validation/README.md#check-a-checkout) for optional native Stage 2 and historical CUDA suites and their compiler/device prerequisites. The [scientific-controls acceptance record](validation/track_b_remediation_20261112.json) records this edition's actual executed roster; the [editorial and statistical-framing acceptance record](validation/track_a_remediation_20261112.json) remains the editorial baseline, and [checks.json](validation/checks.json) retains the differently scoped historical suite record.

For an isolated Tectonic build and PDF inspection:

```sh
python -B scripts/build_paper.py --output build/reviewer_paper
python -B scripts/validate_pdf.py --source-root paper --pdf build/reviewer_paper/main.pdf --log build/reviewer_paper/main.log --output build/reviewer_pdf_qa
```

All output directories must be fresh. Ordinary builds do not install their PDFs. Automated production checks need visual inspection of the rendered pages. Do not refresh receipts, manifests or accepted artifacts while conducting a read-only review. Report findings with exact source or page locations, reproducible calculations where appropriate, the scientific consequence and a concrete correction; see [review guidance](docs/reviewing.md).
