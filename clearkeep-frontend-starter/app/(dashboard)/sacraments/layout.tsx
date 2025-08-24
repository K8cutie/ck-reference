// app/sacraments/layout.tsx  — Server Component (no "use client")
export default function SacramentsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="ck-sac-wrap">
      <div className="mx-auto max-w-6xl px-4 py-6">{children}</div>

      {/* Plain <style>, no styled-jsx */}
      <style>{`
        .ck-sac-wrap {
          /* soft diagonal background that is obviously new */
          background:
            radial-gradient(1200px 600px at -10% -10%, #dbeafe 0%, transparent 60%),
            radial-gradient(1000px 600px at 110% -10%, #d1fae5 0%, transparent 60%),
            radial-gradient(900px 500px at 50% 110%, #fde7f3 0%, transparent 60%);
          min-height: 100dvh;
        }
        .ck-card {
          border: 1px solid #e5e7eb;
          border-radius: 18px;
          background: #fff;
          box-shadow: 0 8px 30px rgba(0,0,0,.04);
        }
        .ck-hero {
          border-radius: 26px;
          border: 1px solid var(--sac-ring, #1d4ed8);
          background: linear-gradient(135deg, var(--sac-bg, #dbeafe) 0%, #ffffff 60%);
          box-shadow: 0 20px 50px rgba(16,24,40,.08);
        }
        .ck-pill {
          display: inline-flex; align-items: center; gap: 8px;
          border-radius: 999px; padding: 6px 12px; font-size: 0.875rem;
          border: 1px solid var(--sac-ring, #1d4ed8);
          color: var(--sac-text,#111827);
          background: var(--sac-bg,#eef2ff);
        }
        .ck-badge {
          display: inline-block; border-radius: 12px; padding: 4px 10px; font-size: 12px;
          border: 1px solid #e5e7eb; background: #f9fafb;
        }

        @media (prefers-color-scheme: dark) {
          .ck-card   { background:#0b0b0c; border-color:#262b33; box-shadow: inset 0 1px 0 rgba(255,255,255,.02); }
          .ck-hero   { background: linear-gradient(135deg, var(--sac-bg,#0b1220) 0%, #0b0b0c 60%); }
          .ck-pill   { background: color-mix(in srgb, var(--sac-ring,#111827) 12%, transparent);
                       border-color: var(--sac-ring,#30363d); color:#e5e7eb; }
          .ck-badge  { background:#111827; border-color:#262b33; color:#e5e7eb; }
          .ck-sac-wrap {
            background:
              radial-gradient(1200px 600px at -10% -10%, #0b1320 0%, transparent 60%),
              radial-gradient(1000px 600px at 110% -10%, #0f1a13 0%, transparent 60%),
              radial-gradient(900px 500px at 50% 110%, #1a0f16 0%, transparent 60%);
          }
        }

        @media print {
          .ck-sac-wrap { background: white !important; }
          .ck-card, .ck-hero { box-shadow: none !important; }
          button, .no-print { display: none !important; }
        }
      `}</style>
    </div>
  );
}
