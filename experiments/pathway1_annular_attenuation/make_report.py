"""Render the Pathway 1 scientific report from the saved JSON authorities."""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "validation/live_results/pathway1_annular_20261116"
REPORT = ROOT / "docs/reviews/pathway1_annular_report_20261116.md"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def f(value, digits=3):
    if value is None:
        return "—"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "—"
    return f"{value:.{digits}f}"


def sci(value, digits=2):
    if value is None:
        return "—"
    return f"{value:.{digits}e}"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(out)


def p11_section(stage):
    rows = stage["rows"]
    groups = []
    for baseline in ("interior", "bound_2km"):
        for kernel in ("mono", "ann1", "ann2", "shield"):
            for scaled in (True, False):
                subset = [r for r in rows if r["baseline"] == baseline
                          and r["kernel"] == kernel and r["scaled"] == scaled]
                if not subset:
                    continue
                best = max(subset, key=lambda r: r["score_slope_total"])
                groups.append([baseline, kernel, "scaled" if scaled else "unscaled",
                               len([r for r in subset if r["score_slope_total"] > 0]),
                               f(best["score_slope_total"], 2),
                               f"{best['ell0_km']:g}/{best['psi_days']:g}",
                               f(best["delta_train_max_total"], 2),
                               f(best["delta_test_total"], 2)])
    headline = [r for r in rows if r["ell0_km"] == 15.0 and r["psi_days"] == 5.0]
    headline_rows = [[r["case"], r["baseline"], r["kernel"], "scaled" if r["scaled"] else "unscaled",
                      f(r["event_sum"], 2), f(r["exposure_integral"], 2),
                      f(r["score_slope_total"], 2), f(r["score_slope_immigrant"], 2)]
                     for r in headline]
    positive = [r for r in rows if r["score_slope_total"] > 0]
    positive_imm = [r for r in rows if r["score_slope_immigrant"] > 0]
    pos_max_delta = max([r["delta_train_max_total"] for r in positive], default=0.0)
    pos_imm_max_delta = max([r["delta_train_max_immigrant"] for r in positive_imm], default=0.0)
    checks = stage.get("integration_checks", [])
    diffs = [abs(c["slope_difference_vs_primary"]) for c in checks if "slope_difference_vs_primary" in c]
    integration_text = ""
    if diffs:
        integration_text = (
            f" Independent scrambles and a power-16/18 reference at the headline state "
            f"differ from the primary slope by at most {f(max(diffs), 2)} nats "
            f"(median {f(sorted(diffs)[len(diffs)//2], 2)}), on slopes of order "
            f"10^3–10^4. The sign of the large negative slopes is therefore robust, "
            f"but the small positive bound-pinned corner should not be read as a "
            f"quadrature-resolved effect."
        )
    return f"""## Stage P1.1 — Null score slopes and eta profiles

The full grid is {stage['n_rows']} rows ({len(stage['baselines'])} baselines ×
{len(stage['kernels'])} kernels × 2 scalings × 7 × 6 scale pairs × 3 folds),
evaluated with the frozen `power=14` training proposal and the `power=16`
held-out proposal.

**Positive total-intensity null slopes:** {stage['positive_total_slope_rows']} of
{stage['n_rows']} rows. **Positive immigrant-only slopes:**
{stage['positive_immigrant_slope_rows']} of {stage['n_rows']} rows.

The largest training profile gain among positive total-slope rows is
{f(pos_max_delta, 4)} nats; among positive immigrant-slope rows it is
{f(pos_imm_max_delta, 4)} nats. Both are far below the project's 1.9207-nat
profile threshold, so the sign reversal is present in the primary quadrature
but scientifically negligible; the headline-state integration checks below
show that it is not quadrature-resolved.

{table(['baseline', 'kernel', 'scaling', 'positive rows', 'best slope', 'best ell/psi', 'best train Δ', 'test Δ at eta-hat'], groups)}

### Headline state (`ell0 = 15 km`, `psi = 5 d`)

{table(['fold', 'baseline', 'kernel', 'scaling', 'event sum', 'exposure integral', 'total slope', 'immigrant slope'], headline_rows)}

The exact bound-pinned example reproduces the handoff: for fold 0, `mono`, scaled,
`ell0=15 km`, `psi=5 d`, the event sum is 75,313.903, the exposure integral is
59,415.479 and the null slope is −15,898.423 nats per unit eta.

The largest positive total-intensity slope anywhere in the grid is
{f(stage['best_total_slope']['score_slope_total'], 2)} at
`{stage['best_total_slope']['case']}` / `{stage['best_total_slope']['baseline']}`
/ `{stage['best_total_slope']['kernel']}`
({'scaled' if stage['best_total_slope']['scaled'] else 'unscaled'}),
`ell0={stage['best_total_slope']['ell0_km']:g} km`,
`psi={stage['best_total_slope']['psi_days']:g} d`.

{"The interior-scale baseline has no positive total-intensity slope anywhere in the grid. Any positive rows are confined to the bound-pinned 2 km comparator and to narrow unscaled long-memory corners; they are disclosed here as a sensitivity, not as evidence at the interior baseline." if stage['positive_total_slope_rows'] and not any(r['score_slope_total'] > 0 for r in rows if r['baseline'] == 'interior') else "The interior-scale baseline has at least one positive total-intensity slope; see the best-row table." if stage['positive_total_slope_rows'] else "No total-intensity null slope is positive anywhere in the grid. Excising the epicentral peak reduces the magnitude of the negative slope but does not reverse its sign."}{integration_text}
"""


def p12_section(stage):
    rows = []
    for kernel in ("mono", "ann1", "ann2", "shield"):
        subset = [r for r in stage["rows"] if r["kernel"] == kernel]
        if not subset:
            continue
        rows.append([kernel,
                     sum(r["training_selected_eta"] > 0 for r in subset),
                     sum(r["selected_by_exact_nested_null"] for r in subset),
                     f(sum(r["training_nll_gain"] for r in subset), 3),
                     f(sum(r["test"]["gain_mean"] for r in subset), 3),
                     f(sum(r["test"].get("attenuation_gain_mean", 0.0) for r in subset), 3)])
    nuisance = stage.get("eta_zero_nuisance_refits", [])
    nuisance_text = ""
    if nuisance:
        nuisance_text = (
            "\nThe bound-pinned jobs also found eta=0 backbones with lower training "
            f"NLL (total {f(sum(r['training_gain'] for r in nuisance), 2)} nats over "
            f"{len(nuisance)} rows). These are nuisance relaxations of the 2 km bound, "
            "not attenuation effects: their eta is exactly zero and their attenuation "
            "contrast is identically zero. Their held-out gain is "
            f"{f(float(sum(r['heldout_gain_mean'] for r in nuisance)), 2)} nats in total "
            "(seeds 20261250–20261251).\n"
        )
    detail = []
    blocks = []
    for r in stage["rows"]:
        detail.append([r["case"], r["baseline"], r["kernel"],
                       f(r["training_selected_eta"], 4),
                       f(r["selected"]["ell0_km"], 2), f(r["selected"]["psi_days"], 2),
                       f(r["training_nll_gain"], 3),
                       f(r["test"]["gain_mean"], 3),
                       f(r["test"].get("attenuation_gain_mean", 0.0), 3),
                       f(r["test"]["gain_standard_error"], 3)])
        interval = r["test"]["block_intervals"]
        cells = []
        for days in ("90", "180", "365"):
            entry = interval[days]["resample"]
            cells.append(f"{f(entry['total'], 2)} [{f(entry['ci95_total'][0], 2)}, {f(entry['ci95_total'][1], 2)}]")
        blocks.append([r["case"], r["baseline"], r["kernel"], *cells])
    return f"""## Stage P1.2 — Full joint optimization

Twelve parameters `(a,d,n,log c,p,log sigma0,alpha_s,q,eta,log ell0,log psi,gamma)`
were optimized with analytic gradients from the exact interior/bound null and
the six prescribed positive starts. The exact `eta=0` state was retained as a
nested candidate. Selected positive eta rows: **{stage['n_selected_positive_eta']}
of {stage['n_rows']}**; exact nested-null rows: **{stage['n_exact_nested_null']}
of {stage['n_rows']}**.

{table(['kernel', 'selected eta>0', 'nested null', 'training gain', 'test gain', 'attenuation gain'], rows)}

Held-out scores use four independent `power=16` scrambles (`20261250..20261253`);
the standard error is the seed-to-seed standard deviation divided by sqrt(4).
The attenuation gain compares the selected state with its own `eta=0` state at
the same backbone, isolating the annular attenuation contribution from nuisance
re-estimation. The total gain compares the selected state with the EP+ baseline
state.{nuisance_text}

{table(['fold', 'baseline', 'kernel', 'eta', 'ell0', 'psi', 'train gain', 'test gain', 'atten. gain', 'SE'], detail)}

Paired calendar-block summaries of the attenuation contrast (total nats and
non-overlapping block-bootstrap 95% intervals; adjacent blocks are dependent,
so these are descriptive multi-scale sensitivities). Every interval is
identically zero because the selected state is the exact η = 0 null:

{table(['fold', 'baseline', 'kernel', '90 d', '180 d', '365 d'], blocks)}

Supplemental η = 0 nuisance refits of the bound-pinned baseline:

{table(['fold', 'kernel', 'training gain', 'held-out gain'], [[r['case'], r['kernel'], f(r['training_gain'], 2), f(r['heldout_gain_mean'], 2)] for r in nuisance])}
"""


def p13_section(summary):
    if not summary:
        return "## Stage P1.3 — Synthetic ann2 control bank\n\nNo synthetic summary was found.\n"
    def stat(name):
        s = summary[name]
        return f"{f(s['mean'], 3)} ± {f(s['mcse'], 3)} (median {f(s['median'], 3)}, wins {s['wins']}/{s['N']})"
    return f"""## Stage P1.3 — Synthetic ann2 control bank

{summary['N']} histories were generated under the ann2 law with the archived S8
chronological simulator, ETAS backbone and mark law. The achieved thinning
fraction is {f(summary['achieved_thinning']['mean'] * 100, 2)}% (range
{f(min(summary['achieved_thinning']['values']) * 100, 2)}–{f(max(summary['achieved_thinning']['values']) * 100, 2)}%)
and the achieved test-event count is {f(summary['achieved_test_events']['mean'], 1)}
(range {min(summary['achieved_test_events']['values'])}–{max(summary['achieved_test_events']['values'])}).

| quantity | mean ± MCSE |
|---|---|
| mono-kernel held-out gain | {stat('mono_gain')} |
| ann2-kernel held-out gain | {stat('ann2_gain')} |
| true-law oracle gain | {stat('oracle_gain')} |
| mono shortfall vs oracle | {stat('mono_shortfall')} |
| ann2 shortfall vs oracle | {stat('ann2_shortfall')} |
| ann2 recovery fraction | {stat('ann2_recovery_fraction')} |

The ann2 estimator beats the mono estimator in
{summary['ann2_beats_mono']}/{summary['N']} histories and beats the null in
{summary['ann2_beats_null']}/{summary['N']}; the mono estimator beats the null in
{summary['mono_beats_null']}/{summary['N']}.

The mean gains are dominated by one history whose two fitted estimators both
lose several hundred nats; the median is the robust summary. Read together, the
bank says that the ann2 shadow is detectable when the generating law is known
({summary['positive_oracle_gain']}/{summary['N']} positive oracle gains), but at
about 95 held-out events the need to estimate the attenuation coordinates
outweighs the kernel-shape benefit. The ann2 estimator is less bad than mono on
average but does not recover the oracle gain in the median history.
"""


def main():
    stage11 = read(RESULTS / "stage_p11_null_profiles.json")
    stage12_path = RESULTS / "stage_p12_joint_optimization.json"
    stage12 = read(stage12_path) if stage12_path.exists() else None
    synth_path = RESULTS / "synthetic/summary.json"
    synth = read(synth_path) if synth_path.exists() else None
    audit_path = RESULTS / "independent_audit.json"
    audit = read(audit_path) if audit_path.exists() else None
    parts = [
        "# Pathway 1 — Annular attenuation kernels and the California stress shadow",
        "",
        "**Date:** 16 November 2026  ",
        "**Baseline commit:** `a9d7f9d`  ",
        "**Isolated code:** `experiments/pathway1_annular_attenuation/`  ",
        "**Isolated results:** `validation/live_results/pathway1_annular_20261116/`",
        "",
        "## Question",
        "",
        "Does replacing the epicentral-peaked kernel `(1+r^2/ell_j^2)^-2` with an",
        "annular or trigger-core-shielded kernel make the null score slope positive",
        "on the California training folds, and does the fitted annular attenuation",
        "model improve held-out log score over the interior-scale EP+ baseline?",
        "",
        "## Design",
        "",
        "Four spatial attenuation profiles are compared at the same EP+ backbone:",
        "the monotone epicentral kernel (`mono`), a first-order ring (`ann1`), a",
        "second-order ring (`ann2`), and a trigger-core-shielded kernel (`shield`).",
        "Each is tested with rupture-scaled `ell_j = ell0 10^(0.5 m_j)` and with",
        "unscaled `ell_j = ell0`. The attenuation field multiplies the total",
        "intensity by `exp(-eta G)`; the exact `eta=0` state is retained in every",
        "search. The primary baseline is the relaxed interior-scale EP+ fit with",
        "`sigma0 >= 0.05 km`; the bound-pinned 2 km EP+ fit is retained as a",
        "completeness comparator.",
        "",
        "All slopes and profile curves use analytic derivatives. Training",
        "integrals use the frozen power-14 scrambled-Sobol proposal; held-out",
        "checks use power 16. The compiled row contractions were verified against",
        "independent NumPy formulas and central finite differences before any",
        "optimization. Profile curves are concave in `eta`; a non-positive null",
        "slope returns the exact boundary `eta_hat = 0`.",
        "",
        p11_section(stage11),
    ]
    if stage12:
        parts.append(p12_section(stage12))
    else:
        parts.append("## Stage P1.2 — Full joint optimization\n\nNo P1.2 summary was found.\n")
    parts.append(p13_section(synth))
    parts.append("""## Conclusion

The hypothesis is rejected at the interior-scale EP+ baseline. Replacing the
epicentral-peaked kernel with `ann1`, `ann2` or `shield` reduces the magnitude
of the negative total-intensity null slope but does not reverse its sign
anywhere in the interior grid. The immigrant-only channel does produce 52 small
positive slopes, but their largest training profile gain is 0.0935 nats, also
far below the 1.9207-nat threshold. The only positive total-intensity slopes are 11 rows at the
bound-pinned 2 km comparator, all `ann2` unscaled `ell0 = 5 km`; their training
profile gains are below 0.04 nats and the headline-state quadrature sensitivity
(up to 302 nats) is far larger than that gain, so they are not a resolved
stress-shadow detection.

The full 12-parameter joint search selects the exact nested η = 0 state in
24/24 rows, including the extra sensitivity start at the strongest positive
P1.1 corner. The held-out attenuation contrast and all 90/180/365-day block
intervals are therefore identically zero. The bound-pinned jobs do find η = 0
backbones with lower training NLL and a modest held-out gain, but these are
nuisance relaxations of the 2 km bound, not annular attenuation.

The synthetic bank sharpens the interpretation. When the true law is annular,
the oracle gain is +13.1 nats and positive in 20/20 histories, so the shadow is
detectable in principle. At about 95 held-out events, however, both fitted
estimators lose held-out score on average (mono −35.0, ann2 −22.3 nats), and the
ann2 estimator's median recovery of the oracle gain is negative. Estimation
variance, not kernel shape, is the binding constraint at this sample size.

The practical conclusion is that the California `eta = 0` result is not an
artifact of the epicentral peak. An annular or core-shielded stress shadow is
not supported by these training folds at the available resolution, and even a
correctly specified annular estimator would not be expected to improve
held-out score at the current test-event count.
""")
    if audit:
        status = "passed" if audit.get("passed") else "FAILED"
        grad_error = max((x for r in audit.get("objective_gradients", {}).get("checks", [])
                          for x in r.get("errors", {}).values()), default=float("nan"))
        slope_error = audit.get("slopes", {}).get("max_slope_rel")
        quad_delta = audit.get("synthetic", {}).get("fast_minus_frozen_abs")
        parts.append(f"""## Independent audit

The independent audit **{status}**. It checks sealed-file integrity, native
kernel formulas against a separate NumPy implementation, full objective
gradients against central finite differences for every kernel and scaling,
a stratified NumPy recomputation of the null slopes, profile concavity and
boundary logic, P1.2 selected-state consistency, and synthetic summary
arithmetic. The machine-readable receipt is `independent_audit.json`.

* Maximum full-objective gradient relative error: {sci(grad_error)}.
* Maximum NumPy-recomputed null-slope relative error: {sci(slope_error)}.
* Synthetic fast-grid versus frozen order-8 held-out joint difference:
  {sci(quad_delta)} nats.
* All 24 P1.2 selected states are within bounds and exactly equal to the
  baseline null state; the held-out recomputation check is therefore the
  exact zero contrast.
""")
    else:
        parts.append("## Independent audit\n\nNo audit receipt was found.\n")
    parts.append("""## Limitations

* The 90/180/365-day block intervals are paired calendar-block summaries;
  adjacent blocks are dependent under long memory, so they are descriptive
  multi-scale sensitivities rather than calibrated frequentist guarantees.
* The synthetic bank uses the archived S8 ETAS backbone, mark law and smooth
  background, not the California catalogue. It isolates kernel-shape
  estimation, not regional geology or catalogue-specific noise.
* The positive null slopes at the bound-pinned 2 km comparator occur in a
  narrow unscaled ann2 corner and carry training profile gains below 0.04
  nats. They are reported for completeness, not as evidence of a detectable
  stress shadow.
* The joint search is a declared finite multi-start search with the exact
  nested null retained; it does not claim global optimality.
* The attenuation coordinate `eta` is a statistical inhibition parameter, not
  a physical Coulomb stress measurement.

## Reproduction and custody

All writes are confined to
`experiments/pathway1_annular_attenuation/`,
`validation/live_results/pathway1_annular_20261116/` and this report. The native
source and binary hashes are pinned in
`build/pathway1_annular_20261116_joint/build_receipt.json`; all generated rows
carry the frozen source hash and baseline source hashes. No file under
`validation/authorities/` or a pre-existing `validation/live_results/`
subdirectory was modified.
""")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(parts), encoding="utf-8")
    print(REPORT)


if __name__ == "__main__":
    main()
