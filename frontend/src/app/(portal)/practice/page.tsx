"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import {
  Code2,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Sparkles,
  Award,
  RefreshCw,
  Terminal,
  AlertCircle,
  HelpCircle,
  SlidersHorizontal,
  Compass,
  Check,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  MCQCard,
  ShortAnswerBox,
  MonacoCodeWorkspace,
  MockTestCaseResult,
} from "@/components/arena";
import {
  CANONICAL_KNOWLEDGE_COMPETENCIES,
  ACTIVE_DEMONSTRATION_TARGET,
} from "@/lib/mock-data/curriculum-store";
import {
  getPublicBundle,
  BundleEvaluationResult,
  PublicConceptBundle,
  PublicCodingQuestion,
  PublicQuestion,
} from "@/lib/mock-data/bundle-catalog";
import { hasMeaningfulCode } from "@/lib/code-structure";
import type {
  SandboxConnectionStatus,
  CodeResultMode,
} from "@/lib/practice-sandbox-ui";

const ALL_CONCEPTS = [
  "Variables",
  "Syntax",
  "Conditionals",
  "Loops",
  "Functions",
  "Arrays",
  "Dictionaries",
  "OOP",
  "File Handling",
  "Exception Handling",
] as const;

type ConceptName = typeof ALL_CONCEPTS[number];
type DifficultyLevel = "easy" | "medium" | "hard";
type LearningMode = "adaptive" | "student";
type PracticeQuestion = PublicQuestion & { hints?: string[] };

function formatApiBundle(
  apiData: any,
  concept: string,
  difficulty: DifficultyLevel
): PublicConceptBundle | null {
  const b = apiData?.bundle;
  if (!b) return null;

  const rawMcqs = Array.isArray(b.mcqs) ? b.mcqs : [];
  const mcqs: PracticeQuestion[] = rawMcqs.map((m: any, idx: number) => {
    let options: { key: string; text: string }[] = [];
    if (Array.isArray(m.options)) {
      options = m.options.map((opt: any, i: number) => ({
        key: typeof opt === "object" && opt?.key ? opt.key : String.fromCharCode(65 + i),
        text: typeof opt === "object" && opt?.text ? opt.text : String(opt),
      }));
    } else if (typeof m.options === "object" && m.options !== null) {
      options = Object.entries(m.options).map(([k, v]) => ({
        key: k,
        text: String(v),
      }));
    }
    return {
      id: m.id || `${concept.toLowerCase()}_${difficulty}_mcq_${idx + 1}`,
      type: "mcq" as const,
      number: idx + 1,
      title: m.question || `Question ${idx + 1}`,
      options,
      hints: Array.isArray(m.hints) ? m.hints : [],
    };
  });

  const questions: PracticeQuestion[] = [...mcqs];

  if (b.short_answer && typeof b.short_answer === "object") {
    questions.push({
      id: b.short_answer.id || `${concept.toLowerCase()}_${difficulty}_sa_1`,
      type: "short_answer" as const,
      number: 4,
      title: b.short_answer.question || "Short Answer Conceptual Question",
      maxWords: 150,
      hints: Array.isArray(b.short_answer.hints) ? b.short_answer.hints : [],
    });
  }

  if (b.coding && typeof b.coding === "object") {
    questions.push({
      id: b.coding.id || `${concept.toLowerCase()}_${difficulty}_code_1`,
      type: "coding" as const,
      number: 5,
      title: b.coding.problem || "Programming Challenge",
      starterCode: b.coding.template || "# Write your solution here\npass\n",
      hints: Array.isArray(b.coding.hints) ? b.coding.hints : [],
      testCases: Array.isArray(b.coding.test_cases)
        ? b.coding.test_cases.map((tc: any) => ({
          call: tc.call || "",
          description: tc.description || "Public unit test assertion",
        }))
        : [],
    });
  }

  if (questions.length === 0) return null;

  return {
    concept,
    difficulty,
    questions: questions as PublicQuestion[],
  };
}

function PracticeArenaInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // 1. Authenticated Live Recommendation State
  const [liveRecommendation, setLiveRecommendation] = React.useState<{
    name: ConceptName;
    difficulty: DifficultyLevel;
    mastery: number;
    uncertainty: number;
    priorityScore: number;
    reasoning?: string;
  } | null>(null);
  const [isRecommendLoading, setIsRecommendLoading] = React.useState(true);
  const [recommendError, setRecommendError] = React.useState<string | null>(null);

  // Authenticated Student Identity (Phase 11C)
  const [user, setUser] = React.useState<{ id: string } | null>(null);
  const isMountedRef = React.useRef(true);

  React.useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // 2. Resolve initial mode, concept, and difficulty from URL parameters or fallbacks
  const initialMode: LearningMode =
    searchParams.get("mode") === "student" ? "student" : "adaptive";

  const paramConcept = searchParams.get("concept");
  const validConcept: ConceptName =
    ALL_CONCEPTS.find(
      (c) => c.toLowerCase() === (paramConcept || "").toLowerCase()
    ) || (initialMode === "adaptive" ? "Variables" : (ACTIVE_DEMONSTRATION_TARGET.concept as ConceptName));

  const paramDifficulty = searchParams.get("difficulty")?.toLowerCase();
  const validDifficulty: DifficultyLevel =
    paramDifficulty === "easy" || paramDifficulty === "medium" || paramDifficulty === "hard"
      ? (paramDifficulty as DifficultyLevel)
      : (initialMode === "adaptive" ? "medium" : (ACTIVE_DEMONSTRATION_TARGET.difficulty as DifficultyLevel));

  // 3. State Management
  const [learningMode, setLearningMode] = React.useState<LearningMode>(initialMode);
  const [selectedConcept, setSelectedConcept] = React.useState<ConceptName>(validConcept);
  const [selectedDifficulty, setSelectedDifficulty] = React.useState<DifficultyLevel>(validDifficulty);

  // Live vs Fallback Bundle Management
  const [liveBundle, setLiveBundle] = React.useState<PublicConceptBundle | null>(null);
  const [isLiveBundle, setIsLiveBundle] = React.useState(false);
  const [isBundleLoading, setIsBundleLoading] = React.useState(false);
  const [bundleError, setBundleError] = React.useState<string | null>(null);

  // Fallback public bundle (sanitized, zero answer keys or test outputs)
  const fallbackBundle = React.useMemo(() => {
    return getPublicBundle(selectedConcept, selectedDifficulty);
  }, [selectedConcept, selectedDifficulty]);

  // Active bundle resolves to live bundle when available, otherwise honest demo fallback
  const currentBundle: PublicConceptBundle = liveBundle || fallbackBundle;

  // Extract starter code for current coding challenge
  const currentCodingQuestion = React.useMemo(() => {
    return currentBundle.questions.find((q) => q.type === "coding") as PublicCodingQuestion | undefined;
  }, [currentBundle]);

  const defaultStarterCode = currentCodingQuestion?.starterCode || "# Write your solution here\npass\n";

  const [currentStep, setCurrentStep] = React.useState(0); // 0 to 4
  const [answers, setAnswers] = React.useState<{
    q1: string | null;
    q2: string | null;
    q3: string | null;
    q4: string;
    q5: string;
  }>({
    q1: null,
    q2: null,
    q3: null,
    q4: "",
    q5: defaultStarterCode,
  });

  const [mockCodeResults, setMockCodeResults] = React.useState<MockTestCaseResult[] | null>(null);
  const [sandboxStatus, setSandboxStatus] = React.useState<SandboxConnectionStatus>("checking");
  const [codeResultMode, setCodeResultMode] = React.useState<CodeResultMode>("none");
  const [isRunningDockerTests, setIsRunningDockerTests] = React.useState(false);
  const [dockerPreviewScore, setDockerPreviewScore] = React.useState<number | null>(null);
  const [dockerPreviewRuntimeError, setDockerPreviewRuntimeError] = React.useState<string | null>(null);
  const [isBundleSubmitted, setIsBundleSubmitted] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [evaluationResult, setEvaluationResult] = React.useState<BundleEvaluationResult | null>(null);
  const [backendRecorded, setBackendRecorded] = React.useState<boolean | null>(null);
  const [persistenceNotice, setPersistenceNotice] = React.useState<string | null>(null);

  // Helper: Check if student provided meaningful implementation code
  const isCodeModified = (rawCode: string) => hasMeaningfulCode(rawCode);

  // Helper: Reset all answers and evaluation state on concept/difficulty shift
  const resetBundleState = (concept: ConceptName, difficulty: DifficultyLevel) => {
    const nextFallback = getPublicBundle(concept, difficulty);
    const nextCodingQ = nextFallback.questions.find((q) => q.type === "coding") as PublicCodingQuestion | undefined;
    const starter = nextCodingQ?.starterCode || "# Write your solution here\npass\n";

    setAnswers({
      q1: null,
      q2: null,
      q3: null,
      q4: "",
      q5: starter,
    });
    setMockCodeResults(null);
    setCodeResultMode("none");
    setIsRunningDockerTests(false);
    setDockerPreviewScore(null);
    setDockerPreviewRuntimeError(null);
    setIsBundleSubmitted(false);
    setEvaluationResult(null);
    setBackendRecorded(null);
    setPersistenceNotice(null);
    setSubmitError(null);
    setCurrentStep(0);
  };

  // Probe live Docker sandbox availability via Next.js BFF (fails closed to offline)
  React.useEffect(() => {
    let isMounted = true;
    const checkSandbox = async () => {
      try {
        const res = await fetch("/api/practice/sandbox-status", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          if (isMounted && data?.available === true && data?.status === "READY") {
            setSandboxStatus("available");
            return;
          }
        }
        if (isMounted) setSandboxStatus("offline");
      } catch {
        if (isMounted) setSandboxStatus("offline");
      }
    };
    checkSandbox();
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch authenticated student recommendation from /api/adaptive/recommend
  const loadRecommendation = React.useCallback(
    async (userId?: string, syncSelection: boolean = false) => {
      setIsRecommendLoading(true);
      setRecommendError(null);
      try {
        const url = userId
          ? `/api/adaptive/recommend?student_id=${encodeURIComponent(userId)}`
          : "/api/adaptive/recommend";
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (data && data.recommended_concept && isMountedRef.current) {
            const conceptName = data.recommended_concept as ConceptName;
            const diff =
              (data.recommended_difficulty?.toLowerCase() as DifficultyLevel) || "medium";
            const m =
              typeof data.concept_mastery === "number"
                ? Number((data.concept_mastery * 100).toFixed(1))
                : 30.0;
            const u =
              typeof data.concept_uncertainty === "number"
                ? Number((data.concept_uncertainty * 100).toFixed(1))
                : 50.0;
            const p =
              typeof data.priority_score === "number"
                ? Number(data.priority_score.toFixed(4))
                : 1.0500;

            if (data.student_id) {
              setUser({ id: data.student_id });
            }

            setLiveRecommendation({
              name: conceptName,
              difficulty: diff,
              mastery: m,
              uncertainty: u,
              priorityScore: p,
              reasoning: data.scaffolding_reasoning || data.reasoning,
            });

            // If user did not specify a concept in query params and mode is adaptive, align with recommendation (initial mount only)
            if (syncSelection && !paramConcept && initialMode === "adaptive") {
              setSelectedConcept(conceptName);
              setSelectedDifficulty(diff);
              resetBundleState(conceptName, diff);
            }
            return data;
          }
        }
        if (isMountedRef.current) {
          setRecommendError("Live adaptive recommendation service is currently unavailable.");
        }
      } catch {
        if (isMountedRef.current) {
          setRecommendError("Network error while contacting adaptive recommendation service.");
        }
      } finally {
        if (isMountedRef.current) {
          setIsRecommendLoading(false);
        }
      }
    },
    [paramConcept, initialMode]
  );

  // Initial recommendation load on mount (aligns bundle when in adaptive mode)
  React.useEffect(() => {
    loadRecommendation(undefined, true);
  }, [loadRecommendation]);

  // Synchronize authenticated session user identity
  React.useEffect(() => {
    let active = true;
    fetch("/api/auth/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((authData) => {
        if (active && authData?.student?.studentId) {
          setUser({ id: authData.student.studentId });
        }
      })
      .catch(() => { });
    return () => {
      active = false;
    };
  }, []);

  // Fetch live bundle from BFF API
  React.useEffect(() => {
    let isMounted = true;
    const fetchBundle = async () => {
      setIsBundleLoading(true);
      setBundleError(null);
      try {
        const res = await fetch(
          `/api/practice/bundle/${encodeURIComponent(selectedConcept)}?difficulty=${selectedDifficulty}`
        );
        if (res.ok) {
          const data = await res.json();
          const parsed = formatApiBundle(data, selectedConcept, selectedDifficulty);
          if (parsed && isMounted) {
            setLiveBundle(parsed);
            setIsLiveBundle(true);
            const starter = (parsed.questions.find((q) => q.type === "coding") as PublicCodingQuestion | undefined)?.starterCode;
            if (starter) {
              setAnswers((prev) => ({
                ...prev,
                q5: isCodeModified(prev.q5) ? prev.q5 : starter,
              }));
            }
            return;
          }
        }
        if (isMounted) {
          setLiveBundle(null);
          setIsLiveBundle(false);
        }
      } catch {
        if (isMounted) {
          setLiveBundle(null);
          setIsLiveBundle(false);
          setBundleError("Live bundle fetch unavailable; using offline catalog.");
        }
      } finally {
        if (isMounted) {
          setIsBundleLoading(false);
        }
      }
    };

    fetchBundle();

    return () => {
      isMounted = false;
    };
  }, [selectedConcept, selectedDifficulty]);

  // Sync state when URL params change externally
  React.useEffect(() => {
    const urlConcept = searchParams.get("concept");
    const matched = ALL_CONCEPTS.find(
      (c) => c.toLowerCase() === (urlConcept || "").toLowerCase()
    );
    if (matched && matched !== selectedConcept) {
      setSelectedConcept(matched);
      resetBundleState(matched, selectedDifficulty);
    }
  }, [searchParams]);

  // Switch Learning Mode
  const handleModeSwitch = (newMode: LearningMode) => {
    setLearningMode(newMode);
    if (newMode === "adaptive") {
      const recConcept = (liveRecommendation?.name || selectedConcept) as ConceptName;
      const recDiff = (liveRecommendation?.difficulty || selectedDifficulty) as DifficultyLevel;
      setSelectedConcept(recConcept);
      setSelectedDifficulty(recDiff);
      resetBundleState(recConcept, recDiff);
      router.replace(
        `${pathname}?concept=${encodeURIComponent(recConcept)}&difficulty=${recDiff}&mode=adaptive`,
        { scroll: false }
      );
    } else {
      router.replace(
        `${pathname}?concept=${encodeURIComponent(selectedConcept)}&difficulty=${selectedDifficulty}&mode=student`,
        { scroll: false }
      );
    }
  };

  // Switch Concept (Student Mode)
  const handleConceptChange = (concept: ConceptName) => {
    setSelectedConcept(concept);
    resetBundleState(concept, selectedDifficulty);
    router.replace(
      `${pathname}?concept=${encodeURIComponent(concept)}&difficulty=${selectedDifficulty}&mode=student`,
      { scroll: false }
    );
  };

  // Switch Difficulty
  const handleDifficultyChange = (difficulty: DifficultyLevel) => {
    setSelectedDifficulty(difficulty);
    resetBundleState(selectedConcept, difficulty);
    router.replace(
      `${pathname}?concept=${encodeURIComponent(selectedConcept)}&difficulty=${difficulty}&mode=${learningMode}`,
      { scroll: false }
    );
  };

  // Syntax/structure preview runner (never claims live Docker execution)
  const handleRunMockCodeTests = () => {
    if (!currentCodingQuestion) return;
    const hasCode = isCodeModified(answers.q5);

    const results: MockTestCaseResult[] = currentCodingQuestion.testCases.map((tc, idx) => ({
      testIndex: idx + 1,
      call: tc.call,
      passed: hasCode,
      description: hasCode
        ? "Structure & syntax check passed (not executed in Docker)"
        : "Incomplete code: Starter template unchanged or empty",
      statusLabel: hasCode ? "SYNTAX PREVIEW" : "INCOMPLETE",
    }));

    setCodeResultMode("syntax_preview");
    setDockerPreviewScore(null);
    setDockerPreviewRuntimeError(null);
    setMockCodeResults(results);
  };

  // Stateless pre-submission Docker test runner (zero score persistence)
  const handleRunDockerCodeTests = async () => {
    if (!currentCodingQuestion) return;
    setIsRunningDockerTests(true);
    try {
      const res = await fetch("/api/practice/evaluate-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          concept: selectedConcept,
          difficulty: selectedDifficulty,
          code_string: answers.q5,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (
          data?.codeExecutionStatus === "EXECUTED" &&
          data?.codeStatus === "EVALUATED"
        ) {
          setSandboxStatus("available");
          setCodeResultMode("docker_executed");
          setDockerPreviewScore(
            typeof data.codeScore === "number" ? data.codeScore : 0.0
          );
          setDockerPreviewRuntimeError(data.codeRuntimeError || null);
          const mapped: MockTestCaseResult[] = Array.isArray(data.codeTestResults) && data.codeTestResults.length > 0
            ? data.codeTestResults.map((tc: any, idx: number) => ({
              testIndex: typeof tc.testIndex === "number" ? tc.testIndex : idx + 1,
              call: String(tc.call ?? ""),
              passed: Boolean(tc.passed),
              description: tc.passed
                ? String(tc.description || "Isolated Docker test case passed.")
                : String(tc.error || tc.description || "Test case assertion failed."),
              statusLabel: tc.passed ? "PASSED" : "FAILED",
            }))
            : currentCodingQuestion.testCases.map((tc, idx) => ({
              testIndex: idx + 1,
              call: tc.call,
              passed: false,
              description: data.codeRuntimeError || "Execution returned no passing tests.",
              statusLabel: "FAILED",
            }));
          setMockCodeResults(mapped);
          return;
        }
      }

      // Fail closed if sandbox became offline/unavailable
      setSandboxStatus("offline");
      setCodeResultMode("pending_offline");
      setDockerPreviewScore(null);
      setDockerPreviewRuntimeError(null);
    } catch {
      setSandboxStatus("offline");
      setCodeResultMode("pending_offline");
      setDockerPreviewScore(null);
      setDockerPreviewRuntimeError(null);
    } finally {
      setIsRunningDockerTests(false);
    }
  };

  // Bundle submission to Next.js BFF server evaluation endpoint
  const handleSubmitBundle = async () => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch("/api/practice/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          concept: selectedConcept,
          difficulty: selectedDifficulty,
          answers,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setEvaluationResult(data.evaluation);
        if (
          data.evaluation?.codeExecutionStatus === "EXECUTED" &&
          data.evaluation?.codeStatus === "EVALUATED"
        ) {
          setSandboxStatus("available");
          setCodeResultMode("docker_executed");
          setDockerPreviewScore(
            typeof data.evaluation.codeScore === "number" ? data.evaluation.codeScore : 0.0
          );
          setDockerPreviewRuntimeError(data.evaluation.codeRuntimeError || null);
          const liveResults: MockTestCaseResult[] =
            Array.isArray(data.evaluation?.codeTestResults) &&
              data.evaluation.codeTestResults.length > 0
              ? data.evaluation.codeTestResults.map((tc: any, idx: number) => ({
                testIndex: typeof tc.testIndex === "number" ? tc.testIndex : idx + 1,
                call: String(tc.call ?? ""),
                passed: Boolean(tc.passed),
                description: tc.passed
                  ? String(tc.description || "Isolated Docker test case passed.")
                  : String(tc.error || tc.description || "Test case assertion failed."),
                statusLabel: tc.passed ? "PASSED" : "FAILED",
              }))
              : currentCodingQuestion
                ? currentCodingQuestion.testCases.map((tc, idx) => ({
                  testIndex: idx + 1,
                  call: tc.call,
                  passed: false,
                  description: data.evaluation?.codeRuntimeError || "Execution completed with 0 passing tests.",
                  statusLabel: "FAILED",
                }))
                : [];
          if (liveResults.length > 0) {
            setMockCodeResults(liveResults);
          }
        } else {
          setSandboxStatus("offline");
          setCodeResultMode("pending_offline");
          setDockerPreviewScore(null);
          setDockerPreviewRuntimeError(null);
          if (currentCodingQuestion) {
            const hasCode = isCodeModified(answers.q5);
            setMockCodeResults(
              currentCodingQuestion.testCases.map((tc, idx) => ({
                testIndex: idx + 1,
                call: tc.call,
                passed: false,
                description: hasCode
                  ? "Secure Docker sandbox unavailable; execution deferred as Pending Secure Evaluation."
                  : "Incomplete code and Docker sandbox unavailable.",
                statusLabel: "PENDING EVALUATION",
              }))
            );
          }
        }
        setBackendRecorded(Boolean(data.backend_recorded));
        setPersistenceNotice(data.persistence_notice || null);
        setIsBundleSubmitted(true);

        // Phase 11C: Refresh live adaptive recommendation after successful evaluation & persistence
        if (user?.id) {
          await loadRecommendation(user.id);
        } else {
          await loadRecommendation();
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setSubmitError(errData.error || "Failed to evaluate bundle server-side.");
      }
    } catch {
      setSubmitError("Network connectivity error. Server evaluation currently unavailable.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Compatibility alias for assessment submission handler
  const handleSubmitAssessment = handleSubmitBundle;

  // Manual reset
  const handleResetPractice = () => {
    resetBundleState(selectedConcept, selectedDifficulty);
  };

  // Scoring derivations
  const mcqPassedCount = evaluationResult
    ? evaluationResult.mcqPassedCount
    : 0;
  const mcqAttemptedCount = [answers.q1, answers.q2, answers.q3].filter(Boolean).length;

  const saWordCount = answers.q4.trim().split(/\s+/).filter(Boolean).length;
  const hasSaResponse = saWordCount >= 3;

  const codeTestsTotal = currentCodingQuestion?.testCases.length || evaluationResult?.codeTotalTests || 3;
  const rawPreviewCount = mockCodeResults
    ? mockCodeResults.filter((r) => r.passed).length
    : evaluationResult?.syntaxPreviewCount !== undefined
      ? evaluationResult.syntaxPreviewCount
      : isCodeModified(answers.q5)
        ? codeTestsTotal
        : 0;
  const syntaxPreviewPassedCount = Math.min(rawPreviewCount, codeTestsTotal);
  const codeTestsPassed = evaluationResult
    ? evaluationResult.codeTestsPassed
    : 0;

  const currentQuestion = currentBundle.questions[currentStep];
  const totalQuestions = currentBundle.questions.length;

  const handleNext = () => {
    if (currentStep < totalQuestions - 1) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  // Find KC metadata for badge displays
  const currentKCMeta = CANONICAL_KNOWLEDGE_COMPETENCIES.find(
    (k) => k.name.toLowerCase() === selectedConcept.toLowerCase()
  );

  return (
    <div className="space-y-6">
      {/* Top Header & Mode Toggle */}
      <div className="flex flex-col gap-4 pb-2">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-teal-200/90 bg-teal-50 px-3 py-0.5 text-xs font-semibold text-teal-800 mb-2">
              <Terminal className="h-3 w-3" />
              Academic Practice Arena · Interactive Assessment
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 flex items-center gap-3 flex-wrap">
              <span>Adaptive Practice Arena</span>
              <Badge
                variant={
                  selectedDifficulty === "easy"
                    ? "success"
                    : selectedDifficulty === "medium"
                      ? "warning"
                      : "danger"
                }
                size="md"
                className="uppercase font-mono"
              >
                {selectedDifficulty}
              </Badge>
              {isBundleLoading ? (
                <Badge variant="default" size="sm" className="font-mono text-[10px] text-teal-700 border border-teal-200 bg-teal-50">
                  <RefreshCw className="h-3 w-3 animate-spin mr-1 inline" />
                  Loading...
                </Badge>
              ) : isLiveBundle ? (
                <Badge variant="success" size="sm" className="font-mono text-[10px]">
                  <Check className="h-3 w-3 mr-1 inline" />
                  Ready
                </Badge>
              ) : (
                <Badge variant="default" size="sm" className="font-mono text-[10px] text-amber-700 border border-amber-200 bg-amber-50">
                  Standard Bundle
                </Badge>
              )}
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-600">
              Active Concept: <b className="text-teal-700 font-semibold">{selectedConcept}</b> | 5 activities per difficulty tier.
            </p>
          </div>

          {/* Mode Switcher Buttons */}
          <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 shrink-0 self-start sm:self-auto shadow-xs">
            <button
              type="button"
              onClick={() => handleModeSwitch("adaptive")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${learningMode === "adaptive"
                ? "bg-teal-700 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
                }`}
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Adaptive AI Mode</span>
            </button>
            <button
              type="button"
              onClick={() => handleModeSwitch("student")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${learningMode === "student"
                ? "bg-teal-700 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900"
                }`}
            >
              <Compass className="h-3.5 w-3.5" />
              <span>Student Choice</span>
            </button>
          </div>
        </div>

        {/* Mode Specific Controls & Explanations */}
        {learningMode === "adaptive" ? (
          <div className="p-3.5 rounded-xl border border-teal-200/90 bg-teal-50/60 text-xs text-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-xs">
            <div className="flex items-start md:items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-teal-100 border border-teal-200/90 flex items-center justify-center shrink-0 text-teal-800">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-900">Recommended Topic:</span>
                  {isRecommendLoading ? (
                    <Badge variant="default" size="sm" className="font-mono text-[10px]">
                      Loading...
                    </Badge>
                  ) : liveRecommendation ? (
                    <Badge variant="warning" size="sm" className="font-mono text-[10px]">
                      Recommended
                    </Badge>
                  ) : (
                    <Badge variant="danger" size="sm" className="font-mono text-[10px]">
                      Offline
                    </Badge>
                  )}
                </div>
                <p className="text-slate-600 text-[11px] mt-0.5">
                  {isRecommendLoading ? (
                    "Finding your recommended topic..."
                  ) : liveRecommendation ? (
                    <>
                      Recommended practice for <b>{liveRecommendation.name}</b> (<b>{liveRecommendation.difficulty}</b>) based on your progress.
                    </>
                  ) : (
                    <span className="text-amber-700 font-medium">{recommendError || "Recommendation service is unavailable. Choose a concept manually above."}</span>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] text-slate-600 font-mono">Scaffolded Difficulty:</span>
              <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-xs">
                {(["easy", "medium", "hard"] as DifficultyLevel[]).map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => handleDifficultyChange(d)}
                    className={`px-2 py-0.5 rounded text-[11px] font-mono uppercase transition-all ${selectedDifficulty === d
                      ? "bg-teal-700 text-white font-bold"
                      : "text-slate-600 hover:text-slate-900"
                      }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="p-3.5 rounded-xl border border-slate-200/90 bg-white text-xs text-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex items-center gap-1.5 text-slate-600 font-medium">
                <SlidersHorizontal className="h-3.5 w-3.5 text-teal-700" />
                <span>Select Concept:</span>
              </div>
              <select
                value={selectedConcept}
                onChange={(e) => handleConceptChange(e.target.value as ConceptName)}
                className="bg-white border border-slate-300 text-slate-900 rounded-lg px-3 py-1.5 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-teal-600 focus:border-teal-600 shadow-xs"
              >
                {ALL_CONCEPTS.map((concept) => {
                  const meta = CANONICAL_KNOWLEDGE_COMPETENCIES.find((k) => k.name === concept);
                  return (
                    <option key={concept} value={concept}>
                      {concept} {meta ? `(${meta.mastery.toFixed(0)}% mastery)` : ""}
                    </option>
                  );
                })}
              </select>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-slate-600 font-medium">Difficulty Tier:</span>
              <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5">
                {(["easy", "medium", "hard"] as DifficultyLevel[]).map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => handleDifficultyChange(d)}
                    className={`px-2.5 py-1 rounded text-xs font-mono uppercase transition-all ${selectedDifficulty === d
                      ? "bg-teal-700 text-white font-bold"
                      : "text-slate-600 hover:text-slate-900"
                      }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Progress Stepper Bar */}
      <Card className="border-slate-200/90 bg-white shadow-xs">
        <div className="p-3.5 sm:p-4">
          <div className="flex items-center justify-between gap-2 overflow-x-auto pb-1">
            {currentBundle.questions.map((q, idx) => {
              const isCurrent = currentStep === idx;
              let isAnswered = false;
              if (q.type === "mcq") {
                isAnswered = answers[`q${idx + 1}` as "q1" | "q2" | "q3"] !== null;
              } else if (q.type === "short_answer") {
                isAnswered = answers.q4.trim().length > 10;
              } else if (q.type === "coding") {
                isAnswered = isCodeModified(answers.q5);
              }

              return (
                <button
                  key={q.id}
                  type="button"
                  onClick={() => setCurrentStep(idx)}
                  className="flex items-center gap-2 group outline-none select-none"
                >
                  <div
                    className={`flex h-8 w-8 items-center justify-center rounded-xl font-mono text-xs font-bold transition-all ${isCurrent
                      ? "bg-teal-700 text-white ring-2 ring-teal-500 ring-offset-2 ring-offset-white shadow-xs"
                      : isAnswered
                        ? "bg-emerald-50 text-emerald-800 border border-emerald-300 font-bold"
                        : "bg-slate-100 text-slate-500 border border-slate-200 hover:border-slate-300 hover:text-slate-800"
                      }`}
                  >
                    {idx + 1}
                  </div>
                  <div className="hidden md:flex flex-col text-left">
                    <span className="text-[11px] font-semibold text-slate-900">
                      {q.type === "mcq" ? `MCQ ${idx + 1}` : q.type === "short_answer" ? "Short Answer" : "Code Sandbox"}
                    </span>
                    <span className="text-[9px] font-mono text-slate-500">
                      {isAnswered ? "Answered" : "Pending"}
                    </span>
                  </div>
                  {idx < totalQuestions - 1 && (
                    <div className="hidden sm:block w-6 lg:w-12 h-0.5 bg-slate-200 mx-2" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Main Question Viewport */}
      <div>
        {currentQuestion.type === "mcq" && (
          <MCQCard
            questionId={currentQuestion.id}
            questionNumber={currentQuestion.number}
            question={currentQuestion.title}
            options={currentQuestion.options}
            hints={(currentQuestion as any).hints}
            selectedOption={answers[`q${currentStep + 1}` as "q1" | "q2" | "q3"]}
            onSelectOption={(opt) =>
              setAnswers((prev) => ({
                ...prev,
                [`q${currentStep + 1}`]: opt,
              }))
            }
            difficulty={selectedDifficulty}
            concept={selectedConcept}
            isSubmitted={isBundleSubmitted}
            feedback={
              isBundleSubmitted && evaluationResult
                ? {
                  isCorrect: evaluationResult.mcqResults[currentStep]?.isCorrect ?? false,
                  correctOption: evaluationResult.mcqResults[currentStep]?.correctOption,
                  explanation: `Demonstration evaluation: Question assesses conceptual understanding of ${selectedConcept} (${selectedDifficulty}).`,
                  score: evaluationResult.mcqResults[currentStep]?.isCorrect ? 1.0 : 0.0,
                }
                : null
            }
          />
        )}

        {currentQuestion.type === "short_answer" && (
          <ShortAnswerBox
            questionId={currentQuestion.id}
            questionNumber={currentQuestion.number}
            question={currentQuestion.title}
            value={answers.q4}
            hints={(currentQuestion as any).hints}
            onChange={(val) => setAnswers((prev) => ({ ...prev, q4: val }))}
            difficulty={selectedDifficulty}
            concept={selectedConcept}
            maxWords={currentQuestion.maxWords}
            isSubmitted={isBundleSubmitted}
            feedback={
              isBundleSubmitted && evaluationResult
                ? {
                  similarityScore:
                    evaluationResult.shortAnswerStatus === "EVALUATED" && typeof evaluationResult.shortAnswerScore === "number"
                      ? evaluationResult.shortAnswerScore
                      : 0,
                  isAcceptable:
                    evaluationResult.shortAnswerStatus === "EVALUATED" &&
                    (evaluationResult.shortAnswerScore ?? 0) >= 30,
                  missingKeywords: [],
                  feedbackText:
                    evaluationResult.shortAnswerStatus === "EVALUATED"
                      ? (evaluationResult.shortAnswerFeedback || "Short answer semantic evaluation complete.")
                      : (evaluationResult.shortAnswerFeedback || "Short-answer semantic evaluation is currently unavailable (no score assigned)."),
                }
                : null
            }
          />
        )}

        {currentQuestion.type === "coding" && (
          <MonacoCodeWorkspace
            questionId={currentQuestion.id}
            questionNumber={currentQuestion.number}
            problem={currentQuestion.title}
            code={answers.q5}
            hints={(currentQuestion as any).hints}
            onChange={(val) => {
              setAnswers((prev) => ({ ...prev, q5: val }));
              if (!isBundleSubmitted && codeResultMode !== "none") {
                setCodeResultMode("none");
                setMockCodeResults(null);
                setDockerPreviewScore(null);
                setDockerPreviewRuntimeError(null);
              }
            }}
            onResetCode={() => {
              setAnswers((prev) => ({
                ...prev,
                q5: defaultStarterCode,
              }));
              if (!isBundleSubmitted) {
                setCodeResultMode("none");
                setMockCodeResults(null);
                setDockerPreviewScore(null);
                setDockerPreviewRuntimeError(null);
              }
            }}
            difficulty={selectedDifficulty}
            concept={selectedConcept}
            testCases={currentQuestion.testCases}
            mockResults={mockCodeResults}
            onRunMockTests={handleRunMockCodeTests}
            onRunDockerTests={handleRunDockerCodeTests}
            isRunningDockerTests={isRunningDockerTests}
            sandboxStatus={sandboxStatus}
            resultMode={codeResultMode}
            dockerCodeScore={
              evaluationResult?.codeExecutionStatus === "EXECUTED"
                ? evaluationResult.codeScore ?? dockerPreviewScore
                : dockerPreviewScore
            }
            dockerRuntimeError={
              evaluationResult?.codeExecutionStatus === "EXECUTED"
                ? evaluationResult.codeRuntimeError ?? dockerPreviewRuntimeError
                : dockerPreviewRuntimeError
            }
            isSubmitted={isBundleSubmitted}
            isLiveEvaluated={evaluationResult?.codeExecutionStatus === "EXECUTED"}
          />
        )}
      </div>

      {/* Stepper Navigation Controls */}
      <div className="flex items-center justify-between pt-2 gap-2">
        <Button
          variant="outline"
          size="md"
          onClick={handlePrev}
          disabled={currentStep === 0}
          className="gap-2 shrink-0 border-slate-300 text-slate-700 hover:bg-slate-50 hover:text-slate-900"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Previous</span>
        </Button>

        <div className="flex items-center gap-2">
          {currentStep < totalQuestions - 1 ? (
            <Button variant="primary" size="md" onClick={handleNext} className="gap-2 bg-teal-700 hover:bg-teal-800 text-white shadow-xs">
              <span>Next Activity</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          ) : (
            !isBundleSubmitted && (
              <Button
                variant="primary"
                size="md"
                onClick={handleSubmitBundle}
                disabled={isSubmitting}
                className="gap-2 bg-teal-700 hover:bg-teal-800 text-white shadow-xs disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Evaluating Bundle...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    <span className="hidden sm:inline">Submit 5-Question Bundle</span>
                    <span className="sm:hidden">Submit Bundle</span>
                  </>
                )}
              </Button>
            )
          )}
        </div>
      </div>

      {submitError && (
        <div className="p-3.5 rounded-xl border border-rose-200 bg-rose-50 text-xs text-rose-900 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{submitError}</span>
        </div>
      )}

      {/* Post-Submission Completion Summary Card */}
      {isBundleSubmitted && evaluationResult && (
        <Card
          className={
            evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT"
              ? "border-amber-300 bg-white shadow-md border-t-4 border-t-amber-500"
              : evaluationResult.assessmentLabel === "ASSESSMENT UNAVAILABLE"
                ? "border-rose-300 bg-white shadow-md border-t-4 border-t-rose-500"
                : "border-slate-200/90 bg-white shadow-md border-t-4 border-t-teal-600"
          }
        >
          <CardHeader className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
              <div className="flex items-center gap-2 min-w-0">
                {evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT" ? (
                  <AlertCircle className="h-5 w-5 text-amber-600 shrink-0" />
                ) : evaluationResult.assessmentLabel === "ASSESSMENT UNAVAILABLE" ? (
                  <AlertCircle className="h-5 w-5 text-rose-600 shrink-0" />
                ) : (
                  <Award className="h-5 w-5 text-teal-700 shrink-0" />
                )}
                <CardTitle
                  className={
                    evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT"
                      ? "text-base sm:text-lg text-amber-900 leading-snug font-bold"
                      : evaluationResult.assessmentLabel === "ASSESSMENT UNAVAILABLE"
                        ? "text-base sm:text-lg text-rose-900 leading-snug font-bold"
                        : "text-base sm:text-lg text-slate-900 leading-snug font-bold"
                  }
                >
                  {evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT"
                    ? `Partial Assessment Summary (${selectedConcept} — ${selectedDifficulty.toUpperCase()})`
                    : evaluationResult.assessmentLabel === "ASSESSMENT UNAVAILABLE"
                      ? `Assessment Unavailable (${selectedConcept} — ${selectedDifficulty.toUpperCase()})`
                      : `Assessment Bundle Summary (${selectedConcept} — ${selectedDifficulty.toUpperCase()})`}
                </CardTitle>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge
                  variant={
                    evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT"
                      ? "warning"
                      : evaluationResult.assessmentLabel === "ASSESSMENT UNAVAILABLE"
                        ? "danger"
                        : "success"
                  }
                  size="sm"
                  className="font-mono text-[10px] shrink-0"
                >
                  {evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT"
                    ? "Partial Assessment"
                    : evaluationResult.assessmentLabel === "ASSESSMENT UNAVAILABLE"
                    ? "Assessment Unavailable"
                    : "Complete Bundle"}
                </Badge>
                {backendRecorded !== null && (
                  <Badge
                    variant={backendRecorded ? "success" : "warning"}
                    size="sm"
                    className="font-mono text-[10px] shrink-0"
                  >
                    {backendRecorded ? "Saved" : "Saving Deferred"}
                  </Badge>
                )}
              </div>
            </div>
            <CardDescription className="text-slate-600 text-xs sm:text-sm">
              {evaluationResult.isPartialAssessment && evaluationResult.scaffoldingReason
                ? evaluationResult.scaffoldingReason
                : "Your practice session has been evaluated. Review your detailed score breakdown below."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {persistenceNotice && (
              <div className="p-3 rounded-lg bg-amber-50 border border-amber-300 text-xs text-amber-900 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <span className="font-semibold block font-mono text-[11px] text-amber-900 uppercase tracking-wider">
                    Score Persistence Deferred
                  </span>
                  <span className="leading-relaxed text-amber-800">{persistenceNotice}</span>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs font-mono">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase">
                  {evaluationResult.isPartialAssessment ? "Partial Score" : "Overall Score"}
                </span>
                <span
                  className={
                    typeof evaluationResult.bundleAveragePercent === "number"
                      ? "text-teal-700 font-bold text-base"
                      : "text-slate-500 font-bold text-base"
                  }
                >
                  {typeof evaluationResult.bundleAveragePercent === "number"
                    ? `${evaluationResult.bundleAveragePercent.toFixed(1)}%`
                    : "Unavailable"}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {evaluationResult.assessmentLabel === "COMPLETE BUNDLE"
                    ? "Average across activities"
                    : evaluationResult.assessmentLabel === "PARTIAL ASSESSMENT"
                    ? "MCQ performance only"
                    : "No valid score available"}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase">MCQ Correctness</span>
                <span className="text-slate-900 font-bold text-base">
                  {mcqPassedCount} / 3 Correct
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {mcqAttemptedCount} of 3 attempted
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <span className="text-slate-500 block text-[10px] uppercase">Short Answer</span>
                <span
                  className={
                    evaluationResult.shortAnswerStatus === "EVALUATED" && typeof evaluationResult.shortAnswerScore === "number"
                      ? "text-blue-700 font-bold text-base"
                      : "text-amber-700 font-bold text-base"
                  }
                >
                  {evaluationResult.shortAnswerStatus === "EVALUATED" && typeof evaluationResult.shortAnswerScore === "number"
                    ? `${evaluationResult.shortAnswerScore.toFixed(1)}%`
                    : "Unavailable"}
                </span>
                <span className="text-[10px] text-slate-500 block mt-0.5">
                  {evaluationResult.shortAnswerStatus === "EVALUATED"
                    ? (evaluationResult.shortAnswerScore !== null ? "Evaluated" : "Omitted")
                    : "Evaluation unavailable"}
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <span className="text-slate-500 block text-[10px] uppercase">Coding Challenge</span>
                {evaluationResult.codeExecutionStatus === "EXECUTED" &&
                  evaluationResult.codeStatus === "EVALUATED" ? (
                  <div className="space-y-0.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-600">Python Execution:</span>
                      <span className="text-emerald-700 font-medium">Executed</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-600">Automated Tests:</span>
                      <span
                        className={
                          codeTestsPassed > 0
                            ? "text-emerald-700 font-bold"
                            : "text-amber-700 font-bold"
                        }
                      >
                        {codeTestsPassed} / {evaluationResult.codeTotalTests ?? codeTestsTotal} Passed
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] pt-0.5 border-t border-slate-200">
                      <span className="text-slate-600">Coding Score:</span>
                      <span
                        className={
                          (evaluationResult.codeScore ?? 0) > 0
                            ? "text-emerald-700 font-bold"
                            : "text-amber-700 font-bold"
                        }
                      >
                        {(evaluationResult.codeScore ?? 0).toFixed(1)}%
                      </span>
                    </div>
                    {evaluationResult.codeRuntimeError && (
                      <div
                        className="text-[10px] text-rose-700 pt-1 break-words"
                        title={evaluationResult.codeRuntimeError}
                      >
                        {evaluationResult.codeRuntimeError}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-0.5">
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-600">Syntax Preview:</span>
                      <span className={syntaxPreviewPassedCount > 0 ? "text-emerald-700 font-bold" : "text-amber-700 font-bold"}>
                        {syntaxPreviewPassedCount}/{codeTestsTotal} Structure Preview
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-slate-600">Python Execution:</span>
                      <span className="text-slate-600 font-medium">Not performed</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] pt-0.5 border-t border-slate-200">
                      <span className="text-slate-600">Coding Score:</span>
                      <span className="text-amber-700 font-bold text-[10px]">Pending Secure Evaluation</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="p-3 rounded-lg bg-teal-50/70 border border-teal-200 text-xs text-slate-800 flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-teal-700 shrink-0" />
              <span>
                <b className="text-teal-900">Next Recommended Topic:</b>{" "}
                {liveRecommendation ? (
                  <>
                    Practice{" "}
                    <b className="text-teal-800">{liveRecommendation.name} ({liveRecommendation.difficulty})</b>{" "}
                    to continue building your mastery.
                  </>
                ) : (
                  "Complete additional practice sessions to generate personalized recommendations."
                )}
              </span>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleResetPractice}
                className="w-full sm:w-auto gap-1.5 text-xs justify-center border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Reset This Bundle</span>
              </Button>

              <div className="flex flex-col sm:flex-row items-center gap-2 w-full sm:w-auto">
                <Link href="/adaptive-learning" className="w-full sm:w-auto">
                  <Button variant="secondary" size="sm" className="w-full sm:w-auto gap-1.5 text-xs justify-center border-slate-200">
                    <span>View Learning Plan</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
                <Link href="/analytics" className="w-full sm:w-auto">
                  <Button variant="primary" size="sm" className="w-full sm:w-auto gap-1.5 text-xs justify-center bg-teal-700 hover:bg-teal-800 text-white">
                    <span>View Skill Radar</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function PracticeArenaPage() {
  return (
    <React.Suspense
      fallback={
        <div className="p-8 text-center text-slate-400 text-sm">
          Loading Practice Arena question bundle...
        </div>
      }
    >
      <PracticeArenaInner />
    </React.Suspense>
  );
}
