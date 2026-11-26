"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { TopNavbar } from "@/components/layout/top-navbar";
import type { SafeStudentSession } from "@/lib/auth/session";

interface PortalClientShellProps {
  children: React.ReactNode;
  session: SafeStudentSession;
}

export function PortalClientShell({
  children,
  session,
}: PortalClientShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isMobileOpen, setIsMobileOpen] = React.useState(false);
  const [isCollapsed, setIsCollapsed] = React.useState(false);

  // Authenticated live recommendation state (no silent mock fallbacks)
  const [activeTarget, setActiveTarget] = React.useState<{
    concept: string;
    difficulty: "easy" | "medium" | "hard";
    isLoading: boolean;
    isError: boolean;
  }>({
    concept: "Loading Recommendation...",
    difficulty: "medium",
    isLoading: true,
    isError: false,
  });

  // Load authenticated student recommendation from /api/adaptive/recommend
  React.useEffect(() => {
    let isMounted = true;
    async function loadActiveTarget() {
      try {
        const res = await fetch("/api/adaptive/recommend");
        if (res.ok) {
          const data = await res.json();
          if (data && data.recommended_concept && isMounted) {
            setActiveTarget({
              concept: data.recommended_concept,
              difficulty: (data.recommended_difficulty as "easy" | "medium" | "hard") || "medium",
              isLoading: false,
              isError: false,
            });
            return;
          }
        }
        if (isMounted) {
          setActiveTarget((prev) => ({
            ...prev,
            concept: "Recommendation Unavailable",
            isLoading: false,
            isError: true,
          }));
        }
      } catch {
        if (isMounted) {
          setActiveTarget((prev) => ({
            ...prev,
            concept: "Recommendation Unavailable",
            isLoading: false,
            isError: true,
          }));
        }
      }
    }
    loadActiveTarget();
    return () => {
      isMounted = false;
    };
  }, []);

  // Update practice target dynamically when user navigates with URL parameters (e.g. in /practice)
  React.useEffect(() => {
    if (typeof window !== "undefined" && pathname === "/practice") {
      const params = new URLSearchParams(window.location.search);
      const c = params.get("concept");
      const d = params.get("difficulty");
      if (c) {
        setActiveTarget((prev) => ({
          concept: c,
          difficulty: (d as "easy" | "medium" | "hard") || prev.difficulty,
          isLoading: false,
          isError: false,
        }));
      }
    }
  }, [pathname]);

  const handleLogout = async () => {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Proceed with redirect regardless
    }
    router.push("/login");
    router.refresh();
  };

  return (
    <div className="flex min-h-screen bg-[#FAFAF8] text-[#0F172A] antialiased">
      {/* Sidebar Navigation */}
      <Sidebar
        isMobileOpen={isMobileOpen}
        onMobileClose={() => setIsMobileOpen(false)}
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(!isCollapsed)}
        studentName={session.fullName}
        studentId={session.studentId}
      />

      {/* Main Viewport */}
      <div className="flex flex-1 flex-col min-w-0">
        <TopNavbar
          onMobileMenuToggle={() => setIsMobileOpen(true)}
          activeConcept={activeTarget.concept}
          activeDifficulty={activeTarget.difficulty}
          studentName={session.fullName}
          studentId={session.studentId}
          systemStatusLabel={activeTarget.isError ? "Service Offline" : "Live Session"}
          onLogout={handleLogout}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
