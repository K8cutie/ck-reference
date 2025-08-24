// app/expenses/[id]/page.tsx
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

async function getExpense(id: string) {
  const r = await fetch(`${API_BASE}/expenses/${id}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export default async function ExpenseDetailPage({ params }: { params: { id: string } }) {
  const expense = await getExpense(params.id);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Expense #{expense.id}</h1>
        <Link href="/transactions/new" className="text-sm underline">
          + New expense
        </Link>
      </div>

      <div className="rounded-3xl border bg-white p-6 shadow-sm space-y-4">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Date" value={expense.expense_date} />
          <Field label="Status" value={expense.status} />
          <Field label="Amount" value={`₱ ${expense.amount}`} />
          <Field label="Category ID" value={expense.category_id ?? "—"} />
          <Field label="Vendor" value={expense.vendor_name ?? "—"} />
          <Field label="Payment method" value={expense.payment_method ?? "—"} />
          <Field label="Reference no." value={expense.reference_no ?? "—"} />
          <Field label="Due date" value={expense.due_date ?? "—"} />
          <Field label="Paid at" value={expense.paid_at ?? "—"} />
        </div>

        <div>
          <div className="text-sm font-medium mb-1">Notes</div>
          <div className="text-sm text-gray-700">{expense.description ?? "—"}</div>
        </div>

        <div className="text-xs text-gray-500">
          Created: {new Date(expense.created_at).toLocaleString()} • Updated:{" "}
          {new Date(expense.updated_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-sm font-medium">{label}</div>
      <div className="text-sm text-gray-700">{value}</div>
    </div>
  );
}
