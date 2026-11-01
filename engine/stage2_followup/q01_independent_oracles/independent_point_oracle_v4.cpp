// Q01 independent raw-path evaluator. No production includes, DLLs or caches.
// Spatial masses use polar ray/rectangle intersection and positive radial integrals.
#include <cmath>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <string>
#include <memory>
#include <limits>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
namespace independent {
constexpr double PI=3.141592653589793238462643383279502884;
thread_local std::string error;
void need(bool v,const char* why){if(!v)throw std::runtime_error(why);}
struct Add {double value=0,correction=0;void put(double x){double y=x-correction,z=value+y;correction=(z-value)-y;value=z;}};
struct Box {double x0,x1,y0,y1;};
struct Ray {
 Box b;double scale,q;
 double operator()(double theta)const{
  double lower=0,upper=std::numeric_limits<double>::infinity();
  auto slab=[&](double lo,double hi,double direction){
   if(direction==0)return lo<=0&&hi>=0;
   double a=lo/direction,c=hi/direction;if(a>c)std::swap(a,c);
   lower=std::max(lower,a);upper=std::min(upper,c);return upper>lower;
  };
  if(!slab(b.x0,b.x1,std::cos(theta))||!slab(b.y0,b.y1,std::sin(theta))||upper<=0)return 0;
  lower=std::max(0.,lower);if(upper<=lower)return 0;
  double ll=std::log1p((lower/scale)*(lower/scale));
  double uu=std::log1p((upper/scale)*(upper/scale));
  return scale*scale/(2*(q-1))*std::exp((1-q)*ll)*(-std::expm1((1-q)*(uu-ll)));
 }
};
double simpson(const Ray&f,double a,double b,double fa,double fm,double fb,double whole,double tolerance,int depth){
 double mid=(a+b)/2,lm=(a+mid)/2,rm=(mid+b)/2,fl=f(lm),fr=f(rm);
 double left=(mid-a)*(fa+4*fl+fm)/6,right=(b-mid)*(fm+4*fr+fb)/6,delta=left+right-whole;
 if(std::abs(delta)<=15*tolerance)return left+right+delta/15;
 need(depth<24,"independent polar quadrature did not converge");
 return simpson(f,a,mid,fa,fl,fm,left,tolerance/2,depth+1)+simpson(f,mid,b,fm,fr,fb,right,tolerance/2,depth+1);
}
// Open-node Gauss integration avoids using angular cut endpoint values.
// The absolute error budget remains the original segment estimate *2e-11.
double polar_rule(const Ray&f,double a,double b,int order){
 Add sum;for(int j=0;j<(order+1)/2;++j){double z=std::cos(PI*(j+.75)/(order+.5)),der=0;
  for(int it=0;it<40;++it){double p0=1,p1=z;for(int k=2;k<=order;++k){double pn=((2*k-1)*z*p1-(k-1)*p0)/k;p0=p1;p1=pn;}der=order*(z*p1-p0)/(z*z-1);double step=p1/der;z-=step;if(std::abs(step)<2e-16)break;}
  // Recompute derivative at final root, independently of last Newton step.
  double p0=1,p1=z;for(int k=2;k<=order;++k){double pn=((2*k-1)*z*p1-(k-1)*p0)/k;p0=p1;p1=pn;}der=order*(z*p1-p0)/(z*z-1);
  double weight=2/((1-z*z)*der*der),m=(a+b)/2,h=(b-a)/2;sum.put(weight*(f(m-h*z)+f(m+h*z)));
 }return (b-a)/2*sum.value;
}
double polar_adapt(const Ray&f,double a,double b,double tolerance,int depth){
 double lower=polar_rule(f,a,b,16),upper=polar_rule(f,a,b,32);
 if(std::abs(upper-lower)<=tolerance)return upper;
 need(depth<32,"independent open polar quadrature did not converge");double mid=(a+b)/2;need(mid>a&&mid<b,"independent polar floating interval exhausted");
 return polar_adapt(f,a,mid,tolerance/2,depth+1)+polar_adapt(f,mid,b,tolerance/2,depth+1);
}
double mass(Box b,double px,double py,double scale,double q){
 need(scale>0&&q>1&&b.x1>b.x0&&b.y1>b.y0,"radial domain");
 b.x0-=px;b.x1-=px;b.y0-=py;b.y1-=py;Ray f{b,scale,q};
 std::vector<double> cuts{0,PI/2,PI,3*PI/2,2*PI};
 for(double x:{b.x0,b.x1})for(double y:{b.y0,b.y1}){double a=std::atan2(y,x);if(a<0)a+=2*PI;cuts.push_back(a);}
 // Resolve narrow angular layers where a near face is intersected at
 // radial distances comparable to the kernel scale. Corner/quadrant cuts
 // alone do not resolve a parent arbitrarily close to a face.
 auto angle=[&](double a){while(a<0)a+=2*PI;while(a>=2*PI)a-=2*PI;cuts.push_back(a);};
 for(double radius_factor:{.25,1.,4.,16.}){double radius=radius_factor*scale;
  for(double distance:{b.x0,b.x1})if(distance!=0&&std::abs(distance)<16*scale&&std::abs(distance)<radius){double a=std::acos(distance/radius);angle(a);angle(2*PI-a);}
  for(double distance:{b.y0,b.y1})if(distance!=0&&std::abs(distance)<16*scale&&std::abs(distance)<radius){double a=std::asin(distance/radius);angle(a);angle(PI-a);}
 }
 std::sort(cuts.begin(),cuts.end());cuts.erase(std::unique(cuts.begin(),cuts.end()),cuts.end());Add sum;
 for(size_t i=1;i<cuts.size();++i){double a=cuts[i-1],b1=cuts[i],whole=polar_rule(f,a,b1,32);
  if(whole==0)continue;
  sum.put(polar_adapt(f,a,b1,std::max(1e-300,std::abs(whole)*2e-11),0));
 }
 need(sum.value>0&&std::isfinite(sum.value),"independent nonpositive rectangle mass");return sum.value;
}
struct Event {double t,q,x,y,z;};
struct State {
 std::vector<Box> boxes;std::vector<double> rho,pi,background_z,parameters;std::vector<Event> training,pre;
 int model;
 int cell(double x,double y)const{int found=-1;for(size_t j=0;j<boxes.size();++j){auto b=boxes[j];if(x>=b.x0&&x<=b.x1&&y>=b.y0&&y<=b.y1)found=(int)j;}need(found>=0,"point outside domain");return found;}
 double normalizer(double x,double y,double scale,double q,bool weighted)const {Add a;for(size_t k=0;k<boxes.size();++k)a.put(mass(boxes[k],x,y,scale,q)*(weighted?rho[k]:1));return a.value;}
 double kernel(double x,double y,const Event&e,double scale,double q)const {double dx=(x-e.x)/scale,dy=(y-e.y)/scale;return std::exp(-q*std::log1p(dx*dx+dy*dy));}
 double background(double x,double y)const{Add a;for(size_t j=0;j<training.size();++j)a.put(kernel(x,y,training[j],parameters[6],2)/background_z[j]);return .05*rho[cell(x,y)]+.95*a.value/training.size();}
 Event parent(const double*row)const{Event e{row[0],row[1],row[2],row[3],0};need(e.q>=0&&std::isfinite(e.q),"mark domain");cell(e.x,e.y);e.z=normalizer(e.x,e.y,parameters[5],model?parameters[11]:2,!model);return e;}
};
double immigrant(const State&s){auto&p=s.parameters;double dt=p[10]-p[9],z=2*p[1]*dt/p[8];return dt*std::exp(p[0]+p[1]*(2*p[9]/p[8]-1))*(z==0?1:std::expm1(z)/z);}
double fraction(const State&s,double t){auto&p=s.parameters;if(t>=p[10])return 0;double a=std::max(p[9]-t,0.),b=p[10]-t;return std::exp((1-p[4])*std::log1p(a/p[3]))*(-std::expm1((1-p[4])*std::log1p((b-a)/(p[3]+a))));}
}
API const char* q01_error(){return independent::error.c_str();}
API double q01_mass(const double*b,double x,double y,double scale,double q){try{return independent::mass({b[0],b[1],b[2],b[3]},x,y,scale,q);}catch(const std::exception&e){independent::error=e.what();return NAN;}}
API void* q01_create(int nt,const double*xy,int np,const double*pre,const double*rect,const double*pi,const double*p,int model){
 using namespace independent;try{
  need(nt>0&&np>=0&&xy&&rect&&pi&&p&&(!np||pre),"state pointers");auto s=std::make_unique<State>();s->model=model;s->parameters.assign(p,p+12);
  for(double x:s->parameters)need(std::isfinite(x),"nonfinite parameter");need(p[2]>=0&&p[3]>0&&p[4]>1&&p[5]>0&&p[6]>0&&p[7]>0&&p[8]>0&&p[10]>p[9]&&(!model||p[11]>1),"parameter domain");
  double psum=0;for(int k=0;k<9;++k){Box b{rect[4*k],rect[4*k+1],rect[4*k+2],rect[4*k+3]};need(b.x1>b.x0&&b.y1>b.y0&&pi[k]>0,"reference domain");s->boxes.push_back(b);s->pi.push_back(pi[k]);s->rho.push_back(pi[k]/((b.x1-b.x0)*(b.y1-b.y0)));psum+=pi[k];}need(std::abs(psum-1)<1e-12,"reference mass");
  for(int i=0;i<nt;++i){Event e{0,0,xy[2*i],xy[2*i+1],0};s->cell(e.x,e.y);s->training.push_back(e);s->background_z.push_back(s->normalizer(e.x,e.y,p[6],2,false));}
  for(int j=0;j<np;++j){auto e=s->parent(pre+4*j);need(e.t<p[9]&&(!j||e.t>=s->pre.back().t),"prehistory chronology");s->pre.push_back(e);}return s.release();
 }catch(const std::exception&e){error=e.what();return nullptr;}
}
API void q01_free(void*h){delete static_cast<independent::State*>(h);}
// out count,sumQ,B,triggerExposure,eventLogGround,eventLogPoint,markLog,joint.
API int q01_evaluate(void*h,int n,const double*events,double*out){
 using namespace independent;try{
  need(h&&out&&n>=0&&(!n||events),"evaluate pointers");auto&s=*static_cast<State*>(h);auto&p=s.parameters;std::vector<Event> parents=s.pre;Add marks,logground,logpoint,trigger;
  for(const auto&e:parents)trigger.put(p[2]*.3*std::exp(.7*p[7]*e.q)*fraction(s,e.t));
  for(int i=0;i<n;++i){auto e=s.parent(events+4*i);need(e.t>=p[9]&&e.t<p[10]&&(!i||e.t>=events[4*(i-1)]),"future chronology");
   double mu=std::exp(p[0]+p[1]*(2*e.t/p[8]-1));Add ground,point;ground.put(mu);point.put(mu*s.background(e.x,e.y));
   for(const auto&parent:parents){double dt=e.t-parent.t;if(dt<=0)continue;double temp=p[2]*.3*std::exp(.7*p[7]*parent.q)*(p[4]-1)/p[3]*std::exp(-p[4]*std::log1p(dt/p[3]));ground.put(temp);point.put(temp*s.kernel(e.x,e.y,parent,p[5],s.model?p[11]:2)/parent.z*(s.model?1:s.rho[s.cell(e.x,e.y)]));}
   need(ground.value>0&&point.value>0,"nonpositive intensity");logground.put(std::log(ground.value));logpoint.put(std::log(point.value));marks.put(e.q);trigger.put(p[2]*.3*std::exp(.7*p[7]*e.q)*fraction(s,e.t));parents.push_back(e);
  }
  double B=immigrant(s),ml=n*std::log(p[7])-p[7]*marks.value;
  out[0]=n;out[1]=marks.value;out[2]=B;out[3]=trigger.value;out[4]=logground.value;out[5]=logpoint.value;out[6]=ml;out[7]=logpoint.value-B-trigger.value+ml;
  for(int j=0;j<8;++j)need(std::isfinite(out[j]),"nonfinite oracle output");return 0;
 }catch(const std::exception&e){error=e.what();return 1;}
}

API int q01_mass_batch(int n,const double*boxes,const double*centers,double scale,double q,double*out){
 using namespace independent;try{need(n>=0&&boxes&&centers&&out,"batch pointers");for(int i=0;i<n;++i){Box b{boxes[4*i],boxes[4*i+1],boxes[4*i+2],boxes[4*i+3]};out[i]=(b.x1<=b.x0||b.y1<=b.y0)?0:mass(b,centers[2*i],centers[2*i+1],scale,q);}return 0;}catch(const std::exception&e){error=e.what();return 1;}
}
namespace independent {
struct Cross {
 double horizontal,scale,q;
 double operator()(double theta)const{return std::pow(std::cos(theta),2*q-2);}
};
double cross_rule(const Cross&f,double a,double b,int order){
 // Independently generated Gauss nodes via Legendre Newton roots.
 Add sum;for(int j=0;j<(order+1)/2;++j){double z=std::cos(PI*(j+.75)/(order+.5)),der=0;
  for(int it=0;it<30;++it){double p0=1,p1=z;for(int k=2;k<=order;++k){double pn=((2*k-1)*z*p1-(k-1)*p0)/k;p0=p1;p1=pn;}der=order*(z*p1-p0)/(z*z-1);double change=p1/der;z-=change;if(std::abs(change)<2e-16)break;}
  double wt=2/((1-z*z)*der*der),m=(a+b)/2,h=(b-a)/2;sum.put(wt*(f(m-h*z)+f(m+h*z)));
 }return (b-a)/2*sum.value;
}
double cross_adapt(const Cross&f,double a,double b,int depth){double lo=cross_rule(f,a,b,8),hi=cross_rule(f,a,b,16);if(std::abs(lo-hi)<=2e-11*std::abs(hi)+1e-300)return hi;need(depth<24,"line quadrature convergence");double mid=(a+b)/2;return cross_adapt(f,a,mid,depth+1)+cross_adapt(f,mid,b,depth+1);}
double line(double lower,double upper,double horizontal,double scale,double q){if(upper<=lower)return 0;double A=1+(horizontal/scale)*(horizontal/scale),root=scale*std::sqrt(A);double a=std::atan2(lower,root),b=std::atan2(upper,root);need(b>a,"line angle precision");return scale*std::pow(A,.5-q)*cross_adapt({horizontal,scale,q},a,b,0);}
}
API int q01_line_batch(int n,const double*lower,const double*upper,const double*horizontal,double scale,double q,double*out){
 using namespace independent;try{need(n>=0&&lower&&upper&&horizontal&&out,"line pointers");for(int i=0;i<n;++i)out[i]=line(lower[i],upper[i],horizontal[i],scale,q);return 0;}catch(const std::exception&e){error=e.what();return 1;}
}
