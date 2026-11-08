"""Seal one audited wall failure as metadata; this command never authorizes a fit."""
import argparse
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import zipfile
from . import (INDEX_SCHEMA, FAILURE, read, sha, require, resolve, write_new,
               verify_protocol, source_identity, operational_reference)


def counts(records):
    kinds=[r['disposition'] for r in records]
    require(all(k in ('complete','scientific_unknown','wall_time_failure') for k in kinds), 'Undisposed record')
    failed=[r for r in records if r['disposition']=='wall_time_failure']
    require(len(failed)==1 and failed[0]['case_id']==FAILURE and failed[0]['scientific_passed'] is False
            and failed[0]['outcomes']==[], 'Only the pinned wall failure is permitted')
    complete=kinds.count('complete');unknown=kinds.count('scientific_unknown')
    return dict(processed_histories=len(records),complete_histories=complete,unknown_histories=unknown,
        wall_time_failure_histories=1,unattempted_histories=80-len(records),computed_outcomes=5*complete)


def base_evidence(p):
    audit=read(resolve(p['base']['review']))
    with zipfile.ZipFile(resolve(p['base']['archive'])) as archive:
        require(len(archive.namelist())==len(set(archive.namelist())), 'Duplicate archive member')
        def member(name,pin):
            data=archive.read(name);require(hashlib.sha256(data).hexdigest()==pin,'Pinned member changed: '+name)
            return json.loads(data)
        index=member(p['base']['index_member'],p['base']['index_sha256'])
        values={key:member(p['failure'][key+'_member'],p['failure'][key+'_sha256'])
                for key in ('case','result','supervision')}
        trace=archive.read(p['failure']['trace_member'])
        require(hashlib.sha256(trace).hexdigest()==p['failure']['trace_sha256'],'Failure trace changed')
    return index,values['case'],values['result'],values['supervision'],audit


def failure_projection(p,case,result,supervision,audit):
    f=p['failure'];census=audit['failure']
    require(case['case_id']==result['case_id']==census['case_id']==FAILURE
        and case['passed'] is False and case['error_type']=='TimeoutError'
        and case['error']=='Joint experiment deadline' and case['outcomes']==[], 'Not the audited scientific wall failure')
    require(result['disposition']=='technical_failure' and result['handled'] is False
        and result['disposition_valid'] is False and result['scientific_passed'] is False
        and result['passed'] is False and result['error_type']=='ValueError'
        and result['error']=='Case optimizer records differ from trace'
        and result['scientific_clock_cap_exceeded'] is True, 'Raw technical failure changed')
    require(census==f['failure_census'] and census['held_out_calls']==0
        and census['new_outcomes_available']==0, 'Failure census differs')
    require(str(result['wall_seconds'])==p['accounting']['failure_scientific_seconds']
        and str(supervision['wall_seconds_including_cleanup'])==p['accounting']['failure_outer_seconds'], 'Failure clocks differ')
    source=dict(kind='host_execution',execution_id=f['execution_id'])
    for key in ('case','trace','result','supervision'):
        require(f[key+'_member'].startswith('host/'),'Failure member outside host')
        source[key+'_path']=f[key+'_member'][5:];source[key+'_sha256']=f[key+'_sha256']
    row={key:copy.deepcopy(case[key]) for key in ('case_id','regime','seed','input_sha256','n_train','n_test','stratum','thinning','fixed_spatial_mark_law','historical_comparisons')}
    row.update(disposition='wall_time_failure',scientific_passed=False,outcomes=[],source=source,
        reason_code='scientific_wall_limit',failure_review=copy.deepcopy(p['base']['review']),
        raw_case_status=case['status'],raw_result_disposition=result['disposition'],
        primary_error=dict(type=case['error_type'],message=case['error']),
        secondary_error=dict(type=result['error_type'],message=result['error']),
        allocation=copy.deepcopy(result['allocation']),failure_census=copy.deepcopy(census),
        numerical_amendment=copy.deepcopy(result['numerical_amendment']))
    attempt=dict(case_id=FAILURE,numerical_attempt_id=result['numerical_attempt_id'],host_execution_id=f['execution_id'],
        seconds=result['wall_seconds'],outer_seconds=supervision['wall_seconds_including_cleanup'],
        result_sha256=f['result_sha256'],supervision_sha256=f['supervision_sha256'],
        actual_optimizer_attempts=result['actual_optimizer_attempts'],reused_optimizer_attempts=result['reused_optimizer_attempts'])
    require(attempt['actual_optimizer_attempts']==29 and attempt['reused_optimizer_attempts']==0,'Failed attempt census differs')
    return row,attempt


def budget(p,attempts,audited_host_overheads=()):
    """Known all-wall baseline plus new outer durations; nested science is diagnostic."""
    require([r['case_id'] for r in attempts]==p['full_sequence'][44:44+len(attempts)]
        and len(attempts)>=12,'Attempt prefix differs')
    suffix=attempts[12:];slots=p['case_slots']
    require([r['case_id'] for r in suffix]==p['case_ids'][:len(suffix)],'Future attempt roster differs')
    for row,slot in zip(suffix,slots):
        outer=Decimal(str(row['outer_seconds']));science=Decimal(str(row['seconds']))
        require(outer.is_finite() and science.is_finite() and 0<=outer<=slot['wall_seconds']
            and 0<=science<=slot['scientific_seconds'], 'Future child exceeded unchanged cap')
    ids=[r['execution_id'] for r in audited_host_overheads]
    require(len(ids)==len(set(ids)) and p['failure']['execution_id'] not in ids, 'Duplicated host overhead')
    overhead=Decimal(0)
    for row in audited_host_overheads:
        value=Decimal(str(row['seconds']))
        require(value.is_finite() and 0<=value<=1800 and set(row)=={'execution_id','seconds','review','archive'},'Invalid audited overhead')
        overhead+=value
    a=p['accounting'];baseline=Decimal(a['sealed_known_seconds']);reserve=Decimal(a['unconsumed_host_overhead_reserve_seconds'])-overhead
    outer=sum((Decimal(str(r['outer_seconds'])) for r in suffix),Decimal(0))
    science=sum((Decimal(str(r['seconds'])) for r in suffix),Decimal(0))
    remaining=sum(r['wall_seconds'] for r in slots[len(suffix):]);accounted=baseline+outer+overhead
    upper=accounted+remaining+reserve+a['global_finalization_reserve_seconds']
    require(reserve>=0 and upper<=a['global_cap_seconds'],'Global unchanged allocation exceeded')
    return dict(sealed_known_seconds=str(baseline),future_scientific_seconds=str(science),future_outer_seconds=str(outer),
        audited_future_host_overhead_seconds=str(overhead),accounted_seconds=str(accounted),
        remaining_case_slots_seconds=remaining,unconsumed_host_overhead_reserve_seconds=str(reserve),
        global_finalization_reserve_seconds=a['global_finalization_reserve_seconds'],upper_bound_seconds=str(upper),
        remaining_headroom_seconds=str(Decimal(a['global_cap_seconds'])-upper),historical_unmeasured_setup_caveat=True)


def build_sealed(p,index,case,result,supervision,audit):
    require(len(index['records'])==55 and [r['case_id'] for r in index['records']]==p['full_sequence'][:55]
        and len(index['attempts'])==11 and index['scientific_source_sha256']==p['core_source_sha256'], 'Wrong raw prefix')
    row,attempt=failure_projection(p,case,result,supervision,audit)
    sealed=copy.deepcopy(index)
    sealed.update(schema=INDEX_SCHEMA,operational_continuation=operational_reference(),
        host_source_sha256=source_identity(),records=sealed['records']+[row],attempts=sealed['attempts']+[attempt],
        audited_host_overheads=[],passed=False,scientific_completion=False,
        predecessor=dict(kind='audited_wall_failure_transition',raw_archive=p['base']['archive'],
            raw_review=p['base']['review'],raw_index_member=p['base']['index_member'],raw_index_sha256=p['base']['index_sha256']))
    sealed['counts']=counts(sealed['records']);sealed['budget']=budget(p,sealed['attempts'])
    require(sealed['counts']==dict(processed_histories=56,complete_histories=54,unknown_histories=1,
        wall_time_failure_histories=1,unattempted_histories=24,computed_outcomes=270),'Sealed census differs')
    return sealed


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();p=verify_protocol();require(not args.output.exists(),'Fresh seal directory required')
    sealed=build_sealed(p,*base_evidence(p));args.output.mkdir(parents=True)
    write_new(args.output/'index.json',sealed)
    write_new(args.output/'result.json',dict(schema='joint_wall_failure_seal_v1',failure_accounting_valid=True,
        scientific_execution_passed=False,scientific_completion=False,live_agent_review=False,independent_transition_review_required=True,
        operational_continuation=operational_reference(),index_sha256=sha(args.output/'index.json'),
        raw_archive=p['base']['archive'],raw_review=p['base']['review'],raw_index_sha256=p['base']['index_sha256'],
        counts=sealed['counts'],budget=sealed['budget'],source_sha256=source_identity()))


if __name__=='__main__':main()
