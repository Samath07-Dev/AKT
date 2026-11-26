/**
 * frontend/src/app/api/practice/evaluate/route.ts
 *
 * Next.js BFF Route: Secure Assessment Bundle Evaluation
 * Evaluates student submissions server-side.
 * Enforces Origin check, session check, answer key isolation, and code sandbox safety.
 * Connects to FastAPI Phase 33 Idempotent Score Ledger with stable submission identity.
 */

import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "@/lib/auth/session";
import { verifyRequestOrigin, callFastApiBackend } from "@/lib/api/backend-client";
import { evaluateAssessmentBundleServer, getVerifiedBinaryMcqScores } from "@/lib/server/bundle-evaluator";

/**
 * Derives or generates a server-controlled, deterministic submission ID.
 * - If a client attempt ID is provided, validates that it strictly matches safe token syntax
 *   (/^[a-zA-Z0-9_-]{10,64}$/) and binds it to the authenticated student namespace (sub_<studentId>_<token>).
 * - If omitted, generates a cryptographically random UUIDv4 bound to the student namespace.
 * - Server namespace guarantees a client cannot spoof or overwrite another student's submission.
 */
function resolveServerControlledSubmissionId(
  studentId: string,
  clientAttemptId?: unknown
): string {
  if (
    typeof clientAttemptId === "string" &&
    /^[a-zA-Z0-9_-]{10,64}$/.test(clientAttemptId.trim())
  ) {
    return `sub_${studentId}_${clientAttemptId.trim()}`;
  }
  return `sub_${studentId}_${crypto.randomUUID()}`;
}

export async function POST(request: NextRequest) {
  // 1. Origin verification for state-changing endpoint (Step 3)
  if (!verifyRequestOrigin(request)) {
    return NextResponse.json(
      { error: "Forbidden: Cross-origin request rejected." },
      { status: 403 }
    );
  }

  // 2. Session verification
  const session = await getServerSession();
  if (!session) {
    return NextResponse.json(
      { error: "Unauthorized: Active session required." },
      { status: 401 }
    );
  }

  // 3. Payload validation
  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON request payload." },
      { status: 400 }
    );
  }

  const { concept, difficulty = "medium", answers } = body || {};

  if (!concept || typeof concept !== "string") {
    return NextResponse.json(
      { error: "Missing or invalid concept parameter." },
      { status: 400 }
    );
  }

  const { q1, q2, q3, q4, q5 } = answers || {};

  // 4. Safe server-side evaluation (Isolates answer keys, quarantines untrusted code execution)
  const evalResult = await evaluateAssessmentBundleServer(
    concept,
    difficulty,
    {
      q1: q1 || null,
      q2: q2 || null,
      q3: q3 || null,
      q4: q4 || "",
      q5: q5 || "",
    }
  );

  // 5. Generate or resolve server-controlled stable submission ID
  const rawAttemptId =
    body?.submission_id || body?.client_submission_id || body?.clientSubmissionId;
  const submissionId = resolveServerControlledSubmissionId(
    session.studentId,
    rawAttemptId
  );

  // 6. Record score into backend score ledger (Phase 33 FastAPI contract)
  // Ensures itemized binary MCQ scores only contribute to EMA updates.
  // Safety rule (Phase 6A): Stop before persistence if short-answer evaluation is unavailable,
  // because the backend score ledger requires a numeric float and cannot represent UNAVAILABLE
  // without recording a false zero or failing type conversion on null.
  let backendRes: any = null;
  let persistenceNotice: string | undefined = undefined;

  if (evalResult.shortAnswerStatus === "UNAVAILABLE") {
    persistenceNotice = "Score persistence deferred: short-answer evaluation was unavailable, and the existing backend score ledger requires a numeric score. Score was not recorded to prevent logging a false zero or failing type conversion.";
  } else if (typeof evalResult.shortAnswerScore === "number" && typeof evalResult.bundleAveragePercent === "number") {
    const scorePayload = {
      submission_id: submissionId,
      student_id: session.studentId,
      concept,
      difficulty,
      bundle_average_score: evalResult.bundleAveragePercent,
      mcq_scores: getVerifiedBinaryMcqScores(evalResult.mcqResults),
      short_answer_score: evalResult.shortAnswerScore,
      code_score: evalResult.codeScore,
      code_status: evalResult.codeStatus,
      code_execution_status: evalResult.codeExecutionStatus,
      code_tests_passed: evalResult.codeTestsPassed,
      code_tests_total: evalResult.codeTotalTests,
      syntax_preview_passed: evalResult.syntaxPreviewPassed,
      syntax_preview_count: evalResult.syntaxPreviewCount,
      next_difficulty: evalResult.nextDifficulty,
      scaffolding_reasoning: evalResult.scaffoldingReason,
      timestamp: new Date().toISOString(),
    };

    try {
      backendRes = await callFastApiBackend(
        `/api/v1/student/${session.studentId}/record_score`,
        {
          method: "POST",
          studentId: session.studentId,
          body: JSON.stringify(scorePayload),
        }
      );

      // If transient backend error (status >= 500 or timeout), retry once with the identical submission_id
      if (!backendRes.ok && (backendRes.status >= 500 || backendRes.status === 0)) {
        backendRes = await callFastApiBackend(
          `/api/v1/student/${session.studentId}/record_score`,
          {
            method: "POST",
            studentId: session.studentId,
            body: JSON.stringify(scorePayload),
          }
        );
      }
    } catch {
      // Non-fatal if backend record write fails; evaluation still succeeds safely
    }
  }

  return NextResponse.json({
    status: "success",
    submission_id: submissionId,
    evaluation: evalResult,
    backend_recorded: Boolean(backendRes?.ok),
    ...(persistenceNotice ? { persistence_notice: persistenceNotice } : {}),
  });
}

