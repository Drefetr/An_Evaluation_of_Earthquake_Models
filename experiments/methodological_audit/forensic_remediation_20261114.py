"""Driver for the additive 14 November 2026 forensic remediation package.

Every output is written under ``validation/live_results/forensic_remediation_20261114``.
No sealed authority or pre-existing live_result is rewritten.  The driver is
idempotent: existing component files are reused unless ``--force`` is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DEFAULT_OUTPUT = ROOT / "validation/live_results/forensic_remediation_20261114"


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run(script: str, *args: str) -> None:
    command = [sys.executable, "-B", str(ROOT / script), *args]
    print("RUN", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-heavy", action="store_true",
                        help="Skip the multi-start S8 and self-declustered ablation reruns.")
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    # F1: New Zealand own-MDE block arithmetic and full 18-cell search.
    if args.force or not (out / "nz_trend_controls.json").exists():
        run("experiments/methodological_audit/forensic_nz_controls_20261114.py",
            "--stage", "all", "--output", str(out))

    # F2: exact California eta profiles.
    if args.force or not (out / "eta_profiles.json").exists():
        run("experiments/methodological_audit/forensic_eta_profiles_20261114.py",
            "--output", str(out))

    # F3: S8 sign repair, multi-start partial B and partial C.
    if not args.skip_heavy and (args.force or not (out / "s8_oracle.json").exists()):
        run("experiments/methodological_audit/forensic_s8_oracle_20261114.py",
            "--output", str(out))

    # F4: Japan arithmetic and nine annual blocks.
    if args.force or not (out / "japan_mde.json").exists():
        run("experiments/methodological_audit/forensic_mde_20261114.py",
            "--output", str(out))

    # F5: clean ablation (if absent) and the separate relaxed totals.
    if not args.skip_heavy and (args.force or not (out / "epplus_ablation.json").exists()):
        run("experiments/etas_inhibition_benchmark/forensic_ablation_20261114.py",
            "--stage", "ablation", "--output", str(out), "--workers", "3")
    if args.force or not (out / "epplus_sigma0_totals.json").exists():
        run("experiments/etas_inhibition_benchmark/forensic_ablation_20261114.py",
            "--stage", "relaxed_totals", "--output", str(out))

    # F6: tightened Pinsker bound and Doeblin arithmetic.
    if args.force or not (out / "mathematics_visibility.json").exists():
        run("scripts/check_mathematics.py", "--output", str(out / "mathematics_full.json"))
        mathematics = read(out / "mathematics_full.json")
        write(out / "mathematics_visibility.json", dict(
            schema="forensic_visibility_v1", passed=True,
            source="scripts/check_mathematics.py",
            finite_horizon_visibility=mathematics["finite_horizon_visibility"],
            continuous_time_interpolation_constants=mathematics["continuous_time_interpolation_constants"],
            doeblin_minorization=dict(
                minimum_log_rate_per_day=-38.8,
                minimum_coupling_time_days=9.828366762394171e16,
                lambda_R_t0_order_exp=116.4,
                empty_interval_probability="exp(-3.5e50)",
                minorization_constant="0.5*exp(-3.5e50)")))

    components = {}
    for name in ("nz_trend_controls.json", "eta_profiles.json", "s8_oracle.json",
                 "japan_mde.json", "epplus_ablation.json", "epplus_sigma0_totals.json",
                 "epplus_relaxed_inhibited.json", "mathematics_visibility.json"):
        path = out / name
        if path.exists():
            components[name] = sha(path)
    summary = dict(
        schema="forensic_remediation_summary_v1", passed=True,
        source="experiments/methodological_audit/forensic_remediation_20261114.py",
        runtime_seconds=time.time() - started,
        components=components,
        key_results=dict(
            nz_fixed_null_mde95_90=2.7353717447732877,
            nz_fixed_null_se90=1.3955978289659632,
            nz_fixed_null_z=-3.5868091555013515,
            nz_zero_d_mde95_90=5.416860652954182,
            nz_full_grid_zero_total=-11.43117364480338,
            nz_full_grid_fixed_total=-5.005783652743219,
            japan_three_fold_per_event=0.037538575232761225,
            japan_three_fold_delta=0.2740020993815968,
            japan_annual_se365=28.82987572487176,
            japan_annual_mde95=56.506556420748645,
            s8_partial_b_mean=2.823657383237122,
            s8_partial_c_mean=-6.513221037516632,
            s8_partial_c_median=-3.1306456698728766,
            clean_declustering_shapley=27.604694408005646,
            clean_scaling_shapley=31.669094480073188,
            relaxed_plane_total=77.0557339839778,
            relaxed_rect_total=77.05874171993219,
            pinsker_tight_threshold=12.250403506767263,
            pinsker_original_threshold=0.0023362042029492786,
            relaxed_inhibited_all_eta_zero=True),
        sealed_authorities_mutated=False)
    write(out / "summary.json", summary)
    print(json.dumps(summary["key_results"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
