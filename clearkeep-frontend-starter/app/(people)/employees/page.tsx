'use client';

import React from 'react';
import { apiGet, apiPost, setApiKey } from '../../../lib/api';

type AnyRec = Record<string, any>;

export default function EmployeesPage() {
  // status
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // api key
  const [apiKeyInput, setApiKeyInput] = React.useState('');

  // EMPLOYEES
  const [employees, setEmployees] = React.useState<AnyRec[] | null>(null);
  const [empDetails, setEmpDetails] = React.useState<AnyRec | null>(null);
  const [empCreated, setEmpCreated] = React.useState<AnyRec | null>(null);

  // Create-employee form
  const [empForm, setEmpForm] = React.useState({
    code: '',
    first_name: '',
    last_name: '',
    active: true,
    pay_type: 'monthly', // monthly | daily | hourly
    monthly_rate: '',
    daily_rate: '',
    hourly_rate: '',
    tax_status: '',
    sss_no: '',
    philhealth_no: '',
    pagibig_no: '',
    tin: '',
    hire_date: '',
    termination_date: '',
    contact_no: '',
    email: '',
    address_line1: '',
    address_line2: '',
    barangay: '',
    city: '',
    province: '',
    postal_code: '',
    country: '',
    emergency_contact_name: '',
    emergency_contact_no: '',
    notes: '',
  });

  // Compensation-change form
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

  function saveKey() {
    setApiKey(apiKeyInput || null);
    alert(apiKeyInput ? 'API key saved.' : 'API key cleared.');
  }

  // ---- actions ----
  async function loadEmployees() {
    setLoading(true); setError(null);
    try {
      const data = await apiGet('/payroll/employees?limit=200');
      const arr = Array.isArray(data) ? data : (Array.isArray((data as any)?.value) ? (data as any).value : null);
      setEmployees(arr);
      setEmpDetails(null);
      setLastChange(null);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load employees');
    } finally { setLoading(false); }
  }

  async function loadEmployee(id: string) {
    setLoading(true); setError(null);
    try {
      const data = await apiGet(`/payroll/employees/${encodeURIComponent(id)}`);
      setEmpDetails(data);
      setLastChange(null);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load employee');
    } finally { setLoading(false); }
  }

  async function createEmployee() {
    setLoading(true); setError(null);
    try {
      const b: AnyRec = {
        code: empForm.code,
        first_name: empForm.first_name,
        last_name: empForm.last_name,
        active: !!empForm.active,
        pay_type: empForm.pay_type,
      };
      if (empForm.monthly_rate) b.monthly_rate = Number(empForm.monthly_rate);
      if (empForm.daily_rate) b.daily_rate = Number(empForm.daily_rate);
      if (empForm.hourly_rate) b.hourly_rate = Number(empForm.hourly_rate);

      if (empForm.tax_status) b.tax_status = empForm.tax_status;
      if (empForm.sss_no) b.sss_no = empForm.sss_no;
      if (empForm.philhealth_no) b.philhealth_no = empForm.philhealth_no;
      if (empForm.pagibig_no) b.pagibig_no = empForm.pagibig_no;
      if (empForm.tin) b.tin = empForm.tin;

      if (empForm.hire_date) b.hire_date = empForm.hire_date;
      if (empForm.termination_date) b.termination_date = empForm.termination_date;

      if (empForm.contact_no) b.contact_no = empForm.contact_no;
      if (empForm.email) b.email = empForm.email;
      if (empForm.address_line1) b.address_line1 = empForm.address_line1;
      if (empForm.address_line2) b.address_line2 = empForm.address_line2;
      if (empForm.barangay) b.barangay = empForm.barangay;
      if (empForm.city) b.city = empForm.city;
      if (empForm.province) b.province = empForm.province;
      if (empForm.postal_code) b.postal_code = empForm.postal_code;
      if (empForm.country) b.country = empForm.country;

      if (empForm.emergency_contact_name) b.emergency_contact_name = empForm.emergency_contact_name;
      if (empForm.emergency_contact_no) b.emergency_contact_no = empForm.emergency_contact_no;
      if (empForm.notes) b.notes = empForm.notes;

      const emp = await apiPost('/payroll/employees', b);
      setEmpCreated(emp);
      if (employees) loadEmployees();
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create employee');
    } finally { setLoading(false); }
  }

  async function recordCompChange() {
    if (!empDetails?.id) { alert('Select an employee first.'); return; }
    if (!compForm.effective_date) { alert('Effective date is required.'); return; }
    if (!compForm.new_pay_type && !compForm.new_monthly_rate && !compForm.new_daily_rate && !compForm.new_hourly_rate) {
      alert('Provide at least one new value (pay type or rate).'); return;
    }

    setLoading(true); setError(null);
    try {
      const b: AnyRec = { effective_date: compForm.effective_date };
      if (compForm.change_type) b.change_type = compForm.change_type;
      if (compForm.reason) b.reason = compForm.reason;
      if (compForm.new_pay_type) b.new_pay_type = compForm.new_pay_type;
      if (compForm.new_monthly_rate) b.new_monthly_rate = Number(compForm.new_monthly_rate);
      if (compForm.new_daily_rate) b.new_daily_rate = Number(compForm.new_daily_rate);
      if (compForm.new_hourly_rate) b.new_hourly_rate = Number(compForm.new_hourly_rate);
      if (compForm.notes) b.notes = compForm.notes;

      const res = await apiPost(`/payroll/employees/${encodeURIComponent(empDetails.id)}/comp-change`, b);
      setLastChange(res?.change ?? null);
      await loadEmployee(String(empDetails.id));
      if (employees) loadEmployees();
      alert('Compensation updated.');
    } catch (e: any) {
      setError(e?.message ?? 'Failed to apply compensation change');
    } finally { setLoading(false); }
  }

  // ---- UI helpers ----
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

  // -------------------- RENDER --------------------
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Employees</h1>
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

      {error && (
        <div className="rounded border border-red-400 bg-red-500/10 p-3 text-sm">
          <b>Error:</b> {error}
        </div>
      )}

      <SectionCard title="Directory">
        <div className="flex items-center gap-2">
          <button onClick={loadEmployees} className="rounded border px-3 py-1 text-sm" disabled={loading}>
            {loading ? 'Loading…' : 'Load employees'}
          </button>
        </div>

        <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="overflow-auto">
            {employees ? (
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
                          <button onClick={() => loadEmployee(String(e.id))} className="underline">
                            View
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="text-sm opacity-80">No data loaded.</div>
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

      <SectionCard title="Create employee">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Identity */}
          <Row label="Code">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.code} onChange={(e) => setEmpForm({ ...empForm, code: e.target.value })} />
          </Row>
          <Row label="Active">
            <input type="checkbox" checked={empForm.active}
              onChange={(e) => setEmpForm({ ...empForm, active: e.target.checked })} />
          </Row>
          <Row label="First name">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.first_name} onChange={(e) => setEmpForm({ ...empForm, first_name: e.target.value })} />
          </Row>
          <Row label="Last name">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.last_name} onChange={(e) => setEmpForm({ ...empForm, last_name: e.target.value })} />
          </Row>

          {/* Pay */}
          <Row label="Pay type">
            <select className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.pay_type} onChange={(e) => setEmpForm({ ...empForm, pay_type: e.target.value })}>
              <option value="monthly">monthly</option>
              <option value="daily">daily</option>
              <option value="hourly">hourly</option>
            </select>
          </Row>
          <Row label="Monthly rate">
            <input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.monthly_rate} onChange={(e) => setEmpForm({ ...empForm, monthly_rate: e.target.value })} />
          </Row>
          <Row label="Daily rate">
            <input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.daily_rate} onChange={(e) => setEmpForm({ ...empForm, daily_rate: e.target.value })} />
          </Row>
          <Row label="Hourly rate">
            <input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.hourly_rate} onChange={(e) => setEmpForm({ ...empForm, hourly_rate: e.target.value })} />
          </Row>

          {/* Gov/tax */}
          <Row label="Tax status">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.tax_status} onChange={(e) => setEmpForm({ ...empForm, tax_status: e.target.value })} />
          </Row>
          <Row label="SSS no">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.sss_no} onChange={(e) => setEmpForm({ ...empForm, sss_no: e.target.value })} />
          </Row>
          <Row label="PhilHealth no">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.philhealth_no} onChange={(e) => setEmpForm({ ...empForm, philhealth_no: e.target.value })} />
          </Row>
          <Row label="Pag-IBIG no">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.pagibig_no} onChange={(e) => setEmpForm({ ...empForm, pagibig_no: e.target.value })} />
          </Row>
          <Row label="TIN">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.tin} onChange={(e) => setEmpForm({ ...empForm, tin: e.target.value })} />
          </Row>

          {/* Employment dates */}
          <Row label="Hire date">
            <input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.hire_date} onChange={(e) => setEmpForm({ ...empForm, hire_date: e.target.value })} />
          </Row>
          <Row label="Termination date">
            <input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.termination_date} onChange={(e) => setEmpForm({ ...empForm, termination_date: e.target.value })} />
          </Row>

          {/* Contact & address */}
          <Row label="Contact no">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.contact_no} onChange={(e) => setEmpForm({ ...empForm, contact_no: e.target.value })} />
          </Row>
          <Row label="Email">
            <input type="email" className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.email} onChange={(e) => setEmpForm({ ...empForm, email: e.target.value })} />
          </Row>
          <Row label="Address line 1">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.address_line1} onChange={(e) => setEmpForm({ ...empForm, address_line1: e.target.value })} />
          </Row>
          <Row label="Address line 2">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.address_line2} onChange={(e) => setEmpForm({ ...empForm, address_line2: e.target.value })} />
          </Row>
          <Row label="Barangay">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.barangay} onChange={(e) => setEmpForm({ ...empForm, barangay: e.target.value })} />
          </Row>
          <Row label="City">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.city} onChange={(e) => setEmpForm({ ...empForm, city: e.target.value })} />
          </Row>
          <Row label="Province">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.province} onChange={(e) => setEmpForm({ ...empForm, province: e.target.value })} />
          </Row>
          <Row label="Postal code">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.postal_code} onChange={(e) => setEmpForm({ ...empForm, postal_code: e.target.value })} />
          </Row>
          <Row label="Country">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.country} onChange={(e) => setEmpForm({ ...empForm, country: e.target.value })} />
          </Row>

          {/* Emergency & notes */}
          <Row label="Emergency name">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.emergency_contact_name} onChange={(e) => setEmpForm({ ...empForm, emergency_contact_name: e.target.value })} />
          </Row>
          <Row label="Emergency no">
            <input className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.emergency_contact_no} onChange={(e) => setEmpForm({ ...empForm, emergency_contact_no: e.target.value })} />
          </Row>
          <Row label="Notes">
            <textarea className="rounded border px-2 py-1 w-full bg-transparent"
              value={empForm.notes} onChange={(e) => setEmpForm({ ...empForm, notes: e.target.value })} />
          </Row>
        </div>

        <div className="mt-3">
          <button onClick={createEmployee} className="rounded border px-3 py-1 text-sm" disabled={loading}>
            {loading ? 'Submitting…' : 'Create employee'}
          </button>
        </div>
        {empCreated && (
          <pre className="mt-3 max-h-64 overflow-auto rounded bg-black/30 p-3 text-xs">
            {JSON.stringify(empCreated, null, 2)}
          </pre>
        )}
      </SectionCard>
    </div>
  );
}
