"use client";

import React, { useMemo, useState } from "react";

export type MatrixRow = {
  key: string;
  label: string;
  values: number[];
  total: number;
  children?: MatrixRow[];
};

type Props = {
  title?: string;
  months: string[];
  rows: MatrixRow[];
  colTotals: number[];
  grandTotal: number;
  format: (n: number) => string;
  // optional drilldown
  onCellClick?: (args: { rowKey: string; month: string; value: number }) => void;
  // options
  allowSort?: boolean;      // default true
  showTotalsRow?: boolean;  // default true
  expandable?: boolean;     // default true
};

/* ----------------------------- Export helpers ----------------------------- */

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** CSV export (human-formatted using the provided formatter) */
function toCSV(
  months: string[],
  rows: MatrixRow[],
  colTotals: number[],
  grandTotal: number,
  fmt: (n: number) => string
) {
  const esc = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const header = ["Category", ...months, "Total"].map(esc).join(",");
  const lines: string[] = [header];

  for (const r of rows) {
    lines.push([esc(r.label), ...r.values.map(v => fmt(v)), esc(fmt(r.total))].join(","));
    if (r.children) {
      for (const c of r.children) {
        lines.push([esc("  " + c.label), ...c.values.map(v => fmt(v)), esc(fmt(c.total))].join(","));
      }
    }
  }
  lines.push([esc("Column Totals"), ...colTotals.map(v => fmt(v)), esc(fmt(grandTotal))].join(","));
  return lines.join("\r\n");
}

/**
 * Excel export (HTML table wrapped as .xls) — lightweight, no external libs.
 * We export **raw numbers** (no currency symbols) so Excel keeps them numeric.
 */
function toExcelHTML(months: string[], rows: MatrixRow[], colTotals: number[], grandTotal: number) {
  const tdRight = `style="mso-number-format:'0'; text-align:right; padding:4px; border-bottom:1px solid #eee"`;
  const tdLeft  = `style="text-align:left; padding:4px; border-bottom:1px solid #eee"`;
  const th      = `style="text-align:right; padding:4px; border-bottom:1px solid #ddd; background:#f9f9f9"`;
  const thFirst = `style="text-align:left;  padding:4px; border-bottom:1px solid #ddd; background:#f9f9f9"`;

  const esc = (s: string) => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");

  const parts: string[] = [];
  parts.push(`<table border="0" cellspacing="0" cellpadding="0">`);
  // header
  parts.push(`<tr><th ${thFirst}>Category</th>${months.map(m=>`<th ${th}>${esc(m)}</th>`).join("")}<th ${th}>Total</th></tr>`);

  // rows
  for (const r of rows) {
    parts.push(`<tr><td ${tdLeft}>${esc(r.label)}</td>${r.values.map(v=>`<td ${tdRight}>${Number(v)||0}</td>`).join("")}<td ${tdRight}>${Number(r.total)||0}</td></tr>`);
    if (r.children) {
      for (const c of r.children) {
        parts.push(`<tr><td ${tdLeft}>&nbsp;&nbsp;${esc(c.label)}</td>${c.values.map(v=>`<td ${tdRight}>${Number(v)||0}</td>`).join("")}<td ${tdRight}>${Number(c.total)||0}</td></tr>`);
      }
    }
  }

  // totals
  parts.push(`<tr><td ${thFirst}>Column Totals</td>${colTotals.map(v=>`<td ${th}>${Number(v)||0}</td>`).join("")}<td ${th}>${Number(grandTotal)||0}</td></tr>`);
  parts.push(`</table>`);

  // full HTML doc
  return `<!DOCTYPE html><html><head><meta charset="utf-8" /></head><body>${parts.join("")}</body></html>`;
}

/* -------------------------------- Component -------------------------------- */

export default function ReceiptsMatrixSection({
  title = "Receipts Matrix — Actuals",
  months,
  rows,
  colTotals,
  grandTotal,
  format,
  onCellClick,
  allowSort = true,
  showTotalsRow = true,
  expandable = true,
}: Props) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [sortBy, setSortBy] = useState<"label" | "total">("total");

  const sortedRows = useMemo(() => {
    if (!allowSort) return rows;
    const copy = [...rows];
    if (sortBy === "label") copy.sort((a, b) => a.label.localeCompare(b.label));
    else copy.sort((a, b) => Math.abs(b.total) - Math.abs(a.total));
    return copy;
  }, [rows, sortBy, allowSort]);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
      {/* Header / actions */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: 12,
          borderBottom: "1px solid #e5e7eb",
        }}
      >
        <div style={{ fontWeight: 700 }}>{title}</div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            style={{
              border: "1px solid #d1d5db",
              borderRadius: 6,
              padding: "4px 8px",
              fontSize: 12,
              background: "#fff",
            }}
            title="Sort rows"
          >
            <option value="total">Sort by Total (desc)</option>
            <option value="label">Sort by Label (A→Z)</option>
          </select>

          {/* CSV */}
          <button
            onClick={() =>
              downloadBlob(
                "receipts_matrix.csv",
                new Blob([toCSV(months, rows, colTotals, grandTotal, format)], {
                  type: "text/csv;charset=utf-8;",
                })
              )
            }
            style={{
              border: "1px solid #d1d5db",
              borderRadius: 6,
              padding: "4px 8px",
              background: "#fff",
              cursor: "pointer",
              fontSize: 12,
            }}
            title="Export CSV"
          >
            Export CSV
          </button>

          {/* Excel (.xls via HTML table) */}
          <button
            onClick={() => {
              const html = toExcelHTML(months, rows, colTotals, grandTotal);
              downloadBlob(
                "receipts_matrix.xls",
                new Blob([html], { type: "application/vnd.ms-excel;charset=utf-8" })
              );
            }}
            style={{
              border: "1px solid #d1d5db",
              borderRadius: 6,
              padding: "4px 8px",
              background: "#fff",
              cursor: "pointer",
              fontSize: 12,
            }}
            title="Export Excel (.xls)"
          >
            Export Excel
          </button>
        </div>
      </div>

      {/* Grid */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f9fafb" }}>
              <th
                style={{
                  position: "sticky",
                  left: 0,
                  background: "#f9fafb",
                  zIndex: 2,
                  padding: 8,
                  borderBottom: "1px solid #e5e7eb",
                  textAlign: "left",
                }}
              >
                Category
              </th>
              {months.map((m) => (
                <th
                  key={m}
                  style={{
                    padding: 8,
                    borderBottom: "1px solid #e5e7eb",
                    textAlign: "right",
                  }}
                >
                  {m}
                </th>
              ))}
              <th
                style={{
                  padding: 8,
                  borderBottom: "1px solid #e5e7eb",
                  textAlign: "right",
                }}
              >
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.length === 0 ? (
              <tr>
                <td
                  colSpan={months.length + 2}
                  style={{ padding: 12, color: "#6b7280", fontSize: 12 }}
                >
                  No data
                </td>
              </tr>
            ) : (
              sortedRows.map((r) => {
                const isOpen = expanded[r.key];
                return (
                  <React.Fragment key={r.key}>
                    <tr>
                      <td
                        style={{
                          position: "sticky",
                          left: 0,
                          background: "#fff",
                          zIndex: 1,
                          padding: 8,
                          borderBottom: "1px solid #f3f4f6",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {r.children && expandable ? (
                          <button
                            onClick={() =>
                              setExpanded((s) => ({ ...s, [r.key]: !isOpen }))
                            }
                            style={{
                              marginRight: 6,
                              border: "1px solid #d1d5db",
                              borderRadius: 4,
                              padding: "0 6px",
                              cursor: "pointer",
                              fontSize: 12,
                              background: "#fff",
                            }}
                            aria-expanded={isOpen}
                            title={isOpen ? "Collapse" : "Expand"}
                          >
                            {isOpen ? "−" : "+"}
                          </button>
                        ) : null}
                        {r.label}
                      </td>
                      {r.values.map((v, j) => (
                        <td
                          key={j}
                          style={{
                            padding: 8,
                            borderBottom: "1px solid #f3f4f6",
                            textAlign: "right",
                            cursor: onCellClick ? "pointer" : "default",
                          }}
                          onClick={() =>
                            onCellClick?.({
                              rowKey: r.key,
                              month: months[j],
                              value: v,
                            })
                          }
                        >
                          {format(v)}
                        </td>
                      ))}
                      <td
                        style={{
                          padding: 8,
                          borderBottom: "1px solid #f3f4f6",
                          textAlign: "right",
                          fontWeight: 700,
                        }}
                      >
                        {format(r.total)}
                      </td>
                    </tr>

                    {isOpen &&
                      r.children?.map((c) => (
                        <tr key={c.key}>
                          <td
                            style={{
                              position: "sticky",
                              left: 0,
                              background: "#fff",
                              zIndex: 1,
                              padding: "8px 8px 8px 32px",
                              borderBottom: "1px solid #f3f4f6",
                            }}
                          >
                            {c.label}
                          </td>
                          {c.values.map((v, j) => (
                            <td
                              key={j}
                              style={{
                                padding: 8,
                                borderBottom: "1px solid #f3f4f6",
                                textAlign: "right",
                              }}
                            >
                              {format(v)}
                            </td>
                          ))}
                          <td
                            style={{
                              padding: 8,
                              borderBottom: "1px solid #f3f4f6",
                              textAlign: "right",
                              fontWeight: 700,
                            }}
                          >
                            {format(c.total)}
                          </td>
                        </tr>
                      ))}
                  </React.Fragment>
                );
              })
            )}
          </tbody>

          {showTotalsRow ? (
            <tfoot>
              <tr style={{ background: "#f9fafb" }}>
                <td
                  style={{
                    position: "sticky",
                    left: 0,
                    background: "#f9fafb",
                    zIndex: 2,
                    padding: 8,
                    borderTop: "1px solid #e5e7eb",
                    fontWeight: 700,
                  }}
                >
                  Column Totals
                </td>
                {colTotals.map((v, j) => (
                  <td
                    key={j}
                    style={{
                      padding: 8,
                      borderTop: "1px solid #e5e7eb",
                      textAlign: "right",
                      fontWeight: 700,
                    }}
                  >
                    {format(v)}
                  </td>
                ))}
                <td
                  style={{
                    padding: 8,
                    borderTop: "1px solid #e5e7eb",
                    textAlign: "right",
                    fontWeight: 700,
                  }}
                >
                  {format(grandTotal)}
                </td>
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
    </div>
  );
}
