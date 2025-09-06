"use client";

import React from "react";

/** Keep types local so the component stays drop‑in and “dumb”. */
export type Domain = "expense" | "revenue" | "all";

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
function accountType(a: Account | undefined): string {
  if (!a) return "other";
  const t = (a.type || a.account_type || a.kind || a.group || "").toString().toLowerCase();
  if (t.includes("expens")) return "expense";
  if (t.includes("revenue") || t.includes("income") || t === "sales") return "revenue";
  return t || "other";
}

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
    borderRadius: 8,
    padding: 12,
    background: "#fff",
    marginBottom: 12,
  };

  const headerStyle: React.CSSProperties = {
    display: "flex",
    gap: 12,
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  };

  const inputStyle: React.CSSProperties = {
    padding: 8,
    border: "1px solid #d1d5db",
    borderRadius: 6,
    width: 320,
  };

  const gridStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
    gap: 6,
    maxHeight: 220,
    overflowY: "auto",
  };

  const filtered = React.useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = (accounts || []).filter((a) => {
      const t = accountType(a);
      if (domain === "expense" && t !== "expense") return false;
      if (domain === "revenue" && t !== "revenue") return false;
      if (!q) return true;
      const hay = `${a.name || ""} ${a.code || ""}`.toLowerCase();
      return hay.includes(q);
    });
    return list.sort(
      (a, b) =>
        (a.code || "").localeCompare(b.code || "") ||
        (a.name || "").localeCompare(b.name || "")
    );
  }, [accounts, domain, search]);

  const toggle = (id: string | number) =>
    setSelected(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);

  const clearSelection = () => setSelected([]);
  const selectAllShown = () => setSelected(filtered.map((a) => a.id));

  return (
    <div style={cardStyle} role="region" aria-label="Accounts filter">
      <div style={headerStyle}>
        <div style={{ fontWeight: 600 }}>
          {title ?? "Accounts"} ({domain})
        </div>
        <input
          type="text"
          placeholder="Search account name or code…"
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          style={inputStyle}
          aria-label="Search accounts"
        />
      </div>

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
                checked={selected.includes(a.id)}
                onChange={() => toggle(a.id)}
                aria-label={`Toggle ${a.code ? `${a.code} — ` : ""}${a.name || `Account ${String(a.id)}`}`}
              />
              <span style={{ fontSize: 12, color: "#374151" }}>
                {(a.code ? `${a.code} — ` : "") + (a.name || `Account ${String(a.id)}`)}
              </span>
            </label>
          ))}
          {filtered.length === 0 && (
            <div style={{ fontSize: 12, color: "#6b7280", padding: "4px 6px" }}>
              No accounts match your filters.
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
        <button
          onClick={clearSelection}
          style={{
            padding: "6px 10px",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            background: "#f9fafb",
          }}
        >
          Clear selection
        </button>
        <button
          onClick={selectAllShown}
          style={{
            padding: "6px 10px",
            border: "1px solid #d1d5db",
            borderRadius: 6,
            background: "#f9fafb",
          }}
        >
          Select all shown
        </button>
      </div>
    </div>
  );
}
