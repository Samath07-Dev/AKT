/**
 * frontend/src/app/api/student/mastery/route.ts
 *
 * Next.js BFF Route: Student Knowledge Mastery State
 * Retrieves real-time Bayesian knowledge state vector from FastAPI backend.
 * Uses only verified session identity; browser cannot override student_id.
 */

import { NextResponse } from "next/server";
import { getServerSession } from "@/lib/auth/session";
import { callFastApiBackend } from "@/lib/api/backend-client";

export async function GET() {
  const session = await getServerSession();

  if (!session) {
    return NextResponse.json(
      { error: "Unauthorized: Active session required." },
      { status: 401 }
    );
  }

  const result = await callFastApiBackend(
    `/api/v1/student/${session.studentId}/mastery`,
    {
      method: "GET",
      studentId: session.studentId,
    }
  );

  if (!result.ok) {
    return NextResponse.json(
      { error: result.error || "Failed to fetch student mastery state." },
      { status: result.status }
    );
  }

  return NextResponse.json(result.data);
}

