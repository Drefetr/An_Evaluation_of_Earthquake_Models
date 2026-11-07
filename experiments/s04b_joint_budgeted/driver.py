"""Finite one-case allocations after a failed forecast; unchanged scientific fits."""
from __future__ import annotations
import time
PROCESS_STARTED=time.monotonic()  # Imports are charged; external supervision also bounds interpreter startup.
import argparse,copy,datetime,hashlib,math,os,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
sys.path.insert(0,str(REPO))
from experiments.s04b_joint_execution import driver as legacy
frozen,model,checkpoint=legacy.frozen,legacy.model,legacy.checkpoint
read,sha,require,write=legacy.read,legacy.sha,legacy.require,legacy.write
SCHEMA='joint_budgeted_case_index_v2'


def source_identity():
    files=[p for p in HERE.rglob('*')if p.is_file()and p.suffix in ('.py','.json')]
    result={p.relative_to(REPO).as_posix():sha(p)for p in sorted(files)}
    result.update(legacy.source_identity())
    result.update({(legacy.SCIENCE/name).relative_to(REPO).as_posix():pin for name,pin in frozen.source_identity().items()})
    return result


def verify_protocol():
    policy=read(HERE/'allocation_protocol.json');old,science=legacy.verify_protocol();p=policy['predecessor']
    require(policy['schema']=='joint_finite_allocation_protocol_v1','Allocation schema changed')
    require(legacy.source_identity()==p['source_sha256'],'Predecessor execution source changed')
    require(sha(legacy.HERE/'operational_protocol.json')==p['operational_protocol_sha256'],'Predecessor envelope changed')
    actual={(legacy.SCIENCE/name).relative_to(REPO).as_posix():pin for name,pin in frozen.source_identity().items()}
    require(actual==p['scientific_source_sha256'],'Scientific source changed')
    require(sha(legacy.SCIENCE/'protocol.json')==policy['scientific_protocol_sha256'],'Scientific protocol changed')
    require(policy['sequence']==old['sequence']and p['accepted_case_count']==len(science['pilot'])==5,'Fixed predecessor/roster differs')
    slots=policy['fixed_slots'];require([s['case_id']for s in slots]==old['sequence'][5:],'Allocation roster/order changed')
    require(len(slots)==len({s['case_id']for s in slots})==75,'Fixed75 remaining cases required')
    r=policy['resources'];require(r['campaign_aggregate_seconds']==115200 and r['batch_wall_seconds']==14400 and r['threads']==2 and r['workers']==1,'Allocation resource envelope changed')
    require(r['sampled_process_tree_rss_cap_bytes']==6442450944 and r['minimum_host_free_bytes']==2147483648 and r['startup_finalization_allowance_seconds']==30,'Memory/startup envelope changed')
    for s in slots:
        cap=2520 if s['input']['regime']in (4,6)else 420
        require(s['wall_seconds']==cap and s['scientific_reservation_seconds']==cap-30,'Frozen slot cap changed')
    require(math.fsum(s['wall_seconds']for s in slots)==109200,'Allocation total changed')
    require(p['already_charged_seconds']+109200<=115200,'Frozen allocation exceeds total budget')
    for name,pin in policy['evidence_sha256'].items():require(sha(frozen.safe(HERE,name))==pin,'Allocation evidence changed: '+name)
    reviewed=read(HERE/'evidence/allocation_protocol_review.json')
    require(sha(HERE/'evidence/allocation_protocol_review.json')==policy['transition_review_sha256']and reviewed['passed']is True,'Unreviewed transition proposal')
    require(reviewed['prior_index_sha256']==p['accepted_index_sha256']and reviewed['prior_output_review_sha256']==p['accepted_review_sha256'],'Transition predecessor review differs')
    return policy


def check_admission(args,policy,current):
    a=read(args.admission);p=policy['predecessor'];r=policy['resources']
    require(a['mode']=='budgeted_campaign','Explicit budgeted mode required')
    require(a['independent_review_passed']is True and a['scheduler_review_passed']is True and a['external_supervision']is True,'Independent source/scheduler/supervision admission required')
    require(a['source_sha256']==current['source_sha256']and a['allocation_protocol_sha256']==current['allocation_protocol_sha256'],'Admitted source/allocation differs')
    expiry=datetime.datetime.fromisoformat(a['expires_utc'])
    require(datetime.datetime.now(datetime.timezone.utc)<expiry<=datetime.datetime.fromisoformat(policy['shared_run']['expires_utc']),'Expired admission or expiry exceeds unchanged shared run')
    token=os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','')
    require(token and hashlib.sha256(token.encode()).hexdigest()==a['lease_token_sha256'],'Numerical lease attestation mismatch')
    require(a['threads']==2 and a['workers']==1 and a['sampled_process_tree_rss_cap_bytes']==r['sampled_process_tree_rss_cap_bytes'],'Execution resources differ')
    require(a.get('case_ids',[a['case_id']])==[a['case_id']],'Contradictory case admission')
    require(a['library_sha256']==current['library_sha256']==p['library_sha256']and a['build_receipt_sha256']==current['build_receipt_sha256']==p['build_receipt_sha256'],'Original native/build bytes required')
    require(current['runtime']['essential']==p['runtime_essential'],'Exact predecessor runtime required')
    build=read(args.build_receipt)
    require(build['passed']is True and build['source_sha256']==sha(legacy.SCIENCE/'attenuation.cpp')and build['library_sha256']==current['library_sha256'],'Original native build provenance differs')
    attempt=a['numerical_attempt_id'];require(isinstance(attempt,str)and attempt and all(c.isalnum()or c=='-'for c in attempt),'Invalid attempt ID')
    wall=a['wall_seconds'];require(isinstance(wall,(int,float))and not isinstance(wall,bool)and math.isfinite(wall)and 0<wall<=r['batch_wall_seconds'],'Invalid finite batch cap')
    return a


def transition_files(policy,index_path,review_path,out):
    dest=out/'transition';dest.mkdir()
    sources={'predecessor_index.json':Path(index_path),'predecessor_review.json':Path(review_path)}
    sources.update({name:HERE/name for name in policy['evidence_sha256']})
    pins={}
    for relative,source in sources.items():
        target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        pins['transition/'+relative]=sha(source)
    return dict(schema='joint_budgeted_transition_v1',predecessor_index_sha256=policy['predecessor']['accepted_index_sha256'],
        predecessor_source_sha256=policy['predecessor']['source_sha256'],predecessor_operational_protocol_sha256=policy['predecessor']['operational_protocol_sha256'],
        allocation_protocol_sha256=sha(HERE/'allocation_protocol.json'),old_projection_status='failed',files=pins)


def validate_transition(index,policy,root):
    t=index['transition'];p=policy['predecessor']
    require(t['schema']=='joint_budgeted_transition_v1'and t['old_projection_status']=='failed','Transition classification changed')
    require(t['predecessor_index_sha256']==p['accepted_index_sha256']and t['predecessor_source_sha256']==p['source_sha256']and t['predecessor_operational_protocol_sha256']==p['operational_protocol_sha256'],'Transition predecessor source changed')
    require(t['allocation_protocol_sha256']==sha(HERE/'allocation_protocol.json'),'Transition allocation changed')
    expected={'transition/predecessor_index.json':p['accepted_index_sha256'],'transition/predecessor_review.json':p['accepted_review_sha256']}
    expected.update({'transition/'+name:pin for name,pin in policy['evidence_sha256'].items()})
    require(t['files']==expected,'Transition evidence roster differs')
    for name,pin in expected.items():require(sha(frozen.safe(root,name))==pin,'Transition evidence changed: '+name)
    predecessor=read(root/'transition/predecessor_index.json')
    require(index['cases'][:5]==predecessor['cases']and index['attempts'][:len(predecessor['attempts'])]==predecessor['attempts'],'Original accepted cases/charged attempts changed')
    require(index['reviews'][:len(predecessor['reviews'])]==predecessor['reviews'],'Original review prefix changed')
    validate_resume(root,index,policy)


def validate_resume(root,index,policy):
    require((root/'training_resume').is_dir(),'Original training_resume directory is required')
    first=index['cases'][0];path=frozen.safe(root,first['file'])
    require(sha(path)==first['sha256'],'Frozen first-case report changed')
    provenance_path=root/'training_resume/provenance.json'
    require(sha(provenance_path)==policy['predecessor']['training_resume_provenance_sha256'],'Original resume provenance bytes changed')
    provenance=read(provenance_path)
    require(provenance==read(path)['resume_provenance'],'Resume provenance differs from frozen first case')
    expected={'training_resume/provenance.json',*provenance['evidence_files'].values()}
    require({p.relative_to(root).as_posix()for p in (root/'training_resume').rglob('*')if p.is_file()}==expected,'Original resume evidence roster differs')
    for key,relative in provenance['evidence_files'].items():require(sha(frozen.safe(root,relative))==provenance[key],'Original resume evidence changed')


def copy_resume(root,out,index,policy):
    validate_resume(root,index,policy)
    shutil.copytree(root/'training_resume',out/'training_resume')


def copy_new_index(args,admission,policy,current,cases,out):
    path=Path(args.prior_index).resolve();root=path.parent;review_path=Path(args.prior_review).resolve()
    review=read(review_path);index=read(path);old=read(legacy.HERE/'operational_protocol.json')
    require(review['passed']is True and sha(path)==review['index_sha256']==admission['prior_index_sha256']and sha(review_path)==admission['prior_review_sha256'],'Prior index lacks exact independent acceptance')
    require(index['schema']==SCHEMA and index['source_sha256']==current['source_sha256']and index['allocation_protocol_sha256']==current['allocation_protocol_sha256'],'Accepted budgeted source/schema differs')
    require(index['runtime']['essential']==current['runtime']['essential']and index['library_sha256']==current['library_sha256']and index['build_receipt_sha256']==current['build_receipt_sha256'],'Accepted runtime/native differs')
    require(index['science_protocol_sha256']==policy['scientific_protocol_sha256'],'Accepted scientific protocol differs')
    require(index['partial_case']is None and index['last_attempt_passed']is True,'Failed/partial predecessor blocks automatic progression')
    legacy.charged(index,old);validate_transition(index,policy,root)
    require([r['case_id']for r in index['cases']]==policy['sequence'][:len(index['cases'])],'Accepted cases are not fixed prefix')
    lookup={c['case_id']:c for c in cases}
    for entry in index['cases']:
        require(entry['file']=='cases/'+entry['case_id']+'.json'and entry['trace']=='cases/'+entry['case_id']+'.attempts.jsonl','Accepted case path differs')
        record=read(frozen.safe(root,entry['file']));legacy.verify_case(record,entry,lookup[entry['case_id']])
        require(record['attempts_sha256']==entry['trace_sha256'],'Case trace pin differs')
        legacy.copy_bound(root,out,entry['file'],entry['sha256']);legacy.copy_bound(root,out,entry['trace'],entry['trace_sha256'])
    old_attempt_count=len(read(root/'transition/predecessor_index.json')['attempts'])
    require(len(index['attempts'])-old_attempt_count==len(index['cases'])-5,'New accepted attempts/cases differ')
    for number,entry in enumerate(index['attempts']):
        receipt=read(frozen.safe(root,entry['file']))
        require(receipt['attempt_id']==entry['attempt_id']and receipt['phase']==entry['phase']and receipt['wall_seconds']==entry['seconds']and receipt['passed']is True,'Charged attempt differs or failed')
        if number>=old_attempt_count:
            slot=policy['fixed_slots'][number-old_attempt_count]
            require(receipt['source_sha256']==current['source_sha256']and receipt['allocation_protocol_sha256']==current['allocation_protocol_sha256'],'New attempt source/allocation changed')
            require(receipt['phase']=='campaign'and receipt['case_ids']==[slot['case_id']]and receipt['wall_seconds']<=slot['wall_seconds']and receipt['partial_case']is None,'New attempt roster/cap/completion differs')
        legacy.copy_bound(root,out,entry['file'],entry['sha256'])
    for entry in index['reviews']:legacy.copy_bound(root,out,entry['file'],entry['sha256'])
    for name,pin in index['transition']['files'].items():legacy.copy_bound(root,out,name,pin)
    copy_resume(root,out,index,policy);shutil.copy2(path,out/'parent_index.json')
    name='reviews/'+sha(review_path)+'.json';(out/'reviews').mkdir(exist_ok=True)
    require(not(out/name).exists(),'Repeated acceptance review');shutil.copy2(review_path,out/name)
    index['reviews'].append(dict(file=name,sha256=sha(review_path),accepted_index_sha256=sha(path)))
    return index


def accepted_index(args,admission,policy,current,cases,out):
    prior=read(args.prior_index);p=policy['predecessor']
    if prior['schema']==SCHEMA:return copy_new_index(args,admission,policy,current,cases,out)
    require(prior['schema']=='joint_accepted_case_index_v1','Unsupported predecessor schema')
    require(sha(args.prior_index)==p['accepted_index_sha256']and sha(args.prior_review)==p['accepted_review_sha256'],'Only frozen completed five-case predecessor can transition')
    require(admission['transition_review_sha256']==policy['transition_review_sha256'],'Unreviewed explicit operational transition')
    old=read(legacy.HERE/'operational_protocol.json')
    old_current=dict(source_sha256=legacy.source_identity(),operational_protocol_sha256=sha(legacy.HERE/'operational_protocol.json'),runtime=current['runtime'],library_sha256=current['library_sha256'],build_receipt_sha256=current['build_receipt_sha256'])
    index=legacy.accepted_index(args,admission,old,old_current,cases,out)
    require(len(index['cases'])==5 and legacy.charged(index,old)[0]==p['already_charged_seconds'],'Transition case/time basis differs')
    index['transition']=transition_files(policy,args.prior_index,args.prior_review,out)
    index.update(schema=SCHEMA,source_sha256=current['source_sha256'],allocation_protocol_sha256=current['allocation_protocol_sha256'],last_attempt_passed=True)
    index.pop('operational_protocol_sha256')
    validate_transition(index,policy,out)
    return index


def allocation(index,policy,admission,cases):
    count=len(index['cases']);require(5<=count<80,'Exactly one remaining case required')
    require([r['case_id']for r in index['cases']]==policy['sequence'][:count],'Accepted prefix differs')
    slots=policy['fixed_slots'];slot=slots[count-5]
    require(admission['case_id']==slot['case_id']==policy['sequence'][count]and admission['wall_seconds']==slot['wall_seconds'],'Wrong next case or frozen wall cap')
    require(admission['numerical_attempt_id']not in {r['attempt_id']for r in index['attempts']},'Attempt already charged')
    require(index['partial_case']is None and index['last_attempt_passed']is True,'Unresolved predecessor stops progression')
    total,pilot=legacy.charged(index,read(legacy.HERE/'operational_protocol.json'))
    unspent=math.fsum(s['wall_seconds']for s in slots[count-5:])
    require(total+unspent<=policy['resources']['campaign_aggregate_seconds'],'All unspent fixed slots no longer fit aggregate cap')
    lookup={c['case_id']:c for c in cases};case=lookup[slot['case_id']]
    require(all(case[k]==v for k,v in slot['input'].items()),'Fixed input dimensions/identity changed')
    return slot,dict(prior_charged_seconds=total,unspent_fixed_slot_seconds=unspent,maximum_future_charge=total+unspent,forecast_passed=False)


def persist_attempt(out,index,result,admission,policy,current,started,deadline,active):
    """Write truthful failure/success records, then test final serialization deadline."""
    if active and index['partial_case']is None:
        path=out/'cases'/(active+'.json');trace=out/'cases'/(active+'.attempts.jsonl')
        index['partial_case']=dict(case_id=active,file='cases/'+active+'.json',sha256=sha(path)if path.exists()else None,
            trace='cases/'+active+'.attempts.jsonl',trace_sha256=sha(trace)if trace.exists()else None,status='interrupted_or_persistence_failure')
    if index['partial_case']is not None:
        result.update(passed=False,status='failed_requires_review',scientific_completion=False)
    attempt=admission['numerical_attempt_id'];relative='attempts/'+attempt+'.json'
    require(attempt not in {r['attempt_id']for r in index['attempts']},'Duplicate attempted persistence')
    entry=dict(attempt_id=attempt,phase='campaign',file=relative);index['attempts'].append(entry)
    def save():
        elapsed=time.monotonic()-started;result['wall_seconds']=elapsed;index['last_attempt_passed']=result['passed']
        receipt=dict(attempt_id=attempt,phase='campaign',wall_seconds=elapsed,passed=result['passed'],status=result['status'],case_ids=[r['case_id']for r in result['cases']],partial_case=index['partial_case'],source_sha256=current['source_sha256'],allocation_protocol_sha256=current['allocation_protocol_sha256'],admission_sha256=sha(admission['_path']),parent_index_sha256=admission['prior_index_sha256'],clock_scope='Module entry through final persistence preparation; outer supervisor bounds full process lifetime')
        write(out/relative,receipt);entry.update(seconds=elapsed,sha256=sha(out/relative))
        original=index['original_failure']['prior_scientific_seconds']
        index['budget']=dict(total_seconds=math.fsum([original,*[r['seconds']for r in index['attempts']]]),pilot_seconds=math.fsum([original,*[r['seconds']for r in index['attempts']if r['phase']=='pilot']]))
        write(out/'index.json',index)
        result.update(index_sha256=sha(out/'index.json'),complete_cases=len(index['cases']),budget=index['budget'],independent_index_review_required=True,**legacy.fit_census(index,out))
        write(out/'result.json',result)
    save()
    # No late result may retain a pass, even if case/summary computation finished in time.
    if time.monotonic()>=deadline or index['budget']['total_seconds']>policy['resources']['campaign_aggregate_seconds']:
        result.update(passed=False,status='failed_requires_review',scientific_completion=False,error_type='FinalizationDeadline',error='Final receipt/index serialization exceeded admitted deadline or aggregate budget')
        save()


def run(args,started=None):
    started=PROCESS_STARTED if started is None else started
    out=Path(args.output).resolve();require(not out.is_relative_to(REPO),'Output must be outside checkout')
    out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir();(out/'attempts').mkdir()
    result=dict(schema='joint_budgeted_batch_v1',passed=False,status='preflight',cases=[],scientific_completion=False,old_projection_status='failed')
    write(out/'result.json',result);index=None;admission=None;active=None;deadline=started
    try:
        policy=verify_protocol();science=read(legacy.SCIENCE/'protocol.json')
        current=dict(source_sha256=source_identity(),allocation_protocol_sha256=sha(HERE/'allocation_protocol.json'),runtime=frozen.runtime_identity(),library_sha256=sha(args.library),build_receipt_sha256=sha(args.build_receipt))
        result.update(current);admission=check_admission(args,policy,current);admission['_path']=str(args.admission)
        result['admission_sha256']=sha(args.admission)
        deadline=min(started+admission['wall_seconds'],time.monotonic()+(datetime.datetime.fromisoformat(admission['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        cases=frozen.verify_inputs(science);index=accepted_index(args,admission,policy,current,cases,out)
        slot,budget=allocation(index,policy,admission,cases);result.update(allocation=budget,requested_case=slot['case_id'],prior_case_count=len(index['cases']))
        require(deadline-time.monotonic()>=slot['scientific_reservation_seconds'],'Startup consumed reserved scientific opportunity; stop before fitting')
        require(time.monotonic()<deadline,'Expired before case')
        modules=model.archived();native=model.Native(args.library)
        with legacy.OrderedChunkScheduler()as scheduler:
            delegate=legacy.runner_with_scheduler(scheduler);active=slot['case_id'];result.update(status='running',active_case=active);write(out/'result.json',result)
            case=next(c for c in cases if c['case_id']==active)
            case_deadline=min(deadline,time.monotonic()+slot['scientific_reservation_seconds'])
            report=delegate.case_run(case,modules,native,science,out/'cases',case_deadline,None)
            entry=dict(case_id=active,file='cases/'+active+'.json',sha256=sha(out/'cases'/(active+'.json')),trace='cases/'+active+'.attempts.jsonl',trace_sha256=sha(out/'cases'/(active+'.attempts.jsonl')),reused_fit_arms=0,new_fit_arms=4)
            if not report['passed']:
                index['partial_case']=entry;require(False,'Failed partial retained; no automatic continuation')
            legacy.verify_case(report,entry,case);index['cases'].append(entry);result['cases'].append(entry)
            active=None;result.pop('active_case',None)
        require(time.monotonic()<deadline,'Case completed after wall allowance')
        if len(index['cases'])==80:
            result['summary_sha256']=legacy.final_summary(index,science,out,deadline);result['scientific_completion']=True
        result.update(passed=True,status='batch_complete',new_fit_arms=4,reused_fit_arms=0)
    except BaseException as exc:
        result.update(passed=False,status='failed_requires_review',scientific_completion=False,error_type=type(exc).__name__,error=str(exc))
    finally:
        if index is not None and admission is not None and admission['numerical_attempt_id']not in {r['attempt_id']for r in index['attempts']}:
            persist_attempt(out,index,result,admission,policy,current,started,deadline,active)
        else:
            result.update(wall_seconds=time.monotonic()-started,unindexed_attempt_requires_conductor_accounting=True);write(out/'result.json',result)
    return 0 if result['passed']else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('admission','library','build-receipt','prior-index','prior-review','output'):parser.add_argument('--'+name,required=True)
    raise SystemExit(run(parser.parse_args()))
