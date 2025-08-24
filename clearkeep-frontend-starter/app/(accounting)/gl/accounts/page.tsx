"use client";

import * as React from "react";

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
  description?: string | null;
  created_at?: string;
  updated_at?: string;
};

type ListResponse =
  | GLAccount[]
  | { items?: GLAccount[]; results?: GLAccount[]; total?: number };

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
const TZ = process.env.NEXT_PUBLIC_TZ || "Asia/Manila";

// ------- helpers -------
function toItems(data: ListResponse): GLAccount[] {
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

export default function ChartOfAccountsPage() {
  const [q, setQ] = React.useState("");
  const [type, setType] = React.useState<AccountType | "">("");
  const [onlyActive, setOnlyActive] = React.useState(true);
  const [isCash, setIsCash] = React.useState<"" | "true" | "false">("");
  const [limit, setLimit] = React.useState(25);
  const [offset, setOffset] = React.useState(0);

  const [rows, setRows] = React.useState<GLAccount[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // create dialog
  const [showCreate, setShowCreate] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [cform, setCForm] = React.useState({
    code: "",
    name: "",
    type: "" as AccountType,
    normal_side: "debit" as NormalSide,
    is_cash: false,
    description: "",
  });

  // edit dialog
  const [editId, setEditId] = React.useState<number | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [editError, setEditError] = React.useState<string | null>(null);
  const [eform, setEForm] = React.useState({
    code: "",
    name: "",
    type: "" as AccountType,
    normal_side: "debit" as NormalSide,
    is_cash: false,
    description: "",
  });

  async function fetchAccounts() {
    setLoading(true);
    setError(null);
    try {
      const params = {
        q: q || undefined,
        type: type || undefined,
        is_active: onlyActive ? "true" : undefined,
        is_cash: isCash || undefined,
        limit,
        offset,
      };
      const res = await fetch(`${API_BASE}/gl/accounts${qparams(params)}`, {
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
      });
      if (!res.ok) throw new Error(await res.text());
      setRows(toItems(await res.json()));
    } catch (e: any) {
      setError(e?.message || "Failed to load accounts");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    fetchAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, type, onlyActive, isCash, limit, offset]);

  function resetFilters() {
    setQ("");
    setType("");
    setOnlyActive(true);
    setIsCash("");
    setLimit(25);
    setOffset(0);
  }

  async function createAccount(e: React.FormEvent) {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const body = {
        code: cform.code.trim(),
        name: cform.name.trim(),
        type: cform.type,
        normal_side: cform.normal_side,
        is_cash: !!cform.is_cash,
        description: cform.description?.trim() || null,
      };
      const res = await fetch(`${API_BASE}/gl/accounts`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setShowCreate(false);
      setCForm({
        code: "",
        name: "",
        type: "" as AccountType,
        normal_side: "debit",
        is_cash: false,
        description: "",
      });
      setOffset(0);
      await fetchAccounts();
    } catch (e: any) {
      setCreateError(e?.message || "Failed to create account");
    } finally {
      setCreating(false);
    }
  }

  function openEdit(a: GLAccount) {
    setEditId(a.id);
    setEForm({
      code: a.code,
      name: a.name,
      type: a.type,
      normal_side: a.normal_side,
      is_cash: a.is_cash,
      description: a.description || "",
    });
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editId) return;
    setEditError(null);
    setEditing(true);
    try {
      const body = {
        code: eform.code.trim(),
        name: eform.name.trim(),
        type: eform.type,
        normal_side: eform.normal_side,
        is_cash: !!eform.is_cash,
        description: eform.description?.trim() || null,
      };
      const res = await fetch(`${API_BASE}/gl/accounts/${editId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      setEditId(null);
      await fetchAccounts();
    } catch (e: any) {
      setEditError(e?.message || "Failed to update account");
    } finally {
      setEditing(false);
    }
  }

  async function toggleActive(a: GLAccount) {
    try {
      const res = await fetch(`${API_BASE}/gl/accounts/${a.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
        body: JSON.stringify({ is_active: !a.is_active }),
      });
      if (!res.ok) throw new Error(await res.text());
      await fetchAccounts();
    } catch (e: any) {
      alert("Toggle failed:\n" + (e?.message || "unknown error"));
    }
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Chart of Accounts</h1>
          <p className="text-sm text-gray-500">
            View and manage GL accounts used by Journal Entries and Books.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-2 rounded-2xl bg-black text-white shadow"
          >
            New account
          </button>
        </div>
      </header>

      {/* Filters */}
      <section className="rounded-2xl border p-4 bg-white shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-1">Search</label>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Code or Name"
              className="w-full rounded-xl border px-3 py-2"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full rounded-xl border px-3 py-2 bg-white"
            >
              <option value="">All</option>
              <option value="asset">Asset</option>
              <option value="liability">Liability</option>
              <option value="equity">Equity</option>
              <option value="income">Income</option>
              <option value="expense">Expense</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Cash</label>
            <select
              value={isCash}
              onChange={(e) =>
                setIsCash(e.target.value as "" | "true" | "false")
              }
              className="w-full rounded-xl border px-3 py-2 bg-white"
            >
              <option value="">All</option>
              <option value="true">Cash accounts</option>
              <option value="false">Non-cash</option>
            </select>
          </div>

          <div className="flex items-end">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={onlyActive}
                onChange={(e) => setOnlyActive(e.target.checked)}
                className="rounded"
              />
              <span className="text-sm">Only active</span>
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
              <th className="w-24">Code</th>
              <th>Name</th>
              <th className="w-28">Type</th>
              <th className="w-24">Normal</th>
              <th className="w-20">Cash</th>
              <th className="w-20">Active</th>
              <th className="w-40">Updated</th>
              <th className="w-40">Actions</th>
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
            {!loading && error && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-red-600">
                  {error}
                </td>
              </tr>
            )}
            {!loading && !error && rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-gray-500">
                  No accounts found.
                </td>
              </tr>
            )}
            {!loading &&
              !error &&
              rows.map((a) => (
                <tr key={a.id} className="border-t">
                  <td className="px-4 py-2 font-mono">{a.code}</td>
                  <td className="px-4 py-2">{a.name}</td>
                  <td className="px-4 py-2 capitalize">{a.type}</td>
                  <td className="px-4 py-2 capitalize">{a.normal_side}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${
                        a.is_cash
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {a.is_cash ? "Yes" : "No"}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs ${
                        a.is_active
                          ? "bg-indigo-100 text-indigo-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {a.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">
                    {a.updated_at ? new Date(a.updated_at).toLocaleString() : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openEdit(a)}
                        className="px-2 py-1 rounded-lg border bg-white"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => toggleActive(a)}
                        className={`px-2 py-1 rounded-lg ${
                          a.is_active ? "bg-gray-900 text-white" : "bg-green-600 text-white"
                        }`}
                        title={a.is_active ? "Deactivate" : "Activate"}
                      >
                        {a.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
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
            onClick={() => setOffset((o) => Math.max(0, o - limit))}
            disabled={offset === 0 || loading}
            className="px-3 py-2 rounded-xl border bg-white disabled:opacity-50"
          >
            Prev
          </button>
          <button
            onClick={() => setOffset((o) => o + limit)}
            disabled={loading || rows.length < limit}
            className="px-3 py-2 rounded-xl border bg-white disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </section>

      {/* Create Dialog */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-lg font-semibold">New Account</h2>
              <button
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setShowCreate(false)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={createAccount} className="p-4 space-y-3">
              {createError && (
                <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
                  {createError}
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input
                    required
                    value={cform.code}
                    onChange={(e) =>
                      setCForm((s) => ({ ...s, code: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    required
                    value={cform.name}
                    onChange={(e) =>
                      setCForm((s) => ({ ...s, name: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select
                    required
                    value={cform.type}
                    onChange={(e) =>
                      setCForm((s) => ({ ...s, type: e.target.value as AccountType }))
                    }
                    className="w-full rounded-xl border px-3 py-2 bg-white"
                  >
                    <option value="" disabled>
                      Select a type…
                    </option>
                    <option value="asset">Asset</option>
                    <option value="liability">Liability</option>
                    <option value="equity">Equity</option>
                    <option value="income">Income</option>
                    <option value="expense">Expense</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Normal Side
                  </label>
                  <select
                    required
                    value={cform.normal_side}
                    onChange={(e) =>
                      setCForm((s) => ({
                        ...s,
                        normal_side: e.target.value as NormalSide,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 bg-white"
                  >
                    <option value="debit">Debit</option>
                    <option value="credit">Credit</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={cform.is_cash}
                      onChange={(e) =>
                        setCForm((s) => ({ ...s, is_cash: e.target.checked }))
                      }
                      className="rounded"
                    />
                    <span className="text-sm">Cash account</span>
                  </label>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-1">
                    Description
                  </label>
                  <textarea
                    value={cform.description}
                    onChange={(e) =>
                      setCForm((s) => ({ ...s, description: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                    rows={3}
                  />
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
                  disabled={creating}
                  className="px-3 py-2 rounded-2xl bg-black text-white shadow disabled:opacity-50"
                >
                  {creating ? "Creating…" : "Create account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Dialog */}
      {editId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-lg font-semibold">Edit Account</h2>
              <button
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setEditId(null)}
              >
                ✕
              </button>
            </div>
            <form onSubmit={saveEdit} className="p-4 space-y-3">
              {editError && (
                <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
                  {editError}
                </div>
              )}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input
                    required
                    value={eform.code}
                    onChange={(e) =>
                      setEForm((s) => ({ ...s, code: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    required
                    value={eform.name}
                    onChange={(e) =>
                      setEForm((s) => ({ ...s, name: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select
                    required
                    value={eform.type}
                    onChange={(e) =>
                      setEForm((s) => ({ ...s, type: e.target.value as AccountType }))
                    }
                    className="w-full rounded-xl border px-3 py-2 bg-white"
                  >
                    <option value="asset">Asset</option>
                    <option value="liability">Liability</option>
                    <option value="equity">Equity</option>
                    <option value="income">Income</option>
                    <option value="expense">Expense</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Normal Side
                  </label>
                  <select
                    required
                    value={eform.normal_side}
                    onChange={(e) =>
                      setEForm((s) => ({
                        ...s,
                        normal_side: e.target.value as NormalSide,
                      }))
                    }
                    className="w-full rounded-xl border px-3 py-2 bg-white"
                  >
                    <option value="debit">Debit</option>
                    <option value="credit">Credit</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="inline-flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={eform.is_cash}
                      onChange={(e) =>
                        setEForm((s) => ({ ...s, is_cash: e.target.checked }))
                      }
                      className="rounded"
                    />
                    <span className="text-sm">Cash account</span>
                  </label>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-1">
                    Description
                  </label>
                  <textarea
                    value={eform.description}
                    onChange={(e) =>
                      setEForm((s) => ({ ...s, description: e.target.value }))
                    }
                    className="w-full rounded-xl border px-3 py-2"
                    rows={3}
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditId(null)}
                  className="px-3 py-2 rounded-xl border bg-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editing}
                  className="px-3 py-2 rounded-2xl bg-black text-white shadow disabled:opacity-50"
                >
                  {editing ? "Saving…" : "Save changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
