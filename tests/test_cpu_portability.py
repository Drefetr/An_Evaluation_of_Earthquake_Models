"""Portable compilation and explicit CPU backend controls, without study fits."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from engine.cpu_build import build_shared


class PortableCpu(unittest.TestCase):
    def test_compiled_export_and_poisson_objective_preserve_source(self):
        with tempfile.TemporaryDirectory(prefix='cpu_abi_fixture_') as directory:
            root = Path(directory)
            source = root / 'source' / 'fixture.cpp'
            source.parent.mkdir()
            # The generic builder must accept preserved Windows-decorated
            # sources on Linux without changing even their export spelling.
            source.write_text('#include <cmath>\nextern "C" __declspec(dllexport) '
                              'double poisson(double rate) { return 10*rate-2*std::log(rate); }\n',
                              encoding='utf-8')
            identity = hashlib.sha256(source.read_bytes()).hexdigest()
            receipt = build_shared(source, root / 'build')
            self.assertTrue(receipt['passed'])
            self.assertFalse(receipt['binaries_executed'])
            self.assertEqual(identity, receipt['source_sha256'])
            self.assertEqual(identity, hashlib.sha256(source.read_bytes()).hexdigest())
            # A child process releases the DLL before TemporaryDirectory cleanup
            # on Windows. This is a real compiled analytic objective, not a stub.
            code = ('import ctypes, math, sys; p=ctypes.CDLL(sys.argv[1]); '
                    'p.poisson.argtypes=[ctypes.c_double]; p.poisson.restype=ctypes.c_double; '
                    'value=p.poisson(.2); assert abs(value-(2-2*math.log(.2)))<1e-12; print(value)')
            executed = subprocess.run([sys.executable, '-B', '-c', code, receipt['library']],
                                      capture_output=True, text=True, timeout=30)
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertGreater(float(executed.stdout), 0)

    def test_compiler_cannot_write_into_source_tree(self):
        with tempfile.TemporaryDirectory(prefix='cpu_path_fixture_') as directory:
            root = Path(directory)
            source = root / 'fixture.cpp'
            source.write_text('int fixture=1;\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'outside'):
                build_shared(source, root / 'build')

    def test_cpu_route_does_not_accept_a_fake_cuda_context(self):
        code = Path(__file__).resolve().parents[1] / 'engine/iteration_27/code'
        sys.path.insert(0, str(code))
        from engine.cpu_fit import fit_pair
        with self.assertRaisesRegex(ValueError, 'CPU route'):
            fit_pair(None, None, {}, object(), 0, backend='cpu')
        with self.assertRaisesRegex(ValueError, 'CUDA context'):
            fit_pair(None, None, {}, None, 0, backend='cuda')


if __name__ == '__main__':
    unittest.main()
