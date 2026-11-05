"""Terminal saved-score analysis only; no history evaluator, simulation or fit.

Both statistics use the same fixed 999 reference identities, with independent
1000-case null checks and 150 alternatives. No in-sample calibration decisions.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import argparse, csv, io, math
from collections import Counter
import numpy as np
from scipy.stats import beta as beta_distribution
ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT/'iteration_17'
sys.path.insert(0,str(ROOT/'iteration_6/code'))
from checkpoint_io import read_json, read_sealed, sha256, canonical_hash, sealed_json, atomic_bytes, utc_now

FROZEN_PROTOCOL_SHA='dc3369af795b8116cea5a1d4603f365affe5111b0100639da1090af7e88cd754'
INVENTORY_PATH='iteration_17/results/inventory_20261016T120350054217Z.json'
INVENTORY_SHA='2d7ef9883147fa1d6bed60b007eecf5dd5b97ff16a4f11cfb75625be29fdad60'
EXPECTED_REFERENCE=[f'null_{r:04d}' for r in range(999)]
EXPECTED_CHECK=[f'null_{r:04d}' for r in range(999,1999)]
EXPECTED_ALTERNATIVE=[f'new_r{r:03d}' for r in range(150)]
EXPECTED_ALL=EXPECTED_REFERENCE+EXPECTED_CHECK+EXPECTED_ALTERNATIVE
RUNTIME_SOURCES={'iteration_17/code/oracle_likelihood.py','iteration_17/code/run_oracle.py',
                 'iteration_5/code/kernels.py','iteration_5/code/empirical_process.py',
                 'iteration_12/code/paired_history.py','iteration_6/code/checkpoint_io.py'}


def require(condition,message):
    if not condition:raise ValueError(message)


def score_pair(value,error=1e-6):
    require(math.isfinite(value) and math.isfinite(error) and error>=0,'Nonfinite score or invalid numerical envelope')
    return float(value),max(1e-6,float(error))


def classify(query,references):
    """Exact point ties plus the frozen numerical-sensitivity classification."""
    if len(references)!=999 or any(v is None for v in references):
        return dict(rank=None,rank_sensitivity_range=None,reject=None,reason='incomplete_reference_bank')
    if query is None:
        return dict(rank=None,rank_sensitivity_range=None,reject=None,reason='unresolved_query')
    value,error=score_pair(*query)
    refs=[score_pair(*v) for v in references]
    k=sum(v>=value for v,e in refs)
    lower=sum(v-e>=value+error for v,e in refs)
    upper=sum(v+e>=value-error for v,e in refs)
    require(0<=lower<=k<=upper<=999,'Invalid comparison envelope')
    lo,hi=(1+lower)/1000,(1+upper)/1000
    reject=True if hi<=.05 else False if lo>.05 else None
    return dict(rank=(1+k)/1000,rank_sensitivity_range=[lo,hi],reject=reject,
                reason='stable_reject' if reject is True else 'stable_nonreject' if reject is False else 'ordering_sensitive')


def tally(decisions):
    n=len(decisions)
    require(n>0 and all(v is None or type(v) is bool for v in decisions),'Invalid binary/unknown cohort')
    k=sum(v is True for v in decisions);u=sum(v is None for v in decisions)
    result=dict(requested=n,rejections=k,resolved=n-u,unknown=u,conditional_frequency=None,
                monte_carlo_se=None,exact_binomial_95_interval=None,accounting_bounds=[k/n,(k+u)/n])
    if not u:
        p=k/n
        result.update(conditional_frequency=p,monte_carlo_se=math.sqrt(p*(1-p)/n),
            exact_binomial_95_interval=[0. if not k else float(beta_distribution.ppf(.025,k,n-k+1)),
                                       1. if k==n else float(beta_distribution.ppf(.975,k+1,n-k))])
    return result


def paired(pairs):
    require(bool(pairs),'Empty paired cohort')
    table=dict(neither=0,fitted_only=0,oracle_only=0,both=0,unknown=0)
    values=[];bounds=[]
    for oracle,fitted in pairs:
        require(all(v is None or type(v) is bool for v in (oracle,fitted)),'Invalid paired decision')
        bounds.append([(int(oracle) if oracle is not None else 0)-(int(fitted) if fitted is not None else 1),
                       (int(oracle) if oracle is not None else 1)-(int(fitted) if fitted is not None else 0)])
        if oracle is None or fitted is None:table['unknown']+=1
        else:
            table['both' if oracle and fitted else 'oracle_only' if oracle else 'fitted_only' if fitted else 'neither']+=1
            values.append(int(oracle)-int(fitted))
    n=len(pairs);complete=not table['unknown']
    return dict(requested=n,complete=complete,table=table,oracle_minus_fitted=float(np.mean(values)) if complete else None,
                descriptive_MCSE=float(np.std(values,ddof=1)/math.sqrt(n)) if complete and n>1 else None,
                accounting_bounds=[sum(v[i] for v in bounds)/n for i in (0,1)])


def validate_protocol(protocol):
    require(protocol['status']=='frozen_scientific_rules_before_new_oracle_outcomes' and
            protocol['protocol_id']=='iteration17_primary_adjusted_eta','Unfrozen or different protocol')
    p=protocol['phase1'];c=p['cohorts'];law=p['law'];cal=p['calibration']
    require(c['reference_null_ids']==EXPECTED_REFERENCE and c['heldout_check_null_ids']==EXPECTED_CHECK and
            c['alternative_ids']==EXPECTED_ALTERNATIVE and c['maximum_histories_scored']==2149,'Fixed cohorts differ')
    require(cal['B']==999 and cal['check_N']==1000 and cal['alternative_N']==150 and
            cal['reject_rank_le']==.05 and cal['maximum_reference_exceedances_for_rejection']==49,'Calibration differs')
    require(law['alternative_eta']==.4885010300470942 and law['beta']==2.849401764894274 and
            law['horizon_days']==law['coordinate_horizon_days']==24394. and law['empty_initial_history'] is True and
            law['same_mark_density'] is True and law['marks_not_refitted'] is True,'Primary simple laws differ')
    return p


def interpretation(methods,comparison):
    size_ok={}
    for name in ('oracle','fitted'):
        s=methods[name]['heldout_null_size'];ci=s['exact_binomial_95_interval'];q=s['conditional_frequency']
        size_ok[name]=None if q is None else bool(.025<=q<=.075 and ci[0]<=.05<=ci[1])
    sizes=[methods[n]['heldout_null_size']['conditional_frequency'] for n in ('oracle','fitted')]
    gap=None if any(v is None for v in sizes) else abs(sizes[0]-sizes[1])
    p=methods['oracle']['alternative_power'];ci=p['exact_binomial_95_interval'];gain=comparison['alternative_power']
    low=None if ci is None else bool(ci[1]<.50)
    ready=ci is not None and gain['complete'] and all(v is True for v in size_ok.values()) and gap<=.02
    strong=None if not ready else bool(ci[0]>.80 and gain['oracle_minus_fitted']>=.20 and
                                       gain['oracle_minus_fitted']>=2*gain['descriptive_MCSE'])
    return dict(size_screen_passed=size_ok,absolute_size_point_gap=gap,
                equal_size_warning=None if gap is None else bool(gap>.02),low_oracle_flag=low,
                strong_pipeline_loss_flag=strong,
                scope='Frozen descriptive flags; otherwise intermediate/unresolved. No nuisance-block attribution or rigorous optimal-power bound.')


def analyse_values(protocol,oracle_values,fitted_values):
    """Pure arithmetic; missing cases remain None in the full fixed cohorts."""
    validate_protocol(protocol)
    allowed=set(EXPECTED_ALL)
    require(set(oracle_values).issubset(allowed) and set(fitted_values)==allowed,'Unplanned/duplicate/missing fitted identities')
    methods={};outcomes={id:dict(id=id) for id in EXPECTED_CHECK+EXPECTED_ALTERNATIVE}
    for name,values in [('oracle',oracle_values),('fitted',fitted_values)]:
        refs=[values.get(id) for id in EXPECTED_REFERENCE]
        reference_complete=all(v is not None for v in refs)
        decisions={}
        for id in outcomes:
            decision=classify(values.get(id),refs);outcomes[id][name]=decision;decisions[id]=decision['reject']
        methods[name]=dict(reference_requested=999,reference_complete=reference_complete,
            reference_resolved=sum(v is not None for v in refs),
            heldout_null_size=tally([decisions[id] for id in EXPECTED_CHECK]),
            alternative_power=tally([decisions[id] for id in EXPECTED_ALTERNATIVE]))
    comparison={name:paired([(outcomes[id]['oracle']['reject'],outcomes[id]['fitted']['reject']) for id in ids])
                for name,ids in [('heldout_null_size',EXPECTED_CHECK),('alternative_power',EXPECTED_ALTERNATIVE)]}
    return dict(methods=methods,paired=comparison,interpretation=interpretation(methods,comparison),
                outcomes=list(outcomes.values()),scope='Conditional on realized999-reference banks, fixed generating law and accepted numerical conventions; not plug-in-bootstrap power or modeltruth')


def load_fitted(entry):
    ref=entry['files']['validation.json'];path=ROOT/ref['path']
    require(sha256(path)==ref['sha256'],'Saved fitted validation bytes changed')
    v=read_sealed(path)
    require(v['complete'] and v['passed'] and v['id']==entry['id'] and v['seed']==entry['seed'],'Invalid fitted validation authority')
    require(v['fit_sha256']==entry['files']['fit.json']['sha256'] and
            v['catalogue_sha256']==entry['files']['catalogue.npz']['sha256'],'Fitted chain differs')
    require(sha256(ROOT/entry['files']['fit.json']['path'])==v['fit_sha256'],'Saved fitted result bytes changed')
    ds=v['deltas'];require(all(math.isfinite(x) and abs(x)<1e-4 for x in ds.values()),'Saved CPU32 gate differs')
    return score_pair(v['statistics']['feedback'],2*(abs(ds['ml_null'])+abs(ds['ml_separate_scale'])))


def load_oracle(record,entry,plan_id):
    require(record['plan_id']==plan_id and record['id']==entry['id'] and record['seed']==entry['seed'] and
            record['catalogue_sha256']==entry['files']['catalogue.npz']['sha256'] and
            record['clock_mode']==entry['clock_mode'] and record['role']==entry['role'] and
            record['arm']==entry.get('arm') and record['replication']==entry['replication'] and
            record['inventory_entry_sha256']==canonical_hash(entry),'Oracle input identity/clock differs')
    if record['status']!='complete':return None
    p=record['payload'];r=p['result'];order=p['selected_order'];values=p['evaluations']
    require(p['complete'] and p['refinement_passed'] and p['tolerance']==1e-6 and order in (32,64),'Unaccepted oracle refinement')
    require(r==values[str(order)] and r['order']==order and r['eta']==.4885010300470942 and
            r['beta_fixed']==2.849401764894274 and r['clock_mode']==entry['clock_mode'] and
            r['n_events']==entry['n_events'],'Oracle fixed law or selected order differs')
    initial=abs(values['32']['log_lr']-values['16']['log_lr'])
    require(initial==p['initial_16_32_difference'],'Initial refinement evidence differs')
    require((order==64)==(initial>1e-6),'Unprescribed order64 selection')
    delta=abs(values[str(order)]['log_lr']-values['32' if order==64 else '16']['log_lr'])
    require(delta==p['selected_refinement_difference'] and delta<=1e-6 and
            record['log_lr']==r['log_lr'] and record['refinement_error']==delta,'Refinement delta differs')
    # Individual large NLL totals may lose a small LR on subtraction. The
    # independent subtraction control belongs to non-extreme validation
    # fixtures; it is not a new cancellation-based acceptance gate here.
    require(math.isfinite(r['nll0']) and math.isfinite(r['nll1']),'Nonfinite auxiliary likelihood')
    return score_pair(r['log_lr'],delta)


def validate_terminal(plan,terminal,sessions,index):
    """No score inspection until the complete planned cohort is terminal."""
    require(terminal['plan_id']==plan['plan_id'] and terminal['sessions_closed'] is True and
            terminal['active_ids']==[] and terminal['active'] is False and sessions and
            all(s['closed'] is True and not s.get('active_ids') for s in sessions),
            'Active oracle run; terminal analysis refused')
    states=index['states']
    require(index['plan_id']==plan['plan_id'] and set(states)==set(EXPECTED_ALL) and
            dict(Counter(states.values()))==terminal['counts'] and terminal['total_planned']==2149,
            'Terminal identities/counts differ')
    allowed={'complete','refinement_failed','time_cap','error','interrupted'}
    require(all(s in allowed for s in states.values()) or
            (terminal['reason']=='global_budget' and all(s in allowed|{'pending'} for s in states.values())),
            'Resumable selected prefix is not a terminal experiment')
    require(terminal['reason'] in ('selected_complete','global_budget','stop_requested') and
            terminal['charged_seconds']==sum(s['elapsed_seconds'] for s in sessions),'Terminal budget authority differs')
    return states


def collect(run):
    """Runner authority adapter: terminal metadata must precede any statistics."""
    run=Path(run).resolve();require(run.is_relative_to(AREA/'results'),'Output path outside iteration17')
    protocol_path=AREA/'configs/phase1_frozen.json'
    require(sha256(protocol_path)==FROZEN_PROTOCOL_SHA and sha256(ROOT/INVENTORY_PATH)==INVENTORY_SHA,'Frozen scientific authority changed')
    protocol=read_json(protocol_path);validate_protocol(protocol)
    plan=read_sealed(run/'plan.json');terminal=read_sealed(run/'summary.json')
    sessions=read_sealed(run/'sessions.json')['sessions']
    index=read_sealed(run/'case_index.json');states=validate_terminal(plan,terminal,sessions,index)
    require(plan['protocol_sha256']==FROZEN_PROTOCOL_SHA and plan['protocol']==protocol and
            plan['inventory_sha256']==INVENTORY_SHA and plan['ids']==EXPECTED_ALL and
            plan['resources']==protocol['phase1']['resources'],'Runner science authority differs')
    plan_keys=('schema_version','protocol','protocol_path','protocol_sha256','inventory_path','inventory_sha256',
               'sources','ids','entries','resources')
    require(canonical_hash({k:plan[k] for k in plan_keys})==plan['plan_id'] and
            set(plan['sources'])==RUNTIME_SOURCES,'Canonical runner or source inventory differs')
    for name,digest in plan['sources'].items():require(sha256(ROOT/name)==digest,'Pinned source changed')
    inventory=read_sealed(ROOT/INVENTORY_PATH)
    entries={e['id']:e for e in inventory['entries']}
    require(len(entries)==2299 and all(id in entries for id in EXPECTED_ALL),'Inventory identity quota differs')
    require(plan['entries']==[entries[id] for id in EXPECTED_ALL],'Prepared inventory entries differ')
    require(len({entries[id]['seed'] for id in EXPECTED_ALL})==2149,'Seed duplication across primary cohorts')
    oracle={};fitted={};score_hashes={}
    for id in EXPECTED_ALL:
        entry=entries[id];path=run/'cases'/f'{id}.json'
        require(sha256(ROOT/entry['files']['catalogue.npz']['path'])==entry['files']['catalogue.npz']['sha256'],
                'Authoritative catalogue bytes changed')
        if path.exists():
            record=read_sealed(path);require(record['status']==states[id],'Terminal score status differs')
            oracle[id]=load_oracle(record,entry,plan['plan_id']);score_hashes[id]=sha256(path)
        else:
            require(states[id] in ('pending','time_cap'),'Missing committed score')
            oracle[id]=None
        fitted[id]=load_fitted(entry)
    result=analyse_values(protocol,oracle,fitted)
    result.update(created_utc=utc_now(),plan_id=plan['plan_id'],protocol_sha256=FROZEN_PROTOCOL_SHA,
                  inventory_sha256=INVENTORY_SHA,runner_summary_sha256=sha256(run/'summary.json'),
                  score_file_sha256=score_hashes,summarizer_sha256=sha256(Path(__file__)),
                  scored_complete=sum(v is not None for v in oracle.values()),planned=2149,
                  charged_seconds=terminal['charged_seconds'],
                  budget_overrun_seconds=max(0.,terminal['charged_seconds']-plan['resources']['total_scientific_wall_seconds']))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,default=AREA/'results/oracle_primary');args=p.parse_args()
    result=collect(args.run_dir);out=AREA/'results/analysis'/utc_now().replace(':','').replace('.','').replace('+','_')
    out.mkdir(parents=True,exist_ok=False);sealed_json(out/'summary.json',result)
    stream=io.StringIO(newline='');fields=['id','oracle_rank','oracle_reject','oracle_reason','fitted_rank','fitted_reject','fitted_reason']
    writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    for r in result['outcomes']:
        writer.writerow(dict(id=r['id'],**{f'{n}_{k}':r[n][k] for n in ('oracle','fitted') for k in ('rank','reject','reason')}))
    atomic_bytes(out/'outcomes.csv',stream.getvalue().encode());print(out)
    return 0 if all(result['methods'][n][c]['unknown']==0 for n in ('oracle','fitted') for c in ('alternative_power','heldout_null_size')) else 2


if __name__=='__main__':raise SystemExit(main())
