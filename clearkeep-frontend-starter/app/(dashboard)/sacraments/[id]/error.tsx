"use client";
export default function Error({ error }: { error: Error }) {
  return (
    <div className="p-6">
      <div className="rounded-3xl border bg-white p-8 shadow-sm text-red-600">
        {error.message || "Something went wrong."}
      </div>
    </div>
  );
}
