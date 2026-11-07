"""Invented publication evidence only; no models, fitting or real result formatting."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import render_joint_nuisance_results as formatter
from scripts import verify_claims


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False, indent=2)+'\n', encoding='utf-8')


class InventedEvidence:
    def __init__(self, root):
        self.repo=root/'repo'
        self.base=self.repo/'validation/reproductions/invented'
        self.base.mkdir(parents=True)
        self.paths={name:'validation/reproductions/invented/'+name+'.json'
                    for name in ('summary','result','index','audit','completion_review')}
        self.cases=[]
        self.index=dict(cases=[],partial_case=None,last_attempt_passed=True)
        for regime in range(4,8):
            for seed in range(20):
                case_id=f'invented_regime_{regime}_history_{seed}'
                gain=-1. if seed<8 else (0. if seed<12 else 1.)
                case=dict(case_id=case_id,regime=regime,passed=True,status='complete',
                    outcomes=[dict(model=m,gate=g,new_gain=gain,new_win=gain>0,near_zero=gain==0)
                              for m,g in formatter.PROCEDURES],
                    historical_comparisons=[dict(model=m,gate=g,passed=True)for m,g in formatter.PROCEDURES],
                    floor_checks=[dict(phase=p,model=m,actual_nll=1.,expected_nll=1.,absolute_delta=0.,tolerance=1e-9)
                                  for p in ('train','test')for m in formatter.LABELS])
                self.cases.append(case)
                self.index['cases'].append(dict(case_id=case_id,file='cases/'+case_id+'.json'))
        protocol=dict(roster=[r['case_id']for r in self.cases])
        write(self.repo/formatter.PROTOCOL,protocol)
        self.index['science_protocol_sha256']=formatter.sha(self.repo/formatter.PROTOCOL)
        self.summary=[dict(regime=r,model=m,gate=g,N=20,mean_gain=0.,median_gain=0.,wins=8,
            wilson95=[.21880653237281705,.6134184992377469],off_floor=16,a_boundary=5,eta_lower=4,eta_upper=1,
            optimizer_failed_attempts=7,unknowns=0,null_search_gap_cases=1,coarse_fine_gate_disagreements=0,
            floor_returns=4,near_zero=4,positive_near_zero=0,robust_positive=8,robust_negative=8,
            coordinate_boundaries=dict(a=dict(lower=2,upper=3),eta=dict(lower=4,upper=1)),
            primary=(r,m,g)in formatter.PRIMARY)
            for r in range(4,8)for m,g in formatter.PROCEDURES]
        self.result=dict(passed=True,scientific_completion=True,complete_cases=80,status='batch_complete')
        self.audit=dict(passed=True,scientific_completion=True,complete_cases=80,outcomes=400,
            historical_floor_checks=480,historical_comparison_rows=400,independent_summary=deepcopy(self.summary))
        self.completion=dict(schema='joint_nuisance_publication_acceptance_v1',passed=True,
            live_independent_review=True,scientific_completion=True,counts=deepcopy(formatter.COUNTS),tasks={})
        for task in ('task1','task2','task3'):
            name='validation/reproductions/invented/'+task+'.json'
            write(self.repo/name,dict(passed=True,scope='Invented unit fixture, not actual acceptance'))
            self.completion['tasks'][task]=dict(passed=True,acceptance=dict(path=name,sha256=formatter.sha(self.repo/name)))
        self.old_tex=self.repo/'paper/source/chapters/existing_fixed_and_intercept.tex'
        self.old_ledger=self.repo/'validation/MASTER_CLAIM_LEDGER.json'
        self.old_tex.parent.mkdir(parents=True)
        self.old_tex.write_text('Existing tables: preserved fixture.\n',encoding='utf-8')
        write(self.old_ledger,dict(claims=[]))
        self.persist()

    def persist(self):
        """Re-pin deliberate fixture changes, so deeper semantic gates are tested."""
        by_id={r['case_id']:r for r in self.cases}
        for entry in self.index['cases']:
            path=self.base/entry['file']
            write(path,by_id[entry['case_id']]);entry['sha256']=formatter.sha(path)
        write(self.repo/self.paths['summary'],self.summary)
        write(self.repo/self.paths['index'],self.index)
        self.result.update(index_sha256=formatter.sha(self.repo/self.paths['index']),
                           summary_sha256=formatter.sha(self.repo/self.paths['summary']))
        write(self.repo/self.paths['result'],self.result)
        self.audit.update(index_sha256=self.result['index_sha256'],summary_sha256=self.result['summary_sha256'],
                          execution_result_sha256=formatter.sha(self.repo/self.paths['result']))
        write(self.repo/self.paths['audit'],self.audit)
        self.completion['artifact_sha256']={self.paths[k]:formatter.sha(self.repo/self.paths[k])
                                           for k in ('summary','result','index','audit')}
        write(self.repo/self.paths['completion_review'],self.completion)


class TestJointPublicationFormatter(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.fixture=InventedEvidence(self.root)
        self.destination='chapters/new_invented_joint_tables.tex'

    def stage(self):
        return formatter.stage(self.fixture.repo,self.fixture.paths,self.root/'staging',self.destination)

    def rejects(self,pattern):
        self.fixture.persist()
        with self.assertRaisesRegex(ValueError,pattern):self.stage()
        self.assertFalse((self.root/'staging').exists())

    def test_complete_fixture_stages_every_pointer_without_mutating_repository(self):
        before={p.relative_to(self.fixture.repo).as_posix():formatter.sha(p)
                for p in self.fixture.repo.rglob('*')if p.is_file()}
        receipt=self.stage()
        self.assertTrue(receipt['passed']);self.assertTrue(receipt['staging_only'])
        self.assertFalse(receipt['manuscript_installed']);self.assertFalse(receipt['ledger_modified'])
        self.assertEqual(receipt['scientific_calls'],0)
        self.assertEqual(receipt['claim_bindings'],420)
        self.assertEqual([receipt[x]for x in ('score_table_rows','diagnostic_table_rows','floor_census_table_rows')],[20]*3)
        tex=(self.root/'staging'/self.destination).read_text(encoding='utf-8')
        self.assertEqual(tex.count('\\begin{table}'),3)
        self.assertEqual(sum(line.startswith(('S4 &','S5 &','S6 &','S7 &'))for line in tex.splitlines()),60)
        self.assertIn('procedure and optimizer contrast, not evidence of inhibition',tex)
        claims=formatter.read(self.root/'staging/claims.additions.json')['claims']
        self.assertEqual(len({c['id']for c in claims}),len(claims))
        for claim in claims:
            raw=verify_claims.resolve(self.fixture.summary,claim['json_pointer'])
            value=verify_claims.transformed(raw,claim,self.fixture.summary)
            self.assertTrue(verify_claims.equal_display(value,claim),claim)
            self.assertEqual(raw,claim['resolved_source_value'])
            self.assertEqual(claim['final_display_locations'],[self.destination])
            self.assertNotIn('final_display_presence',claim)
            self.assertNotIn('authorities/',claim['bundled_source'])
        after={p.relative_to(self.fixture.repo).as_posix():formatter.sha(p)
               for p in self.fixture.repo.rglob('*')if p.is_file()}
        self.assertEqual(before,after)

    def test_incomplete_task_and_nonlive_acceptance_are_rejected(self):
        self.fixture.completion['tasks']['task2']['passed']=False
        self.rejects('Incomplete task2')
        self.fixture.completion['tasks']['task2']['passed']=True
        self.fixture.completion['live_independent_review']=False
        self.rejects('final live independent')

    def test_artifact_tampering_is_rejected_before_any_output(self):
        path=self.fixture.repo/self.fixture.paths['summary']
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'does not bind summary'):self.stage()
        self.assertFalse((self.root/'staging').exists())

    def test_missing_and_duplicate_case_roster_are_rejected_even_when_repinned(self):
        removed=self.fixture.index['cases'].pop()
        self.rejects('eighty unique')
        self.fixture.index['cases'].append(deepcopy(self.fixture.index['cases'][0]))
        self.rejects('eighty unique')
        self.fixture.index['cases'][-1]=removed

    def test_outcome_and_floor_omissions_are_not_accepted_as_completed_counts(self):
        case=self.fixture.cases[0];removed=case['outcomes'].pop()
        self.rejects('Missing/duplicate outcome')
        case['outcomes'].append(removed);case['floor_checks'].pop()
        self.rejects('floor check roster')

    def test_floor_tolerance_and_strict_positive_rule_are_enforced(self):
        floor=self.fixture.cases[0]['floor_checks'][0]
        floor.update(actual_nll=1.01,absolute_delta=.01)
        self.rejects('floor check failed')
        floor.update(actual_nll=1.,absolute_delta=0.)
        outcome=self.fixture.cases[8]['outcomes'][0];outcome['new_win']=True
        self.rejects('Strict win')

    def test_unknown_boundary_and_independent_summary_errors_fail(self):
        self.fixture.summary[0]['unknowns']=1;self.fixture.audit['independent_summary'][0]['unknowns']=1
        self.rejects('Unknown cases')
        self.fixture.summary[0]['unknowns']=0;self.fixture.audit['independent_summary'][0]['unknowns']=0
        self.fixture.summary[0]['coordinate_boundaries']['a']['upper']=20
        self.rejects('Invalid boundary census')
        self.fixture.summary[0]['coordinate_boundaries']['a']['upper']=3
        self.fixture.audit['independent_summary'][0]['wilson95'].pop()
        self.rejects('Independent Wilson')

    def test_near_zero_and_floor_census_cannot_silently_disagree(self):
        for rows in (self.fixture.summary,self.fixture.audit['independent_summary']):rows[0]['floor_returns']=5
        self.rejects('near-zero census')

    def test_shuffled_summary_preserves_exact_pointer_operands_and_rounding(self):
        self.fixture.summary.reverse()
        self.fixture.summary[0]['mean_gain']=-.0000001
        self.fixture.summary[0]['median_gain']=1.23445
        self.fixture.audit['independent_summary']=deepcopy(self.fixture.summary)
        self.fixture.persist();self.stage()
        claims=formatter.read(self.root/'staging/claims.additions.json')['claims']
        indexed={c['json_pointer']:c for c in claims}
        self.assertEqual(indexed['/0/mean_gain']['display'],'0.0000')
        self.assertEqual(indexed['/0/median_gain']['display'],'1.2344')
        self.assertEqual(indexed['/0/regime']['resolved_source_value'],7)

    def test_json_duplicate_nonfinite_and_boolean_numeric_rejected(self):
        path=self.root/'invalid.json'
        for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            path.write_text(text,encoding='utf-8')
            with self.assertRaises(ValueError):formatter.read(path)
        self.fixture.summary[0]['mean_gain']=True;self.fixture.audit['independent_summary'][0]['mean_gain']=True
        self.rejects('non-boolean scalar')

    def test_existing_source_and_in_repository_staging_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Fresh external'):
            formatter.stage(self.fixture.repo,self.fixture.paths,self.fixture.repo/'staging',self.destination)
        (self.fixture.repo/'paper/source'/self.destination).write_text('Existing source',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'must not be replaced'):self.stage()
        with self.assertRaisesRegex(ValueError,'Escaping input'):
            formatter.safe(self.fixture.repo,'../outside.json')

    def test_duplicate_additive_claim_ids_are_rejected(self):
        summary_sha=formatter.sha(self.fixture.repo/self.fixture.paths['summary'])
        _,claims=formatter.render(self.fixture.summary,self.fixture.paths['summary'],summary_sha,self.destination)
        write(self.fixture.old_ledger,dict(claims=[claims[0]]))
        with self.assertRaisesRegex(ValueError,'Binding IDs already exist'):self.stage()
        self.assertFalse((self.root/'staging').exists())


if __name__=='__main__':unittest.main()
