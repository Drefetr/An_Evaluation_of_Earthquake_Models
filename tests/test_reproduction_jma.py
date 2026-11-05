"""Handcrafted JMA bytes: source integrity, grammar, selection and calendar checks."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

import numpy as np

from reproduction.jma import replay
from reproduction.jma.source import geometry_v1 as geometry, eligibility_v2 as eligibility, vectorized


def fixture(*changes):
    """Independent literal one-based JMA columns, with known 2016 JST origin."""
    row = bytearray(b' ' * 96)
    fields = [(1, b'J'), (2, b'2016'), (6, b'01'), (8, b'01'), (10, b'00'), (12, b'00'),
              (14, b'0000'), (18, b'0012'), (22, b'037'), (25, b'0000'), (29, b'0005'),
              (33, b'0138'), (37, b'0000'), (41, b'0007'), (45, b'01234'), (50, b'056'),
              (53, b'45'), (55, b'D'), (56, b'65'), (58, b'W'), (59, b'7'), (60, b'1'),
              (61, b'1'), (65, b'1'), (66, b'123'), (69, b'HANDCRAFTED ONLY'.ljust(24)),
              (93, b'012'), (96, b'K')]
    for col, value in fields + list(changes):
        row[col - 1:col - 1 + len(value)] = value
    return bytes(row)


def decode(raw, year=2016):
    return vectorized.decode(np.frombuffer(raw, dtype=np.uint8).reshape(-1, 96), year)


class JMAReproductionTests(unittest.TestCase):
    def test_failed_replay_writes_machine_readable_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'schema': 'jma_public_input_manifest_v1',
                'archives': [{'year': y} for y in range(2006, 2025)],
                'historical_manifest_sha256': 'invalid'}))
            result = replay.replay(root / 'output', manifest)
            self.assertFalse(result['passed'])
            self.assertIn('UID namespace', result['error'])
            self.assertFalse(json.loads((root / 'output/result.json').read_text())['passed'])

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'keep.txt'
            marker.write_text('original')
            with self.assertRaises(FileExistsError):
                replay.replay(root)
            self.assertEqual(marker.read_text(), 'original')

    def test_wrong_hash_is_rejected_before_zip_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'h2016.zip'
            p.write_bytes(b'not the pinned source')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                replay.verify_file(p, '0' * 64)
            self.assertEqual(replay.verify_file(p, hashlib.sha256(p.read_bytes()).hexdigest()), hashlib.sha256(p.read_bytes()).hexdigest())

    def test_manifest_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in ('../outside.zip', '/outside.zip', 'C:/private.zip', 'folder\\private.zip'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    replay.relative_file(tmp, path)

    def test_framing_rejects_bad_tail_and_keeps_valid_records(self):
        raw = fixture() + b'\n' + fixture((8, b'02')) + b'\n'
        mode, stride, count, final, _ = vectorized.framing(raw)
        self.assertEqual((mode, stride, count, final), ('LF96', 97, 2, True))
        with self.assertRaisesRegex(ValueError, 'FRAMING'):
            vectorized.framing(raw + b'X')

    def test_known_record_scalar_and_vector_agree(self):
        raw = fixture()
        d = decode(raw)
        self.assertEqual(int(d['target']['status'][0]), 0)
        r = replay.scalar_target(raw, 0, 0, b'\n', 2016, 'a' * 64, 'b' * 64, 0)
        self.assertEqual(r['history_key_cs'], 3652 * 8640000)
        self.assertEqual((r['latitude'], r['longitude'], r['depth_km']), (37.0, 138.0, 12.34))
        self.assertEqual((r['x_km'], r['y_km'], r['cell_id'], r['M_tenths']), (0.0, 0.0, 4, 45))

    def test_missing_primary_is_not_replaced_by_large_secondary(self):
        raw = fixture((53, b'  '), (56, b'99'))
        payload = np.frombuffer(raw, dtype=np.uint8).reshape(1, 96)
        d = decode(raw)
        a = replay.adjudicate_unknowns(payload, d)
        self.assertEqual(int(d['target']['status'][0]), 2)
        self.assertTrue(a['initial_target_unknown'][0])
        self.assertTrue(a['nonqualifying_reported_primary'][0])
        self.assertFalse(a['remaining_target_unknown'][0])
        with self.assertRaisesRegex(ValueError, 'membership disagreement'):
            replay.scalar_target(raw, 0, 0, b'\n', 2016, 'a' * 64, 'b' * 64, 0)

    def test_blank_primary_type_retains_initial_uncertainty(self):
        raw = fixture((55, b' '))
        d = decode(raw)
        a = replay.adjudicate_unknowns(np.frombuffer(raw, dtype=np.uint8).reshape(1, 96), d)
        self.assertEqual(int(d['target']['status'][0]), 2)
        self.assertTrue(a['blank_primary_type'][0])
        self.assertTrue(a['nonqualifying_reported_primary'][0])

    def test_nonblank_invalid_primary_remains_unresolved(self):
        raw = fixture((53, b'X5'))
        d = decode(raw)
        a = replay.adjudicate_unknowns(np.frombuffer(raw, dtype=np.uint8).reshape(1, 96), d)
        self.assertTrue(a['remaining_target_unknown'][0])
        self.assertFalse(a['nonqualifying_reported_primary'][0])

    def test_trusted_low_magnitude_excludes_despite_missing_other_field(self):
        d = decode(fixture((53, b'44'), (45, b'     ')))
        self.assertEqual(int(d['target']['status'][0]), 1)
        self.assertEqual(int(d['target']['reason'][0]), 6)  # PRIMARY_BELOW_THRESHOLD

    def test_coarse_depth_requires_documented_location_method(self):
        raw = fixture((45, b'012  '), (60, b'1'))
        self.assertEqual(int(decode(raw)['target']['status'][0]), 2)
        self.assertEqual(int(decode(fixture((45, b'012  '), (60, b'2')))['target']['status'][0]), 0)

    def test_source_jst_year_and_invalid_calendar_are_detected(self):
        self.assertTrue(decode(fixture(), year=2015)['year_mismatch'][0])
        self.assertFalse(decode(fixture((6, b'02'), (8, b'30')))['civil_ok'][0])
        with self.assertRaisesRegex(ValueError, 'membership disagreement'):
            replay.scalar_target(fixture(), 0, 0, b'\n', 2015, 'a' * 64, 'b' * 64, 0)

    def test_region_outer_and_internal_edge_ownership(self):
        self.assertEqual(geometry.cell_at(-600, -800), 0)
        self.assertEqual(geometry.cell_at(600, 800), 8)
        self.assertEqual(geometry.cell_at(-200, -800 / 3), 4)
        self.assertEqual(geometry.cell_at(200, 800 / 3), 8)
        self.assertIsNone(geometry.cell_at(np.nextafter(600., np.inf), 0))
        self.assertIsNone(geometry.cell_at(0, np.nextafter(-800., -np.inf)))

    def test_half_open_test_boundary_and_simultaneous_history(self):
        origin, end = 3652 * 8640000, 4748 * 8640000
        self.assertEqual(eligibility.phase(origin - 1, 0), 'scored_training')
        self.assertEqual(eligibility.phase(origin, 0), 'test')
        self.assertEqual(eligibility.phase(end - 1, 0), 'test')
        self.assertEqual(eligibility.phase(end, 0), 'outside_fold')
        self.assertEqual(eligibility.prebatch_prefix_lengths([10, 10, 11, 12, 12]), (0, 0, 2, 3, 3))

    def test_uid_includes_member_offset_and_original_namespace(self):
        uid, _ = replay.occurrence_uid('a' * 64, 'b' * 64, 0, fixture())
        self.assertNotEqual(uid, replay.occurrence_uid('a' * 64, 'b' * 64, 97, fixture())[0])
        self.assertNotEqual(uid, replay.occurrence_uid('c' * 64, 'b' * 64, 0, fixture())[0])

    def test_expected_array_comparison_detects_wrong_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'expected.npz'
            np.savez(path, history_key_cs=np.array([10, 11], dtype=np.int64))
            checks = replay.compare_arrays({'history_key_cs': np.array([10, 12], dtype=np.int64)}, path)
            self.assertFalse(checks['history_key_cs']['passed'])


if __name__ == '__main__':
    unittest.main()
