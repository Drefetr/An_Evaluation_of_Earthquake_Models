"""Portable build and explicit FP64 ABI for the accepted S04B CPU source."""
from pathlib import Path
import ctypes as C
import hashlib
import json
import os
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent / 'source'
KEYS = ('parents', 'events', 'space', 'times', 'weights', 'meta')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _quote(path):
    value = str(Path(path).resolve())
    if any(c in value for c in '\r\n"&|<>^%!'):
        raise ValueError('Build paths must not contain cmd metacharacters')
    return '"' + value + '"'


def _vcvars():
    configured = os.environ.get('INHIBITORY_VCVARS')
    if configured:
        path = Path(configured).resolve()
        if not path.is_file():
            raise FileNotFoundError('INHIBITORY_VCVARS does not name a file')
        return path
    if shutil.which('cl.exe'):
        return None
    installer = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if installer.is_file():
        result = subprocess.run([str(installer), '-latest', '-products', '*', '-requires',
                                 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                 '-property', 'installationPath'], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            path = Path(line.strip()) / 'VC/Auxiliary/Build/vcvars64.bat'
            if path.is_file():
                return path
    raise FileNotFoundError('Install MSVC C++ tools, use a developer shell, or set INHIBITORY_VCVARS')


def build(output):
    """Compile only. All build products and logs stay in a fresh output path."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    suffix = '.dll' if os.name == 'nt' else ('.dylib' if sys.platform == 'darwin' else '.so')
    libraries = {name: output / (name + suffix) for name in ('cpu', 'radial')}
    targets = [('cpu', SOURCE / 'cpu_reference.cpp'), ('radial', SOURCE / 'radial.cpp')]
    commands = []
    if os.name == 'nt':
        setup = _vcvars()
        lines = ['@echo off', 'setlocal DisableDelayedExpansion']
        if setup:
            lines.extend(['call ' + _quote(setup), 'if errorlevel 1 exit /b %errorlevel%'])
        lines.append('cl.exe /Bv')
        for name, source in targets:
            command = ('cl.exe /nologo /std:c++17 /O2 /DNDEBUG /EHsc /fp:strict /LD ' +
                       _quote(source) + ' /Fo' + _quote(output / (name + '.obj')) +
                       ' /link /OUT:' + _quote(libraries[name]) +
                       ' /IMPLIB:' + _quote(output / (name + '.lib')))
            commands.append(command)
            lines.extend([command, 'if errorlevel 1 exit /b %errorlevel%'])
        batch = output / 'build.cmd'
        batch.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with (output / 'build.log').open('w', encoding='utf-8') as log:
            subprocess.run(['cmd.exe', '/d', '/c', str(batch)], cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
    else:
        compiler = os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            raise FileNotFoundError('A C++17 compiler (g++ or clang++) is required')
        with (output / 'build.log').open('w', encoding='utf-8') as log:
            subprocess.run([compiler, '--version'], stdout=log, stderr=subprocess.STDOUT, check=True)
            for name, source in targets:
                command = [compiler, '-std=c++17', '-O2', '-fPIC', '-shared', '-fno-fast-math',
                           '-ffp-contract=off', str(source), '-o', str(libraries[name])]
                commands.append(command)
                subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, check=True)
    receipt = dict(commands=commands, sources={p.name: sha(p) for p in [SOURCE/'cpu_reference.cpp', SOURCE/'architecture.hpp', SOURCE/'radial.cpp']},
                   libraries={k:dict(file=p.name, sha256=sha(p)) for k,p in libraries.items()})
    (output/'build_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    return libraries


class Native:
    def __init__(self, library):
        self.lib = C.CDLL(str(Path(library).resolve()))
        self.ptr = C.POINTER(C.c_double)
        self.lib.m02_create.argtypes = [C.c_int]*4 + [self.ptr]*6
        self.lib.m02_create.restype = C.c_void_p
        self.lib.m02_integrated.argtypes = [C.c_void_p,C.c_int,C.c_int,self.ptr,self.ptr]
        self.lib.m02_integrated.restype = C.c_int
        self.lib.m02_free.argtypes = [C.c_void_p]
        self.lib.m02_free.restype = None
        self.lib.m02_integrated_error.restype = C.c_char_p

    def create(self, data):
        handle = self.lib.m02_create(*(len(data[k]) for k in KEYS[:4]),
                                    *(data[k].ctypes.data_as(self.ptr) for k in KEYS))
        if not handle:
            raise ArithmeticError(self.lib.m02_integrated_error().decode())
        return handle

    def evaluate(self, handle, parameters, plus, inclusive):
        import numpy as np
        parameters = np.ascontiguousarray(parameters, dtype=np.float64)
        if parameters.shape != (3,):
            raise ValueError('Exactly eta/logell/logpsi required')
        output = np.empty(6, dtype=np.float64)
        status = self.lib.m02_integrated(handle,int(plus),int(inclusive),parameters.ctypes.data_as(self.ptr),output.ctypes.data_as(self.ptr))
        if status or not np.isfinite(output).all():
            raise ArithmeticError(self.lib.m02_integrated_error().decode())
        return output

    def free(self, handle):
        self.lib.m02_free(handle)
