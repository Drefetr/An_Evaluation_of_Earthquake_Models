// Additive epoch: original objective source remains unchanged and included.
#include "recursive_temporal.cpp"
static double lograte(double lb,double h,double n){
 double lh=(n>0&&h>0)?std::log(n)+std::log(h):-std::numeric_limits<double>::infinity();
 double mx=std::max(lb,lh);return mx+std::log(std::exp(lb-mx)+std::exp(lh-mx));
}
// out=[GLR,event difference,background exposure difference,trigger exposure difference]
API int temporal_contrast(int N,const double* hi,const double* lo,const double* gap,
 const double* excess,int M,const double* sw,const double* sr,const double* tw,const double* tr,
 int K,const double* offsets,int order,const double* z,const double* w,int paired,
 double horizon,double coordinate,double beta,double gamma,double ratio0,double ratio1,
 const double* p0,const double* p1,double* out) noexcept {
 try{
  if(N<0||M<=0||K<0||order<=0||p0[3]!=0||p1[3]<0||p0[2]<0||p1[2]<0||ratio0<0||ratio0>=1||ratio1<0||ratio1>=1)return 1;
  std::vector<double>s(M,0),t0(M,0),t1(M,0);Sum event,background,trigger;
  for(int i=0;i<=N;++i){
   double dt=gap[i],base=i?hi[i-1]:0,low=i?lo[i-1]:0;
   if(!(dt>=0&&std::isfinite(dt)))return 1;
   if(i==0)background.add(bg(p0[0],p0[1],dt,coordinate,false)-bg(p1[0],p1[1],dt,coordinate,false));
   else{
    double left=0;
    for(int e=0;e<=K;++e){
     double right=e<K?offsets[e]:dt;if(e<K&&right>=dt)continue;
     if(!(right>=left&&right<=dt))return 1;
     for(int k=0;k<order;++k){
      double l=paired?left:base+left,r=paired?right:base+right;
      double query=(l+r)/2+(r-l)*z[k]/2,lag=paired?query:query-base;
      double x=2*(paired?base+(low+query):query)/coordinate-1;Sum g;
      for(int q=0;q<M;++q)g.add(sw[q]*s[q]*std::exp(-sr[q]*lag));
      double delta=(p1[0]-p0[0])+(p1[1]-p0[1])*x-p1[3]*g.s;
      background.add(-(r-l)*w[k]/2*std::exp(p0[0]+p0[1]*x)*std::expm1(delta));
     }left=right;
    }
   }
   if(i==N)break;
   Sum g,h0,h1,c;
   double prod0=(1-ratio0)*std::exp(beta*ratio0*excess[i]);
   double prod1=(1-ratio1)*std::exp(beta*ratio1*excess[i]);
   double stress=std::exp(gamma*excess[i])/std::exp(gamma),duration=(horizon-hi[i])-lo[i];
   for(int q=0;q<M;++q){
    s[q]*=std::exp(-sr[q]*dt);double decay=std::exp(-tr[q]*dt);t0[q]*=decay;t1[q]*=decay;
    g.add(sw[q]*s[q]);h0.add(tw[q]*tr[q]*t0[q]);h1.add(tw[q]*tr[q]*t1[q]);
    c.add(tw[q]*(-std::expm1(-tr[q]*duration)));s[q]+=stress;t0[q]+=prod0;t1[q]+=prod1;
   }
   double x=2*(hi[i]+lo[i])/coordinate-1;
   event.add(lograte(p1[0]+p1[1]*x-p1[3]*g.s,h1.s,p1[2])-lograte(p0[0]+p0[1]*x,h0.s,p0[2]));
   trigger.add((p0[2]*prod0-p1[2]*prod1)*c.s);
  }
  out[1]=event.s;out[2]=background.s;out[3]=trigger.s;
  out[0]=2*(event.s+background.s+trigger.s);
  for(int k=0;k<4;++k)if(!std::isfinite(out[k]))return 1;return 0;
 }catch(...){return 1;}
}
