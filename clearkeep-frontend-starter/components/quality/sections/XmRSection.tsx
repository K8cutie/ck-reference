"use client";

import React from "react";
import { XmRChart } from "../XmR";

export type XmRSeries = {
  labels: string[];
  x: number[];
  mr: number[];
  x_ucl: number[];
  x_lcl: number[];
  x_cl: number[];
  mr_ucl: number[];
  mr_lcl: number[];
  mr_cl: number[];
  xbar: number;
  mrbar: number;
  /** Title above the chart, e.g., "Range A (...)" */
  title: string;
};

type Props = {
  /** Required: Range A series */
  a: XmRSeries;
  /** Optional: Range B series (renders a second chart when present) */
  b?: XmRSeries | null;
  /** Optional custom section title */
  heading?: string;
};

/**
 * XmRSection — presentational wrapper for one or two XmR charts.
 * Pure UI; computes nothing. Safe to reuse anywhere.
 */
export default function XmRSection({ a, b, heading }: Props) {
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 12, background: "#fff" }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>
        {heading ?? "Quality — XmR (Individuals & Moving Range of totals)"}
      </div>

      <XmRChart
        labels={a.labels}
        x={a.x}
        mr={a.mr}
        x_ucl={a.x_ucl}
        x_lcl={a.x_lcl}
        x_cl={a.x_cl}
        mr_ucl={a.mr_ucl}
        mr_lcl={a.mr_lcl}
        mr_cl={a.mr_cl}
        xbar={a.xbar}
        mrbar={a.mrbar}
        title={a.title}
      />

      {b ? (
        <div style={{ marginTop: 12 }}>
          <XmRChart
            labels={b.labels}
            x={b.x}
            mr={b.mr}
            x_ucl={b.x_ucl}
            x_lcl={b.x_lcl}
            x_cl={b.x_cl}
            mr_ucl={b.mr_ucl}
            mr_lcl={b.mr_lcl}
            mr_cl={b.mr_cl}
            xbar={b.xbar}
            mrbar={b.mrbar}
            title={b.title}
          />
        </div>
      ) : null}
    </div>
  );
}
