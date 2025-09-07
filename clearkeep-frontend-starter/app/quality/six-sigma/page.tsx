"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { computePChartSeries } from "../../../components/quality/PChart";
import { computeXmRSeries } from "../../../components/quality/XmR";
import {
  buildAccountParetoFromLines,
  buildDefectTypeParetoFromUnits,
} from "../../../components/quality/Pareto";

// Dates & grain helpers
import {
  ymd,
  ym,
  addDays,
  parseISODate,
  daysBetween,
  monthsCovered,
  isYmd,
} from "../../../lib/quality/time";

// Number helpers
import { fmt, fmtInt } from "../../../lib/quality/format";

// Sigma helper
import { sigmaFromYield } from "../../../lib/quality/stats";

// API helpers
import { fetchAccounts, fetchJournalPaged, fetchLocksStatus } from "../../../lib/quality/api";

// Selectors (pure compute)
import { buildFacts as selBuildFacts } from "../../../lib/quality/selectors";

// Centralized defect rules
import { countDefects } from "../../../lib/quality/defects";

// Locks helper
import { normalizeLocks } from "../../../lib/quality/locks";

// Modular/presentational components
import ReportBuilder from "../../../components/quality/ReportBuilder";
import AccountsFilter from "../../../components/quality/AccountsFilter";
import KpiCards from "../../../components/quality/KpiCards";
import ToolsBar from "../../../components/quality/ToolsBar";
import MonthlyBarChart from "../../../components/quality/MonthlyBarChart";
import PChartSection from "../../../components/quality/sections/PChartSection";
import XmRSection from "../../../components/quality/sections/XmRSection";
import ParetoAccountsSection from "../../../components/quality/sections/ParetoAccountsSection";
import ParetoDefectsSection from "../../../components/quality/sections/ParetoDefectsSection";
import PeriodReworkSection from "../../../components/quality/sections/PeriodReworkSection";
import NotesSection from "../../../components/quality/sections/NotesSection";
import { Section, Card } from "../../../components/quality/ui";

/**
 * ClearKeep — Quality + Analytics (Six Sigma) v1
 */

type Grain = "day" | "week" | "month";
type CompareMode = "none" | "prev_period" | "prev_year" | "custom";
type Domain = "expense" | "revenue" | "all";

type ToolView =
  | "pchart"
  | "xmr"
  | "pareto_accounts"
  | "pareto_defects"
  | "acct_trend_mom"
  | "receipts_matrix" // kept for now so ToolsBar won't break; page simply doesn't render extra UI for it yet
  | "all";

type Account = {
  id: number | string;
  name?: string;
  code?: string;
  type?: string | null;
  account_type?: string | null;
  kind?: string | null;
  group?: string | null;
};

type JournalLine = {
  account_id?: number | string | null;
  account_code?: string | null;
  account_name?: string | null;
  debit?: number | null;
  credit?: number | null;
};

type JournalEntry = {
  id: number | string;
  entry_no?: number | null;
  entry_date: string; // YYYY-MM-DD
  is_locked?: boolean;
  locked_at?: string | null;
  posted_at?: string | null;
  posted_by_user_id?: number | null;
  reference_no?: string | null;
  source_module?: string | null; // "reversal" for reworks
  lines?: JournalLine[];
};

type FetchState<T> = { loading: boolean; error: string | null; data: T | null };
type Range = { from: string; to: string }; // YYYY-MM-DD inclusive

function normalizeRange(r: Range): Range {
  const today = new Date();
  const def = ymd(today);
  let from = isYmd(r.from) ? r.from : (isYmd(r.to) ? r.to : def);
  let to = isYmd(r.to) ? r.to : from;
  const f = parseISODate(from),
    t = parseISODate(to);
  if (f > t) {
    const tmp = from;
    from = to;
    to = tmp;
  }
  return { from, to };
}
function rangeDays(r: Range): number {
  const n = normalizeRange(r);
  const f = parseISODate(n.from),
    t = parseISODate(n.to);
  return daysBetween(t, f) + 1;
}
function previousPeriod(r: Range): Range {
  const n = normalizeRange(r);
  const len = rangeDays(n);
  return { from: ymd(addDays(parseISODate(n.from), -len)), to: ymd(addDays(parseISODate(n.from), -1)) };
}
function shiftRangeYears(r: Range, years: number): Range {
  const n = normalizeRange(r);
  const f = parseISODate(n.from);
  f.setFullYear(f.getFullYear() + years);
  const t = parseISODate(n.to);
  t.setFullYear(t.getFullYear() + years);
  return { from: ymd(f), to: ymd(t) };
}

export default function SixSigmaAnalyticsPage() {
  // Defaults: last 90 days
  const today = new Date();
  const defTo = ymd(today);
  const defFrom = ymd(addDays(today, -89));

  // Report Builder state
  const [grain, setGrain] = useState<Grain>("month");
  const [domain, setDomain] = useState<Domain>("expense");
  const [postedOnly, setPostedOnly] = useState<boolean>(false);
  const [rangeA, setRangeA] = useState<Range>({ from: defFrom, to: defTo });
  const [compareMode, setCompareMode] = useState<CompareMode>("none");
  const [rangeB, setRangeB] = useState<Range>(() => previousPeriod({ from: defFrom, to: defTo }));
  const [slaDays, setSlaDays] = useState<number>(2);
  const [includeReversals, setIncludeReversals] = useState<boolean>(true);
  const [includeReopen, setIncludeReopen] = useState<boolean>(true);

  // Tools tab
  const [toolView, setToolView] = useState<ToolView>("pchart");

  // Accounts
  const [acctState, setAcctState] = useState<FetchState<Account[]>>({
    loading: false,
    error: null,
    data: null,
  });
  const [acctSearch, setAcctSearch] = useState<string>("");
  const [selectedAccounts, setSelectedAccounts] = useState<Array<string | number>>([]);
  const selectedSet = useMemo(() => new Set(selectedAccounts.map(String)), [selectedAccounts]);

  // Journal + Locks (A & B)
  const [jA, setJA] = useState<FetchState<JournalEntry[]>>({
    loading: false,
    error: null,
    data: null,
  });
  const [jB, setJB] = useState<FetchState<JournalEntry[]>>({
    loading: false,
    error: null,
    data: null,
  });
  const [locks, setLocks] = useState<FetchState<any>>({ loading: false, error: null, data: null });

  // Effective Range B
  const effRangeB: Range | null = useMemo(() => {
    const A = normalizeRange(rangeA);
    if (compareMode === "none") return null;
    if (compareMode === "prev_period") return previousPeriod(A);
    if (compareMode === "prev_year") return shiftRangeYears(A, -1);
    return normalizeRange(rangeB);
  }, [rangeA, rangeB, compareMode]);

  // Load accounts
  useEffect(() => {
    let mounted = true;
    (async () => {
      setAcctState({ loading: true, error: null, data: null });
      try {
        const data = await fetchAccounts();
        if (!mounted) return;
        setAcctState({ loading: false, error: null, data });
      } catch (e: any) {
        setAcctState({ loading: false, error: e?.message || "Failed to load accounts", data: [] });
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // Reload A/B + locks
  const reload = useCallback(async () => {
    try {
      const A = normalizeRange(rangeA);
      setJA({ loading: true, error: null, data: null });
      const Adata = await fetchJournalPaged(A, postedOnly, 200);
      setJA({ loading: false, error: null, data: Adata });

      if (effRangeB) {
        setJB({ loading: true, error: null, data: null });
        const Bdata = await fetchJournalPaged(effRangeB, postedOnly, 200);
        setJB({ loading: false, error: null, data: Bdata });
      } else {
        setJB({ loading: false, error: null, data: null });
      }

      const Afrom = parseISODate(A.from),
        Ato = parseISODate(A.to);
      let minFrom = ym(Afrom),
        maxTo = ym(Ato);
      if (effRangeB) {
        const Bfrom = parseISODate(effRangeB.from),
          Bto = parseISODate(effRangeB.to);
        minFrom = [minFrom, ym(Bfrom)].sort()[0];
        maxTo = [maxTo, ym(Bto)].sort().slice(-1)[0];
      }
      setLocks({ loading: true, error: null, data: null });
      const lockData = await fetchLocksStatus(minFrom, maxTo);
      setLocks({ loading: false, error: null, data: lockData });
    } catch (e: any) {
      const msg = e?.message || "Failed to reload data";
      setJA({ loading: false, error: msg, data: null });
      setJB({ loading: false, error: msg, data: null });
      setLocks({ loading: false, error: msg, data: null });
    }
  }, [rangeA, effRangeB, postedOnly]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Map of accounts for label enrichment
  const acctMap: Map<string | number, Account> = useMemo(() => {
    const m = new Map<string | number, Account>();
    (acctState.data || []).forEach((a) => m.set(a.id, a));
    return m;
  }, [acctState.data]);

  // ---------- Facts (via selectors) ----------
  const factsA = useMemo(
    () =>
      selBuildFacts({
        entries: jA.data as any,
        accounts: acctState.data as any,
        domain: domain as any,
        grain: grain as any,
        range: rangeA as any,
        selectedSet,
      }),
    [jA.data, acctState.data, domain, grain, rangeA, selectedSet]
  );

  const factsB = useMemo(
    () =>
      effRangeB
        ? selBuildFacts({
            entries: jB.data as any,
            accounts: acctState.data as any,
            domain: domain as any,
            grain: grain as any,
            range: effRangeB as any,
            selectedSet,
          })
        : null,
    [jB.data, acctState.data, domain, grain, effRangeB, selectedSet]
  );

  // Totals by bucket (for XmR/Trend)
  const bucketsA = factsA.buckets;
  const aggA = useMemo(() => {
    const sums: Record<string, number> = {};
    for (const b of bucketsA) sums[b] = 0;
    for (const ln of factsA.lines) sums[ln.bucket] = (sums[ln.bucket] || 0) + ln.amount;
    return bucketsA.map((b) => sums[b] || 0);
  }, [factsA.lines, bucketsA]);

  const bucketsB = factsB?.buckets || [];
  const aggB = useMemo(() => {
    if (!factsB) return [];
    const sums: Record<string, number> = {};
    for (const b of bucketsB) sums[b] = 0;
    for (const ln of factsB.lines) sums[ln.bucket] = (sums[ln.bucket] || 0) + ln.amount;
    return bucketsB.map((b) => sums[b] || 0);
  }, [factsB, bucketsB]);

  // Pareto breakdown data (for Accounts)
  const paretoAcctA = useMemo(() => {
    const rows = factsA.lines.map((ln) => {
      const a = acctMap.get((ln.account_id as any) ?? "");
      const fallbackCode = ln.account_code || a?.code || (ln.account_id != null ? String(ln.account_id) : null);
      const fallbackName = ln.account_name || a?.name || (fallbackCode ? `Account ${fallbackCode}` : "Unknown");
      return { account_id: ln.account_id, account_code: fallbackCode, account_name: fallbackName, amount: ln.amount };
    });
    return buildAccountParetoFromLines(rows, { topN: 10, groupOthers: true });
  }, [factsA.lines, acctMap]);

  const paretoAcctB = useMemo(() => {
    if (!factsB) return null;
    const rows = factsB.lines.map((ln) => {
      const a = acctMap.get((ln.account_id as any) ?? "");
      const fallbackCode = ln.account_code || a?.code || (ln.account_id != null ? String(ln.account_id) : null);
      const fallbackName = ln.account_name || a?.name || (fallbackCode ? `Account ${fallbackCode}` : "Unknown");
      return { account_id: ln.account_id, account_code: fallbackCode, account_name: fallbackName, amount: ln.amount };
    });
    return buildAccountParetoFromLines(rows, { topN: 10, groupOthers: true });
  }, [factsB, acctMap]);

  // Totals for KPI card
  const totalA = useMemo(() => aggA.reduce((a, b) => a + b, 0), [aggA]);
  const totalB = useMemo(() => aggB.reduce((a, b) => a + b, 0), [aggB]);

  // KPIs — use centralized defect counter
  function sigmaKpis(unitsLen: number, defects: number) {
    const U = unitsLen;
    const y = U > 0 ? 1 - defects / U : 1;
    const dpmo = U > 0 ? (defects / U) * 1_000_000 : 0;
    return { units: U, defects, yield: y, dpmo, sigma: sigmaFromYield(y) };
  }

  // Build Set<YYYY-MM> for reopened months toggle
  const reopenedMonths = useMemo(() => {
    const out = new Map<string, string>();
    const list = normalizeLocks(locks.data);
    for (const r of list) {
      const note = (r.note || "").toLowerCase();
      if (includeReopen && (note.includes("reopen") || note.includes("reclose"))) out.set(r.period, r.note || "");
    }
    return out;
  }, [locks.data, includeReopen]);

  // A defects (centralized)
  const resA = useMemo(
    () =>
      countDefects(
        (factsA.units as any[]).map((u) => ({
          id: u.id,
          date: u.date,
          is_locked: u.is_locked,
          source_module: u.source_module || null,
          bucket: u.bucket,
        })),
        {
          slaDays,
          includeReversals,
          includeReopenedMonths: includeReopen,
          reopenedMonths: new Set<string>(Array.from(reopenedMonths.keys())),
        }
      ),
    [factsA.units, slaDays, includeReversals, includeReopen, reopenedMonths]
  );

  const kpiA = useMemo(
    () => sigmaKpis((factsA.units as any[]).length, resA.defects),
    [factsA.units, resA.defects]
  );

  // B defects (centralized)
  const resB = useMemo(
    () =>
      factsB
        ? countDefects(
            (factsB.units as any[]).map((u) => ({
              id: u.id,
              date: u.date,
              is_locked: u.is_locked,
              source_module: u.source_module || null,
              bucket: u.bucket,
            })),
            {
              slaDays,
              includeReversals,
              includeReopenedMonths: includeReopen,
              reopenedMonths: new Set<string>(Array.from(reopenedMonths.keys())),
            }
          )
        : null,
    [factsB, slaDays, includeReversals, includeReopen, reopenedMonths]
  );

  const kpiB = useMemo(
    () => (factsB && resB ? sigmaKpis((factsB.units as any[]).length, resB.defects) : null),
    [factsB, resB]
  );

  const anyLoading = jA.loading || jB.loading || locks.loading || acctState.loading;
  const anyError = jA.error || jB.error || locks.error || acctState.error;

  // p-Chart series (compute only)
  const pA = useMemo(
    () => computePChartSeries(factsA.units as any, factsA.buckets, { slaDays, includeReversals }),
    [factsA.units, factsA.buckets, slaDays, includeReversals]
  );
  const pB = useMemo(
    () => (factsB ? computePChartSeries(factsB.units as any, factsB.buckets, { slaDays, includeReversals }) : null),
    [factsB, slaDays, includeReversals]
  );

  // Account Trend (A only)
  const monthsA = useMemo(() => {
    const A = normalizeRange(rangeA);
    return monthsCovered(parseISODate(A.from), parseISODate(A.to));
  }, [rangeA]);

  const moSeriesA = useMemo(() => {
    if ((selectedAccounts || []).length === 0) return { labels: monthsA, values: monthsA.map(() => 0) };
    const sums: Record<string, number> = {};
    for (const m of monthsA) sums[m] = 0;
    for (const ln of factsA.lines) {
      const m = ym(parseISODate(ln.date));
      if (sums[m] === undefined) continue;
      if (selectedAccounts.length > 0 && !selectedAccounts.includes((ln.account_id as any))) continue;
      sums[m] += ln.amount;
    }
    return { labels: monthsA, values: monthsA.map((m) => sums[m] || 0) };
  }, [monthsA, factsA.lines, selectedAccounts]);

  // KPI labels
  const aLabel = `${domain.toUpperCase()} • ${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to}`;
  const bLabel =
    effRangeB ? (compareMode === "custom" ? `${effRangeB.from} → ${effRangeB.to}` : compareMode.replace("_", " ")) : undefined;

  // Titles for sections
  const pTitleA = `Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`;
  const pTitleB = effRangeB
    ? compareMode === "custom"
      ? `Range B (${effRangeB.from} → ${effRangeB.to})`
      : `Range B (${compareMode.replace("_", " ")})`
    : null;

  // XmR series (compute only)
  const xmrA = useMemo(() => computeXmRSeries(aggA, bucketsA), [aggA, bucketsA]);
  const xmrB = useMemo(() => (factsB ? computeXmRSeries(aggB, bucketsB) : null), [factsB, aggB, bucketsB]);

  // Combined months for Period Rework table (unique + sorted)
  const periodMonths = useMemo(() => {
    const A = normalizeRange(rangeA);
    const mA = monthsCovered(parseISODate(A.from), parseISODate(A.to));
    let mB: string[] = [];
    if (effRangeB) {
      mB = monthsCovered(parseISODate(effRangeB.from), parseISODate(effRangeB.to));
    }
    return Array.from(new Set<string>([...mA, ...mB])).sort();
  }, [rangeA, effRangeB]);

  // Pareto — Defects series (compute)
  const paretoDefA = useMemo(() => {
    const units = (factsA.units as any[]).map((u) => ({
      id: u.id,
      date: u.date,
      is_locked: u.is_locked,
      source_module: u.source_module || null,
    }));
    return buildDefectTypeParetoFromUnits(units, { slaDays, includeReversals, topN: 6, groupOthers: false });
  }, [factsA.units, slaDays, includeReversals]);

  const paretoDefB = useMemo(() => {
    if (!factsB) return null;
    const units = (factsB.units as any[]).map((u) => ({
      id: u.id,
      date: u.date,
      is_locked: u.is_locked,
      source_module: u.source_module || null,
    }));
    return buildDefectTypeParetoFromUnits(units, { slaDays, includeReversals, topN: 6, groupOthers: false });
  }, [factsB, slaDays, includeReversals]);

  return (
    <main style={{ padding: 16 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>Quality + Analytics (Six Sigma) — v1</h1>

      {/* Report Builder */}
      <ReportBuilder
        grain={grain}
        setGrain={setGrain}
        domain={domain}
        setDomain={setDomain}
        rangeA={rangeA}
        setRangeA={setRangeA}
        compareMode={compareMode}
        setCompareMode={setCompareMode}
        rangeB={rangeB}
        setRangeB={setRangeB}
        postedOnly={postedOnly}
        setPostedOnly={setPostedOnly}
        slaDays={slaDays}
        setSlaDays={setSlaDays}
        includeReversals={includeReversals}
        setIncludeReversals={setIncludeReversals}
        includeReopen={includeReopen}
        setIncludeReopen={setIncludeReopen}
        onReload={reload}
      />

      {/* Accounts filter */}
      <AccountsFilter
        title="Accounts"
        domain={domain}
        accounts={acctState.data || []}
        loading={acctState.loading}
        error={acctState.error}
        search={acctSearch}
        setSearch={setAcctSearch}
        selected={selectedAccounts}
        setSelected={setSelectedAccounts}
      />

      {/* KPI row */}
      <Section title="Six Sigma — KPIs">
        <KpiCards a={kpiA} b={kpiB ?? undefined} aLabel={aLabel} bLabel={bLabel} />
      </Section>

      {/* Tools bar */}
      <ToolsBar value={toolView} onChange={setToolView} />

      {anyLoading ? (
        <div style={{ padding: 12, background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: 8 }}>Loading…</div>
      ) : anyError ? (
        <div style={{ padding: 12, background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, color: "#991b1b", whiteSpace: "pre-wrap" }}>
          {anyError}
        </div>
      ) : (
        <>
          {/* Financial cards */}
          <Section title="Financial — Totals">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 12 }}>
              <Card title="Total (A)" value={`₱ ${fmt(totalA)}`} sub={`${domain.toUpperCase()} • ${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to}`} />
              {bLabel ? (
                <>
                  <Card title="Total (B)" value={`₱ ${fmt(totalB)}`} sub={bLabel} />
                  <Card title="Δ (A − B)" value={`₱ ${fmt(totalA - totalB)}`} sub={totalB !== 0 ? `${fmt(((totalA - totalB) / Math.abs(totalB)) * 100)}%` : "—"} />
                </>
              ) : null}
            </div>
          </Section>

          {/* p-Chart section */}
          {(toolView === "pchart" || toolView === "all") && (
            <PChartSection a={{ ...pA, includeReversals, title: pTitleA }} b={pB && pTitleB ? { ...pB, includeReversals, title: pTitleB } : undefined} />
          )}

          {/* XmR section */}
          {(toolView === "xmr" || toolView === "all") && (
            <XmRSection
              a={{ ...xmrA, title: `Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})` }}
              b={xmrB && pTitleB ? { ...xmrB, title: pTitleB } : undefined}
            />
          )}

          {/* Pareto — Account totals */}
          {(toolView === "pareto_accounts" || toolView === "all") && (
            <ParetoAccountsSection
              a={{
                ...paretoAcctA,
                title: `Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`,
                valueFormatter: (v: number) => `₱ ${fmt(v)}`,
              }}
              b={
                pTitleB && paretoAcctB
                  ? {
                      ...paretoAcctB,
                      title: pTitleB,
                      valueFormatter: (v: number) => `₱ ${fmt(v)}`,
                    }
                  : undefined
              }
            />
          )}

          {/* Pareto — Defect types */}
          {(toolView === "pareto_defects" || toolView === "all") && (
            <ParetoDefectsSection
              a={{
                ...paretoDefA,
                title: `Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`,
                valueFormatter: (v: number) => fmtInt(v),
                note: `Defect rules: unposted > ${slaDays} days${includeReversals ? " + reversals" : ""}${includeReopen ? " + reopened months" : ""}.`,
              }}
              b={
                pTitleB && paretoDefB
                  ? {
                      ...paretoDefB,
                      title: pTitleB,
                      valueFormatter: (v: number) => fmtInt(v),
                      note: `Defect rules: unposted > ${slaDays} days${includeReversals ? " + reversals" : ""}${includeReopen ? " + reopened months" : ""}.`,
                    }
                  : undefined
              }
            />
          )}

          {/* Account Trend — Month by Month (A only) */}
          {(toolView === "acct_trend_mom" || toolView === "all") && (
            <Section title="Account Trend — Month by Month (₱)">
              {selectedAccounts.length === 0 ? (
                <div style={{ padding: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff", color: "#6b7280", fontSize: 12 }}>
                  Select one or more accounts (e.g., Electricity) to see month-by-month totals for Range A.
                </div>
              ) : (
                <MonthlyBarChart
                  labels={monthsA}
                  values={moSeriesA.values}
                  title={`Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`}
                  valueFormatter={(v) => `₱ ${fmt(v)}`}
                />
              )}
            </Section>
          )}

          {/* Period rework — extracted */}
          <PeriodReworkSection months={periodMonths} reopenedNotes={reopenedMonths} />

          {/* Notes — extracted */}
          <NotesSection slaDays={slaDays} includeReversals={includeReversals} includeReopen={includeReopen} />
        </>
      )}
    </main>
  );
}
