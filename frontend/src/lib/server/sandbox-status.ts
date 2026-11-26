/**
 * frontend/src/lib/server/sandbox-status.ts
 *
 * Server-side probe and stateless code evaluation helpers communicating
 * exclusively with FastAPI `/api/v1/evaluate_code`.
 * Fails closed to `SANDBOX_OFFLINE` whenever the backend cannot confirm
 * live Docker sandbox readiness.
 */

import { callFastApiBackend } from "@/lib/api/backend-client";
import { getPublicBundle, type PublicCodingQuestion } from "@/lib/mock-data/bundle-catalog";
import { evaluateCodeSandboxServer } from "@/lib/server/bundle-evaluator";

export interface SandboxAvailabilityResult {
  available: boolean;
  status: "READY" | "SANDBOX_OFFLINE";
  message: string;
}

/**
 * Probes FastAPI `/api/v1/evaluate_code` with an empty string.
 * FastAPI's SecureDockerPythonEvaluator verifies `SANDBOX_OFFLINE`, Docker CLI,
 * Docker daemon health, and pinned image digest first, then returns immediately
 * on empty input without launching a container or touching MongoDB.
 */
export async function probeDockerSandboxAvailability(): Promise<SandboxAvailabilityResult> {
  try {
    const res = await callFastApiBackend<any>("/api/v1/evaluate_code", {
      method: "POST",
      timeoutMs: 8000,
      body: JSON.stringify({
        concept: "Variables",
        difficulty: "easy",
        code_string: "",
      }),
    });

    if (
      res.ok &&
      res.data &&
      res.data.code_status === "EVALUATED" &&
      res.data.code_execution_status === "EXECUTED"
    ) {
      return {
        available: true,
        status: "READY",
        message: "Isolated Docker Python sandbox verified and ready.",
      };
    }

    return {
      available: false,
      status: "SANDBOX_OFFLINE",
      message: String(
        res.data?.feedback ||
          res.error ||
          "Docker Python sandbox is offline or unavailable."
      ),
    };
  } catch {
    return {
      available: false,
      status: "SANDBOX_OFFLINE",
      message: "Failed to verify Docker sandbox status from FastAPI backend.",
    };
  }
}

/**
 * Runs stateless isolated Docker code evaluation without recording scores
 * or updating BKT knowledge state.
 */
export async function evaluatePracticeCodeStateless(
  concept: string,
  difficulty: "easy" | "medium" | "hard",
  codeString: string
) {
  const publicBundle = getPublicBundle(concept, difficulty);
  const codingQ = publicBundle?.questions.find(
    (q) => q.type === "coding"
  ) as PublicCodingQuestion | undefined;
  const fallbackTotalTests =
    codingQ && Array.isArray(codingQ.testCases) ? codingQ.testCases.length : 3;

  return evaluateCodeSandboxServer(
    concept,
    difficulty,
    codeString,
    fallbackTotalTests
  );
}

