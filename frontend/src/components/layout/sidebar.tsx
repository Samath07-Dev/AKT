"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  LineChart,
  Sparkles,
  Code2,
  History,
  GraduationCap,
  ChevronLeft,
  ChevronRight,
  X,
  User,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

export const NAV_ITEMS: NavItem[] = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    title: "Knowledge Analytics",
    href: "/analytics",
    icon: LineChart,
  },
  {
    title: "Adaptive Learning",
    href: "/adaptive-learning",
    icon: Sparkles,
    badge: "AI",
  },
  {
    title: "Practice Arena",
    href: "/practice",
    icon: Code2,
  },
  {
    title: "Assessment History",
    href: "/history",
    icon: History,
  },
  {
    title: "Student Profile",
    href: "/profile",
    icon: User,
  },
];

interface SidebarProps {
  isMobileOpen?: boolean;
  onMobileClose?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  studentName?: string;
  studentId?: string;
}

export function Sidebar({
  isMobileOpen = false,
  onMobileClose,
  isCollapsed = false,
  onToggleCollapse,
  studentName,
  studentId = "S001",
}: SidebarProps) {
  const pathname = usePathname();

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between p-4 bg-white border-r border-slate-200/90 shadow-xs">
      {/* Brand Header */}
      <div>
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <Link
            href="/dashboard"
            className="flex items-center gap-3 transition-opacity hover:opacity-90"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-700 text-white shadow-xs">
              <GraduationCap className="h-5 w-5" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col">
                <span className="text-sm font-bold tracking-tight text-slate-900">
                  Adaptive Tutor
                </span>
                <span className="text-[10px] font-mono tracking-wider uppercase font-semibold text-teal-700">
                  Learning Platform
                </span>
              </div>
            )}
          </Link>

          {/* Desktop collapse toggle */}
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden lg:flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              {isCollapsed ? (
                <ChevronRight className="h-3.5 w-3.5" />
              ) : (
                <ChevronLeft className="h-3.5 w-3.5" />
              )}
            </button>
          )}

          {/* Mobile close button */}
          {onMobileClose && (
            <button
              type="button"
              onClick={onMobileClose}
              aria-label="Close menu"
              className="lg:hidden flex h-8 w-8 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-900 cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Navigation Section */}
        <nav aria-label="Main Navigation" className="mt-5 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onMobileClose}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "group flex items-center gap-3 rounded-lg px-3 py-2 text-xs font-medium transition-all duration-150 select-none outline-none focus-visible:ring-2 focus-visible:ring-teal-600",
                  isActive
                    ? "bg-teal-50/90 text-teal-900 font-semibold border border-teal-200/80 shadow-xs"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900 border border-transparent"
                )}
                title={isCollapsed ? item.title : undefined}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    isActive
                      ? "text-teal-700"
                      : "text-slate-400 group-hover:text-slate-600"
                  )}
                />
                {!isCollapsed && (
                  <span className="flex-1 truncate tracking-tight">
                    {item.title}
                  </span>
                )}
                {!isCollapsed && item.badge && (
                  <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold tracking-wider uppercase bg-teal-100 text-teal-800 border border-teal-200">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer / Student Meta Tile */}
      <div className="pt-3 border-t border-slate-100">
        {!isCollapsed ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-teal-600" />
              <span className="text-[11px] font-semibold text-slate-800 truncate">
                {studentName ? studentName : `Active Session (${studentId})`}
              </span>
            </div>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">Student ID</span>
              <span className="text-[11px] font-mono font-bold text-teal-800">
                {studentId}
              </span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <span
              className="h-2.5 w-2.5 rounded-full bg-teal-600"
              title={studentName ? `${studentName} (${studentId})` : `Session (${studentId})`}
            />
          </div>
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          "hidden lg:flex flex-col shrink-0 h-screen sticky top-0 transition-all duration-200 z-30",
          isCollapsed ? "w-20" : "w-64"
        )}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Backdrop & Drawer */}
      {isMobileOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Navigation Menu"
          className="lg:hidden fixed inset-0 z-50 flex"
        >
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={onMobileClose}
            aria-hidden="true"
          />
          <div className="relative flex flex-col w-72 max-w-[80vw] h-full z-10 shadow-xl">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
