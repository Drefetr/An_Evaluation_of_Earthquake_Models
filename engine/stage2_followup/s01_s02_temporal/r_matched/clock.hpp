#pragma once

#include <cmath>

#include <stdexcept>

#include <limits>

namespace mdfhp {

struct Time { double hi=0.0, lo=0.0; };

inline Time two_sum(double a,double b) {

    const double s=a+b; const double bb=s-a;

    return {s,(a-(s-bb))+(b-bb)};

}

inline Time add(Time a, Time b) {

    Time s=two_sum(a.hi,b.hi), t=two_sum(a.lo,b.lo);

    Time u=two_sum(s.lo,t.hi), v=two_sum(s.hi,u.hi);

    return two_sum(v.hi, v.lo+u.lo+t.lo);

}

inline Time add_wait(Time a,double w) {

    if (!(w>0.0) || !std::isfinite(w)) throw std::runtime_error("unrepresentable_positive_wait");

    Time out=add(a,{w,0.0});

    if (!(out.hi>a.hi || (out.hi==a.hi && out.lo>a.lo))) throw std::runtime_error("paired_clock_addition_failed");

    return out;

}

inline bool less(Time a,Time b) {return a.hi<b.hi || (a.hi==b.hi && a.lo<b.lo);}

inline bool equal(Time a,Time b) {return a.hi==b.hi && a.lo==b.lo;}

inline double difference(Time a,Time b) {Time d=add(a,{-b.hi,-b.lo});return d.hi+d.lo;}

inline double positive_gap(Time a,Time b) {

    if (!less(b,a)) throw std::runtime_error("nonpositive_paired_gap");

    double d=difference(a,b);

    if (!(d>0.0) || !std::isfinite(d)) throw std::runtime_error("unrepresentable_positive_gap");

    return d;

}

}

