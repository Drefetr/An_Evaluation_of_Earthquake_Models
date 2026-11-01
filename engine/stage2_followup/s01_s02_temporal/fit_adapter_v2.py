"""Additive fixed-kernel fit interface; requires controls before use in fits."""
import ctypes as C
import math,time
from dataclasses import asdict
import numpy as np
if __package__:
    from .recursive_adapter import StreamingObjective
else:
    from recursive_adapter import StreamingObjective

class StreamingHistory(StreamingObjective):
    def __init__(self,dll,arrays,law,cpu_authority,*,clock_mode,order=16,deadline=None):
        super().__init__(dll,arrays,law,cpu_authority,clock_mode,order)
        self.deadline=deadline
        self.mark_nll_constant=-len(self.times)*math.log(law.beta)+law.beta*math.fsum(self.excess)
        self.cf=self.dll.temporal_contrast;I=C.c_int;D=C.c_double;P=C.POINTER(D)
        self.cf.argtypes=[I,P,P,P,P,I,P,P,P,P,I,P,I,P,P,I,D,D,D,D,D,D,P,P,P]
        self.cf.restype=I
    def objective(self,*args,**kwargs):
        if self.deadline is not None and time.perf_counter()>=self.deadline:raise TimeoutError('fit deadline')
        return super().objective(*args,**kwargs)
    def contrast(self,null,alternative):
        if self.deadline is not None and time.perf_counter()>=self.deadline:raise TimeoutError('fit deadline')
        if null['trigger']!=alternative['trigger'] or null['trigger']!=asdict(self.law.trigger):raise ValueError('fixed kernel contrast only')
        p0=np.ascontiguousarray(null['pars'],dtype=np.float64);p1=np.ascontiguousarray(alternative['pars'],dtype=np.float64)
        if p0.shape!=(4,) or p1.shape!=(4,) or not np.isfinite(p0).all() or not np.isfinite(p1).all():raise ValueError('invalid contrast points')
        ptr=lambda a:a.ctypes.data_as(C.POINTER(C.c_double))
        hi,lo,gap,q,sw,sr,tw,tr,offsets,z,w=self.arrays;out=np.empty(4)
        r0=null['ratio'];r1=alternative['ratio']
        status=self.cf(self.N,ptr(hi),ptr(lo),ptr(gap),ptr(q),self.M,ptr(sw),ptr(sr),ptr(tw),ptr(tr),len(offsets),ptr(offsets),self.order,ptr(z),ptr(w),self.paired,self.law.horizon,self.law.coordinate,self.law.beta,self.gamma,r0,r1,ptr(p0),ptr(p1),ptr(out))
        if status:raise FloatingPointError('invalid/nonfinite streaming contrast')
        subtract=2*(self.objective(p0,ratio=r0,gradient=False)-self.objective(p1,ratio=r1,gradient=False))
        return dict(statistic=float(out[0]),event_difference=float(out[1]),background_compensator_difference=float(out[2]),trigger_compensator_difference=float(out[3]),nll_subtraction_control=subtract,direct_minus_subtraction=float(out[0])-subtract)

def history_factory(dll,cpu_authority):
    """Bound factory matching RestrictedHistory's constructor for fit drivers.

    Geometry callers that require cached gq/ge or event_logs are unsupported.
    This does not mutate/import the historical module or change its optimizers.
    """
    class RestrictedHistory(StreamingHistory):
        def __init__(self,arrays,law,*,clock_mode,order=16,backend='cpu',context=None,
                     deadline=None,chunk_nodes=32768,host_limit_bytes=128*2**20):
            if backend!='cpu' or context is not None:raise ValueError('streaming CPU only')
            super().__init__(dll,arrays,law,cpu_authority,clock_mode=clock_mode,order=order,deadline=deadline)
    return RestrictedHistory
