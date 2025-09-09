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
} from "../../../lib/quality/selectors";
import { getReceiptCategoryRules } from "../../../lib/quality/receipts_categories";
import { getExpenseCategoryRules } from "../../../lib/quality/expenses_categories";

// Projections (for Budget)
import { projectReceipts } from "../../../lib/quality/projections";

// Presentational
import ReceiptsMatrixSection from "../../../components/quality/sections/ReceiptsMatrixSection";
import ProjectionsSection from "../../../components/quality/sections/ProjectionsSection";
import AccountsCatalog from "../../../components/quality/sections/AccountsCatalog";
import IncomeVsExpensesChart from "../../../components/quality/sections/IncomeVsExpensesChart";
import VarianceSection from "../../../components/quality/sections/VarianceSection";
import BudgetVsRevExpChart from "../../../components/quality/sections/BudgetVsRevExpChart";
import JournalLinesDrawer, { type JournalLineRow } from "../../../components/quality/sections/JournalLinesDrawer";
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

// helpers
function relabelMonthsToYear(months: string[], year: number): string[] {
  return months.map((m) => `${year}-${m.slice(5)}`);
}
function yearOf(iso: string): number {
  return Number(iso.slice(0, 4));
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
  const [entriesLastYear, setEntriesLastYear] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Central category mappings
  const revenueCategoryRules = useMemo(() => getReceiptCategoryRules(), []);
  const expenseCategoryRules = useMemo(() => getExpenseCategoryRules(), []);

  // Map accounts by id for fast lookups (drawer build)
  const acctMap = useMemo(() => {
    const m = new Map<string | number, Account>();
    (accounts || []).forEach((a) => m.set(a.id, a));
    return m;
  }, [accounts]);

  // Hardened reload: call our paged helper ONCE (it internally paginates)
  const reload = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // compute last-year range for convenience
      const from = range.from;
      const to = range.to;
      const fromY = yearOf(from);
      const toY = yearOf(to);
      const lastFrom = `${fromY - 1}${from.slice(4)}`;
      const lastTo = `${toY - 1}${to.slice(4)}`;

      const [accs, ents, entsLY] = await Promise.all([
        fetchAccounts(200), // will page internally if needed
        fetchJournalPaged({ from, to }, false, 200) as Promise<JournalEntry[]>,
        fetchJournalPaged({ from: lastFrom, to: lastTo }, false, 200) as Promise<JournalEntry[]>,
      ]);

      setAccounts(accs as any);
      setEntries(ents as any);
      setEntriesLastYear(entsLY as any);
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

  // =============== Budget controls for Variance ===============
  type BaselineMode = "this_period" | "last_year";
  const currentYear = yearOf(range.from);
  const [budgetUpliftPct, setBudgetUpliftPct] = useState<number>(0); // % applied to baseline
  const [baselineMode, setBaselineMode] = useState<BaselineMode>("last_year");
  const [targetYear, setTargetYear] = useState<number>(currentYear + 1);

  // Baseline matrix for Variance (revenue only)
  const baselineRevenueForVariance = useMemo(() => {
    if (baselineMode === "this_period") {
      return buildReceiptsMatrix({
        entries,
        accounts,
        domain: "revenue",
        range,
        selectedSet: undefined,
        categories: revenueCategoryRules,
        includeUnmapped,
        showAccountsAsChildren: false,
      });
    }
    // same months LAST YEAR
    const from = range.from;
    const to = range.to;
    const fromY = yearOf(from);
    const toY = yearOf(to);
    const lastRange: Range = {
      from: `${fromY - 1}${from.slice(4)}`,
      to: `${toY - 1}${to.slice(4)}`,
    };
    return buildReceiptsMatrix({
      entries: entriesLastYear,
      accounts,
      domain: "revenue",
      range: lastRange,
      selectedSet: undefined,
      categories: revenueCategoryRules,
      includeUnmapped,
      showAccountsAsChildren: false,
    });
  }, [baselineMode, entries, entriesLastYear, accounts, range, revenueCategoryRules, includeUnmapped]);

  // Budget matrix for Variance (apply uplift to baseline)
  const budgetMatrix = useMemo(() => {
    const projected = projectReceipts(baselineRevenueForVariance, {
      globalPct: (budgetUpliftPct || 0) / 100,
      monthlyFactors: new Array(12).fill(1),
      rounding: "none",
      compounding: false,
    });

    // If baseline is last_year, re-label months to targetYear for clarity
    if (baselineMode === "last_year") {
      return {
        ...projected,
        months: relabelMonthsToYear(projected.months, targetYear),
      };
    }
    return projected;
  }, [baselineRevenueForVariance, budgetUpliftPct, baselineMode, targetYear]);

  // ---------- Drawer state / wiring ----------
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerRows, setDrawerRows] = useState<JournalLineRow[]>([]);
  const [drawerMonth, setDrawerMonth] = useState<string | undefined>(undefined);
  const [drawerCategory, setDrawerCategory] = useState<string | undefined>(undefined);
  const [drawerTitle, setDrawerTitle] = useState<string | undefined>(undefined);

  // Build journal rows for a clicked (domain, month, categoryKey)
  const buildRowsFor = useCallback(
    (domain: "revenue" | "expense", month: string, categoryKey: string, categoryLabel: string) => {
      const lines: JournalLineRow[] = [];
      const rules = domain === "revenue" ? revenueCategoryRules : expenseCategoryRules;

      // iterate entries in month
      for (const e of entries || []) {
        if (!e.entry_date || !e.entry_date.startsWith(month)) continue; // ensure YYYY-MM match
        for (const ln of e.lines || []) {
          const acc = acctMap.get((ln.account_id as any) ?? "");
          // signed amount per domain
          const amt = signedAmountForDomain(ln as any, acc as any, domain as any);
          if (!amt) continue;

          // categorize line
          const key = (() => {
            // 1) account_ids
            for (const r of rules) {
              if (r.account_ids && ln.account_id != null && r.account_ids.includes(ln.account_id)) return r.key;
            }
            // 2) code prefixes
            const code = (ln.account_code || (acc as any)?.code || "").toString();
            if (code) {
              for (const r of rules) if (r.code_prefixes?.some((p) => code.startsWith(p))) return r.key;
            }
            // 3) name includes
            const name = (ln.account_name || (acc as any)?.name || "").toString().toLowerCase();
            if (name) {
              for (const r of rules) if (r.name_includes?.some((tok) => name.includes(tok.toLowerCase()))) return r.key;
            }
            return "";
          })();

          const matched = key ? key === categoryKey : (includeUnmapped && categoryKey === "_other");
          if (!matched) continue;

          lines.push({
            date: e.entry_date,
            entryId: e.id,
            accountCode: ln.account_code || (acc as any)?.code || null,
            accountName: ln.account_name || (acc as any)?.name || null,
            amount: amt,
          });
        }
      }

      lines.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : Math.abs(b.amount) - Math.abs(a.amount)));
      return { lines, title: `${domain === "revenue" ? "Revenue" : "Expenses"} • ${categoryLabel} — ${month}` };
    },
    [entries, acctMap, includeUnmapped, revenueCategoryRules, expenseCategoryRules]
  );

  // Map of category key -> label for quick lookup
  const revenueLabels = useMemo(() => {
    const m = new Map<string, string>();
    (revenueMatrix.rows || []).forEach((r) => m.set(r.key, r.label));
    return m;
  }, [revenueMatrix.rows]);
  const expenseLabels = useMemo(() => {
    const m = new Map<string, string>();
    (expenseMatrix.rows || []).forEach((r) => m.set(r.key, r.label));
    return m;
  }, [expenseMatrix.rows]);

  // Handlers for cell clicks
  const handleRevenueCell = useCallback(
    ({ rowKey, month }: { rowKey: string; month: string }) => {
      const label = revenueLabels.get(rowKey) || (rowKey === "_other" ? "Other Receipts" : rowKey);
      const { lines, title } = buildRowsFor("revenue", month, rowKey, label);
      setDrawerRows(lines);
      setDrawerMonth(month);
      setDrawerCategory(label);
      setDrawerTitle(title);
      setDrawerOpen(true);
    },
    [buildRowsFor, revenueLabels]
  );

  const handleExpenseCell = useCallback(
    ({ rowKey, month }: { rowKey: string; month: string }) => {
      const label = expenseLabels.get(rowKey) || (rowKey === "_other" ? "Other Expenses" : rowKey);
      const { lines, title } = buildRowsFor("expense", month, rowKey, label);
      setDrawerRows(lines);
      setDrawerMonth(month);
      setDrawerCategory(label);
      setDrawerTitle(title);
      setDrawerOpen(true);
    },
    [buildRowsFor, expenseLabels]
  );

  // Quick flags for variance
  const projectingDifferentYear = useMemo(() => {
    return baselineMode === "last_year" && targetYear !== yearOf(range.from);
  }, [baselineMode, targetYear, range.from]);

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
        <div style={{ padding: 12, marginTop: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#f9fafb" }}>
          Loading…
        </div>
      ) : error ? (
        <div style={{ padding: 12, marginTop: 12, border: "1px solid #fecaca", borderRadius: 8, background: "#fef2f2", color: "#991b1b", whiteSpace: "pre-wrap" }}>
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
                  onCellClick={({ rowKey, month }) => handleRevenueCell({ rowKey, month })}
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
                  onCellClick={({ rowKey, month }) => handleExpenseCell({ rowKey, month })}
                />
              </Section>

              <div style={{ height: 12 }} />

              {/* Income vs Expenses chart */}
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

          {/* VARIANCE */}
          {tab === "variance" && (
            <>
              <Section title="Budget Controls">
                <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 12, color: "#6b7280" }}>Baseline</span>
                    <select
                      value={baselineMode}
                      onChange={(e)=>setBaselineMode(e.target.value as any)}
                      style={{ border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px" }}
                    >
                      <option value="this_period">This period’s actuals</option>
                      <option value="last_year">Same months last year</option>
                    </select>
                  </label>

                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 12, color: "#6b7280" }}>Target year</span>
                    <input
                      type="number"
                      value={targetYear}
                      onChange={(e)=>setTargetYear(Number(e.target.value))}
                      style={{ width: 120, border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px", textAlign: "right" }}
                    />
                  </label>

                  <label style={{ display: "grid", gap: 6 }}>
                    <span style={{ fontSize: 12, color: "#6b7280" }}>Budget uplift (%)</span>
                    <input
                      type="number"
                      step={0.1}
                      value={budgetUpliftPct}
                      onChange={(e)=>setBudgetUpliftPct(Number(e.target.value))}
                      style={{ width: 120, border: "1px solid #d1d5db", borderRadius: 6, padding: "6px 8px", textAlign: "right" }}
                    />
                  </label>

                  {projectingDifferentYear && (
                    <div style={{ color: "#6b7280", fontSize: 12, maxWidth: 520 }}>
                      Planning view: bars are <b>Budget {targetYear}</b> built from <b>last year’s months</b> + uplift. Numerical variance vs current actuals is hidden (different-year comparison).
                    </div>
                  )}
                </div>
              </Section>

              <div style={{ height: 12 }} />

              {/* 3-way comparison chart: bars = Budget (possibly re-labeled to target year), lines = Revenue & Expenses */}
              <Section title={`Budget vs Revenue & Expenses${baselineMode === "last_year" ? ` — ${targetYear}` : ""}`}>
                <BudgetVsRevExpChart
                  months={baselineMode === "last_year" ? budgetMatrix.months : revenueMatrix.months}
                  budget={budgetMatrix.colTotals}
                  revenue={revenueMatrix.colTotals}
                  expenses={expenseMatrix.colTotals}
                />
              </Section>

              <div style={{ height: 12 }} />

              {/* Variance table only when comparing the same period */}
              {!projectingDifferentYear ? (
                <VarianceSection
                  title="Variance — Actual (Revenue) vs Budget"
                  actual={revenueMatrix}
                  budget={budgetMatrix}
                  format={(n)=>`₱ ${fmt(n)}`}
                  positiveIsGood={false} // below budget = good (green), over budget = bad (red)
                />
              ) : null}
            </>
          )}

          {/* CATALOG */}
          {tab === "catalog" && (
            <Section title="Accounts Catalog">
              <AccountsCatalog accounts={accounts as any} />
            </Section>
          )}

          {/* Journal Lines Drawer */}
          <JournalLinesDrawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            title={drawerTitle}
            month={drawerMonth}
            categoryLabel={drawerCategory}
            rows={drawerRows}
            format={(n)=>`₱ ${fmt(n)}`}
          />
        </>
      )}
    </main>
  );
}
