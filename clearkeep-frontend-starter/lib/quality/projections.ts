/**
 * ClearKeep — Financial Projections (pure helpers)
 *
 * Pure, side-effect-free functions for projecting a Receipts Matrix into a
 * Budget/Forecast and comparing matrices. Works with the ReceiptMatrix shape
 * from lib/quality/selectors.ts.
 *
 * Design goals:
 *  - Deterministic, easily unit-testable
 *  - No fetches, no UI, no dates dependency beyond "YYYY-MM" strings
 *  - Can be extended later (drivers, CPI sources, goal-seek with constraints)
 */

import type {
  ReceiptMatrix,
  ReceiptMatrixRow,
} from "./selectors";

/** Rounding modes for neat budgets */
export type RoundingMode = "none" | "nearest10" | "nearest100" | "nearest1000";

/** Parameters controlling projection */
export type ProjectionParams = {
  /** Global uplift applied to ALL cells (e.g., 0.05 = +5%) */
  globalPct?: number;
  /**
   * Per-category uplift (overrides/compounds with global). Keys must match
   * ReceiptMatrixRow.key for top-level category rows (e.g., "mass", "stole", ...).
   */
  perCategoryPct?: Record<string, number>;
  /**
   * Monthly seasonality factors, length = 12, January..December (e.g., 1.00, 0.95, 1.10, ...).
   * If missing or wrong length, treated as all 1.0.
   */
  monthlyFactors?: number[];
  /**
   * Inflation applied at the very end (after uplifts & monthly factors).
   * (e.g., 0.03 = +3% CPI).
   */
  inflationPct?: number;
  /**
   * If true, compounding applies month-over-month using prior projected month as the base
   * (only within the month’s seasonal chain). Default false (flat from actuals).
   */
  compounding?: boolean;
  /** Optional rounding for budget neatness. */
  rounding?: RoundingMode;
};

/** Result of comparing two matrices (B minus A) */
export type VarianceMatrix = {
  months: string[];
  rows: Array<{
    key: string;
    label: string;
    abs: number[];     // B - A
    pct: number[];     // (B - A) / |A|, 0 when A=0
    totalAbs: number;  // sum(abs) over months for row
    totalPct: number;  // (sum_B - sum_A) / |sum_A|
    children?: VarianceMatrix["rows"][number]["children"];
  }>;
  colAbs: number[];    // column totals delta (B - A)
  grandAbs: number;    // grand total delta
};

/** Convenience: safe rounder */
function roundValue(v: number, mode: RoundingMode = "none"): number {
  if (!isFinite(v)) return 0;
  switch (mode) {
    case "nearest10":   return Math.round(v / 10) * 10;
    case "nearest100":  return Math.round(v / 100) * 100;
    case "nearest1000": return Math.round(v / 1000) * 1000;
    default:            return v;
  }
}

/** Normalize a 12-vector of monthly factors (fallback to all 1s) */
function normalizeMonthlyFactors(f?: number[]): number[] {
  if (!Array.isArray(f) || f.length !== 12) return new Array(12).fill(1);
  return f.map((x) => (isFinite(x) && x > 0 ? x : 1));
}

/** Extract month index (0..11) from "YYYY-MM"; fallback 0 if malformed */
function monthIndex(ym: string): number {
  const m = Number(ym.slice(5, 7));
  return isFinite(m) && m >= 1 && m <= 12 ? m - 1 : 0;
}

/** Project a single row (and optional children) for a given month index */
function projectCell(
  base: number,
  catKey: string,
  mIdx: number,
  p: ProjectionParams
): number {
  const g = p.globalPct ?? 0;
  const c = (p.perCategoryPct && isFinite(p.perCategoryPct[catKey]) ? p.perCategoryPct[catKey] : 0) || 0;
  const monthFactors = normalizeMonthlyFactors(p.monthlyFactors);
  const mf = monthFactors[mIdx] ?? 1;
  const infl = p.inflationPct ?? 0;

  // Order of application: base → global → per-category → monthly → inflation
  // (all multiplicative: v * (1+g) * (1+c) * mf * (1+infl))
  const projected = base * (1 + g) * (1 + c) * mf * (1 + infl);
  return projected;
}

/**
 * Project a ReceiptMatrix into a Budget/Forecast using ProjectionParams.
 * - Keeps the same category structure and months by default.
 * - If compounding=true, we apply (1+uplifts)*factor cumulated per month relative to the previous month’s *projected* value.
 */
export function projectReceipts(
  base: ReceiptMatrix,
  params: ProjectionParams
): ReceiptMatrix {
  const months = base.months.slice(); // keep same months; year-shift can be handled upstream if desired
  const mFactors = normalizeMonthlyFactors(params.monthlyFactors);

  // Helper to deep-project a row (with optional compounding)
  const projectRow = (row: ReceiptMatrixRow): ReceiptMatrixRow => {
    const values: number[] = new Array(months.length).fill(0);

    if (params.compounding) {
      // Start from first month, compounding on projected value
      for (let j = 0; j < months.length; j++) {
        const mIdx = monthIndex(months[j]);
        const baseVal = j === 0 ? row.values[0] : values[j - 1]; // previous projected month if compounding
        values[j] = roundValue(
          projectCell(baseVal, row.key, mIdx, params),
          params.rounding ?? "none"
        );
      }
    } else {
      // Flat off actuals
      for (let j = 0; j < months.length; j++) {
        const mIdx = monthIndex(months[j]);
        const baseVal = row.values[j] ?? 0;
        values[j] = roundValue(
          projectCell(baseVal, row.key, mIdx, params),
          params.rounding ?? "none"
        );
      }
    }

    const children = row.children?.map(projectRow);
    const total = values.reduce((s, v) => s + v, 0) + (children?.reduce((s, c) => s + c.total, 0) || 0);

    return {
      key: row.key,
      label: row.label,
      values,
      total,
      children,
    };
  };

  // Project all rows
  const rows = base.rows.map(projectRow);

  // Column totals & grand total
  const colTotals = months.map((_, j) =>
    rows.reduce((s, r) => s + r.values[j], 0)
  );
  const grandTotal = colTotals.reduce((s, v) => s + v, 0);

  return { months, rows, colTotals, grandTotal };
}

/**
 * Compare two matrices (B - A). Assumes same row structure and months.
 * If the shape differs, we attempt a best-effort alignment by row.key and month label.
 */
export function compareMatrices(A: ReceiptMatrix, B: ReceiptMatrix): VarianceMatrix {
  // Align month list
  const months = Array.from(new Set<string>([...A.months, ...B.months])).sort();

  // Build month index maps
  const idxA = new Map(A.months.map((m, i) => [m, i]));
  const idxB = new Map(B.months.map((m, i) => [m, i]));

  // Row maps by key for fast lookup
  const mapRows = (rows: ReceiptMatrixRow[]) => {
    const m = new Map<string, ReceiptMatrixRow>();
    const walk = (r: ReceiptMatrixRow) => {
      m.set(r.key, r);
      r.children?.forEach(walk);
    };
    rows.forEach(walk);
    return m;
  };
  const mapA = mapRows(A.rows);
  const mapB = mapRows(B.rows);

  const allKeys = Array.from(new Set<string>([...mapA.keys(), ...mapB.keys()]));
  const rows = allKeys.map((key) => {
    const ra = mapA.get(key);
    const rb = mapB.get(key);
    const label = rb?.label ?? ra?.label ?? key;

    const abs: number[] = months.map((m) => {
      const a = ra ? (ra.values[idxA.get(m) ?? -1] ?? 0) : 0;
      const b = rb ? (rb.values[idxB.get(m) ?? -1] ?? 0) : 0;
      return b - a;
    });
    const suma = ra ? ra.values.reduce((s, v) => s + v, 0) : 0;
    const sumb = rb ? rb.values.reduce((s, v) => s + v, 0) : 0;
    const totalAbs = sumb - suma;
    const totalPct = suma !== 0 ? totalAbs / Math.abs(suma) : 0;

    return { key, label, abs, pct: abs.map((v, i) => {
      const a = ra ? (ra.values[idxA.get(months[i]) ?? -1] ?? 0) : 0;
      return a !== 0 ? v / Math.abs(a) : 0;
    }), totalAbs, totalPct };
  });

  // Column/Grand totals deltas
  const colAbs = months.map((m, i) => rows.reduce((s, r) => s + r.abs[i], 0));
  const grandAbs = colAbs.reduce((s, v) => s + v, 0);

  return { months, rows, colAbs, grandAbs };
}

/**
 * Goal-seek: find a global uplift to hit a target grand total for the projection,
 * keeping perCategoryPct / monthlyFactors / inflation fixed.
 * Binary-search between [-50%, +200%] by default.
 */
export function goalSeekGlobal(
  base: ReceiptMatrix,
  params: Omit<ProjectionParams, "globalPct">,
  targetGrandTotal: number,
  bounds: { lo?: number; hi?: number } = {}
): { globalPct: number; projected: ReceiptMatrix } {
  const lo = bounds.lo ?? -0.5;  // -50%
  const hi = bounds.hi ?? 2.0;   // +200%
  let L = lo, R = hi;

  for (let iter = 0; iter < 40; iter++) {
    const mid = (L + R) / 2;
    const projected = projectReceipts(base, { ...params, globalPct: mid });
    const diff = projected.grandTotal - targetGrandTotal;
    if (Math.abs(diff) <= 1e-2) return { globalPct: mid, projected };
    if (diff < 0) L = mid; else R = mid;
  }

  const projected = projectReceipts(base, { ...params, globalPct: R });
  return { globalPct: R, projected };
}
