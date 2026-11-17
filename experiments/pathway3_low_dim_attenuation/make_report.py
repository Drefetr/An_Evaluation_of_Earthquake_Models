"""Generate the Pathway 3 Markdown report from the archived JSON results."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway3_low_dim_attenuation import common as C

LADDER_ORDER = (
    ("S1_fixed_backbone_a_eta", "Step 1: fixed true backbone, fit (a, eta) at (ell*, psi*)"),
    ("S2_fixed_backbone_a_eta_ell_psi", "Step 2: fixed true backbone, fit (a, eta, ell, psi)"),
    ("S3a_stat_null_a_n_eta_true_scale", "Step 3a: stationary null backbone, profile (a, n, eta) at true scale"),
    ("S3b_stat_null_a_n_eta_grid", "Step 3b: stationary null backbone, (a, n, eta) with 3-scale selection"),
    ("E1D_Profile_2p", "E1D_Profile_2p: (a, eta) + 3-scale selection"),
    ("E1D_Profile_3p", "E1D_Profile_3p: (a, n, eta) + 3-scale selection"),
    ("E_Split_CV", "E_Split_CV: chronological split shrinkage"),
    ("E_L1_Shrinkage", "E_L1_Shrinkage: split-selected lambda"),
    ("Free_7D_stationary", "Free 7-parameter stationary fit"),
    ("WC_Rupture_2p", "E_WC_Rupture sensitivity on S8"),
    ("Free_8D_archived", "Archived free 8-parameter fit"),
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def f(x, digits=2):
    if x is None:
        return "n/a"
    if abs(x) < 0.5 * 10 ** (-digits):
        x = 0.0
    return f"{x:.{digits}f}"


def pct(x):
    return f"{100.0 * x:.1f}%"


def main():
    summary = read(C.OUT / "summary.json")
    audit = read(C.OUT / "independent_audit.json")
    s8 = summary["s8_by_arm"]
    winner = summary["winning_estimator"]
    name = winner["name"]
    banks = summary["banks"]["by_regime"]
    ca = summary["california"]
    nz = summary["new_zealand"]
    oracle = summary["oracle_ceiling"]
    nz_folds = read(C.OUT / "nz/summary.json")["folds"]
    s8_summary = read(C.OUT / "s8/summary.json")

    ladder_rows = []
    for key, label in LADDER_ORDER:
        entry = s8[key]
        g = entry["gain_vs_archived_joint_null"]
        gs = entry["gain_vs_stationary_null"]
        ladder_rows.append(
            "| " + label + " | " + f(g["mean"]) + " | " + f(g["median"]) + " | "
            + f(g["mcse"]) + " | " + str(g["wins"]) + "/20 | " + f(gs["mean"]) + " | "
            + f(entry["eta"]["mean"]) + " | " + f(entry["eta"]["rmse_vs_true"], 3) + " | "
            + str(entry["nested_null"]) + "/20 |")
    ladder_table = "\n".join(ladder_rows)

    ranking_rows = []
    for i, r in enumerate(summary["estimator_ranking"]):
        ranking_rows.append(
            "| " + str(i + 1) + " | `" + r["name"] + "` | " + f(r["mean"], 3) + " | "
            + f(r["median"], 3) + " | " + f(r["mcse"], 3) + " | " + f(r["rmse"], 3)
            + " | " + str(r["nested"]) + "/20 | " + f(r.get("s4_mean", 0.0), 2)
            + " | " + pct(r.get("s4_positive_rate", 0.0)) + " | "
            + ("yes" if r.get("admissible") else "no") + " |")
    ranking_table = "\n".join(ranking_rows)

    bank_rows = []
    for regime, label in (("4", "S4 narrow/short immigrant (zero realised thinning)"),
                          ("5", "S5 broad/long immigrant"),
                          ("6", "S6 narrow/short total"),
                          ("7", "S7 broad/long total")):
        entry = banks[regime]
        raw = entry["raw_replay_gain"]
        best = entry[name]
        bank_rows.append(
            "| " + label + " | " + str(raw["N"]) + " | " + f(raw["mean"]) + " | "
            + f(raw["median"]) + " | " + f(best["gain_vs_stationary_null"]["mean"])
            + " | " + f(best["gain_vs_stationary_null"]["median"])
            + " | " + str(best["positive_gain"]) + "/" + str(entry["N"]) + " ("
            + pct(best["positive_gain_rate"]) + ") | " + str(best["eta_positive"]) + "/"
            + str(entry["N"]) + " | " + f(best["eta"]["mean"], 3) + " |")
    bank_table = "\n".join(bank_rows)

    ca_rows = []
    for kernel in ("mono", "ann2"):
        for arm in ca[kernel]:
            entry = ca[kernel][arm]
            ca_rows.append(
                "| `" + kernel + "` | `" + arm + "` | " + f(entry["gain_vs_null"]["mean"], 3)
                + " | " + f(entry["gain_vs_null"]["median"], 3) + " | "
                + f(entry["eta"]["mean"], 3) + " | " + f(entry["psi_days"]["mean"], 2)
                + " | " + str(entry.get("eta_zero", entry["nested_null"])) + "/3 |")
    ca_table = "\n".join(ca_rows)

    nz_rows = []
    for key, label in (("E1D_Profile_2p", "`E1D_Profile_2p` (temporal analogue)"),
                       ("E1D_Profile_3p", "`E1D_Profile_3p` (temporal analogue)"),
                       ("E_L1_Shrinkage", "`E_L1_Shrinkage` (temporal analogue)")):
        gains = [nz_folds[fold]["arms"][key]["gain"] for fold in ("fold_50", "fold_65", "fold_80")]
        etas = [nz_folds[fold]["arms"][key]["eta"] for fold in ("fold_50", "fold_65", "fold_80")]
        nz_rows.append("| " + label + " | " + f(gains[0]) + " | " + f(gains[1]) + " | "
                       + f(gains[2]) + " | " + f(sum(gains)) + " | " + f(sum(etas) / 3, 3) + " |")
    nz_rows.append("| Stationary full (a, n, eta) | "
                   + " | ".join(f(nz_folds[fold]["t1_full"]["gain"])
                                for fold in ("fold_50", "fold_65", "fold_80"))
                   + " | " + f(nz["T1_full"]) + " | n/a |")
    nz_rows.append("| Archived free-d comparator | "
                   + " | ".join(f(nz_folds[fold]["archived"]["heldout"]["delta_joint"])
                                for fold in ("fold_50", "fold_65", "fold_80"))
                   + " | " + f(nz["archived_free_d"]) + " | n/a |")
    nz_table = "\n".join(nz_rows)

    audit_rows = "\n".join(
        "| `" + c["name"] + "` | " + ("pass" if c["passed"] else "FAIL") + " |"
        for c in audit["checks"])

    closure_rows = "\n".join(
        "| " + step["step"] + " | " + f(step["nats"], 3) + " |"
        for step in summary["ladder_closure"]["steps"])
    closure_rows += ("\n| **total truth -> archived Free-8D** | **"
                     + f(summary["ladder_closure"]["total"], 3) + "** |\n"
                     + "| sealed estimation-loss magnitude | "
                     + f(-oracle["estimation_loss"]["mean"], 3) + " |\n"
                     + "| closure residual | "
                     + f(summary["ladder_closure"]["residual"], 6) + " |")

    seed_rows = []
    for row in s8_summary["rows"]:
        arms = row["arms"]
        seed_rows.append(
            "| " + str(row["seed"]) + " | "
            + f(arms["S1_fixed_backbone_a_eta"]["gain_vs_archived_joint_null"]) + " | "
            + f(arms["S2_fixed_backbone_a_eta_ell_psi"]["gain_vs_archived_joint_null"]) + " | "
            + f(arms["E1D_Profile_2p"]["gain_vs_archived_joint_null"]) + " | "
            + f(arms["E1D_Profile_3p"]["gain_vs_archived_joint_null"]) + " | "
            + f(arms["E_L1_Shrinkage"]["gain_vs_archived_joint_null"]) + " | "
            + f(arms["Free_8D_archived"]["gain_vs_archived_joint_null"]) + " | "
            + f(arms["Free_8D_archived"]["eta"], 2) + " |")
    seed_table = "\n".join(seed_rows)

    win = s8[name]
    win_mean = win["gain_vs_archived_joint_null"]["mean"]
    win_frac = win_mean / oracle["gain_vs_joint_null"]["mean"]
    s1_mean = s8["S1_fixed_backbone_a_eta"]["gain_vs_archived_joint_null"]["mean"]
    s2_mean = s8["S2_fixed_backbone_a_eta_ell_psi"]["gain_vs_archived_joint_null"]["mean"]
    s3a_mean = s8["S3a_stat_null_a_n_eta_true_scale"]["gain_vs_archived_joint_null"]["mean"]
    free_mean = s8["Free_8D_archived"]["gain_vs_archived_joint_null"]["mean"]
    s4 = banks["4"][name]
    ca_qmax = max(abs(v["test_quadrature_delta"]["maximum"]) for v in ca["mono"].values())

    values = dict(
        LADDER_TABLE=ladder_table, RANKING_TABLE=ranking_table, BANK_TABLE=bank_table,
        CLOSURE_TABLE=closure_rows,
        CA_TABLE=ca_table, NZ_TABLE=nz_table, AUDIT_TABLE=audit_rows, SEED_TABLE=seed_table,
        WIN_NAME=name, WIN_MEAN=f(win_mean), WIN_FRAC=pct(win_frac),
        WIN_STAT_MEAN=f(win["gain_vs_stationary_null"]["mean"]),
        ORACLE_FIXED=f(oracle["gain_vs_fixed"]["mean"]),
        ORACLE_INTERCEPT=f(oracle["gain_vs_intercept"]["mean"]),
        ORACLE_JOINT=f(oracle["gain_vs_joint_null"]["mean"]),
        ORACLE_LOSS=f(oracle["estimation_loss"]["mean"]),
        FREE_MEAN=f(free_mean), S1_MEAN=f(s1_mean), S2_MEAN=f(s2_mean),
        S3A_MEAN=f(s3a_mean), STEP12=f(s1_mean - s2_mean), STEP23=f(s2_mean - s3a_mean),
        STEP3FREE=f(s3a_mean - free_mean), S4_GAIN=f(s4["gain_vs_stationary_null"]["mean"], 3),
        LOWDIM_GAP=f(oracle["gain_vs_joint_null"]["mean"]
                     - s8["E1D_Profile_3p"]["gain_vs_archived_joint_null"]["mean"]),
        FREE_JUMP=f(s8["E1D_Profile_3p"]["gain_vs_archived_joint_null"]["mean"] - free_mean),
        S4_POS=str(s4["positive_gain"]), S4_N=str(banks["4"]["N"]),
        S4_RATE=pct(s4["positive_gain_rate"]),
        S4_WILSON="[" + f(s4["positive_gain_wilson95"][0], 3) + ", "
                 + f(s4["positive_gain_wilson95"][1], 3) + "]",
        S4_RAW=f(banks["4"]["raw_replay_gain"]["mean"]),
        E1D3_S4=f(banks["4"]["E1D_Profile_3p"]["gain_vs_stationary_null"]["mean"]),
        E1D3_S4_MIN=f(banks["4"]["E1D_Profile_3p"]["gain_vs_stationary_null"]["minimum"]),
        GRID_STEP=f(s3a_mean - s8["E1D_Profile_3p"]["gain_vs_archived_joint_null"]["mean"]),
        S1_ETA_RMSE=f(s8["S1_fixed_backbone_a_eta"]["eta"]["rmse_vs_true"], 3),
        S2_ETA_RMSE=f(s8["S2_fixed_backbone_a_eta_ell_psi"]["eta"]["rmse_vs_true"], 3),
        S3A_ETA_RMSE=f(s8["S3a_stat_null_a_n_eta_true_scale"]["eta"]["rmse_vs_true"], 3),
        S4_REDUCTION=pct(1.0 - s4["gain_vs_stationary_null"]["mean"]
                         / banks["4"]["raw_replay_gain"]["mean"]),
        S6_REDUCTION=pct(1.0 - banks["6"][name]["gain_vs_stationary_null"]["mean"]
                         / banks["6"]["raw_replay_gain"]["mean"]),
        S6_OFF_ACC=str(banks["6"]["realized_thinning"]["accepted_offspring"]),
        S6_OFF_REJ=str(banks["6"]["realized_thinning"]["rejected_offspring"]),
        S7_OFF_ACC=str(banks["7"]["realized_thinning"]["accepted_offspring"]),
        S7_OFF_REJ=str(banks["7"]["realized_thinning"]["rejected_offspring"]),
        S6_OFF_RATE=pct(banks["6"]["realized_thinning"]["rejected_offspring"]
                        / (banks["6"]["realized_thinning"]["rejected_offspring"]
                           + banks["6"]["realized_thinning"]["accepted_offspring"])),
        S7_OFF_RATE=pct(banks["7"]["realized_thinning"]["rejected_offspring"]
                        / (banks["7"]["realized_thinning"]["rejected_offspring"]
                           + banks["7"]["realized_thinning"]["accepted_offspring"])),
        S6_OFF_TOTAL=f"{banks['6']['realized_thinning']['rejected_offspring'] + banks['6']['realized_thinning']['accepted_offspring']:,}",
        S7_OFF_TOTAL=f"{banks['7']['realized_thinning']['rejected_offspring'] + banks['7']['realized_thinning']['accepted_offspring']:,}",
        CA_QMAX=f(ca_qmax, 2), NZ_ARCH=f(nz["archived_free_d"]),
        NZ_E1D3=f(nz["E1D_Profile_3p"]),
        NZ_IMPROVE=f(nz["E1D_Profile_3p"] - nz["archived_free_d"]),
        NZ_L1=f(nz["E_L1_Shrinkage"]),
        NZ_L1_IMPROVE=f(nz["E_L1_Shrinkage"] - nz["archived_free_d"]),
        NZ_F50_IMPROVE=f(nz_folds["fold_50"]["arms"]["E_L1_Shrinkage"]["gain"]
                         - nz_folds["fold_50"]["arms"]["E1D_Profile_3p"]["gain"]),
        RECON_TRUTH32=f"{summary['reconstruction']['truth32']:.1e}",
        RECON_FIXED=f"{summary['reconstruction']['fixed_null']:.1e}",
        RECON_INTERCEPT=f"{summary['reconstruction']['intercept_null']:.1e}",
    )

    template = """# Pathway 3 — low-dimensional and penalised attenuation estimators

**Scope:** `experiments/pathway3_low_dim_attenuation/` and
`validation/live_results/pathway3_low_dim_20261116/`. The sealed authorities
and all pre-existing live-result files are read-only.

**Date:** 2026-11-17. **Baseline commit:** `a9d7f9d`.

## 1. Executive summary

- The S8 oracle ceiling is reproduced exactly: truth / fixed-null /
  refit-intercept deltas are at most `@@RECON_TRUTH32@@` / `@@RECON_FIXED@@` /
  `@@RECON_INTERCEPT@@` nats.
- No single freed group explains the 17.8-nat loss. Estimating only (a, eta)
  on the true backbone recovers `@@S1_MEAN@@`; freeing the scale costs
  `@@STEP12@@`, freeing the backbone at a fixed scale costs `@@STEP23@@`, and
  the three-point grid costs `@@GRID_STEP@@`. The remaining `@@FREE_JUMP@@`
  nats appear only in the joint eight-parameter fit (`@@FREE_MEAN@@`). The
  scale-eta ridge is visible in the eta RMSE jump from `@@S1_ETA_RMSE@@` to
  `@@S2_ETA_RMSE@@`; re-estimating the backbone at a fixed scale keeps the eta
  RMSE at `@@S3A_ETA_RMSE@@`.
- The pre-declared winner is the **`@@WIN_NAME@@`** estimator. The S8-only
  ranking would choose `E1D_Profile_3p` (`@@E1D3_MEAN@@` nats), but it fails the
  S4 zero-thinning tail: its S4 mean is `@@E1D3_S4@@` nats with a
  `@@E1D3_S4_MIN@@`-nat worst case. Under the admissibility rule (at least 70%
  of the archived S4 loss removed), `@@WIN_NAME@@` is the best admissible
  estimator, with a mean S8 gain of `@@WIN_MEAN@@` nats against the archived
  joint null (`@@WIN_FRAC@@` of the oracle signal) and a mean gain of
  `@@WIN_STAT_MEAN@@` nats against its own stationary null. It removes
  `@@S4_REDUCTION@@` of the archived S4 loss and `@@S6_REDUCTION@@` of the S6
  loss.
- The +16.43/+18.11 ceiling is **not** fully recovered by any three-point scale
  grid; the residual gap is the cost of learning the scale and the trigger
  backbone on 90-120 training events.
- On the S4 zero-realised-thinning bank the winner produces
  `@@S4_POS@@/@@S4_N@@` positive held-out gains (rate `@@S4_RATE@@`, Wilson95
  `@@S4_WILSON@@`) and a mean attenuation-specific gain of `@@S4_GAIN@@` nats.
  The archived raw eight-parameter S4 gain is `@@S4_RAW@@` nats.
- Wells-Coppersmith rupture scaling selects **zero attenuation** on all three
  California folds for both kernels: the training score slope at eta = 0 is
  negative. The WC scale (0.8-13 km at M4-M6) is far below the empirically
  selected EP+ attenuation scale. This is a clean negative result, not a
  detection.
- New Zealand: the sealed predictive model is temporal-only, so a spatial WC
  scale is not defined. The temporal 1-D profile improves the three-fold
  attenuation deficit from `@@NZ_ARCH@@` to `@@NZ_E1D3@@` nats but remains
  negative.

## 2. What was tested

### 2.1 Stepwise degree-of-freedom ladder (S8, 20 histories)

The ladder starts at the full generating truth and frees one parameter group
at a time. Free-8D is the archived eight-parameter joint fit. Two additional
rungs separate the stationary clock from the scale and trigger coordinates:
the seven-parameter stationary free fit and the WC sensitivity.

| rung | mean gain vs archived null | median | MCSE | wins | mean gain vs stationary null | mean eta | eta RMSE | nested |
|---|---|---|---|---|---|---|---|---|
@@LADDER_TABLE@@

`gain_vs_archived_joint_null` is the held-out joint score relative to the
archived jointly fitted five-parameter null. `gain_vs_stationary_null` uses the
nested stationary null, so it isolates the attenuation contrast from the d = 0
background change. `eta RMSE` is against eta* = 0.4. `nested` counts exact
eta-hat = 0 returns.

The ladder closes exactly against the sealed estimation loss:

| gap | nats |
|---|---|
@@CLOSURE_TABLE@@

The largest single term is the last one: the step from the three-parameter
low-dimensional estimator to the archived eight-parameter joint fit. The
first four steps (intercept-plus-eta, scale, backbone and grid selection)
account for essentially all of the `@@LOWDIM_GAP@@`-nat gap between the truth
and `E1D_Profile_3p`; the joint free fit accounts for the remaining
`@@FREE_JUMP@@`-nat jump. This is why fixing the scale helps far more than
shrinking `eta` alone.

### 2.2 Estimators

| id | training-only rule | parameters |
|---|---|---|
| `E_1D_Profile` | fit (a, eta) or (a, n, eta) at each of (5,1), (15,5), (50,30) km/d; select by training likelihood plus a log 3 multiplicity term | 2 or 3 |
| `E_L1_Shrinkage` | penalise l_train - lambda * eta * mean(G_train); lambda in {0.5, 1, 2}, selected on the second training half; a per-event penalty is a declared sensitivity | 2 |
| `E_Split_CV` | fit on [30, 212.5); choose alpha in {0, 0.25, 0.5, 0.75, 1} on [212.5, 395); re-balance a on the full training window | 2 |
| `E_WC_Rupture` | fix ell_j = 10^(-2.44 + 0.59 M_j) km and gamma = 0.75 log 10; fit (a, eta) or (a, n, eta), optionally profiling psi | 2-4 |

Every estimator receives only the training phase. The held-out phase is used
only by the final scoring call.

## 3. S8 results

Three facts stand out.

1. **The fixed-backbone scale cost.** Moving from Step 1 to Step 2
   (`@@S1_MEAN@@` to `@@S2_MEAN@@` nats) costs `@@STEP12@@` nats. That is the
   price of estimating (ell, psi) rather than fixing them at the generating
   values.
2. **The backbone cost is comparable.** Moving from the true backbone to the
   stationary fitted backbone costs `@@STEP23@@` nats. The archived free
   eight-parameter fit then loses the remaining `@@STEP3FREE@@` nats. The two
   channels are of similar size; no single freed group explains the whole
   estimation loss.
3. **The three-point grid is a real constraint.** `E1D_Profile_2p` and
   `E1D_Profile_3p` are `@@E1D2_MEAN@@` and `@@E1D3_MEAN@@` nats against the
   archived null. The 3D (a, n, eta) variant beats the 2D (a, eta) variant on
   the mean and median because profiling `n` recovers part of the backbone
   cost; the eta RMSE is essentially unchanged (1.159 vs 1.160) because the
   scale-selection ridge dominates it. Freeing the scale (Step 2) is different:
   it raises the eta RMSE from 0.176 to 1.159, which is the finite-sample
   identifiability ridge described in the handoff.

The winner declared by the pre-declared admissibility rule (highest mean S8
gain among estimators that remove at least 70% of the archived S4 loss) is
**`@@WIN_NAME@@`**. The full ranking, including the S8-only admissible screen,
is:

| rank | estimator | mean S8 gain vs stationary null | median | MCSE | eta RMSE | nested | S4 mean | S4 positive | admissible |
|---|---|---|---|---|---|---|---|---|---|
@@RANKING_TABLE@@

## 4. S04B bank controls

| bank | N | archived raw gain mean | archived raw median | winner mean | winner median | positive gains | eta > 0 | mean eta |
|---|---|---|---|---|---|---|---|---|
@@BANK_TABLE@@

`raw replay` is the archived uninhibited-to-inhibited contrast recomputed under
the same evaluator. The S4 bank has zero realised thinning in its generator
receipt: it is the S4 zero-thinning null control. The S6 bank is the primary
positive total-intensity control; S5 and S7 are secondary positive banks. The
winner returns the exact null on 7/20 S4 histories and near-zero on most of the
remainder, but a few large negative outliers dominate the mean; it reduces the
S4 and S6 mean losses by `@@S4_REDUCTION@@` and `@@S6_REDUCTION@@`, while
retaining a positive mean on S7. The unscreened `E1D_Profile_3p` arm has a much
worse S4 tail (`@@E1D3_S4@@` mean, `@@E1D3_S4_MIN@@` minimum); that failure is
the reason the admissibility screen is part of the winner rule. The raw S4/S6
losses are dominated by inhibition-coordinate overfitting, not by the
background clock; the stationary null removes the clock channel separately.
The generator counters sharpen the interpretation: S4 rejects 1 immigrant and
no offspring (zero realised thinning), S6 rejects `@@S6_OFF_REJ@@` of
`@@S6_OFF_TOTAL@@` offspring proposals (`@@S6_OFF_RATE@@`), and
S7 rejects `@@S7_OFF_REJ@@` of `@@S7_OFF_TOTAL@@` (`@@S7_OFF_RATE@@`). S6 is
therefore a weak realised-thinning control, while S7 is the strong positive
control and the only bank where every estimator retains a positive mean.

## 5. California: Wells-Coppersmith rupture scaling

The WC scale is fixed at

    ell_j = 10^(-2.44 + 0.59 M_j) km,      gamma = 0.75 log 10,

with M0 = 3 for these catalogues, so ell0 = 0.214 km and the exponent is 0.59.
The primary arm estimates (a, eta) at psi = 5 d on the sealed interior EP+
backbone. `WC_a_n_eta` also profiles n; the `psi` variants profile the
relaxation time.

| kernel | arm | mean gain vs null | median | mean eta | mean psi (d) | eta = 0 |
|---|---|---|---|---|---|---|
@@CA_TABLE@@

`gain_vs_null` is the held-out joint score relative to the arm's own nested
null on the same frozen test proposal. The quadrature check re-scores every
selected state on an independent seed; the maximum absolute delta is
`@@CA_QMAX@@` nats. The training slope at eta = 0 is negative for both kernels
(-801 nats per unit eta for `mono`, -6753 for `ann2` on fold 0), so the exact
eta-hat = 0 boundary is the correct training solution. The WC scale is
substantially smaller than the 15-50 km scale selected by the free EP+
attenuation fit; this is the scientific content of the negative result.

## 6. New Zealand: scope and temporal analogue

The sealed New Zealand predictive model is a temporal renewal/Omori mixture
with `times` and `excess` only; it has **no epicentral-distance kernel**. A
Wells-Coppersmith rupture length is therefore undefined in that model. This is
recorded as a scope limitation, not silently replaced. The temporal analogue of
`E_1D_Profile` holds the archived trigger and stress kernels fixed and
estimates (a, eta) or (a, n, eta) with d = 0.

| arm | fold_50 | fold_65 | fold_80 | total | mean eta |
|---|---|---|---|---|---|
@@NZ_TABLE@@

The temporal profile improves the free-d deficit by roughly `@@NZ_IMPROVE@@`
nats but does not turn it positive. `E_L1_Shrinkage` is the best New Zealand
arm (`@@NZ_L1@@` nats, `@@NZ_L1_IMPROVE@@` nats better than the archived
free-d comparator): it zeros the unsupported attenuation on folds 65 and 80 and
removes `@@NZ_F50_IMPROVE@@` nats of the fold-50 loss. This is consistent with
Pathway 2's T1 result: removing the trend clock helps, but the residual
attenuation contrast is not supported out of sample on these three folds.

## 7. Audit

| check | status |
|---|---|
@@AUDIT_TABLE@@

The audit re-hashes the sealed inputs, checks tracked-file custody with git,
recomputes every S8 arm on the archived adaptive plan for two seeds (including
the worst-case seed 410840), re-derives the gain and joint decompositions,
checks the L1 KKT conditions, verifies the native annular rows against an
independent NumPy formula and central finite differences, verifies the joint
deficit against a direct recurrence, and checks the S04B and California
closures. The maximum archived-plan vs reported S8 score delta is recorded in
`independent_audit.json`.

## 8. Limitations

1. **S04 unit-mark null banks.** The named `Uniform null` and `Smooth null`
   S04 histories are not part of the reproducible S04B corpus; they belong to
   the earlier unit-mark fixed-backbone study. They were not regenerated or
   relabelled. The S4 bank (zero realised thinning) is the explicit
   S4 zero-thinning control. This is a scope reduction relative to the handoff.
2. **New Zealand WC.** The sealed NZ model has no distance kernel, so
   `E_WC_Rupture` cannot be evaluated there. The temporal 1-D profile is the
   declared analogue.
3. **Local optima.** The fits use multi-start L-BFGS-B on a smooth analytic
   objective. The exact eta = 0 state is always an eligible candidate. The
   results certify the executed recipe, not a global optimum.
4. **Quadrature plan.** Optimisation uses a frozen tensor-Gauss plan; reported
   scores use a 20x20 spatial and 24-node time plan at order 16. The audit
   replays the archived adaptive plan and records the deltas. The truth at
   order 32 is evaluated on the same plan and reproduces the sealed oracle.
5. **Finite-sample scale.** The grid has three points. A denser or continuous
   scale profile would change the exact trade-off and is outside the
   pre-declared design.

## 9. Reproduction

```powershell
python -m experiments.pathway3_low_dim_attenuation.run_s8 --workers 6 --resume
python -m experiments.pathway3_low_dim_attenuation.run_banks --workers 6 --resume
python -m experiments.pathway3_low_dim_attenuation.run_california --workers 3
python -m experiments.pathway3_low_dim_attenuation.run_nz
python -m experiments.pathway3_low_dim_attenuation.build_summary
python -m experiments.pathway3_low_dim_attenuation.audit_pathway3
python -m experiments.pathway3_low_dim_attenuation.make_report
```

## Appendix: S8 per-history contrasts

| seed | Step 1 | Step 2 | E1D-2p | E1D-3p | L1 | Free-8D | Free-8D eta |
|---|---|---|---|---|---|---|---|
@@SEED_TABLE@@
"""
    for key, value in values.items():
        template = template.replace("@@" + key + "@@", value)
    # The two E1D means are read from the ranking table's winner-neutral fields.
    template = template.replace("@@E1D2_MEAN@@",
                                f(s8["E1D_Profile_2p"]["gain_vs_archived_joint_null"]["mean"]))
    template = template.replace("@@E1D3_MEAN@@",
                                f(s8["E1D_Profile_3p"]["gain_vs_archived_joint_null"]["mean"]))
    C.REPORT.parent.mkdir(parents=True, exist_ok=True)
    C.REPORT.write_text(template, encoding="utf-8")
    print("wrote", C.REPORT)
    return template


if __name__ == "__main__":
    main()
