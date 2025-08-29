"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

type NavItem = {
  label: string;
  href: string;
  emoji: string; // use Unicode escapes to avoid encoding issues
  match?: (p: string) => boolean;
};

// Top-level items (some act as group headers via match + sublinks)
const NAV: NavItem[] = [
  { label: "Dashboard",    href: "/dashboard",            emoji: "\uD83C\uDFE0" }, // 🏠
  { label: "Calendar",     href: "/calendar",             emoji: "\uD83D\uDCC5", match: (p) => p.startsWith("/calendar") }, // 📅
  { label: "Sacraments",   href: "/sacraments/new",       emoji: "\u26EA",       match: (p) => p.startsWith("/sacraments") }, // ⛪
  { label: "Transactions", href: "/transactions/new",     emoji: "\uD83D\uDCB3", match: (p) => p.startsWith("/transactions") }, // 💳

  // People group (employees live under /people/*)
  {
    label: "People",
    href: "/people/employees",
    emoji: "\uD83D\uDC65",
    match: (p) => p.startsWith("/people"),
  }, // 👥

  // Accounting group (GL + Payroll belong here)
  {
    label: "Accounting",
    href: "/gl/accounts",
    emoji: "\uD83D\uDCBC",
    match: (p) => p.startsWith("/gl/") || p === "/categories" || p === "/payroll",
  }, // 💼

  { label: "Reports",      href: "/reports/transactions", emoji: "\uD83D\uDCC8", match: (p) => p.startsWith("/reports") }, // 📈
  { label: "Settings",     href: "/settings",             emoji: "\u2699\uFE0F" }, // ⚙️
];

// Sub-links under Transactions
const TXN_LINKS = [
  { label: "New Expense", href: "/transactions/new" },
  { label: "New Income",  href: "/transactions/income/new" },
];

// Sub-links under People — point “New Employee” to /people/new-employee
const PEOPLE_LINKS = [
  { label: "Employees",     href: "/people/employees" },
  { label: "New Employee",  href: "/people/new-employee" },
];

// Sub-links under Accounting (no Payroll creation here; just core GL pages)
const ACCT_LINKS = [
  { label: "Chart of Accounts",   href: "/gl/accounts" },
  { label: "Journal",             href: "/gl/journal"  },
  { label: "Categories (GL Map)", href: "/categories"  },
  { label: "Period Controls",     href: "/gl/periods"  },
  { label: "Trial Balance",       href: "/gl/reports/trial-balance" },
  { label: "Profit & Loss",       href: "/gl/reports/income-statement" },
  { label: "Balance Sheet",       href: "/gl/reports/balance-sheet" },
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

  // Auto-open groups based on current route
  const txActive     = useMemo(() => pathname.startsWith("/transactions"), [pathname]);
  const peopleActive = useMemo(() => pathname.startsWith("/people"), [pathname]);
  const acctActive   = useMemo(() => pathname.startsWith("/gl/") || pathname === "/categories" || pathname === "/payroll", [pathname]);
  const repActive    = useMemo(() => pathname.startsWith("/reports"), [pathname]);

  const [openTx, setOpenTx] = useState(txActive);
  const [openPeople, setOpenPeople] = useState(peopleActive);
  const [openAcct, setOpenAcct] = useState(acctActive);
  const [openReports, setOpenReports] = useState(repActive);

  useEffect(() => {
    if (txActive) setOpenTx(true);
    if (peopleActive) setOpenPeople(true);
    if (acctActive) setOpenAcct(true);
    if (repActive) setOpenReports(true);
    setOpenMobile(false);
  }, [txActive, peopleActive, acctActive, repActive, pathname]);

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
            <span className="text-lg">{"\u2728"}</span> {/* ✨ */}
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
            {collapsed ? "\u203A" : "\u2039"} {/* › or ‹ */}
          </button>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2">
        <div className="space-y-1">
          {TopLink(NAV[0])} {/* Dashboard */}
          {TopLink(NAV[1])} {/* Calendar */}
          {TopLink(NAV[2])} {/* Sacraments */}

          {/* Transactions */}
          <div>
            {TopLink(
              NAV[3],
              <button
                onClick={() => setOpenTx((v) => !v)}
                className={caretBtn}
                aria-label="Toggle Transactions submenu"
                title="Toggle submenu"
              >
                {openTx ? "\u25BE" : "\u25B8"} {/* ▾ or ▸ */}
              </button>
            )}
            {openTx && <SubLinks items={TXN_LINKS} />}
          </div>

          {/* People */}
          <div>
            {TopLink(
              NAV[4],
              <button
                onClick={() => setOpenPeople((v) => !v)}
                className={caretBtn}
                aria-label="Toggle People submenu"
                title="Toggle submenu"
              >
                {openPeople ? "\u25BE" : "\u25B8"}
              </button>
            )}
            {openPeople && <SubLinks items={PEOPLE_LINKS} />}
          </div>

          {/* Accounting */}
          <div>
            {TopLink(
              NAV[5],
              <button
                onClick={() => setOpenAcct((v) => !v)}
                className={caretBtn}
                aria-label="Toggle Accounting submenu"
                title="Toggle submenu"
              >
                {openAcct ? "\u25BE" : "\u25B8"}
              </button>
            )}
            {openAcct && <SubLinks items={ACCT_LINKS} />}
          </div>

          {/* Reports */}
          <div>
            {TopLink(
              NAV[6],
              <button
                onClick={() => setOpenReports((v) => !v)}
                className={caretBtn}
                aria-label="Toggle Reports submenu"
                title="Toggle submenu"
              >
                {openReports ? "\u25BE" : "\u25B8"}
              </button>
            )}
            {openReports && <SubLinks items={REPORT_LINKS} />}
          </div>

          {TopLink(NAV[7])} {/* Settings */}
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
                {"\u2795"} New sacrament {/* ➕ */}
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
            <span className="text-lg">{"\u2728"}</span>
            <div className="text-base font-semibold">ClearKeep</div>
          </div>
          <button
            onClick={() => setOpenMobile(false)}
            className="rounded-lg border px-2 py-1 text-sm"
            aria-label="Close menu"
          >
            {"\u2716"} {/* ✖ */}
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
                <button onClick={() => setOpenTx((v) => !v)} className={caretBtn} aria-label="Toggle Transactions submenu">
                  {openTx ? "\u25BE" : "\u25B8"}
                </button>
              )}
              {openTx && <SubLinks items={TXN_LINKS} />}
            </div>
            <div>
              {TopLink(
                NAV[4],
                <button onClick={() => setOpenPeople((v) => !v)} className={caretBtn} aria-label="Toggle People submenu">
                  {openPeople ? "\u25BE" : "\u25B8"}
                </button>
              )}
              {openPeople && <SubLinks items={PEOPLE_LINKS} />}
            </div>
            <div>
              {TopLink(
                NAV[5],
                <button onClick={() => setOpenAcct((v) => !v)} className={caretBtn} aria-label="Toggle Accounting submenu">
                  {openAcct ? "\u25BE" : "\u25B8"}
                </button>
              )}
              {openAcct && <SubLinks items={ACCT_LINKS} />}
            </div>
            {TopLink(NAV[6])}
            {TopLink(NAV[7])}
          </div>

          <div className="my-4 h-px bg-gray-200" />
          <div className="px-1 pb-4">
            <Link
              href="/sacraments/new"
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              {"\u2795"} New sacrament
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
          {"\u2630"} {/* ☰ */}
        </button>
        <div className="text-sm font-semibold">ClearKeep</div>
        <div className="w-8" />
      </div>

      {DesktopAside}
      {MobileDrawer}
    </>
  );
}
