"""Compile an explicitly supplied CPU kernel without executing numerical work.

The optional GNU/Clang __declspec macro removes Windows export decoration only.
Source bytes and dependency bytes are never rewritten.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from engine.stage2_followup.native_build import discover_vcvars, library_suffix, quote_batch


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_shared(source, output, dependency_root=None, compiler=None):
    source = Path(source).resolve()
    if not source.is_file() or source.suffix not in ('.cpp', '.cc', '.cxx'):
        raise ValueError('source must be an existing C++ translation unit')
    root = Path(dependency_root).resolve() if dependency_root else source.parent
    if source != root and root not in source.parents:
        raise ValueError('source must lie in dependency_root')
    out = Path(output).resolve()
    if out == root or root in out.parents:
        raise ValueError('Build output must be outside the source/dependency directory')
    dependencies = sorted(p for p in root.rglob('*') if p.is_file() and p.suffix in ('.cpp', '.cc', '.cxx', '.h', '.hpp', '.inc'))
    source_hashes = {p.relative_to(root).as_posix(): digest(p) for p in dependencies}
    use_msvc = compiler == 'msvc' or (compiler is None and os.name == 'nt' and not os.environ.get('CXX'))
    if use_msvc and os.name != 'nt':
        raise ValueError('MSVC requires Windows')
    setup = discover_vcvars() if use_msvc else None
    cxx = None if use_msvc else (compiler or os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++'))
    if not use_msvc and not cxx:
        raise FileNotFoundError('A C++17 compiler is required; no numerical stub is substituted')
    out.mkdir(parents=True, exist_ok=False)
    library = out / (source.stem + library_suffix())
    commands = []
    returncode, error = 1, None
    try:
        if use_msvc:
            lines = ['@echo off', 'setlocal DisableDelayedExpansion']
            if setup:
                lines += ['call ' + quote_batch(setup), 'if errorlevel 1 exit /b %errorlevel%']
            lines.append('cl.exe /Bv')
            command = ('cl.exe /nologo /std:c++17 /O2 /EHsc /fp:strict /LD ' +
                       quote_batch(source) + ' /Fo' + quote_batch(out / (source.stem + '.obj')) +
                       ' /link /OUT:' + quote_batch(library) +
                       ' /IMPLIB:' + quote_batch(out / (source.stem + '.lib')))
            commands.append(command)
            lines += [command, 'if errorlevel 1 exit /b %errorlevel%', 'exit /b 0', '']
            batch = out / 'build.cmd'
            batch.write_text('\n'.join(lines), encoding='utf-8')
            argv = ['cmd.exe', '/d', '/c', str(batch)]
        else:
            # Archived kernels may have an unconditional Windows export spelling.
            # With default ELF/Mach-O visibility, removing it preserves exported C ABI.
            argv = [str(cxx), '-std=c++17', '-O2', '-fPIC',
                    '-dynamiclib' if sys.platform == 'darwin' else '-shared',
                    '-fno-fast-math', '-ffp-contract=off', '-D__declspec(x)=',
                    str(source), '-o', str(library)]
            commands.append(argv)
        with (out / 'build.log').open('w', encoding='utf-8') as log:
            if not use_msvc:
                probe = subprocess.run([str(cxx), '--version'], stdout=log, stderr=subprocess.STDOUT)
                if probe.returncode:
                    raise RuntimeError('Compiler version probe failed')
            returncode = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
    except Exception as exc:
        error = type(exc).__name__ + ': ' + str(exc)
    if any(not (root/name).is_file() or digest(root/name) != expected for name, expected in source_hashes.items()):
        error = 'Source changed during compilation'
    receipt = dict(schema='portable_cpu_shared_build_v1', passed=returncode == 0 and error is None and library.is_file(),
                   source=str(source), source_sha256=digest(source), dependency_root=str(root),
                   dependencies_sha256=source_hashes, library=str(library),
                   library_sha256=digest(library) if library.is_file() else None,
                   compiler_family='msvc' if use_msvc else 'gnu_or_clang',
                   commands=commands, returncode=returncode, error=error,
                   platform=platform.platform(), python=sys.version,
                   fp_policy='source floating-point types preserved; fast-math disabled; FP contraction disabled',
                   export_decoration='source unchanged; GNU/Clang compile-only __declspec macro' if not use_msvc else 'native Windows exports',
                   builder_sha256=digest(__file__), discovery_sha256=digest(Path(__file__).parent/'stage2_followup/native_build.py'),
                   binaries_executed=False)
    (out/'build_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    if not receipt['passed']:
        raise RuntimeError('CPU build failed; see '+str(out/'build_receipt.json'))
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-root', type=Path)
    parser.add_argument('--compiler')
    args=parser.parse_args()
    receipt=build_shared(args.source,args.output,args.dependency_root,args.compiler)
    print(json.dumps({'passed':receipt['passed'],'library':receipt['library']}))


if __name__=='__main__':
    main()
