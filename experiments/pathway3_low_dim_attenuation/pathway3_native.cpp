// Pathway 3 compiled contractions for the low-dimensional attenuation study.
//
// This file is an isolated derivative of two archived sources, both of which
// are read-only:
//   * experiments/s04b_joint_nuisance/attenuation.cpp  (joint deficit recurrence)
//   * experiments/pathway1_annular_attenuation/annular_native.cpp
//     (annular row contractions)
//
// The archived files are never modified.  Pathway 3 adds two exported
// generalisations:
//   joint_integral_ell  -- the deficit recurrence with an explicit per-parent
//                          squared attenuation scale, so that
//                          ell_j = WellsCoppersmith(M_j) can be supplied as a
//                          data-dependent vector without refitting a global ell;
//   annular_rows_p3     -- the annular row contraction with an explicit
//                          magnitude exponent alpha_ell, so that
//                          ell_j = ell0 10^(alpha_ell m_j) can represent the
//                          Wells-Coppersmith exponent 0.59 rather than the
//                          archived design value 0.5.
//
// Row output columns (12 per row), unchanged from the archived Pathway 1 ABI:
//   0 H, 1 dH/dlogc, 2 dH/dp, 3 dH/dlogsigma0, 4 dH/dalpha_s, 5 dH/dq,
//   6 G, 7 dG/dlogell0, 8 dG/dlogpsi, 9 dG/dgamma,
//  10 dG/dlogsigma0, 11 dG/dalpha_s.
#include <cmath>
#include <cstddef>
#include <exception>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C" __attribute__((visibility("default")))
#endif

static const double PI = 3.141592653589793238462643383279502884;
static thread_local std::string error;
static void require(bool x, const char* message) { if (!x) throw std::runtime_error(message); }

// ---------------------------------------------------------------------------
// Shared joint deficit recurrence.  ``ell2`` has one entry per parent and is
// the square of the attenuation length used by that parent.  Output:
//   0 deficit, 1 d/da, 2 d/dd, 3 d/dn, 4 d/dlogc, 5 d/dp,
//   6 d/deta, 7 d/dlogell_uniform, 8 d/dlogpsi.
// The 7th component is the derivative under a common multiplicative scaling of
// every parent's ell; it is retained so the uniform-ell path can be checked
// against the archived ABI.
// ---------------------------------------------------------------------------
static int joint_integral_common(int ns, int np, int nt, int inclusive,
                                 const double* pt, const double* marks,
                                 const double* r2, const double* area,
                                 const double* background, const double* times,
                                 const double* weights, const double* triggering,
                                 const double* theta, double horizon,
                                 const double* clock, int orthogonal,
                                 double orth_c, double orth_k,
                                 const double* ell2, double* out) {
  require(ns >= 0 && np >= 0 && nt > 0 && horizon > 0, "invalid dimensions");
  require(pt && marks && r2 && area && background && times && weights &&
          triggering && theta && clock && ell2 && out, "null pointer");
  require(inclusive == 0 || inclusive == 1, "invalid mode");
  for (int k = 0; k < 8; ++k) require(std::isfinite(theta[k]), "nonfinite parameter");
  require(std::isfinite(orth_c) && std::isfinite(orth_k), "nonfinite orthogonalisation");
  const double a = theta[0], d = theta[1], n = theta[2];
  const double eta = theta[5], psi = std::exp(theta[7]);
  require(eta >= 0 && psi > 0 && n >= 0, "invalid attenuation parameter");
  for (int j = 0; j < np; ++j) require(std::isfinite(ell2[j]) && ell2[j] > 0, "invalid ell2");
  std::fill(out, out + 9, 0.0);
  std::vector<double> pr(np), pd(np), qr(nt), qd(nt), mu(nt), xx(nt);
  std::vector<int> end(nt);
  double clock_parent = np ? std::min(pt[0], times[0]) : times[0];
  int consumed = 0;
  for (int i = 0; i < nt; ++i) {
    require(std::isfinite(times[i]) && std::isfinite(weights[i]) && weights[i] > 0,
            "invalid quadrature");
    require(std::isfinite(clock[i]), "nonfinite background clock");
    if (i) require(times[i] >= times[i - 1], "unordered quadrature");
    while (consumed < np && pt[consumed] < times[i]) {
      require(pt[consumed] >= clock_parent, "unordered parents");
      pr[consumed] = (pt[consumed] - clock_parent) / psi;
      pd[consumed] = std::exp(-pr[consumed]);
      clock_parent = pt[consumed];
      ++consumed;
    }
    end[i] = consumed;
    qr[i] = (times[i] - clock_parent) / psi;
    qd[i] = std::exp(-qr[i]);
    clock_parent = times[i];
    xx[i] = clock[i];
    mu[i] = std::exp(a + d * xx[i]);
  }
  std::vector<double> radial(np), dell(np);
  for (int s = 0; s < ns; ++s) {
    require(area[s] > 0 && background[s] > 0, "nonpositive spatial quadrature");
    for (int j = 0; j < np; ++j) {
      const double v = r2[(size_t)s * np + j] / ell2[j];
      const double one = 1.0 + v;
      radial[j] = marks[j] / (one * one);
      dell[j] = radial[j] * 4.0 * v / one;
      require(std::isfinite(radial[j]) && std::isfinite(dell[j]), "nonfinite stress input");
    }
    double G = 0.0, L = 0.0, P = 0.0;
    int j = 0;
    auto decay = [&](double ratio, double e) {
      P = e * (P + G * ratio);
      G *= e;
      L *= e;
    };
    const double* tr = triggering + (inclusive ? (size_t)s * 3 * nt : 0);
    for (int i = 0; i < nt; ++i) {
      while (j < end[i]) { decay(pr[j], pd[j]); G += radial[j]; L += dell[j]; ++j; }
      decay(qr[i], qd[i]);
      const double R = orthogonal ? G - orth_c - orth_k * xx[i] : G;
      const double B = mu[i] * background[s], H = inclusive ? tr[i] : 0.0;
      const double base = B + n * H, w = area[s] * weights[i];
      const double e = std::exp(-eta * R);
      const double lost = -std::expm1(-eta * R);
      out[0] += w * base * lost;
      out[1] += w * B * lost;
      out[2] += w * xx[i] * B * lost;
      if (inclusive) {
        out[3] += w * H * lost;
        out[4] += w * n * tr[nt + i] * lost;
        out[5] += w * n * tr[2 * nt + i] * lost;
      }
      out[6] += w * base * e * R;
      out[7] += w * base * e * eta * L;
      out[8] += w * base * e * eta * P;
    }
  }
  for (int k = 0; k < 9; ++k) require(std::isfinite(out[k]), "nonfinite attenuation integral");
  return 0;
}

API const char* p3_error() { return error.c_str(); }

// Archived-compatible entry point with a global scale in theta[6].
API int joint_integral_law(int ns, int np, int nt, int inclusive,
                           const double* pt, const double* marks, const double* r2,
                           const double* area, const double* background,
                           const double* times, const double* weights,
                           const double* triggering, const double* theta,
                           double horizon, const double* clock, int orthogonal,
                           double orth_c, double orth_k, double* out) {
  try {
    const double ell = std::exp(theta[6]);
    require(ell > 0, "invalid global ell");
    std::vector<double> ell2(np ? np : 1, ell * ell);
    const int status = joint_integral_common(
        ns, np, nt, inclusive, pt, marks, r2, area, background, times, weights,
        triggering, theta, horizon, clock, orthogonal, orth_c, orth_k,
        ell2.data(), out);
    return status;
  } catch (const std::exception& e) { error = e.what(); return 1; }
}

// Explicit per-parent squared attenuation scale.
API int joint_integral_ell(int ns, int np, int nt, int inclusive,
                           const double* pt, const double* marks, const double* r2,
                           const double* area, const double* background,
                           const double* times, const double* weights,
                           const double* triggering, const double* theta,
                           double horizon, const double* clock, int orthogonal,
                           double orth_c, double orth_k, const double* ell2,
                           double* out) {
  try {
    return joint_integral_common(ns, np, nt, inclusive, pt, marks, r2, area,
                                 background, times, weights, triggering, theta,
                                 horizon, clock, orthogonal, orth_c, orth_k, ell2, out);
  } catch (const std::exception& e) { error = e.what(); return 1; }
}

// ---------------------------------------------------------------------------
// Annular row contraction with an explicit magnitude exponent.
// ``alpha_ell`` replaces the archived fixed 0.5 in ell_j = ell0 10^(alpha m).
// ---------------------------------------------------------------------------
API void annular_rows_p3(int rows, int cols, const double* lag, const double* r2,
                         const double* marks, const double* fertility,
                         const double* x, int kernel, int scaled,
                         int need_h, int need_g, int threads, double alpha_ell,
                         double* out) {
  const double a = x[0], d = x[1], n = x[2], logc = x[3], p = x[4];
  const double logsigma = x[5], alpha = x[6], q = x[7];
  const double eta = x[8], logell = x[9], logpsi = x[10], gamma = x[11];
  const double c = std::exp(logc), psi = std::exp(logpsi);
  const double log10 = std::log(10.0);
  std::vector<double> sigma2(cols), ell2(cols), mag(cols), fert(cols), mk(cols);
  for (int j = 0; j < cols; ++j) {
    const double m = marks[j];
    sigma2[j] = std::exp(2.0 * logsigma + 2.0 * alpha * m);
    ell2[j] = scaled ? std::exp(2.0 * logell + 2.0 * alpha_ell * log10 * m)
                     : std::exp(2.0 * logell);
    mag[j] = std::exp(gamma * m);
    fert[j] = fertility[j];
    mk[j] = m;
  }
  const int stride = 12;
#pragma omp parallel for num_threads(threads) schedule(static)
  for (int i = 0; i < rows; ++i) {
    double s[12];
    for (int k = 0; k < 12; ++k) s[k] = 0.0;
    const double* li = lag + (size_t)i * cols;
    const double* ri = r2 + (size_t)i * cols;
    for (int j = 0; j < cols; ++j) {
      const double t = li[j];
      if (!(t > 0.0)) continue;
      const double d2 = ri[j];
      if (need_h) {
        const double v = d2 / sigma2[j];
        const double tl = std::log1p(t / c);
        const double sl = std::log1p(v);
        const double k = (p - 1.0) / c * std::exp(-p * tl) *
                         (q - 1.0) / (PI * sigma2[j]) * std::exp(-q * sl) * fert[j];
        const double ds = -2.0 + 2.0 * q * v / (1.0 + v);
        s[0] += k;
        s[1] += k * (-1.0 + p * t / (c + t));
        s[2] += k * (1.0 / (p - 1.0) - tl);
        s[3] += k * ds;
        s[4] += k * ds * mk[j];
        s[5] += k * (1.0 / (q - 1.0) - sl);
      }
      if (need_g) {
        const double v = d2 / ell2[j];
        const double base = mag[j] * std::exp(-t / psi);
        double K = 0.0, dK = 0.0, dsK = 0.0;
        if (kernel == 0) {                      // epicentral monotone
          const double one = 1.0 + v;
          K = 1.0 / (one * one);
          dK = 4.0 * v / (one * one * one);
        } else if (kernel == 1) {               // first-order annular ring
          const double one = 1.0 + v;
          K = 6.75 * v / (one * one * one);
          dK = 13.5 * v * (2.0 * v - 1.0) / (one * one * one * one);
        } else if (kernel == 2) {               // second-order sharp annulus
          const double one = 1.0 + v;
          const double one2 = one * one;
          K = 16.0 * v * v / (one2 * one2);
          dK = 64.0 * v * v * (v - 1.0) / (one2 * one2 * one);
        } else {                                // trigger-core-shielded
          const double one = 1.0 + v;
          const double one2 = one * one;
          const double w = d2 / sigma2[j];
          const double inv = 1.0 / (1.0 + w);
          K = w * inv / one2;
          dK = 4.0 * v * w * inv / (one2 * one);
          dsK = -2.0 * w * inv * inv / one2;
        }
        const double g = base * K;
        s[6] += g;
        s[7] += base * dK;
        s[8] += g * (t / psi);
        s[9] += g * mk[j];
        if (kernel == 3) {
          s[10] += base * dsK;
          s[11] += base * dsK * mk[j];
        }
      }
    }
    for (int k = 0; k < 12; ++k) out[(size_t)i * stride + k] = s[k];
  }
}
