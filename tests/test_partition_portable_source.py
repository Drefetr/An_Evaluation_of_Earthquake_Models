"""Compiler-name regression controls; no historical scores or native execution."""
import json
from pathlib import Path
import re
import unittest
import zipfile
from reproduction.score_replay.california_blocks_replay import portable_interval_source
from reproduction.score_replay.core import digest


class PrivateValidatorPortability(unittest.TestCase):
    def test_only_unqualified_validator_identifier_changes(self):
        original = (b'void finite(double v) { check(std::isfinite(v)); }\n'
                    b'finite(1.); finite (2.); std::isfinite(3.); other::finite(4.);')
        for kind in ('annual','sequence'):
            with self.subTest(kind=kind):
                changed, record = portable_interval_source(kind, original)
                self.assertEqual(record['replacements'], 3)
                self.assertIn(b'std::isfinite(3.); other::finite(4.);', changed)
                self.assertEqual(changed.replace(b'require_finite', b'finite'), original)
                self.assertEqual(record['original_sha256'], digest(original))
                self.assertEqual(record['compiled_sha256'], digest(changed))

    def test_unrecognized_or_already_adapted_source_rejected(self):
        for original in (b'void finite(double v) { unrelated(v); } finite(1.);',
                         b'void finite(double v) { check(std::isfinite(v)); } require_finite(1.);'):
            for kind in ('annual','sequence'):
                with self.subTest(kind=kind),self.assertRaises(ValueError):
                    portable_interval_source(kind, original)

    def test_unrelated_source_remains_exact(self):
        original = b'bool valid(double v) { return std::isfinite(v); }'
        changed, record = portable_interval_source('unrelated', original)
        self.assertEqual(changed, original)
        self.assertEqual(record['kind'], 'unchanged')
        self.assertEqual(record['original_sha256'], record['compiled_sha256'])

    def test_both_pinned_originals_exact_reverse_and_only_identifier_tokens(self):
        root=Path(__file__).resolve().parents[1]/'reproduction/score_replay/california_blocks'
        registry=json.loads((root/'registry.json').read_bytes())
        expected={'annual':(15,'06f7ccd974d1a436df9c56464e94c0978e322ccaaeb5b9dbd624d67e29da2e01'),
                  'sequence':(13,'96459e4beb387aa5439efe8f788e2aaeb1a56e44652442c954c480ada225f893')}
        tokenize=lambda raw:re.findall(rb'[A-Za-z_]\w*|[^\sA-Za-z_]+',raw)
        for kind,spec in registry['native_libraries'].items():
            with self.subTest(kind=kind),zipfile.ZipFile(root/spec['archive'])as archive:
                raw=archive.read(spec['member']);self.assertEqual(digest(raw),spec['sha256'])
                adapted,record=portable_interval_source(kind,raw)
                self.assertEqual((record['replacements'],digest(adapted)),expected[kind])
                self.assertEqual(adapted.replace(b'require_finite',b'finite'),raw)
                before,after=tokenize(raw),tokenize(adapted);self.assertEqual(len(before),len(after))
                changes=[(a,b)for a,b in zip(before,after)if a!=b]
                self.assertEqual(changes,[(b'finite',b'require_finite')]*expected[kind][0])
                self.assertEqual(archive.read(spec['member']),raw)


if __name__ == '__main__':
    unittest.main()
