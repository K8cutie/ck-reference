"use client";

import React, { useMemo } from "react";
import type { ReceiptMatrix } from "../../../lib/quality/selectors";
import { compareMatrices } from "../../../lib/quality/projections";

/**
 * VarianceSection
 * Shows a variance matrix (Actual vs Budget) with colored deltas,
 * and includes CSV / Excel exports. Pure presentational; no fetching.
 *
 * We compute:  Actual − Budget  (positive = green by default)
 */

type Props = {
  title?: string;
  actual: ReceiptMatrix;
  budget: ReceiptMatrix;
  /** Formats currency/number, e.g., (n)=>`₱ ${fmt(n)}` */
  format: (n: number) => string;
  /** If true, positive deltas are green (favorable). Default true. */
  positiveIsGood?: boolean;
};

/* ----------------------------- export helpers ----------------------------- */

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function toCSV(
  months: string[],
  rows: Array<{ label: string; abs: number[]; totalAbs: number }>,
  format: (n: number) => string
) {
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const header = ["Category", ...months, "Total Δ"].map(esc).join(",");
  const lines: string[] = [header];

  for (const r of rows) {
    lines.push([esc(r.label), ...r.abs.map(v => format(v)), esc(format(r.totalAbs))].join(","));
  }
  return lines.join("\r\n");
}

function toExcelHTML(
  months: string[],
  rows: Array<{ label: string; abs: number[]; totalAbs: number }>
) {
  const tdRight = `style="mso-number-format:'0'; text-align:right; padding:4px; border-bottom:1px solid #eee"`;
  const tdLeft  = `style="text-align:left; padding:4px; border-bottom:1px solid #eee"`;
  const th      = `style="text-align:right; padding:4px; border-bottom:1px solid #ddd; background:#f9f9f9"`;
  const thFirst = `style="text-align:left;  padding:4px; border-bottom:1px solid #ddd; background:#f9f9f9"`;

  const esc = (s: string) => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

  const parts: string[] = [];
  parts.push(`<table border="0" cellspacing="0" cellpadding="0">`);
  parts.push(`<tr><th ${thFirst}>Category</th>${months.map(m=>`<th ${th}>${esc(m)}</th>`).join("")}<th ${th}>Total Δ</th></tr>`);
  for (const r of rows) {
    parts.push(
      `<tr><td ${tdLeft}>${esc(r.label)}</td>${r.abs.map(v=>`<td ${tdRight}>${Number(v)||0}</td>`).join("")}<td ${tdRight}>${Number(r.totalAbs)||0}</td></tr>`
    );
  }
  parts.push(`</table>`);
  return `<!DOCTYPE html><html><head><meta charset="utf-8" /></head><body>${parts.join("")}</body></html>`;
}

/* -------------------------------- Component -------------------------------- */

export default function VarianceSection({
  title = "Variance — Actual vs Budget",
  actual,
  budget,
  format,
  positiveIsGood = true,
}: Props) {
  // Compare B - A using our helper; we want Actual − Budget,
  // so pass A = budget, B = actual (B minus A).
  const variance = useMemo(() => compareMatrices(budget, actual), [budget, actual]);

  const green = (v: number) => positiveIsGood ? v >= 0 : v < 0;
  const colorOf = (v: number) => (green(v) ? "#10b981" : "#ef4444"); // green/red

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
      {/* Header */}
      <div style={{ padding: 12, borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ fontWeight: 700 }}>{title}</div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            onClick={() => downloadBlob(
              "variance.csv",
              new Blob([toCSV(variance.months, variance.rows.map(r => ({
                label: r.label,
                abs: r.abs,
                totalAbs: r.totalAbs,
              })), format)], { type: "text/csv;charset=utf-8;" })
            )}
            style={{ border: "1px solid #d1d5db", borderRadius: 6, padding: "4px 8px", background: "#fff", cursor: "pointer", fontSize: 12 }}
          >
            Export CSV
          </button>
          <button
            onClick={() => downloadBlob(
              "variance.xls",
              new Blob([toExcelHTML(
                variance.months,
                variance.rows.map(r => ({ label: r.label, abs: r.abs, totalAbs: r.totalAbs }))
              )], { type: "application/vnd.ms-excel;charset=utf-8" })
            )}
            style={{ border: "1px solid #d1d5db", borderRadius: 6, padding: "4px 8px", background: "#fff", cursor: "pointer", fontSize: 12 }}
          >
            Export Excel
          </button>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f9fafb" }}>
              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Category</th>
              {variance.months.map(m => (
                <th key={m} style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #e5e7eb" }}>{m}</th>
              ))}
              <th style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Total Δ</th>
            </tr>
          </thead>
          <tbody>
            {variance.rows.length === 0 ? (
              <tr><td colSpan={variance.months.length + 2} style={{ padding: 12, color: "#6b7280", fontSize: 12 }}>No variance</td></tr>
            ) : variance.rows.map(r => (
              <tr key={r.label}>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{r.label}</td>
                {r.abs.map((v, i) => (
                  <td key={i} style={{ padding: 8, borderBottom: "1px solid #f3f4f6", textAlign: "right", color: colorOf(v) }}>
                    {format(v)}{" "}
                    <span style={{ color: "#9ca3af", fontSize: 11 }}>
                      ({isFinite(r.pct[i]) ? (r.pct[i] * 100).toFixed(1) : "0.0"}%)
                    </span>
                  </td>
                ))}
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", textAlign: "right", fontWeight: 700, color: colorOf(r.totalAbs) }}>
                  {format(r.totalAbs)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ background: "#f9fafb" }}>
              <td style={{ padding: 8, borderTop: "1px solid #e5e7eb", fontWeight: 700 }}>Totals Δ</td>
              {variance.colAbs.map((v, i) => (
                <td key={i} style={{ padding: 8, borderTop: "1px solid #e5e7eb", textAlign: "right", fontWeight: 700, color: colorOf(v) }}>
                  {format(v)}
                </td>
              ))}
              <td style={{ padding: 8, borderTop: "1px solid #e5e7eb", textAlign: "right", fontWeight: 700, color: colorOf(variance.grandAbs) }}>
                {format(variance.grandAbs)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
