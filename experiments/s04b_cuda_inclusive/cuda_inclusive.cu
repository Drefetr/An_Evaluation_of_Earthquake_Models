// Variable-backbone total-intensity deficit. Reuses the independently checked
// chronological decay machinery; adds resident coefficient/temporal GEMMs.
#include "../s04b_completion/cuda_immigrant.cu"
#include <cublas_v2.h>
#define CB(x) do{if((x)!=CUBLAS_STATUS_SUCCESS)throw std::runtime_error("cuBLAS failure");}while(0)
struct FullContext {
 std::unique_ptr<Context> base;
 Buffer<double> pt,coeff,temporal[3],trigger[3];
 cublasHandle_t blas=nullptr;int tile=0;
 ~FullContext(){if(blas)cublasDestroy(blas);}
};
__global__ void temporal_fields(int np,int nt,const double* pt,const double* times,
 const double* theta,double* K,double* Kc,double* Kp){
 size_t index=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(index>=(size_t)np*nt)return;
 int j=index/nt,i=index%nt;double lag=times[i]-pt[j];
 if(lag<=0){K[index]=0;Kc[index]=0;Kp[index]=0;return;}
 double c=exp(theta[3]),p=theta[4],v=log1p(lag/c),k=(p-1)/c*exp(-p*v);
 K[index]=k;Kc[index]=k*(-1+p*lag/(c+lag));Kp[index]=k*(1/(p-1)-v);
}
__global__ void inclusive_rows(int np,int ns,int nt,int begin,int rows,
 const double* marks,const double* r2,const double* area,const double* background,
 const double* weights,const int* ends,const double* pr,const double* pd,
 const double* qr,const double* qd,const double* mu,const double* xx,
 const double* theta,const double* H,const double* Hc,const double* Hp,double* out){
 int local=blockIdx.x*blockDim.x+threadIdx.x;if(local>=rows)return;int s=begin+local;
 double G=0,L=0,P=0,v[9]={0,0,0,0,0,0,0,0,0};
 double ell=exp(theta[6]),eta=theta[5],n=theta[2];int j=0;
 for(int i=0;i<nt;i++){
  while(j<ends[i]){
   P=pd[j]*(P+G*pr[j]);G*=pd[j];L*=pd[j];
   double z=r2[(size_t)s*np+j]/(ell*ell),one=1+z,radial=marks[j]/(one*one);
   G+=radial;L+=radial*4*z/one;++j;
  }
  P=qd[i]*(P+G*qr[i]);G*=qd[i];L*=qd[i];
  size_t k=(size_t)local*nt+i;double B=mu[i]*background[s],base=B+n*H[k];
  double w=area[s]*weights[i],e=exp(-eta*G),lost=-expm1(-eta*G);
  v[0]+=w*base*lost;v[1]+=w*B*lost;v[2]+=w*xx[i]*B*lost;
  v[3]+=w*H[k]*lost;v[4]+=w*n*Hc[k]*lost;v[5]+=w*n*Hp[k]*lost;
  v[6]+=w*base*e*G;v[7]+=w*base*e*eta*L;v[8]+=w*base*e*eta*P;
 }
 for(int k=0;k<9;k++)out[9*(size_t)s+k]=v[k];
}
extern "C" void* ci_create(int np,int ns,int nt,const double* pt,const double* marks,
 const double* r2,const double* coeff,const double* area,const double* background,
 const double* times,const double* weights,double horizon,size_t workspace_bytes,char* error,int cap){
 try{
  require(np>0,"inclusive context requires parents");auto c=std::make_unique<FullContext>();
  c->base.reset(static_cast<Context*>(cim_create(np,ns,nt,pt,marks,r2,area,background,times,weights,horizon,error,cap)));
  require(bool(c->base),"base CUDA context creation failed");
  for(size_t k=0;k<(size_t)ns*np;k++)require(std::isfinite(coeff[k])&&coeff[k]>=0,"invalid offspring coefficient");
  c->pt.alloc(np);c->pt.put(pt);c->coeff.alloc((size_t)ns*np);c->coeff.put(coeff);
  for(int k=0;k<3;k++)c->temporal[k].alloc((size_t)np*nt);
  size_t free_bytes,total_bytes;CK(cudaMemGetInfo(&free_bytes,&total_bytes));
  size_t row_bytes=3*(size_t)nt*sizeof(double),budget=std::min(workspace_bytes,free_bytes/2);
  require(budget>=row_bytes,"insufficient inclusive workspace for one row");
  size_t tile=std::min((size_t)ns,budget/row_bytes);if(tile<(size_t)ns&&tile>128)tile=(tile/128)*128;
  c->tile=(int)std::max((size_t)1,tile);
  for(int k=0;k<3;k++)c->trigger[k].alloc((size_t)c->tile*nt);
  CB(cublasCreate(&c->blas));CB(cublasSetMathMode(c->blas,CUBLAS_DEFAULT_MATH));return c.release();
 }catch(const std::exception& e){if(cap>0)std::snprintf(error,cap,"%s",e.what());return nullptr;}
}
extern "C" int ci_evaluate(void* handle,const double* theta,double* out,char* error,int cap){
 try{
  require(handle&&theta&&out,"null inclusive evaluation argument");auto& c=*static_cast<FullContext*>(handle);auto& b=*c.base;
  for(int k=0;k<8;k++)require(std::isfinite(theta[k]),"nonfinite coordinate");
  require(theta[5]>=0&&theta[2]>=0&&theta[4]>1&&exp(theta[3])>0&&std::isfinite(exp(theta[3]))&&
      exp(theta[6])>0&&std::isfinite(exp(theta[6]))&&exp(theta[7])>0&&std::isfinite(exp(theta[7])),"invalid coordinates");
  b.theta.put(theta);
  parent_decay<<<(b.np+127)/128,128>>>(b.np,b.parent_delta.p,b.theta.p,b.pr.p,b.pd.p);CK(cudaGetLastError());
  query_values<<<(b.nt+127)/128,128>>>(b.nt,b.query_delta.p,b.times.p,b.theta.p,b.horizon,b.qr.p,b.qd.p,b.mu.p,b.xx.p);CK(cudaGetLastError());
  size_t pairs=(size_t)b.np*b.nt;
  temporal_fields<<<(pairs+127)/128,128>>>(b.np,b.nt,c.pt.p,b.times.p,b.theta.p,c.temporal[0].p,c.temporal[1].p,c.temporal[2].p);CK(cudaGetLastError());
  double one=1,zero=0;
  for(int begin=0;begin<b.ns;begin+=c.tile){
   int rows=std::min(c.tile,b.ns-begin);
   // Row-major H=C*K; cuBLAS computes H^T=K^T*C^T.
   for(int k=0;k<3;k++)CB(cublasDgemm(c.blas,CUBLAS_OP_N,CUBLAS_OP_N,b.nt,rows,b.np,
      &one,c.temporal[k].p,b.nt,c.coeff.p+(size_t)begin*b.np,b.np,&zero,c.trigger[k].p,b.nt));
   inclusive_rows<<<(rows+127)/128,128>>>(b.np,b.ns,b.nt,begin,rows,b.marks.p,b.r2.p,b.area.p,b.background.p,
       b.weights.p,b.ends.p,b.pr.p,b.pd.p,b.qr.p,b.qd.p,b.mu.p,b.xx.p,b.theta.p,
       c.trigger[0].p,c.trigger[1].p,c.trigger[2].p,b.rows.p);CK(cudaGetLastError());
  }
  b.rows.get(b.host_rows.data());std::fill(out,out+9,0.);
  for(int s=0;s<b.ns;s++)for(int k=0;k<9;k++){
   double v=b.host_rows[9*(size_t)s+k];require(std::isfinite(v),"nonfinite inclusive GPU row");out[k]+=v;
  }
  for(int k=0;k<9;k++)require(std::isfinite(out[k]),"nonfinite inclusive integral");return 0;
 }catch(const std::exception& e){if(cap>0)std::snprintf(error,cap,"%s",e.what());return 1;}
}
extern "C" int ci_tile_rows(void* handle){return static_cast<FullContext*>(handle)->tile;}
extern "C" void ci_free(void* handle){delete static_cast<FullContext*>(handle);}
