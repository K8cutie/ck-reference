"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { PChart, computePChartSeries } from "../../../components/quality/PChart";
import { XmRChart, computeXmRSeries } from "../../../components/quality/XmR";
import {
  ParetoChart,
  buildAccountParetoFromLines,
  buildDefectTypeParetoFromUnits,
} from "../../../components/quality/Pareto";
// Dates & grain helpers (extracted)
import {
  ymd,
  ym,
  addDays,
  parseISODate,
  daysBetween,
  bucketOf,
  monthsCovered,
  isYmd,
} from "../../../lib/quality/time";
// Number helpers (extracted)
import { fmt, fmtInt, clamp } from "../../../lib/quality/format";
// Modular controls
import ReportBuilder from "../../../components/quality/ReportBuilder";
// Modular Accounts filter
import AccountsFilter from "../../../components/quality/AccountsFilter";
// NEW: modular Receipts Matrix
import ReceiptsMatrix from "../../../components/quality/ReceiptsMatrix";

/**
 * ClearKeep — Quality + Analytics (Six Sigma) v1
 * Phase 1 (modularized): p-Chart + XmR + Pareto + Receipts Matrix as components/helpers
 *
 * - Flexible grain: Day / Week / Month
 * - Domain filter: Expense / Revenue / All
 * - Account filter: search + select specific accounts (e.g., Electricity)
 * - Compare: None / Previous Period / Previous Year / Custom A vs B
 * - Six Sigma overlays:
 *     • units (entries touching slice)
 *     • defects (unposted > SLA days; optional reversals)
 * - Period rework overlay: /gl/locks/status (reopen/reclose months)
 *
 * Endpoints (STATUS.md is source of truth):
 *   GET /gl/journal?date_from&date_to&limit&offset[&is_locked]
 *   GET /gl/accounts
 *   GET /gl/locks/status?from=YYYY-MM&to=YYYY-MM
 */

type Grain = "day" | "week" | "month";
type CompareMode = "none" | "prev_period" | "prev_year" | "custom";
type Domain = "expense" | "revenue" | "all";

/** Tools palette (includes: Receipts Matrix + Account Trend MoM) */
type ToolView =
  | "pchart"
  | "xmr"
  | "pareto_accounts"
  | "pareto_defects"
  | "acct_trend_mom"
  | "receipts_matrix"
  | "all";

type Account = {
  id: number | string;
  name?: string;
  code?: string;
  type?: string | null;         // preferred
  account_type?: string | null; // fallbacks
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
  is_locked: boolean;
  reference_no?: string | null;
  source_module?: string | null; // "reversal" if rework
  lines?: JournalLine[];
};

type LockStatus = {
  period: string; // YYYY-MM
  is_locked: boolean;
  note?: string | null; // contains "reopen"/"reclose" when reworked
  updated_at?: string | null;
};

type FetchState<T> = { loading: boolean; error: string | null; data: T | null };

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, "");
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";
function apiHeaders(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) h["X-API-Key"] = API_KEY;
  return h;
}
async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: apiHeaders(), cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`.trim());
  }
  return (await res.json()) as T;
}

// ------------ local utils that remain here for now ------------

// Acklam inverse normal CDF (kept local until stats.ts extraction)
function invNorm(p: number): number {
  const a=[-39.69683028665376,220.9460984245205,-275.9285104469687,138.357751867269,-30.66479806614716,2.506628277459239];
  const b=[-54.47609879822406,161.5858368580409,-155.6989798598866,66.80131188771972,-13.28068155288572];
  const c=[-0.007784894002430293,-0.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783];
  const d=[0.007784695709041462,0.3224671290700398,2.445134137142996,3.754408661907416];
  const plow=0.02425, phigh=1-plow; let q:number, r:number;
  if (p < plow) { q=Math.sqrt(-2*Math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
  if (phigh < p) { q=Math.sqrt(-2*Math.log(1-p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
  q=p-0.5; r=q*q; return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+1));
}
function sigmaFromYield(y: number) { return invNorm(clamp(y,1e-12,1-1e-12)) + 1.5; }

function accountType(a: Account | undefined): string {
  if (!a) return "other";
  const t = (a.type || a.account_type || a.kind || a.group || "").toString().toLowerCase();
  if (t.includes("expens")) return "expense";
  if (t.includes("revenue") || t.includes("income") || t === "sales") return "revenue";
  return t || "other";
}
function signedAmountFor(line: JournalLine, a: Account | undefined, domain: Domain): number {
  const debit = Number(line.debit || 0), credit = Number(line.credit || 0);
  const typ = accountType(a);
  if (domain === "expense") { if (typ !== "expense") return 0; return debit - credit; }
  if (domain === "revenue") { if (typ !== "revenue") return 0; return credit - debit; }
  if (typ === "expense") return debit - credit;
  if (typ === "revenue") return credit - debit;
  return 0;
}

type Range = { from: string; to: string }; // YYYY-MM-DD inclusive

function normalizeRange(r: Range): Range {
  const today = new Date();
  const def = ymd(today);
  let from = isYmd(r.from) ? r.from : (isYmd(r.to) ? r.to : def);
  let to   = isYmd(r.to)   ? r.to   : from;
  const f = parseISODate(from), t = parseISODate(to);
  if (f > t) { const tmp = from; from = to; to = tmp; }
  return { from, to };
}

function rangeDays(r: Range): number {
  const n = normalizeRange(r);
  const f = parseISODate(n.from), t = parseISODate(n.to);
  return daysBetween(t, f) + 1;
}
function previousPeriod(r: Range): Range {
  const n = normalizeRange(r);
  const len = rangeDays(n);
  return { from: ymd(addDays(parseISODate(n.from), -len)), to: ymd(addDays(parseISODate(n.from), -1)) };
}
function shiftRangeYears(r: Range, years: number): Range {
  const n = normalizeRange(r);
  const f = parseISODate(n.from); f.setFullYear(f.getFullYear() + years);
  const t = parseISODate(n.to);   t.setFullYear(t.getFullYear() + years);
  return { from: ymd(f), to: ymd(t) };
}

type FactLine = { date: string; account_id?: number|string|null; account_code?: string|null; account_name?: string|null; amount: number; bucket: string; };
type FactEntry = { id: number|string; date: string; bucket: string; is_locked: boolean; source_module?: string|null; };

/** /gl/locks/status can be array, {data:[]}, {month:obj}, etc. */
function normalizeLocks(data: any): LockStatus[] {
  if (!data) return [];
  if (Array.isArray(data)) return data as LockStatus[];
  if (Array.isArray((data as any).data)) return (data as any).data as LockStatus[];
  if (Array.isArray((data as any).items)) return (data as any).items as LockStatus[];
  if (typeof data === "object") {
    const arr: LockStatus[] = [];
    for (const [period, v] of Object.entries(data)) {
      if (v && typeof v === "object") {
        const o: any = v;
        arr.push({
          period,
          is_locked: Boolean(o.is_locked ?? o.locked ?? o.closed ?? false),
          note: o.note ?? o.status ?? null,
          updated_at: o.updated_at ?? null,
        });
      } else {
        arr.push({ period, is_locked: Boolean(v), note: null, updated_at: null });
      }
    }
    return arr;
  }
  return [];
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (<section style={{ marginTop: 16 }}>
    <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>{title}</h2>
    <div>{children}</div>
  </section>);
}
function Card({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (<div style={{ padding: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff" }}>
    <div style={{ fontSize: 12, color: "#6b7280" }}>{title}</div>
    <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
    {sub ? <div style={{ fontSize: 12, color: "#6b7280" }}>{sub}</div> : null}
  </div>);
}

/** Mini line chart (kept for potential reuse; not rendered unless needed) */
function MiniLineChart({ seriesA, seriesB, labels, aName, bName }:{
  seriesA: number[]; seriesB?: number[]; labels: string[]; aName: string; bName?: string;
}) {
  const w=720, h=200, pad=28; const all=[...seriesA, ...(seriesB||[])];
  const min=Math.min(...all,0), max=Math.max(...all,1), rng=max-min||1;
  const x=(i:number)=>pad+(i*(w-2*pad))/Math.max(labels.length-1,1);
  const y=(v:number)=>h-pad-((v-min)*(h-2*pad))/rng;
  const path=(s:number[])=>s.map((v,i)=>`${i?"L":"M"} ${x(i).toFixed(2)} ${y(v).toFixed(2)}`).join(" ");
  return (
    <div style={{ border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", padding:8 }}>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="auto" role="img" aria-label="Trend">
        <line x1={pad} y1={h-pad} x2={w-pad} y2={h-pad} stroke="#e5e7eb" />
        <line x1={pad} y1={pad} x2={pad} y2={h-pad} stroke="#e5e7eb" />
        {[0,0.5,1].map((t,i)=><line key={i} x1={pad} y1={pad+t*(h-2*pad)} x2={w-pad} y2={pad+t*(h-2*pad)} stroke="#f3f4f6" />)}
        <path d={path(seriesA)} fill="none" stroke="#111827" strokeWidth={2} />
        {seriesB ? <path d={path(seriesB)} fill="none" stroke="#9ca3af" strokeWidth={2} /> : null}
        {labels.map((m,i)=><text key={m} x={x(i)} y={h-pad+14} fontSize={10} textAnchor="middle" fill="#6b7280">{m}</text>)}
      </svg>
      <div style={{ display:"flex", gap:12, fontSize:12, color:"#6b7280", marginTop:6 }}>
        <span style={{ display:"inline-flex", alignItems:"center", gap:6 }}>
          <span style={{ width:12, height:2, background:"#111827", display:"inline-block" }} />{aName}
        </span>
        {bName ? <span style={{ display:"inline-flex", alignItems:"center", gap:6 }}>
          <span style={{ width:12, height:2, background:"#9ca3af", display:"inline-block" }} />{bName}
        </span> : null}
      </div>
    </div>
  );
}

/** NEW: small, local month-by-month bar chart for Range A (used by Account Trend) */
function MonthlyBarChart({ labels, values, title, valueFormatter }:{
  labels: string[]; values: number[]; title: string; valueFormatter: (n:number)=>string;
}) {
  const w = 880, h = 240, padLeft = 44, padBottom = 40, padTop = 12, padRight = 44;
  const max = Math.max(1, ...values.map(v => Math.abs(v)));
  const barW = Math.max(8, (w - padLeft - padRight) / Math.max(values.length, 1) - 6);
  const x = (i:number) => padLeft + i * (barW + 6);
  const y = (v:number) => h - padBottom - (Math.abs(v) / max) * (h - padTop - padBottom);

  return (
    <div style={{ border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", padding:12 }}>
      <div style={{ fontSize:12, color:"#6b7280", marginBottom:6 }}>{title}</div>
      <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="auto" role="img" aria-label="Account Month-by-Month">
        {[0,0.25,0.5,0.75,1].map((t,i)=>
          <line key={i} x1={padLeft} y1={padTop + t*(h-padTop-padBottom)} x2={w-padRight} y2={padTop + t*(h-padTop-padBottom)} stroke="#f3f4f6" />
        )}
        {values.map((v,i)=>(<g key={i}><rect x={x(i)} y={y(v)} width={barW} height={h - padBottom - y(v)} fill="#111827" rx={3} /></g>))}
        <text x={padLeft-6} y={padTop+12} fontSize={12} fill="#6b7280" textAnchor="end">{valueFormatter(max)}</text>
        <g transform={`translate(${w-padRight+6},0)`} fill="#6b7280" fontSize={12}>
          <text x={0} y={padTop+12}>100%</text>
          <text x={0} y={padTop + 0.5*(h-padTop-padBottom)+4}>50%</text>
          <text x={0} y={h - padBottom}>0%</text>
        </g>
        {labels.map((m,i)=>(<text key={i} x={x(i)+barW/2} y={h-10} fontSize={10} fill="#6b7280" textAnchor="middle">{m}</text>))}
      </svg>
    </div>
  );
}

export default function SixSigmaAnalyticsPage() {
  // Defaults: last 90 days
  const today = new Date(); const defTo = ymd(today); const defFrom = ymd(addDays(today, -89));

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

  // Which tool to show (now includes account MoM & receipts matrix)
  const [toolView, setToolView] = useState<ToolView>("pchart");

  // Accounts
  const [acctState, setAcctState] = useState<FetchState<Account[]>>({ loading: false, error: null, data: null });
  const [acctSearch, setAcctSearch] = useState<string>("");
  const [selectedAccounts, setSelectedAccounts] = useState<Array<string | number>>([]);

  // Journal + Locks (A & B)
  const [jA, setJA] = useState<FetchState<JournalEntry[]>>({ loading: false, error: null, data: null });
  const [jB, setJB] = useState<FetchState<JournalEntry[]>>({ loading: false, error: null, data: null });
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
        const data = await getJSON<Account[]>("/gl/accounts");
        if (!mounted) return;
        setAcctState({ loading: false, error: null, data });
      } catch (e: any) {
        setAcctState({ loading: false, error: e?.message || "Failed to load accounts", data: [] });
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Paged fetcher
  const fetchJournalRange = useCallback(async (r: Range): Promise<JournalEntry[]> => {
    const out: JournalEntry[] = []; const norm = normalizeRange(r); let offset = 0; const limit = 200;
    while (true) {
      const q = `/gl/journal?date_from=${norm.from}&date_to=${norm.to}&limit=${limit}&offset=${offset}` + (postedOnly ? `&is_locked=true` : ``);
      const page = await getJSON<JournalEntry[]>(q);
      out.push(...page);
      if (page.length < limit) break;
      offset += limit;
    }
    return out;
  }, [postedOnly]);

  // Reload A/B + locks
  const reload = useCallback(async () => {
    try {
      const A = normalizeRange(rangeA);
      setJA({ loading: true, error: null, data: null });
      const Adata = await fetchJournalRange(A);
      setJA({ loading: false, error: null, data: Adata });

      if (effRangeB) {
        setJB({ loading: true, error: null, data: null });
        const Bdata = await fetchJournalRange(effRangeB);
        setJB({ loading: false, error: null, data: Bdata });
      } else {
        setJB({ loading: false, error: null, data: null });
      }

      const Afrom = parseISODate(A.from), Ato = parseISODate(A.to);
      let minFrom = ym(Afrom), maxTo = ym(Ato);
      if (effRangeB) {
        const Bfrom = parseISODate(effRangeB.from), Bto = parseISODate(effRangeB.to);
        minFrom = [minFrom, ym(Bfrom)].sort()[0];
        maxTo = [maxTo, ym(Bto)].sort().slice(-1)[0];
      }
      setLocks({ loading: true, error: null, data: null });
      const lockData = await getJSON<any>(`/gl/locks/status?from=${minFrom}&to=${maxTo}`);
      setLocks({ loading: false, error: null, data: lockData });
    } catch (e: any) {
      const msg = e?.message || "Failed to reload data";
      setJA({ loading: false, error: msg, data: null });
      setJB({ loading: false, error: msg, data: null });
      setLocks({ loading: false, error: msg, data: null });
    }
  }, [rangeA, effRangeB, fetchJournalRange]);

  useEffect(() => { reload(); }, [reload]);

  const acctMap: Map<string | number, Account> = useMemo(() => {
    const m = new Map<string | number, Account>();
    (acctState.data || []).forEach((a) => m.set(a.id, a));
    return m;
  }, [acctState.data]);

  function buildFacts(entries: JournalEntry[] | null, r: Range) {
    const norm = normalizeRange(r);
    const start = parseISODate(norm.from), end = parseISODate(norm.to);
    const lines: Array<{ date: string; account_id?: number|string|null; account_code?: string|null; account_name?: string|null; amount: number; bucket: string; }> = [];
    const units: FactEntry[] = [];
    const unitSeen = new Set<string | number>();

    const buck = (ds: string) => bucketOf(parseISODate(ds), grain);

    for (const e of entries || []) {
      let touched = false;
      const bkey = buck(e.entry_date);
      for (const ln of e.lines || []) {
        const acc = acctMap.get((ln.account_id as any) ?? "");
        const amt = signedAmountFor(ln, acc, domain);
        if (domain !== "all" && amt === 0) continue;
        lines.push({ date: e.entry_date, account_id: ln.account_id ?? null, account_code: ln.account_code ?? null, account_name: ln.account_name ?? null, amount: amt, bucket: bkey });
        touched = true;
      }
      if (touched && !unitSeen.has(e.id)) {
        units.push({ id: e.id, date: e.entry_date, bucket: bkey, is_locked: !!e.is_locked, source_module: e.source_module || null });
        unitSeen.add(e.id);
      }
    }

    const buckets: string[] = [];
    if (grain === "day") { for (let d = new Date(start); d <= end; d = addDays(d,1)) buckets.push(ymd(d)); }
    else if (grain === "month") { buckets.push(...monthsCovered(start, end)); }
    else { const s = new Set<string>(); for (let d = new Date(start); d <= end; d = addDays(d,1)) s.add(bucketOf(d,"week")); buckets.push(...Array.from(s).sort()); }

    return { lines, units, buckets };
  }

  const factsA = useMemo(() => buildFacts(jA.data, rangeA), [jA.data, rangeA, grain, domain, acctMap]);
  const factsB = useMemo(() => effRangeB ? buildFacts(jB.data, effRangeB) : null, [jB.data, effRangeB, grain, domain, acctMap]);

  const bucketsA = factsA.buckets;
  const aggA = useMemo(() => {
    const sums: Record<string, number> = {}; for (const b of bucketsA) sums[b] = 0;
    for (const ln of factsA.lines) sums[ln.bucket] = (sums[ln.bucket] || 0) + ln.amount;
    return bucketsA.map((b) => sums[b] || 0);
  }, [factsA.lines, bucketsA]);

  const bucketsB = factsB?.buckets || [];
  const aggB = useMemo(() => {
    if (!factsB) return [];
    const sums: Record<string, number> = {}; for (const b of bucketsB) sums[b] = 0;
    for (const ln of factsB.lines) sums[ln.bucket] = (sums[ln.bucket] || 0) + ln.amount;
    return bucketsB.map((b) => sums[b] || 0);
  }, [factsB, bucketsB]);

  function buildAccountBreakdown(lines: any[]) {
    const keyOf = (ln: any) => (ln.account_id as any) ?? ln.account_code ?? ln.account_name ?? "unknown";
    const sums = new Map<any, number>();
    for (const ln of lines) { const k = keyOf(ln); sums.set(k, (sums.get(k) || 0) + ln.amount); }
    const rows = Array.from(sums.entries()).map(([k, v]) => {
      const a = acctMap.get(k);
      const code = a?.code ?? (typeof k === "string" ? "" : "");
      const name = a?.name ?? (typeof k === "string" ? String(k) : `Account ${String(k)}`);
      return { key: k, code, name, type: accountType(a), total: v };
    });
    rows.sort((a,b) => Math.abs(b.total) - Math.abs(a.total));
    return rows;
  }

  const rowsA = useMemo(() => buildAccountBreakdown(factsA.lines), [factsA.lines]);
  const rowsB = useMemo(() => factsB ? buildAccountBreakdown(factsB.lines) : [], [factsB]);
  const totalA = useMemo(() => aggA.reduce((a,b)=>a+b,0), [aggA]);
  const totalB = useMemo(() => aggB.reduce((a,b)=>a+b,0), [aggB]);

  function sigmaKpis(units: FactEntry[], defects: number) {
    const U = units.length; const y = U > 0 ? 1 - defects / U : 1; const dpmo = U > 0 ? (defects / U) * 1_000_000 : 0;
    return { units: U, defects, yield: y, dpmo, sigma: sigmaFromYield(y) };
  }
  function unitsAndDefects(units: FactEntry[], sla: number) {
    const todayLocal = new Date(); let defects = 0; const defective = new Set<string|number>();
    for (const u of units) {
      if (!u.is_locked) {
        const age = daysBetween(todayLocal, parseISODate(u.date));
        if (age > sla && !defective.has(u.id)) { defects += 1; defective.add(u.id); }
      }
      if (includeReversals && (u.source_module || "").toLowerCase().includes("reversal") && !defective.has(u.id)) {
        defects += 1; defective.add(u.id);
      }
    }
    return { defects, defectiveIds: defective };
  }

  const { defects: defectsA } = unitsAndDefects(factsA.units, slaDays);
  const kpiA = sigmaKpis(factsA.units, defectsA);
  const { defects: defectsB } = factsB ? unitsAndDefects(factsB.units, slaDays) : { defects: 0 };
  const kpiB = factsB ? sigmaKpis(factsB.units, defectsB) : null;

  const reopenedMonths = useMemo(() => {
    const out = new Map<string,string>();
    const list = normalizeLocks(locks.data);
    for (const r of list) {
      const note = (r.note || "").toLowerCase();
      if (includeReopen && (note.includes("reopen") || note.includes("reclose"))) out.set(r.period, r.note || "");
    }
    return out;
  }, [locks.data, includeReopen]);

  const anyLoading = jA.loading || jB.loading || locks.loading || acctState.loading;
  const anyError = jA.error || jB.error || locks.error || acctState.error;

  // ======= Precomputed alignment for charts (kept even if some views hidden) =======
  const allBuckets = useMemo(() => {
    if (!factsB) return bucketsA;
    const s = new Set<string>([...bucketsA, ...bucketsB]);
    return Array.from(s).sort();
  }, [bucketsA, bucketsB, factsB]);
  const alignedA = useMemo(() => {
    const map: Record<string, number> = {}; bucketsA.forEach((k,i)=>map[k]=aggA[i]); return allBuckets.map((k)=>map[k] ?? 0);
  }, [aggA, bucketsA, allBuckets]);
  const alignedB = useMemo(() => {
    if (!factsB) return null; const map: Record<string, number> = {}; bucketsB.forEach((k,i)=>map[k]=aggB[i]); return allBuckets.map((k)=>map[k] ?? 0);
  }, [aggB, bucketsB, allBuckets, factsB]);

  /** ------ p-Chart series ------ */
  const pA = useMemo(
    () => computePChartSeries(factsA.units, factsA.buckets, { slaDays, includeReversals }),
    [factsA.units, factsA.buckets, slaDays, includeReversals]
  );
  const pB = useMemo(
    () => factsB ? computePChartSeries(factsB.units, factsB.buckets, { slaDays, includeReversals }) : null,
    [factsB, slaDays, includeReversals]
  );

  /** ------ XmR series ------ */
  const xmrA = useMemo(
    () => computeXmRSeries(alignedA, allBuckets),
    [alignedA, allBuckets]
  );
  const xmrB = useMemo(
    () => alignedB ? computeXmRSeries(alignedB, allBuckets) : null,
    [alignedB, allBuckets]
  );

  /** ------ Pareto series (with label enrichment) ------ */
  const paretoAcctA = useMemo(() => {
    const rows = factsA.lines.map(ln => {
      const a = acctMap.get((ln.account_id as any) ?? "");
      const fallbackCode = ln.account_code || a?.code || (ln.account_id != null ? String(ln.account_id) : null);
      const fallbackName = ln.account_name || a?.name || (fallbackCode ? `Account ${fallbackCode}` : "Unknown");
      return { account_id: ln.account_id, account_code: fallbackCode, account_name: fallbackName, amount: ln.amount };
    });
    return buildAccountParetoFromLines(rows, { topN: 10, groupOthers: true });
  }, [factsA.lines, acctMap]);

  const paretoAcctB = useMemo(() => {
    if (!factsB) return null;
    const rows = factsB.lines.map(ln => {
      const a = acctMap.get((ln.account_id as any) ?? "");
      const fallbackCode = ln.account_code || a?.code || (ln.account_id != null ? String(ln.account_id) : null);
      const fallbackName = ln.account_name || a?.name || (fallbackCode ? `Account ${fallbackCode}` : "Unknown");
      return { account_id: ln.account_id, account_code: fallbackCode, account_name: fallbackName, amount: ln.amount };
    });
    return buildAccountParetoFromLines(rows, { topN: 10, groupOthers: true });
  }, [factsB, acctMap]);

  const paretoDefA = useMemo(() => {
    const units = factsA.units.map(u => ({
      id: u.id,
      date: u.date,
      is_locked: u.is_locked,
      source_module: u.source_module || null,
    }));
    return buildDefectTypeParetoFromUnits(units, { slaDays, includeReversals, topN: 6, groupOthers: false });
  }, [factsA.units, slaDays, includeReversals]);

  const paretoDefB = useMemo(() => {
    if (!factsB) return null;
    const units = factsB.units.map(u => ({
      id: u.id,
      date: u.date,
      is_locked: u.is_locked,
      source_module: u.source_module || null,
    }));
    return buildDefectTypeParetoFromUnits(units, { slaDays, includeReversals, topN: 6, groupOthers: false });
  }, [factsB, slaDays, includeReversals]);

  /** ------ Account Trend — inputs ------ */
  const monthsA = useMemo(() => {
    const A = normalizeRange(rangeA);
    return monthsCovered(parseISODate(A.from), parseISODate(A.to));
  }, [rangeA]);

  const moSeriesA = useMemo(() => {
    if ((selectedAccounts || []).length === 0) return { labels: monthsA, values: monthsA.map(()=>0) };
    const sums: Record<string, number> = {}; for (const m of monthsA) sums[m] = 0;
    for (const ln of factsA.lines) {
      const m = ym(parseISODate(ln.date));
      if (sums[m] === undefined) continue;
      if (selectedAccounts.length > 0 && !selectedAccounts.includes((ln.account_id as any))) continue;
      sums[m] += ln.amount;
    }
    return { labels: monthsA, values: monthsA.map((m)=>sums[m] || 0) };
  }, [monthsA, factsA.lines, selectedAccounts]);

  /** ------ Receipts Matrix (Range A) ------ */
  type MatrixRow = { key: string; label: string; values: number[]; total: number };
  const receiptsMatrixA = useMemo(() => {
    // Build month index
    const mIndex = new Map<string, number>(); monthsA.forEach((m, i) => mIndex.set(m, i));
    const rows = new Map<string, MatrixRow>();

    const labelFor = (ln: FactLine) => {
      const a = acctMap.get((ln.account_id as any) ?? "");
      const code = ln.account_code || a?.code || (ln.account_id != null ? String(ln.account_id) : "");
      const name = ln.account_name || a?.name || (code ? `Account ${code}` : "Unknown");
      return { key: String((ln.account_id as any) ?? ln.account_code ?? name), label: (code ? `${code} — ` : "") + name };
    };

    for (const ln of factsA.lines) {
      const month = ym(parseISODate(ln.date));
      const idx = mIndex.get(month);
      if (idx === undefined) continue;
      // Respect account selection if set
      if (selectedAccounts.length > 0 && !selectedAccounts.includes((ln.account_id as any))) continue;

      const { key, label } = labelFor(ln);
      let r = rows.get(key);
      if (!r) {
        r = { key, label, values: monthsA.map(()=>0), total: 0 };
        rows.set(key, r);
      }
      r.values[idx] += ln.amount;
      r.total += ln.amount;
    }

    const out = Array.from(rows.values());
    out.sort((a,b)=> Math.abs(b.total) - Math.abs(a.total));
    const colTotals = monthsA.map((_,j)=> out.reduce((s,r)=> s + r.values[j], 0));
    const grandTotal = colTotals.reduce((s,v)=> s+v, 0);
    return { rows: out, colTotals, grandTotal };
  }, [factsA.lines, monthsA, acctMap, selectedAccounts]);

  // --- button helper (pure style) ---
  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: "8px 10px",
    border: "1px solid #d1d5db",
    borderRadius: 6,
    background: active ? "#111827" : "#fff",
    color: active ? "#fff" : "#374151",
    cursor: "pointer",
    fontSize: 12,
  });

  return (
    <main style={{ padding: 16 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 12 }}>Quality + Analytics (Six Sigma) — v1</h1>

      {/* Report Builder — modular */}
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

      {/* Accounts filter — modular */}
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

      {anyLoading ? (
        <div style={{ padding:12, background:"#f9fafb", border:"1px solid #e5e7eb", borderRadius:8 }}>Loading…</div>
      ) : anyError ? (
        <div style={{ padding:12, background:"#fef2f2", border:"1px solid #fecaca", borderRadius:8, color:"#991b1b", whiteSpace:"pre-wrap" }}>{anyError}</div>
      ) : (
        <>
          {/* Financial cards */}
          <Section title="Financial — Totals">
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4, minmax(0,1fr))", gap:12 }}>
              <Card title="Total (A)" value={`₱ ${fmt(totalA)}`} sub={`${domain.toUpperCase()} • ${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to}`} />
              {effRangeB ? (
                <>
                  <Card title="Total (B)" value={`₱ ${fmt(totalB)}`} sub={compareMode === "custom" ? `${effRangeB.from} → ${effRangeB.to}` : compareMode.replace("_"," ")} />
                  <Card title="Δ (A − B)" value={`₱ ${fmt(totalA - totalB)}`} sub={totalB !== 0 ? `${fmt(((totalA - totalB)/Math.abs(totalB))*100)}%` : "—"} />
                </>
              ) : null}
            </div>
          </Section>

          {/* Six Sigma tools button bar */}
          <div style={{ border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", padding:12, marginTop:12 }}>
            <div style={{ display:"flex", gap:12, alignItems:"center", flexWrap:"wrap" }}>
              <div style={{ fontWeight:600, fontSize:13 }}>Six Sigma tools</div>
              <div style={{ display:"flex", gap:8, flexWrap:"wrap" }} role="tablist" aria-label="Six Sigma tools">
                <button type="button" onClick={()=>setToolView("pchart")} aria-pressed={toolView==="pchart"} style={btnStyle(toolView==="pchart")}>p‑Chart</button>
                <button type="button" onClick={()=>setToolView("xmr")} aria-pressed={toolView==="xmr"} style={btnStyle(toolView==="xmr")}>XmR</button>
                <button type="button" onClick={()=>setToolView("pareto_accounts")} aria-pressed={toolView==="pareto_accounts"} style={btnStyle(toolView==="pareto_accounts")}>Pareto (Account)</button>
                <button type="button" onClick={()=>setToolView("pareto_defects")} aria-pressed={toolView==="pareto_defects"} style={btnStyle(toolView==="pareto_defects")}>Pareto (Defects)</button>
                <button type="button" onClick={()=>setToolView("acct_trend_mom")} aria-pressed={toolView==="acct_trend_mom"} style={btnStyle(toolView==="acct_trend_mom")}>Account Trend (MoM)</button>
                <button type="button" onClick={()=>setToolView("receipts_matrix")} aria-pressed={toolView==="receipts_matrix"} style={btnStyle(toolView==="receipts_matrix")}>Receipts Matrix</button>
                <button type="button" onClick={()=>setToolView("all")} aria-pressed={toolView==="all"} style={btnStyle(toolView==="all")}>All</button>
              </div>
            </div>
          </div>

          {/* p‑Chart */}
          {(toolView === "pchart" || toolView === "all") && (
            <Section title="Quality — p‑Chart (defect proportion by period)">
              {pA.labels.length === 0 ? (
                <div style={{ padding:12, border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", color:"#6b7280", fontSize:12 }}>
                  No units in Range A for the selected filters; nothing to chart.
                </div>
              ) : (
                <PChart
                  labels={pA.labels}
                  p={pA.p}
                  ucl={pA.ucl}
                  lcl={pA.lcl}
                  pbar={pA.pbar}
                  n={pA.n}
                  title={`Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`}
                  includeReversals={includeReversals}
                />
              )}
              {effRangeB && pB ? (
                <div style={{ marginTop:12 }}>
                  {pB.labels.length === 0 ? (
                    <div style={{ padding:12, border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", color:"#6b7280", fontSize:12 }}>
                      No units in Range B; nothing to chart.
                    </div>
                  ) : (
                    <PChart
                      labels={pB.labels}
                      p={pB.p}
                      ucl={pB.ucl}
                      lcl={pB.lcl}
                      pbar={pB.pbar}
                      n={pB.n}
                      title={compareMode==="custom" ? `Range B (${effRangeB.from} → ${effRangeB.to})` : `Range B (${compareMode.replace("_"," ")})`}
                      includeReversals={includeReversals}
                    />
                  )}
                </div>
              ) : null}
            </Section>
          )}

          {/* XmR */}
          {(toolView === "xmr" || toolView === "all") && (
            <Section title="Quality — XmR (Individuals & Moving Range of totals)">
              {allBuckets.length === 0 ? (
                <div style={{ padding:12, border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", color:"#6b7280", fontSize:12 }}>
                  No periods in Range A; nothing to chart.
                </div>
              ) : (
                <XmRChart
                  labels={xmrA.labels}
                  x={xmrA.x}
                  mr={xmrA.mr}
                  x_ucl={xmrA.x_ucl}
                  x_lcl={xmrA.x_lcl}
                  x_cl={xmrA.x_cl}
                  mr_ucl={xmrA.mr_ucl}
                  mr_lcl={xmrA.mr_lcl}
                  mr_cl={xmrA.mr_cl}
                  xbar={xmrA.xbar}
                  mrbar={xmrA.mrbar}
                  title={`Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`}
                />
              )}
              {effRangeB && xmrB ? (
                <div style={{ marginTop:12 }}>
                  <XmRChart
                    labels={xmrB.labels}
                    x={xmrB.x}
                    mr={xmrB.mr}
                    x_ucl={xmrB.x_ucl}
                    x_lcl={xmrB.x_lcl}
                    x_cl={xmrB.x_cl}
                    mr_ucl={xmrB.mr_ucl}
                    mr_lcl={xmrB.mr_lcl}
                    mr_cl={xmrB.mr_cl}
                    xbar={xmrB.xbar}
                    mrbar={xmrB.mrbar}
                    title={compareMode==="custom" ? `Range B (${effRangeB.from} → ${effRangeB.to})` : `Range B (${compareMode.replace("_"," ")})`}
                  />
                </div>
              ) : null}
            </Section>
          )}

          {/* Pareto — Account totals */}
          {(toolView === "pareto_accounts" || toolView === "all") && (
            <Section title="Pareto — by Account (₱)">
              <div style={{ display:"grid", gridTemplateColumns: effRangeB ? "repeat(2, minmax(0, 1fr))" : "repeat(1, minmax(0, 1fr))", gap:12 }}>
                <ParetoChart
                  labels={paretoAcctA.labels}
                  bars={paretoAcctA.bars}
                  cumPct={paretoAcctA.cumPct}
                  total={paretoAcctA.total}
                  title={`Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`}
                  valueFormatter={(v)=>`₱ ${fmt(v)}`}
                  note="Bars show absolute magnitudes (sum of signed totals per account); cumulative line shows share of total absolute."
                />
                {effRangeB && paretoAcctB ? (
                  <ParetoChart
                    labels={paretoAcctB.labels}
                    bars={paretoAcctB.bars}
                    cumPct={paretoAcctB.cumPct}
                    total={paretoAcctB.total}
                    title={compareMode==="custom" ? `Range B (${effRangeB.from} → ${effRangeB.to})` : `Range B (${compareMode.replace("_"," ")})`}
                    valueFormatter={(v)=>`₱ ${fmt(v)}`}
                    note="Bars show absolute magnitudes (sum of signed totals per account); cumulative line shows share of total absolute."
                  />
                ) : null}
              </div>
            </Section>
          )}

          {/* Pareto — Defect types */}
          {(toolView === "pareto_defects" || toolView === "all") && (
            <Section title="Pareto — Defect Types (count)">
              <div style={{ display:"grid", gridTemplateColumns: effRangeB ? "repeat(2, minmax(0, 1fr))" : "repeat(1, minmax(0, 1fr))", gap:12 }}>
                <ParetoChart
                  labels={paretoDefA.labels}
                  bars={paretoDefA.bars}
                  cumPct={paretoDefA.cumPct}
                  total={paretoDefA.total}
                  title={`Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`}
                  valueFormatter={(v)=>fmtInt(v)}
                  note={`Defect rules: unposted > ${slaDays} days and${includeReversals ? "" : " not"} reversals.`}
                />
                {effRangeB && paretoDefB ? (
                  <ParetoChart
                    labels={paretoDefB.labels}
                    bars={paretoDefB.bars}
                    cumPct={paretoDefB.cumPct}
                    total={paretoDefB.total}
                    title={compareMode==="custom" ? `Range B (${effRangeB.from} → ${effRangeB.to})` : `Range B (${compareMode.replace("_"," ")})`}
                    valueFormatter={(v)=>fmtInt(v)}
                    note={`Defect rules: unposted > ${slaDays} days and${includeReversals ? "" : " not"} reversals.`}
                  />
                ) : null}
              </div>
            </Section>
          )}

          {/* Account Trend — Month by Month (A only) */}
          {(toolView === "acct_trend_mom" || toolView === "all") && (
            <Section title="Account Trend — Month by Month (₱)">
              {selectedAccounts.length === 0 ? (
                <div style={{ padding:12, border:"1px solid #e5e7eb", borderRadius:8, background:"#fff", color:"#6b7280", fontSize:12 }}>
                  Select one or more accounts (e.g., Electricity) to see month‑by‑month totals for Range A.
                </div>
              ) : (
                <MonthlyBarChart
                  labels={moSeriesA.labels}
                  values={moSeriesA.values}
                  title={`Range A (${normalizeRange(rangeA).from} → ${normalizeRange(rangeA).to})`}
                  valueFormatter={(v)=>`₱ ${fmt(v)}`}
                />
              )}
            </Section>
          )}

          {/* Receipts Matrix — by Month (exportable) */}
          {(toolView === "receipts_matrix" || toolView === "all") && (
            <Section title={`Receipts Matrix — by Month (${domain.toUpperCase()})`}>
              <ReceiptsMatrix
                months={monthsA}
                rows={receiptsMatrixA.rows}
                colTotals={receiptsMatrixA.colTotals}
                grandTotal={receiptsMatrixA.grandTotal}
                format={(n)=>fmt(n)}
                exportBaseName="receipts_matrix"
                exportSuffix={`${normalizeRange(rangeA).from}_to_${normalizeRange(rangeA).to}`}
              />
              <div style={{ fontSize:11, color:"#6b7280", marginTop:6 }}>
                Tip: Set <b>Domain = Revenue</b> and select categories (e.g., Mass Collections) to mirror your church receipts view.
              </div>
            </Section>
          )}

          {/* Period rework */}
          <Section title="Defects — Reopened / Reclosed Months">
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse" }}>
                <thead>
                  <tr>{["Month","Defect?","Note"].map((h)=> <th key={h} style={{ textAlign:"left", padding:8, borderBottom:"1px solid #e5e7eb", fontSize:12 }}>{h}</th>)}</tr>
                </thead>
                <tbody>
                  {(() => {
                    const A = normalizeRange(rangeA);
                    const monthsA = monthsCovered(parseISODate(A.from), parseISODate(A.to));
                    const monthsB = effRangeB ? monthsCovered(parseISODate(effRangeB.from), parseISODate(effRangeB.to)) : [];
                    const M = Array.from(new Set([...monthsA, ...monthsB])).sort();
                    if (M.length === 0) return <tr><td colSpan={3} style={{ padding:8, fontSize:12, color:"#6b7280" }}>No months found in selection.</td></tr>;
                    return M.map((m)=>(
                      <tr key={m}>
                        <td style={{ padding:8, borderBottom:"1px solid #f3f4f6" }}>{m}</td>
                        <td style={{ padding:8, borderBottom:"1px solid #f3f4f6" }}>{reopenedMonths.has(m) ? "Yes" : "No"}</td>
                        <td style={{ padding:8, borderBottom:"1px solid #f3f4f6" }}>{reopenedMonths.get(m) || "—"}</td>
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
          </Section>

          <Section title="Notes">
            <ul style={{ margin:0, paddingLeft:18, fontSize:12, color:"#6b7280" }}>
              <li>Expense = debit − credit; Revenue = credit − debit. Domain and account filters come from <code>/gl/accounts</code>.</li>
              <li>Units are entries with at least one included line. Defects: unposted &gt; SLA days + reversal entries (toggleable).</li>
              <li>Sigma uses long‑term convention: <code>σ = Φ⁻¹(yield) + 1.5</code>. Period rework shows from <code>/gl/locks/status</code>.</li>
              <li>p‑Chart uses variable‑n limits: <code>UCL/LCL_t = p̄ ± 3√[p̄(1−p̄)/n_t]</code>. Reopened months are not included in p.</li>
              <li>XmR uses n=2 constants: <code>X UCL/LCL = X̄ ± 2.66·MR̄</code>; <code>MR UCL = 3.267·MR̄</code>, <code>MR LCL = 0</code>.</li>
              <li>Pareto (Account): bars show absolute magnitudes from signed totals; line is cumulative share of total absolute.</li>
              <li>Configure <code>NEXT_PUBLIC_API_BASE</code> and optional <code>NEXT_PUBLIC_API_KEY</code>. The Journal API accepts <code>date_from</code>, <code>date_to</code>, <code>limit</code>, and <code>offset</code>.</li>
            </ul>
          </Section>
        </>
      )}
    </main>
  );
}
