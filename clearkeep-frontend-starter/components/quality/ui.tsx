"use client";

import React from "react";

/** Lightweight section wrapper with a bold title and body */
export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginTop: 16 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>{title}</h2>
      <div>{children}</div>
    </section>
  );
}

/** Small card used for KPI/summary tiles */
export function Card({ title, value, sub }: { title: string; value: string; sub?: string }) {
  return (
    <div style={{ padding: 12, border: "1px solid #e5e7eb", borderRadius: 8, background: "#fff" }}>
      <div style={{ fontSize: 12, color: "#6b7280" }}>{title}</div>
      <div style={{ fontSize: 20, fontWeight: 700 }}>{value}</div>
      {sub ? <div style={{ fontSize: 12, color: "#6b7280" }}>{sub}</div> : null}
    </div>
  );
}
