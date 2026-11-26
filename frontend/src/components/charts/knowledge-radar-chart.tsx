"use client";

import * as React from "react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

export interface KnowledgeRadarItem {
  concept: string;
  mastery: number;      // 0 to 100
  uncertainty: number;  // 0 to 100
  hasAttempts?: boolean;
}

interface KnowledgeRadarChartProps {
  data: KnowledgeRadarItem[];
  height?: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    payload: KnowledgeRadarItem;
  }>;
}

function CustomRadarTooltip({ active, payload }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const item = payload[0].payload;
    const isAssessed = Boolean(item.hasAttempts);

    return (
      <div className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-xl text-xs">
        <div className="flex items-center justify-between gap-2 mb-1.5 pb-1 border-b border-slate-100">
          <p className="font-bold text-slate-900 text-sm">{item.concept}</p>
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
              isAssessed
                ? "bg-teal-50 text-teal-800 border-teal-200/90"
                : "bg-slate-100 text-slate-600 border-slate-200"
            }`}
          >
            {isAssessed ? "Assessed" : "Unassessed"}
          </span>
        </div>
        <div className="space-y-1 font-mono text-[11px]">
          <div className="flex items-center justify-between gap-4">
            <span className="text-teal-700 font-medium">Mastery (μ):</span>
            {isAssessed ? (
              <span className="font-bold text-slate-900">
                {item.mastery.toFixed(1)}%{" "}
                <span className="text-[10px] text-teal-700 font-normal">
                  (Updated EMA Mastery)
                </span>
              </span>
            ) : (
              <span className="font-medium text-slate-500">
                Unassessed — No Attempts
              </span>
            )}
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-blue-700 font-medium">Uncertainty (σ):</span>
            <span className="font-bold text-slate-900">
              {item.uncertainty.toFixed(1)}%
              {!isAssessed && (
                <span className="text-[10px] text-slate-500 font-normal ml-1">
                  (Baseline Prior)
                </span>
              )}
            </span>
          </div>
          {isAssessed && (
            <p className="text-[10px] text-slate-600 pt-1 font-sans border-t border-slate-100 mt-1 leading-snug">
              Real-time EMA mastery state derived from verified multi-modal assessment submissions.
            </p>
          )}
        </div>
      </div>
    );
  }
  return null;
}

export function KnowledgeRadarChart({
  data,
  height = 360,
}: KnowledgeRadarChartProps) {
  const [isMounted, setIsMounted] = React.useState(false);

  React.useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return (
      <div
        className="w-full flex items-center justify-center rounded-xl bg-slate-50/60 border border-slate-200"
        style={{ height }}
      >
        <span className="text-xs font-mono text-slate-500 animate-pulse">
          Loading Knowledge State Radar...
        </span>
      </div>
    );
  }

  return (
    <div className="w-full">
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
            <PolarGrid stroke="#CBD5E1" strokeDasharray="3 3" />
            <PolarAngleAxis
              dataKey="concept"
              stroke="#94A3B8"
              tick={{ fill: "#0F172A", fontSize: 11, fontWeight: 600 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              stroke="#94A3B8"
              tick={{ fill: "#475569", fontSize: 10, fontWeight: 500 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip content={<CustomRadarTooltip />} />
            <Legend
              wrapperStyle={{ paddingTop: 16 }}
              formatter={(value) => {
                const isMastery = value.includes("Mastery");
                return (
                  <span className={`text-xs font-semibold ${isMastery ? "text-teal-800" : "text-blue-800"} mr-4`}>
                    {value}
                  </span>
                );
              }}
            />
            <Radar
              name="Mastery (μ)"
              dataKey="mastery"
              stroke="#0D9488"
              fill="#0D9488"
              fillOpacity={0.25}
              strokeWidth={2}
            />
            <Radar
              name="Uncertainty (σ)"
              dataKey="uncertainty"
              stroke="#2563EB"
              fill="#2563EB"
              fillOpacity={0.15}
              strokeWidth={2}
              strokeDasharray="4 4"
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {/* Screen-reader accessible data summary */}
      <div className="sr-only">
        <h4>Knowledge State Radar Data Table</h4>
        <table>
          <thead>
            <tr>
              <th>Concept</th>
              <th>Mastery</th>
              <th>Uncertainty</th>
            </tr>
          </thead>
          <tbody>
            {data.map((item) => (
              <tr key={item.concept}>
                <td>{item.concept}</td>
                <td>{item.mastery}%</td>
                <td>{item.uncertainty}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

