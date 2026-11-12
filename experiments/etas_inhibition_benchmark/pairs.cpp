#include <cmath>
#include <vector>
#include <omp.h>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif
// Each row is independent. Reductions over parents retain chronological order.
// No fast-math, stochastic evaluation, training selection or hidden state.
API void pairs(int rows,int cols,const double* lag,const double* r2,
               const double* marks,const double* fertility,const double* x,
               int mode,int threads,double* out) {
  double c=std::exp(x[3]),p=x[4],q=x[7],psi=std::exp(x[10]);
  std::vector<double> s2(cols),e2(cols),mag(cols);
  for(int j=0;j<cols;j++) {
    s2[j]=std::exp(2*x[5]+2*x[6]*marks[j]);
    e2[j]=std::exp(2*x[9]+std::log(10.)*marks[j]);
    mag[j]=std::exp(x[11]*marks[j]);
  }
  #pragma omp parallel for num_threads(threads) schedule(static)
  for(int i=0;i<rows;i++) {
    double sums[6]={0,0,0,0,0,0};
    for(int j=0;j<cols;j++) {
      double t=lag[(size_t)i*cols+j];
      if(t<=0) continue;
      double d=r2[(size_t)i*cols+j];
      if(mode==0) {
        double tl=std::log1p(t/c),sl=std::log1p(d/s2[j]);
        double k=(p-1)/c*std::exp(-p*tl)*(q-1)/(3.14159265358979323846*s2[j])*std::exp(-q*sl)*fertility[j];
        double ds=-2+2*q*d/(s2[j]+d);
        sums[0]+=k;sums[1]+=k*(-1+p*t/(c+t));
        sums[2]+=k*(1/(p-1)-tl);sums[3]+=k*ds;
        sums[4]+=k*ds*marks[j];sums[5]+=k*(1/(q-1)-sl);
      } else {
        double v=1+d/e2[j],k=mag[j]*std::exp(-t/psi)/(v*v);
        sums[0]+=k;sums[1]+=k*4*d/(e2[j]+d);
        sums[2]+=k*t/psi;sums[3]+=k*marks[j];
      }
    }
    for(int k=0;k<(mode==0?6:4);k++)out[(size_t)i*(mode==0?6:4)+k]=sums[k];
  }
}
