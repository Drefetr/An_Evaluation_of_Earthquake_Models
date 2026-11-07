// Combined continuous spatial / temporal model. Single threaded, analytic derivatives.
#include <cmath>
#include <vector>
#include <stdexcept>
#include <limits>
#include <cstddef>
#include <algorithm>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C" __attribute__((visibility("default")))
#endif
namespace {
thread_local char err[512]={};void fail(const char*s){std::size_t i=0;for(;s[i]&&i<511;++i)err[i]=s[i];err[i]='\0';}
void check(bool x,const char*s){if(!x)throw std::runtime_error(s);}void finite(double x,const char*s){check(std::isfinite(x),s);}
std::vector<double> cp(const double*p,std::size_t n,bool positive=false){check(p||!n,"null feature");std::vector<double>v;if(n)v.assign(p,p+n);for(double x:v){finite(x,"nonfinite feature");if(positive)check(x>=0,"negative feature");}return v;}
// Copied from sealed continuous_location/objective.cpp; not linked to its DLL.
long double angle(long double lo,long double hi,long double scale){return std::atan2(scale*(hi-lo),scale*scale+hi*lo);}
long double rectangle(long double xl,long double xh,long double yl,long double yh,long double sigma){long double ss=sigma*sigma;auto fx=[&](long double x){long double s=std::sqrt(ss+x*x);return x/s*angle(yl,yh,s);};auto fy=[&](long double y){long double s=std::sqrt(ss+y*y);return y/s*angle(xl,xh,s);};return ss/2*(fx(xh)-fx(xl)+fy(yh)-fy(yl));}
struct Temporal {bool valid=false;int model=-1;double l=0,p=0;std::vector<double>hp,hc,dhp,dhc,ehp,ehc,K,dK,eK;};
struct F {int ne,np,nm,first;double start,end,T,marks;std::vector<double>t,x,cell,b,bmass,spatial,W,kappa,lo,hi,weights,rates;Temporal fixed,dynamic;};
struct B {double b,bd;};
B background(const F&f,double a,double d){double center=(f.start+f.end)/f.T-1,half=(f.end-f.start)/f.T,z=d*half,s,cor;if(std::abs(z)<1e-4){double zz=z*z;s=1+zz/6+zz*zz/120+zz*zz*zz/5040;cor=half*(z/3-z*zz/45+2*z*zz*zz/945);}else{s=std::sinh(z)/z;cor=half*(1/std::tanh(z)-1/z);}double b=std::exp(a+d*center)*(f.end-f.start)*s;finite(b,"background overflow");return{b,b*(center+cor)};}
double add(double a,double b){if(a==-std::numeric_limits<double>::infinity())return b;if(b==-std::numeric_limits<double>::infinity())return a;double hi=std::max(a,b),lo=std::min(a,b);return hi+std::log1p(std::exp(lo-hi));}
Temporal& temporal(F&f,int model,double l,double p){Temporal&c=model==0?f.fixed:f.dynamic;if(c.valid&&c.model==model&&c.l==l&&c.p==p)return c;
 c=Temporal();c.model=model;c.l=l;c.p=p;c.hp.assign(f.ne,0);c.hc.assign(9*f.ne,0);c.dhp.assign(f.ne,0);c.dhc.assign(9*f.ne,0);c.ehp.assign(f.ne,0);c.ehc.assign(9*f.ne,0);c.K.assign(9,0);c.dK.assign(9,0);c.eK.assign(9,0);
 std::vector<double>density(static_cast<std::size_t>(f.ne)*f.np,0),derivative(density.size(),0),extra(density.size(),0),J(f.np,0),dJ(f.np,0),eJ(f.np,0);
 if(model<2){double tau=std::exp(l);std::vector<double>step(f.np);
  // Modal exponentials for consecutive history gaps avoid O(195*N^2) exp calls.
  for(int m=0;m<f.nm;++m){double r=f.rates[m]/tau,wr=f.weights[m]*r;for(int k=1;k<f.np;++k)step[k]=std::exp(-r*(f.t[k]-f.t[k-1]));
   for(int j=0;j<f.np;++j){double zlo=r*f.lo[j],zw=r*(f.hi[j]-f.lo[j]),el=std::exp(-zlo),ew=std::exp(-zw),one=-std::expm1(-zw),mass=f.weights[m]*el;J[j]+=mass*one;dJ[j]+=mass*(zlo*one-zw*ew);}
   // Target-major rows make each modal pass contiguous. The positive mixture
   // is unchanged: propagate exact consecutive-gap exponentials backwards
   // through every parent; retain ties as zero-lag, noncausal contributions.
   for(int k=f.first;k<f.np;++k){double v=wr;std::size_t row=static_cast<std::size_t>(k-f.first)*f.np;
    for(int j=k-1;j>=0;--j){v*=step[j+1];if(v==0)break;if(f.t[k]>f.t[j]){std::size_t ix=row+j;density[ix]+=v;derivative[ix]+=v*(r*(f.t[k]-f.t[j])-1);}}
   }
  }
 }else{double cc=std::exp(l),pm=p-1;
  for(int j=0;j<f.np;++j){double L=f.lo[j],U=f.hi[j],vL=std::log1p(L/cc),delta=std::log1p((U-L)/(cc+L)),vU=vL+delta,S=std::exp(-pm*vL),width=pm*delta,one=-std::expm1(-width);J[j]=S*one;
   double gU=pm*U/(cc+U),dg=-pm*cc*(U-L)/((cc+L)*(cc+U));dJ[j]=S*(dg+gU*one);eJ[j]=S*(delta-vU*one);
   for(int k=std::max(j+1,f.first);k<f.np;++k){double lag=f.t[k]-f.t[j];if(lag<=0)continue;double vlog=std::log1p(lag/cc),v=pm/cc*std::exp(-p*vlog);std::size_t ix=static_cast<std::size_t>(k-f.first)*f.np+j;density[ix]=v;derivative[ix]=v*(-1+p*lag/(cc+lag));extra[ix]=v*(1/pm-vlog);}
  }
 }
 for(int j=0;j<f.np;++j){for(int z=0;z<9;++z){double scale=f.kappa[j]*f.W[9*j+z];c.K[z]+=J[j]*scale;c.dK[z]+=dJ[j]*scale;c.eK[z]+=eJ[j]*scale;}}
 for(int i=0;i<f.ne;++i)for(int j=0;j<i+f.first;++j){std::size_t ix=static_cast<std::size_t>(i)*f.np+j;double h=density[ix]*f.kappa[j],dh=derivative[ix]*f.kappa[j],eh=extra[ix]*f.kappa[j];c.hp[i]+=h*f.spatial[ix];c.dhp[i]+=dh*f.spatial[ix];c.ehp[i]+=eh*f.spatial[ix];for(int z=0;z<9;++z){double w=f.W[9*j+z];c.hc[9*i+z]+=h*w;c.dhc[9*i+z]+=dh*w;c.ehc[9*i+z]+=eh*w;}}
 c.valid=true;return c;
}
void eval(F&f,int model,const double*p,int dim,double*out,double*grad,double*logs){int dims[3]={3,4,5};check(model>=0&&model<3&&dim==dims[model],"model dimension");for(int j=0;j<dim;++j)finite(p[j],"parameter");double a=p[0],d=p[1],n=p[2],l=model?p[3]:0,pp=model==2?p[4]:0;check(a>=-12&&a<=0&&d>=-2&&d<=2&&n>=0&&n<=.98,"base bounds");if(model==1)check(l>=std::log(.001)&&l<=std::log(20.),"tau bounds");if(model==2)check(l>=std::log(.0001)&&l<=std::log(20.)&&pp>=1.01&&pp<=2.5,"Omori bounds");
 auto&c=temporal(f,model,l,pp);auto bg=background(f,a,d);double comp=0,K=0,dK=0,eK=0;for(int z=0;z<9;++z){out[10+z]=bg.b*f.bmass[z]+n*c.K[z];comp+=out[10+z];K+=c.K[z];dK+=c.dK[z];eK+=c.eK[z];out[19+z]=0;}
 double point=0,cell=0,zone=0,ground=0,sa=0,sd=0,sn=0,sl=0,sp=0;
 for(int i=0;i<f.ne;++i){int z=static_cast<int>(f.cell[i]);double mu=std::exp(a+d*f.x[i]),lb=std::log(f.b[i])+a+d*f.x[i],lh=n>0&&c.hp[i]>0?std::log(n)+std::log(c.hp[i]):-std::numeric_limits<double>::infinity(),lp=add(lb,lh),lc[9],lz[3]={0,0,0},lg=0;
  for(int k=0;k<9;++k){lc[k]=mu*f.bmass[k]+n*c.hc[9*i+k];check(lc[k]>0,"cell intensity");lz[k/3]+=lc[k];lg+=lc[k];}
  double frac=std::exp(lb-lp),inv=std::exp(-lp);point+=lp;cell+=std::log(lc[z]);zone+=std::log(lz[z/3]);ground+=std::log(lg);out[19+z]+=lp;sa+=frac;sd+=f.x[i]*frac;sn+=c.hp[i]*inv;sl+=n*c.dhp[i]*inv;sp+=n*c.ehp[i]*inv;logs[13*i]=lp;logs[13*i+1]=std::log(lc[z]);logs[13*i+2]=std::log(lz[z/3]);logs[13*i+3]=std::log(lg);for(int k=0;k<9;++k)logs[13*i+4+k]=lc[k]/lg;
 }
 out[0]=comp-point-f.marks;out[1]=ground-comp;out[2]=zone-ground;out[3]=cell-zone;out[4]=point-cell;out[5]=f.marks;out[6]=comp;out[7]=point;out[8]=ground;out[9]=K;grad[0]=bg.b-sa;grad[1]=bg.bd-sd;grad[2]=K-sn;if(model)grad[3]=n*dK-sl;if(model==2)grad[4]=n*eK-sp;for(int j=0;j<28;++j)finite(out[j],"nonfinite output");for(int j=0;j<dim;++j)finite(grad[j],"nonfinite gradient");
}
}
API int cl_rectangles(int np,int nc,const double*xy,const double*bounds,double sigma,double*out){err[0]=0;try{check(np>=0&&nc==9&&xy&&bounds&&out&&sigma>0&&std::isfinite(sigma),"rectangle arguments");for(int j=0;j<np;++j)for(int c=0;c<nc;++c){double xl=bounds[4*c],xh=bounds[4*c+1],yl=bounds[4*c+2],yh=bounds[4*c+3];check(xl<xh&&yl<yh,"rectangle orientation");double value=static_cast<double>(rectangle(static_cast<long double>(xl)-xy[2*j],static_cast<long double>(xh)-xy[2*j],static_cast<long double>(yl)-xy[2*j+1],static_cast<long double>(yh)-xy[2*j+1],sigma));check(value>0&&std::isfinite(value),"nonpositive rectangle mass");out[9*j+c]=value;}return 0;}catch(const std::exception&e){fail(e.what());return 1;}catch(...){fail("rectangle error");return 1;}}
API void* ts_create(int ne,int np,int nm,const double*t,const double*x,const double*cell,const double*b,const double*bmass,const double*spatial,const double*W,const double*kappa,const double*lo,const double*hi,const double*weights,const double*rates,const double*meta){err[0]=0;try{check(ne>=0&&np>=ne&&nm==195&&meta,"dimensions");for(int i=0;i<4;++i)finite(meta[i],"metadata");check(meta[0]>=0&&meta[1]>meta[0]&&meta[2]>0,"window");F f{ne,np,nm,np-ne,meta[0],meta[1],meta[2],meta[3],cp(t,np),cp(x,ne),cp(cell,ne),cp(b,ne,true),cp(bmass,9,true),cp(spatial,static_cast<std::size_t>(ne)*np,true),cp(W,static_cast<std::size_t>(np)*9,true),cp(kappa,np,true),cp(lo,np,true),cp(hi,np,true),cp(weights,nm,true),cp(rates,nm,true)};
 double mass=0;for(double v:f.bmass){check(v>0,"background mass");mass+=v;}check(std::abs(mass-1)<1e-12,"background normalization");mass=0;for(int m=0;m<nm;++m){check(f.rates[m]>0,"mixture rate");mass+=f.weights[m];}check(std::abs(mass-1)<1e-12,"mixture mass");for(double v:f.b)check(v>0,"background density");for(double v:f.cell)check(v>=0&&v<9&&v==std::floor(v),"event cell");for(int j=0;j<np;++j){check(f.t[j]<f.end&&(!j||f.t[j]>=f.t[j-1]),"parent chronology");check((j<f.first)==(f.t[j]<f.start),"event suffix");double sum=0;for(int k=0;k<9;++k)sum+=f.W[9*j+k];check(std::abs(sum-1)<1e-12,"trigger mass");}return new F(std::move(f));}catch(const std::exception&e){fail(e.what());return nullptr;}catch(...){fail("create error");return nullptr;}}
API int ts_eval(void*h,int model,const double*p,int dim,double*out,double*grad,double*logs){err[0]=0;try{check(h&&p&&out&&grad&&logs,"null pointer");eval(*static_cast<F*>(h),model,p,dim,out,grad,logs);return 0;}catch(const std::exception&e){fail(e.what());return 1;}catch(...){fail("eval error");return 1;}}
API void ts_destroy(void*h){delete static_cast<F*>(h);}API const char* ts_last_error(){return err;}
API const char* cl_last_error(){return err;}
