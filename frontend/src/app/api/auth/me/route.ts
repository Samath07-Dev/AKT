/**
 * frontend/src/app/api/auth/me/route.ts
 *
 * Next.js BFF Route: Current Session Verification
 * Verifies the `akt_session` cookie and returns the authenticated student profile.
 */

import { NextRequest, NextResponse } from "next/server";
import {
  verifySessionToken,
  SESSION_COOKIE_NAME,
} from "@/lib/auth/session";

export async function GET(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;

  if (!token) {
    return NextResponse.json(
      { authenticated: false, error: "No active session." },
      { status: 401 }
    );
  }

  const session = await verifySessionToken(token);

  if (!session) {
    return NextResponse.json(
      { authenticated: false, error: "Invalid or expired session." },
      { status: 401 }
    );
  }

  return NextResponse.json({
    authenticated: true,
    student: {
      studentId: session.studentId,
      username: session.username,
      fullName: session.fullName,
    },
  });
}
