/**
 * frontend/src/middleware.ts
 *
 * Next.js Edge Middleware for route protection.
 * Intercepts requests to portal routes and redirects unauthenticated visitors to `/login`.
 * Redirects authenticated visitors attempting to access `/login` or `/register` to `/dashboard`.
 */

import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME, verifySessionToken } from "@/lib/auth/session";

const PROTECTED_ROUTES = [
  "/dashboard",
  "/adaptive-learning",
  "/practice",
  "/analytics",
  "/history",
  "/profile",
];

const AUTH_ROUTES = ["/login", "/register"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtectedRoute = PROTECTED_ROUTES.some((route) =>
    pathname === route || pathname.startsWith(`${route}/`)
  );

  const isAuthRoute = AUTH_ROUTES.some((route) =>
    pathname === route || pathname.startsWith(`${route}/`)
  );

  const token = request.cookies.get(SESSION_COOKIE_NAME)?.value;
  const session = token ? await verifySessionToken(token) : null;

  // Protect Portal Routes
  if (isProtectedRoute && !session) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect away from Auth Routes if already authenticated
  if (isAuthRoute && session) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/adaptive-learning/:path*",
    "/practice/:path*",
    "/analytics/:path*",
    "/history/:path*",
    "/profile/:path*",
    "/login",
    "/register",
  ],
};
