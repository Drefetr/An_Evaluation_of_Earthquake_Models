"""FP64 CUDA/cuBLAS implementation of original quadrature time marginals."""
from pathlib import Path
import ctypes as C,hashlib,json,subprocess,shutil,os
import numpy as np

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build(output):
    source=Path(__file__).with_name('inhibition_marginal.cu');output=Path(output)/digest(source)[:16];output.mkdir(parents=True,exist_ok=True)
    lib=output/'inhibition_marginal.so';receipt=output/'build_receipt.json'
    if receipt.exists():
        r=json.loads(receipt.read_bytes())
        if r['source_sha256']!=digest(source) or r['library_sha256']!=digest(lib):raise ValueError('CUDA source/binary drift')
        return lib
    compiler=os.environ.get('CUDA_HOST_CXX') or shutil.which('g++-11') or shutil.which('g++')
    command=['nvcc','-std=c++17','-O3','-ccbin',compiler,'-arch=sm_75','--fmad=false','--prec-div=true','--prec-sqrt=true','-Xcompiler=-fPIC,-ffp-contract=off','-shared',str(source.resolve()),'-lcublas','-o',str(lib.resolve())]
    probe=subprocess.run(['nvcc','--version'],capture_output=True,text=True);p=subprocess.run(command,capture_output=True,text=True)
    (output/'build.log').write_text(probe.stdout+p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('CUDA compilation failed: '+str(output/'build.log'))
    receipt.write_text(json.dumps(dict(command=command,nvcc_version=probe.stdout,source_sha256=digest(source),library_sha256=digest(lib),fast_math=False,scalar_fmad=False,gemm='cuBLAS Dgemm, binary64, default math'),indent=2)+'\n');return lib

def marginal(parents,space,times,meta,eta,ell,psi,build_directory,tile=2048):
    path=build(build_directory);lib=C.CDLL(str(path.resolve()));D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
    fun=lib.inhibition_marginal;fun.argtypes=[C.c_int,C.c_int,C.c_int,D,D,D,D,C.c_double,C.c_double,C.c_double,C.c_int,D,C.c_char_p,C.c_int];fun.restype=C.c_int
    p,s,t,m=[np.ascontiguousarray(a,dtype=np.float64) for a in (parents,space,times,meta)];out=np.empty(len(t));error=C.create_string_buffer(4096)
    code=fun(len(p),len(s),len(t),p,s,t,m,float(eta),float(ell),float(psi),tile,out,error,len(error))
    if code:raise ArithmeticError(error.value.decode())
    if not np.isfinite(out).all():raise ArithmeticError('nonfinite CUDA marginal')
    return out,dict(library_sha256=digest(path),source_sha256=digest(Path(__file__).with_name('inhibition_marginal.cu')),tile=tile,precision='float64',gemm='cublasDgemm',library=path.as_posix())
