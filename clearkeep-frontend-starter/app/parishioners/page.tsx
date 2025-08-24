'use client';

import { useEffect, useState } from 'react';
import { apiGet, apiPost } from '@/lib/api';
import type { Parishioner } from '@/lib/types';

export default function Page() {
  const [items, setItems] = useState<Parishioner[]>([]);
  const [loading, setLoading] = useState(true);
  const [first, setFirst] = useState('');
  const [last, setLast] = useState('');
  const [phone, setPhone] = useState('');

  async function load() {
    setLoading(true);
    try {
      const data: Parishioner[] = await apiGet(`/parishioners/?limit=200`);
      setItems(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const body = { first_name: first || 'Smoke', last_name: last || 'Calendar', contact_number: phone || '09999990000' };
    await apiPost('/parishioners/', body);
    setFirst(''); setLast(''); setPhone('');
    await load();
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="rounded-2xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold mb-4">Create parishioner</h2>
        <form onSubmit={create} className="space-y-3">
          <input className="w-full border rounded-lg px-3 py-2" placeholder="First name" value={first} onChange={e=>setFirst(e.target.value)} />
          <input className="w-full border rounded-lg px-3 py-2" placeholder="Last name" value={last} onChange={e=>setLast(e.target.value)} />
          <input className="w-full border rounded-lg px-3 py-2" placeholder="Contact number" value={phone} onChange={e=>setPhone(e.target.value)} />
          <button className="rounded-xl bg-gray-900 text-white px-4 py-2">Create</button>
        </form>
      </div>

      <div className="rounded-2xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold mb-4">Parishioners</h2>
        {loading ? <div>Loading…</div> : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2 pr-4">ID</th>
                  <th className="py-2 pr-4">First</th>
                  <th className="py-2 pr-4">Last</th>
                  <th className="py-2 pr-4">Phone</th>
                </tr>
              </thead>
              <tbody>
                {items.map(p => (
                  <tr key={p.id} className="border-b">
                    <td className="py-2 pr-4">{p.id}</td>
                    <td className="py-2 pr-4">{p.first_name}</td>
                    <td className="py-2 pr-4">{p.last_name}</td>
                    <td className="py-2 pr-4">{p.contact_number || ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
