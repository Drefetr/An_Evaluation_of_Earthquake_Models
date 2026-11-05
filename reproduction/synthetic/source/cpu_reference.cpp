// Fixed-backbone LI/LI+ FP64 integration. All quadrature arrays remain local.
#include "architecture.hpp"
#include <vector>
#include <string>
#include <algorithm>
#include <memory>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
using remediation::require;
static thread_local std::string error;
static double logadd(double a,double b){
 if(a==-std::numeric_limits<double>::infinity())return b;
 if(b==-std::numeric_limits<double>::infinity())return a;
 double hi=std::max(a,b),lo=std::min(a,b);return hi+std::log1p(std::exp(lo-hi));
}
struct Model {
 int np,ns,nt,ne;double a,d,n,c,p,T,basecomp,marks;
 std::vector<double> parents,events,space,times,weights,r2,H,B,coeff;
};
// parents [t,x,y,Q,kappa,Z], events [t,x,y,b,H,reference_b],
// space [x,y,areaweight,b,reference_b], times/weights
API void* m02_create(int np,int ne,int ns,int nt,const double* parents,const double* events,const double* space,const double* times,const double* weights,const double* meta){
 try{require(np>=0&&ne>=0&&ns>0&&nt>0&&parents&&events&&space&&times&&weights&&meta,"sizes");
 require(np<=2147483647/6&&ne<=2147483647/6&&ns<=2147483647/5,"ABI count representation");
 require((size_t)ns<=std::numeric_limits<size_t>::max()/std::max(1,nt)/sizeof(double),"ABI matrix representation");
 for(int k=0;k<9;++k)require(std::isfinite(meta[k]),"finite metadata");
 auto holder=std::make_unique<Model>();auto f=holder.get();f->np=np;f->ne=ne;f->ns=ns;f->nt=nt;
 f->parents.assign(parents,parents+6*np);f->events.assign(events,events+6*ne);f->space.assign(space,space+5*ns);f->times.assign(times,times+nt);f->weights.assign(weights,weights+nt);
 f->a=meta[0];f->d=meta[1];f->n=meta[2];f->c=meta[3];f->p=meta[4];f->T=meta[5];f->basecomp=meta[6];f->marks=meta[7];double sigma=meta[8];
 require(f->a>=-12&&f->a<=0&&f->d>=-2&&f->d<=2&&f->n>=0&&f->n<=.98&&f->c>=.0001&&f->c<=20&&f->p>=1.01&&f->p<=2.5&&f->T>0&&sigma>0&&f->basecomp>=0,"bounded scientific backbone");f->r2.resize((size_t)ns*np);f->coeff.resize((size_t)ns*np);f->H.resize((size_t)ns*nt);f->B.resize((size_t)ns*nt);
 for(int j=0;j<np;++j){for(int k=0;k<6;++k)require(std::isfinite(parents[6*j+k]),"parent finite");require(parents[6*j+3]>=0&&parents[6*j+4]>=0&&parents[6*j+5]>0&&(!j||parents[6*j]>=parents[6*(j-1)]),"parent chronology/normalization");}
 for(int i=0;i<nt;++i)require(std::isfinite(times[i])&&weights[i]>0&&std::isfinite(weights[i])&&(!i||times[i]>times[i-1]),"time quadrature");
 for(int s=0;s<ns;++s)for(int k=0;k<5;++k)require(std::isfinite(space[5*s+k])&&(k<2||space[5*s+k]>=0),"space quadrature");
 for(int i=0;i<ne;++i)for(int k=0;k<6;++k)require(std::isfinite(events[6*i+k])&&(k<3||events[6*i+k]>=0),"nonnegative finite event components");
 std::vector<double> temporal((size_t)nt*np);for(int i=0;i<nt;++i)for(int j=0;j<np;++j){double lag=times[i]-parents[6*j];temporal[(size_t)i*np+j]=lag>0?(f->p-1)/f->c*std::exp(-f->p*std::log1p(lag/f->c)):0;}
 for(int s=0;s<ns;++s){for(int j=0;j<np;++j){double dx=space[5*s]-parents[6*j+1],dy=space[5*s+1]-parents[6*j+2];size_t ix=(size_t)s*np+j;double r2=dx*dx+dy*dy;require(std::isfinite(r2),"unrepresentable coordinate distance");f->r2[ix]=r2;
  f->coeff[ix]=parents[6*j+4]*remediation::kernel(r2,sigma)*space[5*s+4]/parents[6*j+5];}
  for(int i=0;i<nt;++i){double H=0;for(int j=0;j<np;++j)H+=f->coeff[(size_t)s*np+j]*temporal[(size_t)i*np+j];
   f->H[(size_t)s*nt+i]=f->n*H;f->B[(size_t)s*nt+i]=std::exp(f->a+f->d*(2*times[i]/f->T-1))*space[5*s+3];require(std::isfinite(f->H[(size_t)s*nt+i])&&std::isfinite(f->B[(size_t)s*nt+i]),"unrepresentable fixed backbone");}}
 return holder.release();
 }catch(const std::exception& e){error=e.what();return nullptr;}
}
API int m02_integrated(void* handle,int plus,int inclusive,const double* p,double* out){
 try{require(handle&&p&&out,"null evaluation ABI");require((plus==0||plus==1)&&(inclusive==0||inclusive==1),"mode flags");
 for(int k=0;k<3;++k)require(std::isfinite(p[k]),"finite parameters");
 require(p[0]>=0&&p[0]<=4&&p[1]>=std::log(5.)&&p[1]<=std::log(150.)&&p[2]>=std::log(1./24)&&p[2]<=std::log(365.),"bounded scientific stress parameters");
 auto& f=*static_cast<Model*>(handle);double eta=p[0],ell=std::exp(p[1]),psi=std::exp(p[2]);double gamma=plus?.75*std::log(10.):0;
 double deficit=0,de=0,dl=0,dp=0,point=0,pe=0,pl=0,pp=0;
 std::vector<double> radial(f.np),dell(f.np);
 // The strict-past parent/query timeline is identical for every spatial row.
 // Compute the SAME scalar ratios/exp values once; retain state update order.
 std::vector<double> parent_g(f.np),parent_ratio(f.np),parent_decay(f.np),query_ratio(f.nt),query_decay(f.nt);std::vector<int> parent_end(f.nt);
 for(int j=0;j<f.np;++j){parent_g[j]=std::exp(gamma*f.parents[6*j+3]);require(std::isfinite(parent_g[j]),"unrepresentable magnitude stress: retain numerical unknown");}
 double clock=f.np?std::min(f.parents[0],f.times[0]):f.times[0];int consumed=0;
 for(int i=0;i<f.nt;++i){double t=f.times[i];while(consumed<f.np&&f.parents[6*consumed]<t){double dt=(f.parents[6*consumed]-clock)/psi;parent_ratio[consumed]=dt;parent_decay[consumed]=std::exp(-dt);clock=f.parents[6*consumed];++consumed;}
  parent_end[i]=consumed;double dt=(t-clock)/psi;query_ratio[i]=dt;query_decay[i]=std::exp(-dt);clock=t;}
 for(int s=0;s<f.ns;++s){for(int j=0;j<f.np;++j){double r2=f.r2[(size_t)s*f.np+j],one=1+r2/(ell*ell),g=parent_g[j];radial[j]=g/(one*one);dell[j]=radial[j]*4*(one-1)/one;}
  double G=0,L=0,P=0;int j=0;
  auto decay=[&](double dt,double e){P=e*(P+G*dt);G*=e;L*=e;};
  for(int i=0;i<f.nt;++i){while(j<parent_end[i]){decay(parent_ratio[j],parent_decay[j]);G+=radial[j];L+=dell[j];++j;}decay(query_ratio[i],query_decay[i]);
   size_t ix=(size_t)s*f.nt+i;double attenuation=f.B[ix]+(inclusive?f.H[ix]:0),w=f.weights[i]*f.space[5*s+2],e=std::exp(-eta*G);deficit+=w*attenuation*(-std::expm1(-eta*G));de-=w*attenuation*e*G;dl-=w*attenuation*e*eta*L;dp-=w*attenuation*e*eta*P;}}
 for(int i=0;i<f.ne;++i){const double* row=&f.events[6*i];double G=0,L=0,P=0;
  for(int j=0;j<f.np;++j){double lag=row[0]-f.parents[6*j];if(lag<=0)continue;double dx=row[1]-f.parents[6*j+1],dy=row[2]-f.parents[6*j+2],r2=dx*dx+dy*dy,one=1+r2/(ell*ell),v=std::exp(gamma*f.parents[6*j+3]-lag/psi)/(one*one);G+=v;L+=v*4*(one-1)/one;P+=v*lag/psi;}
  double neginf=-std::numeric_limits<double>::infinity();
  double logB=row[3]>0?f.a+f.d*(2*row[0]/f.T-1)+std::log(row[3]):neginf,logH=row[4]>0?std::log(row[4]):neginf;
  // Preserve finite log intensity when exp(-eta*G) is below FP64 range.
  double log_point=inclusive?logadd(logB,logH)-eta*G:logadd(logB-eta*G,logH);
  require(std::isfinite(log_point),"event log intensity");point+=log_point;
  double fraction=inclusive?1:(logB==neginf?0:std::exp(logB-eta*G-log_point));pe-=G*fraction;pl-=eta*L*fraction;pp-=eta*P*fraction;
 }
 out[0]=f.basecomp-deficit-point-f.marks;out[1]=de-pe;out[2]=dl-pl;out[3]=dp-pp;out[4]=deficit;out[5]=point;for(int k=0;k<6;++k)require(std::isfinite(out[k]),"finite output");return 0;
 }catch(const std::exception& e){error=e.what();return 1;}
}
API void m02_free(void* h){delete static_cast<Model*>(h);}API const char* m02_integrated_error(){return error.c_str();}
