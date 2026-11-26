import * as React from "react";
import { cn } from "@/lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number; // 0 to 100
  variant?: "default" | "mastery" | "uncertainty" | "danger";
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  (
    {
      className,
      value = 0,
      variant = "default",
      size = "md",
      showLabel = false,
      ...props
    },
    ref
  ) => {
    // Safely clamp value between 0 and 100
    const clampedValue = Math.min(100, Math.max(0, isNaN(value) ? 0 : value));

    const heightStyles = {
      sm: "h-1.5",
      md: "h-2.5",
      lg: "h-3.5",
    };

    const barColors = {
      default: "bg-teal-600",
      mastery: "bg-emerald-600",
      uncertainty: "bg-amber-500",
      danger: "bg-rose-600",
    };

    return (
      <div className={cn("w-full space-y-1", className)}>
        {showLabel && (
          <div className="flex justify-between items-center text-xs text-slate-500 mb-1">
            <span>Progress</span>
            <span className="font-mono font-semibold text-slate-800">
              {clampedValue.toFixed(1)}%
            </span>
          </div>
        )}
        <div
          ref={ref}
          role="progressbar"
          aria-valuenow={clampedValue}
          aria-valuemin={0}
          aria-valuemax={100}
          className={cn(
            "relative w-full overflow-hidden rounded-full bg-slate-100 border border-slate-200/80",
            heightStyles[size]
          )}
          {...props}
        >
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300 ease-out",
              barColors[variant]
            )}
            style={{ width: `${clampedValue}%` }}
          />
        </div>
      </div>
    );
  }
);

Progress.displayName = "Progress";
