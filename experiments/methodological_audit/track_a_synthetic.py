"""Track A saved-output reporting: no fitting, simulation, or integration.

Read the sealed per-history scientific outputs, compute sample Monte Carlo
standard errors, and render the two owned manuscript fragments. All derived
JSON is written to a new reporting directory; no scientific JSON is modified.
"""
from pathlib import Path
import hashlib
import json
import math
import re
import statistics

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/live_results/track_a_supplement_20261112"
JOINT = ROOT / "validation/live_results/s04b_joint_complete_20261111"
CONCAVE = ROOT / "validation/live_results/s04b_concave_20261111"
INTERCEPT = ROOT / "validation/live_results/methodological_20261106/refitted_floor"
JTEX = ROOT / "paper/source/chapters/13_s04b_joint_dispositions.tex"
RTEX = ROOT / "paper/source/chapters/13_s04_refitted_floor.tex"
PROCEDURES = [("LI", "raw"), ("LIplus_immigrant", "raw"),
              ("LIplus_immigrant", "BIC"), ("LIplus_inclusive", "raw"),
              ("LIplus_inclusive", "BIC")]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def stats(values):
    n = len(values)
    assert n == 20 and all(math.isfinite(x) for x in values)
    return dict(N=n, mean=statistics.mean(values), median=statistics.median(values),
                sample_sd=statistics.stdev(values),
                mcse=statistics.stdev(values) / math.sqrt(n),
                wins=sum(x > 0 for x in values), values=values)


def outcome(case, model, gate):
    matches = [o for o in case["outcomes"] if (o["model"], o["gate"]) == (model, gate)]
    assert len(matches) == 1
    return matches[0]


def label(model, gate, joint=False):
    name = {"LI": "LI", "LIplus_immigrant": "LI+ immigrant",
            "LIplus_inclusive": "LI+ total"}[model]
    return name + (f" ({gate})" if joint else (" gated" if gate == "BIC" else ""))


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-10), (a, b)


def collect():
    source_paths = [JOINT / "summary.json", CONCAVE / "summary.json"]
    joint_cases = []
    for path in sorted((JOINT / "cases").glob("*.json")):
        joint_cases.append(read(path))
        source_paths.append(path)
    assert len(joint_cases) == 80
    old_summary = read(JOINT / "summary.json")
    assert old_summary["completed_histories"] == 80
    assert old_summary["completed_outcomes"] == 400
    old_rows = {(r["regime"], r["model"], r["gate"]): r for r in old_summary["summary"]}
    old_concave = {(r["regime"], r["model"], r["gate"]): r for r in read(CONCAVE / "summary.json")["summary"]}
    refitted, intercept = {}, {}
    for case in joint_cases:
        for folder, target in ((CONCAVE, refitted), (INTERCEPT, intercept)):
            path = folder / (case["case_id"] + ".json")
            target[case["case_id"]] = read(path)
            source_paths.append(path)
    regimes, joint_rows, comparator_rows, components = [], [], [], []
    for regime in range(4, 8):
        cases = [c for c in joint_cases if c["regime"] == regime]
        assert len(cases) == 20 and all(c["passed"] for c in cases)
        thin = {k: sum(c["thinning"][k] for c in cases) for k in
                ("accepted_immigrants", "rejected_immigrants", "accepted_offspring", "rejected_offspring")}
        proposed_imm = thin["accepted_immigrants"] + thin["rejected_immigrants"]
        proposed_off = thin["accepted_offspring"] + thin["rejected_offspring"]
        regimes.append(dict(regime=regime, N=len(cases),
                            mean_n_train=statistics.mean(c["n_train"] for c in cases),
                            mean_n_test=statistics.mean(c["n_test"] for c in cases),
                            n_train=[c["n_train"] for c in cases], n_test=[c["n_test"] for c in cases],
                            case_ids=[c["case_id"] for c in cases], thinning=thin,
                            immigrant_proposals=proposed_imm, offspring_proposals=proposed_off,
                            all_proposals=proposed_imm + proposed_off,
                            immigrant_rejection_fraction=thin["rejected_immigrants"] / proposed_imm,
                            offspring_rejection_fraction=thin["rejected_offspring"] / proposed_off,
                            all_proposal_rejection_fraction=(thin["rejected_immigrants"] + thin["rejected_offspring"]) / (proposed_imm + proposed_off)))
        for model, gate in PROCEDURES:
            values = [outcome(c, model, gate)["new_gain"] for c in cases]
            row = dict(regime=regime, model=model, gate=gate, **stats(values))
            prior = old_rows[(regime, model, gate)]
            close(row["mean"], prior["mean_gain"])
            close(row["median"], prior["median_gain"])
            assert row["wins"] == prior["wins"] and row["N"] == prior["N"]
            row.update(wilson95=prior["wilson95"], primary=prior["primary"])
            joint_rows.append(row)
            cc = [refitted[c["case_id"]] for c in cases]
            oo = [intercept[c["case_id"]] for c in cases]
            co = [outcome(c, model, gate) for c in cc]
            io = [outcome(c, model, gate) for c in oo]
            for a, b in zip(co, io):
                close(a["original_gain"], b["original_gain"])
                close(a["new_gain"], b["new_gain"])
                assert a["original_off_floor"] == b["original_off_floor"]
            comparator_rows.append(dict(regime=regime, model=model, gate=gate, N=20,
                                        fixed=stats([o["original_gain"] for o in co]),
                                        intercept=stats([o["new_gain"] for o in co]),
                                        concave=stats([o["concave_gain"] for o in co]),
                                        active=sum(o["original_off_floor"] for o in co)))
            reference = old_concave[(regime, model, gate)]
            close(comparator_rows[-1]["concave"]["mean"], reference["mean_gain"])
            assert comparator_rows[-1]["concave"]["wins"] == reference["wins"]
            assert comparator_rows[-1]["active"] == reference["active"]
        for c in cases:
            old = intercept[c["case_id"]]
            assert old["phases"]["train"]["n_events"] == c["n_train"]
            assert old["phases"]["test"]["n_events"] == c["n_test"]
        components.append(dict(regime=regime, **{key: stats([
            intercept[c["case_id"]]["phases"]["test"]["delta"][key] for c in cases])
            for key in ("P", "C", "joint")}))
    return dict(schema="track_a_synthetic_sample_mcse_v1",
                definition=dict(sample_sd_ddof=1, mcse="sample standard deviation / sqrt(number of independent synthetic histories)",
                                fixed_analysis_histories_per_regime=20,
                                scope="Monte Carlo error of the simulation mean; not a confidence interval for one catalogue and not a physical detection test"),
                source_files=[dict(path=relative(p), sha256=sha(p)) for p in source_paths],
                regimes=regimes, joint_rows=joint_rows, comparator_rows=comparator_rows,
                floor_components=components)


def event_subheader(regime, ncols):
    return (r"\multicolumn{" + str(ncols) + r"}{@{}l}{\textbf{S" + str(regime["regime"]) +
            r"}: mean $N_{\mathrm{train}}=" + f'{regime["mean_n_train"]:.2f}' +
            r"$, $N_{\mathrm{test}}=" + f'{regime["mean_n_test"]:.2f}' + r"$} \\")


def replace_table(text, table_label, replacement):
    pattern = r"\\begin\{table\}.*?\\end\{table\}"
    matches = [m for m in re.finditer(pattern, text, re.S) if r"\label{" + table_label + "}" in m.group()]
    assert len(matches) == 1, table_label
    m = matches[0]
    return text[:m.start()] + replacement + text[m.end():]


def render(payload):
    lines = [r"\begin{table}[htbp]", r"\centering\footnotesize", r"\setlength{\tabcolsep}{2.3pt}",
             r"\caption{Held-out joint-score gains against the jointly training-refitted uninhibited comparator, in nats. MCSE is the sample standard deviation divided by the square root of the number of histories. Wins are strictly positive gains; Wilson intervals quantify the win probability. Marked rows are the matched broad/long contrasts.}",
             r"\label{tab:s04b-joint-disposition-scores}", r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
             r"Regime & Procedure & Computed & Mean & MCSE & Median & Wins & Wilson interval \\", r"\midrule"]
    for regime in payload["regimes"]:
        if regime["regime"] != 4:
            lines.append(r"\addlinespace")
        lines.append(event_subheader(regime, 8))
        for row in payload["joint_rows"]:
            if row["regime"] != regime["regime"]:
                continue
            proc = label(row["model"], row["gate"], True) + (r"$^{\dagger}$" if row["primary"] else "")
            low, high = row["wilson95"]
            lines.append(f'S{row["regime"]} & {proc} & {row["N"]}/20 & {row["mean"]:.4f} & {row["mcse"]:.4f} & {row["median"]:.4f} & {row["wins"]}/20 & [{low:.4f}, {high:.4f}] ' + r"\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    joint_text = replace_table(JTEX.read_text(encoding="utf-8"), "tab:s04b-joint-disposition-scores", "\n".join(lines))
    JTEX.write_text(joint_text, encoding="utf-8")
    lines = [r"\begin{table}[H]\centering\footnotesize", r"\setlength{\tabcolsep}{2pt}",
             r"\caption{S04B comparator sensitivity. Cells give mean held-out gain (MCSE), in nats, against the fixed floor, training-fitted intercept, and jointly fitted $(a,n)$ comparator. MCSE is the sample standard deviation divided by the square root of the number of histories. The two win columns count strictly positive contrasts against their respective fitted comparators. Active counts describe the saved attenuation procedure; original gates are unchanged. A gate returning the original fixed floor can beat a refitted floor without selecting inhibition.}\label{tab:s04b-refitted-floor}",
             r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule Regime & Saved procedure & \shortstack{Fixed\\floor} & \shortstack{Fitted\\intercept} & \shortstack{Fitted\\$(a,n)$} & \shortstack{Wins\\$a$} & \shortstack{Wins\\$(a,n)$} & Active\\\midrule"]
    for regime in payload["regimes"]:
        if regime["regime"] != 4:
            lines.append(r"\addlinespace")
        lines.append(event_subheader(regime, 8))
        for row in payload["comparator_rows"]:
            if row["regime"] != regime["regime"]:
                continue
            cells = [f'{row[k]["mean"]:.4f} ({row[k]["mcse"]:.4f})' for k in ("fixed", "intercept", "concave")]
            lines.append(f'S{row["regime"]} & {label(row["model"], row["gate"])} & ' + " & ".join(cells) + f' & {row["intercept"]["wins"]}/20 & {row["concave"]["wins"]}/20 & {row["active"]}/20' + r"\\")
    lines.append(r"\bottomrule\end{tabular}\end{table}")
    text = replace_table(RTEX.read_text(encoding="utf-8"), "tab:s04b-refitted-floor", "\n".join(lines))
    lines = [r"\begin{table}[htbp]\centering\small",
             r"\caption{Held-out change from the fixed to the training-fitted uninhibited floor. Cells give mean (MCSE), using the same histories as Table~\ref{tab:s04b-refitted-floor}; $C=-E$ is signed exposure and the mark contrast is zero.}\label{tab:s04b-floor-components}",
             r"\begin{tabular}{@{}lrrr@{}}\toprule Regime & $\Delta P$ & $\Delta C$ & $\Delta$ joint\\\midrule"]
    for regime, row in zip(payload["regimes"], payload["floor_components"]):
        lines.append(event_subheader(regime, 4))
        lines.append(f'S{row["regime"]} & ' + " & ".join(f'{row[k]["mean"]:.4f} ({row[k]["mcse"]:.4f})' for k in ("P", "C", "joint")) + r"\\")
    lines.append(r"\bottomrule\end{tabular}\end{table}")
    text = replace_table(text, "tab:s04b-floor-components", "\n".join(lines))
    # Retain the established numerical prose, adding the corresponding MCSEs.
    def selected(regime, model):
        return next(r for r in payload["comparator_rows"] if (r["regime"], r["model"], r["gate"]) == (regime, model, "raw"))
    def estimate(row, comparator):
        return f'{row[comparator]["mean"]:.4f} ({row[comparator]["mcse"]:.4f})'
    s5imm, s5total, s7total = selected(5, "LIplus_immigrant"), selected(5, "LIplus_inclusive"), selected(7, "LIplus_inclusive")
    s7joint = next(r for r in payload["joint_rows"] if (r["regime"], r["model"], r["gate"]) == (7, "LIplus_inclusive", "raw"))
    text = re.sub(r"Refitting the intercept reduces.*\Z",
                  f'Refitting the intercept reduces the broad/long immigrant mean gain from {estimate(s5imm, "fixed")} to {estimate(s5imm, "intercept")} nats and reverses the misspecified S5 total procedure from {estimate(s5total, "fixed")} to {estimate(s5total, "intercept")} nats. In S7, freeing $(a,n)$ further reduces the total-procedure residual from {estimate(s7total, "intercept")} to {estimate(s7total, "concave")} nats; the fully joint temporal comparison in the next subsection reverses that residual to {s7joint["mean"]:.4f} ({s7joint["mcse"]:.4f}) nats. Parentheses give MCSEs. The S4 gated procedures have 13/20 fitted-intercept wins but only 1/20 active fits. S6 immigrant and total gates each have 15/20 wins, with respectively 0/20 and 1/20 active fits. These wins therefore mostly compare two uninhibited floors and are not detections of inhibition.\n',
                  text, flags=re.S)
    RTEX.write_text(text, encoding="utf-8")


def make_claims(payload, source):
    claims = []
    source_path = relative(source)
    def claim(pointer, value, display, location):
        claims.append(dict(id="track-a-synthetic-20261112-" + str(len(claims) + 1).zfill(3),
                           bundled_source=source_path, source_path=source_path, source_sha256=sha(source),
                           json_pointer=pointer, resolved_source_value=value, value=value, display=str(display),
                           transformation="decimal rounding to displayed precision", json_value_kind="numeric_scalar",
                           ledger_role="manuscript_binding", final_display_locations=[location],
                           component="Track A synthetic means, sample MCSEs, event counts and comparator win census",
                           qualification="Computed only from the twenty saved histories per regime; MCSE is sample sd(ddof=1)/sqrt(N). No fitting, simulation or integration repeated.",
                           status="source_bound", binding_kind="exact_json_pointer", reconciliation_status="verified_at_declared_granularity"))
    for i, row in enumerate(payload["joint_rows"]):
        location = "chapters/13_s04b_joint_dispositions.tex"
        for key in ("mean", "mcse", "median"):
            claim(f"/joint_rows/{i}/{key}", row[key], f'{row[key]:.4f}', location)
        for key in ("N", "wins"):
            claim(f"/joint_rows/{i}/{key}", row[key], row[key], location)
        for j, value in enumerate(row["wilson95"]):
            claim(f"/joint_rows/{i}/wilson95/{j}", value, f'{value:.4f}', location)
        if row["regime"] == 7 and row["model"] == "LIplus_inclusive" and row["gate"] == "raw":
            for key in ("mean", "mcse"):
                claim(f"/joint_rows/{i}/{key}", row[key], f'{row[key]:.4f}', "chapters/13_s04_refitted_floor.tex")
    for i, row in enumerate(payload["comparator_rows"]):
        location = "chapters/13_s04_refitted_floor.tex"
        for comparator in ("fixed", "intercept", "concave"):
            for key in ("mean", "mcse"):
                value = row[comparator][key]
                claim(f"/comparator_rows/{i}/{comparator}/{key}", value, f'{value:.4f}', location)
        for comparator in ("intercept", "concave"):
            value = row[comparator]["wins"]
            claim(f"/comparator_rows/{i}/{comparator}/wins", value, value, location)
        for key in ("active", "N"):
            claim(f"/comparator_rows/{i}/{key}", row[key], row[key], location)
    for i, row in enumerate(payload["floor_components"]):
        for component in ("P", "C", "joint"):
            for key in ("mean", "mcse"):
                value = row[component][key]
                claim(f"/floor_components/{i}/{component}/{key}", value, f'{value:.4f}', "chapters/13_s04_refitted_floor.tex")
    for i, row in enumerate(payload["regimes"]):
        for location in ("chapters/13_s04b_joint_dispositions.tex", "chapters/13_s04_refitted_floor.tex"):
            for key in ("mean_n_train", "mean_n_test"):
                claim(f"/regimes/{i}/{key}", row[key], f'{row[key]:.2f}', location)
    return dict(claims=claims)


def audit(payload, source, claims_path):
    # A fresh saved-output read checks both mathematical identities and custody.
    again = collect()
    assert again == payload
    all_stats = list(payload["joint_rows"])
    all_stats += [row[k] for row in payload["comparator_rows"] for k in ("fixed", "intercept", "concave")]
    all_stats += [row[k] for row in payload["floor_components"] for k in ("P", "C", "joint")]
    for row in all_stats:
        vals = row["values"]
        direct = math.sqrt(sum((x - sum(vals) / len(vals)) ** 2 for x in vals) / (len(vals) - 1) / len(vals))
        close(direct, row["mcse"])
    for pin in payload["source_files"]:
        assert sha(ROOT / pin["path"]) == pin["sha256"]
    snapshot_path = ROOT / "validation/track_a_prechange_snapshot_20261112.json"
    snapshot = read(snapshot_path)
    for path, expected in snapshot["sealed_json_sha256"].items():
        assert sha(ROOT / path) == expected, path
    prior_audit_paths = [ROOT / "validation/live_results/s04b_joint_complete_independent_audit_20261111.json",
                         CONCAVE / "audit.json"]
    prior_audits = [dict(path=relative(p), sha256=sha(p)) for p in prior_audit_paths]
    joint_text, refitted_text = JTEX.read_text(encoding="utf-8"), RTEX.read_text(encoding="utf-8")
    def table_rows(text, name):
        table = next(m.group() for m in re.finditer(r"\\begin\{table\}.*?\\end\{table\}", text, re.S) if r"\label{" + name + "}" in m.group())
        return [line.removesuffix(r"\\").strip().split(" & ") for line in table.splitlines() if re.match(r"S[4-7] & ", line)]
    for row, cells in zip(payload["joint_rows"], table_rows(joint_text, "tab:s04b-joint-disposition-scores"), strict=True):
        assert len(cells) == 8 and cells[0] == f'S{row["regime"]}'
        assert cells[2:] == [f'{row["N"]}/20', f'{row["mean"]:.4f}', f'{row["mcse"]:.4f}', f'{row["median"]:.4f}', f'{row["wins"]}/20', f'[{row["wilson95"][0]:.4f}, {row["wilson95"][1]:.4f}]']
    for row, cells in zip(payload["comparator_rows"], table_rows(refitted_text, "tab:s04b-refitted-floor"), strict=True):
        assert len(cells) == 8 and cells[0] == f'S{row["regime"]}'
        assert cells[2:5] == [f'{row[k]["mean"]:.4f} ({row[k]["mcse"]:.4f})' for k in ("fixed", "intercept", "concave")]
        assert cells[5:] == [f'{row["intercept"]["wins"]}/20', f'{row["concave"]["wins"]}/20', f'{row["active"]}/20']
    for row, cells in zip(payload["floor_components"], table_rows(refitted_text, "tab:s04b-floor-components"), strict=True):
        assert len(cells) == 4 and cells[0] == f'S{row["regime"]}'
        assert cells[1:] == [f'{row[k]["mean"]:.4f} ({row[k]["mcse"]:.4f})' for k in ("P", "C", "joint")]
    return dict(schema="track_a_synthetic_saved_output_audit_v1", passed=True,
                no_scientific_execution=True, histories=80, joint_procedure_rows=20,
                joint_outcomes=400, comparator_procedure_rows=20,
                sample_mcse_statistics_checked=len(all_stats), rendered_table_rows_checked=44,
                sample_mcse_denominator="sqrt(20); sample variance denominator 19",
                checks=["Every saved history is present and passed", "Existing joint means, medians and wins unchanged",
                        "Intercept and concave inputs agree on saved procedures and intercept scores",
                        "Event counts match joint and historical score outputs",
                        "MCSE agrees with independently written centered-sum formula",
                        "All scientific source hashes unchanged after rendering"],
                authority_path=relative(source), authority_sha256=sha(source),
                claims_path=relative(claims_path), claims_sha256=sha(claims_path),
                reporting_module=dict(path=relative(Path(__file__)), sha256=sha(Path(__file__))),
                manuscript_sha256={relative(p): sha(p) for p in (JTEX, RTEX)},
                preserved_source_count=len(payload["source_files"]),
                prechange_snapshot=dict(path=relative(snapshot_path), sha256=sha(snapshot_path)),
                preserved_sealed_json_count=len(snapshot["sealed_json_sha256"]),
                archived_prior_manuscript_sha256={relative(p): snapshot["archive"]["members"][relative(p)] for p in (JTEX, RTEX)},
                prior_scientific_audits=prior_audits,
                prior_scientific_audits_remain_unchanged=True,
                publication_adapter_change="Joint table has eight columns including MCSE. All three tables have multicolumn event-count subheaders. Comparator/component gain cells are mean (MCSE).")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    payload = collect()
    source = OUT / "s04b_joint_mcse.json"
    write(source, payload)
    render(payload)
    claims_path = OUT / "synthetic_numeric_claims.json"
    write(claims_path, make_claims(payload, source))
    write(OUT / "synthetic_table_audit.json", audit(payload, source, claims_path))
    print(json.dumps(dict(passed=True, source=relative(source), claims=len(read(claims_path)["claims"]),
                          matched=[r for r in payload["joint_rows"] if r["primary"]]), indent=2))


if __name__ == "__main__":
    main()
