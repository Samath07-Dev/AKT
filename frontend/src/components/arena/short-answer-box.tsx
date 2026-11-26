"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Sparkles, CheckCircle2, AlertTriangle, FileText, ArrowRight } from "lucide-react";
import { ProgressiveHintPanel } from "./progressive-hint-panel";

export interface ShortAnswerFeedback {
  similarityScore: number; // 0 to 100
  isAcceptable: boolean;
  missingKeywords: string[];
  feedbackText: string;
}

export interface ShortAnswerBoxProps {
  questionId?: string;
  questionNumber: number;
  question: string;
  value: string;
  onChange: (val: string) => void;
  hints?: string[];
  difficulty?: "easy" | "medium" | "hard";
  concept?: string;
  maxWords?: number;
  onSubmitAnswer?: () => void;
  isSubmitted?: boolean;
  feedback?: ShortAnswerFeedback | null;
}

export function ShortAnswerBox({
  questionId,
  questionNumber,
  question,
  value,
  onChange,
  hints,
  difficulty = "medium",
  concept = "Python",
  maxWords = 150,
  onSubmitAnswer,
  isSubmitted = false,
  feedback,
}: ShortAnswerBoxProps) {
  const wordCount = React.useMemo(() => {
    const trimmed = value.trim();
    return trimmed ? trimmed.split(/\s+/).length : 0;
  }, [value]);

  const difficultyVariant = {
    easy: "success" as const,
    medium: "warning" as const,
    hard: "danger" as const,
  };

  const isOverLimit = wordCount > maxWords;

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
          <span className="text-[11px] font-mono text-slate-500">
            Conceptual Short Answer
          </span>
        </div>
        <CardTitle className="text-base sm:text-lg leading-snug mt-2 text-slate-900 font-bold">
          {question}
        </CardTitle>
        <CardDescription className="text-xs text-slate-500">
          Provide a concise conceptual explanation in your own words.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Text Area */}
        <div className="space-y-1.5">
          <textarea
            value={value}
            disabled={isSubmitted}
            onChange={(e) => onChange(e.target.value)}
            rows={4}
            placeholder="Write your explanation here..."
            className={cn(
              "w-full rounded-xl border border-slate-300 bg-white p-3.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus:border-teal-600 transition-all font-sans leading-relaxed resize-y min-h-[110px] shadow-xs",
              isOverLimit ? "border-rose-400 focus-visible:ring-rose-500" : "border-slate-300 hover:border-slate-400",
              isSubmitted && "opacity-90 cursor-not-allowed bg-slate-50 border-slate-200 text-slate-800"
            )}
          />

          {/* Word Counter & Guidelines */}
          <div className="flex items-center justify-between text-[11px] font-mono px-1">
            <span className="text-slate-500">
              Target: 20–{maxWords} words
            </span>
            <span
              className={cn(
                "transition-colors",
                isOverLimit
                  ? "text-rose-600 font-bold"
                  : wordCount < 5
                    ? "text-slate-400"
                    : "text-slate-600 font-medium"
              )}
            >
              {wordCount} / {maxWords} words
            </span>
          </div>
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
          <div className="pt-1 flex justify-end">
            <Button
              variant="primary"
              size="sm"
              disabled={wordCount === 0 || isOverLimit}
              onClick={onSubmitAnswer}
              className="gap-1.5"
            >
              <span>Submit Conceptual Answer</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}

        {/* Semantic Evaluation Feedback */}
        {isSubmitted && feedback && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-200 pb-2.5">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-teal-700" />
                <span className="text-xs font-bold text-slate-900">
                  Semantic Evaluation
                </span>
                <Badge
                  variant={feedback.isAcceptable ? "success" : "danger"}
                  size="sm"
                >
                  {feedback.isAcceptable ? "Conceptually Sound" : "Needs Refinement"}
                </Badge>
              </div>
              <div className="font-mono text-xs text-slate-600">
                Cosine Similarity:{" "}
                <b className="text-blue-700">{feedback.similarityScore.toFixed(1)}%</b>
              </div>
            </div>

            <Progress
              value={feedback.similarityScore}
              variant={feedback.isAcceptable ? "mastery" : "danger"}
              size="sm"
            />

            <p className="text-xs text-slate-700 leading-relaxed">
              {feedback.feedbackText}
            </p>

            {feedback.missingKeywords && feedback.missingKeywords.length > 0 && (
              <div className="pt-1">
                <span className="text-[11px] font-mono text-slate-500 block mb-1.5">
                  Missing Conceptual Terminology:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {feedback.missingKeywords.map((kw) => (
                    <Badge
                      key={kw}
                      variant="warning"
                      size="sm"
                      className="font-mono text-[10px]"
                    >
                      {kw}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

