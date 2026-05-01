"use client";

import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { progressApi } from "@/lib/api";
import { Loader2 } from "lucide-react";

export function WeeklyChart() {
  const [data, setData] = useState<any[]>([]);
  const [totalHours, setTotalHours] = useState(0);
  const [totalMinutes, setTotalMinutes] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWeeklyData();
  }, []);

  const loadWeeklyData = async () => {
    try {
      const weeklyData = await progressApi.getWeeklyStudyData();
      setData(weeklyData.week_data);
      setTotalHours(weeklyData.total_hours);
      setTotalMinutes(weeklyData.remaining_minutes);
    } catch (error) {
      console.error("Failed to load weekly study data:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <section className="rounded-3xl border border-border bg-card p-6" aria-labelledby="weekly-heading">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-border bg-card p-6" aria-labelledby="weekly-heading">
      <header className="flex items-end justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-primary">Your week</p>
          <h2 id="weekly-heading" className="mt-1 font-serif text-2xl">
            Study minutes
          </h2>
        </div>
        <div className="text-right">
          <p className="text-[11px] uppercase tracking-widest text-muted-foreground">Total</p>
          <p className="font-serif text-2xl">{totalHours}h {totalMinutes}m</p>
        </div>
      </header>

      <div className="mt-4 h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="mintes" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={36}
            />
            <Tooltip
              contentStyle={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                fontSize: 12,
              }}
              labelStyle={{ color: "var(--foreground)" }}
            />
            <Area
              type="monotone"
              dataKey="minutes"
              stroke="var(--chart-1)"
              strokeWidth={2}
              fill="url(#mintes)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
