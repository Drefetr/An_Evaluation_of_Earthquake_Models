"""Optional whole-plan CUDA immigrant deficit, leaving Phase.evaluate intact.

Only LIplus_immigrant uses this backend. All other models keep the exact
supplied phase implementation. The frozen CPU source is not edited. Callers
must validate same-state scores/gradients before using this in a search.
"""
from pathlib import Path
import ctypes as C
import hashlib
import json
import math
import os
import shutil
import subprocess
import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output):
    source=Path(__file__).with_suffix('.cu');output=Path(output)/sha(source)[:16]
    output.mkdir(parents=True,exist_ok=True);library=output/'cuda_immigrant.so';receipt=output/'build_receipt.json'
    if receipt.exists():
        saved=json.loads(receipt.read_text())
        if saved['source_sha256']!=sha(source) or saved['library_sha256']!=sha(library):
            raise RuntimeError('CUDA build identity changed')
        return library
    compiler=os.environ.get('CUDA_HOST_CXX') or shutil.which('g++-11') or shutil.which('g++')
    command=['nvcc','-std=c++17','-O3','-ccbin',compiler,'-arch=sm_75','--fmad=false',
        '--prec-div=true','--prec-sqrt=true','-Xcompiler=-fPIC,-ffp-contract=off',
        '-shared',str(source.resolve()),'-o',str(library.resolve())]
    result=subprocess.run(command,capture_output=True,text=True)
    (output/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('CUDA compilation failed: '+str(output/'build.log'))
    receipt.write_text(json.dumps(dict(source_sha256=sha(source),library_sha256=sha(library),command=command,
        reduction='Chronological recurrence per spatial row, ascending spatial-row host sum.',
        fast_math=False,fused_multiply_add=False),indent=2)+'\n')
    return library


class ImmigrantDeficit:
    """Install a backend on one phase instance; restore it on close().

    Per-order quadrature arrays are immutable and retained by this object.
    There is no fitted-parameter cache: every call recomputes the entire deficit.
    """
    def __init__(self,phase,library):
        self.phase=phase;self.original=phase.deficit;self.contexts={}
        self.library=Path(library).resolve();self.lib=C.CDLL(str(self.library))
        D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.lib.cim_create.argtypes=[C.c_int]*3+[D]*7+[C.c_double,C.c_char_p,C.c_int]
        self.lib.cim_create.restype=C.c_void_p
        self.lib.cim_evaluate.argtypes=[C.c_void_p,D,D,C.c_char_p,C.c_int]
        self.lib.cim_evaluate.restype=C.c_int
        self.lib.cim_free.argtypes=[C.c_void_p];self.lib.cim_free.restype=None
        phase.deficit=self.deficit

    def deficit(self,theta,model,order):
        if model!='LIplus_immigrant':return self.original(theta,model,order)
        self.phase.check();theta=np.ascontiguousarray(theta,dtype=np.float64)
        if theta.shape!=(8,) or not np.isfinite(theta).all():raise ValueError('Eight finite coordinates required')
        state=self.contexts.get(order);error=C.create_string_buffer(4096)
        if state is None:
            grid=self.phase.plan(order)
            marks=np.exp(.75*math.log(10)*self.phase.a['parent_excess'])
            arrays=[np.ascontiguousarray(v,dtype=np.float64) for v in
                (self.phase.a['parent_time'],marks,grid['r2'],grid['area'],grid['b'],grid['t'],grid['w'])]
            pt,_,r2,_,_,t,_=arrays
            handle=self.lib.cim_create(len(pt),len(r2),len(t),*arrays,self.phase.m['T0'],error,len(error))
            if not handle:raise ArithmeticError(error.value.decode())
            state=dict(handle=handle,arrays=arrays,space_nodes=len(r2),time_nodes=len(t),parents=len(pt),
                       immutable_grid=grid);self.contexts[order]=state
        out=np.zeros(9)
        if self.lib.cim_evaluate(state['handle'],theta,out,error,len(error)):
            raise ArithmeticError(error.value.decode())
        if not np.isfinite(out).all():raise ArithmeticError('Nonfinite GPU integral')
        return out

    def receipt(self):
        return dict(backend='Whole-plan immigrant-only CUDA deficit',library=str(self.library),
            library_sha256=sha(self.library),source_sha256=sha(Path(__file__).with_suffix('.cu')),
            adapter_sha256=sha(__file__),orders={str(k):{name:v[name] for name in ('space_nodes','time_nodes','parents')} for k,v in self.contexts.items()},
            objective='Original Phase.evaluate and baseline/event-score source unchanged.',
            summation='Chronological recurrence per row; deterministic ascending row reduction; no atomics.')

    def close(self):
        if getattr(self.phase.deficit,'__self__',None) is self:self.phase.deficit=self.original
        for state in self.contexts.values():self.lib.cim_free(state['handle'])
        self.contexts={}

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
