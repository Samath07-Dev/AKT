/**
 * frontend/src/app/api/practice/bundle/[concept]/route.ts
 *
 * Next.js BFF Route: Public Concept Assessment Bundle
 * Fetches question bundle from FastAPI and strictly strips all answer keys,
 * reference rubrics, and expected test case outputs before returning to the browser.
 */

import { NextRequest, NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import { getServerSession } from "@/lib/auth/session";
import { callFastApiBackend } from "@/lib/api/backend-client";

let cachedHints: Record<string, string[]> | null = null;

function getHintsMap(): Record<string, string[]> {
  if (cachedHints) return cachedHints;
  try {
    const candidates = [
      path.resolve(process.cwd(), "..", "data", "hints.json"),
      path.resolve(process.cwd(), "data", "hints.json"),
    ];
    for (const p of candidates) {
      if (fs.existsSync(/*turbopackIgnore: true*/ p)) {
        cachedHints = JSON.parse(fs.readFileSync(/*turbopackIgnore: true*/ p, "utf-8"));
        return cachedHints || {};
      }
    }
  } catch (err) {
    console.error("Failed to load data/hints.json:", err);
  }
  return {};
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ concept: string }> }
) {
  const session = await getServerSession();

  if (!session) {
    return NextResponse.json(
      { error: "Unauthorized: Active session required." },
      { status: 401 }
    );
  }

  const { concept } = await params;
  const { searchParams } = new URL(request.url);
  const difficulty = searchParams.get("difficulty") || "medium";

  const result = await callFastApiBackend(
    `/api/v1/concept_bundle/${encodeURIComponent(concept)}?difficulty=${encodeURIComponent(difficulty)}`,
    {
      method: "GET",
    }
  );

  if (!result.ok) {
    return NextResponse.json(
      { error: result.error || "Failed to retrieve concept assessment bundle." },
      { status: result.status }
    );
  }

  const rawBundle = result.data?.bundle || {};
  const hintsMap = getHintsMap();

  // CRITICAL SANITIZATION (Step 4):
  // Strip answer keys, reference answers, and expected test outputs
  const sanitizedMcqs = (rawBundle.mcqs || []).map((mcq: any) => ({
    id: mcq.id,
    difficulty: mcq.difficulty,
    question: mcq.question,
    options: mcq.options,
    hints: hintsMap[mcq.id] || [],
    // Exclude correct_option
  }));

  const sanitizedShortAnswer = rawBundle.short_answer
    ? {
        id: rawBundle.short_answer.id,
        difficulty: rawBundle.short_answer.difficulty,
        question: rawBundle.short_answer.question,
        hints: hintsMap[rawBundle.short_answer.id] || [],
        // Exclude reference_answer
      }
    : null;

  const sanitizedCoding = rawBundle.coding
    ? {
        id: rawBundle.coding.id,
        difficulty: rawBundle.coding.difficulty,
        problem: rawBundle.coding.problem,
        template: rawBundle.coding.template,
        hints: hintsMap[rawBundle.coding.id] || [],
        test_cases: (rawBundle.coding.test_cases || []).map((tc: any) => ({
          call: tc.call,
          description: tc.description,
          // Exclude expected return value
        })),
      }
    : null;

  return NextResponse.json({
    concept: result.data.concept || concept,
    difficulty: result.data.difficulty || difficulty,
    bundle: {
      mcqs: sanitizedMcqs,
      short_answer: sanitizedShortAnswer,
      coding: sanitizedCoding,
    },
  });
}

