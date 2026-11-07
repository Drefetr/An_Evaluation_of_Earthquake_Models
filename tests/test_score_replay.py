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


if __name__ == '__main__':
    unittest.main()
