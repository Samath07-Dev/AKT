/**
 * frontend/src/app/api/student/history/route.ts
 *
 * Next.js BFF Route: Student Assessment History
 * Retrieves verified assessment and interaction history from MongoDB via FastAPI.
 * Scoped strictly to the authenticated student session.
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
    `/api/v1/student/${session.studentId}/history`,
    {
      method: "GET",
      studentId: session.studentId,
    }
  );

  if (!result.ok) {
    return NextResponse.json(
      { error: result.error || "Failed to fetch assessment history." },
      { status: result.status }
    );
  }

  return NextResponse.json(result.data);
}

