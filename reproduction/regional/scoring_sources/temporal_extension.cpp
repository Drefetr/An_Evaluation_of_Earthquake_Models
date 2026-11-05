// Includes only independently authored Q01 oracle; no production code/cache.
#include "independent.cpp"
// Independent raw Tier1 temporal outputs: count,sumQ,B,trigger,eventLogGround,
// markLog,timingLog. Spatial point/joint logs require separate full-point mode.
API int q01_temporal(void*h,int n,const double*events,double*out){
 using namespace independent;try{
  need(h&&out&&n>=0&&(!n||events),"temporal pointers");auto&s=*static_cast<State*>(h);auto&p=s.parameters;
  Add marks,logs,trigger;
  auto fertility=[&](double q){double f=p[2]*.3*std::exp(.7*p[7]*q);need(std::isfinite(f),"productivity finite");return f;};
  std::vector<double> pf;pf.reserve(s.pre.size());
  for(const auto&e:s.pre){double f=fertility(e.q);pf.push_back(f);trigger.put(f*fraction(s,e.t));}
  std::vector<double> ef(n);
  for(int i=0;i<n;++i){const double*e=events+4*i;
   for(int j=0;j<4;++j)need(std::isfinite(e[j]),"finite raw event");
   need(e[0]>=p[9]&&e[0]<p[10]&&e[1]>=0&&(!i||e[0]>=events[4*(i-1)]),"raw chronology");s.cell(e[2],e[3]);
   ef[i]=fertility(e[1]);marks.put(e[1]);trigger.put(ef[i]*fraction(s,e[0]));
   Add ground;ground.put(std::exp(p[0]+p[1]*(2*e[0]/p[8]-1)));
   auto put=[&](double t,double f){double lag=e[0]-t;if(lag>0)ground.put(f*(p[4]-1)/p[3]*std::exp(-p[4]*std::log1p(lag/p[3])));};
   for(size_t j=0;j<s.pre.size();++j)put(s.pre[j].t,pf[j]);
   for(int j=0;j<i;++j)put(events[4*j],ef[j]);
   need(ground.value>0&&std::isfinite(ground.value),"ground intensity");logs.put(std::log(ground.value));
  }
  double B=immigrant(s),ml=n*std::log(p[7])-p[7]*marks.value;
  out[0]=n;out[1]=marks.value;out[2]=B;out[3]=trigger.value;out[4]=logs.value;out[5]=ml;out[6]=logs.value-B-trigger.value;
  for(int j=0;j<7;++j)need(std::isfinite(out[j]),"finite temporal output");return 0;
 }catch(const std::exception&e){error=e.what();return 1;}
}
