"""Optional compiled row contractions; reference NumPy formulas remain in run.py."""
from pathlib import Path
import ctypes as C,hashlib,json,os,subprocess,sys
import numpy as np

def build(output):
    from engine.stage2_followup.native_build import discover_vcvars,quote_batch
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True);source=Path(__file__).with_name('pairs.cpp');dll=output/('pairs.dll' if os.name=='nt' else 'pairs.so')
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();sha=digest(source)
    receipt=output/'build_receipt.json'
    if receipt.exists():
        r=json.loads(receipt.read_bytes())
        if r['source_sha256']==sha and dll.exists() and digest(dll)==r['binary_sha256']:return dll
        raise ValueError('native build inputs changed; use new output directory')
    if os.name=='nt':
        setup=discover_vcvars();commands=['@echo off','setlocal DisableDelayedExpansion']
        if setup:commands+=['call '+quote_batch(setup),'if errorlevel 1 exit /b %errorlevel%']
        commands+=['cl.exe /nologo /std:c++17 /W4 /EHsc /O2 /fp:strict /openmp /LD '+quote_batch(source)+' /Fo'+quote_batch(output/'pairs.obj')+' /link /OUT:'+quote_batch(dll)+' /IMPLIB:'+quote_batch(output/'pairs.lib'),'exit /b %errorlevel%']
        batch=output/'build.cmd';batch.write_text('\n'.join(commands)+'\n');cmd=['cmd.exe','/d','/c',str(batch)]
    else:cmd=['g++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-fopenmp','-shared','-fPIC',str(source),'-o',str(dll)]
    p=subprocess.run(cmd,cwd=output,capture_output=True,text=True);(output/'build.log').write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError('native compilation failed: '+str(output/'build.log'))
    receipt.write_text(json.dumps(dict(source_sha256=sha,binary_sha256=digest(dll),command=cmd,fp_strict=True,openmp=True),indent=2)+'\n');return dll

class Native:
    def __init__(self,dll,threads=4):
        self.lib=C.CDLL(str(Path(dll).resolve()));self.threads=threads;D=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.lib.pairs.argtypes=[C.c_int,C.c_int,D,D,D,D,D,C.c_int,C.c_int,D];self.lib.pairs.restype=None
    def evaluate(self,data,marks,fertility,x,mode):
        out=np.empty((len(data['t']),6 if mode==0 else 4));lag=np.ascontiguousarray(data['lag']);r2=np.ascontiguousarray(data['r2'])
        self.lib.pairs(len(lag),len(marks),lag,r2,np.ascontiguousarray(marks),np.ascontiguousarray(fertility),np.ascontiguousarray(x),mode,self.threads,out)
        return out[:,0],out[:,1:]
