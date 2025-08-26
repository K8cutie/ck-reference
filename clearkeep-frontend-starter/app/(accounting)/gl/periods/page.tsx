"use client";

import React, { useEffect, useState } from "react";
// Use relative import to top-level /lib to avoid alias issues
import { apiGet, apiPost, setApiKey } from "../../../../lib/api";

type EquityAcct = { id: number; code: string; name: string };
type RangeResult = { period: string; ok: boolean; je_id?: number; error?: string };
type LocksRow = { period: string; is_locked: boolean; note: string | null; closed_ref: string; closed_je_id: number | null };

function monthStr(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function parseMonth(s: string): { y: number; m: number } {
  const [y, m] = s.split("-").map(Number);
  return { y, m };
}
function addMonths(s: string, delta: number) {
  let { y, m } = parseMonth(s);
  m += delta;
  while (m > 12) { y++; m -= 12; }
  while (m < 1)  { y--; m += 12; }
  return `${y}-${String(m).padStart(2, "0")}`;
}

// Local, SSR-safe accessor for optional API key (matches lib/api storage key)
const getSavedKey = () =>
  typeof window === "undefined" ? null : window.localStorage.getItem("ck_api_key");

export default function PeriodControlsPage() {
  // API key (optional; only used if RBAC_ENFORCE=true later)
  const [apiKey, setApiKeyState] = useState<string>(getSavedKey() ?? "");
  const onSaveKey = () => setApiKey(apiKey || null);

  // Equity list
  const [equity, setEquity] = useState<EquityAcct[]>([]);
  const [equityId, setEquityId] = useState<number | undefined>(undefined);

  // Single-period state
  const [period, setPeriod] = useState<string>(monthStr());
  const [note, setNote] = useState<string>("");

  // Range state
  const [rStart, setRStart] = useState<string>(addMonths(monthStr(), -1));
  const [rEnd, setREnd] = useState<string>(monthStr());
  const [rangeBusy, setRangeBusy] = useState(false);
  const [rangeOut, setRangeOut] = useState<RangeResult[] | null>(null);

  // Locks Status
  const [lsFrom, setLsFrom] = useState<string>(addMonths(monthStr(), -1));
  const [lsTo, setLsTo] = useState<string>(monthStr());
  const [locks, setLocks] = useState<LocksRow[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Load equity accounts on mount
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const rows = await apiGet<EquityAcct[]>("/gl/accounts?type=equity&limit=200&offset=0");
        if (!mounted) return;
        setEquity(rows);
        if (rows.length && equityId === undefined) setEquityId(rows[0].id);
      } catch (e: any) {
        setToast(`Failed to load equity accounts: ${e.message || e}`);
      }
    })();
    return () => { mounted = false; };
  }, []); // eslint-disable-line

  // Helpers
  const setBusyRun = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setToast(null);
    try {
      await fn();
      setToast(`${label}: OK`);
    } catch (e: any) {
      setToast(`${label}: ${e.message || e}`);
    } finally {
      setBusy(null);
    }
  };

  // Actions
  const doClose = () =>
    setBusyRun("Close", async () => {
      if (!equityId) throw new Error("Select an equity account");
      await apiPost(`/gl/close/${period}?equity_account_id=${equityId}${note ? `&note=${encodeURIComponent(note)}` : ""}`, {});
    });

  const doReopen = () =>
    setBusyRun("Reopen", async () => {
      await apiPost(`/gl/reopen/${period}${note ? `?note=${encodeURIComponent(note)}` : ""}`, {});
    });

  const doReclose = () =>
    setBusyRun("Reclose", async () => {
      const q = new URLSearchParams();
      if (equityId) q.set("equity_account_id", String(equityId));
      if (note) q.set("note", note);
      await apiPost(`/gl/reclose/${period}${q.toString() ? `?${q}` : ""}`, {});
    });

  const doRange = (kind: "close" | "reopen" | "reclose") =>
    setBusyRun(`${kind}-range`, async () => {
      setRangeBusy(true);
      setRangeOut(null);
      const path =
        kind === "close"
          ? `/gl/close-range/${rStart}/${rEnd}${equityId ? `?equity_account_id=${equityId}` : ""}${note ? `${equityId ? "&" : "?"}note=${encodeURIComponent(note)}` : ""}`
          : kind === "reopen"
          ? `/gl/reopen-range/${rStart}/${rEnd}${note ? `?note=${encodeURIComponent(note)}` : ""}`
          : `/gl/reclose-range/${rStart}/${rEnd}${equityId ? `?equity_account_id=${equityId}` : ""}${note ? `${equityId ? "&" : "?"}note=${encodeURIComponent(note)}` : ""}`;
      const out = await apiPost<{ results: RangeResult[] }>(path, {});
      setRangeOut(out.results || []);
      setRangeBusy(false);
    });

  const doLocksStatus = () =>
    setBusyRun("Locks status", async () => {
      const data = await apiGet<{ results: LocksRow[] }>(`/gl/locks/status?from=${lsFrom}&to=${lsTo}`);
      setLocks(data.results || []);
    });

  // UI bits
  const Badge: React.FC<{ ok: boolean }> = ({ ok }) => (
    <span
      style={{
        padding: "2px 8px",
        borderRadius: 8,
        fontSize: 12,
        background: ok ? "#DCFCE7" : "#FEE2E2",
        color: ok ? "#065F46" : "#991B1B",
        border: `1px solid ${ok ? "#86EFAC" : "#FCA5A5"}`,
      }}
    >
      {ok ? "Locked" : "Open"}
    </span>
  );

  const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
    <section style={{ border: "1px solid #eee", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
      <div style={{ marginTop: 12 }}>{children}</div>
    </section>
  );

  return (
    <main style={{ maxWidth: 980, margin: "24px auto", padding: "0 16px" }}>
      <h1 style={{ fontSize: 24, marginBottom: 8 }}>Period Controls</h1>
      <p style={{ color: "#666", marginTop: 0 }}>
        Manage monthly period state (close / reopen / reclose), run range operations, and view locks status.
      </p>

      {/* Dev-only convenience: store API key to localStorage (used only if RBAC is enforced later) */}
      <Section title="API Key (optional)">
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="text"
            placeholder="paste X-API-Key (optional)"
            value={apiKey}
            onChange={(e) => setApiKeyState(e.target.value)}
            style={{ flex: "1 1 320px", padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
          />
          <button onClick={onSaveKey} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #ddd" }}>
            Save
          </button>
        </div>
      </Section>

      <Section title="Single Period">
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label>
            <div>Month</div>
            <input
              type="month"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
            />
          </label>
          <label>
            <div>Equity Account</div>
            <select
              value={equityId ?? ""}
              onChange={(e) => setEquityId(Number(e.target.value))}
              style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
            >
              {equity.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.code} — {e.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <div>Note (optional)</div>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="reason or context"
              style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }}
            />
          </label>
        </div>

        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button disabled={!!busy} onClick={doClose} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Close
          </button>
          <button disabled={!!busy} onClick={doReopen} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Reopen
          </button>
          <button disabled={!!busy} onClick={doReclose} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Reclose
          </button>
          {busy && <span style={{ color: "#666" }}>Running: {busy}…</span>}
          {toast && <span style={{ marginLeft: 12 }}>{toast}</span>}
        </div>
      </Section>

      <Section title="Range Operations">
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label>
            <div>Start</div>
            <input type="month" value={rStart} onChange={(e) => setRStart(e.target.value)} style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }} />
          </label>
          <label>
            <div>End</div>
            <input type="month" value={rEnd} onChange={(e) => setREnd(e.target.value)} style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }} />
          </label>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button disabled={rangeBusy} onClick={() => doRange("close")} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Close-range
          </button>
          <button disabled={rangeBusy} onClick={() => doRange("reopen")} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Reopen-range
          </button>
          <button disabled={rangeBusy} onClick={() => doRange("reclose")} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Reclose-range
          </button>
        </div>
        {rangeOut && (
          <div style={{ marginTop: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>Period</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>Result</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>JE ID</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>Error</th>
                </tr>
              </thead>
              <tbody>
                {rangeOut.map((r) => (
                  <tr key={r.period}>
                    <td style={{ padding: 6 }}>{r.period}</td>
                    <td style={{ padding: 6 }}>{r.ok ? "OK" : "Error"}</td>
                    <td style={{ padding: 6 }}>{r.je_id ?? ""}</td>
                    <td style={{ padding: 6, color: r.error ? "#991B1B" : undefined }}>{r.error ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Locks Status">
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label>
            <div>From</div>
            <input type="month" value={lsFrom} onChange={(e) => setLsFrom(e.target.value)} style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }} />
          </label>
          <label>
            <div>To</div>
            <input type="month" value={lsTo} onChange={(e) => setLsTo(e.target.value)} style={{ width: "100%", padding: 8, border: "1px solid #ddd", borderRadius: 8 }} />
          </label>
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button onClick={doLocksStatus} style={{ padding: "8px 12px", borderRadius: 8 }}>
            Refresh
          </button>
        </div>
        {locks && (
          <div style={{ marginTop: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>Period</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>State</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>Note</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: 6 }}>Closing JE</th>
                </tr>
              </thead>
              <tbody>
                {locks.map((row) => (
                  <tr key={row.period}>
                    <td style={{ padding: 6 }}>{row.period}</td>
                    <td style={{ padding: 6 }}><Badge ok={row.is_locked} /></td>
                    <td style={{ padding: 6 }}>{row.note ?? ""}</td>
                    <td style={{ padding: 6 }}>{row.closed_je_id ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </main>
  );
}
