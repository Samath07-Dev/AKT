/**
 * frontend/src/app/api/practice/sandbox-status/route.ts
 *
 * Next.js BFF Route: Live Docker Sandbox Availability Check
 * Queries the FastAPI evaluator server-side without executing untrusted code
 * or touching MongoDB. Always fails closed to SANDBOX_OFFLINE on error.
 */

import { NextResponse } from "next/server";
import { getServerSession } from "@/lib/auth/session";
import { probeDockerSandboxAvailability } from "@/lib/server/sandbox-status";

export async function GET() {
  const session = await getServerSession();
  if (!session) {
    return NextResponse.json(
      { error: "Unauthorized: Active session required." },
      { status: 401 }
    );
  }

  const result = await probeDockerSandboxAvailability();
  return NextResponse.json(result, {
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}

