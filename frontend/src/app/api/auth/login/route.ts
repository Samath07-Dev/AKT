/**
 * frontend/src/app/api/auth/login/route.ts
 *
 * Next.js BFF Route: Student Login
 * Forwards credentials to FastAPI `/login` with `X-Internal-Service-Secret`.
 * On success, issues a secure HttpOnly `akt_session` cookie containing
 * an HMAC-signed student session token.
 */

import { NextRequest, NextResponse } from "next/server";
import {
  createSessionToken,
  SESSION_COOKIE_NAME,
  DEFAULT_SESSION_MAX_AGE,
  getSessionCookieOptions,
  getFastApiBackendUrl,
  getInternalServiceSecret,
} from "@/lib/auth/session";

export async function POST(request: NextRequest) {
  try {
    let body: any;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json(
        { error: "Invalid JSON request payload." },
        { status: 400 }
      );
    }

    const { username, password } = body || {};

    if (!username || typeof username !== "string" || username.trim().length < 3) {
      return NextResponse.json(
        { error: "Username must be at least 3 characters long." },
        { status: 400 }
      );
    }

    if (!password || typeof password !== "string" || password.length < 4) {
      return NextResponse.json(
        { error: "Password must be at least 4 characters long." },
        { status: 400 }
      );
    }

    let serviceSecret: string;
    try {
      serviceSecret = getInternalServiceSecret();
    } catch {
      return NextResponse.json(
        { error: "Server configuration error: authentication service is not properly configured." },
        { status: 500 }
      );
    }

    const backendUrl = getFastApiBackendUrl();

    let backendRes: Response | null = null;
    let networkError = false;

    // Retry once on network/connection failure to smooth over HF Spaces wake-ups
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        backendRes = await fetch(`${backendUrl}/login`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Internal-Service-Secret": serviceSecret,
          },
          body: JSON.stringify({
            username: username.trim().toLowerCase(),
            password,
          }),
        });
        networkError = false;
        // If we received 502/503 from backend wake-up, pause briefly and retry once
        if (backendRes.status >= 502 && attempt === 0) {
          await new Promise((r) => setTimeout(r, 1200));
          continue;
        }
        break;
      } catch {
        networkError = true;
        if (attempt === 0) {
          await new Promise((r) => setTimeout(r, 1500));
        }
      }
    }

    if (networkError || !backendRes) {
      return NextResponse.json(
        { error: "Service waking up, retry in a moment" },
        { status: 503 }
      );
    }

    if (!backendRes.ok) {
      if (backendRes.status === 401) {
        return NextResponse.json(
          { error: "Invalid username or password." },
          { status: 401 }
        );
      }
      if (backendRes.status === 403) {
        return NextResponse.json(
          { error: "Internal service authorization failed. Please contact the administrator." },
          { status: 500 }
        );
      }
      if (backendRes.status === 503) {
        let message = "Service waking up, retry in a moment";
        try {
          const errData = await backendRes.json();
          if (errData && errData.detail) message = errData.detail;
        } catch {}
        return NextResponse.json(
          { error: message },
          { status: 503 }
        );
      }
      let genericError = "Authentication failed. Please check your credentials.";
      try {
        const errData = await backendRes.json();
        if (errData && errData.detail) genericError = errData.detail;
      } catch {}
      return NextResponse.json(
        { error: genericError },
        { status: backendRes.status }
      );
    }

    const data = await backendRes.json();

    if (!data || !data.student_id) {
      return NextResponse.json(
        { error: "Authentication response from backend did not include a valid student identity." },
        { status: 502 }
      );
    }

    // Generate signed HMAC session token using verified backend student identity
    let sessionToken: string;
    try {
      sessionToken = await createSessionToken({
        studentId: data.student_id,
        username: data.username || username.trim().toLowerCase(),
        fullName: data.full_name || data.username || username.trim(),
      });
    } catch {
      return NextResponse.json(
        { error: "Failed to establish secure session." },
        { status: 500 }
      );
    }

    const response = NextResponse.json({
      status: "success",
      message: "Login successful",
      student: {
        studentId: data.student_id,
        username: data.username || username.trim().toLowerCase(),
        fullName: data.full_name || data.username || username.trim(),
      },
    });

    response.cookies.set(
      SESSION_COOKIE_NAME,
      sessionToken,
      getSessionCookieOptions(DEFAULT_SESSION_MAX_AGE)
    );

    return response;
  } catch {
    return NextResponse.json(
      { error: "An unexpected error occurred during authentication." },
      { status: 500 }
    );
  }
}
