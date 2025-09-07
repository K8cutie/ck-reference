"use client";

import React from "react";

type Props = {
  slaDays: number;
  includeReversals: boolean;
  includeReopen: boolean;
};

/**
 * NotesSection — static/help text for the Six Sigma page.
 * Pure presentational; no app-specific imports.
 */
export default function NotesSection({ slaDays, includeReversals, includeReopen }: Props) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 12, background: "#fff" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>Notes</div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#6b7280" }}>
        <li>Expense = debit − credit; Revenue = credit − debit.</li>
        <li>
          Units are entries with at least one included line. Defects: unposted &gt; {slaDays} days
          {includeReversals ? " + reversals" : ""}{includeReopen ? " + reopened months" : ""}.
        </li>
        <li>
          Sigma uses long-term convention: <code>σ = Φ⁻¹(yield) + 1.5</code>. Period rework shows from
          {" "}<code>/gl/locks/status</code>.
        </li>
        <li>
          p-Chart uses variable-n limits: <code>UCL/LCL<sub>t</sub> = p̄ ± 3√[p̄(1−p̄)/n<sub>t</sub>]</code>.
        </li>
        <li>
          XmR constants (n=2): <code>X UCL/LCL = X̄ ± 2.66·MR̄</code>; <code>MR UCL = 3.267·MR̄</code>;{" "}
          <code>MR LCL = 0</code>.
        </li>
        <li>Pareto (Account): bars show absolute magnitudes; line is cumulative share of total absolute.</li>
      </ul>
    </div>
  );
}
