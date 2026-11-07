"""Portable admission checks; Linux lifecycle controls are a separate suite."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts/supervise_research.py'
spec = importlib.util.spec_from_file_location('research_supervisor_spec', PATH)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class SupervisorAdmission(unittest.TestCase):
    def good(self):
        return dict(command=[sys.executable, '-c', 'pass'], cwd=str(PATH.parent),
                    wall_cap_seconds=2., rss_cap_bytes=2**30, sample_seconds=.01)

    def test_valid_argv_and_limits(self):
        supervisor.validate(self.good())

    def test_rejects_nonfinite_negative_and_zero_limits(self):
        for key in ('wall_cap_seconds', 'rss_cap_bytes', 'sample_seconds', 'cleanup_grace_seconds'):
            for value in (float('nan'), float('inf'), -1, 0, True):
                with self.subTest(key=key, value=value), self.assertRaises(supervisor.AdmissionError):
                    supervisor.validate(dict(self.good(), **{key: value}))

    def test_rejects_bad_launch_and_environment_before_creation(self):
        for update in ({'command': 'shell text'}, {'command': []}, {'command': ['bad\0path']},
                       {'cwd': '/missing/supervisor/working_directory'}, {'env': {'BAD=KEY': 'x'}},
                       {'env': {'OK': 3}}, {'sample_seconds': 10}, {'cleanup_grace_seconds': 20}):
            with self.subTest(update=update), self.assertRaises(supervisor.AdmissionError):
                supervisor.validate(dict(self.good(), **update))

    def test_invalid_spec_writes_failure_without_launch(self):
        with tempfile.TemporaryDirectory(prefix='supervisor_admission_') as folder:
            payload = dict(self.good(), wall_cap_seconds=-1)
            output = Path(folder) / 'out'
            code = supervisor.run(payload, json.dumps(payload).encode(), output)
            record = json.loads((output / 'result.json').read_text())
            self.assertEqual(code, 1)
            self.assertFalse(record['launched'])
            self.assertEqual(record['stop_reason'], 'admission_error')

    def test_unsupported_platform_rejects_before_launch(self):
        with tempfile.TemporaryDirectory(prefix='supervisor_platform_') as folder:
            payload = self.good()
            output = Path(folder) / 'out'
            with patch.object(supervisor.sys, 'platform', 'win32'):
                code = supervisor.run(payload, json.dumps(payload).encode(), output)
            record = json.loads((output / 'result.json').read_text())
            self.assertEqual(code, 1)
            self.assertFalse(record['launched'])
            self.assertEqual(record['stop_reason'], 'admission_error')
            self.assertIn('requires Linux', record['error'])


if __name__ == '__main__':
    unittest.main()
