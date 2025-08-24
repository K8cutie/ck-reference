// lib/types.ts
export type Transaction = {
  id: string | number;
  amount?: number;
  currency?: string;      // e.g., "PHP"
  memo?: string;          // description / note
  reference?: string;     // e.g., "SAC-123"
  status?: string;        // e.g., "paid" | "pending" | "void"
  method?: string;        // e.g., "cash" | "gcash" | "card"
  created_at?: string;    // ISO
  updated_at?: string;    // ISO
  person_name?: string;   // optional payer name
  external_ref?: string;  // optional
};
