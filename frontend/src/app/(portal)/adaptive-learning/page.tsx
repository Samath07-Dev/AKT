"use client";

import * as React from "react";
import Link from "next/link";
import {
  Brain,
  Sparkles,
  ArrowRight,
  Cpu,
  Target,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getRankedPolicyMatrix,
  ACTIVE_DEMONSTRATION_TARGET,
} from "@/lib/mock-data/curriculum-store";

export default function AdaptiveLearningPage() {
  const [isLoading, setIsLoading] = React.useState(true);
  const [isLive, setIsLive] = React.useState(false);
  const [liveRecommendation, setLiveRecommendation] = React.useState<any | null>(null);
  const [liveMatrix, setLiveMatrix] = React.useState<any[] | null>(null);

  React.useEffect(() => {
    let isMounted = true;

    async function loadAdaptiveData() {
      try {
        const [recommendRes, masteryRes] = await Promise.all([
          fetch("/api/adaptive/recommend"),
          fetch("/api/student/mastery"),
        ]);

        if (!isMounted) return;

        let liveFound = false;

        if (recommendRes.ok) {
          const recData = await recommendRes.json();
          if (recData && recData.recommended_concept) {
            setLiveRecommendation({
              name: recData.recommended_concept,
              priorityScore: recData.priority_score,
              recommendedModality: recData.recommended_activity,
              mastery: recData.concept_mastery * 100,
              uncertainty: recData.concept_uncertainty * 100,
              difficulty: (recData.recommended_difficulty || "medium") as "easy" | "medium" | "hard",
              explanation: recData.scaffolding_reasoning || recData.reasoning || `Targeted acquisition deficit identified in ${recData.recommended_concept}.`,
            });
            liveFound = true;
          }
        }

        if (masteryRes.ok) {
          const mData = await masteryRes.json();
          if (mData && mData.knowledge_state) {
            const matrix = Object.entries(mData.knowledge_state).map(([concept, data]: [string, any]) => {
              const m = typeof data.mastery === "number" ? data.mastery : 0.5;
              const u = typeof data.uncertainty === "number" ? data.uncertainty : 0.3;
              const priority = (1.0 - m) * (1.0 + u);
              return {
                name: concept,
                mastery: Number((m * 100).toFixed(1)),
                uncertainty: Number((u * 100).toFixed(1)),
                priorityScore: Number(priority.toFixed(4)),
                status: (m >= 0.75 ? "Mastered" : m >= 0.45 ? "In Progress" : "Focus Area") as "Mastered" | "In Progress" | "Focus Area",
                difficulty: ((mData.concept_difficulties && mData.concept_difficulties[concept]) || "medium") as "easy" | "medium" | "hard",
                recommendedModality: m < 0.4 ? "5-Question Diagnostic Bundle" : m > 0.8 ? "Python Coding Sandbox" : "Conceptual Short Answer",
                explanation: `Recommended focus area based on your recent performance.`,
              };
            });
            matrix.sort((a, b) => b.priorityScore - a.priorityScore);
            if (matrix.length > 0) {
              setLiveMatrix(matrix);
              liveFound = true;
            }
          }
        }

        setIsLive(liveFound);
      } catch {
        if (isMounted) setIsLive(false);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadAdaptiveData();
    return () => {
      isMounted = false;
    };
  }, []);

  const sortedMatrix = liveMatrix || getRankedPolicyMatrix();
  const topTarget = liveRecommendation || (liveMatrix && liveMatrix.length > 0 ? liveMatrix[0] : null);
  const loopsData = sortedMatrix.find((item) => item.name === "Loops");

  const difficultyBadgeVariant: Record<string, "default" | "success" | "warning" | "danger" | "info"> = {
    easy: "success",
    medium: "warning",
    hard: "danger",
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-teal-50 px-3 py-0.5 text-xs font-semibold text-teal-800 mb-2">
            <Brain className="h-3 w-3 text-teal-700" />
            {isLoading
              ? "Loading Learning Plan..."
              : isLive
              ? "Adaptive Learning Plan"
              : "Demonstration Mode (Offline)"}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-3">
            <span>Adaptive Learning Policy &amp; Scaffolding</span>
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-600">
            Personalized topic recommendations based on your learning progress.
          </p>
        </div>
      </div>

      {/* Two-Target Clarity Grid: Global Highest Deficit vs Active Practice Bundle */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Card 1: Globally Highest-Priority Deficit */}
        <Card className="border border-teal-200/90 bg-gradient-to-r from-teal-50/50 via-white to-white shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-wider text-teal-700 font-bold">
                Recommended Focus Area
              </span>
              <Badge variant="warning" size="sm" className="font-medium text-[10px]">
                High Priority
              </Badge>
            </div>
            <CardTitle className="text-xl text-slate-900 flex items-center gap-3 mt-1">
              {isLoading ? (
                <span className="text-slate-400">Loading recommendation...</span>
              ) : topTarget ? (
                <>
                  <span className="text-teal-700 font-bold">{topTarget.name}</span>
                  <Badge
                    variant={difficultyBadgeVariant[String(topTarget.difficulty)] || "default"}
                    size="sm"
                    className="uppercase font-mono text-[9px]"
                  >
                    {topTarget.difficulty}
                  </Badge>
                </>
              ) : (
                <span className="text-amber-700 font-bold text-base">Recommendation Service Offline</span>
              )}
            </CardTitle>
            <CardDescription className="text-slate-600 text-xs">
              {isLoading
                ? "Evaluating curriculum policy across student knowledge components..."
                : topTarget
                ? topTarget.explanation
                : "Live recommendation service is temporarily unavailable."}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2 space-y-3">
            {topTarget && (
              <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs font-mono">
                <div className="flex flex-wrap items-center gap-2.5">
                  <div className="rounded-lg bg-white px-2.5 py-1 border border-slate-200/90 shadow-2xs">
                    <span className="text-slate-500 mr-1.5">Modality:</span>
                    <span className="text-slate-800 font-bold">{topTarget.recommendedModality}</span>
                  </div>
                  <div className="rounded-lg bg-white px-2.5 py-1 border border-slate-200/90 shadow-2xs">
                    <span className="text-slate-500 mr-1.5">Mastery:</span>
                    <span className="text-teal-700 font-bold">{topTarget.mastery.toFixed(1)}%</span>
                  </div>
                  <div className="rounded-lg bg-white px-2.5 py-1 border border-slate-200/90 shadow-2xs">
                    <span className="text-slate-500 mr-1.5">Confidence:</span>
                    <span className="text-blue-700 font-bold">{(100 - topTarget.uncertainty).toFixed(1)}%</span>
                  </div>
                </div>

                <Link href={`/practice?concept=${encodeURIComponent(topTarget.name)}&difficulty=${topTarget.difficulty}&mode=adaptive`}>
                  <Button variant="primary" size="sm" className="gap-2 shadow-xs">
                    <span>Practice Recommended Bundle</span>
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Card 2: Fixed Demonstration Showcase Target (Loops) */}
        <Card className="border border-slate-200/90 bg-slate-50/50 shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono uppercase tracking-wider text-slate-700 font-bold flex items-center gap-1.5">
                <Target className="h-3.5 w-3.5 text-slate-600" />
                <span>Quick Practice</span>
              </span>
              <Badge variant="default" size="sm" className="font-medium text-[10px]">
                Practice Bundle
              </Badge>
            </div>
            <CardTitle className="text-xl text-slate-900 flex items-center gap-3 mt-1">
              <span>{ACTIVE_DEMONSTRATION_TARGET.concept}</span>
              <Badge
                variant={difficultyBadgeVariant[ACTIVE_DEMONSTRATION_TARGET.difficulty]}
                size="sm"
                className="uppercase font-mono text-[9px]"
              >
                {ACTIVE_DEMONSTRATION_TARGET.difficulty}
              </Badge>
            </CardTitle>
            <CardDescription className="text-slate-600 text-xs">
              Curated practice exercises across multiple formats.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2 flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono">
              <div className="rounded-lg bg-white px-2.5 py-1 border border-slate-200/90 shadow-2xs">
                <span className="text-slate-500 mr-1.5">Mastery:</span>
                <span className="text-teal-700 font-bold">
                  {loopsData ? `${loopsData.mastery.toFixed(1)}%` : "64.2%"}
                </span>
              </div>
              <div className="rounded-lg bg-white px-2.5 py-1 border border-slate-200/90 shadow-2xs">
                <span className="text-slate-500 mr-1.5">Confidence:</span>
                <span className="text-blue-700 font-bold">
                  {loopsData ? `${(100 - loopsData.uncertainty).toFixed(1)}%` : "69.3%"}
                </span>
              </div>
            </div>

            <Link href={`/practice?concept=${encodeURIComponent(ACTIVE_DEMONSTRATION_TARGET.concept)}&difficulty=${ACTIVE_DEMONSTRATION_TARGET.difficulty}&mode=student`}>
              <Button variant="secondary" size="sm" className="gap-2 shadow-xs">
                <span>Practice Loops</span>
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Curriculum Priority Policy Matrix Table */}
      <Card className="border border-slate-200/90 bg-white shadow-xs">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base sm:text-lg text-slate-900">
                Curriculum Policy Matrix
              </CardTitle>
              <CardDescription className="text-slate-500">
                Topics ordered by recommended study priority.
              </CardDescription>
            </div>
            <Badge variant="default" size="sm" className="font-mono text-[10px]">
              10 Domains Ranked
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 bg-slate-50/80 text-slate-600 font-mono uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="py-3 px-4">Rank</th>
                  <th className="py-3 px-4">Knowledge Component</th>
                  <th className="py-3 px-4">Mastery</th>
                  <th className="py-3 px-4">Confidence</th>
                  <th className="py-3 px-4">Priority Score</th>
                  <th className="py-3 px-4">Recommended Modality</th>
                  <th className="py-3 px-4">Scaffolded Level</th>
                  <th className="py-3 px-4">Recommendation</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-slate-700">
                {sortedMatrix.map((item, idx) => (
                  <tr key={item.name} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3 px-4 font-bold text-slate-500">
                      #{idx + 1}
                    </td>
                    <td className="py-3 px-4 font-sans font-semibold text-slate-900">
                      {item.name}
                    </td>
                    <td className="py-3 px-4 font-bold text-teal-700">
                      {item.mastery.toFixed(1)}%
                    </td>
                    <td className="py-3 px-4 font-bold text-blue-700">
                      {item.uncertainty.toFixed(1)}%
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-bold text-teal-800 bg-teal-50 px-2 py-0.5 rounded border border-teal-200/80">
                        {item.priorityScore.toFixed(4)}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-sans text-slate-700">
                      {item.recommendedModality}
                    </td>
                    <td className="py-3 px-4">
                      <Badge
                        variant={difficultyBadgeVariant[String(item.difficulty)] || "default"}
                        size="sm"
                        className="uppercase font-mono text-[9px]"
                      >
                        {item.difficulty}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 font-sans text-slate-500 text-[11px] max-w-xs truncate" title={item.explanation}>
                      {item.explanation}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/practice?concept=${encodeURIComponent(item.name)}&difficulty=${item.difficulty}&mode=student`}
                        className="inline-flex items-center gap-1 text-[11px] font-sans font-semibold text-teal-700 hover:text-teal-800 hover:underline"
                      >
                        <span>Practice</span>
                        <ArrowRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
