"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Search,
  Filter,
  ArrowUpDown,
  ExternalLink,
  X,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  FileQuestion,
} from "lucide-react";
export {
  resolveCodeTestsTotal,
  getCodingEvaluationDisplay,
  getCodingExecutionNotice,
  type CodingStatusDisplay,
} from "@/lib/history-evaluation";
import {
  resolveCodeTestsTotal,
  getCodingEvaluationDisplay,
  CodingStatusDisplay,
} from "@/lib/history-evaluation";

export interface MockHistoryRecord {
  id: string;
  submissionId?: string;
  timestamp?: string;
  date: string;
  concept: string;
  difficulty: "easy" | "medium" | "hard";
  bundleScore: number;       // 0 to 100
  mcqScores: number[];       // e.g. [1.0, 1.0, 0.0]
  shortAnswerScore: number | null;  // 0 to 100 or null if not recorded
  codeScore: number;         // 0 to 100
  codeStatus?: string;
  codeExecutionStatus?: string;
  syntaxPreviewPassed?: boolean;
  codeTestsPassed: number;
  codeTestsTotal: number;
  nextDifficulty: "easy" | "medium" | "hard";
  scaffoldingReason: string;
  details: {
    mcqs: Array<{ question: string; selected: string; correct: string; isCorrect: boolean }>;
    shortAnswer: { question: string; studentAnswer: string; rubric: string; similarity: number | null };
    coding: { problem: string; passed: number; total: number; syntaxValid: boolean };
  };
}

interface HistoryTableProps {
  records: MockHistoryRecord[];
}

export function HistoryTable({ records }: HistoryTableProps) {
  const [searchTerm, setSearchTerm] = React.useState("");
  const [difficultyFilter, setDifficultyFilter] = React.useState<string>("all");
  const [sortField, setSortField] = React.useState<"date" | "score">("date");
  const [sortDirection, setSortDirection] = React.useState<"asc" | "desc">("desc");
  const [selectedRecord, setSelectedRecord] = React.useState<MockHistoryRecord | null>(null);

  // Filter & Search Logic
  const filteredRecords = React.useMemo(() => {
    return records
      .filter((rec) => {
        const matchesSearch = rec.concept.toLowerCase().includes(searchTerm.toLowerCase());
        const matchesDiff = difficultyFilter === "all" || rec.difficulty === difficultyFilter;
        return matchesSearch && matchesDiff;
      })
      .sort((a, b) => {
        if (sortField === "score") {
          const scoreA = typeof a.bundleScore === "number" ? a.bundleScore : 0;
          const scoreB = typeof b.bundleScore === "number" ? b.bundleScore : 0;
          return sortDirection === "desc"
            ? scoreB - scoreA
            : scoreA - scoreB;
        }
        // Chronological timestamp sorting using actual ISO timestamps
        const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        if (!isNaN(timeA) && !isNaN(timeB) && (timeA > 0 || timeB > 0)) {
          return sortDirection === "desc" ? timeB - timeA : timeA - timeB;
        }
        // Fallback for legacy records lacking parseable ISO timestamps
        return sortDirection === "desc"
          ? b.id.localeCompare(a.id)
          : a.id.localeCompare(b.id);
      });
  }, [records, searchTerm, difficultyFilter, sortField, sortDirection]);

  const handleToggleSort = (field: "date" | "score") => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const difficultyBadgeVariant = {
    easy: "success" as const,
    medium: "warning" as const,
    hard: "danger" as const,
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar: Search, Filters & Sorters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by Knowledge Component..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-xl border border-slate-300 bg-white pl-9 pr-4 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 font-sans shadow-xs transition-colors"
          />
        </div>

        {/* Filter & Sort Controls */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          <div className="flex items-center gap-1 bg-slate-100 border border-slate-200 rounded-xl p-1 text-xs">
            <span className="text-[10px] uppercase font-mono text-slate-500 px-2 flex items-center gap-1">
              <Filter className="h-3 w-3" />
              <span>Diff</span>
            </span>
            {(["all", "easy", "medium", "hard"] as const).map((diff) => (
              <button
                key={diff}
                type="button"
                onClick={() => setDifficultyFilter(diff)}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs capitalize transition-colors font-medium",
                  difficultyFilter === diff
                    ? "bg-teal-700 text-white shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                )}
              >
                {diff}
              </button>
            ))}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleToggleSort("score")}
            className="text-xs h-9 gap-1.5 border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-50"
          >
            <ArrowUpDown className="h-3.5 w-3.5" />
            <span>Score {sortField === "score" ? (sortDirection === "desc" ? "↓" : "↑") : ""}</span>
          </Button>
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-200/90 bg-white shadow-xs">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-slate-200 bg-slate-50/80 text-slate-600 font-mono uppercase text-[10px] tracking-wider">
            <tr>
              <th className="py-3.5 px-4">Date / Session</th>
              <th className="py-3.5 px-4">Knowledge Component</th>
              <th className="py-3.5 px-4">Difficulty</th>
              <th className="py-3.5 px-4">Bundle Avg</th>
              <th className="py-3.5 px-4">MCQs Score</th>
              <th className="py-3.5 px-4">Short Answer</th>
              <th className="py-3.5 px-4">Coding Tests</th>
              <th className="py-3.5 px-4">Next Scaffold</th>
              <th className="py-3.5 px-4 text-right">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-mono text-slate-700">
            {filteredRecords.length > 0 ? (
              filteredRecords.map((rec) => {
                const hasMcqScores = Array.isArray(rec.mcqScores) && rec.mcqScores.length > 0;
                const mcqAvg = hasMcqScores
                  ? (
                    (rec.mcqScores.reduce((a, b) => a + (typeof b === "number" && !isNaN(b) ? b : 0), 0) /
                      rec.mcqScores.length) *
                    100
                  ).toFixed(0)
                  : null;

                return (
                  <tr key={rec.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-3.5 px-4 text-slate-500">
                      <div className="flex items-center gap-1.5 font-sans">
                        <Clock className="h-3 w-3 text-slate-400" />
                        <span>{rec.date}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 font-sans font-semibold text-slate-900">
                      {rec.concept}
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge
                        variant={difficultyBadgeVariant[rec.difficulty] || "default"}
                        size="sm"
                        className="uppercase font-mono text-[9px]"
                      >
                        {rec.difficulty}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={cn(
                          "font-bold text-sm",
                          rec.bundleScore >= 75
                            ? "text-emerald-700"
                            : rec.bundleScore >= 50
                              ? "text-amber-700"
                              : "text-rose-700"
                        )}
                      >
                        {typeof rec.bundleScore === "number" ? `${rec.bundleScore.toFixed(1)}%` : "0.0%"}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      {mcqAvg !== null ? `${mcqAvg}%` : "N/A"}
                    </td>
                    <td className="py-3.5 px-4 text-blue-700 font-medium">
                      {typeof rec.shortAnswerScore === "number" ? `${rec.shortAnswerScore.toFixed(1)}%` : "Not Recorded"}
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      {(() => {
                        const codingInfo = getCodingEvaluationDisplay(rec);
                        if (codingInfo.isPending) {
                          return (
                            <span className="text-amber-700 font-medium">
                              Pending evaluation
                            </span>
                          );
                        }
                        if (codingInfo.isMissingMetadata) {
                          return (
                            <span className="text-slate-500">
                              Not evaluated
                            </span>
                          );
                        }
                        return <span>{codingInfo.tableCellLabel}</span>;
                      })()}
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge
                        variant={difficultyBadgeVariant[rec.nextDifficulty]}
                        size="sm"
                        className="uppercase font-mono text-[9px]"
                      >
                        {rec.nextDifficulty}
                      </Badge>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedRecord(rec)}
                        className="h-7 px-2 text-teal-700 hover:text-teal-800 hover:bg-teal-50 text-xs gap-1 font-sans"
                      >
                        <span>Breakdown</span>
                        <ExternalLink className="h-3 w-3" />
                      </Button>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={9} className="py-12 text-center text-slate-500 font-sans">
                  <div className="flex flex-col items-center justify-center gap-2">
                    <FileQuestion className="h-8 w-8 text-slate-400" />
                    <p className="text-sm font-medium text-slate-800">
                      No matching assessment sessions found.
                    </p>
                    <p className="text-xs text-slate-500">
                      Try adjusting your search query or difficulty filters.
                    </p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Accessible Question Breakdown Modal */}
      {selectedRecord && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="relative w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl text-slate-900 space-y-5">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-200 pb-3">
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <Badge variant="default" size="sm">
                    {selectedRecord.concept}
                  </Badge>
                  <Badge
                    variant={difficultyBadgeVariant[selectedRecord.difficulty] || "default"}
                    size="sm"
                    className="uppercase font-mono text-[9px]"
                  >
                    {selectedRecord.difficulty}
                  </Badge>
                  <span className="text-xs text-slate-500 font-mono">{selectedRecord.date}</span>
                  {selectedRecord.submissionId && (
                    <span className="text-[10px] text-slate-500 font-mono">
                      ID: {selectedRecord.submissionId.length > 24 ? `${selectedRecord.submissionId.slice(0, 24)}...` : selectedRecord.submissionId}
                    </span>
                  )}
                </div>
                <h3 id="modal-title" className="text-lg font-bold text-slate-900">
                  Granular Assessment Breakdown
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRecord(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Performance Summary Banner */}
            <div className="grid grid-cols-3 gap-3 font-mono text-xs">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-slate-500 block text-[10px]">Bundle Average</span>
                <span className="text-emerald-700 font-bold text-base">
                  {typeof selectedRecord.bundleScore === "number" ? `${selectedRecord.bundleScore.toFixed(1)}%` : "0.0%"}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-slate-500 block text-[10px]">Short-Answer Score</span>
                <span className="text-blue-700 font-bold text-base">
                  {typeof selectedRecord.shortAnswerScore === "number" ? `${selectedRecord.shortAnswerScore.toFixed(1)}%` : "Not Recorded"}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200">
                <span className="text-slate-500 block text-[10px]">Code Evaluation</span>
                {(() => {
                  const codingInfo = getCodingEvaluationDisplay(selectedRecord);
                  return (
                    <span className={codingInfo.isPending ? "text-amber-700 font-bold text-xs" : codingInfo.isMissingMetadata ? "text-slate-500 font-bold text-xs" : "text-slate-800 font-bold text-base"}>
                      {codingInfo.summaryCardLabel}
                    </span>
                  );
                })()}
              </div>
            </div>

            {/* 1. MCQs Breakdown */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                  1. Multiple Choice Questions
                </h4>
                <span className="text-[11px] font-mono text-slate-600">
                  MCQ Performance:{" "}
                  <b className="text-slate-900">
                    {Array.isArray(selectedRecord.mcqScores) && selectedRecord.mcqScores.length > 0
                      ? `${(
                        (selectedRecord.mcqScores.reduce((a, b) => a + (typeof b === "number" && !isNaN(b) ? b : 0), 0) /
                          selectedRecord.mcqScores.length) *
                        100
                      ).toFixed(0)}%`
                      : "N/A"}
                  </b>
                </span>
              </div>
              {selectedRecord.details.mcqs && selectedRecord.details.mcqs.length > 0 ? (
                <div className="space-y-2">
                  {selectedRecord.details.mcqs.map((mcq, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs space-y-1.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800">
                          MCQ {idx + 1}: {mcq.question}
                        </span>
                        {mcq.isCorrect ? (
                          <span className="flex items-center gap-1 text-emerald-700 font-mono text-[11px]">
                            <CheckCircle2 className="h-3.5 w-3.5" /> Correct
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-rose-700 font-mono text-[11px]">
                            <XCircle className="h-3.5 w-3.5" /> Incorrect
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 flex items-center gap-4">
                        <span>Selected: <b className="text-slate-800">{mcq.selected}</b></span>
                        <span>Correct: <b className="text-emerald-700">{mcq.correct}</b></span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 text-xs text-slate-600 space-y-1 font-sans">
                  <p className="text-slate-800 font-medium text-xs">
                    Individual MCQ prompts and option selections were not retained.
                  </p>
                  <p className="text-[11px] text-slate-500 font-mono leading-relaxed">
                    {Array.isArray(selectedRecord.mcqScores) && selectedRecord.mcqScores.length > 0
                      ? `The score ledger stores aggregate correctness only: ${selectedRecord.mcqScores.length} question(s) recorded (${selectedRecord.mcqScores.map((s, i) => `Q${i + 1}: ${s > 0 ? "Correct" : "Incorrect"}`).join(", ")}).`
                      : "No MCQ scores were recorded for this assessment session."}
                  </p>
                </div>
              )}
            </div>

            {/* 2. Conceptual Short Answer */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                  2. Conceptual Short Answer
                </h4>
                <span className="text-[11px] font-mono text-blue-700">
                  Recorded Score:{" "}
                  <b>
                    {typeof selectedRecord.shortAnswerScore === "number"
                      ? `${selectedRecord.shortAnswerScore.toFixed(1)}%`
                      : "Not Recorded"}
                  </b>
                </span>
              </div>
              {selectedRecord.details.shortAnswer?.studentAnswer || selectedRecord.details.shortAnswer?.rubric ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 text-xs space-y-2">
                  {selectedRecord.details.shortAnswer.question && (
                    <p className="font-semibold text-slate-800">
                      {selectedRecord.details.shortAnswer.question}
                    </p>
                  )}
                  {selectedRecord.details.shortAnswer.studentAnswer && (
                    <div className="rounded-lg bg-white p-2.5 border border-slate-200">
                      <span className="text-[10px] font-mono text-slate-500 block mb-1">
                        Student Submitted Answer:
                      </span>
                      <p className="text-slate-700 italic">
                        "{selectedRecord.details.shortAnswer.studentAnswer}"
                      </p>
                    </div>
                  )}
                  {selectedRecord.details.shortAnswer.rubric && (
                    <div className="rounded-lg bg-white p-2.5 border border-slate-200">
                      <span className="text-[10px] font-mono text-slate-500 block mb-1">
                        Reference Rubric:
                      </span>
                      <p className="text-slate-600 text-[11px]">
                        "{selectedRecord.details.shortAnswer.rubric}"
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 text-xs text-slate-600 space-y-1 font-sans">
                  <p className="text-slate-800 font-medium text-xs">
                    Student response text and evaluation rubrics were not retained.
                  </p>
                  <p className="text-[11px] text-slate-500 font-mono leading-relaxed">
                    {typeof selectedRecord.shortAnswerScore === "number"
                      ? `Recorded score: ${selectedRecord.shortAnswerScore.toFixed(1)}%.`
                      : "No short-answer score was recorded for this assessment session."}
                  </p>
                </div>
              )}
            </div>

            {/* 3. Coding Challenge */}
            {(() => {
              const codingInfo = getCodingEvaluationDisplay(selectedRecord);
              return (
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 font-mono">
                      3. Python Coding Challenge
                    </h4>
                    <span className="text-[11px] font-mono text-slate-600">
                      Recorded Code Score:{" "}
                      <b className={codingInfo.isPending ? "text-amber-700" : codingInfo.isMissingMetadata ? "text-slate-500" : "text-slate-900"}>
                        {codingInfo.codeScoreLabel}
                      </b>
                    </span>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3.5 text-xs space-y-2">
                    {selectedRecord.details.coding?.problem && (
                      <p className="font-semibold text-slate-800">
                        {selectedRecord.details.coding.problem}
                      </p>
                    )}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono pt-1">
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                        <span className="text-slate-500 block text-[10px] uppercase">Execution</span>
                        <span className={codingInfo.isPending ? "text-amber-700 font-medium" : codingInfo.isMissingMetadata ? "text-slate-500 font-medium" : "text-slate-700 font-medium"}>
                          {codingInfo.executionLabel}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                        <span className="text-slate-500 block text-[10px] uppercase">Automated Tests</span>
                        <span className={codingInfo.isPending ? "text-amber-700 font-medium" : codingInfo.isMissingMetadata ? "text-slate-500 font-medium" : "text-slate-700 font-medium"}>
                          {codingInfo.automatedTestsLabel}
                        </span>
                      </div>
                      <div className="p-2.5 rounded-lg bg-white border border-slate-200">
                        <span className="text-slate-500 block text-[10px] uppercase">Recorded Code Score</span>
                        <span className={codingInfo.isPending ? "text-amber-700 font-bold text-[11px]" : codingInfo.isMissingMetadata ? "text-slate-500 font-bold text-xs" : "text-slate-900 font-bold"}>
                          {codingInfo.codeScoreLabel}
                        </span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-500 font-mono mt-1">
                      {codingInfo.executionNotice}
                    </p>
                  </div>
                </div>
              );
            })()}

            {/* Scaffolding Policy Outcome */}
            <div className="rounded-xl border border-teal-200 bg-teal-50/80 p-3.5 text-xs text-teal-950 flex items-start gap-2">
              <Sparkles className="h-4 w-4 text-teal-700 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-teal-900">Recommended Next Step:</span>
                <p className="text-slate-700 text-[11px] mt-0.5">
                  {selectedRecord.scaffoldingReason} (Next: {selectedRecord.nextDifficulty.toUpperCase()})
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedRecord(null)}
                className="border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-50"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

