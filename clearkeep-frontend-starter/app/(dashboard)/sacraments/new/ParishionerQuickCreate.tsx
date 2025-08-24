"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type CreatedParishioner = {
  id: string | number;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  suffix?: string | null;
  contact_number?: string | null;
};

export default function ParishionerQuickCreate(props: {
  onCreated: (p: { id: string | number; name: string }) => void;
}) {
  const { onCreated } = props;

  const [firstName, setFirstName]   = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName]     = useState("");
  const [suffix, setSuffix]         = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [okMsg, setOkMsg]           = useState<string | null>(null);

  function composeName(p: CreatedParishioner) {
    const parts = [
      p.first_name ?? firstName,
      p.middle_name?.trim(),
      p.last_name ?? lastName,
    ].filter(Boolean);
    return parts.join(" ") + (p.suffix ? ` ${p.suffix}` : "");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setOkMsg(null);

    if (!firstName.trim() || !lastName.trim()) {
      setError("First and last name are required.");
      return;
    }

    const payload: Record<string, any> = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      ...(middleName.trim() ? { middle_name: middleName.trim() } : {}),
      ...(suffix.trim() ? { suffix: suffix.trim() } : {}),
    };

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/parishioners/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }

      const data: CreatedParishioner = await res.json();
      const name = composeName(data);

      setOkMsg(`Created: ${name}`);
      onCreated({ id: data.id, name });

      // reset (keep success visible)
      setFirstName("");
      setMiddleName("");
      setLastName("");
      setSuffix("");
    } catch (err: any) {
      setError(err?.message ?? "Failed to create parishioner.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="ck-card p-6 space-y-4">
      <div className="h2">Parishioner (quick create)</div>
      <p className="muted">Use separate fields to reduce typos and improve search.</p>

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
            placeholder=""
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

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-xl bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "Creating…" : "Create parishioner"}
        </button>

        {okMsg && <span className="text-sm text-green-700">{okMsg}</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </form>
  );
}
