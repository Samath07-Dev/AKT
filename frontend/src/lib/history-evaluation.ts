import {
  PUBLIC_BUNDLE_CATALOG,
  type PublicCodingQuestion,
} from "./mock-data/bundle-catalog";
import type { DetailedSessionRecord } from "./mock-data/curriculum-store";

export interface CodingStatusDisplay {
  isPending: boolean;
  isEvaluated: boolean;
  isMissingMetadata: boolean;
  executionLabel: string;
  automatedTestsLabel: string;
  codeScoreLabel: string;
  summaryCardLabel: string;
  tableCellLabel: string;
  executionNotice: string;
}

/**
 * Normalizes coding status and execution status tokens to uppercase snake_case
 * to ensure robust matching across legacy and normalized payloads:
 * e.g. "PENDING SECURE EVALUATION" -> "PENDING_SECURE_EVALUATION"
 */
export function normalizeCodingStatus(val?: string | null): string {
  if (!val || typeof val !== "string") return "";
  return val.toUpperCase().trim().replace(/[\s-]+/g, "_");
}

/**
 * Resolves the actual number of coding unit test specifications defined
 * for a given concept and difficulty from the curriculum catalog.
 */
export function resolveCodeTestsTotal(
  concept?: string,
  difficulty?: string,
  storedTotal?: number | null
): number | null {
  if (typeof storedTotal === "number" && !isNaN(storedTotal) && storedTotal > 0) {
    return storedTotal;
  }
  if (concept) {
    try {
      const normalizedConcept = Object.keys(PUBLIC_BUNDLE_CATALOG).find(
        (k) => k.toLowerCase() === concept.trim().toLowerCase()
      );
      if (normalizedConcept) {
        const conceptBundles = PUBLIC_BUNDLE_CATALOG[normalizedConcept];
        const diffKey = ((difficulty || "medium").toLowerCase() as "easy" | "medium" | "hard");
        const bundle = conceptBundles[diffKey] || conceptBundles["medium"] || conceptBundles["easy"];
        const codingQ = bundle?.questions.find((q) => q.type === "coding") as PublicCodingQuestion | undefined;
        if (codingQ && Array.isArray(codingQ.testCases) && codingQ.testCases.length > 0) {
          return codingQ.testCases.length;
        }
      }
    } catch {
      // Ignore lookup failure
    }
  }
  return null;
}

/**
 * Derives a truthful execution disclaimer solely from the authoritative
 * persisted execution status field (`codeExecutionStatus`), with limited
 * non-executed fallback to `codeStatus` only when `codeExecutionStatus` is missing.
 * Never infers execution from `codeScore` or `codeTestsPassed`, and fails safely
 * on unknown or missing statuses without claiming execution occurred.
 */
export function getCodingExecutionNotice(record: {
  codeStatus?: string | null;
  codeExecutionStatus?: string | null;
}): string {
  const execStatus = normalizeCodingStatus(record.codeExecutionStatus);

  if (execStatus === "EXECUTED") {
    return "Python code was executed inside an isolated, network-disabled Docker container. Host execution remains disabled.";
  }
  if (execStatus === "NOT_PERFORMED" || execStatus === "SANDBOX_OFFLINE") {
    return "Python execution was not performed because secure sandbox evaluation was unavailable.";
  }
  if (execStatus === "PENDING_SECURE_EVALUATION") {
    return "Python execution is pending secure evaluation.";
  }

  if (!execStatus) {
    const codeStatus = normalizeCodingStatus(record.codeStatus);
    if (codeStatus === "PENDING_SECURE_EVALUATION") {
      return "Python execution is pending secure evaluation.";
    }
    if (codeStatus === "NOT_PERFORMED" || codeStatus === "SANDBOX_OFFLINE") {
      return "Python execution was not performed because secure sandbox evaluation was unavailable.";
    }
  }

  return "Python execution status is unavailable or unverified. Host execution remains disabled.";
}

/**
 * Formats coding evaluation state according to safety and audit rules:
 * - Explicit SANDBOX_OFFLINE, NOT_PERFORMED, NOT_EVALUATED, or PENDING_SECURE_EVALUATION:
 *   Execution: Not performed | Automated Tests: Pending secure evaluation | Coding Score: Pending secure evaluation
 * - Explicit EVALUATED / EXECUTED: preserves genuine zero scores as 0.0% and shows passed / total.
 * - Historical records with missing metadata: displays "Not evaluated" across all cards
 *   rather than fabricating 0.0% or 0/3.
 */
export function getCodingEvaluationDisplay(record: {
  concept?: string;
  difficulty?: string;
  codeScore?: number | null;
  codeStatus?: string | null;
  codeExecutionStatus?: string | null;
  codeTestsPassed?: number | null;
  codeTestsTotal?: number | null;
}): CodingStatusDisplay {
  const status = normalizeCodingStatus(record.codeStatus);
  const execStatus = normalizeCodingStatus(record.codeExecutionStatus);
  const resolvedTotal = resolveCodeTestsTotal(record.concept, record.difficulty, record.codeTestsTotal);
  const executionNotice = getCodingExecutionNotice(record);

  // 1. Explicit pending / sandbox-offline execution status
  const isPending =
    status === "PENDING_SECURE_EVALUATION" ||
    status === "SANDBOX_OFFLINE" ||
    status === "NOT_PERFORMED" ||
    status === "NOT_EVALUATED" ||
    execStatus === "NOT_PERFORMED" ||
    execStatus === "SANDBOX_OFFLINE" ||
    execStatus === "NOT_EVALUATED" ||
    execStatus === "PENDING_SECURE_EVALUATION";

  if (isPending) {
    return {
      isPending: true,
      isEvaluated: false,
      isMissingMetadata: false,
      executionLabel: "Not performed",
      automatedTestsLabel: "Pending secure evaluation",
      codeScoreLabel: "Pending secure evaluation",
      summaryCardLabel: "Pending secure evaluation",
      tableCellLabel: "Pending evaluation",
      executionNotice,
    };
  }

  // 2. Explicit evaluated status (genuine execution)
  const isEvaluated =
    status === "EVALUATED" ||
    execStatus === "EXECUTED" ||
    (typeof record.codeTestsPassed === "number" && record.codeTestsPassed > 0);

  if (isEvaluated) {
    const passed = typeof record.codeTestsPassed === "number" ? record.codeTestsPassed : 0;
    const total = resolvedTotal ?? 3;
    const scoreVal = typeof record.codeScore === "number" ? `${record.codeScore.toFixed(1)}%` : "0.0%";
    return {
      isPending: false,
      isEvaluated: true,
      isMissingMetadata: false,
      executionLabel: "Executed",
      automatedTestsLabel: `${passed} / ${total}`,
      codeScoreLabel: scoreVal,
      summaryCardLabel: scoreVal,
      tableCellLabel: `${passed} / ${total}`,
      executionNotice,
    };
  }

  // 3. Historical records with missing evaluation-status metadata
  const recordedScoreLabel =
    typeof record.codeScore === "number" && !isNaN(record.codeScore)
      ? `${record.codeScore.toFixed(1)}%`
      : "Not evaluated";

  return {
    isPending: false,
    isEvaluated: false,
    isMissingMetadata: true,
    executionLabel: "Not evaluated",
    automatedTestsLabel: "Not evaluated",
    codeScoreLabel: recordedScoreLabel,
    summaryCardLabel: "Not evaluated",
    tableCellLabel: "Not evaluated",
    executionNotice,
  };
}

/**
 * Maps a raw FastAPI `/student/{id}/history` score record into the frontend
 * DetailedSessionRecord / MockHistoryRecord view model without fabricating
 * missing coding evaluation status metadata.
 */
export function mapHistoryApiRecordToSession(rec: any, idx: number): DetailedSessionRecord {
  const rawTimestamp = typeof rec?.timestamp === "string" ? rec.timestamp : undefined;
  const formattedDate = rawTimestamp
    ? (() => {
        const d = new Date(rawTimestamp);
        return isNaN(d.getTime())
          ? "Recent"
          : d.toLocaleString("en-US", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            });
      })()
    : "Recent";

  const saScore =
    typeof rec?.short_answer_score === "number" && !isNaN(rec.short_answer_score)
      ? Number(rec.short_answer_score.toFixed(1))
      : null;

  const bundleScore =
    typeof rec?.bundle_average_score === "number" && !isNaN(rec.bundle_average_score)
      ? Number(rec.bundle_average_score.toFixed(1))
      : 0;

  const mcqScores = Array.isArray(rec?.mcq_scores)
    ? rec.mcq_scores.map((s: any) => (typeof s === "number" && !isNaN(s) ? s : 0))
    : [];

  const codeScore =
    typeof rec?.code_score === "number" && !isNaN(rec.code_score)
      ? Number(rec.code_score.toFixed(1))
      : 0;

  const codeTestsPassed =
    typeof rec?.code_tests_passed === "number" && !isNaN(rec.code_tests_passed)
      ? rec.code_tests_passed
      : typeof rec?.codeTestsPassed === "number" && !isNaN(rec.codeTestsPassed)
      ? rec.codeTestsPassed
      : 0;

  const conceptName =
    typeof rec?.concept === "string" && rec.concept.trim() ? rec.concept : "Variables";
  const difficultyName = (rec?.difficulty as "easy" | "medium" | "hard") || "medium";
  const rawTotal = rec?.code_tests_total ?? rec?.codeTestsTotal;
  const codeTestsTotal =
    resolveCodeTestsTotal(conceptName, difficultyName, rawTotal) ??
    (typeof rawTotal === "number" ? rawTotal : 2);

  const rawCodeStatus = rec?.code_status ?? rec?.codeStatus;
  const rawCodeExecutionStatus = rec?.code_execution_status ?? rec?.codeExecutionStatus;
  const normalizedCodeStatus = normalizeCodingStatus(rawCodeStatus) || undefined;
  const normalizedCodeExecutionStatus = normalizeCodingStatus(rawCodeExecutionStatus) || undefined;
  const syntaxPreviewPassed = rec?.syntax_preview_passed ?? rec?.syntaxPreviewPassed;

  return {
    id: rec?.submission_id || rec?._id || `live_sess_${idx}`,
    submissionId: rec?.submission_id,
    timestamp: rawTimestamp,
    date: formattedDate,
    concept: conceptName,
    difficulty: difficultyName,
    bundleScore,
    mcqScores,
    shortAnswerScore: saScore,
    codeScore,
    codeStatus: normalizedCodeStatus,
    codeExecutionStatus: normalizedCodeExecutionStatus,
    syntaxPreviewPassed,
    codeTestsPassed,
    codeTestsTotal,
    nextDifficulty: (rec?.next_difficulty as "easy" | "medium" | "hard") || "medium",
    scaffoldingReason:
      typeof rec?.scaffolding_reasoning === "string" && rec.scaffolding_reasoning.trim()
        ? rec.scaffolding_reasoning
        : "Scaffolding interval maintained.",
    details: {
      mcqs: [],
      shortAnswer: {
        question: "",
        studentAnswer: "",
        rubric: "",
        similarity: saScore,
      },
      coding: {
        problem: "",
        passed: codeTestsPassed,
        total: codeTestsTotal,
        syntaxValid: Boolean(syntaxPreviewPassed),
      },
    },
  };
}
