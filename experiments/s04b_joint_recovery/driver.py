"""Finite one-case operational recovery; frozen scientific functions are delegates."""
from __future__ import annotations
import time
PROCESS_STARTED = time.monotonic()
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from experiments.s04b_joint_budgeted import driver as old
from experiments.s04b_joint_recovery.adapter import RecoveryAdapter, CountedPhase, same, SUPPORT_EQUIVALENCE_POLICY
legacy, frozen, model = old.legacy, old.frozen, old.model
read, sha, write, require = old.read, old.sha, old.write, old.require
SCHEMA = 'joint_recovery_case_index_v2'
STARTUP_FILES = {'archive':'startup_failure.zip','review':'startup_failure_review.json',
    'resource_review':'startup_failure_resource.json','workflow_log':'startup_failure_workflow.log'}
SUPPORT_FILES = {'archive':'pilot02_support_failure.zip','review':'pilot02_support_failure_review.json',
    'resource_review':'pilot02_support_failure_resource.json','workflow_log':'pilot02_support_failure_workflow.log'}
DIAGNOSTIC_FILES = {'archive':'support_diagnostic01.zip','review':'support_diagnostic01_review.json',
    'resource_review':'support_diagnostic01_resource.json','workflow_log':'support_diagnostic01_workflow.log'}


def operational_failures(policy):
    """The historical singleton is an alias, never an additional charged row."""
    rows=policy.get('operational_failures',[policy['pre_execution_failure']])
    count=2 if 'operational_failures' in policy else 1
    require(isinstance(rows,list) and len(rows)==count and rows[0]==policy['pre_execution_failure'],
        'Ordered operational failures must preserve the historical alias')
    require([r['charge_seconds'] for r in rows]==[90,120][:count], 'Reviewed operational charges changed')
    require(len({r['archive_sha256'] for r in rows})==count, 'Duplicate operational failure archive')
    for i,row in enumerate(rows):
        require(row['scientific_predecessor_unchanged'] is True and row['status']==
            ('failed_before_scientific_evaluation' if i==0 else 'failed_during_training_support'), 'Operational failure scope changed')
        require(0<=row['nested_scientific_seconds']<=row['nested_supervised_seconds']<=row['charge_seconds'],
            'Nested operational time exceeds its whole-launch charge')
        if i==1:require(row['support_evaluation_count']==5 and row['optimizer_call_count']==0,
            'Second failure support/optimizer census changed')
    return rows


def operational_failure_files(policy):
    files={}
    for row,names in zip(operational_failures(policy),(STARTUP_FILES,SUPPORT_FILES)):
        files.update({name:(row[key],row[key+'_sha256']) for key,name in names.items()})
    return files


def operational_diagnostics(policy):
    rows=policy.get('operational_diagnostics',[])
    require(isinstance(rows,list) and len(rows)==(1 if 'operational_diagnostics' in policy else 0), 'Diagnostic accounting roster changed')
    if rows:
        row=rows[0]
        require(row['status']=='diagnostic_complete' and row['passed'] is True and row['equality_passed'] is False
            and row['scientific_completion'] is False and row['scientific_predecessor_unchanged'] is True
            and row['charge_seconds']==80 and row['support_evaluation_count']==5
            and row['optimizer_call_count']==0 and row['held_out_call_count']==0, 'Diagnostic scope or charge changed')
        require(0<=row['nested_scientific_seconds']<=row['nested_supervised_seconds']<=80,'Nested diagnostic time exceeds whole-launch charge')
        require(row['archive_sha256'] not in {v['archive_sha256'] for v in operational_failures(policy)}, 'Duplicated diagnostic/failure charge')
    return rows


def operational_evidence_files(policy):
    files=operational_failure_files(policy)
    for row in operational_diagnostics(policy):
        files.update({name:(row[key],row[key+'_sha256']) for key,name in DIAGNOSTIC_FILES.items()})
    return files


def source_identity():
    current = old.source_identity()
    current.update({p.relative_to(REPO).as_posix():sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.suffix in ('.py', '.json')})
    return current


def verify_protocol():
    policy = read(HERE/'recovery_protocol.json')
    previous = old.verify_protocol()
    require(policy['schema'] == 'joint_partial_optimizer_recovery_protocol_v1', 'Wrong recovery protocol')
    require(same(policy['recovery'].get('support_equivalence'),SUPPORT_EQUIVALENCE_POLICY), 'Unreviewed operational gradient policy')
    require(old.source_identity() == policy['predecessor_source_sha256'], 'Frozen predecessor source changed')
    require(policy['scientific_protocol_sha256'] == previous['scientific_protocol_sha256'], 'Scientific protocol changed')
    require(policy['sequence'] == previous['sequence'], 'Scientific roster/order changed')
    slots = policy['fixed_slots']
    require([v['case_id'] for v in slots] == previous['sequence'][40:] and len(slots) == 40, 'Wrong remaining fixed roster')
    for entry in slots:
        cap = 2520 if entry['regime'] in (4, 6) else 1200
        require(entry['wall_seconds'] == cap and entry['scientific_reservation_seconds'] == cap-30, 'Recovery slot changed')
    require(sum(v['wall_seconds'] for v in slots) == 71760, 'Recovery total allocation changed')
    hosts = policy['actual_hosts']
    require([v['case_id'] for v in slots] == [c for h in hosts for c in h['case_ids']], 'Host partition reorders cases')
    require([len(h['case_ids']) for h in hosts] == [1,5,5,5,5,8,8,3], 'Eight fixed hosts required')
    require(all(h['outer_maximum_seconds'] <= 14400 and h['host_overhead_reserve_seconds'] == 1800 for h in hosts), 'Host resource envelope changed')
    r = policy['resources']
    require(r == dict(campaign_aggregate_seconds=115200,batch_wall_seconds=14400,threads=2,workers=1,
        sampled_process_tree_rss_cap_bytes=6442450944,minimum_host_free_bytes=2147483648,
        startup_finalization_allowance_seconds=30,host_overhead_reserve_seconds=1800,
        global_finalization_reserve_seconds=1800,maximum_cases_per_host=8), 'Recovery resources changed')
    for name, pin in policy['evidence_sha256'].items():
        require(sha(frozen.safe(HERE, name)) == pin, 'Changed recovery design evidence')
    p = policy['predecessor']
    for name in ('archive', 'review'):
        require(sha(frozen.safe(REPO, p[name])) == p[name+'_sha256'], 'Changed original failed artifact/review')
    require(policy['shared_run'] == previous['shared_run'], 'Shared run or expiry changed')
    require(same(p['known_outer_overhead_seconds'], p['known_outer_charged_seconds']-p['original_index_charged_seconds']), 'Outer charge arithmetic changed')
    failures=operational_failures(policy);failure_charge=sum(row['charge_seconds'] for row in failures)
    diagnostic_charge=sum(row['charge_seconds'] for row in operational_diagnostics(policy))
    for name,(path,pin) in operational_evidence_files(policy).items():
        require(sha(frozen.safe(REPO,path)) == pin, 'Changed retained operational failure '+name)
    require(p['known_outer_charged_seconds']+failure_charge+diagnostic_charge+71760+8*1800+1800 <= 115200, 'Fixed recovery allocation exceeds aggregate')
    return policy


def check_admission(args, policy, current):
    a = read(args.admission)
    p, r = policy['predecessor'], policy['resources']
    require(a['mode'] == 'recovery_campaign', 'Explicit recovery mode required')
    require(a['independent_review_passed'] is True and a['scheduler_review_passed'] is True and a['external_supervision'] is True, 'Recovery source/scheduler/supervision required')
    require(a['source_sha256'] == current['source_sha256'] and a['recovery_protocol_sha256'] == current['recovery_protocol_sha256'], 'Recovery source/protocol admission differs')
    require(a['operational_run_id'] == policy['shared_run']['run_id'] and a['operational_run_config_sha256'] == policy['shared_run']['config_sha256'], 'Shared-run attestation differs')
    expiry = datetime.datetime.fromisoformat(a['expires_utc'])
    require(datetime.datetime.now(datetime.timezone.utc) < expiry <= datetime.datetime.fromisoformat(policy['shared_run']['expires_utc']), 'Expired recovery admission')
    token = os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN', '')
    require(token and hashlib.sha256(token.encode()).hexdigest() == a['lease_token_sha256'], 'Lease attestation differs')
    require(a['threads'] == 2 and a['workers'] == 1 and a['sampled_process_tree_rss_cap_bytes'] == r['sampled_process_tree_rss_cap_bytes'] and a['minimum_host_free_bytes'] == r['minimum_host_free_bytes'], 'Resource admission differs')
    require(a['case_ids'] == [a['case_id']], 'One fixed case required')
    require(current['runtime']['essential'] == p['runtime_essential'], 'Original runtime required')
    require(a['library_sha256'] == current['library_sha256'] == p['library_sha256'] and a['build_receipt_sha256'] == current['build_receipt_sha256'] == p['build_receipt_sha256'], 'Original native/build bytes required')
    build = read(args.build_receipt)
    require(build['passed'] is True and build['source_sha256'] == sha(legacy.SCIENCE/'attenuation.cpp') and build['library_sha256'] == current['library_sha256'], 'Native build provenance differs')
    attempt = a['numerical_attempt_id']
    require(isinstance(attempt,str) and attempt and all(c.isalnum() or c=='-' for c in attempt), 'Invalid attempt ID')
    return a


def copy_index_payload(index, root, out, cases, previous):
    lookup = {c['case_id']:c for c in cases}
    for entry in index['cases']:
        report = read(frozen.safe(root,entry['file']))
        legacy.verify_case(report,entry,lookup[entry['case_id']])
        require(report['attempts_sha256'] == entry['trace_sha256'], 'Prior trace pin differs')
        legacy.copy_bound(root,out,entry['file'],entry['sha256'])
        legacy.copy_bound(root,out,entry['trace'],entry['trace_sha256'])
    for entry in index['attempts']:
        receipt = read(frozen.safe(root,entry['file']))
        require(receipt['attempt_id'] == entry['attempt_id'] and receipt['phase'] == entry['phase'] and receipt['wall_seconds'] == entry['seconds'], 'Prior charged attempt changed')
        legacy.copy_bound(root,out,entry['file'],entry['sha256'])
    for entry in index['reviews']:
        legacy.copy_bound(root,out,entry['file'],entry['sha256'])
    for relative,pin in index['transition']['files'].items():
        legacy.copy_bound(root,out,relative,pin)
    old.copy_resume(root,out,index,previous)


def validate_recovery_transition(index, policy, root):
    t, p = index['recovery_transition'], policy['predecessor']
    require(t['schema'] == 'joint_interrupted_optimizer_transition_v1' and t['original_status'] == 'failed', 'Recovery must retain failed status')
    require(t['original_index_sha256'] == p['index_sha256'] and t['protocol_sha256'] == sha(HERE/'recovery_protocol.json'), 'Recovery lineage identity differs')
    for name,pin in t['files'].items():
        require(sha(frozen.safe(root,name)) == pin, 'Recovery lineage artifact changed: '+name)
    original = read(root/'recovery_lineage/failed_index.json')
    require(sha(root/'recovery_lineage/failed_index.json') == p['index_sha256'], 'Original failed index changed')
    require(index['cases'][:40] == original['cases'] and index['attempts'][:len(original['attempts'])] == original['attempts'] and index['reviews'][:len(original['reviews'])] == original['reviews'], 'Original case/attempt/review prefix changed')
    require(t['known_outer_overhead_seconds'] == p['known_outer_overhead_seconds'], 'Historical overhead changed')
    require(t['pre_execution_failure'] == index['pre_execution_failure'] == policy['pre_execution_failure'], 'Startup failure accounting changed')
    require(t['operational_failures'] == index['operational_failures'] == operational_failures(policy), 'Ordered operational failure accounting changed')
    require(t['operational_diagnostics'] == index['operational_diagnostics'] == operational_diagnostics(policy), 'Diagnostic accounting changed')
    expected = {'recovery_lineage/failed_index.json':p['index_sha256'], 'recovery_lineage/failed_case.json':p['case_sha256'],
        'recovery_lineage/failed_trace.jsonl':p['trace_sha256'], 'recovery_lineage/failed_review.json':p['review_sha256'],
        'recovery_lineage/failed_result.json':p['result_sha256'], 'recovery_lineage/failed_supervision.json':p['supervision_sha256'],
        'recovery_lineage/failed_admission.json':p['admission_sha256'], 'recovery_lineage/failed_host.zip':p['archive_sha256']}
    expected.update({'recovery_lineage/'+filename:pin for filename,(_,pin) in operational_evidence_files(policy).items()})
    require(t['files'] == expected, 'Recovery lineage roster changed')


def accepted_index(args, admission, policy, current, cases, out):
    path, review_path = Path(args.prior_index).resolve(), Path(args.prior_review).resolve()
    root = path.parent
    index, review = read(path), read(review_path)
    p = policy['predecessor']
    require(sha(path) == admission['prior_index_sha256'] and sha(review_path) == admission['prior_review_sha256'], 'Prior admission pin differs')
    previous = old.verify_protocol()
    old.validate_transition(index,previous,root)
    legacy.charged(index,read(legacy.HERE/'operational_protocol.json'))
    count = len(index['cases'])
    require([c['case_id'] for c in index['cases']] == policy['sequence'][:count], 'Prior cases are not exact prefix')
    require(index['runtime']['essential'] == current['runtime']['essential'] and index['library_sha256'] == current['library_sha256'] and index['build_receipt_sha256'] == current['build_receipt_sha256'], 'Prior native/runtime differs')
    first = index['schema'] != SCHEMA
    if first:
        require(index['schema'] == old.SCHEMA and sha(path) == p['index_sha256'] and sha(review_path) == p['review_sha256'], 'Only exact frozen failed predecessor may transition')
        require(review['audit_passed'] is True and review['passed'] is False and review['live_agent_review'] is True and review['failed_index']['sha256'] == sha(path), 'Missing genuine failed-output audit')
        require(index['source_sha256'] == policy['predecessor_source_sha256'] and count == 40 and index['last_attempt_passed'] is False and index['partial_case']['sha256'] == p['case_sha256'] and index['partial_case']['trace_sha256'] == p['trace_sha256'], 'Wrong partial predecessor')
        require(index['budget']['total_seconds'] == p['original_index_charged_seconds'], 'Failed charge changed')
    else:
        require(review['passed'] is True and review['index_sha256'] == sha(path), 'New predecessor lacks accepted review')
        require(index['source_sha256'] == current['source_sha256'] and index['recovery_protocol_sha256'] == current['recovery_protocol_sha256'], 'New predecessor source differs')
        require(index['partial_case'] is None and index['last_attempt_passed'] is True, 'New failure/partial blocks automatic continuation')
        require(41 <= count < 80 and len(index['attempts']) == 41+count-40, 'Recovery attempts/cases differ')
        if count == 41:
            require(review.get('live_agent_review') is True and review.get('review_kind') == 'live_agent_saved_output_review' and not review.get('final_batch_agent_review_required',False), 'Recovery pilot requires independent live output review')
        validate_recovery_transition(index,policy,root)
        for entry in index['attempts'][41:]:
            receipt = read(root/entry['file'])
            require(receipt['passed'] is True and receipt['source_sha256'] == current['source_sha256'] and receipt['recovery_protocol_sha256'] == current['recovery_protocol_sha256'], 'Unaccepted recovery attempt')
        for name,pin in index['recovery_transition']['files'].items():
            legacy.copy_bound(root,out,name,pin)
        # The first case's physical-versus-logical execution evidence is retained
        # alongside the immutable predecessor, not regenerated by later cases.
        for relative,pin in index.get('recovery_execution_files',{}).items():
            legacy.copy_bound(root,out,relative,pin)
    copy_index_payload(index,root,out,cases,previous)
    shutil.copy2(path,out/'parent_index.json')
    if first:
        lineage = out/'recovery_lineage';lineage.mkdir()
        sources = {'failed_index.json':path,'failed_case.json':root/index['partial_case']['file'],
            'failed_trace.jsonl':root/index['partial_case']['trace'],'failed_result.json':root/'result.json',
            'failed_supervision.json':root.parent/'supervision/result.json','failed_admission.json':root.parent/'admission.json',
            'failed_review.json':review_path,'failed_host.zip':REPO/p['archive']}
        sources.update({filename:frozen.safe(REPO,path) for filename,(path,_) in operational_evidence_files(policy).items()})
        for name,source in sources.items():shutil.copy2(source,lineage/name)
        index['recovery_transition'] = dict(schema='joint_interrupted_optimizer_transition_v1',original_status='failed',
            original_index_sha256=p['index_sha256'],protocol_sha256=current['recovery_protocol_sha256'],
            known_outer_overhead_seconds=p['known_outer_overhead_seconds'],pre_execution_failure=copy.deepcopy(policy['pre_execution_failure']),
            operational_failures=copy.deepcopy(operational_failures(policy)),
            operational_diagnostics=copy.deepcopy(operational_diagnostics(policy)),
            files={'recovery_lineage/'+name:sha(lineage/name) for name in sources})
        index.update(schema=SCHEMA,source_sha256=current['source_sha256'],recovery_protocol_sha256=current['recovery_protocol_sha256'],
            pre_execution_failure=copy.deepcopy(policy['pre_execution_failure']),
            operational_failures=copy.deepcopy(operational_failures(policy)),operational_diagnostics=copy.deepcopy(operational_diagnostics(policy)),
            partial_case=None,last_attempt_passed=None)
        validate_recovery_transition(index,policy,out)
    target='reviews/'+sha(review_path)+'.json'
    require(not(out/target).exists(), 'Repeated prior review')
    (out/'reviews').mkdir(exist_ok=True);shutil.copy2(review_path,out/target)
    index['reviews'].append(dict(file=target,sha256=sha(review_path),accepted_index_sha256=sha(path),review_scope='failed predecessor disposition' if first else 'accepted recovery predecessor'))
    return index,first


def allocation(index, policy, admission, first):
    count=len(index['cases'])
    require(40 <= count < 80 and [v['case_id'] for v in index['cases']] == policy['sequence'][:count], 'Recovery prefix differs')
    slot=policy['fixed_slots'][count-40]
    require(admission['case_id'] == slot['case_id'] and admission['wall_seconds'] == slot['wall_seconds'], 'Wrong next case or slot')
    require(index['partial_case'] is None and (first or index['last_attempt_passed'] is True), 'Partial/failed predecessor unresolved')
    require(first == (count == 40), 'Partial-recovery pilot cannot repeat')
    require(admission['numerical_attempt_id'] not in {v['attempt_id'] for v in index['attempts']}, 'Duplicate charged attempt')
    total,_=legacy.charged(index,read(legacy.HERE/'operational_protocol.json'))
    # Reserve all eight host allowances conservatively throughout. These do not
    # masquerade as measured elapsed seconds; actual scientific time remains exact.
    failure_charge=sum(row['charge_seconds'] for row in operational_failures(policy))
    diagnostic_charge=sum(row['charge_seconds'] for row in operational_diagnostics(policy))
    bound=total+policy['predecessor']['known_outer_overhead_seconds']+failure_charge+diagnostic_charge+sum(s['wall_seconds'] for s in policy['fixed_slots'][count-40:])+8*1800+1800
    require(bound <= policy['resources']['campaign_aggregate_seconds'], 'Remaining fixed envelope exceeds aggregate')
    return slot,dict(scientific_charge_seconds=total,known_prior_outer_overhead_seconds=policy['predecessor']['known_outer_overhead_seconds'],
        operational_failure_charge_seconds=failure_charge,operational_diagnostic_charge_seconds=diagnostic_charge,
        all_host_reserve_seconds=8*1800,global_finalization_reserve_seconds=1800,
        maximum_with_unspent_slots_seconds=bound,completion_guaranteed=False)


def recovery_delegate(scheduler, partial, trace, science, policy, out):
    delegate=legacy.runner_with_scheduler(scheduler)
    adapter=RecoveryAdapter(partial,trace,science,policy['recovery'],out/'recovery_calls.jsonl')
    original_factory=delegate.model.phase_from_rows
    def factory(*args,**kwargs):
        phase=original_factory(*args,**kwargs)
        return CountedPhase(phase,adapter,'train' if args[2:4] == (30,395) else 'test')
    delegate.model.phase_from_rows=factory
    delegate.fit_arm=adapter.fit_arm
    original_fine=delegate.fine_check
    def checked_fine(phase, name, fitted, protocol):
        checked=original_fine(phase,name,fitted,protocol)
        if name in ('null','LI'):
            comparison=adapter.record_training_check(name,checked,partial['training_checks'][name])
            require(comparison['operational_equivalence']['passed'], 'Repeated completed-arm training check differs')
            return copy.deepcopy(partial['training_checks'][name])
        return checked
    delegate.fine_check=checked_fine
    return delegate,adapter


def validate_recovered_report(report, partial):
    """Fresh support checks must agree exactly with saved completed-arm checks."""
    require(report['input_sha256'] == partial['input_sha256'], 'Recovery input hashes changed')
    require(same(report['historical_comparisons'], partial['historical_comparisons']), 'Historical comparison custody changed')
    require(same([v for v in report['floor_checks'] if v['phase']=='train'], partial['floor_checks']), 'Repeated training-floor checks differ')
    for name in ('null','LI'):
        require(same(report['fits'][name], partial['fits'][name]), 'Complete reused fit changed')
        require(same(report['training_checks'][name], partial['training_checks'][name]), 'Repeated completed-arm training check differs')


def persist(out,index,result,admission,current,started,deadline,active):
    if active and index['partial_case'] is None:
        path=out/'cases'/(active+'.json');trace=out/'cases'/(active+'.attempts.jsonl')
        index['partial_case']=dict(case_id=active,file='cases/'+active+'.json',sha256=sha(path) if path.exists() else None,
            trace='cases/'+active+'.attempts.jsonl',trace_sha256=sha(trace) if trace.exists() else None,status='interrupted_or_persistence_failure')
    if index['partial_case'] is not None:result.update(passed=False,status='failed_requires_review',scientific_completion=False)
    relative='attempts/'+admission['numerical_attempt_id']+'.json'
    entry=dict(attempt_id=admission['numerical_attempt_id'],phase='campaign',file=relative);index['attempts'].append(entry)
    def save():
        elapsed=time.monotonic()-started
        result['wall_seconds']=elapsed;index['last_attempt_passed']=result['passed']
        receipt=dict(attempt_id=entry['attempt_id'],phase='campaign',wall_seconds=elapsed,passed=result['passed'],status=result['status'],
            case_ids=[v['case_id'] for v in result['cases']],partial_case=index['partial_case'],source_sha256=current['source_sha256'],
            recovery_protocol_sha256=current['recovery_protocol_sha256'],admission_sha256=result['admission_sha256'],parent_index_sha256=admission['prior_index_sha256'])
        write(out/relative,receipt);entry.update(seconds=elapsed,sha256=sha(out/relative))
        original=index['original_failure']['prior_scientific_seconds']
        index['budget']=dict(total_seconds=math.fsum([original,*[v['seconds'] for v in index['attempts']]]),
            pilot_seconds=math.fsum([original,*[v['seconds'] for v in index['attempts'] if v['phase']=='pilot']]))
        scientific=index['budget']['total_seconds'];overhead=index['recovery_transition']['known_outer_overhead_seconds']
        failures=index.get('operational_failures',[index['pre_execution_failure']])
        failure_charge=math.fsum(row['charge_seconds'] for row in failures)
        diagnostics=index.get('operational_diagnostics',[]);diagnostic_charge=math.fsum(row['charge_seconds'] for row in diagnostics)
        index['operational_accounting']=dict(scientific_indexed_seconds=scientific,known_prior_outer_overhead_seconds=overhead,
            operational_failure_charge_seconds=failure_charge,operational_diagnostic_charge_seconds=diagnostic_charge,
            accounted_seconds=math.fsum([scientific,overhead,failure_charge,diagnostic_charge]))
        write(out/'index.json',index)
        result.update(index_sha256=sha(out/'index.json'),complete_cases=len(index['cases']),budget=index['budget'],
            pre_execution_failure=index['pre_execution_failure'],operational_accounting=index['operational_accounting'],
            operational_failures=failures,
            operational_diagnostics=diagnostics,
            independent_index_review_required=True,**legacy.fit_census(index,out))
        write(out/'result.json',result)
    save()
    if time.monotonic() >= deadline or index['operational_accounting']['accounted_seconds'] > 115200:
        result.update(passed=False,status='failed_requires_review',scientific_completion=False,error_type='FinalizationDeadline',error='Final serialization exceeded finite allowance')
        save()


def run(args,started=None):
    started=PROCESS_STARTED if started is None else started
    out=Path(args.output).resolve();require(not out.is_relative_to(REPO),'Fresh output must be outside checkout')
    out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir();(out/'attempts').mkdir()
    result=dict(schema='joint_recovery_batch_v1',passed=False,status='preflight',cases=[],scientific_completion=False,original_fixed_slot_status='failed')
    write(out/'result.json',result)
    index=admission=None;active=None;deadline=started;adapter=None
    try:
        policy=verify_protocol();science=read(legacy.SCIENCE/'protocol.json')
        current=dict(source_sha256=source_identity(),recovery_protocol_sha256=sha(HERE/'recovery_protocol.json'),runtime=frozen.runtime_identity(),library_sha256=sha(args.library),build_receipt_sha256=sha(args.build_receipt))
        result.update(current);admission=check_admission(args,policy,current);result['admission_sha256']=sha(args.admission)
        deadline=min(started+admission['wall_seconds'],time.monotonic()+(datetime.datetime.fromisoformat(admission['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        cases=frozen.verify_inputs(science);index,first=accepted_index(args,admission,policy,current,cases,out)
        slot,budget=allocation(index,policy,admission,first)
        result.update(allocation=budget,requested_case=slot['case_id'],prior_case_count=len(index['cases']))
        require(deadline-time.monotonic() >= slot['scientific_reservation_seconds'],'Startup consumed reserved scientific opportunity')
        modules=model.archived();native=model.Native(args.library)
        with legacy.OrderedChunkScheduler() as scheduler:
            if first:
                partial=read(out/'recovery_lineage/failed_case.json')
                trace=[json.loads(line) for line in (out/'recovery_lineage/failed_trace.jsonl').read_text().splitlines()]
                delegate,adapter=recovery_delegate(scheduler,partial,trace,science,policy,out)
            else:delegate=legacy.runner_with_scheduler(scheduler)
            active=slot['case_id'];result.update(status='running',active_case=active);write(out/'result.json',result)
            case=next(v for v in cases if v['case_id']==active)
            report=delegate.case_run(case,modules,native,science,out/'cases',min(deadline,time.monotonic()+slot['scientific_reservation_seconds']),None)
            if adapter is not None:
                write(out/'recovery_execution.json',adapter.receipt())
                index['recovery_execution_files']={name:sha(out/name) for name in ('recovery_calls.jsonl','recovery_execution.json')}
                report['recovery_provenance']=dict(schema='explicit_optimizer_return_replay_v1',original_partial_sha256=policy['predecessor']['case_sha256'],
                    original_trace_sha256=policy['predecessor']['trace_sha256'],execution_files=index['recovery_execution_files'],
                    no_completed_optimizer_trajectory_repeated=True,exact_internal_optimizer_resume=False,
                    support_recomputations='Recorded by phase/model/context/order in recovery_execution.json',original_interrupted_invocation_retained=True)
                report['prior_training_attempt_seconds']=partial['wall_seconds']
                report['wall_seconds']=report['current_attempt_wall_seconds']+partial['wall_seconds']
                write(out/'cases'/(active+'.json'),report)
            trace_path=out/'cases'/(active+'.attempts.jsonl')
            entry=dict(case_id=active,file='cases/'+active+'.json',sha256=sha(out/'cases'/(active+'.json')),
                trace='cases/'+active+'.attempts.jsonl',trace_sha256=sha(trace_path) if trace_path.exists() else None,
                reused_fit_arms=2 if first else 0,new_fit_arms=2 if first else 4)
            if not report['passed']:
                index['partial_case']=entry
                result.update(passed=False,status='failed_requires_review',scientific_completion=False,
                    error_type=report.get('error_type','CaseFailure'),
                    error=report.get('error','Failed recovery/partial retained; no automatic retry'),
                    failed_case_sha256=entry['sha256'])
                return 1
            require(trace_path.exists(),'Completed case lacks optimizer trace')
            if first:validate_recovered_report(report,partial)
            legacy.verify_case(report,entry,case);index['cases'].append(entry);result['cases'].append(entry)
            active=None;result.pop('active_case',None)
        require(time.monotonic()<deadline,'Completed after finite slot')
        if len(index['cases'])==80:
            result.update(summary_sha256=legacy.final_summary(index,science,out,deadline),scientific_completion=True)
        result.update(passed=True,status='batch_complete',new_fit_arms=2 if first else 4,reused_fit_arms=2 if first else 0,
            original_interrupted_optimizer_attempts=1,physical_attempt_census_scope='Original failed trace plus recovery call ledger, separate from logical fit-summary failure count')
    except BaseException as exc:
        result.update(passed=False,status='failed_requires_review',scientific_completion=False,error_type=type(exc).__name__,error=str(exc))
    finally:
        if adapter is not None:
            try:
                write(out/'recovery_execution.json',adapter.receipt())
                if index is not None:index['recovery_execution_files']={name:sha(out/name) for name in ('recovery_calls.jsonl','recovery_execution.json')}
            except BaseException as exc:
                result.update(passed=False,status='failed_requires_review',scientific_completion=False,
                    recovery_accounting_error_type=type(exc).__name__,recovery_accounting_error=str(exc))
        if index is not None and admission is not None and admission['numerical_attempt_id'] not in {v['attempt_id'] for v in index['attempts']}:
            persist(out,index,result,admission,current,started,deadline,active)
        else:
            result.update(wall_seconds=time.monotonic()-started,unindexed_attempt_requires_conductor_accounting=True);write(out/'result.json',result)
    return 0 if result['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('admission','library','build-receipt','prior-index','prior-review','output'):parser.add_argument('--'+name,required=True)
    raise SystemExit(run(parser.parse_args()))
