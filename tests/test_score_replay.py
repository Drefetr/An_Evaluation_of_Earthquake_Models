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


class TestScoreReplay(unittest.TestCase):
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
