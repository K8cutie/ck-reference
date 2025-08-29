'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { apiPost, setApiKey } from '../../../lib/api'; // <-- fixed (3x ..)

type AnyRec = Record<string, any>;

export default function NewEmployeePage() {
  const router = useRouter();

  // top-right API key
  const [apiKeyInput, setApiKeyInput] = React.useState('');
  function saveKey() {
    setApiKey(apiKeyInput || null);
    alert(apiKeyInput ? 'API key saved.' : 'API key cleared.');
  }

  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [created, setCreated] = React.useState<AnyRec | null>(null);

  // form state
  const [f, setF] = React.useState({
    code: '', first_name: '', last_name: '', active: true,
    pay_type: 'monthly', monthly_rate: '', daily_rate: '', hourly_rate: '',
    tax_status: '', sss_no: '', philhealth_no: '', pagibig_no: '', tin: '',
    hire_date: '', termination_date: '',
    contact_no: '', email: '',
    address_line1: '', address_line2: '', barangay: '', city: '', province: '', postal_code: '', country: '',
    emergency_contact_name: '', emergency_contact_no: '', notes: '',
  });

  function Row({ label, children }: { label: string; children: React.ReactNode }) {
    return (
      <label className="flex items-center gap-3 text-sm mb-2">
        <span className="w-44 opacity-70">{label}</span>
        <span className="flex-1">{children}</span>
      </label>
    );
  }

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      const body: AnyRec = {
        code: f.code, first_name: f.first_name, last_name: f.last_name,
        active: !!f.active, pay_type: f.pay_type,
      };
      if (f.monthly_rate) body.monthly_rate = Number(f.monthly_rate);
      if (f.daily_rate)   body.daily_rate   = Number(f.daily_rate);
      if (f.hourly_rate)  body.hourly_rate  = Number(f.hourly_rate);

      if (f.tax_status)    body.tax_status    = f.tax_status;
      if (f.sss_no)        body.sss_no        = f.sss_no;
      if (f.philhealth_no) body.philhealth_no = f.philhealth_no;
      if (f.pagibig_no)    body.pagibig_no    = f.pagibig_no;
      if (f.tin)           body.tin           = f.tin;

      if (f.hire_date)        body.hire_date        = f.hire_date;
      if (f.termination_date) body.termination_date = f.termination_date;

      if (f.contact_no)    body.contact_no    = f.contact_no;
      if (f.email)         body.email         = f.email;
      if (f.address_line1) body.address_line1 = f.address_line1;
      if (f.address_line2) body.address_line2 = f.address_line2;
      if (f.barangay)      body.barangay      = f.barangay;
      if (f.city)          body.city          = f.city;
      if (f.province)      body.province      = f.province;
      if (f.postal_code)   body.postal_code   = f.postal_code;
      if (f.country)       body.country       = f.country;

      if (f.emergency_contact_name) body.emergency_contact_name = f.emergency_contact_name;
      if (f.emergency_contact_no)   body.emergency_contact_no   = f.emergency_contact_no;
      if (f.notes)                  body.notes                  = f.notes;

      const emp = await apiPost('/payroll/employees', body);
      setCreated(emp);
      setTimeout(() => router.push('/people/employees?created=1'), 600);
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create employee');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/people/employees" className="rounded border px-3 py-1 text-sm hover:bg-gray-100">← Back to Employees</Link>
          <h1 className="text-2xl font-bold">New Employee</h1>
        </div>
        <div className="flex items-center gap-2">
          <input value={apiKeyInput} onChange={(e) => setApiKeyInput(e.target.value)}
                 placeholder="X-API-Key…" className="rounded border px-3 py-1 text-sm bg-transparent" />
          <button onClick={saveKey} className="rounded bg-white text-black px-3 py-1 text-sm">Save</button>
        </div>
      </div>

      {error && <div className="rounded border border-red-400 bg-red-500/10 p-3 text-sm"><b>Error:</b> {error}</div>}
      {created && <div className="rounded border border-green-600 bg-green-500/10 p-3 text-sm">
        Created <b>{created.code}</b> — redirecting to directory…
      </div>}

      <div className="rounded-2xl border p-4 shadow-sm bg-white/5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <div className="text-sm font-semibold mb-2">Identity & Pay</div>
            <Row label="Code"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></Row>
            <Row label="Active"><input type="checkbox" checked={f.active}
              onChange={(e) => setF({ ...f, active: e.target.checked })} /></Row>
            <Row label="First name"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.first_name} onChange={(e) => setF({ ...f, first_name: e.target.value })} /></Row>
            <Row label="Last name"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.last_name} onChange={(e) => setF({ ...f, last_name: e.target.value })} /></Row>
            <Row label="Pay type">
              <select className="rounded border px-2 py-1 w-full bg-transparent"
                value={f.pay_type} onChange={(e) => setF({ ...f, pay_type: e.target.value })}>
                <option value="monthly">monthly</option>
                <option value="daily">daily</option>
                <option value="hourly">hourly</option>
              </select>
            </Row>
            <Row label="Monthly rate"><input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.monthly_rate} onChange={(e) => setF({ ...f, monthly_rate: e.target.value })} /></Row>
            <Row label="Daily rate"><input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.daily_rate} onChange={(e) => setF({ ...f, daily_rate: e.target.value })} /></Row>
            <Row label="Hourly rate"><input type="number" step="0.01" className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.hourly_rate} onChange={(e) => setF({ ...f, hourly_rate: e.target.value })} /></Row>

            <div className="text-sm font-semibold mt-6 mb-2">Government / Tax</div>
            <Row label="Tax status"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.tax_status} onChange={(e) => setF({ ...f, tax_status: e.target.value })} /></Row>
            <Row label="SSS no"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.sss_no} onChange={(e) => setF({ ...f, sss_no: e.target.value })} /></Row>
            <Row label="PhilHealth no"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.philhealth_no} onChange={(e) => setF({ ...f, philhealth_no: e.target.value })} /></Row>
            <Row label="Pag-IBIG no"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.pagibig_no} onChange={(e) => setF({ ...f, pagibig_no: e.target.value })} /></Row>
            <Row label="TIN"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.tin} onChange={(e) => setF({ ...f, tin: e.target.value })} /></Row>
          </div>

          <div>
            <div className="text-sm font-semibold mb-2">Employment</div>
            <Row label="Hire date"><input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.hire_date} onChange={(e) => setF({ ...f, hire_date: e.target.value })} /></Row>
            <Row label="Termination date"><input type="date" className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.termination_date} onChange={(e) => setF({ ...f, termination_date: e.target.value })} /></Row>

            <div className="text-sm font-semibold mt-6 mb-2">Contacts & Address</div>
            <Row label="Contact no"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.contact_no} onChange={(e) => setF({ ...f, contact_no: e.target.value })} /></Row>
            <Row label="Email"><input type="email" className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Row>
            <Row label="Address 1"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.address_line1} onChange={(e) => setF({ ...f, address_line1: e.target.value })} /></Row>
            <Row label="Address 2"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.address_line2} onChange={(e) => setF({ ...f, address_line2: e.target.value })} /></Row>
            <Row label="Barangay"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.barangay} onChange={(e) => setF({ ...f, barangay: e.target.value })} /></Row>
            <Row label="City"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></Row>
            <Row label="Province"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.province} onChange={(e) => setF({ ...f, province: e.target.value })} /></Row>
            <Row label="Postal code"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.postal_code} onChange={(e) => setF({ ...f, postal_code: e.target.value })} /></Row>
            <Row label="Country"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })} /></Row>

            <div className="text-sm font-semibold mt-6 mb-2">Emergency & Notes</div>
            <Row label="Emergency name"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.emergency_contact_name} onChange={(e) => setF({ ...f, emergency_contact_name: e.target.value })} /></Row>
            <Row label="Emergency no"><input className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.emergency_contact_no} onChange={(e) => setF({ ...f, emergency_contact_no: e.target.value })} /></Row>
            <Row label="Notes"><textarea className="rounded border px-2 py-1 w-full bg-transparent"
              value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Row>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <button onClick={submit} disabled={loading} className="rounded border px-4 py-2 text-sm">
            {loading ? 'Creating…' : 'Create employee'}
          </button>
          <Link href="/people/employees" className="rounded border px-3 py-2 text-sm hover:bg-gray-100">Cancel</Link>
        </div>
      </div>
    </div>
  );
}
