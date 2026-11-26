"use client";

import * as React from "react";
import {
  Brain,
  Sparkles,
  TrendingUp,
  Activity,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/ui/metric-card";
import {
  KnowledgeRadarChart,
  KnowledgeRadarItem,
  LearningVelocityChart,
  LearningSessionItem,
} from "@/components/charts";
import {
  CANONICAL_KNOWLEDGE_COMPETENCIES,
  CANONICAL_ASSESSMENT_SESSIONS,
  DetailedSessionRecord,
} from "@/lib/mock-data/curriculum-store";
import { resolveCodeTestsTotal } from "@/components/history/history-table";

interface AnalyticsKCItem {
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

export default function AnalyticsPage() {
  const [isLoading, setIsLoading] = React.useState(true);
  const [isLive, setIsLive] = React.useState(false);
  const [isFallbackMode, setIsFallbackMode] = React.useState(false);
  const [liveKCs, setLiveKCs] = React.useState<AnalyticsKCItem[] | null>(null);
  const [liveSessions, setLiveSessions] = React.useState<DetailedSessionRecord[] | null>(null);
  const [conceptScores, setConceptScores] = React.useState<Map<string, number>>(new Map());

  React.useEffect(() => {
    let isMounted = true;

    async function loadAnalyticsData() {
      try {
        const [masteryRes, historyRes] = await Promise.all([
          fetch("/api/student/mastery"),
          fetch("/api/student/history"),
        ]);

        if (!isMounted) return;

        let masteryLoaded = false;
        let historyLoaded = false;

        // 1. Process History to correlate verified concept attempts and score evidence
        const conceptAttemptsFromHistory = new Map<string, number>();
        const latestConceptScoreMap = new Map<string, number>();
        let mappedSessions: DetailedSessionRecord[] = [];

        if (historyRes.ok) {
          const hData = await historyRes.json();
          if (hData && Array.isArray(hData.history)) {
            for (const rec of hData.history) {
              if (rec.concept) {
                conceptAttemptsFromHistory.set(
                  rec.concept,
                  (conceptAttemptsFromHistory.get(rec.concept) || 0) + 1
                );
                if (!latestConceptScoreMap.has(rec.concept) && typeof rec.bundle_average_score === "number") {
                  latestConceptScoreMap.set(rec.concept, rec.bundle_average_score);
                }
              }
            }

            mappedSessions = hData.history.map((rec: any, idx: number) => ({
              id: rec._id || `sess_${idx}`,
              date: rec.timestamp
                ? new Date(rec.timestamp).toLocaleDateString("en-US", { month: "short", day: "numeric" })
                : `S${idx + 1}`,
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
              scaffoldingReason: rec.scaffolding_reasoning || "Scaffolding interval maintained.",
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

            setLiveSessions(mappedSessions);
            setConceptScores(latestConceptScoreMap);
            historyLoaded = true;
          }
        }

        // 2. Process Knowledge State and correlate with attempt evidence
        if (masteryRes.ok) {
          const mData = await masteryRes.json();
          if (mData && mData.knowledge_state) {
            const mapped: AnalyticsKCItem[] = Object.entries(mData.knowledge_state).map(
              ([concept, data]: [string, any]) => {
                const rawM = typeof data.mastery === "number" ? data.mastery * 100 : 30.0;
                const rawU = typeof data.uncertainty === "number" ? data.uncertainty * 100 : 50.0;
                const rawAttempts =
                  typeof data.attempts === "number"
                    ? data.attempts
                    : Array.isArray(data.history)
                    ? data.history.length
                    : 0;
                const historyAttempts = conceptAttemptsFromHistory.get(concept) || 0;
                const totalAttempts = Math.max(rawAttempts, historyAttempts);
                const hasAttempts = totalAttempts > 0;

                const status: "Mastered" | "In Progress" | "Focus Area" | "Not Attempted" = !hasAttempts
                  ? "Not Attempted"
                  : rawM >= 75
                  ? "Mastered"
                  : rawM >= 45
                  ? "In Progress"
                  : "Focus Area";

                const difficulty: "easy" | "medium" | "hard" =
                  (mData.concept_difficulties && mData.concept_difficulties[concept]) || "medium";

                return {
                  name: concept,
                  mastery: Number(rawM.toFixed(1)),
                  uncertainty: Number(rawU.toFixed(1)),
                  status,
                  difficulty,
                  recommendedModality: "5-Activity Concept Assessment Bundle",
                  explanation: hasAttempts
                    ? `Estimated mastery for ${concept}.`
                    : `Initial baseline prior for ${concept} (unassessed).`,
                  attempts: totalAttempts,
                  hasAttempts,
                };
              }
            );

            if (mapped.length > 0) {
              setLiveKCs(mapped);
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

    loadAnalyticsData();
    return () => {
      isMounted = false;
    };
  }, []);

  const isDemoFallback = isFallbackMode || (!isLoading && liveSessions === null);
  const activeKCs: AnalyticsKCItem[] =
    liveKCs !== null
      ? liveKCs
      : CANONICAL_KNOWLEDGE_COMPETENCIES.map((kc) => ({
          ...kc,
          attempts: 1,
          hasAttempts: true,
        }));

  const activeSessions: DetailedSessionRecord[] =
    liveSessions !== null
      ? liveSessions
      : isDemoFallback
      ? CANONICAL_ASSESSMENT_SESSIONS
      : [];

  const assessedKCs = activeKCs.filter((kc) => kc.hasAttempts);
  const meanMastery =
    assessedKCs.length > 0
      ? Number(
          (
            assessedKCs.reduce((acc, kc) => acc + kc.mastery, 0) /
            assessedKCs.length
          ).toFixed(1)
        )
      : 0.0;

  const assessmentAverage =
    activeSessions.length > 0
      ? Number(
          (
            activeSessions.reduce((acc, s) => acc + s.bundleScore, 0) /
            activeSessions.length
          ).toFixed(1)
        )
      : 0.0;

  const meanUncertainty = Number(
    (activeKCs.reduce((acc, kc) => acc + kc.uncertainty, 0) / activeKCs.length).toFixed(1)
  );

  // Radar chart: Unassessed concepts display 0 earned mastery with their raw tracking uncertainty
  const radarData: KnowledgeRadarItem[] = React.useMemo(() => {
    return activeKCs.map((kc) => ({
      concept: kc.name,
      mastery: kc.hasAttempts ? kc.mastery : 0,
      uncertainty: kc.uncertainty,
      hasAttempts: kc.hasAttempts,
    }));
  }, [activeKCs]);

  // Velocity data: uses actual verified assessment bundle scores; does not fabricate mastery trajectory
  const velocityData: LearningSessionItem[] = React.useMemo(() => {
    return [...activeSessions]
      .reverse()
      .map((s, idx) => ({
        session: `S${idx + 1}`,
        date: s.date.split(",")[0],
        concept: s.concept,
        bundleScore: s.bundleScore,
      }));
  }, [activeSessions]);

  // Determine highest assessed competency based on actual verified evidence
  const highestCompetency = React.useMemo(() => {
    if (assessedKCs.length === 0) {
      return { name: "None", description: "No concepts assessed yet" };
    }
    const sorted = [...assessedKCs].sort((a, b) => {
      const scoreA = conceptScores.get(a.name) ?? a.mastery;
      const scoreB = conceptScores.get(b.name) ?? b.mastery;
      return scoreB - scoreA;
    });
    const top = sorted[0];
    const topScore = conceptScores.get(top.name);
    return {
      name: top.name,
      description:
        topScore !== undefined
          ? `Assessed score at ${topScore.toFixed(1)}%`
          : `Mastery at ${top.mastery.toFixed(1)}%`,
    };
  }, [assessedKCs, conceptScores]);

  // Determine highest uncertainty reflecting actual underlying data
  const highestUncertainty = React.useMemo(() => {
    const unassessedCount = activeKCs.filter((kc) => !kc.hasAttempts).length;
    const sortedByUnc = [...activeKCs].sort((a, b) => b.uncertainty - a.uncertainty);
    const top = sortedByUnc[0] || { name: "None", uncertainty: 0 };

    if (unassessedCount === activeKCs.length) {
      return {
        name: "All KCs (Prior)",
        description: `Baseline prior (${top.uncertainty.toFixed(1)}% uncertainty across 10 KCs)`,
      };
    }
    if (unassessedCount > 0) {
      return {
        name: `${unassessedCount} Unassessed KCs`,
        description: `Prior uncertainty at ${top.uncertainty.toFixed(1)}%`,
      };
    }
    return {
      name: top.name,
      description: `Uncertainty at ${top.uncertainty.toFixed(1)}%`,
    };
  }, [activeKCs]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-teal-50 px-3 py-0.5 text-xs font-semibold text-teal-800 mb-2">
            <Sparkles className="h-3 w-3 text-teal-700" />
            {isLoading
              ? "Loading Knowledge Analytics..."
              : isLive
              ? "Skill Analytics"
              : "Demonstration Mode (Offline)"}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Knowledge Tracing &amp; Mastery Analytics
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-600">
            Detailed breakdown of your Python concept mastery and learning progress.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono text-slate-700 bg-white border border-slate-200/90 rounded-xl px-3 py-2 shadow-2xs">
          <Activity className="h-3.5 w-3.5 text-teal-700" />
          <span>Updated</span>
        </div>
      </div>

      {/* 1. Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Average Mastery"
          value={`${meanMastery.toFixed(1)}%`}
          description={
            assessedKCs.length > 0
              ? `Average score across ${assessedKCs.length} assessed concepts`
              : "No concepts assessed yet"
          }
          icon={TrendingUp}
          accentColor="indigo"
        />
        <MetricCard
          label="Average Confidence"
          value={`${(100 - meanUncertainty).toFixed(1)}%`}
          description="Confidence level across 10 concepts"
          icon={HelpCircle}
          accentColor="amber"
        />
        <MetricCard
          label="Highest Competency"
          value={highestCompetency.name}
          description={highestCompetency.description}
          icon={CheckCircle2}
          accentColor="emerald"
        />
        <MetricCard
          label="Highest Uncertainty"
          value={highestUncertainty.name}
          description={highestUncertainty.description}
          icon={AlertCircle}
          accentColor="rose"
        />
      </div>

      {/* 2. Primary Charts: Radar and Learning Velocity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Knowledge State Radar Chart */}
        <Card className="border-slate-200/90 bg-white shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base sm:text-lg flex items-center gap-2 text-slate-900">
                  <Brain className="h-4 w-4 text-teal-700" />
                  <span>Knowledge State Radar</span>
                </CardTitle>
                <CardDescription className="mt-1 text-slate-600">
                  Concept proficiency across 10 core Python domains.
                </CardDescription>
              </div>
              <Badge variant="info" size="sm">
                10 Concepts
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {isLoading ? (
              <div
                className="w-full flex items-center justify-center rounded-xl bg-slate-50/60 border border-slate-200"
                style={{ height: 360 }}
              >
                <span className="text-xs font-mono text-slate-500 animate-pulse">
                  Loading Knowledge State Radar...
                </span>
              </div>
            ) : (
              <KnowledgeRadarChart data={radarData} height={360} />
            )}
          </CardContent>
        </Card>

        {/* Learning Velocity Trend */}
        <Card className="border-slate-200/90 bg-white shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base sm:text-lg flex items-center gap-2 text-slate-900">
                  <TrendingUp className="h-4 w-4 text-blue-600" />
                  <span>Curriculum Learning Velocity</span>
                </CardTitle>
                <CardDescription className="mt-1 text-slate-600">
                  Progress across completed practice sessions.
                </CardDescription>
              </div>
              <Badge variant="default" size="sm">
                {velocityData.length} Sessions
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-2">
            {isLoading ? (
              <div
                className="w-full flex items-center justify-center rounded-xl bg-slate-50/60 border border-slate-200"
                style={{ height: 360 }}
              >
                <span className="text-xs font-mono text-slate-500 animate-pulse">
                  Loading Learning Velocity...
                </span>
              </div>
            ) : velocityData.length === 0 ? (
              <div
                className="flex flex-col items-center justify-center py-20 text-center rounded-xl bg-slate-50/50 border border-dashed border-slate-200 p-6"
                style={{ minHeight: 360 }}
              >
                <TrendingUp className="h-8 w-8 text-slate-400 mb-2 opacity-60" />
                <p className="text-xs font-semibold text-slate-800">No Assessment Sessions Completed</p>
                <p className="text-[11px] text-slate-500 mt-1 max-w-xs">
                  Complete practice sessions in the Practice Arena to track your progress over time.
                </p>
              </div>
            ) : (
              <LearningVelocityChart data={velocityData} isDemo={isDemoFallback} height={360} />
            )}
          </CardContent>
        </Card>
      </div>

      {/* 3. Mastery & Uncertainty Interpretation Banner */}
      <Card className="border-slate-200/90 bg-white shadow-xs">
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-900">
                  Understanding Your Scores
                </h3>
                <Badge variant="info" size="sm" className="font-mono text-[10px]">
                  Progress Tracking
                </Badge>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed max-w-3xl">
                Higher mastery indicates strong retention. Review lower-scoring concepts to build well-rounded proficiency.
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <div className="text-right">
                <span className="text-[10px] uppercase font-mono text-slate-500 block">
                  Goal Threshold
                </span>
                <span className="text-xs font-mono font-bold text-slate-900">
                  75.0% Goal
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
