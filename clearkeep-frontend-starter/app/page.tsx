"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function NewTransactionPage() {
  const router = useRouter();
  const [amount, setAmount] = useState<string>("");
  const [currency, setCurrency] = useState<string>("PHP");
  const [memo, setMemo] = useState<string>("");
  const [reference, setReference] = useState<string>(""); // e.g. SAC-123
  const [method, setMethod] = useState<string>("cash");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: Number(amount),
          currency,
          memo: memo || undefined,
          reference: reference || undefined,
          method: method || undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const created = await res.json();
      const id = created?.id ?? created?.data?.id;
      router.push(`/transactions/${id}`);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to create transaction");
      setBusy(false);
    }
  }

  const input = "w-full rounded-xl border border-gray-300 px-3 py-2 outline-none focus:ring focus:ring-blue-100";
  const label = "block text-xs text-gray-500 mb-1";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">New Transaction</h1>
        <a href="/reports/transactions" className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50">
          View history
        </a>
      </div>

      <div className="rounded-3xl border bg-white p-6 shadow-sm">
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className={label}>Amount</label>
            <input className={input} inputMode="decimal" placeholder="e.g., 500" value={amount} onChange={(e) => setAmount(e.target.value)} required />
          </div>
          <div>
            <label className={label}>Currency</label>
            <input className={input} value={currency} onChange={(e) => setCurrency(e.target.value)} />
          </div>
          <div>
            <label className={label}>Reference (optional)</label>
            <input className={input} placeholder="e.g., SAC-123" value={reference} onChange={(e) => setReference(e.target.value)} />
          </div>
          <div>
            <label className={label}>Method (optional)</label>
            <input className={input} placeholder="cash / gcash / card" value={method} onChange={(e) => setMethod(e.target.value)} />
          </div>
          <div className="md:col-span-2">
            <label className={label}>Memo (optional)</label>
            <textarea rows={3} className={input} placeholder="note…" value={memo} onChange={(e) => setMemo(e.target.value)} />
          </div>

          {err && <div className="md:col-span-2 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">{err}</div>}

          <div className="md:col-span-2 flex items-center justify-end gap-2">
            <a href="/transactions" className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50">Cancel</a>
            <button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
              {busy ? "Saving…" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
