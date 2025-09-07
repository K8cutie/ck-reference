"use client";

import React from "react";
import { ParetoChart } from "../Pareto";

export type ParetoSeries = {
  labels: string[];
  bars: number[];
  cumPct: number[];
  total: number;
  /** Title above the chart, e.g., "Range A (...)" */
  title: string;
  /** Format numeric values (e.g., integers) */
  valueFormatter: (n: number) => string;
  /** Optional note rendered under the chart */
  note?: string;
};

type Props = {
  /** Required: Range A series */
  a: ParetoSeries;
  /** Optional: Range B series (renders side-by-side if present) */
  b?: ParetoSeries | null;
  /** Optional custom section title */
  heading?: string;
};

/**
 * ParetoDefectsSection — presentational wrapper for one or two
 * defect-type Pareto charts. Pure UI; computes nothing.
 */
export default function ParetoDefectsSection({ a, b, heading }: Props) {
  const twoCols = Boolean(b);
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 12, background: "#fff" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>
        {heading ?? "Pareto — Defect Types (count)"}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: twoCols ? "repeat(2, minmax(0, 1fr))" : "repeat(1, minmax(0, 1fr))",
          gap: 12,
        }}
      >
        <ParetoChart
          labels={a.labels}
          bars={a.bars}
          cumPct={a.cumPct}
          total={a.total}
          title={a.title}
          valueFormatter={a.valueFormatter}
          note={a.note}
        />

        {b ? (
          <ParetoChart
            labels={b.labels}
            bars={b.bars}
            cumPct={b.cumPct}
            total={b.total}
            title={b.title}
            valueFormatter={b.valueFormatter}
            note={b.note}
          />
        ) : null}
      </div>
    </div>
  );
}
