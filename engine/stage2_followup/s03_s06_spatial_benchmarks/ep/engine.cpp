// Original O-C conditional marked branching law. One thread, binary64 chronology.
// Local event arrays must never be forwarded to a model/provider context.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <random>
#include <stdexcept>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C" __attribute__((visibility("default")))
#endif
#define CC_STRINGIFY_INNER(x) #x
#define CC_STRINGIFY(x) CC_STRINGIFY_INNER(x)
namespace {
thread_local char error_text[512]={};
void check(bool b,const char*s){if(!b)throw std::runtime_error(s);}
void finite(double x,const char*s){check(std::isfinite(x),s);}
void error(const char*s){std::strncpy(error_text,s,511);error_text[511]=0;}
using Rect=std::array<double,4>;
struct Event{double t,q,x,y;};
struct Shape{std::array<double,9> mass{},prob{};double z=0;};
struct Parent{Event e;double kappa;Shape shape;};
struct Rule {
 std::vector<long double>x,w;
 explicit Rule(int n):x(n),w(n){
  const long double pi=std::acos(-1.L);
  for(int i=0;i<(n+1)/2;++i){long double z=std::cos(pi*(i+.75L)/(n+.5L)),pp=0;
   for(int k=0;k<64;++k){long double p0=1,p1=z;
    for(int j=2;j<=n;++j){auto p=((2*j-1)*z*p1-(j-1)*p0)/j;p0=p1;p1=p;}
    pp=n*(z*p1-p0)/(z*z-1);auto next=z-p1/pp;
    if(std::abs(next-z)<4*std::numeric_limits<long double>::epsilon()){z=next;break;}z=next;
   }
   // Recompute derivative at final node (weights are not based on prior iterate).
   long double p0=1,p1=z;for(int j=2;j<=n;++j){auto p=((2*j-1)*z*p1-(j-1)*p0)/j;p0=p1;p1=p;}
   pp=n*(z*p1-p0)/(z*z-1);x[i]=-z;x[n-1-i]=z;w[i]=w[n-1-i]=2/((1-z*z)*pp*pp);
  }
 }
};
const Rule gl16(16),gl32(32);
long double angle(long double lo,long double hi,long double s){
 auto z=std::atan2(s*(hi-lo),s*s+hi*lo);return z>0?z:z+std::acos(-1.L);
}
// Positive cross section: y=sqrt(A)tan(theta), never subtract two primitives.
long double cross(long double x,long double lo,long double hi,long double s){
 long double A=s*s+x*x,root=std::sqrt(A),a=std::atan2(lo,root),d=angle(lo,hi,root);
 if(lo>8*root||hi< -8*root){
  // Reciprocal coordinate avoids cos(atan(y/root)) in a deep tail.
  if(hi<0){auto tmp=lo;lo=-hi;hi=-tmp;}
  auto wl=root/hi,wh=root/lo,m=(wl+wh)/2,h=(wh-wl)/2;long double v=0;
  for(std::size_t i=0;i<gl16.x.size();++i){auto w=m+h*gl16.x[i],den=1+w*w;v+=gl16.w[i]*w*w/(den*den);}
  return s*s*s*s/(A*root)*h*v;
 }
 auto wave=std::cos(2*a+d)*std::sin(d),integral=(d+wave)/2;
 if(integral>1e-5L*(d+std::abs(wave)))return s*s*s*s/(A*root)*integral;
 // Integral cos^2(theta) dtheta, evaluated by a positive GL rule when the
 // interval is very narrow or near +/-pi/2 (closed form would cancel).
 long double sum=0;for(std::size_t i=0;i<gl16.x.size();++i){auto th=a+(gl16.x[i]+1)*d/2;auto c=std::cos(th);sum+=gl16.w[i]*c*c;}
 return s*s*s*s/(A*root)*d/2*sum;
}
long double integrate_cross(long double xl,long double xh,long double yl,long double yh,long double s,const Rule&r){
 long double m=(xl+xh)/2,h=(xh-xl)/2,v=0;
 for(std::size_t i=0;i<r.x.size();++i)v+=r.w[i]*cross(m+h*r.x[i],yl,yh,s);return h*v;
}
long double positive_mass(long double xl,long double xh,long double yl,long double yh,long double s,int depth=0){
 auto a=integrate_cross(xl,xh,yl,yh,s,gl16),b=integrate_cross(xl,xh,yl,yh,s,gl32);
 if(std::abs(a-b)<=2e-13L*std::abs(b))return b;
 check(depth<24,"positive rectangle integration depth");auto m=(xl+xh)/2;
 return positive_mass(xl,m,yl,yh,s,depth+1)+positive_mass(m,xh,yl,yh,s,depth+1);
}
double rectangle(const Rect&r,double px,double py,double s){
 check(s>0&&std::isfinite(s),"positive spatial scale");
 long double xl=(long double)r[0]-px,xh=(long double)r[1]-px,yl=(long double)r[2]-py,yh=(long double)r[3]-py,ss=(long double)s*s;
 check(xl<xh&&yl<yh,"rectangle orientation");
 auto fx=[&](long double x){auto root=std::sqrt(ss+x*x);return x/root*angle(yl,yh,root);};
 auto fy=[&](long double y){auto root=std::sqrt(ss+y*y);return y/root*angle(xl,xh,root);};
 long double v[4]={fx(xh),-fx(xl),fy(yh),-fy(yl)},sum=v[0]+v[1]+v[2]+v[3],ab=0;for(auto z:v)ab+=std::abs(z);
 long double mass=ss/2*sum;
 if(!(mass>0)||sum<1e-5L*ab){
  // Geometric cuts prevent the two quadrature rules from jointly missing a
  // narrow peak. No signed boundary cancellation enters this fallback.
  std::vector<long double>cuts={xl,xh};if(xl<0&&xh>0)cuts.push_back(0);
  for(int k=-20;k<=40;++k)for(int sign:{-1,1}){auto x=sign*std::ldexp((long double)s,k);if(x>xl&&x<xh)cuts.push_back(x);}
  std::sort(cuts.begin(),cuts.end());mass=0;
  for(std::size_t i=1;i<cuts.size();++i)mass+=positive_mass(cuts[i-1],cuts[i],yl,yh,s);
 }
 double out=(double)mass;check(out>0&&std::isfinite(out),"positive finite rectangle mass");return out;
}
namespace ep {
struct Triple { double v=0, ds=0, dq=0; };
Triple operator+(Triple a,Triple b) { return {a.v+b.v,a.ds+b.ds,a.dq+b.dq}; }
Triple operator-(Triple a,Triple b) { return {a.v-b.v,a.ds-b.ds,a.dq-b.dq}; }
Triple operator*(double k,Triple a) { return {k*a.v,k*a.ds,k*a.dq}; }

// Divergence theorem: div[x F(r), y F(r)] = (1+r^2/ell^2)^(-q),
// F(r)=ell^2/(2(q-1)r^2) * [1-(1+r^2/ell^2)^(1-q)].
// Derivatives are with respect to log(ell) and q.
Triple flux(double r2,double ell,double q) {
  if(r2==0) return {.5,0,0};
  double u=r2/(ell*ell),v=std::log1p(u),a=q-1,z=a*v;
  if(u==0)return {.5,0,0}; // representable r2 can still underflow after division
  double f=(-std::expm1(-z))/(2*a*u);
  if(z<1e-4){
    double z2=z*z,z4=z2*z2,one_minus_t=z/2-z2/12+z4/720;
    double ratio_u=(u<1e-4)?(1-u/2+5*u*u/12):u/((1+u)*v);
    double one_minus_ratio=(u<1e-4)?(u/2-5*u*u/12):(1-ratio_u);
    return {f,f*2*(one_minus_ratio+ratio_u*one_minus_t),f*(-one_minus_t/a)};
  }
  double ratio=1/std::expm1(z);
  return {f,f*(2-2*a*u/(1+u)*ratio),f*(-1/a+v*ratio)};
}
// Fixed 16/32 point Gauss-Legendre pairs, nodes/weights generated once locally.
struct Rule { std::vector<double> x,w; explicit Rule(int n) {
  x.resize(n);w.resize(n);const double pi=std::acos(-1.);
  for(int i=0;i<(n+1)/2;++i){double z=std::cos(pi*(i+.75)/(n+.5)),pp=0;
    for(int it=0;it<30;++it){double p0=1,p1=z;for(int k=2;k<=n;++k){double p=((2*k-1)*z*p1-(k-1)*p0)/k;p0=p1;p1=p;}pp=n*(z*p1-p0)/(z*z-1);double next=z-p1/pp;if(std::abs(next-z)<2e-16){z=next;break;}z=next;}
    x[i]=-z;x[n-1-i]=z;w[i]=w[n-1-i]=2/((1-z*z)*pp*pp);
  }
}};
const Rule low(16),high(32),very_high(64);
thread_local bool fine_order=false;
Triple edge_rule(double fixed,double lo,double hi,double ell,double q,const Rule& rule) {
  double half=(hi-lo)/2,center=(hi+lo)/2;Triple sum;
  for(std::size_t i=0;i<rule.x.size();++i){double z=center+half*rule.x[i];sum=sum+(rule.w[i]*flux(fixed*fixed+z*z,ell,q));}
  return (fixed*half)*sum;
}
Triple edge(double fixed,double lo,double hi,double ell,double q,int depth=0) {
  // This is one oriented edge's unsigned-coordinate integral; fixed may be signed.
  const Rule& first=fine_order?high:low;const Rule& second=fine_order?very_high:high;
  Triple a=edge_rule(fixed,lo,hi,ell,q,first),b=edge_rule(fixed,lo,hi,ell,q,second);
  double scale=std::max({1.,std::abs(b.v),std::abs(b.ds),std::abs(b.dq)});
  double tol=fine_order?1e-12:2e-11;
  bool converged=std::abs(a.v-b.v)<tol*scale && std::abs(a.ds-b.ds)<10*tol*scale && std::abs(a.dq-b.dq)<10*tol*scale;
  if(converged)return b;
  check(depth<18,"edge quadrature depth");
  double mid=(lo+hi)/2;return edge(fixed,lo,mid,ell,q,depth+1)+edge(fixed,mid,hi,ell,q,depth+1);
}
Triple area_rule(double xl,double xh,double yl,double yh,double ell,double q,const Rule& rule) {
  double mx=(xl+xh)/2,my=(yl+yh)/2,hx=(xh-xl)/2,hy=(yh-yl)/2;Triple sum;
  for(std::size_t i=0;i<rule.x.size();++i)for(std::size_t j=0;j<rule.x.size();++j){
    double x=mx+hx*rule.x[i],y=my+hy*rule.x[j],u=(x*x+y*y)/(ell*ell),v=std::log1p(u),d=std::exp(-q*v),w=hx*hy*rule.w[i]*rule.w[j];
    sum=sum+(w*Triple{d,d*2*q*u/(1+u),-d*v});
  }return sum;
}
Triple area_fallback(double xl,double xh,double yl,double yh,double ell,double q,int depth=0) {
  const Rule& first=fine_order?high:low;const Rule& second=fine_order?very_high:high;
  Triple a=area_rule(xl,xh,yl,yh,ell,q,first),b=area_rule(xl,xh,yl,yh,ell,q,second);
  bool converged=std::abs(a.v-b.v)<1e-10*std::abs(b.v) && std::abs(a.ds-b.ds)<1e-9*std::max(1e-30,std::abs(b.ds)) && std::abs(a.dq-b.dq)<1e-9*std::max(1e-30,std::abs(b.dq));
  if(converged)return b;
  check(depth<8,"area quadrature depth");
  double xm=(xl+xh)/2,ym=(yl+yh)/2;
  return area_fallback(xl,xm,yl,ym,ell,q,depth+1)+area_fallback(xm,xh,yl,ym,ell,q,depth+1)
       +area_fallback(xl,xm,ym,yh,ell,q,depth+1)+area_fallback(xm,xh,ym,yh,ell,q,depth+1);
}
Triple rectangle(const double* rect,double px,double py,double ell,double q) {
  double xl=rect[0]-px,xh=rect[1]-px,yl=rect[2]-py,yh=rect[3]-py;
  check(xl<xh && yl<yh,"rectangle orientation");
  finite(xl,"rectangle coordinate");finite(xh,"rectangle coordinate");finite(yl,"rectangle coordinate");finite(yh,"rectangle coordinate");
  Triple top=edge(yh,xl,xh,ell,q),bottom=edge(yl,xl,xh,ell,q),right=edge(xh,yl,yh,ell,q),left=edge(xl,yl,yh,ell,q);
  Triple z=top-bottom+right-left;
  double cancellation=std::abs(top.v)+std::abs(bottom.v)+std::abs(right.v)+std::abs(left.v);
  if(z.v<=0 || z.v<1e-3*cancellation)z=area_fallback(xl,xh,yl,yh,ell,q);
  double sign_tol=1e-9*std::max(std::abs(z.v),1e-14);
  if(z.ds< -sign_tol || z.dq>sign_tol)z=area_fallback(xl,xh,yl,yh,ell,q);
  check(z.v>0 && std::isfinite(z.v) && std::isfinite(z.ds) && std::isfinite(z.dq),"rectangle mass");
  sign_tol=1e-9*std::max(std::abs(z.v),1e-14);
  check(z.ds>=-sign_tol && z.dq<=sign_tol,"rectangle derivative sign");
  return z;
}
}
thread_local double ep_q=2;
double ep_kernel(double x,double y,double px,double py,double scale){double dx=(x-px)/scale,dy=(y-py)/scale;return std::exp(-ep_q*std::log1p(dx*dx+dy*dy));}
double ep_rectangle(const Rect&r,double px,double py,double scale){return ep::rectangle(r.data(),px,py,scale,ep_q).v;}
long double ep_cross(long double x,long double lo,long double hi,long double scale,int depth=0){
 auto integrate=[&](const Rule&r){long double sum=0,m=(lo+hi)/2,h=(hi-lo)/2;for(std::size_t i=0;i<r.x.size();++i){auto y=m+h*r.x[i];sum+=r.w[i]*std::exp(-ep_q*std::log1p((x*x+y*y)/(scale*scale)));}return h*sum;};
 auto a=integrate(gl16),b=integrate(gl32);if(std::abs(a-b)<=2e-12L*std::abs(b))return b;check(depth<24,"EP line quadrature depth");auto m=(lo+hi)/2;return ep_cross(x,lo,m,scale,depth+1)+ep_cross(x,m,hi,scale,depth+1);}
double kernel(double x,double y,double px,double py,double s){auto dx=(x-px)/s,dy=(y-py)/s,z=1+dx*dx+dy*dy;return 1/(z*z);}
struct State {
 // a,d,n,c,p,scale,bandwidth,beta,T0,start,end. c is natural, not log(c).
 std::array<double,12> p;
 std::array<Rect,9>rect;std::array<double,9>pi,rho,bcell;
 std::vector<Event>training;std::vector<Shape>kde;std::vector<Parent>pre;
 Rect whole;
 int cell(double x,double y)const{int k=-1;for(int i=0;i<9;++i)if(x>=rect[i][0]&&x<=rect[i][1]&&y>=rect[i][2]&&y<=rect[i][3])k=i;check(k>=0,"point outside support");return k;}
 Shape shape(double x,double y,double s,bool weighted)const{Shape v;for(int k=0;k<9;++k){v.mass[k]=weighted?ep_rectangle(rect[k],x,y,s):rectangle(rect[k],x,y,s);v.prob[k]=v.mass[k];v.z+=v.prob[k];}check(v.z>0&&std::isfinite(v.z),"spatial normalizer");for(auto&z:v.prob)z/=v.z;return v;}
 Parent parent(Event e)const{check(e.q>=0&&std::isfinite(e.q),"nonnegative finite mark");double k=.3*std::exp(.7*p[7]*e.q);finite(k,"productivity overflow");return{e,k,shape(e.x,e.y,p[5],true)};}
 double mu(double t)const{return std::exp(p[0]+p[1]*(2*t/p[8]-1));}
 double B(double a,double b)const{if(a==b)return 0;check(b>a,"immigrant integration bounds");auto z=p[1]*(b-a)/p[8];double sc;if(std::abs(z)<1e-4){auto zz=z*z;sc=1+zz/6+zz*zz/120+zz*zz*zz/5040;}else sc=std::sinh(z)/z;auto v=(b-a)*std::exp(p[0]+p[1]*((a+b)/p[8]-1))*sc;finite(v,"immigrant exposure overflow");return v;}
 double J(double t,double a,double b)const{if(t>=b)return 0;double L=std::max(a-t,0.),U=b-t,lp=std::log1p(L/p[3]);return std::exp((1-p[4])*lp)*(-std::expm1((1-p[4])*std::log1p((U-L)/(p[3]+L))));}
 double g(double lag)const{return lag>0?(p[4]-1)/p[3]*std::exp(-p[4]*std::log1p(lag/p[3])):0;}
 double background(double x,double y)const{double v=0;for(std::size_t i=0;i<training.size();++i)v+=kernel(x,y,training[i].x,training[i].y,p[6])/kde[i].z;return .05*rho[cell(x,y)]+.95*v/training.size();}
};
struct Random {
 using result_type=std::uint64_t;
 std::mt19937_64 engine;std::uint64_t draws=0,proposals=0;
 explicit Random(const std::uint32_t*seed){std::seed_seq words(seed,seed+4);engine.seed(words);}
 static constexpr result_type min(){return std::mt19937_64::min();}
 static constexpr result_type max(){return std::mt19937_64::max();}
 result_type operator()(){++draws;return engine();}
 double u(){return (((*this)()>>12)+.5)*0x1.0p-52;}
 std::uint64_t poisson(double mean){check(mean>=0&&std::isfinite(mean),"Poisson mean overflow");check(mean<(double)std::numeric_limits<std::uint64_t>::max()/4,"Poisson integer overflow");if(mean==0)return 0;std::poisson_distribution<std::uint64_t>d(mean);return d(*this);}
};
int categorical(const std::array<double,9>&p,Random&r){auto u=r.u();double v=0;for(int k=0;k<8;++k){v+=p[k];if(u<v)return k;}return 8;}
std::array<double,2> sample_rectangle(const Rect&b,double px,double py,double s,double mass,Random&r,bool ep=false){
 double cx=std::max(b[0],std::min(b[1],px)),cy=std::max(b[2],std::min(b[3],py));
 double kmax=ep?ep_kernel(cx,cy,px,py,s):kernel(cx,cy,px,py,s),area=(b[1]-b[0])*(b[3]-b[2]),plane=std::acos(-1.)*s*s/(ep?ep_q-1:1);
 // mass/(area*kmax) >= mass/plane iff area*kmax <= plane.
 // No outcome-dependent envelope choice, and no rejection has parenthood.
 check(mass>0&&kmax>0,"spatial envelope");bool uniform=area*kmax<=plane;
 for(;;){++r.proposals;double x,y;
  if(uniform){x=b[0]+r.u()*(b[1]-b[0]);y=b[2]+r.u()*(b[3]-b[2]);double ratio=(ep?ep_kernel(x,y,px,py,s):kernel(x,y,px,py,s))/kmax;check(ratio<=1+2e-14,"uniform spatial bound");if(r.u()<=ratio)return{x,y};}
  else{double u=r.u(),rad=s*std::sqrt(std::expm1(-std::log1p(-u)/(ep?ep_q-1:1))),theta=2*std::acos(-1.)*r.u();finite(rad,"spatial radial inverse overflow");x=px+rad*std::cos(theta);y=py+rad*std::sin(theta);if(x>=b[0]&&x<=b[1]&&y>=b[2]&&y<=b[3])return{x,y};}
 }
}
std::array<double,2> sample_location(const State&s,const Parent&parent,Random&r){int k=categorical(parent.shape.prob,r);return sample_rectangle(s.rect[k],parent.e.x,parent.e.y,s.p[5],parent.shape.mass[k],r,true);}
std::array<double,2> sample_background(const State&s,Random&r){
 if(r.u()<.05){int k=categorical(s.pi,r);return{s.rect[k][0]+r.u()*(s.rect[k][1]-s.rect[k][0]),s.rect[k][2]+r.u()*(s.rect[k][3]-s.rect[k][2])};}
 auto i=std::min(s.training.size()-1,(std::size_t)(r.u()*s.training.size()));int k=categorical(s.kde[i].prob,r);return sample_rectangle(s.rect[k],s.training[i].x,s.training[i].y,s.p[6],s.kde[i].mass[k],r);
}
std::unique_ptr<State> make_state(int nh,const double*h,int nt,const double*xy,const double*bounds,const double*pi,const double*parameters){
 check(nh>=0&&nt>0&&(!nh||h)&&xy&&bounds&&pi&&parameters,"state arguments");auto s=std::unique_ptr<State>(new State());
 ep_q=parameters[11];check(ep_q>1&&std::isfinite(ep_q),"EP spatial exponent");
 for(int i=0;i<12;++i){finite(parameters[i],"state parameter");s->p[i]=parameters[i];}
 check(s->p[2]>=0&&s->p[3]>0&&s->p[4]>1&&s->p[5]>0&&s->p[6]>0&&s->p[7]>0&&s->p[8]>0&&s->p[10]>s->p[9],"state parameter domain");
 double sum=0;for(int k=0;k<9;++k){for(int j=0;j<4;++j){finite(bounds[4*k+j],"rectangle coordinate");s->rect[k][j]=bounds[4*k+j];}auto&r=s->rect[k];check(r[1]>r[0]&&r[3]>r[2]&&pi[k]>0&&std::isfinite(pi[k]),"cell domain");s->pi[k]=pi[k];s->rho[k]=pi[k]/((r[1]-r[0])*(r[3]-r[2]));sum+=pi[k];s->bcell[k]=.05*pi[k];}
 check(std::abs(sum-1)<1e-12,"reference mass normalization");
 // Require the frozen row-major 3x3 partition, including exact shared edges.
 for(int row=0;row<3;++row)for(int col=0;col<3;++col){auto&r=s->rect[3*row+col];check(r[0]==s->rect[col][0]&&r[1]==s->rect[col][1]&&r[2]==s->rect[3*row][2]&&r[3]==s->rect[3*row][3],"rectangular grid");if(col)check(r[0]==s->rect[3*row+col-1][1],"shared x edge");if(row)check(r[2]==s->rect[3*(row-1)+col][3],"shared y edge");}
 s->whole={s->rect[0][0],s->rect[2][1],s->rect[0][2],s->rect[6][3]};
 for(int i=0;i<nt;++i){finite(xy[2*i],"training x");finite(xy[2*i+1],"training y");s->cell(xy[2*i],xy[2*i+1]);s->training.push_back({0,0,xy[2*i],xy[2*i+1]});s->kde.push_back(s->shape(xy[2*i],xy[2*i+1],s->p[6],false));for(int k=0;k<9;++k)s->bcell[k]+=.95*s->kde.back().prob[k]/nt;}
 for(int i=0;i<nh;++i){Event e={h[4*i],h[4*i+1],h[4*i+2],h[4*i+3]};for(int j=0;j<4;++j)finite(h[4*i+j],"prehistory value");check(e.t<s->p[9]&&(!i||e.t>=s->pre.back().e.t),"strict preorigin history");s->cell(e.x,e.y);s->pre.push_back(s->parent(e));}
 return s;
}
}
API const char* cc_last_error(){return error_text;}
API const char* cc_version(){return "ep-conditional-cluster-prototype-v1;mt19937_64;binary64;EP-unweighted-q;KDE-tail2;single-thread"
#ifdef _MSC_FULL_VER
 ";MSC_FULL_VER=" CC_STRINGIFY(_MSC_FULL_VER)
#endif
#ifdef _MSVC_STL_VERSION
 ";MSVC_STL_VERSION=" CC_STRINGIFY(_MSVC_STL_VERSION)
#endif
#ifdef _MSVC_STL_UPDATE
 ";MSVC_STL_UPDATE=" CC_STRINGIFY(_MSVC_STL_UPDATE)
#endif
#ifdef __GLIBCXX__
 ";GLIBCXX=" CC_STRINGIFY(__GLIBCXX__)
#endif
 ;}
API void* cc_create(int nh,const double*h,int nt,const double*xy,const double*bounds,const double*pi,const double*p){error_text[0]=0;try{return make_state(nh,h,nt,xy,bounds,pi,p).release();}catch(const std::exception&e){error(e.what());return nullptr;}}
API void cc_destroy(void*p){delete static_cast<State*>(p);}
API double cc_rectangle(const double*b,double x,double y,double scale){error_text[0]=0;try{check(b,"rectangle pointer");return rectangle({b[0],b[1],b[2],b[3]},x,y,scale);}catch(const std::exception&e){error(e.what());return std::numeric_limits<double>::quiet_NaN();}}
struct Simulation{std::vector<Parent>path;std::array<double,8>meta{};int status=0;char message[512]={};};
// No event/proposal cap. Resource failure/watchdog aborts the whole seed.
// Seed words: four big-endian uint32 words for each purpose, in stream order
// immigrant, prehistory-offspring, descendants, marks. Each uses seed_seq.
// meta: accepted,candidates,raw_engine_draws,processed_parents,immigrants,
// preorigin_direct,future_direct,spatial_proposals.
void* simulate(void*handle,const std::uint32_t*seeds){
 error_text[0]=0;auto result=std::unique_ptr<Simulation>(new Simulation());auto&path=result->path;std::uint64_t candidates=0,processed=0,immigrants=0,prechildren=0,futurechildren=0;
 if(!seeds){error("seed pointer");return nullptr;}Random immigrant(seeds),pre(seeds+4),desc(seeds+8),marks(seeds+12);
 try{check(handle,"simulation arguments");const auto&s=*static_cast<State*>(handle);ep_q=s.p[11];double start=s.p[9],end=s.p[10];
  auto append=[&](double t,std::array<double,2>z){
   check(t>=start&&t<end,"generated window boundary");double q=-std::log1p(-marks.u())/s.p[7];path.push_back(s.parent({t,q,z[0],z[1]}));
  };
  auto count=[&](double mean,Random&r){auto n=r.poisson(mean);check(n<=std::numeric_limits<std::uint64_t>::max()-candidates,"candidate integer overflow");candidates+=n;return n;};
  auto ni=count(s.B(start,end),immigrant);
  for(std::uint64_t k=0;k<ni;++k){double u=immigrant.u(),z=2*s.p[1]*(end-start)/s.p[8],fraction;
   // Stable exact trend inverse, including increasing/decreasing trend.
   if(z==0)fraction=u;else fraction=std::log1p(u*std::expm1(z))/z;
   double t=start+(end-start)*fraction;if(!(t<end)){result->status=4;throw std::runtime_error("immigrant chronology rounding");}append(t,sample_background(s,immigrant));++immigrants;
  }
  auto offspring=[&](const Parent&parent,bool old){Random&r=old?pre:desc;double L=std::max(start-parent.e.t,0.),U=end-parent.e.t;if(U<=L)return;double J=s.J(parent.e.t,start,end),D=(s.p[4]-1)*std::log1p((U-L)/(s.p[3]+L));auto n=count(s.p[2]*parent.kappa*J,r);
   for(std::uint64_t k=0;k<n;++k){double B=-std::log1p(r.u()*std::expm1(-D))/(s.p[4]-1);double lag=L+(s.p[3]+L)*std::expm1(B);double t=parent.e.t+lag;
    if(old)t=start+(s.p[3]+L)*std::expm1(B);
    if(!(t>parent.e.t&&t>=start&&t<end)){result->status=4;throw std::runtime_error("offspring chronology rounding");}append(t,sample_location(s,parent,r));if(old)++prechildren;else ++futurechildren;
   }++processed;
  };
  for(const auto&parent:s.pre)offspring(parent,true);
  // Copy the parent: append can reallocate path, invalidating a reference.
  for(std::size_t j=0;j<path.size();++j){Parent parent=path[j];offspring(parent,false);}
 }catch(const std::exception&e){if(!result->status)result->status=1;error(e.what());std::strncpy(result->message,e.what(),511);}
 std::stable_sort(path.begin(),path.end(),[](const Parent&a,const Parent&b){return a.e.t<b.e.t;});
 result->meta={(double)path.size(),(double)candidates,(double)(immigrant.draws+pre.draws+desc.draws+marks.draws),(double)processed,(double)immigrants,(double)prechildren,(double)futurechildren,(double)(immigrant.proposals+pre.proposals+desc.proposals)};return result.release();
}
API void* cc_simulate(void*handle,const std::uint32_t*seeds){try{return simulate(handle,seeds);}catch(const std::exception&e){error(e.what());return nullptr;}catch(...){error("unknown simulation exception");return nullptr;}}
API std::uint64_t cc_path_size(void*p){return p?static_cast<Simulation*>(p)->path.size():0;}
API int cc_path_copy(void*p,double*out,double*meta){if(!p||!meta)return 1;auto&r=*static_cast<Simulation*>(p);std::copy(r.meta.begin(),r.meta.end(),meta);for(std::size_t i=0;i<r.path.size();++i){if(!out)return 1;auto&e=r.path[i].e;out[4*i]=e.t;out[4*i+1]=e.q;out[4*i+2]=e.x;out[4*i+3]=e.y;}error(r.message);return r.status;}
API void cc_path_destroy(void*p){delete static_cast<Simulation*>(p);}

namespace {
double ks(std::vector<double>u){if(u.empty())return 0;std::sort(u.begin(),u.end());double d=0;for(std::size_t i=0;i<u.size();++i)d=std::max({d,(double)(i+1)/u.size()-u[i],u[i]-(double)i/u.size()});return d;}
// Kernel integrals for an x-then-y Rosenblatt transform: cumulative area left
// of x, vertical line density at x, and vertical line mass below y.
struct Transform{double left=0,line=0,below=0;};
Transform transform(const State&s,double x,double y,double px,double py,double scale,bool weighted,const Shape&shape){
 if(weighted){Transform z;if(x>s.whole[0])z.left=x>=s.whole[1]?shape.z:ep_rectangle({s.whole[0],x,s.whole[2],s.whole[3]},px,py,scale);z.line=(double)ep_cross(x-px,s.whole[2]-py,s.whole[3]-py,scale);if(y>s.whole[2])z.below=(double)ep_cross(x-px,s.whole[2]-py,std::min(y,s.whole[3])-py,scale);return z;}
 Transform v;int column=-1;for(int c=0;c<3;++c)if(x>=s.rect[c][0]&&x<=s.rect[c][1])column=c;check(column>=0,"transform x support");
 if(!weighted){
  if(x>s.whole[0])v.left=x>=s.whole[1]?shape.z:rectangle({s.whole[0],x,s.whole[2],s.whole[3]},px,py,scale);
  v.line=(double)cross((long double)x-px,(long double)s.whole[2]-py,(long double)s.whole[3]-py,scale);
  if(y>s.whole[2])v.below=(double)cross((long double)x-px,(long double)s.whole[2]-py,(long double)std::min(y,s.whole[3])-py,scale);
  return v;
 }
 for(int k=0;k<9;++k){const auto&b=s.rect[k];double factor=weighted?s.rho[k]:1;
  if(x>b[0]){double right=std::min(x,b[1]);if(x>=b[1])v.left+=factor*shape.mass[k];else if(right>b[0])v.left+=factor*rectangle({b[0],right,b[2],b[3]},px,py,scale);}
  if(k%3==column){v.line+=factor*(double)cross((long double)x-px,(long double)b[2]-py,(long double)b[3]-py,scale);if(y>b[2]){double top=std::min(y,b[3]);if(top>b[2])v.below+=factor*(double)cross((long double)x-px,(long double)b[2]-py,(long double)top-py,scale);}}
 }return v;
}
Transform floor_transform(const State&s,double x,double y){Transform v;int column=-1;for(int c=0;c<3;++c)if(x>=s.rect[c][0]&&x<=s.rect[c][1])column=c;
 for(int k=0;k<9;++k){auto&b=s.rect[k];v.left+=s.rho[k]*std::max(0.,std::min(x,b[1])-b[0])*(b[3]-b[2]);if(k%3==column){v.line+=s.rho[k]*(b[3]-b[2]);v.below+=s.rho[k]*std::max(0.,std::min(y,b[3])-b[2]);}}return v;}
double exposure(const State&s,const std::vector<Parent>&parents,double start,double end,std::array<double,9>*cells=nullptr){
 double B=s.B(start,end),E=B;if(cells)for(int k=0;k<9;++k)(*cells)[k]=B*s.bcell[k];
 for(const auto&parent:parents){double v=s.p[2]*parent.kappa*s.J(parent.e.t,start,end);E+=v;if(cells)for(int k=0;k<9;++k)(*cells)[k]+=v*parent.shape.prob[k];}return E;
}
void evaluate(const State&s,int ne,const double*events,const double*blocks,double*out,double*detail){
 ep_q=s.p[11];check(ne>=0&&(!ne||events)&&blocks&&out&&(!ne||detail),"evaluate arguments");std::fill(out,out+84,0);
 check(blocks[0]==s.p[9]&&blocks[5]==s.p[10],"subblock endpoints");for(int j=1;j<6;++j)check(blocks[j]>blocks[j-1],"subblock chronology");
 std::vector<Parent>parents=s.pre;std::size_t first=parents.size();
 for(int i=0;i<ne;++i){Event e={events[4*i],events[4*i+1],events[4*i+2],events[4*i+3]};for(int j=0;j<4;++j)finite(events[4*i+j],"event value");check(e.t>=s.p[9]&&e.t<s.p[10]&&(!i||e.t>=events[4*(i-1)]),"event chronology/window");s.cell(e.x,e.y);parents.push_back(s.parent(e));}
 std::array<double,9>cellE{},cellN{},cellP{};double E=exposure(s,parents,s.p[9],s.p[10],&cellE),B=s.B(s.p[9],s.p[10]);
 std::vector<double>gapU,ux,uy,ell;double sumg=0,pointSum=0,groundSum=0,zoneSum=0,cellSum=0,markSum=0,serial=0,crosssum=0,wmax=0,wsum=0;double area=(s.whole[1]-s.whole[0])*(s.whole[3]-s.whole[2]);
 for(int i=0;i<ne;++i){const auto&e=parents[first+i].e;int cell=s.cell(e.x,e.y);++cellN[cell];int block=0;while(block<4&&e.t>=blocks[block+1])++block;++out[24+block];
  double mu=s.mu(e.t),ground=mu,point=mu*s.background(e.x,e.y);std::array<double,9>cells;for(int k=0;k<9;++k)cells[k]=mu*s.bcell[k];
  Transform f=floor_transform(s,e.x,e.y);f.left*=mu*.05;f.line*=mu*.05;f.below*=mu*.05;
  for(std::size_t j=0;j<s.training.size();++j){auto tr=transform(s,e.x,e.y,s.training[j].x,s.training[j].y,s.p[6],false,s.kde[j]);double v=mu*.95/s.training.size()/s.kde[j].z;f.left+=v*tr.left;f.line+=v*tr.line;f.below+=v*tr.below;}
  for(std::size_t j=0;j<first+(std::size_t)i;++j){const auto&parent=parents[j];if(parent.e.t>=e.t)continue;double v=s.p[2]*parent.kappa*s.g(e.t-parent.e.t);ground+=v;point+=v*ep_kernel(e.x,e.y,parent.e.x,parent.e.y,s.p[5])/parent.shape.z;for(int k=0;k<9;++k)cells[k]+=v*parent.shape.prob[k];
   if(v>0){auto tr=transform(s,e.x,e.y,parent.e.x,parent.e.y,s.p[5],true,parent.shape);v/=parent.shape.z;f.left+=v*tr.left;f.line+=v*tr.line;f.below+=v*tr.below;}
  }
  check(ground>0&&point>0&&f.line>0,"positive evaluated intensity");finite(ground,"ground overflow");finite(point,"point overflow");
  double Ux=f.left/ground,Uy=f.below/f.line;check(Ux>=-1e-10&&Ux<=1+1e-10&&Uy>=-1e-10&&Uy<=1+1e-10,"Rosenblatt probability range");
  // Preserve numerical transform values; tolerance violations fail above.
  ux.push_back(Ux);uy.push_back(Uy);crosssum+=(Ux-.5)*(Uy-.5);
  for(int k=0;k<9;++k)cellP[k]+=cells[k]/ground;
  double zone=0;for(int k=(cell/3)*3;k<(cell/3)*3+3;++k)zone+=cells[k];
  double lg=std::log(ground),lp=std::log(point),lc=std::log(cells[cell]),lz=std::log(zone),lm=std::log(s.p[7])-s.p[7]*e.q;
  groundSum+=lg;pointSum+=lp;cellSum+=lc;zoneSum+=lz;markSum+=lm;
  double dim=lp-lg+std::log(area),A=(s.rect[cell][1]-s.rect[cell][0])*(s.rect[cell][3]-s.rect[cell][2]),w=lp-lc+std::log(A);ell.push_back(dim);wmax=std::max(wmax,std::abs(w));wsum+=w;
  double previous=i?parents[first+i-1].e.t:s.p[9],gap=0;
  if(e.t>previous)gap=exposure(s,parents,previous,e.t);sumg+=gap;double U=-std::expm1(-gap);gapU.push_back(U);if(i)serial+=(U-.5)*(gapU[i-1]-.5);
  // Local detailed rows: gap, U_gap, Ux, Uy, logground, logpoint,
  // logcell, logzone, logmark, dimensionless_location, dimensionless_within.
  double vals[11]={gap,U,Ux,Uy,lg,lp,lc,lz,lm,dim,w};std::copy(vals,vals+11,detail+11*i);
 }
 double tail=exposure(s,parents,ne?parents.back().e.t:s.p[9],s.p[10]);
 check(std::abs(sumg+tail-E)<=1e-10*std::max(1.,E),"gap plus censored exposure conservation");
 double cellEsum=0,cellPsum=0;for(int k=0;k<9;++k){cellEsum+=cellE[k];cellPsum+=cellP[k];out[39+k]=cellN[k];out[48+k]=cellP[k];out[57+k]=cellE[k];out[66+k]=cellN[k]-cellP[k];out[75+k]=cellN[k]-cellE[k];out[19]=std::max(out[19],std::abs(cellN[k]-cellP[k])/(1+cellP[k]));}
 check(std::abs(cellEsum-E)<=1e-10*std::max(1.,E)&&std::abs(cellPsum-ne)<=1e-10*std::max(1,ne),"cell exposure/allocation conservation");
 double yearE=0;for(int j=0;j<5;++j){out[29+j]=exposure(s,parents,blocks[j],blocks[j+1]);out[34+j]=out[24+j]-out[29+j];out[13]=std::max(out[13],std::abs(out[34+j])/(1+out[29+j]));yearE+=out[29+j];}check(std::abs(yearE-E)<=1e-10*std::max(1.,E),"subblock exposure conservation");
 out[0]=ne;out[1]=E;out[2]=B;out[3]=E-B;out[4]=ne-E;out[5]=groundSum;out[6]=groundSum-E;out[7]=pointSum-groundSum;out[8]=markSum;out[9]=pointSum-E+markSum;out[10]=zoneSum-groundSum;out[11]=cellSum-zoneSum;out[12]=pointSum-cellSum;out[14]=ks(gapU);out[15]=ne>1?serial/(ne-1):0;out[16]=tail;out[17]=std::max(ks(ux),ks(uy));out[18]=ne?std::abs(crosssum/ne):0;out[22]=wmax;out[23]=wsum;
 if(ne){double mean=0;for(auto v:ell)mean+=v;mean/=ne;out[20]=mean;double variance=0;for(auto v:ell)variance+=(v-mean)*(v-mean);out[21]=variance/ne;}
 for(int k=0;k<84;++k)finite(out[k],"nonfinite diagnostic");
}
}
// out: fixed 24 scalar, 3x5 year arrays, 5x9 cell arrays = 84 doubles.
// detail is local-only (N,11); see evaluated row declaration above.
API int cc_evaluate(void*h,int n,const double*events,const double*blocks,double*out,double*detail){error_text[0]=0;try{check(h,"evaluate state");evaluate(*static_cast<State*>(h),n,events,blocks,out,detail);return 0;}catch(const std::exception&e){error(e.what());return 1;}}
API double cc_uniform_from_word(std::uint64_t word){return ((word>>12)+.5)*0x1.0p-52;}

// Engineering normalization probe; inputs are scalar geometry, no private rows.
API double cc_ep_rectangle(const double*b,double x,double y,double scale,double q){error_text[0]=0;try{check(b&&q>1&&std::isfinite(q)&&scale>0,"EP rectangle probe domain");ep_q=q;return ep_rectangle({b[0],b[1],b[2],b[3]},x,y,scale);}catch(const std::exception&e){error(e.what());return std::numeric_limits<double>::quiet_NaN();}}
