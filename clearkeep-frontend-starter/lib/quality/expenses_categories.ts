/**
 * ClearKeep — Expense Category Mapping
 *
 * Central config for mapping GL accounts -> Expense categories used by
 * the Financial Analysis report. This file is *pure data* (plus a small helper)
 * so you can tune the mapping without touching compute or UI.
 *
 * Matching order (per rule), same as receipts_categories:
 *   1) account_ids   (exact id)
 *   2) code_prefixes (startsWith)
 *   3) name_includes (case-insensitive substring)
 *
 * The first matching rule wins. Add/remove rules freely.
 */

import type { CategoryRule } from "./selectors";

/** Default expense categories (tune freely). */
export const EXPENSE_CATEGORY_RULES: CategoryRule[] = [
  {
    key: "utilities",
    label: "Utilities",
    // account_ids: [],
    // code_prefixes: ["61"],
    name_includes: ["utility", "electric", "power", "water", "internet", "wifi", "phone", "telco"],
  },
  {
    key: "office_supplies",
    label: "Office Supplies",
    // code_prefixes: ["62"],
    name_includes: ["office supply", "stationery", "paper", "ink", "toner", "envelope", "binder"],
  },
  {
    key: "repairs",
    label: "Repairs & Maintenance",
    // code_prefixes: ["63"],
    name_includes: ["repair", "maintenance", "service", "fix", "replace"],
  },
  {
    key: "transport",
    label: "Transportation & Fuel",
    // code_prefixes: ["64"],
    name_includes: ["transport", "fuel", "gas", "diesel", "fare", "parking", "uber", "grab"],
  },
  {
    key: "banking_fees",
    label: "Banking & Fees",
    // code_prefixes: ["65"],
    name_includes: ["bank", "fee", "charge", "service charge", "processing", "gateway"],
  },
  {
    key: "charity",
    label: "Charity / Outreach",
    // code_prefixes: ["66"],
    name_includes: ["charity", "outreach", "aid", "relief", "donation"],
  },
  {
    key: "salaries",
    label: "Salaries & Honoraria",
    // code_prefixes: ["67"],
    name_includes: ["salary", "salaries", "honoraria", "stipend", "payroll", "wage", "benefit"],
  },
  {
    key: "liturgical",
    label: "Liturgical Supplies",
    // code_prefixes: ["68"],
    name_includes: ["liturgical", "host", "wine", "candle", "incense", "missal"],
  },
  {
    key: "rentals",
    label: "Facility Rentals",
    // code_prefixes: ["69"],
    name_includes: ["rental", "rent", "lease"],
  },
  {
    key: "insurance",
    label: "Insurance",
    name_includes: ["insurance", "premium"],
  },
  {
    key: "training",
    label: "Training & Seminars",
    name_includes: ["training", "seminar", "workshop", "conference"],
  },
  // NOTE: An "Other Expenses" bucket is created automatically by the selector
  // when includeUnmapped=true; you don't need to declare it here.
];

/** Helper to clone rules (avoid accidental mutation of the default array). */
export function getExpenseCategoryRules(): CategoryRule[] {
  return EXPENSE_CATEGORY_RULES.map((r) => ({
    key: r.key,
    label: r.label,
    account_ids: r.account_ids ? [...r.account_ids] : undefined,
    code_prefixes: r.code_prefixes ? [...r.code_prefixes] : undefined,
    name_includes: r.name_includes ? [...r.name_includes] : undefined,
  }));
}
