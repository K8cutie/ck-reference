// lib/quality/time.ts
// Date + grain utilities used across Quality / Six Sigma.
// Kept intentionally small and pure for re-use and testing.

export type Grain = "day" | "week" | "month";

/** Strict YYYY-MM-DD */
export const YMD_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Type guard for YYYY-MM-DD strings */
export function isYmd(s: unknown): s is string {
  return typeof s === "string" && YMD_RE.test(s);
}

/** Parse YYYY-MM-DD (or YYYY-MM with day fallback) to a local Date at noon to avoid DST edge cases. */
export function parseISODate(d: string): Date {
  const [y, m, dd] = d.split("-").map((t) => parseInt(t, 10));
  return new Date(y, (m || 1) - 1, dd || 1, 12, 0, 0, 0);
}

/** Add n days (can be negative). */
export function addDays(d: Date, n: number): Date {
  const out = new Date(d);
  out.setDate(out.getDate() + n);
  return out;
}

/** Inclusive day count difference a − b (in days). */
export function daysBetween(a: Date, b: Date): number {
  return Math.floor((a.getTime() - b.getTime()) / (1000 * 60 * 60 * 24));
}

/** Format Date → YYYY-MM-DD (local). */
export function ymd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}

/** Format Date → YYYY-MM (local). */
export function ym(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
}

/** ISO‑8601 week number (Mon‑based), returns {year, week}. */
export function isoWeekYearWeek(d: Date): { year: number; week: number } {
  const tmp = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNr = (tmp.getUTCDay() + 6) % 7; // Monday=0
  tmp.setUTCDate(tmp.getUTCDate() - dayNr + 3);
  const firstThursday = new Date(Date.UTC(tmp.getUTCFullYear(), 0, 4));
  const diff = tmp.getTime() - firstThursday.getTime();
  const week = 1 + Math.round(diff / (7 * 24 * 3600 * 1000));
  return { year: tmp.getUTCFullYear(), week };
}

/** Bucket key for a Date given a grain. */
export function bucketOf(d: Date, grain: Grain): string {
  if (grain === "day") return ymd(d);
  if (grain === "week") {
    const { year, week } = isoWeekYearWeek(d);
    return `${year}-W${String(week).padStart(2, "0")}`;
  }
  return ym(d); // "month"
}

/** Inclusive list of YYYY‑MM months covered by [from, to]. */
export function monthsCovered(from: Date, to: Date): string[] {
  const list: string[] = [];
  const cur = new Date(from.getFullYear(), from.getMonth(), 1);
  const end = new Date(to.getFullYear(), to.getMonth(), 1);
  while (cur <= end) {
    list.push(ym(cur));
    cur.setMonth(cur.getMonth() + 1);
  }
  return list;
}
