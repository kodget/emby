"use client";

import { useEffect, useState } from "react";
import { Clock, Calendar } from "lucide-react";
import { classApi, ExamCountdown } from "@/lib/api";

export function ExamCountdownWidget() {
  const [countdowns, setCountdowns] = useState<ExamCountdown[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCountdowns();
  }, []);

  const loadCountdowns = async () => {
    try {
      const data = await classApi.getExamCountdowns();
      const sorted = data.sort((a, b) => 
        new Date(a.exam_date).getTime() - new Date(b.exam_date).getTime()
      );
      setCountdowns(sorted.slice(0, 3));
    } catch (error) {
      console.error("Failed to load countdowns:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-border bg-card p-6 animate-pulse">
        <div className="mb-4 h-6 w-1/2 rounded bg-muted"></div>
        <div className="space-y-3">
          <div className="h-4 rounded bg-muted"></div>
          <div className="h-4 w-3/4 rounded bg-muted"></div>
        </div>
      </div>
    );
  }

  if (countdowns.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="flex size-7 items-center justify-center rounded-lg bg-review/15 text-review">
          <Calendar className="size-4" />
        </span>
        <h3 className="font-serif text-base font-semibold tracking-tight">Upcoming Exams</h3>
      </div>

      <div className="space-y-2.5">
        {countdowns.slice(0, 3).map((countdown) => {
          const urgency =
            countdown.days_remaining <= 7
              ? "weakness"
              : countdown.days_remaining <= 14
                ? "review"
                : "mastery";
          return (
            <div
              key={countdown.id}
              className={`rounded-xl border border-border bg-background/50 p-3 ${
                urgency === "weakness" ? "border-weakness/30 bg-weakness/5" : ""
              }`}
            >
              <div className="mb-1 font-medium text-foreground">{countdown.title}</div>
              <div className="flex items-center gap-2 text-sm">
                <Clock className="size-4 text-muted-foreground" />
                <span
                  className={`font-mono font-semibold tabular-nums ${
                    urgency === "weakness"
                      ? "text-weakness"
                      : urgency === "review"
                        ? "text-review"
                        : "text-mastery"
                  }`}
                >
                  {countdown.days_remaining} days
                </span>
                <span className="text-muted-foreground">remaining</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
