"""Invented disposition-export and browser fixtures; no scientific evaluation."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from website import build_findings as findings

SPEC=importlib.util.spec_from_file_location('disposition_legacy_fixture',Path(__file__).with_name('test_joint_findings.py'))
legacy=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(legacy)


class TestDispositionFindings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repository';self.repo.mkdir()
        old=legacy.fixture_module.InventedEvidence(self.root/'old')
        self.report=self.invented_report(old.summary)
        self.paths={k:findings.DISPOSITION_DIRECTORY+'/'+v+'.json' for k,v in
                    [('report','report'),('audit','independent_review'),('completion_review','completion_review')]}
        for path in self.paths.values():
            target=self.repo/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('{}\n',encoding='utf-8')
        self.formatter=self.root/'validator_fixture.py';self.formatter.write_text('# Invented source identity only\n',encoding='utf-8')

    @staticmethod
    def invented_report(original,unknowns=None):
        unknowns={5:{0}} if unknowns is None else unknowns
        summary=[];outcomes=[];cases=[]
        procedures=[('LI','raw'),('LIplus_immigrant','raw'),('LIplus_immigrant','BIC'),('LIplus_inclusive','raw'),('LIplus_inclusive','BIC')]
        for regime in range(4,8):
            unavailable=unknowns.get(regime,set())
            for n in range(20):
                case='invented_'+str(regime)+'_'+str(n);is_unknown=n in unavailable
                cases.append(dict(case_id=case,regime=regime,disposition='scientific_unknown' if is_unknown else 'complete'))
                for model,gate in procedures:
                    outcomes.append(dict(id=case+'|'+model+'|'+gate,case_id=case,regime=regime,model=model,gate=gate,
                        availability='unavailable' if is_unknown else 'computed',new_gain=None if is_unknown else -.1,
                        new_win=None if is_unknown else False,reason_code='original_optimizer_cap_unknown' if is_unknown else None))
            for model,gate in procedures:
                full=deepcopy(next(r for r in original if (r['regime'],r['model'],r['gate'])==(regime,model,gate)))
                summary.append(dict(regime=regime,model=model,gate=gate,primary=(regime,model,gate) in
                    {(5,'LIplus_immigrant','raw'),(7,'LIplus_inclusive','raw')},planned_histories=20,
                    computed_histories=20-len(unavailable),unavailable_histories=len(unavailable),
                    statistics_available=not unavailable,full_regime=None if unavailable else full,
                    unavailable_case_ids=['invented_'+str(regime)+'_'+str(n) for n in sorted(unavailable)],
                    unavailable_reason='incomplete_original_20_history_regime' if unavailable else None))
        u=sum(len(s) for s in unknowns.values())
        return dict(schema='joint_nuisance_disposition_report_v1',scientific_completion=False,regime_summary=summary,outcomes=outcomes,
            counts=dict(planned_histories=80,accepted_terminal_dispositions=80,complete_histories=80-u,scientific_unknown_histories=u,
                pending_histories=0,unresolved_technical_failures=0,planned_outcomes=400,computed_outcomes=5*(80-u),
                unavailable_outcomes=5*u,regime_procedure_rows=20),case_dispositions=cases,
            unknown_census=[r for r in cases if r['disposition']=='scientific_unknown'],
            complete_regimes=[r for r in range(4,8) if not unknowns.get(r)],
            campaign_identity={'scientific_protocol_sha256':'invented'},historical_comparators={'scope':'invented, unchanged'},
            coverage={'scope':'invented accepted fixture, not research'})

    def load_fixture(self,report=None,error=None):
        # The independent renderer owns scientific/custody acceptance. This spy
        # verifies the website invokes that exact gate before exporting a report.
        validator=SimpleNamespace(validate=MagicMock(return_value=(report or self.report,{'validation/fixture.json':'invented'}),side_effect=error))
        loader=SimpleNamespace(exec_module=lambda module:None)
        with patch.object(findings,'DISPOSITION_FORMATTER_PATH',self.formatter),\
             patch.object(findings.importlib.util,'spec_from_file_location',return_value=SimpleNamespace(loader=loader)),\
             patch.object(findings.importlib.util,'module_from_spec',return_value=validator):
            result=findings.load_joint_disposition_study(self.repo)
        validator.validate.assert_called_once_with(self.repo,self.paths)
        return result

    def test_absent_evidence_changes_nothing_and_does_not_import_validator(self):
        empty=self.root/'empty';empty.mkdir()
        with patch.object(findings.importlib.util,'spec_from_file_location') as importer:
            self.assertEqual(findings.load_joint_disposition_study(empty),(None,[]));importer.assert_not_called()

    def test_present_incomplete_evidence_fails_before_import(self):
        (self.repo/self.paths['audit']).unlink()
        with patch.object(findings.importlib.util,'spec_from_file_location') as importer:
            with self.assertRaisesRegex(ValueError,'incomplete'):findings.load_joint_disposition_study(self.repo)
            importer.assert_not_called()

    def test_separate_validator_rejection_is_not_swallowed(self):
        for reason in ('Missing independent reporting acceptance','Incomplete task2','Incomplete task3','Nonterminal roster'):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):self.load_fixture(error=ValueError(reason))

    def test_exact_report_export_retains_all_slots_and_nulls(self):
        before=deepcopy(self.report);study,sources=self.load_fixture()
        self.assertEqual(self.report,before);self.assertEqual(study['kind'],'joint_disposition_simulation')
        self.assertEqual(study['summary'],self.report['regime_summary']);self.assertEqual(study['outcomes'],self.report['outcomes'])
        self.assertEqual(len(study['outcomes']),400);self.assertEqual(len(study['summary']),20)
        self.assertEqual(sum(r['availability']=='unavailable' for r in study['outcomes']),5)
        self.assertTrue(all(r['new_gain'] is None for r in study['outcomes'] if r['availability']=='unavailable'))
        self.assertFalse(study['scientific_completion']);self.assertFalse(study['original_publication_gate_satisfied'])
        for row in study['display_summary']:
            if row['regime']==5:self.assertEqual([row['mean_gain'],row['median_gain'],row['wilson95']],[None,None,None])
        self.assertIn('raw and gated rows',study['note']);self.assertIn('Reporting acceptance is distinct',study['source'])

    def test_unavailable_statistics_never_reach_numeric_formatter(self):
        calls=[];original=findings.joint_display
        def numeric(value):
            self.assertIsNotNone(value);calls.append(value);return original(value)
        with patch.object(findings,'joint_display',side_effect=numeric):self.load_fixture()
        self.assertEqual(len(calls),15*4)

    def test_display_half_even_and_negative_zero_remain_precise(self):
        self.report['regime_summary'][0]['full_regime'].update(mean_gain=-.00001,median_gain=1.23445)
        study,_=self.load_fixture();self.assertEqual(study['display_summary'][0]['mean_gain'],'0.0000')
        self.assertEqual(study['display_summary'][0]['median_gain'],'1.2344')
        self.assertEqual(study['summary'][0]['full_regime']['mean_gain'],-.00001)

    def test_failed_original_success_gate_never_falls_back(self):
        with patch.object(findings,'load_joint_study',side_effect=ValueError('original full-success rejection')),\
             patch.object(findings,'load_joint_disposition_study') as other:
            with self.assertRaisesRegex(ValueError,'original full-success rejection'):findings.append_joint_publications(self.repo,[],[])
            other.assert_not_called()

    def test_simultaneous_campaign_views_rejected_without_partial_export(self):
        studies=[{'unchanged':True}];sources=[{'old':'source'}]
        with patch.object(findings,'load_joint_study',return_value=({'kind':'joint_simulation'},[])),\
             patch.object(findings,'load_joint_disposition_study',return_value=({'kind':'joint_disposition_simulation'},[])):
            with self.assertRaisesRegex(ValueError,'cannot publish'):findings.append_joint_publications(self.repo,studies,sources)
        self.assertEqual(studies,[{'unchanged':True}]);self.assertEqual(sources,[{'old':'source'}])

    def payload(self,study):
        helper=legacy.TestJointFindings()
        data=helper.invented_payload(study)
        data['studies'].append(study);return data

    def render_fixture(self,study,name):
        output=self.root/name;output.mkdir();payload=self.payload(study)
        findings.write_findings(output,payload);return output,payload

    def node(self,output,check=True):
        binary=shutil.which('node');self.assertIsNotNone(binary)
        return subprocess.run([binary,str(findings.ROOT/'website/check_interactions.cjs'),str(output)],
                              capture_output=True,text=True,check=check)

    def test_all_selectors_preserve_unavailable_rows_and_old_studies(self):
        for unknowns in ({5:{0}},{5:{0},6:{2}},{5:set(range(20))}):
            report=self.invented_report([r['full_regime'] for r in self.report['regime_summary'] if r['full_regime']] +
                [dict(r['full_regime'],regime=5) for r in self.report['regime_summary'] if r['regime']==4],unknowns)
            study,_=self.load_fixture(report);output,payload=self.render_fixture(study,'view'+str(sum(map(len,unknowns.values()))))
            original=deepcopy(payload['studies'][:2]);result=json.loads(self.node(output).stdout)
            self.assertEqual(result['disposition_selector_cases'],10);self.assertEqual(result['selector_combinations'],30)
            exported=json.loads((output/'findings-data.json').read_bytes())
            self.assertEqual(exported['studies'][:2],original)
            self.assertEqual(exported['studies'][-1]['outcomes'],report['outcomes'])
            self.assertEqual(result['joint_selector_cases'],0)

    def test_panel_must_be_real_unique_uncommented_id(self):
        study,_=self.load_fixture();output,_=self.render_fixture(study,'missing_panel')
        path=output/'findings.html';original=path.read_text(encoding='utf-8')
        for missing in ('joint-disposition-diagnostics','joint-disposition-census','joint-disposition-search-rows','joint-disposition-floor-rows'):
            for mutation in ('removed','data_id','comment','duplicate','quoted'):
                with self.subTest(missing=missing,mutation=mutation):
                    replace={'removed':'id="absent"','data_id':'data-id="'+missing+'"','comment':'id="absent"',
                             'duplicate':'id="'+missing+'"','quoted':"data-note=' id=\""+missing+"\"'"}[mutation]
                    text=original.replace('id="'+missing+'"',replace)
                    if mutation=='comment':text=text.replace('<body>','<body><!-- <div id="'+missing+'"></div> -->')
                    if mutation=='duplicate':text=text.replace('<body>','<body><div id="'+missing+'"></div>')
                    path.write_text(text,encoding='utf-8');ran=self.node(output,False)
                    self.assertNotEqual(ran.returncode,0);self.assertIn('Disposition dataset requires one actual panel node: '+missing,ran.stderr)

    def test_unavailable_ui_cannot_be_silently_coerced_to_zero(self):
        study,_=self.load_fixture();output,_=self.render_fixture(study,'zero_mutation')
        path=output/'findings.html';text=path.read_text(encoding='utf-8')
        self.assertIn("unavailable='Unavailable'",text)
        path.write_text(text.replace("unavailable='Unavailable'","unavailable=0"),encoding='utf-8')
        self.assertNotEqual(self.node(output,False).returncode,0)

    def test_export_cannot_drop_unavailable_outcome_slots(self):
        study,_=self.load_fixture();study['outcomes']=[r for r in study['outcomes'] if r['availability']=='computed']
        output,_=self.render_fixture(study,'dropped_slots');self.assertNotEqual(self.node(output,False).returncode,0)

    def actual_validator_fixture(self,extra_unknown=False):
        spec=importlib.util.spec_from_file_location('disposition_saved_evidence_fixture',
            Path(__file__).with_name('test_joint_disposition_reporting.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        fixture=module.InventedDispositionEvidence(self.root/'actual_gate',extra_unknown=extra_unknown)
        fixture.public=dict(self.paths)
        documents=fixture.accept()
        return module,fixture,documents

    def test_real_saved_evidence_validator_to_browser(self):
        module,fixture,(report,audit,acceptance)=self.actual_validator_fixture(extra_unknown=True)
        before={p.relative_to(fixture.repo).as_posix():p.read_bytes() for p in fixture.repo.rglob('*') if p.is_file()}
        study,sources=findings.load_joint_disposition_study(fixture.repo)
        self.assertEqual(study['counts']['complete_histories'],78)
        self.assertEqual(study['counts']['unavailable_outcomes'],10)
        self.assertEqual(study['summary'],report['regime_summary'])
        self.assertEqual(sum(row['statistics_available'] for row in study['summary']),10)
        for row in sources:self.assertEqual(module.builder.sha(fixture.repo/row['path']),row['sha256'])
        output,_=self.render_fixture(study,'actual_gate_browser')
        result=json.loads(self.node(output).stdout);self.assertEqual(result['disposition_selector_cases'],10)
        self.assertEqual(before,{p.relative_to(fixture.repo).as_posix():p.read_bytes() for p in fixture.repo.rglob('*') if p.is_file()})

    def test_real_reporting_acceptance_and_task_acceptances_are_required(self):
        module,fixture,(report,audit,acceptance)=self.actual_validator_fixture()
        findings.load_joint_disposition_study(fixture.repo)
        target=fixture.repo/fixture.public['completion_review']
        for task in ('task2','task3'):
            changed=deepcopy(acceptance);changed['tasks'][task]['passed']=False;module.write(target,changed)
            with self.assertRaisesRegex(ValueError,'Incomplete '+task):findings.load_joint_disposition_study(fixture.repo)
        changed=deepcopy(acceptance);changed['live_independent_review']=False;module.write(target,changed)
        with self.assertRaisesRegex(ValueError,'Genuine live independent'):findings.load_joint_disposition_study(fixture.repo)
        changed=deepcopy(acceptance);changed['scientific_completion']=True;module.write(target,changed)
        with self.assertRaisesRegex(ValueError,'Genuine live independent'):findings.load_joint_disposition_study(fixture.repo)


if __name__=='__main__':unittest.main()
