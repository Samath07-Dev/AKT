"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  User,
  Shield,
  LogOut,
  Clock,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";

interface StudentProfile {
  studentId: string;
  username: string;
  fullName: string;
  email?: string;
}

interface ProfileKCItem {
  name: string;
  mastery: number;
  uncertainty: number;
  status: "Mastered" | "In Progress" | "Focus Area" | "Not Attempted";
  difficulty: "easy" | "medium" | "hard";
  attempts: number;
  hasAttempts: boolean;
}

interface ProfileSessionItem {
  id: string;
  date: string;
  concept: string;
  difficulty: "easy" | "medium" | "hard";
  bundleScore: number;
  rawTimestamp?: string;
}

const CANONICAL_KC_NAMES = [
  "Variables",
  "Conditionals",
  "Loops",
  "Functions",
  "Arrays",
  "Syntax",
  "OOP",
  "Dictionaries",
  "File Handling",
  "Exception Handling",
];

export default function ProfilePage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(true);
  const [isLive, setIsLive] = React.useState(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = React.useState(false);

  const [student, setStudent] = React.useState<StudentProfile | null>(null);
  const [kcs, setKcs] = React.useState<ProfileKCItem[]>([]);
  const [sessions, setSessions] = React.useState<ProfileSessionItem[]>([]);

  React.useEffect(() => {
    let isMounted = true;

    async function loadProfileData() {
      try {
        const [meRes, masteryRes, historyRes] = await Promise.all([
          fetch("/api/auth/me"),
          fetch("/api/student/mastery"),
          fetch("/api/student/history"),
        ]);

        if (!isMounted) return;

        // 1. Process Authenticated Session Identity
        if (!meRes.ok) {
          if (meRes.status === 401) {
            router.push("/login");
            return;
          }
          throw new Error("Unable to retrieve authenticated student identity from session.");
        }

        const meData = await meRes.json();
        if (!meData?.student?.studentId) {
          throw new Error("Authentication response did not contain a valid student profile.");
        }

        const authenticatedStudent: StudentProfile = {
          studentId: meData.student.studentId,
          username: meData.student.username || "",
          fullName: meData.student.fullName || meData.student.username || "Student",
          email: meData.student.email || undefined,
        };
        setStudent(authenticatedStudent);

        // 2. Process Assessment History
        const conceptAttemptsMap = new Map<string, number>();
        let mappedSessions: ProfileSessionItem[] = [];

        if (historyRes.ok) {
          const hData = await historyRes.json();
          if (hData && Array.isArray(hData.history)) {
            for (const rec of hData.history) {
              if (rec.concept) {
                conceptAttemptsMap.set(
                  rec.concept,
                  (conceptAttemptsMap.get(rec.concept) || 0) + 1
                );
              }
            }

            mappedSessions = hData.history.map((rec: any, idx: number) => ({
              id: rec._id || `sess_${idx}`,
              date: rec.timestamp
                ? new Date(rec.timestamp).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })
                : "Recent",
              rawTimestamp: rec.timestamp,
              concept: rec.concept || "Variables",
              difficulty: (rec.difficulty as "easy" | "medium" | "hard") || "medium",
              bundleScore: typeof rec.bundle_average_score === "number" ? rec.bundle_average_score : 0,
            }));
            setSessions(mappedSessions);
          }
        }

        // 3. Process Live Knowledge State
        if (masteryRes.ok) {
          const mData = await masteryRes.json();
          const stateObj = mData?.knowledge_state || {};
          const diffsObj = mData?.concept_difficulties || {};

          const mappedKCs: ProfileKCItem[] = CANONICAL_KC_NAMES.map((concept) => {
            const data = stateObj[concept];
            const masteryVal = data && typeof data.mastery === "number" ? data.mastery * 100 : 30.0;
            const uncVal = data && typeof data.uncertainty === "number" ? data.uncertainty * 100 : 50.0;
            const rawAttempts =
              data && typeof data.attempts === "number"
                ? data.attempts
                : data && Array.isArray(data.history)
                ? data.history.length
                : 0;
            const historyAttempts = conceptAttemptsMap.get(concept) || 0;
            const totalAttempts = Math.max(rawAttempts, historyAttempts);
            const hasAttempts = totalAttempts > 0;

            const status: "Mastered" | "In Progress" | "Focus Area" | "Not Attempted" = !hasAttempts
              ? "Not Attempted"
              : masteryVal >= 75
              ? "Mastered"
              : masteryVal >= 45
              ? "In Progress"
              : "Focus Area";

            const difficulty: "easy" | "medium" | "hard" = diffsObj[concept] || "medium";

            return {
              name: concept,
              mastery: Number(masteryVal.toFixed(1)),
              uncertainty: Number(uncVal.toFixed(1)),
              status,
              difficulty,
              attempts: totalAttempts,
              hasAttempts,
            };
          });

          setKcs(mappedKCs);
          setIsLive(true);
        } else {
          throw new Error("Failed to load live knowledge competency state.");
        }
      } catch (err: any) {
        if (isMounted) {
          setErrorMessage(err?.message || "Failed to load student profile data.");
          setIsLive(false);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadProfileData();

    return () => {
      isMounted = false;
    };
  }, [router]);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {
      // Proceed with redirect regardless
    }
    router.push("/login");
    router.refresh();
  };

  const totalSessions = sessions.length;
  const overallAccuracy =
    totalSessions > 0
      ? (sessions.reduce((acc, s) => acc + s.bundleScore, 0) / totalSessions).toFixed(1)
      : "0.0";
  const masteredCount = kcs.filter((kc) => kc.hasAttempts && kc.mastery >= 75).length;
  const focusAreasCount = kcs.filter((kc) => kc.hasAttempts && kc.mastery < 45).length;

  const latestSession = sessions.length > 0 ? sessions[0] : null;
  const lastActivityDisplay = latestSession?.rawTimestamp
    ? new Date(latestSession.rawTimestamp).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      }) +
      " at " +
      new Date(latestSession.rawTimestamp).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : latestSession
    ? latestSession.date
    : "Not available";

  const initials = (student?.fullName || "Student")
    .split(" ")
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-teal-50 px-3 py-0.5 text-xs font-semibold text-teal-800 mb-2">
            <User className="h-3 w-3" />
            {isLoading
              ? "Loading Student Profile..."
              : isLive
              ? "Authenticated Student Profile"
              : "Student Profile (Offline)"}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Student Account &amp; Identity
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-600">
            Manage your student profile, view learning competency states, and inspect active sessions.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={handleLogout}
          isLoading={isLoggingOut}
          className="gap-2 text-rose-700 border-rose-200 hover:bg-rose-50 text-xs"
        >
          <LogOut className="h-3.5 w-3.5" />
          <span>Sign Out</span>
        </Button>
      </div>

      {/* Explicit Error State Banner if API failed */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50/80 p-4 text-xs text-rose-900 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-semibold text-rose-950 text-sm">Student Profile Unavailable</h4>
            <p className="text-rose-800 leading-relaxed">{errorMessage}</p>
            <p className="text-[11px] text-slate-600 font-mono mt-1">
              Please verify the backend service and database are online. Live profile records cannot be loaded at this time.
            </p>
          </div>
        </div>
      )}

      {/* 1. Primary Student Identity Card */}
      <Card className="border-slate-200/90 bg-white shadow-xs">
        <div className="p-5 sm:p-6">
          {isLoading ? (
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="flex items-center gap-4">
                <Skeleton className="h-16 w-16 rounded-2xl" />
                <div className="space-y-2">
                  <Skeleton className="h-6 w-48" />
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-56" />
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-16 w-20 rounded-xl" />
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-teal-700 via-teal-600 to-sky-600 text-white font-bold text-xl shadow-md shadow-teal-700/20">
                  {initials}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg sm:text-xl font-bold text-slate-900">
                      {student?.fullName || "Student"}
                    </h2>
                    <Badge variant="info" size="sm" className="font-mono text-[10px]">
                      {student?.studentId || "—"}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600 font-mono">
                    <span>@{student?.username || "student"}</span>
                    <span>&bull;</span>
                    <span>{student?.email ? student.email : "Email: Not available"}</span>
                  </div>
                  <p className="text-xs text-slate-600 font-sans">
                    Python Core Programming (10 Knowledge Components)
                  </p>
                </div>
              </div>

              {/* Quick stats badge group */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono text-xs">
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-center">
                  <span className="text-[10px] text-slate-500 block uppercase">Sessions</span>
                  <span className="text-base font-bold text-slate-900">
                    {totalSessions}
                  </span>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-center">
                  <span className="text-[10px] text-slate-500 block uppercase">Accuracy</span>
                  <span className="text-base font-bold text-emerald-700">
                    {overallAccuracy}%
                  </span>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-center">
                  <span className="text-[10px] text-slate-500 block uppercase">Mastered</span>
                  <span className="text-base font-bold text-teal-700">
                    {masteredCount} / 10
                  </span>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-center">
                  <span className="text-[10px] text-slate-500 block uppercase">Focus Areas</span>
                  <span className="text-base font-bold text-amber-700">
                    {focusAreasCount}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* 2. Knowledge Mastery Summary & Account Preferences Two-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Competency State Summary */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="border-slate-200/90 bg-white shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base sm:text-lg text-slate-900">
                    Curriculum Competencies Overview
                  </CardTitle>
                  <CardDescription className="text-xs text-slate-600">
                    Your current mastery across Python topics.
                  </CardDescription>
                </div>
                <Link href="/analytics">
                  <Button variant="ghost" size="sm" className="text-xs text-teal-700 hover:text-teal-800 hover:bg-teal-50">
                    Analytics View
                  </Button>
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {isLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <Skeleton key={i} className="h-20 rounded-lg" />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {kcs.map((kc) => {
                    const statusVariant =
                      kc.status === "Not Attempted"
                        ? ("default" as const)
                        : kc.mastery >= 75
                        ? ("success" as const)
                        : kc.mastery >= 45
                        ? ("warning" as const)
                        : ("danger" as const);

                    return (
                      <div
                        key={kc.name}
                        className="rounded-lg border border-slate-200/80 bg-slate-50/60 hover:bg-slate-100/60 transition-colors p-3 space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-900">
                            {kc.name}
                          </span>
                          <Badge variant={statusVariant} size="sm">
                            {kc.status}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between text-[11px] font-mono text-slate-600">
                          <span>Mastery</span>
                          <span className="text-slate-900 font-bold">
                            {kc.hasAttempts ? `${kc.mastery.toFixed(1)}%` : "—"}
                          </span>
                        </div>
                        <Progress
                          value={kc.hasAttempts ? kc.mastery : 0}
                          variant={kc.mastery >= 75 ? "mastery" : "default"}
                          size="sm"
                        />
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Col: Account & Session Diagnostics */}
        <div className="space-y-4">
          <Card className="border-slate-200/90 bg-white shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-base sm:text-lg text-slate-900">
                Account Information
              </CardTitle>
              <CardDescription className="text-xs text-slate-600">
                Authenticated student attributes
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 font-mono text-xs text-slate-700">
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Student ID</span>
                <span className="text-slate-900 font-bold">
                  {student?.studentId ?? "Not available"}
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Enrolled Since</span>
                <span className="text-slate-500">Not available</span>
              </div>
              <div className="flex items-center justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Session Mode</span>
                <span className={isLive ? "text-emerald-700 font-bold" : "text-amber-700 font-bold"}>
                  {isLive ? "Live Authenticated Session" : isLoading ? "Connecting..." : "Offline / Unreachable"}
                </span>
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-slate-500">Last Activity</span>
                <span className="text-slate-700">{lastActivityDisplay}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
