"""Stage P4.1 held-out scoring: New Zealand 612-target EP+ contrasts.

Runs only after ``fit_seal.json`` exists.  The archived arm-1 (OC) and arm-4
(EP) totals are opened here, never during fitting.
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
from experiments.pathway4_confirmatory_transfer.model import EPModel
from experiments.pathway4_confirmatory_transfer import scoring as S

ARMS = [(f"nz_fold_{f}_{n}_{t}", f, n, t)
        for f in range(3) for n, t in (("plane", "T0"), ("plane", "T1"),
                                       ("rect", "T0"), ("rect", "T1"))]


def score_arm(name, fold, normalization, trend):
    payload = S.fit_payload(name)
    train = data.nz_train_view(fold, weights=payload["background_weights"],
                               floor_mode=payload["background_floor_mode"])
    test = data.nz_test_view(fold, train.background)
    model = EPModel(test, normalization)
    x = np.asarray(payload["parameters"], dtype=float)
    null = model.scores(x)
    mark = S.mark_score_continuous(test.event_excess, test.beta)
    archived = data.nz_archived_comparators(fold)
    ep_joint = null["ground_joint"] + mark
    ep_timing = null["timing"]
    ep_location = null["location"]
    out = dict(
        schema="pathway4_nz_score_v1", name=name, fold=fold,
        normalization=normalization, trend=trend,
        n_test=int(len(test.event_time)),
        fit_protocol_sha256=payload["protocol_sha256"],
        null=dict(P=null["P"], E=null["E"], timing=ep_timing,
                  location=ep_location, ground_joint=null["ground_joint"],
                  mark=mark, joint=ep_joint),
        archived=archived,
        ep_minus_ep=S.contrast(ep_timing, ep_location, ep_joint,
                               archived["ep"]),
        ep_minus_oc=S.contrast(ep_timing, ep_location, ep_joint,
                               archived["oc"]),
        mark_reconciliation=float(mark - archived["ep"]["mark"]),
    )
    atten = S.attenuation_test(payload, model, x, power=16,
                               seed=20261120)
    out["attenuation"] = atten
    if atten.get("status") == "complete":
        mono_joint = ep_joint + atten["mono"]["gain"]
        refined_joint = ep_joint + atten["refined"]["gain"]
        out["mono_attenuation"] = dict(
            joint=mono_joint,
            minus_ep=S.contrast(ep_timing, ep_location, mono_joint,
                                archived["ep"]),
            minus_oc=S.contrast(ep_timing, ep_location, mono_joint,
                                archived["oc"]),
        )
        out["refined_attenuation"] = dict(
            joint=refined_joint,
            minus_ep=S.contrast(ep_timing, ep_location, refined_joint,
                                archived["ep"]),
            minus_oc=S.contrast(ep_timing, ep_location, refined_joint,
                                archived["oc"]),
        )
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
    C.write_json(C.OUT / "nz_score_index.json",
                 dict(schema="pathway4_nz_score_index_v1",
                      rows=[dict(name=r["name"], fold=r["fold"],
                                 n_test=r["n_test"],
                                 normalization=r["normalization"],
                                 trend=r["trend"],
                                 ep_minus_ep=r["ep_minus_ep"],
                                 ep_minus_oc=r["ep_minus_oc"],
                                 refined=r.get("refined_attenuation"),
                                 mono=r.get("mono_attenuation"))
                            for r in rows]))


if __name__ == "__main__":
    main()
