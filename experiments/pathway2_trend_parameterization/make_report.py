"""Render the Pathway 2 report from the audited result summaries."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "validation/live_results/pathway2_trend_controls_20261116"
REPORT = ROOT / "docs/reviews/pathway2_trend_report_20261116.md"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def f(x, digits=3):
    if x is None:
        return "---"
    return f"{x:.{digits}f}"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return "\n".join(out)


def main():
    merged = read(BASE / "summary.json") if (BASE / "summary.json").exists() else {"stages": {}}
    s8 = merged["stages"].get("s8")
    s04 = merged["stages"].get("s04b")
    nz = merged["stages"].get("nz")
    ca = merged["stages"].get("california")
    audit = read(BASE / "independent_audit.json") if (BASE / "independent_audit.json").exists() else None

    lines = []
    lines.append("# Pathway 2 — stationary, origin-clamped and orthogonalised background laws")
    lines.append("")
    lines.append("**Date:** 16 November 2026  ")
    lines.append("**Baseline commit:** `a9d7f9d`  ")
    lines.append("**Code:** `experiments/pathway2_trend_parameterization/`  ")
    lines.append("**Results:** `validation/live_results/pathway2_trend_controls_20261116/`")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    if s8:
        t0 = s8["by_law"]["T0"]
        lines.append(
            f"- **S8, seed 410840.** The archived T0 overfitting loss is "
            f"`{f(t0['overfitting_loss']['mean'])}` nats on average (maximum "
            f"`{f(t0['overfitting_loss']['maximum'])}`, seed 410840). Under T1/T2/T3 the "
            f"mean is `{f(s8['by_law']['T1']['overfitting_loss']['mean'])}` / "
            f"`{f(s8['by_law']['T2']['overfitting_loss']['mean'])}` / "
            f"`{f(s8['by_law']['T3']['overfitting_loss']['mean'])}` and the maximum is "
            f"`{f(s8['by_law']['T1']['overfitting_loss']['maximum'])}` / "
            f"`{f(s8['by_law']['T2']['overfitting_loss']['maximum'])}` / "
            f"`{f(s8['by_law']['T3']['overfitting_loss']['maximum'])}`. Seed 410840 falls "
            f"from `{f(s8['seed_410840']['t0']['overfitting_loss'])}` to "
            f"`{f(s8['seed_410840']['laws']['T1']['overfitting_loss'])}` / "
            f"`{f(s8['seed_410840']['laws']['T2']['overfitting_loss'])}` / "
            f"`{f(s8['seed_410840']['laws']['T3']['overfitting_loss'])}`.")
        lines.append(
            f"- **S8 estimation loss.** The mean falls from "
            f"`{f(t0['estimation_loss']['mean'])}` nats under T0 to "
            f"`{f(s8['by_law']['T1']['estimation_loss']['mean'])}` / "
            f"`{f(s8['by_law']['T2']['estimation_loss']['mean'])}` / "
            f"`{f(s8['by_law']['T3']['estimation_loss']['mean'])}` under T1/T2/T3. The "
            f"median held-out gain is `{f(t0['heldout_gain']['median'])}` under T0, "
            f"`{f(s8['by_law']['T1']['heldout_gain']['median'])}` under T1, "
            f"`{f(s8['by_law']['T2']['heldout_gain']['median'])}` under T2 and "
            f"`{f(s8['by_law']['T3']['heldout_gain']['median'])}` under T3.")
    if s04:
        worst = s04["worst_t0_cases"][0]
        lines.append(
            f"- **S04B tails are not trend-driven.** The worst archived-T0 case "
            f"`{worst['case_id']}` has T0 `{f(worst['T0'], 2)}` nats and remains "
            f"`{f(worst['T1'], 2)}` / `{f(worst['T2'], 2)}` under T1/T2.")
    if nz:
        lines.append(
            f"- **New Zealand.** T1 improves the three-fold shared-attenuation deficit from "
            f"`{f(nz['totals']['T0'])}` to `{f(nz['totals']['T1'])}` nats, while T2/T3 give "
            f"`{f(nz['totals']['T2'])}` / `{f(nz['totals']['T3'])}`. On Fold 1 the clamped "
            f"arms reproduce the sealed non-refit counterfactual because the training "
            f"likelihood is invariant to the clamp.")
    if ca:
        tot = ca["totals"]
        lines.append(
            f"- **California EP+.** The interior total gain is `{f(tot['T0'])}` nats under "
            f"T0 and `{f(tot['T1'])}` / `{f(tot['T2'])}` / `{f(tot['T3'])}` under T1/T2/T3.")
    lines.append("")
    lines.append("## 1. Question and definitions")
    lines.append("")
    lines.append("The archived background is `B(t) = exp(a + d x_trend(t))` with "
                 "`x_trend(t) = 2t/T0 - 1`. Because `x_trend` is normalised by the whole "
                 "catalogue horizon, early training windows sit on the negative branch and "
                 "the held-out window sits on the positive branch. A positive fitted `d` is "
                 "therefore extrapolated exponentially. The Pathway 2 handoff replaces this "
                 "clock with three forecast-admissible laws, applied identically to the "
                 "uninhibited and inhibited arms:")
    lines.append("")
    lines.append("| id | clock / background | free trend? |")
    lines.append("|---|---|---|")
    lines.append("| T0 | `2t/T0 - 1` (archived) | yes |")
    lines.append("| T1 | stationary, `d = 0` | no |")
    lines.append("| T2 | `x_clamp(t) = min{0, (t - T_origin)/(T_origin - T_start)}` | yes, but zero future |")
    lines.append("| T3 | T2 clock plus training-orthogonalised `G` | yes, but zero future |")
    lines.append("| D* | conditional true-trend control, `d = 0.2` | frozen at truth |")
    lines.append("")
    lines.append("Primary contrasts: the uninhibited comparator overfitting loss "
                 "`l_test(a_hat, theta_star,0,-a) - l_test(theta_hat_0)`, the inhibited "
                 "estimation loss `l_test(theta_hat_1) - l_test(theta_star)`, and the paired "
                 "held-out gain `l_test(theta_hat_1) - l_test(theta_hat_0)`.")
    lines.append("")
    lines.append("## 2. Guardrails and numerical checks")
    lines.append("")
    lines.append("All writes are confined to the isolated code and result paths. The audit "
                 "re-hashes every pre-existing `validation/authorities/` and "
                 "`validation/live_results/` file against `MANIFEST.json`; no sealed file was "
                 "modified. The T0 replay reproduces every sealed S8 null and inhibited "
                 "held-out score; the analytic background integrals are checked against "
                 "adaptive quadrature; the native deficit recurrence is checked against a "
                 "direct NumPy fixture with and without orthogonalisation; and all eight "
                 "analytic gradients are checked against central finite differences.")
    lines.append("")
    if audit:
        lines.append(f"**Audit verdict:** {'PASS' if audit['passed'] else 'FAIL'} "
                     f"({len(audit['checks'])} checks; failed: {audit['failed'] or 'none'}).")
        lines.append("")
    lines.append("## 3. S8 moderate control (20 histories)")
    lines.append("")
    if s8:
        headers = ["arm", "overfitting loss", "estimation loss", "held-out gain",
                   "BIC-gated gain", "gate active", "eta RMSE"]
        rows = []
        for law in ("T0", "T1", "T2", "T3", "DSTAR"):
            v = s8["by_law"][law]
            rows.append([law, f(v["overfitting_loss"]["mean"]), f(v["estimation_loss"]["mean"]),
                         f(v["heldout_gain"]["mean"]),
                         f(v["bic_gated_gain"]["mean"]),
                         f"{v['bic_gate_active']}/20",
                         f(v["fitted_eta"]["rmse_vs_true"])])
        lines.append(table(headers, rows))
        lines.append("")
        lines.append("The BIC gate uses the archived `1.5 log N_train` threshold on the "
                     "fine training scores and returns the exact null when the threshold is "
                     "not met. It is a sensitivity, not a replacement for the raw contrast: "
                     "under it T0/T2/T3 retain 12/20 active alternatives with gated mean gains "
                     "of 2.50/2.13/1.70 nats, while T1 activates only 3/20 and its gated mean "
                     "falls to 0.98. T1's raw advantage is therefore concentrated in fits that "
                     "the BIC gate would not select.")
        lines.append("")
        eta_bits = []
        for law in ("T0", "T1", "T2", "T3", "DSTAR"):
            v = s8["by_law"][law]["fitted_eta"]
            eta_bits.append(f"{law} mean {v['mean']:.3f}, median {v['median']:.3f}, "
                            f"IQR [{v['q25']:.3f}, {v['q75']:.3f}], RMSE {v['rmse_vs_true']:.3f}")
        lines.append("Fitted `eta` recovery against `eta_star = 0.4`: " + "; ".join(eta_bits) +
                     ". T1 has the lowest RMSE but a strongly zero-inflated median; T2/T3 track "
                     "the archived T0 distribution.")
        lines.append("")
        lines.append("Paired changes against T0 (mean, MCSE):")
        lines.append("")
        rows = []
        for law in ("T1", "T2", "T3", "DSTAR"):
            v = s8["deltas_vs_t0"][law]
            rows.append([law, f(v["overfitting_loss_change"]["mean"]),
                         f(v["overfitting_loss_change"]["mcse"]),
                         f(v["estimation_loss_change"]["mean"]),
                         f(v["estimation_loss_change"]["mcse"]),
                         f(v["gain_change"]["mean"]), f(v["gain_change"]["mcse"])])
        lines.append(table(["arm", "d overfitting", "MCSE", "d estimation", "MCSE",
                            "d gain", "MCSE"], rows))
        lines.append("")
        seed = s8["seed_410840"]
        lines.append("**Seed 410840.** T0 overfitting loss "
                     f"`{f(seed['t0']['overfitting_loss'])}`, estimation loss "
                     f"`{f(seed['t0']['estimation_loss'])}`. Under T1/T2/T3 the overfitting "
                     f"loss is `{f(seed['laws']['T1']['overfitting_loss'])}` / "
                     f"`{f(seed['laws']['T2']['overfitting_loss'])}` / "
                     f"`{f(seed['laws']['T3']['overfitting_loss'])}` and the estimation loss "
                     f"is `{f(seed['laws']['T1']['estimation_loss'])}` / "
                     f"`{f(seed['laws']['T2']['estimation_loss'])}` / "
                     f"`{f(seed['laws']['T3']['estimation_loss'])}`.")
        lines.append("")
        lines.append(f"Maximum T0 replay discrepancy: null train "
                     f"`{s8['t0_reproduction_max_abs']['null_train']:.2e}`, null test "
                     f"`{s8['t0_reproduction_max_abs']['null_test']:.2e}`, inhibited test "
                     f"`{s8['t0_reproduction_max_abs']['inhibited_test']:.2e}` nats.")
        lines.append("")
        lines.append("**Trade-off.** T1 has the best mean overfitting and estimation losses and "
                     "the best eta RMSE, but its worst single-seed overfitting loss is "
                     f"`{f(s8['by_law']['T1']['overfitting_loss']['maximum'])}` nats "
                     "(seed 410825) and its median held-out gain is only "
                     f"`{f(s8['by_law']['T1']['heldout_gain']['median'])}`. T2/T3 have a "
                     "slightly worse mean but a smaller worst case "
                     f"(`{f(s8['by_law']['T2']['overfitting_loss']['maximum'])}` on seed "
                     "410840) and a median gain close to the archived T0 value. The choice "
                     "therefore depends on whether the criterion is the mean, the median or "
                     "the worst case.")
        lines.append("")
    lines.append("## 4. S04B tail-outlier evaluation (80 histories)")
    lines.append("")
    if s04:
        rows = []
        for regime in ("4", "5", "6", "7"):
            for law in ("T0", "T1", "T2"):
                v = s04["by_regime"][regime][law]
                rows.append([regime, law, f(v["mean"]), f(v["median"]), f(v["minimum"]),
                             f(v["q05"]), f(v["q25"]), f(v["q95"]),
                             str(v["n_lt_minus_50"]), str(v["n_lt_minus_100"])])
        lines.append(table(["regime", "law", "mean", "median", "min", "q05", "q25", "q95",
                            "n<-50", "n<-100"], rows))
        lines.append("")
        lines.append("Worst archived-T0 cases and their refitted gains:")
        lines.append("")
        lines.append(table(["case", "regime", "T0", "T1", "T2"],
                           [[r["case_id"], r["regime"], f(r["T0"], 2), f(r["T1"], 2), f(r["T2"], 2)]
                            for r in s04["worst_t0_cases"]]))
        lines.append("")
        worst = s04["worst_t0_cases"][0]
        lines.append(f"The largest archived tail, `{worst['case_id']}`, is "
                     f"`{f(worst['T0'], 2)}` nats under T0, `{f(worst['T1'], 2)}` under T1 and "
                     f"`{f(worst['T2'], 2)}` under T2. Its selected inhibition coordinates are "
                     "essentially identical across the three laws. The S4/S5 tails are "
                     "therefore not background-trend extrapolation events; they are "
                     "inhibition-parameter overfitting. T1 repairs the S6 case "
                     "`S6_narrow_short_total_seed410606` from -178.40 to -5.23 nats, but "
                     "worsens several other S6 tails, and T2 worsens that same case to -221.59. "
                     "The regime-level means improve under T1 for S6 and S7, but the extreme "
                     "negative tail survives.")
        diag = s04.get("trend_diagnostic")
        if diag:
            lines.append("")
            lines.append("The archived fitted trend is essentially uncorrelated with the "
                         f"held-out gain across the 80 histories (null `d`: "
                         f"`{diag['corr_t0_null_d_gain']:.3f}`; inhibited `d`: "
                         f"`{diag['corr_t0_inhibited_d_gain']:.3f}`). The ten worst T0 gains "
                         "also span both signs of `d`. This is direct evidence that the tail "
                         "is not a trend-extrapolation effect.")
        lines.append("")
    lines.append("## 5. New Zealand three-fold controls")
    lines.append("")
    if nz:
        rows = []
        for fold in ("fold_50", "fold_65", "fold_80"):
            v = nz["folds"][fold]
            rows.append([fold, f(v["T0"]), f(v["T1"]), f(v["T2"]), f(v["T3"])])
        rows.append(["total", f(nz["totals"]["T0"]), f(nz["totals"]["T1"]),
                     f(nz["totals"]["T2"]), f(nz["totals"]["T3"])])
        lines.append(table(["fold", "T0 free d", "T1 stationary", "T2 clamp", "T3 orth+clamp"], rows))
        lines.append("")
        lines.append("The sealed fixed-null and zero-trend controls are "
                     f"`{f(nz['totals']['fixed_null_trend'])}` and "
                     f"`{f(nz['totals']['zero_trend'])}` nats. T1 coincides with the sealed "
                     "zero-trend fit. On Fold 1 the T2 and T3 values coincide with the sealed "
                     "clamped counterfactual because, with `T0 = 2 T_origin`, the clamped clock "
                     "is identical to the archived clock on the training window; the training "
                     "likelihood cannot identify the test-window level, so a refit returns the "
                     "same maximum-likelihood state.")
        lines.append("")
    lines.append("## 6. California interior EP+ baseline")
    lines.append("")
    if ca:
        rows = []
        for r in ca["rows"]:
            rows.append([r["case"], f(r["T0"]), f(r["T1"]), f(r["T2"]), f(r["T3"]),
                         f(r["t1_minus_t0"]), f(r["t2_minus_t0"]), f(r["t3_minus_t0"])])
        lines.append(table(["fold", "T0", "T1", "T2", "T3", "T1-T0", "T2-T0", "T3-T0"], rows))
        lines.append("")
        lines.append(f"Totals: T0 `{f(ca['totals']['T0'])}`, T1 `{f(ca['totals']['T1'])}`, "
                     f"T2 `{f(ca['totals']['T2'])}`, T3 `{f(ca['totals']['T3'])}` nats.")
        lines.append("")
        lines.append("All three folds select `eta_hat = 0` on the training attenuation profile "
                     "at the fixed `(ell0, psi)` grid, so the T3 residualisation has no "
                     "inhibited-arm effect; the T2 and T3 rows are identical by construction. "
                     "The T0 evaluator reproduces the sealed interior plane-normalised test "
                     "joint score exactly (offset 0.0 on every fold); the interior total gain "
                     "is 77.056 nats, distinct from the bound-pinned 69.55-nat total. The "
                     "paired law differences are on the same fixed Sobol proposal.")
        lines.append("")
    lines.append("## 7. Interpretation")
    lines.append("")
    lines.append("- **T1 removes the trend channel entirely.** It eliminates the fitted `d` "
                 "and the trend--depletion collinearity, and it is the only synthetic arm that "
                 "cannot manufacture a positive future slope. Its cost is a misspecified "
                 "background when the generating trend is real.")
    lines.append("- **T2 and T3 remove future extrapolation but not in-sample trend fitting.** "
                 "They are therefore forecast-admissible. They do not uniformly improve "
                 "held-out performance: on S8 the paired gain change is mixed, and on New "
                 "Zealand Fold 1 the clamped arm is worse than the archived free trend because "
                 "the positive extrapolation was, in that sample, beneficial. This is a "
                 "negative result for the hypothesis that clamping alone recovers the loss.")
    lines.append("- **The S04B tail outliers** are the clearest test. T1 and T2 are compared "
                 "with the archived T0 tails at the same 80 histories and the same fixed "
                 "spatial/mark laws.")
    lines.append("- **California EP+** improves under T1 by several nats on every fold, while "
                 "T2/T3 give smaller improvements. The improvement is a null-backbone effect, "
                 "not an attenuation effect, because the profile selects zero attenuation in "
                 "all folds.")
    lines.append("")
    lines.append("## 8. What changed against the handoff expectation")
    lines.append("")
    lines.append("1. **The S8 blow-up hypothesis is supported.** Seed 410840's +75.28-nat "
                 "overfitting loss is a trend-extrapolation event. Removing the positive future "
                 "clock collapses it to +2.58 (T1), +10.07 (T2/T3) and +1.10 (conditional true "
                 "trend). The mean S8 estimation loss falls by 8.0-8.8 nats. Under the BIC "
                 "gate, however, T1 activates only 3/20 alternatives and its gated mean gain "
                 "falls to 0.98, while T2 retains 12/20 and a gated mean of 2.13. T2 is the "
                 "best compromise between tail control and gate-supported gain.")
    lines.append("2. **The S04B tail hypothesis is not supported for the largest S4/S5 "
                 "outliers.** The worst case (`S4_narrow_short_imm_seed410415`, -592.90 nats) "
                 "is -593.00 under T1 and -590.08 under T2. Its fitted inhibition parameters "
                 "are essentially unchanged across laws. Those tails are inhibition-parameter "
                 "overfitting, not background-trend extrapolation. T1 does repair most of the "
                 "S6 and S7 median, but not the single worst S6 case.")
    lines.append("3. **The New Zealand clamped counterfactual is not merely a non-refit "
                 "illustration.** On Fold 1, `T0 = 2 T_origin`, so the clamped clock is "
                 "identical to the archived clock on the training window. The training "
                 "likelihood is invariant and the refit returns the same state: the proper "
                 "T2 fit is the -24.791-nat counterfactual. T1 is the only law that improves "
                 "the three-fold New Zealand deficit.")
    lines.append("4. **California EP+ favours T1, not T2.** The interior total gain rises from "
                 "77.06 to 87.74 nats under T1, but only to 79.40 under T2/T3. The attenuation "
                 "profile selects eta=0 in every fold, so T3 is observationally identical to "
                 "T2 there.")
    lines.append("")
    lines.append("## 9. Caveats")
    lines.append("")
    lines.append("1. The S8/S04B refits use a frozen tensor-Gauss fast plan for optimisation "
                 "and the archived adaptive plan (S8) or a high-order fast plan (S04B) for the "
                 "reported scores. The maximum scored quadrature difference is recorded in the "
                 "audit and the S8 summary.")
    lines.append("2. The S8 true-trend control is conditional: an unrestricted `d = 0.2` "
                 "refit develops a `p -> 2.5, n -> 0` overfitting ridge on several histories "
                 "(seed 410821 is documented in `s8/full_dstar_diagnostic.json`), so the control "
                 "fixes the archived T0 trigger nuisance in both arms. The unrestricted-refit "
                 "instability is itself a finite-sample finding.")
    lines.append("3. The New Zealand fits hold the archived per-fold trigger/stress kernels "
                 "and productivity ratio fixed, as in the sealed trend controls. They are not "
                 "a new kernel search.")
    lines.append("4. The California EP+ evaluation uses one fixed Sobol test proposal and a "
                 "three-point `(ell0, psi)` profile grid. The T0 evaluator reproduces the "
                 "sealed interior baseline exactly on that proposal; the absolute interior "
                 "total is 77.056 nats, not the bound-pinned 69.55-nat total.")
    lines.append("5. These are conditional synthetic and regional procedure comparisons, not "
                 "physical inhibition claims, global optima or prospective forecast validation.")
    lines.append("")
    lines.append("## 10. Appendix: S8 per-history contrasts")
    lines.append("")
    if s8:
        rows = []
        for row in s8["rows"]:
            t0 = row["t0"]
            vals = [str(row["seed"]), f(t0["overfitting_loss"], 2), f(t0["estimation_loss"], 2),
                    f(t0["fitted_gain"], 2)]
            for law in ("T1", "T2", "T3"):
                x = row["laws"][law]
                vals += [f(x["overfitting_loss"], 2), f(x["estimation_loss"], 2),
                         f(x["heldout_gain"], 2)]
            rows.append(vals)
        lines.append(table(["seed", "T0 over", "T0 est", "T0 gain",
                            "T1 over", "T1 est", "T1 gain",
                            "T2 over", "T2 est", "T2 gain",
                            "T3 over", "T3 est", "T3 gain"], rows))
        lines.append("")
    lines.append("## 11. Reproduction")
    lines.append("")
    lines.append("```powershell")
    lines.append("python -m experiments.pathway2_trend_parameterization.run_s8 --workers 6")
    lines.append("python -m experiments.pathway2_trend_parameterization.run_s04b --workers 6")
    lines.append("python -m experiments.pathway2_trend_parameterization.run_nz")
    lines.append("python -m experiments.pathway2_trend_parameterization.run_ca --workers 2")
    lines.append("python -m experiments.pathway2_trend_parameterization.audit_pathway2")
    lines.append("python -m experiments.pathway2_trend_parameterization.build_summary")
    lines.append("python -m experiments.pathway2_trend_parameterization.make_report")
    lines.append("```")
    lines.append("")
    lines.append("All commands are run from the repository root. No sealed authority or "
                 "pre-existing live-result file is written.")
    lines.append("")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
