"""Build and load the Pathway 2 background-clock deficit DLL."""
from __future__ import annotations

import ctypes as C
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "background_native.cpp"
DEFAULT_OUTPUT = ROOT / "build/pathway2_trend_controls_20261116/native"


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output: Path = DEFAULT_OUTPUT) -> Path:
    from engine.stage2_followup.native_build import discover_vcvars, quote_batch

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_sha = _digest(SOURCE)
    suffix = ".dll" if os.name == "nt" else ".so"
    library = output / ("background_law" + suffix)
    receipt = output / "build_receipt.json"
    if receipt.exists() and library.exists():
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        if saved.get("source_sha256") == source_sha and saved.get("binary_sha256") == _digest(library):
            return library
        raise ValueError("native build inputs changed; use a fresh output directory")
    obj = output / "background_law.obj"
    if os.name == "nt":
        setup = discover_vcvars()
        commands = ["@echo off", "setlocal DisableDelayedExpansion"]
        if setup:
            commands += ["call " + quote_batch(setup), "if errorlevel 1 exit /b %errorlevel%"]
        commands += [
            "cl.exe /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict /LD "
            + quote_batch(SOURCE)
            + " /Fo"
            + quote_batch(obj)
            + " /link /OUT:"
            + quote_batch(library)
            + " /IMPLIB:"
            + quote_batch(output / "background_law.lib"),
            "exit /b %errorlevel%",
        ]
        batch = output / "build.cmd"
        batch.write_text("\n".join(commands) + "\n", encoding="utf-8")
        command = ["cmd.exe", "/d", "/c", str(batch)]
    else:
        compilers = [os.environ.get("CXX"), "g++", "clang++"]
        from shutil import which

        compiler = next((c for c in compilers if c and (os.path.sep in c or which(c))), None)
        if not compiler:
            raise FileNotFoundError("a C++17 compiler is required")
        command = [compiler, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off",
                   "-shared", "-fPIC", str(SOURCE), "-o", str(library)]
    result = subprocess.run(command, cwd=output, capture_output=True, text=True)
    (output / "build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("native compilation failed; see " + str(output / "build.log"))
    receipt.write_text(
        json.dumps(
            dict(schema="pathway2_background_native_build_v1",
                 source_sha256=source_sha, binary_sha256=_digest(library),
                 command=command, fp_strict=True, openmp=False,
                 platform=platform.platform(), python=sys.version),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return library


class NativeLaw:
    """ctypes wrapper for the isolated Pathway 2 deficit integral."""

    def __init__(self, library: Path):
        self.library = C.CDLL(str(Path(library).resolve()))
        ptr = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
        self.library.joint_integral_law.argtypes = [
            C.c_int, C.c_int, C.c_int, C.c_int,
            ptr, ptr, ptr, ptr, ptr, ptr, ptr, ptr, ptr,
            C.c_double, ptr, C.c_int, C.c_double, C.c_double, ptr,
        ]
        self.library.joint_integral_law.restype = C.c_int
        self.library.joint_error.restype = C.c_char_p

    def integrate(self, pt, marks, r2, area, b, t, w, h, theta, clock,
                  orthogonal: bool, orth_c: float, orth_k: float, horizon: float = 1.0):
        out = np.zeros(9)
        inclusive = 1 if h is not None else 0
        if h is None:
            h = np.zeros(1)
        arrays = [np.ascontiguousarray(v, dtype=np.float64)
                  for v in (pt, marks, r2, area, b, t, w, h, theta)]
        clock = np.ascontiguousarray(clock, dtype=np.float64)
        status = self.library.joint_integral_law(
            np.shape(r2)[0], len(pt), len(t), inclusive,
            *arrays, float(horizon), clock,
            1 if orthogonal else 0, float(orth_c), float(orth_k), out,
        )
        if status:
            raise ArithmeticError(self.library.joint_error().decode())
        return out
