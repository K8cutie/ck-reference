"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const DISPLAY_TZ = "Asia/Manila";

type SacData = Record<string, any>;
type CanonSac = "BAPTISM" | "CONFIRMATION" | "MARRIAGE" | "FUNERAL" | "FIRST_COMMUNION";

const THEME: Record<CanonSac, { label: string; ring: string; bg: string; text: string; icon: string }> = {
  BAPTISM:          { label: "Baptism",         ring:"#1d4ed8", bg:"#dbeafe", text:"#1e3a8a", icon:"🕊️" },
  CONFIRMATION:     { label: "Confirmation",    ring:"#d97706", bg:"#ffedd5", text:"#7c2d12", icon:"🔥" },
  MARRIAGE:         { label: "Marriage",        ring:"#be185d", bg:"#fce7f3", text:"#831843", icon:"💍" },
  FUNERAL:          { label: "Funeral",         ring:"#374151", bg:"#e5e7eb", text:"#111827", icon:"✝️" },
  FIRST_COMMUNION:  { label: "First Communion", ring:"#047857", bg:"#d1fae5", text:"#065f46", icon:"🍞" },
};

function canonicalize(raw?: string | null): CanonSac | null {
  const s = (raw ?? "").toUpperCase().replace(/\s+/g, "_").trim();
  if (!s) return null;
  if (s === "DEATH") return "FUNERAL";
  const list: CanonSac[] = ["BAPTISM","CONFIRMATION","MARRIAGE","FUNERAL","FIRST_COMMUNION"];
  return (list as string[]).includes(s) ? (s as CanonSac) : null;
}
function inferType(d: SacData): CanonSac {
  const direct = canonicalize(d?.type ?? d?.sacrament_type ?? d?.meta?.sacrament_type ?? d?.kind ?? d?.category);
  if (direct) return direct;
  const t = (d?.title ?? d?.name ?? "").toLowerCase();
  if (t.includes("baptism")) return "BAPTISM";
  if (t.includes("confirmation")) return "CONFIRMATION";
  if (t.includes("wedding") || t.includes("marriage")) return "MARRIAGE";
  if (t.includes("funeral") || t.includes("burial") || t.includes("death")) return "FUNERAL";
  if (t.includes("first communion") || t.includes("1st communion") || t.includes("holy communion")) return "FIRST_COMMUNION";
  return "BAPTISM";
}

function fmtDate(d?: string) {
  if (!d) return "";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "full", timeZone: DISPLAY_TZ }).format(new Date(d));
}
function fmtRange(start?: string, end?: string, allDay?: boolean) {
  if (!start) return "";
  const s = new Date(start); const e = end ? new Date(end) : null;
  const dFmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: DISPLAY_TZ });
  const tFmt = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: DISPLAY_TZ });
  if (allDay) return `All day — ${dFmt.format(s)}`;
  if (!e) return `${dFmt.format(s)} · ${tFmt.format(s)}`;
  const sameDay = new Intl.DateTimeFormat("en-CA", { timeZone: DISPLAY_TZ, year:"numeric", month:"2-digit", day:"2-digit" }).format(s) ===
                  new Intl.DateTimeFormat("en-CA", { timeZone: DISPLAY_TZ, year:"numeric", month:"2-digit", day:"2-digit" }).format(e);
  return sameDay
    ? `${dFmt.format(s)} · ${tFmt.format(s)}–${tFmt.format(e)}`
    : `${dFmt.format(s)} ${tFmt.format(s)} → ${dFmt.format(e)} ${tFmt.format(e)}`;
}
function pick(...vals: any[]) { for (const v of vals) { const s = (v ?? "").toString().trim(); if (s) return s; } return ""; }

function useSacrament() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<SacData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        setLoading(true); setError(null);
        const res = await fetch(`${API_BASE}/sacraments/${id}`, { cache: "no-store" });
        if (!res.ok) throw new Error(`Failed to load (HTTP ${res.status})`);
        const json = await res.json();
        if (!cancel) setData(json);
      } catch (e: any) {
        if (!cancel) setError(e?.message ?? "Failed to load");
      } finally { if (!cancel) setLoading(false); }
    })();
    return () => { cancel = true; };
  }, []);

  return { id: (useParams() as any).id as string, data, loading, error };
}

export default function SacramentDetail() {
  const router = useRouter();
  const { id, data, loading, error } = useSacrament();

  // derive theme + common fields
  const sac = useMemo(() => inferType(data ?? {}), [data]);
  const theme = THEME[sac];
  const title = pick(data?.title, data?.person_name, data?.child_name, data?.couple_name, data?.name, `${theme.label} #${id}`);
  const start_at = pick(data?.start_at, data?.start, data?.datetime, data?.date);
  const end_at   = pick(data?.end_at, data?.end);
  const allDay   = Boolean(data?.all_day ?? data?.allday);
  const when     = fmtRange(start_at, end_at, allDay);
  const dateOnly = fmtDate(start_at);
  const location = pick(data?.location, data?.church, data?.parish);
  const celebrant= pick(data?.celebrant, data?.officiant, data?.priest);
  const status   = pick(data?.status, data?.state, data?.stage);
  const notes    = pick(data?.notes, data?.description, data?.remarks, data?.memo);
  const calendarRef = pick(data?.external_ref, data?.calendar_ref, data?.meta?.calendar_ref);
  const hasCalRef = /^SAC-\d+$/i.test(calendarRef);

  // people (best-effort)
  const parents = (data?.parents && (Array.isArray(data.parents) ? data.parents : [])) ||
    [pick(data?.father, data?.parents?.father, data?.parents?.father_name), pick(data?.mother, data?.parents?.mother, data?.parents?.mother_name)].filter(Boolean);
  const sponsors = (data?.sponsors || data?.godparents || data?.ninongs || data?.ninangs || []) as any[];
  const attachments = (data?.files || data?.documents || data?.attachments || []) as any[];

  // actions
  function backToCalendar() { router.push("/calendar"); }
  function copyLink() { navigator.clipboard?.writeText(window.location.href); }
  function printPage() { window.print(); }
  function onEdit() { router.push(`/sacraments/${id}/edit`); }

  return (
    <div className="space-y-6">
      {/* HERO */}
      <section
        className="ck-hero p-6 md:p-8"
        style={{ ["--sac-ring" as any]: theme.ring, ["--sac-bg" as any]: theme.bg, ["--sac-text" as any]: theme.text }}
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <div className="h-12 w-12 grid place-items-center rounded-2xl text-xl text-white" style={{ background: theme.ring }}>
              {theme.icon}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="ck-pill">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: theme.ring }} />
                  {theme.label}
                </span>
                <span className="ck-badge">ID: {id}</span>
                {status && <span className="ck-badge">Status: {status}</span>}
                {hasCalRef && <span className="ck-badge">{calendarRef}</span>}
              </div>
              <h1 className="mt-2 text-2xl md:text-3xl font-semibold tracking-tight">{title}</h1>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-sm md:text-base text-gray-700">
                {when && <span>🕑 {when}</span>}
                {location && <span>📍 {location}</span>}
                {celebrant && <span>⛪ Officiant: {celebrant}</span>}
              </div>
            </div>
          </div>

          {/* sticky-feel action bar */}
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={onEdit} className="rounded-xl border px-3 py-1.5 text-sm hover:bg-gray-50">Edit</button>
            <button onClick={copyLink} className="rounded-xl border px-3 py-1.5 text-sm hover:bg-gray-50">Copy link</button>
            <button onClick={printPage} className="rounded-xl border px-3 py-1.5 text-sm hover:bg-gray-50">Print</button>
            <button
              onClick={backToCalendar}
              className="rounded-xl bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
            >
              View in Calendar
            </button>
          </div>
        </div>
      </section>

      {/* GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT: main */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview */}
          <section className="ck-card p-5">
            <h2 className="text-lg font-semibold mb-3">Overview</h2>
            <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-sm">
              {dateOnly && (<><dt className="text-gray-500">Date</dt><dd>{dateOnly}</dd></>)}
              {location && (<><dt className="text-gray-500">Location</dt><dd>{location}</dd></>)}
              {celebrant && (<><dt className="text-gray-500">Officiant</dt><dd>{celebrant}</dd></>)}
              {data?.record_number && (<><dt className="text-gray-500">Record No.</dt><dd>{data.record_number}</dd></>)}
              {data?.reference_code && (<><dt className="text-gray-500">Reference</dt><dd>{data.reference_code}</dd></>)}
            </dl>
          </section>

          {/* People */}
          {(title || parents.length || sponsors.length) && (
            <section className="ck-card p-5">
              <h2 className="text-lg font-semibold mb-3">People</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Primary</div>
                  <div className="rounded-xl border p-3 bg-white">{title}</div>
                </div>
                {parents.length > 0 && (
                  <div>
                    <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Parents</div>
                    <ul className="rounded-xl border p-3 bg-white space-y-1">
                      {parents.map((p: string, i: number) => <li key={i}>👪 {p}</li>)}
                    </ul>
                  </div>
                )}
                {sponsors.length > 0 && (
                  <div className="md:col-span-2">
                    <div className="text-xs uppercase tracking-wide text-gray-500 mb-1">Sponsors / Godparents</div>
                    <ul className="rounded-xl border p-3 bg-white grid sm:grid-cols-2 gap-2">
                      {sponsors.map((s: any, i: number) => (
                        <li key={i} className="truncate">🎉 {typeof s === "string" ? s : s?.name ?? JSON.stringify(s)}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Notes */}
          {notes && (
            <section className="ck-card p-5">
              <h2 className="text-lg font-semibold mb-3">Notes</h2>
              <div className="prose max-w-none whitespace-pre-wrap text-sm">{notes}</div>
            </section>
          )}

          {/* Attachments */}
          {attachments.length > 0 && (
            <section className="ck-card p-5">
              <h2 className="text-lg font-semibold mb-3">Attachments</h2>
              <ul className="space-y-2">
                {attachments.map((f: any, i: number) => {
                  const name = f?.name ?? f?.filename ?? `File ${i + 1}`;
                  const url = f?.url ?? f?.href ?? f?.download_url ?? "#";
                  return (
                    <li key={i} className="flex items-center justify-between rounded-xl border p-3 bg-white">
                      <span className="truncate">📎 {name}</span>
                      <a href={url} target="_blank" rel="noreferrer" className="rounded-lg border px-3 py-1 text-sm hover:bg-gray-50">Open</a>
                    </li>
                  );
                })}
              </ul>
            </section>
          )}
        </div>

        {/* RIGHT: quick info */}
        <aside className="space-y-6">
          <section className="ck-card p-5">
            <h3 className="text-sm font-semibold mb-3">Quick info</h3>
            <dl className="text-sm grid grid-cols-1 gap-2">
              <div className="flex items-start justify-between gap-4">
                <dt className="text-gray-500">Type</dt><dd className="text-right">{theme.label}</dd>
              </div>
              {status && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">Status</dt><dd className="text-right">{status}</dd>
                </div>
              )}
              {hasCalRef && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">Calendar Ref</dt><dd className="text-right">{calendarRef}</dd>
                </div>
              )}
              {data?.created_at && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">Created</dt><dd className="text-right">{fmtDate(data.created_at)}</dd>
                </div>
              )}
              {data?.updated_at && (
                <div className="flex items-start justify-between gap-4">
                  <dt className="text-gray-500">Updated</dt><dd className="text-right">{fmtDate(data.updated_at)}</dd>
                </div>
              )}
            </dl>
          </section>

          {/* Placeholder checklist */}
          <section className="ck-card p-5">
            <h3 className="text-sm font-semibold mb-3">Checklist</h3>
            <ul className="text-sm space-y-2">
              <li>□ Requirements reviewed</li>
              <li>□ Payment recorded</li>
              <li>□ Certificates prepared</li>
            </ul>
          </section>
        </aside>
      </div>

      {/* Blocking states */}
      {loading && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-white/50 backdrop-blur-sm">
          <div className="animate-pulse rounded-2xl border bg-white p-6 shadow-sm">Loading sacrament…</div>
        </div>
      )}
      {error && (
        <div className="ck-card p-6 text-red-600">{error}</div>
      )}
    </div>
  );
}
