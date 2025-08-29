'use client';

import React from 'react';
import { apiGet, apiPost, setApiKey } from '../../../lib/api';

type AnyRec = Record<string, any>;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

export default function PayrollPage() {
  // Only Runs & Payslips now
  const [activeTab, setActiveTab] = React.useState<'runs' | 'payslips'>('runs');

  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // API key
  const [apiKeyInput, setApiKeyInput] = React.useState('');
  function saveKey() {
    setApiKey(apiKeyInput || null);
    alert(apiKeyInput ? 'API key saved.' : 'API key cleared.');
  }

  // Period + Run
  const [periodForm, setPeriodForm] = React.useState({
    period_key: '',
    start_date: '',
    end_date: '',
    pay_date: '',
  });
  const [createdPeriod, setCreatedPeriod] = React.useState<AnyRec | null>(null);

  const [runForm, setRunForm] = React.useState({
    period_id: '',
    notes: '',
  });
  const [createdRun, setCreatedRun] = React.useState<AnyRec | null>(null);
  const [runSummary, setRunSummary] = React.useState<AnyRec | null>(null);

  // Payslips
  const [runIdForSlips, setRunIdForSlips] = React.useState('');
  const [payslips, setPayslips] = React.useState<AnyRec[] | null>(null);

  // UI helpers
  function SectionCard(props: { title: string; children: React.ReactNode }) {
    return (
      <div className="rounded-2xl border p-4 shadow-sm bg-white/5">
        <h2 className="text-xl font-semibold mb-3">{props.title}</h2>
        {props.children}
      </div>
    );
  }
  function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <label className="flex items-center gap-3 text-sm mb-2">
        <span className="w-36 opacity-70">{label}</span>
        <span className="flex-1">{children}</span>
      </label>
    );
  }
  function TabButton(props: { id: 'runs' | 'payslips'; label: string }) {
    const on = activeTab === props.id;
    return (
      <button
        onClick={() => setActiveTab(props.id)}
        className={`px-3 py-1 rounded-full border text-sm mr-2 ${on ? 'bg-white text-black' : 'bg-transparent'}`}
      >
        {props.label}
      </button>
    );
  }

  // Actions
  async function createPeriod() {
    setLoading(true); setError(null);
    try {
      const p = await apiPost('/payroll/periods', { ...periodForm });
      setCreatedPeriod(p);
      if (p?.id) setRunForm((f) => ({ ...f, period_id: p.id }));
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create period');
    } finally { setLoading(false); }
  }

  async function createRun() {
    setLoading(true); setError(null);
    try {
      const r = await apiPost('/payroll/runs', {
        period_id: runForm.period_id,
        notes: runForm.notes || undefined,
      });
      setCreatedRun(r);
      if (r?.id) setRunIdForSlips(r.id);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create run');
    } finally { setLoading(false); }
  }

  async function computeBasic() {
    if (!createdRun?.id) { setError('Create/select a run first.'); return; }
    setLoading(true); setError(null);
    try {
      await apiPost(`/payroll/runs/${encodeURIComponent(createdRun.id)}/compute-basic`, {});
      await loadSummary(createdRun.id);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to compute run');
    } finally { setLoading(false); }
  }

  async function loadSummary(runId?: string) {
    const id = runId || createdRun?.id;
    if (!id) return;
    setLoading(true); setError(null);
    try {
      const s = await apiGet(`/payroll/runs/${encodeURIComponent(id)}/summary`);
      setRunSummary(s);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load summary');
    } finally { setLoading(false); }
  }

  async function loadPayslips() {
    if (!runIdForSlips) return;
    setLoading(true); setError(null);
    try {
      const data = await apiGet(`/payroll/payslips?run_id=${encodeURIComponent(runIdForSlips)}`);
      setPayslips(Array.isArray(data) ? data : null);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load payslips');
    } finally { setLoading(false); }
  }

  // Render
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Payroll</h1>
        <div className="flex items-center gap-2">
          <input
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="X-API-Key…"
            className="rounded border px-3 py-1 text-sm bg-transparent"
          />
          <button onClick={saveKey} className="rounded bg-white text-black px-3 py-1 text-sm">Save</button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded border border-red-400 bg-red-500/10 p-3 text-sm">
          <b>Error:</b> {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center">
        <TabButton id="runs" label="Runs" />
        <TabButton id="payslips" label="Payslips" />
      </div>

      {/* RUNS */}
      {activeTab === 'runs' && (
        <div className="space-y-6">
          <SectionCard title="Create period">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Row label="Period key">
                <input className="rounded border px-2 py-1 w-full bg-transparent"
                  placeholder="e.g., 2025-08" value={periodForm.period_key}
                  onChange={(e) => setPeriodForm({ ...periodForm, period_key: e.target.value })} />
              </Row>
              <Row label="Start date">
                <input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
                  value={periodForm.start_date}
                  onChange={(e) => setPeriodForm({ ...periodForm, start_date: e.target.value })} />
              </Row>
              <Row label="End date">
                <input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
                  value={periodForm.end_date}
                  onChange={(e) => setPeriodForm({ ...periodForm, end_date: e.target.value })} />
              </Row>
              <Row label="Pay date">
                <input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
                  value={periodForm.pay_date}
                  onChange={(e) => setPeriodForm({ ...periodForm, pay_date: e.target.value })} />
              </Row>
            </div>
            <div className="mt-3">
              <button onClick={createPeriod} className="rounded border px-3 py-1 text-sm" disabled={loading}>
                {loading ? 'Submitting…' : 'Create period'}
              </button>
            </div>
            {createdPeriod && (
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-black/30 p-3 text-xs">
                {JSON.stringify(createdPeriod, null, 2)}
              </pre>
            )}
          </SectionCard>

          <SectionCard title="Create run">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <Row label="Period ID">
                <input className="rounded border px-2 py-1 w-full bg-transparent"
                  value={runForm.period_id}
                  onChange={(e) => setRunForm({ ...runForm, period_id: e.target.value })} />
              </Row>
              <Row label="Notes">
                <input className="rounded border px-2 py-1 w-full bg-transparent"
                  value={runForm.notes}
                  onChange={(e) => setRunForm({ ...runForm, notes: e.target.value })} />
              </Row>
            </div>
            <div className="mt-3">
              <button onClick={createRun} className="rounded border px-3 py-1 text-sm" disabled={loading}>
                {loading ? 'Submitting…' : 'Create run'}
              </button>
            </div>
            {createdRun && (
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-black/30 p-3 text-xs">
                {JSON.stringify(createdRun, null, 2)}
              </pre>
            )}
          </SectionCard>

          <SectionCard title="Compute & summary">
            <div className="flex items-center gap-2">
              <button onClick={computeBasic} className="rounded border px-3 py-1 text-sm" disabled={!createdRun?.id || loading}>
                {loading ? 'Computing…' : 'Compute basic'}
              </button>
              <button onClick={() => loadSummary(createdRun!.id)} className="rounded border px-3 py-1 text-sm" disabled={!createdRun?.id || loading}>
                {loading ? 'Loading…' : 'Load summary'}
              </button>
              {createdRun?.id && (
                <a
                  href={`${API_BASE}/payroll/runs/${encodeURIComponent(createdRun.id)}/export.csv`}
                  className="rounded border px-3 py-1 text-sm"
                >
                  Download CSV
                </a>
              )}
            </div>
            {runSummary && (
              <pre className="mt-3 max-h-64 overflow-auto rounded bg-black/30 p-3 text-xs">
                {JSON.stringify(runSummary, null, 2)}
              </pre>
            )}
          </SectionCard>
        </div>
      )}

      {/* PAYSLIPS */}
      {activeTab === 'payslips' && (
        <SectionCard title="Payslips by run">
          <div className="flex items-center gap-2">
            <input
              value={runIdForSlips}
              onChange={(e) => setRunIdForSlips(e.target.value)}
              placeholder="Run ID…"
              className="rounded border px-3 py-1 text-sm bg-transparent"
            />
            <button onClick={loadPayslips} className="rounded border px-3 py-1 text-sm" disabled={!runIdForSlips || loading}>
              {loading ? 'Loading…' : 'Load payslips'}
            </button>
          </div>

          <div className="mt-3 text-sm opacity-80">Tip: Click an ID to open the server-rendered payslip HTML.</div>

          {payslips ? (
            <div className="mt-3 overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left opacity-70">
                    <th className="py-1 pr-4">ID</th>
                    <th className="py-1 pr-4">Employee</th>
                    <th className="py-1 pr-4">Gross</th>
                    <th className="py-1 pr-4">Net</th>
                    <th className="py-1 pr-4">Ref</th>
                    <th className="py-1 pr-4">Open</th>
                  </tr>
                </thead>
                <tbody>
                  {payslips.map((p) => {
                    const id = String(p.id);
                    const ref = p.reference_no ?? id;
                    return (
                      <tr key={id} className="border-t border-white/10">
                        <td className="py-1 pr-4">{id}</td>
                        <td className="py-1 pr-4">{p.employee_id ?? '—'}</td>
                        <td className="py-1 pr-4">{p.gross_pay ?? '—'}</td>
                        <td className="py-1 pr-4">{p.net_pay ?? '—'}</td>
                        <td className="py-1 pr-4">{ref}</td>
                        <td className="py-1 pr-4">
                          <a
                            href={`${API_BASE}/payroll/payslips/${encodeURIComponent(id)}.html`}
                            target="_blank"
                            rel="noreferrer"
                            className="underline"
                          >
                            HTML
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="mt-3 text-sm opacity-80">No data loaded.</div>
          )}
        </SectionCard>
      )}
    </div>
  );
}
