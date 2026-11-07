"""Invented publication evidence and DOM controls; no scientific evaluation."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from website import build_findings as findings

SPEC=importlib.util.spec_from_file_location('joint_formatter_test_fixture',
    Path(__file__).with_name('test_render_joint_nuisance_results.py'))
fixture_module=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(fixture_module)


class TestJointFindings(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.fixture=fixture_module.InventedEvidence(self.root)
        self.fixture.base=self.fixture.repo/findings.JOINT_DIRECTORY
        self.fixture.paths={k:findings.JOINT_DIRECTORY+'/'+
            ('independent_review' if k=='audit' else k)+'.json' for k in self.fixture.paths}
        self.fixture.persist()

    def load(self):
        return findings.load_joint_study(self.fixture.repo)

    def test_absent_directory_does_not_add_study_or_sources(self):
        other=self.root/'empty_repository';other.mkdir()
        self.assertEqual(findings.load_joint_study(other),(None,[]))
        self.assertEqual(list(other.iterdir()),[])

    def test_present_but_incomplete_directory_fails(self):
        (self.fixture.repo/self.fixture.paths['result']).unlink()
        with self.assertRaisesRegex(ValueError,'incomplete'):self.load()

    def test_complete_fixture_exports_exact_summary_and_pins_without_mutation(self):
        before={p.relative_to(self.fixture.repo).as_posix():p.read_bytes()
                for p in self.fixture.repo.rglob('*') if p.is_file()}
        study,sources=self.load()
        self.assertEqual(study['summary'],self.fixture.summary)
        self.assertEqual(study['kind'],'joint_simulation')
        self.assertEqual(study['comparator'],'Jointly fitted uninhibited floor')
        self.assertIn('spatial and mark laws remain fixed',study['note'])
        self.assertIn('null-search',study['note'])
        self.assertEqual(study['validation_source_sha256'],fixture_module.formatter.sha(findings.FORMATTER_PATH))
        self.assertEqual({r['path'] for r in sources},set(self.fixture.paths.values())|
                         {fixture_module.formatter.PROTOCOL}|
                         {t['acceptance']['path'] for t in self.fixture.completion['tasks'].values()})
        for row in sources:self.assertEqual(row['sha256'],fixture_module.formatter.sha(self.fixture.repo/row['path']))
        self.assertEqual(before,{p.relative_to(self.fixture.repo).as_posix():p.read_bytes()
                                for p in self.fixture.repo.rglob('*') if p.is_file()})

    def test_pseudocomplete_counts_do_not_replace_actual_roster_and_checks(self):
        self.fixture.index['cases'].pop();self.fixture.persist()
        with self.assertRaisesRegex(ValueError,'eighty unique'):self.load()

    def test_missing_floor_check_is_rejected_despite_complete_declared_totals(self):
        self.fixture.cases[0]['floor_checks'].pop();self.fixture.persist()
        with self.assertRaisesRegex(ValueError,'floor check roster'):self.load()

    def test_automated_audit_or_pending_tasks_cannot_activate_panel(self):
        self.fixture.audit['live_agent_review']=False;self.fixture.persist()
        with self.assertRaisesRegex(ValueError,'completed live independent'):self.load()
        self.fixture.audit['live_agent_review']=True
        self.fixture.completion['tasks']['task3']['passed']=False;self.fixture.persist()
        with self.assertRaisesRegex(ValueError,'Incomplete task3'):self.load()

    def test_changed_summary_or_unresolved_case_is_rejected(self):
        p=self.fixture.repo/self.fixture.paths['summary'];p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'does not bind summary'):self.load()
        self.fixture.index['partial_case']={'case_id':'invented'};self.fixture.persist()
        with self.assertRaisesRegex(ValueError,'Unresolved final index'):self.load()

    def test_independent_summary_disagreement_is_rejected(self):
        self.fixture.audit['independent_summary'][0]['mean_gain']=12.;self.fixture.persist()
        with self.assertRaisesRegex(ValueError,'independent arithmetic'):self.load()

    def test_four_decimal_presentation_matches_decimal_half_even_and_normalizes_zero(self):
        for value,expected in [(1.23445,'1.2344'),(1.23455,'1.2346'),
                               (-1.23445,'-1.2344'),(-0.00001,'0.0000'),(0.0,'0.0000')]:
            self.assertEqual(findings.joint_display(value),expected)
        self.fixture.summary[0]['mean_gain']=-0.00001
        self.fixture.summary[0]['median_gain']=1.23445
        self.fixture.audit['independent_summary']=deepcopy(self.fixture.summary);self.fixture.persist()
        study,_=self.load()
        self.assertEqual(study['display_summary'][0]['mean_gain'],'0.0000')
        self.assertEqual(study['display_summary'][0]['median_gain'],'1.2344')
        self.assertEqual(study['summary'][0]['mean_gain'],-0.00001)

    def invented_payload(self,joint):
        comparisons=deepcopy(joint['comparisons'])
        observed=dict(name='Invented observed (S04)',comparisons=comparisons,metrics=['joint'],
            windows=[dict(label='Invented window '+str(i),n=105,
                          values={k:dict(joint=float(i))for k in comparisons})for i in range(3)],
            note='Invented fixture only',source='Invented')
        fixed=dict(name='Invented fixed and intercept comparisons',kind='simulation',
            comparisons=comparisons,metrics=['joint'],regime_names=joint['regime_names'],
            summary=[dict(regime=r['regime'],model=r['model'],gate=r['gate'],n=20,
                          mean_gain=-2.,median_gain=-1.,mean_standard_error=.2,wins=3,
                          win_wilson95=[.1,.3],off_floor=5)for r in joint['summary']],
            refitted_floor=[dict(regime=r['regime'],model=r['model'],gate=r['gate'],N=20,
                                 original_mean_gain=-2.,mean_gain=-3.,wins=2)for r in joint['summary']],
            note='Invented fixed comparator retained',source='Invented')
        return dict(studies=[observed,fixed],sources=[],scope='Invented fixture; no scientific evidence')

    def test_generated_selectors_keep_fixed_intercept_and_joint_semantics_separate(self):
        node=shutil.which('node')
        self.assertIsNotNone(node,'Node is required to exercise the published JavaScript')
        joint,sources=self.load();payload=self.invented_payload(joint)
        original=deepcopy(payload)
        for enabled in (False,True):
            output=self.root/('with_joint' if enabled else 'without_joint');output.mkdir()
            current=deepcopy(payload)
            if enabled:current['studies'].append(joint);current['sources'].extend(sources)
            findings.write_findings(output,current)
            completed=subprocess.run([node,str(findings.ROOT/'website/check_interactions.cjs'),str(output)],
                                     capture_output=True,text=True,check=True)
            report=json.loads(completed.stdout)
            self.assertTrue(report['passed'])
            self.assertEqual(report['joint_selector_cases'],10 if enabled else 0)
            self.assertEqual(report['selector_combinations'],30 if enabled else 20)
            exported=json.loads((output/'findings-data.json').read_text(encoding='utf-8'))
            self.assertEqual(exported['studies'][:2],original['studies'])
            self.assertEqual(len(exported['studies']),3 if enabled else 2)
        self.assertEqual(payload,original)

    def test_installed_legacy_site_without_joint_dataset_keeps_all_selector_checks(self):
        node=shutil.which('node');self.assertIsNotNone(node)
        site=findings.ROOT/'website/site'
        data=json.loads((site/'findings-data.json').read_text(encoding='utf-8'))
        completed=subprocess.run([node,str(findings.ROOT/'website/check_interactions.cjs'),str(site)],
                                 capture_output=True,text=True,check=True)
        report=json.loads(completed.stdout)
        self.assertTrue(report['passed'])
        expected=sum(len(s['comparisons'])*len(s['metrics'])*2 for s in data['studies'])
        self.assertEqual(report['selector_combinations'],expected)
        self.assertEqual(report['joint_selector_cases'],10*sum(s.get('kind')=='joint_simulation'for s in data['studies']))

    def test_joint_dataset_requires_real_panel_markup_not_stub_created_nodes(self):
        node=shutil.which('node');self.assertIsNotNone(node)
        joint,_=self.load();payload=self.invented_payload(joint);payload['studies'].append(joint)
        output=self.root/'joint_missing_panel';output.mkdir();findings.write_findings(output,payload)
        path=output/'findings.html';original=path.read_text(encoding='utf-8')
        for missing in ('joint-diagnostics','joint-search-rows','joint-floor-rows'):
            with self.subTest(missing=missing):
                modified=original.replace('id="'+missing+'"','id="missing-'+missing+'"')
                self.assertNotEqual(modified,original);path.write_text(modified,encoding='utf-8')
                completed=subprocess.run([node,str(findings.ROOT/'website/check_interactions.cjs'),str(output)],
                                         capture_output=True,text=True)
                self.assertNotEqual(completed.returncode,0)
                self.assertIn('Joint dataset requires one actual panel node: '+missing,completed.stderr)

    def test_invented_legacy_view_without_joint_nodes_keeps_seventy_combinations(self):
        node=shutil.which('node');self.assertIsNotNone(node)
        joint,_=self.load();payload=self.invented_payload(joint)
        for index in range(5):
            extra=deepcopy(payload['studies'][0]);extra['name']='Invented extra region '+str(index)
            payload['studies'].append(extra)
        output=self.root/'invented_legacy';output.mkdir();findings.write_findings(output,payload)
        path=output/'findings.html';html=path.read_text(encoding='utf-8')
        start=html.index('<div id="joint-diagnostics"')
        end=html.index('<h3>How to read this comparison</h3>',start)
        # Emulate the legacy template and its original simulation/observed code:
        # no joint DOM nodes or active initialization calls exist in that edition.
        html=(html[:start]+html[end:]).replace("el('joint-diagnostics').hidden=true;",'')
        self.assertNotIn('id="joint-diagnostics"',html)
        path.write_text(html,encoding='utf-8')
        completed=subprocess.run([node,str(findings.ROOT/'website/check_interactions.cjs'),str(output)],
                                 capture_output=True,text=True,check=True)
        report=json.loads(completed.stdout)
        self.assertTrue(report['passed']);self.assertEqual(report['selector_combinations'],70)
        self.assertEqual(report['joint_selector_cases'],0)


if __name__=='__main__':unittest.main()
