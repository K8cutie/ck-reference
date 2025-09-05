'use client';

import React from 'react';
import Link from 'next/link';
import { apiGet, apiPost, setApiKey } from '../../../lib/api';

type AnyRec = Record<string, any>;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mb-2 flex items-center gap-3 text-sm">
      <span className="w-40 text-gray-600">{label}</span>
      <span className="flex-1">{children}</span>
    </label>
  );
}

function Kvp({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex text-sm">
      <div className="w-48 text-gray-600">{k}</div>
      <div className="flex-1 break-words">{v ?? '—'}</div>
    </div>
  );
}

export default function EmployeesPage() {
  // status
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // api key
  const [apiKeyInput, setApiKeyInput] = React.useState('');
  function saveKey() {
    setApiKey(apiKeyInput || null);
    alert(apiKeyInput ? 'API key saved.' : 'API key cleared.');
  }

  // Directory search (manual)
  const searchRef = React.useRef<HTMLInputElement>(null); // uncontrolled
  const [activeOnly, setActiveOnly] = React.useState<boolean | null>(null);
  const [limit, setLimit] = React.useState<number>(50);

  // data
  const [employees, setEmployees] = React.useState<AnyRec[] | null>(null);
  const [empDetails, setEmpDetails] = React.useState<AnyRec | null>(null);

  // comp change form
  const [compForm, setCompForm] = React.useState({
    effective_date: '',
    change_type: 'promotion',
    reason: '',
    new_pay_type: '',
    new_monthly_rate: '',
    new_daily_rate: '',
    new_hourly_rate: '',
    notes: '',
  });
  const [lastChange, setLastChange] = React.useState<AnyRec | null>(null);

  // actions
  async function loadEmployeesManual() {
    const q = searchRef.current?.value ?? '';
    const qs = new URLSearchParams();
    if (q) qs.set('q', q);
    if (activeOnly !== null) qs.set('active', String(!!activeOnly));
    qs.set('limit', String(limit));

    setLoading(true); setError(null);
    try {
      const data = await apiGet(`/payroll/employees?${qs.toString()}`);
      const arr = Array.isArray(data) ? data : (Array.isArray((data as any)?.value) ? (data as any).value : null);
      setEmployees(arr);
      if (!arr || arr.length === 0) setEmpDetails(null);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load employees');
    } finally {
      setLoading(false);
      searchRef.current?.focus({ preventScroll: true });
    }
  }

  function onSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      loadEmployeesManual();
    }
  }

  async function loadEmployee(id: string) {
    setLoading(true); setError(null);
    try { setEmpDetails(await apiGet(`/payroll/employees/${encodeURIComponent(id)}`)); setLastChange(null); }
    catch (e: any) { setError(e?.message ?? 'Failed to load employee'); }
    finally { setLoading(false); }
  }

  async function recordCompChange() {
    if (!empDetails?.id) { alert('Select an employee first.'); return; }
    if (!compForm.effective_date) { alert('Effective date is required.'); return; }
    if (!compForm.new_pay_type && !compForm.new_monthly_rate && !compForm.new_daily_rate && !compForm.new_hourly_rate) {
      alert('Provide at least one new value (pay type or rate).'); return;
    }
    setLoading(true); setError(null);
    try {
      const body: AnyRec = { effective_date: compForm.effective_date };
      if (compForm.change_type) body.change_type = compForm.change_type;
      if (compForm.reason) body.reason = compForm.reason;
      if (compForm.new_pay_type) body.new_pay_type = compForm.new_pay_type;
      if (compForm.new_monthly_rate) body.new_monthly_rate = Number(compForm.new_monthly_rate);
      if (compForm.new_daily_rate) body.new_daily_rate = Number(compForm.new_daily_rate);
      if (compForm.new_hourly_rate) body.new_hourly_rate = Number(compForm.new_hourly_rate);
      if (compForm.notes) body.notes = compForm.notes;

      const res = await apiPost(`/payroll/employees/${encodeURIComponent(empDetails.id)}/comp-change`, body);
      setLastChange(res?.change ?? null);
      await loadEmployee(String(empDetails.id));
      if (employees) loadEmployeesManual();
      alert('Compensation updated.');
    } catch (e: any) {
      setError(e?.message ?? 'Failed to apply compensation change');
    } finally {
      setLoading(false);
    }
  }

  // UI (Option A — Ledger Pro: dense, formal, crisp)
  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-5 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Employees</h1>
          <p className="mt-1 text-sm text-gray-500">Directory & profiles</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/people/new-employee"
            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            + New employee
          </Link>
          <input
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="X-API-Key…"
            className="rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <button onClick={saveKey} className="rounded-md border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">
            Save
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
          <b>Error:</b> {error}
        </div>
      )}

      {/* Toolbar */}
      <div className="mb-4 rounded-md border border-gray-200 bg-white p-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={searchRef}
            defaultValue=""
            onKeyDown={onSearchKeyDown}
            placeholder="Search code, name, email, city…"
            className="w-72 rounded-md border border-gray-300 px-3 py-2 text-sm"
          />
          <select
            value={String(limit)}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded-md border border-gray-300 px-2 py-2 text-sm"
            title="Page size"
          >
            <option value="20">20</option>
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200">200</option>
          </select>
          <label className="ml-2 flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              className="accent-blue-600"
              checked={activeOnly === true}
              onChange={(e) => setActiveOnly(e.target.checked ? true : null)}
            />
            Active only
          </label>
          <button
            onClick={loadEmployeesManual}
            className="rounded-md border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-60"
            disabled={loading}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </div>

      {/* 12-col layout: Directory (8) | Right rail (4) */}
      <div className="grid grid-cols-12 gap-6">
        {/* Directory */}
        <div className="col-span-12 lg:col-span-8">
          <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="overflow-auto">
              {!employees ? (
                <div className="p-6 text-sm text-gray-500">No data loaded. Use the search above.</div>
              ) : employees.length === 0 ? (
                <div className="p-6 text-sm text-gray-500">No matches.</div>
              ) : (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-white text-left text-gray-600">
                    <tr className="[&>th]:py-2 [&>th]:pr-4">
                      <th>ID</th>
                      <th>Code</th>
                      <th>Name</th>
                      <th>Pay type</th>
                      <th className="text-right">Rate</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody className="[&>tr]:border-t [&>tr]:border-gray-100">
                    {employees.map((e, i) => {
                      const name = (e.first_name || '') + ' ' + (e.last_name || '');
                      const rate = e.monthly_rate ?? e.daily_rate ?? e.hourly_rate ?? '—';
                      return (
                        <tr key={String(e.id)} className={i % 2 ? 'bg-gray-50' : ''}>
                          <td className="py-2 pr-4 text-gray-700">{String(e.id)}</td>
                          <td className="py-2 pr-4">{e.code ?? '—'}</td>
                          <td className="py-2 pr-4">{name.trim() || '—'}</td>
                          <td className="py-2 pr-4">{e.pay_type ?? '—'}</td>
                          <td className="py-2 pr-4 text-right font-mono tabular-nums">{rate}</td>
                          <td className="py-2 pr-4">
                            <button
                              onClick={() => loadEmployee(String(e.id))}
                              className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-800 hover:bg-gray-50"
                            >
                              View
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Right rail */}
        <div className="col-span-12 lg:col-span-4">
          <div className="sticky top-20 space-y-4">
            {/* Details */}
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Employee details</h2>
                {empDetails ? (
                  <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${empDetails.active ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'bg-gray-100 text-gray-700 border border-gray-300'}`}>
                    {empDetails.active ? 'Active' : 'Inactive'}
                  </span>
                ) : null}
              </div>
              {!empDetails ? (
                <div className="text-sm text-gray-500">Select an employee → View</div>
              ) : (
                <div className="space-y-1">
                  <Kvp k="ID" v={empDetails.id} />
                  <Kvp k="Code" v={empDetails.code} />
                  <Kvp k="Name" v={`${empDetails.first_name ?? ''} ${empDetails.last_name ?? ''}`.trim()} />
                  <Kvp k="Pay type" v={empDetails.pay_type} />
                  <Kvp k="Monthly rate" v={empDetails.monthly_rate} />
                  <Kvp k="Daily rate" v={empDetails.daily_rate} />
                  <Kvp k="Hourly rate" v={empDetails.hourly_rate} />
                  <Kvp k="SSS no" v={empDetails.sss_no} />
                  <Kvp k="PhilHealth no" v={empDetails.philhealth_no} />
                  <Kvp k="Pag-IBIG no" v={empDetails.pagibig_no} />
                  <Kvp k="TIN" v={empDetails.tin} />
                  <Kvp k="Hire date" v={empDetails.hire_date} />
                  <Kvp k="Contact no" v={empDetails.contact_no} />
                  <Kvp k="Email" v={empDetails.email} />
                  <Kvp k="Address 1" v={empDetails.address_line1} />
                  <Kvp k="Address 2" v={empDetails.address_line2} />
                  <Kvp k="City/Province" v={`${empDetails.city ?? ''}${empDetails.city && empDetails.province ? ', ' : ''}${empDetails.province ?? ''}`} />
                  <Kvp k="Postal/Country" v={`${empDetails.postal_code ?? ''}${empDetails.postal_code && empDetails.country ? ', ' : ''}${empDetails.country ?? ''}`} />
                  <Kvp k="Emergency contact" v={`${empDetails.emergency_contact_name ?? ''} ${empDetails.emergency_contact_no ?? ''}`.trim()} />
                  <Kvp k="Notes" v={empDetails.notes} />
                  <Kvp k="Created" v={empDetails.created_at} />
                </div>
              )}
            </div>

            {/* Compensation change */}
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-lg font-semibold text-gray-900">Compensation change</h2>
              {!empDetails ? (
                <div className="text-sm text-gray-500">Select an employee to enable this form.</div>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-3">
                    <Row label="Effective date">
                      <input
                        type="date"
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.effective_date}
                        onChange={(e) => setCompForm({ ...compForm, effective_date: e.target.value })}
                      />
                    </Row>
                    <Row label="Change type">
                      <input
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.change_type}
                        onChange={(e) => setCompForm({ ...compForm, change_type: e.target.value })}
                      />
                    </Row>
                    <Row label="Reason">
                      <input
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.reason}
                        onChange={(e) => setCompForm({ ...compForm, reason: e.target.value })}
                      />
                    </Row>
                    <Row label="New pay type">
                      <select
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.new_pay_type}
                        onChange={(e) => setCompForm({ ...compForm, new_pay_type: e.target.value })}
                      >
                        <option value="">(keep current)</option>
                        <option value="monthly">monthly</option>
                        <option value="daily">daily</option>
                        <option value="hourly">hourly</option>
                      </select>
                    </Row>
                    <Row label="New monthly rate">
                      <input
                        type="number"
                        step="0.01"
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.new_monthly_rate}
                        onChange={(e) => setCompForm({ ...compForm, new_monthly_rate: e.target.value })}
                      />
                    </Row>
                    <Row label="New daily rate">
                      <input
                        type="number"
                        step="0.01"
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.new_daily_rate}
                        onChange={(e) => setCompForm({ ...compForm, new_daily_rate: e.target.value })}
                      />
                    </Row>
                    <Row label="New hourly rate">
                      <input
                        type="number"
                        step="0.01"
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.new_hourly_rate}
                        onChange={(e) => setCompForm({ ...compForm, new_hourly_rate: e.target.value })}
                      />
                    </Row>
                    <Row label="Notes">
                      <input
                        className="w-full rounded-md border border-gray-300 px-2 py-1"
                        value={compForm.notes}
                        onChange={(e) => setCompForm({ ...compForm, notes: e.target.value })}
                      />
                    </Row>
                  </div>

                  <div className="mt-3">
                    <button
                      onClick={recordCompChange}
                      className="rounded-md border border-blue-600 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-60"
                      disabled={loading}
                    >
                      {loading ? 'Saving…' : 'Record change'}
                    </button>
                  </div>

                  {lastChange && (
                    <pre className="mt-3 max-h-64 overflow-auto rounded-md bg-gray-50 p-3 text-xs">
                      {JSON.stringify(lastChange, null, 2)}
                    </pre>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
