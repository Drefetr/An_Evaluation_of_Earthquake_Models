"""Invented resource counterexamples only; no actual cohort or scientific calls."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
import importlib.util,json,hashlib
P=Path(r'C:/Users/Drefetr/work/joint_replay_continuation_20261107T071500Z/joint_final_disposition_independent_audit/revision_02/audit_saved.py')
s=importlib.util.spec_from_file_location('independent_candidate',P);A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
seq=['invented_'+str(i) for i in range(80)]
old={'execution_id':'old-host','seconds':'3','review':{'path':'validation/old_review.json','sha256':'a'*64},'archive':{'path':'validation/old.zip','sha256':'b'*64}}
final={'execution_id':'last-host','resource':{'whole_workflow_overhead_beyond_all_child_outer_seconds':'4'}}
index=dict(records=[{'case_id':key,'source':{'execution_id':'base' if pos<56 else 'old-host' if pos<68 else 'last-host'}} for pos,key in enumerate(seq)],audited_host_overheads=[old],attempts=[dict(case_id=k,numerical_attempt_id='id'+str(i),seconds=1,outer_seconds=2,reused_optimizer_attempts=0) for i,k in enumerate(seq[44:])])
# Metadata counterpart of the independently loaded raw objects. Preserve them
# while perturbing index rows in the two original counterexamples.
physical={}
for position,r in enumerate(index['attempts'],44):
    source=index['records'][position]['source']
    source.update(kind='host_execution',result_sha256='e'*64,supervision_sha256='f'*64)
    if position==44:r.update(seconds=7.25,outer_seconds=7.75)
    if position==55:r.update(seconds=2490.027,outer_seconds=2490.578)
    result=dict(case_id=r['case_id'],numerical_attempt_id=r['numerical_attempt_id'],wall_seconds=r['seconds'],actual_optimizer_attempts=4 if position==44 else 29 if position==55 else 32,reused_optimizer_attempts=28 if position==44 else 0)
    r.update(host_execution_id=source['execution_id'],result_sha256=source['result_sha256'],supervision_sha256=source['supervision_sha256'],actual_optimizer_attempts=result['actual_optimizer_attempts'],reused_optimizer_attempts=result['reused_optimizer_attempts'])
    physical[r['case_id']]=dict(source=deepcopy(source),result=result,supervision=dict(wall_seconds_including_cleanup=r['outer_seconds']))
op=dict(full_sequence=seq,case_slots=[dict(scientific_seconds=2,wall_seconds=3)]*24,failure={'execution_id':'failed-host'},accounting=dict(sealed_known_seconds='100',unconsumed_host_overhead_reserve_seconds='20',global_finalization_reserve_seconds=1800,global_cap_seconds=115200))
entries={'old-host':(old,{'resource':{'whole_workflow_overhead_beyond_all_child_outer_seconds':'3'}})}
class Pins:pins={'validation/final_review.json':'d'*64}
def refresh(i):
 overhead=sum((Decimal(r['seconds']) for r in i['audited_host_overheads']),Decimal(0));science=sum((Decimal(str(r['seconds'])) for r in i['attempts'][12:]),Decimal(0));outer=sum((Decimal(str(r['outer_seconds'])) for r in i['attempts'][12:]),Decimal(0));reserve=20-overhead;accounted=100+outer+overhead;upper=accounted+reserve+1800
 i['budget']=dict(sealed_known_seconds='100',future_scientific_seconds=str(science),future_outer_seconds=str(outer),audited_future_host_overhead_seconds=str(overhead),accounted_seconds=str(accounted),remaining_case_slots_seconds=0,unconsumed_host_overhead_reserve_seconds=str(reserve),global_finalization_reserve_seconds=1800,upper_bound_seconds=str(upper),remaining_headroom_seconds=str(115200-upper),historical_unmeasured_setup_caveat=True)
 return dict(inputs={'index_review':'validation/final_review.json'},resource_evidence=dict(index_budget=deepcopy(i['budget']),indexed_host_overheads=deepcopy(i['audited_host_overheads']),final_live_resource=deepcopy(final['resource']),final_live_review=dict(path='validation/final_review.json',sha256='d'*64,json_pointer='/resource'),final_host_execution_id='last-host'))
results={}
for name in ('baseline','omitted_prior_overhead','changed_physical_duration','clamped_historical_failure','changed_host_identity','changed_partial_reuse'):
 i=deepcopy(index)
 if name=='omitted_prior_overhead':i['audited_host_overheads']=[]
 if name=='changed_physical_duration':
  for r in i['attempts'][12:]:r['outer_seconds']=1;r['seconds']=0.5
 if name=='clamped_historical_failure':i['attempts'][11]['seconds']=2490.
 if name=='changed_host_identity':i['attempts'][12]['host_execution_id']='other-host'
 if name=='changed_partial_reuse':i['attempts'][0]['reused_optimizer_attempts']=0
 report=refresh(i)
 try:result=A.audit_resources(report,i,final,op,entries,Pins(),physical);results[name]={'accepted':True,'output':result}
 except Exception as e:results[name]={'accepted':False,'error_type':type(e).__name__,'error':str(e)}
# Independent known invariants of these invented retained execution facts.
assert results['baseline']['accepted'] and all(not r['accepted'] for k,r in results.items() if k!='baseline')
results['scope']='Retained original counterexamples adapted only to the new required raw-evidence interface. Baseline passes; omitted overhead and altered raw clocks/IDs/reuse reject. No actual report/cohort or source was changed.'
results['source_sha256']=hashlib.sha256(P.read_bytes()).hexdigest()
Path(__file__).with_suffix('.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(results,indent=2))
