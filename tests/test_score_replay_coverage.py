"""Invented table/delta custody controls; no model, build or score campaign."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from reproduction.score_replay import coverage_report as c


class CoverageControls(unittest.TestCase):
    def put(self, root, name, value):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        raw=value.encode() if isinstance(value,str) else json.dumps(value).encode()
        path.write_bytes(raw);return dict(path=name,sha256=c.digest(raw))

    def fixture(self, root):
        source='\\begin{table}\n\\caption{Invented}\\label{tab:invented}\n\\begin{tabular}{lr}\nLabel & Score\\\\\nX & -1.0\\\\\n\\end{tabular}\n\\end{table}\n'
        self.put(root,'paper/demo.tex',source);table=dict(c.parse_tables(source)[0],id='demo:table:1',source_file='paper/demo.tex')
        inventory=self.put(root,'inventory.json',dict(tables=[table]))
        dep=dict(table_id=table['id'],source_file=table['source_file'],execution_status='requires_terminal_evidence_reconciliation',
                 prior_evidence=[],coverage_limit='invented scalar only',study_routes=['fake'])
        plan=self.put(root,'plan.json',dict(table_count=1,table_dependencies=[dep],previously_withdrawn=dict(studies=['F/S01'],reason='retained')))
        cell=dict(id='1:1',source_row_index=1,column_index=1,display='-1.0',display_value=-1.,rounding_half_unit=.05,
                  expression=dict(op='atom',row='fake',kind='components',field='joint'))
        links=self.put(root,'links.json',dict(tables=[dict(id=table['id'],source_file=table['source_file'],source_body_sha256=table['body_sha256'],cells=[cell])]))
        evidence=self.put(root,'evidence.json',{})
        delta=self.put(root,'delta.json',dict(passed=True,links_sha256=links['sha256'],evidence_index_sha256=evidence['sha256'],
            tables=[dict(id=table['id'],cells=[dict(cell,status='reconciled',recomputed=-1.04,arithmetic_allowance_nats=.01,arithmetic_reconciled=True)])]))
        producer=self.put(root,'producer.py','invented reviewed scalar producer')
        manifest=dict(schema='score_table_coverage_inputs_v1',plan=plan,inventory=inventory,
            routes=[dict(id='fake',kind='cached',delta=delta,links=links,evidence=evidence,producer=producer)])
        self.put(root,'inputs.json',manifest)
        return manifest,table,cell

    def run_fixture(self, root, manifest):
        self.put(root,'inputs.json',manifest)
        return c.build(root,root/'inputs.json',root/'out.json')

    def test_actual_cell_and_current_source_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,_,_=self.fixture(root);result=self.run_fixture(root,manifest)
            self.assertTrue(result['passed']);self.assertEqual(result['tables'][0]['status'],'mapped_fields_reconciled')
            self.assertAlmostEqual(result['tables'][0]['maximum_absolute_delta'],.04)
            self.assertEqual(result['previously_withdrawn']['studies'],['F/S01'])

    def test_route_complete_does_not_complete_unmapped_table(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,table,_=self.fixture(root)
            links=self.put(root,'links.json',dict(tables=[dict(id=table['id'],source_file=table['source_file'],source_body_sha256=table['body_sha256'],cells=[])]))
            manifest['routes'][0]['links']=links
            delta=json.loads((root/'delta.json').read_bytes());delta['links_sha256']=links['sha256'];delta['tables'][0]['cells']=[]
            manifest['routes'][0]['delta']=self.put(root,'delta.json',delta)
            result=self.run_fixture(root,manifest)
            self.assertFalse(result['passed']);self.assertEqual(result['tables'][0]['status'],'unmapped')

    def test_source_change_and_wrong_link_hash_fail_closed(self):
        for mutation in ('source','link'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);manifest,_,_=self.fixture(root)
                if mutation=='source':(root/'paper/demo.tex').write_text((root/'paper/demo.tex').read_text().replace('-1.0','-2.0'))
                else:manifest['routes'][0]['links']['sha256']='bad'
                with self.assertRaises(ValueError):self.run_fixture(root,manifest)

    def test_reference_operands_rejected(self):
        for expr in [dict(op='field',pointer='/expected/joint'),dict(op='atom',field='original_gain'),
                     dict(op='sum',terms=[dict(op='atom',field='expected_joint')])]:
            with self.assertRaises(ValueError):c.no_reference_operand(expr)
        c.no_reference_operand(dict(op='field',pointer='/actual/components/joint'))

    def test_failed_evidence_cannot_be_outvoted(self):
        result=c.merge_fields({'x'},{'x':[dict(status='reconciled',route='a'),dict(status='failed',route='b')]})
        self.assertEqual(result[0]['status'],'failed')
        self.assertEqual(c.merge_fields({'y'},{})[0]['status'],'not_run')

    def test_prior_label_without_pinned_prior_stays_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,_,_=self.fixture(root)
            plan=json.loads((root/'plan.json').read_bytes());plan['table_dependencies'][0].update(execution_status='already_replayed',prior_evidence=['prior.json'])
            manifest['plan']=self.put(root,'plan.json',plan)
            result=self.run_fixture(root,manifest)
            self.assertEqual(result['tables'][0]['status'],'not_run')
            self.assertEqual(result['tables'][0]['missing_prior_evidence'],['prior.json'])

    def test_case_semantic_crosswalk_and_contract_fields(self):
        inventory={};observations={};required={}
        for ordinal,label,count in [(1,'tab:pilot-frequency',6),(2,'tab:pilot-paired',4)]:
            rows=['header','header']
            for i in range(count):
                method='Supplied' if i<count//2 else 'Fitted (primary)'
                h=([0.,.5,.9][i%3] if ordinal==1 else [.5,.9][i%2])
                rows.append(f'{method} & {h} & 0/20 & 0 & 0.000000 & 0.000000 & 0.000000' if ordinal==1 else
                            f'{method} & {h} & 0.000000 & 0.000000 & 0.000000 & 0.000000 & 0.000000 & 0.000000')
            tid=f'09_temporal_mark_extensions:table:{ordinal}'
            inventory[tid]=dict(labels=[label],caption=[],source_rows=rows,source_file='paper/09_temporal_mark_extensions.tex');observations[tid]={};required[tid]=set()
        bindings,_=c.case_bindings('initial_mark')
        links=[dict(source='paper/09_temporal_mark_extensions.tex',label=x) for x in ('tab:pilot-frequency','tab:pilot-paired')]
        delta=dict(manuscript_sources=links,cells=[dict(table=label,pointer=ptr,recomputed=0.,expected=999.,tolerance=.0001,passed=True)
                     for _,label,ptr,_,_,_ in bindings])
        protocol=dict(roster=[f's{i:02d}_h{h}' for i in range(20) for h in ('0p0','0p5','0p9')],table_links=links)
        execution=dict(passed=True,full_complete=True,mode='completion',cases=[dict(case_id=x) for x in protocol['roster']])
        c.add_case_route('initial_mark',delta,execution,protocol,inventory,observations,required,'fake')
        self.assertTrue(all(x['status'] in ('reconciled','contract_checked') for tid in required for x in c.merge_fields(required[tid],observations[tid])))
        self.assertTrue(any(x['status']=='contract_checked' for v in observations.values() for fields in v.values() for x in fields))
        execution['cases'].pop()
        with self.assertRaises(ValueError):c.add_case_route('initial_mark',delta,execution,protocol,inventory,observations,required,'fake')

    def test_s02_crosswalk_maps_interval_tokens_and_skips_control_differences(self):
        bindings,contracts=c.case_bindings('s02')
        self.assertEqual(len(bindings),48)
        paired=[r for r in bindings if r[1]=='tab:s02-paired']
        self.assertEqual({r[2].split('/')[2] for r in paired},{'1','2','4','5'})
        lower=next(r for r in bindings if r[2]=='/table/0/wilson95/0')
        upper=next(r for r in bindings if r[2]=='/table/0/wilson95/1')
        self.assertEqual(lower[3:],(1,3,0));self.assertEqual(upper[3:],(1,3,1))
        self.assertEqual(len([r for r in contracts if r[-1]=='planned paired forests']),12)


if __name__=='__main__':unittest.main()
