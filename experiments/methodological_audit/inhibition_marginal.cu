#include <cuda_runtime.h>
#include <algorithm>
#include <cublas_v2.h>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <string>
#define CUDA(x) do {cudaError_t e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
#define BLAS(x) do {if((x)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("cuBLAS failure");}while(0)
struct Buffer {
 double* p=nullptr;
 explicit Buffer(size_t n){CUDA(cudaMalloc(&p,n*sizeof(double)));}
 ~Buffer(){if(p)cudaFree(p);}
 void copy(const double* h,size_t n){CUDA(cudaMemcpy(p,h,n*sizeof(double),cudaMemcpyHostToDevice));}
};
struct Handle {cublasHandle_t h;Handle(){BLAS(cublasCreate(&h));}~Handle(){cublasDestroy(h);}};
__global__ void temporal(int np,int nt,const double* parents,const double* times,double c,double p,double psi,double* H,double* D){
 size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=(size_t)np*nt)return;
 int j=i/nt,k=i%nt;double lag=times[k]-parents[6*j];
 if(lag<=0){H[i]=0;D[i]=0;}else{H[i]=(p-1)/c*exp(-p*log1p(lag/c));D[i]=exp(-lag/psi);}
}
__global__ void radial(int np,int rows,int begin,const double* parents,const double* space,double ell,double sigma,double* G,double* H){
 size_t i=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(i>=(size_t)np*rows)return;
 int row=i/np,j=i%np;const double* s=space+5*(begin+row);const double* v=parents+6*j;
 double dx=s[0]-v[1],dy=s[1]-v[2],r2=dx*dx+dy*dy;
 double u=1+r2/(ell*ell);G[i]=exp(.75*log(10.)*v[3])/(u*u);
 H[i]=exp(-2*log1p(r2/(sigma*sigma)))*v[4]/v[5]*s[4];
}
__global__ void reduce_time(int rows,int nt,int begin,const double* space,const double* times,const double* G,const double* H,double a,double d,double n,double T,double eta,double* total){
 int k=blockIdx.x*blockDim.x+threadIdx.x;if(k>=nt)return;
 double bt=exp(a+d*(2*times[k]/T-1)),sum=0;
 for(int row=0;row<rows;row++) {
  const double* s=space+5*(begin+row);size_t index=(size_t)row*nt+k;
  sum+=(-expm1(-eta*G[index]))*(s[3]*bt+n*H[index])*s[2];
 }
 total[k]+=sum;
}
extern "C" int inhibition_marginal(int np,int ns,int nt,const double* parents,const double* space,const double* times,const double* meta,double eta,double ell,double psi,int tile,double* out,char* error,int cap){
 try{
  if(np<=0||ns<=0||nt<=0||tile<=0)throw std::runtime_error("invalid dimensions");
  Buffer P((size_t)np*6),S((size_t)ns*5),T(nt),TH((size_t)np*nt),TD((size_t)np*nt),RG((size_t)tile*np),RH((size_t)tile*np),G((size_t)tile*nt),H((size_t)tile*nt),O(nt);
  P.copy(parents,(size_t)np*6);S.copy(space,(size_t)ns*5);T.copy(times,nt);CUDA(cudaMemset(O.p,0,nt*sizeof(double)));
  Handle handle;BLAS(cublasSetMathMode(handle.h,CUBLAS_DEFAULT_MATH));
  size_t temporal_size=(size_t)np*nt;temporal<<<(temporal_size+255)/256,256>>>(np,nt,P.p,T.p,meta[3],meta[4],psi,TH.p,TD.p);CUDA(cudaGetLastError());
  double one=1.,zero=0.;
  for(int begin=0;begin<ns;begin+=tile){
   int rows=std::min(tile,ns-begin);size_t count=(size_t)rows*np;
   radial<<<(count+255)/256,256>>>(np,rows,begin,P.p,S.p,ell,meta[8],RG.p,RH.p);CUDA(cudaGetLastError());
   // Row-major G=RG*TD; cuBLAS evaluates G^T=TD^T*RG^T.
   BLAS(cublasDgemm(handle.h,CUBLAS_OP_N,CUBLAS_OP_N,nt,rows,np,&one,TD.p,nt,RG.p,np,&zero,G.p,nt));
   BLAS(cublasDgemm(handle.h,CUBLAS_OP_N,CUBLAS_OP_N,nt,rows,np,&one,TH.p,nt,RH.p,np,&zero,H.p,nt));
   reduce_time<<<(nt+127)/128,128>>>(rows,nt,begin,S.p,T.p,G.p,H.p,meta[0],meta[1],meta[2],meta[5],eta,O.p);CUDA(cudaGetLastError());
  }
  CUDA(cudaDeviceSynchronize());CUDA(cudaMemcpy(out,O.p,nt*sizeof(double),cudaMemcpyDeviceToHost));return 0;
 }catch(const std::exception& e){if(cap>0)std::snprintf(error,cap,"%s",e.what());return 1;}
}
