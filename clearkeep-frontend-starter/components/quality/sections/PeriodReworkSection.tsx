"use client";

import React from "react";

type Props = {
  /** Sorted list of YYYY-MM month labels to display */
  months: string[];
  /** Map of YYYY-MM → note string (e.g., "reopened 2025-07-03") */
  reopenedNotes: Map<string, string>;
  /** Optional custom heading */
  heading?: string;
};

/**
 * PeriodReworkSection — simple, dependency-free table that lists months
 * and whether each was reopened/reclosed (with note).
 * Pure presentational; computes nothing.
 */
export default function PeriodReworkSection({ months, reopenedNotes, heading }: Props) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 12, background: "#fff" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>
        {heading ?? "Defects — Reopened / Reclosed Months"}
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Month", "Defect?", "Note"].map((h) => (
                <th
                  key={h}
                  style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb", fontSize: 12 }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {months.length === 0 ? (
              <tr>
                <td colSpan={3} style={{ padding: 8, fontSize: 12, color: "#6b7280" }}>
                  No months found in selection.
                </td>
              </tr>
            ) : (
              months.map((m) => (
                <tr key={m}>
                  <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{m}</td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>
                    {reopenedNotes.has(m) ? "Yes" : "No"}
                  </td>
                  <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>
                    {reopenedNotes.get(m) || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
