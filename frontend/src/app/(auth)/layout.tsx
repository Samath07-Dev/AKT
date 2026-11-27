import * as React from "react";
import Link from "next/link";
import { GraduationCap } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased">
      {/* Top Brand Bar */}
      <header className="flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-600 text-white shadow-sm">
            <GraduationCap className="h-4.5 w-4.5" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold tracking-tight text-slate-900">
              Adaptive Tutor
            </span>
            <span className="text-[10px] font-mono text-teal-600">
              Learning Platform
            </span>
          </div>
        </Link>
        <span className="text-xs font-mono text-slate-500">
          Student Portal
        </span>
      </header>

      {/* Main Centered Content */}
      <main className="flex flex-1 items-center justify-center p-4 sm:p-6 lg:p-8">
        <div className="w-full max-w-md">{children}</div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500 font-mono">
        Adaptive Tutor &middot; Student Learning Platform
      </footer>
    </div>
  );
}

