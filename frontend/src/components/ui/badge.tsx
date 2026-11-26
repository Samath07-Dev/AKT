import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "danger" | "info";
  size?: "sm" | "md";
  dot?: boolean;
}

export function Badge({
  className,
  variant = "default",
  size = "md",
  dot = false,
  children,
  ...props
}: BadgeProps) {
  const variantStyles = {
    default: "bg-slate-100 text-slate-700 border-slate-200/90",
    success: "bg-emerald-50 text-emerald-800 border-emerald-200/90",
    warning: "bg-amber-50 text-amber-800 border-amber-200/90",
    danger: "bg-rose-50 text-rose-800 border-rose-200/90",
    info: "bg-teal-50 text-teal-800 border-teal-200/90",
  };

  const dotColors = {
    default: "bg-slate-500",
    success: "bg-emerald-600",
    warning: "bg-amber-600",
    danger: "bg-rose-600",
    info: "bg-teal-600",
  };

  const sizeStyles = {
    sm: "px-2 py-0.5 text-[10px] gap-1 font-medium",
    md: "px-2.5 py-0.5 text-xs gap-1.5 font-medium",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border transition-colors select-none",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={cn("h-1.5 w-1.5 rounded-full shrink-0", dotColors[variant])}
          aria-hidden="true"
        />
      )}
      {children}
    </div>
  );
}
