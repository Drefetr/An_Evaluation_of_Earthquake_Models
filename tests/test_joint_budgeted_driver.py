"""Invented artifact/process controls only; no native loading, fitting or scoring."""
import copy,hashlib,json,math,os,tempfile,time,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from experiments.s04b_joint_budgeted import driver as d


def report(root,name,passed=True):
    folder=root/'cases';folder.mkdir(exist_ok=True)
    trace=folder/(name+'.attempts.jsonl');trace.write_text('{"invented":true}\n')
    fits={m:dict(passed=True,required_starts=8,resolved_starts=[True]*8)for m in ('null',*d.frozen.MODELS)}
    value=dict(case_id=name,passed=passed,status='complete'if passed else'partial',training_selections_frozen=True,
        fits=fits,outcomes=[{}]*5,floor_checks=[{}]*6,historical_comparisons=[{}]*5,n_train=3,n_test=3,
        training_checks={m:{'passed':True}for m in fits},input_sha256={},attempts_sha256=d.sha(trace))
    path=folder/(name+'.json');d.write(path,value)
    entry=dict(case_id=name,file='cases/'+name+'.json',sha256=d.sha(path),trace='cases/'+name+'.attempts.jsonl',trace_sha256=d.sha(trace),reused_fit_arms=4 if name=='a'else 0,new_fit_arms=0 if name=='a'else 4)
    return entry,value


class Fixture:
    def __init__(self,root):
        self.root=root;self.package=root/'package';self.package.mkdir();self.oldhome=root/'oldhome';self.oldhome.mkdir()
        self.prior=root/'prior';self.prior.mkdir();self.sequence=list('abcdefg')
        self.cases=[dict(case_id=n,n_train=3,n_test=3)for n in self.sequence]
        self.op=dict(sequence=self.sequence,pilot=self.sequence[:5],science_protocol_sha256='science',original_failure={'prior_scientific_seconds':17.})
        d.write(self.oldhome/'operational_protocol.json',self.op)
        (self.package/'evidence').mkdir();d.write(self.package/'evidence/proposal.json',{'invented':True})
        entries=[report(self.prior,n)[0]for n in self.sequence[:5]]
        (self.prior/'attempts').mkdir();d.write(self.prior/'attempts/old.json',dict(attempt_id='old',phase='pilot',wall_seconds=3.,passed=True,status='batch_complete'))
        self.oldsource={'old.py':'invented-old-source'};self.newsource={'new.py':'invented-new-source'}
        self.runtime={'essential':{'invented_runtime':1}}
        self.index=dict(schema='joint_accepted_case_index_v1',source_sha256=self.oldsource,operational_protocol_sha256=d.sha(self.oldhome/'operational_protocol.json'),science_protocol_sha256='science',runtime=self.runtime,library_sha256='library',build_receipt_sha256='build',original_failure=self.op['original_failure'],cases=entries,attempts=[dict(attempt_id='old',phase='pilot',seconds=3.,file='attempts/old.json',sha256=d.sha(self.prior/'attempts/old.json'))],reviews=[],partial_case=None,budget=dict(total_seconds=20.,pilot_seconds=20.))
        resume=self.prior/'training_resume';resume.mkdir();(resume/'checkpoint').write_bytes(b'original invented partial training bytes')
        d.write(resume/'provenance.json',dict(checkpoint_sha256=d.sha(resume/'checkpoint'),evidence_files={'checkpoint_sha256':'training_resume/checkpoint'}))
        d.write(self.prior/'index.json',self.index);self.review=root/'review.json';d.write(self.review,dict(passed=True,index_sha256=d.sha(self.prior/'index.json')))
        self.policy=dict(predecessor=dict(accepted_index_sha256=d.sha(self.prior/'index.json'),accepted_review_sha256=d.sha(self.review),source_sha256=self.oldsource,operational_protocol_sha256=d.sha(self.oldhome/'operational_protocol.json'),already_charged_seconds=20.),scientific_protocol_sha256='science',sequence=self.sequence,transition_review_sha256='proposal-review',fixed_slots=[dict(case_id=n,wall_seconds=420,scientific_reservation_seconds=390,input={'case_id':n})for n in self.sequence[5:]],resources=dict(campaign_aggregate_seconds=115200),evidence_sha256={'evidence/proposal.json':d.sha(self.package/'evidence/proposal.json')})
        d.write(self.package/'allocation_protocol.json',self.policy)
        self.current=dict(source_sha256=self.newsource,allocation_protocol_sha256=d.sha(self.package/'allocation_protocol.json'),runtime=self.runtime,library_sha256='library',build_receipt_sha256='build')
        self.args=SimpleNamespace(prior_index=self.prior/'index.json',prior_review=self.review)
        self.admission=dict(prior_index_sha256=d.sha(self.args.prior_index),prior_review_sha256=d.sha(self.args.prior_review),transition_review_sha256='proposal-review',numerical_attempt_id='new',case_id='f',wall_seconds=420)

    def patch(self,stack):
        stack.enter_context(patch.object(d,'HERE',self.package));stack.enter_context(patch.object(d.legacy,'HERE',self.oldhome))
        stack.enter_context(patch.object(d.legacy,'source_identity',return_value=self.oldsource))

    def migrate(self,out):
        out.mkdir();return d.accepted_index(self.args,self.admission,self.policy,self.current,self.cases,out)

    def new_parent(self,index,out):
        d.write(out/'index.json',index);p=self.root/'newreview.json';d.write(p,dict(passed=True,index_sha256=d.sha(out/'index.json')))
        args=SimpleNamespace(prior_index=out/'index.json',prior_review=p)
        a={**self.admission,'prior_index_sha256':d.sha(args.prior_index),'prior_review_sha256':d.sha(p)}
        return args,a


class TransitionControls(unittest.TestCase):
    def test_real_protocol_source_pins_without_history_evaluation(self):
        value=d.verify_protocol();self.assertEqual(len(value['fixed_slots']),75)
        self.assertEqual(sum(s['wall_seconds']for s in value['fixed_slots']),109200)
        self.assertEqual(value['resources']['campaign_aggregate_seconds'],115200)

    def test_transition_calls_actual_old_identity_then_copies_every_bound_byte(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);out=f.root/'transitioned'
            original=d.legacy.accepted_index
            with patch.object(d.legacy,'accepted_index',wraps=original)as old:
                index=f.migrate(out)
            self.assertEqual(old.call_args.args[3]['source_sha256'],f.oldsource)
            self.assertEqual(index['source_sha256'],f.newsource);self.assertEqual(index['schema'],d.SCHEMA)
            self.assertNotIn('operational_protocol_sha256',index)
            for entry in f.index['cases']:
                for key in ('file','trace'):self.assertEqual((f.prior/entry[key]).read_bytes(),(out/entry[key]).read_bytes())
            self.assertEqual((out/'transition/predecessor_index.json').read_bytes(),(f.prior/'index.json').read_bytes())
            self.assertEqual((out/'training_resume/checkpoint').read_bytes(),(f.prior/'training_resume/checkpoint').read_bytes())
            self.assertEqual(d.legacy.charged(index,f.op),(20.,20.));self.assertEqual(index['transition']['old_projection_status'],'failed')

    def test_new_index_prefix_reuse_copies_transition_and_never_invokes_case(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);first=f.root/'one';index=f.migrate(first)
            args,a=f.new_parent(index,first);second=f.root/'two';second.mkdir()
            with patch.object(d.legacy,'runner_with_scheduler')as runner:
                new=d.accepted_index(args,a,f.policy,f.current,f.cases,second)
            runner.assert_not_called();self.assertEqual(new['transition'],index['transition'])
            for name in index['transition']['files']:self.assertEqual((first/name).read_bytes(),(second/name).read_bytes())
            self.assertEqual(new['cases'],index['cases']);self.assertEqual(len(new['reviews']),2)

    def test_source_runtime_native_schema_and_protocol_tampering_rejected(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);first=f.root/'one';base=f.migrate(first)
            changes=[('source_sha256',{}),('runtime',{'essential':{'wrong':1}}),('library_sha256','wrong'),('build_receipt_sha256','wrong'),('allocation_protocol_sha256','wrong'),('science_protocol_sha256','wrong'),('schema','unknown')]
            for number,(key,value)in enumerate(changes):
                index=copy.deepcopy(base);index[key]=value;args,a=f.new_parent(index,first);out=f.root/str(number);out.mkdir()
                with self.subTest(key=key),self.assertRaises(ValueError):d.accepted_index(args,a,f.policy,f.current,f.cases,out)

    def test_transition_artifact_and_case_trace_corruption_rejected(self):
        for name in ('transition/evidence/proposal.json','cases/a.attempts.jsonl','training_resume/checkpoint'):
            with self.subTest(name=name),tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
                f=Fixture(Path(temp));f.patch(stack);first=f.root/'one';index=f.migrate(first);args,a=f.new_parent(index,first)
                (first/name).write_bytes(b'changed');out=f.root/'two';out.mkdir()
                with self.assertRaises(ValueError):d.accepted_index(args,a,f.policy,f.current,f.cases,out)

    def test_partial_or_failed_index_blocks_even_after_review(self):
        for key,value in [('partial_case',{'case_id':'f'}),('last_attempt_passed',False)]:
            with self.subTest(key=key),tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
                f=Fixture(Path(temp));f.patch(stack);first=f.root/'one';index=f.migrate(first);index[key]=value
                args,a=f.new_parent(index,first);out=f.root/'two';out.mkdir()
                with self.assertRaisesRegex(ValueError,'Failed/partial'):d.accepted_index(args,a,f.policy,f.current,f.cases,out)

    def test_only_pinned_old_index_and_transition_review_are_eligible(self):
        for field in ('prior_index_sha256','transition_review_sha256'):
            with self.subTest(field=field),tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
                f=Fixture(Path(temp));f.patch(stack);f.admission[field]='wrong'
                with self.assertRaises(ValueError):f.migrate(f.root/'out')


class AllocationControls(unittest.TestCase):
    def test_fixed_order_caps_duplicate_and_input_identity(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);index=f.migrate(f.root/'one')
            slot,cost=d.allocation(index,f.policy,f.admission,f.cases)
            self.assertEqual(slot['case_id'],'f');self.assertEqual(cost['maximum_future_charge'],860.)
            for change in ({'case_id':'g'},{'case_id':'e'},{'wall_seconds':421},{'wall_seconds':419},{'numerical_attempt_id':'old'}):
                with self.subTest(change=change),self.assertRaises(ValueError):d.allocation(index,f.policy,{**f.admission,**change},f.cases)
            corrupt=copy.deepcopy(index);corrupt['cases'][0],corrupt['cases'][1]=corrupt['cases'][1],corrupt['cases'][0]
            with self.assertRaises(ValueError):d.allocation(corrupt,f.policy,f.admission,f.cases)
            changed=copy.deepcopy(f.policy);changed['fixed_slots'][0]['input']['n_train']=4
            with self.assertRaisesRegex(ValueError,'input'):d.allocation(index,changed,f.admission,f.cases)

    def test_all_unspent_slots_fit_and_no_implicit_inflation(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);index=f.migrate(f.root/'one')
            policy=copy.deepcopy(f.policy);policy['resources']['campaign_aggregate_seconds']=859.999
            with self.assertRaisesRegex(ValueError,'unspent'):d.allocation(index,policy,f.admission,f.cases)
            index['attempts'].append(copy.deepcopy(index['attempts'][0]))
            with self.assertRaisesRegex(ValueError,'Duplicate'):d.allocation(index,f.policy,f.admission,f.cases)


class PersistenceControls(unittest.TestCase):
    def persist(self,f,index,out,late=False,active=None):
        grant={**f.admission,'_path':str(f.root/'admission.json')};d.write(grant['_path'],f.admission)
        result=dict(passed=True,status='batch_complete',cases=[],scientific_completion=False)
        original=d.write;now={'value':1.}
        def output(path,value):
            original(path,value)
            if Path(path).name=='result.json'and late:now['value']=3.
        with patch.object(d,'write',side_effect=output),patch.object(d.time,'monotonic',side_effect=lambda:now['value']):
            d.persist_attempt(out,index,result,grant,f.policy,f.current,0.,2.,active)
        return d.read(out/'result.json'),d.read(out/'index.json')

    def test_final_serialization_expiry_rewrites_pass_and_charge_truthfully(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);out=f.root/'one';index=f.migrate(out)
            result,index=self.persist(f,index,out,late=True)
            self.assertFalse(result['passed']);self.assertFalse(index['last_attempt_passed'])
            self.assertEqual(result['error_type'],'FinalizationDeadline');self.assertEqual(index['budget']['total_seconds'],23.)
            self.assertFalse(d.read(out/'attempts/new.json')['passed'])
            self.assertEqual(result['index_sha256'],d.sha(out/'index.json'))

    def test_partial_checkpoint_kept_and_unknown_is_not_zero(self):
        with tempfile.TemporaryDirectory()as temp,ExitStack()as stack:
            f=Fixture(Path(temp));f.patch(stack);out=f.root/'one';index=f.migrate(out)
            report(out,'f',False);result,index=self.persist(f,index,out,active='f')
            self.assertEqual(index['partial_case']['case_id'],'f');self.assertEqual(len(index['cases']),5)
            self.assertEqual(result['partial_fit_checkpoint']['recorded_fit_arms'],4)
            self.assertFalse(result['passed']);self.assertFalse(index['last_attempt_passed'])
            self.assertTrue((out/'cases/f.json').exists())


class AdmissionControls(unittest.TestCase):
    def test_exact_source_runtime_native_and_external_cap_contract(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);library=root/'native';library.write_bytes(b'invented library; never loaded')
            build=root/'build.json';d.write(build,dict(passed=True,source_sha256=d.sha(d.legacy.SCIENCE/'attenuation.cpp'),library_sha256=d.sha(library)))
            runtime={'essential':{'fixture':True}}
            current=dict(source_sha256={'fixture':'pin'},allocation_protocol_sha256='allocation',runtime=runtime,library_sha256=d.sha(library),build_receipt_sha256=d.sha(build))
            policy=dict(predecessor={**current,'runtime_essential':runtime['essential']},resources=dict(batch_wall_seconds=14400,sampled_process_tree_rss_cap_bytes=6442450944))
            grant=dict(mode='budgeted_campaign',independent_review_passed=True,scheduler_review_passed=True,external_supervision=True,source_sha256=current['source_sha256'],allocation_protocol_sha256='allocation',expires_utc='2099-01-01T00:00:00+00:00',lease_token_sha256=hashlib.sha256(b'fixture').hexdigest(),threads=2,workers=1,sampled_process_tree_rss_cap_bytes=6442450944,library_sha256=d.sha(library),build_receipt_sha256=d.sha(build),numerical_attempt_id='fixture-id',wall_seconds=420,case_id='f',case_ids=['f'])
            args=SimpleNamespace(admission=root/'admission.json',library=library,build_receipt=build)
            with patch.dict(os.environ,{'JOINT_NUMERICAL_LEASE_TOKEN':'fixture'}):
                d.write(args.admission,grant);self.assertEqual(d.check_admission(args,policy,current),grant)
                for field,value in [('mode','campaign'),('source_sha256',{}),('allocation_protocol_sha256','wrong'),('external_supervision',False),('library_sha256','wrong'),('build_receipt_sha256','wrong'),('threads',3),('wall_seconds',True),('wall_seconds',14401),('case_ids',['g']),('lease_token_sha256','wrong')]:
                    with self.subTest(field=field):
                        d.write(args.admission,{**grant,field:value})
                        with self.assertRaises(ValueError):d.check_admission(args,policy,current)
                d.write(args.admission,grant)
                with self.assertRaisesRegex(ValueError,'runtime'):d.check_admission(args,policy,{**current,'runtime':{'essential':{'fixture':False}}})


class BatchControls(unittest.TestCase):
    def exercise(self,temp,fail=False,late=False):
        f=Fixture(Path(temp));out=f.root/'out';lib=f.root/'library';build=f.root/'build';lib.write_bytes(b'invented');build.write_bytes(b'invented')
        args=SimpleNamespace(**vars(f.args),output=out,library=lib,build_receipt=build,admission=f.root/'admission.json')
        grant={**f.admission,'expires_utc':'2099-01-01T00:00:00+00:00'};d.write(args.admission,grant);calls=[]
        def fake(case,modules,native,science,destination,deadline,resume):
            calls.append((case['case_id'],resume,deadline));entry,value=report(destination.parent,case['case_id'],not fail)
            if late:raise KeyboardInterrupt('invented interrupted fit')
            return value
        with ExitStack()as stack:
            f.patch(stack);stack.enter_context(patch.object(d,'verify_protocol',return_value=f.policy))
            stack.enter_context(patch.object(d,'source_identity',return_value=f.newsource))
            stack.enter_context(patch.object(d,'check_admission',return_value=grant))
            stack.enter_context(patch.object(d.frozen,'runtime_identity',return_value=f.runtime))
            stack.enter_context(patch.object(d.frozen,'verify_inputs',return_value=f.cases))
            stack.enter_context(patch.object(d.model,'archived',return_value={}))
            stack.enter_context(patch.object(d.model,'Native',return_value=object()))
            stack.enter_context(patch.object(d.legacy,'runner_with_scheduler',return_value=SimpleNamespace(case_run=fake)))
            current=copy.deepcopy(f.current);current['library_sha256']=d.sha(lib);current['build_receipt_sha256']=d.sha(build)
            # This fixture changes only invented native identities consistently in the old index.
            f.index['library_sha256']=current['library_sha256'];f.index['build_receipt_sha256']=current['build_receipt_sha256']
            d.write(f.prior/'index.json',f.index);d.write(f.review,dict(passed=True,index_sha256=d.sha(f.prior/'index.json')))
            f.policy['predecessor'].update(accepted_index_sha256=d.sha(f.prior/'index.json'),accepted_review_sha256=d.sha(f.review))
            grant.update(prior_index_sha256=d.sha(f.prior/'index.json'),prior_review_sha256=d.sha(f.review));d.write(args.admission,grant)
            code=d.run(args,started=time.monotonic())
        return code,out,calls,f

    def test_one_case_delegate_no_completed_fit_repetition(self):
        with tempfile.TemporaryDirectory()as temp:
            code,out,calls,f=self.exercise(temp);self.assertEqual(code,0,d.read(out/'result.json'))
            self.assertEqual(len(calls),1);self.assertEqual(calls[0][:2],('f',None))
            self.assertEqual((out/'cases/a.json').read_bytes(),(f.prior/'cases/a.json').read_bytes())
            result=d.read(out/'result.json');self.assertEqual([e['case_id']for e in result['cases']],['f'])
            self.assertEqual(result['complete_cases'],6);self.assertFalse(result['scientific_completion'])
            self.assertEqual(result['status'],'batch_complete');self.assertEqual(result['old_projection_status'],'failed')

    def test_failed_and_interrupted_cases_retained_and_charged(self):
        for fail,late in ((True,False),(False,True)):
            with self.subTest(fail=fail,late=late),tempfile.TemporaryDirectory()as temp:
                code,out,calls,f=self.exercise(temp,fail,late);self.assertEqual(code,1)
                index=d.read(out/'index.json');self.assertEqual(len(index['cases']),5)
                self.assertEqual(index['partial_case']['case_id'],'f');self.assertFalse(index['last_attempt_passed'])
                self.assertGreater(index['budget']['total_seconds'],20.);self.assertEqual(len(calls),1)
                self.assertFalse(d.read(out/'result.json')['scientific_completion'])


if __name__=='__main__':unittest.main()
