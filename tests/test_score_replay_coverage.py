"""Invented table/delta custody controls; no model, build or score campaign."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

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
            self.assertFalse(result['passed']);self.assertEqual(result['tables'][0]['status'],'not_run')

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

    def test_operation_specific_metadata_and_aggregate_guards(self):
        valid=[dict(op='state',registry='jma',row='invented',pointer='/nuisance/N',absolute_tolerance=0),
               dict(op='select',record='aggregate',pointer='/contrasts',where={'fold':0},field='joint_logscore'),
               dict(op='select',record='aggregate',pointer='/absolute_rows',where={'arm':'OC'},field='n_target'),
               dict(op='select',record='aggregate',pointer='/comparison/comparisons',where={'arm':'LI'},field='gain')]
        for value in valid:c.no_reference_operand(value)
        bad=[dict(valid[0],pointer='/nuisance/expected'),dict(valid[0],pointer='/nuisance/beta'),
             dict(valid[0],absolute_tolerance=.1),dict(valid[1],field='expected'),
             dict(valid[1],field='original_gain'),dict(valid[1],pointer='/expected/contrasts'),
             dict(valid[1],where={}),dict(op='field',pointer='/actual/expected_joint'),
             dict(op='field',pointer='/actual/expected~1joint'),dict(op='constant',pointer='/nuisance/N')]
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):c.no_reference_operand(value)

    def test_unmapped_new_score_column_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);manifest,table,_=self.fixture(root)
            source=(root/'paper/demo.tex').read_text().replace('Label & Score','Label & Score & Other').replace('X & -1.0','X & -1.0 & -2.0')
            self.put(root,'paper/demo.tex',source)
            table.update(c.parse_tables(source)[0]);manifest['inventory']=self.put(root,'inventory.json',dict(tables=[table]))
            links=json.loads((root/'links.json').read_bytes());links['tables'][0]['source_body_sha256']=table['body_sha256']
            manifest['routes'][0]['links']=self.put(root,'links.json',links)
            delta=json.loads((root/'delta.json').read_bytes());delta['links_sha256']=manifest['routes'][0]['links']['sha256']
            manifest['routes'][0]['delta']=self.put(root,'delta.json',delta)
            result=self.run_fixture(root,manifest)
            self.assertFalse(result['passed']);self.assertEqual(result['tables'][0]['status'],'partial')
            missing=[r['field'] for r in result['tables'][0]['fields'] if r['status']=='not_run']
            self.assertEqual(missing,['1:2:0'])

    def test_numeric_inventory_includes_interval_and_fraction_tokens(self):
        value=dict(source_rows=['M1 & [0.1, 0.9] & 2/20 & 1.25','Heading & h=0 & Model M1 & none'])
        self.assertEqual(c.inventory_numeric_fields(value),{'0:1:0','0:1:1','0:2:0','0:2:1','0:3:0'})

    def test_wrapped_scientific_display_is_one_required_value(self):
        table=dict(source_rows=[r'Label & Score',r'X & \shortstack[r]{$-1.23456$\\$\times10^{-12}$}'])
        self.assertEqual(c.inventory_numeric_fields(table),{'1:1:0'})
        literal,value,half=c.source_number(table,1,1)
        self.assertEqual(literal,'-1.23456e-12');self.assertEqual(value,-1.23456e-12)
        self.assertAlmostEqual(half/5e-18,1.)
        mapped=dict(source_row_index=1,column_index=1,display_value=-1.23456e-12,
                    expression=dict(op='atom',row='fake/fold_0/A/test',field='joint'))
        evidence=dict(mapped,recomputed=-1.23456e-12,arithmetic_allowance_nats=0.,arithmetic_reconciled=True)
        self.assertEqual(c.checked_cell(table,mapped,evidence,'fake','cached')['status'],'reconciled')
        mapped['display_value']=float('-1.23456')*10**-12
        self.assertEqual(c.checked_cell(table,mapped,evidence,'fake','cached')['status'],'reconciled')
        mapped['display_value']=-1.23455e-12
        with self.assertRaises(ValueError):c.checked_cell(table,mapped,evidence,'fake','cached')
        # A missing mapping still cannot drop this score from the required census.
        self.assertEqual(c.merge_fields(c.inventory_numeric_fields(table),{})[0]['status'],'not_run')

    def test_tiny_zero_tolerance_and_producer_rounding_disagreement(self):
        table=dict(source_rows=[r'X & \shortstack[r]{$1.00000$\\$\times10^{-13}$}'])
        mapped=dict(source_row_index=0,column_index=1,display_value=1e-13)
        evidence=dict(mapped,recomputed=0.,arithmetic_allowance_nats=0.,arithmetic_reconciled=True,
                      display_rounding_agrees=False)
        result=c.checked_cell(table,mapped,evidence,'fake','cached')
        self.assertEqual(result['status'],'failed');self.assertFalse(result['exact_display_match'])
        evidence['arithmetic_allowance_nats']=1e-9
        result=c.checked_cell(table,mapped,evidence,'fake','cached')
        self.assertEqual(result['status'],'reconciled');self.assertFalse(result['exact_display_match'])
        self.assertIs(result['producer_display_rounding_flags']['display_rounding_agrees'],False)
        evidence['recomputed']=1e-13
        self.assertFalse(c.checked_cell(table,mapped,evidence,'fake','cached')['exact_display_match'])

    def test_comma_counts_and_calendar_labels(self):
        table=dict(source_rows=['Year & Count','2011-2016 (79) & 2,829'])
        self.assertEqual(c.inventory_numeric_fields(table),{'1:0:0','1:0:1','1:0:2','1:1:0'})
        self.assertEqual(c.source_number(table,1,1),('2,829',2829.,0.))
        self.assertEqual(c.source_number(table,1,0,1),('2016',2016.,0.))

    def test_exact_support_companions_and_distinct_actual_win_denominator(self):
        table=dict(source_rows=['Label & Support','X & 0.35, 0.50'])
        mapped=dict(source_row_index=1,column_index=1)
        result=dict(field='1:1:semantic',route='test',status='reconciled',semantic=True,actual='0.35, 0.50')
        companions=c.companion_fields(table,mapped,result)
        self.assertEqual([x['actual'] for x in companions],[.35,.50])
        self.assertEqual(c.companion_fields(table,mapped,dict(result,status='failed')),[])
        table['source_rows'][1]='X & 1/2'
        contrasts=[dict(op='atom',row=f'fake/fold_{i}/A/test',kind='components',field='joint') for i in range(2)]
        mapped['expression']=dict(op='wins',contrasts=contrasts)
        result=dict(field='1:1:0',route='test',status='reconciled')
        denominator=c.companion_fields(table,mapped,result)[0]
        self.assertEqual(denominator['actual'],2);self.assertEqual(denominator['status'],'contract_checked')
        self.assertEqual(denominator['distinct_case_ids'],['fold_0','fold_1'])
        self.assertEqual(c.companion_fields(table,mapped,dict(result,status='not_run'))[0]['status'],'not_run')
        # A different arm in the same case must not inflate the case denominator.
        contrasts[1]['row']='fake/fold_0/B/test'
        with self.assertRaises(ValueError):c.companion_fields(table,mapped,result)

    def test_explicit_metadata_disposition_is_bound_and_not_a_score(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);resources=c.Resources(root,root/'inputs.json')
            table=dict(id='fake:table:1',body_sha256='sourcepin',source_rows=['Fold & Score','1 & -2.0'])
            inventory={table['id']:table};observations={table['id']:{}};required={table['id']:c.inventory_numeric_fields(table)}
            record=self.put(root,'actual.json',dict(rows=[dict(passed=True,id='fake/fold_1/A/test',fold_id=1)]))
            entry=dict(table_id=table['id'],source_body_sha256='sourcepin',source_row_index=1,column_index=0,
                numeric_token_index=0,source_token='1',role='fold_id',evidence=dict(resource=record,record_pointer='/rows/0',
                    identity_pointer='/id',identity='fake/fold_1/A/test',value_pointer='/fold_id'))
            spec=self.put(root,'metadata.json',dict(schema='score_table_metadata_dispositions_v1',entries=[entry]))
            c.add_metadata_dispositions(resources,spec,inventory,observations,required)
            fields=c.merge_fields(required[table['id']],observations[table['id']])
            self.assertEqual([r['status'] for r in fields],['metadata_checked','not_run'])
            for mutation in ('identity','source','role','reference','failed'):
                bad=copy.deepcopy(entry)
                if mutation=='identity':bad['evidence']['identity']='other'
                elif mutation=='source':bad['source_body_sha256']='wrong'
                elif mutation=='role':bad['role']='score'
                elif mutation=='reference':bad['evidence']['value_pointer']='/expected'
                else:
                    bad['evidence']['resource']=self.put(root,'failed.json',dict(rows=[dict(passed=False,id='fake/fold_1/A/test',fold_id=1)]))
                badspec=self.put(root,'bad.json',dict(schema='score_table_metadata_dispositions_v1',entries=[bad]))
                with self.subTest(mutation=mutation),self.assertRaises((ValueError,KeyError)):
                    c.add_metadata_dispositions(resources,badspec,inventory,observations,required)

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
        execution=dict(passed=True,full_complete=True,mode='completion',cases=[dict(case_id=x,passed=True) for x in protocol['roster']])
        c.add_case_route('initial_mark',delta,execution,protocol,inventory,observations,required,'fake')
        self.assertTrue(all(x['status'] in ('reconciled','contract_checked') for tid in required for x in c.merge_fields(required[tid],observations[tid])))
        self.assertTrue(any(x['status']=='contract_checked' for v in observations.values() for fields in v.values() for x in fields))
        # A complete case campaign cannot turn a small zero-tolerance count
        # discrepancy into success through a blanket absolute epsilon.
        tiny=copy.deepcopy(delta);tiny['cells'][0].update(recomputed=1e-13,tolerance=0.)
        local_observations={tid:{} for tid in inventory};local_required={tid:set() for tid in inventory}
        c.add_case_route('initial_mark',tiny,execution,protocol,inventory,local_observations,local_required,'tiny')
        self.assertEqual(local_observations['09_temporal_mark_extensions:table:1']['2:2:0'][0]['status'],'failed')
        execution['cases'][0]['passed']=False
        with self.assertRaises(ValueError):c.add_case_route('initial_mark',delta,execution,protocol,inventory,observations,required,'fake')
        execution['cases'][0]['passed']=True
        duplicate=copy.deepcopy(protocol);duplicate['roster'][-1]=duplicate['roster'][0]
        with self.assertRaises(ValueError):c.add_case_route('initial_mark',delta,execution,duplicate,inventory,observations,required,'fake')
        execution['cases'].pop()
        with self.assertRaises(ValueError):c.add_case_route('initial_mark',delta,execution,protocol,inventory,observations,required,'fake')

    def test_case_index_requires_hashed_individual_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);archive=root/'results.zip'
            good=json.dumps(dict(case_id='good',passed=True)).encode()
            bad=json.dumps(dict(case_id='bad',passed=False)).encode()
            with zipfile.ZipFile(archive,'w') as source:
                source.writestr('reader/science/good.json',good);source.writestr('reader/science/bad.json',bad)
            spec=dict(archive='results.zip',archive_sha256=c.digest(archive.read_bytes()),member='reader/science/result.json',sha256='unused')
            index=dict(passed=True,cases=[dict(case_id='good',file='good.json',sha256=c.digest(good))])
            resources=c.Resources(root,root/'inputs.json')
            self.assertTrue(c.case_records(resources,spec,index,'case')['good']['passed'])
            index['cases'].append(dict(case_id='bad',file='bad.json',sha256=c.digest(bad)))
            with self.assertRaises(ValueError):c.case_records(resources,spec,index,'case')
            index['cases']=index['cases'][:1];index['cases'][0]['sha256']='wrong'
            with self.assertRaises(ValueError):c.case_records(resources,spec,index,'case')

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
