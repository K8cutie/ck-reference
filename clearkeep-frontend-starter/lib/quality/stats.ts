/**
 * ClearKeep — Quality Stats (pure helpers)
 *
 * Central place for statistical helpers used by Six Sigma views.
 * Keep this file side-effect-free for easy testing.
 */

/** Clamp without depending on UI helpers */
function clamp01(x: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, x));
}

/** Acklam inverse normal CDF approximation (balanced parentheses) */
export function invNorm(p: number): number {
  const a = [
    -39.69683028665376,
    220.9460984245205,
    -275.9285104469687,
    138.357751867269,
    -30.66479806614716,
    2.506628277459239,
  ];
  const b = [
    -54.47609879822406,
    161.5858368580409,
    -155.6989798598866,
    66.80131188771972,
    -13.28068155288572,
  ];
  const c = [
    -0.007784894002430293,
    -0.3223964580411365,
    -2.400758277161838,
    -2.549732539343734,
    4.374664141464968,
    2.938163982698783,
  ];
  const d = [
    0.007784695709041462,
    0.3224671290700398,
    2.445134137142996,
    3.754408661907416,
  ];

  const plow = 0.02425;
  const phigh = 1 - plow;
  let q: number, r: number;

  if (p < plow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }

  if (phigh < p) {
    q = Math.sqrt(-2 * Math.log(1 - p));
    return -(
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }

  q = p - 0.5;
  r = q * q;
  return (
    (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + 1))
  );
}

/** Long-term sigma convention: σ = Φ⁻¹(yield) + 1.5 */
export function sigmaFromYield(yield_: number): number {
  return invNorm(clamp01(yield_, 1e-12, 1 - 1e-12)) + 1.5;
}
