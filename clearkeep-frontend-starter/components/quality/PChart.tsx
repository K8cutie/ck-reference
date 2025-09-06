"use client";

import * as React from "react";

/**
 * Modular p‑Chart for ClearKeep Six Sigma
 * - UI component: <PChart />
 * - Pure helper: computePChartSeries(units, buckets, { slaDays, includeReversals })
 *
 * This module is self-contained (no external deps). It can be imported by
 * any client component (e.g., the Six Sigma page).
 */

/** Minimal unit shape required for p‑Chart series computation */
export type PChartUnit = {
  id: string | number;
  date: string;        // YYYY-MM-DD
  bucket: string;      // day / week / month key already assigned upstream
  is_locked: boolean;  // posted flag
  source_module?: string | null; // "reversal" denotes rework
};

export type PChartSeries = {
  labels: string[];
  p: number[];     // proportion defective per label
  ucl: number[];   // per-label UCL (variable n)
  lcl: number[];   // per-label LCL (variable n)
  pbar: number;    // overall center line
  n: number[];     // sample size per label
};

/** ---------- tiny utils (local, pure) ---------- */
function clamp(x: number, lo: number, hi: number) { return Math.max(lo, Math.min(hi, x)); }
function fmtInt(n: number) { return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(n); }
function fmtPct(n: number, frac = 2) { return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: frac }).format(n * 100)}%`; }
function parseISODate(d: string) { const [y, m, dd] = d.split("-").map((t) => parseInt(t, 10)); return new Date(y, (m || 1) - 1, dd || 1, 12, 0, 0, 0); }
function daysBetween(a: Date, b: Date) { return Math.floor((a.getTime() - b.getTime()) / (1000 * 60 * 60 * 24)); }

/** Build p‑Chart series from unit‑level flags (unposted>SLA and optional reversals). */
export function computePChartSeries(
  units: PChartUnit[],
  buckets: string[],
  opts: { slaDays: number; includeReversals: boolean }
): PChartSeries {
  const { slaDays, includeReversals } = opts;

  // 1) Decide which units are defective
  const today = new Date();
  const defectiveIds = new Set<string | number>();
  for (const u of units) {
    let bad = false;
    if (!u.is_locked) {
      const age = daysBetween(today, parseISODate(u.date));
      if (age > slaDays) bad = true;
    }
    if (!bad && includeReversals && (u.source_module || "").toLowerCase().includes("reversal")) {
      bad = true;
    }
    if (bad) defectiveIds.add(u.id);
  }

  // 2) Count n and d per bucket
  const nByBucket = new Map<string, number>();
  const dByBucket = new Map<string, number>();
  for (const u of units) {
    nByBucket.set(u.bucket, (nByBucket.get(u.bucket) || 0) + 1);
    if (defectiveIds.has(u.id)) dByBucket.set(u.bucket, (dByBucket.get(u.bucket) || 0) + 1);
  }

  // 3) Produce aligned arrays for buckets with any observations
  const labels = buckets.filter((b) => (nByBucket.get(b) || 0) > 0);
  const n = labels.map((b) => nByBucket.get(b) || 0);
  const d = labels.map((b) => dByBucket.get(b) || 0);

  const totalN = n.reduce((a, v) => a + v, 0);
  const totalD = d.reduce((a, v) => a + v, 0);
  const pbar = totalN > 0 ? totalD / totalN : 0;

  const p = labels.map((_, i) => (n[i] > 0 ? d[i] / n[i] : 0));
  const ucl = labels.map((_, i) => {
    const ni = n[i]; if (ni <= 0) return pbar;
    const se = Math.sqrt(pbar * (1 - pbar) / ni);
    return clamp(pbar + 3 * se, 0, 1);
  });
  const lcl = labels.map((_, i) => {
    const ni = n[i]; if (ni <= 0) return pbar;
    const se = Math.sqrt(pbar * (1 - pbar) / ni);
    return Math.max(0, pbar - 3 * se);
  });

  return { labels, p, ucl, lcl, pbar, n };
}

/** Presentational p‑Chart (SVG). Pure + stateless. */
export function PChart({
  labels, p, ucl, lcl, pbar, n, title, includeReversals
}: {
  labels: string[]; p: number[]; ucl: number[]; lcl: number[]; pbar: number; n: number[]; title: string; includeReversals?: boolean;
}) {
  const w = 720, h = 220, pad = 28;

  const allVals = [...p, ...ucl, ...lcl, pbar].filter((x) => Number.isFinite(x));
  // proportions start at 0; auto-scale upper bound with a sane minimum
  const min = 0;
  const max = Math.max(0.05, Math.max(...allVals, 0.01));
  const x = (i: number) => pad + (i * (w - 2 * pad)) / Math.max(labels.length - 1, 1);
  const y = (v: number) => h - pad - ((v - min) * (h - 2 * pad)) / (max - min || 1);
  const path = (s: number[]) => s.map((v, i) => `${i ? "L" : "M"} ${x(i).toFixed(2)} ${y(v).toFixed(2)}`).join(" ");

  // out-of-control markers (Rule 1)
  const ooc = p.map((pt, i) => (pt > ucl[i] || pt < lcl[i]) ? i : -1).filter((i) => i >= 0);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", padding: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="auto" role="img" aria-label="p-Chart">
        {/* axes */}
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#e5e7eb" />
        {/* grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
          <line key={i} x1={pad} y1={pad + t * (h - 2 * pad)} x2={w - pad} y2={pad + t * (h - 2 * pad)} stroke="#f3f4f6" />
        ))}
        {/* UCL / LCL / CL */}
        <path d={path(ucl)} fill="none" stroke="#9ca3af" strokeWidth={1.5} />
        <path d={path(lcl)} fill="none" stroke="#9ca3af" strokeWidth={1.5} />
        <line x1={pad} y1={y(pbar)} x2={w - pad} y2={y(pbar)} stroke="#6b7280" strokeDasharray="4 3" />
        {/* p series */}
        <path d={path(p)} fill="none" stroke="#111827" strokeWidth={2} />
        {/* highlight out-of-control points */}
        {ooc.map((i) => <circle key={i} cx={x(i)} cy={y(p[i])} r={3} fill="#111827" />)}
        {/* x labels */}
        {labels.map((m, i) => (
          <text key={m} x={x(i)} y={h - pad + 14} fontSize={10} textAnchor="middle" fill="#6b7280">{m}</text>
        ))}
      </svg>
      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#6b7280", marginTop: 6, flexWrap: "wrap" }}>
        <span>CL = {fmtPct(pbar)}</span>
        <span>Σn = {fmtInt(n.reduce((a, b) => a + b, 0))}</span>
        <span>Out-of-control points: {ooc.length}</span>
        <span style={{ marginLeft: "auto" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, marginRight: 12 }}>
            <span style={{ width: 12, height: 2, background: "#111827", display: "inline-block" }} /> p (defect %)
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, marginRight: 12 }}>
            <span style={{ width: 12, height: 2, background: "#9ca3af", display: "inline-block" }} /> UCL / LCL
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 12, height: 2, background: "#6b7280", display: "inline-block" }} /> CL
          </span>
        </span>
      </div>
      <div style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
        Note: p‑Chart uses unit‑level defects (unposted &gt; SLA days{includeReversals ? " and reversals" : ""}). Reopened/reclosed months are managed separately.
      </div>
    </div>
  );
}
