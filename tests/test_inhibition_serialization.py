"""Constructed output-boundary tests only; no native library or historical input."""
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from reproduction.score_replay.core import write_new
from reproduction.score_replay.inhibition_replay import tiny_native_control


class InventedNative:
    def __init__(self, floor_offset=0.):
        self.created = self.evaluated = self.freed = 0
        self.floor_offset = floor_offset

    def create(self, data):
        self.created += 1
        return data

    def evaluate(self, data, pars, plus, inclusive):
        self.evaluated += 1
        point = 0.
        for event in data['events']:
            point += math.log(math.exp(data['meta'][0]+data['meta'][1]*
                              (2*event[0]/data['meta'][5]-1))*event[3]+event[4])
        result = np.zeros(6, dtype=np.float64)
        result[0] = data['meta'][6]-point-data['meta'][7]
        result[0] += pars[0]*sum(data['space'][:, 2])
        if len(data['events']):
            result[0] += self.floor_offset
        return result

    def free(self, handle):
        self.freed += 1


class NativeControlSerialization(unittest.TestCase):
    def test_passed_numpy_scalar_controls_write_with_unchanged_strict_json_writer(self):
        native = InventedNative()
        controls = tiny_native_control(native)
        self.assertIs(controls['passed'], True)
        self.assertEqual(len(controls['controls']), 6)
        self.assertEqual((native.created, native.evaluated, native.freed), (18, 18, 18))
        for row in controls['controls']:
            self.assertIs(type(row['passed']), bool)
            self.assertIs(type(row['maximum_split_delta']), float)
            if row['eta'] == 0:
                self.assertIs(type(row['analytic_floor_nll_error']), float)
                self.assertEqual(row['analytic_floor_nll_error'], 0.)
            else:
                self.assertIsNone(row['analytic_floor_nll_error'])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'controls.json'
            write_new(path, controls)
            self.assertEqual(json.loads(path.read_text()), controls)

    def test_failed_floor_remains_false_after_output_scalar_conversion(self):
        controls = tiny_native_control(InventedNative(floor_offset=1e-5))
        self.assertIs(controls['passed'], False)
        floors = [r for r in controls['controls'] if r['eta'] == 0]
        self.assertEqual(len(floors), 3)
        self.assertTrue(all(r['passed'] is False and r['analytic_floor_nll_error'] > r['absolute_tolerance']
                            for r in floors))
        self.assertEqual(json.loads(json.dumps(controls, allow_nan=False)), controls)

    def test_original_numpy_boolean_reproduces_the_reported_writer_failure(self):
        # The comparison is unchanged; only its exported Python scalar differs.
        floor_error = abs(float(1.)-np.float64(1.))
        original = True and (floor_error is None or floor_error <= 1e-12)
        self.assertIs(type(original), np.bool_)
        with self.assertRaises(TypeError):
            json.dumps({'passed': original}, allow_nan=False)
        self.assertEqual(json.loads(json.dumps({'passed': bool(original)})), {'passed': True})


if __name__ == '__main__':
    unittest.main()
