// Extra read-only exports around the unchanged archived Q01 evaluator.
#include "original/independent_f_oracle.cpp"

// P, E, background exposure, triggering exposure, number of quadrature nodes.
API int s02_components(void* handle, const double* par, double* out) {
 using namespace faudit;
 try {
  require(handle && par && out, "component pointers");
  const auto& f=*static_cast<F*>(handle);
  const double a=par[0], d=par[1], n=par[2], eta=par[3];
  require(n>=0 && eta>=0, "component parameter domain");
  Total points, background_sum;
  for(size_t i=0;i<f.G.size();++i) {
   const double immigrant=a+d*f.X[i]-eta*f.G[i];
   const double offspring=n>0?std::log(n)+f.logH[i]:-std::numeric_limits<double>::infinity();
   points.add(logarithm_sum(immigrant,offspring));
  }
  background_sum.add(background(a,d,f.quiet,f.coordinate).first);
  for(size_t i=0;i<f.QG.size();++i)
   background_sum.add(f.QW[i]*std::exp(a+d*f.QX[i]-eta*f.QG[i]));
  if(eta==0) background_sum.x=background(a,d,f.T,f.coordinate).first;
  out[0]=points.x;out[1]=background_sum.x+n*f.exposure;
  out[2]=background_sum.x;out[3]=n*f.exposure;out[4]=double(f.QG.size());
  for(int k=0;k<5;++k) require(std::isfinite(out[k]),"nonfinite components");
  return 0;
 } catch(const std::exception& e) { error=e.what();return 1; }
}

// 2*(log L(alternative)-log L(null)), event delta, signed exposure delta.
// Same state/mark density; this computes a contrast, not a new selected fit.
API int s02_direct_glr(void* handle, const double* zero, const double* alternative, double* out) {
 using namespace faudit;
 try {
  require(handle && zero && alternative && out, "contrast pointers");
  const auto& f=*static_cast<F*>(handle);
  const double a0=zero[0],d0=zero[1],n0=zero[2],e0=zero[3];
  const double a1=alternative[0],d1=alternative[1],n1=alternative[2],e1=alternative[3];
  require(n0>=0 && n1>=0 && e0>=0 && e1>=0, "contrast parameter domain");
  Total point_delta, exposure_delta;
  for(size_t i=0;i<f.G.size();++i) {
   const double l0=logarithm_sum(a0+d0*f.X[i]-e0*f.G[i],n0>0?std::log(n0)+f.logH[i]:-std::numeric_limits<double>::infinity());
   const double l1=logarithm_sum(a1+d1*f.X[i]-e1*f.G[i],n1>0?std::log(n1)+f.logH[i]:-std::numeric_limits<double>::infinity());
   point_delta.add(l1-l0);
  }
  if(e0==0 && e1==0) {
   exposure_delta.add(background(a0,d0,f.T,f.coordinate).first-background(a1,d1,f.T,f.coordinate).first);
  } else {
   exposure_delta.add(background(a0,d0,f.quiet,f.coordinate).first-background(a1,d1,f.quiet,f.coordinate).first);
   for(size_t i=0;i<f.QG.size();++i) {
    const double base=f.QW[i]*std::exp(a0+d0*f.QX[i]-e0*f.QG[i]);
    exposure_delta.add(-base*std::expm1((a1-a0)+(d1-d0)*f.QX[i]-(e1-e0)*f.QG[i]));
   }
  }
  exposure_delta.add((n0-n1)*f.exposure);
  out[0]=2*(point_delta.x+exposure_delta.x);out[1]=point_delta.x;out[2]=exposure_delta.x;
  for(int k=0;k<3;++k) require(std::isfinite(out[k]),"nonfinite direct contrast");
  return 0;
 } catch(const std::exception& e) { error=e.what();return 1; }
}
