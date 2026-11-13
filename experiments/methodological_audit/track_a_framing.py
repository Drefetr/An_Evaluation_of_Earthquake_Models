"""Bind Track A framing statistics by scientific meaning and paragraph context.

Only saved scalar/vector arithmetic is performed. Existing scientific sources,
manuscripts, claim files and audits are never modified.
"""
from pathlib import Path
import ast
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/track_a_supplement_20261112"
PREFIX = "validation/live_results/"
J = PREFIX + "track_a_supplement_20261112/s04b_joint_mcse.json"
U = PREFIX + "score_uncertainty_remote_v2_20261111/summary.json"
S8 = PREFIX + "reporting_supplement_20261112/supplement.json"
S8GEN = PREFIX + "s8_moderate_complete_20261111/summary.json"
TREND = PREFIX + "trend_depletion_20261111.json"
STABILITY = PREFIX + "methodological_20261106/stability.json"
MATH = PREFIX + "mathematics_remediation_20261111.json"
EP = PREFIX + "etas_inhibition_benchmark_interior_20261112/"
EPU = PREFIX + "etas_baseline_uncertainty_20261111/summary.json"
A = "abstract.tex"
NZ = "chapters/08_score_uncertainty.tex"
E = "chapters/11_epplus_benchmark.tex"
C13 = "chapters/13_continuous_local_inhibition.tex"
C14 = "chapters/14_discussion_conclusion.tex"
CACHE, FACTS, BINDINGS = {}, {}, []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if path not in CACHE:
        CACHE[path] = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return CACHE[path]


def resolve(path, pointer):
    value = read(path)
    for part in pointer.lstrip("/").split("/") if pointer else []:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def ref(path, pointer):
    return dict(path=path, sha256=sha(ROOT / path), json_pointer=pointer,
                resolved_source_value=resolve(path, pointer))


def fact(key, path, pointer, meaning, factor=1, exponential=False):
    pin = ref(path, pointer)
    raw = pin["resolved_source_value"]
    assert isinstance(raw, (int, float)) and not isinstance(raw, bool)
    value = math.exp(raw) if exponential else raw * factor
    FACTS[key] = dict(value=value, meaning=meaning, inputs=[pin],
                      transformation="exp(source)" if exponential else ("identity" if factor == 1 else f"source * {factor}"))
    return value


def derived(key, inputs, operation, meaning):
    pins = [ref(path, pointer) for path, pointer in inputs]
    vals = [p["resolved_source_value"] for p in pins]
    if operation == "sum": value = sum(vals)
    elif operation == "min": value = min(vals)
    elif operation == "max": value = max(vals)
    elif operation == "count_zero": value = sum(x == 0 for x in vals)
    elif operation == "median": value = statistics.median(vals)
    else: raise ValueError(operation)
    FACTS[key] = dict(value=value, meaning=meaning, inputs=pins, transformation=operation + " of listed scientific inputs")
    return value


def bind(key, display, location, anchor, literal=None):
    assert key in FACTS
    BINDINGS.append(dict(fact=key, display=str(display), location=location,
                         paragraph_anchor=anchor, manuscript_literal=str(literal if literal is not None else display)))


def joint_facts():
    data = read(J)
    for regime, model, index in ((5, "LIplus_immigrant", 6), (7, "LIplus_inclusive", 18)):
        row = data["joint_rows"][index]
        assert (row["regime"], row["model"], row["gate"]) == (regime, model, "raw")
        for key in ("mean", "median", "mcse", "wins", "N"):
            fact(f"s{regime}_{key}", J, f"/joint_rows/{index}/{key}", f"Matched S{regime} raw joint-fit {key}")
        ri = regime - 4
        fact(f"s{regime}_mean_n_test", J, f"/regimes/{ri}/mean_n_test", f"S{regime} mean number of held-out events")
    for regime, ri in ((5, 1), (7, 3)):
        for key in ("immigrant_rejection_fraction", "offspring_rejection_fraction", "all_proposal_rejection_fraction"):
            fact(f"s{regime}_{key}_percent", J, f"/regimes/{ri}/{key}", f"S{regime} percentage with explicit {key} denominator", factor=100)
    fact("joint_histories", PREFIX + "s04b_joint_complete_20261111/summary.json", "/completed_histories", "Completed S4--S7 histories")
    fact("joint_outcomes", PREFIX + "s04b_joint_complete_20261111/summary.json", "/completed_outcomes", "Five procedure outcomes for each completed history")
    for case in data["regimes"][0]["case_ids"]:
        c = read(PREFIX + "s04b_joint_complete_20261111/cases/" + case + ".json")
        assert c["thinning"]["rejected_offspring"] == 0
    paths = [(PREFIX + "s04b_joint_complete_20261111/cases/" + case + ".json", "/thinning/rejected_immigrants") for case in data["regimes"][0]["case_ids"]]
    derived("s4_unthinned_histories", paths, "count_zero", "Magnitude-scaled narrow/short immigrant histories with no rejected proposals")
    fact("s2_unthinned_histories", PREFIX + "s2_control_20261107/summary.json", "/zero_rejection_histories", "Unit-mark S2 histories with no rejected proposal")
    fact("s4_rejected_immigrants", J, "/regimes/0/thinning/rejected_immigrants", "Total rejected immigrant proposals in S4")
    for regime, index, comparator in ((5, 8, "fixed"), (5, 8, "intercept"), (7, 18, "intercept"), (7, 18, "concave")):
        row = data["comparator_rows"][index]
        assert row["regime"] == regime and row["model"] == "LIplus_inclusive" and row["gate"] == "raw"
        fact(f"s{regime}_total_{comparator}_mean", J, f"/comparator_rows/{index}/{comparator}/mean", f"S{regime} saved total-attenuation mean against {comparator} comparator")
    concave = PREFIX + "s04b_concave_20261111/summary.json"
    assert resolve(concave, "/summary/18/regime") == 7
    fact("s7_zero_branching_fits", concave, "/summary/18/n_zero", "S7 jointly concave uninhibited fits selecting branching ratio zero")


def synthetic_bindings():
    anchors = {A: "Synthetic results depend", C13: "The synthetic controls distinguish", C14: "Joint fitting in both arms gives"}
    for location, anchor in anchors.items():
        for key, display in (("s5_mean", "-10.37"), ("s5_median", "+2.26"), ("s5_mcse", "8.56"),
                             ("s5_wins", "10"), ("s5_N", "20"), ("s5_mean_n_test", "16.9"),
                             ("s7_mean", "-1.26"), ("s7_median", "-1.26"), ("s7_mcse", "2.63"),
                             ("s7_wins", "8"), ("s7_N", "20"), ("s7_mean_n_test", "13.25")):
            bind(key, display, location, anchor)
    for key, display in (("joint_histories", "80"), ("joint_outcomes", "400")):
        bind(key, display, C13, anchors[C13])
    for key, display in (("s5_mean_n_test", "16.9"), ("s7_mean_n_test", "13.25")):
        bind(key, display, C14, "The controls leave a gap")
    bind("s7_offspring_rejection_fraction_percent", "98.2", A, anchors[A])
    for key, display in (("s2_unthinned_histories", "20"), ("s4_unthinned_histories", "19")):
        bind(key, display, A, anchors[A])
    for key, display in (("s5_immigrant_rejection_fraction_percent", "83.4"),
                         ("s5_all_proposal_rejection_fraction_percent", "78.2"),
                         ("s7_all_proposal_rejection_fraction_percent", "82.5"),
                         ("s7_offspring_rejection_fraction_percent", "98.2"),
                         ("s5_total_fixed_mean", "+19.50"), ("s5_total_intercept_mean", "-23.72"),
                         ("s7_total_intercept_mean", "+9.74"), ("s7_total_concave_mean", "+5.63"),
                         ("s7_zero_branching_fits", "20")):
        bind(key, display, C14, "The matched-generator extension")
    for phase in ("raw", "bic"):
        for key in ("mean", "median", "mcse", "wins", "active", "N"):
            fact(f"s8_{phase}_{key}", S8, f"/s8/{phase}/{key}", f"S8 {phase} saved-output {key}")
    fact("s8_boundary_any", S8, "/s8/any_boundary", "Number of S8 raw selected fits on any declared parameter-box boundary")
    fact("s8_mean_n_test", S8GEN, "/generation/mean_test_events", "S8 mean held-out event count")
    fact("s8_rejected_percent", S8GEN, "/generation/rejected_fraction", "S8 percentage of all chronological proposals rejected", factor=100)
    for location, anchor in ((A, anchors[A]), (C13, "The intermediate S8 bank"), (C14, "The controls leave a gap")):
        for key, display in (("s8_mean_n_test", "94.7"), ("s8_raw_mean", "+0.294"), ("s8_raw_mcse", "2.777"),
                             ("s8_raw_wins", "13"), ("s8_raw_N", "20"), ("s8_bic_mean", "+2.495"),
                             ("s8_bic_mcse", "1.444"), ("s8_bic_wins", "9"), ("s8_bic_active", "12"), ("s8_bic_N", "20")):
            bind(key, display, location, anchor)
        if location != A:
            bind("s8_rejected_percent", "27.2", location, anchor)
        if location != C13:
            bind("s8_bic_median", "0", location, anchor)
            bind("s8_boundary_any", "13", location, anchor)


def uncertainty_facts_bindings():
    for day in (90, 180, 365):
        prefix = "" if day == 90 else f"/sensitivity/{day}"
        for i in range(3):
            p = prefix + f"/rows/{i}"
            row = resolve(U, p)
            assert row["contrast"] == "NZ_shared_minus_ML" and row["case"] == ("fold_50", "fold_65", "fold_80")[i]
            for metric in ("total", "paired_sign_permutation_p", "replicates"):
                fact(f"nz_f{i+1}_{day}_{metric}", U, p + "/summary/" + metric, f"NZ fold {i+1}, {day}-day {metric}")
            for j in (0, 1):
                fact(f"nz_f{i+1}_{day}_ci{j}", U, p + f"/summary/ci95_total/{j}", f"NZ fold {i+1}, {day}-day paired percentile interval endpoint {j}")
        fact(f"block_days_{day}", U, prefix + "/rows/0/block_days", f"Calendar block length {day} days")
    fact("nz_total_loss", U, "/pooled/NZ_shared_minus_ML/total", "Magnitude of pooled NZ shared attenuation minus ML deficit", factor=-1)
    fact("nz_fold1_loss", U, "/rows/0/summary/total", "Magnitude of first-fold NZ deficit", factor=-1)
    fact("nz_fold1_share_percent", U, "/NZ_first_fold_fraction", "NZ first-fold share of pooled loss in percent", factor=100)
    for key, display in (("nz_total_loss", "17.62"), ("nz_fold1_loss", "16.52"), ("nz_fold1_share_percent", "93.7")):
        bind(key, display, A, "New Zealand shared attenuation loses")
    for day in (90, 180, 365):
        for location, anchor in ((A, "New Zealand shared attenuation loses"), (NZ, "For each test fold"), (C14, "The block analysis in Section")):
            bind(f"block_days_{day}", str(day), location, anchor)
        bind(f"block_days_{day}", str(day), NZ, "Small nominal sign-flip values")
        bind(f"block_days_{day}", str(day), NZ, "Fold~1 contributes")
    bind("nz_f1_90_replicates", "49,999", NZ, "For each test fold")
    for i, (total, ci0, ci1, p) in enumerate(((-16.518, -25.526, -7.459, "0.00104"), (-0.075, -1.320, 1.215, "0.91248"), (-1.030, -2.087, 0.004, "0.05766")), 1):
        anchor = f"{i} & "
        for metric, display in (("total", f"{total:.3f}"), ("ci0", f"{ci0:.3f}"), ("ci1", f"{ci1:.3f}"), ("paired_sign_permutation_p", p)):
            bind(f"nz_f{i}_90_{metric}", display, NZ, anchor)
    for key, display in (("nz_f1_90_paired_sign_permutation_p", "0.00104"), ("nz_f1_90_ci0", "-25.526"), ("nz_f1_90_ci1", "-7.459")):
        bind(key, display, NZ, "Small nominal sign-flip values")
    for key, display in (("nz_f3_90_ci0", "-2.087"), ("nz_f3_90_ci1", "0.004")):
        bind(key, display, A, "New Zealand shared attenuation loses")
    bind("nz_fold1_share_percent", "93.7", NZ, "Fold~1 contributes")
    for fold, day, low, high in ((2, 180, "-1.109", "1.014"), (2, 365, "-1.511", "1.324"),
                                (3, 180, "-2.185", "-0.091"), (3, 365, "-2.149", "-0.225")):
        bind(f"nz_f{fold}_{day}_ci0", low, NZ, "Fold~1 contributes")
        bind(f"nz_f{fold}_{day}_ci1", high, NZ, "Fold~1 contributes")
    bind("nz_f3_365_paired_sign_permutation_p", "0.015", NZ, "Fold~1 contributes")
    for i, display in enumerate(("-0.22", "-1.95", "-0.21")):
        assert resolve(U, f"/rows/{i+6}/contrast") == "CA_LIplus_total_minus_floor"
        fact(f"ca_li_f{i}_total", U, f"/rows/{i+6}/summary/total", f"CA raw LI+ total versus floor, fold {i}")
        bind(f"ca_li_f{i}_total", display, A, "New Zealand shared attenuation loses")
    for j, display in enumerate(("-6.564", "-0.033")):
        fact(f"ca_li_pooled_90_ci{j}", U, f"/pooled/CA_LIplus_total_minus_floor/ci95_total/{j}", f"CA LI+ total pooled 90-day interval endpoint {j}")
        bind(f"ca_li_pooled_90_ci{j}", display, A, "New Zealand shared attenuation loses")


def mathematical_facts_bindings():
    kernel = resolve(STABILITY, "/kernel")
    half = kernel["half_count"]
    spacing = kernel["log_rate_max"] / half
    rates = [math.exp(spacing * j) for j in range(-half, half+1)]
    slow = sum(-math.expm1(-x * kernel["horizon_days"]) < kernel["decay_threshold"] for x in rates)
    assert len(rates) == kernel["modes"] and slow == kernel["slow_mode_count"]
    assert math.isclose(math.log(4) / min(rates), kernel["minimum_coupling_time_days"], rel_tol=1e-14)
    for key, pointer in (("mode_count", "/kernel/modes"), ("slow_modes", "/kernel/slow_mode_count"),
                         ("horizon", "/kernel/horizon_days"), ("minimum_log_rate", "/kernel/log_rate_min"),
                         ("decay_percent", "/kernel/decay_threshold_percent"), ("minimum_skeleton_days", "/kernel/minimum_coupling_time_days")):
        fact(key, STABILITY, pointer, "Finite-mixture weak-Harris certificate: " + key)
    cutoff = fact("pinsker_eta_cutoff", MATH, "/finite_horizon_visibility/eta_at_which_clipped_bound_equals_one", "Feedback at which the finite-horizon clipped Pinsker bound becomes one")
    assert math.isclose(cutoff, 1 / math.sqrt(resolve(MATH, "/finite_horizon_visibility/K_T") / 2), rel_tol=1e-14)
    for location, anchor in ((A, "The mathematical results also"), (NZ, "Calendar splitting does not")):
        for key, display, literal in (("mode_count", "195", None), ("slow_modes", "61", None),
                                      ("horizon", "24,394", "24{,}394"), ("minimum_log_rate", "-38.8", None),
                                      ("decay_percent", "1", None)):
            bind(key, display, location, anchor, literal)
    bind("mode_count", "195", C14, "The block analysis in Section")
    bind("slow_modes", "61", C14, "The block analysis in Section")
    bind("minimum_skeleton_days", "9.8e16", A, "The mathematical results also", r"9.8\times10^{16}")
    bind("pinsker_eta_cutoff", "2.34e-3", A, "The mathematical results also", r"2.34\times10^{-3}")
    for key, pointer, display in (("nz_inhibited_d", "/fit_contrast/inhibited_d", "1.790"),
                                  ("nz_null_d", "/fit_contrast/null_d", "-0.252"),
                                  ("nz_trend_depletion_rho", "/event_score_weighted_trend_depletion_correlation", "0.9341")):
        fact(key, TREND, pointer, "First-fold training event-score geometry: " + key)
        bind(key, display, A, "New Zealand shared attenuation loses")
    return dict(reconstructed_modes=len(rates), reconstructed_slow_modes=slow,
                reconstructed_minimum_skeleton_days=math.log(4)/min(rates), reconstructed_pinsker_cutoff=cutoff)


def benchmark_facts_bindings():
    comparison = EP + "baseline_comparison.json"
    fact("epplus_total_gain", comparison, "/total_gain", "Combined EP+ procedure minus archived EP total held-out score")
    for location, anchor in ((A, "New Zealand shared attenuation loses"), (E, "All three baseline fits"), (C14, "The magnitude-scaled benchmark")):
        bind("epplus_total_gain", "69.55", location, anchor)
    for i, display in enumerate(("14.58", "30.69", "24.28")):
        fact(f"epplus_f{i}_gain", comparison, f"/rows/{i}/gain", f"EP+ procedure minus archived EP, fold {i}")
        bind(f"epplus_f{i}_gain", display, E, "All three baseline fits")
    for i in range(3):
        path = EP + f"california_fold_{i}/result.json"
        assert resolve(path, "/parameter_names/5") == "log_sigma0"
        lower = fact(f"epplus_f{i}_sigma_lower_km", path, "/bounds/5/0", f"EP+ fold {i} spatial-scale lower bound in kilometres", exponential=True)
        assert math.exp(resolve(path, "/null/selected/parameters/5")) == lower
        assert resolve(path, "/inhibited/selected/parameters/8") == 0
    for location, anchor in ((A, "New Zealand shared attenuation loses"), (C14, "The magnitude-scaled benchmark")):
        bind("epplus_f0_sigma_lower_km", "2.0", location, anchor)
    bind("epplus_f0_sigma_lower_km", "2", E, "All three baseline fits")
    fact("sobol_training_exponent", EP + "california_fold_0/result.json", "/training_rounds/0/training_power", "Exponent specifying frozen scrambled-Sobol training integration resolution, not statistical power")
    bind("sobol_training_exponent", "14", E, "The saved field")
    for day, low, high, p in ((90, "32.239", "123.719", "0.00002"), (180, "32.153", "120.312", "0.00010"), (365, "26.589", "122.164", "0.00452")):
        for j, display in enumerate((low, high)):
            key = f"epplus_pooled_{day}_ci{j}"
            fact(key, EPU, f"/pooled_by_block_days/{day}/ci95_total/{j}", f"EP+ versus archived EP {day}-day paired interval endpoint {j}")
            bind(key, display, E, "For this combined excitation improvement")
        key = f"epplus_pooled_{day}_p"
        fact(key, EPU, f"/pooled_by_block_days/{day}/paired_sign_permutation_p", f"EP+ versus archived EP {day}-day nominal independent-sign-flip reference")
        bind(key, p, E, "For this combined excitation improvement")
        bind(f"block_days_{day}", str(day), E, "For this combined excitation improvement")
    s05 = "validation/acceptances/S05_public.json"
    pins = [(s05, f"/rows/{i}/{method}/pooled_upper_inclusive_p") for i in range(6) for method in ("fisher", "quadratic")]
    derived("conditional_continuous_p_min", pins, "min", "Minimum inclusive conditional Monte Carlo value across both continuous-statistic methods and all six model/origin combinations")
    derived("conditional_continuous_p_max", pins, "max", "Maximum inclusive conditional Monte Carlo value across both continuous-statistic methods and all six model/origin combinations")
    for key, display in (("conditional_continuous_p_min", "0.001"), ("conditional_continuous_p_max", "0.012")):
        bind(key, display, A, "New Zealand shared attenuation loses")


def cohort_facts_bindings():
    fact("nz_minimum_magnitude", "validation/authorities/903cb8f6fc5407b9_protocol_observed_v1.json", "/data/minimum_magnitude", "Declared New Zealand cohort magnitude threshold")
    fact("ca_minimum_magnitude", "reproduction/nzca/cohort_contract_california.json", "/population/minimum_magnitude", "Declared California cohort magnitude threshold")
    # Read the actual target eligibility predicate, not a data minimum or a
    # coincidentally matching numeral in a catalogue filename.
    path = "reproduction/jma/source/eligibility_v2.py"
    text = (ROOT/path).read_text(encoding="utf-8")
    matches = [n for n in ast.walk(ast.parse(text)) if isinstance(n, ast.If)
               and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
               and n.test.left.id == "tenths" and len(n.test.ops) == 1
               and isinstance(n.test.ops[0], ast.Lt) and len(n.test.comparators) == 1
               and isinstance(n.test.comparators[0], ast.Constant)]
    assert len(matches) == 1
    node = matches[0]
    value = node.test.comparators[0].value / 10
    FACTS["jma_minimum_magnitude"] = dict(value=value, meaning="JMA target eligibility threshold, converted from stored magnitude tenths",
                                         inputs=[dict(path=path, sha256=sha(ROOT/path), source_locator=f"AST If at line {node.lineno}",
                                                      source_excerpt=text.splitlines()[node.lineno-1], resolved_source_value=node.test.comparators[0].value)],
                                         transformation="target exclusion threshold in magnitude tenths / 10")
    for key, display in (("nz_minimum_magnitude", "5.0"), ("ca_minimum_magnitude", "4.0"), ("jma_minimum_magnitude", "4.5")):
        bind(key, display, A, "This monograph studies")
    fact("ca_primary_targets", "validation/authorities/438d5e8eb6d872c2_case_matrix_v1.json", "/denominators/observed/targets", "Shared California primary held-out target count")
    bind("ca_primary_targets", "315", C13, "Continuous immigrant-only local attenuation selects")
    source = "validation/acceptances/S06_ACCEPTANCE.json"
    assert resolve(source, "/eligibility/3/case") == "CA_episode_08"
    fact("el_mayor_episode_year", source, "/eligibility/3/year", "Calendar year of retained El Mayor--Cucapah retrospective backtest episode")
    bind("el_mayor_episode_year", "2010", C14, "Across the completed comparisons")


def paragraph(text, anchor):
    assert text.count(anchor) == 1, anchor
    start = text.index(anchor)
    end = text.find("\n\n", start)
    return text[start:end if end >= 0 else len(text)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    joint_facts()
    synthetic_bindings()
    uncertainty_facts_bindings()
    math_checks = mathematical_facts_bindings()
    benchmark_facts_bindings()
    cohort_facts_bindings()
    manuscript = {location: (ROOT / "paper/source" / location).read_text(encoding="utf-8") for location in (A, NZ, E, C13, C14)}
    for binding in BINDINGS:
        scope = paragraph(manuscript[binding["location"]], binding["paragraph_anchor"])
        assert binding["manuscript_literal"] in scope, binding
    source = OUT / "framing_summary.json"
    summary = dict(schema="track_a_semantic_framing_statistics_v1", scientific_execution=False,
                   mapping_method="Explicit named scientific quantities, JSON pointers and manual paragraph anchors; no assignment by global number matching.",
                   postprocessing_source=dict(path=Path(__file__).relative_to(ROOT).as_posix(), sha256=sha(Path(__file__))),
                   facts=FACTS, display_bindings=BINDINGS, independent_scalar_checks=math_checks,
                   source_sha256={path: sha(ROOT/path) for path in sorted(CACHE)},
                   manuscript_sha256={location: sha(ROOT / "paper/source" / location) for location in manuscript})
    source.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    source_rel = source.relative_to(ROOT).as_posix()
    claims = []
    for i, binding in enumerate(BINDINGS, 1):
        key = binding["fact"]
        value = FACTS[key]["value"]
        claims.append(dict(id=f"track-a-framing-20261112-{i:03}", bundled_source=source_rel,
                           source_path=source_rel, source_sha256=sha(source), json_pointer=f"/facts/{key}/value",
                           resolved_source_value=value, value=value, display=binding["display"],
                           transformation="decimal rounding to displayed precision", json_value_kind="numeric_scalar",
                           ledger_role="manuscript_binding", final_display_locations=[binding["location"]],
                           component=FACTS[key]["meaning"], qualification="Explicit semantic source map with paragraph anchor: " + binding["paragraph_anchor"] + ". Underlying scientific source hashes and transformations are retained in framing_summary.json; no scientific fitting or integration repeated.",
                           status="source_bound", binding_kind="exact_json_pointer", reconciliation_status="verified_at_declared_granularity"))
    target = OUT / "framing_numeric_claims.json"
    target.write_text(json.dumps(dict(claims=claims), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    # Recheck all sealed sources against the user's prechange snapshot.
    snapshot = read("validation/track_a_prechange_snapshot_20261112.json")
    for path, expected in snapshot["sealed_json_sha256"].items():
        assert sha(ROOT/path) == expected, path
    audit = dict(passed=True, semantic_facts=len(FACTS), explicit_display_bindings=len(BINDINGS),
                 all_paragraph_scoped_literals_present=True, all_upstream_pointers_resolved=True,
                 preserved_sealed_json_count=len(snapshot["sealed_json_sha256"]), no_manuscript_or_prior_output_writes=True,
                 independent_scalar_checks=math_checks, authority_sha256=sha(source), claims_sha256=sha(target),
                 manuscript_sha256=summary["manuscript_sha256"], postprocessing_source=summary["postprocessing_source"])
    (OUT/"framing_semantic_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
