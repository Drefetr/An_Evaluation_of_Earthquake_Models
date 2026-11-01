#pragma once
// Prospective FP64 building blocks. Callers own quadrature, chronology and units.
#include <cmath>
#include <vector>
#include <stdexcept>
#include <limits>
namespace remediation {
inline void require(bool yes,const char* why){if(!yes)throw std::invalid_argument(why);}
inline void nonnegative(double x){require(std::isfinite(x)&&x>=0,"invalid nonnegative input");}
inline double kernel(double r2,double scale,double q=2){
 nonnegative(r2);require(std::isfinite(scale)&&scale>0&&std::isfinite(q)&&q>1,"kernel domain");
 return std::exp(-q*std::log1p(r2/(scale*scale)));
}
// Finite-domain normalization: masses are integrals of the SAME unnormalized
// radial kernel over each disjoint cell. Reference density is optional.
inline std::vector<double> cell_probabilities(const std::vector<double>& mass,const std::vector<double>& reference={}){
 require(reference.empty()||reference.size()==mass.size(),"reference shape");
 std::vector<double> p(mass.size());double z=0;
 for(std::size_t k=0;k<mass.size();++k){nonnegative(mass[k]);double b=reference.empty()?1:reference[k];nonnegative(b);p[k]=mass[k]*b;z+=p[k];}
 require(std::isfinite(z)&&z>0,"zero spatial normalizer");for(double& x:p)x/=z;return p;
}
inline double rupture_scale(double base,double alpha,double excess){
 require(std::isfinite(base)&&base>0&&std::isfinite(alpha)&&std::isfinite(excess),"rupture domain");
 double s=base*std::exp(alpha*excess);require(std::isfinite(s)&&s>0,"rupture overflow");return s;
}
struct Parent {double time,x,y,excess;};
struct StressGradient {double value=0,dell=0,dpsi=0,dalpha=0;};
inline StressGradient stress_gradient(double time,double x,double y,const std::vector<Parent>& parents,double ell0,double alpha_ell,double psi,double qref){
 require(std::isfinite(time)&&std::isfinite(x)&&std::isfinite(y)&&std::isfinite(psi)&&psi>0&&std::isfinite(qref),"stress domain");
 StressGradient sum;const double gamma=.75*std::log(10.);
 for(const auto& p:parents){require(std::isfinite(p.time)&&std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.excess),"parent domain");if(p.time>=time)continue;
  double scale=rupture_scale(ell0,alpha_ell,p.excess),dx=x-p.x,dy=y-p.y,r2=dx*dx+dy*dy;
  double v=std::exp(gamma*(p.excess-qref)-(time-p.time)/psi)*kernel(r2,scale);
  double logscale=4*r2/(scale*scale+r2);
  sum.value+=v;sum.dell+=v*logscale/ell0;sum.dalpha+=v*logscale*p.excess;sum.dpsi+=v*(time-p.time)/(psi*psi);
 }for(double v:{sum.value,sum.dell,sum.dpsi,sum.dalpha})require(std::isfinite(v),"stress gradient overflow");return sum;
}
inline double stress(double time,double x,double y,const std::vector<Parent>& parents,double ell0,double alpha_ell,double psi,double qref){
 require(std::isfinite(time)&&std::isfinite(x)&&std::isfinite(y)&&std::isfinite(psi)&&psi>0&&std::isfinite(qref),"stress domain");
 double sum=0;const double gamma=.75*std::log(10.);
 for(const auto& p:parents){require(std::isfinite(p.time)&&std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.excess),"parent domain");if(p.time>=time)continue;
  double scale=rupture_scale(ell0,alpha_ell,p.excess),dx=x-p.x,dy=y-p.y;
  sum+=std::exp(gamma*(p.excess-qref)-(time-p.time)/psi)*kernel(dx*dx+dy*dy,scale);
 }require(std::isfinite(sum),"stress overflow");return sum;
}
struct Intensity {double value,d_eta_bg,d_eta_trigger;};
// mode mapping: immigrant-only (eta,0), inclusive (eta,eta), split (eta_bg,eta_trig).
inline Intensity intensity(double B,double H,double G,double eta_bg,double eta_trig){
 for(double x:{B,H,G,eta_bg,eta_trig})nonnegative(x);
 double b=B*std::exp(-eta_bg*G),h=H*std::exp(-eta_trig*G);
 return {b+h,-G*b,-G*h};
}
struct Node {double weight,B,H,G;};
inline Intensity compensator(const std::vector<Node>& nodes,double eb,double et){
 Intensity total{0,0,0};for(auto n:nodes){nonnegative(n.weight);auto v=intensity(n.B,n.H,n.G,eb,et);total.value+=n.weight*v.value;total.d_eta_bg+=n.weight*v.d_eta_bg;total.d_eta_trigger+=n.weight*v.d_eta_trigger;}
 require(std::isfinite(total.value)&&std::isfinite(total.d_eta_bg)&&std::isfinite(total.d_eta_trigger),"compensator overflow");return total;
}
// Each component has already been normalized on D. LOO removes the component
// with the target's identity, not every coincident point. Weights are training
// posterior immigrant probabilities; held-out callers pass excluded=-1.
inline double kde(const std::vector<double>& densities,const std::vector<double>& weights,int excluded=-1){
 require(densities.size()==weights.size()&&excluded>=-1&&(excluded<0||static_cast<std::size_t>(excluded)<weights.size()),"KDE shape");double z=0,v=0;
 for(std::size_t j=0;j<weights.size();++j){nonnegative(weights[j]);nonnegative(densities[j]);if(static_cast<int>(j)==excluded)continue;z+=weights[j];v+=weights[j]*densities[j];}
 require(z>0&&std::isfinite(z)&&std::isfinite(v),"empty LOO KDE");return v/z;
}
inline double immigrant_probability(double B,double H){nonnegative(B);nonnegative(H);require(B+H>0&&std::isfinite(B+H),"zero posterior intensity");return B/(B+H);}
// Critical value must come from full-search null calibration or frozen inner
// validation. No chi-square/Davies quantile is silently assumed.
inline bool leave_floor(double floor_nll,double candidate_nll,double critical_improvement){
 require(std::isfinite(floor_nll)&&std::isfinite(candidate_nll)&&std::isfinite(critical_improvement)&&critical_improvement>=0,"selection domain");return floor_nll-candidate_nll>critical_improvement;
}
}
