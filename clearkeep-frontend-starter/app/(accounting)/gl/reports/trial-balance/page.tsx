"use client";

import * as React from "react";

type TBRow = {
  account_id: number;
  code: string;
  name: string;
  type: string;
  normal_side: string;
  debit_total: number;
  credit_total: number;
  balance: number;
  dr_balance: number;
  cr_balance: number;
};

type TBPayload = {
  date_from?: string | null;
  date_to?: string | null;
  rows: TBRow[];
  totals: {
    debit_total: number;
    credit_total: number;
    dr_balance: number;
    cr_balance: number;
  };
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
const TZ = process.env.NEXT_PUBLIC_TZ || "Asia/Manila";

function monthBounds(d = new Date()) {
  const y = d.getFullYear();
  const m = d.getMonth();
  const start = new Date(Date.UTC(y, m, 1));
  const end = new Date(Date.UTC(y, m + 1, 0));
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  return { start: iso(start), end: iso(end) };
}

function q(params: Record<string, any>) {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    s.set(k, String(v));
  }
  const str = s.toString();
  return str ? `?${str}` : "";
}

export default function TrialBalancePage() {
  const rng = React.useMemo(() => monthBounds(new Date()), []);
  const [dateFrom, setDateFrom] = React.useState<string>(rng.start);
  const [dateTo, setDateTo] = React.useState<string>(rng.end);

  const [data, setData] = React.useState<TBPayload | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const canFetch = API_BASE.length > 0;

  async function fetchTB() {
    if (!canFetch) {
      setErr(
        "NEXT_PUBLIC_API_BASE is not set. Add it to .env.local (e.g., http://127.0.0.1:8000)"
      );
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(
        `${API_BASE}/gl/reports/trial_balance${q({
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        })}`,
        { headers: { "Content-Type": "application/json", "X-TZ": TZ } }
      );
      if (!res.ok) throw new Error(await res.text());
      const payload: TBPayload = await res.json();
      setData(payload);
    } catch (e: any) {
      setErr(e?.message || "Failed to load trial balance");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    fetchTB();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function resetRange() {
    setDateFrom(rng.start);
    setDateTo(rng.end);
  }

  function fmt(n: number | null | undefined) {
    const v = Number(n || 0);
    return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Trial Balance</h1>
          <p className="text-sm text-gray-500">
            Posted Journal Entries only. Use date range to filter.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchTB}
            className="px-3 py-2 rounded-2xl bg-black text-white shadow disabled:opacity-50"
            disabled={loading}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </header>

      {/* Filters */}
      <section className="rounded-2xl border p-4 bg-white shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
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
          <div className="flex items-end gap-2">
            <button
              onClick={resetRange}
              className="px-3 py-2 rounded-xl border bg-white"
            >
              This month
            </button>
            <button
              onClick={fetchTB}
              className="px-3 py-2 rounded-xl border bg-white"
              disabled={loading}
            >
              Apply
            </button>
          </div>
        </div>
      </section>

      {/* Errors */}
      {err && (
        <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
          {err}
        </div>
      )}

      {/* Table */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-28">Type</th>
              <th className="w-20">Normal</th>
              <th className="w-32 text-right">Debits</th>
              <th className="w-32 text-right">Credits</th>
              <th className="w-32 text-right">DR Balance</th>
              <th className="w-32 text-right">CR Balance</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && data && data.rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-gray-500">
                  No entries in this range.
                </td>
              </tr>
            )}
            {!loading &&
              data &&
              data.rows.map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-4 py-2 font-mono">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 capitalize">{r.type}</td>
                  <td className="px-4 py-2 capitalize">{r.normal_side}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.debit_total)}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.credit_total)}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.dr_balance)}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.cr_balance)}</td>
                </tr>
              ))}

            {/* Totals */}
            {!loading && data && (
              <tr className="border-t bg-gray-50 font-medium">
                <td className="px-4 py-2" colSpan={4}>
                  Totals
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.debit_total)}
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.credit_total)}
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.dr_balance)}
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.cr_balance)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
