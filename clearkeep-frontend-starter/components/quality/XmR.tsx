"use client";

import * as React from "react";

/**
 * ClearKeep — XmR (Individuals & Moving Range) Module
 *
 * What you get:
 * - computeXmRSeries(values, labels): pure helper to build limits + series
 * - <XmRChart .../>: presentational SVG with two stacked charts (X and MR)
 *
 * Typical usage in a page:
 *   const totals = ... // per-bucket totals (e.g., expenses by month)
 *   const labels = ... // matching bucket keys
 *   const xmr = computeXmRSeries(totals, labels);
 *   <XmRChart {...xmr} title="Expenses — XmR" />
 */

/** ---------- Types ---------- */
export type XmRSeries = {
  labels: string[];
  x: number[];         // Individuals
  mr: number[];        // Moving Range (|x_i - x_{i-1}|)
  xbar: number;        // mean of Individuals
  mrbar: number;       // mean of MR (excluding the first, which is 0)
  x_ucl: number;
  x_lcl: number;
  x_cl: number;
  mr_ucl: number;
  mr_lcl: number;
  mr_cl: number;
};

/** ---------- Pure helpers ---------- */
function mean(arr: number[]) {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

/**
 * Compute XmR limits using n=2 constants:
 *  - sigma ≈ MRbar / d2, where d2(2) ≈ 1.128
 *  - X UCL/LCL = Xbar ± 3*sigma = Xbar ± (3/d2)*MRbar ≈ Xbar ± 2.66*MRbar
 *  - MR UCL = 3.267 * MRbar ; MR LCL = 0
 */
export function computeXmRSeries(values: number[], labels: string[]): XmRSeries {
  const x = (values || []).map((v) => Number(v) || 0);
  const n = x.length;
  const mr: number[] = new Array(Math.max(n, 1)).fill(0);
  for (let i = 1; i < n; i++) mr[i] = Math.abs(x[i] - x[i - 1]);

  const mrSamples = mr.slice(1); // exclude the first (0)
  const xbar = mean(x);
  const mrbar = mrSamples.length ? mean(mrSamples) : 0;

  const TWO_POINT_SIX_SIX = 2.66;
  const THREE_POINT_TWO_SIX_SEVEN = 3.267;

  const x_ucl = xbar + TWO_POINT_SIX_SIX * mrbar;
  const x_lcl = xbar - TWO_POINT_SIX_SIX * mrbar;
  const x_cl = xbar;

  const mr_ucl = THREE_POINT_TWO_SIX_SEVEN * mrbar;
  const mr_lcl = 0;
  const mr_cl = mrbar;

  return {
    labels: labels || [],
    x,
    mr,
    xbar,
    mrbar,
    x_ucl,
    x_lcl,
    x_cl,
    mr_ucl,
    mr_lcl,
    mr_cl,
  };
}

/** ---------- Presentational SVG chart (stateless) ---------- */
export function XmRChart({
  labels, x, mr,
  x_ucl, x_lcl, x_cl,
  mr_ucl, mr_lcl, mr_cl,
  title = "XmR Chart",
}: XmRSeries & { title?: string }) {

  // Layout
  const pad = 28;
  const w = 760;

  // --- Individuals (X) panel sizing ---
  const xVals = [...x, x_ucl, x_lcl, x_cl].filter((v) => Number.isFinite(v));
  let xMin = Math.min(...xVals);
  let xMax = Math.max(...xVals);
  if (xMin === xMax) { xMin -= 1; xMax += 1; }
  // add 5% headroom
  const xRange = xMax - xMin;
  xMin = xMin - 0.05 * xRange;
  xMax = xMax + 0.05 * xRange;

  const xHeight = 180;
  const xX = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(labels.length - 1, 1);
  const xY = (v: number) => xHeight - pad - ((v - xMin) * (xHeight - 2 * pad)) / (xMax - xMin || 1);

  const xPath = (s: number[]) => s.map((v, i) => `${i ? "L" : "M"} ${xX(i).toFixed(2)} ${xY(v).toFixed(2)}`).join(" ");

  // Rule 1 (beyond 3σ) markers
  const xOOC = x.map((v, i) => (v > x_ucl || v < x_lcl) ? i : -1).filter((i) => i >= 0);

  // --- MR panel sizing ---
  const mrVals = [...mr, mr_ucl, mr_lcl, mr_cl].filter((v) => Number.isFinite(v));
  let mrMin = Math.min(...mrVals, 0);
  let mrMax = Math.max(...mrVals, 1);
  if (mrMin === mrMax) { mrMin = 0; mrMax = mrMax || 1; }
  const mrHeight = 150;
  const mrX = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(labels.length - 1, 1);
  const mrY = (v: number) => mrHeight - pad - ((v - mrMin) * (mrHeight - 2 * pad)) / (mrMax - mrMin || 1);
  const mrPath = (s: number[]) => s.map((v, i) => `${i ? "L" : "M"} ${mrX(i).toFixed(2)} ${mrY(v).toFixed(2)}`).join(" ");

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", padding: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{title}</div>

      {/* Individuals (X) */}
      <svg viewBox={`0 0 ${w} ${xHeight}`} width="100%" height="auto" role="img" aria-label="Individuals Chart">
        {/* axes */}
        <line x1={pad} y1={xHeight - pad} x2={w - pad} y2={xHeight - pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={xHeight - pad} stroke="#e5e7eb" />
        {/* grid */}
        {[0, 0.5, 1].map((t, i) => (
          <line key={i} x1={pad} y1={pad + t * (xHeight - 2 * pad)} x2={w - pad} y2={pad + t * (xHeight - 2 * pad)} stroke="#f3f4f6" />
        ))}
        {/* limits */}
        <line x1={pad} y1={xY(x_ucl)} x2={w - pad} y2={xY(x_ucl)} stroke="#9ca3af" />
        <line x1={pad} y1={xY(x_lcl)} x2={w - pad} y2={xY(x_lcl)} stroke="#9ca3af" />
        <line x1={pad} y1={xY(x_cl)}  x2={w - pad} y2={xY(x_cl)}  stroke="#6b7280" strokeDasharray="4 3" />
        {/* series */}
        <path d={xPath(x)} fill="none" stroke="#111827" strokeWidth={2} />
        {/* markers */}
        {xOOC.map((i) => <circle key={`xooc-${i}`} cx={xX(i)} cy={xY(x[i])} r={3} fill="#111827" />)}
        {/* x labels */}
        {labels.map((m, i) => (
          <text key={`xl-${m}`} x={xX(i)} y={xHeight - pad + 14} fontSize={10} textAnchor="middle" fill="#6b7280">{m}</text>
        ))}
      </svg>

      {/* Moving Range (MR) */}
      <svg viewBox={`0 0 ${w} ${mrHeight}`} width="100%" height="auto" role="img" aria-label="Moving Range Chart" style={{ marginTop: 6 }}>
        {/* axes */}
        <line x1={pad} y1={mrHeight - pad} x2={w - pad} y2={mrHeight - pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={mrHeight - pad} stroke="#e5e7eb" />
        {/* grid */}
        {[0, 0.5, 1].map((t, i) => (
          <line key={i} x1={pad} y1={pad + t * (mrHeight - 2 * pad)} x2={w - pad} y2={pad + t * (mrHeight - 2 * pad)} stroke="#f3f4f6" />
        ))}
        {/* limits */}
        <line x1={pad} y1={mrY(mr_ucl)} x2={w - pad} y2={mrY(mr_ucl)} stroke="#9ca3af" />
        <line x1={pad} y1={mrY(mr_lcl)} x2={w - pad} y2={mrY(mr_lcl)} stroke="#9ca3af" />
        <line x1={pad} y1={mrY(mr_cl)}  x2={w - pad} y2={mrY(mr_cl)}  stroke="#6b7280" strokeDasharray="4 3" />
        {/* series */}
        <path d={mrPath(mr)} fill="none" stroke="#111827" strokeWidth={2} />
        {/* x labels (MR panel uses sparse labeling to avoid clutter) */}
        {labels.map((m, i) => (
          (i % Math.ceil(labels.length / 8) === 0) ? (
            <text key={`mrl-${m}`} x={mrX(i)} y={mrHeight - pad + 14} fontSize={10} textAnchor="middle" fill="#6b7280">{m}</text>
          ) : null
        ))}
      </svg>

      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#6b7280", marginTop: 6, flexWrap: "wrap" }}>
        <span>Individuals: CL = {formatNum(x_cl)}, UCL = {formatNum(x_ucl)}, LCL = {formatNum(x_lcl)}</span>
        <span>MR: CL = {formatNum(mr_cl)}, UCL = {formatNum(mr_ucl)}</span>
        <span style={{ marginLeft: "auto" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, marginRight: 12 }}>
            <span style={{ width: 12, height: 2, background: "#111827", display: "inline-block" }} /> Series
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, marginRight: 12 }}>
            <span style={{ width: 12, height: 2, background: "#9ca3af", display: "inline-block" }} /> UCL / LCL
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 12, height: 2, background: "#6b7280", display: "inline-block" }} /> CL
          </span>
        </span>
      </div>
    </div>
  );
}

/** Local number formatter (no currency) to keep the module generic */
function formatNum(n: number, frac = 2) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: frac }).format(n);
}
