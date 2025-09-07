/**
 * ClearKeep — Quality Selectors (pure helpers)
 *
 * Centralize heavy, pure computations used by the Six Sigma & Finance views:
 * - buildFacts(): normalize journal entries into lines/units/buckets
 * - buildAccountBreakdown(): aggregate totals by account for Pareto/table
 * - buildReceiptsMatrix(): aggregate totals by category x month (Financial Analysis)
 *
 * No side effects. Safe to unit-test.
 */

import { bucketOf, parseISODate, addDays, monthsCovered } from "./time";
import {
  accountType as canonicalAccountType,
  signedAmountForDomain,
  type Domain,
  type Grain,
} from "./accounting";

/** Basic shapes (kept minimal for interop) */
export type Range = { from: string; to: string }; // YYYY-MM-DD inclusive

export type Account = {
  id: number | string;
  code?: string | null;
  name?: string | null;
  type?: string | null;
  account_type?: string | null;
  kind?: string | null;
  group?: string | null;
};

export type JournalLine = {
  account_id?: number | string | null;
  account_code?: string | null;
  account_name?: string | null;
  debit?: number | null;
  credit?: number | null;
};

export type JournalEntry = {
  id: number | string;
  entry_date: string;          // YYYY-MM-DD
  is_locked?: boolean;         // may be omitted by API
  locked_at?: string | null;
  posted_at?: string | null;
  posted_by_user_id?: number | null;
  source_module?: string | null;
  lines?: JournalLine[];
};

export type FactLine = {
  date: string;
  account_id?: number | string | null;
  account_code?: string | null;
  account_name?: string | null;
  amount: number;
  bucket: string;              // label per-grain (YYYY-MM for month, etc.)
};

export type FactEntry = {
  id: number | string;
  date: string;
  bucket: string;
  is_locked: boolean;
  source_module?: string | null;
};

export type Facts = {
  lines: FactLine[];
  units: FactEntry[];
  buckets: string[];
};

/** Options for buildFacts */
export type BuildFactsOpts = {
  entries: JournalEntry[] | null;
  accounts: Account[] | null;
  domain: Domain;
  grain: Grain;
  range: Range;
  /** Apply global account selection when set */
  selectedSet?: Set<string>;
};

/** Robust posted/locked detection from a JE record */
function isLockedFrom(je: JournalEntry): boolean {
  if (Object.prototype.hasOwnProperty.call(je as any, "is_locked")) {
    return !!(je as any).is_locked;
  }
  return !!(je.locked_at || je.posted_at || je.posted_by_user_id);
}

/**
 * Normalize journal into Facts (pure)
 * - Applies global account selection (selectedSet) if provided
 * - Uses signedAmountForDomain() to compute signed amounts by domain
 * - Buckets by grain (day/week/month)
 */
export function buildFacts(opts: BuildFactsOpts): Facts {
  const { entries, accounts, domain, grain, range, selectedSet } = opts;

  const acctMap: Map<string | number, Account> = new Map();
  (accounts || []).forEach(a => acctMap.set(a.id, a));

  const start = parseISODate(range.from);
  const end = parseISODate(range.to);

  const lines: FactLine[] = [];
  const units: FactEntry[] = [];
  const unitSeen = new Set<string | number>();

  const buck = (ds: string) => bucketOf(parseISODate(ds), grain);

  for (const e of entries || []) {
    let touched = false;
    const bkey = buck(e.entry_date);
    const isLocked = isLockedFrom(e);

    for (const ln of e.lines || []) {
      // Apply global account selection when any account is selected
      if (selectedSet && selectedSet.size > 0 && !selectedSet.has(String(ln.account_id))) continue;

      const acc = acctMap.get((ln.account_id as any) ?? "");
      const amt = signedAmountForDomain(ln as any, acc as any, domain);
      if (domain !== "all" && amt === 0) continue;

      lines.push({
        date: e.entry_date,
        account_id: ln.account_id ?? null,
        account_code: ln.account_code ?? (acc?.code ?? null),
        account_name: ln.account_name ?? (acc?.name ?? null),
        amount: amt,
        bucket: bkey,
      });
      touched = true;
    }

    if (touched && !unitSeen.has(e.id)) {
      units.push({
        id: e.id,
        date: e.entry_date,
        bucket: bkey,
        is_locked: isLocked,
        source_module: e.source_module || null,
      });
      unitSeen.add(e.id);
    }
  }

  // Build bucket labels for the chosen grain
  const buckets: string[] = [];
  if (grain === "day") {
    for (let d = new Date(start); d <= end; d = addDays(d, 1)) {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      buckets.push(`${y}-${m}-${day}`);
    }
  } else if (grain === "month") {
    buckets.push(...monthsCovered(start, end));
  } else {
    // week: unique week tokens from bucketOf()
    const s = new Set<string>();
    for (let d = new Date(start); d <= end; d = addDays(d, 1)) s.add(bucketOf(d, "week"));
    buckets.push(...Array.from(s).sort());
  }

  return { lines, units, buckets };
}

/**
 * Aggregate totals by account for Pareto/table displays.
 * Returns sorted rows (descending by |total|).
 */
export function buildAccountBreakdown(
  lines: FactLine[],
  acctMap: Map<string | number, Account>
): Array<{ key: string | number; code: string; name: string; type: string; total: number }> {
  const keyOf = (ln: FactLine) => (ln.account_id as any) ?? ln.account_code ?? ln.account_name ?? "unknown";

  const sums = new Map<any, number>();
  for (const ln of lines) {
    const k = keyOf(ln);
    sums.set(k, (sums.get(k) || 0) + ln.amount);
  }

  const rows = Array.from(sums.entries()).map(([k, v]) => {
    const a = acctMap.get(k);
    const code = (a?.code ?? (typeof k === "string" ? "" : "")) || "";
       const name = (a?.name ?? (typeof k === "string" ? String(k) : `Account ${String(k)}`)) || "";
    const type = canonicalAccountType(a as any);
    return { key: k, code, name, type, total: v as number };
  });

  rows.sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
  return rows;
}

/* =======================================================================
 * Financial Analysis — Receipts Matrix (category x month)
 * ======================================================================= */

/** Category matching rules (any of these can hit) */
export type CategoryRule = {
  key: string;                // machine key
  label: string;              // human label
  account_ids?: Array<string | number>;
  code_prefixes?: string[];   // e.g., ["4", "400"]
  name_includes?: string[];   // e.g., ["Mass", "Collection"]
};

export type ReceiptMatrixRow = {
  key: string;
  label: string;
  values: number[];           // by month
  total: number;
  children?: ReceiptMatrixRow[];
};

export type ReceiptMatrix = {
  months: string[];
  rows: ReceiptMatrixRow[];
  colTotals: number[];
  grandTotal: number;
};

export type BuildReceiptsMatrixOpts = {
  entries: JournalEntry[] | null;
  accounts: Account[] | null;
  domain: Domain;                     // typically "revenue"
  range: Range;                       // YYYY-MM-DD
  selectedSet?: Set<string>;          // account filter
  categories: CategoryRule[];         // mapping
  includeUnmapped?: boolean;          // include an "Other Receipts" bucket
  showAccountsAsChildren?: boolean;   // nested sub-rows per account
};

function categorize(
  rules: CategoryRule[],
  line: JournalLine,
  acc: Account | undefined
): string {
  // 1) explicit account id matches
  for (const r of rules) {
    if (r.account_ids && line.account_id != null && r.account_ids.includes(line.account_id)) return r.key;
  }
  // 2) code prefixes
  const code = (line.account_code || acc?.code || "").toString();
  if (code) {
    for (const r of rules) {
      if (r.code_prefixes?.some(p => code.startsWith(p))) return r.key;
    }
  }
  // 3) name includes
  const name = (line.account_name || acc?.name || "").toString().toLowerCase();
  if (name) {
    for (const r of rules) {
      if (r.name_includes?.some(tok => name.includes(tok.toLowerCase()))) return r.key;
    }
  }
  return "";
}

/**
 * Build Receipts Matrix (pure)
 * - Totals amounts by category per month (range inferred to months[])
 * - Optional nested subrows (accounts) under each category
 * - Optional "Other Receipts" bucket
 */
export function buildReceiptsMatrix(opts: BuildReceiptsMatrixOpts): ReceiptMatrix {
  const {
    entries, accounts, domain, range, selectedSet,
    categories, includeUnmapped = true, showAccountsAsChildren = false,
  } = opts;

  const acctMap: Map<string | number, Account> = new Map();
  (accounts || []).forEach(a => acctMap.set(a.id, a));

  // Build months (always month grain here)
  const months = monthsCovered(parseISODate(range.from), parseISODate(range.to));
  const monthIndex = new Map<string, number>();
  months.forEach((m, i) => monthIndex.set(m, i));

  // Template for rows
  const catByKey = new Map<string, ReceiptMatrixRow>();
  const rows: ReceiptMatrixRow[] = [];
  for (const r of categories) {
    const row: ReceiptMatrixRow = { key: r.key, label: r.label, values: months.map(() => 0), total: 0 };
    catByKey.set(r.key, row);
    rows.push(row);
  }
  let other: ReceiptMatrixRow | null = includeUnmapped
    ? { key: "_other", label: "Other Receipts", values: months.map(() => 0), total: 0 }
    : null;

  // Optionally prepare children maps
  const childMap: Map<string, Map<string | number, ReceiptMatrixRow>> = new Map();
  if (showAccountsAsChildren) {
    for (const r of categories) childMap.set(r.key, new Map());
    if (other) childMap.set(other.key, new Map());
  }

  // Iterate entries -> lines
  for (const e of (entries || [])) {
    for (const ln of e.lines || []) {
      // filter by selected
      if (selectedSet && selectedSet.size > 0 && !selectedSet.has(String(ln.account_id))) continue;

      const acc = acctMap.get((ln.account_id as any) ?? "");
      const amt = signedAmountForDomain(ln as any, acc as any, domain);
      if (amt === 0) continue;

      // use entry date month as bucket
      const ym = (e.entry_date || "").slice(0, 7);
      const idx = monthIndex.get(ym);
      if (idx === undefined) continue;

      // categorize
      const key = categorize(categories, ln, acc);
      let row = key ? catByKey.get(key) || null : null;
      if (!row) row = other;

      if (!row) continue; // unmapped but not including "other"

      row.values[idx] += amt;
      row.total += amt;

      // children rows per account (optional)
      if (showAccountsAsChildren) {
        const cmap = childMap.get(row.key)!;
        const akey = (ln.account_id as any) ?? ln.account_code ?? ln.account_name ?? "unknown";
        let crow = cmap.get(akey);
        if (!crow) {
          const code = ln.account_code || acc?.code || "";
          const name = ln.account_name || acc?.name || (code ? `Account ${code}` : "Unknown");
          crow = { key: String(akey), label: (code ? `${code} — ` : "") + name, values: months.map(() => 0), total: 0 };
          cmap.set(akey, crow);
          if (!row.children) row.children = [];
          row.children.push(crow);
        }
        crow.values[idx] += amt;
        crow.total += amt;
      }
    }
  }

  // If "other" exists and has data, append it
  if (other && (other.total !== 0 || other.values.some(v => v !== 0))) {
    rows.push(other);
  }

  // Column totals
  const colTotals = months.map((_, j) => rows.reduce((s, r) => s + r.values[j], 0));
  const grandTotal = colTotals.reduce((s, v) => s + v, 0);

  // Sort rows by absolute total (desc), keep children order by total
  rows.sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
  for (const r of rows) {
    if (r.children) r.children.sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
  }

  return { months, rows, colTotals, grandTotal };
}
