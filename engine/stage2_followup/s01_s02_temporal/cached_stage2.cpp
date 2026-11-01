// Stage2 bounded output-feature cache, constructed by the exact recursive engine.
// Modal scratch O(M); explicit cache cap and streaming fallback in Python.
#include "contrast_v2.cpp"
struct Features {
 std::vector<double> ge,xe,lh,gq,xq,wq;double integral=0,quiet=0,T=0,C=0;
};
API void* feature_create(int N,const double* hi,const double* lo,const double* gap,
 const double* excess,int M,const double* sw,const double* sr,const double* tw,const double* tr,
 int K,const double* offsets,int order,const double* z,const double* w,int paired,
 double horizon,double coordinate,double beta,double gamma,double ratio,double maxbytes) noexcept {
 Features* f=nullptr;
 try{
  if(N<0||M<=0||order<=0||ratio<0||ratio>=1)return nullptr;
  f=new Features;f->quiet=gap[0];f->T=horizon;f->C=coordinate;
  std::vector<double>s(M,0),t(M,0);Sum integral;
  for(int i=0;i<=N;++i){
   double dt=gap[i],base=i?hi[i-1]:0,low=i?lo[i-1]:0;
   if(!(dt>=0&&std::isfinite(dt)))throw std::runtime_error("gap");
   if(i){double left=0;
    for(int e=0;e<=K;++e){double right=e<K?offsets[e]:dt;if(e<K&&right>=dt)continue;
     if(!(right>=left&&right<=dt))throw std::runtime_error("edges");
     if(24.*(f->gq.size()+order)+24.*N>maxbytes)throw std::runtime_error("cache_cap");
     for(int k=0;k<order;++k){double l=paired?left:base+left,r=paired?right:base+right;
      double query=(l+r)/2+(r-l)*z[k]/2,lag=paired?query:query-base;Sum g;
      for(int q=0;q<M;++q)g.add(sw[q]*s[q]*std::exp(-sr[q]*lag));
      f->gq.push_back(g.s);f->xq.push_back(2*(paired?base+(low+query):query)/coordinate-1);f->wq.push_back((r-l)*w[k]/2);
     }left=right;
    }
   }
   if(i==N)break;
   Sum g,h,c;double duration=(horizon-hi[i])-lo[i];
   double stress=std::exp(gamma*excess[i])/std::exp(gamma),prod=(1-ratio)*std::exp(beta*ratio*excess[i]);
   for(int q=0;q<M;++q){s[q]*=std::exp(-sr[q]*dt);t[q]*=std::exp(-tr[q]*dt);g.add(sw[q]*s[q]);h.add(tw[q]*tr[q]*t[q]);c.add(tw[q]*(-std::expm1(-tr[q]*duration)));s[q]+=stress;t[q]+=prod;}
   f->ge.push_back(g.s);f->xe.push_back(2*(hi[i]+lo[i])/coordinate-1);f->lh.push_back(h.s>0?std::log(h.s):-INFINITY);integral.add(prod*c.s);
  }f->integral=integral.s;return f;
 }catch(...){delete f;return nullptr;}
}
API void feature_destroy(void* pointer) noexcept {delete static_cast<Features*>(pointer);}
API const double* feature_view(void* pointer,int which,long long* size) noexcept {
 auto f=static_cast<Features*>(pointer);if(!f)return nullptr;
 std::vector<double>* v=which==0?&f->ge:which==1?&f->xe:which==2?&f->lh:which==3?&f->gq:which==4?&f->xq:&f->wq;
 *size=static_cast<long long>(v->size());return v->data();
}
API int feature_objective(void* pointer,const double* pars,int mask,double* out) noexcept {
 try{auto f=static_cast<Features*>(pointer);if(!f)return 1;
 double a=pars[0],d=pars[1],n=pars[2],eta=pars[3];if(n<0||eta<0)return 1;
 Sum event,pa,pd,pg,hn,j,jd,jg;
 for(size_t i=0;i<f->ge.size();++i){double lb=a+d*f->xe[i]-eta*f->ge[i],lh=n>0?std::log(n)+f->lh[i]:-INFINITY,mx=std::max(lb,lh);
  double ll=mx+std::log(std::exp(lb-mx)+std::exp(lh-mx)),p=std::exp(lb-ll);
  event.add(ll);pa.add(p);pd.add(p*f->xe[i]);pg.add(p*f->ge[i]);if(mask&4)hn.add(std::exp(f->lh[i]-ll));
 }
 j.add(bg(a,d,f->quiet,f->C,false));jd.add(bg(a,d,f->quiet,f->C,true));
 for(size_t i=0;i<f->gq.size();++i){double wb=f->wq[i]*std::exp(a+d*f->xq[i]-eta*f->gq[i]);j.add(wb);jd.add(wb*f->xq[i]);jg.add(wb*f->gq[i]);}
 if(eta==0){j.s=bg(a,d,f->T,f->C,false);jd.s=bg(a,d,f->T,f->C,true);}
 out[0]=j.s+n*f->integral-event.s;out[1]=j.s-pa.s;out[2]=jd.s-pd.s;out[3]=f->integral-hn.s;out[4]=pg.s-jg.s;
 for(int k=0;k<5;++k)if((k==0||(mask&(1<<(k-1))))&&!std::isfinite(out[k]))return 1;return 0;
 }catch(...){return 1;}
}
