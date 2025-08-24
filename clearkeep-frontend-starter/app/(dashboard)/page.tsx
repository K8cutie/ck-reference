import Link from 'next/link';

export default function Page() {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="rounded-2xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold">Get started</h2>
        <p className="text-sm text-gray-600 mt-2">Create a sacrament and verify it appears in Transactions & Calendar.</p>
        <div className="mt-4 flex gap-3">
          <Link href="/parishioners" className="rounded-xl bg-gray-900 text-white px-4 py-2">Parishioners</Link>
          <Link href="/sacraments/new" className="rounded-xl bg-gray-100 px-4 py-2">New Sacrament</Link>
        </div>
      </div>
      <div className="rounded-2xl bg-white p-6 shadow">
        <h2 className="text-lg font-semibold">Data views</h2>
        <ul className="list-disc ml-5 mt-2 text-sm text-gray-700 space-y-1">
          <li><Link className="underline" href="/transactions">Transactions</Link></li>
          <li><Link className="underline" href="/calendar">Calendar</Link></li>
        </ul>
      </div>
    </div>
  );
}
