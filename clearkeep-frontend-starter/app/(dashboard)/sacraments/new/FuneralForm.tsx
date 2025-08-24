"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

/**
 * Flow:
 * 1) Create Parishioner for the deceased.
 * 2) POST /sacraments with:
 *    - sacrament_type: "funeral"
 *    - details: { deceased, date_of_death, burial_site, time?, funeral_place?, wake_location? }
 *    (time is HH:mm Asia/Manila; optional fields are included if provided)
 * 3) If fee > 0, backend links a Transaction (ref SAC-{id}) and creates a 1-hour Calendar event at `time`.
 */
export default function FuneralForm() {
  const router = useRouter();

  const today = useMemo(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  // Deceased (creates Parishioner)
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [suffix, setSuffix] = useState("");

  // Funeral details
  const [serviceDate, setServiceDate] = useState<string>(today); // funeral/mass date
  const [time, setTime] = useState<string>("10:00"); // Asia/Manila, HH:mm (optional but used for calendar)
  const [funeralPlace, setFuneralPlace] = useState<string>("");  // optional
  const [burialSite, setBurialSite] = useState<string>("");      // REQUIRED by API
  const [wakeLocation, setWakeLocation] = useState<string>("");  // optional
  const [dateOfDeath, setDateOfDeath] = useState<string>("");    // REQUIRED by API (YYYY-MM-DD)
  const [fee, setFee] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function deceasedFullName() {
    const parts = [firstName.trim(), middleName.trim(), lastName.trim()].filter(Boolean);
    const base = parts.join(" ");
    return suffix.trim() ? `${base} ${suffix.trim()}` : base;
  }

  async function createParishioner() {
    const payload: Record<string, any> = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
    };
    if (middleName.trim()) payload.middle_name = middleName.trim();
    if (suffix.trim()) payload.suffix = suffix.trim();

    const r = await fetch(`${API_BASE}/parishioners/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error(await r.text());
    const j = await r.json();
    if (!j?.id) throw new Error("Parishioner created but no id returned.");
    return j.id as number;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!firstName.trim() || !lastName.trim()) {
      setError("Deceased person’s first and last name are required.");
      return;
    }
    if (!dateOfDeath) {
      setError("Date of death is required.");
      return;
    }
    if (!burialSite.trim()) {
      setError("Burial site is required.");
      return;
    }

    setSubmitting(true);
    try {
      const parishioner_id = await createParishioner();

      const feeNumber = parseFloat(fee);
      const details: Record<string, any> = {
        deceased: deceasedFullName(),
        date_of_death: dateOfDeath,       // ✅ required
        burial_site: burialSite.trim(),   // ✅ required
      };
      if (time) details.time = time; // optional but used by backend to schedule
      if (funeralPlace.trim()) details.funeral_place = funeralPlace.trim();
      if (wakeLocation.trim()) details.wake_location = wakeLocation.trim();

      const payload: Record<string, any> = {
        parishioner_id,
        date: serviceDate,                // YYYY-MM-DD (service/mass date)
        sacrament_type: "funeral",
        details,                          // ✅ top-level details
        ...(notes ? { notes } : {}),
        ...(Number.isFinite(feeNumber) && feeNumber > 0 ? { fee: feeNumber } : {}),
      };

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

      router.push(`/sacraments/${newId}`);
    } catch (err: any) {
      setError(err?.message ?? "Failed to create funeral record.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="ck-card p-6 space-y-6">
      <div className="h2">Deceased (creates Parishioner)</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="First name" value={firstName} onChange={setFirstName} required />
        <Field label="Middle name (optional)" value={middleName} onChange={setMiddleName} />
        <Field label="Last name" value={lastName} onChange={setLastName} required />
        <Field label="Suffix (optional)" value={suffix} onChange={setSuffix} placeholder="Sr., Jr., III" />
      </div>

      <div className="h2">Funeral details</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <label className="block">
          <span className="text-sm font-medium">Service date</span>
          <input
            type="date"
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={serviceDate}
            onChange={(e) => setServiceDate(e.target.value)}
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
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="text-sm font-medium">Funeral place (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={funeralPlace}
            onChange={(e) => setFuneralPlace(e.target.value)}
            placeholder="Parish Church / Chapel"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block">
          <span className="text-sm font-medium">Burial site</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={burialSite}
            onChange={(e) => setBurialSite(e.target.value)}
            placeholder="Cemetery / columbarium"
            required
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Wake location (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={wakeLocation}
            onChange={(e) => setWakeLocation(e.target.value)}
            placeholder="Family residence / funeral home"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Date of death</span>
          <input
            type="date"
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={dateOfDeath}
            onChange={(e) => setDateOfDeath(e.target.value)}
            required
          />
        </label>
      </div>

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
            placeholder="e.g. 1000"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Notes (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="celebrant, remarks, etc."
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-xl bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create funeral record"}
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
