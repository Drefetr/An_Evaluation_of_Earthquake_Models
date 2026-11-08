"""Invented trust roots and saved numbers; no model/native/optimizer evaluation.

The integration controls run the real public reader's output assembly and bridge
append into the real independent auditor. Only the numerical runner/adapter
boundary supplies invented saved output. No audit function is mocked.
"""
import copy
from contextlib import ExitStack, nullcontext
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value

A = module('reader_independent_audit_tested', ROOT/'experiments/s04b_refined_cpu_reader_audit/check.py')
F = module('reader_saved_campaign_fixture', ROOT/'tests/test_joint_exposure_refinement_audit.py')
from experiments.s04b_refined_cpu_reader import reader as reader
from experiments import s04b_refined_cpu_reader as metadata
from experiments.s04b_refined_cpu_bridge import contract, host as bridge


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def replace(value, old, new):
    if isinstance(value, dict):
        return {k: replace(v, old, new) for k, v in value.items()}
    if isinstance(value, list):
        return [replace(v, old, new) for v in value]
    return new if value == old else value


class InventedReaderCampaign(F.InventedSavedCampaign):
    def __init__(self, directory):
        super().__init__(directory)
        # Explicit invented authorities extend the existing custody fixture.
        # The real source/profile contract is exercised against these bytes.
        real_policy = A.read(ROOT/A.frozen.PROTOCOL_PATH)
        self.resources.update(future_hosts=copy.deepcopy(real_policy['resources']['future_hosts']),
            original_case_outer_cap_seconds=2520, original_case_scientific_cap_seconds=2490)
        self.policy.update(resources=self.resources, partial_case_id=A.frozen.PARTIAL)
        design = A.read(self.design_dir/'protocol_proposal.json')
        # An ELF-shaped byte fixture satisfies extraction metadata only. Native()
        # remains replaced below; these bytes can never execute as a library.
        self.native = b'\x7fELF\x02\x01'+bytes(12)+b'\x3e\x00'+b'invented; never loaded'
        self.build['library_sha256'] = A.frozen.hash_bytes(self.native)
        self.build_raw = (json.dumps(self.build,indent=2)+'\n').encode()
        self.native_meta.update(library_sha256=A.frozen.hash_bytes(self.native),
            build_receipt_sha256=A.frozen.hash_bytes(self.build_raw),
            runtime_essential=dict(numpy='2.2.6',scipy='1.15.3',fixture='not executed'))
        self.policy['original_native'] = self.native_meta
        design['unchanged']['native'] = self.native_meta
        archive = self.repo/self.policy['base']['archive']
        old_pin = A.sha(archive)
        self.members.update({'native/library.so':self.native, 'native/build.json':self.build_raw})
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as saved:
            for name, raw in self.members.items(): saved.writestr(name, raw)
        new_pin = A.sha(archive)
        self.policy = replace(self.policy, old_pin, new_pin)
        design = replace(design, old_pin, new_pin)
        review_path = self.repo/self.policy['base']['review']
        old_review_pin = A.sha(review_path)
        review = A.read(review_path); review.update(artifact_sha256=new_pin, archive_sha256=new_pin)
        dump(review_path, review)
        self.policy = replace(self.policy, old_review_pin, A.sha(review_path))
        design = replace(design, old_review_pin, A.sha(review_path))
        extra = dict(review=self.policy['base']['review'], review_sha256=A.sha(review_path),
                     library_member='native/library.so', build_receipt_member='native/build.json')
        self.policy['permanent_unknown'].update(extra)
        design['reuse']['permanent_unknown'].update(extra)
        self.unknown_ref = self.policy['permanent_unknown']
        dump(self.design_dir/'protocol_proposal.json', design)
        dump(self.design_dir/'resources.json', self.resources)
        self.design_pins = {name:A.sha(self.design_dir/name) for name in A.frozen.DESIGN_PINS}
        self.policy['design_evidence_sha256'] = {A.frozen.DESIGN+name:pin for name,pin in self.design_pins.items()}
        dump(self.repo/A.frozen.PROTOCOL_PATH, self.policy)
        self.protocol_sha = A.sha(self.repo/A.frozen.PROTOCOL_PATH)
        self.profile = A.read(ROOT/A.PROFILE)
        # Copy every real reader/bridge/audit source, including the focused tests.
        for name in self.profile['producer_source_paths']:
            target = self.repo/name; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        self.core = A.expected_core(self.repo, self.policy)
        self.host_map = self.source_map = self.core
        self.profile.update(core_source_sha256=self.core,
            amendment_protocol=dict(path=A.frozen.PROTOCOL_PATH, sha256=self.protocol_sha),
            scientific_protocol=dict(path=A.frozen.SCIENCE_PATH, sha256=self.science_sha),
            bundled_native=dict(archive_reference=dict(path=self.policy['base']['archive'], sha256=new_pin),
                review_reference=dict(path=self.policy['base']['review'], sha256=A.sha(review_path)),
                library_member='native/library.so', build_receipt_member='native/build.json',
                library_sha256=self.native_meta['library_sha256'], build_receipt_sha256=self.native_meta['build_receipt_sha256']))
        dump(self.repo/A.PROFILE, self.profile)
        self.reports = {}
        for name in self.sequence[46:51]:
            report = self.make_report(name); self.add_historical_inputs(report); self.reports[name] = report
        dump(self.repo/'reproduction/synthetic/input_manifest.json', {'s04b':{'cases':self.manifest}})
        self.graph = {**self.core, **{name:A.sha(self.repo/name) for name in self.profile['producer_source_paths']}}
        for command in (['git','-c','core.autocrlf=false','add','.'],
                        ['git','-c','user.name=Invented fixture','-c','user.email=fixture@example.invalid',
                         '-c','commit.gpgsign=false','commit','-m','Invented actual-reader interface fixture']):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True)
        self.commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=self.repo, text=True).strip()
        dump(self.repo/self.review_rel, dict(passed=True, live_agent_review=True, live_agent_review_performed=True,
             final_batch_agent_review_required=False, reviewed_files_sha256=self.graph))
        self.review_sha = A.sha(self.repo/self.review_rel)
        self.reference = dict(path=self.review_rel, sha256=self.review_sha)
        with patch.object(metadata, 'REPO', self.repo): self.producer = metadata.producer(self.reference)
        first = self.build_child()
        first_review = self.root/'invented_partial_review.json'
        dump(first_review, dict(index_sha256=A.sha(first[0]/'index.json')))
        second = self.build_child(True, first[0]/'index.json', first_review)
        self.prior = second[0]/'index.json'
        self.prior_review = self.root/'invented_host2_live_review.json'
        dump(self.prior_review, dict(passed=True, audit_passed=True, scientific_completion=False,
             review_kind='live_agent_saved_output_review', live_agent_review=True, live_agent_review_performed=True,
             final_batch_agent_review_required=False, index_sha256=A.sha(self.prior), artifact_sha256='2'*64))
        self.host = self.root/'reader_host3/host'; self.host.mkdir(parents=True)
        group = self.resources['future_hosts'][2]
        self.grant = dict(mode='exposure_refinement_host_batch', batch_id=3, case_ids=group['case_ids'],
            child_attempt_ids={name:'invented-reader-'+str(i) for i,name in enumerate(group['case_ids'])},
            numerical_attempt_id='invented-reader-host3', protocol_sha256=self.protocol_sha,
            source_sha256=self.core, scientific_source_sha256=self.core, reader_source_review=self.reference,
            execution_producer=self.producer, reviewed_files_sha256=self.graph,
            source_review_sha256=self.review_sha, checker_source_review_sha256=self.review_sha,
            prior_index_sha256=A.sha(self.prior), prior_review_sha256=A.sha(self.prior_review), prior_archive_sha256='2'*64,
            shared_run=self.shared, expires_utc=self.shared['expires_utc'],
            rss_cap_bytes=6442450944, host_headroom_bytes=2147483648,
            lease_token_sha256=A.frozen.hash_bytes(b'invented-lease'),
            library_sha256=self.native_meta['library_sha256'], build_receipt_sha256=self.native_meta['build_receipt_sha256'])
        dump(self.host.parent/'admission.json', self.grant)

    def patches(self):
        stack = super().patches()
        stack.enter_context(patch.object(A.frozen, 'DESIGN_PINS', self.design_pins))
        stack.enter_context(patch.object(A.frozen, 'SCIENCE_SHA', self.science_sha))
        return stack

    def mathematical_boundary(self, report):
        """Construct saved counters, without calling any numerical routine."""
        counts, calls, keys = {}, [], []
        def add(phase, model, order, context, n, gradient=True):
            if n:
                key = f'{phase}|{model}|{order}|{context}|{gradient}'
                prior = counts.setdefault(key, dict(attempted=0, returned=0, errors=0))
                prior['attempted'] += n; prior['returned'] += n
        for model, fit in report['fits'].items():
            for row in fit['records']:
                method = row['method']; n = row['nfev']; keys.append([model, row['start_index'], method])
                add('train', model, 8, 'optimizer', n, method=='L-BFGS-B')
                options = ({k:self.science['solver'][k] for k in ('maxiter','maxls','ftol','gtol')}
                           if method=='L-BFGS-B' else self.science['solver']['powell'])
                calls += [dict(event='optimizer_start', model=model, start_index=row['start_index'], method=method,
                    initial_parameters=row['initial_parameters'], bounds=self.science['shared_bounds']+([] if model=='null' else self.science['inhibition_bounds']),
                    options=options, jac=method=='L-BFGS-B'),
                    dict(event='optimizer_end', model=model, start_index=row['start_index'], method=method,
                         returned=True, callback_attempts=n, callback_returns=n, evaluation_census=copy.deepcopy(counts))]
        add('train','null',8,'original_support',1)
        for model, fit in report['fits'].items():
            add('train',model,8,'original_support',1+sum(r.get('finite_feasible') is True for r in fit['records'])+
                (1 if model in report['training_checks'] else 0))
            if model in report['training_checks']: add('train',model,16,'original_support',1)
        if report['passed']:
            for model in A.ARMS:
                add('test',model,8,'original_support',1); add('test',model,16,'original_support',1)
        phases = [dict(start=30,end=395,returned=True)]+([dict(start=395,end=760,returned=True)] if report['passed'] else [])
        receipt = dict(arm_calls=list(report['fits']), selected_check_calls=list(report['training_checks']),
            physical_optimizer_calls=keys, evaluation_census=counts, refinement_started=0, refinement_accepted=0,
            refinement_rejected=0, reuse_entries=[], phase_constructions=phases, callback_active=False, refinement_active=False)
        return calls, receipt

    def build_reader(self, position=0, unknown=False, prior=None, prior_review=None):
        from experiments.s04b_joint_execution import driver as legacy
        from experiments.s04b_exposure_refinement import adapter
        from experiments.s04b_exposure_refinement import case_driver as dated
        name = self.grant['case_ids'][position]
        current = self.host/'children'/f'{position+1:02}_{name}'; output = current/'science'; output.mkdir(parents=True)
        slot = next(s for s in self.policy['case_slots'] if s['case_id']==name)
        report = copy.deepcopy(self.reports[name])
        if unknown:
            report = F.U.unknown_fixture()[1]
            report.update({k:self.reports[name][k] for k in ('case_id','regime','seed','input_sha256','stratum')})
        report.update(current_attempt_wall_seconds=2., wall_seconds=2., prior_training_attempt_seconds=0.)
        calls, receipt = self.mathematical_boundary(report)
        case = next(c for c in self.manifest if c['case_id']==name)
        with patch.object(metadata,'REPO',self.repo):
            admission = contract.child_admission(self.grant,self.policy,name,slot)
        dump(current/'admission.json',admission)
        dump(current/'conductor_review.json',dict(source_review=self.review_rel,source_review_sha256=self.review_sha,
             host_source_review_sha256=self.review_sha,reviewed_files_sha256=self.graph))
        remote = '/invented/artifact/host/children/'+current.name
        old_command = [sys.executable,'-B','-m','experiments.s04b_exposure_refinement.case_driver',
            '--mode','untouched','--case-id',name,'--library','/unused','--build-receipt','/unused',
            '--admission',remote+'/admission.json','--output',remote+'/science']
        with patch.object(contract,'REPO',Path('/invented/checkout')):
            command = bridge.reader_command(old_command,slot['wall_seconds'])
        # Windows Path prints backslashes; the retained target run is Linux.
        command[2] = command[2].replace('\\','/')
        spec = dict(command=command,cwd='/invented/checkout',wall_cap_seconds=slot['wall_seconds'],
            rss_cap_bytes=6442450944,host_headroom_bytes=2147483648,env={k:'2' for k in reader.THREAD_ENV})
        dump(current/'supervisor_spec.json',spec)
        request = dict(schema='joint_refined_cpu_request_v1',mode='author_envelope',case_id=name,
            output=remote+'/science',wall_seconds=slot['wall_seconds'],scientific_seconds=slot['scientific_seconds'],
            rss_cap_bytes=6442450944,headroom_bytes=2147483648,threads=2,workers=1,started_monotonic=0.,
            created_utc='2029-01-01T00:00:00+00:00',attempt_id='invented-request',source_sha256=self.graph,
            execution_producer=self.producer,actual_command=command,execution_record=remote+'/admission.json',
            execution_record_sha256=A.sha(current/'admission.json'),verification_kind='automated_local_integrity',
            live_agent_review=False,scientific_completion=False)
        dump(output/'reader_request.json',request)
        def case_run(*args):
            (output/'refinement_events.jsonl').write_bytes(b'')
            (output/'execution_calls.jsonl').write_bytes(''.join(json.dumps(r)+'\n' for r in calls).encode())
            trace = F.trace_bytes(report)
            (output/'cases'/(name+'.attempts.jsonl')).write_bytes(trace)
            dump(output/'cases'/(name+'.json'),report)
            return report
        fake = SimpleNamespace(reuse_entries=[],phase_constructions=receipt['phase_constructions'],
            receipt=lambda:receipt,wrap_phase=None,fit_arm=None,fine_check=None,historical_floor=None)
        runner = SimpleNamespace(model=SimpleNamespace(phase_from_rows=None),historical_floor=None,case_run=case_run)
        def recorded_path(value):
            # Simulate the retained Linux mount on the test machine; argv and
            # request bytes remain the actual bridge command throughout.
            return current/'admission.json' if str(value)==remote+'/admission.json' else Path(value)
        with ExitStack() as stack:
            stack.enter_context(patch.object(metadata,'REPO',self.repo))
            stack.enter_context(patch.object(reader,'REPO',self.repo))
            stack.enter_context(patch.object(reader,'Path',side_effect=recorded_path))
            stack.enter_context(patch.object(reader,'platform_check'))
            stack.enter_context(patch.object(reader.time,'monotonic',return_value=3.))
            stack.enter_context(patch.dict(os.environ,{'JOINT_NUMERICAL_LEASE_TOKEN':'invented-lease'}))
            stack.enter_context(patch.object(dated,'verify_protocol',return_value=self.policy))
            stack.enter_context(patch.object(legacy,'verify_protocol'))
            stack.enter_context(patch.object(legacy.frozen,'runtime_identity',return_value={'essential':self.native_meta['runtime_essential']}))
            stack.enter_context(patch.object(legacy,'REPO',self.repo))
            stack.enter_context(patch.object(legacy,'SCIENCE',self.repo/'experiments/s04b_joint_nuisance'))
            stack.enter_context(patch.object(legacy.frozen,'verify_inputs',return_value=[case]))
            stack.enter_context(patch.object(legacy.model,'archived',return_value=None))
            stack.enter_context(patch.object(legacy.model,'Native',return_value=None))
            stack.enter_context(patch.object(legacy,'OrderedChunkScheduler',return_value=nullcontext()))
            stack.enter_context(patch.object(legacy,'runner_with_scheduler',return_value=runner))
            stack.enter_context(patch.object(adapter,'Adapter',return_value=fake))
            code = reader.worker(request,output)
        actual = A.read(output/'result.json')
        if code: raise AssertionError(actual)
        if not actual['handled']: raise AssertionError(actual)
        (current/'supervision').mkdir();(current/'supervision/execution.log').write_bytes(b'')
        dump(current/'supervision/result.json',dict(status='passed',returncode=0,launched=True,stop_reason=None,
            cleanup_errors=[],survivors_after_cleanup=[],spec_sha256=A.sha(current/'supervisor_spec.json'),
            execution_log_sha256=A.sha(current/'supervision/execution.log'),supervisor_sha256=A.sha(self.repo/'scripts/supervise_research.py'),
            started_utc='2029-01-01T00:00:00+00:00',finished_utc='2029-01-01T00:00:04+00:00',
            execution_wall_seconds=3.2,wall_seconds_including_cleanup=3.3,sampled_peak_tree_rss_bytes=1024,
            minimum_sampled_host_available_bytes=9999999999))
        prior, prior_review = prior or self.prior, prior_review or self.prior_review
        with patch.object(metadata,'REPO',self.repo):
            index = contract.append_candidate(self.policy,self.grant,A.read(prior),current,self.host,prior,prior_review,A.old.projection)
        dump(current/'index.json',index)
        return current,prior,prior_review

    def check(self, paths, output):
        current,prior,review = paths
        args = ['--repo',str(self.repo),'--current',str(current),'--prior',str(prior),'--prior-review',str(review),
            '--config',str(self.config),'--commit',self.commit,'--output',str(output),
            '--checker-source-review',str(self.repo/self.review_rel),'--checker-source-review-sha256',self.review_sha]
        with self.patches(): return A.main(args)


class ActualReaderInterface(unittest.TestCase):
    def test_real_assembly_append_and_independent_complete_then_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = InventedReaderCampaign(temp)
            first = fixture.build_reader(); review = Path(temp)/'reader_first_review.json'
            self.assertEqual(fixture.check(first,review),0,A.read(review))
            accepted = A.read(review)
            contract.check_receipt(review,first[0]/'index.json',accepted['checker_sources_sha256'],fixture.review_sha)
            self.assertEqual(accepted['execution_producer'],fixture.producer)
            self.assertEqual(set(accepted['checker_sources_sha256']),set(contract.CHECKER_FILES))
            self.assertFalse(accepted['scientific_completion']);self.assertFalse(accepted['live_agent_review'])
            second = fixture.build_reader(1,True,first[0]/'index.json',review)
            next_review = Path(temp)/'reader_second_review.json'
            self.assertEqual(fixture.check(second,next_review),0,A.read(next_review))
            contract.check_receipt(next_review,second[0]/'index.json',A.read(next_review)['checker_sources_sha256'],fixture.review_sha)
            final = A.read(second[0]/'index.json')
            self.assertEqual(final['records'][:-2],A.read(fixture.prior)['records'])
            self.assertEqual(final['records'][-1]['outcomes'],[])
            self.assertEqual(A.read(next_review)['refinement_and_reuse_census']['reused_optimizer_attempts'],0)

    def test_repinned_actual_command_and_mode_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = InventedReaderCampaign(temp); paths = fixture.build_reader(); current = paths[0]
            result_path = current/'science/result.json'; original = A.read(result_path)
            mutations = [lambda r:r.update(execution_mode='fresh_local'),
                         lambda r:r['actual_command'].__setitem__(2,A.ENTRYPOINT),
                         lambda r:r.update(reader_request_sha256='0'*64),
                         lambda r:r.update(reused_optimizer_attempts=28)]
            for i,mutate in enumerate(mutations):
                value = copy.deepcopy(original);mutate(value);dump(result_path,value);fixture.repin(current)
                target = Path(temp)/f'rejected_{i}.json'
                self.assertEqual(fixture.check(paths,target),1,(i,A.read(target)))
                self.assertFalse(A.read(target)['audit_passed'])
            dump(result_path,original)
            # Even fully consistent hashes/requests cannot replace the genuine
            # absolute bridge entrypoint with a plausible relative command.
            spec_path=current/'supervisor_spec.json';spec=A.read(spec_path)
            spec['command'][2]=A.ENTRYPOINT;dump(spec_path,spec)
            request_path=current/'science/reader_request.json';request=A.read(request_path)
            request['actual_command']=spec['command'];dump(request_path,request)
            original.update(actual_command=spec['command'],reader_request_sha256=A.sha(request_path));dump(result_path,original)
            supervisor_path=current/'supervision/result.json';supervisor=A.read(supervisor_path)
            supervisor['spec_sha256']=A.sha(spec_path);dump(supervisor_path,supervisor);fixture.repin(current)
            rejected=Path(temp)/'relative_command.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('absolute public entrypoint',A.read(rejected)['error'])

    def test_repinned_prefix_group_and_native_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = InventedReaderCampaign(temp);paths=fixture.build_reader();current=paths[0]
            original=A.read(current/'index.json')
            changed=copy.deepcopy(original);changed['records'][0]['scientific_passed']=False
            dump(current/'index.json',changed)
            rejected=Path(temp)/'prefix.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('prior prefix',A.read(rejected)['error'])
            dump(current/'index.json',original)
            grant=copy.deepcopy(fixture.grant);grant['batch_id']=4;dump(fixture.host.parent/'admission.json',grant)
            rejected=Path(temp)/'group.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('group is ineligible',A.read(rejected)['error'])
            dump(fixture.host.parent/'admission.json',fixture.grant)
            (current/'science/native/attenuation.so').write_bytes(b'changed')
            rejected=Path(temp)/'native.json';self.assertEqual(fixture.check(paths,rejected),1)
            self.assertIn('native bytes',A.read(rejected)['error'])

    def test_full_graph_review_cannot_omit_actual_checker_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=InventedReaderCampaign(temp)
            review=A.read(fixture.repo/fixture.review_rel)
            review['reviewed_files_sha256'].pop('experiments/s04b_joint_nuisance_audit/audit.py')
            dump(fixture.repo/fixture.review_rel,review)
            with fixture.patches(),self.assertRaisesRegex(ValueError,'source graph'):
                A.load_contract(fixture.repo,fixture.repo/fixture.review_rel,A.sha(fixture.repo/fixture.review_rel))


if __name__ == '__main__': unittest.main()
