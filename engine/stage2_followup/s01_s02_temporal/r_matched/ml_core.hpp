#pragma once
#include <cmath>
#include <limits>
#include <stdexcept>

namespace mdfhp {
// Independent implementation of elementary closed-form ML identities.
// Deliberately restricted to beta=1/2 and beta=1. No upstream source is copied.
// For beta=1/2, E_(1/2,1)(-x)=exp(x*x)erfc(x),
// E_(1/2,1/2)(-x)=1/sqrt(pi)-x*exp(x*x)erfc(x).
// At x>=8 an alternating asymptotic series avoids overflow/cancellation;
// stop before terms grow. Deterministic cross-method controls are required.
constexpr double inv_sqrt_pi=0.564189583547756286948079451560772586;
inline void validate_ml(double x,double alpha,double second) {
    if(!std::isfinite(x) || x<0 || !std::isfinite(alpha) || !std::isfinite(second))
        throw std::invalid_argument("invalid_mittag_leffler_argument");
    if(!((alpha==0.5 && (second==0.5 || second==1)) || (alpha==1 && second==1)))
        throw std::invalid_argument("unsupported_beta_closed_form_core_supports_half_or_one_only");
}
inline double half_ml(double x,bool second_half) {
    if(x<8) {
        double survival=std::exp(x*x)*std::erfc(x);
        return second_half ? inv_sqrt_pi-x*survival:survival;
    }
    const double inv2x2=0.5/x/x;
    double term=1.0,sum=1.0,correction=0.0;
    for(unsigned k=1;k<=256;++k) {
        double next=-term*(2.0*k-1)*inv2x2;
        if(std::abs(next)>std::abs(term))break;
        sum+=next;correction-=next;term=next;
        if(std::abs(next)<=std::numeric_limits<double>::epsilon()*std::abs(sum)*0.125)break;
    }
    double value=second_half ? inv_sqrt_pi*correction:inv_sqrt_pi/x*sum;
    if(!(value>=0) || !std::isfinite(value))throw std::runtime_error("invalid_half_mittag_leffler_value");
    return value;
}
inline double ml_negative(double x,double alpha,double second) {
    validate_ml(x,alpha,second);
    if(alpha==1)return std::exp(-x);
    return half_ml(x,second==0.5);
}
inline void validate_kernel(double t,double beta,double c) {
    if(!std::isfinite(t) || t<0 || !std::isfinite(c) || !(c>0) || !(beta==0.5 || beta==1))
        throw std::invalid_argument("kernel_requires_nonnegative_time_positive_scale_and_beta_half_or_one");
}
inline double survival(double t,double beta,double c) {
    validate_kernel(t,beta,c);
    if(t==0)return 1;
    if(!std::isfinite(c*t))throw std::overflow_error("kernel_time_scale_overflow");
    if(beta==1)return std::exp(-c*t);
    return half_ml(std::sqrt(c*t),false);
}
inline double density(double t,double beta,double c) {
    validate_kernel(t,beta,c);
    if(t==0)return beta==1?c:std::numeric_limits<double>::infinity();
    if(!std::isfinite(c*t) || c*t==0)throw std::overflow_error("kernel_time_scale_unrepresentable");
    if(beta==1)return c*std::exp(-c*t);
    double x=std::sqrt(c*t);
    return c/x*half_ml(x,true);
}
}
