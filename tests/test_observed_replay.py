"""Reject scientific omissions/tampering while permitting declared run metadata."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('test_observed_comparator',ROOT/'reproduction/observed/compare.py')
compare=importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


class ObservedReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=compare.load_manifest()
        cls.historical,_=compare.unpack(cls.manifest['historical_result'])
        cls.actual,_=compare.unpack(cls.manifest['completed_refit'])

    def check(self,actual):return compare.compare_records(actual,self.historical,self.manifest)

    def test_actual_completed_refit_is_exact_scientifically(self):
        result=self.check(self.actual)
        self.assertTrue(result['passed'])
        self.assertEqual(result['counts']['numeric'],83506)
        self.assertEqual(result['maximum_absolute_numeric_difference'],0)

    def test_event_contribution_change_fails_even_when_summary_is_unchanged(self):
        actual=copy.deepcopy(self.actual)
        actual['folds']['fold_50']['test_controls']['ml_shared']['order16']['event_log_intensities'][0]+=0.01
        result=self.check(actual)
        self.assertFalse(result['passed'])
        self.assertEqual(result['counts']['numeric_differences'],1)
        self.assertIn('event_log_intensities/0',result['scientific_differences'][0]['path'])

    def test_missing_fold_cannot_pass(self):
        actual=copy.deepcopy(self.actual);del actual['folds']['fold_65']
        self.assertFalse(self.check(actual)['passed'])

    def test_missing_optimizer_record_cannot_pass_with_unchanged_best_score(self):
        actual=copy.deepcopy(self.actual);actual['folds']['fold_80']['fit']['records'].pop()
        result=self.check(actual)
        self.assertFalse(result['passed'])
        self.assertTrue(any(r['kind']=='list_length' for r in result['scientific_differences']))

    def test_input_binding_and_source_binding_tampering_fail(self):
        for field in ('input_binding','source_hashes','array_binding'):
            with self.subTest(field=field):
                actual=copy.deepcopy(self.actual)
                key=next(iter(actual[field]));actual[field][key]='altered'
                self.assertFalse(self.check(actual)['passed'])

    def test_changed_protocol_is_not_a_free_metadata_exception(self):
        actual=copy.deepcopy(self.actual);actual['protocol_sha256']='0'*64
        result=self.check(actual)
        self.assertFalse(result['passed'])
        self.assertTrue(any(r['kind']=='identity_mismatch' for r in result['identity_and_completion_issues']))

    def test_legitimate_elapsed_time_difference_is_reported_and_allowed(self):
        actual=copy.deepcopy(self.actual);actual['folds']['fold_50']['elapsed_seconds']+=3
        result=self.check(actual)
        self.assertTrue(result['passed'])
        self.assertTrue(any(r['path']=='/folds/fold_50/elapsed_seconds' for r in result['metadata_changes']))

    def test_removed_or_new_timing_field_is_not_silently_discarded(self):
        actual=copy.deepcopy(self.actual);del actual['folds']['fold_50']['elapsed_seconds']
        self.assertFalse(self.check(actual)['passed'])
        actual=copy.deepcopy(self.actual);actual['folds']['fold_50']['elapsed_seconds_extra']=1
        self.assertFalse(self.check(actual)['passed'])

    def test_negative_timing_and_wrong_native_thread_count_fail(self):
        actual=copy.deepcopy(self.actual);actual['folds']['fold_50']['elapsed_seconds']=-1
        self.assertFalse(self.check(actual)['passed'])
        actual=copy.deepcopy(self.actual);actual['environment']['native_threads']=2
        self.assertFalse(self.check(actual)['passed'])

    def test_environment_version_change_is_recorded_without_assuming_numeric_equivalence(self):
        actual=copy.deepcopy(self.actual);actual['environment']['scipy']='different-version'
        result=self.check(actual)
        self.assertTrue(result['passed'])
        actual['folds']['fold_50']['fit']['beta_train']+=1e-10
        self.assertFalse(self.check(actual)['passed'])

    def test_incomplete_run_and_failed_control_fail(self):
        actual=copy.deepcopy(self.actual);actual['complete']=False
        self.assertFalse(self.check(actual)['passed'])
        actual=copy.deepcopy(self.actual);actual['folds']['fold_50']['test_controls']['ml_shared']['pass']=False
        self.assertFalse(self.check(actual)['passed'])

    def test_duplicate_keys_and_nonfinite_json_are_rejected(self):
        for text in ('{"value":1,"value":2}','{"value":NaN}','{"value":Infinity}'):
            with self.subTest(text=text),self.assertRaises(ValueError):compare.strict_json(text)

    def test_physical_source_tampering_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'engine').mkdir()
            source=root/'engine/core.py';source.write_bytes(b'original')
            protocol={'source_hashes':{'core.py':compare.digest(b'original')}}
            payload=json.dumps(protocol).encode();(root/'protocol.json').write_bytes(payload)
            (root/'data.csv').write_bytes(b'csv')
            manifest={'current_protocol':{'path':'protocol.json','sha256':compare.digest(payload)},
                      'all_protocol_source_hashes':protocol['source_hashes'],'bundled_csv':'data.csv',
                      'required_input_binding':{'sha256':compare.digest(b'csv')}}
            compare.verify_repository(manifest,root)
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash_or_size'):compare.verify_repository(manifest,root)

    def test_existing_comparison_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'report.json';output.write_bytes(b'keep')
            self.assertEqual(compare.main(['--output',str(output)]),2)
            self.assertEqual(output.read_bytes(),b'keep')


if __name__=='__main__':unittest.main()
