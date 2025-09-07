"use client";

import React, { useMemo, useState } from "react";
import type { ReceiptMatrix } from "../../../lib/quality/selectors";
import {
  projectReceipts,
  type ProjectionParams,
  type RoundingMode,
} from "../../../lib/quality/projections";
import ReceiptsMatrixSection from "./ReceiptsMatrixSection";

/**
 * ProjectionsSection
 *
 * Presentational “budget builder” for Receipts:
 * - Lets a user set global uplift, per-category uplifts, monthly factors (seasonality),
 *   inflation, compounding, and rounding.
 * - Computes a projected (budget) matrix from a base actuals matrix.
 * - Renders the projected matrix using ReceiptsMatrixSection.
 *
 * NOTE: This component is self-contained for now (local state). Later we can
 * lift state up to the page or add “Save Scenario” support without changing this API.
 */

type Props = {
  title?: string;
  /** Base matrix (Actuals) to project from */
  base: ReceiptMatrix;
  /** Currency/number formatter, e.g., (n)=>`₱ ${fmt(n)}` */
  format: (n: number) => string;
};

export default function ProjectionsSection({ title = "Budget / Projections", base, format }: Props) {
  // --- Controls state ---
  const [globalPct, setGlobalPct] = useState<number>(0);           // %
  const [inflationPct, setInflationPct] = useState<number>(0);     // %
  const [compounding, setCompounding] = useState<boolean>(false);
  const [rounding, setRounding] = useState<RoundingMode>("none");

  // Monthly factors (Jan..Dec), default 1.00
  const [monthlyFactors, setMonthlyFactors] = useState<number[]>(
    Array.from({ length: 12 }, () => 1)
  );

  // Per-category uplift table (by key), inferred from base top-level rows
  const initialPerCat: Record<string, number> = useMemo(() => {
    const out: Record<string, number> = {};
    (base.rows || []).forEach((r) => (out[r.key] = 0));
    return out;
  }, [base.rows]);

  const [perCategoryPct, setPerCategoryPct] = useState<Record<string, number>>(initialPerCat);

  // Derived labels for per-category controls
  const categoryLabels = useMemo(
    () => (base.rows || []).map((r) => ({ key: r.key, label: r.label })).slice(),
    [base.rows]
  );

  // Build ProjectionParams (convert UI % to decimals)
  const params: ProjectionParams = useMemo(
    () => ({
      globalPct: (globalPct || 0) / 100,
      perCategoryPct: Object.fromEntries(
        Object.entries(perCategoryPct).map(([k, v]) => [k, (Number(v) || 0) / 100])
      ),
      monthlyFactors: monthlyFactors.map((x) => (isFinite(x) && x > 0 ? x : 1)),
      inflationPct: (inflationPct || 0) / 100,
      compounding,
      rounding,
    }),
    [globalPct, perCategoryPct, monthlyFactors, inflationPct, compounding, rounding]
  );

  // Compute projected matrix
  const projected = useMemo(() => projectReceipts(base, params), [base, params]);

  // --- Small UI helpers ---
  const pctInputStyle: React.CSSProperties = {
    width: 90,
    border: "1px solid #d1d5db",
    borderRadius: 6,
    padding: "6px 8px",
    textAlign: "right",
  };

  const numberInputStyle: React.CSSProperties = {
    width: 80,
    border: "1px solid #d1d5db",
    borderRadius: 6,
    padding: "6px 8px",
    textAlign: "right",
  };

  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
      {/* Header / Controls */}
      <div style={{ padding: 12, borderBottom: "1px solid #e5e7eb" }}>
        <div style={{ fontWeight: 700, marginBottom: 8 }}>{title}</div>

        {/* Top row controls */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 12,
            alignItems: "center",
          }}
        >
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 12, color: "#6b7280" }}>Global uplift (%)</span>
            <input
              type="number"
              value={globalPct}
              onChange={(e) => setGlobalPct(Number(e.target.value))}
              placeholder="0"
              step={0.1}
              style={pctInputStyle}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 12, color: "#6b7280" }}>Inflation (%)</span>
            <input
              type="number"
              value={inflationPct}
              onChange={(e) => setInflationPct(Number(e.target.value))}
              placeholder="0"
              step={0.1}
              style={pctInputStyle}
            />
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              type="checkbox"
              checked={compounding}
              onChange={(e) => setCompounding(e.target.checked)}
            />
            Compounding (month-over-month)
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 12, color: "#6b7280" }}>Rounding</span>
            <select
              value={rounding}
              onChange={(e) => setRounding(e.target.value as RoundingMode)}
              style={{ border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px" }}
            >
              <option value="none">None</option>
              <option value="nearest10">Nearest 10</option>
              <option value="nearest100">Nearest 100</option>
              <option value="nearest1000">Nearest 1000</option>
            </select>
          </label>
        </div>

        {/* Monthly seasonality factors */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13 }}>Seasonality (Monthly factors)</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(12, minmax(52px, 1fr))", gap: 8 }}>
            {["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].map((m, i) => (
              <label key={m} style={{ display: "grid", gap: 4, justifyItems: "center" }}>
                <span style={{ fontSize: 11, color: "#6b7280" }}>{m}</span>
                <input
                  type="number"
                  value={monthlyFactors[i]}
                  step={0.01}
                  min={0}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setMonthlyFactors((arr) => arr.map((x, idx) => (idx === i ? v : x)));
                  }}
                  style={numberInputStyle}
                />
              </label>
            ))}
          </div>
        </div>

        {/* Per-category uplifts */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13 }}>Per-Category Uplifts (%)</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "#f9fafb" }}>
                  <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Category</th>
                  <th style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #e5e7eb", width: 140 }}>Uplift (%)</th>
                </tr>
              </thead>
              <tbody>
                {categoryLabels.map(({ key, label }) => (
                  <tr key={key}>
                    <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{label}</td>
                    <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", textAlign: "right" }}>
                      <input
                        type="number"
                        step={0.1}
                        value={perCategoryPct[key] ?? 0}
                        onChange={(e) =>
                          setPerCategoryPct((m) => ({ ...m, [key]: Number(e.target.value) }))
                        }
                        style={pctInputStyle}
                      />
                    </td>
                  </tr>
                ))}
                {categoryLabels.length === 0 && (
                  <tr>
                    <td colSpan={2} style={{ padding: 8, color: "#6b7280", fontSize: 12 }}>
                      No categories detected in the base matrix.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Projected matrix */}
      <div style={{ padding: 12 }}>
        <ReceiptsMatrixSection
          title="Projected Budget — Matrix"
          months={projected.months}
          rows={projected.rows}
          colTotals={projected.colTotals}
          grandTotal={projected.grandTotal}
          format={format}
          allowSort={true}
          expandable={true}
          showTotalsRow={true}
        />
      </div>
    </div>
  );
}
