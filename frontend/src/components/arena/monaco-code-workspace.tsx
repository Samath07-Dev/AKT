"use client";

import * as React from "react";
import Editor from "@monaco-editor/react";
import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Play, CheckCircle2, XCircle, RotateCcw, Terminal, AlertCircle, ShieldCheck, RefreshCw } from "lucide-react";
import {
  getPracticeSandboxPresentation,
  type SandboxConnectionStatus,
  type CodeResultMode,
} from "@/lib/practice-sandbox-ui";
import { ProgressiveHintPanel } from "./progressive-hint-panel";

export interface MockTestCaseResult {
  testIndex: number;
  call: string;
  passed: boolean;
  expected?: string;
  actual?: string;
  description?: string;
  statusLabel?: string;
}

export interface MonacoCodeWorkspaceProps {
  questionId?: string;
  questionNumber: number;
  problem: string;
  code: string;
  onChange: (val: string) => void;
  onResetCode?: () => void;
  hints?: string[];
  difficulty?: "easy" | "medium" | "hard";
  concept?: string;
  testCases?: Array<{
    call: string;
    description: string;
  }>;
  mockResults?: MockTestCaseResult[] | null;
  onRunMockTests?: () => void;
  onRunDockerTests?: () => void;
  isRunningDockerTests?: boolean;
  sandboxStatus?: SandboxConnectionStatus;
  resultMode?: CodeResultMode;
  dockerCodeScore?: number | null;
  dockerRuntimeError?: string | null;
  isSubmitted?: boolean;
  isLiveEvaluated?: boolean;
}

export function MonacoCodeWorkspace({
  questionId,
  questionNumber,
  problem,
  code,
  onChange,
  onResetCode,
  hints,
  difficulty = "medium",
  concept = "Python",
  testCases = [],
  mockResults = null,
  onRunMockTests,
  onRunDockerTests,
  isRunningDockerTests = false,
  sandboxStatus = "offline",
  resultMode,
  dockerCodeScore = null,
  dockerRuntimeError = null,
  isSubmitted = false,
  isLiveEvaluated = false,
}: MonacoCodeWorkspaceProps) {
  const [editorMounted, setEditorMounted] = React.useState(false);

  const effectiveResultMode: CodeResultMode =
    resultMode ?? (isSubmitted && isLiveEvaluated ? "docker_executed" : mockResults ? "syntax_preview" : "none");

  const testsPassed = mockResults ? mockResults.filter((r) => r.passed).length : 0;
  const testsTotal = mockResults ? mockResults.length : testCases.length;

  const presentation = getPracticeSandboxPresentation({
    sandboxStatus,
    resultMode: effectiveResultMode,
    isSubmitted,
    testsPassed,
    testsTotal,
    codeScore: dockerCodeScore,
  });

  const difficultyVariant = {
    easy: "success" as const,
    medium: "warning" as const,
    hard: "danger" as const,
  };

  return (
    <Card className="border-slate-200/90 bg-white shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-teal-50 border border-teal-200/90 text-xs font-mono font-bold text-teal-800">
              Q{questionNumber}
            </span>
            <Badge variant="default" size="sm">
              {concept}
            </Badge>
            <Badge
              variant={difficultyVariant[difficulty]}
              size="sm"
              className="uppercase font-mono text-[9px]"
            >
              {difficulty}
            </Badge>
          </div>
          <Badge variant={presentation.badgeVariant} size="sm" className="font-mono text-[10px]">
            {presentation.badgeLabel}
          </Badge>
        </div>
        <CardTitle className="text-base sm:text-lg leading-snug mt-2 text-slate-900 font-bold">
          {problem}
        </CardTitle>
        <CardDescription className="text-xs text-slate-500">
          {presentation.cardDescription}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 pt-1">
        {/* Progressive Hint Panel */}
        {hints && hints.length > 0 && (
          <ProgressiveHintPanel
            hints={hints}
            questionId={questionId || `q${questionNumber}`}
            isSubmitted={isSubmitted}
          />
        )}

        {/* Editor Wrapper with Toolbar */}
        <div className="rounded-xl border border-slate-300 overflow-hidden bg-[#1E1E1E] shadow-xs">
          {/* Editor Top Bar */}
          <div className="flex items-center justify-between px-4 py-2 bg-slate-100 border-b border-slate-200 text-xs">
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full", presentation.editorDotClass)} />
              <span className="font-mono text-slate-700 text-[11px] font-medium">
                solution.py (Python Mode)
              </span>
            </div>
            <div className="flex items-center gap-2">
              {onResetCode && !isSubmitted && (
                <button
                  type="button"
                  onClick={onResetCode}
                  className="flex items-center gap-1 text-[11px] font-mono text-slate-600 hover:text-slate-900 transition-colors"
                  title="Reset to starter template"
                >
                  <RotateCcw className="h-3 w-3" />
                  <span>Reset</span>
                </button>
              )}
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white text-slate-600 border border-slate-200">
                Monaco Editor
              </span>
            </div>
          </div>

          {/* Monaco Editor Container */}
          <div className="h-64 sm:h-72 w-full">
            <Editor
              height="100%"
              defaultLanguage="python"
              language="python"
              theme="vs-dark"
              value={code}
              onChange={(val) => onChange(val || "")}
              onMount={() => setEditorMounted(true)}
              options={{
                readOnly: isSubmitted,
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "JetBrains Mono, Menlo, monospace",
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 4,
                padding: { top: 12, bottom: 12 },
              }}
              loading={
                <div className="h-full flex items-center justify-center font-mono text-xs text-slate-500 bg-[#1E1E1E]">
                  Initializing Monaco Python Workspace...
                </div>
              }
            />
          </div>
        </div>

        {/* Action Toolbar */}
        {!isSubmitted && (onRunMockTests || onRunDockerTests) && (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
            <span className="text-[11px] font-mono text-slate-500">
              Unit Tests: {testCases.length} specifications defined
            </span>
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              {onRunMockTests && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onRunMockTests}
                  disabled={isRunningDockerTests}
                  className="gap-1.5 w-full sm:w-auto justify-center border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Check Code Syntax (Preview)</span>
                </Button>
              )}
              {presentation.canRunDockerTests && onRunDockerTests && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={onRunDockerTests}
                  disabled={isRunningDockerTests}
                  className="gap-1.5 shadow-xs w-full sm:w-auto justify-center"
                >
                  {isRunningDockerTests ? (
                    <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3.5 w-3.5 fill-current" />
                  )}
                  <span>
                    {isRunningDockerTests ? "Running in Docker..." : "Run Tests (Docker Sandbox)"}
                  </span>
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Test Case Results Panel */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-200 pb-2 gap-1">
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-teal-700" />
              <span className="text-xs font-bold text-slate-900">
                {presentation.panelTitle}
              </span>
            </div>
            {presentation.counterLabel && (
              <span className="text-[11px] font-mono text-slate-700 font-semibold">
                {presentation.counterLabel}
              </span>
            )}
          </div>

          <div className="text-[11px] text-slate-600 flex items-center gap-1.5 bg-white p-2.5 rounded-lg border border-slate-200">
            {effectiveResultMode === "docker_executed" || sandboxStatus === "available" ? (
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
            )}
            <span>{presentation.panelNotice}</span>
          </div>

          {effectiveResultMode === "docker_executed" && dockerRuntimeError && (
            <div className="text-[11px] font-mono text-rose-800 bg-rose-50 border border-rose-200 rounded p-2 break-words">
              Runtime Error: {dockerRuntimeError}
            </div>
          )}

          {/* Test cases list */}
          <div className="space-y-2">
            {(mockResults || testCases.map((tc, idx) => ({
              testIndex: idx + 1,
              call: tc.call,
              passed: false,
              description: tc.description,
              statusLabel: "NOT RUN",
            }))).map((res) => (
              <div
                key={res.testIndex}
                className={cn(
                  "rounded-lg border p-2.5 text-xs font-mono transition-colors",
                  mockResults
                    ? res.passed
                      ? "border-emerald-300 bg-emerald-50 text-emerald-950"
                      : "border-amber-300 bg-amber-50 text-amber-950"
                    : "border-slate-200 bg-white text-slate-600"
                )}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
                  <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                    <span className="font-semibold text-slate-800 shrink-0">
                      Test #{res.testIndex}:
                    </span>
                    <code className="text-teal-900 bg-slate-100 px-1.5 py-0.5 rounded break-all text-[11px] border border-slate-200">
                      {res.call}
                    </code>
                  </div>
                  {mockResults && (
                    <span className="flex items-center gap-1 font-bold text-[11px] shrink-0 self-start sm:self-auto">
                      {res.passed ? (
                        <>
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                          <span className="text-emerald-900">{res.statusLabel || "SYNTAX CHECK PASSED"}</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                          <span className="text-amber-900">{res.statusLabel || "INCOMPLETE"}</span>
                        </>
                      )}
                    </span>
                  )}
                </div>
                {res.description && (
                  <p className="text-[11px] text-slate-600 font-sans mt-1">
                    {res.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
