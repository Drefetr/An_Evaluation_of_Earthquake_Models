"""Compact source-reviewed amendment hosts; no automatic retry or old fits."""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import hashlib
import math
import os
from pathlib import Path
import shutil
import sys
import time
from . import case_driver as driver
REPO=driver.REPO;HERE=driver.HERE
read,sha,write,require,safe=driver.read,driver.sha,driver.write,driver.require,driver.safe


def source_identity():return driver.source_identity()


def verify_protocol():
    p=driver.verify_protocol();groups=p['resources']['future_hosts']
    require([g['host'] for g in groups]==list(range(1,9)) and [n for g in groups for n in g['case_ids']]==p['case_ids'],'Frozen eight-host roster differs')
    slots={r['case_id']:r for r in p['case_slots']}
    for g in groups:
        total=sum(slots[n]['wall_seconds'] for n in g['case_ids'])
        require(g['case_outer_seconds']==total and g['host_overhead_reserve_seconds']==1800
            and g['whole_host_upper_seconds']==total+1800,'Fixed host reservation differs')
    return p


def counts(records):
    complete=sum(r['disposition']=='complete' for r in records);unknown=sum(r['disposition']=='scientific_unknown' for r in records)
    require(complete+unknown==len(records),'Undisposed compact record')
    return dict(processed_histories=len(records),complete_histories=complete,unknown_histories=unknown,
                unattempted_histories=80-len(records),computed_outcomes=5*complete)


def budget(p,attempts):
    ids=[r['case_id'] for r in attempts];require(ids==p['case_ids'][:len(ids)] and len(set(ids))==len(ids),'Budget attempt roster differs')
    for r in attempts:
        slot=next(s for s in p['case_slots'] if s['case_id']==r['case_id'])
        require(math.isfinite(r['outer_seconds']) and 0<=r['outer_seconds']<=slot['wall_seconds']
            and math.isfinite(r['seconds']) and 0<=r['seconds']<=slot['scientific_seconds'],'Invalid measured child duration')
        if r['case_id']==p['partial_case_id']:
            require(float(p['resources']['partial_case_original_outer_seconds'])+r['outer_seconds']<=p['resources']['original_case_outer_cap_seconds']
                and float(p['resources']['partial_case_original_scientific_seconds'])+r['seconds']<=p['resources']['original_case_scientific_cap_seconds'],'Cumulative original partial-case cap exceeded')
    result=dict(base_accounted_seconds=float(p['resources']['accounted_seconds']),
                amended_scientific_seconds=math.fsum(r['seconds'] for r in attempts),
                amended_outer_seconds=math.fsum(r['outer_seconds'] for r in attempts),
                remaining_case_slots_seconds=sum(r['wall_seconds'] for r in p['case_slots'][len(ids):]),
                all_eight_host_overhead_reserved_seconds=float(p['resources']['future_host_overhead_seconds']),
                global_finalization_reserve_seconds=float(p['resources']['global_finalization_reserve_seconds']))
    result['accounted_seconds']=result['base_accounted_seconds']+result['amended_outer_seconds']
    result['upper_bound_seconds']=math.fsum(result[k] for k in ('accounted_seconds','remaining_case_slots_seconds','all_eight_host_overhead_reserved_seconds','global_finalization_reserve_seconds'))
    result['remaining_headroom_seconds']=115200-result['upper_bound_seconds']
    require(result['upper_bound_seconds']<=115200,'Global unchanged budget exceeded')
    return result


def next_cases(p,a,index,review):
    number=a['batch_id'];require(type(number) is int and 1<=number<=8,'Wrong host number')
    group=p['resources']['future_hosts'][number-1]
    require(a['case_ids']==group['case_ids'] and set(a['child_attempt_ids'])==set(group['case_ids'])
        and len(set(a['child_attempt_ids'].values()))==len(group['case_ids']),'Host case/attempt roster differs')
    preceding=sum(len(g['case_ids']) for g in p['resources']['future_hosts'][:number-1])
    require(len(index['records'])==44+preceding and [r['case_id'] for r in index['records']]==p['full_sequence'][:44+preceding], 'Wrong exact prefix')
    if number==1:
        require(a['prior_index_sha256']==p['base']['index_sha256'] and a['prior_review_sha256']==p['base']['review_sha256']
            and a['prior_archive_sha256']==p['base']['archive_sha256'],'Wrong partial predecessor')
        require(index['schema']=='joint_remaining_index_v1' and counts(index['records'])['complete_histories']==43
            and review['audit_passed'] is True and review['passed'] is False and review['accepted_completed_prefix'] is True,'Initial failed-host prefix not independently accepted')
    else:
        require(index['schema']=='joint_exposure_refinement_index_v1' and index['protocol_sha256']==a['protocol_sha256']
            and index['host_source_sha256']==a['source_sha256'] and index['scientific_source_sha256']==a['scientific_source_sha256'],'Amended predecessor source differs')
        require(review.get('passed') is True and review.get('audit_passed') is True and review.get('review_kind')=='live_agent_saved_output_review'
            and review.get('live_agent_review') is True and review.get('final_batch_agent_review_required') is False,'Live prior-host audit required before any new child')
        require(review['index_sha256']==a['prior_index_sha256'] and review['artifact_sha256']==a['prior_archive_sha256'],'Live prior archive/index identity differs')
        require(index['records'][44]['case_id']==p['partial_case_id'] and index['records'][44]['disposition']=='complete','Partial pilot must complete before future cases')
        require(index['budget']==budget(p,index['attempts']),'Prior budget differs')
    return group


def timing(p,g,a,next_slot,now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    start=dt.datetime.fromisoformat(a['host_started_utc']);expiry=dt.datetime.fromisoformat(a['expires_utc'])
    elapsed=(now-start).total_seconds();window=g['whole_host_upper_seconds']-600
    require(a['execution_window_seconds']==window and elapsed>=0,'Wrong host timing origin/window')
    require(elapsed+next_slot+(150 if next_slot else 0)<window,'Host preparation/scientific/checker reservation exhausted')
    require((expiry-now).total_seconds()>=next_slot+(150 if next_slot else 0),'Shared deadline reservation exhausted')


def check_source_reviews(a,p,source_path,checker_path):
    require(sha(source_path)==a['source_review_sha256'] and sha(checker_path)==a['checker_source_review_sha256'],'Source review bytes differ')
    source,checker=read(source_path),read(checker_path)
    require(source['passed'] is True and checker['passed'] is True and source['live_agent_review'] is True and checker['live_agent_review'] is True,'Independent source audit required')
    checker_paths=p['checker']['sources'];require(checker_paths and checker_paths[0]=='experiments/s04b_exposure_refinement_audit/check.py','Checker graph not frozen')
    cp={name:sha(safe(REPO,name)) for name in checker_paths}
    for name,pin in source_identity().items():require(source['reviewed_files_sha256'].get(name)==pin,'Unreviewed source: '+name)
    for name,pin in cp.items():require(checker['reviewed_files_sha256'].get(name)==pin,'Unreviewed checker: '+name)
    for name,pin in {**source_identity(),**cp}.items():require(a['reviewed_files_sha256'].get(name)==pin,'Conductor omitted source')
    for name,pin in a['reviewed_files_sha256'].items():require(sha(safe(REPO,name))==pin,'Changed admitted source')
    return cp


def child_admission(a,p,name,slot):
    return dict(mode='exposure_refinement_case',case_id=name,case_ids=[name],source_sha256=a['scientific_source_sha256'],
        protocol_sha256=a['protocol_sha256'],amendment_protocol_sha256=a['protocol_sha256'],
        independent_review_passed=True,external_supervision=True,operational_run_id=p['shared_run']['run_id'],
        operational_run_config_sha256=p['shared_run']['config_sha256'],expires_utc=a['expires_utc'],
        wall_seconds=slot['wall_seconds'],scientific_seconds=slot['scientific_seconds'],threads=2,workers=1,
        sampled_process_tree_rss_cap_bytes=a['rss_cap_bytes'],minimum_host_free_bytes=a['host_headroom_bytes'],
        lease_token_sha256=a['lease_token_sha256'],library_sha256=a['library_sha256'],build_receipt_sha256=a['build_receipt_sha256'],
        numerical_attempt_id=a['child_attempt_ids'][name])


def append_candidate(p,a,previous,current,out,prior_index,prior_review,projection):
    actual=read(current/'science/result.json');name=actual['case_id']
    require(actual['schema']=='joint_exposure_refinement_case_v1' and actual.get('handled') is True
        and actual.get('disposition_valid') is True and actual['status']=='terminal_disposition','Missing valid case disposition')
    require(actual['passed'] is actual['scientific_passed'] and actual['passed'] is (actual['disposition']=='complete'),'Unknown relabeled passed')
    require(name==p['full_sequence'][len(previous['records'])] and actual['source_sha256']==a['scientific_source_sha256']
        and actual['protocol_sha256']==a['protocol_sha256'] and actual['numerical_attempt_id']==a['child_attempt_ids'][name],'Child identity differs')
    if name==p['partial_case_id']:require(actual['scientific_passed'] is True,'Mandatory partial pilot did not complete')
    case_path=safe(current/'science',actual['report_file']);trace_path=safe(current/'science',actual['trace_file'])
    require(sha(case_path)==actual['report_sha256'] and sha(trace_path)==actual['trace_sha256'],'Case/trace changed')
    report=read(case_path);require(report['case_id']==name,'Child case report identity differs');require(report['numerical_amendment']==actual['numerical_amendment'],'Amendment identity differs')
    for filename,key in [('reuse_map.json','reuse_map_sha256'),('refinement_events.jsonl','refinement_event_log_sha256'),('execution_calls.jsonl','execution_calls_sha256')]:
        require(sha(current/'science'/filename)==actual['numerical_amendment'][key],'Amendment evidence changed')
    source=dict(kind='host_execution',execution_id=a['numerical_attempt_id'],
        case_path=case_path.relative_to(out).as_posix(),case_sha256=sha(case_path),trace_path=trace_path.relative_to(out).as_posix(),trace_sha256=sha(trace_path),
        result_path=(current/'science/result.json').relative_to(out).as_posix(),result_sha256=sha(current/'science/result.json'),
        supervision_path=(current/'supervision/result.json').relative_to(out).as_posix(),supervision_sha256=sha(current/'supervision/result.json'))
    row=projection(report,actual['disposition'],source);row['numerical_amendment']=actual['numerical_amendment']
    row['refinement_census']=actual['refinement_census']
    if not actual['scientific_passed']:
        row.update(unknown_origin='new_frozen_solver_cap',unknown_reason=actual['unknown_reason'],model_census=actual['model_census'],terminal_solver_return=actual['terminal_solver_return'])
    supervisor=read(current/'supervision/result.json');outer=supervisor['wall_seconds_including_cleanup']
    attempt=dict(case_id=name,numerical_attempt_id=actual['numerical_attempt_id'],host_execution_id=a['numerical_attempt_id'],seconds=actual['wall_seconds'],outer_seconds=outer,
        result_sha256=source['result_sha256'],supervision_sha256=source['supervision_sha256'],actual_optimizer_attempts=actual['actual_optimizer_attempts'],reused_optimizer_attempts=actual['reused_optimizer_attempts'])
    rows=previous['records']+[row];attempts=previous['attempts']+[attempt]
    local=Path(prior_index).resolve().is_relative_to(out.resolve())
    return dict(schema='joint_exposure_refinement_index_v1',protocol_sha256=a['protocol_sha256'],numerical_amendment_version=p['version'],
        original_scientific_protocol_sha256=p['original_scientific_protocol_sha256'],host_source_sha256=a['source_sha256'],scientific_source_sha256=a['scientific_source_sha256'],
        original_native=p['original_native'],immutable_failure_reference=p['permanent_unknown'],original_exposure_failure_reference=p['failed_case'],compatible_saved_prefix=p['base'],
        records=rows,attempts=attempts,predecessor=dict(index_sha256=sha(prior_index),review_sha256=sha(prior_review),archive_sha256=None if local else a['prior_archive_sha256']),
        budget=budget(p,attempts),counts=counts(rows),passed=False,scientific_completion=False)


def check_receipt(path,index,pins,review_pin):
    r=read(path)
    require(r.get('passed') is True and r.get('audit_passed') is True and r.get('disposition_valid') is True and r.get('index_sha256')==sha(index)
        and r.get('live_agent_review') is False and r.get('live_agent_review_performed') is False
        and r.get('scientific_completion') is False and r.get('final_batch_agent_review_required') is True,'Independent automated check did not accept exact case/index')
    require(r['checker_sources_sha256']==pins and r['checker_source_review_sha256']==review_pin,'Checker source identity differs')


def run(args):
    out=Path(args.output).resolve();require(not out.exists() and not out.is_relative_to(REPO),'Fresh external host output required')
    out.mkdir(parents=True);current=None;child_seconds=0.
    result=dict(schema='joint_exposure_refinement_host_v1',passed=False,host_execution_passed=False,status='preflight',children=[],scientific_completion=False,live_agent_review=False,final_batch_agent_review_required=True)
    write(out/'result.json',result)
    try:
        p=verify_protocol();a=read(args.admission);scientific=driver.source_identity()
        require(a['mode']=='exposure_refinement_host_batch' and a['source_sha256']==source_identity() and a['scientific_source_sha256']==scientific
            and a['protocol_sha256']==sha(HERE/'protocol.json')==a['amendment_protocol_sha256'],'Host source identity differs')
        require(a['host_batch_source_review_passed'] is True and a['checker_source_review_passed'] is True,'Source admission missing')
        require(a['shared_run']==p['shared_run'] and sha(args.config)==p['shared_run']['config_sha256'] and a['expires_utc']==p['shared_run']['expires_utc'],'Shared allocation changed')
        require(a['rss_cap_bytes']==6442450944 and a['host_headroom_bytes']==2147483648,'Resource bounds differ')
        token=os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','');require(token and hashlib.sha256(token.encode()).hexdigest()==a['lease_token_sha256'],'Numerical lease differs')
        for key,path in [('library_sha256',args.library),('build_receipt_sha256',args.build_receipt)]:require(sha(path)==a[key]==p['original_native'][key],'Original native differs')
        checker_pins=check_source_reviews(a,p,args.source_review,args.checker_review)
        # Only generic pinned utilities are reused; no frozen module globals mutate.
        from experiments.s04b_joint_remaining.host import supervised,projection
        pi,pr=Path(args.prior_index),Path(args.prior_review)
        require(sha(pi)==a['prior_index_sha256'] and sha(pr)==a['prior_review_sha256'],'Prior bytes differ')
        previous=read(pi);g=next_cases(p,a,previous,read(pr))
        if a['batch_id']==1:
            require(args.failed_prior is not None,'Partial pilot requires exact extracted failed artifact')
            previous=dict(records=copy.deepcopy(previous['records']),attempts=[])
        else:require(args.failed_prior is None,'Later host cannot consume partial archive')
        environment={k:'2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
        environment.update(PYTHONDONTWRITEBYTECODE='1',JOINT_NUMERICAL_LEASE_TOKEN=token,NUMERICAL_LEASE_TOKEN=token)
        result.update(status='running',batch_id=a['batch_id'],requested_cases=g['case_ids'],source_sha256=source_identity(),admission_sha256=sha(args.admission),protocol_sha256=a['protocol_sha256'])
        slots={r['case_id']:r for r in p['case_slots']}
        for number,name in enumerate(g['case_ids'],1):
            slot=slots[name];timing(p,g,a,slot['wall_seconds'])
            current=out/'children'/('%02d_%s'%(number,name));current.mkdir(parents=True)
            result['active_child']=current.relative_to(out).as_posix();write(out/'result.json',result)
            grant=child_admission(a,p,name,slot);write(current/'admission.json',grant)
            write(current/'conductor_review.json',dict(a['conductor_review'],stage='joint-exposure-refinement-case',case_id=name,case_ids=[name],numerical_attempt_id=grant['numerical_attempt_id'],wall_cap_seconds=slot['wall_seconds'],prior_index_sha256=sha(pi),prior_review_sha256=sha(pr),live_agent_review_of_this_child=False,automated_progression=number>1,host_source_review_sha256=a['source_review_sha256']))
            command=[sys.executable,'-B','-m','experiments.s04b_exposure_refinement.case_driver','--mode',slot['mode'],'--case-id',name,'--library',str(args.library),'--build-receipt',str(args.build_receipt),'--admission',str(current/'admission.json'),'--output',str(current/'science')]
            if slot['mode']=='partial':command+=['--failed-prior',str(args.failed_prior)]
            timing(p,g,a,slot['wall_seconds']);started=time.monotonic()
            try:supervised(command,current/'supervision',slot['wall_seconds'],a,environment,current/'supervisor_spec.json')
            finally:child_seconds+=time.monotonic()-started
            candidate=append_candidate(p,a,previous,current,out,pi,pr,projection);write(current/'index.json',candidate)
            check=current/'automated_review.json'
            command=[sys.executable,'-B','-m',p['checker']['module'],'--repo',str(REPO),'--current',str(current),'--prior',str(pi),'--prior-review',str(pr),'--config',str(args.config),'--commit',a['source_commit'],'--output',str(check),'--checker-source-review',str(args.checker_review),'--checker-source-review-sha256',a['checker_source_review_sha256']]
            supervised(command,current/'checker_supervision',120,a,environment,current/'checker_supervisor_spec.json')
            check_receipt(check,current/'index.json',checker_pins,a['checker_source_review_sha256'])
            shutil.copyfile(current/'index.json',out/'index.json')
            result['children'].append(dict(case_id=name,artifact=current.relative_to(out).as_posix(),disposition=candidate['records'][-1]['disposition'],scientific_passed=candidate['records'][-1]['scientific_passed'],index_sha256=sha(out/'index.json'),automated_review_sha256=sha(check),scientific_result_sha256=sha(current/'science/result.json'),supervision_sha256=sha(current/'supervision/result.json')))
            result.pop('active_child',None);result.update(latest_index='index.json',index_sha256=sha(out/'index.json'),latest_automated_review=check.relative_to(out).as_posix(),counts=candidate['counts'],budget=candidate['budget'])
            write(out/'result.json',result);previous=candidate;pi=current/'index.json';pr=check;current=None
        timing(p,g,a,0);result.update(host_execution_passed=True,status='host_batch_complete')
    except BaseException as exc:
        result.update(host_execution_passed=False,status='stopped_requires_review',error_type=type(exc).__name__,error=str(exc))
        if current is not None:
            result['failed_child']=dict(artifact=current.relative_to(out).as_posix(),evidence={name:dict(path=(current/name).relative_to(out).as_posix(),sha256=sha(current/name)) if (current/name).is_file() else None for name in ('science/result.json','index.json','supervision/result.json','checker_supervision/result.json','automated_review.json')})
    finally:
        result['supervised_case_process_seconds']=child_seconds;write(out/'result.json',result)
    return 0 if result['host_execution_passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('admission','output','prior-index','prior-review','config','source-review','checker-review','library','build-receipt'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--failed-prior',type=Path)
    raise SystemExit(run(parser.parse_args()))
