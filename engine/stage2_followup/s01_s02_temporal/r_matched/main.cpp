#include "model.hpp"
#include <filesystem>
#include <map>
#include <iostream>

using namespace mdfhp;
std::vector<std::string> split(const std::string& text,char delimiter) {
    std::vector<std::string> fields;std::stringstream ss(text);std::string item;
    while(std::getline(ss,item,delimiter))fields.push_back(item);
    return fields;
}
Config read_config(const std::string& file) {
    std::ifstream in(file);if(!in)throw std::runtime_error("cannot_read_configuration");
    Config cfg;std::string line;std::map<std::string,bool> seen;
    while(std::getline(in,line)) {
        if(line.empty() || line[0]=='#')continue;
        auto p=line.find('=');if(p==std::string::npos)throw std::runtime_error("configuration_requires_key_equals_value");
        auto key=line.substr(0,p);double v=std::stod(line.substr(p+1));
        if(seen[key])throw std::runtime_error("duplicate_configuration_key");seen[key]=true;
        if(key=="horizon")cfg.horizon=v;else if(key=="mu")cfg.mu=v;
        else if(key=="reproduction")cfg.reproduction=v;else if(key=="beta")cfg.beta=v;
        else if(key=="c")cfg.c=v;else if(key=="persistence")cfg.persistence=v;
        else if(key=="magnitude_rate")cfg.magnitude_rate=v;else if(key=="m0")cfg.m0=v;
        else if(key=="cutoff")cfg.cutoff=v;
        else if(key=="productivity_ratio")cfg.productivity_ratio=v;
        else if(key=="max_events") {if(v<1 || std::floor(v)!=v)throw std::runtime_error("invalid_event_cap");cfg.max_events=static_cast<std::size_t>(v);}
        else throw std::runtime_error("unknown_configuration_key");
    }
    if(seen.size()!=11)throw std::runtime_error("configuration_requires_all_eleven_keys");
    cfg.validate();return cfg;
}
std::vector<Event> read_history(const std::string& file,const Config& cfg) {
    std::ifstream in(file);if(!in)throw std::runtime_error("cannot_read_history");
    std::string line;std::getline(in,line);
    if(line!="time_hi,time_lo,event_gap,magnitude,excess,magnitude_class,event_id,parent_id,generation")
        throw std::runtime_error("history_schema_mismatch");
    std::vector<Event> events;std::map<std::size_t,Event> ancestors;Time previous{0,0};
    while(std::getline(in,line)) {
        if(line.empty())continue;auto f=split(line,',');if(f.size()!=9)throw std::runtime_error("history_column_count");
        Event event{{std::stod(f[0]),std::stod(f[1])},std::stoi(f[5]),std::stod(f[4]),
            static_cast<std::size_t>(std::stoull(f[6])),std::stoll(f[7]),static_cast<unsigned>(std::stoul(f[8]))};
        double recorded_gap=std::stod(f[2]),magnitude=std::stod(f[3]);
        for(double v:{event.time.hi,event.time.lo,event.excess,recorded_gap,magnitude})
            if(!std::isfinite(v))throw std::runtime_error("nonfinite_history_field");
        const double ulp_hi=std::nextafter(event.time.hi,std::numeric_limits<double>::infinity())-event.time.hi;
        if(std::abs(event.time.lo)>4*ulp_hi)throw std::runtime_error("nonnormalized_paired_timestamp");
        double gap=positive_gap(event.time,previous);
        const double gap_ulp=std::nextafter(gap,std::numeric_limits<double>::infinity())-gap;
        if(!(recorded_gap>0) || std::abs(recorded_gap-gap)>4*gap_ulp)
            throw std::runtime_error("inconsistent_recorded_gap");
        if(magnitude!=cfg.m0+event.excess)throw std::runtime_error("inconsistent_magnitude_and_excess");
        if(ancestors.count(event.id))throw std::runtime_error("duplicate_event_identity");
        if(event.parent<0) {if(event.parent!=-1 || event.generation!=0)throw std::runtime_error("invalid_immigrant_ancestry");}
        else {
            auto parent=ancestors.find(static_cast<std::size_t>(event.parent));
            if(parent==ancestors.end() || event.generation!=parent->second.generation+1)
                throw std::runtime_error("invalid_descendant_ancestry");
        }
        ancestors.emplace(event.id,event);events.push_back(event);previous=event.time;
    }
    return events;
}
std::ofstream fresh_output(const std::string& file) {
    if(std::filesystem::exists(file))throw std::runtime_error("refusing_to_overwrite_output");
    std::ofstream out(file);if(!out)throw std::runtime_error("cannot_create_output");out<<std::setprecision(17);return out;
}
int main(int argc,char** argv) {
    std::cout<<std::setprecision(17);
    try {
        if(argc<2)throw std::runtime_error("expected_simulate_score_kernels_or_clock_check");
        std::string mode=argv[1];
        if(mode=="simulate" && argc==6) {
            Config cfg=read_config(argv[2]);
            auto result=simulate(cfg,std::stoull(argv[4]),std::stoull(argv[5]));
            write_history(argv[3],cfg,result);
            std::cout<<"{\"status\":\""<<result.status<<"\",\"reason\":\""<<result.reason<<"\",\"events\":"<<result.events.size()
                <<",\"attempted_offspring\":"<<result.attempted_offspring<<",\"outside_window_offspring\":"<<result.outside_window_offspring
                <<",\"construction_complete\":"<<(result.status=="ok"?"true":"false")
                <<",\"max_wait_relative_error\":"<<result.max_wait_relative_error
                <<",\"time_seed\":\""<<result.time_seed<<"\",\"mark_seed\":\""<<result.mark_seed<<"\"}\n";
            return result.status=="ok"?0:2;
        }
        if(mode=="score" && argc==5) {
            auto cfg=read_config(argv[2]);auto score=known_score(cfg,read_history(argv[3],cfg));auto out=fresh_output(argv[4]);
            out<<"{\"timing\":"<<score.timing<<",\"mark\":"<<score.mark<<",\"joint\":"<<score.joint
                <<",\"compensator\":"<<score.compensator<<"}\n";
            std::cout<<"{\"status\":\"ok\"}\n";return 0;
        }
        if(mode=="kernels" && argc==4) {
            std::ifstream in(argv[2]);if(!in)throw std::runtime_error("cannot_read_kernel_fixture");
            auto out=fresh_output(argv[3]);out<<"time,beta,c,survival,density\n";
            std::string line;std::getline(in,line);
            while(std::getline(in,line)) {
                if(line.empty())continue;auto f=split(line,',');if(f.size()!=3)throw std::runtime_error("kernel_fixture_column_count");
                double t=std::stod(f[0]),beta=std::stod(f[1]),c=std::stod(f[2]);
                out<<t<<','<<beta<<','<<c<<','<<survival(t,beta,c)<<','<<density(t,beta,c)<<'\n';
            }
            std::cout<<"{\"status\":\"ok\"}\n";return 0;
        }
        if(mode=="clock-check" && argc==3) {
            auto out=fresh_output(argv[2]);out<<"parent_hi,parent_lo,wait,child_hi,child_lo,recovered_gap\n";
            Time parent{24394,0};
            for(double wait:{1e-6,1e-12,1e-16,1e-20,1e-24}) {
                auto child=add_wait(parent,wait);
                out<<parent.hi<<','<<parent.lo<<','<<wait<<','<<child.hi<<','<<child.lo<<','<<positive_gap(child,parent)<<'\n';
            }
            // Chain nonzero low residuals, including projected sibling ties.
            parent=add_wait(parent,1e-12);
            for(double wait:{1e-16,1e-20,1e-24}) {
                auto child=add_wait(parent,wait);
                out<<parent.hi<<','<<parent.lo<<','<<wait<<','<<child.hi<<','<<child.lo<<','<<positive_gap(child,parent)<<'\n';
                parent=child;
            }
            std::cout<<"{\"status\":\"ok\"}\n";return 0;
        }
        throw std::runtime_error("invalid_mode_or_argument_count");
    } catch(const std::exception& ex) {
        std::cerr<<"{\"status\":\"error\",\"reason\":\""<<ex.what()<<"\"}\n";return 1;
    }
}
