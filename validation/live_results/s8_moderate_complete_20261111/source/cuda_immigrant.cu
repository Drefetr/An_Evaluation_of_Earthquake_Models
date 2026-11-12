// Immigrant-only port of joint_nuisance/attenuation.cpp.
// Same chronological recurrence per spatial row; row-ordered host reduction.
// No triggering fields, objective approximation, optimizer or parameter cache.
#include <cuda_runtime.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <memory>
#include <stdexcept>
#include <vector>
#define CK(x) do {cudaError_t e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
static void require(bool yes,const char* why){if(!yes)throw std::runtime_error(why);}
template<class T> struct Buffer {
 T* p=nullptr;size_t size=0;
 ~Buffer(){if(p)cudaFree(p);}
 void alloc(size_t n){size=n;if(n)CK(cudaMalloc((void**)&p,n*sizeof(T)));}
 void put(const T* v){if(size)CK(cudaMemcpy(p,v,size*sizeof(T),cudaMemcpyHostToDevice));}
 void get(T* v){if(size)CK(cudaMemcpy(v,p,size*sizeof(T),cudaMemcpyDeviceToHost));}
};
struct Context {
 int np,ns,nt;double horizon;
 Buffer<double> marks,r2,area,background,times,weights,parent_delta,query_delta,pr,pd,qr,qd,mu,xx,theta,rows;
 Buffer<int> ends;
 std::vector<double> host_rows;
};
__global__ void parent_decay(int np,const double* delta,const double* theta,double* ratio,double* decay){
 int j=blockIdx.x*blockDim.x+threadIdx.x;if(j>=np)return;
 double r=delta[j]/exp(theta[7]);ratio[j]=r;decay[j]=exp(-r);
}
__global__ void query_values(int nt,const double* delta,const double* times,const double* theta,double T,
 double* ratio,double* decay,double* mu,double* xx){
 int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=nt)return;
 double r=delta[i]/exp(theta[7]);ratio[i]=r;decay[i]=exp(-r);
 xx[i]=2*times[i]/T-1;mu[i]=exp(theta[0]+theta[1]*xx[i]);
}
__global__ void integrate_rows(int np,int ns,int nt,const double* marks,const double* r2,
 const double* area,const double* background,const double* weights,const int* ends,
 const double* pr,const double* pd,const double* qr,const double* qd,const double* mu,
 const double* xx,const double* theta,double* out){
 int s=blockIdx.x*blockDim.x+threadIdx.x;if(s>=ns)return;
 double G=0,L=0,P=0,deficit=0,dd=0,de=0,dl=0,dp=0;
 double ell=exp(theta[6]),eta=theta[5];int j=0;
 for(int i=0;i<nt;i++){
  while(j<ends[i]){
   P=pd[j]*(P+G*pr[j]);G*=pd[j];L*=pd[j];
   double v=r2[(size_t)s*np+j]/(ell*ell),one=1+v,radial=marks[j]/(one*one);
   G+=radial;L+=radial*4*v/one;++j;
  }
  P=qd[i]*(P+G*qr[i]);G*=qd[i];L*=qd[i];
  double B=mu[i]*background[s],w=area[s]*weights[i],e=exp(-eta*G),lost=-expm1(-eta*G);
  deficit+=w*B*lost;dd+=w*xx[i]*B*lost;
  de+=w*B*e*G;dl+=w*B*e*eta*L;dp+=w*B*e*eta*P;
 }
 double* v=out+9*(size_t)s;
 v[0]=deficit;v[1]=deficit;v[2]=dd;v[3]=0;v[4]=0;v[5]=0;v[6]=de;v[7]=dl;v[8]=dp;
}
extern "C" void* cim_create(int np,int ns,int nt,const double* pt,const double* marks,
 const double* r2,const double* area,const double* background,const double* times,
 const double* weights,double horizon,char* error,int cap){
 try{
  require(np>=0&&ns>0&&nt>0&&horizon>0,"invalid dimensions/horizon");
  auto c=std::make_unique<Context>();c->np=np;c->ns=ns;c->nt=nt;c->horizon=horizon;
  std::vector<double> pr(np,0),qr(nt);std::vector<int> ends(nt);
  double clock=np?std::min(pt[0],times[0]):times[0];int consumed=0;
  for(int i=0;i<nt;i++){
   require(std::isfinite(times[i])&&std::isfinite(weights[i])&&weights[i]>0&&(!i||times[i]>=times[i-1]),"invalid time quadrature");
   while(consumed<np&&pt[consumed]<times[i]){
    require(pt[consumed]>=clock&&std::isfinite(marks[consumed])&&marks[consumed]>=0,"invalid parent");
    pr[consumed]=pt[consumed]-clock;clock=pt[consumed];++consumed;
   }
   ends[i]=consumed;qr[i]=times[i]-clock;clock=times[i];
  }
  for(int s=0;s<ns;s++)require(std::isfinite(area[s])&&area[s]>0&&std::isfinite(background[s])&&background[s]>0,"invalid spatial quadrature");
  for(size_t k=0;k<(size_t)ns*np;k++)require(std::isfinite(r2[k])&&r2[k]>=0,"invalid squared distance");
  c->marks.alloc(np);c->marks.put(marks);c->r2.alloc((size_t)ns*np);c->r2.put(r2);
  c->area.alloc(ns);c->area.put(area);c->background.alloc(ns);c->background.put(background);
  c->times.alloc(nt);c->times.put(times);c->weights.alloc(nt);c->weights.put(weights);
  c->parent_delta.alloc(np);c->parent_delta.put(pr.data());c->query_delta.alloc(nt);c->query_delta.put(qr.data());
  c->ends.alloc(nt);c->ends.put(ends.data());c->pr.alloc(np);c->pd.alloc(np);c->qr.alloc(nt);c->qd.alloc(nt);
  c->mu.alloc(nt);c->xx.alloc(nt);c->theta.alloc(8);c->rows.alloc((size_t)ns*9);c->host_rows.resize((size_t)ns*9);
  return c.release();
 }catch(const std::exception& e){if(cap>0)std::snprintf(error,cap,"%s",e.what());return nullptr;}
}
extern "C" int cim_evaluate(void* handle,const double* theta,double* out,char* error,int cap){
 try{
  require(handle&&theta&&out,"null argument");auto& c=*static_cast<Context*>(handle);
  for(int k=0;k<8;k++)require(std::isfinite(theta[k]),"nonfinite coordinate");
  require(theta[5]>=0&&theta[2]>=0&&std::isfinite(exp(theta[6]))&&exp(theta[6])>0&&std::isfinite(exp(theta[7]))&&exp(theta[7])>0,"invalid attenuation coordinates");
  c.theta.put(theta);
  if(c.np){parent_decay<<<(c.np+127)/128,128>>>(c.np,c.parent_delta.p,c.theta.p,c.pr.p,c.pd.p);CK(cudaGetLastError());}
  query_values<<<(c.nt+127)/128,128>>>(c.nt,c.query_delta.p,c.times.p,c.theta.p,c.horizon,c.qr.p,c.qd.p,c.mu.p,c.xx.p);CK(cudaGetLastError());
  integrate_rows<<<(c.ns+127)/128,128>>>(c.np,c.ns,c.nt,c.marks.p,c.r2.p,c.area.p,c.background.p,c.weights.p,c.ends.p,c.pr.p,c.pd.p,c.qr.p,c.qd.p,c.mu.p,c.xx.p,c.theta.p,c.rows.p);CK(cudaGetLastError());
  c.rows.get(c.host_rows.data());std::fill(out,out+9,0.);
  for(int s=0;s<c.ns;s++)for(int k=0;k<9;k++){
   double v=c.host_rows[9*(size_t)s+k];require(std::isfinite(v),"nonfinite GPU row");out[k]+=v;
  }
  for(int k=0;k<9;k++)require(std::isfinite(out[k]),"nonfinite reduced integral");
  return 0;
 }catch(const std::exception& e){if(cap>0)std::snprintf(error,cap,"%s",e.what());return 1;}
}
extern "C" void cim_free(void* handle){delete static_cast<Context*>(handle);}
