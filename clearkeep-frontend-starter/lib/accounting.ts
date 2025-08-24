// clearkeep-frontend-starter/lib/accounting.ts
// Frontend client for GL Accounts, Journal, and Books export.
// Uses NEXT_PUBLIC_API_BASE (defaults to http://localhost:8000).

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/+$/, "") || "http://localhost:8000";

/* =========================
 * Types
 * =======================*/
export type GLAccountType = "asset" | "liability" | "equity" | "income" | "expense";
export type NormalSide = "debit" | "credit";

export interface GLAccount {
  id: number;
  code: string;
  name: string;
  type: GLAccountType;
  normal_side: NormalSide;
  is_cash: boolean;
  description?: string | null;
  is_active: boolean;
  created_at: string; // ISO
  updated_at: string; // ISO
}

export interface JournalLine {
  id: number;
  entry_id: number;
  account_id: number;
  description?: string | null;
  debit: number;
  credit: number;
  line_no: number;
  created_at: string;
  updated_at: string;
}

export interface JournalEntry {
  id: number;
  entry_no: number;
  entry_date: string; // YYYY-MM-DD
  memo?: string | null;
  currency_code: string;
  reference_no?: string | null;
  source_module?: string | null;
  source_id?: string | null;
  is_locked: boolean;
  posted_at?: string | null;
  created_by_user_id?: number | null;
  posted_by_user_id?: number | null;
  locked_at?: string | null;
  created_at: string;
  updated_at: string;
  lines: JournalLine[];
  total_debits?: number;
  total_credits?: number;
  is_balanced?: boolean;
}

export type BooksViewKey =
  | "general_journal"
  | "general_ledger"
  | "cash_receipts_book"
  | "cash_disbursements_book";

/* =========================
 * Helpers
 * =======================*/
async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if ((body as any)?.detail) msg = (body as any).detail as string;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

function n(x: unknown): number {
  // coerce backend decimal-as-string or number to number
  if (typeof x === "number") return x;
  if (typeof x === "string") return Number(x);
  return 0;
}

/* =========================
 * GL Accounts
 * =======================*/
export async function listGLAccounts(params?: {
  q?: string;
  type?: GLAccountType;
  is_active?: boolean;
  is_cash?: boolean;
  limit?: number;
  offset?: number;
}): Promise<GLAccount[]> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.type) qs.set("type", params.type);
  if (typeof params?.is_active === "boolean") qs.set("is_active", String(params.is_active));
  if (typeof params?.is_cash === "boolean") qs.set("is_cash", String(params.is_cash));
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  return fetchJSON<GLAccount[]>(`/gl/accounts${query}`);
}

export async function createGLAccount(payload: {
  code: string;
  name: string;
  type: GLAccountType;
  normal_side: NormalSide;
  is_cash?: boolean;
  description?: string | null;
}): Promise<GLAccount> {
  return fetchJSON<GLAccount>(`/gl/accounts`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/* =========================
 * Journal Entries
 * =======================*/
export async function listJournalEntries(params?: {
  date_from?: string; // YYYY-MM-DD
  date_to?: string;   // YYYY-MM-DD
  reference_no?: string;
  source_module?: string;
  is_locked?: boolean;
  limit?: number;
  offset?: number;
}): Promise<JournalEntry[]> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  if (params?.reference_no) qs.set("reference_no", params.reference_no);
  if (params?.source_module) qs.set("source_module", params.source_module);
  if (typeof params?.is_locked === "boolean") qs.set("is_locked", String(params.is_locked));
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString() ? `?${qs}` : "";
  const entries = await fetchJSON<JournalEntry[]>(`/gl/journal${query}`);
  // normalize numbers just in case
  return entries.map((e) => ({
    ...e,
    total_debits: n(e.total_debits),
    total_credits: n(e.total_credits),
    lines: e.lines?.map((l) => ({ ...l, debit: n(l.debit), credit: n(l.credit) })) || [],
  }));
}

export async function createJournalEntry(payload: {
  entry_date: string; // YYYY-MM-DD
  memo?: string | null;
  currency_code?: string;
  reference_no?: string | null;
  source_module?: string | null;
  source_id?: string | null;
  lines: Array<{
    account_id: number;
    description?: string | null;
    debit?: number;
    credit?: number;
    line_no?: number;
  }>;
}): Promise<JournalEntry> {
  const je = await fetchJSON<JournalEntry>(`/gl/journal`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return {
    ...je,
    total_debits: n(je.total_debits),
    total_credits: n(je.total_credits),
    lines: je.lines?.map((l) => ({ ...l, debit: n(l.debit), credit: n(l.credit) })) || [],
  };
}

export async function postJournalEntry(jeId: number): Promise<JournalEntry> {
  return fetchJSON<JournalEntry>(`/gl/journal/${jeId}/post`, { method: "POST" });
}

/* =========================
 * Books (views + export)
 * =======================*/
export async function getBooksView(
  viewKey: BooksViewKey,
  params?: { date_from?: string; date_to?: string }
): Promise<{ view: BooksViewKey; count: number; rows: any[] }> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";
  return fetchJSON(`/compliance/books/view/${viewKey}${query}`);
}

export async function downloadBooksZip(params?: {
  date_from?: string;
  date_to?: string;
  filename?: string;
}): Promise<void> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  const query = qs.toString() ? `?${qs}` : "";

  const url = `${API_BASE}/compliance/books/export${query}`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) throw new Error(`Export failed: ${res.status} ${res.statusText}`);
  const blob = await res.blob();

  const filename = params?.filename || `books_export_${new Date().toISOString().slice(0,10)}.zip`;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  URL.revokeObjectURL(link.href);
  document.body.removeChild(link);
}
