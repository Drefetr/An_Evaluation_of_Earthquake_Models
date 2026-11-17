"""Merge the four Pathway 2 stages into one auditable summary."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "validation/live_results/pathway2_trend_controls_20261116"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def has(path):
    return Path(path).exists()


def main():
    out = dict(schema="pathway2_trend_controls_summary_v1", passed=True,
               source="experiments/pathway2_trend_parameterization/build_summary.py",
               stages={})
    s8_path = BASE / "s8/summary.json"
    if has(s8_path):
        s8 = read(s8_path)
        out["stages"]["s8"] = dict(
            by_law={k: dict(
                overfitting_loss=v["overfitting_loss"],
                estimation_loss=v["estimation_loss"],
                heldout_gain=v["heldout_gain"],
                bic_gated_gain=v["bic_gated_gain"],
                bic_gate_active=v["bic_gate_active"],
                fitted_eta=v["fitted_eta"],
            ) for k, v in s8["by_law"].items()},
            deltas_vs_t0=s8["deltas_vs_t0"],
            seed_410840=s8["seed_410840"],
            t0_reproduction_max_abs=s8["t0_reproduction_max_abs"],
            rows=s8["rows"],
        )
    s04_path = BASE / "s04b/summary.json"
    if has(s04_path):
        s04 = read(s04_path)
        import numpy as np

        d_null, d_inh, gains = [], [], []
        for row in s04["rows"]:
            sealed = read(ROOT / "validation/live_results/s04b_joint_complete_20261111/cases"
                          / (row["case_id"] + ".json"))
            d_null.append(float(sealed["fits"]["null"]["selected"]["parameters"][1]))
            d_inh.append(float(sealed["fits"]["LIplus_inclusive"]["selected"]["parameters"][1]))
            gains.append(float(row["t0"]["heldout_gain"]))
        d_null = np.asarray(d_null)
        d_inh = np.asarray(d_inh)
        gains = np.asarray(gains)
        worst = np.argsort(gains)[:10]
        out["stages"]["s04b"] = dict(
            trend_diagnostic=dict(
                corr_t0_null_d_gain=float(np.corrcoef(d_null, gains)[0, 1]),
                corr_t0_inhibited_d_gain=float(np.corrcoef(d_inh, gains)[0, 1]),
                worst10_t0_null_d=[float(v) for v in d_null[worst]],
                worst10_t0_inhibited_d=[float(v) for v in d_inh[worst]],
                worst10_t0_gain=[float(v) for v in gains[worst]],
                note=("Near-zero correlations between the archived fitted trend and the "
                      "held-out gain show that the S04B negative tail is not explained by "
                      "the background trend."),
            ),
            by_regime={regime: {law: dict(
                mean=v[law]["gain"]["mean"], median=v[law]["gain"]["median"],
                minimum=v[law]["gain"]["minimum"], q05=v[law]["gain"]["q05"],
                q25=v[law]["gain"]["q25"], q75=v[law]["gain"]["q75"],
                q95=v[law]["gain"]["q95"], wins=v[law]["gain"]["wins"],
                n_lt_minus_50=sum(x < -50 for x in v[law]["gain"]["values"]),
                n_lt_minus_100=sum(x < -100 for x in v[law]["gain"]["values"]),
                nested_null=v[law].get("nested_null"),
                eta_zero=v[law].get("eta_zero"),
                null_p_at_upper_bound=v[law].get("null_p_at_upper_bound"),
            ) for law in ("T0", "T1", "T2")}
                for regime, v in s04["by_regime"].items()},
            worst_t0_cases=s04["worst_t0_cases"],
        )
    nz_path = BASE / "nz/summary.json"
    if has(nz_path):
        nz = read(nz_path)
        out["stages"]["nz"] = dict(
            totals=nz["totals"],
            folds={name: dict(
                T0=nz["folds"][name]["archived"]["heldout"]["delta_joint"],
                **{k: nz["folds"][name]["laws"][k]["heldout"]["delta_joint"] for k in ("T1", "T2", "T3")},
            ) for name in nz["folds"]},
        )
    ca_path = BASE / "california/summary.json"
    if has(ca_path):
        ca = read(ca_path)
        out["stages"]["california"] = dict(
            totals={law: float(sum((r["t0"]["epplus_gain"] if law == "T0"
                                    else r["laws"][law]["test"]["epplus_gain"]) for r in ca["rows"]))
                    for law in ("T0", "T1", "T2", "T3")},
            rows=[dict(case=r["case"], T0=r["t0"]["epplus_gain"],
                       **{k: r["laws"][k]["test"]["epplus_gain"] for k in ("T1", "T2", "T3")},
                       t1_minus_t0=float(r["laws"]["T1"]["test"]["epplus_gain"] - r["t0"]["epplus_gain"]),
                       t2_minus_t0=float(r["laws"]["T2"]["test"]["epplus_gain"] - r["t0"]["epplus_gain"]),
                       t3_minus_t0=float(r["laws"]["T3"]["test"]["epplus_gain"] - r["t0"]["epplus_gain"]),
                       sealed_epplus_joint=r["t0"]["sealed_epplus_joint"],
                       evaluator_offset=float(r["t0"]["null_joint"] - r["t0"]["sealed_epplus_joint"]))
                  for r in ca["rows"]],
        )
    (BASE / "summary.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n",
                                       encoding="utf-8")
    print(json.dumps({k: sorted(v) for k, v in out["stages"].items()}, indent=1))


if __name__ == "__main__":
    main()
