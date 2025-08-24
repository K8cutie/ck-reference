"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function BaptismForm() {
  const router = useRouter();

  // defaults
  const today = useMemo(() => {
    const d = new Date();
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }, []);

  // Child (creates Parishioner)
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [suffix, setSuffix] = useState("");

  // Baptism details
  const [date, setDate] = useState<string>(today);
  const [time, setTime] = useState<string>("10:00"); // sent as details.time
  const [fee, setFee] = useState<string>("");        // creates Linked Transaction when > 0
  const [mother, setMother] = useState("");
  const [father, setFather] = useState("");
  const [godParentsText, setGodParentsText] = useState("");
  const [notes, setNotes] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function composeChildName() {
    const parts = [firstName.trim(), middleName.trim(), lastName.trim()].filter(Boolean);
    const base = parts.join(" ");
    return suffix.trim() ? `${base} ${suffix.trim()}` : base;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!firstName.trim() || !lastName.trim()) {
      setError("Child's first and last name are required.");
      return;
    }
    if (!mother.trim() || !father.trim()) {
      setError("Mother and Father are required.");
      return;
    }

    const god_parents = godParentsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    setSubmitting(true);
    try {
      // 1) Create Parishioner (child)
      const parishionerPayload: Record<string, any> = {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        ...(middleName.trim() ? { middle_name: middleName.trim() } : {}),
        ...(suffix.trim() ? { suffix: suffix.trim() } : {}),
      };

      const pRes = await fetch(`${API_BASE}/parishioners/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parishionerPayload),
      });
      if (!pRes.ok) {
        const t = await pRes.text();
        throw new Error(t || `Parishioner create failed (${pRes.status})`);
      }
      const p = await pRes.json();
      const parishioner_id = p?.id;
      if (!parishioner_id) throw new Error("Parishioner created but no id returned.");

      // 2) Create Sacrament (baptism) using that ID
      const feeNumber = parseFloat(fee);
      const payload: Record<string, any> = {
        parishioner_id,
        date, // YYYY-MM-DD
        sacrament_type: "baptism",
        details: {
          child_name: composeChildName(),
          mother,
          father,
          god_parents,
          time, // <- backend expects details.time (HH:mm 24h)
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
          const t = await sRes.text();
          throw new Error(t || `Sacrament create failed (${sRes.status})`);
        }
      }
      const data = await sRes.json();
      const newId = data?.id ?? data?.sacrament?.id ?? data?.result?.id ?? null;
      if (!newId) throw new Error("Sacrament created but no id returned.");
      router.push(`/sacraments/${newId}`);
    } catch (err: any) {
      setError(err?.message ?? "Failed to create baptism.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="ck-card p-6 space-y-6">
      <div className="h2">Child (creates Parishioner)</div>
      <div className="grid gap-4 sm:grid-cols-4">
        <label className="block sm:col-span-1">
          <span className="text-sm font-medium">First name</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
          />
        </label>
        <label className="block sm:col-span-1">
          <span className="text-sm font-medium">Middle name (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={middleName}
            onChange={(e) => setMiddleName(e.target.value)}
          />
        </label>
        <label className="block sm:col-span-1">
          <span className="text-sm font-medium">Last name</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
          />
        </label>
        <label className="block sm:col-span-1">
          <span className="text-sm font-medium">Suffix (optional)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={suffix}
            onChange={(e) => setSuffix(e.target.value)}
            placeholder="Jr., Sr., III"
          />
        </label>
      </div>

      <div className="h2">Baptism details</div>
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
            placeholder="celebrant, batch, etc."
          />
        </label>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium">Mother (full name)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={mother}
            onChange={(e) => setMother(e.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Father (full name)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={father}
            onChange={(e) => setFather(e.target.value)}
            required
          />
        </label>
        <label className="block sm:col-span-2">
          <span className="text-sm font-medium">God parents (comma-separated)</span>
          <input
            className="mt-1 w-full rounded-xl border border-gray-300 px-3 py-2"
            value={godParentsText}
            onChange={(e) => setGodParentsText(e.target.value)}
            placeholder="e.g. Maria Santos, Jose Reyes"
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-xl bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create baptism"}
        </button>
        {error && <span className="text-sm text-red-600 break-all">{error}</span>}
      </div>
    </form>
  );
}
