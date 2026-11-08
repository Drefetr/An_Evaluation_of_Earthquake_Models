"""Invented controls only. No likelihood, optimizer, native or report builder."""
from copy import deepcopy
import importlib.util
import json
import math
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('private_final_audit', HERE/'audit_saved.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)


def invented():
    sequence, records, raw, refs, historical, slots = [], {}, {}, {}, {}, []
    gains = [-2., -1e-9, -5e-10, 0., 5e-10, 1e-9, 2e-9, 3.]+[0.]*12
    science = dict(shared_bounds=[[0.,2.]]*5, inhibition_bounds=[[0.,2.]]*3,
                   coordinates=['a','d','n','c','p','eta','sigma','tau'])
    for regime in range(4,8):
        for i in range(20):
            key = f'invented_S{regime}_{i}'
            sequence.append(key)
            disposition = 'scientific_unknown' if (regime,i)==(5,7) else 'wall_time_failure' if (regime,i)==(6,14) else 'complete'
            record = dict(case_id=key, regime=regime, disposition=disposition, outcomes=[], model_census={'invented':True})
            records[key] = record
            refs[key] = {'case':dict(path='validation/invented.zip',sha256='a'*64,member=key+'.json',member_sha256='b'*64,json_pointer=''), 'independent_review':{'path':'validation/invented_review.json','sha256':'c'*64}}
            case = dict(case_id=key, regime=regime, passed=disposition=='complete', n_train=100+i, n_test=50+i,
                thinning=dict(accepted_immigrants=i,rejected_immigrants=2,accepted_offspring=3,rejected_offspring=4),
                fits={},training_checks={},outcomes=[])
            gain=gains[i]; floor=gain==0
            for arm in A.ARMS:
                case['fits'][arm]=dict(selected={'state_index':0 if floor else 1},null_search_gaps=[1] if i==1 else [],records=[dict(success=i!=2)])
                case['training_checks'][arm]=dict(fine={'nll':100. if arm=='null' else 90.}, coarse={'nll':100. if arm=='null' or i==0 else 90.})
            for model,gate in A.PROCEDURES:
                comp=dict(fixed_floor_gain=-17.,intercept_only_gain=23.,fixed_floor={'path':'fixed'},intercept_only={'path':'intercept'})
                historical[(key,model,gate)]=comp
                if disposition=='complete':
                    theta=[1.]*8;theta[5]=0. if floor else 1.
                    if i==0:theta[0]=0.
                    out=dict(model=model,gate=gate,new_gain=gain,new_win=gain>0,near_zero=abs(gain)<=1e-9,
                        robust_positive=gain>1e-9,robust_negative=gain < -1e-9,floor_return=floor,
                        score={'joint':gain},new_null_score={'joint':0.},parameters=theta,
                        historical={'fixed_floor_gain':-17.,'intercept_only_gain':23.})
                    case['outcomes'].append(out)
                    slots.append(dict(deepcopy(out),id=key+'|'+model+'|'+gate,case_id=key,regime=regime,availability='computed',historical_comparators=comp,
                        source=dict(refs[key]['case'],json_pointer='/outcomes/'+str(len(case['outcomes'])-1))))
                else:
                    out={name:None for name in A.NULL_FIELDS}
                    out.update(id=key+'|'+model+'|'+gate,case_id=key,regime=regime,model=model,gate=gate,availability='unavailable',
                        reason_code='scientific_wall_limit' if disposition=='wall_time_failure' else 'original_optimizer_cap_unknown',source=refs[key]['case'],failure_evidence=refs[key],historical_comparators=comp)
                    if disposition=='scientific_unknown':out['model_census']=record['model_census']
                    slots.append(out)
            record['outcomes']=deepcopy(case['outcomes']);raw[key]=case
    return sequence,records,raw,refs,historical,{'outcomes':slots},science


def invented_resources():
    seq=['invented_'+str(i) for i in range(80)]
    old={'execution_id':'old-host','seconds':'3','review':{'path':'validation/old_review.json','sha256':'a'*64},'archive':{'path':'validation/old.zip','sha256':'b'*64}}
    final={'execution_id':'last-host','resource':{'whole_workflow_overhead_beyond_all_child_outer_seconds':'4'}}
    records=[];attempts=[];physical={}
    for i,key in enumerate(seq):
        host='base-host' if i<56 else 'old-host' if i<68 else 'last-host'
        source=dict(kind='host_execution',execution_id=host,result_sha256='e'*64,supervision_sha256='f'*64)
        records.append(dict(case_id=key,source=source))
        if i<44:continue
        # Deliberately heterogeneous retained clocks: do not reapply future
        # success caps to the already sealed over-deadline failure.
        seconds=2490.027 if i==55 else 7.25 if i<56 else 1
        outer=2490.578 if i==55 else 7.75 if i<56 else 2
        result=dict(case_id=key,numerical_attempt_id='id'+str(i),wall_seconds=seconds,
            actual_optimizer_attempts=4 if i==44 else 29 if i==55 else 32,
            reused_optimizer_attempts=28 if i==44 else 0,
            case_report_wall_seconds=seconds-0.25)
        supervision=dict(wall_seconds_including_cleanup=outer,execution_wall_seconds=outer-0.1)
        physical[key]=dict(result=result,supervision=supervision,source=deepcopy(source))
        attempts.append(dict(case_id=key,numerical_attempt_id=result['numerical_attempt_id'],host_execution_id=host,
            seconds=seconds,outer_seconds=outer,result_sha256=source['result_sha256'],supervision_sha256=source['supervision_sha256'],
            actual_optimizer_attempts=result['actual_optimizer_attempts'],reused_optimizer_attempts=result['reused_optimizer_attempts']))
    index=dict(records=records,audited_host_overheads=[old],attempts=attempts)
    op=dict(full_sequence=seq,case_slots=[dict(scientific_seconds=2,wall_seconds=3)]*24,
        failure={'execution_id':'failed-host'},accounting=dict(sealed_known_seconds='100',unconsumed_host_overhead_reserve_seconds='20',global_finalization_reserve_seconds=1800,global_cap_seconds=115200))
    entries={'old-host':(old,{'resource':{'whole_workflow_overhead_beyond_all_child_outer_seconds':'3'}})}
    class Pins:pins={'validation/final_review.json':'d'*64}
    return index,final,op,entries,Pins(),physical


def resource_report(index,final):
    overhead=sum((Decimal(r['seconds']) for r in index['audited_host_overheads']),Decimal(0))
    science=sum((Decimal(str(r['seconds'])) for r in index['attempts'][12:]),Decimal(0))
    outer=sum((Decimal(str(r['outer_seconds'])) for r in index['attempts'][12:]),Decimal(0))
    reserve=20-overhead;accounted=100+outer+overhead;upper=accounted+reserve+1800
    index['budget']=dict(sealed_known_seconds='100',future_scientific_seconds=str(science),future_outer_seconds=str(outer),
        audited_future_host_overhead_seconds=str(overhead),accounted_seconds=str(accounted),remaining_case_slots_seconds=0,
        unconsumed_host_overhead_reserve_seconds=str(reserve),global_finalization_reserve_seconds=1800,
        upper_bound_seconds=str(upper),remaining_headroom_seconds=str(115200-upper),historical_unmeasured_setup_caveat=True)
    return dict(inputs={'index_review':'validation/final_review.json'},resource_evidence=dict(index_budget=deepcopy(index['budget']),
        indexed_host_overheads=deepcopy(index['audited_host_overheads']),final_live_resource=deepcopy(final['resource']),
        final_live_review=dict(path='validation/final_review.json',sha256='d'*64,json_pointer='/resource'),final_host_execution_id='last-host'))


class IndependentArithmetic(unittest.TestCase):
    def test_strict_sign_floor_boundary_and_complete_regime_statistics(self):
        seq,records,raw,_,_,_,science=invented()
        rows=A.summarize(seq,records,raw,science)
        self.assertEqual(len(rows),20)
        full=rows[0]['full_regime']
        self.assertEqual((full['wins'],full['positive_near_zero'],full['robust_positive'],full['robust_negative'],full['near_zero']),(4,2,2,1,17))
        self.assertAlmostEqual(full['mean_gain'],(1+2e-9)/20,places=15)
        self.assertEqual(full['median_gain'],0.)
        self.assertEqual((full['floor_returns'],full['off_floor'],full['a_boundary'],full['eta_lower']),(13,7,1,13))
        self.assertEqual(full['optimizer_failed_attempts'],2)
        self.assertEqual(full['coarse_fine_gate_disagreements'],1)
        self.assertEqual(full['mean_training_events'],109.5)
        self.assertEqual(full['realized_thinning']['accepted_immigrants'],190)
        self.assertEqual(full['coordinate_boundaries']['eta'],{'lower':13,'upper':0})
        # Direct known numerical Wilson endpoint check independent of implementation.
        self.assertAlmostEqual(full['wilson95'][0],0.08065766257979806,places=14)
        self.assertAlmostEqual(full['wilson95'][1],0.4160174322518936,places=14)

    def test_incomplete_regime_has_no_conditional_mean_or_wilson(self):
        seq,records,raw,_,_,_,science=invented()
        for row in A.summarize(seq,records,raw,science):
            incomplete=row['regime'] in (5,6)
            self.assertEqual(row['statistics_available'],not incomplete)
            self.assertEqual(row['computed_histories'],19 if incomplete else 20)
            if incomplete:self.assertIsNone(row['full_regime'])
        raw['invented_S5_7']['outcomes']=[{'new_gain':99999.}]
        self.assertIsNone(A.summarize(seq,records,raw,science)[5]['full_regime'])

    def test_all80_and_unique_roster_required(self):
        seq,records,raw,_,_,_,science=invented()
        for bad in (seq[:-1],seq[:-1]+[seq[0]]):
            with self.assertRaises(ValueError):A.summarize(bad,records,raw,science)

    def test_wilson_extreme_wins(self):
        expected=3.841458820694124/(20+3.841458820694124)
        zero,allwins=A.wilson(0,20),A.wilson(20,20)
        self.assertAlmostEqual(zero[0],0.,places=15)
        self.assertAlmostEqual(zero[1],expected,places=15)
        self.assertAlmostEqual(allwins[0],1-expected,places=15)
        self.assertAlmostEqual(allwins[1],1.,places=15)

    def test_400_exact_operands_and_both_comparators_survive_missingness(self):
        seq,records,raw,refs,historical,report,_=invented()
        actual=A.check_slots(report,seq,records,raw,refs,historical)
        self.assertEqual(sum(r['availability']=='computed' for r in actual),390)
        missing=[r for r in actual if r['availability']=='unavailable']
        self.assertEqual(len(missing),10)
        self.assertEqual({r['reason_code'] for r in missing},{'scientific_wall_limit','original_optimizer_cap_unknown'})
        self.assertTrue(all(r['new_gain'] is None and r['new_win'] is None and r['historical_comparators']['fixed_floor_gain']==-17. and r['historical_comparators']['intercept_only_gain']==23. for r in missing))

    def test_zero_false_loss_or_heldout_in_missing_slot_rejected(self):
        seq,records,raw,refs,historical,report,_=invented()
        i=next(i for i,r in enumerate(report['outcomes']) if r['availability']=='unavailable')
        for field,value in [('new_gain',0.),('new_win',False),('score',{'joint':0.})]:
            changed=deepcopy(report);changed['outcomes'][i][field]=value
            with self.assertRaises(ValueError):A.check_slots(changed,seq,records,raw,refs,historical)
        raw['invented_S5_7']['new_null_test']={'joint':0.}
        with self.assertRaises(ValueError):A.check_slots(report,seq,records,raw,refs,historical)

    def test_recomputed_summary_rejects_new_conditioning_or_sign_count(self):
        seq,records,raw,_,_,_,science=invented();expected=A.summarize(seq,records,raw,science)
        for key,value in [('wins',2),('positive_near_zero',0),('optimizer_failed_attempts',0)]:
            bad=deepcopy(expected);bad[0]['full_regime'][key]=value
            with self.assertRaises(ValueError):A.compare(bad,expected)
        bad=deepcopy(expected);bad[5]['full_regime']=deepcopy(expected[0]['full_regime'])
        with self.assertRaises(ValueError):A.compare(bad,expected)

    def test_historical_or_slot_source_mutation_rejected(self):
        seq,records,raw,refs,historical,report,_=invented()
        for action in ('historical','operand','source'):
            changed=deepcopy(report)
            if action=='historical':changed['outcomes'][0]['historical_comparators']['fixed_floor_gain']=0.
            if action=='operand':changed['outcomes'][0]['score']['joint']=-1.
            if action=='source':changed['outcomes'][0]['source']['member']='wrong.json'
            with self.assertRaises(ValueError):A.check_slots(changed,seq,records,raw,refs,historical)


class CustodyControls(unittest.TestCase):
    def test_final_resource_receipt_is_separate_and_duplicate_charge_rejected(self):
        index,final,op,entries,pins,physical=invented_resources();report=resource_report(index,final)
        value=A.audit_resources(report,index,final,op,entries,pins,physical)
        self.assertEqual(value['known_with_final_host_overhead_seconds'],'155')
        self.assertEqual(value['conservative_reserved_upper_seconds'],'1968')
        self.assertFalse(value['overlapping_totals_added'])
        for key in ('old-host','last-host','failed-host'):
            bad=deepcopy(index);bad['audited_host_overheads'].append(dict(index['audited_host_overheads'][0],execution_id=key))
            r=deepcopy(report);r['resource_evidence']['indexed_host_overheads']=deepcopy(bad['audited_host_overheads'])
            with self.subTest(execution=key),self.assertRaises(ValueError):A.audit_resources(r,bad,final,op,entries,pins,physical)

    def test_FA1_missing_prior_host_overhead_rejected_even_if_budget_recomputed(self):
        index,final,op,entries,pins,physical=invented_resources()
        index['audited_host_overheads']=[]
        report=resource_report(index,final)
        self.assertEqual(index['budget']['accounted_seconds'],'148')
        with self.assertRaisesRegex(ValueError,'prior operational host overhead'):
            A.audit_resources(report,index,final,op,entries,pins,physical)

    def test_FA2_lowered_within_cap_clocks_rejected_even_if_budget_recomputed(self):
        index,final,op,entries,pins,physical=invented_resources()
        for r in index['attempts'][12:]:r.update(seconds=0.5,outer_seconds=1)
        report=resource_report(index,final)
        self.assertEqual(index['budget']['accounted_seconds'],'127')
        with self.assertRaisesRegex(ValueError,'bound result/supervision'):
            A.audit_resources(report,index,final,op,entries,pins,physical)

    def test_attempt_ids_host_ids_hashes_and_reuse_counts_bound_to_raw(self):
        index,final,op,entries,pins,physical=invented_resources()
        for field,value in [('numerical_attempt_id','other-id'),('host_execution_id','other-host'),
                            ('result_sha256','0'*64),('supervision_sha256','0'*64),
                            ('actual_optimizer_attempts',31),('reused_optimizer_attempts',1)]:
            bad=deepcopy(index);bad['attempts'][12][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'bound result/supervision'):
                A.audit_resources(resource_report(bad,final),bad,final,op,entries,pins,physical)

    def test_retained_partial_and_wall_clocks_are_exact_not_new_uniform_success_caps(self):
        index,final,op,entries,pins,physical=invented_resources()
        A.audit_resources(resource_report(index,final),index,final,op,entries,pins,physical)
        self.assertEqual(index['attempts'][0]['reused_optimizer_attempts'],28)
        self.assertGreater(index['attempts'][11]['seconds'],2490)
        for position in (0,11):
            bad=deepcopy(index);bad['attempts'][position]['seconds']=1
            with self.subTest(position=position),self.assertRaisesRegex(ValueError,'bound result/supervision'):
                A.audit_resources(resource_report(bad,final),bad,final,op,entries,pins,physical)

    def test_missing_raw_attempt_evidence_or_source_association_rejected(self):
        index,final,op,entries,pins,physical=invented_resources();report=resource_report(index,final)
        bad=deepcopy(physical);bad.pop('invented_56')
        with self.assertRaises(ValueError):A.audit_resources(report,index,final,op,entries,pins,bad)
        bad=deepcopy(physical);bad['invented_56']['source']['execution_id']='old-other-host'
        with self.assertRaises(ValueError):A.audit_resources(report,index,final,op,entries,pins,bad)

    def test_pinned_archive_and_member_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'validation').mkdir();path=root/'validation/a.zip';payload=b'{"x":1}'
            with zipfile.ZipFile(path,'w') as z:z.writestr('host/a.json',payload)
            ref={'path':'validation/a.zip','sha256':A.digest(path.read_bytes())};s=A.Saved(root)
            self.assertEqual(s.member(ref,'host/a.json',A.digest(payload)),{'x':1})
            with self.assertRaises(ValueError):s.member(ref,'host/a.json','0'*64)
            with self.assertRaises(ValueError):s.archive(dict(ref,sha256='0'*64))
            s.close()

    def test_duplicate_json_aliases_and_unsafe_zip_paths(self):
        with self.assertRaises(ValueError):A.document('{"x":1,"x":2}')
        with self.assertRaises(ValueError):A.document('{"x":NaN}')
        for value in ('../a','validation/../a','validation\\a','/a','validation//a','validation/./a'):
            with self.subTest(value=value),self.assertRaises(ValueError):A.member_name(value)

    def test_live_failed_host_cannot_borrow_pass_or_pending_review(self):
        valid=dict(live_agent_review=True,live_agent_review_performed=True,final_batch_agent_review_required=False,
                   audit_passed=True,scientific_completion=False,passed=False)
        A.live(valid,True)
        for key,value in [('passed',True),('live_agent_review',False),('live_independent_review',False),('final_batch_agent_review_required',True),('scientific_completion',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):A.live(dict(valid,**{key:value}),True)

    def test_summary_type_sensitive_false_is_not_zero(self):
        with self.assertRaises(ValueError):A.compare({'count':False},{'count':0})
        with self.assertRaises(ValueError):A.compare({'value':0},{'value':None})


if __name__=='__main__':unittest.main(verbosity=2)
