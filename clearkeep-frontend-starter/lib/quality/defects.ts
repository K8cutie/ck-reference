/**
 * ClearKeep — Quality defect rules (single source of truth)
 *
 * This module centralizes how a journal entry "unit" becomes a defect for Six Sigma views.
 * It intentionally has **no** runtime side‑effects and can be unit‑tested in isolation.
 *
 * NOTE: Step 4A — add this file only. In the next step, the Six Sigma page will delegate
 * its local `unitsAndDefects` logic to the functions here.
 */

export type DefectType = "unposted_sla" | "reversal" | "reopened_month";

/** Minimal shape the page already has for units (FactEntry) */
export type UnitLike = {
  id: string | number;
  date: string;            // YYYY-MM-DD
  is_locked: boolean;      // posted or not
  source_module?: string | null; // "reversal" for reworks
  bucket?: string;         // e.g., YYYY-MM (optional but useful)
};

export type ClassifyOpts = {
  /** SLA in days: if an entry remains unposted beyond this many days, it's a defect */
  slaDays: number;
  /** Whether to treat reversals as defects */
  includeReversals?: boolean;
  /** Whether to mark reopened/reclosed months as defects */
  includeReopenedMonths?: boolean;
  /** Months like "YYYY-MM" that were reopened/reclosed during the analysis window */
  reopenedMonths?: Set<string>;
  /** Clock to use for aging; defaults to new Date() in the caller's tz */
  today?: Date;
};

/** Utility: integer day difference (caller ensures tz expectations) */
export function daysBetween(a: Date, b: Date): number {
  const ms = a.getTime() - b.getTime();
  return Math.floor(ms / 86400000); // 24*60*60*1000
}

export function ymFromYmd(ymd: string): string {
  // expects YYYY-MM-DD; returns YYYY-MM; safe fallback if malformed
  if (typeof ymd === "string" && ymd.length >= 7) return ymd.slice(0, 7);
  return "";
}

/** Decide a single defect label for a unit; returns null if not defective */
export function classifyDefect(unit: UnitLike, opts: ClassifyOpts): DefectType | null {
  const today = opts.today ?? new Date();
  const includeReversals = !!opts.includeReversals;
  const includeReopened = !!opts.includeReopenedMonths;
  const reopened = opts.reopenedMonths ?? new Set<string>();

  // 1) Unposted beyond SLA days
  if (!unit.is_locked) {
    const dt = new Date(unit.date);
    const age = daysBetween(today, dt);
    if (age > opts.slaDays) return "unposted_sla";
  }

  // 2) Reversal counted as a defect (optional)
  const src = (unit.source_module || "").toLowerCase();
  if (includeReversals && src.includes("reversal")) return "reversal";

  // 3) Month reopened/reclosed (optional, by bucket or by date→YYYY-MM)
  if (includeReopened) {
    const ym = unit.bucket || ymFromYmd(unit.date);
    if (ym && reopened.has(ym)) return "reopened_month";
  }

  return null;
}

export type CountResult = {
  defects: number;
  defectiveIds: Set<string | number>;
  byType: Record<DefectType, number>;
};

/** Tally defects across a list of units; each unit counts at most once */
export function countDefects(units: UnitLike[], opts: ClassifyOpts): CountResult {
  const defectiveIds = new Set<string | number>();
  const byType: Record<DefectType, number> = {
    unposted_sla: 0,
    reversal: 0,
    reopened_month: 0,
  };

  for (const u of units) {
    const t = classifyDefect(u, opts);
    if (t && !defectiveIds.has(u.id)) {
      defectiveIds.add(u.id);
      byType[t] += 1;
    }
  }

  return { defects: defectiveIds.size, defectiveIds, byType };
}
