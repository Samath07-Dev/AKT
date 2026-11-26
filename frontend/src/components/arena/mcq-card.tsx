"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, HelpCircle, ArrowRight } from "lucide-react";
import { ProgressiveHintPanel } from "./progressive-hint-panel";

export interface MCQOption {
  key: string;       // "A", "B", "C", "D"
  text: string;      // Option content
}

export interface MCQCardProps {
  questionId?: string;
  questionNumber: number;
  question: string;
  options: string[] | MCQOption[];
  selectedOption: string | null;
  onSelectOption: (optionKey: string) => void;
  hints?: string[];
  difficulty?: "easy" | "medium" | "hard";
  concept?: string;
  onSubmitAnswer?: () => void;
  isSubmitted?: boolean;
  feedback?: {
    isCorrect: boolean;
    correctOption?: string;
    explanation?: string;
    score?: number;
  } | null;
}

export function MCQCard({
  questionId,
  questionNumber,
  question,
  options,
  selectedOption,
  onSelectOption,
  hints,
  difficulty = "medium",
  concept = "Python",
  onSubmitAnswer,
  isSubmitted = false,
  feedback,
}: MCQCardProps) {
  // Normalize options to key/text pairs
  const normalizedOptions: MCQOption[] = React.useMemo(() => {
    return options.map((opt, idx) => {
      if (typeof opt === "string") {
        const parts = opt.split(")");
        if (parts.length > 1 && parts[0].length <= 2) {
          return { key: parts[0].trim().toUpperCase(), text: parts.slice(1).join(")").trim() };
        }
        const letter = String.fromCharCode(65 + idx);
        return { key: letter, text: opt };
      }
      return opt;
    });
  }, [options]);

  const difficultyVariant = {
    easy: "success" as const,
    medium: "warning" as const,
    hard: "danger" as const,
  };

  return (
    <Card className="border-slate-200/90 bg-white shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-50 border border-teal-200/90 text-xs font-mono font-bold text-teal-800">
              Q{questionNumber}
            </span>
            <Badge variant="default" size="sm">
              {concept}
            </Badge>
            <Badge variant={difficultyVariant[difficulty]} size="sm" className="uppercase font-mono text-[9px]">
              {difficulty}
            </Badge>
          </div>
          <span className="text-[11px] font-mono text-slate-500">Multiple Choice</span>
        </div>
        <CardTitle className="text-base sm:text-lg leading-snug mt-2 text-slate-900 font-bold">
          {question}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Accessible Radio Group */}
        <div
          role="radiogroup"
          aria-label={`Options for Question ${questionNumber}`}
          className="space-y-2.5"
        >
          {normalizedOptions.map((opt) => {
            const isSelected = selectedOption === opt.key;
            let optionStateStyles = "border-slate-200 bg-slate-50/50 hover:border-slate-300 hover:bg-slate-100/60 text-slate-800";

            if (isSubmitted && feedback) {
              if (opt.key === feedback.correctOption) {
                optionStateStyles = "border-emerald-300 bg-emerald-50 text-emerald-950 ring-1 ring-emerald-400 font-medium";
              } else if (isSelected && !feedback.isCorrect) {
                optionStateStyles = "border-rose-300 bg-rose-50 text-rose-950 ring-1 ring-rose-400 font-medium";
              } else {
                optionStateStyles = "border-slate-200 bg-slate-50/40 text-slate-400 opacity-60";
              }
            } else if (isSelected) {
              optionStateStyles = "border-teal-600 bg-teal-50/60 text-teal-950 ring-2 ring-teal-600/30 shadow-xs";
            }

            return (
              <button
                key={opt.key}
                type="button"
                role="radio"
                aria-checked={isSelected}
                disabled={isSubmitted}
                onClick={() => onSelectOption(opt.key)}
                className={cn(
                  "w-full flex items-center justify-between rounded-xl border p-3.5 text-left text-xs sm:text-sm transition-all duration-150 select-none outline-none focus-visible:ring-2 focus-visible:ring-teal-600",
                  optionStateStyles
                )}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-lg font-mono text-xs font-bold border transition-colors",
                      isSelected
                        ? "border-teal-600 bg-teal-700 text-white"
                        : "border-slate-300 bg-white text-slate-600"
                    )}
                  >
                    {opt.key}
                  </span>
                  <span className="font-medium leading-relaxed">{opt.text}</span>
                </div>

                {isSubmitted && feedback && (
                  <div className="shrink-0 ml-2">
                    {opt.key === feedback.correctOption && (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    )}
                    {isSelected && !feedback.isCorrect && (
                      <XCircle className="h-4 w-4 text-rose-600" />
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>

        {/* Progressive Hint Panel */}
        {hints && hints.length > 0 && (
          <ProgressiveHintPanel
            hints={hints}
            questionId={questionId || `q${questionNumber}`}
            isSubmitted={isSubmitted}
          />
        )}

        {/* Action Button if unsubmitted */}
        {!isSubmitted && onSubmitAnswer && (
          <div className="pt-2 flex justify-end">
            <Button
              variant="primary"
              size="sm"
              disabled={!selectedOption}
              onClick={onSubmitAnswer}
              className="gap-1.5"
            >
              <span>Submit Answer</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {/* Feedback Display */}
        {isSubmitted && feedback && (
          <div
            className={cn(
              "rounded-xl border p-3.5 text-xs transition-all",
              feedback.isCorrect
                ? "border-emerald-200 bg-emerald-50/80 text-emerald-950"
                : "border-rose-200 bg-rose-50/80 text-rose-950"
            )}
          >
            <div className="flex items-center gap-2 font-bold mb-1">
              {feedback.isCorrect ? (
                <>
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  <span className="text-emerald-900">Correct Answer!</span>
                </>
              ) : (
                <>
                  <XCircle className="h-4 w-4 text-rose-600" />
                  <span className="text-rose-900">
                    Incorrect. Correct Option is {feedback.correctOption}.
                  </span>
                </>
              )}
              {feedback.score !== undefined && (
                <span className="ml-auto font-mono text-[11px] text-slate-500">
                  Score: {(feedback.score * 100).toFixed(0)}%
                </span>
              )}
            </div>
            {feedback.explanation && (
              <p className="text-slate-700 mt-1 leading-relaxed text-[11px]">
                {feedback.explanation}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

