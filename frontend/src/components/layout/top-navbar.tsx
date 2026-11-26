"use client";

import * as React from "react";
import { Menu, Bell, Cpu, Sparkles, LogOut } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DEMO_STUDENT, ACTIVE_DEMONSTRATION_TARGET } from "@/lib/mock-data/curriculum-store";

interface TopNavbarProps {
  onMobileMenuToggle: () => void;
  activeConcept?: string;
  activeDifficulty?: "easy" | "medium" | "hard";
  studentName?: string;
  studentId?: string;
  systemStatusLabel?: string;
  onLogout?: () => void;
}

export function TopNavbar({
  onMobileMenuToggle,
  activeConcept = ACTIVE_DEMONSTRATION_TARGET.concept,
  activeDifficulty = ACTIVE_DEMONSTRATION_TARGET.difficulty,
  studentName = DEMO_STUDENT.fullName,
  studentId = DEMO_STUDENT.studentId,
  systemStatusLabel = "Live Session",
  onLogout,
}: TopNavbarProps) {
  const difficultyBadgeVariant = {
    easy: "success" as const,
    medium: "warning" as const,
    hard: "danger" as const,
  };

  const [notificationsOpen, setNotificationsOpen] = React.useState(false);
  const notificationsRef = React.useRef<HTMLDivElement>(null);

  // Close on outside click
  React.useEffect(() => {
    if (!notificationsOpen) return;
    function handlePointerDown(event: PointerEvent) {
      if (
        notificationsRef.current &&
        !notificationsRef.current.contains(event.target as Node)
      ) {
        setNotificationsOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [notificationsOpen]);

  // Close on Escape
  React.useEffect(() => {
    if (!notificationsOpen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setNotificationsOpen(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [notificationsOpen]);

  return (
    <header className="sticky top-0 z-20 flex h-16 w-full items-center justify-between border-b border-slate-200/90 bg-white/85 px-4 sm:px-6 backdrop-blur-md shadow-xs">
      {/* Left: Mobile Toggle & Active KC Indicator */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMobileMenuToggle}
          aria-label="Open navigation menu"
          className="lg:hidden flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
        >
          <Menu className="h-5 w-5" />
        </button>

        {/* Active Target Concept Banner */}
        <div className="hidden sm:flex items-center gap-2 rounded-lg border border-slate-200/80 bg-slate-50/80 px-3 py-1.5 text-xs shadow-xs">
          <Sparkles className="h-3.5 w-3.5 text-teal-600" />
          <span className="text-slate-500 font-medium">Practice Target:</span>
          <span className="font-semibold text-slate-900">{activeConcept}</span>
          <Badge
            variant={difficultyBadgeVariant[activeDifficulty]}
            size="sm"
            className="uppercase tracking-wider font-mono text-[9px]"
          >
            {activeDifficulty}
          </Badge>
        </div>
      </div>

      {/* Right: Engine Status & Student Profile */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* System Status Pill */}
        <div className="hidden md:flex items-center gap-1.5 rounded-full border border-teal-200 bg-teal-50/80 px-3 py-1 text-[11px] font-medium text-teal-800">
          <Cpu className="h-3 w-3 text-teal-600" />
          <span>{systemStatusLabel}</span>
        </div>

        {/* Notifications Bell with Popover */}
        <div ref={notificationsRef} className="relative">
          <button
            type="button"
            onClick={() => setNotificationsOpen((prev) => !prev)}
            aria-label="Notifications"
            aria-expanded={notificationsOpen}
            aria-haspopup="dialog"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <Bell className="h-4 w-4" />
          </button>

          {notificationsOpen && (
            <div
              role="dialog"
              aria-label="Notifications"
              className="absolute right-0 top-11 z-30 w-72 rounded-xl border border-slate-200 bg-white shadow-xl ring-1 ring-slate-900/5"
            >
              {/* Popover header */}
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <span className="text-xs font-semibold tracking-wide text-slate-800 uppercase font-mono">
                  Notifications
                </span>
                <button
                  type="button"
                  onClick={() => setNotificationsOpen(false)}
                  aria-label="Close notifications"
                  className="flex h-6 w-6 items-center justify-center rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors text-xs cursor-pointer"
                >
                  ✕
                </button>
              </div>

              {/* Empty state */}
              <div className="flex flex-col items-center gap-2 px-4 py-6 text-center">
                <Bell className="h-7 w-7 text-slate-300" aria-hidden="true" />
                <p className="text-sm font-medium text-slate-700">
                  No new notifications
                </p>
                <p className="text-xs text-slate-400">
                  You&apos;re all caught up.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Profile Tile */}
        <div className="flex items-center gap-2.5 pl-2 sm:pl-3 border-l border-slate-200">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-700 text-white font-bold text-xs shadow-xs">
            {studentName
              .split(" ")
              .map((n) => n[0])
              .join("")
              .toUpperCase()}
          </div>
          <div className="hidden sm:flex flex-col text-left">
            <span className="text-xs font-semibold text-slate-900 leading-tight">
              {studentName}
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              {studentId}
            </span>
          </div>
        </div>

        {/* Sign Out Button */}
        {onLogout && (
          <button
            type="button"
            onClick={onLogout}
            title="Sign Out"
            aria-label="Sign Out"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-500 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50 transition-colors cursor-pointer"
          >
            <LogOut className="h-4 w-4" />
          </button>
        )}
      </div>
    </header>
  );
}
