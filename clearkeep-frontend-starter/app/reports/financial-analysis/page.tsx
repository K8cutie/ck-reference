"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";

// APIs & utils
import { fetchAccounts, fetchJournalPaged } from "../../../lib/quality/api";
import { ymd, addDays } from "../../../lib/quality/time";
import { fmt } from "../../../lib/quality/format";

// Selectors
import {
  buildReceiptsMatrix,
  type Range,
  type CategoryRule,
} from "../../../lib/quality/selectors";
import { getReceiptCategoryRules } from "../../../lib/quality/receipts_categories";

// Presentational
import ReceiptsMatrixSection from "../../../components/quality/sections/ReceiptsMatrixSection";
import ProjectionsSection from "../../../components/quality/sections/ProjectionsSection";
import AccountsCatalog from "../../../components/quality/sections/AccountsCatalog";
import IncomeVsExpensesChart from "../../../components/quality/sections/IncomeVsExpensesChart";
import { Section } from "../../../components/quality/ui";

// Minimal local types to help TS (matches your API shape loosely)
type Account = { id: number | string; code?: string | null; name?: string | null };
type JournalLine = {
  account_id?: number | string | null;
  account_code?: string | null;
  account_name?: string | null;
  debit?: number | null;
  credit?: number | null;
};
type JournalEntry = {
  id: number | string;
  entry_date: string; // YYYY-MM-DD
  is_locked?: boolean;
  locked_at?: string | null;
  posted_at?: string | null;
  posted_by_user_id?: number | null;
  lines?: JournalLine[];
};

// ---------- UI bits ----------
type TabKey = "overview" | "actuals" | "budget" | "variance" | "catalog";

function TabBar({
  active,
  onChange,
}: {
  active: TabKey;
  onChange: (t: TabKey) => void;
}) {
  const btn = (key: TabKey, label: string) => {
    const is = active === key;
    return (
      <button
        key={key}
        onClick={() => onChange(key)}
        className={`rounded-lg border px-3 py-1.5 text-sm ${
          is ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
        }`}
        aria-pressed={is}
      >
        {label}
      </button>
    );
  };
  return (
    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
      {btn("overview", "Overview")}
      {btn("actuals", "Actuals")}
      {btn("budget", "Budget")}
      {btn("variance", "Variance")}
      {btn("catalog", "Catalog")}
    </div>
  );
}

// Simple controls (leaner than ReportBuilder)
function Controls({
  range,
  setRange,
  showAccountsAsChildren,
  setShowAccountsAsChildren,
  includeUnmapped,
  setIncludeUnmapped,
}: {
  range: Range;
  setRange: (r: Range) => void;
  showAccountsAsChildren: boolean;
  setShowAccountsAsChildren: (b: boolean) => void;
  includeUnmapped: boolean;
  setIncludeUnmapped: (b: boolean) => void;
}) {
  return (
    <div
      style={{
        position: "sticky",
        top: 48, // leave room for any global header
        zIndex: 10,
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        background: "#fff",
        padding: 12,
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))",
        gap: 12,
      }}
    >
      <div>
        <div style={{ fontSize: 12, color: "#6b7280" }}>Range — From</div>
        <input
          type="date"
          value={range.from}
          onChange={(e) => setRange({ ...range, from: e.target.value })}
          style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px" }}
        />
      </div>
      <div>
        <div style={{ fontSize: 12, color: "#6b7280" }}>Range — To</div>
        <input
          type="date"
          value={range.to}
          onChange={(e) => setRange({ ...range, to: e.target.value })}
          style={{ width: "100%", border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px" }}
        />
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="checkbox"
          checked={showAccountsAsChildren}
          onChange={(e) => setShowAccountsAsChildren(e.target.checked)}
        />
        Show accounts beneath categories
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="checkbox"
          checked={includeUnmapped}
          onChange={(e) => setIncludeUnmapped(e.target.checked)}
        />
        Include “Other Receipts/Other Expenses”
      </label>
    </div>
  );
}

export default function FinancialAnalysisPage() {
  // Defaults: last ~8 months
  const today = new Date();
  const [range, setRange] = useState<Range>({
    from: ymd(addDays(today, -240)),
    to: ymd(today),
  });
  const [showAccountsAsChildren, setShowAccountsAsChildren] = useState<boolean>(false);
  const [includeUnmapped, setIncludeUnmapped] = useState<boolean>(true);

  // Tabs
  const [tab, setTab] = useState<TabKey>("actuals");

  // Data state
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Central category mapping (Revenue) — editable in lib/quality/receipts_categories.ts
  const revenueCategoryRules = useMemo(() => getReceiptCategoryRules(), []);

  // Inline default mapping for Expenses (by common name tokens)
  const expenseCategoryRules: CategoryRule[] = useMemo(
    () => [
      { key: "utilities",        label: "Utilities",                 name_includes: ["utility", "electric", "water", "internet", "phone"] },
      { key: "office_supplies",  label: "Office Supplies",           name_includes: ["office supply", "stationery", "paper", "ink", "toner"] },
      { key: "repairs",          label: "Repairs & Maintenance",     name_includes: ["repair", "maintenance", "service"] },
      { key: "transport",        label: "Transportation/Fuel",       name_includes: ["transport", "fuel", "gas", "diesel", "fare"] },
      { key: "banking_fees",     label: "Banking & Fees",            name_includes: ["bank", "fee", "charge", "service charge"] },
      { key: "charity",          label: "Charity/Outreach",          name_includes: ["charity", "outreach", "aid"] },
      { key: "salaries",         label: "Salaries & Honoraria",      name_includes: ["salary", "salaries", "honoraria", "stipend", "payroll"] },
      { key: "liturgical",       label: "Liturgical Supplies",       name_includes: ["liturgical", "host", "wine", "candle"] },
      // Other auto-bucket will be added if includeUnmapped=true
    ],
    []
  );

  // Hardened reload: call our paged helper ONCE (it internally paginates)
  const reload = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [accs, ents] = await Promise.all([
        fetchAccounts(200), // will page internally if needed
        fetchJournalPaged({ from: range.from, to: range.to }, false, 200) as Promise<JournalEntry[]>,
      ]);

      setAccounts(accs as any);
      setEntries(ents as any);
    } catch (e: any) {
      setError(e?.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to]);

  useEffect(() => {
    reload();
  }, [reload]);

  // ---------- Actuals matrices (Revenue + Expenses) ----------
  const revenueMatrix = useMemo(() => {
    return buildReceiptsMatrix({
      entries,
      accounts,
      domain: "revenue",
      range,
      selectedSet: undefined,
      categories: revenueCategoryRules,
      includeUnmapped,
      showAccountsAsChildren,
    });
  }, [entries, accounts, range, revenueCategoryRules, includeUnmapped, showAccountsAsChildren]);

  const expenseMatrix = useMemo(() => {
    return buildReceiptsMatrix({
      entries,
      accounts,
      domain: "expense",
      range,
      selectedSet: undefined,
      categories: expenseCategoryRules,
      includeUnmapped,
      showAccountsAsChildren,
    });
  }, [entries, accounts, range, expenseCategoryRules, includeUnmapped, showAccountsAsChildren]);

  // ---------- Net summary (Revenue − Expenses) ----------
  const netByMonth = useMemo(() => {
    const len = Math.max(revenueMatrix.months.length, expenseMatrix.months.length);
    const arr: number[] = new Array(len).fill(0);
    for (let i = 0; i < len; i++) {
      const rev = revenueMatrix.colTotals[i] ?? 0;
      const exp = expenseMatrix.colTotals[i] ?? 0;
      arr[i] = rev - exp;
    }
    return arr;
  }, [revenueMatrix.colTotals, expenseMatrix.colTotals, revenueMatrix.months.length, expenseMatrix.months.length]);

  const netGrandTotal = useMemo(
    () => netByMonth.reduce((s, v) => s + v, 0),
    [netByMonth]
  );

  return (
    <main style={{ padding: 16 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Reports — Financial Analysis</h1>

      {/* Tabs */}
      <TabBar active={tab} onChange={setTab} />

      {/* Controls (sticky) */}
      <Controls
        range={range}
        setRange={setRange}
        showAccountsAsChildren={showAccountsAsChildren}
        setShowAccountsAsChildren={setShowAccountsAsChildren}
        includeUnmapped={includeUnmapped}
        setIncludeUnmapped={setIncludeUnmapped}
      />

      {/* Status / Content */}
      {loading ? (
        <div
          style={{
            padding: 12,
            marginTop: 12,
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            background: "#f9fafb",
          }}
        >
          Loading…
        </div>
      ) : error ? (
        <div
          style={{
            padding: 12,
            marginTop: 12,
            border: "1px solid #fecaca",
            borderRadius: 8,
            background: "#fef2f2",
            color: "#991b1b",
            whiteSpace: "pre-wrap",
          }}
        >
          {error}
        </div>
      ) : (
        <>
          {/* OVERVIEW */}
          {tab === "overview" && (
            <>
              <Section title="At a glance">
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px,1fr))", gap: 12 }}>
                  <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>Revenue Total</div>
                    <div style={{ fontSize: 20, fontWeight: 700 }}>₱ {fmt(revenueMatrix.grandTotal)}</div>
                  </div>
                  <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>Expense Total</div>
                    <div style={{ fontSize: 20, fontWeight: 700 }}>₱ {fmt(expenseMatrix.grandTotal)}</div>
                  </div>
                  <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: 12 }}>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>Net</div>
                    <div style={{ fontSize: 20, fontWeight: 700 }}>
                      ₱ {fmt(revenueMatrix.grandTotal - expenseMatrix.grandTotal)}
                    </div>
                  </div>
                </div>
              </Section>
            </>
          )}

          {/* ACTUALS */}
          {tab === "actuals" && (
            <>
              <Section title="Actuals — Receipts (Revenue)">
                <ReceiptsMatrixSection
                  months={revenueMatrix.months}
                  rows={revenueMatrix.rows}
                  colTotals={revenueMatrix.colTotals}
                  grandTotal={revenueMatrix.grandTotal}
                  format={(n) => `₱ ${fmt(n)}`}
                />
              </Section>

              <div style={{ height: 12 }} />

              <Section title="Actuals — Expenses">
                <ReceiptsMatrixSection
                  months={expenseMatrix.months}
                  rows={expenseMatrix.rows}
                  colTotals={expenseMatrix.colTotals}
                  grandTotal={expenseMatrix.grandTotal}
                  format={(n) => `₱ ${fmt(n)}`}
                />
              </Section>

              <div style={{ height: 12 }} />

              {/* Income vs Expenses chart (crossover markers) */}
              <Section title="Income vs Expenses — Crossover">
                <IncomeVsExpensesChart
                  months={revenueMatrix.months}
                  revenue={revenueMatrix.colTotals}
                  expenses={expenseMatrix.colTotals}
                />
              </Section>

              <div style={{ height: 12 }} />

              {/* Net summary */}
              <Section title="Net — Revenue minus Expenses">
                <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff", overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ background: "#f9fafb" }}>
                        <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Row</th>
                        {revenueMatrix.months.map((m) => (
                          <th key={m} style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #e5e7eb" }}>{m}</th>
                        ))}
                        <th style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", fontWeight: 600 }}>Net (Rev − Exp)</td>
                        {netByMonth.map((v, i) => (
                          <td key={i} style={{ padding: 8, borderBottom: "1px solid #f3f4f6", textAlign: "right" }}>
                            ₱ {fmt(v)}
                          </td>
                        ))}
                        <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6", textAlign: "right", fontWeight: 700 }}>
                          ₱ {fmt(netGrandTotal)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Section>
            </>
          )}

          {/* BUDGET */}
          {tab === "budget" && (
            <Section title="Budget / Projections">
              <ProjectionsSection base={revenueMatrix} format={(n)=>`₱ ${fmt(n)}`} />
            </Section>
          )}

          {/* VARIANCE (stub for next step) */}
          {tab === "variance" && (
            <Section title="Variance (Actual vs Budget)">
              <div style={{ padding: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", color: "#6b7280", fontSize: 12 }}>
                We’ll add a Variance matrix here next (A vs B with abs/% deltas and color cues).
              </div>
            </Section>
          )}

          {/* CATALOG */}
          {tab === "catalog" && (
            <Section title="Accounts Catalog">
              <AccountsCatalog accounts={accounts as any} />
            </Section>
          )}
        </>
      )}
    </main>
  );
}
