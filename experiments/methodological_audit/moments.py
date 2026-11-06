"""Recompute exponential-mark moment conditions from shipped source parameters.

No catalogue, random-number generation, optimization or simulation is performed.
Run from any directory:
    python -B experiments/methodological_audit/moments.py
    python -B experiments/methodological_audit/moments.py --check
The statements concern ideal, unstopped, continuous exponential mark laws.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "validation/live_results/methodological_20261106/moments.json"
ARCHIVE = "reproduction/s02/completed_inputs_20261031.zip"
PREFIX = "source/research_runs/scientific_stage2_resume_20261031T205913Z/temporal/source/"
MEMBERS = {
    "recipe": "contracts/original/S02_STAGED_RECIPE.json",
    "wrapper": PREFIX + "s02_campaign.py",
    "features": PREFIX + "cached_stage2.cpp",
    "oracle": "source/research_f_continuation/engine/iteration_17/code/oracle_likelihood.py",
}
SPATIAL = "reproduction/synthetic/source/generator.py"
SPATIAL_FEATURES = "reproduction/synthetic/source/cpu_reference.cpp"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def constant_expression(node: ast.expr) -> float:
    """Accept only the source's numeric gamma expression, never arbitrary code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return constant_expression(node.left) * constant_expression(node.right)
    if (isinstance(node, ast.Call) and not node.keywords and len(node.args) == 1
            and isinstance(node.func, ast.Attribute) and node.func.attr == "log"
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "math"):
        return math.log(constant_expression(node.args[0]))
    raise ValueError("Unexpected numeric source expression")


def gamma_from_source(source: str) -> float:
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "GAMMA" for t in node.targets)):
            return constant_expression(node.value)
    raise ValueError("Missing GAMMA source assignment")


def law_defaults(source: str) -> dict[str, float]:
    law = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "Law")
    return {
        n.target.id: constant_expression(n.value)
        for n in law.body
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        and n.target.id in {"beta", "r", "n"}
    }


def candidate_ratios(source: str) -> dict[str, float]:
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.For) and isinstance(node.target, ast.Tuple)
                and [getattr(t, "id", None) for t in node.target.elts] == ["method", "r"]):
            pairs = ast.literal_eval(node.iter)
            return {name: float(value) for name, value in pairs}
    raise ValueError("Missing S02 candidate-ratio loop")


def moment(beta: float, ratio: float, gamma: float, scale: float,
           stress_power: int, productivity_power: int) -> dict:
    """E[g(Q)^p kappa(Q)^q] for Q~Exp(beta), g=C exp(gamma Q)."""
    margin = beta - stress_power * gamma - productivity_power * ratio * beta
    finite = margin > 0
    return {
        "stress_power": stress_power,
        "productivity_power": productivity_power,
        "integrability_margin": margin,
        "finite": finite,
        "value": (scale ** stress_power * (1-ratio) ** productivity_power
                  * beta / margin) if finite else None,
        "nonfinite_value": None if finite else "positive_infinity",
    }


def row(beta: float, ratio: float, gamma: float, scale: float, transform: str) -> dict:
    powers = {
        "stress_first": (1, 0),
        "stress_second": (2, 0),
        "productivity_second": (0, 2),
        "immigrant_ratio": (2, -1),
        "total_diagonal_second": (2, 1),
        "total_diagonal_first": (1, 1),
    }
    return {
        "beta": beta, "productivity_ratio": ratio, "gamma": gamma,
        "stress_scale": scale, "stress_transform": transform,
        "moments": {name: moment(beta, ratio, gamma, scale, *power)
                    for name, power in powers.items()},
    }


def calculate() -> dict:
    raw_archive = (ROOT / ARCHIVE).read_bytes()
    with zipfile.ZipFile(ROOT / ARCHIVE) as archive:
        member_bytes = {key: archive.read(name) for key, name in MEMBERS.items()}
    recipe = json.loads(member_bytes["recipe"])
    beta = float(recipe["law"]["beta"])
    ratios = candidate_ratios(member_bytes["wrapper"].decode("utf-8"))
    gamma = gamma_from_source(member_bytes["oracle"].decode("utf-8"))
    features = member_bytes["features"].decode("utf-8")
    if "stress=std::exp(gamma*excess[i])/std::exp(gamma)" not in features:
        raise ValueError("Archived temporal stress transform changed; review required")
    if "prod=(1-ratio)*std::exp(beta*ratio*excess[i])" not in features:
        raise ValueError("Archived temporal productivity transform changed; review required")
    spatial_bytes = (ROOT / SPATIAL).read_bytes()
    spatial_source = spatial_bytes.decode("utf-8")
    spatial = law_defaults(spatial_source)
    spatial_gamma = gamma_from_source(spatial_source)
    if gamma != spatial_gamma:
        raise ValueError("Temporal and spatial gamma differ; review required")
    spatial_features = (ROOT / SPATIAL_FEATURES).read_bytes()
    if b"parent_g[j]=std::exp(gamma*f.parents[6*j+3])" not in spatial_features:
        raise ValueError("Spatial stress transform changed; review required")
    rows = {
        "temporal_s02_m1": row(beta, ratios["M1"], gamma, math.exp(-gamma),
                              "exp(gamma*(Q-1))"),
        "temporal_s02_m2": row(beta, ratios["M2"], gamma, math.exp(-gamma),
                              "exp(gamma*(Q-1))"),
        "spatial_li_plus": row(spatial["beta"], spatial["r"], gamma, 1.,
                               "exp(gamma*Q)"),
        "spatial_unit_li": row(spatial["beta"], spatial["r"], 0., 1., "1"),
    }
    return {
        "schema_version": 1,
        "scope": "Analytic exponential-mark moments only; not simulation, fitting or held-out loss attribution.",
        "ideal_law": "Unstopped continuous exponential marks; S02 fresh-mark interpretation is h=0.",
        "formula": "E[g^p*kappa^q]=C^p*(1-r)^q*beta/(beta-p*gamma-q*r*beta) for positive denominator; otherwise infinity.",
        "source_sha256": {
            ARCHIVE: sha(raw_archive),
            SPATIAL: sha(spatial_bytes),
            SPATIAL_FEATURES: sha(spatial_features),
            "experiments/methodological_audit/moments.py": sha(Path(__file__).read_bytes()),
        },
        "archive_member_sha256": {MEMBERS[k]: sha(value) for k, value in member_bytes.items()},
        "two_gamma": 2*gamma,
        "rows": rows,
        "limits": [
            "The immigrant ratio moment is a sufficient-condition input; divergence alone is not a score-variance proof.",
            "The manuscript's first-parent argument supplies null divergence under its additional kernel and fresh-mark assumptions.",
            "Total diagonal moments are necessary obstructions, not a sufficient cross-parent moment theorem.",
            "Positive generating eta, persistent marks, misspecified scores and capped machine output distributions are separate.",
            "No causal explanation of saved held-out losses or parameter selection is inferred.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Check the saved JSON without changing it")
    args = parser.parse_args()
    encoded = json.dumps(calculate(), indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    if args.check:
        if args.output.read_text(encoding="utf-8") != encoded:
            raise SystemExit("Moment diagnostic differs from saved JSON")
        print("Moment diagnostic matches saved JSON")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

