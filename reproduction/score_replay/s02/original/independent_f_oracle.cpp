// Q01 independent finite-mixture raw-history audit. No producer includes or calls.
// Original panel/clock definition supplied as semantic inputs; native Gauss nodes
// generated independently. Scalar features belong only to this auditor.
#include <cmath>
#include <vector>
#include <algorithm>
#include <memory>
#include <string>
#include <stdexcept>
#include <limits>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
namespace faudit {
thread_local std::string error;
void require(bool x,const char*why){if(!x)throw std::runtime_error(why);}
struct Total {double x=0,c=0;void add(double v){double y=v-c,z=x+y;c=(z-x)-y;x=z;}};
struct F {
 std::vector<double> G,X,logH,QG,QX,QW;double exposure=0,quiet=0,T=0,coordinate=0;
};
void gauss(int order,std::vector<double>&nodes,std::vector<double>&weights){
 require(order>=2&&order%2==0,"even Gauss order required");nodes.resize(order);weights.resize(order);
 const double pi=3.141592653589793238462643383279502884;
 for(int j=0;j<order/2;++j){double root=std::cos(pi*(j+.75)/(order+.5)),derivative=0;
  for(int iter=0;iter<40;++iter){double a=1,b=root;for(int k=2;k<=order;++k){double z=((2*k-1)*root*b-(k-1)*a)/k;a=b;b=z;}derivative=order*(root*b-a)/(root*root-1);double delta=b/derivative;root-=delta;if(std::abs(delta)<2e-16)break;}
  double weight=2/((1-root*root)*derivative*derivative);nodes[j]=-root;nodes[order-j-1]=root;weights[j]=weights[order-j-1]=weight;
 }
}
std::pair<double,double> background(double a,double d,double duration,double T){
 double z=2*d*duration/T,E=0,E1=0;
 if(std::abs(z)<.2){double term=1;for(int k=0;k<28;++k){E+=term/(k+1);E1+=term/(k+2);term*=z/(k+1);}}
 else{E=std::expm1(z)/z;E1=((z-1)*std::exp(z)+1)/(z*z);}
 double factor=std::exp(a-d)*duration;return {factor*E,factor*(-E+2*duration/T*E1)};
}
double logarithm_sum(double a,double b){double m=std::max(a,b);return m+std::log(std::exp(a-m)+std::exp(b-m));}
}
API const char* qf_error(){return faudit::error.c_str();}
API void* qf_create(int N,const double*hi,const double*lo,const double*gap,const double*Q,int ms,const double*sw,const double*sr,int mt,const double*tw,const double*tr,int no,const double*offsets,int order,int paired,double horizon,double coordinate,double beta,double gamma,double ratio,double maximum_bytes){
 using namespace faudit;try{
  require(N>=0&&ms>0&&mt>0&&no>=0&&hi&&lo&&gap&&Q&&sw&&sr&&tw&&tr&&horizon>0&&coordinate>0&&ratio>=0&&ratio<1,"input domain");
  auto f=std::make_unique<F>();f->quiet=gap[0];f->T=horizon;f->coordinate=coordinate;
  std::vector<double>s(ms,0),trigger(mt,0),nodes,weights;gauss(order,nodes,weights);Total exposure;
  for(int i=0;i<=N;++i){double dt=gap[i];require(dt>=0&&std::isfinite(dt),"chronological gaps");
   if(i>0){double anchor=hi[i-1],residual=lo[i-1];std::vector<double>edges{0};for(int j=0;j<no;++j)if(offsets[j]<dt)edges.push_back(offsets[j]);edges.push_back(dt);
    for(size_t panel=1;panel<edges.size();++panel){double l=edges[panel-1],r=edges[panel];require(r>=l,"panel ordering");if(!paired){l=anchor+l;r=anchor+r;}
     require(24.*(f->QG.size()+order)+24.*N<=maximum_bytes,"auditor feature memory budget");
     for(int k=0;k<order;++k){double u=(l+r)/2+(r-l)*nodes[k]/2,age=paired?u:u-anchor;Total stress;
      for(int j=0;j<ms;++j)stress.add(sw[j]*s[j]*std::exp(-sr[j]*age));double absolute=paired?anchor+(residual+u):u;
      f->QG.push_back(stress.x);f->QX.push_back(2*absolute/coordinate-1);f->QW.push_back((r-l)*weights[k]/2);
     }
    }
   }
   if(i==N)break;
   Total G,H,tail;for(int j=0;j<ms;++j){s[j]*=std::exp(-sr[j]*dt);G.add(sw[j]*s[j]);}
   for(int j=0;j<mt;++j){trigger[j]*=std::exp(-tr[j]*dt);H.add(tw[j]*tr[j]*trigger[j]);tail.add(tw[j]*(-std::expm1(-tr[j]*((horizon-hi[i])-lo[i]))));}
   require(std::isfinite(G.x)&&std::isfinite(H.x),"unrepresentable feature");f->G.push_back(G.x);f->X.push_back(2*(hi[i]+lo[i])/coordinate-1);f->logH.push_back(H.x>0?std::log(H.x):-std::numeric_limits<double>::infinity());
   double stress_mark=std::exp(gamma*Q[i])/std::exp(gamma),productivity=(1-ratio)*std::exp(beta*ratio*Q[i]);
   require(std::isfinite(stress_mark)&&std::isfinite(productivity),"unrepresentable marks");for(double&v:s)v+=stress_mark;for(double&v:trigger)v+=productivity;exposure.add(productivity*tail.x);
  }
  f->exposure=exposure.x;return f.release();
 }catch(const std::exception&e){error=e.what();return nullptr;}
}
API void qf_free(void*ptr){delete static_cast<faudit::F*>(ptr);}
// out NLL, da,dd,dn,deta,number_quad_nodes. Marks common constant excluded.
API int qf_evaluate(void*handle,const double*par,double*out){
 using namespace faudit;try{
  require(handle&&par&&out,"evaluate pointers");auto&f=*static_cast<F*>(handle);double a=par[0],d=par[1],n=par[2],eta=par[3];require(n>=0&&eta>=0,"parameter bounds");
  Total logsum,pa,pd,pg,hn,j,jd,jg;for(size_t i=0;i<f.G.size();++i){double lb=a+d*f.X[i]-eta*f.G[i],lh=n>0?std::log(n)+f.logH[i]:-std::numeric_limits<double>::infinity(),ll=logarithm_sum(lb,lh),p=std::exp(lb-ll);logsum.add(ll);pa.add(p);pd.add(p*f.X[i]);pg.add(p*f.G[i]);hn.add(std::exp(f.logH[i]-ll));}
  auto quiet=background(a,d,f.quiet,f.coordinate);j.add(quiet.first);jd.add(quiet.second);
  for(size_t i=0;i<f.QG.size();++i){double b=f.QW[i]*std::exp(a+d*f.QX[i]-eta*f.QG[i]);j.add(b);jd.add(b*f.QX[i]);jg.add(b*f.QG[i]);}
  if(eta==0){auto exact=background(a,d,f.T,f.coordinate);j.x=exact.first;jd.x=exact.second;}
  out[0]=j.x+n*f.exposure-logsum.x;out[1]=j.x-pa.x;out[2]=jd.x-pd.x;out[3]=f.exposure-hn.x;out[4]=pg.x-jg.x;out[5]=(double)f.QG.size();
  for(int k=0;k<6;++k)require(std::isfinite(out[k]),"nonfinite reconstructed result");return 0;
 }catch(const std::exception&e){error=e.what();return 1;}
}
