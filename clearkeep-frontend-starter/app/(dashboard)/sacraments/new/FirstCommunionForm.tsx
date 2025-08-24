"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function FirstCommunionForm() {
  const router = useRouter();

  const today = useMemo(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  // Communicant (creates Parishioner)
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [suffix, setSuffix] = useState("");

  // Details
  const [date, setDate] = useState<string>(today);
  const [time, setTime] = useState<string>("10:00");
  const [church, setChurch] = useState("");
  const [classBatch, setClassBatch] = useState("");
  const [sponsorsText, setSponsorsText] = useState("");
  const [fee, setFee] = useState("");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fullName = () => {
    const parts = [firstName.trim(), middleName.trim(), lastName.trim()].filter(Boolean);
    const base = parts.join(" ");
    return suffix.trim() ? `${base} ${suffix.trim()}` : base;
  };

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
      setError("Communicant’s first and last name are required.");
      return;
    }

    const sponsor_names = sponsorsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      const parishioner_id = await createParishioner();
      const feeNumber = parseFloat(fee);

      const payload: Record<string, any> = {
        parishioner_id,
        date, // YYYY-MM-DD
        sacrament_type: "first_communion",
        details: {
          communicant: fullName(),
          time, // HH:mm Asia/Manila
          ...(church.trim() ? { church: church.trim() } : {}),
          ...(classBatch.trim() ? { class_batch: classBatch.trim() } : {}),
          ...(sponsor_names.length ? { sponsor_names } : {}),
        },
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
          throw new Error(await sRes.text());
        }
      }

      const data = await sRes.json();
      const newId = data?.id ?? data?.sacrament?.id ?? data?.result?.id ?? null;
      if (!newId) throw new Error("Sacrament created but no id returned.");
      router.push(`/sacraments/${newId}`);
    } catch (err: any) {
      setError(err?.message || "Failed to create First Communion.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="ck-card p-6 space-y-6">
      <div className="h2">Communicant (creates Parishioner)</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="First name" value={firstName} onChange={setFirstName} required />
        <Field label="Middle name (optional)" value={middleName} onChange={setMiddleName} />
        <Field label="Last name" value={lastName} onChange={setLastName} required />
        <Field label="Suffix (optional)" value={suffix} onChange={setSuffix} placeholder="Sr., Jr., III" />
      </div>

      <div className="h2">Details</div>
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
          <span className="text-sm font-medium">Church / Location (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={church}
            onChange={(e) => setChurch(e.target.value)}
            placeholder="Parish name / venue"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium">Class / Batch (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={classBatch}
            onChange={(e) => setClassBatch(e.target.value)}
            placeholder="e.g., 2025-Q3"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Sponsors (comma-separated, optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={sponsorsText}
            onChange={(e) => setSponsorsText(e.target.value)}
            placeholder="Juan Dela Cruz, Maria Santos"
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium">Fee (optional)</span>
          <input
            type="number"
            min="0"
            step="0.01"
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={fee}
            onChange={(e) => setFee(e.target.value)}
            placeholder="e.g., 300"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Notes (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes"
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-xl bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create First Communion"}
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
