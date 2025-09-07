"use client";

import React, { useMemo, useRef, useState } from "react";

/**
 * IncomeVsExpensesChart — pretty, interactive SVG
 * - Smooth lines + soft gradients
 * - Shaded bands when Expenses > Revenue
 * - Crossover markers
 * - Hover crosshair + tooltip (month, revenue, expenses, net)
 * (No external libs)
 */
type Props = {
  title?: string;
  months: string[];
  revenue: number[];
  expenses: number[];
  height?: number;
};

export default function IncomeVsExpensesChart({
  title = "Income vs Expenses (by month)",
  months,
  revenue,
  expenses,
  height = 300,
}: Props) {
  const n = Math.min(months.length, revenue.length, expenses.length);
  const M = months.slice(0, n);
  const R = revenue.slice(0, n).map((v) => Number(v) || 0);
  const E = expenses.slice(0, n).map((v) => Number(v) || 0);

  const w = 980;
  const h = height;
  const pad = { l: 60, r: 16, t: 14, b: 44 };

  const maxVal = Math.max(1, ...R, ...E);
  const yMax = niceCeil(maxVal * 1.08);

  const x = (i: number) => pad.l + (i * (w - pad.l - pad.r)) / Math.max(n - 1, 1);
  const y = (v: number) => pad.t + (1 - v / yMax) * (h - pad.t - pad.b);

  /* ---------- line + area paths (visually smoother) ---------- */
  const linePath = (arr: number[]) => {
    if (arr.length === 0) return "";
    const pts = arr.map((v, i) => [x(i), y(v)]);
    let d = `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1];
      const [x1, y1] = pts[i];
      const cx = (x0 + x1) / 2;
      d += ` Q ${x0.toFixed(2)} ${y0.toFixed(2)} ${cx.toFixed(2)} ${((y0 + y1) / 2).toFixed(2)}`;
      d += ` T ${x1.toFixed(2)} ${y1.toFixed(2)}`;
    }
    return d;
  };

  const areaPath = (arr: number[]) => {
    if (arr.length === 0) return "";
    const baseY = y(0);
    const pts = arr.map((v, i) => [x(i), y(v)]);
    let d = `M ${pts[0][0].toFixed(2)} ${baseY.toFixed(2)} L ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
    for (let i = 1; i < pts.length; i++) d += ` L ${pts[i][0].toFixed(2)} ${pts[i][1].toFixed(2)}`;
    d += ` L ${pts[pts.length - 1][0].toFixed(2)} ${baseY.toFixed(2)} Z`;
    return d;
  };

  /* ---------- crossover + expense bands ---------- */
  const crossovers = useMemo(() => {
    const pts: Array<{ x: number; y: number }> = [];
    for (let i = 1; i < n; i++) {
      const d0 = R[i - 1] - E[i - 1];
      const d1 = R[i] - E[i];
      if ((d0 === 0 && d1 !== 0) || (d1 === 0 && d0 !== 0) || (d0 < 0 && d1 > 0) || (d0 > 0 && d1 < 0)) {
        const R0 = R[i - 1], R1 = R[i];
        const E0 = E[i - 1], E1 = E[i];
        const denom = (R1 - R0) - (E1 - E0);
        const t = denom === 0 ? 0 : (E0 - R0) / denom;
        const clamped = Math.max(0, Math.min(1, t));
        const xi = x(i - 1) + clamped * (x(i) - x(i - 1));
        const yi = y(R0 + clamped * (R1 - R0));
        pts.push({ x: xi, y: yi });
      }
    }
    return pts;
  }, [n, R, E]);

  const expenseBands = useMemo(() => {
    const bands: Array<{ x0: number; x1: number }> = [];
    for (let i = 0; i < n; i++) {
      if ((E[i] ?? 0) > (R[i] ?? 0)) {
        const x0 = i === 0 ? x(0) : (x(i - 1) + x(i)) / 2;
        const x1 = i === n - 1 ? x(n - 1) : (x(i) + x(i + 1)) / 2;
        bands.push({ x0, x1 });
      }
    }
    return bands;
  }, [n, R, E]);

  /* ---------- y ticks ---------- */
  const yTicks = useMemo(() => {
    const step = niceStep(yMax, 4);
    const arr: number[] = [];
    for (let v = 0; v <= yMax + 1e-6; v += step) arr.push(v);
    return arr;
  }, [yMax]);

  /* ---------- hover interaction ---------- */
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const fmtN = (v: number) => Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(v);

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left;
    let nearest = 0, best = Infinity;
    for (let i = 0; i < n; i++) {
      const dx = Math.abs(mx - x(i));
      if (dx < best) { best = dx; nearest = i; }
    }
    setHoverIdx(nearest);
  };
  const handleLeave = () => setHoverIdx(null);

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff", padding: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ fontWeight: 700 }}>{title}</div>
        <div style={{ display: "flex", gap: 12, color: "#374151", fontSize: 12 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 14, height: 2, background: "#0ea5e9", display: "inline-block", borderRadius: 2 }} />Revenue
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 14, height: 2, background: "#ef4444", display: "inline-block", borderRadius: 2 }} />Expenses
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, display: "inline-block", borderRadius: 999, background: "#ef4444" }} />Crossover
          </span>
        </div>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${w} ${h}`}
        width="100%"
        height="auto"
        role="img"
        aria-label="Income vs Expenses"
        onMouseMove={handleMove}
        onMouseLeave={handleLeave}
        style={{ touchAction: "none", cursor: "crosshair" }}
      >
        <defs>
          <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0ea5e9" stopOpacity="0.20" />
            <stop offset="100%" stopColor="#0ea5e9" stopOpacity="0.03" />
          </linearGradient>
          <linearGradient id="expFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.20" />
            <stop offset="100%" stopColor="#ef4444" stopOpacity="0.03" />
          </linearGradient>
          <filter id="tooltipShadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#000" floodOpacity="0.25"/>
          </filter>
        </defs>

        {/* grid + y labels */}
        {yTicks.map((v, i) => (
          <g key={i}>
            <line x1={pad.l} y1={y(v)} x2={w - pad.r} y2={y(v)} stroke="#f3f4f6" />
            <text x={pad.l - 8} y={y(v) + 4} fontSize={10} textAnchor="end" fill="#6b7280">
              {fmtN(v)}
            </text>
          </g>
        ))}

        {/* shade where expenses > revenue */}
        {expenseBands.map((b, i) => (
          <rect
            key={i}
            x={b.x0}
            y={pad.t}
            width={Math.max(1, b.x1 - b.x0)}
            height={h - pad.t - pad.b}
            fill="#fee2e2"
            opacity={0.35}
          />
        ))}

        {/* axes */}
        <line x1={pad.l} y1={h - pad.b} x2={w - pad.r} y2={h - pad.b} stroke="#e5e7eb" />
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={h - pad.b} stroke="#e5e7eb" />

        {/* areas */}
        <path d={areaPath(R)} fill="url(#revFill)" />
        <path d={areaPath(E)} fill="url(#expFill)" />

        {/* lines */}
        <path d={linePath(R)} fill="none" stroke="#0ea5e9" strokeWidth={2.5} strokeLinecap="round" />
        <path d={linePath(E)} fill="none" stroke="#ef4444" strokeWidth={2.5} strokeLinecap="round" />

        {/* x labels */}
        {M.map((m, i) => (
          <text key={m} x={x(i)} y={h - pad.b + 14} fontSize={10} textAnchor="middle" fill="#6b7280">
            {m}
          </text>
        ))}

        {/* crossover markers */}
        {crossovers.map((p, idx) => (
          <g key={idx}>
            <circle cx={p.x} cy={p.y} r={4.5} fill="#ef4444" stroke="#fff" strokeWidth={1.5} />
          </g>
        ))}

        {/* hover crosshair + tooltip */}
        {hoverIdx !== null && (
          <g>
            {/* vertical line */}
            <line x1={x(hoverIdx)} y1={pad.t} x2={x(hoverIdx)} y2={h - pad.b} stroke="#9ca3af" strokeDasharray="3 3" />

            {/* focus points */}
            <circle cx={x(hoverIdx)} cy={y(R[hoverIdx])} r={4.5} fill="#0ea5e9" stroke="#fff" strokeWidth={1.5} />
            <circle cx={x(hoverIdx)} cy={y(E[hoverIdx])} r={4.5} fill="#ef4444" stroke="#fff" strokeWidth={1.5} />

            {/* tooltip box (wider; 3 lines so nothing overlaps) */}
            {(() => {
              const boxW = 210;
              const boxH = 82; // month + 3 lines
              const tx = Math.min(Math.max(x(hoverIdx) + 10, pad.l + 8), w - pad.r - boxW - 8);
              const yy = Math.min(y(R[hoverIdx]), y(E[hoverIdx]));
              const ty = Math.max(pad.t + 8, Math.min(yy - boxH / 2, h - pad.b - boxH - 8));
              const net = (R[hoverIdx] || 0) - (E[hoverIdx] || 0);
              const netColor = net >= 0 ? "#10b981" : "#ef4444";
              return (
                <g transform={`translate(${tx}, ${ty})`} filter="url(#tooltipShadow)">
                  <rect width={boxW} height={boxH} rx={10} fill="#111827" opacity={0.95} />
                  <text x={10} y={18} fontSize={11} fill="#9ca3af">{M[hoverIdx]}</text>
                  <text x={10} y={36} fontSize={13} fill="#0ea5e9">Revenue: {fmtN(R[hoverIdx] || 0)}</text>
                  <text x={10} y={52} fontSize={13} fill="#ef4444">Expenses: {fmtN(E[hoverIdx] || 0)}</text>
                  <text x={10} y={68} fontSize={13} fill={netColor}>Net: {fmtN(net)}</text>
                </g>
              );
            })()}
          </g>
        )}
      </svg>
    </div>
  );
}

/* --------------------------- helpers (nice ticks) -------------------------- */

function niceCeil(v: number) {
  const p = Math.pow(10, Math.floor(Math.log10(v || 1)));
  const m = Math.ceil(v / p);
  const nice = [1, 2, 2.5, 5, 10];
  for (const k of nice) {
    if (m <= k) return k * p;
  }
  return 10 * p;
}

function niceStep(max: number, approxTicks: number) {
  const raw = max / Math.max(1, approxTicks);
  const p = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const m = raw / p;
  const nice = m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10;
  return nice * p;
}
