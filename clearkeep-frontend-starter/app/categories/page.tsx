"use client";

import * as React from "react";

type Category = {
  id: number;
  name: string;
  description?: string | null;
};

type GLAccount = {
  id: number;
  code: string;
  name: string;
};

type GLMap = {
  category_id: number;
  debit_account_id?: number | null;
  credit_account_id?: number | null;
  debit_account?: GLAccount | null;
  credit_account?: GLAccount | null;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "").replace(/\/+$/, "");
const TZ = process.env.NEXT_PUBLIC_TZ || "Asia/Manila";

function q(params: Record<string, any>) {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    s.set(k, String(v));
  }
  const str = s.toString();
  return str ? `?${str}` : "";
}

export default function CategoriesPage() {
  const [rows, setRows] = React.useState<Category[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  const [accounts, setAccounts] = React.useState<GLAccount[]>([]);
  const [acctErr, setAcctErr] = React.useState<string | null>(null);

  // Mapping dialog state
  const [openId, setOpenId] = React.useState<number | null>(null);
  const [mapLoading, setMapLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [mapErr, setMapErr] = React.useState<string | null>(null);
  const [glMap, setGlMap] = React.useState<GLMap | null>(null);

  async function fetchCategories() {
    setLoading(true);
    setErr(null);
    try {
      const res = await fetch(`${API_BASE}/categories/${q({ limit: 500 })}`, {
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
        cache: "no-store",
      });
      if (!res.ok) throw new Error(await res.text());
      const payload = await res.json();
      const list: Category[] = Array.isArray(payload)
        ? payload
        : payload.items || payload.results || payload.value || payload; // tolerate shapes
      setRows(list);
    } catch (e: any) {
      setErr(e?.message || "Failed to load categories");
    } finally {
      setLoading(false);
    }
  }

  async function fetchAccounts() {
    setAcctErr(null);
    try {
      const res = await fetch(
        `${API_BASE}/gl/accounts${q({ is_active: "true", limit: 200 })}`,
        { headers: { "Content-Type": "application/json", "X-TZ": TZ } }
      );
      if (!res.ok) throw new Error(await res.text());
      const payload = await res.json();
      const list: GLAccount[] = Array.isArray(payload)
        ? payload
        : payload.items || payload.results || payload;
      setAccounts(list);
    } catch (e: any) {
      setAcctErr(e?.message || "Failed to load GL accounts");
    }
  }

  React.useEffect(() => {
    fetchCategories();
    fetchAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openMapDialog(catId: number) {
    setOpenId(catId);
    setMapErr(null);
    setMapLoading(true);
    try {
      const res = await fetch(`${API_BASE}/categories/${catId}/glmap`, {
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
        cache: "no-store",
      });
      if (!res.ok) throw new Error(await res.text());
      const payload: GLMap = await res.json();
      setGlMap(payload);
    } catch (e: any) {
      setMapErr(e?.message || "Failed to load mapping");
    } finally {
      setMapLoading(false);
    }
  }

  async function saveMap() {
    if (!glMap) return;
    setSaving(true);
    setMapErr(null);
    try {
      const res = await fetch(`${API_BASE}/categories/${glMap.category_id}/glmap`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", "X-TZ": TZ },
        body: JSON.stringify({
          debit_account_id: glMap.debit_account_id ?? null,
          credit_account_id: glMap.credit_account_id ?? null,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const payload: GLMap = await res.json();
      setGlMap(payload);
      setOpenId(null);
    } catch (e: any) {
      setMapErr(e?.message || "Failed to save mapping");
    } finally {
      setSaving(false);
    }
  }

  function accountLabel(a?: GLAccount | null) {
    return a ? `${a.code} — ${a.name}` : "—";
  }

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Categories</h1>
          <p className="text-sm text-gray-500">
            Manage Category → GL mapping used for automatic journal posting.
          </p>
        </div>
      </header>

      {/* Accounts fetch note */}
      {acctErr && (
        <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
          {acctErr}
        </div>
      )}

      {/* Table */}
      <section className="rounded-2xl border bg-white shadow-sm overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-700">
            <tr className="[&>th]:px-4 [&>th]:py-3 text-left">
              <th className="w-16">ID</th>
              <th>Name</th>
              <th className="w-1/2">Description</th>
              <th className="w-40">Actions</th>
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
            {!loading && err && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-red-600">
                  {err}
                </td>
              </tr>
            )}
            {!loading && !err && rows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-gray-500">
                  No categories found.
                </td>
              </tr>
            )}
            {!loading &&
              !err &&
              rows.map((c) => (
                <tr key={c.id} className="border-t">
                  <td className="px-4 py-2 font-mono">{c.id}</td>
                  <td className="px-4 py-2">{c.name}</td>
                  <td className="px-4 py-2 text-gray-600">
                    {c.description || "—"}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => openMapDialog(c.id)}
                      className="px-3 py-2 rounded-xl border bg-white"
                    >
                      Configure GL map
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </section>

      {/* Mapping dialog */}
      {openId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-lg font-semibold">
                Category GL Mapping — ID {glMap?.category_id ?? openId}
              </h2>
              <button
                className="text-gray-500 hover:text-gray-700"
                onClick={() => setOpenId(null)}
                aria-label="Close dialog"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-4">
              {mapLoading ? (
                <div className="text-sm text-gray-500">Loading…</div>
              ) : mapErr ? (
                <div className="rounded-xl bg-red-50 text-red-700 px-3 py-2 text-sm">
                  {mapErr}
                </div>
              ) : glMap ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-1">
                        Debit account
                      </label>
                      <select
                        value={glMap.debit_account_id ?? 0}
                        onChange={(e) =>
                          setGlMap((s) =>
                            s
                              ? {
                                  ...s,
                                  debit_account_id:
                                    Number(e.target.value) || null,
                                }
                              : s
                          )
                        }
                        className="w-full rounded-xl border px-3 py-2 bg-white"
                      >
                        <option value={0}>— none —</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </option>
                        ))}
                      </select>
                      <div className="mt-1 text-xs text-gray-500">
                        Current: {accountLabel(glMap.debit_account)}
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-1">
                        Credit account
                      </label>
                      <select
                        value={glMap.credit_account_id ?? 0}
                        onChange={(e) =>
                          setGlMap((s) =>
                            s
                              ? {
                                  ...s,
                                  credit_account_id:
                                    Number(e.target.value) || null,
                                }
                              : s
                          )
                        }
                        className="w-full rounded-xl border px-3 py-2 bg-white"
                      >
                        <option value={0}>— none —</option>
                        {accounts.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.code} — {a.name}
                          </option>
                        ))}
                      </select>
                      <div className="mt-1 text-xs text-gray-500">
                        Current: {accountLabel(glMap.credit_account)}
                      </div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <div className="rounded-xl bg-gray-50 p-3 text-xs text-gray-700">
                      <div className="font-medium mb-1">Rule summary</div>
                      <div className="space-y-1">
                        <div>
                          <span className="font-medium">Income:</span> Dr{" "}
                          <span className="font-mono">
                            debit_account
                          </span>{" "}
                          / Cr{" "}
                          <span className="font-mono">
                            credit_account
                          </span>
                        </div>
                        <div>
                          <span className="font-medium">Expense:</span> Dr{" "}
                          <span className="font-mono">
                            debit_account
                          </span>{" "}
                          / Cr{" "}
                          <span className="font-mono">
                            credit_account
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            <div className="flex items-center justify-end gap-2 border-t px-4 py-3">
              <button
                type="button"
                onClick={() => setOpenId(null)}
                className="px-3 py-2 rounded-xl border bg-white"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={saveMap}
                disabled={saving || !glMap}
                className="px-3 py-2 rounded-2xl bg-black text-white shadow disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save mapping"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
