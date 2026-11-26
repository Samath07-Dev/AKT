"use client";

import * as React from "react";
import Link from "next/link";
import {
  Award,
  CheckCircle2,
  TrendingUp,
  Target,
  Sparkles,
  ArrowRight,
  Clock,
  BookOpen,
  Zap,
  Cpu,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  CANONICAL_KNOWLEDGE_COMPETENCIES,
  CANONICAL_ASSESSMENT_SESSIONS,
  DetailedSessionRecord,
  calculateMeanBundleScore,
  ACTIVE_DEMONSTRATION_TARGET,
} from "@/lib/mock-data/curriculum-store";
import { resolveCodeTestsTotal } from "@/components/history/history-table";

interface DashboardKCItem {
  name: string;
  mastery: number;
  uncertainty: number;
  status: "Mastered" | "In Progress" | "Focus Area" | "Not Attempted";
  difficulty: "easy" | "medium" | "hard";
  recommendedModality: string;
  explanation: string;
  attempts: number;
  hasAttempts: boolean;
}

const canonicalAsDashboardKCs: DashboardKCItem[] = CANONICAL_KNOWLEDGE_COMPETENCIES.map((kc) => ({
  ...kc,
  attempts: 1,
  hasAttempts: true,
}));

export default function DashboardPage() {
  const [isLoading, setIsLoading] = React.useState(true);
  const [isLive, setIsLive] = React.useState(false);
  const [isFallbackMode, setIsFallbackMode] = React.useState(false);
  const [liveKCs, setLiveKCs] = React.useState<DashboardKCItem[] | null>(null);
  const [liveSessions, setLiveSessions] = React.useState<DetailedSessionRecord[] | null>(null);
  const [liveRecommendation, setLiveRecommendation] = React.useState<{
    name: string;
    difficulty: "easy" | "medium" | "hard";
    mastery: number;
    uncertainty: number;
    priorityScore: number;
    explanation: string;
    recommendedModality: string;
  } | null>(null);
  const [isRecommendLoading, setIsRecommendLoading] = React.useState(true);
  const [isRecommendError, setIsRecommendError] = React.useState(false);

  React.useEffect(() => {
    let isMounted = true;

    async function loadDashboardData() {
      try {
        const [masteryRes, historyRes, recommendRes] = await Promise.all([
          fetch("/api/student/mastery"),
          fetch("/api/student/history"),
          fetch("/api/adaptive/recommend"),
        ]);

        if (!isMounted) return;

        let masteryLoaded = false;
        let historyLoaded = false;

        // Process Live Recommendation
        if (recommendRes.ok) {
          const recData = await recommendRes.json();
          if (recData && recData.recommended_concept && isMounted) {
            setLiveRecommendation({
              name: recData.recommended_concept,
              difficulty: (recData.recommended_difficulty as "easy" | "medium" | "hard") || "medium",
              mastery: typeof recData.concept_mastery === "number" ? Number((recData.concept_mastery * 100).toFixed(1)) : 30.0,
              uncertainty: typeof recData.concept_uncertainty === "number" ? Number((recData.concept_uncertainty * 100).toFixed(1)) : 50.0,
              priorityScore: typeof recData.priority_score === "number" ? Number(recData.priority_score.toFixed(4)) : 1.0500,
              explanation: recData.scaffolding_reasoning || recData.reasoning || `Targeted acquisition deficit identified in ${recData.recommended_concept}.`,
              recommendedModality: recData.recommended_activity === "MCQ" ? "5-Question Diagnostic Bundle" : (recData.recommended_activity || "5-Question Diagnostic Bundle"),
            });
            setIsRecommendLoading(false);
          } else if (isMounted) {
            setIsRecommendLoading(false);
            setIsRecommendError(true);
          }
        } else if (isMounted) {
          setIsRecommendLoading(false);
          setIsRecommendError(true);
        }

        // 1. Process History First to know which concepts have live attempt records
        const conceptAttemptsFromHistory = new Map<string, number>();
        let mappedHistory: DetailedSessionRecord[] = [];

        if (historyRes.ok) {
          const hData = await historyRes.json();
          if (hData && Array.isArray(hData.history)) {
            for (const rec of hData.history) {
              if (rec.concept) {
                conceptAttemptsFromHistory.set(
                  rec.concept,
                  (conceptAttemptsFromHistory.get(rec.concept) || 0) + 1
                );
              }
            }

            mappedHistory = hData.history.map((rec: any, idx: number) => ({
              id: rec._id || `live_sess_${idx}`,
              date: rec.timestamp
                ? new Date(rec.timestamp).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
                : "Recent",
              concept: rec.concept || "Variables",
              difficulty: (rec.difficulty as "easy" | "medium" | "hard") || "medium",
              bundleScore: typeof rec.bundle_average_score === "number" ? rec.bundle_average_score : 0,
              mcqScores: rec.mcq_scores || [1.0, 1.0, 1.0],
              shortAnswerScore: rec.short_answer_score || 0,
              codeScore: typeof rec.code_score === "number" ? rec.code_score : 0,
              codeStatus: rec.code_status || rec.codeStatus,
              codeExecutionStatus: rec.code_execution_status || rec.codeExecutionStatus,
              syntaxPreviewPassed: rec.syntax_preview_passed ?? rec.syntaxPreviewPassed,
              codeTestsPassed:
                typeof rec.code_tests_passed === "number"
                  ? rec.code_tests_passed
                  : typeof rec.codeTestsPassed === "number"
                    ? rec.codeTestsPassed
                    : 0,
              codeTestsTotal:
                resolveCodeTestsTotal(rec.concept, rec.difficulty, rec.code_tests_total ?? rec.codeTestsTotal) ??
                (typeof (rec.code_tests_total ?? rec.codeTestsTotal) === "number" ? (rec.code_tests_total ?? rec.codeTestsTotal) : 2),
              nextDifficulty: (rec.next_difficulty as "easy" | "medium" | "hard") || "medium",
              scaffoldingReason: rec.scaffolding_reasoning || "Scaffolding interval applied.",
              details: {
                mcqs: [],
                shortAnswer: { question: "", studentAnswer: "", rubric: "", similarity: 0 },
                coding: {
                  problem: "",
                  passed: 0,
                  total:
                    resolveCodeTestsTotal(rec.concept, rec.difficulty, rec.code_tests_total) ??
                    (typeof rec.code_tests_total === "number" ? rec.code_tests_total : 2),
                  syntaxValid: true,
                },
              },
            }));

            setLiveSessions(mappedHistory);
            historyLoaded = true;
          }
        }

        // 2. Process Mastery and correlate concept attempts
        if (masteryRes.ok) {
          const mData = await masteryRes.json();
          if (mData && mData.knowledge_state) {
            const mappedKCs: DashboardKCItem[] = Object.entries(mData.knowledge_state).map(
              ([concept, data]: [string, any]) => {
                const masteryVal = typeof data.mastery === "number" ? data.mastery * 100 : 30.0;
                const uncVal = typeof data.uncertainty === "number" ? data.uncertainty * 100 : 50.0;
                const rawAttempts =
                  typeof data.attempts === "number"
                    ? data.attempts
                    : Array.isArray(data.history)
                      ? data.history.length
                      : 0;
                const historyAttempts = conceptAttemptsFromHistory.get(concept) || 0;
                const totalConceptAttempts = Math.max(rawAttempts, historyAttempts);
                const hasAttempts = totalConceptAttempts > 0;

                const status: "Mastered" | "In Progress" | "Focus Area" | "Not Attempted" = !hasAttempts
                  ? "Not Attempted"
                  : masteryVal >= 75
                    ? "Mastered"
                    : masteryVal >= 45
                      ? "In Progress"
                      : "Focus Area";

                const difficulty: "easy" | "medium" | "hard" =
                  (mData.concept_difficulties && mData.concept_difficulties[concept]) || "medium";

                return {
                  name: concept,
                  mastery: Number(masteryVal.toFixed(1)),
                  uncertainty: Number(uncVal.toFixed(1)),
                  status,
                  difficulty,
                  recommendedModality: "5-Activity Concept Assessment Bundle",
                  explanation: hasAttempts
                    ? `Estimated mastery for ${concept}.`
                    : `Initial baseline prior for ${concept} (unassessed).`,
                  attempts: totalConceptAttempts,
                  hasAttempts,
                };
              }
            );

            if (mappedKCs.length > 0) {
              setLiveKCs(mappedKCs);
              masteryLoaded = true;
            }
          }
        }

        if (masteryLoaded && historyLoaded) {
          setIsLive(true);
          setIsFallbackMode(false);
        } else {
          setIsLive(false);
          setIsFallbackMode(true);
        }
      } catch {
        if (isMounted) {
          setIsLive(false);
          setIsFallbackMode(true);
          setLiveKCs(null);
          setLiveSessions(null);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadDashboardData();

    return () => {
      isMounted = false;
    };
  }, []);

  const isDemoFallback = isFallbackMode || (liveSessions === null && !isLoading);
  const activeKCs: DashboardKCItem[] = liveKCs !== null ? liveKCs : canonicalAsDashboardKCs;
  const activeSessions: DetailedSessionRecord[] = liveSessions !== null ? liveSessions : CANONICAL_ASSESSMENT_SESSIONS;

  const assessedKCs = activeKCs.filter((kc) => kc.hasAttempts);
  const overallMastery =
    assessedKCs.length > 0
      ? Number(
        (
          assessedKCs.reduce((acc, curr) => acc + curr.mastery, 0) /
          assessedKCs.length
        ).toFixed(1)
      )
      : 0.0;

  const masteredCount = activeKCs.filter((kc) => kc.hasAttempts && kc.mastery >= 75).length;
  const learningAccuracy =
    activeSessions.length > 0
      ? Number(
        (
          activeSessions.reduce((acc, s) => acc + s.bundleScore, 0) /
          activeSessions.length
        ).toFixed(1)
      )
      : isDemoFallback
        ? calculateMeanBundleScore()
        : 0.0;

  const questionsAttempted = activeSessions.length * 5;
  const completedBundles = activeSessions.length;
  const recentSessions = activeSessions.slice(0, 3);

  const difficultyVariant = {
    easy: "success" as const,
    medium: "warning" as const,
    hard: "danger" as const,
  };

  const targetConcept = liveRecommendation?.name ?? ACTIVE_DEMONSTRATION_TARGET.concept;
  const targetDifficulty = liveRecommendation?.difficulty ?? ACTIVE_DEMONSTRATION_TARGET.difficulty;
  const showDemonstrationCallout = isDemoFallback || !liveRecommendation;

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-teal-50 px-3 py-0.5 text-xs font-semibold text-teal-800 mb-2">
            <Cpu className="h-3 w-3 text-teal-700" />
            {isLoading
              ? "Loading..."
              : isLive
                ? "Connected"
                : "Offline"}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Student Learning Dashboard
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-600">
            Track your mastery and continue your personalized practice.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link href={`/practice?concept=${encodeURIComponent(targetConcept)}&difficulty=${targetDifficulty}&mode=student`}>
            <Button variant="primary" size="md" className="gap-2 shadow-xs">
              <Zap className="h-4 w-4" />
              <span>Practice: {targetConcept}</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* 1. Four Metric KPI Cards (Dynamically Derived from Canonical Store or Live Sessions) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Overall Mastery"
          value={`${overallMastery.toFixed(1)}%`}
          description={
            assessedKCs.length > 0
              ? `Mean mastery score across ${assessedKCs.length} assessed KCs`
              : "Baseline prior (Unassessed student)"
          }
          icon={Award}
          accentColor="indigo"
        />
        <MetricCard
          label="Learning Accuracy"
          value={`${learningAccuracy.toFixed(1)}%`}
          description={
            activeSessions.length > 0
              ? "Average across verified historical sessions"
              : isDemoFallback
                ? "Based on your recent practice sessions"
                : "No assessment sessions completed yet"
          }
          icon={TrendingUp}
          accentColor="cyan"
        />
        <MetricCard
          label="Questions Attempted"
          value={questionsAttempted.toString()}
          description={
            isDemoFallback
              ? `${CANONICAL_ASSESSMENT_SESSIONS.length} completed practice sessions`
              : `${completedBundles} completed practice session${completedBundles === 1 ? "" : "s"}`
          }
          icon={CheckCircle2}
          accentColor="emerald"
        />
        <MetricCard
          label="Learning Progress"
          value={`${masteredCount} / ${activeKCs.length} KCs`}
          description="Mastery score ≥ 75% threshold"
          icon={Target}
          accentColor="amber"
        />
      </div>

      {/* 2. Dual Recommendation Architecture Banner */}
      <Card className="relative overflow-hidden border border-teal-200/90 bg-gradient-to-r from-teal-50/50 via-white to-white shadow-xs">
        <div className="absolute top-0 right-0 p-6 pointer-events-none opacity-10 hidden md:block">
          <Sparkles className="h-32 w-32 text-teal-600" />
        </div>
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="info" size="sm" dot>
              Recommended Focus Area
            </Badge>
            <span className="text-xs text-slate-500 font-medium">
              High Priority
            </span>
          </div>
          <CardTitle className="text-xl sm:text-2xl mt-1 text-slate-900 flex flex-wrap items-center gap-2">
            <span>Next Recommended Topic:</span>
            {isRecommendLoading ? (
              <span className="text-slate-400 font-bold text-lg">Loading recommendation...</span>
            ) : liveRecommendation ? (
              <>
                <span className="text-teal-700 font-bold">
                  {liveRecommendation.name}
                </span>
                <Badge
                  variant={difficultyVariant[liveRecommendation.difficulty]}
                  size="sm"
                  className="uppercase font-mono text-[9px]"
                >
                  {liveRecommendation.difficulty}
                </Badge>
              </>
            ) : (
              <span className="text-amber-700 font-bold text-base">Recommendation Service Offline</span>
            )}
          </CardTitle>
          <CardDescription className="text-slate-600 text-xs sm:text-sm max-w-3xl mt-1">
            {isRecommendLoading
              ? "Finding your next recommended practice topic..."
              : liveRecommendation
                ? liveRecommendation.explanation
                : "Recommendation service is currently unavailable."}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0 space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            <div className="rounded-lg bg-white px-3 py-1.5 border border-slate-200/90 shadow-2xs">
              <span className="text-slate-500 mr-2">Format:</span>
              <span className="text-slate-800 font-semibold">
                {isRecommendLoading ? "..." : liveRecommendation ? liveRecommendation.recommendedModality : "Unavailable"}
              </span>
            </div>
            <div className="rounded-lg bg-white px-3 py-1.5 border border-slate-200/90 shadow-2xs">
              <span className="text-slate-500 mr-2">Estimated Mastery:</span>
              <span className="text-teal-700 font-bold">
                {isRecommendLoading ? "..." : liveRecommendation ? `${liveRecommendation.mastery.toFixed(1)}%` : "N/A"}
              </span>
            </div>
            <div className="rounded-lg bg-white px-3 py-1.5 border border-slate-200/90 shadow-2xs">
              <span className="text-slate-500 mr-2">Confidence Level:</span>
              <span className="text-amber-700 font-bold">
                {isRecommendLoading ? "..." : liveRecommendation ? `${liveRecommendation.uncertainty.toFixed(1)}%` : "N/A"}
              </span>
            </div>
            {liveRecommendation && (
              <Link
                href={`/practice?concept=${encodeURIComponent(liveRecommendation.name)}&difficulty=${liveRecommendation.difficulty}&mode=adaptive`}
                className="ml-auto"
              >
                <Button variant="primary" size="sm" className="gap-1.5 shadow-xs">
                  <span>Practice Target</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            )}
          </div>

          {/* Active Demonstration Practice Target Callout */}
          {showDemonstrationCallout && (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-3.5 rounded-xl border border-slate-200/90 bg-slate-50/80">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-700 uppercase tracking-wider font-mono">
                    Quick Practice
                  </span>
                  <Badge variant="warning" size="sm" className="uppercase font-mono text-[9px]">
                    {ACTIVE_DEMONSTRATION_TARGET.difficulty}
                  </Badge>
                </div>
                <p className="text-xs text-slate-600">
                  <b className="text-slate-800">{ACTIVE_DEMONSTRATION_TARGET.concept}</b> — Practice exercises across multiple formats.
                </p>
              </div>
              <Link href={`/practice?concept=${encodeURIComponent(ACTIVE_DEMONSTRATION_TARGET.concept)}&difficulty=${ACTIVE_DEMONSTRATION_TARGET.difficulty}&mode=student`}>
                <Button variant="secondary" size="sm" className="gap-1.5 shrink-0 shadow-xs">
                  <span>Start Practice</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 3. Knowledge Competencies Grid & Recent Sessions Two-Column Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Concept Competencies Breakdown */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base sm:text-lg text-slate-900">
                    Concept Competencies Breakdown
                  </CardTitle>
                  <CardDescription className="mt-0.5 text-slate-500">
                    Mastery across key Python concepts
                  </CardDescription>
                </div>
                <Link
                  href="/analytics"
                  className="text-xs text-teal-700 hover:text-teal-800 font-semibold hidden sm:inline-flex items-center gap-1"
                >
                  <span>Radar View</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {activeKCs.map((kc) => {
                const statusVariant =
                  kc.status === "Not Attempted"
                    ? ("default" as const)
                    : kc.mastery >= 75
                      ? ("success" as const)
                      : kc.mastery >= 45
                        ? ("warning" as const)
                        : ("danger" as const);

                const progressVariant =
                  kc.mastery >= 75
                    ? ("mastery" as const)
                    : kc.mastery >= 45
                      ? ("default" as const)
                      : ("danger" as const);

                return (
                  <div
                    key={kc.name}
                    className="rounded-lg border border-slate-200/80 bg-slate-50/50 hover:bg-slate-100/60 hover:border-slate-300 p-3.5 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-900">
                          {kc.name}
                        </span>
                        <Badge variant={statusVariant} size="sm">
                          {kc.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 text-xs font-mono">
                        <span className="text-slate-500">
                          Mastery: <b className="text-slate-900 font-bold">{kc.hasAttempts ? `${kc.mastery.toFixed(1)}%` : "0.0%"}</b>
                        </span>
                        <span className="text-slate-500">
                          Confidence: <b className="text-slate-700 font-semibold">{(100 - kc.uncertainty).toFixed(1)}%</b>
                        </span>
                      </div>
                    </div>
                    <Progress value={kc.hasAttempts ? kc.mastery : 0} variant={progressVariant} size="sm" />
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>

        {/* Right Col: Recent Learning Activity Log */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base sm:text-lg text-slate-900">
                    Recent Activity
                  </CardTitle>
                  <CardDescription className="mt-0.5 text-slate-500">
                    Recent assessment sessions
                  </CardDescription>
                </div>
                <Link
                  href="/history"
                  className="text-xs text-teal-700 hover:text-teal-800 font-semibold inline-flex items-center gap-1"
                >
                  <span>All ({activeSessions.length})</span>
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentSessions.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-6 text-center">
                  <Clock className="h-8 w-8 text-slate-400 mx-auto mb-2 opacity-60" />
                  <p className="text-xs font-semibold text-slate-800">No Practice History Yet</p>
                  <p className="text-[11px] text-slate-500 mt-1 max-w-xs mx-auto">
                    Complete your first practice session to see your progress here.
                  </p>
                </div>
              ) : (
                recentSessions.map((sess) => (
                  <div
                    key={sess.id}
                    className="rounded-lg border border-slate-200/80 bg-slate-50/50 hover:bg-slate-100/60 p-3 flex flex-col gap-2 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-slate-900">
                        {sess.concept}
                      </span>
                      <Badge variant="default" size="sm" className="uppercase font-mono text-[9px]">
                        {sess.difficulty}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs font-mono">
                      <span className="text-slate-500">
                        Bundle Score:{" "}
                        <b
                          className={
                            sess.bundleScore >= 75
                              ? "text-emerald-700 font-bold"
                              : "text-amber-700 font-bold"
                          }
                        >
                          {sess.bundleScore.toFixed(1)}%
                        </b>
                      </span>
                      <span className="text-slate-500 flex items-center gap-1 text-[11px]">
                        <Clock className="h-3 w-3" />
                        {sess.date}
                      </span>
                    </div>
                  </div>
                ))
              )}

              <div className="pt-2">
                <Link
                  href={`/practice?concept=${encodeURIComponent(targetConcept)}&difficulty=${targetDifficulty}&mode=student`}
                  className="block"
                >
                  <Button variant="outline" size="sm" className="w-full text-xs gap-1.5 shadow-2xs">
                    <BookOpen className="h-3.5 w-3.5" />
                    <span>Practice {targetConcept}</span>
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
