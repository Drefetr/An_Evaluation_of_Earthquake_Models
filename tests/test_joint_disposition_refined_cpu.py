"""Invented mixed old/amended/public-reader reporting; no scientific execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import build_joint_disposition_report as B, render_joint_disposition_results as R
from tests.test_joint_disposition_reporting import data, write
from tests.test_joint_disposition_refinement import AmendedEvidence


class ReaderEvidence(AmendedEvidence):
    def __init__(self,root,extra_unknown=False,omit_source=None):
        super().__init__(root,extra_unknown=extra_unknown)
        self.reader_ids=self.sequence[-5:] if extra_unknown else self.sequence[46:51]
        self.omit_source=omit_source
        self.reader()

    def reader(self):
        policy=B.read(self.repo/B.AMENDMENT);original=policy['permanent_unknown']
        paths=sorted(B.READER_SOURCES-{self.omit_source})
        for name in paths:
            target=self.repo/name
            if name!=B.READER_PROFILE and not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'# invented producer source; never imported\n')
        self.profile=dict(schema='joint_refined_cpu_reader_profile_v1',version='public_refined_cpu_v1',operation='fit',
            entrypoint=B.READER_ENTRYPOINT,numerical_version=policy['version'],core_source_sha256=self.new_sources,
            producer_source_paths=paths,case_ids=self.sequence,
            amendment_protocol=self.registry['numerical_amendment']['protocol'],
            scientific_protocol={'path':B.SCIENCE,'sha256':B.sha(self.repo/B.SCIENCE)},
            bundled_native=dict(archive_reference={'path':original['archive'],'sha256':original['archive_sha256']},
                review_reference={'path':original['review'],'sha256':original['review_sha256']},
                library_member='build/attenuation.so',build_receipt_member='build/build_receipt.json',
                library_sha256=self.native['library_sha256'],build_receipt_sha256=self.native['build_receipt_sha256']))
        write(self.repo/B.READER_PROFILE,self.profile)
        extra={path:B.sha(self.repo/path) for path in paths};full=dict(self.new_sources,**extra)
        source_path=self.base+'reader_source_review.json'
        write(self.repo/source_path,dict(passed=True,live_agent_review=True,reviewed_files_sha256=full))
        refs=dict(profile={'path':B.READER_PROFILE,'sha256':B.sha(self.repo/B.READER_PROFILE)},
                  source_review={'path':source_path,'sha256':B.sha(self.repo/source_path)})
        self.producer=dict(schema='joint_refined_cpu_producer_v1',kind='public_refined_cpu',entrypoint=B.READER_ENTRYPOINT,
            operation='fit',profile_reference=refs['profile'],source_review=refs['source_review'],
            core_source_sha256=self.new_sources,producer_source_sha256=extra,execution_source_sha256=full)
        self.registry['public_reader']=refs
        entry=next(v for v in self.registry['executions'] if v['execution_id']=='amended')
        with zipfile.ZipFile(self.repo/entry['archive']['path']) as z:
            old={name:z.read(name) for name in z.namelist()}
        self.public_files={}
        for key in self.reader_ids:
            record=self.index['records'][self.sequence.index(key)];source=record['source']
            prefix='host/'+str(Path(source['result_path']).parent).replace('\\','/')+'/'
            for name,raw in old.items():
                if name.startswith(prefix):self.public_files[name]=raw
            result=B.document(self.public_files['host/'+source['result_path']])
            report=B.document(self.public_files['host/'+source['case_path']])
            report['execution_producer']=deepcopy(self.producer)
            record['execution_producer']=deepcopy(self.producer);source['execution_id']='reader-host'
            directory='/invented/host/children/'+key
            command=['/python','-B','/checkout/'+B.READER_ENTRYPOINT,'fit','--case-id',key,'--output',directory+'/science',
                     '--wall-seconds','2520','--rss-mib','6144','--headroom-mib','2048','--execution-record',directory+'/admission.json']
            admission=dict(mode='exposure_refinement_case',case_id=key,case_ids=[key],external_supervision=True,
                independent_review_passed=True,execution_producer=deepcopy(self.producer),source_sha256=full,
                reader_source_review=refs['source_review'],library_sha256=self.native['library_sha256'],build_receipt_sha256=self.native['build_receipt_sha256'])
            request=dict(schema='joint_refined_cpu_request_v1',mode='author_envelope',case_id=key,
                source_sha256=full,execution_producer=deepcopy(self.producer),actual_command=command,output=directory+'/science',
                execution_record=directory+'/admission.json',execution_record_sha256=B.digest(data(admission)),
                wall_seconds=2520,rss_cap_bytes=6442450944,headroom_bytes=2147483648)
            native=dict(self.profile['bundled_native'],library_path='native/attenuation.so',build_receipt_path='native/build_receipt.json')
            result.update(schema='joint_refined_cpu_case_v1',execution_producer=deepcopy(self.producer),source_sha256=full,
                execution_mode='author_envelope',reader_request_sha256=B.digest(data(request)),actual_command=command,
                admission_sha256=B.digest(data(admission)),bundled_native=native,bundled_native_sha256=B.digest(data(native)))
            self.public_files[prefix+'reader_request.json']=data(request)
            self.public_files[prefix+'bundled_native.json']=data(native)
            parent=str(Path(prefix.rstrip('/')).parent).replace('\\','/')+'/'
            self.public_files[parent+'admission.json']=data(admission)
            self.public_files['host/'+source['case_path']]=data(report)
            source['case_sha256']=B.digest(data(report));result['report_sha256']=source['case_sha256']
            self.public_files['host/'+source['result_path']]=data(result)
            source['result_sha256']=B.digest(data(result))
        self.reader_entry=dict(execution_id='reader-host',archive={},member_prefix='host/',review={})
        self.registry['executions'].append(self.reader_entry)
        self.repin()

    def repin(self):
        for key in self.reader_ids:
            record=self.index['records'][self.sequence.index(key)];source=record['source']
            result=B.document(self.public_files['host/'+source['result_path']])
            source['case_sha256']=B.digest(self.public_files['host/'+source['case_path']]);result['report_sha256']=source['case_sha256']
            self.public_files['host/'+source['result_path']]=data(result);source['result_sha256']=B.digest(data(result))
        archive=self.zip('reader_host.zip',self.public_files)
        review_path=self.base+'reader_host_review.json'
        review=dict(passed=True,audit_passed=True,scientific_completion=False,live_agent_review=True,live_agent_review_performed=True,
            final_batch_agent_review_required=False,review_kind='live_agent_saved_output_review',artifact_sha256=archive['sha256'],
            execution_id='reader-host',checked_case_ids=self.reader_ids,source_sha256=self.producer['execution_source_sha256'],
            core_source_sha256=self.new_sources,execution_producer=self.producer)
        write(self.repo/review_path,review)
        self.reader_entry.update(archive=archive,review={'path':review_path,'sha256':B.sha(self.repo/review_path)})
        write(self.repo/self.paths['registry'],self.registry);write(self.repo/self.paths['index'],self.index)
        self.index_review['index_sha256']=B.sha(self.repo/self.paths['index']);write(self.repo/self.paths['index_review'],self.index_review)
    def alter_result(self,change):
        record=self.index['records'][self.sequence.index(self.reader_ids[0])];name='host/'+record['source']['result_path']
        value=B.document(self.public_files[name]);change(value);self.public_files[name]=data(value);self.repin()


class PublicReaderReportingControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_mixed_sources_preserve_original_prefix_partial_and_future_core(self):
        f=ReaderEvidence(self.root);report,_=B.build(f.repo,f.paths)
        self.assertEqual(report['counts']['computed_outcomes'],395);self.assertEqual(len(report['outcomes']),400)
        self.assertEqual(report['public_reader']['case_ids'],f.reader_ids)
        self.assertEqual(report['case_dispositions'][44]['computation']['reused_optimizer_attempts'],28)
        self.assertNotIn('public_reader',report['case_dispositions'][-1])
        for row in report['case_dispositions']:
            if row['case_id'] in f.reader_ids:
                self.assertEqual(row['public_reader']['execution_producer'],f.producer)
                self.assertEqual(row['computation']['reused_optimizer_attempts'],0)
        self.assertFalse(report['scientific_completion']);self.assertFalse(report['original_publication_gate_satisfied'])
        text,_=R.render(report,'validation/fixture.json','0'*64)
        self.assertIn('not a fresh compilation claim',text)
    def test_reader_unknown_is_unavailable_and_full_regime_stats_stay_null(self):
        f=ReaderEvidence(self.root,extra_unknown=True);report,_=B.build(f.repo,f.paths)
        self.assertEqual(report['counts']['unavailable_outcomes'],10)
        self.assertEqual(report['case_dispositions'][-1]['disposition'],'scientific_unknown')
        self.assertEqual(report['complete_regimes'],[4,6])
        self.assertTrue(all(row['full_regime'] is None for row in report['regime_summary'] if row['regime']==7))
    def test_separate_report_validator_rebuilds_reader_branch(self):
        f=ReaderEvidence(self.root);report,_,_=f.accept();rebuilt,_=R.validate(f.repo,f.public)
        self.assertEqual(report,rebuilt)
    def test_reader_cannot_claim_old_driver_schema(self):
        f=ReaderEvidence(self.root);f.alter_result(lambda r:r.update(schema='joint_exposure_refinement_case_v1'))
        with self.assertRaisesRegex(ValueError,'disposition differs'):B.build(f.repo,f.paths)
    def test_unreviewed_full_source_map_rejected_even_if_result_claims_it(self):
        f=ReaderEvidence(self.root);f.alter_result(lambda r:r.update(source_sha256={'fake.py':'0'*64}))
        with self.assertRaisesRegex(ValueError,'reviewed source identity'):B.build(f.repo,f.paths)
    def test_agreeing_result_and_host_review_cannot_substitute_profile_graph(self):
        f=ReaderEvidence(self.root)
        for key in f.reader_ids:
            record=f.index['records'][f.sequence.index(key)];name='host/'+record['source']['result_path']
            value=B.document(f.public_files[name]);value['source_sha256']={'disguised.py':'9'*64};f.public_files[name]=data(value)
        f.repin()
        ref=f.reader_entry['review'];review=B.read(f.repo/ref['path']);review['source_sha256']={'disguised.py':'9'*64}
        write(f.repo/ref['path'],review);ref['sha256']=B.sha(f.repo/ref['path']);write(f.repo/f.paths['registry'],f.registry)
        with self.assertRaisesRegex(ValueError,'reviewed original/amended graph'):B.build(f.repo,f.paths)
    def test_missing_reader_registry_does_not_fall_back(self):
        f=ReaderEvidence(self.root);f.registry.pop('public_reader');write(f.repo/f.paths['registry'],f.registry)
        with self.assertRaisesRegex(ValueError,'reviewed untouched-case profile'):B.build(f.repo,f.paths)
    def test_omitted_checker_source_rejected_before_reconciliation(self):
        f=ReaderEvidence(self.root,omit_source='experiments/s04b_refined_cpu_reader_audit/check.py')
        with self.assertRaisesRegex(ValueError,'graph is incomplete'):B.build(f.repo,f.paths)
    def test_case_producer_disagreement_rejects_after_repinning(self):
        f=ReaderEvidence(self.root);record=f.index['records'][f.sequence.index(f.reader_ids[0])]
        name='host/'+record['source']['case_path'];report=B.document(f.public_files[name]);report['execution_producer']['operation']='score_replay'
        f.public_files[name]=data(report);f.repin()
        with self.assertRaisesRegex(ValueError,'producer identity differs'):B.build(f.repo,f.paths)
    def test_fake_old_module_command_rejected(self):
        f=ReaderEvidence(self.root)
        def change(value):
            value['actual_command']=['python','-B','-m','experiments.s04b_exposure_refinement.case_driver']
        f.alter_result(change)
        with self.assertRaisesRegex(ValueError,'request/actual command differs'):B.build(f.repo,f.paths)
    def test_bundled_receipt_substitution_rejected(self):
        f=ReaderEvidence(self.root);f.alter_result(lambda r:r['bundled_native'].update(library_path='a/new/build.so'))
        with self.assertRaisesRegex(ValueError,'extracted native receipt differs'):B.build(f.repo,f.paths)
    def test_auto_review_cannot_be_relabelled_live(self):
        f=ReaderEvidence(self.root);ref=f.registry['public_reader']['source_review'];review=B.read(f.repo/ref['path'])
        review['live_agent_review_performed']=False;write(f.repo/ref['path'],review);ref['sha256']=B.sha(f.repo/ref['path']);write(f.repo/f.paths['registry'],f.registry)
        with self.assertRaisesRegex(ValueError,'Independent reader source'):B.build(f.repo,f.paths)


if __name__=='__main__':unittest.main()
