"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * We create TWO parishioners (groom & bride).
 * For now we set the sacrament's primary parishioner_id = groom_id
 * and also store both IDs in details for reference:
 *   details.groom_parishioner_id / details.bride_parishioner_id
 * Calendar event uses details.time (HH:mm, Asia/Manila) for a 1-hour slot.
 */
export default function MarriageForm() {
  const router = useRouter();

  const today = useMemo(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  // Groom
  const [gFirst, setGFirst] = useState("");
  const [gMiddle, setGMiddle] = useState("");
  const [gLast, setGLast] = useState("");
  const [gSuffix, setGSuffix] = useState("");

  // Bride
  const [bFirst, setBFirst] = useState("");
  const [bMiddle, setBMiddle] = useState("");
  const [bLast, setBLast] = useState("");
  const [bSuffix, setBSuffix] = useState("");

  // Marriage
  const [date, setDate] = useState<string>(today);
  const [time, setTime] = useState<string>("10:00"); // Asia/Manila
  const [place, setPlace] = useState<string>("");
  const [witnessesText, setWitnessesText] = useState<string>("");
  const [fee, setFee] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function fullName(first: string, middle: string, last: string, suffix: string) {
    const parts = [first.trim(), middle.trim(), last.trim()].filter(Boolean);
    const base = parts.join(" ");
    return suffix.trim() ? `${base} ${suffix.trim()}` : base;
  }

  async function createParishioner(first: string, middle: string, last: string, suffix: string) {
    const payload: Record<string, any> = {
      first_name: first.trim(),
      last_name: last.trim(),
    };
    if (middle.trim()) payload.middle_name = middle.trim();
    if (suffix.trim()) payload.suffix = suffix.trim();

    const r = await fetch(`${API_BASE}/parishioners/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || `Parishioner create failed (${r.status})`);
    }
    const j = await r.json();
    if (!j?.id) throw new Error("Parishioner created but no id returned.");
    return j.id as number;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!gFirst.trim() || !gLast.trim() || !bFirst.trim() || !bLast.trim()) {
      setError("Groom and Bride first/last names are required.");
      return;
    }
    if (!place.trim()) {
      setError("Place of marriage is required.");
      return;
    }

    const witnesses = witnessesText
      .split(",")
      .map((w) => w.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      // 1) Parishioners
      const groomId = await createParishioner(gFirst, gMiddle, gLast, gSuffix);
      const brideId = await createParishioner(bFirst, bMiddle, bLast, bSuffix);

      // 2) Build details payload
      const groomName = fullName(gFirst, gMiddle, gLast, gSuffix);
      const brideName = fullName(bFirst, bMiddle, bLast, bSuffix);

      const feeNumber = parseFloat(fee);
      const payload: Record<string, any> = {
        parishioner_id: groomId, // primary
        date, // YYYY-MM-DD
        sacrament_type: "marriage",
        details: {
          groom: groomName,
          bride: brideName,
          place_of_marriage: place.trim(),
          witnesses,
          // extras we also store/use:
          time, // HH:mm for calendar
          groom_parishioner_id: groomId,
          bride_parishioner_id: brideId,
        },
        ...(notes ? { notes } : {}),
        ...(Number.isFinite(feeNumber) && feeNumber > 0 ? { fee: feeNumber } : {}),
      };

      // 3) Create sacrament
      const sRes = await fetch(`${API_BASE}/sacraments/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!sRes.ok) {
        const ct = sRes.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const j = await sRes.json();
          throw new Error(JSON.stringify(j));
        } else {
          const t = await sRes.text();
          throw new Error(t || `Sacrament create failed (${sRes.status})`);
        }
      }
      const data = await sRes.json();
      const newId = data?.id ?? data?.sacrament?.id ?? data?.result?.id ?? null;
      if (!newId) throw new Error("Sacrament created but no id returned.");

      // 4) Redirect
      router.push(`/sacraments/${newId}`);
    } catch (err: any) {
      setError(err?.message ?? "Failed to create marriage.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="ck-card p-6 space-y-6">
      <div className="h2">Groom (creates Parishioner)</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="First name" value={gFirst} onChange={setGFirst} required />
        <Field label="Middle name (optional)" value={gMiddle} onChange={setGMiddle} />
        <Field label="Last name" value={gLast} onChange={setGLast} required />
        <Field label="Suffix (optional)" value={gSuffix} onChange={setGSuffix} placeholder="Jr., Sr., III" />
      </div>

      <div className="h2">Bride (creates Parishioner)</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="First name" value={bFirst} onChange={setBFirst} required />
        <Field label="Middle name (optional)" value={bMiddle} onChange={setBMiddle} />
        <Field label="Last name" value={bLast} onChange={setBLast} required />
        <Field label="Suffix (optional)" value={bSuffix} onChange={setBSuffix} placeholder="Jr., Sr., III" />
      </div>

      <div className="h2">Marriage details</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <label className="block">
          <span className="text-sm font-medium">Date</span>
          <input
            type="date"
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Time (Asia/Manila)</span>
          <input
            type="time"
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            required
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="text-sm font-medium">Place of marriage</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={place}
            onChange={(e) => setPlace(e.target.value)}
            required
            placeholder="Parish church / chapel"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium">Witnesses (comma-separated)</span>
        <input
          className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
          value={witnessesText}
          onChange={(e) => setWitnessesText(e.target.value)}
          placeholder="e.g. Juan Dela Cruz, Maria Santos"
        />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium">Fee (optional)</span>
          <input
            type="number"
            step="0.01"
            min="0"
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={fee}
            onChange={(e) => setFee(e.target.value)}
            placeholder="e.g. 500"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Notes (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="remarks, celebrant, etc."
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-xl bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create marriage"}
        </button>
        {error && <span className="text-sm text-red-600 break-all">{error}</span>}
      </div>
    </form>
  );
}

function Field({
  label,
  value,
  onChange,
  required,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <input
        className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
      />
    </label>
  );
}
