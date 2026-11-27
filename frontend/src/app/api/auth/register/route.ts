/**
 * frontend/src/app/api/auth/register/route.ts
 *
 * Next.js BFF Route: Student Registration
 * Forwards registration details to FastAPI `/register` with `X-Internal-Service-Secret`.
 * Does not create an active session; requires student to sign in afterward.
 */

import { NextRequest, NextResponse } from "next/server";
import {
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

    const { username, password, fullName, email } = body || {};

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

    // Retry once on network failure to smooth over cold boots
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        backendRes = await fetch(`${backendUrl}/register`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Internal-Service-Secret": serviceSecret,
          },
          body: JSON.stringify({
            username: username.trim().toLowerCase(),
            password,
            full_name: fullName ? String(fullName).trim() : undefined,
            email: email ? String(email).trim() : undefined,
          }),
        });
        networkError = false;
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
      let errorDetail = "Registration failed.";
      if (backendRes.status === 503) {
        errorDetail = "Service waking up, retry in a moment";
      }
      try {
        const errorData = await backendRes.json();
        if (errorData && errorData.detail) {
          errorDetail = errorData.detail;
        }
      } catch {
        // fallback
      }
      return NextResponse.json({ error: errorDetail }, { status: backendRes.status });
    }

    const data = await backendRes.json();

    return NextResponse.json({
      status: "success",
      message: "Student registered successfully. Please sign in to continue.",
      studentId: data.student_id,
      username: data.username,
    });
  } catch {
    return NextResponse.json(
      { error: "An unexpected error occurred during registration." },
      { status: 500 }
    );
  }
}

