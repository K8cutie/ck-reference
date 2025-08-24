"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import type {
  EventApi,
  EventInput,
  EventDropArg,
  EventResizeDoneArg,
  DateSelectArg,
  DateClickArg,
  EventContentArg,
} from "@fullcalendar/core";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const DISPLAY_TZ = "Asia/Manila";

// ---- API (expand=false) ----
type ApiEvent = {
  id: string;
  title: string;
  description?: string | null;
  location?: string | null;
  start?: string;
  end?: string | null;
  start_at?: string;
  end_at?: string | null;
  all_day?: boolean;
  timezone?: string | null;
  origin?: string | null;
  external_ref?: string | null;
  meta?: Record<string, any> | null; // -> sacrament_type (UPPERCASED)
  rrule?: string | null;
};

type CanonSacrament =
  | "BAPTISM"
  | "CONFIRMATION"
  | "MARRIAGE"
  | "FUNERAL"
  | "FIRST_COMMUNION";

const COLOR_MAP: Record<
  CanonSacrament,
  { bg: string; border: string; text: string; label: string; icon: string }
> = {
  BAPTISM:          { bg: "#3B82F6", border: "#1D4ED8", text: "#FFFFFF", label: "Baptism",         icon: "🕊️" },
  CONFIRMATION:     { bg: "#F59E0B", border: "#D97706", text: "#111827", label: "Confirmation",    icon: "🔥" },
  MARRIAGE:         { bg: "#EC4899", border: "#BE185D", text: "#FFFFFF", label: "Marriage",        icon: "💍" },
  FUNERAL:          { bg: "#6B7280", border: "#374151", text: "#FFFFFF", label: "Funeral",         icon: "✝️" },
  FIRST_COMMUNION:  { bg: "#10B981", border: "#047857", text: "#FFFFFF", label: "First Communion", icon: "🍞" },
};

function canonicalizeSacrament(raw: unknown): CanonSacrament | null {
  const s = String(raw ?? "").toUpperCase().trim();
  if (!s) return null;
  if (s === "DEATH") return "FUNERAL";
  if (s === "FIRST COMMUNION") return "FIRST_COMMUNION";
  if ((["BAPTISM","CONFIRMATION","MARRIAGE","FUNERAL","FIRST_COMMUNION"] as const).includes(s as any)) return s as CanonSacrament;
  return null;
}
function inferFromTitle(title?: string | null): CanonSacrament | null {
  const t = (title ?? "").toLowerCase();
  if (!t) return null;
  if (t.includes("baptism")) return "BAPTISM";
  if (t.includes("confirmation")) return "CONFIRMATION";
  if (t.includes("wedding") || t.includes("marriage")) return "MARRIAGE";
  if (t.includes("funeral") || t.includes("burial") || t.includes("death")) return "FUNERAL";
  if (t.includes("first communion") || t.includes("1st communion") || t.includes("holy communion")) return "FIRST_COMMUNION";
  return null;
}

function toEventInput(ev: ApiEvent): EventInput {
  const start = ev.start ?? ev.start_at ?? undefined;
  const end = ev.end ?? ev.end_at ?? undefined;
  const allDay = ev.all_day ?? false;

  const canon = canonicalizeSacrament(ev.meta?.sacrament_type) ?? inferFromTitle(ev.title);

  const input: EventInput = {
    id: String(ev.id),
    title: ev.title,
    start, end, allDay,
    extendedProps: {
      description: ev.description ?? undefined,
      notes: (ev as any).notes ?? undefined,
      location: ev.location ?? undefined,
      external_ref: ev.external_ref ?? undefined,
      sacramentType: canon ? COLOR_MAP[canon].label : undefined,
      sacramentKey: canon ?? undefined,
      rrule: ev.rrule ?? undefined,
    },
  };

  if (canon) {
    const { bg, border, text } = COLOR_MAP[canon];
    input.backgroundColor = bg;
    input.borderColor = border;
    input.textColor = text;
    (input as any).display = "block";
  }

  return input;
}

// ---------- Utils ----------
type TooltipState = {
  visible: boolean; x: number; y: number;
  title: string; timeLine: string; location?: string; notes?: string;
};
function formatYMD(d: Date, tz: string) {
  const y = new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric" }).format(d);
  const m = new Intl.DateTimeFormat("en-CA", { timeZone: tz, month: "2-digit" }).format(d);
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: tz, day: "2-digit" }).format(d);
  return `${y}-${m}-${day}`;
}
function formatTooltipTime(api: EventApi): string {
  const tz = DISPLAY_TZ;
  const start = api.start!, end = api.end ?? null;
  const dateFmt = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: tz });
  const timeFmt = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: tz });
  if (api.allDay) return `All day — ${dateFmt.format(start)}`;
  if (end && formatYMD(start, tz) === formatYMD(end, tz)) return `${dateFmt.format(start)}, ${timeFmt.format(start)} – ${timeFmt.format(end)}`;
  if (end) return `${dateFmt.format(start)} ${timeFmt.format(start)} → ${dateFmt.format(end)} ${timeFmt.format(end)}`;
  return `${dateFmt.format(start)}, ${timeFmt.format(start)}`;
}
function toIsoZ(d: Date | null | undefined): string | undefined { return d ? new Date(d.getTime()).toISOString() : undefined; }
function addHours(d: Date, h: number) { return new Date(d.getTime() + h * 3600 * 1000); }
function addDays(d: Date, days: number) { return new Date(d.getTime() + days * 86400 * 1000); }
function toLocalDateInputValue(d: Date) {
  const y = d.getFullYear(); const m = String(d.getMonth()+1).padStart(2,"0"); const day = String(d.getDate()).padStart(2,"0");
  return `${y}-${m}-${day}`;
}
function toLocalDateTimeInputValue(d: Date) {
  const y = d.getFullYear(); const m = String(d.getMonth()+1).padStart(2,"0"); const day = String(d.getDate()).padStart(2,"0");
  const hh = String(d.getHours()).padStart(2,"0"); const mm = String(d.getMinutes()).padStart(2,"0");
  return `${y}-${m}-${day}T${hh}:${mm}`;
}

// ---------- Quick Create ----------
type ComposerState = {
  visible: boolean; x: number; y: number; allDay: boolean; start: Date; end: Date;
  title: string; location?: string; notes?: string;
};

export default function CalendarPage() {
  const router = useRouter();
  const [events, setEvents] = useState<EventInput[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const lastRangeRef = useRef<string>("");
  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, y: 0, title: "", timeLine: "" });
  const [composer, setComposer] = useState<ComposerState | null>(null);
  const calRef = useRef<any>(null);
  const [title, setTitle] = useState<string>("");
  const [viewType, setViewType] = useState<"dayGridMonth" | "timeGridWeek" | "timeGridDay">("dayGridMonth");

  // Filters + search
  const [showGeneral, setShowGeneral] = useState(true);
  const [filter, setFilter] = useState<Record<CanonSacrament, boolean>>({
    BAPTISM: true, CONFIRMATION: true, MARRIAGE: true, FUNERAL: true, FIRST_COMMUNION: true,
  });
  const [q, setQ] = useState("");

  const visibleEvents = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return events.filter((e) => {
      // type filter
      const key = (e.extendedProps as any)?.sacramentKey as CanonSacrament | undefined;
      const allowed = key ? filter[key] : showGeneral;
      if (!allowed) return false;
      // search filter
      if (!needle) return true;
      const loc = ((e.extendedProps as any)?.location ?? "") + "";
      return (e.title?.toLowerCase().includes(needle) || loc.toLowerCase().includes(needle));
    });
  }, [events, filter, showGeneral, q]);

  async function fetchRange(start: Date, end: Date) {
    const key = `${start.toISOString()}|${end.toISOString()}`;
    if (key === lastRangeRef.current) return;
    lastRangeRef.current = key;

    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setLoading(true); setError(null);
    try {
      const url = new URL(`${API_BASE}/calendar/events`);
      url.searchParams.set("expand", "false");
      url.searchParams.set("start", start.toISOString());
      url.searchParams.set("end", end.toISOString());
      const res = await fetch(url.toString(), { cache: "no-store", signal: ac.signal });
      if (!res.ok) throw new Error(`Failed to load events (HTTP ${res.status})`);
      const data: ApiEvent[] = await res.json();
      setEvents(data.map(toEventInput));
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(e?.message ?? "Failed to load events");
    } finally {
      setLoading(false);
    }
  }
  function refetchCurrentRange() {
    const api = calRef.current?.getApi?.();
    if (!api) return;
    fetchRange(api.view.activeStart, api.view.activeEnd);
  }
  function onDatesSet(arg: { start: Date; end: Date; view: any }) {
    setTitle(arg.view?.title ?? "");
    setViewType(arg.view?.type ?? "dayGridMonth");
    fetchRange(arg.start, arg.end);
  }

  // navigation
  function api() { return calRef.current?.getApi?.(); }
  function prev() { api()?.prev(); }
  function next() { api()?.next(); }
  function today() { api()?.today(); }
  function changeView(v: "dayGridMonth" | "timeGridWeek" | "timeGridDay") {
    api()?.changeView(v); setViewType(v);
  }

  // interactions
  function onEventClick(info: any) {
    const ext = (info?.event?.extendedProps ?? {}) as { external_ref?: string };
    const m = String(ext.external_ref ?? "").match(/^SAC-(\d+)$/i);
    if (m?.[1]) { info.jsEvent?.preventDefault?.(); router.push(`/sacraments/${m[1]}`); }
  }
  async function updateSingleEvent(event: EventApi) {
    const payload = { start_at: toIsoZ(event.start)!, end_at: toIsoZ(event.end) ?? toIsoZ(event.start)!, all_day: !!event.allDay, timezone: DISPLAY_TZ };
    const res = await fetch(`${API_BASE}/calendar/events/${event.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Update failed (HTTP ${res.status})`);
  }
  async function editRecurringOccurrence(event: EventApi, instanceStartBeforeChange: Date) {
    const payload = { instance_start_at: toIsoZ(instanceStartBeforeChange)!, start_at: toIsoZ(event.start)!, end_at: toIsoZ(event.end) ?? toIsoZ(event.start)!, all_day: !!event.allDay, timezone: DISPLAY_TZ };
    const res = await fetch(`${API_BASE}/calendar/events/${event.id}/exceptions:edit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!res.ok) throw new Error(`Occurrence edit failed (HTTP ${res.status})`);
  }
  async function onEventDrop(arg: EventDropArg) {
    const hasRRule = Boolean((arg.event.extendedProps as any).rrule);
    const oldStart: Date = (arg as any).oldEvent?.start ?? new Date(arg.event.start!.getTime() - arg.delta.milliseconds);
    try { if (hasRRule) await editRecurringOccurrence(arg.event, oldStart); else await updateSingleEvent(arg.event); refetchCurrentRange(); }
    catch (e: any) { arg.revert(); setError(e?.message ?? "Failed to move event"); }
  }
  async function onEventResize(arg: EventResizeDoneArg) {
    const hasRRule = Boolean((arg.event.extendedProps as any).rrule);
    const oldStart: Date = (arg as any).prevEvent?.start ?? arg.event.start!;
    try { if (hasRRule) await editRecurringOccurrence(arg.event, oldStart); else await updateSingleEvent(arg.event); refetchCurrentRange(); }
    catch (e: any) { arg.revert(); setError(e?.message ?? "Failed to resize event"); }
  }
  async function onSelect(arg: DateSelectArg) {
    try {
      const defaultTitle = "";
      const title = window.prompt("Event title", defaultTitle);
      if (title == null) return;
      const payload = { title: title.trim() || "Untitled", start_at: toIsoZ(arg.start)!, end_at: toIsoZ(arg.end) ?? toIsoZ(arg.start)!, all_day: !!arg.allDay, timezone: DISPLAY_TZ };
      const res = await fetch(`${API_BASE}/calendar/events`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`Create failed (HTTP ${res.status})`);
      refetchCurrentRange();
    } catch (e: any) { setError(e?.message ?? "Failed to create event"); }
  }
  function onDateClick(arg: DateClickArg) {
    const isMonth = arg.view?.type?.startsWith("dayGrid");
    const start = new Date(arg.date.getTime());
    const end = isMonth ? addDays(start, 1) : addHours(start, 1);
    setComposer({ visible: true, x: arg.jsEvent.clientX + 12, y: arg.jsEvent.clientY + 12, allDay: !!arg.allDay || isMonth, start, end, title: "" });
  }
  function openComposerNow() {
    const now = new Date();
    setComposer({ visible: true, x: Math.max(window.innerWidth / 2 - 160, 24), y: 120, allDay: false, start: now, end: addHours(now, 1), title: "" });
  }
  function closeComposer() { setComposer(null); }
  async function createFromComposer(e?: React.FormEvent) {
    e?.preventDefault();
    if (!composer) return;
    try {
      const title = composer.title.trim() || "Untitled";
      let start_at = composer.start; let end_at = composer.end;
      if (composer.allDay) {
        const sameDay = toLocalDateInputValue(start_at) === toLocalDateInputValue(end_at);
        if (sameDay) end_at = addDays(start_at, 1);
      }
      const payload = {
        title, start_at: toIsoZ(start_at)!, end_at: toIsoZ(end_at)!, all_day: composer.allDay, timezone: DISPLAY_TZ,
        ...(composer.location ? { location: composer.location } : {}),
        ...(composer.notes ? { description: composer.notes } : {}),
      };
      const res = await fetch(`${API_BASE}/calendar/events`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`Create failed (HTTP ${res.status})`);
      closeComposer(); refetchCurrentRange();
    } catch (err: any) { setError(err?.message ?? "Failed to create event"); }
  }

  // tooltips
  function onEventMouseEnter(arg: { el: HTMLElement; event: EventApi; jsEvent: MouseEvent }) {
    const ext = (arg.event.extendedProps ?? {}) as { description?: string; notes?: string; location?: string; };
    const timeLine = formatTooltipTime(arg.event); const title = arg.event.title ?? "";
    const contentLines = [timeLine, ext.location ? `📍 ${ext.location}` : null, ext.description ? ext.description : ext.notes ? ext.notes : null].filter(Boolean) as string[];
    arg.el.setAttribute("title", [title, ...contentLines].join("\n"));
    setTooltip({ visible: true, x: arg.jsEvent.clientX + 12, y: arg.jsEvent.clientY + 12, title, timeLine, location: ext.location, notes: ext.description ?? ext.notes });
  }
  function onEventMouseLeave() { setTooltip((t) => ({ ...t, visible: false })); }

  // event renderer (BIG visual change)
  function renderEventContent(arg: EventContentArg) {
    const key = (arg.event.extendedProps as any)?.sacramentKey as CanonSacrament | undefined;
    const meta = key ? COLOR_MAP[key] : null;
    const icon = meta?.icon ?? "🗓️";
    const loc = (arg.event.extendedProps as any)?.location as string | undefined;
    const lineTop = arg.timeText ? arg.timeText + (loc ? ` · ${loc}` : "") : (loc ? `All day · ${loc}` : "All day");

    return (
      <div className="ck-event">
        <span className="ck-event-icon" aria-hidden>{icon}</span>
        <div className="ck-event-main">
          <div className="ck-event-top">{lineTop}</div>
          <div className="ck-event-title">{arg.event.title}</div>
        </div>
      </div>
    );
  }

  // filter helpers
  function setAllFilters(val: boolean) {
    setFilter({ BAPTISM: val, CONFIRMATION: val, MARRIAGE: val, FUNERAL: val, FIRST_COMMUNION: val });
  }
  function toggleFilter(key: CanonSacrament) { setFilter((f) => ({ ...f, [key]: !f[key] })); }
  const chips = (Object.keys(COLOR_MAP) as CanonSacrament[]).map((k) => ({ key: k, ...COLOR_MAP[k] }));

  return (
    <div className="relative space-y-4">
      {/* Gradient header (sticky) */}
      <div className="sticky top-0 z-30 -mx-4 mb-2 bg-gradient-to-r from-blue-50 via-emerald-50 to-pink-50 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/50">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <button onClick={prev} className="btn-nav">←</button>
            <button onClick={today} className="btn-nav">today</button>
            <button onClick={next} className="btn-nav">→</button>
            <div className="ml-2 text-xl font-semibold tracking-tight">{title}</div>
          </div>

          <div className="flex items-center gap-2">
            <div className="inline-flex rounded-xl border p-1 bg-white">
              <button onClick={() => changeView("dayGridMonth")} className={`seg ${viewType === "dayGridMonth" ? "seg-active" : ""}`}>month</button>
              <button onClick={() => changeView("timeGridWeek")}  className={`seg ${viewType === "timeGridWeek"  ? "seg-active" : ""}`}>week</button>
              <button onClick={() => changeView("timeGridDay")}   className={`seg ${viewType === "timeGridDay"   ? "seg-active" : ""}`}>day</button>
            </div>

            <div className="hidden md:block w-56">
              <input
                type="text"
                placeholder="Search title or location…"
                className="w-full rounded-xl border px-3 py-1.5 text-sm outline-none focus:ring"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>

            <button onClick={openComposerNow} className="rounded-xl bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
              + New
            </button>
          </div>
        </div>
      </div>

      {/* Filters row */}
      <div className="flex flex-wrap items-center gap-2">
        {chips.map((c) => (
          <button
            key={c.key}
            onClick={() => toggleFilter(c.key)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition ${filter[c.key] ? "" : "opacity-40"}`}
            style={{ backgroundColor: c.bg, color: c.text, borderColor: c.border }}
            title={c.label}
          >
            <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: c.text }} />
            {c.icon} {c.label}
          </button>
        ))}
        <span className="mx-1 h-5 w-px bg-gray-300" />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showGeneral} onChange={(e) => setShowGeneral(e.target.checked)} />
          Show general events
        </label>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setAllFilters(true)} className="rounded-xl border px-3 py-1 text-sm hover:bg-gray-50" title="Show all">All</button>
          <button onClick={() => setAllFilters(false)} className="rounded-xl border px-3 py-1 text-sm hover:bg-gray-50" title="Hide all">None</button>
        </div>
      </div>

      {/* Notices */}
      {loading && <div className="text-sm text-gray-500">Loading events…</div>}
      {error && <div className="text-sm text-red-600">Error: {error}</div>}
      {!loading && visibleEvents.length === 0 && (
        <div className="rounded-xl border border-dashed p-6 text-center text-sm text-gray-500">
          No events in this range.
        </div>
      )}

      {/* Calendar */}
      <div className="rounded-2xl border border-gray-200 p-2 shadow-sm">
        <FullCalendar
          ref={calRef}
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          headerToolbar={false}
          height="auto"
          timeZone={DISPLAY_TZ}
          firstDay={0}
          navLinks
          nowIndicator
          weekNumbers={false}
          slotLabelFormat={{ hour: "numeric", minute: "2-digit", hour12: true }}
          eventTimeFormat={{ hour: "2-digit", minute: "2-digit", hour12: true }}
          dayMaxEventRows={3}
          events={visibleEvents}
          datesSet={onDatesSet}
          eventClick={onEventClick}
          editable
          selectable
          selectMirror
          eventStartEditable
          eventDurationEditable
          select={onSelect}
          eventDrop={onEventDrop}
          eventResize={onEventResize}
          eventMouseEnter={onEventMouseEnter}
          eventMouseLeave={onEventMouseLeave}
          dateClick={onDateClick}
          eventContent={renderEventContent}   // <<< custom pill renderer
        />
      </div>

      {/* Floating Action Button */}
      <button
        className="fixed bottom-6 right-6 z-40 rounded-full bg-blue-600 p-4 text-white shadow-lg hover:bg-blue-700"
        onClick={openComposerNow}
        aria-label="Create new schedule"
      >
        +
      </button>

      {/* Overlay tooltip */}
      {tooltip.visible && (
        <div
          className="fixed z-50 max-w-xs rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm shadow-lg pointer-events-none"
          style={{ top: tooltip.y, left: tooltip.x }}
        >
          <div className="font-medium">{tooltip.title}</div>
          <div className="text-gray-600">{tooltip.timeLine}</div>
          {tooltip.location && <div className="mt-1 text-gray-700"><span className="mr-1">📍</span>{tooltip.location}</div>}
          {tooltip.notes && <div className="mt-1 text-gray-700 whitespace-pre-wrap">{tooltip.notes}</div>}
        </div>
      )}

      {/* Quick Create popover */}
      {composer?.visible && (
        <>
          <div className="fixed inset-0 z-40" onClick={closeComposer} aria-hidden />
          <form
            onSubmit={createFromComposer}
            className="fixed z-50 w-[320px] rounded-2xl border border-gray-200 bg-white p-4 shadow-xl"
            style={{ top: composer.y, left: composer.x }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 text-sm font-semibold">New schedule</div>
            <input
              autoFocus
              type="text"
              placeholder="Title"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring"
              value={composer.title}
              onChange={(e) => setComposer({ ...composer, title: e.target.value })}
            />

            <label className="mt-3 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={composer.allDay}
                onChange={(e) =>
                  setComposer({
                    ...composer,
                    allDay: e.target.checked,
                    start: e.target.checked
                      ? new Date(composer.start.getFullYear(), composer.start.getMonth(), composer.start.getDate(), 0, 0, 0)
                      : composer.start,
                    end: e.target.checked
                      ? new Date(composer.start.getFullYear(), composer.start.getMonth(), composer.start.getDate(), 0, 0, 0)
                      : composer.end,
                  })
                }
              />
              All-day
            </label>

            {composer.allDay ? (
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-gray-600">Start date</label>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm"
                    value={toLocalDateInputValue(composer.start)}
                    onChange={(e) => setComposer({ ...composer, start: new Date(e.target.value + "T00:00") })}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600">End date</label>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm"
                    value={toLocalDateInputValue(composer.end)}
                    onChange={(e) => setComposer({ ...composer, end: new Date(e.target.value + "T00:00") })}
                  />
                </div>
              </div>
            ) : (
              <div className="mt-2 grid grid-cols-1 gap-2">
                <div>
                  <label className="block text-xs text-gray-600">Start</label>
                  <input
                    type="datetime-local"
                    className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm"
                    value={toLocalDateTimeInputValue(composer.start)}
                    onChange={(e) => {
                      const d = new Date(e.target.value);
                      const dur = composer.end.getTime() - composer.start.getTime();
                      setComposer({ ...composer, start: d, end: new Date(d.getTime() + Math.max(dur, 0)) });
                    }}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600">End</label>
                  <input
                    type="datetime-local"
                    className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm"
                    value={toLocalDateTimeInputValue(composer.end)}
                    onChange={(e) => setComposer({ ...composer, end: new Date(e.target.value) })}
                  />
                </div>
              </div>
            )}

            <div className="mt-2 grid grid-cols-1 gap-2">
              <div>
                <label className="block text-xs text-gray-600">Location (optional)</label>
                <input
                  type="text"
                  className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm"
                  value={composer.location ?? ""}
                  onChange={(e) => setComposer({ ...composer, location: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600">Notes (optional)</label>
                <textarea
                  className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm"
                  rows={3}
                  value={composer.notes ?? ""}
                  onChange={(e) => setComposer({ ...composer, notes: e.target.value })}
                />
              </div>
            </div>

            <div className="mt-3 flex items-center justify-end gap-2">
              <button type="button" className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm" onClick={closeComposer}>Cancel</button>
              <button type="submit" className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">Save</button>
            </div>
          </form>
        </>
      )}

      {/* Global theme polish */}
      <style jsx global>{`
        .btn-nav { border: 1px solid #e5e7eb; padding: 6px 12px; border-radius: 12px; font-size: 0.875rem; background: white; }
        .btn-nav:hover { background: #f9fafb; }
        .seg { padding: 6px 12px; border-radius: 10px; font-size: 0.875rem; }
        .seg-active { background: #111827; color: white; }

        :root {
          --fc-border-color: #e5e7eb;
          --fc-page-bg-color: transparent;
          --fc-neutral-bg-color: #fafafa;
          --fc-today-bg-color: #fef3c7; /* amber-100 */
          --fc-now-indicator-color: #ef4444;
        }
        /* Headers */
        .fc .fc-col-header-cell { background: #f3f4f6; font-weight: 600; }
        .fc .fc-col-header-cell-cushion { padding: 10px 0; }

        /* Month cells */
        .fc .fc-daygrid-day { transition: background-color .15s ease; }
        .fc .fc-daygrid-day:hover { background: #f8fafc; }
        .fc .fc-daygrid-day-number { padding: 6px 10px; border-radius: 9999px; font-weight: 600; }
        .fc .fc-daygrid-day.fc-day-today .fc-daygrid-day-number { background: #111827; color: white; }
        .fc .fc-day-sat, .fc .fc-day-sun { background: #fbfbfb; } /* weekend shading */

        /* Event pill (custom) */
        .ck-event { display: flex; gap: 8px; align-items: flex-start; padding: 6px 8px; }
        .ck-event-icon { font-size: 0.95rem; line-height: 1; }
        .ck-event-main { display: grid; gap: 2px; min-width: 0; }
        .ck-event-top { font-size: 0.72rem; opacity: 0.9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .ck-event-title { font-weight: 600; font-size: 0.85rem; line-height: 1.1; overflow: hidden; text-overflow: ellipsis; }

        /* FullCalendar events */
        .fc .fc-event { border-radius: 12px !important; border-width: 1px !important; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
        .fc .fc-daygrid-more-link { border-radius: 8px; padding: 0 6px; }
        .fc .fc-popover { border-radius: 12px; }

        /* Time grid tweaks */
        .fc .fc-timegrid-axis-cushion { font-size: 0.75rem; }
        .fc .fc-timegrid-slot { height: 2.25rem; }
        .fc .fc-timegrid .fc-now-indicator-line { border-top-width: 2px; }

        /* Dark mode */
        @media (prefers-color-scheme: dark) {
          :root {
            --fc-border-color: #374151;
            --fc-neutral-bg-color: #0b0b0c;
            --fc-today-bg-color: #1f2937;
          }
          .btn-nav, .seg { background: #111827; color: #e5e7eb; border-color: #374151; }
          .btn-nav:hover { background: #0f172a; }
          .seg-active { background: #e5e7eb; color: #111827; }
          .fc .fc-col-header-cell { background: #111827; color: #e5e7eb; }
          .fc .fc-daygrid-day:hover { background: #0b1320; }
          .fc .fc-day-sat, .fc .fc-day-sun { background: #0b0b0c; }
          .fc .fc-event { box-shadow: 0 1px 2px rgba(0,0,0,.4); }
        }
      `}</style>
    </div>
  );
}
