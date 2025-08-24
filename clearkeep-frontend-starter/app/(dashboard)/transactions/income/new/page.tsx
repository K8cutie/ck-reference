"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

// From your API
type AccountType = "cash" | "bank" | "ewallet" | "other";
type Account = { id: number; name: string; type: AccountType; institution?: string | null; active: boolean };
type Fund = { id: number; name: string; code?: string | null; restricted?: boolean };

type TransferCreate = {
  date: string;
  amount: number;
  from_account_id: number;
  to_account_id: number;
  description?: string | null;
  fund_id?: number | null;
  reference_no_from?: string | null;
  reference_no_to?: string | null;
  batch_id?: string | null;
  transfer_ref?: string | null;
};

export default function NewIncomePage() {
  const router = useRouter();

  // Form fields
  const [date, setDate] = useState(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  });
  const [amount, setAmount] = useState<string>("");

  const [fromAccountId, setFromAccountId] = useState<string>(""); // source (e.g., Collection Basket)
  const [toAccountId, setToAccountId] = useState<string>("");     // deposit (e.g., Bank)
  const [fundId, setFundId] = useState<string>("");

  const [description, setDescription] = useState<string>("");
  const [refFrom, setRefFrom] = useState<string>(""); // OR / txn #
  const [refTo, setRefTo] = useState<string>("");     // deposit slip / check #
  const [batchId, setBatchId] = useState<string>("");

  // Data
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [funds, setFunds] = useState<Fund[]>([]);
  const [loading, setLoading] = useState(true);

  // UI
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Load accounts and funds
  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const [accR, fundR] = await Promise.all([
          fetch(`${API_BASE}/accounts/`, { cache: "no-store" }),
          fetch(`${API_BASE}/funds/`, { cache: "no-store" }),
        ]);
        if (!accR.ok) throw new Error(`Accounts HTTP ${accR.status}`);
        if (!fundR.ok) throw new Error(`Funds HTTP ${fundR.status}`);

        const acc: Account[] = await accR.json();
        const f: Fund[] = await fundR.json();
        if (cancel) return;

        const active = acc.filter(a => a.active);
        setAccounts(active);
        setFunds(f);

        // Prefill defaults if available
        if (!fromAccountId && active.length) setFromAccountId(String(active[0].id));
        if (!toAccountId && active.length > 1) setToAccountId(String(active[1].id));
        else if (!toAccountId && active.length) setToAccountId(String(active[0].id));
      } catch (e: any) {
        if (!cancel) setError(e?.message ?? "Failed to load accounts/funds");
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; };
  }, []);

  const sortedAccounts = useMemo(() => [...accounts].sort((a,b)=>a.name.localeCompare(b.name)), [accounts]);
  const sortedFunds = useMemo(() => [...funds].sort((a,b)=>a.name.localeCompare(b.name)), [funds]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const amt = Number(amount);
    if (!date) return setError("Date is required.");
    if (!(amt > 0)) return setError("Amount must be positive.");
    if (!fromAccountId) return setError("Source account is required.");
    if (!toAccountId) return setError("Deposit account is required.");
    if (fromAccountId === toAccountId) return setError("Source and deposit must be different.");

    const payload: TransferCreate = {
      date,
      amount: amt,
      from_account_id: Number(fromAccountId),
      to_account_id: Number(toAccountId),
      description: description || null,
      fund_id: fundId ? Number(fundId) : null,
      reference_no_from: refFrom || null,
      reference_no_to: refTo || null,
      batch_id: batchId || null,
    };

    try {
      setSubmitting(true);
      const r = await fetch(`${API_BASE}/transfers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const body = await r.text().catch(() => "");
        throw new Error(`Create failed: HTTP ${r.status}${body ? ` – ${body}` : ""}`);
      }
      const created = await r.json(); // has income_tx_id/expense_tx_id
      const nextId = created?.income_tx_id ?? null;
      router.push(nextId ? `/transactions/${nextId}` : `/transactions`);
    } catch (err: any) {
      setError(err?.message ?? "Failed to create income");
    } finally {
      setSubmitting(false);
    }
  }

  const input = "w-full rounded-xl border border-gray-300 px-3 py-2 outline-none focus:ring focus:ring-blue-100";
  const label = "block text-xs text-gray-500 mb-1";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">New Income</h1>
        <div className="flex items-center gap-2 text-sm">
          <a href="/transactions/new" className="rounded-lg border px-3 py-1.5 hover:bg-gray-50">+ Expense</a>
          <a href="/transactions" className="rounded-lg border px-3 py-1.5 hover:bg-gray-50">View history</a>
        </div>
      </div>

      <form onSubmit={onSubmit} className="rounded-3xl border bg-white p-6 shadow-sm space-y-6">
        {error && <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className={label}>Date *</span>
            <input type="date" value={date} onChange={e=>setDate(e.target.value)} className={input} required />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Amount (₱) *</span>
            <input type="number" min="0.01" step="0.01" inputMode="decimal" placeholder="0.00"
              value={amount} onChange={e=>setAmount(e.target.value)} className={input} required />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Fund (optional)</span>
            <select value={fundId} onChange={e=>setFundId(e.target.value)} className={input} disabled={loading}>
              <option value="">— None —</option>
              {sortedFunds.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1">
            <span className={label}>Source account *</span>
            <select value={fromAccountId} onChange={e=>setFromAccountId(e.target.value)} className={input} disabled={loading}>
              {sortedAccounts.map(a => (
                <option key={a.id} value={a.id}>
                  {a.name}{a.institution ? ` • ${a.institution}` : ""} ({a.type})
                </option>
              ))}
            </select>
            <span className="mt-1 text-[11px] text-gray-500">
              For Sunday collection, use “Collection Basket / Undeposited Funds” as the source.
            </span>
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Deposit to *</span>
            <select value={toAccountId} onChange={e=>setToAccountId(e.target.value)} className={input} disabled={loading}>
              {sortedAccounts.map(a => (
                <option key={a.id} value={a.id}>
                  {a.name}{a.institution ? ` • ${a.institution}` : ""} ({a.type})
                </option>
              ))}
            </select>
            <span className="mt-1 text-[11px] text-gray-500">
              Example: “BPI Checking” or “Cash on Hand”.
            </span>
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className={label}>Reference (source)</span>
            <input className={input} value={refFrom} onChange={e=>setRefFrom(e.target.value)} placeholder="e.g., OR#/txn#" maxLength={100}/>
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Reference (deposit)</span>
            <input className={input} value={refTo} onChange={e=>setRefTo(e.target.value)} placeholder="e.g., bank slip, check no." maxLength={100}/>
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Batch ID (optional)</span>
            <input className={input} value={batchId} onChange={e=>setBatchId(e.target.value)} placeholder="e.g., Sunday 9AM batch" maxLength={100}/>
          </label>
        </div>

        <label className="flex flex-col gap-1">
          <span className={label}>Notes / Description</span>
          <textarea rows={4} className={input} value={description} onChange={e=>setDescription(e.target.value)}
            placeholder="e.g., Sunday Offering (9:00 AM mass)" />
        </label>

        <div className="flex items-center justify-end gap-3 pt-2">
          <a href="/transactions/new" className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50">Cancel</a>
          <button type="submit" className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60" disabled={submitting}>
            {submitting ? "Saving…" : "Save income"}
          </button>
        </div>
      </form>
    </div>
  );
}
