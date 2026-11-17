"""Build and load the Pathway 1 annular row-contraction DLL.

The source is compiled with MSVC (or g++ on POSIX) using strict floating point
and OpenMP. A build receipt pins the source and binary hashes. The reference
NumPy formulas in annular.py are used only for auditing, never for fitting when
the DLL is available.
"""
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
SOURCE = HERE / "annular_native.cpp"
DEFAULT_OUTPUT = ROOT / "build" / "pathway1_annular_20261116_joint"


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output: Path = DEFAULT_OUTPUT) -> Path:
    from engine.stage2_followup.native_build import discover_vcvars, quote_batch

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_sha = _digest(SOURCE)
    suffix = ".dll" if os.name == "nt" else ".so"
    library = output / ("annular" + suffix)
    receipt = output / "build_receipt.json"
    if receipt.exists() and library.exists():
        saved = json.loads(receipt.read_text(encoding="utf-8"))
        if saved.get("source_sha256") == source_sha and saved.get("binary_sha256") == _digest(library):
            return library
        raise ValueError("native build inputs changed; use a fresh output directory")
    obj = output / "annular.obj"
    if os.name == "nt":
        setup = discover_vcvars()
        commands = ["@echo off", "setlocal DisableDelayedExpansion"]
        if setup:
            commands += ["call " + quote_batch(setup), "if errorlevel 1 exit /b %errorlevel%"]
        commands += [
            "cl.exe /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict /openmp /LD "
            + quote_batch(SOURCE)
            + " /Fo"
            + quote_batch(obj)
            + " /link /OUT:"
            + quote_batch(library)
            + " /IMPLIB:"
            + quote_batch(output / "annular.lib"),
            "exit /b %errorlevel%",
        ]
        batch = output / "build.cmd"
        batch.write_text("\n".join(commands) + "\n", encoding="utf-8")
        command = ["cmd.exe", "/d", "/c", str(batch)]
    else:
        compilers = [os.environ.get("CXX"), "g++", "clang++"]
        compiler = next((c for c in compilers if c and (os.path.sep in c or _which(c))), None)
        if not compiler:
            raise FileNotFoundError("a C++17 compiler is required")
        command = [compiler, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off",
                   "-fopenmp", "-shared", "-fPIC", str(SOURCE), "-o", str(library)]
    result = subprocess.run(command, cwd=output, capture_output=True, text=True)
    (output / "build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError("native compilation failed; see " + str(output / "build.log"))
    receipt.write_text(
        json.dumps(
            dict(
                schema="pathway1_annular_native_build_v1",
                source_sha256=source_sha,
                binary_sha256=_digest(library),
                command=command,
                fp_strict=True,
                openmp=True,
                platform=platform.platform(),
                python=sys.version,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return library


def _which(name: str) -> bool:
    from shutil import which

    return which(name) is not None


KERNELS = {"mono": 0, "ann1": 1, "ann2": 2, "shield": 3}


class Native:
    """Row contraction returning H, G and their analytic derivatives."""

    def __init__(self, library: Path, threads: int = 1, kernel: str = "mono", scaled: bool = True):
        self.library = C.CDLL(str(Path(library).resolve()))
        self.threads = int(threads)
        self.kernel = kernel
        self.scaled = bool(scaled)
        ptr = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
        self.library.annular_rows.argtypes = [
            C.c_int, C.c_int, ptr, ptr, ptr, ptr, ptr,
            C.c_int, C.c_int, C.c_int, C.c_int, C.c_int, ptr,
        ]
        self.library.annular_rows.restype = None
        self.library.joint_integral_annular.argtypes = [
            C.c_int, C.c_int, C.c_int, C.c_int, ptr, ptr, ptr, ptr, ptr,
            ptr, ptr, ptr, ptr, C.c_double, C.c_int, ptr,
        ]
        self.library.joint_integral_annular.restype = C.c_int

    def joint_integral_annular(self, pt, marks, r2, area, background, times,
                               weights, triggering, theta, horizon,
                               kernel="mono", inclusive=True):
        """Deficit integral and its eight-parameter derivatives (synthetic law)."""
        out = np.zeros(9)
        status = self.library.joint_integral_annular(
            np.shape(r2)[0], len(pt), len(times), 1 if inclusive else 0,
            np.ascontiguousarray(pt, dtype=np.float64),
            np.ascontiguousarray(marks, dtype=np.float64),
            np.ascontiguousarray(r2, dtype=np.float64),
            np.ascontiguousarray(area, dtype=np.float64),
            np.ascontiguousarray(background, dtype=np.float64),
            np.ascontiguousarray(times, dtype=np.float64),
            np.ascontiguousarray(weights, dtype=np.float64),
            np.ascontiguousarray(triggering, dtype=np.float64),
            np.ascontiguousarray(theta, dtype=np.float64),
            float(horizon), KERNELS[kernel], out,
        )
        if status:
            raise ArithmeticError("joint_integral_annular status " + str(status))
        return out

    def rows(self, data, marks, fertility, x, kernel=None, scaled=None, need_h=True, need_g=True):
        """Evaluate all rows for an explicit kernel and scaling."""
        kernel = self.kernel if kernel is None else kernel
        scaled = self.scaled if scaled is None else scaled
        n_rows, n_cols = data["r2"].shape
        lag = np.ascontiguousarray(data["lag"], dtype=np.float64)
        r2 = np.ascontiguousarray(data["r2"], dtype=np.float64)
        out = np.empty((n_rows, 12), dtype=np.float64)
        self.library.annular_rows(
            n_rows,
            n_cols,
            lag,
            r2,
            np.ascontiguousarray(marks, dtype=np.float64),
            np.ascontiguousarray(fertility, dtype=np.float64),
            np.ascontiguousarray(x, dtype=np.float64),
            KERNELS[kernel],
            1 if scaled else 0,
            1 if need_h else 0,
            1 if need_g else 0,
            self.threads,
            out,
        )
        return out

    # Compatibility with the frozen Model.native protocol: mode 0 returns H
    # and its five H derivatives; mode 1 returns G and its three legacy G
    # derivatives (log ell, log psi, gamma).
    def evaluate(self, data, marks, fertility, x, mode):
        out = self.rows(data, marks, fertility, x, need_h=mode == 0, need_g=mode == 1)
        if mode == 0:
            return out[:, 0], out[:, 1:6]
        return out[:, 6], np.stack([out[:, 7], out[:, 8], out[:, 9]], axis=1)
