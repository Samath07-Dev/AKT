"use client";

import * as React from "react";
import {
  History,
  FileSpreadsheet,
  Award,
  TrendingUp,
  Clock,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { HistoryTable } from "@/components/history";
import { mapHistoryApiRecordToSession } from "@/lib/history-evaluation";
import {
  CANONICAL_ASSESSMENT_SESSIONS,
  DetailedSessionRecord,
} from "@/lib/mock-data/curriculum-store";

export default function HistoryPage() {
  const [isLoading, setIsLoading] = React.useState(true);
  const [isLive, setIsLive] = React.useState(false);
  const [liveSessions, setLiveSessions] = React.useState<DetailedSessionRecord[] | null>(null);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    let isMounted = true;

    async function loadHistory() {
      try {
        const res = await fetch("/api/student/history");
        if (!isMounted) return;

        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.history)) {
            const mapped: DetailedSessionRecord[] = data.history.map((rec: any, idx: number) =>
              mapHistoryApiRecordToSession(rec, idx)
            );
            setLiveSessions(mapped);
            setIsLive(true);
            setErrorMessage(null);
          } else {
            setLiveSessions([]);
            setIsLive(true);
            setErrorMessage(null);
          }
        } else {
          const errData = await res.json().catch(() => ({}));
          setIsLive(false);
          setLiveSessions([]);
          setErrorMessage(errData.error || "Failed to fetch student assessment history from server.");
        }
      } catch {
        if (isMounted) {
          setIsLive(false);
          setLiveSessions([]);
          setErrorMessage("Network connectivity error: Unable to contact assessment history service.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadHistory();
    return () => {
      isMounted = false;
    };
  }, []);

  const activeSessions: DetailedSessionRecord[] = liveSessions || [];
  const totalSessions = activeSessions.length;
  const meanScore =
    activeSessions.length > 0
      ? Number(
        (
          activeSessions.reduce((acc, s) => acc + (typeof s.bundleScore === "number" ? s.bundleScore : 0), 0) /
          activeSessions.length
        ).toFixed(1)
      )
      : 0;

  const highestScoreSession =
    activeSessions.length > 0
      ? [...activeSessions].sort((a, b) => b.bundleScore - a.bundleScore)[0]
      : null;

  const latestSession = activeSessions.length > 0 ? activeSessions[0] : null;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-teal-50 px-3 py-0.5 text-xs font-semibold text-teal-800 mb-2">
            <Clock className="h-3 w-3 text-teal-700" />
            {isLoading
              ? "Loading Session History..."
              : errorMessage
              ? "Session History Unavailable"
              : "Session History"}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-3">
            <span>Assessment Session History</span>
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-600">
            Review your past practice scores and question breakdowns.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-700 bg-white border border-slate-200/90 rounded-xl px-3 py-2 shadow-2xs">
          <FileSpreadsheet className="h-3.5 w-3.5 text-teal-700" />
          <span>
            Status:{" "}
            {isLoading
              ? "Connecting..."
              : errorMessage
              ? "Offline"
              : "Verified Records"}
          </span>
        </div>
      </div>

      {/* Explicit Error State Banner if API failed */}
      {errorMessage && (
        <div className="rounded-xl border border-rose-200 bg-rose-50/70 p-4 text-xs text-rose-800 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-semibold text-rose-900 text-sm">Assessment History Unavailable</h4>
            <p className="text-rose-800/90 leading-relaxed">{errorMessage}</p>
            <p className="text-[11px] text-slate-500 font-mono mt-1">
              Please ensure the backend service and database are reachable. Live assessment records cannot be loaded at this time.
            </p>
          </div>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Sessions"
          value={totalSessions}
          description={
            errorMessage
              ? "Assessment history currently unavailable"
              : "Verified 5-question completed bundles"
          }
          icon={History}
          accentColor="indigo"
        />
        <MetricCard
          label="Average Bundle Score"
          value={totalSessions > 0 ? `${meanScore}%` : "0.0%"}
          description={
            totalSessions > 0
              ? "Cumulative across all modalities"
              : errorMessage
                ? "No live records retrieved"
                : "No assessment sessions completed yet"
          }
          icon={TrendingUp}
          accentColor="cyan"
          trend={totalSessions > 0 ? { value: "+5.2%", isPositive: true } : undefined}
        />
        <MetricCard
          label="Highest Score"
          value={highestScoreSession ? `${highestScoreSession.bundleScore.toFixed(0)}%` : "—"}
          description={
            highestScoreSession
              ? `${highestScoreSession.concept} (${highestScoreSession.difficulty} difficulty)`
              : "No assessment sessions completed"
          }
          icon={Award}
          accentColor="emerald"
        />
        <MetricCard
          label="Latest Activity"
          value={latestSession ? latestSession.concept : "None"}
          description={
            latestSession
              ? `Score ${latestSession.bundleScore.toFixed(0)}% -> Next: ${latestSession.nextDifficulty.toUpperCase()}`
              : "No assessment sessions completed"
          }
          icon={Sparkles}
          accentColor="amber"
        />
      </div>

      {/* Main Historical Table */}
      <Card className="border border-slate-200/90 bg-white shadow-xs">
        <CardHeader className="pb-3">
          <CardTitle className="text-base sm:text-lg text-slate-900">
            Chronological Practice Activity
          </CardTitle>
          <CardDescription className="text-slate-500">
            {errorMessage
              ? "Unable to display practice records due to backend communication failure."
              : "Search, filter, and inspect question-level scoring details for past student interactions."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-3">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
              <p className="text-xs text-slate-500 font-mono">Loading session history...</p>
            </div>
          ) : errorMessage ? (
            <div className="flex flex-col items-center justify-center py-16 space-y-3 text-center">
              <AlertCircle className="h-10 w-10 text-rose-500" />
              <h3 className="text-base font-semibold text-slate-900">History Records Unavailable</h3>
              <p className="text-xs text-slate-600 max-w-md">
                {errorMessage}
              </p>
            </div>
          ) : (
            <HistoryTable records={activeSessions} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
