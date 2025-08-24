"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const DISPLAY_TZ = "Asia/Manila";

type Sac =
  | "BAPTISM"
  | "CONFIRMATION"
  | "MARRIAGE"
  | "FUNERAL"
  | "FIRST_COMMUNION";

type Theme = { label: string; ring: string; bg: string; text: string; icon: string };

const THEME: Record<Sac, Theme> = {
  BAPTISM: { label: "Baptism", ring: "#1d4ed8", bg: "#dbeafe", text: "#1e3a8a", icon: "🕊️" },
  CONFIRMATION: { label: "Confirmation", ring: "#d97706", bg: "#ffedd5", text: "#7c2d12", icon: "🔥" },
  MARRIAGE: { label: "Marriage", ring: "#be185d", bg: "#fce7f3", text: "#831843", icon: "💍" },
  FUNERAL: { label: "Funeral", ring: "#374151", bg: "#e5e7eb", text: "#111827", icon: "✝️" },
  FIRST_COMMUNION: { label: "First Communion", ring: "#047857", bg: "#d1fae5", text: "#065f46", icon: "🍞" },
};

function toIsoZLocal(date: string, time: string) {
  const dt = new Date(`${date}T${time || "09:00"}:00`);
  return dt.toISOString();
}

export default function NewSacramentPage() {
  const router = useRouter();

  // Appearance
  const [dim, setDim] = useState<boolean>(true); // start Dim by default

  // type
  const [type, setType] = useState<Sac>("BAPTISM");
  const theme = THEME[type];

  // person / couple
  const [first, setFirst] = useState("");
  const [middle, setMiddle] = useState("");
  const [last, setLast] = useState("");
  const [suffix, setSuffix] = useState("");

  const [brideFirst, setBrideFirst] = useState("");
  const [brideLast, setBrideLast] = useState("");
  const [groomFirst, setGroomFirst] = useState("");
  const [groomLast, setGroomLast] = useState("");

  // details
  const [date, setDate] = useState("");
  const [time, setTime] = useState("10:00");
  const [location, setLocation] = useState("");
  const [fee, setFee] = useState("");
  const [notes, setNotes] = useState("");

  // parents/sponsors
  const [mother, setMother] = useState("");
  const [father, setFather] = useState("");
  const [godparentInput, setGodparentInput] = useState("");
  const [godparents, setGodparents] = useState<string[]>([]);

  // state
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function addGodparent() {
    const name = godparentInput.trim();
    if (!name) return;
    setGodparents((gp) => [...gp, name]);
    setGodparentInput("");
  }
  function removeGodparent(idx: number) {
    setGodparents((gp) => gp.filter((_, i) => i !== idx));
  }

  const titlePreview = useMemo(() => {
    if (type === "MARRIAGE") {
      const a = [brideFirst, brideLast].filter(Boolean).join(" ");
      const b = [groomFirst, groomLast].filter(Boolean).join(" ");
      return a || b ? `${a} & ${b}` : "—";
    }
    const name = [first, middle, last, suffix].filter(Boolean).join(" ").trim();
    return name || "—";
  }, [type, first, middle, last, suffix, brideFirst, brideLast, groomFirst, groomLast]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const payload: any = {
        type,
        title: titlePreview,
        location: location || undefined,
        notes: notes || undefined,
        details: { timezone: DISPLAY_TZ },
        meta: { sacrament_type: type },
      };

      if (type === "MARRIAGE") {
        payload.couple = {
          bride: { first_name: brideFirst, last_name: brideLast },
          groom: { first_name: groomFirst, last_name: groomLast },
        };
      } else {
        payload.person = {
          first_name: first,
          middle_name: middle || undefined,
          last_name: last,
          suffix: suffix || undefined,
          parents:
            mother || father
              ? { mother: mother || undefined, father: father || undefined }
              : undefined,
        };
      }

      if (date) {
        const startISO = toIsoZLocal(date, time);
        const endISO = new Date(new Date(startISO).getTime() + 60 * 60 * 1000).toISOString();
        payload.start_at = startISO;
        payload.end_at = endISO;
        payload.details.time = { date, time };
      }

      if (godparents.length) payload.godparents = godparents;

      // 1) Create record
      const sacRes = await fetch(`${API_BASE}/sacraments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!sacRes.ok) throw new Error(`Create failed (HTTP ${sacRes.status})`);
      const created = await sacRes.json();
      const newId = String(created?.id ?? created?.data?.id);

      // 2) Optional fee -> transaction
      const amount = Number(fee);
      if (!Number.isNaN(amount) && amount > 0) {
        try {
          await fetch(`${API_BASE}/transactions`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              amount,
              currency: "PHP",
              reference: `SAC-${newId}`,
              memo: `${theme.label} – ${titlePreview}`,
            }),
          });
        } catch { /* non-blocking */ }
      }

      // 3) Calendar: auto-create (1h) with external_ref
      if (date) {
        try {
          const startISO = toIsoZLocal(date, time);
          const endISO = new Date(new Date(startISO).getTime() + 60 * 60 * 1000).toISOString();
          await fetch(`${API_BASE}/calendar/events`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              title: `${theme.label}: ${titlePreview}`,
              start_at: startISO,
              end_at: endISO,
              timezone: DISPLAY_TZ,
              location: location || undefined,
              external_ref: `SAC-${newId}`,
              all_day: false,
              meta: { sacrament_type: type },
            }),
          });
        } catch { /* non-blocking */ }
      }

      // 4) Redirect
      router.push(`/sacraments/${newId}`);
    } catch (e: any) {
      setErr(e?.message ?? "Failed to create record");
      setBusy(false);
    }
  }

  // base utility classes
  const inputCls =
    "s-input w-full rounded-xl border border-gray-300 px-3 py-2 outline-none focus:ring focus:ring-blue-100";
  const labelCls = "block text-xs text-gray-500 mb-1";
  const btnCls = "rounded-xl border px-3 py-1.5 text-sm hover:bg-gray-50";
  const chipCls =
    "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm bg-gray-50";

  return (
    <div className={dim ? "ck-dim space-y-6" : "space-y-6"}>
      {/* HERO */}
      <section
        className="rounded-3xl border p-6 md:p-8 shadow-sm"
        style={{
          background: `linear-gradient(135deg, ${theme.bg} 0%, ${dim ? "#f8fafc" : "#ffffff"} 60%)`,
          borderColor: theme.ring,
        }}
      >
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-4">
            <div
              className="grid h-12 w-12 place-items-center rounded-2xl text-xl text-white"
              style={{ background: theme.ring }}
            >
              {theme.icon}
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-gray-500">
                New Sacrament
              </div>
              <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">
                {theme.label}
              </h1>
              <div className="mt-1 text-sm text-gray-700 flex flex-wrap items-center gap-3">
                {titlePreview !== "—" && <span>👤 {titlePreview}</span>}
                {date && (
                  <span>
                    🗓️ {date}
                    {time ? ` · ${time}` : ""} ({DISPLAY_TZ})
                  </span>
                )}
                {location && <span>📍 {location}</span>}
              </div>
            </div>
          </div>

          {/* Right side controls */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setDim((d) => !d)}
              className="rounded-xl border px-3 py-1.5 text-sm hover:bg-gray-50"
              title="Toggle appearance"
            >
              {dim ? "🌙 Dim" : "☀️ Light"}
            </button>
            <div className="hidden md:flex flex-wrap gap-2">
              {(Object.keys(THEME) as Sac[]).map((k) => {
                const t = THEME[k];
                const active = type === k;
                return (
                  <button
                    key={k}
                    onClick={() => setType(k)}
                    className={chipCls + (active ? "" : " opacity-60")}
                    style={{ backgroundColor: t.bg, color: t.text, borderColor: t.ring }}
                    title={t.label}
                  >
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: t.ring }} />
                    {t.icon} {t.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* GRID */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* LEFT: form */}
        <form onSubmit={handleSubmit} className="space-y-6 lg:col-span-2">
          {/* Person / Couple */}
          <section className="s-card rounded-2xl border p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">
              {type === "MARRIAGE" ? "Couple" : type === "FUNERAL" ? "Deceased" : "Person"} details
            </h2>

            {type === "MARRIAGE" ? (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border p-4 s-card">
                  <div className="mb-2 text-xs uppercase text-gray-500">Bride</div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className={inputCls} placeholder="First name" value={brideFirst} onChange={(e) => setBrideFirst(e.target.value)} />
                    <input className={inputCls} placeholder="Last name" value={brideLast} onChange={(e) => setBrideLast(e.target.value)} />
                  </div>
                </div>
                <div className="rounded-xl border p-4 s-card">
                  <div className="mb-2 text-xs uppercase text-gray-500">Groom</div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <input className={inputCls} placeholder="First name" value={groomFirst} onChange={(e) => setGroomFirst(e.target.value)} />
                    <input className={inputCls} placeholder="Last name" value={groomLast} onChange={(e) => setGroomLast(e.target.value)} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <input className={inputCls + " md:col-span-1"} placeholder="First name" value={first} onChange={(e) => setFirst(e.target.value)} />
                <input className={inputCls + " md:col-span-1"} placeholder="Middle (optional)" value={middle} onChange={(e) => setMiddle(e.target.value)} />
                <input className={inputCls + " md:col-span-1"} placeholder="Last name" value={last} onChange={(e) => setLast(e.target.value)} />
                <input className={inputCls + " md:col-span-1"} placeholder="Suffix (optional)" value={suffix} onChange={(e) => setSuffix(e.target.value)} />
              </div>
            )}
          </section>

          {/* Details */}
          <section className="s-card rounded-2xl border p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">{theme.label} details</h2>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div>
                <label className={labelCls}>Date</label>
                <input type="date" className={inputCls} value={date} onChange={(e) => setDate(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Time ({DISPLAY_TZ})</label>
                <input type="time" className={inputCls} value={time} onChange={(e) => setTime(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Location (optional)</label>
                <input className={inputCls} placeholder="e.g., Parish Church" value={location} onChange={(e) => setLocation(e.target.value)} />
              </div>
              <div>
                <label className={labelCls}>Fee (optional)</label>
                <input className={inputCls} inputMode="decimal" placeholder="e.g., 500" value={fee} onChange={(e) => setFee(e.target.value)} />
              </div>
            </div>

            {type !== "MARRIAGE" && (
              <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <label className={labelCls}>{type === "FUNERAL" ? "Next of Kin (optional)" : "Mother (full name)"}</label>
                  <input className={inputCls} placeholder={type === "FUNERAL" ? "Contact person" : "e.g., Maria Santos"} value={mother} onChange={(e) => setMother(e.target.value)} />
                </div>
                <div>
                  <label className={labelCls}>{type === "FUNERAL" ? "Contact no. (optional)" : "Father (full name)"}</label>
                  <input className={inputCls} placeholder={type === "FUNERAL" ? "09xx…" : "e.g., Jose Santos"} value={father} onChange={(e) => setFather(e.target.value)} />
                </div>
              </div>
            )}

            {(type === "BAPTISM" || type === "FIRST_COMMUNION" || type === "CONFIRMATION") && (
              <div className="mt-3">
                <label className={labelCls}>Godparents / Sponsors</label>
                <div className="flex gap-2">
                  <input
                    className={inputCls + " flex-1"}
                    placeholder="Type a name and press Add"
                    value={godparentInput}
                    onChange={(e) => setGodparentInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addGodparent(); } }}
                  />
                  <button type="button" className={btnCls} onClick={addGodparent}>Add</button>
                </div>
                {godparents.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {godparents.map((g, i) => (
                      <span key={i} className="inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm bg-gray-50">
                        {g}
                        <button type="button" className="ml-1 text-gray-500 hover:text-gray-700" onClick={() => removeGodparent(i)} aria-label="Remove sponsor">×</button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mt-3">
              <label className={labelCls}>Notes (optional)</label>
              <textarea rows={3} className={inputCls} placeholder="celebrant, batch, remarks…" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </div>
          </section>

          <div className="flex items-center justify-between">
            <a href="/dashboard" className="text-sm text-gray-500 hover:underline">← Back to dashboard</a>
            <button disabled={busy} className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
              {busy ? "Creating…" : `Create ${theme.label.toLowerCase()}`}
            </button>
          </div>

          {err && <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">{err}</div>}
        </form>

        {/* RIGHT: preview / connectivity */}
        <aside className="space-y-6">
          <section className="s-card rounded-2xl border p-5 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold">Preview</h3>
            <div className="rounded-xl border p-4 s-card">
              <div className="mb-1 text-xs uppercase tracking-wide text-gray-500">Title</div>
              <div className="text-lg font-semibold">{theme.label}: {titlePreview}</div>
              <div className="mt-2 space-y-1 text-sm text-gray-700">
                <div>🕑 {date ? `${date}${time ? ` · ${time}` : ""}` : "—"} ({DISPLAY_TZ})</div>
                <div>📍 {location || "—"}</div>
                {godparents.length > 0 && <div>🎉 Sponsors: {godparents.join(", ")}</div>}
              </div>
            </div>
          </section>

          <section className="s-card rounded-2xl border p-5 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold">Connectivity</h3>
            <ul className="space-y-1 text-sm text-gray-700">
              <li>App base: <code className="rounded bg-gray-100 px-1 py-0.5">{API_BASE}</code></li>
              <li>TZ: <code className="rounded bg-gray-100 px-1 py-0.5">{DISPLAY_TZ}</code></li>
            </ul>
            <ol className="mt-3 list-inside list-decimal space-y-1 text-sm text-gray-700">
              <li>Create the record.</li>
              <li>If Fee provided → create Transaction <code className="rounded bg-gray-100 px-1 py-0.5">ref SAC-{'{id}'}</code>.</li>
              <li>Auto-create a Calendar event (1h) tagged with <code className="rounded bg-gray-100 px-1 py-0.5">external_ref</code>.</li>
              <li>Redirect to detail page.</li>
            </ol>
          </section>
        </aside>
      </div>

      {/* Local page styles (no styled-jsx) */}
      <style>{`
        .ck-dim .s-card { background: #f8fafc; }
        .ck-dim .s-input { background: #f9fafb; }
      `}</style>
    </div>
  );
}
