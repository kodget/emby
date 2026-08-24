"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Play, Sparkles, Clock, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { flashcardApi, aiApi, quizApi } from "@/lib/api";

interface SessionStats {
  dueCards: number;
  weakTopic: string | null;
  missedCount: number;
  estimatedMinutes: number;
}

export function TodaySessionCard() {
  const [stats, setStats] = useState<SessionStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadSessionStats() {
      try {
        // Run all three in parallel; tolerate individual failures gracefully
        const [fcStats, recs, quizHistory] = await Promise.allSettled([
          flashcardApi.getStats(),
          aiApi.getRecommendations(),
          quizApi.getQuizHistory(),
        ]);

        // --- Due flashcards ---
        const dueCards =
          fcStats.status === "fulfilled" ? (fcStats.value.due_today ?? 0) : 0;

        // --- Weak topic from AI recommendations focus_areas ---
        let weakTopic: string | null = null;
        if (recs.status === "fulfilled") {
          const focusAreas = recs.value.focus_areas ?? [];
          weakTopic = focusAreas.length > 0 ? focusAreas[0] : null;
        }

        // --- Missed concepts from most recent completed quiz ---
        let missedCount = 0;
        if (quizHistory.status === "fulfilled") {
          const completed = (quizHistory.value as any[]).filter(
            (q) => q.score !== undefined && q.total_questions !== undefined,
          );
          if (completed.length > 0) {
            const latest = completed[0];
            missedCount = Math.max(
              0,
              (latest.total_questions ?? 0) - (latest.score ?? 0),
            );
          }
        }

        const estMin = Math.round(dueCards * 0.5 + 10 + missedCount * 2);

        setStats({
          dueCards,
          weakTopic,
          missedCount,
          estimatedMinutes: Math.max(15, Math.min(60, estMin)),
        });
      } catch (error) {
        console.error("Failed to load session stats:", error);
        // Show a safe zero-state rather than crash
        setStats({ dueCards: 0, weakTopic: null, missedCount: 0, estimatedMinutes: 15 });
      } finally {
        setLoading(false);
      }
    }

    loadSessionStats();
  }, []);

  return (
    <Card className="noise-overlay relative overflow-hidden rounded-3xl border-2 border-primary/20 bg-linear-to-br from-primary/5 via-card to-transparent shadow-xl shadow-primary/5 mb-6">
      <div
        aria-hidden="true"
        className="ambient-orb pointer-events-none absolute inset-0 opacity-[0.45]"
        style={{
          background:
            "radial-gradient(60% 70% at 90% 0%, color-mix(in oklab, var(--learning) 15%, transparent), transparent 60%)",
        }}
      />

      <CardContent className="p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-4 max-w-xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-semibold text-primary">
              <Sparkles className="size-3.5 animate-pulse" />
              RECOMMENDED FOR TODAY
            </div>

            <h2 className="font-serif text-3xl font-bold leading-tight tracking-tight text-foreground md:text-4xl">
              Today's Study Session
            </h2>
            {loading ? (
              <Skeleton className="h-4 w-4/5 rounded-lg" />
            ) : (
              <p className="text-muted-foreground text-sm">
                Your next {stats!.estimatedMinutes}-minute study session is
                ready. Emby has compiled this to optimize your memory retention
                and cover exam weak spots.
              </p>
            )}

            {/* Steps checklist */}
            <div className="grid gap-3 sm:grid-cols-3 pt-2">
              {/* Step 1: Flashcards */}
              <div className="flex items-start gap-2.5 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-violet-500/10 text-violet-500 mt-0.5 text-xs font-bold">
                  1
                </span>
                <div className="leading-tight">
                  <p className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground">
                    Review
                  </p>
                  {loading ? (
                    <Skeleton className="h-4 w-20 mt-1 rounded" />
                  ) : (
                    <p className="text-sm font-semibold text-foreground mt-0.5">
                      {stats!.dueCards > 0
                        ? `${stats!.dueCards} Flashcards`
                        : "No cards due"}
                    </p>
                  )}
                </div>
              </div>

              {/* Step 2: Weak topic practice */}
              <div className="flex items-start gap-2.5 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500 mt-0.5 text-xs font-bold">
                  2
                </span>
                <div className="leading-tight min-w-0">
                  <p className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground">
                    Practice
                  </p>
                  {loading ? (
                    <Skeleton className="h-4 w-24 mt-1 rounded" />
                  ) : (
                    <p
                      className="text-sm font-semibold text-foreground mt-0.5 truncate max-w-[130px]"
                      title={stats!.weakTopic ?? ""}
                    >
                      {stats!.weakTopic ?? "Weak Area MCQs"}
                    </p>
                  )}
                </div>
              </div>

              {/* Step 3: Missed concepts */}
              <div className="flex items-start gap-2.5 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-rose-500/10 text-rose-500 mt-0.5 text-xs font-bold">
                  3
                </span>
                <div className="leading-tight">
                  <p className="text-[10px] uppercase font-semibold tracking-wider text-muted-foreground">
                    Revise
                  </p>
                  {loading ? (
                    <Skeleton className="h-4 w-20 mt-1 rounded" />
                  ) : (
                    <p className="text-sm font-semibold text-foreground mt-0.5">
                      {stats!.missedCount > 0
                        ? `${stats!.missedCount} Missed Concepts`
                        : "All caught up!"}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-col items-center justify-center min-w-[200px] gap-3">
            <motion.div
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              className="w-full"
            >
              <Link href="/session" className="w-full">
                <Button
                  size="lg"
                  className="w-full h-14 rounded-2xl bg-primary text-primary-foreground font-semibold shadow-lg shadow-primary/25 hover:shadow-primary/45 hover:opacity-90 flex items-center justify-center gap-2 text-base"
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="size-5 animate-spin" />
                  ) : (
                    <Play className="size-5 fill-current" />
                  )}
                  {loading ? "Loading..." : "Start Session"}
                </Button>
              </Link>
            </motion.div>
            <p className="text-[11px] text-muted-foreground flex items-center gap-1">
              <Clock className="size-3" /> Guides you step-by-step
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

