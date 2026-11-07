"""Compiler-name regression controls; no historical scores or native execution."""
import unittest
from reproduction.score_replay.california_blocks_replay import portable_interval_source
from reproduction.score_replay.core import digest


class PrivateValidatorPortability(unittest.TestCase):
    def test_only_unqualified_validator_identifier_changes(self):
        original = (b'void finite(double v) { check(std::isfinite(v)); }\n'
                    b'finite(1.); finite (2.); std::isfinite(3.); other::finite(4.);')
        changed, record = portable_interval_source('annual', original)
        self.assertEqual(record['replacements'], 3)
        self.assertIn(b'std::isfinite(3.); other::finite(4.);', changed)
        self.assertEqual(changed.replace(b'require_finite', b'finite'), original)
        self.assertEqual(record['original_sha256'], digest(original))
        self.assertEqual(record['compiled_sha256'], digest(changed))

    def test_unrecognized_or_already_adapted_source_rejected(self):
        for original in (b'void finite(double v) { unrelated(v); } finite(1.);',
                         b'void finite(double v) { check(std::isfinite(v)); } require_finite(1.);'):
            with self.assertRaises(ValueError):
                portable_interval_source('annual', original)

    def test_sequence_source_remains_exact(self):
        original = b'bool valid(double v) { return std::isfinite(v); }'
        changed, record = portable_interval_source('sequence', original)
        self.assertEqual(changed, original)
        self.assertEqual(record['kind'], 'unchanged')
        self.assertEqual(record['original_sha256'], record['compiled_sha256'])


if __name__ == '__main__':
    unittest.main()
