"""Resident variable-backbone CUDA deficit on a single supplied phase instance.

The original likelihood/gradient/optimizer remain unchanged. GPU state holds
only immutable quadrature geometry plus working arrays, never fitted values.
Only one order context is retained: changing order frees the prior workspace.
"""
from pathlib import Path
import ctypes as C
import hashlib,json,math,os,shutil,subprocess
import numpy as np


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(output):
    source=Path(__file__).with_suffix('.cu');dependency=source.parent.parent/'s04b_completion/cuda_immigrant.cu'
    pins={p.name:sha(p) for p in (source,dependency)}
    key=hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest()[:16]
    output=Path(output)/key;output.mkdir(parents=True,exist_ok=True);library=output/'cuda_inclusive.so';receipt=output/'build_receipt.json'
    if receipt.exists():
        saved=json.loads(receipt.read_text())
        if saved['sources_sha256']!=pins or saved['library_sha256']!=sha(library):raise RuntimeError('CUDA inclusive build identity changed')
        return library
    compiler=os.environ.get('CUDA_HOST_CXX') or shutil.which('g++-11') or shutil.which('g++')
    command=['nvcc','-std=c++17','-O3','-ccbin',compiler,'-arch=sm_75','--fmad=false',
      '--prec-div=true','--prec-sqrt=true','-Xcompiler=-fPIC,-ffp-contract=off',
      '-shared',str(source.resolve()),'-lcublas','-o',str(library.resolve())]
    result=subprocess.run(command,capture_output=True,text=True);(output/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('CUDA inclusive compilation failed: '+str(output/'build.log'))
    receipt.write_text(json.dumps(dict(sources_sha256=pins,library_sha256=sha(library),command=command,
      fast_math=False,fused_multiply_add=False,temporal_backbone='Regenerated at every evaluation, including log-c and p derivatives.'),indent=2)+'\n')
    return library


class InclusiveDeficit:
    def __init__(self,phase,library,workspace_bytes=1024**3):
        self.phase=phase;self.original=phase.deficit;self.library=Path(library).resolve()
        self.workspace_bytes=int(workspace_bytes);self.state=None;self.order=None;self.context_history=[]
        self.lib=C.CDLL(str(self.library));D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.lib.ci_create.argtypes=[C.c_int]*3+[D]*8+[C.c_double,C.c_size_t,C.c_char_p,C.c_int]
        self.lib.ci_create.restype=C.c_void_p
        self.lib.ci_evaluate.argtypes=[C.c_void_p,D,D,C.c_char_p,C.c_int];self.lib.ci_evaluate.restype=C.c_int
        self.lib.ci_tile_rows.argtypes=[C.c_void_p];self.lib.ci_tile_rows.restype=C.c_int
        self.lib.ci_free.argtypes=[C.c_void_p];self.lib.ci_free.restype=None
        phase.deficit=self.deficit

    def release_context(self):
        if self.state is not None:self.lib.ci_free(self.state['handle'])
        self.state=None;self.order=None

    def deficit(self,theta,model,order):
        if model!='LIplus_inclusive':return self.original(theta,model,order)
        self.phase.check();theta=np.ascontiguousarray(theta,dtype=np.float64)
        if theta.shape!=(8,) or not np.isfinite(theta).all():raise ValueError('Eight finite coordinates required')
        error=C.create_string_buffer(4096)
        if self.order!=order or self.state is None:
            self.release_context();grid=self.phase.plan(order)
            marks=np.exp(.75*math.log(10)*self.phase.a['parent_excess'])
            arrays=[np.ascontiguousarray(v,dtype=np.float64) for v in
                (self.phase.a['parent_time'],marks,grid['r2'],grid['coeff'],grid['area'],grid['b'],grid['t'],grid['w'])]
            pt,_,r2,_,_,_,t,_=arrays
            handle=self.lib.ci_create(len(pt),len(r2),len(t),*arrays,self.phase.m['T0'],self.workspace_bytes,error,len(error))
            if not handle:raise ArithmeticError(error.value.decode())
            self.state=dict(handle=handle,arrays=arrays,immutable_grid=grid);self.order=order
            self.context_history.append(dict(order=order,space_nodes=len(r2),time_nodes=len(t),parents=len(pt),tile_rows=self.lib.ci_tile_rows(handle)))
        out=np.zeros(9)
        if self.lib.ci_evaluate(self.state['handle'],theta,out,error,len(error)):raise ArithmeticError(error.value.decode())
        if not np.isfinite(out).all():raise ArithmeticError('Nonfinite inclusive CUDA deficit')
        return out

    def receipt(self):
        return dict(backend='Resident variable-backbone total-intensity CUDA deficit',library=str(self.library),library_sha256=sha(self.library),
          source_sha256=sha(Path(__file__).with_suffix('.cu')),chronology_dependency_sha256=sha(Path(__file__).parent.parent/'s04b_completion/cuda_immigrant.cu'),
          adapter_sha256=sha(__file__),contexts=self.context_history,retained_order=self.order,workspace_limit_bytes=self.workspace_bytes,
          objective='Original Phase.evaluate/baseline/event gradients unchanged.',
          temporal='Fresh Omori field and both temporal derivatives per parameter vector; three FP64 cuBLAS products.',
          memory='One quadrature-order context retained; freed on order change. Trigger workspace <= configured limit and half available GPU memory.')

    def close(self):
        if getattr(self.phase.deficit,'__self__',None) is self:self.phase.deficit=self.original
        self.release_context()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
