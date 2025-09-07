"use client";

import React from "react";
import type { Domain } from "../../lib/quality/accounting";
import { accountType } from "../../lib/quality/accounting";

/** Keep types local so the component stays drop‑in and “dumb”. */
export type Account = {
  id: number | string;
  name?: string;
  code?: string;
  type?: string | null;         // preferred
  account_type?: string | null; // fallbacks
  kind?: string | null;
  group?: string | null;
};

export type AccountsFilterProps = {
  /** Visual */
  title?: string;

  /** Data */
  domain: Domain;
  accounts: Account[];     // pass (acctState.data || [])
  loading: boolean;
  error: string | null;

  /** Search state (lifted) */
  search: string;
  setSearch: (s: string) => void;

  /** Selection state (lifted) */
  selected: Array<string | number>;
  setSelected: (ids: Array<string | number>) => void;
};

/** Same categorization logic as the page (duplicated here to keep the component self-contained). */

export default function AccountsFilter({
  title,
  domain,
  accounts,
  loading,
  error,
  search,
  setSearch,
  selected,
  setSelected,
}: AccountsFilterProps) {
  const cardStyle: React.CSSProperties = {
    border: "1px solid #e5e7eb",
    borderRadius: 12,
    padding: 12,
    background: "#fff",
  };

  const gridStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
    gap: 8,
    alignItems: "start",
  };

  const filtered = React.useMemo(() => {
    const q = (search || "").toLowerCase().trim();
    let list = (accounts || []).filter((a) => {
      const t = accountType(a as any);
      if (domain === "expense" && t !== "expense") return false;
      if (domain === "revenue" && t !== "revenue") return false;
      if (domain === "all" && !(t === "expense" || t === "revenue")) return false;
      return true;
    });

    if (q) {
      list = list.filter((a) =>
        (a.name || "").toLowerCase().includes(q) || (a.code || "").toLowerCase().includes(q)
      );
    }

    // Stable-ish sort: revenue/expense first, then by code, then by name.
    list.sort((a, b) => {
      const ta = accountType(a as any);
      const tb = accountType(b as any);
      const rank = (t: string) => (t === "revenue" || t === "expense" ? 0 : 1);
      const ra = rank(ta), rb = rank(tb);
      if (ra !== rb) return ra - rb;
      const ca = (a.code || "");
      const cb = (b.code || "");
      if (ca !== cb) return ca.localeCompare(cb);
      const na = (a.name || "");
      const nb = (b.name || "");
      return na.localeCompare(nb);
    });

    return list;
  }, [accounts, search, domain]);

  const toggle = (id: string | number, checked: boolean) => {
    const set = new Set(selected.map(String));
    if (checked) set.add(String(id)); else set.delete(String(id));
    setSelected(Array.from(set));
  };

  return (
    <div style={cardStyle}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <div style={{ fontWeight: 600 }}>{title || "Accounts"}</div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search account name or code…"
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "6px 10px",
            fontSize: 12,
            minWidth: 220,
          }}
        />
      </div>

      <div style={{ height: 8 }} />

      {loading ? (
        <div style={{ fontSize: 12, color: "#6b7280" }}>Loading accounts…</div>
      ) : error && (accounts || []).length === 0 ? (
        <div style={{ fontSize: 12, color: "#991b1b" }}>
          Accounts unavailable — domain filters may be approximate.
        </div>
      ) : (
        <div style={gridStyle}>
          {filtered.map((a) => (
            <label
              key={String(a.id)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "4px 6px" }}
            >
              <input
                type="checkbox"
                checked={selected.map(String).includes(String(a.id))}
                onChange={(e) => toggle(a.id, e.target.checked)}
                style={{ width: 14, height: 14 }}
              />
              <span style={{ fontSize: 12, color: "#111827" }}>
                {(a.code ? `${a.code} — ` : "") + (a.name || `Account ${String(a.id)}`)}
              </span>
              <span style={{ fontSize: 11, color: "#6b7280" }}>({accountType(a as any)})</span>
            </label>
          ))}
        </div>
      )}

      <div style={{ height: 8 }} />

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <button
          onClick={() => setSelected([])}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: "6px 10px",
            fontSize: 12,
            background: "#fff",
          }}
        >
          Clear
        </button>
        <div style={{ fontSize: 12, color: "#6b7280" }}>
          Selected: {selected.length}
        </div>
      </div>
    </div>
  );
}
