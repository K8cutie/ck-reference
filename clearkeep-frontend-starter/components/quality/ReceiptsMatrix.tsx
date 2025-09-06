"use client";

import React from "react";

/** Row shape from the existing inline matrix. */
export type MatrixRow = {
  key: string;
  label: string;
  values: number[]; // per-month values aligned with `months`
  total: number;
};

export type ReceiptsMatrixProps = {
  /** Visuals */
  title?: string; // heading above the table (optional)

  /** Data */
  months: string[];           // column labels (e.g., ["2025-06","2025-07","2025-08"])
  rows: MatrixRow[];          // sorted rows
  colTotals: number[];        // per-month totals across rows
  grandTotal: number;         // sum(colTotals)

  /** Formatting & filenames */
  format?: (n: number) => string;      // default: Intl.NumberFormat with 2 decimals
  exportBaseName?: string;             // used for file names, default: "receipts_matrix"
  exportSuffix?: string;               // appended to base name (e.g., "2025-06_to_2025-08")
};

export default function ReceiptsMatrix({
  title,
  months,
  rows,
  colTotals,
  grandTotal,
  format,
  exportBaseName = "receipts_matrix",
  exportSuffix,
}: ReceiptsMatrixProps) {
  const fmt =
    format ||
    ((n: number) =>
      new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(n));

  const headerStyle: React.CSSProperties = {
    display: "flex",
    gap: 8,
    marginBottom: 8,
    alignItems: "center",
    flexWrap: "wrap",
  };

  const boxStyle: React.CSSProperties = {
    border: "1px solid #e5e7eb",
    borderRadius: 8,
    background: "#fff",
    padding: 12,
  };

  const btnStyle: React.CSSProperties = {
    padding: "8px 10px",
    border: "1px solid #d1d5db",
    borderRadius: 6,
    background: "#f9fafb",
    cursor: "pointer",
    fontSize: 12,
  };

  const tableWrap: React.CSSProperties = { overflowX: "auto" };
  const thBase: React.CSSProperties = {
    textAlign: "right",
    padding: 8,
    borderBottom: "1px solid #e5e7eb",
    fontSize: 12,
    whiteSpace: "nowrap",
  };
  const thLeft: React.CSSProperties = { ...thBase, textAlign: "left" };
  const tdBase: React.CSSProperties = {
    textAlign: "right",
    padding: 8,
    borderBottom: "1px solid #f3f4f6",
  };
  const tdLeft: React.CSSProperties = { ...tdBase, textAlign: "left" };

  // ---- File exporting (copied/adapted from the inline implementation) ----
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  };

  const base = exportSuffix
    ? `${exportBaseName}_${exportSuffix}`
    : exportBaseName;

  const exportCSV = () => {
    const header = ["Category", ...months, "Total"];
    const out: string[] = [header.join(",")];

    for (const r of rows) {
      const cat = `"${String(r.label).replace(/"/g, '""')}"`;
      const vals = r.values.map((v) => String(v));
      out.push([cat, ...vals, String(r.total)].join(","));
    }
    out.push(["TOTAL", ...colTotals.map((v) => String(v)), String(grandTotal)].join(","));

    // Add BOM so Excel opens UTF‑8 CSVs cleanly
    const csv = "\uFEFF" + out.join("\r\n");
    downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8" }), `${base}.csv`);
  };

  const exportXLS = () => {
    const esc = (s: string) =>
      s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const ths = months.map((m) => `<th>${esc(m)}</th>`).join("");
    const rowsHtml = rows
      .map((r) => {
        const tds = r.values.map((v) => `<td>${v}</td>`).join("");
        return `<tr><td>${esc(r.label)}</td>${tds}<td>${r.total}</td></tr>`;
      })
      .join("");
    const totTds = colTotals.map((v) => `<td>${v}</td>`).join("");
    const html =
      `<!DOCTYPE html><meta charset="utf-8">` +
      `<table border="1"><thead><tr><th>Category</th>${ths}<th>Total</th></tr></thead>` +
      `<tbody>${rowsHtml}<tr><th>TOTAL</th>${totTds}<th>${grandTotal}</th></tr></tbody></table>`;
    downloadBlob(
      new Blob([html], { type: "application/vnd.ms-excel" }),
      `${base}.xls`
    );
  };
  // ------------------------------------------------------------------------

  return (
    <div style={boxStyle}>
      <div style={headerStyle}>
        {title ? (
          <div style={{ fontWeight: 600, marginRight: "auto" }}>{title}</div>
        ) : null}
        <button onClick={exportCSV} style={btnStyle}>Export CSV</button>
        <button onClick={exportXLS} style={btnStyle}>Export Excel (.xls)</button>
      </div>

      {months.length === 0 ? (
        <div
          style={{
            padding: 12,
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            background: "#fff",
            color: "#6b7280",
            fontSize: 12,
          }}
        >
          No months to display.
        </div>
      ) : rows.length === 0 ? (
        <div
          style={{
            padding: 12,
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            background: "#fff",
            color: "#6b7280",
            fontSize: 12,
          }}
        >
          No matching rows for the current filters.
        </div>
      ) : (
        <div style={tableWrap}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={thLeft}>Category</th>
                {months.map((m) => (
                  <th key={m} style={thBase}>
                    {m}
                  </th>
                ))}
                <th style={thBase}>Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td style={tdLeft}>{r.label}</td>
                  {r.values.map((v, i) => (
                    <td key={i} style={tdBase}>
                      {fmt(v)}
                    </td>
                  ))}
                  <td style={{ ...tdBase, fontWeight: 600 }}>{fmt(r.total)}</td>
                </tr>
              ))}
              <tr>
                <th style={{ ...thLeft, borderTop: "1px solid #e5e7eb" }}>
                  TOTAL
                </th>
                {colTotals.map((v, i) => (
                  <th
                    key={i}
                    style={{ ...thBase, borderTop: "1px solid #e5e7eb" }}
                  >
                    {fmt(v)}
                  </th>
                ))}
                <th style={{ ...thBase, borderTop: "1px solid #e5e7eb" }}>
                  {fmt(grandTotal)}
                </th>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
