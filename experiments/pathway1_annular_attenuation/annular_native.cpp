// Pathway 1 annular attenuation kernels: combined ETAS H and attenuation G
// row contractions with exact analytic parameter derivatives.
//
// Rows are independent and are reduced over strictly prior parents in
// chronological order. No fast-math, stochastic evaluation or hidden state.
//
// Output columns (12 per row):
//   0 H, 1 dH/dlogc, 2 dH/dp, 3 dH/dlogsigma0, 4 dH/dalpha_s, 5 dH/dq,
//   6 G, 7 dG/dlogell0, 8 dG/dlogpsi, 9 dG/dgamma,
//  10 dG/dlogsigma0, 11 dG/dalpha_s
#include <cmath>
#include <vector>
#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C"
#endif

static const double PI = 3.141592653589793238462643383279502884;

// Joint temporal-backbone attenuation integral for the synthetic control bank.
// Mirrors the archived S8 joint_integral recursion, but the radial stress may
// be mono, ann1 or ann2. theta is [a,d,n,logc,p,eta,logell,logpsi].
API int joint_integral_annular(int ns, int np, int nt, int inclusive,
                               const double* pt, const double* marks,
                               const double* r2, const double* area,
                               const double* background, const double* times,
                               const double* weights, const double* triggering,
                               const double* theta, double horizon, int kernel,
                               double* out) {
  if (!(ns >= 0 && np >= 0 && nt > 0 && horizon > 0)) return 1;
  if (!pt || !marks || !r2 || !area || !background || !times || !weights ||
      !triggering || !theta || !out) return 2;
  if (!(inclusive == 0 || inclusive == 1)) return 3;
  for (int k = 0; k < 8; ++k) if (!std::isfinite(theta[k])) return 4;
  const double a = theta[0], d = theta[1], n = theta[2];
  const double eta = theta[5], ell = std::exp(theta[6]), psi = std::exp(theta[7]);
  if (!(eta >= 0 && ell > 0 && psi > 0 && n >= 0)) return 5;
  for (int k = 0; k < 9; ++k) out[k] = 0.0;
  std::vector<double> pr(np), pd(np), qr(nt), qd(nt), mu(nt), xx(nt);
  std::vector<int> end(nt);
  double clock = np ? std::min(pt[0], times[0]) : times[0];
  int consumed = 0;
  for (int i = 0; i < nt; ++i) {
    if (!(std::isfinite(times[i]) && std::isfinite(weights[i]) && weights[i] > 0)) return 6;
    if (i && times[i] < times[i - 1]) return 7;
    while (consumed < np && pt[consumed] < times[i]) {
      if (!(pt[consumed] >= clock)) return 8;
      pr[consumed] = (pt[consumed] - clock) / psi;
      pd[consumed] = std::exp(-pr[consumed]);
      clock = pt[consumed];
      ++consumed;
    }
    end[i] = consumed;
    qr[i] = (times[i] - clock) / psi;
    qd[i] = std::exp(-qr[i]);
    clock = times[i];
    xx[i] = 2.0 * times[i] / horizon - 1.0;
    mu[i] = std::exp(a + d * xx[i]);
  }
  std::vector<double> radial(np), dell(np);
  for (int s = 0; s < ns; ++s) {
    if (!(area[s] > 0 && background[s] > 0)) return 9;
    for (int j = 0; j < np; ++j) {
      const double v = r2[(size_t)s * np + j] / (ell * ell);
      const double one = 1.0 + v;
      if (kernel == 0) {
        radial[j] = marks[j] / (one * one);
        dell[j] = radial[j] * 4.0 * v / one;
      } else if (kernel == 1) {
        radial[j] = marks[j] * 6.75 * v / (one * one * one);
        dell[j] = marks[j] * 13.5 * v * (2.0 * v - 1.0) / (one * one * one * one);
      } else if (kernel == 2) {
        const double one2 = one * one;
        radial[j] = marks[j] * 16.0 * v * v / (one2 * one2);
        dell[j] = marks[j] * 64.0 * v * v * (v - 1.0) / (one2 * one2 * one);
      } else {
        return 10;
      }
      if (!(std::isfinite(radial[j]) && std::isfinite(dell[j]))) return 11;
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
      while (j < end[i]) {
        decay(pr[j], pd[j]);
        G += radial[j];
        L += dell[j];
        ++j;
      }
      decay(qr[i], qd[i]);
      const double B = mu[i] * background[s];
      const double H = inclusive ? tr[i] : 0.0;
      const double base = B + n * H;
      const double w = area[s] * weights[i];
      const double e = std::exp(-eta * G);
      const double lost = -std::expm1(-eta * G);
      out[0] += w * base * lost;
      out[1] += w * B * lost;
      out[2] += w * xx[i] * B * lost;
      if (inclusive) {
        out[3] += w * H * lost;
        out[4] += w * n * tr[nt + i] * lost;
        out[5] += w * n * tr[2 * nt + i] * lost;
      }
      out[6] += w * base * e * G;
      out[7] += w * base * e * eta * L;
      out[8] += w * base * e * eta * P;
    }
  }
  for (int k = 0; k < 9; ++k) if (!std::isfinite(out[k])) return 12;
  return 0;
}

API void annular_rows(int rows, int cols, const double* lag, const double* r2,
                      const double* marks, const double* fertility,
                      const double* x, int kernel, int scaled,
                      int need_h, int need_g, int threads, double* out) {
  const double a = x[0], d = x[1], n = x[2], logc = x[3], p = x[4];
  const double logsigma = x[5], alpha = x[6], q = x[7];
  const double eta = x[8], logell = x[9], logpsi = x[10], gamma = x[11];
  const double c = std::exp(logc), psi = std::exp(logpsi);
  const double log10 = std::log(10.0);
  std::vector<double> sigma2(cols), ell2(cols), mag(cols), fert(cols), mk(cols);
  for (int j = 0; j < cols; ++j) {
    const double m = marks[j];
    sigma2[j] = std::exp(2.0 * logsigma + 2.0 * alpha * m);
    ell2[j] = scaled ? std::exp(2.0 * logell + log10 * m) : std::exp(2.0 * logell);
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
