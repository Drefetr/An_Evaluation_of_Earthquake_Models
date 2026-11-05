// Independent radial ETAS and optimized no-trigger likelihood. Single threaded.
// All coordinates are equal-area projected km; times are days.
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif

namespace {
thread_local char error_text[256] = {};
void fail(const char* s) { std::size_t i=0; for (; s[i] && i<255; ++i) error_text[i]=s[i]; error_text[i]=0; }
void require(bool ok,const char* s) { if (!ok) throw std::runtime_error(s); }
void finite(double x,const char* s) { require(std::isfinite(x),s); }
std::vector<double> copy(const double* p,std::size_t n) {
  require(p || n==0,"null feature"); std::vector<double> a;
  if(n) a.assign(p,p+n); for(double x:a) finite(x,"nonfinite feature"); return a;
}
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
  require(depth<18,"edge quadrature depth");
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
  require(depth<8,"area quadrature depth");
  double xm=(xl+xh)/2,ym=(yl+yh)/2;
  return area_fallback(xl,xm,yl,ym,ell,q,depth+1)+area_fallback(xm,xh,yl,ym,ell,q,depth+1)
       +area_fallback(xl,xm,ym,yh,ell,q,depth+1)+area_fallback(xm,xh,ym,yh,ell,q,depth+1);
}
Triple rectangle(const double* rect,double px,double py,double ell,double q) {
  double xl=rect[0]-px,xh=rect[1]-px,yl=rect[2]-py,yh=rect[3]-py;
  require(xl<xh && yl<yh,"rectangle orientation");
  finite(xl,"rectangle coordinate");finite(xh,"rectangle coordinate");finite(yl,"rectangle coordinate");finite(yh,"rectangle coordinate");
  Triple top=edge(yh,xl,xh,ell,q),bottom=edge(yl,xl,xh,ell,q),right=edge(xh,yl,yh,ell,q),left=edge(xl,yl,yh,ell,q);
  Triple z=top-bottom+right-left;
  double cancellation=std::abs(top.v)+std::abs(bottom.v)+std::abs(right.v)+std::abs(left.v);
  if(z.v<=0 || z.v<1e-3*cancellation)z=area_fallback(xl,xh,yl,yh,ell,q);
  double sign_tol=1e-9*std::max(std::abs(z.v),1e-14);
  if(z.ds< -sign_tol || z.dq>sign_tol)z=area_fallback(xl,xh,yl,yh,ell,q);
  require(z.v>0 && std::isfinite(z.v) && std::isfinite(z.ds) && std::isfinite(z.dq),"rectangle mass");
  sign_tol=1e-9*std::max(std::abs(z.v),1e-14);
  require(z.ds>=-sign_tol && z.dq<=sign_tol,"rectangle derivative sign");
  return z;
}
struct Background { double mass,dd; };
Background background(double a,double d,double start,double end,double T) {
  double center=(start+end)/T-1,half=(end-start)/T,z=d*half,s,cor;
  if(std::abs(z)<1e-4){double zz=z*z;s=1+zz/6+zz*zz/120+zz*zz*zz/5040;cor=half*(z/3-z*zz/45+2*z*zz*zz/945);}
  else{s=std::sinh(z)/z;cor=half*(1/std::tanh(z)-1/z);}
  double b=std::exp(a+d*center)*(end-start)*s;finite(b,"background overflow");return {b,b*(center+cor)};
}
struct Handle {
  int ne,np;double start,end,T,marks;
  std::vector<double> pt,pxy,kappa,lo,hi,et,exy,ex,cell,b,bmass,rect;
};
struct Time { double density,dc,dp,mass,mc,mp; };
Time temporal(double lag,double lo,double hi,double c,double p) {
  double pm=p-1,v=std::log1p(lag/c),density=pm/c*std::exp(-p*v);
  double L=std::log1p(lo/c),D=std::log1p((hi-lo)/(c+lo)),U=L+D,S=std::exp(-pm*L),w=pm*D,one=-std::expm1(-w);
  double mass=S*one;
  // d/dlog(c) [S(L)-S(U)] = S(L)g(L)-S(U)g(U), g(u)=(p-1)u/(c+u).
  double mc=S*(pm*lo/(c+lo)*one-pm*c*(hi-lo)/((c+lo)*(c+hi))*std::exp(-w));
  double mp=S*(D-U*one);
  return {density,density*(-1+p*lag/(c+lag)),density*(1/pm-v),mass,mc,mp};
}
void evaluate(const Handle& h,int model,const double* par,int dim,double* out,double* grad,double* logs) {
  require((model==0&&dim==2)||(model==1&&dim==7),"model dimension");
  for(int k=0;k<dim;++k)finite(par[k],"nonfinite parameter");
  double a=par[0],d=par[1],n=model?par[2]:0,c=model?std::exp(par[3]):1,p=model?par[4]:2,ell=model?std::exp(par[5]):1,q=model?par[6]:2;
  require(a>=-12&&a<=0&&d>=-2&&d<=2,"background bounds");
  if(model)require(n>=0&&n<=.98&&c>=.0001*(1-1e-12)&&c<=20*(1+1e-12)&&p>=1.01&&p<=2.5&&ell>=2*(1-1e-12)&&ell<=500*(1+1e-12)&&q>=1.05&&q<=3,"ETAS bounds");
  for(int k=0;k<28;++k)out[k]=0;for(int k=0;k<dim;++k)grad[k]=0;
  bool detail=logs!=nullptr;
  auto bg=background(a,d,h.start,h.end,h.T);
  double whole[4]={h.rect[0],h.rect[1],h.rect[2],h.rect[3]};
  for(int k=1;k<9;++k){whole[0]=std::min(whole[0],h.rect[4*k]);whole[1]=std::max(whole[1],h.rect[4*k+1]);whole[2]=std::min(whole[2],h.rect[4*k+2]);whole[3]=std::max(whole[3],h.rect[4*k+3]);}
  std::vector<Triple> z;if(model){z.resize(h.np);for(int j=0;j<h.np;++j)z[j]=rectangle(whole,h.pxy[2*j],h.pxy[2*j+1],ell,q);}
  double K=0,Kc=0,Kp=0;
  if(model)for(int j=0;j<h.np;++j){Time tm=temporal(1,h.lo[j],h.hi[j],c,p);K+=h.kappa[j]*tm.mass;Kc+=h.kappa[j]*tm.mc;Kp+=h.kappa[j]*tm.mp;}
  double exposure=bg.mass+n*K,point=0,ground=0,cell=0,zone=0,sa=0,sd=0,sn=0,sc=0,sp=0,ss=0,sq=0;
  std::vector<double> cellmass;if(detail&&n>0){cellmass.resize(std::size_t(h.np)*9);for(int j=0;j<h.np;++j){double total=0;for(int k=0;k<9;++k){Triple t=rectangle(h.rect.data()+4*k,h.pxy[2*j],h.pxy[2*j+1],ell,q);cellmass[9*j+k]=t.v/z[j].v;total+=cellmass[9*j+k];}require(std::abs(total-1)<1e-8,"cell mass sum");}}
  for(int i=0;i<h.ne;++i){double time=h.et[i],mu=std::exp(a+d*h.ex[i]),bp=mu*h.b[i],trigger=0,trigger_ground=0,tc=0,tp=0,ts=0,tq=0,cm[9]={};
    if(detail)for(int k=0;k<9;++k)cm[k]=mu*h.bmass[k];
    if(model)for(int j=0;j<h.np;++j){double lag=time-h.pt[j];if(lag<=0)continue;
      Time tm=temporal(lag,h.lo[j],h.hi[j],c,p);double dx=h.exy[2*i]-h.pxy[2*j],dy=h.exy[2*i+1]-h.pxy[2*j+1],u=(dx*dx+dy*dy)/(ell*ell);
      double spatial_log=std::log1p(u),temporal_log=std::log1p(lag/c);
      double w=h.kappa[j]*tm.density*std::exp(-q*spatial_log)/z[j].v;
      trigger+=w;trigger_ground+=h.kappa[j]*tm.density;
      tc+=w*(-1+p*lag/(c+lag));tp+=w*(1/(p-1)-temporal_log);
      ts+=w*(2*q*u/(1+u)-z[j].ds/z[j].v);tq+=w*(-spatial_log-z[j].dq/z[j].v);
      if(detail&&n>0){double base=n*h.kappa[j]*tm.density;for(int k=0;k<9;++k)cm[k]+=base*cellmass[9*j+k];}
    }
    double intensity=bp+n*trigger,ground_i=mu+n*trigger_ground; // normalized spatial offspring
    require(intensity>0&&ground_i>0,"positive intensity");
    point+=std::log(intensity);ground+=std::log(ground_i);double inv=1/intensity;
    sa+=bp*inv;sd+=h.ex[i]*bp*inv;sn+=trigger*inv;sc+=n*tc*inv;sp+=n*tp*inv;ss+=n*ts*inv;sq+=n*tq*inv;
    if(detail){int k=int(h.cell[i]),g=k/3;double cz=cm[3*g]+cm[3*g+1]+cm[3*g+2];require(cm[k]>0&&cz>0,"cell intensity");
      cell+=std::log(cm[k]);zone+=std::log(cz);out[19+k]+=std::log(intensity);
      logs[4*i]=std::log(intensity);logs[4*i+1]=std::log(cm[k]);logs[4*i+2]=std::log(cz);logs[4*i+3]=std::log(ground_i);
    }
  }
  out[0]=exposure-point-h.marks;out[5]=h.marks;out[6]=exposure;out[7]=point;out[8]=ground;out[9]=K;
  out[1]=ground-exposure;out[2]=point-ground;
  if(detail){out[2]=zone-ground;out[3]=cell-zone;out[4]=point-cell;
    for(int k=0;k<9;++k)out[10+k]=bg.mass*h.bmass[k];
    if(n>0)for(int j=0;j<h.np;++j){Time tm=temporal(1,h.lo[j],h.hi[j],c,p);for(int k=0;k<9;++k)out[10+k]+=n*h.kappa[j]*tm.mass*cellmass[9*j+k];}
  }
  grad[0]=bg.mass-sa;grad[1]=bg.dd-sd;
  if(model){grad[2]=K-sn;grad[3]=n*Kc-sc;grad[4]=n*Kp-sp;grad[5]=-ss;grad[6]=-sq;}
  for(int k=0;k<dim;++k)finite(grad[k],"nonfinite gradient");finite(out[0],"nonfinite objective");
}
}

API void* cb_create(int ne,int np,const double* pt,const double* pxy,const double* kappa,const double* lo,const double* hi,const double* et,const double* exy,const double* ex,const double* cell,const double* b,const double* bmass,const double* rect,const double* meta) {
  error_text[0]=0;try{require(ne>=0&&np>=0&&meta,"dimensions");for(int k=0;k<4;++k)finite(meta[k],"nonfinite metadata");Handle h{ne,np,meta[0],meta[1],meta[2],meta[3],copy(pt,np),copy(pxy,2*std::size_t(np)),copy(kappa,np),copy(lo,np),copy(hi,np),copy(et,ne),copy(exy,2*std::size_t(ne)),copy(ex,ne),copy(cell,ne),copy(b,ne),copy(bmass,9),copy(rect,36)};
    require(h.start>=0&&h.end>h.start&&h.T>0,"window");double mass=0;for(double v:h.bmass){require(v>0,"background mass");mass+=v;}require(std::abs(mass-1)<1e-12,"background normalization");
    for(int j=0;j<np;++j){require(h.pt[j]<h.end&&(!j||h.pt[j]>=h.pt[j-1]),"parent chronology");require(h.kappa[j]>=0&&h.lo[j]>=0&&h.hi[j]>h.lo[j],"parent features");
      require(h.lo[j]==std::max(h.start-h.pt[j],0.)&&h.hi[j]==h.end-h.pt[j],"parent exposure window");}
    // Nine row-major rectangles must form one gap-free, overlap-free box.
    for(int k=0;k<9;++k){const double* r=h.rect.data()+4*k;require(r[0]<r[1]&&r[2]<r[3],"cell rectangle orientation");}
    for(int row=0;row<3;++row)for(int col=0;col<3;++col){int k=3*row+col;const double* r=h.rect.data()+4*k;
      if(col){const double* left=h.rect.data()+4*(k-1);require(r[0]==left[1]&&r[2]==left[2]&&r[3]==left[3],"horizontal cell tiling");}
      if(row){const double* below=h.rect.data()+4*(k-3);require(r[2]==below[3]&&r[0]==below[0]&&r[1]==below[1],"vertical cell tiling");}}
    for(int i=0;i<ne;++i){require(h.et[i]>=h.start&&h.et[i]<h.end&&(!i||h.et[i]>=h.et[i-1]),"target chronology");require(h.cell[i]>=0&&h.cell[i]<9&&h.cell[i]==std::floor(h.cell[i])&&h.b[i]>0,"target features");require(std::abs(h.ex[i]-(2*h.et[i]/h.T-1))<1e-12,"target trend");}
    return new Handle(std::move(h));}catch(const std::exception& e){fail(e.what());return nullptr;}catch(...){fail("create error");return nullptr;}
}
API int cb_eval(void* handle,int model,const double* par,int dim,double* out,double* grad,double* logs) {
  error_text[0]=0;fine_order=false;try{require(handle&&par&&out&&grad,"null pointer");evaluate(*static_cast<Handle*>(handle),model,par,dim,out,grad,logs);return 0;}catch(const std::exception& e){fail(e.what());return 1;}catch(...){fail("evaluation error");return 1;}
}
API int cb_eval_fine(void* handle,int model,const double* par,int dim,double* out,double* grad,double* logs) {
  error_text[0]=0;fine_order=true;try{require(handle&&par&&out&&grad,"null pointer");evaluate(*static_cast<Handle*>(handle),model,par,dim,out,grad,logs);fine_order=false;return 0;}catch(const std::exception& e){fine_order=false;fail(e.what());return 1;}catch(...){fine_order=false;fail("fine evaluation error");return 1;}
}
API void cb_destroy(void* handle){delete static_cast<Handle*>(handle);}
API const char* cb_last_error(){return error_text;}
API int cb_rectangle(const double* rect,double px,double py,double ell,double q,double* out){error_text[0]=0;try{require(rect&&out,"rectangle args");finite(px,"rectangle parent x");finite(py,"rectangle parent y");finite(ell,"rectangle scale");finite(q,"rectangle tail");
    require(ell>=2&&ell<=500&&q>=1.05&&q<=3,"rectangle parameter bounds");Triple x=rectangle(rect,px,py,ell,q);out[0]=x.v;out[1]=x.ds;out[2]=x.dq;return 0;}catch(const std::exception& e){fail(e.what());return 1;}}
