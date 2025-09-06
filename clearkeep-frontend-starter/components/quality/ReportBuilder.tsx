"use client";

import React from "react";

export type Grain = "day" | "week" | "month";
export type Domain = "expense" | "revenue" | "all";
export type CompareMode = "none" | "prev_period" | "prev_year" | "custom";
export type Range = { from: string; to: string };

type ReportBuilderProps = {
  // state + setters provided by parent page
  grain: Grain;
  setGrain: (g: Grain) => void;

  domain: Domain;
  setDomain: (d: Domain) => void;

  rangeA: Range;
  setRangeA: (r: Range) => void;

  compareMode: CompareMode;
  setCompareMode: (m: CompareMode) => void;

  rangeB: Range;
  setRangeB: (r: Range) => void;

  postedOnly: boolean;
  setPostedOnly: (b: boolean) => void;

  slaDays: number;
  setSlaDays: (n: number) => void;

  includeReversals: boolean;
  setIncludeReversals: (b: boolean) => void;

  includeReopen: boolean;
  setIncludeReopen: (b: boolean) => void;

  onReload: () => void;
};

/**
 * ReportBuilder
 * Extracted control panel used at the top of the Six Sigma page:
 * - Grain / Domain
 * - Range A (from/to)
 * - Compare mode + optional Range B
 * - Posted-only, SLA days, defect toggles (reversals, reopen/reclose)
 * - Reload button
 *
 * Note: This component is "dumb" — it only renders controls and calls the provided setters.
 * Parent keeps the data fetching and computed state.
 */
export default function ReportBuilder(props: ReportBuilderProps) {
  const {
    grain, setGrain,
    domain, setDomain,
    rangeA, setRangeA,
    compareMode, setCompareMode,
    rangeB, setRangeB,
    postedOnly, setPostedOnly,
    slaDays, setSlaDays,
    includeReversals, setIncludeReversals,
    includeReopen, setIncludeReopen,
    onReload,
  } = props;

  const grid: React.CSSProperties = {
    display: "grid",
    gap: 12,
    gridTemplateColumns: "repeat(12, minmax(0,1fr))",
    alignItems: "end",
    marginBottom: 12,
  };

  const labelStyle: React.CSSProperties = {
    display: "block",
    fontSize: 12,
    color: "#6b7280",
    marginBottom: 4,
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: 8,
    border: "1px solid #d1d5db",
    borderRadius: 6,
  };

  return (
    <div style={grid} role="region" aria-label="Report Builder">
      {/* Grain */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>Grain</label>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {(["day", "week", "month"] as Grain[]).map((g) => (
            <label key={g} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <input type="radio" name="grain" checked={grain === g} onChange={() => setGrain(g)} />
              <span style={{ fontSize: 12, color: "#374151", textTransform: "capitalize" }}>{g}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Domain */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>Domain</label>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {(["expense", "revenue", "all"] as Domain[]).map((d) => (
            <label key={d} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <input type="radio" name="domain" checked={domain === d} onChange={() => setDomain(d)} />
              <span style={{ fontSize: 12, color: "#374151", textTransform: "capitalize" }}>{d}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Range A — From */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>Range A — From</label>
        <input
          type="date"
          value={rangeA?.from ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setRangeA({ ...(rangeA || { from: "", to: "" }), from: v });
          }}
          style={inputStyle}
        />
      </div>

      {/* Range A — To */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>Range A — To</label>
        <input
          type="date"
          value={rangeA?.to ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setRangeA({ ...(rangeA || { from: "", to: "" }), to: v });
          }}
          style={inputStyle}
        />
      </div>

      {/* Compare mode */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>Compare</label>
        <select
          value={compareMode}
          onChange={(e) => setCompareMode(e.currentTarget.value as CompareMode)}
          style={inputStyle}
        >
          <option value="none">None</option>
          <option value="prev_period">Previous Period</option>
          <option value="prev_year">Previous Year</option>
          <option value="custom">Custom A vs B</option>
        </select>
      </div>

      {/* Range B — From (custom) */}
      <div style={{ gridColumn: "span 3 / span 3", opacity: compareMode === "custom" ? 1 : 0.5 }}>
        <label style={labelStyle}>Range B — From (custom)</label>
        <input
          type="date"
          disabled={compareMode !== "custom"}
          value={rangeB?.from ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setRangeB({ ...(rangeB || { from: "", to: "" }), from: v });
          }}
          style={inputStyle}
        />
      </div>

      {/* Range B — To (custom) */}
      <div style={{ gridColumn: "span 3 / span 3", opacity: compareMode === "custom" ? 1 : 0.5 }}>
        <label style={labelStyle}>Range B — To (custom)</label>
        <input
          type="date"
          disabled={compareMode !== "custom"}
          value={rangeB?.to ?? ""}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setRangeB({ ...(rangeB || { from: "", to: "" }), to: v });
          }}
          style={inputStyle}
        />
      </div>

      {/* Posted-only */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>Posted only</label>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={postedOnly}
            onChange={(e) => setPostedOnly(e.currentTarget.checked)}
          />
          <span style={{ fontSize: 12, color: "#374151" }}>Use only locked (posted) entries</span>
        </label>
      </div>

      {/* SLA days */}
      <div style={{ gridColumn: "span 3 / span 3" }}>
        <label style={labelStyle}>SLA (days, unposted → defect)</label>
        <input
          type="number"
          min={0}
          value={Number.isFinite(props.slaDays) ? slaDays : 0}
          onChange={(e) => setSlaDays(parseInt(e.currentTarget.value || "0", 10))}
          style={inputStyle}
        />
      </div>

      {/* Defect rules toggles */}
      <div style={{ gridColumn: "span 6 / span 6" }}>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          <label style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={includeReversals}
              onChange={(e) => setIncludeReversals(e.currentTarget.checked)}
            />
            <span style={{ fontSize: 12, color: "#374151" }}>Count reversal entries as defects</span>
          </label>
          <label style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={includeReopen}
              onChange={(e) => setIncludeReopen(e.currentTarget.checked)}
            />
            <span style={{ fontSize: 12, color: "#374151" }}>Count reopen/reclose months as defects</span>
          </label>
        </div>
      </div>

      {/* Reload */}
      <div style={{ gridColumn: "span 12 / span 12" }}>
        <button
          onClick={onReload}
          style={{
            padding: "10px 12px",
            background: "#111827",
            color: "#fff",
            borderRadius: 6,
            border: "none",
          }}
        >
          Reload
        </button>
      </div>
    </div>
  );
}
