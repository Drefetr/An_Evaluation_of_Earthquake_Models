"""Independent invented-evidence controls; never assemble the actual cohort."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPOSITORY = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(REPOSITORY))
from scripts import build_joint_disposition_report as B
from scripts import render_joint_disposition_results as R
from scripts import verify_claims as V
from tests.test_joint_disposition_wall_failure import WallEvidence
from tests.test_joint_disposition_reporting import write

HELPER_DIRECTORY = Path(__file__).resolve().parent.parent/'joint_wall_failure_reporting_portable_refs'
sys.path.insert(0, str(HELPER_DIRECTORY))
spec = importlib.util.spec_from_file_location('independent_registry_fixture', HELPER_DIRECTORY/'test_assemble_registry.py')
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)
H.REPOSITORY = str(REPOSITORY)


class IndependentControls(unittest.TestCase):
    def test_wall_fragment_numbers_have_real_bindings_and_identifiers_do_not(self):
        with tempfile.TemporaryDirectory() as temp:
            f = WallEvidence(Path(temp))
            before = (f.repo/f.paths['index']).read_bytes()
            report, _ = B.build(f.repo, f.paths)
            tex, claims = R.render(report, 'validation/invented_report.json', '1'*64)
            self.assertEqual(V.manuscript_numbers(tex), {V.numeric_value(c['display']) for c in claims})
            self.assertEqual(V.manuscript_numbers(r'\path{'+B.WALL_CASE+'}'), set())
            self.assertTrue(any(c['json_pointer']=='/counts/wall_time_failure_histories' for c in claims))
            self.assertTrue(all(not c['json_pointer'].startswith('/failure_census/') for c in claims))
            for claim in claims:
                self.assertIsNotNone(V.resolve(report, claim['json_pointer']))
            self.assertEqual(before, (f.repo/f.paths['index']).read_bytes())
            self.assertEqual(report['resource_evidence']['index_budget'], f.index['budget'])
            self.assertEqual(report['resource_evidence']['final_live_resource'], f.index_review['resource'])

    def test_wall_and_unknown_remain_distinct_nulls_with_all_historical_comparators(self):
        with tempfile.TemporaryDirectory() as temp:
            f = WallEvidence(Path(temp)); report, _ = B.build(f.repo, f.paths)
            missing = [r for r in report['outcomes'] if r['availability']=='unavailable']
            self.assertEqual(len(missing), 10)
            self.assertEqual({r['case_id'] for r in missing}, {B.WALL_CASE, B.UNKNOWN_CASE})
            self.assertEqual(len(report['unknown_census']), 1)
            self.assertEqual(len(report['failure_census']), 1)
            for row in missing:
                self.assertTrue(all(row[key] is None for key in B.NULL_FIELDS))
                self.assertEqual(set(row['historical_comparators']),
                                 {'fixed_floor_gain','intercept_only_gain','fixed_floor','intercept_only'})
            for row in report['regime_summary']:
                self.assertEqual(row['planned_histories'], 20)
                if row['regime'] in (5, 6):
                    self.assertFalse(row['statistics_available'])
                    self.assertIsNone(row['full_regime'])
            self.assertFalse(report['scientific_completion'])
            self.assertFalse(report['original_publication_gate_satisfied'])

    def test_new_reporting_references_cannot_point_to_private_copies(self):
        for key in ('source_review','sealed_index','sealing_review'):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                f = WallEvidence(Path(temp)); refs = f.registry['operational_continuation']
                copied = 'private/'+key+'.json'; target = f.repo/copied
                target.parent.mkdir(); target.write_bytes((f.repo/refs[key]['path']).read_bytes())
                refs[key] = dict(path=copied, sha256=B.sha(target)); f.finish()
                with self.assertRaisesRegex(ValueError, 'public|Public'):
                    B.build(f.repo, f.paths)

    def test_private_assembler_rejects_private_operational_copies(self):
        H.RegistryControls.setUpClass()
        f = H.RegistryControls('test_mixed_registry_is_exact_deterministic_and_does_not_report')
        f.setUp()
        try:
            refs = f.f.registry['operational_continuation']
            for key in ('source_review','sealed_index','sealing_review'):
                copied = 'private/'+key+'.json'; target = f.f.repo/copied
                target.parent.mkdir(exist_ok=True)
                target.write_bytes((f.f.repo/refs[key]['path']).read_bytes())
                refs[key] = dict(path=copied, sha256=B.sha(target))
            with self.assertRaisesRegex(ValueError, 'public|Public'):
                f.prepare()
        finally:
            f.doCleanups()


if __name__ == '__main__':
    unittest.main()
