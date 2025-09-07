"use client";

import React from "react";

type Props = {
  labels: string[];                  // e.g., ["2025-06", "2025-07", ...]
  values: number[];                  // same length as labels
  title: string;                     // card title
  valueFormatter: (n: number) => string; // e.g., (v)=>`₱ ${fmt(v)}`
};

/**
 * MonthlyBarChart — small, dependency-free bar chart for month-by-month totals.
 * Pure presentational; no fetching and no app-specific imports.
 */
export default function MonthlyBarChart({ labels, values, title, valueFormatter }: Props) {
  const w = 880, h = 240, padLeft = 44, padBottom = 40, padTop = 12, padRight = 44;
  const max = Math.max(1, ...values.map((v) => Math.abs(v)));
  const barW = Math.max(8, (w - padLeft - padRight) / Math.max(values.length, 1) - 6);
  const x = (i: number) => padLeft + i * (barW + 6);
  const y = (v: number) => h - padBottom - (Math.abs(v) / max) * (h - padTop - padBottom);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", padding: 12 }}>
      <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 6 }}>{title}</div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="auto" role="img" aria-label="Account Month-by-Month">
        {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
          <line
            key={i}
            x1={padLeft}
            y1={padTop + t * (h - padTop - padBottom)}
            x2={w - padRight}
            y2={padTop + t * (h - padTop - padBottom)}
            stroke="#f3f4f6"
          />
        ))}

        {values.map((v, i) => (
          <g key={i}>
            <rect x={x(i)} y={y(v)} width={barW} height={h - padBottom - y(v)} fill="#111827" rx={3} />
          </g>
        ))}

        {/* Left scale label (max) */}
        <text x={padLeft - 6} y={padTop + 12} fontSize={12} fill="#6b7280" textAnchor="end">
          {valueFormatter(max)}
        </text>

        {/* Right percentage rail (decorative) */}
        <g transform={`translate(${w - padRight + 6},0)`} fill="#6b7280" fontSize={12}>
          <text x={0} y={padTop + 12}>100%</text>
          <text x={0} y={padTop + 0.5 * (h - padTop - padBottom) + 4}>50%</text>
          <text x={0} y={h - padBottom}>0%</text>
        </g>

        {/* Bottom labels */}
        {labels.map((m, i) => (
          <text key={i} x={x(i) + barW / 2} y={h - 10} fontSize={10} fill="#6b7280" textAnchor="middle">
            {m}
          </text>
        ))}
      </svg>
    </div>
  );
}
