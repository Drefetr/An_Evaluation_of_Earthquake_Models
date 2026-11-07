"""Invented custody/failure controls; no scientific model execution."""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('joint_portable_saved_checker',
    ROOT / 'experiments/s04b_joint_audit/check.py')
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)


class SavedCheckerControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value), encoding='utf-8')
        return p

    def source_fixture(self):
        target = self.root / C.CHECKER_PATH
        target.parent.mkdir(parents=True)
        target.write_bytes(Path(C.__file__).read_bytes())
        core = self.root / C.CORE_PATH
        core.parent.mkdir(parents=True)
        core.write_bytes(b'constructed core source, not an evaluator\n')
        pins = {C.CHECKER_PATH: C.sha(target), C.CORE_PATH: C.sha(core)}
        p = self.write('source_review.json', {'passed': True, 'reviewed_files_sha256': pins})
        return p, pins

    def test_json_duplicate_and_nonfinite_cannot_relabel_failure(self):
        p = self.root / 'ambiguous.json'
        for text in ('{"passed": false, "passed": true}', '{"x": NaN}', '{"x": Infinity}'):
            p.write_text(text, encoding='utf-8')
            with self.assertRaises(C.AuditError):
                C.read(p)

    def test_directory_paths_reject_traversal_windows_drive_and_backslash(self):
        for name in ('../outside', '/absolute', 'C:/outside', 'sub\\..\\outside'):
            with self.assertRaises(C.AuditError):
                C.safe(self.root, name)
        self.assertEqual(C.safe(self.root, 'cases/example.json'), self.root / 'cases/example.json')

    def test_archive_must_match_extraction_and_not_escape(self):
        payload = self.root / 'case.json'
        payload.write_bytes(b'{}')
        archive = self.root / 'evidence.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('case.json', b'{}')
        C.verify_archive(archive, C.sha(archive), self.root)
        payload.write_bytes(b'{"passed":true}')
        with self.assertRaises(C.AuditError):
            C.verify_archive(archive, C.sha(archive), self.root)
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('../escape', b'{}')
        with self.assertRaises(C.AuditError):
            C.verify_archive(archive, C.sha(archive), self.root)

    def test_source_review_requires_exact_checker_and_core(self):
        p, pins = self.source_fixture()
        with patch.object(C, 'CORE_SHA256', pins[C.CORE_PATH]):
            review, actual = C.verify_source_review(self.root, p, C.sha(p))
            self.assertEqual(actual, pins)
            (self.root / C.CORE_PATH).write_bytes(b'changed')
            with self.assertRaises(C.AuditError):
                C.verify_source_review(self.root, p, C.sha(p))
        review['passed'] = False
        p.write_text(json.dumps(review), encoding='utf-8')
        with self.assertRaises(C.AuditError):
            C.verify_source_review(self.root, p, C.sha(p))

    def test_git_source_map_checks_current_bytes_and_commit(self):
        p, pins = self.source_fixture()
        review = C.read(p)
        def git_bytes(argv, cwd):
            return (Path(cwd) / argv[2].split(':', 1)[1]).read_bytes()
        with patch.object(C.subprocess, 'check_output', side_effect=git_bytes):
            C.verify_reviewed_sources(self.root, 'abcd123', review, review)
            with self.assertRaises(C.AuditError):
                C.verify_reviewed_sources(self.root, '--bad', review, review)
        with patch.object(C.subprocess, 'check_output', return_value=b'different commit'):
            with self.assertRaises(C.AuditError):
                C.verify_reviewed_sources(self.root, 'abcd123', review, review)
        missing = copy.deepcopy(review)
        del missing['reviewed_files_sha256'][C.CORE_PATH]
        with self.assertRaises(C.AuditError):
            C.verify_reviewed_sources(self.root, 'abcd123', missing, review)

    def test_automated_prior_must_not_impersonate_live_agent(self):
        pins = {'checker': 'invented'}
        prior = dict(passed=True, review_kind='automated_saved_output_check',
            live_agent_review=False, live_agent_review_performed=False,
            final_batch_agent_review_required=True, checker_sources_sha256=pins,
            checker_source_review_sha256='review')
        C.verify_prior_kind(prior, pins, 'review')
        for key, value in [('passed', False), ('live_agent_review', True),
                           ('final_batch_agent_review_required', False),
                           ('checker_source_review_sha256', 'unreviewed')]:
            bad = dict(prior, **{key: value})
            with self.assertRaises(C.AuditError):
                C.verify_prior_kind(bad, pins, 'review')
        C.verify_prior_kind(dict(passed=True, reviewer='/root/continuation_cpu'), pins, 'review')
        with self.assertRaises(C.AuditError):
            C.verify_prior_kind(dict(passed=True, reviewer='unknown'), pins, 'review')

    def test_resource_spec_cannot_expand_caps_or_threads(self):
        env = {k: '2' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS',
            'MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')}
        spec = dict(wall_cap_seconds=420, rss_cap_bytes=6000, host_headroom_bytes=2000, env=env)
        review = dict(wall_cap_seconds=420, rss_cap_bytes=6000, host_headroom_bytes=2000)
        admission = dict(wall_seconds=420, independent_review_passed=True, scheduler_review_passed=True)
        config = {'resources': {'numerical_process_tree_rss_cap_bytes':6000, 'minimum_host_free_bytes':2000}}
        C.verify_resource_spec(spec, review, admission, config)
        for key in ('wall_cap_seconds','rss_cap_bytes','host_headroom_bytes'):
            bad = dict(spec, **{key: spec[key]+1})
            with self.assertRaises(C.AuditError):
                C.verify_resource_spec(bad, review, admission, config)
        bad = copy.deepcopy(spec)
        bad['env']['OPENBLAS_NUM_THREADS'] = '4'
        with self.assertRaises(C.AuditError):
            C.verify_resource_spec(bad, review, admission, config)

    def cli(self, output):
        values = dict(repo=self.root,current=self.root,prior=self.root,
            prior_review=self.root/'prior.json',config=self.root/'config.json',
            commit='abcd123',output=output,checker_source_review=self.root/'review.json',
            checker_source_review_sha256='0'*64)
        return [item for key,value in values.items() for item in ('--'+key.replace('_','-'),str(value))]

    def test_main_failure_is_retained_and_cannot_overwrite_previous_receipt(self):
        output = self.root / 'audit.json'
        with patch.object(C, 'audit_saved', side_effect=C.AuditError('invented missing state')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(C.main(self.cli(output)), 1)
        value = C.read(output)
        self.assertFalse(value['passed'])
        self.assertFalse(value['live_agent_review'])
        self.assertTrue(value['final_batch_agent_review_required'])
        frozen = output.read_bytes()
        with self.assertRaises(FileExistsError):
            C.main(self.cli(output))
        self.assertEqual(output.read_bytes(), frozen)

    def test_optimized_python_fails_before_touching_missing_inputs(self):
        output = self.root / 'optimized.json'
        p = subprocess.run([sys.executable,'-O','-B',C.__file__,*self.cli(output)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 1, p.stderr)
        value = C.read(output)
        self.assertFalse(value['passed'])
        self.assertIn('Optimized Python', value['error'])

    def test_missing_source_review_is_failure_not_unchecked_pass(self):
        output = self.root / 'missing_review.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(C.main(self.cli(output)), 1)
        self.assertEqual(C.read(output)['error_type'], 'FileNotFoundError')


if __name__ == '__main__':
    unittest.main()
