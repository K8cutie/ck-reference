// app/(dashboard)/layout.tsx
import './globals.css';
import Nav from '../../components/Nav';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'ClearKeep • Dashboard',
};

export default function DashboardLayout({ children }: { children: ReactNode }) {
  // Nested layout: do NOT render <html> or <body> here (root layout handles that)
  return (
    <>
      <Nav />
      <main className="container py-6">{children}</main>
    </>
  );
}
