"""Render Track B manuscript fragments and emit their typed numeric claims.

Every displayed scalar is produced from an explicit JSON pointer in a Track B
authority.  The adapter writes only generated manuscript fragments and a claims
file; it never edits a sealed authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import verify_claims as V

BASE = ROOT / "validation/live_results/track_b_controls_20261112"
B1 = BASE / "epplus_ablation"
NZ = BASE / "nz_trend_controls"
B3 = BASE / "profiles_and_power"
OUT = ROOT / "paper/source/chapters"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Claims:
    def __init__(self):
        self.rows = []

    def add(self, source, pointer, display, locations, component, transform=None):
        path = Path(source)
        data = read(path)
        raw = V.resolve(data, pointer)
        c = dict(id="track-b-20261112-" + str(len(self.rows) + 1).zfill(3),
                 bundled_source=path.relative_to(ROOT).as_posix(),
                 source_path=path.relative_to(ROOT).as_posix(), source_sha256=sha(path),
                 json_pointer=pointer, resolved_source_value=raw, display=str(display),
                 transformation=transform if transform else "decimal rounding to displayed precision",
                 json_value_kind="numeric_scalar", ledger_role="manuscript_binding",
                 final_display_locations=list(locations), component=component,
                 qualification="Deterministic Track B control output; frozen inputs and explicit JSON pointer.",
                 status="source_bound", binding_kind="exact_json_pointer",
                 reconciliation_status="verified_at_declared_granularity")
        c["value"] = V.transformed(raw, c, data)
        if not V.equal_display(c["value"], c):
            raise ValueError(("display does not round from source", c["id"], raw, display))
        self.rows.append(c)
        return str(display)


def f(value, places):
    return f"{float(value):.{places}f}"


def n(value):
    return str(int(value))


def scientific(value):
    exponent = int(math.floor(math.log10(abs(value))))
    mantissa = value / (10 ** exponent)
    return f"${mantissa:.2f}\\times10^{{{exponent}}}$", f"{mantissa:.2f}e{exponent}"


def build_b1(claims):
    data = read(B1 / "ablation.json")
    relax = read(B1 / "sigma0_relaxation.json")
    frozen = read(B1 / "sigma0_relaxation_frozen.json")
    profile = read(B1 / "sigma0_profile.json")
    loc = "chapters/11_epplus_ablation.tex"
    arms = data["arms"]
    short_names = {"A0": "EP archived", "A1": "Joint rect, unw", "A2": "Joint plane, unw",
                   "A3": "Joint rect, decl", "A4": "Joint plane, decl",
                   "A5": "Scaled rect, unw", "A6": "Scaled plane, unw",
                   "A7": "Scaled rect, decl", "A8": "Scaled plane, decl"}
    rows = []
    for arm_id in ("A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"):
        arm = arms[arm_id]
        name = short_names[arm_id]
        norm = "rect" if arm["normalization"] == "rect" else "plane"
        kde = "decl" if arm["weighted"] else "unw"
        scale = "free" if arm["scaled"] else "fixed"
        cells = []
        for j in range(3):
            cell = claims.add(B1 / "ablation.json", f"/arms/{arm_id}/fold_gains/{j}", f(arm["fold_gains"][j], 4), [loc],
                              f"{arm_id} F{j} gain over archived EP", None)
            cells.append(cell)
        total = claims.add(B1 / "ablation.json", f"/arms/{arm_id}/total_gain", f(arm["total_gain"], 4), [loc],
                           f"{arm_id} three-fold gain over archived EP", None)
        rows.append(f"{arm_id} & {norm} & {kde} & {scale} & " + " & ".join(cells) + f" & {total} \\\\")
    table = "\n".join([
        r"\begin{table}[htbp]\centering\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}llllrrrr@{}}\toprule",
        r"Arm & Norm. & KDE & $\alpha_s$ & F0 & F1 & F2 & Total\\\midrule",
        *rows,
        r"\bottomrule\end{tabular}",
        r"\caption{Component ablation of the magnitude-scaled ETAS procedure, in held-out nats relative to archived EP. Positive values favour the new procedure. A0 is the archived EP score; A1--A8 form a balanced $2\times2\times2$ factorial over rectangle versus full-plane normalization, unweighted versus five-step training-declustered KDE background, and fixed versus free magnitude scaling, all with joint temporal--spatial fitting except A0. Columns abbreviate normalization (rect/plane), KDE (unw/decl) and magnitude scaling (fixed/free). Each arm uses the same histories, fertility weights and common mark measure.}",
        r"\label{tab:epplus-ablation}",
        r"\end{table}"])
    shapley = data["factorial"]["shapley"]
    sequential = data["factorial"]["sequential_A0_A1_A2_A4_A8"]
    comp_rows = []
    joint = claims.add(B1 / "ablation.json", "/factorial/joint_fit_minus_archived_EP", f(data["factorial"]["joint_fit_minus_archived_EP"], 3), [loc], "Joint temporal--spatial fitting increment A0 to A1")
    comp_rows.append(f"Joint fitting (A0$\\to$A1) & --- & {joint} \\\\")
    for key, label, index in [("normalization", "Full-plane normalization", 1),
                              ("declustering", "Training declustering", 2),
                              ("scaling", "Magnitude scaling", 3)]:
        sh = claims.add(B1 / "ablation.json", f"/factorial/shapley/{key}", f(shapley[key], 3), [loc], f"Shapley contribution of {label}")
        seq = claims.add(B1 / "ablation.json", f"/factorial/sequential_A0_A1_A2_A4_A8/{index}", f(sequential[index], 3), [loc], f"Sequential contribution of {label}")
        comp_rows.append(f"{label} & {sh} & {seq} \\\\")
    total = claims.add(B1 / "ablation.json", "/factorial/closure_A8_minus_A0", f(data["factorial"]["closure_A8_minus_A0"], 3), [loc], "Total A8 minus A0 gain")
    comp_rows.append(f"Total (A8$-$A0) & {total} & {total} \\\\")
    ftable = "\n".join([
        r"\begin{table}[htbp]\centering\small",
        r"\begin{tabular}{@{}lrr@{}}\toprule",
        r"Component & Shapley (nats) & Sequential (nats)\\\midrule",
        *comp_rows,
        r"\bottomrule\end{tabular}",
        r"\caption{Additive decomposition of the $69.553$-nat A8$-$A0 gain. Shapley values average every order of the three procedural factors and sum exactly with the joint-fitting increment; the sequential column follows A0$\to$A1$\to$A2$\to$A4$\to$A8.}",
        r"\label{tab:epplus-factorial}",
        r"\end{table}"])
    # Sigma0 relaxation, plane and rectangle rows.
    relax_rows = []
    for i, row in enumerate(relax["rows"]):
        if row["normalization"] != "plane":
            continue
        cells = [claims.add(B1 / "sigma0_relaxation.json", f"/rows/{i}/sigma0", f(row["sigma0"], 3), [loc], f"{row['case']} relaxed sigma0"),
                 claims.add(B1 / "sigma0_relaxation.json", f"/rows/{i}/alpha_s", f(row["alpha_s"], 3), [loc], f"{row['case']} relaxed alpha_s"),
                 claims.add(B1 / "sigma0_relaxation.json", f"/rows/{i}/q", f(row["q"], 3), [loc], f"{row['case']} relaxed q"),
                 claims.add(B1 / "sigma0_relaxation.json", f"/rows/{i}/gain_over_EP", f(row["gain_over_EP"], 3), [loc], f"{row['case']} relaxed test gain")]
        fold_label = {"california_fold_0": "F0", "california_fold_1": "F1", "california_fold_2": "F2"}[row["case"]]
        relax_rows.append(f"{fold_label} & " + " & ".join(cells) + r" \\")
    for i, row in enumerate(frozen["rows"]):
        if row["normalization"] != "plane":
            continue
        cells = [claims.add(B1 / "sigma0_relaxation_frozen.json", f"/rows/{i}/sigma0", f(row["sigma0"], 3), [loc], f"{row['case']} frozen-weight sigma0"),
                 claims.add(B1 / "sigma0_relaxation_frozen.json", f"/rows/{i}/alpha_s", f(row["alpha_s"], 3), [loc], f"{row['case']} frozen-weight alpha_s"),
                 claims.add(B1 / "sigma0_relaxation_frozen.json", f"/rows/{i}/q", f(row["q"], 3), [loc], f"{row['case']} frozen-weight q"),
                 claims.add(B1 / "sigma0_relaxation_frozen.json", f"/rows/{i}/gain_over_EP", f(row["gain_over_EP"], 3), [loc], f"{row['case']} frozen-weight test gain")]
        fold_label = {"california_fold_0": "F0", "california_fold_1": "F1", "california_fold_2": "F2"}[row["case"]]
        relax_rows.append(f"{fold_label} (frozen KDE) & " + " & ".join(cells) + r" \\")
    rtable = "\n".join([
        r"\begin{table}[htbp]\centering\small",
        r"\begin{tabular}{@{}lrrrr@{}}\toprule",
        r"Fold/weights & $\widehat\sigma_0$ (km) & $\widehat\alpha_s$ & $\widehat q$ & Test gain (nats)\\\midrule",
        *relax_rows,
        r"\bottomrule\end{tabular}",
        r"\caption{Relaxed lower bound $\sigma_0\geq0.05$~km, full-plane normalization. The first three rows rerun five-step training declustering under the relaxed bound; the last three hold the accepted EP+ background weights fixed. Every fit remains training-only and every test score uses the common mark measure.}",
        r"\label{tab:sigma0-relaxation}",
        r"\end{table}"])
    # Profile curve, plane, all folds.
    sigma_grid = profile["grid_km"]
    head_cells = []
    for j, s in enumerate(sigma_grid):
        head_cells.append(claims.add(B1 / "sigma0_profile.json", f"/grid_km/{j}", f(s, 2), [loc],
                                     f"Profile grid sigma0 value {j}"))
    head = " & ".join(head_cells)
    prow = []
    for i, row in enumerate(profile["rows"]):
        if row["normalization"] != "plane":
            continue
        cells = []
        for j, point in enumerate(row["curve"]):
            cells.append(claims.add(B1 / "sigma0_profile.json", f"/rows/{i}/curve/{j}/training_nll",
                                     f(point["training_nll"], 2), [loc], f"{row['case']} profile nll at sigma0 {sigma_grid[j]} km"))
        fold_label = {"california_fold_0": "F0", "california_fold_1": "F1", "california_fold_2": "F2"}[row["case"]]
        prow.append(f"{fold_label} & " + " & ".join(cells) + r" \\")
    ptable = "\n".join([
        r"\begin{table}[htbp]\centering",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{@{}l" + "r" * len(sigma_grid) + r"@{}}\toprule",
        r"Fold & " + head + r"\\\midrule",
        *prow,
        r"\bottomrule\end{tabular}}",
        r"\caption{Training negative log-likelihood at fixed $\sigma_0$ (km), with $(a,d,n,c,p,\alpha_s,q)$ re-optimized at each point, full-plane normalization and accepted EP+ background weights. Lower values are better.}",
        r"\label{tab:sigma0-profile}",
        r"\end{table}"])
    lower = claims.add(B1 / "ablation.json", "/sigma0_lower_bound_km", f(2.0, 3), [loc], "Original lower search bound in km")
    relaxed_lower = claims.add(B1 / "ablation.json", "/sigma0_relaxed_lower_km", f(0.05, 3), [loc], "Relaxed lower search bound in km")
    difference = claims.add(B1 / "ablation.json", "/arms/A8/total_gain", f(arms["A8"]["total_gain"] - arms["A7"]["total_gain"], 3), [loc], "A8 minus A7 total gain",
                            dict(operation="difference", operand_pointers=["/arms/A8/total_gain", "/arms/A7/total_gain"]))
    relaxed_plane = [(i, r) for i, r in enumerate(relax["rows"]) if r["normalization"] == "plane"]
    b1 = claims.add(B1 / "sigma0_relaxation.json", f"/rows/{relaxed_plane[0][0]}/sigma0", f(relaxed_plane[0][1]["sigma0"], 3), [loc], "F0 relaxed sigma0")
    b2 = claims.add(B1 / "sigma0_relaxation.json", f"/rows/{relaxed_plane[1][0]}/sigma0", f(relaxed_plane[1][1]["sigma0"], 3), [loc], "F1 relaxed sigma0")
    b3 = claims.add(B1 / "sigma0_relaxation.json", f"/rows/{relaxed_plane[2][0]}/sigma0", f(relaxed_plane[2][1]["sigma0"], 3), [loc], "F2 relaxed sigma0")
    total_relax = claims.add(B1 / "sigma0_relaxation.json", "/total_gain_plane", f(relax["total_gain_plane"], 3), [loc], "Three-fold full-plane relaxed-bound test gain")
    total_frozen = claims.add(B1 / "sigma0_relaxation_frozen.json", "/total_gain_plane", f(frozen["total_gain_plane"], 3), [loc], "Three-fold full-plane frozen-weight relaxed-bound test gain")
    text = "\n".join([
        r"\subsubsection{Component ablation and the spatial-scale boundary}\label{sec:epplus-ablation}",
        r"The $69.553$-nat EP+ gain is not primarily a normalization effect. The balanced factorial gives Shapley contributions of "
        + claims.add(B1 / "ablation.json", "/factorial/shapley/declustering", f(shapley["declustering"], 2), [loc], "Declustering Shapley contribution")
        + r"~nats for training declustering, "
        + claims.add(B1 / "ablation.json", "/factorial/shapley/scaling", f(shapley["scaling"], 2), [loc], "Scaling Shapley contribution")
        + r"~nats for magnitude scaling, "
        + claims.add(B1 / "ablation.json", "/factorial/shapley/normalization", f(shapley["normalization"], 3), [loc], "Normalization Shapley contribution")
        + r"~nats for full-plane versus rectangle normalization, and "
        + joint + r"~nats for joint temporal--spatial fitting (Table~\ref{tab:epplus-factorial}). The rectangle-normalized analogue A7 reaches "
        + claims.add(B1 / "ablation.json", "/arms/A7/total_gain", f(arms["A7"]["total_gain"], 3), [loc], "A7 total gain")
        + r"~nats, so common-space normalization changes the total by "
        + difference
        + r"~nats.",
        r"",
        r"The original lower bound of " + lower + r"~km is binding in every accepted fit. Releasing it to " + relaxed_lower + r"~km selects interior scales of "
        + b1 + r", " + b2 + r" and " + b3 + r"~km under full-plane normalization, with $\widehat\alpha_s$ near eight tenths (Table~\ref{tab:sigma0-relaxation}). The three-fold test gain rises to "
        + total_relax + r"~nats when the background is redeclustered under the relaxed bound, and to "
        + total_frozen + r"~nats when the accepted EP+ weights are held fixed. The fixed-$\sigma_0$ profile curves in Table~\ref{tab:sigma0-profile} confirm an interior training minimum rather than a boundary one; the earlier boundary was therefore a search-box artefact, not a likelihood maximum.",
        r"",
        table, r"", ftable, r"", rtable, r"", ptable])
    (OUT / "11_epplus_ablation.tex").write_text(text + "\n", encoding="utf-8")


def build_b2(claims):
    data = read(NZ / "summary.json")
    loc = "chapters/08_nz_trend_controls.tex"
    rows = []
    labels = {"fold_50": "F0", "fold_65": "F1", "fold_80": "F2"}
    for fold_name in ("fold_50", "fold_65", "fold_80"):
        fold = data["folds"][fold_name]
        for key, label in [("archived", "Free $d$"), ("fixed_null_trend", "Fixed null $d$"), ("zero_trend", "Zero $d$")]:
            if key == "archived":
                pars = fold["archived"]["ml_shared"]["record"]["pars"]
                held = fold["archived"]["heldout"]
            else:
                pars = fold["controls"][key]["inhibited"]["training"]["parameters"]
                held = fold["controls"][key]["heldout"]
            cells = [labels[fold_name], label]
            for j in range(4):
                pointer = (f"/folds/{fold_name}/archived/ml_shared/record/pars/{j}" if key == "archived"
                           else f"/folds/{fold_name}/controls/{key}/inhibited/training/parameters/{j}")
                cells.append(claims.add(NZ / "summary.json", pointer, f(pars[j], 3), [loc],
                                        f"{fold_name} {label} parameter {j}"))
            pointer = (f"/folds/{fold_name}/archived/heldout/training_delta_loglik" if key == "archived"
                       else f"/folds/{fold_name}/controls/{key}/heldout/training_delta_loglik")
            cells.append(claims.add(NZ / "summary.json", pointer, f(held["training_delta_loglik"], 3), [loc],
                                    f"{fold_name} {label} training gain"))
            for component in ("delta_Q", "delta_C", "delta_joint"):
                pointer = (f"/folds/{fold_name}/archived/heldout/{component}" if key == "archived"
                           else f"/folds/{fold_name}/controls/{key}/heldout/{component}")
                cells.append(claims.add(NZ / "summary.json", pointer, f(held[component], 3), [loc],
                                        f"{fold_name} {label} held-out {component}"))
            rows.append(" & ".join(cells) + r" \\")
    table = "\n".join([
        r"\begin{table}[htbp]\centering\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}llrrrrrrrr@{}}\toprule",
        r"Fold & Control & $a$ & $d$ & $n$ & $\eta$ & $\Delta\ell_{\rm tr}$ & $\Delta Q$ & $\Delta C$ & $\Delta\ell$\\\midrule",
        *rows,
        r"\bottomrule\end{tabular}",
        r"\caption{New Zealand trend--depletion controls. Free $d$ reproduces the archived fits. Fixed null $d$ freezes the uninhibited \texttt{ml\_trigger} trend while fitting $(a,n,\eta)$; the zero-trend row fits $(a,n,\eta)$ with a zero linear trend and the archived productivity ratio and kernels. Training and held-out entries are nats; held-out $\Delta\ell=\Delta Q+\Delta C$ and the common mark cancels.}",
        r"\label{tab:nz-trend-controls}",
        r"\end{table}"])
    fold1 = data["folds"]["fold_50"]["attribution"]
    text = "\n".join([
        r"\subsection{Trend--depletion controls in the first New Zealand fold}\label{sec:nz-trend-controls}",
        r"The first fold accounts for "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/archived_loss", f(fold1["archived_loss"], 3), [loc], "Fold 1 archived loss")
        + r"~nats of the "
        + claims.add(NZ / "summary.json", "/totals/archived_loss", f(data["totals"]["archived_loss"], 3), [loc], "Pooled archived loss")
        + r"~nat shared-attenuation deficit. A matched zero-trend fit reduces the first-fold loss to "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/zero_trend_loss", f(fold1["zero_trend_loss"], 3), [loc], "Fold 1 zero-trend loss")
        + r"; freezing the uninhibited trend reduces it further to "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/fixed_null_trend_loss", f(fold1["fixed_null_trend_loss"], 3), [loc], "Fold 1 fixed-null loss")
        + r". Relative to the free fit, the zero-trend and fixed-null controls therefore remove "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/trend_extrapolation_fraction_zero", f(100 * fold1["trend_extrapolation_fraction_zero"], 1), [loc], "Fold 1 zero-trend removed fraction", dict(operation="multiply", factor=100))
        + r"\% and "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/trend_extrapolation_fraction_fixed_null", f(100 * fold1["trend_extrapolation_fraction_fixed_null"], 1), [loc], "Fold 1 fixed-null removed fraction", dict(operation="multiply", factor=100))
        + r"\% of the deficit, leaving a detrended residual of "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/zero_trend_loss", f(fold1["zero_trend_loss"], 3), [loc], "Fold 1 detrended residual")
        + r"~nats. The positive fitted trend, not depletion alone, accounts for most of the original first-fold loss. The clamped-clock counterfactual is not a refit and produces a "
        + claims.add(NZ / "summary.json", "/folds/fold_50/attribution/clamped_loss", f(fold1["clamped_loss"], 3), [loc], "Fold 1 clamped-clock counterfactual loss")
        + r"~nat loss; it is reported only to show that removing positive extrapolation without re-estimating the intercept is not an admissible control.",
        r"",
        r"The middle fold's zero-trend fit selects the zero boundary and is tied at displayed precision, while the late fold retains a small positive strength. These two folds do not support the same attribution as the first fold. The autonomous zero-trend comparison in Table~\ref{tab:autonomous-nz} remains a separate fitted procedure with a different nuisance treatment.",
        table])
    (OUT / "08_nz_trend_controls.tex").write_text(text + "\n", encoding="utf-8")


def build_b3(claims):
    data = read(B3 / "s8_oracle.json")
    prof = read(B3 / "california_eta_profiles.json")
    mde = read(B3 / "mde.json")
    loc = "chapters/13_s8_oracle.tex"
    rows = []
    for key, label in [("oracle_gain_vs_fixed", "True vs fixed true-backbone null"),
                       ("oracle_gain_vs_intercept", "True vs refitted-intercept null"),
                       ("oracle_gain_vs_joint_null", "True vs jointly fitted null"),
                       ("estimation_loss", "Fitted inhibited minus true"),
                       ("fitted_gain", "Fitted inhibited minus fitted null")]:
        stat = data[key]
        cells = [label]
        for field in ("mean", "median", "sample_sd", "mcse"):
            cells.append(claims.add(B3 / "s8_oracle.json", f"/{key}/{field}", f(stat[field], 3), [loc], f"S8 {label} {field}"))
        cells.append(claims.add(B3 / "s8_oracle.json", f"/{key}/wins", n(stat["wins"]), [loc], f"S8 {label} wins"))
        rows.append(" & ".join(cells) + r" \\")
    table = "\n".join([
        r"\begin{table}[htbp]\centering\small",
        r"\begin{tabular}{@{}lrrrrr@{}}\toprule",
        r"Contrast & Mean & Median & SD & MCSE & Wins\\\midrule",
        *rows,
        r"\bottomrule\end{tabular}",
        r"\caption{S8 oracle ceiling and estimation loss over the twenty histories, in nats. The true law uses the S8 moderate attenuation parameter and the same fixed mark and spatial laws as the fitted procedure. The jointly fitted null is the actual comparator; the fixed and intercept-refitted nulls separate nuisance adaptation from attenuation. MCSE is the sample standard deviation divided by the square root of the history count.}",
        r"\label{tab:s8-oracle}",
        r"\end{table}"])
    text = "\n".join([
        r"\subsubsection{Oracle ceiling and estimation loss}\label{sec:s8-oracle}",
        r"An oracle that knows the generating attenuation parameters but not the nuisance backbone achieves a mean held-out gain of "
        + claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_joint_null/mean", f(data["oracle_gain_vs_joint_null"]["mean"], 2), [loc], "S8 oracle gain mean")
        + r"~nats over the jointly fitted null (median "
        + claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_joint_null/median", f(data["oracle_gain_vs_joint_null"]["median"], 2), [loc], "S8 oracle gain median")
        + r", MCSE "
        + claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_joint_null/mcse", f(data["oracle_gain_vs_joint_null"]["mcse"], 2), [loc], "S8 oracle gain MCSE")
        + r"). Against a fixed true-backbone null the mean is "
        + claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_fixed/mean", f(data["oracle_gain_vs_fixed"]["mean"], 2), [loc], "S8 fixed-null oracle gain")
        + r"~nats, and against an intercept-refitted null it is "
        + claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_intercept/mean", f(data["oracle_gain_vs_intercept"]["mean"], 2), [loc], "S8 intercept-null oracle gain")
        + r"~nats. The fitted procedure captures only "
        + claims.add(B3 / "s8_oracle.json", "/fitted_gain/mean", f(data["fitted_gain"]["mean"], 3), [loc], "S8 fitted gain mean")
        + r"~nats on average; its mean estimation loss relative to the oracle is "
        + claims.add(B3 / "s8_oracle.json", "/estimation_loss/mean", f(data["estimation_loss"]["mean"], 2), [loc], "S8 estimation loss mean")
        + r"~nats (median "
        + claims.add(B3 / "s8_oracle.json", "/estimation_loss/median", f(data["estimation_loss"]["median"], 2), [loc], "S8 estimation loss median")
        + r", MCSE "
        + claims.add(B3 / "s8_oracle.json", "/estimation_loss/mcse", f(data["estimation_loss"]["mcse"], 2), [loc], "S8 estimation loss MCSE")
        + r"). The bottleneck is parameter estimation, not the absence of a true generating effect.",
        table])
    (OUT / "13_s8_oracle.tex").write_text(text + "\n", encoding="utf-8")

    # California eta profiles.
    eloc = "chapters/11_epplus_eta_profiles.tex"
    rows = []
    scale_labels = {}
    for index, pair in enumerate(prof["scale_pairs"]):
        ell_text = claims.add(B3 / "california_eta_profiles.json", f"/scale_pairs/{index}/ell_km",
                              f(pair["ell_km"], 0), [eloc], f"Scale pair {index} ell0 km")
        psi_text = claims.add(B3 / "california_eta_profiles.json", f"/scale_pairs/{index}/psi_days",
                              f(pair["psi_days"], 0), [eloc], f"Scale pair {index} psi days")
        scale_labels[f"ell{pair['ell_km']:g}_psi{pair['psi_days']:g}"] = f"{ell_text}/{psi_text}"
    for i, row in enumerate(prof["rows"]):
        for key, fixed in row["fixed_backbone"].items():
            fold_label = {"california_fold_0": "F0", "california_fold_1": "F1", "california_fold_2": "F2"}[row["case"]]
            cells = [fold_label, scale_labels[key]]
            for field in ("training_score_slope_at_zero", "eta95_upper", "s8_eta_test_gain"):
                pointer = f"/rows/{i}/fixed_backbone/{key}/{field}"
                if field == "eta95_upper":
                    if math.isinf(fixed[field]):
                        cells.append("beyond grid")
                    elif abs(fixed[field]) < 1e-3:
                        tex, display = scientific(fixed[field])
                        claims.add(B3 / "california_eta_profiles.json", pointer, display,
                                   [eloc], f"{row['case']} {key} {field}")
                        cells.append(tex)
                    else:
                        cells.append(claims.add(B3 / "california_eta_profiles.json", pointer,
                                                f(fixed[field], 3), [eloc], f"{row['case']} {key} {field}"))
                else:
                    cells.append(claims.add(B3 / "california_eta_profiles.json", pointer,
                                            f(fixed[field], 4), [eloc], f"{row['case']} {key} {field}"))
            rows.append(" & ".join(cells) + r" \\")
    etable = "\n".join([
        r"\begin{table}[htbp]\centering\scriptsize",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{@{}llrrr@{}}\toprule",
        r"Fold & $\ell/\psi$ (km, d) & Slope at zero & $\eta_{\rm upper}$ & $\Delta\ell_{\rm test}(\eta_{\rm S8})$\\\midrule",
        *rows,
        r"\bottomrule\end{tabular}",
        r"\caption{California EP+ attenuation slices at the uninhibited training MLE. The slope is the one-sided training score derivative at zero; $\eta_{\rm upper}$ is where the training profile falls by the one-sided threshold; the last column is the held-out contrast at the S8 moderate parameter. Positive last-column values favour attenuation.}",
        r"\label{tab:california-eta-profiles}",
        r"\end{table}"])
    def profiled_bound(index, label):
        value = prof["rows"][index]["profiled_s8_scale"]["eta95_upper"]
        tex, display = scientific(value)
        claims.add(B3 / "california_eta_profiles.json", f"/rows/{index}/profiled_s8_scale/eta95_upper",
                   display, [eloc], label)
        return tex

    ptext = "\n".join([
        r"\subsubsection{California attenuation profile and upper bounds}\label{sec:california-eta-profiles}",
        r"At the S8 moderate scale pair, the training profile places the one-sided ninety-five per cent upper bound on $\eta$ at "
        + profiled_bound(0, "F0 profiled eta95")
        + r", " + profiled_bound(1, "F1 profiled eta95")
        + r" and " + profiled_bound(2, "F2 profiled eta95")
        + r" in F0, F1 and F2 after re-optimizing $(a,d,n)$ at each fixed attenuation. The corresponding held-out contrast at the S8 parameter is "
        + claims.add(B3 / "california_eta_profiles.json", "/rows/0/profiled_s8_scale/s8_eta_test_gain", f(prof["rows"][0]["profiled_s8_scale"]["s8_eta_test_gain"], 2), [eloc], "F0 S8-parameter test gain")
        + r", " + claims.add(B3 / "california_eta_profiles.json", "/rows/1/profiled_s8_scale/s8_eta_test_gain", f(prof["rows"][1]["profiled_s8_scale"]["s8_eta_test_gain"], 2), [eloc], "F1 S8-parameter test gain")
        + r" and " + claims.add(B3 / "california_eta_profiles.json", "/rows/2/profiled_s8_scale/s8_eta_test_gain", f(prof["rows"][2]["profiled_s8_scale"]["s8_eta_test_gain"], 2), [eloc], "F2 S8-parameter test gain")
        + r"~nats. The fixed-backbone grid in Table~\ref{tab:california-eta-profiles} shows that the upper bound and test contrast depend strongly on the spatial and temporal scales; the S8 pair is not a universal detection threshold. The training bounds lie far below the S8 generating value, so under the EP+ kernel and the California training windows the zero boundary is strongly selected rather than a flat-direction artefact. The large negative held-out contrasts at that value are model-specific consequences of the same amplitude, not estimates of a physical stress-shadow strength.",
        etable])
    (OUT / "11_epplus_eta_profiles.tex").write_text(ptext + "\n", encoding="utf-8")

    # MDE table.
    mloc = "chapters/14_power_and_mde.tex"
    mrows = []
    for i, region in enumerate(mde["rows"]):
        label = {"NZ_shared_minus_ML": "New Zealand", "CA_EPplus_minus_original_EP": "California",
                 "Japan_OC_minus_EP_joint": "Japan"}[region["region"]]
        for day_index, days in enumerate(("90", "180", "365")):
            block = region["block_days"][days]
            day_display = claims.add(B3 / "mde.json", f"/block_lengths/{day_index}", days, [mloc],
                                     f"Block length {days} days")
            cells = [label, day_display,
                     claims.add(B3 / "mde.json", f"/rows/{i}/block_days/{days}/se_total_nats", f(block["se_total_nats"], 2), [mloc], f"{label} {days}-day SE"),
                     claims.add(B3 / "mde.json", f"/rows/{i}/block_days/{days}/mde95_total_nats", f(block["mde95_total_nats"], 2), [mloc], f"{label} {days}-day MDE95"),
                     claims.add(B3 / "mde.json", f"/rows/{i}/block_days/{days}/mde95_nats_per_event", f(block["mde95_nats_per_event"], 4), [mloc], f"{label} {days}-day MDE95 per event"),
                     claims.add(B3 / "mde.json", f"/rows/{i}/block_days/{days}/required_rate_perturbation", f(100 * block["required_rate_perturbation"], 1), [mloc], f"{label} {days}-day required rate perturbation", dict(operation="multiply", factor=100))]
            mrows.append(" & ".join(cells) + r" \\")
    block90 = claims.add(B3 / "mde.json", "/block_lengths/0", "90", [mloc], "Primary block length in days")
    confidence = claims.add(B3 / "mde.json", "/confidence_percent", "95", [mloc], "Two-sided confidence level in percent")
    ep_total = claims.add(B1 / "ablation.json", "/factorial/closure_A8_minus_A0", f(69.55289384226876, 3), [mloc], "EP+ three-fold gain")
    s8_mean = claims.add(B3 / "s8_oracle.json", "/fitted_gain/mean", f(data["fitted_gain"]["mean"], 3), [mloc], "S8 fitted mean gain")
    mtable = "\n".join([
        r"\begin{table}[htbp]\centering\small",
        r"\begin{tabular}{@{}llrrrr@{}}\toprule",
        r"Region & Block (d) & $\mathrm{SE}_B$ (nats) & $\mathrm{MDE}_{95}$ (nats) & $\mathrm{MDE}_{95}$/event & Required $\delta$ (\%)\\\midrule",
        *mrows,
        r"\bottomrule\end{tabular}",
        r"\caption{Minimum detectable effects at two-sided ninety-five per cent for regional total held-out scores. The final column is the fractional rate perturbation $\delta=\Delta\lambda/\lambda$ satisfying a quadratic small-perturbation score approximation. New Zealand and California use paired calendar-block scores; Japan uses the between-window standard error of three annual fold totals, repeated at each block label and not a calendar-block bootstrap. Contiguous dependent blocks are descriptive dependence-scale units, not independent replications.}",
        r"\label{tab:mde}",
        r"\end{table}"])
    mtext = "\n".join([
        r"\subsection{Minimum detectable effects and the power of the negative result}\label{sec:mde}",
        r"The regional score scales differ sharply. At " + block90 + r"-day blocks the two-sided " + confidence + r" per cent minimum detectable effect is "
        + claims.add(B3 / "mde.json", "/rows/0/block_days/90/mde95_total_nats", f(mde["rows"][0]["block_days"]["90"]["mde95_total_nats"], 2), [mloc], "NZ 90-day MDE95")
        + r"~nats in New Zealand, "
        + claims.add(B3 / "mde.json", "/rows/1/block_days/90/mde95_total_nats", f(mde["rows"][1]["block_days"]["90"]["mde95_total_nats"], 2), [mloc], "CA 90-day MDE95")
        + r"~nats in California and "
        + claims.add(B3 / "mde.json", "/rows/2/block_days/90/mde95_total_nats", f(mde["rows"][2]["block_days"]["90"]["mde95_total_nats"], 2), [mloc], "Japan 90-day MDE95")
        + r"~nats in Japan. The "
        + claims.add(B3 / "mde.json", "/rows/0/block_days/90/se_nats_per_event", f(mde["rows"][0]["block_days"]["90"]["se_nats_per_event"], 4), [mloc], "NZ per-event SE")
        + r"~nat-per-event New Zealand scale is much finer than the "
        + claims.add(B3 / "mde.json", "/rows/1/block_days/90/se_nats_per_event", f(mde["rows"][1]["block_days"]["90"]["se_nats_per_event"], 4), [mloc], "CA per-event SE")
        + r"~nat-per-event California scale because California's block scores are more dispersed. The completed EP+ gain of " + ep_total + r"~nats is of the same order as one California " + block90 + r"-day MDE, while the S8 raw mean of " + s8_mean + r"~nats is far below its own MCSE. These calculations delimit what the negative and positive summaries can detect; they do not convert a non-significant contrast into evidence of physical absence.",
        mtable])
    (OUT / "14_power_and_mde.tex").write_text(mtext + "\n", encoding="utf-8")


def build_abstract_claims(claims):
    loc = "abstract.tex"
    ablation = read(B1 / "ablation.json")
    relax = read(B1 / "sigma0_relaxation.json")
    frozen = read(B1 / "sigma0_relaxation_frozen.json")
    profile = read(B1 / "sigma0_profile.json")
    nz = read(NZ / "summary.json")
    s8 = read(B3 / "s8_oracle.json")
    mde = read(B3 / "mde.json")
    claims.add(B1 / "ablation.json", "/factorial/closure_A8_minus_A0", f(ablation["factorial"]["closure_A8_minus_A0"], 2), [loc], "Abstract EP+ total gain")
    for key, places in (("declustering", 2), ("scaling", 2), ("normalization", 2)):
        claims.add(B1 / "ablation.json", f"/factorial/shapley/{key}", f(ablation["factorial"]["shapley"][key], places), [loc], f"Abstract {key} Shapley contribution")
    claims.add(B1 / "ablation.json", "/factorial/joint_fit_minus_archived_EP", f(ablation["factorial"]["joint_fit_minus_archived_EP"], 2), [loc], "Abstract joint-fit increment")
    claims.add(B1 / "ablation.json", "/sigma0_lower_bound_km", f(2.0, 0), [loc], "Abstract original sigma0 lower bound")
    claims.add(B1 / "ablation.json", "/sigma0_relaxed_lower_km", f(0.05, 2), [loc], "Abstract relaxed sigma0 lower bound")
    relaxed_plane = [r for r in relax["rows"] if r["normalization"] == "plane"]
    lower_row = min(relaxed_plane, key=lambda r: r["sigma0"])
    frozen_plane = [r for r in frozen["rows"] if r["normalization"] == "plane"]
    upper_row = max(frozen_plane, key=lambda r: r["sigma0"])
    claims.add(B1 / "sigma0_relaxation.json", f"/rows/{relax['rows'].index(lower_row)}/sigma0", f(lower_row["sigma0"], 2), [loc], "Abstract lower interior sigma0")
    claims.add(B1 / "sigma0_relaxation_frozen.json", f"/rows/{frozen['rows'].index(upper_row)}/sigma0", f(upper_row["sigma0"], 2), [loc], "Abstract upper interior sigma0")
    claims.add(B1 / "sigma0_relaxation.json", "/total_gain_plane", f(relax["total_gain_plane"], 2), [loc], "Abstract relaxed redeclustered total gain")
    claims.add(B1 / "sigma0_relaxation_frozen.json", "/total_gain_plane", f(frozen["total_gain_plane"], 2), [loc], "Abstract relaxed frozen-weight total gain")
    fold1 = nz["folds"]["fold_50"]["attribution"]
    claims.add(NZ / "summary.json", "/folds/fold_50/attribution/archived_loss", f(fold1["archived_loss"], 2), [loc], "Abstract NZ Fold 1 loss")
    claims.add(NZ / "summary.json", "/folds/fold_50/attribution/zero_trend_loss", f(fold1["zero_trend_loss"], 2), [loc], "Abstract NZ zero-trend residual")
    claims.add(NZ / "summary.json", "/folds/fold_50/attribution/fixed_null_trend_loss", f(fold1["fixed_null_trend_loss"], 2), [loc], "Abstract NZ fixed-null residual")
    for key, factor in (("trend_extrapolation_fraction_zero", 100), ("trend_extrapolation_fraction_fixed_null", 100)):
        claims.add(NZ / "summary.json", f"/folds/fold_50/attribution/{key}", f(factor * fold1[key], 1), [loc], f"Abstract NZ {key}", dict(operation="multiply", factor=100))
    claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_joint_null/mean", f(s8["oracle_gain_vs_joint_null"]["mean"], 2), [loc], "Abstract S8 oracle mean")
    claims.add(B3 / "s8_oracle.json", "/oracle_gain_vs_joint_null/mcse", f(s8["oracle_gain_vs_joint_null"]["mcse"], 2), [loc], "Abstract S8 oracle MCSE")
    claims.add(B3 / "s8_oracle.json", "/fitted_gain/mean", f(s8["fitted_gain"]["mean"], 2), [loc], "Abstract S8 fitted mean")
    claims.add(B3 / "s8_oracle.json", "/estimation_loss/mean", f(-s8["estimation_loss"]["mean"], 2), [loc], "Abstract S8 estimation-loss magnitude", dict(operation="negate"))
    claims.add(B3 / "mde.json", "/block_lengths/0", "90", [loc], "Abstract primary block length")
    claims.add(B3 / "mde.json", "/confidence_percent", "95", [loc], "Abstract confidence level")
    for i in range(3):
        claims.add(B3 / "mde.json", f"/rows/{i}/block_days/90/mde95_total_nats", f(mde["rows"][i]["block_days"]["90"]["mde95_total_nats"], 2), [loc], f"Abstract MDE95 region {i}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "track_b_numeric_claims.json")
    args = parser.parse_args()
    claims = Claims()
    build_b1(claims)
    build_b2(claims)
    build_b3(claims)
    build_abstract_claims(claims)
    for location in ("chapters/11_epplus_ablation.tex", "chapters/11_epplus_eta_profiles.tex",
                     "chapters/08_nz_trend_controls.tex", "chapters/13_s8_oracle.tex",
                     "chapters/14_power_and_mde.tex"):
        text = (ROOT / "paper/source" / location).read_text(encoding="utf-8")
        displayed = V.manuscript_numbers(text)
        covered = {V.numeric_value(c["display"]) for c in claims.rows if location in c["final_display_locations"]}
        missing = sorted(displayed - covered)
        if missing:
            raise ValueError(("unbound numeric literals", location, [str(v) for v in missing]))
    payload = dict(schema="track_b_numeric_claims_v1", claims=claims.rows,
                   generated_from=[(p.relative_to(ROOT).as_posix(), sha(p)) for p in
                                   (B1 / "ablation.json", B1 / "sigma0_relaxation.json",
                                    B1 / "sigma0_relaxation_frozen.json", B1 / "sigma0_profile.json",
                                    NZ / "summary.json", B3 / "s8_oracle.json",
                                    B3 / "california_eta_profiles.json", B3 / "mde.json")])
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(claims=len(claims.rows), output=args.output.resolve().relative_to(ROOT).as_posix()), indent=2))


if __name__ == "__main__":
    main()
