#pragma once
#include "clock.hpp"
#include "ml_core.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <vector>

namespace mdfhp {
// A gamma=0, common-kernel subfamily of the MDFHP. This is a new synthetic
// construction, not the authors' complete fitting workflow or fitted parameters.
struct Config {
    double horizon=24394.0, mu=0.015574684, reproduction=0.5;
    double beta=0.5, c=1.0, persistence=0.0;
    double productivity_ratio=0.;
    double magnitude_rate=2.849401764894274, m0=5.0, cutoff=0.5;
    std::size_t max_events=5000;
    double upper_probability() const { return std::exp(-magnitude_rate*cutoff); }
    void validate() const {
        for(double v:{horizon,mu,reproduction,beta,c,persistence,magnitude_rate,m0,cutoff,productivity_ratio})
            if(!std::isfinite(v)) throw std::invalid_argument("nonfinite_configuration");
        if(!(horizon>0 && mu>=0 && reproduction>=0 && reproduction<1 && beta>0 && beta<=1
             && productivity_ratio>=0 && productivity_ratio<1 && c>0 && persistence>=0 && persistence<=1 && magnitude_rate>0 && cutoff>0 && max_events>0))
            throw std::invalid_argument("configuration_out_of_domain");
        if(!(upper_probability()>0 && upper_probability()<1))
            throw std::invalid_argument("unrepresentable_bin_probability");
        if(!(beta==0.5 || beta==1.0))
            throw std::invalid_argument("current_study_core_supports_beta_half_or_one_only");
    }
};
struct Event {
    Time time;
    int magnitude_class=0;
    double excess=0.0;
    std::size_t id=0;
    std::int64_t parent=-1;
    unsigned generation=0;
};
struct Simulation {
    std::vector<Event> events;
    std::string status="ok", reason="";
    std::uint64_t time_seed=0, mark_seed=0;
    std::size_t attempted_offspring=0, outside_window_offspring=0;
    double max_wait_relative_error=0.0;
};
// Exactly representable open-uniform grid with 52 random mantissa bits. The
// endpoint rule is fixed here, rather than left to std::uniform_real_distribution.
inline double open_uniform(std::mt19937_64& rng) {
    return (static_cast<double>(rng() >> 12)+0.5)/4503599627370496.0;
}
inline double log_ml_wait(std::mt19937_64& rng,double beta,double c) {
    double u=open_uniform(rng);
    const double log_exp=std::log(-std::log(u));
    if(beta==1.0) return log_exp-std::log(c);
    double v=open_uniform(rng), theta=3.141592653589793238462643383279502884*beta;
    // Kozubowski (2000), section 2.3. The sine ratio is algebraically equal
    // to sin(theta)*cot(theta*v)-cos(theta), avoiding endpoint cancellation.
    return log_exp-std::log(c)+(std::log(std::sin(theta*(1-v)))-std::log(std::sin(theta*v)))/beta;
}
inline Simulation simulate(const Config& cfg,std::uint64_t time_seed,std::uint64_t mark_seed) {
    cfg.validate();
    Simulation result; result.time_seed=time_seed; result.mark_seed=mark_seed;
    std::mt19937_64 time_rng(time_seed),mark_rng(mark_seed);
    std::poisson_distribution<std::size_t> immigrants(cfg.mu*cfg.horizon);
    const auto n_immigrants=immigrants(time_rng);
    if(n_immigrants>cfg.max_events) {result.status="event_cap";result.reason="immigrant_count_exceeds_cap";return result;}
    for(std::size_t k=0;k<n_immigrants;++k)
        result.events.push_back({{cfg.horizon*open_uniform(time_rng),0},0,0,k,-1,0});
    // Marks precede parent reproduction: required for matched productivity.
    const double upper=cfg.upper_probability(), lower=1-upper;
    auto assign_mark=[&](Event& event){
    double p_upper=upper;
    if(event.parent>=0)
        p_upper=(1-cfg.persistence)*upper+cfg.persistence*result.events[static_cast<std::size_t>(event.parent)].magnitude_class;
    event.magnitude_class=open_uniform(mark_rng)<p_upper ? 1:0;
    double u=open_uniform(mark_rng);
    event.excess=event.magnitude_class ? cfg.cutoff-std::log1p(-u)/cfg.magnitude_rate
        : -std::log1p(-u*lower)/cfg.magnitude_rate;
    };
    try {
        for(std::size_t k=0;k<result.events.size();++k) {
            assign_mark(result.events[k]);
            const Event parent=result.events[k];
            double productivity=(1-cfg.productivity_ratio)*std::exp(cfg.magnitude_rate*cfg.productivity_ratio*parent.excess);
            double mean=cfg.reproduction*productivity;
            if(!(mean>=0 && std::isfinite(mean)))throw std::runtime_error("unrepresentable_offspring_mean");
            std::poisson_distribution<std::size_t> offspring(mean);
            const auto number=offspring(time_rng);
            for(std::size_t j=0;j<number;++j) {
                ++result.attempted_offspring;
                double lw=log_ml_wait(time_rng,cfg.beta,cfg.c);
                const double remaining=difference({cfg.horizon,0},parent.time);
                if(!(remaining>0)) throw std::runtime_error("parent_outside_window");
                // Compare in log space. An arbitrarily large waiting time is
                // known to be outside this finite window without exponentiation.
                if(lw>=std::log(remaining)) {++result.outside_window_offspring;continue;}
                double wait=std::exp(lw);
                Time child=add_wait(parent.time,wait);
                const double represented_wait=positive_gap(child,parent.time);
                const double relative_error=std::abs((represented_wait-wait)/wait);
                result.max_wait_relative_error=std::max(result.max_wait_relative_error,relative_error);
                if(relative_error>1e-8)
                    throw std::runtime_error("clock_wait_relative_precision_exhausted");
                if(!less(child,{cfg.horizon,0})) {++result.outside_window_offspring;continue;}
                if(result.events.size()==cfg.max_events) {
                    result.status="event_cap";result.reason="descendant_count_exceeds_cap";
                    return result;
                }
                result.events.push_back({child,0,0,result.events.size(),static_cast<std::int64_t>(parent.id),parent.generation+1});
            }
        }
        std::sort(result.events.begin(),result.events.end(),[](const Event& a,const Event& b){return less(a.time,b.time);});
        Time previous{0,0};
        for(const auto& event:result.events) {positive_gap(event.time,previous);previous=event.time;}
    } catch(const std::exception& ex) {result.status="numerical_failure";result.reason=ex.what();}
    return result;
}
inline void write_history(const std::string& path,const Config& cfg,const Simulation& sim) {
    std::ifstream already(path);
    if(already.good()) throw std::runtime_error("refusing_to_overwrite_history");
    std::ofstream out(path);
    if(!out) throw std::runtime_error("cannot_create_history");
    out<<"time_hi,time_lo,event_gap,magnitude,excess,magnitude_class,event_id,parent_id,generation\n"<<std::setprecision(17);
    Time previous{0,0};
    for(const auto& event:sim.events) {
        double gap=less(previous,event.time) ? difference(event.time,previous):std::numeric_limits<double>::quiet_NaN();
        out<<event.time.hi<<','<<event.time.lo<<','<<gap<<','<<cfg.m0+event.excess<<','<<event.excess<<','
           <<event.magnitude_class<<','<<event.id<<','<<event.parent<<','<<event.generation<<'\n';
        previous=event.time;
    }
}
struct Score { double timing=0,mark=0,joint=0,compensator=0; };
inline Score known_score(const Config& cfg,const std::vector<Event>& history) {
    cfg.validate();
    Score out; out.compensator=cfg.mu*cfg.horizon;
    const double upper=cfg.upper_probability();
    Time previous{0,0};
    for(std::size_t k=0;k<history.size();++k) {
        const auto& event=history[k];
        positive_gap(event.time,previous); previous=event.time;
        if(!less(event.time,{cfg.horizon,0})) throw std::runtime_error("event_outside_window");
        if(!(event.magnitude_class==0 || event.magnitude_class==1) ||
           !(event.excess>=0) || !std::isfinite(event.excess) ||
           (event.magnitude_class==0 && !(event.excess<cfg.cutoff)) ||
           (event.magnitude_class==1 && !(event.excess>=cfg.cutoff)))
            throw std::runtime_error("invalid_mark");
        const double class_p=event.magnitude_class ? upper:1-upper;
        double lambda=cfg.mu, lambda_class=cfg.mu*class_p;
        for(std::size_t j=0;j<k;++j) {
            double contribution=cfg.reproduction*(1-cfg.productivity_ratio)*std::exp(cfg.magnitude_rate*cfg.productivity_ratio*history[j].excess)*density(positive_gap(event.time,history[j].time),cfg.beta,cfg.c);
            lambda+=contribution;
            lambda_class+=contribution*((1-cfg.persistence)*class_p+cfg.persistence*(history[j].magnitude_class==event.magnitude_class));
        }
        if(!(lambda>0 && lambda_class>0 && std::isfinite(lambda) && std::isfinite(lambda_class)))
            throw std::runtime_error("nonfinite_or_nonpositive_intensity");
        const double log_conditional_mark=std::log(cfg.magnitude_rate)-cfg.magnitude_rate*event.excess-std::log(class_p);
        out.timing+=std::log(lambda);
        out.mark+=std::log(lambda_class)-std::log(lambda)+log_conditional_mark;
        double remaining=difference({cfg.horizon,0},event.time);
        out.compensator+=cfg.reproduction*(1-cfg.productivity_ratio)*std::exp(cfg.magnitude_rate*cfg.productivity_ratio*event.excess)*(1-survival(remaining,cfg.beta,cfg.c));
    }
    out.timing-=out.compensator;
    out.joint=out.timing+out.mark;
    return out;
}
}
