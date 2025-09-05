'use client';

import React from 'react';
import { apiGet, apiPost, setApiKey } from '../../../lib/api';

type AnyRec = Record<string, any>;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

export default function PayrollPage() {
  // Tabs: Runs & Payslips (formal “Ledger Pro” styling)
  const [activeTab, setActiveTab] = React.useState<'runs' | 'payslips'>('runs');

  // status
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // api key
  const [apiKeyInput, setApiKeyInput] = React.useState('');
  function saveKey() {
    setApiKey(apiKeyInput || null);
    alert(apiKeyInput ? 'API key saved.' : 'API key cleared.');
  }

  // period + run
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

  // payslips
  const [runIdForSlips, setRunIdForSlips] = React.useState('');
  const [payslips, setPayslips] = React.useState<AnyRec[] | null>(null);

  // ---------- UI helpers (Ledger Pro) ----------
  function PageHeader() {
    return (
      <div className="mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Payroll</h1>
          <p className="mt-1 text-sm text-gray-500">Runs, payslips, and exports</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="X-API-Key…"
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            onClick={saveKey}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
          >
            Save
          </button>
        </div>
      </div>
    );
  }

  function Tabs() {
    const Btn = ({ id, label }: { id: 'runs' | 'payslips'; label: string }) => {
      const on = activeTab === id;
      return (
        <button
          onClick={() => setActiveTab(id)}
          className={`px-3 py-1.5 text-sm border ${
            on
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'
          } rounded-md`}
        >
          {label}
        </button>
      );
    };
    return (
      <div className="mb-4 flex items-center gap-2">
        <Btn id="runs" label="Runs" />
        <Btn id="payslips" label="Payslips" />
      </div>
    );
  }

  function Card(props: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{props.title}</h2>
          {props.right}
        </div>
        {props.children}
      </div>
    );
  }

  function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <label className="mb-2 flex items-center gap-3 text-sm">
        <span className="w-36 text-gray-600">{label}</span>
        <span className="flex-1">{children}</span>
      </label>
    );
  }

  // ---------- actions ----------
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

  // ---------- render ----------
  return (
    <div className="p-6">
      <PageHeader />

      {error && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          <b>Error:</b> {error}
        </div>
      )}

      <Tabs />

      {activeTab === 'runs' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: create period & run */}
          <div className="lg:col-span-7 space-y-4">
            <Card title="Create period">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Row label="Period key">
                  <input
                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                    placeholder="e.g., 2025-09"
                    value={periodForm.period_key}
                    onChange={(e) => setPeriodForm({ ...periodForm, period_key: e.target.value })}
                  />
                </Row>
                <Row label="Start date">
                  <input
                    type="date"
                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                    value={periodForm.start_date}
                    onChange={(e) => setPeriodForm({ ...periodForm, start_date: e.target.value })}
                  />
                </Row>
                <Row label="End date">
                  <input
                    type="date"
                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                    value={periodForm.end_date}
                    onChange={(e) => setPeriodForm({ ...periodForm, end_date: e.target.value })}
                  />
                </Row>
                <Row label="Pay date">
                  <input
                    type="date"
                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                    value={periodForm.pay_date}
                    onChange={(e) => setPeriodForm({ ...periodForm, pay_date: e.target.value })}
                  />
                </Row>
              </div>
              <div className="mt-3">
                <button
                  onClick={createPeriod}
                  className="rounded-md border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-60"
                  disabled={loading}
                >
                  {loading ? 'Submitting…' : 'Create period'}
                </button>
              </div>
              {createdPeriod && (
                <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-gray-50 p-3 text-xs">
                  {JSON.stringify(createdPeriod, null, 2)}
                </pre>
              )}
            </Card>

            <Card title="Create run">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Row label="Period ID">
                  <input
                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                    value={runForm.period_id}
                    onChange={(e) => setRunForm({ ...runForm, period_id: e.target.value })}
                  />
                </Row>
                <Row label="Notes">
                  <input
                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                    value={runForm.notes}
                    onChange={(e) => setRunForm({ ...runForm, notes: e.target.value })}
                  />
                </Row>
              </div>
              <div className="mt-3">
                <button
                  onClick={createRun}
                  className="rounded-md border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-60"
                  disabled={loading}
                >
                  {loading ? 'Submitting…' : 'Create run'}
                </button>
              </div>
              {createdRun && (
                <pre className="mt-3 max-h-56 overflow-auto rounded-md bg-gray-50 p-3 text-xs">
                  {JSON.stringify(createdRun, null, 2)}
                </pre>
              )}
            </Card>
          </div>

          {/* Right rail: compute + summary */}
          <div className="lg:col-span-5">
            <div className="sticky top-20 space-y-4">
              <Card
                title="Compute & summary"
                right={
                  createdRun?.id ? (
                    <a
                      href={`${API_BASE}/payroll/runs/${encodeURIComponent(createdRun.id)}/export.csv`}
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
                    >
                      Download CSV
                    </a>
                  ) : null
                }
              >
                <div className="mb-3 flex items-center gap-2">
                  <button
                    onClick={computeBasic}
                    className="rounded-md border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-60"
                    disabled={!createdRun?.id || loading}
                  >
                    {loading ? 'Computing…' : 'Compute basic'}
                  </button>
                  <button
                    onClick={() => loadSummary(createdRun!.id)}
                    className="rounded-md border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-60"
                    disabled={!createdRun?.id || loading}
                  >
                    {loading ? 'Loading…' : 'Load summary'}
                  </button>
                </div>
                {runSummary && (
                  <pre className="max-h-64 overflow-auto rounded-md bg-gray-50 p-3 text-xs">
                    {JSON.stringify(runSummary, null, 2)}
                  </pre>
                )}
              </Card>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'payslips' && (
        <Card
          title="Payslips by run"
          right={
            <div className="flex items-center gap-2">
              <input
                className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                placeholder="Run ID…"
                value={runIdForSlips}
                onChange={(e) => setRunIdForSlips(e.target.value)}
              />
              <button
                onClick={loadPayslips}
                className="rounded-md border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-60"
                disabled={!runIdForSlips || loading}
              >
                {loading ? 'Loading…' : 'Load'}
              </button>
            </div>
          }
        >
          {!payslips ? (
            <div className="text-sm text-gray-500">No data loaded.</div>
          ) : (
            <div className="overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white text-left text-gray-600">
                  <tr className="[&>th]:py-2 [&>th]:pr-4">
                    <th>ID</th>
                    <th>Employee</th>
                    <th className="text-right">Gross</th>
                    <th className="text-right">Net</th>
                    <th>Ref</th>
                    <th>Open</th>
                  </tr>
                </thead>
                <tbody className="[&>tr]:border-t [&>tr]:border-gray-100">
                  {payslips.map((p) => {
                    const id = String(p.id);
                    const ref = p.reference_no ?? id;
                    return (
                      <tr key={id} className="hover:bg-gray-50/60">
                        <td className="py-2 pr-4">{id}</td>
                        <td className="py-2 pr-4">{p.employee_id ?? '—'}</td>
                        <td className="py-2 pr-4 text-right font-mono tabular-nums">{p.gross_pay ?? '—'}</td>
                        <td className="py-2 pr-4 text-right font-mono tabular-nums">{p.net_pay ?? '—'}</td>
                        <td className="py-2 pr-4">{ref}</td>
                        <td className="py-2 pr-4">
                          <a
                            href={`${API_BASE}/payroll/payslips/${encodeURIComponent(id)}.html`}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded-md border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
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
          )}
        </Card>
      )}
    </div>
  );
}
