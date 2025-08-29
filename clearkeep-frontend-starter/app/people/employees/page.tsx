'use client';

import React from 'react';
import Link from 'next/link';
import { apiGet, apiPost, setApiKey } from '../../../lib/api';

type AnyRec = Record<string, any>;

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

  // --- Directory search (manual only) ---
  const searchRef = React.useRef<HTMLInputElement>(null); // uncontrolled; read on Search/Enter
  const [activeOnly, setActiveOnly] = React.useState<boolean | null>(null);
  const [limit, setLimit] = React.useState<number>(50);

  const [employees, setEmployees] = React.useState<AnyRec[] | null>(null);
  const [empDetails, setEmpDetails] = React.useState<AnyRec | null>(null);

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
      searchRef.current?.focus({ preventScroll: true }); // do not steal focus; just keep it
    }
  }

  function onSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault();
      loadEmployeesManual();
    }
  }

  // --- Details + comp-change ---
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
      if (employees) loadEmployeesManual(); // refresh current result set
      alert('Compensation updated.');
    } catch (e: any) {
      setError(e?.message ?? 'Failed to apply compensation change');
    } finally { setLoading(false); }
  }

  // --- UI helpers ---
  function SectionCard(props: { title: string; children: React.ReactNode; right?: React.ReactNode }) {
    return (
      <div className="rounded-2xl border p-4 shadow-sm bg-white/5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold">{props.title}</h2>
          {props.right}
        </div>
        {props.children}
      </div>
    );
  }
  function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <label className="flex items-center gap-3 text-sm mb-2">
        <span className="w-40 opacity-70">{label}</span>
        <span className="flex-1">{children}</span>
      </label>
    );
  }
  function Kvp({ k, v }: { k: string; v: any }) {
    return (
      <div className="flex text-sm">
        <div className="w-48 opacity-70">{k}</div>
        <div className="flex-1">{v ?? '—'}</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Employees</h1>
        <div className="flex items-center gap-2">
          <Link href="/people/employees/new" className="rounded border px-3 py-1 text-sm hover:bg-gray-100">+ New employee</Link>
          <input
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder="X-API-Key…"
            className="rounded border px-3 py-1 text-sm bg-transparent"
          />
          <button onClick={saveKey} className="rounded bg-white text-black px-3 py-1 text-sm">Save</button>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-400 bg-red-500/10 p-3 text-sm">
          <b>Error:</b> {error}
        </div>
      )}

      {/* DIRECTORY (clean) */}
      <SectionCard
        title="Directory"
        right={
          <div className="hidden md:flex items-center gap-2">
            <input
              ref={searchRef}
              defaultValue=""
              onKeyDown={onSearchKeyDown}
              placeholder="Search code, name, email, city…"
              className="rounded border px-3 py-1 text-sm bg-transparent w-64"
            />
            <select
              value={String(limit)}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="rounded border px-2 py-1 text-sm bg-transparent"
              title="Page size"
            >
              <option value="20">20</option>
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="200">200</option>
            </select>
            <label className="ml-2 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={activeOnly === true}
                onChange={(e) => setActiveOnly(e.target.checked ? true : null)}
              />
              Active only
            </label>
            <button
              onClick={loadEmployeesManual}
              className="rounded border px-3 py-1 text-sm"
              disabled={loading}
              title="Search now"
            >
              {loading ? 'Loading…' : 'Search'}
            </button>
          </div>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="overflow-auto">
            {!employees ? (
              <div className="text-sm opacity-80">No data loaded. Type a query and click Search.</div>
            ) : employees.length === 0 ? (
              <div className="text-sm opacity-80">No matches.</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left opacity-70">
                    <th className="py-1 pr-4">ID</th>
                    <th className="py-1 pr-4">Code</th>
                    <th className="py-1 pr-4">Name</th>
                    <th className="py-1 pr-4">Pay type</th>
                    <th className="py-1 pr-4">Rate</th>
                    <th className="py-1 pr-4"></th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((e) => {
                    const name = (e.first_name || '') + ' ' + (e.last_name || '');
                    const rate = e.monthly_rate ?? e.daily_rate ?? e.hourly_rate ?? '—';
                    return (
                      <tr key={String(e.id)} className="border-t border-white/10">
                        <td className="py-1 pr-4">{String(e.id)}</td>
                        <td className="py-1 pr-4">{e.code ?? '—'}</td>
                        <td className="py-1 pr-4">{name.trim() || '—'}</td>
                        <td className="py-1 pr-4">{e.pay_type ?? '—'}</td>
                        <td className="py-1 pr-4">{rate}</td>
                        <td className="py-1 pr-4">
                          <button onClick={() => loadEmployee(String(e.id))} className="underline">View</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          <div className="space-y-4">
            {/* DETAILS */}
            <div className="rounded-xl border p-3">
              <div className="text-sm font-semibold mb-2">Employee details</div>
              {!empDetails ? (
                <div className="text-sm opacity-70">Select an employee → View</div>
              ) : (
                <div className="space-y-1">
                  <Kvp k="ID" v={empDetails.id} />
                  <Kvp k="Code" v={empDetails.code} />
                  <Kvp k="Name" v={`${empDetails.first_name ?? ''} ${empDetails.last_name ?? ''}`.trim()} />
                  <Kvp k="Active" v={String(empDetails.active)} />
                  <Kvp k="Pay type" v={empDetails.pay_type} />
                  <Kvp k="Monthly rate" v={empDetails.monthly_rate} />
                  <Kvp k="Daily rate" v={empDetails.daily_rate} />
                  <Kvp k="Hourly rate" v={empDetails.hourly_rate} />
                  <Kvp k="Tax status" v={empDetails.tax_status} />
                  <Kvp k="SSS no" v={empDetails.sss_no} />
                  <Kvp k="PhilHealth no" v={empDetails.philhealth_no} />
                  <Kvp k="Pag-IBIG no" v={empDetails.pagibig_no} />
                  <Kvp k="TIN" v={empDetails.tin} />
                  <Kvp k="Hire date" v={empDetails.hire_date} />
                  <Kvp k="Termination date" v={empDetails.termination_date} />
                  <Kvp k="Contact no" v={empDetails.contact_no} />
                  <Kvp k="Email" v={empDetails.email} />
                  <Kvp k="Address 1" v={empDetails.address_line1} />
                  <Kvp k="Address 2" v={empDetails.address_line2} />
                  <Kvp k="Barangay" v={empDetails.barangay} />
                  <Kvp k="City" v={empDetails.city} />
                  <Kvp k="Province" v={empDetails.province} />
                  <Kvp k="Postal code" v={empDetails.postal_code} />
                  <Kvp k="Country" v={empDetails.country} />
                  <Kvp k="Emergency name" v={empDetails.emergency_contact_name} />
                  <Kvp k="Emergency no" v={empDetails.emergency_contact_no} />
                  <Kvp k="Notes" v={empDetails.notes} />
                  <Kvp k="Created" v={empDetails.created_at} />
                </div>
              )}
            </div>

            {/* COMP CHANGE */}
            <div className="rounded-xl border p-3">
              <div className="text-sm font-semibold mb-2">Compensation change</div>
              {!empDetails ? (
                <div className="text-sm opacity-70">Select an employee to enable this form.</div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Row label="Effective date">
                      <input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.effective_date}
                        onChange={(e) => setCompForm({ ...compForm, effective_date: e.target.value })} />
                    </Row>
                    <Row label="Change type">
                      <input className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.change_type}
                        onChange={(e) => setCompForm({ ...compForm, change_type: e.target.value })} />
                    </Row>
                    <Row label="Reason">
                      <input className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.reason}
                        onChange={(e) => setCompForm({ ...compForm, reason: e.target.value })} />
                    </Row>
                    <Row label="New pay type">
                      <select className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.new_pay_type}
                        onChange={(e) => setCompForm({ ...compForm, new_pay_type: e.target.value })}>
                        <option value="">(keep current)</option>
                        <option value="monthly">monthly</option>
                        <option value="daily">daily</option>
                        <option value="hourly">hourly</option>
                      </select>
                    </Row>
                    <Row label="New monthly rate">
                      <input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.new_monthly_rate}
                        onChange={(e) => setCompForm({ ...compForm, new_monthly_rate: e.target.value })} />
                    </Row>
                    <Row label="New daily rate">
                      <input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.new_daily_rate}
                        onChange={(e) => setCompForm({ ...compForm, new_daily_rate: e.target.value })} />
                    </Row>
                    <Row label="New hourly rate">
                      <input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.new_hourly_rate}
                        onChange={(e) => setCompForm({ ...compForm, new_hourly_rate: e.target.value })} />
                    </Row>
                    <Row label="Notes">
                      <input className="rounded border px-2 py-1 w-full bg-transparent"
                        value={compForm.notes}
                        onChange={(e) => setCompForm({ ...compForm, notes: e.target.value })} />
                    </Row>
                  </div>

                  <div className="mt-3">
                    <button onClick={recordCompChange} className="rounded border px-3 py-1 text-sm" disabled={loading}>
                      {loading ? 'Saving…' : 'Record change'}
                    </button>
                  </div>

                  {lastChange && (
                    <pre className="mt-3 max-h-64 overflow-auto rounded bg-black/30 p-3 text-xs">
                      {JSON.stringify(lastChange, null, 2)}
                    </pre>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
