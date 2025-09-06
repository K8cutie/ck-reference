// lib/quality/format.ts
// Tiny, shared numeric helpers for Quality / Six Sigma and reports.

// Clamp a number to [lo, hi]
export function clamp(x: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, x));
}

// Format with locale-aware grouping; default 2 fraction digits.
export function fmt(n: number, frac: number = 2): string {
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: frac,
  }).format(n);
}

// Integer format (no decimals)
export function fmtInt(n: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(n);
}

// Optional convenience: percentage from 0..1
export function fmtPct01(x: number, frac: number = 2): string {
  return `${fmt(x * 100, frac)}%`;
}
