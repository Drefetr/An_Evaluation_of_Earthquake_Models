"""Reviewed bounded batches of the unchanged joint study; no automatic admission."""
from __future__ import annotations
import argparse,copy,datetime,gc,hashlib,importlib.util,json,math,os,shutil,sys,time,types
from pathlib import Path
for key in('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='2'
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1];SCIENCE=HERE.parent/'s04b_joint_nuisance'
sys.path.insert(0,str(REPO))
from experiments.s04b_joint_nuisance import model,checkpoint
from experiments.s04b_joint_nuisance import run as frozen
from experiments.s04b_joint_execution.parallel_chunks import OrderedChunkScheduler,ParallelPhase
read,sha,require=frozen.read,frozen.sha,frozen.require
write=checkpoint.write


def identity(value):
    return hashlib.sha256(checkpoint.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def source_identity():
    files=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))
    return {p.relative_to(REPO).as_posix():sha(p)for p in sorted(files)}


def verify_protocol():
    op=read(HERE/'operational_protocol.json');science=read(SCIENCE/'protocol.json')
    require(sha(SCIENCE/'protocol.json')==op['science_protocol_sha256'],'Scientific protocol changed')
    require(sha(SCIENCE/'input_pins.json')==op['science_input_pins_sha256'],'Scientific input pins changed')
    for name,pin in op['frozen_sources_sha256'].items():require(sha(frozen.safe(REPO,name))==pin,'Frozen source changed: '+name)
    require(sha(HERE/'parallel_chunks.py')==op['scheduler_sha256'],'Audited scheduler changed')
    require(op['pilot']==science['pilot'] and op['sequence']==science['pilot']+[c for c in science['roster']if c not in science['pilot']],'Operational roster changed')
    require(len(op['sequence'])==len(set(op['sequence']))==80,'Fixed80 roster required')
    return op,science


def runner_with_scheduler(scheduler):
    """Private module globals/facade; never mutate the process-wide model module."""
    spec=importlib.util.spec_from_file_location('_joint_frozen_batch_delegate',SCIENCE/'run.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    facade=types.SimpleNamespace(**vars(model))
    def phase_factory(*args,**kwargs):
        serial=model.phase_from_rows(*args,**kwargs)
        return ParallelPhase(serial.a,serial.m,serial.modules,serial.native,serial.deadline,scheduler=scheduler)
    facade.phase_from_rows=phase_factory;runner.model=facade
    return runner


def new_index(op,current):
    return dict(schema='joint_accepted_case_index_v1',source_sha256=current['source_sha256'],
        operational_protocol_sha256=current['operational_protocol_sha256'],science_protocol_sha256=op['science_protocol_sha256'],
        runtime=current['runtime'],library_sha256=current['library_sha256'],build_receipt_sha256=current['build_receipt_sha256'],
        original_failure=op['original_failure'],cases=[],attempts=[],reviews=[],partial_case=None,
        budget=dict(total_seconds=op['original_failure']['prior_scientific_seconds'],pilot_seconds=op['original_failure']['prior_scientific_seconds']))


def charged(index,op):
    original=op['original_failure']['prior_scientific_seconds']
    require(index['original_failure']==op['original_failure'],'Original failed time/provenance changed')
    amounts=[r['seconds']for r in index['attempts']]
    require(all(isinstance(v,(int,float))and not isinstance(v,bool)and math.isfinite(v)and v>=0 for v in amounts),'Invalid attempt elapsed time')
    require(len({r['attempt_id']for r in index['attempts']})==len(index['attempts']),'Duplicate charged attempt')
    total=math.fsum([original,*amounts]);pilot=math.fsum([original,*[r['seconds']for r in index['attempts']if r['phase']=='pilot']])
    require(abs(total-index['budget']['total_seconds'])<=1e-9 and abs(pilot-index['budget']['pilot_seconds'])<=1e-9,'Index elapsed-time accounting differs')
    return total,pilot


def verify_case(report,entry,case):
    require(report['passed']is True and report['status']=='complete'and report['case_id']==entry['case_id']==case['case_id'],'Incomplete accepted case')
    require(report['training_selections_frozen']is True and len(report['fits'])==4 and len(report['outcomes'])==5 and len(report['floor_checks'])==6 and len(report['historical_comparisons'])==5,'Accepted case roster incomplete')
    require(report['n_train']==case['n_train']and report['n_test']==case['n_test'],'Accepted denominator changed')
    for name in('null',*frozen.MODELS):
        fit=report['fits'][name];require(fit['passed']is True and fit['required_starts']==8 and fit['resolved_starts']==[True]*8 and report['training_checks'][name]['passed']is True,'Accepted fit/check incomplete')
    for relative,pin in report['input_sha256'].items():
        root=REPO if relative.startswith('validation/')else REPO/'reproduction/synthetic'
        require(sha(frozen.safe(root,relative))==pin,'Accepted case input changed')


def copy_bound(source_root,destination,relative,pin):
    source=frozen.safe(source_root,relative);require(sha(source)==pin,'Bound prior artifact changed: '+relative)
    target=frozen.safe(destination,relative);target.parent.mkdir(parents=True,exist_ok=True)
    require(not target.exists(),'Duplicate artifact path: '+relative);shutil.copy2(source,target)


def accepted_index(args,admission,op,current,cases,out):
    if args.prior_index is None:
        require(args.prior_review is None,'Prior review without index')
        require(admission.get('prior_index_sha256')is None,'Admitted prior index is missing')
        return new_index(op,current)
    path=Path(args.prior_index).resolve();root=path.parent;review_path=Path(args.prior_review).resolve()
    review=read(review_path)
    require(sha(path)==admission['prior_index_sha256']==review['index_sha256']and sha(review_path)==admission['prior_review_sha256']and review['passed']is True,'Prior index lacks exact independent acceptance')
    index=read(path)
    require(index['source_sha256']==current['source_sha256']and index['operational_protocol_sha256']==current['operational_protocol_sha256'],'Accepted source/envelope differs')
    require(index['runtime']['essential']==current['runtime']['essential']and index['library_sha256']==current['library_sha256']and index['build_receipt_sha256']==current['build_receipt_sha256'],'Accepted runtime/native identity differs')
    require(index['partial_case']is None,'Failed partial fit requires an explicit independently reviewed disposition; no automatic refit')
    charged(index,op)
    require([r['case_id']for r in index['cases']]==op['sequence'][:len(index['cases'])],'Accepted cases are not the exact fixed prefix')
    lookup={c['case_id']:c for c in cases}
    for entry in index['cases']:
        require(entry['file']=='cases/'+entry['case_id']+'.json'and entry['trace']=='cases/'+entry['case_id']+'.attempts.jsonl','Accepted case file path differs')
        report=read(frozen.safe(root,entry['file']));verify_case(report,entry,lookup[entry['case_id']])
        require(report['attempts_sha256']==entry['trace_sha256'],'Accepted trace pin differs')
        copy_bound(root,out,entry['file'],entry['sha256']);copy_bound(root,out,entry['trace'],entry['trace_sha256'])
    for entry in index['attempts']:
        receipt=read(frozen.safe(root,entry['file']))
        require(receipt['attempt_id']==entry['attempt_id']and receipt['phase']==entry['phase']and receipt['wall_seconds']==entry['seconds'],'Charged receipt differs')
        copy_bound(root,out,entry['file'],entry['sha256'])
    for entry in index['reviews']:copy_bound(root,out,entry['file'],entry['sha256'])
    if (root/'training_resume').exists():
        provenance=read(root/'training_resume/provenance.json')
        for key,relative in provenance['evidence_files'].items():require(sha(frozen.safe(root,relative))==provenance[key],'Original resume evidence changed')
        shutil.copytree(root/'training_resume',out/'training_resume')
    shutil.copy2(path,out/'parent_index.json')
    target='reviews/'+sha(review_path)+'.json';(out/'reviews').mkdir(exist_ok=True)
    require(not(out/target).exists(),'Repeated acceptance review');shutil.copy2(review_path,out/target)
    index['reviews'].append(dict(file=target,sha256=sha(review_path),accepted_index_sha256=sha(path)))
    return index


def next_batch(index,op,requested):
    count=len(index['cases']);phase='pilot'if count<len(op['pilot'])else'campaign'
    limit=len(op['pilot'])if phase=='pilot'else len(op['sequence'])
    require(requested and len(set(requested))==len(requested),'Empty/duplicate batch')
    require(requested==op['sequence'][count:count+len(requested)]and count+len(requested)<=limit,'Batch must be next exact prefix within one phase')
    require(phase!='pilot'or len(requested)==1,'Initial pilot batches contain exactly one fixed history')
    return phase


def remaining_projection(cases,index,science,out):
    reports=[read(out/r['file'])for r in index['cases']if r['case_id']in science['pilot']]
    require(len(reports)==5,'Campaign requires five accepted pilot cases')
    estimate=frozen.projection(cases,reports);done={r['case_id']for r in index['cases']}
    estimate['remaining_seconds']=3*estimate['maximum_seconds_per_work']*sum(v for k,v in estimate['work_by_case'].items()if k not in done)
    return estimate


def final_summary(index,science,out,deadline):
    require(len(index['cases'])==80,'All80 cases required for final summary')
    reports=[read(out/r['file'])for r in index['cases']]
    summary=frozen.aggregate(reports,science);write(out/'summary.json',summary)
    require(sum(len(r['floor_checks'])for r in reports)==480 and sum(len(r['historical_comparisons'])for r in reports)==400,'Final scientific accounting incomplete')
    require(time.monotonic()<deadline,'Final aggregate/summary serialization completed after wall allowance')
    return sha(out/'summary.json')


def fit_census(index,out):
    census=dict(completed_case_fit_arms=4*len(index['cases']),
        completed_case_new_fit_arms=sum(r['new_fit_arms']for r in index['cases']),
        completed_case_reused_fit_arms=sum(r['reused_fit_arms']for r in index['cases']),
        completed_outcomes=5*len(index['cases']),partial_fit_checkpoint=None)
    partial=index['partial_case']
    if partial is not None:
        detail=dict(case_id=partial['case_id'],case_complete=False,recorded_fit_arms=None,recorded_completed_fit_arm_names=None,
            scope='Only fit records in the retained partial checkpoint; additional in-progress work remains in its trace and is not inferred complete.')
        try:
            path=frozen.safe(out,partial['file']);report=read(path);fits=report.get('fits',{})
            detail.update(checkpoint_sha256=sha(path),recorded_fit_arms=len(fits),
                recorded_completed_fit_arm_names=[name for name,fit in fits.items()if fit.get('passed')is True],
                recorded_incomplete_fit_arm_names=[name for name,fit in fits.items()if fit.get('passed')is not True])
        except (OSError,ValueError,KeyError,TypeError)as exc:
            detail.update(status='checkpoint_unavailable_or_unreadable',error=str(exc))
        census['partial_fit_checkpoint']=detail
    return census


def check_admission(args,op,current):
    a=read(args.admission);now=datetime.datetime.now(datetime.timezone.utc)
    require(a['independent_review_passed']is True and a['scheduler_review_passed']is True,'Unreviewed source/scheduler admission')
    require(a['source_sha256']==current['source_sha256']and a['operational_protocol_sha256']==current['operational_protocol_sha256'],'Admitted source/envelope changed')
    require(datetime.datetime.fromisoformat(a['expires_utc'])>now,'Expired numerical admission')
    token=os.environ.get('JOINT_NUMERICAL_LEASE_TOKEN','');require(token and hashlib.sha256(token.encode()).hexdigest()==a['lease_token_sha256'],'Numerical lease attestation mismatch')
    require(a['threads']==2 and a['workers']==1 and a['external_supervision']is True,'Numerical process/thread supervision differs')
    require(a['sampled_process_tree_rss_cap_bytes']==op['resources']['sampled_process_tree_rss_cap_bytes'],'Memory envelope differs')
    require(a['library_sha256']==current['library_sha256']and a['build_receipt_sha256']==current['build_receipt_sha256'],'Native/build admission differs')
    build=read(args.build_receipt)
    require(build['passed']is True and build['source_sha256']==sha(SCIENCE/'attenuation.cpp')and build['library_sha256']==current['library_sha256'],'Native source/build changed')
    require(isinstance(a['wall_seconds'],(int,float))and not isinstance(a['wall_seconds'],bool)and math.isfinite(a['wall_seconds'])and 0<a['wall_seconds']<=op['resources']['batch_wall_seconds'],'Batch wall exceeds frozen envelope')
    require(isinstance(a['numerical_attempt_id'],str)and a['numerical_attempt_id']and all(c.isalnum()or c=='-'for c in a['numerical_attempt_id']),'Invalid attempt identifier')
    return a


def run(args):
    started=time.monotonic();out=Path(args.output).resolve();require(not out.is_relative_to(REPO),'Output must be outside checkout')
    out.mkdir(parents=True,exist_ok=False);(out/'cases').mkdir();(out/'attempts').mkdir()
    result=dict(schema='joint_operational_batch_v1',passed=False,status='preflight',cases=[],scientific_completion=False)
    write(out/'result.json',result);index=None;admission=None;phase=None;active=None
    try:
        op,science=verify_protocol()
        current=dict(source_sha256=source_identity(),operational_protocol_sha256=sha(HERE/'operational_protocol.json'),runtime=frozen.runtime_identity(),library_sha256=sha(args.library),build_receipt_sha256=sha(args.build_receipt))
        result.update(current);admission=check_admission(args,op,current);result['admission_sha256']=sha(args.admission)
        cases=frozen.verify_inputs(science);lookup={c['case_id']:c for c in cases}
        index=accepted_index(args,admission,op,current,cases,out);requested=admission['case_ids'];phase=next_batch(index,op,requested)
        require(admission['phase']==phase,'Phase admission differs')
        require(admission['numerical_attempt_id']not in{r['attempt_id']for r in index['attempts']},'Attempt already charged')
        total,pilot=charged(index,op);resources=op['resources']
        allowance=min(resources['campaign_aggregate_seconds']-total,resources['pilot_aggregate_seconds']-pilot if phase=='pilot'else math.inf)
        require(admission['wall_seconds']<=allowance,'Aggregate allowance exhausted; no automatic cap increase')
        reservations=admission['case_reservations_seconds']
        require(set(reservations)==set(requested)and all(isinstance(v,(int,float))and not isinstance(v,bool)and math.isfinite(v)and v>0 for v in reservations.values())and math.fsum(reservations.values())<=admission['wall_seconds'],'Invalid pre-outcome case reservations')
        if phase=='campaign':
            projection=remaining_projection(cases,index,science,out);result['projection']=projection
            require(admission['pilot_projection_review_passed']is True and admission['projection_sha256']==identity(projection),'Unreviewed measured-pilot projection')
            require(projection['remaining_seconds']<=resources['campaign_aggregate_seconds']-total,'Projected remaining workload exceeds aggregate envelope')
            for name in requested:require(reservations[name]>=3*projection['maximum_seconds_per_work']*projection['work_by_case'][name],'Case reservation below frozen projection')
        deadline=min(started+admission['wall_seconds'],time.monotonic()+(datetime.datetime.fromisoformat(admission['expires_utc'])-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
        result.update(phase=phase,status='running',requested_cases=requested,prior_case_count=len(index['cases']),prior_charged_seconds=total)
        resume=None
        if not index['cases']:
            require(all(getattr(args,k,None)for k in('resume_training','resume_review','resume_archive')),'First case must reuse original frozen training')
            resume=frozen.load_training_resume(args,admission,current,out)
        else:require(not any(getattr(args,k,None)for k in('resume_training','resume_review','resume_archive')),'Original resume arguments supplied after first case')
        modules=model.archived();native=model.Native(args.library)
        with OrderedChunkScheduler()as scheduler:
            delegate=runner_with_scheduler(scheduler)
            for name in requested:
                require(deadline-time.monotonic()>=reservations[name],'Stop before a case whose reservation no longer fits')
                active=name;result['active_case']=name;write(out/'result.json',result)
                reuse=resume if resume and name==resume['case_id']else None
                report=delegate.case_run(lookup[name],modules,native,science,out/'cases',deadline,reuse)
                entry=dict(case_id=name,file='cases/'+name+'.json',sha256=sha(out/'cases'/(name+'.json')),
                    trace='cases/'+name+'.attempts.jsonl',trace_sha256=sha(out/'cases'/(name+'.attempts.jsonl')),
                    reused_fit_arms=4 if reuse else 0,new_fit_arms=0 if reuse else 4)
                if not report['passed']:
                    index['partial_case']=entry;require(False,'Failed partial case retained; independent disposition required before continuation')
                verify_case(report,entry,lookup[name]);index['cases'].append(entry);result['cases'].append(entry)
                active=None;result.pop('active_case',None);write(out/'result.json',result);gc.collect()
                print(checkpoint.dumps(dict(event='case_complete',case_id=name,complete_cases=len(index['cases']))),flush=True)
        require(time.monotonic()<deadline,'Batch completed after wall allowance')
        if len(index['cases'])==80:
            result.update(scientific_completion=True,summary_sha256=final_summary(index,science,out,deadline))
        result.update(passed=True,status='batch_complete',new_fit_arms=sum(r['new_fit_arms']for r in result['cases']),reused_fit_arms=sum(r['reused_fit_arms']for r in result['cases']))
    except BaseException as exc:
        result.update(passed=False,status='failed_requires_review',error_type=type(exc).__name__,error=str(exc))
    finally:
        elapsed=time.monotonic()-started;result['wall_seconds']=elapsed
        if index is not None and admission is not None and admission['numerical_attempt_id']not in{r['attempt_id']for r in index['attempts']}:
            if active and index['partial_case']is None:
                file=out/'cases'/(active+'.json');trace=out/'cases'/(active+'.attempts.jsonl')
                index['partial_case']=dict(case_id=active,file='cases/'+active+'.json',sha256=sha(file)if file.exists()else None,trace_sha256=sha(trace)if trace.exists()else None,status='interrupted_or_persistence_failure')
            phase=phase or('pilot'if len(index['cases'])<len(op['pilot'])else'campaign')
            receipt=dict(attempt_id=admission['numerical_attempt_id'],phase=phase,wall_seconds=elapsed,passed=result['passed'],status=result['status'],case_ids=[r['case_id']for r in result['cases']],partial_case=index['partial_case'],source_sha256=current['source_sha256'],admission_sha256=sha(args.admission),parent_index_sha256=sha(args.prior_index)if args.prior_index else None)
            relative='attempts/'+receipt['attempt_id']+'.json';write(out/relative,receipt)
            index['attempts'].append(dict(attempt_id=receipt['attempt_id'],phase=phase,seconds=elapsed,file=relative,sha256=sha(out/relative)))
            original=op['original_failure']['prior_scientific_seconds']
            index['budget']=dict(total_seconds=math.fsum([original,*[r['seconds']for r in index['attempts']]]),pilot_seconds=math.fsum([original,*[r['seconds']for r in index['attempts']if r['phase']=='pilot']]))
            write(out/'index.json',index);result.update(index_sha256=sha(out/'index.json'),complete_cases=len(index['cases']),budget=index['budget'],independent_index_review_required=True,
                **fit_census(index,out))
        else:result['unindexed_attempt_requires_conductor_accounting']=True
        write(out/'result.json',result)
    return 0 if result['passed']else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('admission','library','build-receipt','output'):parser.add_argument('--'+name,required=True)
    for name in('prior-index','prior-review','resume-training','resume-review','resume-archive'):parser.add_argument('--'+name)
    raise SystemExit(run(parser.parse_args()))
