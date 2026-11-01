// Streaming fixed-kernel ground likelihood. Input arrays remain caller owned.
// No pairwise or quadrature cache; event clocks are supplied as validated gaps.
#include <cmath>
#include <vector>
#include <limits>
#include <stdexcept>
#include <algorithm>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
struct Sum { double s=0,c=0; void add(double x){double y=x-c,t=s+y;c=(t-s)-y;s=t;} };
static double bg(double a,double d,double duration,double coordinate,bool derivative){
 double z=2*d*duration/coordinate,e=std::abs(z)<1e-8?1+z/2+z*z/6:std::expm1(z)/z;
 double f=0;
 if(std::abs(z)<.1){double power=1,fact=2;for(int k=0;k<14;++k){if(k){power*=z;fact*=k+2;}f+=(k+1)*power/fact;}}
 else f=((z-1)*std::exp(z)+1)/(z*z);
 double scale=std::exp(a-d)*duration;return derivative?scale*(-e+2*duration/coordinate*f):scale*e;
}
// Return 0 success, 1 domain/nonfinite failure. out=[nll, da,dd,dn,deta].
// lo may contain paired-clock residuals; paired=0 uses original projected
// arithmetic for panel edges. Offsets and GL abscissas/weights are pinned upstream.
API int temporal_objective(int N,const double* hi,const double* lo,const double* gap,
 const double* excess,int M,const double* sw,const double* sr,const double* tw,const double* tr,
 int K,const double* offsets,int order,const double* z,const double* w,int paired,
 double horizon,double coordinate,double beta,double gamma,double ratio,
 const double* pars,int derivative_mask,double* out) noexcept {
 try {
  if(N<0||M<=0||K<0||order<=0||!(horizon>0&&coordinate>0&&beta>0&&ratio>=0&&ratio<1))return 1;
  const double a=pars[0],d=pars[1],n=pars[2],eta=pars[3];
  if(!(n>=0&&eta>=0))return 1;
  for(int q=0;q<M;++q)if(!(sw[q]>=0&&sr[q]>0&&tw[q]>=0&&tr[q]>0))return 1;
  std::vector<double> s(M,0),t(M,0);
  Sum event,ea,ed,en,eg,integral,j,jd,jg;
  // Every interval includes its whole background exposure, including empty past.
  for(int i=0;i<=N;++i){
   const double dt=gap[i];if(!(dt>=0&&std::isfinite(dt)))return 1;
   const double base=i?hi[i-1]:0.,low=i?lo[i-1]:0.;
   double left=0;
   if(i==0){j.add(bg(a,d,dt,coordinate,false));jd.add(bg(a,d,dt,coordinate,true));}
   else
   for(int edge=0;edge<=K;++edge){
    double right=edge<K?offsets[edge]:dt;
    if(edge<K&&right>=dt)continue;
    if(!(right>=left&&right<=dt))return 1;
    for(int k=0;k<order;++k){
     // Match authority: paired uses relative nodes, projected uses absolute edges.
     double l=paired?left:base+left,r=paired?right:base+right;
     double query=(l+r)/2+(r-l)*z[k]/2;
     double lag=paired?query:query-base;
     double absolute=paired?base+(low+query):query;
     double x=2*absolute/coordinate-1;Sum g;
     for(int q=0;q<M;++q)g.add(sw[q]*s[q]*std::exp(-sr[q]*lag));
     double wb=(r-l)*w[k]/2*std::exp(a+d*x-eta*g.s);
     j.add(wb);jd.add(wb*x);jg.add(wb*g.s);
    }
    left=right;
   }
   if(i==N)break;
   Sum g,h;
   for(int q=0;q<M;++q){s[q]*=std::exp(-sr[q]*dt);t[q]*=std::exp(-tr[q]*dt);g.add(sw[q]*s[q]);h.add(tw[q]*tr[q]*t[q]);}
   double x=2*(hi[i]+lo[i])/coordinate-1,lb=a+d*x-eta*g.s;
   double lh=n>0&&h.s>0?std::log(n)+std::log(h.s):-std::numeric_limits<double>::infinity();
   double mx=std::max(lb,lh),ll=mx+std::log(std::exp(lb-mx)+std::exp(lh-mx));
   double p=std::exp(lb-ll);
   event.add(ll);ea.add(p);ed.add(p*x);eg.add(p*g.s);
   if(derivative_mask&4)en.add(h.s>0?std::exp(std::log(h.s)-ll):0);
   double stress=std::exp(gamma*excess[i])/std::exp(gamma),prod=(1-ratio)*std::exp(beta*ratio*excess[i]);
   // Paired clock subtraction retains the low component before adding to hi.
   double duration=(horizon-hi[i])-lo[i];Sum c;
   for(int q=0;q<M;++q){s[q]+=stress;t[q]+=prod;c.add(tw[q]*(-std::expm1(-tr[q]*duration)));}
   integral.add(prod*c.s);
  }
  if(eta==0){j.s=bg(a,d,horizon,coordinate,false);jd.s=bg(a,d,horizon,coordinate,true);}
  out[0]=j.s+n*integral.s-event.s;out[1]=j.s-ea.s;out[2]=jd.s-ed.s;out[3]=integral.s-en.s;out[4]=eg.s-jg.s;
  for(int k=0;k<5;++k)if((k==0||(derivative_mask&(1<<(k-1))))&&!std::isfinite(out[k]))return 1;
  return 0;
 }catch(...){return 1;}
}
