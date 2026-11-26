/**
 * frontend/src/app/api/auth/logout/route.ts
 *
 * Next.js BFF Route: Student Logout
 * Clears the HttpOnly `akt_session` cookie.
 */

import { NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/auth/session";

export async function POST() {
  const response = NextResponse.json({
    status: "success",
    message: "Logged out successfully",
  });

  // Explicitly clear session cookie across all path configurations
  response.cookies.delete(SESSION_COOKIE_NAME);
  response.cookies.set(SESSION_COOKIE_NAME, "", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 0,
    expires: new Date(0),
  });

  return response;
}

