"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Eye, EyeOff, Lock, User, Mail, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = React.useState("");
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    // Client-side validations
    if (!fullName.trim()) {
      setError("Please enter your full name.");
      return;
    }
    if (!username.trim() || username.trim().length < 3) {
      setError("Username must be at least 3 characters.");
      return;
    }
    if (!password || password.length < 4) {
      setError("Password must be at least 4 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);

    const performRegister = async (isRetry = false) => {
      try {
        const res = await fetch("/api/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            fullName: fullName.trim(),
            username: username.trim(),
            password,
          }),
        });

        const data = await res.json();

        if (!res.ok) {
          if (res.status === 503 && !isRetry) {
            setError("Service waking up, retry in a moment...");
            setTimeout(() => {
              performRegister(true);
            }, 1800);
            return;
          }

          if (res.status === 503) {
            setError(data.error || "Service waking up, retry in a moment");
          } else {
            setError(data.error || "Registration failed. Please try again.");
          }
          setIsLoading(false);
          return;
        }

        setSuccessMessage(data.message || "Account registered successfully! Redirecting to sign in...");
        setTimeout(() => {
          router.push("/login");
        }, 1200);
      } catch {
        if (!isRetry) {
          setError("Service waking up, retry in a moment...");
          setTimeout(() => {
            performRegister(true);
          }, 1800);
          return;
        }
        setError("Service waking up, retry in a moment");
        setIsLoading(false);
      }
    };

    performRegister(false);
  };

  return (
    <Card className="border-slate-200 bg-white shadow-sm">
      <CardHeader className="space-y-1 pb-4">
        <div className="flex items-center justify-between">
          <Badge variant="info" size="sm" dot>
            New Student
          </Badge>
        </div>
        <CardTitle className="text-xl font-bold text-slate-900 mt-2">
          Create Student Account
        </CardTitle>
        <CardDescription className="text-xs text-slate-600">
          Create an account to start your personalized learning journey.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Error Alert */}
        {error && (
          <div
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-center gap-2"
          >
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Success Alert */}
        {successMessage && (
          <div
            role="alert"
            className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 flex items-center gap-2"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{successMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* Full Name */}
          <div className="space-y-1">
            <label
              htmlFor="fullname-input"
              className="text-xs font-semibold text-slate-700"
            >
              Full Name
            </label>
            <div className="relative">
              <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                id="fullname-input"
                type="text"
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your full name"
                className="w-full rounded-xl border border-slate-300 bg-white pl-9 pr-3.5 py-2 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 font-sans"
              />
            </div>
          </div>

          {/* Username */}
          <div className="space-y-1">
            <label
              htmlFor="reg-username-input"
              className="text-xs font-semibold text-slate-700"
            >
              Username
            </label>
            <div className="relative">
              <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                id="reg-username-input"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Choose a username"
                className="w-full rounded-xl border border-slate-300 bg-white pl-9 pr-3.5 py-2 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 font-sans"
              />
            </div>
          </div>

          {/* Password */}
          <div className="space-y-1">
            <label
              htmlFor="reg-password-input"
              className="text-xs font-semibold text-slate-700"
            >
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                id="reg-password-input"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 4 characters"
                className="w-full rounded-xl border border-slate-300 bg-white pl-9 pr-10 py-2 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 font-sans"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div className="space-y-1">
            <label
              htmlFor="confirm-password-input"
              className="text-xs font-semibold text-slate-700"
            >
              Confirm Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                id="confirm-password-input"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                className="w-full rounded-xl border border-slate-300 bg-white pl-9 pr-3.5 py-2 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 font-sans"
              />
            </div>
          </div>

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isLoading}
            className="w-full mt-3 gap-2 bg-teal-600 hover:bg-teal-700 text-white border-transparent"
          >
            <span>Create Account</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>

      <CardFooter className="border-t border-slate-200 pt-4 flex items-center justify-between text-xs text-slate-600">
        <span>Already have an account?</span>
        <Link
          href="/login"
          className="font-semibold text-teal-600 hover:text-teal-700 transition-colors"
        >
          Sign In
        </Link>
      </CardFooter>
    </Card>
  );
}

