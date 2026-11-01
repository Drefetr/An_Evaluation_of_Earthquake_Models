"""Caller validates/pins source law and clocks; no experiments on import."""
import ctypes as C
from pathlib import Path
import numpy as np

class StreamingObjective:
    def __init__(self, dll, arrays, law, cpu_authority, clock_mode='paired', order=16):
        self.law=law
        hi,q,lo,gap,mode=cpu_authority._clock(arrays,law,clock_mode)
        self.arrays=[np.ascontiguousarray(v,dtype=np.float64) for v in
                     (hi, np.zeros(len(hi)) if lo is None else lo,gap,q,
                      *law.stress.mixture,*law.trigger.mixture,cpu_authority.OFFSETS,
                      *np.polynomial.legendre.leggauss(order))]
        self.N=len(hi);self.M=len(law.stress.mixture[0]);self.order=order
        self.times=self.arrays[0];self.excess=self.arrays[3]
        if self.M!=len(law.trigger.mixture[0]):raise ValueError('mode count mismatch')
        self.paired=int(mode=='paired_clock');self.gamma=cpu_authority.GAMMA
        self.dll=C.CDLL(str(Path(dll).resolve()));self.fn=self.dll.temporal_objective
        I=C.c_int;D=C.c_double;P=C.POINTER(D)
        self.fn.argtypes=[I,P,P,P,P,I,P,P,P,P,I,P,I,P,P,I,D,D,D,D,D,P,I,P]
        self.fn.restype=I
    def objective(self,pars,kernel=None,ratio=None,gradient=True,free=None):
        if kernel is not None and kernel.key!=self.law.trigger.key:raise ValueError('fixed-kernel adapter')
        ratio=self.law.ratio if ratio is None else ratio
        free=list(range(4)) if free is None else list(free)
        if any(i not in range(4) for i in free):raise ValueError('invalid derivative coordinate')
        p=np.ascontiguousarray(pars,dtype=np.float64)
        if p.shape!=(4,) or not np.isfinite(p).all():raise ValueError('invalid parameters')
        out=np.empty(5);ptr=lambda a:a.ctypes.data_as(C.POINTER(C.c_double))
        hi,lo,gap,q,sw,sr,tw,tr,offsets,z,w=self.arrays
        mask=sum(1<<i for i in free) if gradient else 0
        status=self.fn(self.N,ptr(hi),ptr(lo),ptr(gap),ptr(q),self.M,ptr(sw),ptr(sr),ptr(tw),ptr(tr),
            len(offsets),ptr(offsets),self.order,ptr(z),ptr(w),self.paired,
            self.law.horizon,self.law.coordinate,self.law.beta,self.gamma,ratio,ptr(p),mask,ptr(out))
        if status:raise FloatingPointError('streaming nonfinite/domain failure')
        return (float(out[0]),out[1:][free]) if gradient else float(out[0])
    def close(self):pass
