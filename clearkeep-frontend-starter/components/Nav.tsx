// components/Nav.tsx
import Link from "next/link";

export default function Nav() {
  return (
    <header className="border-b bg-white">
      <nav className="container flex h-14 items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="h1">ClearKeep</span>
          <span className="muted hidden sm:inline">• Dashboard</span>
        </Link>

        <ul className="flex items-center gap-4 text-sm">
          <li>
            <Link href="/sacraments/new" className="hover:underline">
              New Sacrament
            </Link>
          </li>
          <li>
            <Link href="/sacraments" className="hover:underline">
              Sacraments
            </Link>
          </li>
          <li>
            <Link href="/transactions" className="hover:underline">
              Transactions
            </Link>
          </li>
          <li>
            <Link href="/calendar" className="hover:underline">
              Calendar
            </Link>
          </li>
        </ul>
      </nav>
    </header>
  );
}
