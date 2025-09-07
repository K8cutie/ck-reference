/**
 * ClearKeep — Accounting helpers (single source of truth)
 *
 * Purpose:
 *  - One place for account classification + domain logic used by the Six Sigma page
 *  - Avoid drift between page.tsx and AccountsFilter.tsx
 *
 * This file is **pure** (no runtime side‑effects) and safe to add without imports yet.
 * Step 2 will switch consumers to import from here.
 */

// ===== Types kept here so consumers share one definition =====
export type Grain = "day" | "week" | "month";
export type Domain = "expense" | "revenue" | "all";

export type AccountLite = {
  id: number | string;
  name?: string;
  code?: string;
  /** Preferred semantic field from backend */
  type?: string | null;
  /** Fallbacks seen in various payloads */
  account_type?: string | null;
  kind?: string | null;
  group?: string | null;
};

/** Canonical GL type used across UI logic */
export type CanonicalType = "asset" | "liability" | "equity" | "revenue" | "expense" | "other";

// ===== Normalization helpers =====
function norm(s: unknown): string {
  return (s ?? "").toString().trim().toLowerCase();
}

/**
 * Map heterogeneous backend labels (type/account_type/kind/group) to a canonical type.
 * Heuristics mirror the existing inline logic in page.tsx & AccountsFilter.tsx.
 */
export function accountType(a?: AccountLite): CanonicalType {
  if (!a) return "other";
  const t = norm(a.type || a.account_type || a.kind || a.group);
  if (!t) return "other";

  // P&L buckets
  if (t.includes("expens")) return "expense";              // expense, expenses
  if (t.includes("revenue") || t.includes("income") || t === "sales") return "revenue";

  // Balance sheet buckets
  if (t.includes("asset")) return "asset";
  if (t.includes("liabil")) return "liability";
  if (t.includes("equity") || t === "capital") return "equity";

  return (t as CanonicalType) || "other";
}

export function isExpense(a?: AccountLite): boolean { return accountType(a) === "expense"; }
export function isRevenue(a?: AccountLite): boolean { return accountType(a) === "revenue"; }
export function isPnL(a?: AccountLite): boolean {
  const t = accountType(a); return t === "expense" || t === "revenue";
}
export function isBalanceSheet(a?: AccountLite): boolean {
  const t = accountType(a); return t === "asset" || t === "liability" || t === "equity";
}

/** Convenience: does a given canonical type pass the selected Domain filter? */
export function includedByDomain(canon: CanonicalType, domain: Domain): boolean {
  if (domain === "all") return canon === "expense" || canon === "revenue"; // Only P&L for Six Sigma views
  return canon === domain;
}

// ===== Amount signing (centralized) =====
export type LineLike = { debit?: number | null; credit?: number | null };

/**
 * Signed amount consistent with page logic:
 *  - Expense = debit − credit
 *  - Revenue = credit − debit
 *  - Domain "all": apply the rule by the account's canonical type; non‑P&L → 0
 */
export function signedAmountForDomain(line: LineLike, account: AccountLite | undefined, domain: Domain): number {
  const debit = Number(line?.debit ?? 0);
  const credit = Number(line?.credit ?? 0);
  const t = accountType(account);

  if (domain === "expense") return t === "expense" ? (debit - credit) : 0;
  if (domain === "revenue") return t === "revenue" ? (credit - debit) : 0;
  // domain === "all": restrict to P&L only
  if (t === "expense") return debit - credit;
  if (t === "revenue") return credit - debit;
  return 0;
}

// ===== UI helpers =====
export function displayName(a?: AccountLite): string {
  if (!a) return "Unknown";
  const code = a.code ? `${a.code} — ` : "";
  const name = a.name || (a.id != null ? `Account ${String(a.id)}` : "Unknown");
  return code + name;
}

/** Stable key that tolerates partial payloads */
export function accountKey(a?: AccountLite): string {
  if (!a) return "unknown";
  return String(a.id ?? a.code ?? a.name ?? "unknown");
}
