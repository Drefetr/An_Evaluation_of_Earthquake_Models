"""Small invented controls; no catalogue scoring, DLL loading or optimization."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from reproduction.score_replay import cached_native
from reproduction.score_replay.core import Inputs, compare, components, digest, pointer, resolve, write_new
from reproduction.score_replay.inventory import tables
from reproduction.score_replay.replay import checked_admission, source_pins
from reproduction.score_replay.regional_replay import compare_arrays, arrays_from_bytes, catalogue_and_geometry, module_from_spec


class TestScoreReplay(unittest.TestCase):
    def test_original_s03_evaluator_on_hand_authored_one_event(self):
        import math
        import numpy as np
        root = Path(__file__).resolve().parents[1]/'reproduction/score_replay/s03'
        registry = json.loads((root/'registry.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as d:
            source = module_from_spec(Inputs(root), registry['rows'][0]['spatial_source'], Path(d), 'tiny_s03_')
            feature = dict(b=np.array([.25]), x=np.array([0.]), hp=np.array([.5]),
                           hg=np.array([2.]), exposure=4., start=0., end=2., T0=2., marks=-1.)
            value, gradient = source.evaluate(feature, [math.log(2.), 0., .5])
            self.assertAlmostEqual(value['compensator'], 6.)
            self.assertAlmostEqual(value['joint'], math.log(.75)-7.)
            self.assertAlmostEqual(value['timing'], math.log(3.)-6.)
            self.assertAlmostEqual(value['location'], math.log(.25))
            self.assertTrue(np.isfinite(gradient).all())

    def test_s06_ca_exact_partition_counts_without_likelihood_execution(self):
        from types import SimpleNamespace
        root = Path(__file__).resolve().parents[1]/'reproduction/score_replay/s06_ca'
        registry = json.loads((root/'registry.json').read_text(encoding='utf-8'))
        inputs = Inputs(root)
        self.assertEqual(len(registry['rows']), 60)
        with tempfile.TemporaryDirectory() as d:
            first = registry['rows'][0]
            catalogue = catalogue_and_geometry(inputs, first, inputs.json(first['state']), Path(d), SimpleNamespace())
        for row in registry['rows']:
            state = inputs.json(row['state'])
            mask = (catalogue['t_days'] >= state['start']) & (catalogue['t_days'] < state['end'])
            self.assertEqual(int(mask.sum()), row['n_events_expected'], row['id'])

    def test_regional_arrays_use_exact_shape_and_declared_absolute_tolerance(self):
        import numpy as np
        reference = {'event_time': np.array([1., 2.]), 'event_logs': np.array([[1., -2.]])}
        self.assertTrue(compare_arrays(reference, reference, {'event_time': 0., 'event_logs': 1e-8})['passed'])
        different = dict(reference, event_time=np.array([1., 2.00001]))
        self.assertFalse(compare_arrays(different, reference, {'event_time': 0., 'event_logs': 1e-8})['passed'])
        wrong_shape = dict(reference, event_logs=np.array([1., -2.]))
        self.assertFalse(compare_arrays(wrong_shape, reference, {'event_time': 0., 'event_logs': 1e-8})['passed'])

    def test_regional_unconfigured_or_nonfinite_arrays_fail(self):
        import numpy as np
        with self.assertRaises(ValueError):
            compare_arrays({'x': np.array([1.])}, {'x': np.array([1.])}, {})
        with self.assertRaises(ValueError):
            compare_arrays({'x': np.array([float('nan')])}, {'x': np.array([1.])}, {'x': 1e-6})

    def test_jma_registry_exact_target_counts_without_likelihood_execution(self):
        root = Path(__file__).resolve().parents[1]/'reproduction/score_replay/jma'
        registry = json.loads((root/'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(len(registry['rows']), 93)
        self.assertEqual(len({r['id'] for r in registry['rows']}), 93)
        self.assertEqual(len(registry['aliases']), 9)
        inputs = Inputs(root)
        catalogue = arrays_from_bytes(inputs.read(registry['rows'][0]['catalogue']))
        for row in registry['rows']:
            state = inputs.json(row['state'])
            selected = (catalogue['t_days'] >= state['start']) & (catalogue['t_days'] < state['end'])
            self.assertEqual(int(selected.sum()), row['n_events_expected'], row['id'])
            self.assertEqual(state['nuisance']['training_start'], 1826.)
            self.assertEqual(state['nuisance']['T0'], 6940.)
            self.assertNotEqual(state['nuisance'].get('mark_measure'), 'continuous')

    def test_registry_distinguishes_same_model_different_background_procedures(self):
        path = Path(__file__).resolve().parents[1]/'reproduction/score_replay/cached_registry.json'
        registry = json.loads(path.read_text(encoding='utf-8'))
        rows = registry['rows']
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        self.assertTrue(all(isinstance(r['n_events_expected'], int) for r in rows))
        backgrounds = [r for r in rows if r['study'] == 'background'
                       and r['case'] == 'primary_fold_0' and r['phase'] == 'test'
                       and r['model'] == 'E_fixed']
        self.assertEqual(len(backgrounds), 4)
        self.assertEqual(len({r['procedure_key'] for r in backgrounds}), 4)

    def test_original_s04_stage_orders_and_saved_history_counts(self):
        import io
        import numpy as np
        from reproduction.score_replay.inhibition_replay import selected_states
        root = Path(__file__).resolve().parents[1]/'reproduction/score_replay/s04_original'
        registry = json.loads((root/'registry.json').read_text(encoding='utf-8'))
        inputs = Inputs(root)
        self.assertEqual(len(registry['rows']), 80)
        counts = {}
        for case in registry['rows']:
            counts[case['stage']] = counts.get(case['stage'], 0)+1
            with np.load(io.BytesIO(inputs.read(case['history'])), allow_pickle=False) as saved:
                rows = saved['rows']
            self.assertEqual(digest(rows.tobytes()), case['rows_sha256'])
            for phase, start, end in [('train',30,395),('test',395,760)]:
                self.assertEqual(int(((rows[:,0]>=start)&(rows[:,0]<end)).sum()),case['n_'+phase])
            for spec in case['fits'].values():
                selected_states(inputs.json(spec))
        self.assertEqual(counts, {'first_pass':59,'fixed_state_refinement':3,'order16_refit':18})

    def test_original_li_raw_counts_and_selected_reference_bindings(self):
        import io
        import numpy as np
        root=Path(__file__).resolve().parents[1]/'reproduction/score_replay/original_li'
        registry=json.loads((root/'registry.json').read_text(encoding='utf-8'));inputs=Inputs(root)
        self.assertEqual(len(registry['rows']),38)
        self.assertEqual(len({(r['case'],r['arm']) for r in registry['rows']}),19)
        for row in registry['rows']:
            state=inputs.json(row['state']);reference=inputs.json(row['expected'])
            self.assertEqual(len(state['parameters']),8 if row['arm']=='LI' else 5)
            with np.load(io.BytesIO(inputs.read(row['raw'])),allow_pickle=False) as saved:
                meta=json.loads(str(saved['metadata_json'].item()));times=saved['parent_time']
            self.assertEqual(int(((times>=meta['start'])&(times<meta['end'])).sum()),row['n_events_expected'])
            for phase in ('coarse','fine'):components(reference[phase],'space_time_mark')

    def test_original_li_array_mismatch_cannot_hide_behind_scalar_match(self):
        import numpy as np
        from reproduction.score_replay.li_replay import compare_result
        raw=dict(P=1.,E=2.,M=3.,timing=-1.,event_log_point_intensity=[1.])
        reference={k:dict(raw) for k in ('coarse','fine')}
        actual={k:dict(components=components(raw,'space_time_mark')) for k in ('coarse','fine')}
        arrays={k+'__event_log_point_intensity':np.array([5.]) for k in ('coarse','fine')}
        row=dict(absolute_tolerances={k:1e-4 for k in ('P','E','C','M','timing','location','joint')},
                 event_log_absolute_tolerance=1e-4)
        self.assertFalse(compare_result(actual,arrays,reference,row)['passed'])

    def test_inhibition_decomposition_does_not_invent_timing_split(self):
        from reproduction.score_replay.inhibition_replay import joint_components
        result = joint_components([7.,0.,0.,0.,2.,1.],[0,0,0,0,0,0,8.,-2.])
        self.assertEqual((result['P'],result['E'],result['C'],result['M'],result['joint']),
                         (1.,6.,-6.,-2.,-7.))
        self.assertIsNone(result['timing'])
        self.assertIsNone(result['location'])
        with self.assertRaisesRegex(ValueError,'decomposition'):
            joint_components([1.,0.,0.,0.,2.,1.],[0,0,0,0,0,0,8.,-2.])

    def test_inhibition_chunks_count_events_and_exposure_once(self):
        import numpy as np
        from reproduction.score_replay.inhibition_replay import chunks
        data=dict(parents=np.zeros((2,6)),events=np.ones((3,6)),space=np.ones((10,5)),
                  times=np.ones(4),weights=np.ones(4),meta=np.arange(9,dtype=float))
        result=list(chunks(data,1000))
        self.assertGreater(len(result),1)
        self.assertEqual(sum(len(x['events']) for x in result),3)
        self.assertEqual(sum(len(x['space']) for x in result),10)
        self.assertEqual(sum(x['meta'][6] for x in result),6.)
        self.assertEqual(sum(x['meta'][7] for x in result),7.)
        self.assertEqual(data['meta'][6],6.)

    def test_temporal_crosswalk_has_positive_integral_and_signed_compensator(self):
        x = components({'timing_logscore': -3., 'mark_logscore': -2.,
                        'integrated_intensity': 5., 'joint_nll': 5.}, 'time_mark')
        self.assertEqual((x['P'], x['E'], x['C'], x['M'], x['joint']), (2., 5., -5., -2., -5.))
        self.assertIsNone(x['location'])

    def test_spatial_crosswalk_keeps_ground_and_point_distinct(self):
        x = components({'event_log_point_intensity_sum': 7., 'regional_timing_logscore': 2.,
                        'integrated_intensity': 3., 'mark_logscore': -1.,
                        'joint_logscore': 3.}, 'space_time_mark')
        self.assertEqual(x['location'], 2.)

    def test_no_manufactured_mark_component(self):
        with self.assertRaisesRegex(ValueError, 'missing evaluator field'):
            components({'timing_logscore': -1., 'integrated_intensity': 1.}, 'time_mark')

    def test_decomposition_and_nonfinite_rejected(self):
        for raw in [dict(P=2., E=3., M=1., joint=4.), dict(P=float('nan'), E=3., M=1.),
                    dict(P=2., E=-3., M=1.)]:
            with self.assertRaises(ValueError):
                components(raw, 'space_time_mark')

    def test_tolerance_is_absolute_and_not_display_rounding(self):
        self.assertFalse(compare({'joint': 1000.0002}, {'joint': 1000.}, {'joint': 1e-6})['passed'])
        self.assertTrue(compare({'joint': 1000.0000002}, {'joint': 1000.}, {'joint': 1e-6})['passed'])

    def test_unconfigured_comparison_cannot_pass(self):
        with self.assertRaises(ValueError):
            compare({'joint': 2.}, {'joint': 2.}, {})
        with self.assertRaises(ValueError):
            compare({}, {}, {})

    def test_pointer_and_path_custody(self):
        self.assertEqual(pointer({'a/b': {'x~y': [7]}}, '/a~1b/x~0y/0'), 7)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for invalid in ('../outside', str(root), 'a\\b'):
                with self.assertRaises(ValueError):
                    resolve(root, invalid)

    def test_member_hash_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with zipfile.ZipFile(root/'input.zip', 'w') as z:
                z.writestr('state.json', b'{}')
            inputs = Inputs(root)
            spec = dict(archive='input.zip', member='state.json', sha256=digest(b'{}'))
            self.assertEqual(inputs.json(spec), {})
            with self.assertRaises(ValueError):
                inputs.read(dict(spec, sha256='0'*64))
            with self.assertRaises(ValueError):
                inputs.read(dict(spec, member='../state.json'))

    def test_output_records_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'r.json'
            write_new(p, {'passed': False})
            with self.assertRaises(FileExistsError):
                write_new(p, {'passed': True})

    def test_nested_table_is_one_inventory_entry(self):
        source = '\\begin{table}\\caption{A {nested} caption}\\begin{tabular}{ll}\nA & B\\\\\n\\end{tabular}\\end{table}'
        found = tables(source)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['caption'], ['A {nested} caption'])

    def test_admission_pins_exact_source_registry_and_ordered_roster(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'review.json'
            value = dict(passed=True, mode='pilot', registry_sha256=digest(b'{}'),
                         source_sha256=source_pins(), row_ids=['b', 'a'])
            p.write_text(json.dumps(value))
            self.assertTrue(checked_admission(p, b'{}', ['b', 'a'], 'pilot')['passed'])
            with self.assertRaises(ValueError):
                checked_admission(p, b'{}', ['a', 'b'], 'pilot')

    def test_evaluator_does_not_receive_or_use_expected_score(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = b'''class Objective:
    def __init__(self, path, dll_path): self.ne = 1
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def evaluate(self, model, pars):
        return {'P':pars[0], 'E':2., 'M':-1., 'timing':pars[0]-2.}
'''
            files = {'adapter.py': source, 'cache.npz': b'hand-authored fake cache',
                     'state.json': json.dumps({'parameters': [4.], 'expected_components': {'joint': 999999.}}).encode(),
                     'fake_library': b'not a DLL'}
            for name, data in files.items(): (root/name).write_bytes(data)
            def spec(name): return {'path': name, 'sha256': digest(files[name])}
            row = {'state': spec('state.json'), 'cache': spec('cache.npz'), 'model': 'tiny',
                   'observation_measure': 'time_mark', 'n_events_expected': 1}
            adapter = {'python': spec('adapter.py'), 'native': {'sha256': 'tiny-native-source'}}
            library = {'path': str(root/'fake_library'), 'sha256': digest(files['fake_library']),
                       'source_sha256': 'tiny-native-source'}
            actual = cached_native.evaluate(Inputs(root), row, adapter, library, root/'result')
            self.assertEqual(actual['components']['joint'], 1.)
            self.assertNotEqual(actual['components']['joint'], 999999.)
            with self.assertRaisesRegex(ValueError, 'event count'):
                cached_native.evaluate(Inputs(root), dict(row, n_events_expected=2),
                                       adapter, library, root/'bad_result')


class CachedProfileTableTests(unittest.TestCase):
    """Invented passed rows; profile selection never reads expected scores."""
    def fixture(self):
        group=dict(case='tiny',model='E0_free',selected_train_row='selected/train',selected_test_row='selected/test',
                   grid=[.2,.35,.5],descriptive_support_nll_gap=2.,nodes=[])
        def row(r,nll):
            return dict(parameters=[-4.,.1,.3,r],components={'joint':-nll},
                        native_scalar_components={'joint_nll':nll},expected={'joint':999999.,'in_sparse_support':False})
        rows={'selected/train':row(.4,100.),'selected/test':row(.4,20.)}
        for i,(r,nll)in enumerate(zip(group['grid'],[103.,102.,100.5])):
            names={'train':str(i)+'/train','test':str(i)+'/test'}
            group['nodes'].append(dict(index=i,r=r,rows=names));rows[names['train']]=row(r,nll);rows[names['test']]=row(r,500.+i)
        return group,rows

    def test_profile_support_uses_actual_training_nll_and_includes_exact_boundary(self):
        from reproduction.score_replay.reconcile_cached_tables import profile_support
        group,rows=self.fixture();result=profile_support(group,rows.__getitem__)
        self.assertEqual(result['selected_r'],.4);self.assertEqual(result['support_r'],[.35,.5])
        self.assertEqual(result['support_display'],'0.35, 0.50');self.assertEqual(result['nodes'][1]['training_nll_gap'],2.)
        for node in group['nodes']:
            actual=rows[node['rows']['test']];actual['components']['joint']=1e9;actual['native_scalar_components']['joint_nll']=-1e9
        self.assertEqual(profile_support(group,rows.__getitem__)['support_display'],'0.35, 0.50')

    def test_profile_none_is_derived_from_all_nodes_not_an_expected_empty_list(self):
        from reproduction.score_replay.reconcile_cached_tables import profile_support
        group,rows=self.fixture()
        for node in group['nodes']:
            actual=rows[node['rows']['train']];actual['components']['joint']=-103.;actual['native_scalar_components']['joint_nll']=103.
            actual['expected']['in_sparse_support']=True
        result=profile_support(group,rows.__getitem__)
        self.assertEqual(result['support_r'],[]);self.assertEqual(result['support_display'],'none')
        self.assertEqual(len(result['nodes']),3)

    def test_profile_rejects_missing_nonfinite_or_mismatched_state(self):
        import copy
        from reproduction.score_replay.reconcile_cached_tables import profile_support,MissingEvidence
        group,rows=self.fixture()
        def missing(rid):
            if rid=='2/test':raise MissingEvidence(rid)
            return rows[rid]
        with self.assertRaises(MissingEvidence):profile_support(group,missing)
        for rowid,field,value in [('0/test','parameters',[-4.,.1,.3,.8]),('selected/test','parameters',[-4.,.1,.3,.9]),
                                  ('0/train','native_scalar_components',{'joint_nll':float('nan')})]:
            changed=copy.deepcopy(rows);changed[rowid][field]=value
            with self.assertRaises(ValueError):profile_support(group,changed.__getitem__)
        with self.assertRaisesRegex(ValueError,'two-nat'):profile_support(dict(group,descriptive_support_nll_gap=3.),rows.__getitem__)

    def test_additional_actual_row_requires_hash_status_and_registry_input_pins(self):
        from reproduction.score_replay.reconcile_cached_tables import Evidence
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);package=root/'package';package.mkdir();evidence=root/'evidence';evidence.mkdir()
            (package/'cached_registry.json').write_text(json.dumps({'rows':[],'adapters':{}}))
            (evidence/'deltas.json').write_text(json.dumps({'rows':[]}));(evidence/'evidence_index.json').write_text(json.dumps({'files':{}}))
            (package/'extra').mkdir();spec={'id':'tiny','adapter':'adapter','state':{'sha256':'state'},'cache':{'sha256':'cache'}}
            registry=package/'extra/cached_registry.json';registry.write_text(json.dumps({'rows':[spec],'adapters':{'adapter':{'python':{'sha256':'python'},'native':{'sha256':'native'}}}}))
            actual=dict(state_sha256='state',cache_sha256='cache',python_source_sha256='python',native_source_sha256='native',parameters=[.2],components={'joint':-3.})
            row=root/'row.json';row.write_text(json.dumps({'id':'tiny','status':'replayed','passed':True,'actual':actual,'expected':{'joint':999.}}))
            manifest=root/'extra.json';manifest.write_text(json.dumps({'records':{'tiny':{'path':'row.json','sha256':digest(row.read_bytes())}}}))
            pins={'extra/cached_registry.json':digest(registry.read_bytes())}
            data=Evidence(package,evidence,manifest,pins);self.assertEqual(data.row('tiny')['components']['joint'],-3.)
            row.write_text(json.dumps({'id':'tiny','status':'replayed','passed':False,'actual':actual}))
            with self.assertRaisesRegex(ValueError,'actual row changed'):Evidence(package,evidence,manifest,pins).row('tiny')
            manifest.write_text(json.dumps({'records':{'tiny':{'path':'row.json','sha256':digest(row.read_bytes())}}}))
            with self.assertRaisesRegex(ValueError,'failed row'):Evidence(package,evidence,manifest,pins).row('tiny')
            row.write_text(json.dumps({'id':'tiny','status':'replayed','passed':True,'actual':dict(actual,state_sha256='wrong')}))
            manifest.write_text(json.dumps({'records':{'tiny':{'path':'row.json','sha256':digest(row.read_bytes())}}}))
            with self.assertRaisesRegex(ValueError,'input/source identity'):Evidence(package,evidence,manifest,pins).row('tiny')

    def test_semantic_table_cell_mismatch_and_missing_evidence_are_not_successful_coverage(self):
        from reproduction.score_replay.reconcile_cached_tables import reconcile,MissingEvidence
        with tempfile.TemporaryDirectory()as directory:
            root=Path(directory);package=root/'reproduction/score_replay';package.mkdir(parents=True)
            (package/'cached_registry.json').write_text('{}');evidence=root/'evidence';evidence.mkdir();(evidence/'evidence_index.json').write_text('{}')
            cell=dict(id='0:3',display='none',display_type='profile_support_list',expression={'op':'profile','group':'tiny','field':'support_display'})
            table=dict(id='tiny',source_file='tiny.tex',source_rows=[],cells=[cell])
            links=root/'links.json';links.write_text(json.dumps(dict(registry_sha256=digest(b'{}'),source_sha256={},tables=[table])))
            with patch('reproduction.score_replay.reconcile_cached_tables.Evidence')as fake:
                fake.return_value.profiles={};fake.return_value.evaluate.return_value='0.35'
                result=reconcile(root,links,evidence,root/'mismatch.json');self.assertFalse(result['passed']);self.assertEqual(result['tables'][0]['cells'][0]['status'],'mismatch')
                fake.return_value.evaluate.side_effect=MissingEvidence('not_run')
                result=reconcile(root,links,evidence,root/'missing.json');self.assertFalse(result['all_chapter_tables_covered']);self.assertEqual(result['counts']['uncovered_cells'],1)

    def test_table23_declares_every_support_list_including_none(self):
        root=Path(__file__).resolve().parents[1]/'reproduction/score_replay'
        links=json.loads((root/'table_links_cached.json').read_text());table=next(t for t in links['tables']if t['id']=='ch09_audit:table:23')
        self.assertEqual(len(table['cells']),12)
        support=[c for c in table['cells']if c['display_type']=='profile_support_list']
        self.assertEqual([c['display']for c in support],['0.35, 0.50','0.35, 0.50','none','none','none','none'])
        self.assertEqual(len({c['expression']['group']for c in support}),6)

    def test_all94_supplemental_expressions_use_declared_actual_component_rows(self):
        root=Path(__file__).resolve().parents[1]/'reproduction/score_replay'
        links=json.loads((root/'table_links_cached.json').read_text())
        base=json.loads((root/'cached_registry.json').read_text());supp=json.loads((root/'cached_supplement/cached_registry.json').read_text())
        byid={r['id']:r for r in base['rows']+supp['rows']};ids=set();count=0
        def check(expr,phase):
            if expr['op']=='sum':
                for child in expr['terms']:check(child,phase)
            elif expr['op']=='scale':check(expr['value'],phase)
            else:
                self.assertEqual((expr['op'],expr['kind']),('atom','components'))
                self.assertIn(expr['field'],('joint','timing','M','n_events'));self.assertEqual(byid[expr['row']]['phase'],phase);ids.add(expr['row'])
        for table in links['tables']:
            for cell in table['cells']:
                self.assertNotIn('pending_expression',cell)
                if 'supplement_registry'in cell:
                    count+=1;check(cell['expression'],'train'if table['id']=='09_temporal_mark_extensions:table:6'else'test')
        self.assertEqual(count,94);self.assertEqual(len(ids),56)
        self.assertEqual(len(ids&{r['id']for r in supp['rows']}),44)

    def test_supplemental_contrast_ignores_expected_payload_and_missing_is_not_zero(self):
        from reproduction.score_replay.reconcile_cached_tables import Evidence,MissingEvidence
        data=Evidence.__new__(Evidence)
        values={'free':{'components':{'joint':4.},'expected':{'joint':-999.}},'fixed':{'components':{'joint':1.},'expected':{'joint':999.}}}
        def actual(name):
            if name not in values:raise MissingEvidence(name)
            return values[name]
        data.row=actual
        expr={'op':'sum','terms':[{'op':'atom','row':'free','kind':'components','field':'joint'},
                                 {'op':'scale','weight':-1,'value':{'op':'atom','row':'fixed','kind':'components','field':'joint'}}]}
        self.assertEqual(data.evaluate(expr),3.)
        del values['fixed']
        with self.assertRaises(MissingEvidence):data.evaluate(expr)


class CaliforniaPartitionTests(unittest.TestCase):
    def test_observed_blas_matches_scalar_strict_past_and_tiling_controls(self):
        from reproduction.score_replay.observed_replay import tiny_controls
        result=tiny_controls()
        self.assertTrue(result['passed']);self.assertEqual(len(result['rows']),6)
        self.assertLessEqual(max(r['max_absolute_delta'] for r in result['rows']),1e-12)
        json.dumps(result,allow_nan=False)

    def test_observed_saved_floor_indices_are_recovered_not_assumed(self):
        base=Path(__file__).resolve().parents[1]/'reproduction/score_replay/observed_fixedbackbone'
        registry=json.loads((base/'registry.json').read_bytes());inputs=Inputs(base)
        self.assertEqual(len(registry['rows']),6)
        self.assertEqual(len(registry['original_resources']),51)
        for row in registry['rows']:
            selected=inputs.json(row['selected_states'])
            self.assertEqual(selected['models']['LIplus_inclusive']['floor_index'],8 if row['case']=='california_fold_2' else 0)
            self.assertGreater(selected['models']['LIplus_inclusive']['selected'][0],0.)
            for model in selected['models'].values():self.assertEqual(model['floor'][0],0.)
            gated=next(p for p in selected['procedures'] if p['model']=='LIplus_inclusive' and p['gate']=='BIC')
            self.assertEqual(gated['state'],'floor')

    def test_complete_saved_productivity_profile_roster_and_identity(self):
        base=Path(__file__).resolve().parents[1]/'reproduction/score_replay/productivity_profiles'
        registry=json.loads((base/'cached_registry.json').read_bytes());inputs=Inputs(base)
        self.assertEqual(len(registry['rows']),84)
        self.assertEqual(len(registry['profile_groups']),6)
        byid={r['id']:r for r in registry['rows']}
        for group in registry['profile_groups']:
            original=inputs.json(group['profile'])
            self.assertEqual(group['grid'],[0.,.2,.35,.5,.7,.85,.95])
            self.assertEqual(group['descriptive_support_nll_gap'],2.)
            for node in group['nodes']:
                for phase,rowid in node['rows'].items():
                    row=byid[rowid];state=inputs.json(row['state'])
                    self.assertEqual(state['parameters'],original['nodes'][node['index']]['pars'])
                    self.assertEqual(row['profile_r'],node['r'])
                    self.assertEqual(state['parameters'][3 if group['model']=='E0_free' else 4],node['r'])
                    self.assertEqual(state['original_source_sha256'],group['profile']['sha256'])
                    self.assertEqual(row['phase'],phase)

    def test_block_finalizer_union_rejects_missing_duplicate_and_unexpected(self):
        from reproduction.score_replay.finalize_blocks import require_union, terminal_roster
        roster=[{'id':'a'},{'id':'b'},{'id':'c'}]
        self.assertEqual(list(require_union(roster,[{'id':'c'},{'id':'a'},{'id':'b'}])),['c','a','b'])
        for rows in ([{'id':'a'},{'id':'b'}],[{'id':'a'},{'id':'a'},{'id':'c'}],[{'id':'a'},{'id':'b'},{'id':'other'}]):
            with self.assertRaises(ValueError): require_union(roster,rows)
        rows=[{'id':'a','passed':True,'status':'replayed'}]
        launch={'row_ids':['a'],'mode':'pilot'}
        terminal={'schema':'california_partition_replay_result_v1','passed':True,'mode':'pilot','rows':rows,'requested_rows':1,'completed_rows':1,'passed_rows':1,'failed_rows':0}
        self.assertEqual(terminal_roster(terminal,launch,['a','b']),rows)
        for mutation in ({'passed':False},{'completed_rows':0},{'failed_rows':1},{'mode':'completion'},{'rows':[dict(rows[0],status='failed')]}):
            with self.assertRaises(ValueError):terminal_roster(dict(terminal,**mutation),launch,['a','b'])

    def test_block_finalizer_requires_exact_attempt_hashes_and_safe_members(self):
        from reproduction.score_replay.finalize_blocks import Attempt
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);data=b'{"passed":true}'
            folder=root/'stage';folder.mkdir();(folder/'result.json').write_bytes(data)
            attempt=Attempt(root,{'directory':'stage'})
            self.assertTrue(attempt.read('result.json',digest(data))['passed'])
            for member,sha in [('result.json','0'*64),('../result.json',digest(data)),('result.json',None)]:
                with self.assertRaises(ValueError):attempt.read(member,sha)
            archive=root/'stage.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('science/result.json',data)
            spec={'archive':'stage.zip','archive_sha256':digest(archive.read_bytes()),'prefix':'science'}
            self.assertTrue(Attempt(root,spec).read('result.json',digest(data))['passed'])
            with self.assertRaises(ValueError):Attempt(root,dict(spec,archive_sha256='0'*64))

    def test_block_finalizer_imports_reducers_without_native_modules(self):
        import sys
        from reproduction.score_replay.finalize_blocks import reducers_only
        base=Path(__file__).resolve().parents[1]/'reproduction/score_replay/california_blocks'
        registry=json.loads((base/'registry.json').read_text())
        reducers=reducers_only(Inputs(base),registry)
        self.assertEqual(set(reducers),{'annual','sequence'})
        self.assertFalse(any(k.startswith('_california_blocks_finalizer_original.') and k.endswith('.native') for k in sys.modules))

    def test_regional_table_arithmetic_reads_actual_values_and_propagates_tolerance(self):
        from reproduction.score_replay.reconcile_regional_tables import Evidence
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);report=root/'row.json'
            report.write_text(json.dumps({'id':'tiny','passed':True,'status':'replayed','actual':{'components':{'joint':4.}},'comparison':{'expected':999.}}))
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'records':{'tiny':{'path':'row.json','sha256':digest(report.read_bytes())}}}))
            e=Evidence(root,manifest,{'registry_sha256':{}})
            expr={'op':'field','record':'tiny','pointer':'/actual/components/joint','absolute_tolerance':1e-6}
            value,bound=e.evaluate({'op':'divide','numerator':{'op':'sum','terms':[expr,expr]},'denominator':{'op':'constant','value':2}})
            self.assertEqual(value,4.);self.assertEqual(bound,1e-6)
            value,bound=e.evaluate({'op':'multiply','left':expr,'right':{'op':'constant','value':.5}})
            self.assertEqual(value,2.);self.assertEqual(bound,5e-7)
            with self.assertRaisesRegex(ValueError,'actual evaluated'):
                e.evaluate(dict(expr,pointer='/comparison/expected'))
            with self.assertRaisesRegex(KeyError,'missing'):
                e.evaluate(dict(expr,record='unexecuted'))

    def test_california_historical_paths_resolve_exact_bundled_bytes(self):
        import base64,io,types,numpy as np
        from unittest.mock import patch
        base=Path(__file__).resolve().parents[1]/'reproduction/score_replay/california'
        registry=json.loads((base/'registry.json').read_text());inputs=Inputs(base)
        adapter=next(iter(registry['adapters'].values()))
        module=types.ModuleType('tiny_portable_california')
        exec(compile(inputs.read(adapter['python']),'portable_adapter.py','exec'),module.__dict__)
        pins=inputs.json(adapter['historical_pin_manifest'])
        self.assertEqual(len(pins['paths']),21)
        self.assertEqual(len(pins['cache_source_pin_sets']),24)
        for path,spec in pins['paths'].items():
            self.assertEqual(module.digest(path),spec['sha256'])
            self.assertEqual(base64.b64decode(module._HISTORICAL_PIN_BYTES[path]['base64']),inputs.read(spec))
        for sourcepins in pins['cache_source_pin_sets'].values():module.verify_historical_pins(sourcepins)
        with self.assertRaisesRegex(ValueError,'unresolved'):
            module.verify_historical_pins({'Z:\\not_recovered\\objective.dll':'0'*64})
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);binary=root/'current.so';binary.write_bytes(b'current build is a distinct artifact')
            self.assertEqual(module.digest(binary),digest(binary.read_bytes()))
            cache=root/'tiny.npz';sourcepins=next(iter(pins['cache_source_pin_sets'].values()))
            np.savez(cache,metadata_json=json.dumps({'production_source_pins':sourcepins}))
            with patch.object(module,'library',side_effect=RuntimeError('hand-authored construction stop')) as mocked:
                with self.assertRaisesRegex(RuntimeError,'construction stop'):module.Objective(cache,dll_path=binary)
                mocked.assert_called_once_with(binary)
        first=next(iter(module._HISTORICAL_PIN_BYTES));module._HISTORICAL_PIN_BYTES[first]['base64']=base64.b64encode(b'tampered').decode()
        with self.assertRaisesRegex(ValueError,'historical pin byte length'):
            module.digest(first)

    def test_complete_partition_roster_and_original_sources_load_without_dll(self):
        from reproduction.score_replay.california_blocks_replay import load_modules
        base = Path(__file__).resolve().parents[1]/'reproduction/score_replay/california_blocks'
        registry = json.loads((base/'registry.json').read_text())
        self.assertEqual(len(registry['rows']),39)
        self.assertEqual(sum(r['expected_rows'] for r in registry['rows']),185)
        modules = load_modules(Inputs(base),registry)
        partition = modules['sequence']['partition']
        # At the origin an anchor cannot inhibit itself; the next event is active.
        episodes = partition.episodes([10])
        rows = partition.rows_for_range('tiny',0,100,[10,11,99],[6.,4.,4.],episodes,[10])
        self.assertEqual(rows[1]['indices'],[1,2])
        self.assertEqual(rows[2]['indices'],[0])

    def test_partition_comparison_keeps_counts_exact_and_numeric_tolerance_separate(self):
        from reproduction.score_replay.california_blocks_replay import numeric_delta
        checks=numeric_delta({'n_target':3,'joint':1.+5e-7},{'n_target':3,'joint':1.},1e-6)
        self.assertTrue(all(c['passed'] for c in checks))
        checks=numeric_delta({'n_target':4,'joint':1.},{'n_target':3,'joint':1.},1e-6)
        self.assertFalse(all(c['passed'] for c in checks))
        with self.assertRaisesRegex(ValueError,'partition identity'):
            numeric_delta({'membership_sha256':'different'},{'membership_sha256':'bound'},1e-6)

    def test_fresh_dependency_requires_real_passed_state_and_cache_identity(self):
        import numpy as np
        from reproduction.score_replay.california_blocks_replay import checked_fresh
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'native_components.npz'
            np.savez(a,**{'event_log_'+k+'_intensity':np.array([1.]) for k in ('point','cell','zone','ground')})
            row=dict(id='tiny',state={'sha256':'state'},cache={'sha256':'cache'},n_events_expected=1)
            adapter=dict(native={'sha256':'cpp'},python={'sha256':'py'})
            record=dict(id='tiny',passed=True,status='replayed',actual=dict(state_sha256='state',cache_sha256='cache',native_source_sha256='cpp',python_source_sha256='py',components={'n_events':1},native_array_components={'path':a.name,'sha256':digest(a.read_bytes())}))
            p=root/'result.json';p.write_text(json.dumps(record));entry={'result_path':str(p),'sha256':digest(p.read_bytes())}
            logs,_,_=checked_fresh(entry,row,adapter);self.assertEqual(logs['point'].tolist(),[1.])
            with self.assertRaisesRegex(ValueError,'state_sha256'):
                checked_fresh(entry,dict(row,state={'sha256':'different'}),adapter)
            record['passed']=False;p.write_text(json.dumps(record));entry['sha256']=digest(p.read_bytes())
            with self.assertRaisesRegex(ValueError,'passed replay'):
                checked_fresh(entry,row,adapter)


if __name__ == '__main__':
    unittest.main()
