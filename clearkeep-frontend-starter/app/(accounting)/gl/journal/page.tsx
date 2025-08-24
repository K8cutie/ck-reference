"use client";

import * as React from "react";

/** ---------- Types (loose; tolerant to your API shapes) ---------- */
type NormalSide = "debit" | "credit" | string;
type AccountType = string;

type GLAccount = {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  normal_side: NormalSide;
  is_cash: boolean;
  is_active: boolean;
};

type JournalLine = {
  id?: number;
  account_id: number;
  line_no: number;
  description?: string | null;
  debit: number;
  credit: number;
};

type JournalEntry = {
  id: number;
  entry_no?: number | null;
  entry_date: string; // ISO
  memo?: string | null;
  currency_code?: string;
  reference_no?: string | null;
  source_module?: string | null;
  source_id?: string | null;
  posted_at?: string | null;
  is_locked?: boolean;
  created_at?: string;
  updated_at?: string;
  lines?: JournalLine[];
  total_debit?: number;
  total_credit?: number;
};

type ListResponseJE =
  | JournalEntry[]
  | { items?: JournalEntry[]; results?: JournalEntry[]; total?: number };

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
const ACCOUNTS_FETCH_LIMIT = 200; // API cap
const TZ = process.env.NEXT_PUBLIC_TZ || "Asia/Manila";

/** ---------- Helpers ---------- */
function toJEItems(data: ListResponseJE): JournalEntry[] {
  if (Array.isArray(data)) return data;
  if (data.items && Array.isArray(data.items)) return data.items;
  if (data.results && Array.isArray(data.results)) return data.results;
  return [];
}
function qparams(params: Record<string, any>) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}
function fmtDateTime(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString();
}
function fmtDateOnly(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString();
}
function computeTotals(lines?: JournalLine[]) {
  let d = 0,
    c = 0;
  (lines || []).forEach((ln) => {
    d += Number(ln.debit || 0);
    c += Number(ln.credit || 0);
  });
  return { d, c };
}
function monthBounds(dateLike: string | Date = new Date()) {
  const d = new Date(dateLike);
  const y = d.getFullYear();
  const m = d.getMonth();
  const start = new Date(Date.UTC(y, m, 1));
  const end = new Date(Date.UTC(y, m + 1, 0));
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  return { start: iso(start), end: iso(end) };
}

/** ---------- Page ---------- */
export default function JournalPage() {
  // filters
  const [q, setQ] = React.useState("");
  const [dateFrom, setDateFrom] = React.useState<string>("");
  const [dateTo, setDateTo] = React.useState<string>("");
  const [onlyUnposted, setOnlyUnposted] = React.useState(false);
  const [limit, setLimit] = React.useState(25);
  const [offset, setOffset] = React.useState(0);

  // data
  const [rows, setRows] = React.useState<JournalEntry[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // expand state
  const [openId, setOpenId] = React.useState<number | null>(null);

  // accounts for dropdown + mapping
  const [accounts, setAccounts] = React.useState<GLAccount[]>([]);
  const [acctErr, setAcctErr] = React.useState<string | null>(null);
  const accountName = React.useMemo(() => {
    const map = new Map<number, string>();
    for (const a of accounts) {
      map.set(a.id, `${a.code} — ${a.name}`);
    }
    return (id?: number) => (id ? map.get(id) || String(id) : "—");
  }, [accounts]);

  // create dialog
  const [showCreate, setShowCreate] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState<{
    entry_date: string;
    memo: string;
    currency_code: string;
    reference_no: string;
    source_module: string;
    source_id: string;
    lines: JournalLine[];
  }>({
    entry_date: new Date().toISOString().slice(0, 10),
    memo: "",
    currency_code: "PHP",
    reference_no: `JE-${new Date().toISOString().slice(0, 10)}`,
    source_module: "manual",
    source_id: "",
    lines: [
      { account_id: 0, line_no: 1, description: "", debit: 0, credit: 0 },
      { account_id: 0, line_no: 2, description: "", debit: 0, credit: 0 },
    ],
  });

  // fetch accounts (for create form & name mapping)
  async function fetchAccounts() {
    try {
      setAcctErr(null);
      const res = await fetch(
        `${API_BASE}/gl/accounts${qparams({
          is_active: "true",
          limit: ACCOUNTS_FETCH_LIMIT,
        })}`,
        {
          headers: {
            "Content-Type": "application/json",
            "X-TZ": TZ,
          },
        }
      );
      if (!res.ok) throw new Error(await res.text());
      const payload = (await res.json()) as any;
      const items = Array.isArray(payload)
        ? payload
        : payload.items || payload.results || [];
      setAccounts(items);
    } catch (e: any) {
      setAcctErr(e?.message || "Failed to load accounts");
    }
  }

  async function fetchJournal() {
    if (!API_BASE) {
      setError(
        "NEXT_PUBLIC_API_BASE is not set. Add it to .env.local (e.g., http://127.0.0.1:8000)"
      );
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = {
        q: q || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        posted: onlyUnposted ? "false" : undefined,
        limit,
        offset,
      };
      const url = `${API_BASE}/gl/journal${qparams(params)}`;
      const res = await fetch(url, {
        headers: {
          "Content-Type": "application/json",
          "X-TZ": TZ,
        },
      });
      if (!res.ok) throw new Error(await res.text());
      const payload = (await res.json()) as ListResponseJE;
      setRows(toJEItems(payload));
    } catch (e: any) {
      setError(e?.message || "Failed to load journal");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    fetchAccounts(); // once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  React.useEffect(() => {
    fetchJournal();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, dateFrom, dateTo, onlyUnposted, limit, offset]);

  function addLine() {
    setForm((s) => ({
      ...s,
      lines: [
        ...s.lines,
        {
          account_id: 0,
          line_no: s.lines.length + 1,
          description: "",
          debit: 0,
          credit: 0,
        },
      ],
    }));
  }
  function removeLine(i: number) {
    setForm((s) => {
      const next = s.lines.slice();
      next.splice(i, 1);
      return {
        ...s,
        lines: next.map((ln, idx) => ({ ...ln, line_no: idx + 1 })),
      };
    });
  }
  function setLine<K extends keyof JournalLine>(
    i: number,
    key: K,
    val: JournalLine[K]
  ) {
    setForm((s) => {
      const next = s.lines.slice();
      next[i] = { ...next[i], [key]: val };
      // one side only rule
      if (key === "debit" && Number(val) > 0) {
        next[i].credit = 0;
      }
      if (key === "credit" && Number(val) > 0) {
        next[i].debit = 0;
      }
      return { ...s, lines: next };
    });
  }

  const totals = computeTotals(form.lines);
  const isBalanced =
    Math.round((totals.d - totals.c) * 100) === 0 && totals.d > 0;

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      // simple client-side validations
      if (!isBalanced) throw new Error("Journal is not balanced.");
      for (const ln of form.lines) {
        if (!ln.account_id) throw new Error("Select an account on all lines.");
        const hasOneSide =
          (Number(ln.debit) > 0 && Number(ln.credit) === 0) ||
          (Number(ln.credit) > 0 && Number(ln.debit) === 0);
        if (!hasOneSide) {
          throw new Error(
            "Each line must have either a debit or a credit (not both)."
          );
        }
      }

      const payload = {
        entry_date: form.entry_date,
        memo: form.memo || null,
        currency_code: form.currency_code || "PHP",
        reference_no: form.reference_no || null,
        source_module: form.source_module || "manual",
        source_id: form.source_id || null,
        lines: form.lines.map((ln) => ({
          account_id: Number(ln.account_id),
          line_no: ln.line_no,
          description: ln.description || null,
          debit: Number(ln.debit || 0),
          credit: Number(ln.credit || 0),
        })),
      };

      const res = await fetch(`${API_BASE}/gl/journal`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-TZ": TZ,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      // reset + refresh
      setShowCreate(false);
      setForm({
        entry_date: new Date().toISOString().slice(0, 10),
        memo: "",
        currency_code: "PHP",
        reference_no: `JE-${new Date().toISOString().slice(0, 10)}`,
        source_module: "manual",
        source_id: "",
        lines: [
          { account_id: 0, line_no: 1, description: "", debit: 0, credit: 0 },
          { account_id: 0, line_no: 2, description: "", debit: 0, credit: 0 },
        ],
      });
      setOffset(0);
      await fetchJournal();
    } catch (e: any) {
      setCreateError(e?.message || "Failed to create journal entry");
    } finally {
      setCreating(false);
    }
  }

  async function postJE(id: number) {
    try {
      const res = await fetch(`${API_BASE}/gl/journal/${id}/post`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-TZ": TZ,
        },
      });
      if (!res.ok) throw new Error(await res.text());
      await fetchJournal();
    } catch (e) {
      alert("Posting failed:\n" + (e as any)?.message);
    }
  }

  async function exportBooks() {
    // Use filters if set; otherwise default to the current month
    const rng = monthBounds(new Date());
    const from = dateFrom || rng.start;
    const to = dateTo || rng.end;

    try {
      const url = `${API_BASE}/compliance/books/export${qparams({
        date_from: from,
        date_to: to,
      })}`;
      const res = await fetch(url, {
        headers: { "X-TZ": TZ },
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `books_${from}_${to}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(a.href);
    } catch (e: any) {
      alert("Export failed:\n" + (e?.message || "unknown error"));
    }
  }

  function resetFilters() {
    setQ("");
    setDateFrom("");
    setDateTo("");
    setOnlyUnposted(false);
    setLimit(25);
    setOffset(0);
  }

  function nextPage() {
    setOffset((o) => o + limit);
  }
  function prevPage() {
    setOffset((o) => Math.max(0, o - limit));
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Journal Entries</h1>
          <p className="text-sm text-gray-500">
            Create, review, and post journal entries.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={exportBooks}
            className="px-3 py-2 rounded-2xl border bg-white"
            title="Download BIR books (ZIP of CSVs + transmittal)"
          >
            Export books (ZIP)
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-2 rounded-2xl bg-black text-white shadow"
          >
            New entry
          </button>
        </div>
      </header>

      {/* Filters */}
      <section className="rounded-2xl border p-4 bg-white shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-1">Search</label>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Memo or Reference"
              className="w-full rounded-xl border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-full rounded-xl border px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-full rounded-xl border px-3 py-2"
            />
          </div>
          <div className="flex items-end">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={onlyUnposted}
                onChange={(e) => setOnlyUnposted(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Only unposted</span>
            </label>
          </div>
          <div className="flex items-end gap-2">
            <button
              onClick={resetFilters}
              className="px-3 py-2 rounded-xl border bg-white"
            >
              Reset
            </button>
            <div className="ml-auto flex items-center gap-2">
              <label className="text-sm">Rows</label>
              <select
                value={limit}
                onChange={(e) => {
                  setLimit(Number(e.target.value) || 25);
                  setOffset(0);
                }}
                className="rounded-xl border px-2 py-2 bg-white"
              >
                {[10, 25, 50, 100].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </section>

      {/* Table */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-20">#</th>
              <th className="w-32">Date</th>
              <th>Memo</th>
              <th className="w-32">Reference</th>
              <th className="w-24">Currency</th>
              <th className="w-28">Posted</th>
              <th className="w-28">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && error && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-red-600">
                  {error}
                </td>
              </tr>
            )}
            {!loading && !error && rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-gray-500">
                  No journal entries found.
                </td>
              </tr>
            )}
            {!loading &&
              !error &&
              rows.map((je) => {
                const totals = computeTotals(je.lines);
                const posted = !!je.posted_at;
                return (
                  <React.Fragment key={je.id}>
                    <tr className="border-t">
                      <td className="px-4 py-2 font-mono">
                        {je.entry_no ?? je.id}
                      </td>
                      <td className="px-4 py-2">{fmtDateOnly(je.entry_date)}</td>
                      <td className="px-4 py-2">
                        <div className="font-medium">
                          {je.memo || <span className="text-gray-400">—</span>}
                        </div>
                        <div className="text-xs text-gray-500">
                          Dr {totals.d.toLocaleString()} / Cr{" "}
                          {totals.c.toLocaleString()}
                        </div>
                      </td>
                      <td className="px-4 py-2">{je.reference_no || "—"}</td>
                      <td className="px-4 py-2">{je.currency_code || "—"}</td>
                      <td className="px-4 py-2">
                        {posted ? (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-green-100 text-green-700">
                            {fmtDateTime(je.posted_at)}
                          </span>
                        ) : (
                          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-gray-100 text-gray-600">
                            Unposted
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() =>
                              setOpenId((v) => (v === je.id ? null : je.id))
                            }
                            className="px-2 py-1 rounded-lg border bg-white"
                          >
                            {openId === je.id ? "Hide" : "View"}
                          </button>
                          {!posted && (
                            <button
                              onClick={() => postJE(je.id)}
                              className="px-2 py-1 rounded-lg bg-black text-white"
                            >
                              Post
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {openId === je.id && (
                      <tr className="bg-gray-50">
                        <td colSpan={7} className="px-4 py-3">
                          <table className="w-full text-sm">
                            <thead>
                              <tr className="[&>th]:px-2 [&>th]:py-1 text-left text-gray-600">
                                <th className="w-12">#</th>
                                <th>Account</th>
                                <th>Description</th>
                                <th className="w-32 text-right">Debit</th>
                                <th className="w-32 text-right">Credit</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(je.lines || []).map((ln) => (
                                <tr key={ln.line_no} className="border-t">
                                  <td className="px-2 py-1">{ln.line_no}</td>
                                  <td className="px-2 py-1">
                                    {accountName(ln.account_id)}
                                  </td>
                                  <td className="px-2 py-1">
                                    {ln.description || "—"}
                                  </td>
                                  <td className="px-2 py-1 text-right">
                                    {ln.debit
                                      ? Number(ln.debit).toLocaleString()
                                      : "—"}
                                  </td>
                                  <td className="px-2 py-1 text-right">
                                    {ln.credit
                                      ? Number(ln.credit).toLocaleString()
                                      : "—"}
                                  </td>
                                </tr>
                              ))}
                              <tr className="border-t font-medium">
                                <td className="px-2 py-1"></td>
                                <td className="px-2 py-1"></td>
                                <td className="px-2 py-1 text-right">Totals</td>
                                <td className="px-2 py-1 text-right">
                                  {totals.d.toLocaleString()}
                                </td>
                                <td className="px-2 py-1 text-right">
                                  {totals.c.toLocaleString()}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
          </tbody>
        </table>
      </section>

      {/* Pager */}
      <section className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          Showing {rows.length} item{rows.length === 1 ? "" : "s"}
        </div>
        <div className="flex gap-2">
          <button
            onClick={prevPage}
            disabled={offset === 0 || loading}
            className="px-3 py-2 rounded-xl border bg-white disabled:opacity-50"
          >
            Prev
          </button>
          <button
            onClick={nextPage}
            disabled={loading || rows.length < limit}
            className="px-3 py-2 rounded-xl border bg-white disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </section>

      {/* Create dialog */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-4xl rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-lg font-semibold">New Journal Entry</h2>
              <button
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setShowCreate(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={onCreate} className="p-4 space-y-4">
              {createError && (
                <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
                  {createError}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Date
                  </label>
                  <input
                    type="date"
                    required
                    value={form.entry_date}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, entry_date: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Currency
                  </label>
                  <input
                    value={form.currency_code}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, currency_code: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-1">
                    Reference
                  </label>
                  <input
                    value={form.reference_no}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, reference_no: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                    placeholder="Optional"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Source Module
                  </label>
                  <input
                    value={form.source_module}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, source_module: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Source ID
                  </label>
                  <input
                    value={form.source_id}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, source_id: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                    placeholder="Optional"
                  />
                </div>
                <div className="md:col-span-6">
                  <label className="block text-sm font-medium mb-1">Memo</label>
                  <input
                    value={form.memo}
                    onChange={(e) =>
                      setForm((s) => ({ ...s, memo: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                    placeholder="Optional memo"
                  />
                </div>
              </div>

              <div className="rounded-xl border">
                <div className="flex items-center justify-between px-3 py-2 border-b">
                  <div className="text-sm font-medium">
                    Lines (balanced:{" "}
                    <span
                      className={
                        isBalanced ? "text-green-600" : "text-red-600"
                      }
                    >
                      {isBalanced ? "yes" : "no"}
                    </span>
                    ) — Dr {totals.d.toLocaleString()} / Cr{" "}
                    {totals.c.toLocaleString()}
                  </div>
                  <button
                    type="button"
                    onClick={addLine}
                    className="px-2 py-1 rounded-lg border bg-white"
                  >
                    + Add line
                  </button>
                </div>

                <div className="overflow-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr className="[&>th]:px-3 [&>th]:py-2 text-left">
                        <th className="w-12">#</th>
                        <th className="w-80">Account</th>
                        <th>Description</th>
                        <th className="w-40 text-right">Debit</th>
                        <th className="w-40 text-right">Credit</th>
                        <th className="w-16"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {form.lines.map((ln, i) => (
                        <tr key={i} className="border-t">
                          <td className="px-3 py-2">{ln.line_no}</td>
                          <td className="px-3 py-2">
                            <select
                              required
                              value={ln.account_id || 0}
                              onChange={(e) =>
                                setLine(i, "account_id", Number(e.target.value))
                              }
                              className="w-full rounded-xl border px-3 py-2 bg-white"
                            >
                              <option value={0} disabled>
                                Select account…
                              </option>
                              {accounts.map((a) => (
                                <option key={a.id} value={a.id}>
                                  {a.code} — {a.name}
                                </option>
                              ))}
                            </select>
                            {acctErr && (
                              <div className="text-xs text-red-600 mt-1">
                                {acctErr}
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <input
                              value={ln.description || ""}
                              onChange={(e) =>
                                setLine(i, "description", e.target.value)
                              }
                              className="w-full rounded-xl border px-3 py-2"
                              placeholder="Optional"
                            />
                          </td>
                          <td className="px-3 py-2 text-right">
                            <input
                              type="number"
                              inputMode="decimal"
                              min={0}
                              step="0.01"
                              value={ln.debit}
                              onChange={(e) =>
                                setLine(i, "debit", Number(e.target.value))
                              }
                              className="w-full rounded-xl border px-3 py-2 text-right"
                            />
                          </td>
                          <td className="px-3 py-2 text-right">
                            <input
                              type="number"
                              inputMode="decimal"
                              min={0}
                              step="0.01"
                              value={ln.credit}
                              onChange={(e) =>
                                setLine(i, "credit", Number(e.target.value))
                              }
                              className="w-full rounded-xl border px-3 py-2 text-right"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <button
                              type="button"
                              onClick={() => removeLine(i)}
                              className="px-2 py-1 rounded-lg border bg-white"
                              disabled={form.lines.length <= 2}
                              title={
                                form.lines.length <= 2
                                  ? "Keep at least 2 lines"
                                  : "Remove this line"
                              }
                            >
                              −
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-3 py-2 rounded-xl border bg-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !isBalanced}
                  className="px-3 py-2 rounded-2xl bg-black text-white shadow disabled:opacity-50"
                >
                  {creating ? "Creating…" : "Create entry"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
