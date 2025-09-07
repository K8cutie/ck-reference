"use client";

import React from "react";

export type KPI = {
  units: number;
  defects: number;
  yield: number;   // 0..1
  dpmo: number;
  sigma: number;
};

type Props = {
  /** Required: KPI for Range A */
  a: KPI | null | undefined;
  /** Optional: KPI for Range B (shown when provided) */
  b?: KPI | null;
  /** Label text under A (e.g., "EXPENSE • 2025-06-10 → 2025-09-07") */
  aLabel?: string;
  /** Label text under B */
  bLabel?: string;
};

/** Local integer formatter (no external deps) */
function fmtInt(n: number): string {
  if (!isFinite(n)) return "0";
  return Math.round(n).toLocaleString();
}

function badge(children: React.ReactNode) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 8px",
        border: "1px solid #e5e7eb",
        borderRadius: 999,
        fontSize: 12,
        background: "#fff",
        marginRight: 8,
        marginBottom: 6,
      }}
    >
      {children}
    </span>
  );
}

function Card({
  title,
  footer,
  children,
}: {
  title: string;
  footer?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: 14,
        background: "#fff",
      }}
    >
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{children}</div>
      {footer ? (
        <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>{footer}</div>
      ) : null}
    </div>
  );
}

/**
 * KPI Cards for Six Sigma (Range A and optional Range B).
 * Pure presentational; no fetching and no app-specific imports.
 */
export default function KpiCards({ a, b, aLabel, bLabel }: Props) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: 12,
      }}
    >
      <Card title="Six Sigma — KPIs (A)" footer={aLabel}>
        {a ? (
          <>
            {badge(<>Units: {fmtInt(a.units)}</>)}
            {badge(<>Defects: {fmtInt(a.defects)}</>)}
            {badge(<>Yield: {(a.yield * 100).toFixed(2)}%</>)}
            {badge(<>DPMO: {fmtInt(a.dpmo)}</>)}
            {badge(<>Sigma: {a.sigma.toFixed(2)}</>)}
          </>
        ) : (
          <span style={{ fontSize: 12, color: "#6b7280" }}>No data</span>
        )}
      </Card>

      {typeof b !== "undefined" ? (
        <Card title="Six Sigma — KPIs (B)" footer={bLabel}>
          {b ? (
            <>
              {badge(<>Units: {fmtInt(b.units)}</>)}
              {badge(<>Defects: {fmtInt(b.defects)}</>)}
              {badge(<>Yield: {(b.yield * 100).toFixed(2)}%</>)}
              {badge(<>DPMO: {fmtInt(b.dpmo)}</>)}
              {badge(<>Sigma: {b.sigma.toFixed(2)}</>)}
            </>
          ) : (
            <span style={{ fontSize: 12, color: "#6b7280" }}>No data</span>
          )}
        </Card>
      ) : null}
    </div>
  );
}
