// app/layout.tsx — Root layout with ClearKeep sidebar (Server Component)
import "./globals.css";     
import type { Metadata } from "next";
import CKSidebar from "../components/CKSidebar"; // <- relative path, no alias, no globals.css

export const metadata: Metadata = {
  title: "ClearKeep",
  description: "Parish management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <div className="flex">
          {/* Sidebar (fixed) */}
          <CKSidebar />

          {/* Main content area */}
          <div className="flex-1 min-h-screen md:ml-64">
            {/* spacer for the mobile top bar in CKSidebar */}
            <div className="h-10 md:hidden" />
            <main className="p-4 md:p-6">{children}</main>
          </div>
        </div>

        {/* tiny polish for scrollbars; plain <style> keeps this a Server Component */}
        <style>{`
          ::-webkit-scrollbar { width: 10px; height: 10px; }
          ::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 8px; }
          ::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
        `}</style>
      </body>
    </html>
  );
}
