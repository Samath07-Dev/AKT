import * as React from "react";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";

export interface MetricCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: string | number;
  description?: string;
  icon?: LucideIcon;
  trend?: {
    value: string;
    isPositive?: boolean;
  };
  accentColor?: "indigo" | "cyan" | "emerald" | "amber" | "rose";
}

export function MetricCard({
  label,
  value,
  description,
  icon: Icon,
  trend,
  accentColor = "cyan",
  className,
  ...props
}: MetricCardProps) {
  const accentIconStyles = {
    indigo: "text-teal-700 bg-teal-50 border-teal-200/80",
    cyan: "text-sky-700 bg-sky-50 border-sky-200/80",
    emerald: "text-emerald-700 bg-emerald-50 border-emerald-200/80",
    amber: "text-amber-700 bg-amber-50 border-amber-200/80",
    rose: "text-rose-700 bg-rose-50 border-rose-200/80",
  };

  return (
    <Card
      className={cn(
        "relative overflow-hidden border border-slate-200/90 bg-white shadow-xs hover:border-slate-300 transition-all duration-200",
        className
      )}
      {...props}
    >
      <div className="p-3.5 sm:p-4 flex flex-col justify-between h-full">
        <div className="flex items-start justify-between gap-2.5">
          <span className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase font-mono leading-snug pt-1">
            {label}
          </span>
          {Icon && (
            <div className={cn("p-2 rounded-lg border shrink-0", accentIconStyles[accentColor])}>
              <Icon className="h-4 w-4" aria-hidden="true" />
            </div>
          )}
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <span className="text-2xl lg:text-3xl font-bold tracking-tight text-slate-900 font-mono">
            {value}
          </span>
          {trend && (
            <span
              className={cn(
                "inline-flex items-center text-[11px] font-semibold font-mono px-1.5 py-0.5 rounded border",
                trend.isPositive
                  ? "text-emerald-800 bg-emerald-50 border-emerald-200"
                  : "text-rose-800 bg-rose-50 border-rose-200"
              )}
            >
              {trend.isPositive ? "+" : ""}{trend.value}
            </span>
          )}
        </div>

        {description && (
          <p className="mt-2 text-xs text-slate-500 leading-relaxed">
            {description}
          </p>
        )}
      </div>
    </Card>
  );
}
