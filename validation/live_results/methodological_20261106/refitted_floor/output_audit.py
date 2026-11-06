"""Saved-output arithmetic/custody audit only: no fitting, scoring, native loading."""
from pathlib import Path
import json, hashlib, math, collections, statistics, datetime
import psutil

RUN=Path(__file__).resolve().parents[1]
REPO=RUN/"checkout"
INPUT=REPO/"reproduction/synthetic"
OUT=Path(__file__).resolve().parent
FULL=RUN/"numerical_continuation/full"
PILOT=RUN/"numerical_continuation/pilot"
def read(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
maxima={}
def check(a,b,tol,kind,where):
    if not all(math.isfinite(v) for v in (a,b)):
        raise AssertionError((kind,where,"nonfinite",a,b))
    delta=abs(a-b)
    if delta>maxima.get(kind,{"absolute":-1})["absolute"]:
        maxima[kind]={"absolute":delta,"where":where}
    assert delta<=tol,(kind,where,a,b,delta,tol)
def keyed(rows,keys):
    result={tuple(row[k] for k in keys):row for row in rows}
    assert len(result)==len(rows)
    return result

full=read(FULL/"result.json");pilot=read(PILOT/"result.json")
execution=read(RUN/"numerical_continuation/execution.json")
prior=read(RUN/"numerical/execution.json")
recovery=read(RUN/"compiler_helper_recovery.json")
review=read(RUN/"review_floor_code/result.json")
protocol=read(REPO/"experiments/s04b_refitted_floor/protocol.json")
assert full["passed"] and pilot["passed"] and execution["passed"]
assert full["phase"]=="full" and pilot["phase"]=="pilot"
assert full["completed_cases"]==80 and pilot["completed_cases"]==4
assert full["historical_floor_checks"]==480 and pilot["historical_floor_checks"]==24
assert full["identity"]==pilot["identity"]
assert execution["full_result_sha256"]==sha(FULL/"result.json")
assert execution["pilot_result_sha256"]==sha(PILOT/"result.json")
assert execution["source_review_sha256"]==sha(RUN/"review_floor_code/result.json")
assert prior["source_review_sha256"]==sha(RUN/"review_floor_code/result.json")
for name,h in full["identity"]["sources"].items():
    path="experiments/s04b_refitted_floor/"+name
    assert sha(REPO/path)==h==review["reviewed_sha256"][path]
assert review["verdict"]=="PASS_SOURCE_REVIEW"
assert execution["protocol_sha256"]==full["identity"]["sources"]["protocol.json"]
assert full["identity"]["input_manifest_sha256"]==sha(INPUT/"input_manifest.json")
sourcepins=read(REPO/"experiments/s04b_refitted_floor/source_pins.json")
for name,h in sourcepins.items():assert sha(REPO/name)==h
native=REPO/"build/refitted_floor_native"
build=read(native/"build_receipt.json")
identity=full["identity"]["native"]
assert sha(native/"build_receipt.json")==identity["build_receipt_sha256"]
assert sha(native/build["libraries"]["radial"]["file"])==identity["library_sha256"]==build["libraries"]["radial"]["sha256"]
assert build["sources"]["radial.cpp"]==identity["radial_source_sha256"]==sourcepins["reproduction/synthetic/source/radial.cpp"]
manifest=read(INPUT/"input_manifest.json")
cases={c["case_id"]:c for c in manifest["s04b"]["cases"]}
entries={e["path"]:e for e in manifest["files"]}
assert len(cases)==80
assert full["inputs"]==pilot["inputs"]
for name,h in full["inputs"].items():
    assert sha(INPUT/name)==h==entries[name]["sha256"]
    assert (INPUT/name).stat().st_size==entries[name]["bytes"]
assert len(full["inputs"])==560
assert sorted(c["seed"] for c in cases.values())==[s for r in range(4,8) for s in range(410001+100*r,410021+100*r)]
pilot_reports={r["file"]:r for r in pilot["reports"]}
assert len(pilot_reports)==4
for f,p in pilot_reports.items():
    assert p["sha256"]==sha(PILOT/f)
assert len(full["reports"])==80 and len({r["file"] for r in full["reports"]})==80
source_counts=collections.Counter(r["source"] for r in full["reports"])
assert source_counts=={"exact pilot reuse":4,"new scalar training fit":76}
reports=[]
choices=collections.Counter()
all_outcomes=[]
gains=[]
residuals=[]
iterations=[]
parameters=[]
models=("LI","LIplus_immigrant","LIplus_inclusive")
for rec in full["reports"]:
    file=FULL/rec["file"]
    assert sha(file)==rec["sha256"]
    row=read(file)
    assert row["passed"] and rec["file"]==row["case_id"]+".json"
    case=cases[row["case_id"]]
    assert (row["seed"],row["regime"])==(case["seed"],case["regime"])
    if rec["source"]=="exact pilot reuse":
        assert file.read_bytes()==(PILOT/rec["file"]).read_bytes()
    else:assert rec["file"] not in pilot_reports
    for name,value in row["input_identity"].items():assert value==case[name]
    expected=read(INPUT/case["expected"])
    states=read(INPUT/case["states"])
    fits={name:read(INPUT/path) for name,path in case["fits"].items()}
    for name,fit in fits.items():
        candidates=[r for r in fit["records"] if r.get("success") and r.get("finite_feasible")]
        assert {r["start"] for r in candidates}==set(range(8)) and fit["status"]=="complete"
        candidates.append(dict(start=-1,pars=fit["floor"],nll=fit["floor_nll"]))
        best=min(candidates,key=lambda r:(r["nll"],r["start"]>=0,r["start"]))
        assert best["pars"]==fit["selected"]["pars"] and best["nll"]==fit["selected"]["nll"]
    backbone=row["fixed_backbone"]
    assert backbone==dict(a_historical=math.log(.2),d=.2,n=.35,c=.05,p=1.3,beta=2.,sigma=10.,r=.7,T0=760.)
    cfg=row["fixed_spatial_configuration"]
    assert cfg["time_mode"]=="binary64_exact_value_ties" and cfg["half_open_time_intervals"]
    assert cfg["training_interval"]==[30.,395.] and cfg["test_interval"]==[395.,760.]
    check(sum(cfg["reference_pi"]),1.,1e-14,"spatial_mass",row["case_id"])
    assert cfg["bg_floor"]==.05 and cfg["kde_xy"]==[[25.,25.],[75.,75.]] and cfg["kde_weight"]==[.5,.5]
    checks=keyed(row["historical_floor_checks"],("phase","model"))
    assert len(checks)==6
    fit=row["fit"];choices[fit["selection"]]+=1;iterations.append(fit["root_iterations"])
    assert fit["bounds_a"]==[-12.,0.] and -12.<=fit["a"]<=0.
    check(math.exp(fit["a"]),fit["b"],1e-15,"a_b_identity",row["case_id"])
    assert fit["initial_bracket_b"]==[math.exp(-12.),1.]
    assert fit["historical_a"]==backbone["a_historical"] and fit["historical_b"]==.2
    dl,du=fit["endpoint_derivatives"];assert dl>=du
    if fit["selection"]=="interior":
        assert dl>0>du and abs(fit["relative_derivative"])<=1e-9
        assert 0<fit["root_iterations"]<=200
    elif fit["selection"]=="lower":assert fit["b"]==math.exp(-12.) and fit["derivative"]<=0
    elif fit["selection"]=="upper":assert fit["b"]==1. and fit["derivative"]>=0
    else:raise AssertionError("selection")
    residuals.append(abs(fit["relative_derivative"]))
    parameters.append(fit["a"])
    assert fit["train_joint_gain"]>=-1e-9
    gains.append(fit["train_joint_gain"])
    for phase,start,end,order in (("train",30.,395.,16),("test",395.,760.,32)):
        p=row["phases"][phase];old=p["historical"];new=p["refitted"];delta=p["delta"]
        where=row["case_id"]+"/"+phase
        assert p["n_events"]==case["n_"+phase]
        assert p["n_parents"]>=p["n_events"] and p["n_parents"]>0
        # Independent closed-form integration at the reported frozen rate; no event objective evaluation.
        d=backbone["d"];T0=backbone["T0"]
        A=T0/(2*d)*(math.exp(d*(2*end/T0-1))-math.exp(d*(2*start/T0-1)))
        for label,obj,b in (("historical",old,.2),("refitted",new,fit["b"])):
            q=where+"/"+label
            assert obj["E"]>=0
            check(obj["C"],-obj["E"],0.,"signed_exposure",q)
            check(obj["joint"],obj["P"]+obj["C"]+obj["M"],1e-9,"score_decomposition",q)
            check(obj["nll"],-obj["joint"],1e-9,"nll_sign",q)
            check(obj["timing"]+obj["location"]+obj["M"],obj["joint"],1e-9,"timing_location",q)
            check(obj["E"],obj["background_exposure"]+obj["triggering_exposure"],1e-9,"exposure_split",q)
            check(obj["background_exposure"],b*A,1e-9,"background_integral",q)
            for component,value in p["formula_crosschecks"][label].items():
                check(value,0.,1e-9,"reported_formula_crosscheck",q+"/"+component)
        check(old["M"],new["M"],0.,"mark_unchanged",where)
        check(old["triggering_exposure"],new["triggering_exposure"],1e-4,"trigger_exposure_unchanged",where)
        for component in ("P","E","C","M","joint"):
            check(delta[component],new[component]-old[component],1e-9,"reported_component_delta",where+"/"+component)
        check(delta["C"],-delta["E"],0.,"signed_delta",where)
        check(delta["joint"],delta["P"]+delta["C"]+delta["M"],1e-9,"delta_decomposition",where)
        for name in models:
            floor_index=next(i for i,r in enumerate(states[name]) if r["pars"]==fits[name]["floor"])
            saved=expected["phase_values"][f"order{order}_{phase}"][name][floor_index]
            check(checks[phase,name]["saved_nll"],saved[0],0.,"saved_floor_identity",where+"/"+name)
            check(checks[phase,name]["delta"],checks[phase,name]["actual_nll"]-saved[0],1e-12,"reported_floor_delta",where+"/"+name)
            check(checks[phase,name]["actual_nll"],saved[0],1e-4,"historical_floor_match",where+"/"+name)
            check(old["nll"],saved[0],1e-4,"historical_score_to_saved_floor",where+"/"+name)
            if name=="LI":
                check(old["P"],saved[5],0.,"historical_point_identity",where)
                check(old["E"],saved[0]+saved[5]+old["M"],1e-9,"saved_exposure_reconstruction",where)
        if phase=="train":
            check(fit["train_joint_gain"],delta["joint"],1e-9,"train_gain",where)
    outcomes=keyed(row["outcomes"],("model","gate"))
    original_outcomes=keyed(expected["results"],("model","gate"))
    assert set(outcomes)==set(original_outcomes)=={("LI","raw"),("LIplus_immigrant","raw"),("LIplus_immigrant","BIC"),("LIplus_inclusive","raw"),("LIplus_inclusive","BIC")}
    for key,outcome in outcomes.items():
        name,gate=key;f=fits[name];original=original_outcomes[key]
        active=f["floor_nll"]-f["selected"]["nll"]>1.5*math.log(max(case["n_train"],1))
        chosen=f["selected"]["pars"] if gate=="raw" or active else f["floor"]
        index=original["selected_state_index"]
        assert states[name][index]["pars"]==chosen
        assert outcome["selected_state_index"]==index
        assert outcome["original_training_threshold_exceeded"]==active
        assert outcome["original_off_floor"]==original["off_floor"]==(chosen[0]>0)
        assert outcome["original_gain"]==original["gain"]
        saved=expected["phase_values"]["order32_test"][name][index]
        floor_index=next(i for i,r in enumerate(states[name]) if r["pars"]==f["floor"])
        floor=expected["phase_values"]["order32_test"][name][floor_index]
        where=row["case_id"]+"/"+name+"/"+gate
        check(outcome["saved_procedure_test_joint"],-saved[0],0.,"saved_procedure_identity",where)
        check(outcome["original_floor_test_joint"],-floor[0],0.,"original_floor_identity",where)
        check(outcome["original_gain"],floor[0]-saved[0],1e-9,"original_gain_identity",where)
        floor_delta=row["phases"]["test"]["refitted"]["joint"]+floor[0]
        check(outcome["refitted_floor_delta_joint"],floor_delta,1e-9,"floor_delta_identity",where)
        check(outcome["new_gain"],-saved[0]-row["phases"]["test"]["refitted"]["joint"],1e-9,"new_gain_direct",where)
        check(outcome["new_gain"],outcome["original_gain"]-floor_delta,1e-9,"new_gain_difference",where)
        assert outcome["new_win"]==(outcome["new_gain"]>0)
        all_outcomes.append(dict(regime=row["regime"],case_id=row["case_id"],**outcome))
    reports.append(row)
assert {r["case_id"] for r in reports}==set(cases)
summary=keyed(full["summary"],("regime","model","gate"))
assert len(summary)==20
for key,saved in summary.items():
    group=[v for v in all_outcomes if (v["regime"],v["model"],v["gate"])==key]
    assert len(group)==saved["N"]==20
    for target,source in (("original_mean_gain","original_gain"),("refitted_floor_mean_delta_joint","refitted_floor_delta_joint"),("mean_gain","new_gain")):
        check(saved[target],math.fsum(v[source] for v in group)/len(group),1e-12,"aggregate_means",str(key)+"/"+target)
    assert saved["wins"]==sum(v["new_win"] for v in group)
# Independent arithmetic check of the exact pilot projection.
p_reports=[read(PILOT/r["file"]) for r in pilot["reports"]]
assert sorted(r["seed"] for r in p_reports)==[410401,410501,410601,410701]
rate=max(r["wall_seconds"]/full["workload"][r["case_id"]] for r in p_reports)
remaining=[r for r in reports if r["seed"] not in {410401,410501,410601,410701}]
projected=3*rate*sum(full["workload"][r["case_id"]] for r in remaining)+pilot["setup_wall_seconds"]
check(full["resource_admission"]["remaining_projection_seconds"],projected,1e-12,"resource_projection","remaining")
check(full["resource_admission"]["total_projection_seconds"],projected+pilot["wall_seconds"],1e-12,"resource_projection","total")
assert projected+pilot["wall_seconds"]<7200
assert pilot["wall_seconds"]<600 and full["cumulative_wall_seconds"]<7200
# Execution/recovery evidence and logs.
assert not prior["passed"] and [p["name"] for p in prior["phases"]]==["fixtures","native_build"]
assert all(p["returncode"]==0 for p in prior["phases"])
assert prior["phases"][1]["live_owned_processes_at_return"]==[35492]
helper=recovery["terminated_exact_owned_helper"]
assert helper["pid"]==35492 and helper["created"]==prior["phases"][1]["owned_process_identities"]["35492"]
assert recovery["passed"] and recovery["remaining_owned_processes"]==[] and recovery["scientific_histories_executed"]==0
assert recovery["successful_controls_retained"]==19 and recovery["native_compile_exit_code"]==0
assert not (RUN/"numerical/pilot").exists() and not (RUN/"numerical/full").exists()
retained=execution["retained_controls_and_build"]
assert retained["execution_sha256"]==sha(RUN/"numerical/execution.json")
assert retained["recovery_sha256"]==sha(RUN/"compiler_helper_recovery.json")
assert execution["completed_unique_scalar_fits"]==80
assert [p["name"] for p in execution["phases"]]==["pilot","full"]
for folder,record in (("numerical",prior),("numerical_continuation",execution)):
    for phase in record["phases"]:
        assert sha(RUN/folder/(phase["name"]+".log"))==phase["log_sha256"]
        assert phase["sampled_peak_tree_rss"]<2**31
for p in execution["phases"]:
    assert p["returncode"]==0 and p["stop_reason"] is None and p["live_owned_processes_at_return"]==[]
fixture_log=(RUN/"numerical/fixtures.log").read_text()
assert "Ran 19 tests" in fixture_log and fixture_log.strip().endswith("OK") and "skipped" not in fixture_log.lower()
live=[]
for record in (prior,execution):
    for phase in record["phases"]:
        for pid,created in phase["owned_process_identities"].items():
            try:
                proc=psutil.Process(int(pid))
                if proc.is_running() and abs(proc.create_time()-created)<.01:live.append([int(pid),created])
            except psutil.NoSuchProcess:pass
assert not live,live
start=datetime.datetime.fromisoformat(prior["started_at_utc"])
end=datetime.datetime.fromisoformat(execution["finished_at_utc"])
elapsed=(end-start).total_seconds()
assert elapsed<7200
floor_distributions={}
for regime in range(4,8):
    values=[r["phases"]["test"]["delta"]["joint"] for r in reports if r["regime"]==regime]
    floor_distributions[str(regime)]={"N":len(values),"mean":statistics.mean(values),"min":min(values),"max":max(values),"median":statistics.median(values)}
pinpaths=[
"numerical/execution.json","numerical/fixtures.log","numerical/native_build.log","compiler_helper_recovery.json",
"numerical_continuation/execution.json","numerical_continuation/pilot/result.json","numerical_continuation/full/result.json",
"review_floor_code/result.json","execute_floor.py","execute_floor_continuation.py","build_floor_native.py"]
result={
"task_id":"review_floor_results","attempt_id":"71f80598-5f91-402e-b5f4-70479f391f16",
"status":"completed","verdict":"PASS_SAVED_OUTPUT_AUDIT",
"audit_source_sha256":sha(Path(__file__)),"report_sha256":sha(OUT/"report.md"),
"reviewer":"native Codex subagent handoff_scientific_scope; computational output audit, not human peer review",
"reviewed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
"evidence_sha256":{p:sha(RUN/p) for p in pinpaths},
"reviewed_case_sha256":{r["file"]:r["sha256"] for r in full["reports"]},
"source_identity":full["identity"],
"counts":{"unique_cases":80,"pilot_reused":4,"new_full_scalar_fits":76,"historical_floor_checks":480,"phase_reports":160,"procedure_contrasts":400,"aggregate_rows":20,"hashed_original_inputs":560,"passed_fixtures":19},
"maxima":maxima,
"solver":{"selection_counts":dict(choices),"max_recorded_relative_derivative":max(residuals),"max_root_iterations":max(iterations),"minimum_training_joint_gain":min(gains),"maximum_training_joint_gain":max(gains),"fitted_a_min":min(parameters),"fitted_a_max":max(parameters)},
"floor_test_delta_distributions":floor_distributions,
"independently_reaggregated_summary":[summary[k] for k in sorted(summary)],
"resource":{"pilot_outer_wall_seconds":execution["phases"][0]["wall_seconds"],"full_outer_wall_seconds":execution["phases"][1]["wall_seconds"],"max_sampled_numerical_tree_rss":max(p["sampled_peak_tree_rss"] for p in execution["phases"]),"max_sampled_all_phases_tree_rss":max(p["sampled_peak_tree_rss"] for rec in (prior,execution) for p in rec["phases"]),"total_elapsed_including_initial_attempt_and_cleanup_seconds":elapsed,"same_owned_processes_live_at_review":live,"sampling_scope":"Recorded process-tree RSS every 0.1s; not an instantaneous OS memory proof."},
"recovery":"First attempt passed nineteen fixtures and compile, then refused history execution because the identified compiler helper remained. Recovery pins the matching PID/create time and absence of remaining owned processes. Continuation reused exact reviewed code/build/controls; all original and continuation logs match their hashes.",
"audit_limits":["No fitting, native loading, new eventwise score evaluation or simulation performed.","Reported root residuals and archived-formula crosscheck residuals were audited against declared bounds; eventwise derivatives were not independently recomputed.","Saved components, input identities, all original selected scores/gates and all aggregation arithmetic were independently checked.","No statistical significance, parameter recovery, causal attribution or external peer review follows from this audit."]
}
(OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"verdict":result["verdict"],"result_sha256":sha(OUT/"result.json"),"counts":result["counts"],"maxima":maxima,"solver":result["solver"],"resource":result["resource"],"matched_broad":[summary[5,"LIplus_immigrant","raw"],summary[7,"LIplus_inclusive","raw"]]},indent=2))

