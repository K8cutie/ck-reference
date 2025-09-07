"use client";

import React from "react";
import { PChart } from "../PChart";

export type PSeries = {
  labels: string[];
  p: number[];
  ucl: number[];
  lcl: number[];
  pbar: number;
  n: number[];
  /** Optional flag to display in the child chart (same as your page prop) */
  includeReversals?: boolean;
  /** Title shown above the individual chart, e.g. "Range A (...)" */
  title: string;
};

type Props = {
  /** Required: Range A series */
  a: PSeries;
  /** Optional: Range B series (renders second chart when present) */
  b?: PSeries | null;
  /** Optional custom section title (defaults to p-Chart heading) */
  heading?: string;
};

/**
 * PChartSection — presentational wrapper for one or two p-Charts.
 * Pure UI; calculates nothing. Safe to reuse anywhere.
 */
export default function PChartSection({ a, b, heading }: Props) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 12, background: "#fff" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>
        {heading ?? "Quality — p-Chart (defect proportion by period)"}
      </div>

      <PChart
        labels={a.labels}
        p={a.p}
        ucl={a.ucl}
        lcl={a.lcl}
        pbar={a.pbar}
        n={a.n}
        title={a.title}
        includeReversals={a.includeReversals}
      />

      {b ? (
        <div style={{ marginTop: 12 }}>
          <PChart
            labels={b.labels}
            p={b.p}
            ucl={b.ucl}
            lcl={b.lcl}
            pbar={b.pbar}
            n={b.n}
            title={b.title}
            includeReversals={b.includeReversals}
          />
        </div>
      ) : null}
    </div>
  );
}
