// components/CKSidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type NavItem = {
  label: string;
  href: string;
  emoji: string;
  match?: (p: string) => boolean;
};

const NAV: NavItem[] = [
  { label: "Dashboard",    href: "/dashboard",            emoji: "🏠" },
  { label: "Calendar",     href: "/calendar",             emoji: "🗓️", match: (p) => p.startsWith("/calendar") },
  { label: "Sacraments",   href: "/sacraments/new",       emoji: "⛪",   match: (p) => p.startsWith("/sacraments") },
  { label: "Transactions", href: "/transactions/new",     emoji: "💳",   match: (p) => p.startsWith("/transactions") },

  // Accounting parent (for /gl/* and accounting tools)
  { label: "Accounting",   href: "/gl/accounts",          emoji: "💼",   match: (p) => p.startsWith("/gl/") || p === "/categories" },

  // Reports (non-accounting only)
  { label: "Reports",      href: "/reports/transactions", emoji: "📈",   match: (p) => p.startsWith("/reports") },

  { label: "Settings",     href: "/settings",             emoji: "⚙️" },
];

// Sub-links under Transactions
const TXN_LINKS = [
  { label: "New Expense", href: "/transactions/new" },
  { label: "New Income",  href: "/transactions/income/new" },
];

// Sub-links under Accounting (UPDATED: added TB, P&L, BS)
const ACCT_LINKS = [
  { label: "Chart of Accounts",     href: "/gl/accounts" },
  { label: "Journal",               href: "/gl/journal"  },
  { label: "Categories (GL Map)",   href: "/categories"  },
  { label: "Trial Balance",         href: "/gl/reports/trial-balance" },
  { label: "Profit & Loss",         href: "/gl/reports/income-statement" },
  { label: "Balance Sheet",         href: "/gl/reports/balance-sheet" },
];

// Sub-links under Reports (non-accounting)
const REPORT_LINKS = [
  { label: "Transactions", href: "/reports/transactions" },
  { label: "Parishioners", href: "/reports/parishioners" },
];

export default function CKSidebar() {
  const pathname = usePathname() || "/";
  const [openMobile, setOpenMobile] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Auto-open groups when route matches them
  const txActive   = useMemo(() => pathname.startsWith("/transactions"), [pathname]);
  const acctActive = useMemo(() => pathname.startsWith("/gl/") || pathname === "/categories", [pathname]);
  const repActive  = useMemo(() => pathname.startsWith("/reports"), [pathname]);

  const [openTx, setOpenTx] = useState(txActive);
  const [openAcct, setOpenAcct] = useState(acctActive);
  const [openReports, setOpenReports] = useState(repActive);

  useEffect(() => {
    if (txActive) setOpenTx(true);
    if (acctActive) setOpenAcct(true);
    if (repActive) setOpenReports(true);
    setOpenMobile(false);
  }, [txActive, acctActive, repActive, pathname]);

  const asideBase =
    "h-screen bg-white border-r border-gray-200 shadow-sm flex flex-col";
  const asideTint =
    "supports-[backdrop-filter]:bg-white/80 backdrop-blur lg:backdrop-blur-0";
  const widthCls = collapsed ? "w-16" : "w-64";

  const topItemBase =
    "flex items-center justify-between rounded-xl px-3 py-2 text-sm transition-colors";
  const topItemLeft = "flex items-center gap-3 min-w-0";
  const caretBtn =
    "ml-2 shrink-0 rounded-md border px-1.5 py-0.5 text-xs text-gray-600 hover:bg-gray-50";

  const TopLink = (it: NavItem, extraRight?: React.ReactNode) => {
    const active = it.match ? it.match(pathname) : pathname === it.href;
    const activeCls = active ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-100";
    return (
      <div className={`${topItemBase} ${activeCls}`} title={it.label}>
        <Link href={it.href} className={`${topItemLeft} ${collapsed ? "justify-center" : ""}`}>
          <span className="text-base">{it.emoji}</span>
          {!collapsed && <span className="truncate">{it.label}</span>}
        </Link>
        {!collapsed && extraRight}
      </div>
    );
  };

  const SubLinks = ({ items }: { items: { label: string; href: string }[] }) => (
    <div className={`mt-1 space-y-1 ${collapsed ? "hidden" : "block"}`}>
      {items.map((r) => {
        const active = pathname.startsWith(r.href) || pathname === r.href;
        return (
          <Link
            key={r.href}
            href={r.href}
            className={`ml-7 block rounded-xl px-3 py-2 text-sm ${
              active ? "bg-blue-50 text-blue-800" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {r.label}
          </Link>
        );
      })}
    </div>
  );

  const DesktopAside = (
    <aside
      className={`${asideBase} ${asideTint} ${widthCls} hidden md:flex fixed left-0 top-0 z-30`}
    >
      <div className="px-3 pb-3 pt-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-lg">✨</span>
            {!collapsed && (
              <div className="text-base font-semibold tracking-tight">ClearKeep</div>
            )}
          </div>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="rounded-lg border px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
            aria-label="Collapse sidebar"
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? "›" : "‹"}
          </button>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2">
        <div className="space-y-1">
          {/* Dashboard */}
          {TopLink(NAV[0])}
          {/* Calendar */}
          {TopLink(NAV[1])}
          {/* Sacraments */}
          {TopLink(NAV[2])}
          {/* Transactions (collapsible) */}
          <div>
            {TopLink(
              NAV[3],
              <button
                onClick={() => setOpenTx((v) => !v)}
                className={caretBtn}
                aria-label="Toggle Transactions submenu"
                title="Toggle submenu"
              >
                {openTx ? "▾" : "▸"}
              </button>
            )}
            {openTx && <SubLinks items={TXN_LINKS} />}
          </div>
          {/* Accounting (collapsible) */}
          <div>
            {TopLink(
              NAV[4],
              <button
                onClick={() => setOpenAcct((v) => !v)}
                className={caretBtn}
                aria-label="Toggle Accounting submenu"
                title="Toggle submenu"
              >
                {openAcct ? "▾" : "▸"}
              </button>
            )}
            {openAcct && <SubLinks items={ACCT_LINKS} />}
          </div>
          {/* Reports (collapsible) */}
          <div>
            {TopLink(
              NAV[5],
              <button
                onClick={() => setOpenReports((v) => !v)}
                className={caretBtn}
                aria-label="Toggle Reports submenu"
                title="Toggle submenu"
              >
                {openReports ? "▾" : "▸"}
              </button>
            )}
            {openReports && <SubLinks items={REPORT_LINKS} />}
          </div>
          {/* Settings */}
          {TopLink(NAV[6])}
        </div>

        {!collapsed && (
          <>
            <div className="my-4 h-px bg-gray-200" />
            <div className="px-1">
              <div className="mb-1 text-xs uppercase tracking-wide text-gray-500">
                Quick actions
              </div>
              <Link
                href="/sacraments/new"
                className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                ➕ New sacrament
              </Link>
            </div>
          </>
        )}
      </nav>

      {!collapsed && (
        <div className="border-t p-3 text-xs text-gray-500">TZ: Asia/Manila</div>
      )}
    </aside>
  );

  const MobileDrawer = openMobile && (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/30"
        onClick={() => setOpenMobile(false)}
      />
      <aside
        className={`${asideBase} ${asideTint} w-64 fixed left-0 top-0 z-50 md:hidden`}
      >
        <div className="flex items-center justify-between px-3 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">✨</span>
            <div className="text-base font-semibold">ClearKeep</div>
          </div>
          <button
            onClick={() => setOpenMobile(false)}
            className="rounded-lg border px-2 py-1 text-sm"
          >
            ✕
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-2">
          <div className="space-y-1">
            {TopLink(NAV[0])}
            {TopLink(NAV[1])}
            {TopLink(NAV[2])}
            <div>
              {TopLink(
                NAV[3],
                <button
                  onClick={() => setOpenTx((v) => !v)}
                  className={caretBtn}
                  aria-label="Toggle Transactions submenu"
                >
                  {openTx ? "▾" : "▸"}
                </button>
              )}
              {openTx && <SubLinks items={TXN_LINKS} />}
            </div>
            <div>
              {TopLink(
                NAV[4],
                <button
                  onClick={() => setOpenAcct((v) => !v)}
                  className={caretBtn}
                  aria-label="Toggle Accounting submenu"
                >
                  {openAcct ? "▾" : "▸"}
                </button>
              )}
              {openAcct && <SubLinks items={ACCT_LINKS} />}
            </div>
            <div>
              {TopLink(
                NAV[5],
                <button
                  onClick={() => setOpenReports((v) => !v)}
                  className={caretBtn}
                  aria-label="Toggle Reports submenu"
                >
                  {openReports ? "▾" : "▸"}
                </button>
              )}
              {openReports && <SubLinks items={REPORT_LINKS} />}
            </div>
            {TopLink(NAV[6])}
          </div>

          <div className="my-4 h-px bg-gray-200" />
          <div className="px-1 pb-4">
            <Link
              href="/sacraments/new"
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              ➕ New sacrament
            </Link>
          </div>
        </nav>
      </aside>
    </>
  );

  return (
    <>
      {/* Mobile top bar */}
      <div className="fixed left-0 top-0 z-40 flex w-full items-center justify-between border-b bg-white/80 px-3 py-2 backdrop-blur md:hidden">
        <button
          onClick={() => setOpenMobile(true)}
          className="rounded-lg border px-2 py-1 text-sm"
          aria-label="Open menu"
        >
          ☰
        </button>
        <div className="text-sm font-semibold">ClearKeep</div>
        <div className="w-8" />
      </div>

      {DesktopAside}
      {MobileDrawer}
    </>
  );
}
