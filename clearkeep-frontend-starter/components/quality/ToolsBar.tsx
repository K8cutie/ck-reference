"use client";

import React from "react";

export type ToolView =
  | "pchart"
  | "xmr"
  | "pareto_accounts"
  | "pareto_defects"
  | "acct_trend_mom"
  | "receipts_matrix"
  | "all";

type Props = {
  value: ToolView;
  onChange: (v: ToolView) => void;
};

const BUTTONS: { key: ToolView; label: string }[] = [
  { key: "pchart",            label: "p-Chart" },
  { key: "xmr",               label: "XmR" },
  { key: "pareto_accounts",   label: "Pareto (Account)" },
  { key: "pareto_defects",    label: "Pareto (Defects)" },
  { key: "acct_trend_mom",    label: "Account Trend (MoM)" },
  { key: "receipts_matrix",   label: "Receipts Matrix" },
  { key: "all",               label: "All" },
];

function btnStyle(active: boolean): React.CSSProperties {
  return {
    padding: "8px 10px",
    border: "1px solid #d1d5db",
    borderRadius: 6,
    background: active ? "#111827" : "#fff",
    color: active ? "#fff" : "#374151",
    cursor: "pointer",
    fontSize: 12,
  };
}

/** Pure presentational toolbar for switching Six Sigma tool views */
export default function ToolsBar({ value, onChange }: Props) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", padding: 12 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600, fontSize: 13 }}>Six Sigma tools</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }} role="tablist" aria-label="Six Sigma tools">
          {BUTTONS.map((b) => (
            <button
              key={b.key}
              type="button"
              onClick={() => onChange(b.key)}
              aria-pressed={value === b.key}
              style={btnStyle(value === b.key)}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
