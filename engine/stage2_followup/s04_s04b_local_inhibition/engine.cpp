#include "architecture.hpp"
#include <string>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
static thread_local std::string last_error;
// Rows: time,x,y,B,H,weight. Event weight must be 1. Node weights are
// spacetime integration weights. Parents: time,x,y,Q. No data are logged.
API int m02_nll(int ne,int nn,int np,const double* events,const double* nodes,
 const double* parent_rows,const double* parameters,double qref,double* out){
 try {using namespace remediation;require(ne>=0&&nn>=0&&np>=0&&parameters&&out,"dimensions");
 require((events||ne==0)&&(nodes||nn==0)&&(parent_rows||np==0),"null rows");
 std::vector<Parent> parents;for(int j=0;j<np;++j)parents.push_back({parent_rows[4*j],parent_rows[4*j+1],parent_rows[4*j+2],parent_rows[4*j+3]});
 double eb=parameters[0],et=parameters[1],ell=parameters[2],psi=parameters[3],alpha=parameters[4];
 nonnegative(eb);nonnegative(et);require(ell>0&&psi>0&&std::isfinite(ell)&&std::isfinite(psi)&&std::isfinite(alpha),"physical parameters");
 double comp=0,point=0,gb=0,gt=0,gl=0,gp=0,ga=0;
 for(int kind=0;kind<2;++kind){int n=kind?ne:nn;const double* rows=kind?events:nodes;
  for(int i=0;i<n;++i){const double* row=rows+6*i;auto G=stress_gradient(row[0],row[1],row[2],parents,ell,alpha,psi,qref);auto v=intensity(row[3],row[4],G.value,eb,et);
   double dl_dG=-eb*row[3]*std::exp(-eb*G.value)-et*row[4]*std::exp(-et*G.value);
   nonnegative(row[5]);if(kind){require(row[5]==1&&v.value>0,"event intensity/weight");point+=std::log(v.value);gb-=v.d_eta_bg/v.value;gt-=v.d_eta_trigger/v.value;}
   else {comp+=row[5]*v.value;gb+=row[5]*v.d_eta_bg;gt+=row[5]*v.d_eta_trigger;}
   double factor=kind?-dl_dG/v.value:row[5]*dl_dG;gl+=factor*G.dell;gp+=factor*G.dpsi;ga+=factor*G.dalpha;
  }
 }out[0]=comp-point;out[1]=gb;out[2]=gt;out[3]=gl;out[4]=gp;out[5]=ga;out[6]=comp;out[7]=point;
 for(int j=0;j<8;++j)require(std::isfinite(out[j]),"nonfinite likelihood");last_error.clear();return 0;
 }catch(const std::exception& e){last_error=e.what();return 1;}
}
API const char* m02_error(){return last_error.c_str();}
