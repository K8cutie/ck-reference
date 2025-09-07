/**
 * ClearKeep — Locks helpers (pure)
 *
 * Centralizes parsing for /gl/locks/status responses which may come in
 * several shapes:
 *   - Array<{ period, is_locked, note?, updated_at? }>
 *   - { data: Array<...> }
 *   - { items: Array<...> }
 *   - { "YYYY-MM": boolean | { is_locked?, locked?, closed?, note?, status?, updated_at? } }
 */

export type LockStatus = {
  period: string;           // "YYYY-MM"
  is_locked: boolean;
  note?: string | null;
  updated_at?: string | null;
};

/** Parse any known locks payload shape into a normalized array. */
export function normalizeLocks(payload: any): LockStatus[] {
  if (!payload) return [];

  // Already an array of lock rows
  if (Array.isArray(payload)) {
    return payload
      .map(rowToLockStatus)
      .filter((x): x is LockStatus => !!x && typeof x.period === "string");
  }

  // Common wrappers
  if (Array.isArray((payload as any).data)) {
    return (payload as any).data
      .map(rowToLockStatus)
      .filter((x): x is LockStatus => !!x && typeof x.period === "string");
  }
  if (Array.isArray((payload as any).items)) {
    return (payload as any).items
      .map(rowToLockStatus)
      .filter((x): x is LockStatus => !!x && typeof x.period === "string");
  }

  // Keyed object: { "YYYY-MM": boolean | object }
  if (typeof payload === "object") {
    const out: LockStatus[] = [];
    for (const [period, v] of Object.entries(payload)) {
      if (!isYYYYMM(period)) continue;
      if (v && typeof v === "object") {
        const o: any = v;
        out.push({
          period,
          is_locked: bool(o.is_locked) ?? bool(o.locked) ?? bool(o.closed) ?? false,
          note: str(o.note) ?? str(o.status) ?? null,
          updated_at: str(o.updated_at) ?? null,
        });
      } else {
        out.push({
          period,
          is_locked: !!v,
          note: null,
          updated_at: null,
        });
      }
    }
    return out;
  }

  return [];
}

// ---------------- internal helpers ----------------

function rowToLockStatus(r: any): LockStatus | null {
  if (!r || typeof r !== "object") return null;
  const period = str(r.period);
  if (!period || !isYYYYMM(period)) return null;
  return {
    period,
    is_locked: bool(r.is_locked) ?? bool(r.locked) ?? bool(r.closed) ?? false,
    note: str(r.note) ?? str(r.status) ?? null,
    updated_at: str(r.updated_at) ?? null,
  };
}

function isYYYYMM(s: string): boolean {
  // very loose check: "YYYY-MM"
  return typeof s === "string" && /^\d{4}-\d{2}$/.test(s);
}

function str(v: any): string | null {
  return v == null ? null : String(v);
}

function bool(v: any): boolean | null {
  return v == null ? null : Boolean(v);
}
