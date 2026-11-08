"""Private metadata facade of the frozen host loop; scientific children are unchanged."""
import argparse
import builtins
import copy
from decimal import Decimal
from pathlib import Path
import sys
import types
from . import (REPO,INDEX_SCHEMA,read,sha,require,safe,resolve,source_identity,
               verify_protocol,operational_reference)
from . import transition
from experiments.s04b_exposure_refinement import host as frozen
from experiments.s04b_joint_remaining import host as generic


def live(review,kind='live_agent_saved_output_review'):
    require(review.get('passed') is True and review.get('audit_passed') is True
        and review.get('review_kind')==kind and review.get('live_agent_review') is True
        and review.get('live_agent_review_performed',True) is True
        and review.get('final_batch_agent_review_required') is False,'Genuine live predecessor review required')


def sealed_predecessor(p,refs,index,review):
    require(set(refs)=={'index','review','raw_archive','raw_review','raw_index_member','raw_index_sha256'},'Sealed predecessor fields differ')
    require(refs['raw_archive']==p['base']['archive'] and refs['raw_review']==p['base']['review']
        and refs['raw_index_member']==p['base']['index_member'] and refs['raw_index_sha256']==p['base']['index_sha256'],'Raw55 identity differs')
    for key in ('index','review','raw_archive','raw_review'):resolve(refs[key])
    require(read(resolve(refs['index']))==index and read(resolve(refs['review']))==review,'Separate sealed56 bytes differ')
    live(review,'live_operational_failure_transition_review')
    require('execution_id' not in review and review.get('failure_accounting_valid') is True
        and review.get('scientific_execution_passed') is False and review.get('scientific_completion') is False
        and review['index_sha256']==refs['index']['sha256'] and review['operational_continuation']==operational_reference()
        and review['raw_archive']==p['base']['archive'] and review['raw_review']==p['base']['review']
        and review['raw_index_sha256']==p['base']['index_sha256'],'Transition must not relabel the failed execution')


def prior_overhead(p,a,review):
    row=a.get('prior_host_overhead')
    if a['batch_id']==5:
        require(row is None,'Host04 overhead is already in sealed baseline');return None
    require(isinstance(row,dict) and set(row)=={'execution_id','seconds','review','archive'},'Audited preceding overhead required')
    require(row['review']['sha256']==a['prior_review_sha256'] and row['archive']['sha256']==a['prior_archive_sha256']
        and read(resolve(row['review']))==review,'Overhead evidence differs')
    resolve(row['archive'])
    require(row['execution_id']==review['execution_id']
        and str(row['seconds'])==str(review['resource']['whole_workflow_overhead_beyond_all_child_outer_seconds']), 'Overhead differs from live workflow audit')
    value=Decimal(str(row['seconds']));require(value.is_finite() and 0<=value<=1800,'Host overhead exceeded reservation')
    return copy.deepcopy(row)


def validate_prefix(p,index):
    base=transition.build_sealed(p,*transition.base_evidence(p))
    require(index['schema']==INDEX_SCHEMA and index['operational_continuation']==operational_reference()
        and index['records'][:56]==base['records'] and index['attempts'][:12]==base['attempts'], 'Immutable sealed prefix changed')
    require(index['counts']==transition.counts(index['records'])
        and index['budget']==transition.budget(p,index['attempts'],index['audited_host_overheads']), 'Prior counts/budget differ')


def next_cases(old,a,index,review):
    p=verify_protocol();number=a['batch_id']
    require(type(number) is int and 5<=number<=8,'Only original untouched hosts5-8 are admitted')
    group=p['hosts'][number-5];expected=56+sum(len(g['case_ids']) for g in p['hosts'][:number-5])
    require(a.get('operational_mode')=='wall_failure_continuation' and a['operational_continuation']==operational_reference(), 'Operational identity missing')
    require(a['case_ids']==group['case_ids'] and set(a['child_attempt_ids'])==set(group['case_ids'])
        and len(set(a['child_attempt_ids'].values()))==len(group['case_ids']), 'Fixed host case/attempt roster differs')
    require(len(index['records'])==expected and [r['case_id'] for r in index['records']]==p['full_sequence'][:expected], 'Wrong exact host prefix')
    validate_prefix(p,index)
    require(index['scientific_source_sha256']==a['scientific_source_sha256']==p['core_source_sha256']
        and index['host_source_sha256']==a['source_sha256']==source_identity()
        and index['protocol_sha256']==a['protocol_sha256']==p['numerical_protocol']['sha256'], 'Actual host/core identities differ')
    if number==5:
        sealed_predecessor(p,a['sealed_predecessor'],index,review)
        require(a['prior_index_sha256']==a['sealed_predecessor']['index']['sha256']
            and a['prior_review_sha256']==a['sealed_predecessor']['review']['sha256']
            and a['prior_archive_sha256']==p['base']['archive']['sha256'], 'Initial separate index/archive pins differ')
    else:
        require(a.get('sealed_predecessor') is None,'Later host must use actual prior host index')
        live(review)
        require(review.get('disposition_valid') is True and review.get('scientific_completion') is False
            and review['index_sha256']==a['prior_index_sha256'] and review['artifact_sha256']==a['prior_archive_sha256'], 'Prior live archive/index differs')
    row=prior_overhead(p,a,review)
    require(row is None or row['execution_id'] not in {r['execution_id'] for r in index['audited_host_overheads']}, 'Preceding overhead already charged')
    return group


def check_source_reviews(a,old,source_path,checker_path):
    p=verify_protocol();require(sha(source_path)==a['source_review_sha256'] and sha(checker_path)==a['checker_source_review_sha256'],'Review bytes differ')
    source,checker=read(source_path),read(checker_path)
    for r in (source,checker):
        require(r.get('passed') is True and r.get('live_agent_review') is True
            and r.get('live_agent_review_performed',True) is True and r.get('final_batch_agent_review_required',False) is False,'Independent source review required')
    pins={name:sha(safe(REPO,name)) for name in p['checker']['sources']}
    for name,pin in source_identity().items():require(source['reviewed_files_sha256'].get(name)==pin,'Unreviewed producer: '+name)
    for name,pin in pins.items():require(checker['reviewed_files_sha256'].get(name)==pin,'Unreviewed checker: '+name)
    for name,pin in {**source_identity(),**pins}.items():require(a['reviewed_files_sha256'].get(name)==pin,'Omitted admitted source')
    for name,pin in a['reviewed_files_sha256'].items():require(sha(safe(REPO,name))==pin,'Changed admitted source')
    return pins


def append_candidate(old,a,previous,current,out,prior_index,prior_review,projection):
    # The original append performs all ordinary result/report/native/source checks.
    namespace=dict(frozen.__dict__,counts=transition.counts,budget=lambda p,rows:None)
    append=types.FunctionType(frozen.append_candidate.__code__,namespace)
    value=append(old,a,previous,current,out,prior_index,prior_review,projection)
    p=verify_protocol();local=Path(prior_index).resolve().is_relative_to(Path(out).resolve())
    overheads=copy.deepcopy(previous['audited_host_overheads'])
    if not local:
        overhead=prior_overhead(p,a,read(prior_review))
        if overhead is not None:overheads.append(overhead)
    value.update(schema=INDEX_SCHEMA,operational_continuation=operational_reference(),audited_host_overheads=overheads,
        budget=transition.budget(p,value['attempts'],overheads))
    if not local and a['batch_id']==5:
        value['predecessor']=dict(kind='sealed_failure_transition',index_sha256=sha(prior_index),review_sha256=sha(prior_review),
            archive_sha256=None,index=a['sealed_predecessor']['index'],review=a['sealed_predecessor']['review'],raw_failure_archive=p['base']['archive'])
    return value


def supervised(command,output,cap,admission,environment,spec_path):
    if command[:4]==[sys.executable,'-B','-m','experiments.s04b_exposure_refinement.case_driver']:
        require(command[4:6]==['--mode','untouched'],'No resume or failed-case retry')
    elif command[:4]==[sys.executable,'-B','-m','experiments.s04b_exposure_refinement_audit.check']:
        command=command.copy();command[3]=verify_protocol()['checker']['module']
    else:raise ValueError('Unrecognized frozen host dispatch')
    return generic.supervised(command,output,cap,admission,environment,spec_path)


def facade():
    namespace=dict(frozen.__dict__);original_import=builtins.__import__
    def private_import(name,globals=None,locals=None,fromlist=(),level=0):
        if name=='experiments.s04b_joint_remaining.host' and level==0 and tuple(fromlist)==('supervised','projection'):
            return types.SimpleNamespace(supervised=supervised,projection=generic.projection)
        return original_import(name,globals,locals,fromlist,level)
    namespace['__builtins__']=dict(vars(builtins),__import__=private_import)
    for name in ('source_identity','next_cases','check_source_reviews','append_candidate'):
        namespace[name]=globals()[name]
    return types.FunctionType(frozen.run.__code__,namespace,'run_wall_failure_continuation')


def run(args):
    code=facade()(args);path=Path(args.output)/'result.json';result=read(path)
    result.update(schema='joint_wall_failure_continuation_host_v1',operational_continuation=operational_reference(),
        scientific_completion=False,retained_wall_time_failure=True,
        execution_scope='Expanded operational host; unchanged numerical child and original fixed groups')
    frozen.write(path,result);return code


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('admission','output','prior-index','prior-review','config','source-review','checker-review','library','build-receipt'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--failed-prior',type=Path)
    return run(parser.parse_args())


if __name__=='__main__':raise SystemExit(main())
