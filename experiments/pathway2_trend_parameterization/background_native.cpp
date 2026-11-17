// Pathway 2 joint temporal-backbone attenuation integral with a selectable
// background clock and optional training-orthogonalised depletion field.
//
// This is an isolated copy of experiments/s04b_joint_nuisance/attenuation.cpp.
// The archived file is never modified.  Rows of triggering have
// [H(time), dH/dlog(c), dH/dp] consecutive blocks.
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <exception>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C" __attribute__((visibility("default")))
#endif
static thread_local std::string error;
static void require(bool x,const char* message){if(!x)throw std::runtime_error(message);}
API const char* joint_error(){return error.c_str();}
API int joint_integral_law(int ns,int np,int nt,int inclusive,
 const double* pt,const double* marks,const double* r2,const double* area,
 const double* background,const double* times,const double* weights,
 const double* triggering,const double* theta,double horizon,
 const double* clock,int orthogonal,double orth_c,double orth_k,double* out){
 try {
  require(ns>=0&&np>=0&&nt>0&&horizon>0,"invalid dimensions");
  require(pt&&marks&&r2&&area&&background&&times&&weights&&triggering&&theta&&clock&&out,"null pointer");
  require(inclusive==0||inclusive==1,"invalid mode");
  for(int k=0;k<8;++k)require(std::isfinite(theta[k]),"nonfinite parameter");
  require(std::isfinite(orth_c)&&std::isfinite(orth_k),"nonfinite orthogonalisation");
  const double a=theta[0],d=theta[1],n=theta[2],eta=theta[5],ell=std::exp(theta[6]),psi=std::exp(theta[7]);
  require(eta>=0&&ell>0&&psi>0&&n>=0,"invalid attenuation parameter");
  std::fill(out,out+9,0.);
  std::vector<double> pr(np),pd(np),qr(nt),qd(nt),mu(nt),xx(nt);
  std::vector<int> end(nt);
  double clock_parent=np?std::min(pt[0],times[0]):times[0];int consumed=0;
  for(int i=0;i<nt;++i){
   require(std::isfinite(times[i])&&std::isfinite(weights[i])&&weights[i]>0,"invalid quadrature");
   require(std::isfinite(clock[i]),"nonfinite background clock");
   if(i)require(times[i]>=times[i-1],"unordered quadrature");
   while(consumed<np&&pt[consumed]<times[i]){
    require(pt[consumed]>=clock_parent,"unordered parents");
    pr[consumed]=(pt[consumed]-clock_parent)/psi;pd[consumed]=std::exp(-pr[consumed]);clock_parent=pt[consumed];++consumed;
   }
   end[i]=consumed;qr[i]=(times[i]-clock_parent)/psi;qd[i]=std::exp(-qr[i]);clock_parent=times[i];
   xx[i]=clock[i];mu[i]=std::exp(a+d*xx[i]);
  }
  std::vector<double> radial(np),dell(np);
  for(int s=0;s<ns;++s){
   require(area[s]>0&&background[s]>0,"nonpositive spatial quadrature");
   for(int j=0;j<np;++j){
    const double v=r2[(size_t)s*np+j]/(ell*ell),one=1+v;
    radial[j]=marks[j]/(one*one);dell[j]=radial[j]*4*v/one;
    require(std::isfinite(radial[j])&&std::isfinite(dell[j]),"nonfinite stress input");
   }
   double G=0,L=0,P=0;int j=0;
   auto decay=[&](double ratio,double e){P=e*(P+G*ratio);G*=e;L*=e;};
   const double* tr=triggering+(inclusive?(size_t)s*3*nt:0);
   for(int i=0;i<nt;++i){
    while(j<end[i]){decay(pr[j],pd[j]);G+=radial[j];L+=dell[j];++j;}
    decay(qr[i],qd[i]);
    const double R=orthogonal?G-orth_c-orth_k*xx[i]:G;
    const double B=mu[i]*background[s],H=inclusive?tr[i]:0;
    const double base=B+n*H,w=area[s]*weights[i];
    const double e=std::exp(-eta*R),lost=-std::expm1(-eta*R);
    out[0]+=w*base*lost;
    out[1]+=w*B*lost;out[2]+=w*xx[i]*B*lost;
    if(inclusive){out[3]+=w*H*lost;out[4]+=w*n*tr[nt+i]*lost;out[5]+=w*n*tr[2*nt+i]*lost;}
    out[6]+=w*base*e*R;out[7]+=w*base*e*eta*L;out[8]+=w*base*e*eta*P;
   }
  }
  for(int k=0;k<9;++k)require(std::isfinite(out[k]),"nonfinite attenuation integral");
  return 0;
 }catch(const std::exception& e){error=e.what();return 1;}
}
