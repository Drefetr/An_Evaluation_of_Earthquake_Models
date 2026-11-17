"""Stage P4.2 held-out scoring: Japan 1,277-target EP+ contrasts.

Runs only after ``fit_seal.json`` exists.  The archived OC/EP fold and annual
block components are opened here, never during fitting.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pathway4_confirmatory_transfer import common as C, data
from experiments.pathway4_confirmatory_transfer.model import (
    EPModel, make_attenuation_nodes, test_attenuation_gain,
    wells_coppersmith_ell)
from experiments.pathway4_confirmatory_transfer.pipeline import GAMMA_FIXED
from experiments.pathway4_confirmatory_transfer import scoring as S

ARMS = [(f"jma_fold_{f}_{n}_{t}", f, n, t)
        for f in range(3) for n, t in (("plane", "T0"), ("plane", "T1"),
                                       ("rect", "T1"))]


def _atten_gain(payload, model, x, seed):
    profiles = payload.get("attenuation_profiles", {}) or {}
    if profiles.get("status") != "complete":
        return None
    excess = model.view.parent_excess
    M0 = getattr(model.view, "M0", 4.0)
    mono_key = profiles["mono_selected"]["key"]
    mono = profiles["mono_grid"][mono_key]
    refined = profiles["refined_ann2_wc"]
    if float(mono["eta"]) == 0.0 and float(refined["eta"]) == 0.0:
        return dict(mono=dict(eta=0.0, gain=0.0),
                    refined=dict(eta=0.0, gain=0.0),
                    node_exposure=0.0, short_circuit="exact nested eta=0")
    mono_nodes = make_attenuation_nodes(
        model, x, mono["ell0_km"] * 10.0 ** (0.5 * excess),
        mono["psi_days"], GAMMA_FIXED, power=13, seed=seed)
    mono_gain = test_attenuation_gain(
        model, x, "mono", mono["ell0_km"], mono["psi_days"], GAMMA_FIXED,
        mono["eta"], mono_nodes)
    wc_nodes = make_attenuation_nodes(
        model, x, wells_coppersmith_ell(excess, M0),
        refined["psi_days"], GAMMA_FIXED, power=13, seed=seed)
    refined_gain = test_attenuation_gain(
        model, x, "ann2", None, refined["psi_days"], GAMMA_FIXED,
        refined["eta"], wc_nodes)
    return dict(mono=mono_gain, refined=refined_gain,
                node_exposure=mono_gain["exposure_integral"])


def score_arm(name, fold, normalization, trend):
    cat = data.load_jma_catalogue_arrays()
    payload = S.fit_payload(name)
    train = data.jma_train_view(fold, cat=cat,
                                weights=payload["background_weights"],
                                floor_mode=payload["background_floor_mode"])
    test = data.jma_test_view(fold, train.background, cat=cat)
    model = EPModel(test, normalization)
    x = np.asarray(payload["parameters"], dtype=float)
    null = model.scores(x)
    mark = S.mark_score_lattice(test.event_excess, test.beta)
    archived = data.jma_archived(fold, cat=cat)
    ep_joint = null["ground_joint"] + mark
    arch_ep = archived["full"]["EP"]
    arch_mark = float(arch_ep["joint"] - arch_ep["P"] + arch_ep["E"])
    out = dict(
        schema="pathway4_jma_score_v1", name=name, fold=fold,
        normalization=normalization, trend=trend,
        n_test=int(len(test.event_time)),
        fit_protocol_sha256=payload["protocol_sha256"],
        null=dict(P=null["P"], E=null["E"], timing=null["timing"],
                  location=null["location"], ground_joint=null["ground_joint"],
                  mark=mark, joint=ep_joint),
        archived=archived,
        ep_minus_ep=S.contrast(null["timing"], null["location"], ep_joint,
                               archived["full"]["EP"]),
        ep_minus_oc=S.contrast(null["timing"], null["location"], ep_joint,
                               archived["full"]["OC"]),
        mark_reconciliation=float(mark - arch_mark),
    )
    atten = S.attenuation_test(payload, model, x, power=16,
                               seed=20261120)
    out["attenuation"] = atten
    if atten.get("status") == "complete":
        mono_joint = ep_joint + atten["mono"]["gain"]
        refined_joint = ep_joint + atten["refined"]["gain"]
        out["mono_attenuation"] = dict(
            joint=mono_joint,
            minus_ep=S.contrast(null["timing"], null["location"], mono_joint,
                                archived["full"]["EP"]),
            minus_oc=S.contrast(null["timing"], null["location"], mono_joint,
                                archived["full"]["OC"]))
        out["refined_attenuation"] = dict(
            joint=refined_joint,
            minus_ep=S.contrast(null["timing"], null["location"], refined_joint,
                                archived["full"]["EP"]),
            minus_oc=S.contrast(null["timing"], null["location"], refined_joint,
                                archived["full"]["OC"]))
    blocks = {}
    for index, (block_start, block_end, year) in enumerate(data.JMA_BLOCK_DAYS[fold]):
        # The catalogue mask is a view; copy it so a block slice cannot mutate
        # the shared fold mask used by later blocks.
        cat_block = dict(cat)
        cat_block["fold_test_mask"] = cat["fold_test_mask"].copy()
        block = data.jma_block_view(fold, block_start, block_end,
                                    train.background, cat=cat_block)
        bmodel = EPModel(block, normalization)
        bs = bmodel.scores(x)
        bmark = S.mark_score_lattice(block.event_excess, block.beta)
        bjoint = bs["ground_joint"] + bmark
        arch_ep_block = archived["partitions"]["EP"][year]
        arch_mark_block = float(arch_ep_block["joint"] - arch_ep_block["P"] +
                                arch_ep_block["E"])
        entry = dict(
            year=year, n_test=int(len(block.event_time)),
            null=dict(P=bs["P"], E=bs["E"], timing=bs["timing"],
                      location=bs["location"], ground_joint=bs["ground_joint"],
                      mark=bmark, joint=bjoint),
            archived=dict(
                OC=archived["partitions"]["OC"][year],
                EP=arch_ep_block),
            ep_minus_ep=S.contrast(bs["timing"], bs["location"], bjoint,
                                   archived["partitions"]["EP"][year]),
            ep_minus_oc=S.contrast(bs["timing"], bs["location"], bjoint,
                                   archived["partitions"]["OC"][year]),
            mark_reconciliation=float(bmark - arch_mark_block),
        )
        gain = _atten_gain(payload, bmodel, x, seed=20261300 + fold * 10 + index)
        if gain is not None:
            mono_b = bjoint + gain["mono"]["gain"]
            refined_b = bjoint + gain["refined"]["gain"]
            entry["mono_attenuation"] = dict(
                joint=mono_b,
                minus_ep=S.contrast(bs["timing"], bs["location"], mono_b,
                                    archived["partitions"]["EP"][year]),
                minus_oc=S.contrast(bs["timing"], bs["location"], mono_b,
                                    archived["partitions"]["OC"][year]))
            entry["refined_attenuation"] = dict(
                joint=refined_b,
                minus_ep=S.contrast(bs["timing"], bs["location"], refined_b,
                                    archived["partitions"]["EP"][year]),
                minus_oc=S.contrast(bs["timing"], bs["location"], refined_b,
                                    archived["partitions"]["OC"][year]))
            entry["attenuation_gain"] = dict(
                mono=gain["mono"]["gain"], refined=gain["refined"]["gain"],
                node_exposure=gain["node_exposure"])
        blocks[year] = entry
    out["blocks"] = blocks
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=C.PROTOCOL)
    parser.add_argument("--seal", type=Path, default=C.OUT / "fit_seal.json")
    args = parser.parse_args()
    S.verify_fit_seal(args.seal, args.protocol)
    rows = []
    for name, fold, normalization, trend in ARMS:
        result = score_arm(name, fold, normalization, trend)
        C.write_json(C.OUT / "scores" / f"{name}.json", result)
        rows.append(result)
        print(name, result["ep_minus_ep"]["joint"],
              result["ep_minus_oc"]["joint"],
              result.get("refined_attenuation", {}).get("minus_ep", {}).get("joint"),
              flush=True)
    C.write_json(C.OUT / "jma_score_index.json",
                 dict(schema="pathway4_jma_score_index_v1",
                      rows=[dict(name=r["name"], fold=r["fold"],
                                 normalization=r["normalization"],
                                 trend=r["trend"],
                                 n_test=r["n_test"],
                                 ep_minus_ep=r["ep_minus_ep"],
                                 ep_minus_oc=r["ep_minus_oc"],
                                 refined=r.get("refined_attenuation"),
                                 mono=r.get("mono_attenuation"),
                                 blocks=r["blocks"])
                            for r in rows]))


if __name__ == "__main__":
    main()
