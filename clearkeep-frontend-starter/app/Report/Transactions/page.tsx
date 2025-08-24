import { apiGet } from "../../../lib/api";
import type { Transaction } from "../../../lib/types";

export const dynamic = "force-dynamic";

function peso(n?: number) {
  if (typeof n !== "number") return "—";
  return new Intl.NumberFormat("en-PH", { style: "currency", currency: "PHP" }).format(n);
}

export default async function TransactionsReportPage() {
  let items: Transaction[] = [];
  try {
    items = await apiGet<Transaction[]>("/transactions");
  } catch {
    items = [];
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Transactions — History</h1>
        <a
          href="/transactions/new"
          className="rounded-xl bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700"
        >
          ➕ New transaction
        </a>
      </div>

      {items.length === 0 ? (
        <div className="rounded-2xl border border-dashed bg-white p-8 text-center text-gray-600">
          No transactions found.
        </div>
      ) : (
        <div className="overflow-auto rounded-2xl border bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Reference</th>
                <th className="px-3 py-2 text-left">Memo</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Created</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((t) => (
                <tr key={String(t.id)} className="border-t">
                  <td className="px-3 py-2">{t.id}</td>
                  <td className="px-3 py-2">{t.reference ?? "—"}</td>
                  <td className="px-3 py-2">{t.memo ?? "—"}</td>
                  <td className="px-3 py-2 text-right">{peso(t.amount)}</td>
                  <td className="px-3 py-2">{t.status ?? "—"}</td>
                  <td className="px-3 py-2">
                    {t.created_at ? new Date(t.created_at).toLocaleString("en-PH") : "—"}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <a href={`/transactions/${t.id}`} className="rounded-lg border px-2 py-1 hover:bg-gray-50">
                      Open
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
