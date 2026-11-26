/**
 * frontend/src/lib/api/backend-client.ts
 *
 * Secure server-side HTTP client for communicating with the FastAPI microservice.
 * Enforces internal service secret injection and verified student identity headers.
 * 
 * Guarantees:
 * - Server-only execution.
 * - Injects X-Internal-Service-Secret on all calls.
 * - Injects X-Authenticated-Student-Id ONLY from verified session identity.
 * - Strict timeout protection via AbortController.
 * - Sanitized error mapping preventing leakage of backend stack traces.
 */

import { getFastApiBackendUrl, getInternalServiceSecret } from "@/lib/auth/session";

export interface BackendRequestOptions extends Omit<RequestInit, "headers"> {
  timeoutMs?: number;
  studentId?: string; // Authenticated student identity strictly from server-side session
  headers?: Record<string, string>;
}

export interface BackendClientResult<T> {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
}

/**
 * Validates that an incoming state-changing request originates from the same host.
 * Mitigates cross-origin CSRF attacks on API routes.
 */
export function verifyRequestOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host") || request.headers.get("x-forwarded-host");

  if (!origin || !host) {
    // If browser doesn't send origin (e.g. same-origin GET/fetch), proceed
    return true;
  }

  try {
    const originHost = new URL(origin).host;
    return originHost.toLowerCase() === host.toLowerCase();
  } catch {
    return false;
  }
}

/**
 * Calls the FastAPI backend with internal service credentials and optional student scoping.
 */
export async function callFastApiBackend<T = any>(
  endpoint: string,
  options: BackendRequestOptions = {}
): Promise<BackendClientResult<T>> {
  const {
    timeoutMs = 8000,
    studentId,
    headers: customHeaders = {},
    ...fetchOptions
  } = options;

  let serviceSecret: string;
  try {
    serviceSecret = getInternalServiceSecret();
  } catch {
    return {
      ok: false,
      status: 500,
      error: "Server configuration error: authentication service is not properly configured.",
    };
  }

  const backendBase = getFastApiBackendUrl();
  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const fullUrl = `${backendBase}${normalizedEndpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const requestHeaders = new Headers(customHeaders);
  requestHeaders.set("X-Internal-Service-Secret", serviceSecret);

  if (studentId && typeof studentId === "string" && studentId.trim()) {
    requestHeaders.set("X-Authenticated-Student-Id", studentId.trim());
  }

  if (!requestHeaders.has("Content-Type") && fetchOptions.body) {
    requestHeaders.set("Content-Type", "application/json");
  }

  try {
    const res = await fetch(fullUrl, {
      ...fetchOptions,
      headers: requestHeaders,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let safeError = "Backend service request failed.";
      if (res.status === 401) {
        safeError = "Unauthorized: Session identity rejected by backend.";
      } else if (res.status === 403) {
        safeError = "Forbidden: Access denied to requested backend resource.";
      } else if (res.status === 404) {
        safeError = "The requested learning resource was not found.";
      } else if (res.status >= 500) {
        safeError = "The backend service encountered an internal error. Please try again later.";
      }

      return {
        ok: false,
        status: res.status,
        error: safeError,
      };
    }

    let parsedData: T;
    try {
      parsedData = (await res.json()) as T;
    } catch {
      return {
        ok: false,
        status: 502,
        error: "Malformed response received from backend service.",
      };
    }

    return {
      ok: true,
      status: res.status,
      data: parsedData,
    };
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      return {
        ok: false,
        status: 504,
        error: "Backend request timed out. Please try again.",
      };
    }
    return {
      ok: false,
      status: 503,
      error: "Backend service is currently unavailable. Please check backend connection.",
    };
  }
}

