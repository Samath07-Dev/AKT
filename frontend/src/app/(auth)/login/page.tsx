"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Eye, EyeOff, Lock, User, ArrowRight, AlertCircle } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [showPassword, setShowPassword] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (!username.trim()) {
      setError("Please enter your student username.");
      return;
    }
    if (username.trim().length < 3) {
      setError("Username must be at least 3 characters.");
      return;
    }
    if (!password) {
      setError("Please enter your password.");
      return;
    }
    if (password.length < 4) {
      setError("Password must be at least 4 characters.");
      return;
    }

    setIsLoading(true);

    const performLogin = async (isRetry = false) => {
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: username.trim(),
            password,
          }),
        });

        const data = await res.json();

        if (!res.ok) {
          // If service is cold/waking up (503) and we haven't retried yet, auto-retry once after 1.5s
          if (res.status === 503 && !isRetry) {
            setError("Service waking up, retry in a moment...");
            setTimeout(() => {
              performLogin(true);
            }, 1800);
            return;
          }

          if (res.status === 401) {
            setError("Invalid username or password.");
          } else if (res.status === 503) {
            setError(data.error || "Service waking up, retry in a moment");
          } else {
            setError(data.error || "Authentication failed. Please check your credentials.");
          }
          setIsLoading(false);
          return;
        }

        router.push("/dashboard");
        router.refresh();
      } catch {
        if (!isRetry) {
          setError("Service waking up, retry in a moment...");
          setTimeout(() => {
            performLogin(true);
          }, 1800);
          return;
        }
        setError("Service waking up, retry in a moment");
        setIsLoading(false);
      }
    };

    performLogin(false);
  };

  return (
    <Card className="border-slate-200 bg-white shadow-sm">
      <CardHeader className="space-y-1 pb-4">
        <div className="flex items-center justify-between">
          <Badge variant="info" size="sm" dot>
            Student Portal
          </Badge>
        </div>
        <CardTitle className="text-xl font-bold text-slate-900 mt-2">
          Sign In to Your Session
        </CardTitle>
        <CardDescription className="text-xs text-slate-600">
          Sign in to access your learning dashboard.
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

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {/* Username Field */}
          <div className="space-y-1.5">
            <label
              htmlFor="username-input"
              className="text-xs font-semibold text-slate-700 flex items-center justify-between"
            >
              <span>Username</span>
            </label>
            <div className="relative">
              <User className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                id="username-input"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                className="w-full rounded-xl border border-slate-300 bg-white pl-9 pr-3.5 py-2 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 font-sans"
              />
            </div>
          </div>

          {/* Password Field */}
          <div className="space-y-1.5">
            <label
              htmlFor="password-input"
              className="text-xs font-semibold text-slate-700 flex items-center justify-between"
            >
              <span>Password</span>
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                id="password-input"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
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

          {/* Submit Action */}
          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isLoading}
            className="w-full mt-2 gap-2 bg-teal-600 hover:bg-teal-700 text-white border-transparent"
          >
            <span>Sign In</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
      </CardContent>

      <CardFooter className="border-t border-slate-200 pt-4 flex items-center justify-between text-xs text-slate-600">
        <span>Need a student account?</span>
        <Link
          href="/register"
          className="font-semibold text-teal-600 hover:text-teal-700 transition-colors"
        >
          Register Here
        </Link>
      </CardFooter>
    </Card>
  );
}

