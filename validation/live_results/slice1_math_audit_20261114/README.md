# Slice 1 Mathematical Audit Supplement — 14 November 2026

This directory is additive. It does not replace any sealed JSON authority.
The pre-existing files under `validation/authorities/` and
`validation/live_results/` remain byte-for-byte unchanged; the pre-change
hashes are in `validation/slice1_prechange_snapshot_20261114.json`.

## Confirmed defect

The F6 display

\[
C_T^{\mathrm{tight}}
=\int_0^T\frac{\Phi_{195}(u)^2}
{B_{\min}/B_{\max}^2+n h_{195}(u)}\,\dif u
\]

added \(B_{\min}/B_{\max}^2\) (units: days) to \(n h_{195}(u)\)
(units: inverse days). The coefficient
\(K_T^{\mathrm{tight}}=B_{\max}^2C_T^{\mathrm{tight}}m\mathcal B/[n(1-n)]\)
also restored \(B_{\max}^2\) a second time. The display and its derived
values are withdrawn.

## Corrected values

| Quantity | Corrected value |
|---|---:|
| \(C_T\) (implemented 195-mode) | \(2.8662509\times10^6\ \mathrm{days}^2\) |
| \(m=\E[g(Q)^2/\kappa(Q)]\) | \(0.21606515\) |
| \(\mathcal B\) | \(383.34958\) |
| \(K_T\) (full process) | \(3.6644466\times10^5\) |
| Full-process clipped threshold \(\sqrt{2/K_T}\) | \(2.3362\times10^{-3}\) |
| One-event \(K_1\) | \(0.2416084\) |
| \(\sqrt{K_1/2}\) | \(0.3475690\) |
| One-event linear threshold | \(2.8771\) |
| One-event clipped threshold | \(4.6419\) |
| One-event bound at \(\eta=0.10\) | \(0.0015266\) |
| One-event bound at \(\eta=0.178\) | \(0.0042328\) |
| One-event bound at \(\eta=1.65\) | \(0.1867405\) |
| One-event bound at \(\eta=4\) | \(0.7883534\) |

The one-event bound is not a full-process multi-event bound. The full-process
finite quadratic bound remains \(K_T\) and remains vacuous above
\(\eta=2.3362\times10^{-3}\).

## Files

| File | Content |
|---|---|
| `summary.json` | Top-level audit result, counts, defect, corrections. |
| `visibility_correction.json` | Corrected visibility values and withdrawn legacy values. |
| `dimensional_audit.json` | Symbolic unit check of the invalid and corrected denominators. |
| `symbolic_algebra.json` | Population balance, Cauchy–Schwarz, mark moment and amplitude curvature. |
| `chapter2_models.json` | Productivity, mixture and spatial-kernel checks. |
| `chapter3_stability.json` | 195-mode constants, \(t_0\), slow modes and Doeblin certificate. |
| `chapter4_identifiability.json` | Survival, finite-mixture scale and regional Jensen checks. |
| `chapter5_moments.json` | Exponential-mark moment rows and divergence thresholds. |
| `chapter5_inference.json` | Score bracket, positive-\(\eta\) envelope and Gram residuals. |
| `appendix_a_custody.json` | Label/reference resolution and score-field authority presence. |
| `sealed_authority_integrity.json` | 710/710 pre-existing sealed JSON files unchanged. |
| `manuscript_binding_audit.json` | New displays present; withdrawn displays absent. |
| `code_consistency.json` | `stability.py --verify` and `moments.py --check` results. |

## Reproduction

```powershell
python -B scripts/check_mathematics.py --output build/mathematics.json
python -B experiments/methodological_audit/slice1_math_audit_20261114.py --output validation/live_results/slice1_math_audit_20261114
```

The full report is `docs/reviews/slice1_math_audit_20261114.md`; the
acceptance record is `validation/slice1_math_remediation_20261114.json`.
