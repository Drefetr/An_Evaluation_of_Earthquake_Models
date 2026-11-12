"""CUDA row adapter with the exact CPU formulas and chronological reductions."""
from pathlib import Path
import ctypes as C,hashlib,json,os,shutil,subprocess
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build(output):
    source=Path(__file__).with_name('gpu_pairs.cu');output=Path(output)/sha(source)[:16];output.mkdir(parents=True,exist_ok=True);lib=output/'gpu_pairs.so';receipt=output/'build_receipt.json'
    if receipt.exists():
        r=json.loads(receipt.read_bytes())
        if r['source_sha256']!=sha(source) or r['library_sha256']!=sha(lib):raise RuntimeError('CUDA source/binary changed')
        return lib
    compiler=os.environ.get('CUDA_HOST_CXX') or shutil.which('g++-11') or shutil.which('g++')
    cmd=['nvcc','-std=c++17','-O3','-ccbin',compiler,'-arch=sm_75','--fmad=false','--prec-div=true','--prec-sqrt=true','-Xcompiler=-fPIC,-ffp-contract=off','-shared',str(source.resolve()),'-o',str(lib.resolve())]
    p=subprocess.run(cmd,capture_output=True,text=True);(output/'build.log').write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('CUDA row compilation failed: '+str(output/'build.log'))
    receipt.write_text(json.dumps(dict(command=cmd,source_sha256=sha(source),library_sha256=sha(lib),fast_math=False,scalar_fmad=False,reduction='chronological parent order, one row accumulator'),indent=2)+'\n');return lib

class Native:
    def __init__(self,path,threads=None):
        self.lib=C.CDLL(str(Path(path).resolve()));self.contexts=[];D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.lib.gp_create.argtypes=[C.c_int,D,D,C.c_char_p,C.c_int];self.lib.gp_create.restype=C.c_void_p
        self.lib.gp_free.argtypes=[C.c_void_p];self.lib.gp_free.restype=None
        self.lib.gp_evaluate.argtypes=[C.c_void_p,C.c_int,D,D,D,C.c_int,C.c_int,D,C.c_char_p,C.c_int];self.lib.gp_evaluate.restype=C.c_int
    def evaluate(self,data,marks,fertility,x,mode):
        state=next((r for r in self.contexts if r['marks'] is marks and r['fertility'] is fertility),None)
        error=C.create_string_buffer(4096)
        if state is None:
            handle=self.lib.gp_create(len(marks),np.ascontiguousarray(marks),np.ascontiguousarray(fertility),error,len(error))
            if not handle:raise ArithmeticError(error.value.decode())
            state=dict(marks=marks,fertility=fertility,handle=handle,last_data=None);self.contexts.append(state)
        upload=state['last_data'] is not data;out=np.empty((len(data['t']),6 if mode==0 else 4))
        code=self.lib.gp_evaluate(state['handle'],len(out),np.ascontiguousarray(data['lag']),np.ascontiguousarray(data['r2']),np.ascontiguousarray(x),mode,int(upload),out,error,len(error))
        if code:raise ArithmeticError(error.value.decode())
        if not np.isfinite(out).all():raise ArithmeticError('nonfinite GPU row contraction')
        state['last_data']=data
        return out[:,0],out[:,1:]
    def close(self):
        for state in self.contexts:self.lib.gp_free(state['handle'])
        self.contexts=[]
