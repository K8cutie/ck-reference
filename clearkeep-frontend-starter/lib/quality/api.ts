/**
 * ClearKeep — Quality API helpers (pure, client-safe)
 * Centralized fetch utilities used by the Six Sigma page.
 * No side effects. All functions return JSON data.
 */

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, "");
export const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

/** Headers for CK API (adds X-API-Key if present) */
export function apiHeaders(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}

/**
 * GET JSON helper
 * Accepts either a full URL (http/https) or an API path like "/gl/journal?...".
 */
export async function getJSON<T = any>(pathOrUrl: string): Promise<T> {
  const isFull = /^https?:\/\//i.test(pathOrUrl);
  const url = isFull ? pathOrUrl : `${API_BASE}${pathOrUrl}`;
  const res = await fetch(url, { headers: apiHeaders(), cache: "no-store" });
  if (!res.ok) {
    let text = "";
    try { text = await res.text(); } catch {}
    throw new Error(`${res.status} ${res.statusText}${text ? " — " + text : ""}`.trim());
  }
  return res.json() as Promise<T>;
}

/** Simple type for date ranges (YYYY-MM-DD inclusive) */
export type DateRange = { from: string; to: string };

/**
 * Paged journal fetcher (array API)
 * Returns the concatenated list of journal entries across pages.
 * @param postedOnly when true, appends &is_locked=true
 * @param limitPerPage hard-capped at 200 by backend
 */
export async function fetchJournalPaged(range: DateRange, postedOnly = false, limitPerPage = 200): Promise<any[]> {
  const limit = Math.min(Math.max(1, limitPerPage), 200);
  const out: any[] = [];
  let offset = 0;
  while (true) {
    const base = `/gl/journal?date_from=${range.from}&date_to=${range.to}&limit=${limit}&offset=${offset}`;
    const url = postedOnly ? `${base}&is_locked=true` : base;
    const page = await getJSON<any>(url);
    // Support both array and {items,next_offset} shapes
    const items: any[] = Array.isArray(page) ? page : Array.isArray(page?.items) ? page.items : [];
    out.push(...items);
    const nextOffset = (Array.isArray(page) ? (items.length < limit ? null : offset + limit) : page?.next_offset ?? null);
    if (!nextOffset) break;
    offset = nextOffset;
  }
  return out;
}

/**
 * Accounts list (paged; backend enforces limit <= 200)
 * Returns ALL accounts by paging with limit=200.
 */
export async function fetchAccounts(): Promise<any[]> {
  const limit = 200;
  const out: any[] = [];
  let offset = 0;
  while (true) {
    const url = `/gl/accounts?limit=${limit}&offset=${offset}`;
    const page = await getJSON<any>(url);
    // Support both array and {items,next_offset} shapes
    const items: any[] = Array.isArray(page) ? page : Array.isArray(page?.items) ? page.items : [];
    out.push(...items);
    const nextOffset = (Array.isArray(page) ? (items.length < limit ? null : offset + limit) : page?.next_offset ?? null);
    if (!nextOffset) break;
    offset = nextOffset;
  }
  return out;
}

/** Locks status for a YM range (YYYY-MM) */
export async function fetchLocksStatus(fromYm: string, toYm: string): Promise<any> {
  return getJSON<any>(`/gl/locks/status?from=${fromYm}&to=${toYm}`);
}
