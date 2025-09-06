"use client";

import * as React from "react";

/**
 * ClearKeep — Pareto module (generic)
 *
 * Exports:
 *   - makePareto(items, opts)  -> { labels, bars, cumPct, total }
 *   - buildAccountParetoFromLines(lines, opts)
 *   - buildDefectTypeParetoFromUnits(units, opts)
 *   - <ParetoChart .../>
 *
 * This file is UI-agnostic (one SVG) + small pure helpers.
 */

/** ---------- Types ---------- */
export type ParetoInput = { label: string; value: number };
export type ParetoSeries = {
  labels: string[];
  bars: number[];         // values per label (descending)
  cumPct: number[];       // cumulative percentage (0..1) aligned to labels
  total: number;          // sum of bars (pre-normalization)
};

export type AccountLine = {
  account_id?: number | string | null;
  account_code?: string | null;
  account_name?: string | null;
  amount: number; // already signed as expense/revenue per your page logic
};

export type UnitMinimal = {
  id: string | number;
  date: string;                  // YYYY-MM-DD
  is_locked: boolean;
  source_module?: string | null; // "reversal" denotes rework
};

/** ---------- Helpers (pure) ---------- */
function nf(n: number, frac = 2) {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: frac }).format(n);
}
function parseISODate(d: string) {
  const [y, m, dd] = d.split("-").map((t) => parseInt(t, 10));
  return new Date(y, (m || 1) - 1, dd || 1, 12, 0, 0, 0);
}
function daysBetween(a: Date, b: Date) {
  return Math.floor((a.getTime() - b.getTime()) / (1000 * 60 * 60 * 24));
}

/**
 * Core Pareto maker. Sorts by value desc, computes cumulative %, and can group the tail.
 * opts:
 *  - topN: keep this many head categories (default 10)
 *  - minShare: keep categories while they have at least this share (default 0)
 *  - groupOthers: whether to group the tail as "Others" (default true)
 *  - othersLabel: custom label for grouped tail (default "Others")
 */
export function makePareto(
  items: ParetoInput[],
  opts?: { topN?: number; minShare?: number; groupOthers?: boolean; othersLabel?: string }
): ParetoSeries {
  const { topN = 10, minShare = 0, groupOthers = true, othersLabel = "Others" } = opts || {};
  const list = (items || []).map((x) => ({ label: String(x.label || "Unknown"), value: Number(x.value) || 0 }));
  list.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  const total = list.reduce((a, b) => a + Math.abs(b.value), 0);
  if (total === 0) return { labels: [], bars: [], cumPct: [], total: 0 };

  // Keep head by topN and/or minShare; group remainder
  const keep: ParetoInput[] = [];
  const rest: ParetoInput[] = [];
  let cumulative = 0;
  for (let i = 0; i < list.length; i++) {
    const share = Math.abs(list[i].value) / total;
    if (keep.length < topN || share >= minShare) {
      keep.push(list[i]);
    } else {
      rest.push(list[i]);
    }
  }
  if (groupOthers && rest.length > 0) {
    const v = rest.reduce((a, b) => a + Math.abs(b.value), 0);
    if (v > 0) keep.push({ label: othersLabel, value: v });
  }

  const labels = keep.map((x) => x.label);
  const bars = keep.map((x) => Math.abs(x.value));
  const cumPct: number[] = [];
  for (let i = 0; i < bars.length; i++) {
    cumulative += bars[i];
    cumPct.push(cumulative / total);
  }
  return { labels, bars, cumPct, total };
}

/** Build Pareto from journal lines by account (code/name aware). */
export function buildAccountParetoFromLines(
  lines: AccountLine[],
  opts?: { topN?: number; minShare?: number; groupOthers?: boolean; othersLabel?: string }
): ParetoSeries {
  const bucket = new Map<string, number>();
  for (const ln of lines || []) {
    const code = (ln.account_code || "").trim();
    const name = (ln.account_name || "").trim();
    const label = code && name ? `${code} — ${name}` : (name || code || "Unknown");
    bucket.set(label, (bucket.get(label) || 0) + (Number(ln.amount) || 0));
  }
  const items: ParetoInput[] = Array.from(bucket.entries()).map(([label, value]) => ({ label, value }));
  return makePareto(items, opts);
}

/**
 * Build defect-type Pareto from units using Phase-1 rules:
 *  - Defect if: (unposted & age > slaDays) OR (includeReversals && source_module contains "reversal")
 *  - Classification precedence: if "reversal" matched -> "Reversal", else if unposted aging -> "SLA Aging"
 */
export function buildDefectTypeParetoFromUnits(
  units: UnitMinimal[],
  opts: { slaDays: number; includeReversals: boolean; topN?: number; groupOthers?: boolean }
): ParetoSeries {
  const { slaDays, includeReversals, topN = 6, groupOthers = false } = opts;
  const today = new Date();
  const cnt = new Map<string, number>();

  for (const u of units || []) {
    const isReversal = includeReversals && (u.source_module || "").toLowerCase().includes("reversal");
    const isAging = !u.is_locked && daysBetween(today, parseISODate(u.date)) > slaDays;
    let label: string | null = null;
    if (isReversal) label = "Reversal";
    else if (isAging) label = "SLA Aging";
    if (label) cnt.set(label, (cnt.get(label) || 0) + 1);
  }

  const items: ParetoInput[] = Array.from(cnt.entries()).map(([label, value]) => ({ label, value }));
  // No need to group others by default (few classes), but honor opts
  return makePareto(items, { topN, groupOthers });
}

/** ---------- Presentational SVG (Pareto) ---------- */
export function ParetoChart({
  labels, bars, cumPct, title,
  valueFormatter,
  note,
}: ParetoSeries & { title: string; valueFormatter?: (n: number) => string; note?: string }) {
  const w = 760;
  const h = 280;
  const pad = { l: 42, r: 42, t: 20, b: 64 };

  const n = labels.length;
  if (n === 0) {
    return (
      <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", padding: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{title}</div>
        <div style={{ fontSize: 12, color: "#6b7280" }}>No data.</div>
      </div>
    );
  }

  const maxBar = Math.max(...bars, 1);
  const x = (i: number) => pad.l + (i + 0.5) * ((w - pad.l - pad.r) / n);
  const bw = Math.max(14, (w - pad.l - pad.r) / n - 10);
  const barLeft = (i: number) => x(i) - bw / 2;
  const yBar = (v: number) => h - pad.b - (v * (h - pad.t - pad.b - 20)) / maxBar;

  const yCum = (p: number) => h - pad.b - p * (h - pad.t - pad.b - 20);

  const valueFmt = valueFormatter || ((v: number) => nf(v, 2));
  const pctFmt = (p: number) => `${nf(p * 100, 1)}%`;

  // Cumulative path
  const cumPath = cumPct.map((p, i) => `${i ? "L" : "M"} ${x(i).toFixed(2)} ${yCum(p).toFixed(2)}`).join(" ");

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", padding: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="auto" role="img" aria-label="Pareto Chart">
        {/* axes */}
        <line x1={pad.l} y1={h - pad.b} x2={w - pad.r} y2={h - pad.b} stroke="#e5e7eb" />
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={h - pad.b} stroke="#e5e7eb" />
        {/* bars */}
        {bars.map((v, i) => {
          const y = yBar(v);
          const height = Math.max(0, (h - pad.b) - y);
          return <rect key={`b-${i}`} x={barLeft(i)} y={y} width={bw} height={height} fill="#111827" />;
        })}
        {/* cumulative line + right axis */}
        <path d={cumPath} fill="none" stroke="#9ca3af" strokeWidth={2} />
        <line x1={w - pad.r} y1={pad.t} x2={w - pad.r} y2={h - pad.b} stroke="#e5e7eb" />
        {[0, 0.25, 0.5, 0.75, 1].map((p, i) => (
          <g key={`gt-${i}`}>
            <line x1={pad.l} y1={yCum(p)} x2={w - pad.r} y2={yCum(p)} stroke="#f3f4f6" />
            <text x={w - pad.r + 4} y={yCum(p) + 4} fontSize={10} fill="#6b7280">{pctFmt(p)}</text>
          </g>
        ))}
        {/* x labels (angled) */}
        {labels.map((lb, i) => (
          <g key={`xl-${i}`} transform={`translate(${x(i)}, ${h - pad.b + 4}) rotate(-35)`}>
            <text fontSize={10} textAnchor="end" fill="#6b7280">{lb}</text>
          </g>
        ))}
        {/* top ticks for max bar value */}
        <text x={pad.l - 6} y={yBar(maxBar) - 4} fontSize={10} fill="#6b7280" textAnchor="end">{valueFmt(maxBar)}</text>
      </svg>
      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#6b7280", marginTop: 6, flexWrap: "wrap" }}>
        <span><span style={{ width: 12, height: 10, background: "#111827", display: "inline-block", marginRight: 6 }} /> Value</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 12, height: 2, background: "#9ca3af", display: "inline-block" }} /> Cumulative %
        </span>
        <span style={{ marginLeft: "auto" }}>Max bar: {valueFmt(maxBar)}</span>
      </div>
      {note ? <div style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>{note}</div> : null}
    </div>
  );
}
