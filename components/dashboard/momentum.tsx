"use client";

/**
 * Momentum — the daily tracker strip.
 *
 * The dashboard stated numbers but never *showed* anything, which is what made the cards
 * feel inert. This card plots the last 28 days of real study minutes, the week's accuracy
 * as a ring, and the current streak, so consistency is legible at a glance.
 *
 * Every value comes from /api/learning/analytics/. Nothing here is illustrative: when
 * there is no activity the card says so rather than drawing a flat line of zeros.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

import { Icon3D } from "@/components/brand/icon-3d";
import { DailyTracker, ProgressRing, Sparkline } from "@/components/ui/spark";
import { analyticsApi, type AnalyticsReport } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Momentum({ className }: { className?: string }) {
  const [report, setReport] = useState<AnalyticsReport | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await analyticsApi.getReport(28);
        if (!cancelled) {
          setReport(data);
          setState("ready");
        }
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return (
      <section className={cn("card-3d p-4", className)} aria-busy="true">
        <div className="skeleton h-4 w-28" />
        <div className="skeleton mt-4 h-[54px] w-full" />
      </section>
    );
  }

  if (state === "error" || !report) return null;

  const days = report.daily_activity.map((d) => ({ date: d.date, value: d.minutes }));
  const minutes = days.map((d) => d.value);
  const active = days.filter((d) => d.value > 0).length;
  const streak = report.consistency.current_streak;
  const accuracy = report.overview.accuracy;
  const totalMinutes = report.consistency.total_minutes;

  return (
    <section className={cn("card-3d overflow-hidden", className)}>
      <div className="flex items-start gap-3 p-4 pb-3">
        <Icon3D name="streak" size="sm" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-[15px] leading-tight">Your momentum</h2>
          <p className="text-[11px] text-muted-foreground">Last 28 days</p>
        </div>
        <Link
          href="/analytics"
          className="press shrink-0 rounded-full bg-secondary px-3 py-1 text-[11px] font-medium text-muted-foreground"
        >
          Details
        </Link>
      </div>

      {/* The tracker itself — gaps are the point, so empty days stay visible. */}
      <div className="px-4">
        <DailyTracker days={days} tone="primary" />
      </div>

      <div className="mt-3 flex items-center gap-4 border-t border-border/60 px-4 py-3">
        <ProgressRing
          value={accuracy}
          tone={accuracy === null ? "primary" : accuracy >= 0.7 ? "mastery" : accuracy >= 0.4 ? "review" : "weakness"}
          sublabel="%"
          label="Accuracy over the last 28 days"
        />
        <dl className="grid min-w-0 flex-1 grid-cols-3 gap-2 text-center">
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">Streak</dt>
            <dd className="font-mono text-base tabular">{streak}d</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">Active</dt>
            <dd className="font-mono text-base tabular">{active}/28</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-muted-foreground">Time</dt>
            <dd className="font-mono text-base tabular">
              {Math.floor(totalMinutes / 60)}h{totalMinutes % 60 ? ` ${totalMinutes % 60}m` : ""}
            </dd>
          </div>
        </dl>
      </div>

      <div className="px-4 pb-4">
        <Sparkline values={minutes} tone="primary" height={30} label="Study minutes per day" />
      </div>
    </section>
  );
}
