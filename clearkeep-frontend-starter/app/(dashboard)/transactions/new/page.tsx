// app/(dashboard)/transactions/new/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type Category = { id: number; name: string; description?: string | null };
type ExpenseStatus = "PENDING" | "PAID";

export default function NewExpensePage() {
  const router = useRouter();

  // form state
  const [expenseDate, setExpenseDate] = useState(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  });
  const [amount, setAmount] = useState<string>("");
  const [categoryId, setCategoryId] = useState<string>("");
  const [vendorName, setVendorName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [status, setStatus] = useState<ExpenseStatus>("PENDING");
  const [dueDate, setDueDate] = useState<string>("");
  const [paidAtLocal, setPaidAtLocal] = useState<string>(""); // datetime-local
  const [paymentMethod, setPaymentMethod] = useState<string>("");
  const [referenceNo, setReferenceNo] = useState<string>("");

  // categories
  const [categories, setCategories] = useState<Category[]>([]);
  const [loadingCats, setLoadingCats] = useState<boolean>(true);

  // ui state
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // "Add category" modal state
  const [showAddCat, setShowAddCat] = useState(false);
  const [newCatName, setNewCatName] = useState("");
  const [newCatDesc, setNewCatDesc] = useState("");
  const [addingCat, setAddingCat] = useState(false);
  const [addCatError, setAddCatError] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoadingCats(true);
      try {
        const r = await fetch(`${API_BASE}/categories/`, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data: Category[] = await r.json();
        if (!cancel) setCategories(data);
      } catch (e: any) {
        if (!cancel) setError(e?.message ?? "Failed to load categories");
      } finally {
        if (!cancel) setLoadingCats(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  // Hide sacrament/income-style categories from an expense form
  const HIDE_PREFIXES = [/^sacraments/i];
  const catOptions = useMemo(() => {
    const expenseOnly = categories.filter((c) => !HIDE_PREFIXES.some((re) => re.test(c.name)));
    return [{ id: 0, name: "— None —" } as Category].concat(
      expenseOnly.sort((a, b) => a.name.localeCompare(b.name))
    );
  }, [categories]);

  function toIsoFromLocal(local: string): string | null {
    if (!local) return null;
    const d = new Date(local.replace(" ", "T"));
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString();
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const amt = Number(amount);
    if (!expenseDate) return setError("Expense date is required.");
    if (!(amt > 0)) return setError("Amount must be a positive number.");

    const payload: Record<string, any> = {
      expense_date: expenseDate, // YYYY-MM-DD
      amount: amt, // positive
      category_id: categoryId ? Number(categoryId) : null,
      vendor_name: vendorName || null,
      description: description || null,
      status,
      due_date: dueDate || null,
      paid_at: status === "PAID" ? toIsoFromLocal(paidAtLocal) : null, // ISO datetime or null
      payment_method: paymentMethod || null,
      reference_no: referenceNo || null,
    };

    try {
      setSubmitting(true);
      const r = await fetch(`${API_BASE}/expenses/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const body = await r.text().catch(() => "");
        throw new Error(`Create failed: HTTP ${r.status}${body ? ` – ${body}` : ""}`);
      }
      const created = await r.json(); // { id, ... }
      router.push(`/expenses/${created.id}`);
    } catch (err: any) {
      setError(err?.message ?? "Failed to create expense");
    } finally {
      setSubmitting(false);
    }
  }

  async function addCategory(e: React.FormEvent) {
    e.preventDefault();
    setAddCatError(null);

    const name = newCatName.trim();
    const description = newCatDesc.trim();

    if (!name) {
      setAddCatError("Name is required.");
      return;
    }
    // Simple duplicate guard (case-insensitive)
    if (categories.some((c) => c.name.toLowerCase() === name.toLowerCase())) {
      setAddCatError("Category already exists.");
      return;
    }

    try {
      setAddingCat(true);
      const r = await fetch(`${API_BASE}/categories/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: description || null }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const created: Category = await r.json();

      // Update local list and select the new category
      setCategories((prev) => [...prev, created]);
      setCategoryId(String(created.id));

      // Reset & close
      setNewCatName("");
      setNewCatDesc("");
      setShowAddCat(false);
    } catch (err: any) {
      setAddCatError(err?.message ?? "Failed to add category");
    } finally {
      setAddingCat(false);
    }
  }

  const input =
    "w-full rounded-xl border border-gray-300 px-3 py-2 outline-none focus:ring focus:ring-blue-100";
  const label = "block text-xs text-gray-500 mb-1";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">New Expense</h1>
      </div>

      <form onSubmit={onSubmit} className="rounded-3xl border bg-white p-6 shadow-sm space-y-6">
        {error && (
          <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        )}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className={label}>Expense date *</span>
            <input
              type="date"
              value={expenseDate}
              onChange={(e) => setExpenseDate(e.target.value)}
              className={input}
              required
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Amount (₱) *</span>
            <input
              type="number"
              min="0.01"
              step="0.01"
              inputMode="decimal"
              placeholder="0.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={input}
              required
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Status</span>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as ExpenseStatus)}
              className={input}
            >
              <option value="PENDING">Pending</option>
              <option value="PAID">Paid</option>
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {/* Category with "+ Add" */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="block text-xs text-gray-500">Category</span>
              <button
                type="button"
                onClick={() => {
                  setNewCatName("");
                  setNewCatDesc("");
                  setAddCatError(null);
                  setShowAddCat(true);
                }}
                className="text-xs text-blue-700 hover:underline"
              >
                + Add category
              </button>
            </div>
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className={input}
              disabled={loadingCats}
            >
              {catOptions.map((c) => (
                <option key={c.id} value={c.id === 0 ? "" : c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <label className="flex flex-col gap-1">
            <span className={label}>Vendor</span>
            <input
              type="text"
              value={vendorName}
              onChange={(e) => setVendorName(e.target.value)}
              className={input}
              placeholder="e.g., Meralco"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Payment method</span>
            <input
              type="text"
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value)}
              className={input}
              placeholder="Cash, Bank Transfer, GCash…"
              maxLength={50}
            />
          </label>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className={label}>Due date</span>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className={input}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>
              Paid at {status === "PAID" ? "*(required)" : "(if paid)"}
            </span>
            <input
              type="datetime-local"
              value={paidAtLocal}
              onChange={(e) => setPaidAtLocal(e.target.value)}
              className={input}
              required={status === "PAID"}
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className={label}>Reference no.</span>
            <input
              type="text"
              value={referenceNo}
              onChange={(e) => setReferenceNo(e.target.value)}
              className={input}
              maxLength={100}
              placeholder="OR#, invoice#, …"
            />
          </label>
        </div>

        <label className="flex flex-col gap-1">
          <span className={label}>Notes / Description</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className={input}
            placeholder="What is this expense for?"
          />
        </label>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50"
            onClick={() => router.back()}
            disabled={submitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            disabled={submitting}
          >
            {submitting ? "Saving…" : "Save expense"}
          </button>
        </div>
      </form>

      {/* Add Category Modal */}
      {showAddCat && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
          onClick={(e) => {
            if (e.currentTarget === e.target) setShowAddCat(false);
          }}
        >
          <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Add category</h2>
              <button
                type="button"
                onClick={() => setShowAddCat(false)}
                className="rounded-md border px-2 py-1 text-sm hover:bg-gray-50"
              >
                ✕
              </button>
            </div>

            <form onSubmit={addCategory} className="space-y-4">
              {addCatError && (
                <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                  {addCatError}
                </div>
              )}

              <label className="flex flex-col gap-1">
                <span className="block text-xs text-gray-500">Name *</span>
                <input
                  className={input}
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                  placeholder="e.g., Utilities"
                  required
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="block text-xs text-gray-500">Description (optional)</span>
                <input
                  className={input}
                  value={newCatDesc}
                  onChange={(e) => setNewCatDesc(e.target.value)}
                  placeholder="Short description"
                />
              </label>

              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setShowAddCat(false)}
                  className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50"
                  disabled={addingCat}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
                  disabled={addingCat}
                >
                  {addingCat ? "Adding…" : "Add category"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
