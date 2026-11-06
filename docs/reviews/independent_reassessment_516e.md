# Independent Reassessment of Methodological Revision (`516e5fd4877c7c7c7b7e2bbac215bfa32275a311`)

---

## 1. Independently Checked Artifact Identity

All checks below were performed in an isolated checkout (`C:\Users\Drefetr\AppData\Local\Temp\opencode\eq-review-516e`) at commit `516e5fd4877c7c7c7b7e2bbac215bfa32275a311` (parent `61aa599cd023f2441a6a0c6af9aa4b6fe9eda3e5`), with all temporary outputs written outside the checkout and `git status --short` verified clean after execution.

| Artifact / Check | Independently Verified Value | Status |
|---|---|---|
| Git commit (`HEAD`) | `516e5fd4877c7c7c7b7e2bbac215bfa32275a311` | **Verified** |
| `paper/manuscript_unified.pdf` | 229 pages, SHA-256 `d5993d49e43ca9ed136eff474dcd4446c09488e49ed7f4f9f2fdbadf7c09488e49ed7f4f9f2fdbadf7c04d904` (`d5993d49e43ca9ed136eff474dcd4446c09488e49ed7f4f9f2fdbadf7c04d904`) | **Verified** |
| `companion/lay_guide_to_the_research.pdf` | 8 pages, SHA-256 `69ade2f0844cd97cf2b8c614636bf55bd897bb826ff8e9090aac82169bd224cf` | **Verified** |
| `scripts/verify_claims.py` | `passed: true`, `release_ready: true`, 11,064 literal manuscript display bindings (10,800 prior + 264 new; 0 missing), 503 withdrawn records, 27,307 total records across `MASTER_CLAIM_LEDGER.json` and `SOURCE_INVENTORY.json` | **Verified** |
| `scripts/verify_repository.py` | `passed: true`, 8,692 checked files, 0 errors | **Verified** |
| Test suites (`tests`, `regional`, `s02`, `stage2` with compiled native DLLs, `iteration_27` with CUDA) | $195 + 44 + 6 + 8 + 20 = 273$ tests, 0 failures, 0 errors, 0 skips | **Verified** |
| Independent full rerun of `experiments/s04b_refitted_floor/run.py` (`pilot` + `full` + `summarize.py`) | 80 cases, 480 historical floor checks (`max_saved_floor_absolute_difference = 6.821210263296962e-13`), exact match to `validation/live_results/methodological_20261106/refitted_floor_summary.json` | **Verified** |

---

## 2. Disposition of Each Original Finding

| Finding | Topic | Disposition | Summary of Resolution / Remaining Gap |
|---|---|---|---|
| **C1** | Degenerate narrow/short immigrant control (`S4_narrow_short_imm` rejected 0 events in 19/20 histories) | **Partially Resolved (S04B resolved; S04 & initial 8-seed `S2_narrow_short` omitted)** | Fully disclosed for S04B in the Abstract, §13.11.1, Table 13.6 (`tab:s04b-thinning`), §14.5, and Companion, with a valid source-backed RNG stream-coupling argument. **However**, the exact same generator check on the unit-mark `S2_narrow_short` regime (`410201`–`410220`) used in the initial 8-seed study (Table 13.4) and original S04 (Table 13.5) shows **0/2,951 rejected immigrants across 20/20 histories**, yet §§13.1, 13.7, 13.11, and 14.5 still describe those unit-mark narrow/short losses as failures to detect active inhibition. |
| **C2** | S04/S04B fixed-backbone comparator handicap in broad/long regimes | **Resolved (within declared intercept-only scope)** | New scalar training-only intercept control (`experiments/s04b_refitted_floor/`) executed on all 80 S04B histories. Refitting $a \in [-12,0]$ alone removes $89.3\%$ of the `S5` gain ($+48.3868 \to +5.1631$ nats, $19/20$ wins) and $81.7\%$ of the `S7` gain ($+53.2332 \to +9.7367$ nats, $18/20$ wins). Scope (fixed $d, n, c, p$, fixed spatial background, unchanged gates) is transparently stated. |
| **C3** | Score-moment divergence in S04/S04B (`LI+`), `LI+ total`, and S02 (`M2`) | **Resolved** | Chapter 5 (`05_inference.tex`, lines 90–143, Proposition 5.2), §9.10 (`09_s02_completed.tex`, line 11), §13.11 (`13_s04_expanded.tex`, lines 20–35), and `moments.py` rigorously prove null score-variance divergence via a first-parent conditional Jensen argument (`prop:null-score-obstruction`), separate `LI+ total` diagonal obstructions ($\mathbb{E}[g^2]=\infty$, $\mathbb{E}[g^2\kappa]=\infty$, and $L^1$ compensator obstruction $\mathbb{E}[g\kappa]=\infty$), and distinguish $\eta=0$ from fixed $\eta>0$. |
| **C4** | False statements on S04B shared coordinates / missing parameter distributions; boundary hits & $\eta=0$ termination | **Resolved** | False claims in `13_s04_expanded.tex` removed; Table 13.7 (`tab:s04b-parameters`) tabulates median $[\min,\max]$, total boundary hits $B$, and zero-strength hits $Z$ across all 240 fits. Both `any_near_boundary` ($B$) and `active_boundary` ($B - Z$) are recorded in `synthetic_diagnostics.json`. The distinction between KKT-valid termination on the singular $\eta=0$ face and an optimizer defect is accurately stated. |
| **C5** | Quantitative vacuity of Theorem 3.1 on the 195-mode mixture; §8.6 identity with Chapter 9’s $d=0$ model; $\rho>0$ equilibrium confounding | **Resolved (with two valid corrections to original review)** | §3.1 (`03_stability.tex`, lines 60–73) and §8.6 (`08_observed_baseline.tex`, lines 215–273) explicitly state $\vartheta_{\min} = e^{-38.8}\,\text{day}^{-1}$, $t_0 \ge 9.8284 \times 10^{16}\,\text{days}$, cross-reference Tables `tab:A-constant_background` and `tab:AG-constant_background`, and show $a_{\mathrm{eff}} = a + \rho\sum_j w_j/\vartheta_j$. The authors’ two corrections to my prior review (**61** modes decay by $<1\%$, whereas 72 decay by $<52.4\%$; and both $\hat\beta$ and the optimizer start/tolerance recipe differ between §8.6 and Stage A) are **verified and accurate**. |
| **M1** | Doubly exponential rarity of zero-aftershock identifying paths in Proposition 4.2 | **Resolved** | §4.3 (`04_identifiability.tex`, lines 79–90) now explicitly writes $S_q(s,u) \le \exp(-a_u\kappa(q))$ and explains both the doubly exponential rarity of quiet paths after large marks and the non-applicability of the $q \to \infty$ step when $r=0$ ($\kappa \equiv 1$, as in S02’s M2). |
| **M2** | Seismological restrictions (isotropic magnitude-invariant $\sigma,\ell$; $b_{\mathrm{ref}}$ cell-boundary jumps; STAI vs. inhibition) | **Resolved as explicit model-class boundary** | §2.5 (`02_models.tex`, lines 187–190) and §6.7 (`06_design.tex`, lines 186–190) explicitly state these restrictions and cite Hainzl (2016) on short-term aftershock incompleteness (STAI), without overclaiming physical stress-shadow or detection recovery. |
| **E1–E3** | Repetitive scope prose, legacy `InhibitoryEarthquakeModels` URLs, and selective execution provenance | **Resolved** | All 11 legacy repository URLs in `paper/source/` updated to `An_Evaluation_of_Earthquake_Models` at `61aa599`; shared empirical interpretation consolidated in §6.7; `docs/result_provenance.md` accurately separates historical records from the new S04B intercept control. |

---

## 3. Detailed Technical Scrutiny & Remaining Issues

### 3.1. Item 1 (C1): Verification of the Stream-Coupling Argument and the Unresolved Unit-Mark `S2_narrow_short` Omission

#### A. Verification of the same-seed zero-rejection coupling argument (`reproduction/synthetic/source/generator.py`)
The authors’ source-level coupling argument in `13_s04_diagnostics.tex` (lines 2–3) is **algorithmically exact**:
* `ScalarStreams` (`generator.py`, lines 302–331) initializes 8 independent `PCG64DXSM(SeedSequence([seed, code]))` streams (`code` $0,\dots,7$).
* Immigrant candidate arrival times are generated upfront in `_immigrant_times()` (`lines 451–474`) using only `stream 0` and `(a, d, T0, horizon)`.
* For each immigrant candidate (`kind == 0`, `lines 574–590`), `_immigrant_location()` draws from `stream 1`, `_mark(2)` draws $Q$ from `stream 2`, and `u_accept = self.streams.uniform(3)` is drawn unconditionally from `stream 3`, independent of $\eta$. Since `m = raw >> 11` satisfies $1 \le m \le 2^{53}-1$, $u_{\mathrm{accept}} = m 2^{-53} \in (0, 1)$, so at $\eta = 0$, `u_accept < math.exp(0) = 1.0` always holds.
* For immigrant-only laws (`S4`, `S5`, and unit-mark `S0`–`S3`), `stream 7` (offspring acceptance) is never called (`line 603`). Offspring counts and delays (`stream 4`), locations (`stream 5`), and marks (`stream 6`) depend only on the committed `self.history` sequence.
* By induction over batches, on any immigrant-only seed where `rejected_immigrants == 0`, the committed event sequence `self.history` (and final RNG state of all 8 streams) is **bit-for-bit identical** to running the same seed with $\eta = 0$.

#### B. Remaining factual/inferential omission: `S2_narrow_short` (`410201`–`410220`) in §§13.1, 13.7, 13.11 (Table 13.5), and 14.5
While the revision fixed this for **S04B (`S4_narrow_short_imm`)**, it overlooked that the earlier **unit-mark `Narrow/short` regime (`S2_narrow_short`, seeds `410201`–`410220`)** has unit stress weights $g(Q) \equiv 1 \le e^{\gamma Q} = g_+(Q)$ and uses the **exact same generator and seed stream structure**. Running `reproduction/synthetic/source/generator.py` directly on `S2_narrow_short` for seeds `410201`–`410220`:

```python
import sys
sys.path.insert(0, "reproduction/synthetic/source")
import generator as g

for seed in range(410201, 410221):
    law = g.Law("S2_narrow_short", seed, "smooth", 0.5, 5.0, 1.0 / 24.0)
    limits = g.Limits()
    budget = g.Budget(limits)
    sim = g._Simulator(law, limits, budget, g.ScalarStreams(seed, limits, budget))
    sim.run()
    # Result: sim.counts.rejected_immigrants == 0 and rejected_offspring == 0 for ALL 20 seeds (20/20)
```

* Across all 20 seeds `410201`–`410220` of `S2_narrow_short` (2,951 proposed immigrants, 1,123 proposed offspring; including `410201` with $N_{\mathrm{train}}=99, N_{\mathrm{test}}=107$ and `410202` with $N_{\mathrm{train}}=90, N_{\mathrm{test}}=102$ in Table 13.4), **`rejected_immigrants = 0` in 20 out of 20 histories**.
* Every single history in the unit-mark `Narrow/short` regime of Table 13.4 (`410201`, `410202`) and Table 13.5 (all 20 `Narrow/short` rows of original S04) is therefore an exact sample-path realization of the uninhibited Smooth Null ($\eta=0$).
* **Locations in commit `516e5fd` that still misdescribe `S2_narrow_short` as a test of active positive inhibition:**
  * `paper/source/chapters/13_continuous_local_inhibition.tex`, line 5: *"and the narrow/short losses prevent a claim that this procedure would reliably detect inhibition when present."*
  * `paper/source/chapters/13_continuous_local_inhibition.tex`, line 234: *"Both narrow/short losses show why the observed zero-strength result cannot be read as a reliable absence test. A true positive term in the generating law need not improve this finite-sample fitted procedure's held-out score."*
  * `paper/source/chapters/13_s04_expanded.tex`, line 99: *"In original S04, gating selects the uninhibited floor throughout both null regimes, but also throughout the narrow/short positive regime. This demonstrates the sensitivity--overfitting tradeoff of this procedure on these controls..."*
  * `paper/source/chapters/14_discussion_conclusion.tex`, lines 54–56: *"Losses under narrow/short positive inhibition prevent an assertion that the procedure reliably detects inhibition whenever it exists... and shows that gating can remove null overfitting while also selecting no inhibition in the narrow/short positive regime."*

---

### 3.2. Item 2 (C2): Audit of the S04B Refitted-Floor Control (`experiments/s04b_refitted_floor/`)

* **Code & Mathematical Audit:**
  * `run.py` precomputes $u_i = e^{d x_{\mathrm{trend}}(t_i)} b_{\mathrm{bg}}(z_i) > 0$, $v_i = n H_{\mathrm{OC}}(t_i, z_i) \ge 0$, $A = \int_{t_{\mathrm{start}}}^{t_{\mathrm{end}}} e^{d(2t/T_0 - 1)}\,dt > 0$, $H = n \int_{t_{\mathrm{start}}}^{t_{\mathrm{end}}}\int_D H_{\mathrm{OC}}(t,z)\,dz\,dt \ge 0$, and $M = N\log\beta - \beta\sum_i Q_i$.
  * The training log-likelihood in $b = e^a \in [e^{-12}, 1]$ is $L(b) = \sum_{i=1}^{N_{\mathrm{train}}} \log(b u_i + v_i) - b A_{\mathrm{train}} - H_{\mathrm{train}} + M_{\mathrm{train}}$, with $L'(b) = \sum_{i=1}^{N_{\mathrm{train}}} \frac{u_i}{b u_i + v_i} - A_{\mathrm{train}}$ and $L''(b) = -\sum_{i=1}^{N_{\mathrm{train}}} \frac{u_i^2}{(b u_i + v_i)^2} < 0$.
  * Training/test separation, strict pre-event history ($t_j < t_i$), KKT endpoint checks, `brentq` root convergence (`xtol=1e-14, rtol=1e-12`), and all 480 historical floor comparisons (`max_saved_floor_absolute_difference = 6.82e-13`) were verified by independent execution.
* **Quantitative Decomposition of the Remaining $+5.1631$ (`S5`) and $+9.7367$ (`S7`) Nat Gains:**
  * In `S5` (`Immigrant: broad/long`) and `S7` (`Total: broad/long`), refitting $a$ alone improves the uninhibited floor’s mean held-out joint score by **$+43.2237$ nats** (`S5`) and **$+43.4965$ nats** (`S7`), confirming that $89.3\%$ (`S5`) and $81.7\%$ (`S7`) of the headline S04B fixed-floor gains ($+48.3868$ and $+53.2332$ nats) were comparator-mismatch artifacts from freezing $a = \log(0.2)$.
  * Why is `S7`’s residual gain ($+9.7367$ nats) still nearly double `S5`’s ($+5.1631$ nats)? Because `S7` rejects $98.2\%$ of offspring ($165/168$; $0$ offspring in $17/20$ histories), yet the intercept-only refitted floor still holds the branching ratio fixed at **$n = 0.35$**, paying a fixed mean test triggering exposure of $H_{\mathrm{test}} = 4.67$ nats on histories with almost no aftershocks.
  * Specifically, maximizing the jointly concave 2-parameter uninhibited log-likelihood $L(b, n) = \sum_i \log(b u_i + n\,\mathrm{hp}_i) - b A_{\mathrm{train}} - n E_{\mathrm{trig,train}} + M_{\mathrm{train}}$ over $(b, n) \in [e^{-12}, 1] \times [0, 0.98]$ on the exact same training sufficient statistics yields **$\hat{n} = 0.0000$ on all $20/20$ `S7` histories**, increasing the uninhibited floor’s mean held-out score improvement in `S7` from **$+43.4965$ nats to $+47.6077$ nats** and reducing the residual `LI+ total` gain in `S7` from **$+9.7367$ nats to $+5.6255$ nats** (comparable to `S5`’s $+5.1631$ nats). Because the manuscript explicitly labels §13.11.3 as a *background-intercept-only* sensitivity with $n$ fixed, this is not a correctness error in §13.11.3, but it explains half of the remaining `S7` gap.

---

### 3.3. Item 3 (C3): Audit of Proposition 5.2 and the Score-Moment Analysis

* **Proposition 5.2 (`prop:null-score-obstruction`, `05_inference.tex`, lines 95–107):**
  * The proof is mathematically sound. By conditioning only on the first arrival $(T_1 = s, Q_1 = q)$ in an early subinterval and retaining the unconditional distribution of all subsequent immigrants and descendants on $(s, T]$, it avoids the measure-tilting error that would occur if one conditioned on $\{N(T) = 1\}$.
  * Using $G_s(t)^2 \ge c\,g(q)^2$, the subcritical conditional expectation bound $\mathbb{E}_0[H_e(t)\mid T_1=s, Q_1=q] \le C(1 + \kappa(q))$, and conditional Jensen’s inequality on the convex function $x \mapsto (B(t) + n x)^{-1}$ yields $\mathbb{E}_0[\langle U_0 \rangle_T] = \infty$ whenever $\mathbb{E}[g(Q)^2/(1+\kappa(Q))] = \infty$.
  * Combined with $\mathbb{E}_0\int_0^T |K_t|\lambda_0(t)\,dt = \mathbb{E}_0\int_0^T B(t)G_s(t)\,dt < \infty$ (since $\mathbb{E}[g(Q)] < \infty$), $U_0$ is a true $L^1$-integrable compensated counting martingale whose terminal square-integrability is equivalent to $\mathbb{E}_0[\langle U_0 \rangle_T] < \infty$.
* **Distinctions verified in `05_inference.tex` (lines 123–143) and `moments.py`:**
  * Correctly distinguishes `LI+ immigrant` ($\beta(1+r) = 3.40 < 2\gamma \approx 3.4539$ in S04/S04B; $r=0 \implies \beta = 2.8494 < 2\gamma$ in S02 M2) from `LI+ total` (where $\partial_\eta \log \lambda_{\mathrm{total}} = -G_+$ has no $1/\lambda$ damping, $\mathbb{E}[g^2]=\infty$, $\mathbb{E}[g^2\kappa]=\infty$, and even the $L^1$ compensator term $\mathbb{E}[g\kappa]$ diverges since $\gamma + r\beta > \beta$).
  * Correctly distinguishes the exact null $\eta=0$ from fixed $\eta > 0$, where $x^2 e^{-\eta x} \le 4/(e^2\eta^2)$ bounds the score bracket for both immigrant-only and total attenuation.

---

### 3.4. Item 4 (C4) & Item 5 (C5): Audit of Selected Parameters, Stability Scale, and §8.6 Equivalence

* **C4 (`13_s04_diagnostics.tex`, Table 13.7 `tab:s04b-parameters` & `synthetic_diagnostics.py`):**
  * Independently re-executing `synthetic_diagnostics.py` reproduces `validation/live_results/methodological_20261106/synthetic_diagnostics.json` with identical SHA-256 (`56b6923d645fb8d89db6dfc1a48b157c7467d6a76892799458d4cb5db42e21dc`).
  * Table 13.7 accurately reports median $[\min,\max]$ of $(\hat\eta,\hat\ell,\hat\psi)$, total boundary selections $B \in [4, 18]$ out of $20$, and zero-strength selections $Z \in \{0, 1\}$, with `active_boundary = B - Z` documented in `synthetic_diagnostics.json`.
  * The explanation of Start 1 (`[0.1, log(5), log(1/24)]`) in `S4_seed410401_LI` terminating at $\hat\eta=0$ (where $\partial_\eta \mathrm{NLL}|_{\eta=0} > 0$ and $\partial_{\log\ell}\mathrm{NLL} = \partial_{\log\psi}\mathrm{NLL} = 0$ satisfy first-order constrained KKT stationarity) while Start 0 reaches a lower training NLL is mathematically accurate.
* **C5 (`03_stability.tex`, lines 60–73; `08_observed_baseline.tex`, lines 215–273; `stability.py`):**
  * Independently verified that for $v_j = 0.4j$ ($j=-97,\dots,97$) and $T = 24{,}394$ days, $-\operatorname{expm1}(-e^{0.4j}T) < 0.01$ holds for $j \in \{-97,\dots,-37\}$, which is **61 modes** (with combined normalized weight $\sum_{j=-97}^{-37} w_j = 0.00042934$), whereas $j=-26$ gives $-\operatorname{expm1}(-e^{-10.4}T) = 0.5240$ (so 72 modes satisfy $\vartheta_j T \lesssim 1$, not $<1\%$ decay).
  * Independently verified in `stability.json` that §8.6 and Stage A’s `constant_background` (`I0_raw_ml - E0_ml`) share the identical conditional intensity family and parameter box, while differing in both their training $\hat\beta$ estimator and their multi-start L-BFGS-B configuration (`4+8` starts with `ftol=1e-12, gtol=1e-7` vs. `8+8` starts with `ftol=1e-10, gtol=2e-6`).

---

## 4. Separation of Issues by Category

1. **Remaining Correctness / Disclosure Defect (Single Narrow Item):**
   * **Omission of `S2_narrow_short` (`20/20` zero-rejection histories) from the C1 disclosure:** Sections 13.1 (`13_continuous_local_inhibition.tex`, line 5), 13.7 (line 234), 13.11 (`13_s04_expanded.tex`, line 99), and 14.5 (`14_discussion_conclusion.tex`, lines 54–56) still describe the unit-mark `Narrow/short` controls (`410201`–`410220` in Table 13.4 and Table 13.5) as cases where a positive inhibition law failed to be detected or was gated off, without disclosing that **0 of 2,951 proposed immigrants were rejected across all 20 `S2_narrow_short` histories** (so all 20 histories are exact Smooth Null sample paths). Adding a two-sentence note in §§13.7 and 13.11 (just as was done for `S4_narrow_short_imm` in §13.11.1) will close this completely.
2. **Limitations of the Evaluated Model Class (Properly Disclosed, Not Correctness Errors):**
   * Common isotropic spatial scales ($\sigma, \ell$) without magnitude-dependent rupture scaling or fault-strike anisotropy (§2.5).
   * Piecewise-constant 9-cell reference weighting $b_{\mathrm{ref}}(z)$ in `OC`, `LI`, and `LI+` (§2.5, §10.7).
   * Absence of an explicit short-term aftershock incompleteness (STAI) observation model (§2.5, §6.7).
   * Intercept-only ($a$-only) refitting in the S04B comparator sensitivity (§13.11.3), which leaves $n=0.35$ fixed on `S7` where $98.2\%$ of offspring are thinned.
   * Non-stationarity of the 195-mode spectral mixture on catalogue horizons ($\vartheta_{\min} = e^{-38.8}\,\text{day}^{-1}$; §3.1).
3. **Judgments About Scientific Significance (Not Grounds for Methodological Rejection):**
   * The empirical programme is a retrospective, exploratory sequence of negative results for inhibitory point-process extensions on repeatedly inspected New Zealand and California catalogues, together with controlled synthetic sensitivity studies. Now that the comparator handicap (C2), score-moment obstructions (C3), parameter boundary hits (C4), and theorem timescales (C5) are explicitly quantified in the manuscript, the work stands as a rigorous, transparent negative-result and methodological critique of stress-depletion point-process recipes.

---

## 5. Exact Record of Executed vs. Inspected Work

### Executed Independently in Isolated Checkout (`516e5fd4877c7c7c7b7e2bbac215bfa32275a311`)
* **Artifact & custody verification:**
  * Checked SHA-256 and page counts of `paper/manuscript_unified.pdf` (229 pp.) and `companion/lay_guide_to_the_research.pdf` (8 pp.).
  * Ran `python -B scripts/verify_claims.py` (passed; 11,064 active manuscript bindings, 0 missing) and `python -B scripts/verify_repository.py` (passed; 8,692 files, 0 errors).
  * Ran `node website/check_interactions.cjs` (passed; 70 selector combinations).
  * Ran `reproduction/regional/inputs.py verify`, `reproduction/s02/inputs.py verify`, and `reproduction/historical_fits/verify.py` (all passed).
* **Methodological diagnostics & mathematical checks:**
  * Ran `python -B experiments/methodological_audit/moments.py --check` (passed).
  * Ran `python -B experiments/methodological_audit/stability.py --verify validation/live_results/methodological_20261106/stability.json` (passed).
  * Ran `python -B experiments/methodological_audit/synthetic_diagnostics.py` to a fresh external path and verified exact SHA-256 identity with `validation/live_results/methodological_20261106/synthetic_diagnostics.json`.
  * Ran `python -B scripts/check_mathematics.py` to a fresh external path (passed).
* **Full independent compilation and execution of the new C2 experiment (`experiments/s04b_refitted_floor/`):**
  * Compiled `radial.dll` via `reproduction/synthetic/native.py` using MSVC into an external temp directory.
  * Executed `experiments/s04b_refitted_floor/run.py --phase pilot` (4 seeds) and `--phase full` (all 80 seeds, 480 historical floor checks) into fresh external temp directories, followed by `summarize.py`, reproducing `validation/live_results/methodological_20261106/refitted_floor_summary.json` identically.
  * Executed an additional read-only 2-parameter concave $(b, n)$ training fit across all 80 S04B histories to quantify the effect of freeing $n$ in `S7` (`mean_delta_joint = +47.6077` nats, $\hat{n}=0$ in $20/20$ `S7` histories).
  * Executed `reproduction/synthetic/source/generator.py` in-memory on all 20 seeds (`410201`–`410220`) of `S2_narrow_short` and both seeds (`410301`, `410302`) of `S3_broad_long` to verify the unit-mark rejection counts (`0/2,951` rejected in `S2_narrow_short`).
* **Complete 273-test suite execution:**
  * Compiled native Stage 2 libraries (`temporal`, `li`, `s06`) into an external directory and executed all five test suites: `tests` (195), `reproduction/regional/tests` (44), `reproduction/s02` (6), `engine/stage2_followup/tests` with `INHIBITORY_TEST_NATIVE_ROOT` (8, 0 skips), and `engine/iteration_27/tests` with CUDA (20) — **total 273/273 passed, 0 failures, 0 errors, 0 skips**.

### Inspected Only (Not Re-Executed)
* Historical California, Japan, S02, S03, S04, S04B, and S06 multi-start optimizer campaigns and S05 conditional simulation campaigns (evaluated via their bundled fit/score records and hashes).
* Full Tectonic PDF recompilation (verified the installed PDF bytes, page count, and LaTeX source diffs directly).