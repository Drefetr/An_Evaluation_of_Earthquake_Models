#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#define CHECK(x) do{cudaError_t e=(x);if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}while(0)
struct Context {
 int cols;size_t capacity=0;double *marks=nullptr,*fertility=nullptr,*lag=nullptr,*r2=nullptr,*values=nullptr,*result=nullptr,*params=nullptr,*scales=nullptr;
 Context(int n,const double* m,const double* f):cols(n){CHECK(cudaMalloc(&marks,n*sizeof(double)));CHECK(cudaMalloc(&fertility,n*sizeof(double)));CHECK(cudaMemcpy(marks,m,n*sizeof(double),cudaMemcpyHostToDevice));CHECK(cudaMemcpy(fertility,f,n*sizeof(double),cudaMemcpyHostToDevice));CHECK(cudaMalloc(&params,12*sizeof(double)));CHECK(cudaMalloc(&scales,3*n*sizeof(double)));}
 ~Context(){cudaFree(marks);cudaFree(fertility);cudaFree(lag);cudaFree(r2);cudaFree(values);cudaFree(result);cudaFree(params);cudaFree(scales);}
 void reserve(size_t rows){if(rows<=capacity)return;cudaFree(lag);cudaFree(r2);cudaFree(values);cudaFree(result);CHECK(cudaMalloc(&lag,rows*cols*sizeof(double)));CHECK(cudaMalloc(&r2,rows*cols*sizeof(double)));CHECK(cudaMalloc(&values,rows*cols*6*sizeof(double)));CHECK(cudaMalloc(&result,rows*6*sizeof(double)));capacity=rows;}
};
__global__ void parent_scales(int cols,const double* marks,const double* x,double* scales){int j=blockIdx.x*blockDim.x+threadIdx.x;if(j>=cols)return;scales[3*j]=exp(2*x[5]+2*x[6]*marks[j]);scales[3*j+1]=exp(2*x[9]+log(10.)*marks[j]);scales[3*j+2]=exp(x[11]*marks[j]);}
__global__ void evaluate_pairs(size_t count,int cols,const double* lag,const double* r2,const double* marks,const double* fertility,const double* x,const double* scales,int mode,double* values){
 size_t index=(size_t)blockIdx.x*blockDim.x+threadIdx.x;if(index>=count)return;int j=index%cols;double t=lag[index],d=r2[index];double* v=values+6*index;
 if(t<=0){for(int k=0;k<6;k++)v[k]=0;return;}
 if(mode==0){double c=exp(x[3]),p=x[4],q=x[7],s2=scales[3*j];double tl=log1p(t/c),sl=log1p(d/s2),k=(p-1)/c*exp(-p*tl)*(q-1)/(3.14159265358979323846*s2)*exp(-q*sl)*fertility[j];double ds=-2+2*q*d/(s2+d);
  v[0]=k;v[1]=k*(-1+p*t/(c+t));v[2]=k*(1/(p-1)-tl);v[3]=k*ds;v[4]=k*ds*marks[j];v[5]=k*(1/(q-1)-sl);
 }else{double psi=exp(x[10]),e2=scales[3*j+1],u=1+d/e2,k=scales[3*j+2]*exp(-t/psi)/(u*u);v[0]=k;v[1]=k*4*d/(e2+d);v[2]=k*t/psi;v[3]=k*marks[j];}
}
__global__ void chronological_reduce(int rows,int cols,int components,const double* values,double* out){
 int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=rows)return;double s[6]={0,0,0,0,0,0};
 for(int j=0;j<cols;j++)for(int k=0;k<components;k++)s[k]+=values[((size_t)i*cols+j)*6+k];
 for(int k=0;k<components;k++)out[(size_t)i*components+k]=s[k];
}
extern "C" void* gp_create(int cols,const double* marks,const double* fertility,char* error,int cap){try{return new Context(cols,marks,fertility);}catch(const std::exception& e){std::snprintf(error,cap,"%s",e.what());return nullptr;}}
extern "C" void gp_free(void* h){delete static_cast<Context*>(h);}
extern "C" int gp_evaluate(void* h,int rows,const double* lag,const double* r2,const double* params,int mode,int upload,double* out,char* error,int cap){
 try{auto& c=*static_cast<Context*>(h);c.reserve(rows);if(upload){CHECK(cudaMemcpy(c.lag,lag,(size_t)rows*c.cols*sizeof(double),cudaMemcpyHostToDevice));CHECK(cudaMemcpy(c.r2,r2,(size_t)rows*c.cols*sizeof(double),cudaMemcpyHostToDevice));}CHECK(cudaMemcpy(c.params,params,12*sizeof(double),cudaMemcpyHostToDevice));
  parent_scales<<<(c.cols+127)/128,128>>>(c.cols,c.marks,c.params,c.scales);CHECK(cudaGetLastError());size_t count=(size_t)rows*c.cols;
  evaluate_pairs<<<(count+127)/128,128>>>(count,c.cols,c.lag,c.r2,c.marks,c.fertility,c.params,c.scales,mode,c.values);CHECK(cudaGetLastError());
  int components=mode==0?6:4;chronological_reduce<<<(rows+63)/64,64>>>(rows,c.cols,components,c.values,c.result);CHECK(cudaGetLastError());CHECK(cudaDeviceSynchronize());CHECK(cudaMemcpy(out,c.result,(size_t)rows*components*sizeof(double),cudaMemcpyDeviceToHost));return 0;
 }catch(const std::exception& e){std::snprintf(error,cap,"%s",e.what());return 1;}
}
