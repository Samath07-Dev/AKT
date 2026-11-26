/**
 * frontend/src/app/api/practice/evaluate-code/route.ts
 *
 * Next.js BFF Route: Stateless Pre-Submission Docker Code Evaluation
 * Executes student Python code inside FastAPI's isolated Docker sandbox
 * without submitting the assessment, recording scores, or mutating BKT state.
 */

import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "@/lib/auth/session";
import { verifyRequestOrigin } from "@/lib/api/backend-client";
import { evaluatePracticeCodeStateless } from "@/lib/server/sandbox-status";

export async function POST(request: NextRequest) {
  if (!verifyRequestOrigin(request)) {
    return NextResponse.json(
      { error: "Forbidden: Cross-origin request rejected." },
      { status: 403 }
    );
  }

  const session = await getServerSession();
  if (!session) {
    return NextResponse.json(
      { error: "Unauthorized: Active session required." },
      { status: 401 }
    );
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON request payload." },
      { status: 400 }
    );
  }

  const concept = typeof body?.concept === "string" ? body.concept.trim() : "";
  if (!concept) {
    return NextResponse.json(
      { error: "Missing or invalid concept parameter." },
      { status: 400 }
    );
  }

  const rawDiff =
    typeof body?.difficulty === "string" ? body.difficulty.toLowerCase().trim() : "medium";
  const difficulty: "easy" | "medium" | "hard" =
    rawDiff === "easy" || rawDiff === "medium" || rawDiff === "hard" ? rawDiff : "medium";

  const codeString = typeof body?.code_string === "string" ? body.code_string : "";

  const result = await evaluatePracticeCodeStateless(concept, difficulty, codeString);
  return NextResponse.json(result, {
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}

