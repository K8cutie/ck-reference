/**
 * ClearKeep — Receipts Category Mapping
 *
 * Central config for mapping GL accounts -> Receipts categories used by
 * the Financial Analysis report. This file is *pure data* (plus light helpers)
 * so you can tune the mapping without touching compute or UI.
 *
 * Matching order (per rule):
 *   1) account_ids (exact id)
 *   2) code_prefixes (startsWith)
 *   3) name_includes (case-insensitive substring)
 *
 * You can mix any/all. The first matching rule wins.
 *
 * Tip: Start with name_includes, then lock down with code_prefixes/account_ids
 * as your chart of accounts stabilizes.
 */

import type { CategoryRule } from "./selectors";

/** Default category set (tune freely). */
export const RECEIPT_CATEGORY_RULES: CategoryRule[] = [
  {
    key: "mass",
    label: "Mass Collections",
    // account_ids: [/* e.g., 4101, 4102 */],
    // code_prefixes: ["41"], // if your Mass accounts start with 41*
    name_includes: ["mass", "collection", "offertory"],
  },
  {
    key: "stole",
    label: "Stole Fees",
    // account_ids: [],
    // code_prefixes: ["42"],
    name_includes: [
      "stole",
      "baptism",
      "wedding",
      "funeral",
      "anoint",
      "intentions",
      "intent",
      "burial",
    ],
  },
  {
    key: "donations",
    label: "Donations",
    // code_prefixes: ["43"],
    name_includes: ["donation", "gift", "pledge", "offering"],
  },
  {
    key: "chapel",
    label: "Chapel Remittance",
    // code_prefixes: ["44"],
    name_includes: ["chapel", "remit", "remittance", "mission", "sub-parish"],
  },
  {
    key: "balik_handog",
    label: "Balik Handog",
    // code_prefixes: ["45"],
    name_includes: ["balik", "handog"],
  },

  // --- Add any custom buckets here ---
  // {
  //   key: "rental",
  //   label: "Facility Rentals",
  //   code_prefixes: ["46"],
  //   name_includes: ["rental", "rent", "lease"],
  // },

  // NOTE: An "Other Receipts" bucket is created automatically *by the selector*
  // when includeUnmapped=true; you don't need to declare it here unless you want
  // a hard rule that forces certain lines into "Other".
  // { key: "other", label: "Other Receipts" },
];

/**
 * Helper to clone rules (so callers don't accidentally mutate the default array).
 */
export function getReceiptCategoryRules(): CategoryRule[] {
  return RECEIPT_CATEGORY_RULES.map((r) => ({
    key: r.key,
    label: r.label,
    account_ids: r.account_ids ? [...r.account_ids] : undefined,
    code_prefixes: r.code_prefixes ? [...r.code_prefixes] : undefined,
    name_includes: r.name_includes ? [...r.name_includes] : undefined,
  }));
}
