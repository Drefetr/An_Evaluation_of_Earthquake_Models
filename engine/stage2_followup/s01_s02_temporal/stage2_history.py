import ctypes as C
import numpy as np
if __package__:
 from .fit_adapter_v2 import StreamingHistory
else:
 from fit_adapter_v2 import StreamingHistory

class CachedHistory(StreamingHistory):
 def __init__(self,*args,cache_bytes=512*2**20,**kwargs):
  super().__init__(*args,**kwargs);I=C.c_int;D=C.c_double;P=C.POINTER(D)
  self.dll.feature_create.argtypes=[I,P,P,P,P,I,P,P,P,P,I,P,I,P,P,I,D,D,D,D,D,D];self.dll.feature_create.restype=C.c_void_p
  self.dll.feature_destroy.argtypes=[C.c_void_p];self.dll.feature_destroy.restype=None
  self.dll.feature_objective.argtypes=[C.c_void_p,P,I,P];self.dll.feature_objective.restype=I
  self.dll.feature_view.argtypes=[C.c_void_p,I,C.POINTER(C.c_longlong)];self.dll.feature_view.restype=P
  hi,lo,gap,q,sw,sr,tw,tr,offsets,z,w=self.arrays;ptr=lambda a:a.ctypes.data_as(P)
  self.handle=self.dll.feature_create(self.N,ptr(hi),ptr(lo),ptr(gap),ptr(q),self.M,ptr(sw),ptr(sr),ptr(tw),ptr(tr),len(offsets),ptr(offsets),self.order,ptr(z),ptr(w),self.paired,self.law.horizon,self.law.coordinate,self.law.beta,self.gamma,self.law.ratio,cache_bytes)
  self.cache_active=bool(self.handle)
 def view(self,which):
  if not self.handle:raise MemoryError('feature cache cap; streaming objective active')
  size=C.c_longlong();pointer=self.dll.feature_view(self.handle,which,C.byref(size))
  return np.ctypeslib.as_array(pointer,shape=(size.value,)) if size.value else np.empty(0)
 @property
 def ge(self):return self.view(0)
 @property
 def xe(self):return self.view(1)
 @property
 def gq(self):return self.view(3)
 @property
 def xq(self):return self.view(4)
 @property
 def wq(self):return self.view(5)
 def objective(self,pars,kernel=None,ratio=None,gradient=True,free=None):
  if not self.handle or ratio is not None and ratio!=self.law.ratio:return super().objective(pars,kernel,ratio,gradient,free)
  if kernel is not None and kernel.key!=self.law.trigger.key:raise ValueError('fixed kernel')
  import time
  if self.deadline is not None and time.perf_counter()>=self.deadline:raise TimeoutError('deadline')
  free=list(range(4)) if free is None else list(free);p=np.ascontiguousarray(pars,dtype=np.float64);out=np.empty(5)
  if p.shape!=(4,) or not np.isfinite(p).all():raise ValueError('parameters')
  P=C.POINTER(C.c_double);mask=sum(1<<i for i in free) if gradient else 0
  status=self.dll.feature_objective(self.handle,p.ctypes.data_as(P),mask,out.ctypes.data_as(P))
  if status:raise FloatingPointError('cache objective')
  return (float(out[0]),out[1:][free]) if gradient else float(out[0])
 def close(self):
  if getattr(self,'handle',None):self.dll.feature_destroy(self.handle);self.handle=None
