/**
 * frontend/src/lib/auth/session.ts
 *
 * Universal Web-Standard cryptographic session utility for the Behavior-AKT Next.js BFF.
 * Employs Web Crypto HMAC-SHA256 signatures with constant-time verification.
 * 
 * Security Guarantees:
 * - Server-only execution; server secrets are NEVER exposed to browser components.
 * - Minimum 32-character secret enforcement; fails closed if secret is missing or weak.
 * - Constant-time Web Crypto signature comparison eliminates timing attack vectors.
 * - Expiration and payload integrity verified on every session check.
 * - Universal runtime compatibility: fully supported in Edge Runtime and Node.js.
 */

import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "akt_session";
export const DEFAULT_SESSION_MAX_AGE = 7 * 24 * 60 * 60; // 7 days in seconds

export interface SessionPayload {
  studentId: string;
  username: string;
  fullName: string;
  iat: number;
  exp: number;
}

export interface SafeStudentSession {
  studentId: string;
  username: string;
  fullName: string;
}

/**
 * Retrieves the server-side signing secret from environment variables.
 * Fails closed if missing or fewer than 32 characters.
 */
export function getSessionSecret(): string {
  const secret = process.env.SESSION_SECRET || process.env.JWT_SECRET;
  if (!secret || secret.trim().length < 32) {
    throw new Error(
      "Server configuration error: SESSION_SECRET (or JWT_SECRET) is not configured or insufficiently strong (minimum 32 characters required)."
    );
  }
  return secret.trim();
}

/**
 * Retrieves the internal service secret for loopback communication with FastAPI.
 * Fails closed if missing or fewer than 32 characters.
 */
export function getInternalServiceSecret(): string {
  const secret = process.env.INTERNAL_SERVICE_SECRET;
  if (!secret || secret.trim().length < 32) {
    throw new Error(
      "Server configuration error: INTERNAL_SERVICE_SECRET is not configured or insufficiently strong (minimum 32 characters required)."
    );
  }
  return secret.trim();
}

/**
 * Retrieves the FastAPI backend URL.
 * Checks BACKEND_URL, FASTAPI_BACKEND_URL, and BACKEND_API_URL.
 */
export function getFastApiBackendUrl(): string {
  return (
    process.env.BACKEND_URL ||
    process.env.FASTAPI_BACKEND_URL ||
    process.env.BACKEND_API_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function base64UrlDecode(str: string): Uint8Array {
  let base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4) {
    base64 += "=";
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function getCryptoKey(secret: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  return await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

/**
 * Creates an HMAC-signed session token encoding the authenticated student identity.
 */
export async function createSessionToken(
  student: { studentId: string; username: string; fullName?: string },
  expiresInSeconds: number = DEFAULT_SESSION_MAX_AGE
): Promise<string> {
  const secret = getSessionSecret();
  const key = await getCryptoKey(secret);
  const enc = new TextEncoder();

  const now = Math.floor(Date.now() / 1000);
  const payload: SessionPayload = {
    studentId: student.studentId.trim(),
    username: student.username.trim(),
    fullName: (student.fullName || student.username).trim(),
    iat: now,
    exp: now + expiresInSeconds,
  };

  const encodedPayload = base64UrlEncode(enc.encode(JSON.stringify(payload)));
  const signatureBuffer = await crypto.subtle.sign(
    "HMAC",
    key,
    enc.encode(encodedPayload)
  );
  const encodedSignature = base64UrlEncode(new Uint8Array(signatureBuffer));

  return `${encodedPayload}.${encodedSignature}`;
}

/**
 * Cryptographically verifies an HMAC-signed session token using constant-time Web Crypto verification.
 * Validates format, signature, and expiration.
 */
export async function verifySessionToken(
  token: string | undefined | null
): Promise<SafeStudentSession | null> {
  if (!token || typeof token !== "string") {
    return null;
  }

  const parts = token.split(".");
  if (parts.length !== 2) {
    return null;
  }

  const [encodedPayload, providedSignature] = parts;
  if (!encodedPayload || !providedSignature) {
    return null;
  }

  let secret: string;
  try {
    secret = getSessionSecret();
  } catch {
    // Fail closed if server secret is missing or misconfigured
    return null;
  }

  try {
    const key = await getCryptoKey(secret);
    const enc = new TextEncoder();
    const signatureBytes = base64UrlDecode(providedSignature);

    const isValid = await crypto.subtle.verify(
      "HMAC",
      key,
      signatureBytes,
      enc.encode(encodedPayload)
    );

    if (!isValid) {
      return null;
    }

    const payloadJson = new TextDecoder().decode(base64UrlDecode(encodedPayload));
    const payload: SessionPayload = JSON.parse(payloadJson);

    if (!payload.studentId || !payload.username || !payload.exp) {
      return null;
    }

    const now = Math.floor(Date.now() / 1000);
    if (now >= payload.exp) {
      return null;
    }

    return {
      studentId: payload.studentId,
      username: payload.username,
      fullName: payload.fullName || payload.username,
    };
  } catch {
    return null;
  }
}

/**
 * Retrieves standard cookie attributes for the session cookie.
 */
export function getSessionCookieOptions(maxAge: number = DEFAULT_SESSION_MAX_AGE) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge,
  };
}

/**
 * Server-only helper extracting and verifying the authenticated session from request cookies.
 */
export async function getServerSession(): Promise<SafeStudentSession | null> {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
    if (!token) {
      return null;
    }
    return await verifySessionToken(token);
  } catch {
    return null;
  }
}
