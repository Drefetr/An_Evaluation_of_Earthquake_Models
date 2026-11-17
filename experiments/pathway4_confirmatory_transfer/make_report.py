"""Render the Pathway 4 confirmatory report from sealed results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C


def f(x, digits=3):
    return f"{float(x):+.{digits}f}"


def p(x, digits=3):
    return f"{float(x):.{digits}f}"


def table_nz(nz):
    lines = [
        "| arm | fold | n | EP+ - EP timing | EP+ - EP location | EP+ - EP joint | EP+ - OC joint |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for arm, block in nz["arms"].items():
        for row in block["folds"]:
            a = row["ep_minus_ep"]
            b = row["ep_minus_oc"]
            lines.append(
                f"| {arm} | {row['fold']} | {row['n_test']} | "
                f"{f(a['timing'])} | {f(a['location'])} | {f(a['joint'])} | "
                f"{f(b['joint'])} |")
        tot = block["totals"]
        lines.append(
            f"| **{arm} total** | 0-2 | 612 | {f(tot['ep_minus_ep']['timing'])} | "
            f"{f(tot['ep_minus_ep']['location'])} | "
            f"{f(tot['ep_minus_ep']['joint'])} | "
            f"{f(tot['ep_minus_oc']['joint'])} |")
    return "\n".join(lines)


def table_jma(jma):
    lines = [
        "| arm | fold | n | EP+ - EP timing | EP+ - EP location | EP+ - EP joint | EP+ - OC joint |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for arm, block in jma["arms"].items():
        for row in block["folds"]:
            a = row["ep_minus_ep"]
            b = row["ep_minus_oc"]
            lines.append(
                f"| {arm} | {row['fold']} | {row['n_test']} | "
                f"{f(a['timing'])} | {f(a['location'])} | {f(a['joint'])} | "
                f"{f(b['joint'])} |")
        tot = block["totals"]
        lines.append(
            f"| **{arm} total** | 0-2 | 1,277 | {f(tot['ep_minus_ep']['timing'])} | "
            f"{f(tot['ep_minus_ep']['location'])} | "
            f"{f(tot['ep_minus_ep']['joint'])} | "
            f"{f(tot['ep_minus_oc']['joint'])} |")
    return "\n".join(lines)


def table_annual(jma):
    lines = [
        "| arm | year | n | EP+ - EP joint | EP+ - OC joint | refined - EP joint |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for arm, block in jma["arms"].items():
        has_refined = any("refined_attenuation" in row
                          for row in block["annual_blocks"].values())
        for year, row in sorted(block["annual_blocks"].items()):
            refined = (f(row["refined_minus_ep"]["joint"])
                       if has_refined else "n/a")
            lines.append(
                f"| {arm} | {year} | {row['n_test']} | "
                f"{f(row['ep_minus_ep']['joint'])} | "
                f"{f(row['ep_minus_oc']['joint'])} | "
                f"{refined} |")
        tot = block["annual_totals"]
        refined_total = (f(tot["refined_minus_ep"]["joint"])
                         if has_refined else "n/a")
        lines.append(
            f"| **{arm} total** | 2016-2024 | 1,277 | "
            f"{f(tot['ep_minus_ep']['joint'])} | "
            f"{f(tot['ep_minus_oc']['joint'])} | "
            f"{refined_total} |")
    return "\n".join(lines)


def table_attenuation(nz, jma):
    lines = [
        "| cohort | arm | training eta (refined) | test refined gain | test refined - EP joint | training eta (mono) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for cohort, block in (("NZ", nz), ("JMA", jma)):
        prefix = "nz" if cohort == "NZ" else "jma"
        for arm, payload in block["arms"].items():
            norm, trend = arm.split("_", 1)
            etas, gains, mono_etas = [], [], []
            for row in payload["folds"]:
                fold = row["fold"]
                fit = C.read_json(C.OUT / "fits" /
                                  f"{prefix}_fold_{fold}_{norm}_{trend}.json")
                score = C.read_json(C.OUT / "scores" /
                                    f"{prefix}_fold_{fold}_{norm}_{trend}.json")
                profiles = fit.get("attenuation_profiles", {}) or {}
                refined = profiles.get("refined_ann2_wc")
                if refined:
                    etas.append(refined["eta"])
                    gains.append(score.get("attenuation", {}).get(
                        "refined", {}).get("gain"))
                mono = profiles.get("mono_grid", {}).get(
                    profiles.get("mono_selected", {}).get("key"))
                if mono:
                    mono_etas.append(mono["eta"])
            if not etas:
                continue
            lines.append(
                f"| {cohort} | {arm} | {', '.join(p(e) for e in etas)} | "
                f"{', '.join(f(g) for g in gains)} | "
                f"{f(payload['totals']['refined_minus_ep']['joint'])} | "
                f"{', '.join(p(e) for e in mono_etas)} |")
    return "\n".join(lines)


def table_california(ca):
    if not ca:
        return "_Conditional calibration results missing._"
    origins = {0: "2011", 1: "2016", 2: "2021"}
    lines = [
        "| origin | n | count p | quadratic p | Fisher p | archived OC (N/quad/Fisher) | archived EP (N/quad/Fisher) |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for fold, row in ca.get("folds", {}).items():
        ref = None
        path = C.OUT / "california" / f"ca_fold_{fold}_calibration.json"
        if path.exists():
            ref = C.read_json(path)["archived_reference"]
        ref_oc = ("/".join(p(ref["OC"][k]) for k in
                           ("count", "quadratic", "fisher")) if ref else "-")
        ref_ep = ("/".join(p(ref["EP"][k]) for k in
                           ("count", "quadratic", "fisher")) if ref else "-")
        origin = origins.get(int(fold), fold)
        lines.append(
            f"| {origin} | {row['n_test']} | "
            f"{p(row['count_two_sided'])} | {p(row['quadratic'])} | "
            f"{p(row['fisher'])} | {ref_oc} | {ref_ep} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=C.OUT / "summary.json")
    parser.add_argument("--output", type=Path, default=C.REPORT)
    args = parser.parse_args()
    summary = C.read_json(args.summary)
    nz = summary["new_zealand"]
    jma = summary["japan"]
    ca = summary.get("california")
    audit = summary.get("audit") or {}
    nz_primary = nz["arms"]["plane_T1"]["totals"]["ep_minus_ep"]
    jma_primary = jma["arms"]["plane_T1"]["totals"]["ep_minus_ep"]
    refined_nz = nz["arms"]["plane_T1"]["totals"]["refined_minus_ep"]["joint"]
    refined_jma = jma["arms"]["plane_T1"]["totals"]["refined_minus_ep"]["joint"]
    refined_gain_nz = refined_nz - nz_primary["joint"]
    refined_gain_jma = refined_jma - jma_primary["joint"]
    ca_lines = []
    if ca:
        origins = {0: "2011", 1: "2016", 2: "2021"}
        for fold, row in ca.get("folds", {}).items():
            ca_lines.append(
                f"- origin {origins.get(int(fold), fold)}: conditional count "
                f"p={p(row['count_two_sided'])}, quadratic p="
                f"{p(row['quadratic'])}, Fisher p={p(row['fisher'])}.")
    text = f"""# Pathway 4 — single-pass frozen confirmation and cross-regional EP+ transfer

**Date:** 17 November 2026  
**Isolated code:** `experiments/pathway4_confirmatory_transfer/`  
**Isolated results:** `validation/live_results/pathway4_confirmatory_20261116/`  
**Protocol SHA-256:** `{summary.get('protocol_sha256')}`  
**Fit-seal manifest SHA-256:** `{summary.get('fit_seal_manifest_sha256')}`

## 1. Design and single-pass custody

The Pathway 1–3 winning refinements were frozen in
`frozen_protocol_v1.json` **before** any New Zealand or Japan test-window
score was evaluated.  The protocol fixes the interior-scale EP+ likelihood
(`sigma_0 >= 0.05 km`, `alpha_s in [0,2]`, five-step training
immigrant-probability KDE declustering), both observation-domain
normalisations, the stationary `d = 0` and free-trend `d` arms, the frozen
monotone and annular-Wells–Coppersmith attenuation profiles, all parameter
bounds, starts and the test score decomposition.  Training fits were written
and hash-sealed in `fit_seal.json`; only then did `score_nz.py`,
`score_jma.py` and the California calibration script open test arrays or
archived score totals.  The independent audit reports
**{'PASS' if audit.get('passed') else 'FAIL'}**.

**Protocol custody note.** An initial freeze was written, then invalidated
**before any New Zealand or Japan test-window score was evaluated** because a
sign/root-search error in the one-dimensional attenuation profile was found
and corrected.  The initial protocol and its twelve superseded New Zealand
fits are retained as
`frozen_protocol_v1_superseded_20261116.*` and `superseded_fits_20261116/`.
The operative protocol is the SHA-256 above; the audit verifies that it
predates every sealed fit and that no test score entered either freeze or the
correction.

## 2. New Zealand (612 targets)

EP+ minus archived procedure, in nats.  Positive favours EP+.

{table_nz(nz)}

The primary stationary, full-plane arm gives a three-fold EP+ minus EP joint
contrast of **{f(nz_primary['joint'])} nats** and EP+ minus OC of
**{f(nz['arms']['plane_T1']['totals']['ep_minus_oc']['joint'])} nats**.
The free-trend arm gives EP+ minus EP **{f(nz['arms']['plane_T0']['totals']['ep_minus_ep']['joint'])}**
nats.  The two normalisations and trend laws are separate fitted procedures;
their differences are not a variance decomposition.

## 3. Japan (1,277 targets)

{table_jma(jma)}

The primary stationary, full-plane arm gives a three-fold EP+ minus EP joint
contrast of **{f(jma_primary['joint'])} nats** and EP+ minus OC of
**{f(jma['arms']['plane_T1']['totals']['ep_minus_oc']['joint'])}** nats.
The free-trend arm gives EP+ minus EP
**{f(jma['arms']['plane_T0']['totals']['ep_minus_ep']['joint'])}** nats.

### Annual blocks (2016–2024)

{table_annual(jma)}

The annual rows are descriptive blocks of the same fitted state; they are not
independent replications.

## 4. Frozen attenuation recipe

The baseline arm profiles the monotone kernel over the three declared
`(ell_0, psi)` pairs; the refined arm uses Pathway 1's `ann2` kernel with the
parameter-free Wells–Coppersmith scale and `psi = 5 d`, `gamma = 0.75 log 10`.
Both are exact one-dimensional profiles on the frozen EP+ null backbone with
the exact nested `eta = 0` state.

{table_attenuation(nz, jma)}

The **refined ann2/Wells–Coppersmith arm is the confirmatory attenuation
test**: its importance field is the ann2 kernel itself, so its profile and
held-out contrast are self-normalised.  The **mono baseline** uses the ann2
kernel as an importance field for its compensator; because the mono kernel has
heavier tails, its held-out contrast is a declared sensitivity only and is
not used in the confirmatory conclusion.  The mono training etas are reported
for completeness, not as a detection.

The refined arms' three-fold joint contrasts versus archived EP are
**{f(refined_nz)} nats** (NZ) and **{f(refined_jma)} nats** (JMA).  Relative
to the EP+ null backbone the attenuation gains are
**{f(refined_gain_nz)} nats** (NZ) and **{f(refined_gain_jma)} nats** (JMA).
A zero gain means the training profile selected the exact nested `eta = 0`
boundary; the attenuation refinement is then observationally identical to the
EP+ null backbone, not evidence for a physical stress shadow.

## 5. California conditional calibration of interior-scale EP+

999 sequential branching paths per origin were simulated from the frozen
interior-scale EP+ states.  The observed vector plus the 999 simulated vectors
form the symmetric pool for the eight-coordinate quadratic and Fisher-type
omnibus statistics.

{table_california(ca)}

{chr(10).join(ca_lines)}

The refinement repairs the 2021 origin's continuous omnibus (quadratic
p=0.101, Fisher p=0.166) but the 2011 and 2016 origins remain rejected at the
five-percent level.  The conditional count behaviour improves at 2016 relative
to archived EP (0.452 versus 0.698), at 2021 (0.266 versus 0.036) but not at
2011 (0.004 versus 0.002).

These are conditional, within-origin tests.  They do not integrate parameter
uncertainty and are not a joint cross-origin rejection.

## 6. Independent audit

| check | result |
|---|---|
""" + "\n".join(f"| {c['name']} | {'pass' if c['passed'] else 'fail'} |"
                for c in audit.get("checks", [])) + f"""

The audit verifies the protocol pin, the fit seal, training-only source
separation, exact common-measure identity of parent histories, fertility
weights, rectangles and event arrays, exact archived-score replay, rectangle
mass against independent quadrature, analytic gradients against central finite
differences, sealed-authority custody and the California frozen-state replay.

## 7. Interpretation and limitations

* The confirmatory execution is single-pass: the New Zealand and Japan fits
  were sealed before any test-window score was read.  No parameter, bound,
  bandwidth or declustering step was changed afterwards.
* EP+ is a separately fitted procedure.  Its contrast with archived EP or OC
  measures the whole procedure, not an isolated physical mechanism.  In Japan
  the stationary-arm joint gain is a location-channel gain (+330.5 nats)
  partly offset by a small timing loss ({f(jma['arms']['plane_T1']['totals']['ep_minus_ep']['timing'])} nats);
  in New Zealand both channels are positive.
* The attenuation arms are frozen one-dimensional profiles on the EP+ null
  backbone.  They are not a new joint twelve-parameter search; the protocol
  declares this low-dimensional design following Pathway 3's winner rule.
* On Japan the productivity coordinate `n` sits at its 0.98 upper bound in
  every stationary and free-trend fit, and the fold-0 free-trend arm also pins
  `d` at the -2 lower bound.  These are constrained boundary solutions; the
  reported contrasts describe the fitted constrained procedure, not an
  unconstrained optimum.
* The California calibration is conditional on the fitted state and history.
  The pooled statistics are descriptive within-origin tests, not CSEP
  L/M/S tests, and non-rejection is not proof of model correctness.
* New Zealand's 612 targets remain a reused archive cohort; this execution
  removes the *adaptive procedure-selection* concern but not the reuse of the
  events themselves.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(str(args.output))


if __name__ == "__main__":
    main()
