"use client";

import React, { useMemo, useState } from "react";

type Account = {
  id: number | string;
  code?: string | null;
  name?: string | null;
  type?: string | null;
  account_type?: string | null;
  kind?: string | null;
  group?: string | null;
};

type Props = {
  title?: string;
  accounts: Account[];
};

function downloadCSV(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function toCSV(rows: Account[]) {
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const header = ["id", "code", "name", "type", "account_type", "kind", "group"].map(esc).join(",");
  const lines = rows.map(r =>
    [
      esc(String(r.id ?? "")),
      esc(String(r.code ?? "")),
      esc(String(r.name ?? "")),
      esc(String(r.type ?? "")),
      esc(String(r.account_type ?? "")),
      esc(String(r.kind ?? "")),
      esc(String(r.group ?? "")),
    ].join(",")
  );
  return [header, ...lines].join("\r\n");
}

export default function AccountsCatalog({ title = "Accounts Catalog", accounts }: Props) {
  const [q, setQ] = useState("");
  const [sortBy, setSortBy] = useState<"id" | "code" | "name">("name");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let rows = accounts || [];
    if (needle) {
      rows = rows.filter(a =>
        String(a.id ?? "").toLowerCase().includes(needle) ||
        String(a.code ?? "").toLowerCase().includes(needle) ||
        String(a.name ?? "").toLowerCase().includes(needle)
      );
    }
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = String((a as any)[sortBy] ?? "").toLowerCase();
      const bv = String((b as any)[sortBy] ?? "").toLowerCase();
      return av.localeCompare(bv);
    });
    return copy.slice(0, 2000); // safety cap for UI
  }, [accounts, q, sortBy]);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
      <div style={{ padding: 12, borderBottom: "1px solid #e5e7eb", display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ fontWeight: 700 }}>{title}</div>
        <input
          placeholder="Search id / code / name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ flex: 1, border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px" }}
        />
        <select
          value={sortBy}
          onChange={(e)=>setSortBy(e.target.value as any)}
          title="Sort by"
          style={{ border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px" }}
        >
          <option value="name">Sort: Name</option>
          <option value="code">Sort: Code</option>
          <option value="id">Sort: ID</option>
        </select>
        <button
          onClick={() => downloadCSV("accounts_catalog.csv", toCSV(filtered))}
          style={{ border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px", background: "#fff", cursor: "pointer", fontSize: 12 }}
          title="Export CSV"
        >
          Export CSV
        </button>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f9fafb" }}>
              {["ID","Code","Name","Type","Account Type","Kind","Group"].map(h => (
                <th key={h} style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 12 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr><td colSpan={7} style={{ padding: 12, color: "#6b7280", fontSize: 12 }}>No matches</td></tr>
            ) : filtered.map(a => (
              <tr key={String(a.id)}>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{a.id}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{a.code ?? ""}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{a.name ?? ""}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", color: "#6b7280", fontSize: 12 }}>{a.type ?? ""}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", color: "#6b7280", fontSize: 12 }}>{a.account_type ?? ""}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", color: "#6b7280", fontSize: 12 }}>{a.kind ?? ""}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", color: "#6b7280", fontSize: 12 }}>{a.group ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ padding: 12, fontSize: 12, color: "#6b7280" }}>
        Tip: copy IDs from here and pin them into <code>lib/quality/receipts_categories.ts</code> under the right category’s <code>account_ids</code>.
      </div>
    </div>
  );
}
