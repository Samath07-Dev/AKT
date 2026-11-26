"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Lightbulb, ChevronDown, ChevronUp, Sparkles, Lock, Unlock, Check } from "lucide-react";

export interface ProgressiveHintPanelProps {
  hints?: string[];
  questionId: string;
  isSubmitted?: boolean;
  className?: string;
}

const HINT_TIER_CONFIG = [
  {
    level: 1,
    title: "Level 1: Conceptual Direction",
    badgeVariant: "info" as const,
    description: "Core programming concept or rule to keep in mind.",
  },
  {
    level: 2,
    title: "Level 2: Strategic Guidance",
    badgeVariant: "warning" as const,
    description: "Algorithmic logic, structure, or elimination criteria.",
  },
  {
    level: 3,
    title: "Level 3: Implementation Clue",
    badgeVariant: "default" as const,
    description: "Specific syntax detail, method contract, or edge case.",
  },
];

export function ProgressiveHintPanel({
  hints = [],
  questionId,
  isSubmitted = false,
  className,
}: ProgressiveHintPanelProps) {
  const [unlockedLevel, setUnlockedLevel] = React.useState<number>(0);
  const [isExpanded, setIsExpanded] = React.useState<boolean>(false);

  // Reset local hint state when navigating between questions
  React.useEffect(() => {
    setUnlockedLevel(0);
    setIsExpanded(false);
  }, [questionId]);

  if (!hints || hints.length === 0) {
    return null;
  }

  const totalAvailable = Math.min(hints.length, 3);

  const handleToggleExpand = () => {
    setIsExpanded((prev) => {
      const next = !prev;
      // Auto-unlock level 1 when first opening if nothing is unlocked yet
      if (next && unlockedLevel === 0) {
        setUnlockedLevel(1);
      }
      return next;
    });
  };

  const handleUnlockNext = () => {
    if (unlockedLevel < totalAvailable) {
      setUnlockedLevel((prev) => prev + 1);
    }
  };

  return (
    <div
      className={cn(
        "rounded-xl border transition-all shadow-xs",
        isExpanded ? "border-amber-300 bg-white" : "border-slate-200 bg-white hover:border-slate-300",
        className
      )}
    >
      {/* Accordion Header / Trigger Button */}
      <button
        type="button"
        onClick={handleToggleExpand}
        className="w-full flex items-center justify-between p-3 text-left transition-colors select-none group"
        aria-expanded={isExpanded}
        aria-label={`Hints for question ${questionId}`}
      >
        <div className="flex items-center gap-2.5">
          <div
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-lg border transition-colors",
              unlockedLevel > 0
                ? "border-amber-300 bg-amber-50 text-amber-800"
                : "border-slate-200 bg-slate-100 text-slate-500 group-hover:text-amber-700 group-hover:border-slate-300"
            )}
          >
            <Lightbulb className="h-4 w-4" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-900 group-hover:text-teal-900 transition-colors">
                Progressive Hints
              </span>
              <Badge
                variant={unlockedLevel > 0 ? "warning" : "default"}
                size="sm"
                className="font-mono text-[9px] uppercase tracking-wider"
              >
                {unlockedLevel === 0
                  ? `${totalAvailable} Available`
                  : `${unlockedLevel} / ${totalAvailable} Unlocked`}
              </Badge>
            </div>
            <p className="text-[11px] text-slate-500">
              Formative guidance without revealing answers or reference solutions.
            </p>
          </div>
        </div>

        <div className="shrink-0 text-slate-400 group-hover:text-slate-600 transition-colors p-1">
          {isExpanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </div>
      </button>

      {/* Accordion Body */}
      {isExpanded && (
        <div className="border-t border-slate-200 p-3.5 space-y-3 bg-slate-50/50 rounded-b-xl">
          {/* Display all currently unlocked hints */}
          <div className="space-y-2.5">
            {hints.slice(0, unlockedLevel).map((hintText, idx) => {
              const tier = HINT_TIER_CONFIG[idx] || HINT_TIER_CONFIG[0];
              return (
                <div
                  key={idx}
                  className="rounded-lg border border-slate-200 bg-white p-3 space-y-1.5 transition-all shadow-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                      <Badge variant={tier.badgeVariant} size="sm" className="text-[10px]">
                        {tier.title}
                      </Badge>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">
                      Step {idx + 1} of {totalAvailable}
                    </span>
                  </div>
                  <p className="text-xs text-slate-800 leading-relaxed font-sans pl-1">
                    {hintText}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Action to unlock subsequent hints */}
          {unlockedLevel < totalAvailable ? (
            <div className="pt-1 flex items-center justify-between gap-3 flex-wrap">
              <span className="text-[11px] text-slate-500 flex items-center gap-1.5">
                <Lock className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                <span>
                  {totalAvailable - unlockedLevel} additional hint
                  {totalAvailable - unlockedLevel > 1 ? "s" : ""} locked.
                </span>
              </span>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleUnlockNext}
                className="gap-1.5 text-xs text-amber-900 border-amber-300 bg-amber-50 hover:bg-amber-100 hover:border-amber-400 font-medium"
              >
                <Unlock className="h-3.5 w-3.5 text-amber-700" />
                <span>
                  Unlock {HINT_TIER_CONFIG[unlockedLevel]?.title || `Hint ${unlockedLevel + 1}`}
                </span>
              </Button>
            </div>
          ) : (
            <div className="pt-1 text-center">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-mono text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
                <Check className="h-3 w-3" />
                All 3 hints unlocked · Formative practice (zero score penalty)
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

