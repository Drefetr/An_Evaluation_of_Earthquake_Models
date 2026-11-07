"""Actual Linux child-lifetime fixtures; no scientific workloads are launched."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import psutil

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/supervise_research.py'


@unittest.skipUnless(sys.platform == 'linux', 'Linux containment fixtures require Linux')
class LinuxSupervisor(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get('SUPERVISOR_TEST_OUTPUT')
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        self.folder = Path(tempfile.mkdtemp(prefix=self._testMethodName + '_', dir=parent))

    def invoke(self, child, update=None, injection=None, interrupt=False):
        source = self.folder / 'worker.py'
        source.write_text(child, encoding='utf-8')
        payload = dict(command=[sys.executable, '-B', str(source)], cwd=str(self.folder),
                       output=str(self.folder / 'run'), wall_cap_seconds=5., rss_cap_bytes=2**30,
                       host_headroom_bytes=0, sample_seconds=.02, cleanup_grace_seconds=.2)
        payload.update(update or {})
        config = self.folder / 'spec.json'
        config.write_text(json.dumps(payload), encoding='utf-8')
        command = [sys.executable, '-B', str(SCRIPT), str(config)]
        if injection:
            wrapper = ("import sys;sys.path.insert(0," + repr(str(SCRIPT.parent)) + ");"
                       "import supervise_research as s;" + injection + ";s.main()")
            command = [sys.executable, '-B', '-c', wrapper, str(config)]
        with (self.folder / 'supervisor.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                if interrupt:
                    until = time.monotonic() + 3
                    while not (self.folder / 'ready').exists() and time.monotonic() < until:
                        time.sleep(.01)
                    self.assertTrue((self.folder / 'ready').exists())
                    process.send_signal(signal.SIGTERM)
                code = process.wait(timeout=15)
            finally:
                # Fixture-only fallback cleanup if the implementation under test
                # fails. Do not leave a sleep process behind in CI.
                if process.poll() is None:
                    tree = psutil.Process(process.pid)
                    children = tree.children(recursive=True)
                    for item in children + [tree]:
                        try:
                            item.kill()
                        except psutil.NoSuchProcess:
                            pass
                    psutil.wait_procs(children, timeout=3)
                    process.wait(timeout=3)
        record = json.loads((self.folder / 'run/result.json').read_text())
        self.assertEqual(code, 0 if record['status'] == 'passed' else 1)
        self.assertEqual(record['survivors_after_cleanup'], [])
        self.assertEqual(record['cleanup_errors'], [])
        return record

    def test_successful_fast_exit(self):
        record = self.invoke("print('complete')\n")
        self.assertEqual(record['status'], 'passed')
        self.assertEqual(record['returncode'], 0)
        self.assertGreater(record['sample_count'], 0)

    def test_timeout(self):
        record = self.invoke('import time;time.sleep(60)\n', {'wall_cap_seconds': .2})
        self.assertEqual(record['stop_reason'], 'wall_cap')
        self.assertEqual(record['status'], 'failed')

    def test_early_parent_exit_with_unobserved_child(self):
        record = self.invoke("import subprocess,sys\nsubprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n",
                             {'sample_seconds': .2})
        self.assertEqual(record['stop_reason'], 'live_descendants_after_parent')
        self.assertGreaterEqual(len(record['known_processes']), 2)

    def test_orphan_in_separate_session_is_still_owned(self):
        record = self.invoke("import subprocess,sys\nsubprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],start_new_session=True)\n",
                             {'sample_seconds': .2})
        self.assertEqual(record['stop_reason'], 'live_descendants_after_parent')
        self.assertGreaterEqual(len(record['known_processes']), 2)

    def test_termination_resistant_child_is_killed(self):
        record = self.invoke('import signal,time\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\ntime.sleep(60)\n',
                             {'wall_cap_seconds': .3})
        self.assertEqual(record['stop_reason'], 'wall_cap')
        self.assertEqual(record['returncode'], -signal.SIGKILL)

    def test_sampling_error_fails_closed_and_cleans(self):
        injection = "s.psutil.virtual_memory=lambda: (_ for _ in ()).throw(s.psutil.AccessDenied())"
        record = self.invoke('import time;time.sleep(60)\n', injection=injection)
        self.assertEqual(record['stop_reason'], 'supervisor_error')
        self.assertIn('AccessDenied', record['error'])

    def test_sampled_rss_cap(self):
        record = self.invoke('import time;time.sleep(60)\n', {'rss_cap_bytes': 1})
        self.assertEqual(record['stop_reason'], 'sampled_process_tree_rss_cap')

    def test_host_headroom_cap(self):
        record = self.invoke('import time;time.sleep(60)\n', {'host_headroom_bytes': psutil.virtual_memory().total + 1})
        self.assertEqual(record['stop_reason'], 'host_memory_headroom')

    def test_missing_executable_retains_failure_receipt(self):
        record = self.invoke('pass\n', {'command': ['/missing/research/executable']})
        self.assertEqual(record['stop_reason'], 'supervisor_error')
        self.assertFalse(record['launched'])
        self.assertIsNone(record['returncode'])

    def test_interrupt_cleans_and_retains_failure(self):
        record = self.invoke("from pathlib import Path\nimport time\nPath('ready').write_text('ready')\ntime.sleep(60)\n", interrupt=True)
        self.assertEqual(record['stop_reason'], 'supervisor_error')
        self.assertIn('InterruptedError', record['error'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
