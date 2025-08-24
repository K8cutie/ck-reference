"use client";

import * as React from "react";

type BSRow = {
  account_id: number;
  code: string;
  name: string;
  type: "asset" | "liability" | "equity" | string;
  normal_side: "debit" | "credit" | string;
  balance: number;     // signed by normal side
  dr_balance: number;  // display helper
  cr_balance: number;  // display helper
};

type BSPayload = {
  as_of?: string | null;
  assets: BSRow[];
  liabilities: BSRow[];
  equity: BSRow[];
  totals: {
    assets: number;
    liabilities: number;
    equity: number;
    liabilities_plus_equity: number;
  };
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
const TZ = process.env.NEXT_PUBLIC_TZ || "Asia/Manila";

function todayISO() {
  const d = new Date();
  // use local date (not UTC) for clarity
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
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

export default function BalanceSheetPage() {
  const [asOf, setAsOf] = React.useState<string>(todayISO());
  const [data, setData] = React.useState<BSPayload | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const canFetch = API_BASE.length > 0;

  async function fetchBS() {
    if (!canFetch) {
      setErr("NEXT_PUBLIC_API_BASE is not set. Add it to .env.local (e.g., http://127.0.0.1:8000)");
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(
        `${API_BASE}/gl/reports/balance_sheet${q({ as_of: asOf || undefined })}`,
        { headers: { "Content-Type": "application/json", "X-TZ": TZ } }
      );
      if (!res.ok) throw new Error(await res.text());
      const payload: BSPayload = await res.json();
      setData(payload);
    } catch (e: any) {
      setErr(e?.message || "Failed to load balance sheet");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    fetchBS();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const diff =
    (data?.totals.assets || 0) -
    ((data?.totals.liabilities_plus_equity || 0));

  return (
    <div className="p-6 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Balance Sheet</h1>
          <p className="text-sm text-gray-500">
            As of a date, based on posted Journal Entries.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchBS}
            className="px-3 py-2 rounded-2xl bg-black text-white shadow disabled:opacity-50"
            disabled={loading}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </header>

      {/* Filter */}
      <section className="rounded-2xl border p-4 bg-white shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-1">As of</label>
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              className="w-full rounded-xl border px-3 py-2"
            />
          </div>
          <div className="flex items-end gap-2">
            <button
              onClick={() => setAsOf(todayISO())}
              className="px-3 py-2 rounded-xl border bg-white"
            >
              Today
            </button>
            <button
              onClick={fetchBS}
              className="px-3 py-2 rounded-xl border bg-white"
              disabled={loading}
            >
              Apply
            </button>
          </div>
        </div>
      </section>

      {/* Error */}
      {err && (
        <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
          {err}
        </div>
      )}

      {/* Assets */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <div className="px-4 py-3 font-medium text-gray-700">Assets</div>
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-32 text-right">DR</th>
              <th className="w-32 text-right">CR</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center">
                  Loading…
                </td>
              </tr>
            )}
            {!loading &&
              data?.assets?.map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-4 py-2 font-mono">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.dr_balance)}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.cr_balance)}</td>
                </tr>
              ))}
            {!loading && data && (
              <tr className="border-t bg-gray-50 font-medium">
                <td className="px-4 py-2" colSpan={2}>
                  Total Assets
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.assets)}
                </td>
                <td className="px-4 py-2 text-right">—</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Liabilities */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <div className="px-4 py-3 font-medium text-gray-700">Liabilities</div>
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-32 text-right">DR</th>
              <th className="w-32 text-right">CR</th>
            </tr>
          </thead>
          <tbody>
            {!loading &&
              data?.liabilities?.map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-4 py-2 font-mono">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.dr_balance)}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.cr_balance)}</td>
                </tr>
              ))}
            {!loading && data && (
              <tr className="border-t bg-gray-50 font-medium">
                <td className="px-4 py-2" colSpan={3}>
                  Total Liabilities
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.liabilities)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Equity */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <div className="px-4 py-3 font-medium text-gray-700">Equity</div>
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-32 text-right">DR</th>
              <th className="w-32 text-right">CR</th>
            </tr>
          </thead>
          <tbody>
            {!loading &&
              data?.equity?.map((r) => (
                <tr key={r.account_id} className="border-t">
                  <td className="px-4 py-2 font-mono">{r.code}</td>
                  <td className="px-4 py-2">{r.name}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.dr_balance)}</td>
                  <td className="px-4 py-2 text-right">{fmt(r.cr_balance)}</td>
                </tr>
              ))}
            {!loading && data && (
              <tr className="border-t bg-gray-50 font-medium">
                <td className="px-4 py-2" colSpan={3}>
                  Total Equity
                </td>
                <td className="px-4 py-2 text-right">
                  {fmt(data.totals.equity)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      {/* Check */}
      <section className="rounded-2xl border bg-white shadow-sm">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="text-sm text-gray-600">
            Check: Assets − (Liabilities + Equity)
          </div>
          <div
            className={`text-lg font-semibold ${
              Math.abs(diff) < 0.005 ? "text-green-600" : "text-red-600"
            }`}
            title="Should be zero when balanced"
          >
            {fmt(diff)}
          </div>
        </div>
      </section>
    </div>
  );
}
