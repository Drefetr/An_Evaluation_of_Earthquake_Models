"""Portable C++17 build entry point for registered Stage 2 native sources.

Compilation only: no simulation, fit, oracle replay or fixture is executed.
Outputs must be outside the source directories and in a fresh directory.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import platform

HERE = Path(__file__).resolve().parent


def library_suffix():
    return '.dll' if os.name == 'nt' else ('.dylib' if sys.platform == 'darwin' else '.so')


def executable_suffix():
    return '.exe' if os.name == 'nt' else ''


def discover_vcvars(explicit=None):
    """Use an explicit setup script, a configured developer shell, or vswhere."""
    configured = explicit or os.environ.get('INHIBITORY_VCVARS')
    if configured:
        path = Path(configured).resolve()
        if not path.is_file():
            raise FileNotFoundError('INHIBITORY_VCVARS/--vcvars must name vcvars64.bat')
        return path
    if shutil.which('cl.exe'):
        return None
    installer = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if installer.is_file():
        result = subprocess.run([str(installer), '-latest', '-products', '*',
                                 '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                                 '-property', 'installationPath'],
                                capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            path = Path(line.strip()) / 'VC/Auxiliary/Build/vcvars64.bat'
            if path.is_file():
                return path
    raise FileNotFoundError('MSVC C++ tools unavailable. Use a developer shell or set INHIBITORY_VCVARS/--vcvars.')


def quote_batch(path):
    value = str(Path(path).resolve())
    if any(c in value for c in '\r\n"&|<>^%!'):
        raise ValueError('Native build paths must not contain cmd metacharacters')
    return '"' + value + '"'


def targets(group):
    temporal = HERE / 's01_s02_temporal'
    spatial = HERE / 's03_s06_spatial_benchmarks'
    li = HERE / 's04_s04b_local_inhibition'
    selected = {
        'temporal': [('temporal_stage2.dll', temporal / 'cached_stage2.cpp'),
                     ('mdfhp_cli.exe', temporal / 'r_matched/main.cpp')],
        'spatial': [('radial.dll', spatial / 'radial.cpp')],
        'li': [('fixture.exe', li / 'fixture.cpp'), ('engine.dll', li / 'engine.cpp'),
               ('integrated.dll', li / 'integrated.cpp'), ('radial.dll', spatial / 'radial.cpp')],
        's06': [('core.dll', spatial / 's06/core.cpp'),
                ('competitive.dll', spatial / 's06/competitive.cpp')],
    }[group]
    return [(name.replace('.dll', library_suffix()).replace('.exe', executable_suffix()), source)
            for name, source in selected]


def build_posix(group, output, compiler=None):
    """Compile real kernels with GNU/Clang; missing compilers are errors."""
    out = Path(output).resolve()
    if out == HERE or HERE in out.parents:
        raise ValueError('Use a build directory outside engine/stage2_followup')
    selected = targets(group)
    for _, source in selected:
        if not source.is_file():
            raise FileNotFoundError(source)
    cxx = compiler or os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++')
    if not cxx:
        raise FileNotFoundError('A C++17 g++ or clang++ compiler is required; no numerical stub is substituted')
    out.mkdir(parents=True, exist_ok=False)
    commands, returncode, failure = [], 1, None
    try:
        with (out / 'build.log').open('w', encoding='utf-8') as log:
            probe = subprocess.run([str(cxx), '--version'], stdout=log, stderr=subprocess.STDOUT)
            if probe.returncode:
                raise RuntimeError('Compiler version probe failed')
            for name, source in selected:
                command = [str(cxx), '-std=c++17', '-O2', '-Wall', '-Wextra',
                           '-fno-fast-math', '-ffp-contract=off']
                if name.endswith(library_suffix()):
                    command += ['-fPIC', '-dynamiclib' if sys.platform == 'darwin' else '-shared']
                command += [str(source), '-o', str(out / name)]
                commands.append(command)
                returncode = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
                if returncode:
                    break
    except Exception as exc:
        failure = type(exc).__name__ + ': ' + str(exc)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    sources = [p for p in HERE.rglob('*') if p.suffix in {'.cpp', '.hpp'}]
    receipt = {'schema': 'stage2_native_build_v2', 'group': group,
               'returncode': returncode, 'error': failure, 'binaries_executed': False,
               'platform': platform.platform(), 'python': sys.version, 'commands': commands,
               'fast_math': False, 'fp_contraction': False,
               'source_sha256': {p.relative_to(HERE).as_posix(): digest(p) for p in sorted(sources)},
               'builder_sha256': digest(Path(__file__)),
               'binary_sha256': {name: digest(out / name) for name, _ in selected if (out / name).is_file()}}
    (out / 'build_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    if returncode or failure:
        raise RuntimeError('Native build failed; see ' + str(out / 'build_receipt.json'))
    return receipt


def build(group, output, vcvars=None, compiler=None):
    if os.name != 'nt':
        return build_posix(group, output, compiler)
    if compiler and compiler != 'msvc':
        return build_posix(group, output, compiler)
    setup = discover_vcvars(vcvars)
    out = Path(output).resolve()
    if out == HERE or HERE in out.parents:
        raise ValueError('Use a build directory outside engine/stage2_followup')
    selected = targets(group)
    for _, source in selected:
        if not source.is_file():
            raise FileNotFoundError(source)
    for path in [out, *(p for _, p in selected), *([setup] if setup else [])]:
        quote_batch(path)
    out.mkdir(parents=True, exist_ok=False)
    commands = ['@echo off', 'setlocal DisableDelayedExpansion']
    if setup:
        commands += ['call ' + quote_batch(setup), 'if errorlevel 1 exit /b %errorlevel%']
    commands.append('cl.exe /Bv')
    for name, source in selected:
        obj = out / (Path(name).stem + '.obj')
        command = 'cl.exe /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict '
        if name.endswith('.dll'):
            command += '/LD '
        command += quote_batch(source) + ' /Fo' + quote_batch(obj)
        if name.endswith('.dll'):
            command += ' /link /OUT:' + quote_batch(out / name) + ' /IMPLIB:' + quote_batch(out / (Path(name).stem + '.lib'))
        else:
            command += ' /Fe:' + quote_batch(out / name)
        commands += [command, 'if errorlevel 1 exit /b %errorlevel%']
    commands += ['exit /b 0', '']
    batch = out / 'build.cmd'
    batch.write_text('\n'.join(commands), encoding='utf-8')
    result = subprocess.run(['cmd.exe', '/d', '/c', str(batch)], cwd=out,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (out / 'build.log').write_text(result.stdout, encoding='utf-8')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    sources = [p for p in HERE.rglob('*') if p.suffix in {'.cpp', '.hpp'}]
    receipt = {'schema': 'stage2_native_build_v2', 'group': group,
               'returncode': result.returncode, 'binaries_executed': False,
               'platform': platform.platform(), 'python': sys.version,
               'commands': commands, 'fast_math': False, 'fp_contraction': False,
               'source_sha256': {p.relative_to(HERE).as_posix(): digest(p) for p in sorted(sources)},
               'builder_sha256': digest(Path(__file__)),
               'binary_sha256': {name: digest(out / name) for name, _ in selected if (out / name).is_file()}}
    (out / 'build_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    if result.returncode:
        raise RuntimeError('Native build failed; see ' + str(out / 'build.log'))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('temporal', 'spatial', 'li', 's06'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vcvars', type=Path, help='Optional explicit vcvars64.bat; otherwise use developer shell/vswhere')
    parser.add_argument('--compiler', help='C++17 compiler executable; defaults to MSVC on Windows and CXX/g++/clang++ elsewhere')
    args = parser.parse_args()
    build(args.group, args.output, args.vcvars, args.compiler)


if __name__ == '__main__':
    main()
