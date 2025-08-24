"use client";

import * as React from "react";

type Row = {
  account_id: number;
  code: string;
  name: string;
  amount: number; // positive (income: credit>debit; expense: debit>credit)
};

type Payload = {
  date_from?: string | null;
  date_to?: string | null;
  incomes: Row[];
  expenses: Row[];
  totals: {
    income_total: number;
    expense_total: number;
    net_income: number;
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

function fmt(n: number | null | undefined) {
  const v = Number(n || 0);
  return v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function IncomeStatementPage() {
  const rng = React.useMemo(() => monthBounds(new Date()), []);
  const [dateFrom, setDateFrom] = React.useState<string>(rng.start);
  const [dateTo, setDateTo] = React.useState<string>(rng.end);

  const [data, setData] = React.useState<Payload | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const canFetch = API_BASE.length > 0;

  async function fetchPL() {
    if (!canFetch) {
      setErr("NEXT_PUBLIC_API_BASE is not set. Add it to .env.local (e.g., http://127.0.0.1:8000)");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(
        `${API_BASE}/gl/reports/income_statement${q({
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
        })}`,
        { headers: { "Content-Type": "application/json", "X-TZ": TZ } }
      );
      if (!res.ok) throw new Error(await res.text());
      const payload: Payload = await res.json();
      setData(payload);
    } catch (e: any) {
      setErr(e?.message || "Failed to load income statement");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    fetchPL();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function resetRange() {
    setDateFrom(rng.start);
    setDateTo(rng.end);
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Profit &amp; Loss (Income Statement)</h1>
          <p className="text-sm text-gray-500">
            Based on posted Journal Entries. Use date range to filter.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchPL}
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
            <button onClick={resetRange} className="px-3 py-2 rounded-xl border bg-white">
              This month
            </button>
            <button
              onClick={fetchPL}
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
        <div className="rounded-XL bg-red-50 text-red-700 px-3 py-2 text-sm">
          {err}
        </div>
      )}

      {/* Incomes */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <div className="px-4 py-3 font-medium text-gray-700">Income</div>
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-32 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && data && data.incomes.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-gray-500">
                  No income accounts in range.
                </td>
              </tr>
            )}
            {!loading &&
              data &&
              data.incomes.map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-4 py-2 font-mono">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.amount)}</td>
                </tr>
              ))}

            {!loading && data && (
              <tr className="border-t bg-gray-50 font-medium">
                <td className="px-4 py-2" colSpan={2}>
                  Total Income
                </td>
                <td className="px-4 py-2 text-right">{fmt(data.totals.income_total)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Expenses */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <div className="px-4 py-3 font-medium text-gray-700">Expenses</div>
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-32 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && data && data.expenses.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-6 text-center text-gray-500">
                  No expense accounts in range.
                </td>
              </tr>
            )}
            {!loading &&
              data &&
              data.expenses.map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-4 py-2 font-mono">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.amount)}</td>
                </tr>
              ))}

            {!loading && data && (
              <tr className="border-t bg-gray-50 font-medium">
                <td className="px-4 py-2" colSpan={2}>
                  Total Expenses
                </td>
                <td className="px-4 py-2 text-right">{fmt(data.totals.expense_total)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Net Income */}
      <section className="rounded-2xl border bg-white shadow-sm">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="text-sm text-gray-600">Net Income</div>
          <div className="text-lg font-semibold">
            {fmt(data?.totals.net_income ?? 0)}
          </div>
        </div>
      </section>
    </div>
  );
}
