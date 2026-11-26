/**
 * frontend/src/app/api/adaptive/recommend/route.ts
 *
 * Next.js BFF Route: Adaptive Learning Recommendation
 * Computes acquisition priority vector (1 - mastery) * (1 + uncertainty)
 * using the Behavior-AKT engine on FastAPI.
 * Injects verified session student_id server-side.
 */

import { NextRequest, NextResponse } from "next/server";
import { getServerSession } from "@/lib/auth/session";
import { callFastApiBackend } from "@/lib/api/backend-client";

export async function GET(request: NextRequest) {
  const session = await getServerSession();

  if (!session) {
    return NextResponse.json(
      { error: "Unauthorized: Active session required." },
      { status: 401 }
    );
  }

  const { searchParams } = new URL(request.url);
  const targetConcept = searchParams.get("concept") || undefined;
  const currentDifficulty = searchParams.get("difficulty") || undefined;

  const result = await callFastApiBackend("/api/v1/recommend", {
    method: "POST",
    studentId: session.studentId,
    body: JSON.stringify({
      student_id: session.studentId,
      target_concept_override: targetConcept,
      current_difficulty: currentDifficulty,
    }),
  });

  if (!result.ok) {
    return NextResponse.json(
      { error: result.error || "Failed to compute adaptive recommendation." },
      { status: result.status }
    );
  }

  const data = result.data || {};
  // Sanitize question details so answer keys are never leaked to client
  if (data.question_details) {
    delete data.question_details.correct_option;
    delete data.question_details.reference_answer;
    if (data.question_details.test_cases && Array.isArray(data.question_details.test_cases)) {
      data.question_details.test_cases = data.question_details.test_cases.map((tc: any) => ({
        call: tc.call,
        description: tc.description,
      }));
    }
  }

  return NextResponse.json(data);
}

