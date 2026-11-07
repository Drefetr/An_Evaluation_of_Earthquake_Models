"""Invented orchestration controls only; no likelihood, optimizer or native calls."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from experiments.s04b_joint_recovery_host import batch


class RecoveryHostControls(unittest.TestCase):
    def metadata(self):
        policy = copy.deepcopy(batch.read(batch.HERE/'batch_policy.json'))
        resource = batch.read(batch.HERE/'evidence/resource_review.json')
        old = batch.read(batch.REPO/'experiments/s04b_joint_budgeted/allocation_protocol.json')
        slots = [dict(case_id=r['case_id'],wall_seconds=r['wall_seconds'],
                      scientific_reservation_seconds=r['scientific_reservation_seconds'],
                      regime=r['regime']) for r in resource['remaining_roster']]
        recovery = dict(sequence=old['sequence'],fixed_slots=slots,actual_hosts=policy['actual_hosts'],
            shared_run=policy['shared_run'],predecessor=dict(case_id=old['sequence'][40],
                index_sha256='failed-index',review_sha256='failed-review',original_index_charged_seconds=21663.863217721,
                known_outer_charged_seconds=21714.885916780))
        actual=batch.read(batch.REPO/'experiments/s04b_joint_recovery/recovery_protocol.json')
        for key in ('pre_execution_failure','operational_failures','operational_diagnostics'):
            recovery[key]=copy.deepcopy(actual[key])
        return policy,recovery

    def prefix(self,host=1):
        p,r=self.metadata();count=p['starting_accepted_counts'][host-1]
        index=dict(schema='joint_recovery_case_index_v2',cases=[{'case_id':x} for x in r['sequence'][:count]],
                   attempts=[{'attempt_id':'old-attempt'}],partial_case=None,last_attempt_passed=True,
                   budget={'total_seconds':21663.863217721})
        review=dict(passed=True,index_sha256='accepted-index',live_agent_review=True,
                    review_kind='live_agent_saved_output_review',final_batch_agent_review_required=False)
        if host==1:
            index.update(schema='joint_budgeted_case_index_v2',last_attempt_passed=False,
                         partial_case={'case_id':r['predecessor']['case_id']})
            review=dict(passed=False,audit_passed=True,overall_scientific_passed=False,live_agent_review=True,
                        review_kind='live_agent_failure_and_partial_output_review',failed_index={'sha256':'failed-index'})
        names=p['actual_hosts'][host-1]['case_ids']
        a=dict(batch_id=host,case_ids=names,numerical_attempt_id='shared-lease',
               child_attempt_ids={n:'shared-lease-case-%03d'%(r['sequence'].index(n)+1) for n in names},
               prior_index_sha256=batch.reviewed_index(review))
        return p,r,index,review,a

    def test_exact_eight_host_roster_and_all_reserves(self):
        p,r=self.metadata()
        self.assertEqual([len(g['case_ids']) for g in p['actual_hosts']],[1,5,5,5,5,8,8,3])
        self.assertEqual([g['case_slot_seconds'] for g in p['actual_hosts']],[1200,9960,12600,12600,12600,9600,9600,3600])
        self.assertEqual([x for g in p['actual_hosts'] for x in g['case_ids']],r['sequence'][40:])
        self.assertEqual(sum(x['wall_seconds'] for x in r['fixed_slots']),71760)
        self.assertTrue(all(g['checker_reservations_seconds']+600+30<=1800 for g in p['actual_hosts']))
        self.assertLess(21714.885916780+71760+8*1800+1800,115200)

    def test_startup_charge_is_once_and_never_changes_scientific_predecessor(self):
        policy,recovery=batch.verify_policy()
        self.assertEqual(batch.pre_execution_charge(policy,recovery),90)
        self.assertEqual(recovery['predecessor']['original_index_charged_seconds'],21663.863217721)
        self.assertEqual(recovery['predecessor']['index_sha256'],
                         'a8dd94439fce7a72d0f6a69c2a095b2abdb06ba312e261f62e9e814229888430')
        future=71760+8*1800+1800
        margin=115200-recovery['predecessor']['known_outer_charged_seconds']-90-future
        self.assertAlmostEqual(margin,5435.114083220,places=8)
        for key,value in [('charge_seconds',0),('charge_seconds',90.665865991),
                          ('status','passed'),('scientific_predecessor_unchanged',False),
                          ('nested_supervised_seconds',91)]:
            changed=copy.deepcopy(recovery);changed['pre_execution_failure'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                batch.pre_execution_charge(policy,changed)
        changed=copy.deepcopy(recovery);changed['pre_execution_failure']['workflow_log_sha256']='0'*64
        with self.assertRaises(ValueError):batch.pre_execution_charge(policy,changed)

    def ordered_failure_fixture(self,root):
        # Primitive invented failure evidence; never an actual fit/result fixture.
        failures=[]
        for number,(charge,status,count) in enumerate(((90,'failed_before_scientific_evaluation',0),
                                                      (120,'failed_during_training_support',5)),1):
            row=dict(status=status,charge_seconds=charge,scientific_predecessor_unchanged=True,
                     nested_scientific_seconds=.25,nested_supervised_seconds=.5)
            if number==2:row.update(support_evaluation_count=count,optimizer_call_count=0)
            for key in ('archive','review','resource_review','workflow_log'):
                relative=f'failure{number}_{key}.json';path=root/relative
                if key=='review':
                    value=dict(audit_passed=True,passed=False,overall_scientific_passed=False,
                               archive_sha256=row['archive_sha256'])
                elif key=='resource_review':
                    value=(dict(passed=True,amendment={'explicit_new_charge_bound_seconds':charge}) if number==1 else
                           dict(passed=True,timing={'conservative_whole_launch_charge_seconds':charge},
                                failure={'support_evaluation_count':5,'optimizer_call_count':0}))
                else:value={'invented':True,'identity':number,'kind':key}
                batch.write(path,value);row[key]=relative;row[key+'_sha256']=batch.sha(path)
            failures.append(row)
        recovery={'pre_execution_failure':copy.deepcopy(failures[0]),'operational_failures':failures}
        policy={'pre_execution_failure_charge_seconds':90,
                'pre_execution_failure_resource_review_sha256':failures[0]['resource_review_sha256']}
        return policy,recovery

    def test_ordered_failures_charge_list_once_without_alias_or_nested_addition(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);policy,recovery=self.ordered_failure_fixture(root)
            with patch.object(batch,'REPO',root):
                self.assertEqual(batch.operational_failure_charge(policy,recovery),210)
                changed=copy.deepcopy(recovery)
                changed['operational_failures'][1]['nested_scientific_seconds']=.3
                self.assertEqual(batch.operational_failure_charge(policy,changed),210)

    def test_order_alias_unique_archive_and_scope_cannot_be_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);policy,recovery=self.ordered_failure_fixture(root)
            mutations=[]
            wrong=copy.deepcopy(recovery);wrong['operational_failures'].reverse();mutations.append(wrong)
            wrong=copy.deepcopy(recovery);wrong['operational_failures'][0]['charge_seconds']=91;mutations.append(wrong)
            wrong=copy.deepcopy(recovery);wrong['operational_failures'][1]['archive_sha256']=wrong['operational_failures'][0]['archive_sha256'];mutations.append(wrong)
            for key,value in [('charge_seconds',121.780888234),('status','failed_before_scientific_evaluation'),
                              ('support_evaluation_count',0),('optimizer_call_count',1),('nested_supervised_seconds',121)]:
                wrong=copy.deepcopy(recovery);wrong['operational_failures'][1][key]=value;mutations.append(wrong)
            with patch.object(batch,'REPO',root):
                for wrong in mutations:
                    with self.subTest(value=wrong),self.assertRaises(ValueError):
                        batch.operational_failure_charge(policy,wrong)

    def test_second_failure_evidence_hash_and_failed_status_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);policy,recovery=self.ordered_failure_fixture(root)
            with patch.object(batch,'REPO',root):
                wrong=copy.deepcopy(recovery);wrong['operational_failures'][1]['workflow_log_sha256']='0'*64
                with self.assertRaises(ValueError):batch.operational_failure_charge(policy,wrong)
                path=root/recovery['operational_failures'][1]['review'];review=batch.read(path)
                review['passed']=True;batch.write(path,review)
                recovery['operational_failures'][1]['review_sha256']=batch.sha(path)
                with self.assertRaises(ValueError):batch.operational_failure_charge(policy,recovery)

    def diagnostic_fixture(self,root):
        policy,recovery=self.ordered_failure_fixture(root)
        row=dict(status='diagnostic_complete',passed=True,equality_passed=False,scientific_completion=False,
            scientific_predecessor_unchanged=True,charge_seconds=80,nested_scientific_seconds=.25,
            nested_supervised_seconds=.5,support_evaluation_count=5,optimizer_call_count=0,held_out_call_count=0)
        for key in ('archive','review','resource_review','workflow_log'):
            relative=f'diagnostic_{key}.json';path=root/relative
            if key=='review':
                value=dict(passed=True,audit_passed=True,diagnostic_complete=True,equality_passed=False,
                    scientific_completion=False,accepted_recovery_case=False,archive_sha256=row['archive_sha256'],
                    execution=dict(actual_training_evaluations=5,optimizer_calls=0,held_out_calls=0,
                        new_complete_cases=0,accepted_complete_cases_unchanged=40,science_seconds=.25,supervised_seconds=.5))
            elif key=='resource_review':
                value=dict(passed=True,timing=dict(conservative_whole_launch_charge_seconds=80,
                    child_scientific_seconds=.25,outer_including_cleanup_seconds=.5),
                    accounting=dict(operational_failure_charge_seconds=210,operational_diagnostic_charge_seconds=80,
                        combined_additional_operational_charge_seconds=290),
                    diagnostic=dict(independent_review_sha256=row['review_sha256']))
            else:value={'invented':True,'kind':key}
            batch.write(path,value);row[key]=relative;row[key+'_sha256']=batch.sha(path)
        recovery['operational_diagnostics']=[row]
        return policy,recovery

    def test_diagnostic_charged_once_separate_from_failures_and_original_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);policy,recovery=self.diagnostic_fixture(root)
            with patch.object(batch,'REPO',root):
                self.assertEqual(batch.pre_execution_charge(policy,recovery),90)
                failure=batch.operational_failure_charge(policy,recovery)
                diagnostic=batch.operational_diagnostic_charge(recovery)
                self.assertEqual((failure,diagnostic,failure+diagnostic),(210,80,290))

    def test_diagnostic_omission_duplication_and_scientific_relabelling_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);policy,recovery=self.diagnostic_fixture(root);mutations=[]
            for replacement in ([],recovery['operational_diagnostics']*2):
                changed=copy.deepcopy(recovery);changed['operational_diagnostics']=replacement;mutations.append(changed)
            for key,value in [('charge_seconds',80.5),('passed',False),('equality_passed',True),
                              ('scientific_completion',True),('scientific_predecessor_unchanged',False),
                              ('support_evaluation_count',0),('optimizer_call_count',1),('held_out_call_count',1),
                              ('nested_scientific_seconds',.3),('nested_supervised_seconds',81),
                              ('archive_sha256',recovery['operational_failures'][0]['archive_sha256'])]:
                changed=copy.deepcopy(recovery);changed['operational_diagnostics'][0][key]=value;mutations.append(changed)
            with patch.object(batch,'REPO',root):
                for changed in mutations:
                    with self.subTest(value=changed),self.assertRaises(ValueError):
                        batch.operational_diagnostic_charge(changed)

    def test_diagnostic_evidence_and_independent_scope_cannot_be_bypassed(self):
        for change in ('hash','case','accounting'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);policy,recovery=self.diagnostic_fixture(root);row=recovery['operational_diagnostics'][0]
                if change=='hash':row['workflow_log_sha256']='0'*64
                elif change=='case':
                    path=root/row['review'];value=batch.read(path);value['accepted_recovery_case']=True
                    batch.write(path,value);row['review_sha256']=batch.sha(path)
                else:
                    path=root/row['resource_review'];value=batch.read(path)
                    value['accounting']['combined_additional_operational_charge_seconds']=380
                    batch.write(path,value);row['resource_review_sha256']=batch.sha(path)
                with patch.object(batch,'REPO',root),self.assertRaises(ValueError):
                    batch.operational_diagnostic_charge(recovery)

    def test_actual_frozen_recovery_protocol_integrates_without_scientific_calls(self):
        policy,recovery=batch.verify_policy()
        self.assertEqual(batch.sha(batch.REPO/'experiments/s04b_joint_recovery/recovery_protocol.json'),
                         policy['recovery_protocol_sha256'])
        self.assertEqual([row['regime'] for row in recovery['fixed_slots']], [5]*3+[6]*18+[7]*19)
        self.assertEqual(len(policy['actual_hosts']),8)
        self.assertEqual(batch.operational_failure_charge(policy,recovery),210)
        self.assertEqual(batch.operational_diagnostic_charge(recovery),80)
        margin=115200-recovery['predecessor']['known_outer_charged_seconds']-290-71760-8*1800-1800
        self.assertAlmostEqual(margin,5235.114083220,places=8)

    def test_policy_rejects_repinning_different_caps_or_incomplete_roster(self):
        original_here=batch.HERE
        for mutation in ('none','cap','roster','reservation','prefix'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                repo=Path(directory);here=repo/'experiments/s04b_joint_recovery_host';(here/'evidence').mkdir(parents=True)
                policy,recovery=self.metadata()
                for row in recovery['operational_failures']+recovery['operational_diagnostics']:
                    for key in ('archive','review','resource_review','workflow_log'):
                        relative=row[key];target=repo/relative
                        target.parent.mkdir(parents=True,exist_ok=True)
                        target.write_bytes((batch.REPO/relative).read_bytes())
                (here/'evidence/resource_review.json').write_bytes((original_here/'evidence/resource_review.json').read_bytes())
                helper=repo/'experiments/s04b_joint_host_batch/batch.py';helper.parent.mkdir(parents=True)
                helper.write_text('invented historical source')
                policy['historical_sources']={helper.relative_to(repo).as_posix():batch.sha(helper)}
                path=repo/'experiments/s04b_joint_recovery/recovery_protocol.json';path.parent.mkdir(parents=True,exist_ok=True)
                if mutation=='cap':recovery['fixed_slots'][0]['wall_seconds']=1800
                if mutation=='reservation':recovery['fixed_slots'][0]['scientific_reservation_seconds']=1200
                if mutation=='roster':recovery['fixed_slots'].pop()
                if mutation=='prefix':policy['starting_accepted_counts'][1]=42
                batch.write(path,recovery);policy['recovery_protocol_sha256']=batch.sha(path)
                batch.write(here/'batch_policy.json',policy)
                with patch.object(batch,'REPO',repo),patch.object(batch,'HERE',here):
                    if mutation=='none':self.assertEqual(len(batch.verify_policy()[1]['fixed_slots']),40)
                    else:
                        with self.assertRaises(ValueError):batch.verify_policy()

    def test_exact_failed_predecessor_allowed_only_for_standalone_pilot(self):
        p,r,i,v,a=self.prefix()
        self.assertEqual(batch.next_cases(p,r,a,i,v),[r['sequence'][40]])
        for change in ({'passed':True},{'audit_passed':False},{'overall_scientific_passed':True},
                       {'failed_index':{'sha256':'other'}},{'live_agent_review':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                batch.next_cases(p,r,a,i,dict(v,**change))
        with self.assertRaises(ValueError):batch.next_cases(p,r,dict(a,batch_id=2),i,v)

    def test_pilot_machine_check_never_unlocks_host_two(self):
        p,r,i,v,a=self.prefix(2)
        self.assertEqual(len(batch.next_cases(p,r,a,i,v)),5)
        for change in ({'live_agent_review':False},{'review_kind':'automated_saved_output_check'},
                       {'final_batch_agent_review_required':True},{'passed':False}):
            with self.subTest(change=change),self.assertRaises(ValueError):batch.next_cases(p,r,a,i,dict(v,**change))

    def test_no_partial_host_suffix_retry_or_duplicate_attempt(self):
        p,r,i,v,a=self.prefix(2)
        changed=copy.deepcopy(i);changed['cases'].append({'case_id':a['case_ids'][0]})
        with self.assertRaises(ValueError):batch.next_cases(p,r,a,changed,v)
        for change in ({'case_ids':a['case_ids'][::-1]}, {'case_ids':a['case_ids'][1:]},
                       {'child_attempt_ids':{n:'same' for n in a['case_ids']}},{'batch_id':True}):
            with self.assertRaises(ValueError):batch.next_cases(p,r,dict(a,**change),i,v)
        i['attempts'].append({'attempt_id':a['child_attempt_ids'][a['case_ids'][0]]})
        with self.assertRaises(ValueError):batch.next_cases(p,r,a,i,v)

    def test_actual_pilot_window_is_not_generic_four_hours(self):
        p,r=self.metadata();g=p['actual_hosts'][0];now=dt.datetime.now(dt.timezone.utc)
        batch.timing(p,g,(now-dt.timedelta(seconds=500)).isoformat(),0,1200,now)
        for elapsed,child in [(1100,1000),(1100,0),(-1,0)]:
            with self.assertRaises(ValueError):batch.timing(p,g,(now-dt.timedelta(seconds=elapsed)).isoformat(),child,1200,now)
        with self.assertRaises(ValueError):batch.timing(p,g,now.isoformat(),float('nan'),1200,now)

    def fixture(self,root,host=2):
        policy,recovery,index,review,grant=self.prefix(host)
        prior=root/'prior';(prior/'science').mkdir(parents=True);(prior/'build').mkdir()
        batch.write(prior/'science/index.json',index)
        (prior/'build/attenuation.so').write_bytes(b'invented native')
        batch.write(prior/'build/build_receipt.json',{'passed':True,'invented':True})
        ip=batch.sha(prior/'science/index.json')
        if host==1:review['failed_index']['sha256']=ip
        else:review['index_sha256']=ip
        batch.write(root/'prior_review.json',review)
        recovery['predecessor'].update(index_sha256=ip,review_sha256=batch.sha(root/'prior_review.json'),
            library_sha256=batch.sha(prior/'build/attenuation.so'),build_receipt_sha256=batch.sha(prior/'build/build_receipt.json'))
        repo=root/'repo';repo.mkdir();here=repo/'experiments/s04b_joint_recovery_host';here.mkdir(parents=True)
        batch.write(here/'batch_policy.json',policy)
        sources={}
        for name in ('experiments/s04b_joint_recovery_host/batch.py','experiments/s04b_joint_recovery/driver.py',
                     policy['checker']['path'],policy['checker']['core_path'],
                     *policy['checker']['helper_sources_sha256']):
            f=repo/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('invented '+name,encoding='utf-8');sources[name]=batch.sha(f)
        hostpins={k:v for k,v in sources.items() if 'recovery_host/' in k}
        driverpins={k:v for k,v in sources.items() if '/s04b_joint_recovery/' in k}
        checker_pins={k:v for k,v in sources.items() if k in (policy['checker']['path'],policy['checker']['core_path'],*policy['checker']['helper_sources_sha256'])}
        policy['checker']['core_sha256']=checker_pins[policy['checker']['core_path']]
        policy['checker']['helper_sources_sha256']={k:checker_pins[k] for k in policy['checker']['helper_sources_sha256']}
        batch.write(here/'batch_policy.json',policy)
        (root/'failed.zip').write_bytes(b'invented original failure')
        old=repo/'experiments/s04b_joint_execution/operational_protocol.json';old.parent.mkdir(parents=True)
        batch.write(old,{'original_failure':{'failed_archive_sha256':batch.sha(root/'failed.zip')}})
        batch.write(root/'config.json',{'invented':True})
        batch.write(root/'checker_review.json',{'passed':True,'reviewed_files_sha256':checker_pins})
        policy['checker']['source_review_sha256']=batch.sha(root/'checker_review.json')
        batch.write(here/'batch_policy.json',policy)
        source_review=repo/'source_review.json';batch.write(source_review,{'passed':True,'reviewed_files_sha256':{**hostpins,**driverpins}})
        policy['shared_run'].update(config_sha256=batch.sha(root/'config.json'),expires_utc='2099-01-01T00:00:00+00:00')
        grant.update(mode='recovery_host_batch',source_sha256=hostpins,scientific_source_sha256=driverpins,
            recovery_protocol_sha256=policy['recovery_protocol_sha256'],batch_policy_sha256=batch.sha(here/'batch_policy.json'),
            shared_run=policy['shared_run'],host_batch_source_review_passed=True,checker_source_review_passed=True,
            rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,
            lease_token_sha256=batch.hashlib.sha256(b'fixture-token').hexdigest(),prior_index_sha256=ip,
            prior_review_sha256=batch.sha(root/'prior_review.json'),expires_utc='2099-01-01T00:00:00+00:00',
            checker_source_review_sha256=batch.sha(root/'checker_review.json'),source_review_sha256=batch.sha(source_review),
            reviewed_files_sha256=sources,host_started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            execution_window_seconds=policy['actual_hosts'][host-1]['outer_maximum_seconds']-600,
            source_commit='abcdef1',conductor_review={'source_review_record':'source_review.json'})
        batch.write(root/'admission.json',grant)
        args=argparse.Namespace(output=root/'output',admission=root/'admission.json',prior=prior,
            prior_review=root/'prior_review.json',config=root/'config.json',checker_review=root/'checker_review.json',
            failed_archive=root/'failed.zip')
        return args,grant,policy,recovery,repo,here,hostpins,driverpins,checker_pins

    def execute(self,values,failure=None):
        args,grant,policy,recovery,repo,here,hostpins,driverpins,checker_pins=values;calls=[]
        def fake(command,output,cap,admission,environment,spec_path):
            is_check='--current' in command;calls.append(('check' if is_check else 'case',cap))
            self.assertTrue(all(environment[k]=='2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')))
            output.mkdir(parents=True);batch.write(spec_path,{'command':command,'wall_cap_seconds':cap})
            batch.write(output/'result.json',{'status':'passed','returncode':0,'cleanup_errors':[],'survivors_after_cleanup':[]})
            destination=Path(command[command.index('--output')+1])
            if is_check:
                current=Path(command[command.index('--current')+1])
                receipt=dict(passed=failure!='checker',index_sha256=batch.sha(current/'science/index.json'),
                    review_kind='automated_saved_output_check',live_agent_review=False,live_agent_review_performed=False,
                    final_batch_agent_review_required=True,checker_source_review_sha256=grant['checker_source_review_sha256'],
                    checker_sources_sha256=checker_pins)
                if failure=='fake_live_review':receipt['live_agent_review']=True
                batch.write(destination,receipt)
            else:
                if failure=='second' and len([c for c in calls if c[0]=='case'])==2:raise ValueError('invented child failure')
                a=batch.read(command[command.index('--admission')+1]);parent=batch.read(command[command.index('--prior-index')+1])
                self.assertEqual(a['mode'],'recovery_campaign');self.assertEqual(a['minimum_host_free_bytes'],2147483648)
                destination.mkdir();parent['cases'].append({'case_id':a['case_id']});parent.update(
                    schema='joint_recovery_case_index_v2',partial_case=None,last_attempt_passed=True)
                batch.write(destination/'index.json',parent)
                batch.write(destination/'result.json',dict(schema='joint_recovery_batch_v1',passed=failure!='false_success',
                    status='batch_complete',cases=[{'case_id':a['case_id']}],index_sha256=batch.sha(destination/'index.json')))
            return batch.read(output/'result.json')
        with patch.object(batch,'REPO',repo),patch.object(batch,'HERE',here),             patch.object(batch,'verify_policy',return_value=(policy,recovery)),             patch.object(batch,'source_identity',return_value=hostpins),             patch.object(batch,'load_driver',return_value=types.SimpleNamespace(source_identity=lambda:driverpins)),             patch.dict(batch.os.environ,{'JOINT_NUMERICAL_LEASE_TOKEN':'fixture-token'}),             patch.object(batch,'supervised',side_effect=fake):
            code=batch.run(args)
        return code,batch.read(args.output/'result.json'),calls

    def test_standalone_pilot_cannot_start_another_case(self):
        with tempfile.TemporaryDirectory() as directory:
            values=self.fixture(Path(directory),1);code,result,calls=self.execute(values)
            self.assertEqual(code,0,result);self.assertEqual(calls,[('case',1200),('check',120)])
            self.assertTrue(result['mandatory_pilot_live_review_pending']);self.assertFalse(result['scientific_completion'])

    def test_order_native_bytes_and_independent_check_between_every_child(self):
        with tempfile.TemporaryDirectory() as directory:
            values=self.fixture(Path(directory));code,result,calls=self.execute(values)
            self.assertEqual(code,0,result);self.assertEqual(calls,[v for cap in (1200,1200,2520,2520,2520) for v in [('case',cap),('check',120)]])
            self.assertEqual([r['case_id'] for r in result['children']],values[1]['case_ids'])
            for row in result['children']:
                child=values[0].output/row['artifact']
                self.assertEqual((child/'build/attenuation.so').read_bytes(),b'invented native')
                self.assertEqual((child/'original_failure.zip').read_bytes(),values[0].failed_archive.read_bytes())
            self.assertFalse(result['live_agent_review']);self.assertTrue(result['final_batch_agent_review_required'])

    def test_bad_checker_or_false_exit_never_starts_next_child(self):
        for failure in ('checker','false_success','fake_live_review'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                values=self.fixture(Path(directory));code,result,calls=self.execute(values,failure)
                self.assertEqual(code,1);self.assertEqual(len([c for c in calls if c[0]=='case']),1)
                self.assertIn('failed_child',result);self.assertFalse(result['passed'])

    def test_second_child_failure_retains_first_accepted_index(self):
        with tempfile.TemporaryDirectory() as directory:
            values=self.fixture(Path(directory));code,result,calls=self.execute(values,'second')
            self.assertEqual(code,1);self.assertEqual(len(result['children']),1)
            self.assertEqual(batch.sha(values[0].output/result['latest_index']),result['children'][0]['index_sha256'])
            self.assertIsNotNone(result['failed_child']['evidence']['supervision/result.json'])

    def test_source_review_pins_and_actual_window_are_not_boolean_bypasses(self):
        for change in ('source','window','prior','expiry','checker_review'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                values=self.fixture(Path(directory));args,grant=values[:2]
                if change=='source':(values[4]/'source_review.json').write_text('{}')
                if change=='checker_review':values[2]['checker']['source_review_sha256']='0'*64
                if change=='window':grant['execution_window_seconds']=13800;batch.write(args.admission,grant)
                if change=='prior':(args.prior/'science/index.json').write_text('{}')
                if change=='expiry':grant['expires_utc']='2099-01-02T00:00:00+00:00';batch.write(args.admission,grant)
                code,result,calls=self.execute(values);self.assertEqual(code,1);self.assertEqual(calls,[])

    def test_preparation_rechecks_whole_slot_before_science(self):
        with tempfile.TemporaryDirectory() as directory:
            values=self.fixture(Path(directory))
            with patch.object(batch,'timing',side_effect=[(0,0),ValueError('preparation exhausted window')]):
                code,result,calls=self.execute(values)
            self.assertEqual(code,1);self.assertEqual(calls,[])

    def test_changed_checker_core_or_misattributed_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            values=self.fixture(Path(directory));(values[4]/values[2]['checker']['core_path']).write_text('changed')
            code,result,calls=self.execute(values);self.assertEqual(code,1);self.assertEqual(calls,[])

    def test_supervisor_survivors_or_uncertainty_are_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for bad in ({'survivors_after_cleanup':[{'pid':123}]},{'cleanup_errors':['unknown']},{'returncode':1}):
                batch.write(root/'result.json',dict(status='passed',returncode=0,cleanup_errors=[],survivors_after_cleanup=[]))
                value=batch.read(root/'result.json');value.update(bad);batch.write(root/'result.json',value)
                with self.assertRaises(ValueError):batch.checked_supervision(root)


if __name__=='__main__':unittest.main()
