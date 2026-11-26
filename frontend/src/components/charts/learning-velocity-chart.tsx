"use client";

import * as React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Button } from "@/components/ui/button";

export interface LearningSessionItem {
  session: string;      // "S1", "S2", etc.
  date: string;         // "Mar 1", "Mar 2"
  concept: string;      // "Variables", "Loops"
  bundleScore: number;  // 0 to 100
  masteryDelta?: number; // Optional legacy field
}

interface LearningVelocityChartProps {
  data: LearningSessionItem[];
  height?: number;
  isDemo?: boolean;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    color: string;
    payload: LearningSessionItem;
  }>;
}

function CustomVelocityTooltip({ active, payload }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const item = payload[0].payload;
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-xl text-xs">
        <div className="flex items-center justify-between gap-3 mb-1.5 pb-1 border-b border-slate-100">
          <span className="font-bold text-slate-900">{item.session}: {item.concept}</span>
          <span className="text-[10px] text-slate-500 font-mono">{item.date}</span>
        </div>
        <div className="space-y-1 font-mono text-[11px]">
          <div className="flex items-center justify-between gap-4">
            <span className="text-blue-700 font-medium">Bundle Score:</span>
            <span className="font-bold text-slate-900">{item.bundleScore.toFixed(1)}%</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
}

export function LearningVelocityChart({
  data,
  height = 320,
  isDemo = false,
}: LearningVelocityChartProps) {
  const [isMounted, setIsMounted] = React.useState(false);
  const [filterRange, setFilterRange] = React.useState<"all" | "last5">("all");

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  const filteredData = React.useMemo(() => {
    if (filterRange === "last5") {
      return data.slice(-5);
    }
    return data;
  }, [data, filterRange]);

  if (!isMounted) {
    return (
      <div
        className="w-full flex items-center justify-center rounded-xl bg-slate-50/60 border border-slate-200"
        style={{ height }}
      >
        <span className="text-xs font-mono text-slate-500 animate-pulse">
          Loading Learning Velocity Chart...
        </span>
      </div>
    );
  }

  return (
    <div className="w-full space-y-3">
      {/* Chart Toolbar Controls */}
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono text-slate-600">
          Showing {filteredData.length} of {data.length}{" "}
          {isDemo ? "demonstration sessions (Demo Data)" : "verified assessment sessions"}
        </span>
        <div className="flex items-center gap-1.5">
          <Button
            variant={filterRange === "all" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilterRange("all")}
            className="text-[11px] h-7 px-2.5"
          >
            All Sessions
          </Button>
          <Button
            variant={filterRange === "last5" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setFilterRange("last5")}
            className="text-[11px] h-7 px-2.5"
          >
            Last 5 Sessions
          </Button>
        </div>
      </div>

      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
            <defs>
              <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#2563EB" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#2563EB" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis
              dataKey="session"
              stroke="#CBD5E1"
              tick={{ fill: "#334155", fontSize: 11, fontWeight: 500 }}
              tickLine={{ stroke: "#CBD5E1" }}
            />
            <YAxis
              domain={[0, 100]}
              stroke="#CBD5E1"
              tick={{ fill: "#334155", fontSize: 10, fontWeight: 500 }}
              tickLine={{ stroke: "#CBD5E1" }}
              unit="%"
            />
            <Tooltip content={<CustomVelocityTooltip />} />
            <Legend
              verticalAlign="top"
              align="right"
              wrapperStyle={{ paddingBottom: 12 }}
              formatter={(value) => (
                <span className="text-xs font-semibold text-blue-800 ml-1 mr-3">
                  {value}
                </span>
              )}
            />
            <Area
              type="monotone"
              name="Bundle Score (%)"
              dataKey="bundleScore"
              stroke="#2563EB"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#scoreGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Screen-reader accessible table */}
      <div className="sr-only">
        <h4>Learning Velocity Performance Table</h4>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>Date</th>
              <th>Concept</th>
              <th>Bundle Score</th>
            </tr>
          </thead>
          <tbody>
            {filteredData.map((item) => (
              <tr key={item.session}>
                <td>{item.session}</td>
                <td>{item.date}</td>
                <td>{item.concept}</td>
                <td>{item.bundleScore}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

