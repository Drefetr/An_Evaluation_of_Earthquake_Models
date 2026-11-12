"""One explicitly amended case; no fit is started without pinned admission."""
from __future__ import annotations
import time
PROCESS_STARTED=time.monotonic()
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path

HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def write(path,value):
    p=Path(path);tmp=p.with_name(p.name+'.tmp')
    with tmp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)


def safe(root,relative):
    p=(root/relative).resolve();require(not Path(relative).is_absolute() and p.is_relative_to(root.resolve()),'Escaping source path');return p


def source_identity():
    p=read(HERE/'protocol.json');paths=set(p['source_sha256'])
    paths.update(x.relative_to(REPO).as_posix() for x in HERE.iterdir() if x.is_file() and x.suffix in ('.py','.json'))
    return {name:sha(safe(REPO,name)) for name in sorted(paths)}


def verify_protocol():
    p=read(HERE/'protocol.json')
    require(p['schema']=='joint_exposure_refinement_protocol_v1' and p['version']=='joint_exposure_refinement_v1','Wrong amendment protocol')
    require(p['partial_case_id']=='S6_narrow_short_total_seed410603' and p['case_ids']==p['full_sequence'][44:]
        and len(p['case_ids'])==len(set(p['case_ids']))==36,'Amended roster differs')
    require([r['case_id'] for r in p['case_slots']]==p['case_ids'],'Slot roster differs')
    for i,r in enumerate(p['case_slots']):
        cap=1806 if i==0 else 2520 if r['case_id'].startswith('S6_') else 1200
        require(r['wall_seconds']==cap and r['scientific_seconds']==cap-30 and r['mode']==('partial' if i==0 else 'untouched'),'Fixed case allocation differs')
    for field in ('source_sha256','design_evidence_sha256'):
        for rel,pin in p[field].items():require(sha(safe(REPO,rel))==pin,'Changed dependency/evidence: '+rel)
    science=read(REPO/'experiments/s04b_joint_nuisance/protocol.json')
    require(sha(REPO/'experiments/s04b_joint_nuisance/protocol.json')==p['original_scientific_protocol_sha256'],'Original science protocol differs')
    require(p['refinement']['joint_absolute_tolerance']==science['quadrature']['joint_absolute_tolerance']
        and p['refinement']['projected_gradient_scaled_tolerance']==science['quadrature']['selected_training_gradient_scaled_tolerance'],'Original numerical limits differ')
    resources=p['resources'];require(resources['shared_cap_seconds']==115200 and resources['threads']==2 and resources['workers']==1
        and resources['rss_cap_bytes']==6442450944 and resources['minimum_host_free_bytes']==2147483648,'Resource envelope differs')
    return p


def load_partial(root,p):
    f=p['failed_case'];root=Path(root).resolve()
    for member,pin in [(f['case_member'],f['case_sha256']),(f['trace_member'],f['trace_sha256']),
                       (f['driver_result_member'],f['driver_result_sha256']),(f['supervision_member'],f['supervision_sha256'])]:
        require(sha(safe(root,member))==pin,'Partial evidence member changed')
    require(sha(safe(REPO,f['archive']['path']))==f['archive']['sha256'] and sha(safe(REPO,f['review']['path']))==f['review']['sha256'],'Partial archive/audit differs')
    report=read(safe(root,f['case_member']));trace=[json.loads(x) for x in safe(root,f['trace_member']).read_text(encoding='utf-8').splitlines()]
    failed=read(safe(root,f['driver_result_member']));require(failed['passed'] is False and failed['disposition_valid'] is False,'Partial failure relabeled')
    return report,trace


def admission(args,p,current):
    a=read(args.admission);r=next(v for v in p['case_slots'] if v['case_id']==args.case_id)
    require(a['mode']=='exposure_refinement_case' and a['case_id']==args.case_id and a['case_ids']==[args.case_id]
        and args.mode==r['mode'],'Wrong amended case admission')
    require(a['source_sha256']==current['source_sha256'] and a['protocol_sha256']==current['protocol_sha256']
        and a['amendment_protocol_sha256']==current['protocol_sha256'],'Amendment source differs')
    require(a['independent_review_passed'] is True and a['external_supervision'] is True,'Unreviewed execution')
    require(a['operational_run_id']==p['shared_run']['run_id'] and a['operational_run_config_sha256']==p['shared_run']['config_sha256'],'Shared run differs')
    expiry=datetime.datetime.fromisoformat(a['expires_utc'])
    require(datetime.datetime.now(datetime.timezone.utc)<expiry<=datetime.datetime.fromisoformat(p['shared_run']['expires_utc']),'Expired admission')
    require(a['wall_seconds']==r['wall_seconds'] and a['scientific_seconds']==r['scientific_seconds'],'Changed fixed cap')
    require(a['threads']==2 and a['workers']==1 and a['sampled_process_tree_rss_cap_bytes']==6442450944 and a['minimum_host_free_bytes']==2147483648,'Resource admission differs')
    token=os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','')
    require(token and hashlib.sha256(token.encode()).hexdigest()==a['lease_token_sha256'],'Missing lease attestation')
    require(current['runtime']['essential']==p['original_native']['runtime_essential'],'Original runtime differs')
    for key in ('library_sha256','build_receipt_sha256'):
        require(current[key]==a[key]==p['original_native'][key],'Original native/build differs')
    b=read(args.build_receipt);require(b['passed'] is True and b['library_sha256']==current['library_sha256'] and b['source_sha256']==p['source_sha256']['experiments/s04b_joint_nuisance/attenuation.cpp'],'Build provenance differs')
    return a,r,expiry


def run(args):
    out=Path(args.output).resolve();require(not out.exists() and not out.is_relative_to(REPO),'Fresh external output required')
    out.mkdir(parents=True);(out/'cases').mkdir()
    result=dict(schema='joint_exposure_refinement_case_v1',case_id=args.case_id,passed=False,scientific_passed=False,
                handled=False,disposition_valid=False,scientific_completion=False,disposition='technical_failure',status='preflight')
    write(out/'result.json',result);adapter=None;deadline=None;scientific_cap=None
    try:
        p=verify_protocol();require(args.case_id in p['case_ids'],'Case outside exact amended roster')
        admitted_sources=source_identity();protocol_pin=sha(HERE/'protocol.json');early=read(args.admission)
        require(early['source_sha256']==admitted_sources and early['protocol_sha256']==protocol_pin,'Source admission must match before scientific imports')
        for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='2'
        # All frozen dependencies were checked before their imports.
        from experiments.s04b_joint_execution import driver as legacy
        from experiments.s04b_joint_remaining import case_driver as original_driver
        from threadpoolctl import threadpool_limits
        from .adapter import Adapter,same
        frozen,model=legacy.frozen,legacy.model
        current=dict(source_sha256=admitted_sources,protocol_sha256=protocol_pin,runtime=frozen.runtime_identity(),library_sha256=sha(args.library),build_receipt_sha256=sha(args.build_receipt))
        result.update(current,admission_sha256=sha(args.admission))
        a,slot,expiry=admission(args,p,current);scientific_cap=slot['scientific_seconds'];result.update(numerical_attempt_id=a['numerical_attempt_id'],allocation=slot)
        deadline=min(PROCESS_STARTED+slot['wall_seconds'],time.monotonic()+(expiry-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        science=read(legacy.SCIENCE/'protocol.json');cases=frozen.verify_inputs(science);case=next(v for v in cases if v['case_id']==args.case_id)
        partial=trace=None
        if args.mode=='partial':require(args.failed_prior is not None,'Exact failed prior required');partial,trace=load_partial(args.failed_prior,p)
        else:require(args.failed_prior is None,'Untouched case cannot consume a partial checkpoint')
        modules=model.archived();native=model.Native(args.library)
        require(deadline-time.monotonic()>=slot['scientific_seconds'],'Startup consumed scientific reservation')
        scientific_deadline=min(deadline,PROCESS_STARTED+slot['scientific_seconds'])
        adapter=Adapter(science,out,partial,trace)
        with threadpool_limits(limits=2),legacy.OrderedChunkScheduler() as scheduler:
            runner=legacy.runner_with_scheduler(scheduler);factory=runner.model.phase_from_rows
            def phase_factory(rows,gm,start,end,modules,native,deadline):
                return adapter.wrap_phase(factory(rows,gm,start,end,modules,native,deadline),start,end)
            runner.model.phase_from_rows=phase_factory;runner.fit_arm=adapter.fit_arm;runner.fine_check=adapter.fine_check
            original_floor=runner.historical_floor
            runner.historical_floor=lambda *values:adapter.historical_floor(original_floor,*values)
            result['status']='running';write(out/'result.json',result)
            report=runner.case_run(case,modules,native,science,out/'cases',scientific_deadline,None)
        path=out/'cases'/(args.case_id+'.json');tracepath=out/'cases'/(args.case_id+'.attempts.jsonl')
        durable=read(path)
        require(same(durable,report),'Original returned case/durable case mismatch')
        # Frozen checkpoint serialization resolves NumPy scalars without changing values.
        report=durable
        reuse=dict(schema='joint_exposure_refinement_reuse_v1',mode=args.mode,entries=adapter.reuse_entries,
                   original_failure_reference=p['failed_case'] if partial is not None else None,
                   reused_optimizer_attempts=sum(8 if v['kind']=='complete_arm' else 4 if v['kind']=='total_prefix' else 0 for v in adapter.reuse_entries),
                   prior_failed_total_start4_attempts_retained=2 if partial is not None else 0,
                   computation='Exact source-bound saved objects; no fresh optimizer/evaluation claim')
        write(out/'reuse_map.json',reuse)
        amendment=dict(version=p['version'],protocol_sha256=current['protocol_sha256'],
            original_scientific_protocol_sha256=p['original_scientific_protocol_sha256'],
            computation_kind='amended_partial_resume' if partial is not None else 'amended_untouched',
            reuse_map_sha256=sha(out/'reuse_map.json'),refinement_event_log_sha256=sha(out/'refinement_events.jsonl'),
            execution_calls_sha256=sha(out/'execution_calls.jsonl'),original_failure_reference=reuse['original_failure_reference'])
        report['numerical_amendment']=amendment;write(path,report)
        result.update(report_file='cases/'+path.name,report_sha256=sha(path),trace_file='cases/'+tracepath.name,
                      trace_sha256=sha(tracepath) if tracepath.exists() else None,numerical_amendment=amendment,
                      input_case=case,phase_constructions=adapter.phase_constructions)
        require(tracepath.exists(),'No retained attempt trace')
        disposition=original_driver.classify(report,case,science,original_driver.trace_records(tracepath),adapter.phase_constructions)
        if disposition['scientific_passed']:legacy.verify_case(report,dict(case_id=args.case_id),case)
        result.update(disposition,handled=True,disposition_valid=True,status='terminal_disposition')
    except BaseException as exc:
        result.update(passed=False,scientific_passed=False,handled=False,disposition_valid=False,disposition='technical_failure',status='failed',error_type=type(exc).__name__,error=str(exc))
    finally:
        if adapter is not None:
            calls=adapter.receipt();result.update(adapter=calls,evaluation_census=calls['evaluation_census'],
                refinement_census=dict(started=calls['refinement_started'],accepted=calls['refinement_accepted'],rejected=calls['refinement_rejected']),
                actual_optimizer_attempts=len(calls['physical_optimizer_calls']),reused_optimizer_attempts=sum(8 if v['kind']=='complete_arm' else 4 if v['kind']=='total_prefix' else 0 for v in adapter.reuse_entries))
        result['wall_seconds']=time.monotonic()-PROCESS_STARTED
        if scientific_cap is not None and result['wall_seconds']>scientific_cap:
            result.update(passed=False,scientific_passed=False,handled=False,disposition_valid=False,disposition='technical_failure',status='failed',scientific_clock_cap_exceeded=True)
        if deadline is not None and time.monotonic()>=deadline:
            result.update(passed=False,scientific_passed=False,handled=False,disposition_valid=False,disposition='technical_failure',status='failed',finalization_deadline_exceeded=True)
        write(out/'result.json',result)
    return 0 if result['handled'] and result['disposition_valid'] else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-id',required=True);parser.add_argument('--mode',required=True,choices=('partial','untouched'))
    for name in ('library','build-receipt','admission','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--failed-prior',type=Path)
    return run(parser.parse_args())


if __name__=='__main__':raise SystemExit(main())
