"use client";

import React from "react";

export type JournalLineRow = {
  date: string;                        // YYYY-MM-DD
  entryId: string | number;
  accountCode?: string | null;
  accountName?: string | null;
  amount: number;                      // signed, already computed for the chosen domain (₱)
};

type Props = {
  open: boolean;
  onClose: () => void;
  /** E.g., "Revenue • Mass Collections — 2025-07" */
  title?: string;
  /** The month key (YYYY-MM) for context, shown in header when title not provided */
  month?: string;
  /** Category label for context (e.g., "Mass Collections") */
  categoryLabel?: string;
  /** Lines to render (already filtered & signed by caller) */
  rows: JournalLineRow[];
  /** Currency/number formatter, e.g., (n)=>`₱ ${fmt(n)}` */
  format: (n: number) => string;
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

function toCSV(rows: JournalLineRow[], fmt: (n: number) => string) {
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const header = ["Date", "Entry ID", "Account", "Amount"].map(esc).join(",");
  const lines = rows.map(r => {
    const acct = [r.accountCode || "", r.accountName || ""].filter(Boolean).join(" — ");
    return [esc(r.date), esc(String(r.entryId)), esc(acct), esc(fmt(r.amount))].join(",");
  });
  return [header, ...lines].join("\r\n");
}

export default function JournalLinesDrawer({
  open,
  onClose,
  title,
  month,
  categoryLabel,
  rows,
  format,
}: Props) {
  if (!open) return null;

  const total = rows.reduce((s, r) => s + (Number(r.amount) || 0), 0);

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.35)",
          zIndex: 60,
        }}
      />

      {/* Drawer */}
      <aside
        role="dialog"
        aria-modal="true"
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100vh",
          width: "min(720px, 92vw)",
          background: "#fff",
          borderLeft: "1px solid #e5e7eb",
          zIndex: 61,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: 12,
            borderBottom: "1px solid #e5e7eb",
            display: "flex",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div style={{ fontWeight: 700, flex: 1 }}>
            {title || `${categoryLabel || "Category"} — ${month || ""}`}
          </div>

          <button
            onClick={() => {
              const nameSafe =
                (categoryLabel || "category").toLowerCase().replace(/\s+/g, "_");
              const file = `journal_lines_${nameSafe}_${month || "range"}.csv`;
              downloadCSV(file, toCSV(rows, format));
            }}
            title="Export CSV"
            style={{
              border: "1px solid #d1d5db",
              borderRadius: 6,
              padding: "6px 10px",
              background: "#fff",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            Export CSV
          </button>

          <button
            onClick={onClose}
            aria-label="Close"
            title="Close"
            style={{
              border: "1px solid #d1d5db",
              borderRadius: 6,
              padding: "6px 10px",
              background: "#fff",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {/* Summary strip */}
        <div
          style={{
            padding: 12,
            borderBottom: "1px solid #e5e7eb",
            display: "flex",
            gap: 12,
            alignItems: "center",
            flexWrap: "wrap",
            background: "#f9fafb",
          }}
        >
          <div style={{ fontSize: 12, color: "#6b7280" }}>
            Lines: <strong style={{ color: "#111827" }}>{rows.length}</strong>
          </div>
          <div style={{ fontSize: 12, color: "#6b7280" }}>
            Total: <strong style={{ color: "#111827" }}>{format(total)}</strong>
          </div>
          {month ? (
            <div style={{ fontSize: 12, color: "#6b7280" }}>
              Month: <strong style={{ color: "#111827" }}>{month}</strong>
            </div>
          ) : null}
          {categoryLabel ? (
            <div style={{ fontSize: 12, color: "#6b7280" }}>
              Category: <strong style={{ color: "#111827" }}>{categoryLabel}</strong>
            </div>
          ) : null}
        </div>

        {/* Table */}
        <div style={{ flex: 1, overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#fff" }}>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 12 }}>Date</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 12 }}>Entry ID</th>
                <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 12 }}>Account</th>
                <th style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 12 }}>Amount</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ padding: 12, color: "#6b7280", fontSize: 12 }}>
                    No lines found for this selection.
                  </td>
                </tr>
              ) : (
                rows.map((r, idx) => (
                  <tr key={`${r.entryId}-${idx}`}>
                    <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{r.date}</td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{r.entryId}</td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>
                      {[r.accountCode || "", r.accountName || ""].filter(Boolean).join(" — ")}
                    </td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", textAlign: "right" }}>
                      {format(r.amount)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </aside>
    </>
  );
}
