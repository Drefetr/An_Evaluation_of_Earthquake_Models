#include "architecture.hpp"
#include <iostream>
#include <cassert>
int main(){using namespace remediation;
 auto p=cell_probabilities({1,2,3});assert(std::abs(p[0]+p[1]+p[2]-1)<1e-15);
 auto a=intensity(2,3,4,0,0);assert(a.value==5);
 auto b=intensity(2,3,4,.2,.2);assert(std::abs(b.value-5*std::exp(-.8))<1e-14);
 auto c=compensator({{.5,2,3,4},{.5,2,3,4}},.2,.2);assert(c.value==b.value);
 assert(kde({100,2,4},{1,1,1},0)==3);assert(immigrant_probability(2,3)==.4);
 assert(!leave_floor(10,9,1));assert(leave_floor(10,8.9,1));
 std::vector<Parent> parents{{0,0,0,0},{1,0,0,0}};
 assert(std::abs(stress(1,0,0,parents,1,0,1,0)-std::exp(-1.))<1e-15);
 std::vector<Parent> marked{{0,1,2,.7},{.5,-2,1,1.2}};
 auto s=stress_gradient(1,.2,.1,marked,2,.3,.8,0);double eps=1e-5;
 auto val=[&](double l,double a,double psi){return stress(1,.2,.1,marked,l,a,psi,0);};
 assert(std::abs(s.dell-(val(2+eps,.3,.8)-val(2-eps,.3,.8))/(2*eps))<1e-8);
 assert(std::abs(s.dpsi-(val(2,.3,.8+eps)-val(2,.3,.8-eps))/(2*eps))<1e-8);
 assert(std::abs(s.dalpha-(val(2,.3+eps,.8)-val(2,.3-eps,.8))/(2*eps))<1e-8);
 std::cout<<"{\"schema\":\"m02_handcrafted_fixture_v1\",\"passed\":true}\n";
}
