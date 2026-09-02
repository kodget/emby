"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { BrainCircuit, Play, Clock, Loader2, Sparkles, Target, BookOpen, Layers, History, ListTodo } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { aiApi } from "@/lib/api";

interface SessionStats {
  dueCards: number;
  weakTopic: string;
  missedCount: number;
  slideToRead: string;
  staleCount: number;
  tasksCount: number;
  estimatedMinutes: number;
  insights?: string;
}

export function TodaySessionCard() {
  const [stats, setStats] = useState<SessionStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadSessionStats() {
      try {
        const recs = await aiApi.getRecommendations();
        
        const dueCards = recs.flashcards_due ?? 0;
        const weakTopic = recs.practice_topic ?? "General Review";
        const missedCount = recs.missed_count ?? 0;
        const slideToRead = recs.slide_to_read?.title ?? "Review your notes";
        const staleCount = recs.stale_slides?.length ?? 0;
        const tasksCount = recs.study_plan_items?.length ?? 0;
        
        const estMin = Math.round(dueCards * 0.5 + 15 + missedCount * 2 + tasksCount * 10);

        setStats({
          dueCards,
          weakTopic,
          missedCount,
          slideToRead,
          staleCount,
          tasksCount,
          estimatedMinutes: Math.max(15, Math.min(120, estMin)),
          insights: recs.insights,
        });
      } catch (error) {
        console.error("Failed to load session stats:", error);
        setStats({ dueCards: 0, weakTopic: "Error loading", missedCount: 0, slideToRead: "Error loading", staleCount: 0, tasksCount: 0, estimatedMinutes: 15 });
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
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-8">
          <div className="space-y-4 max-w-2xl flex-1">
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

            {/* 5-Steps checklist */}
            <div className="grid gap-3 grid-cols-2 md:grid-cols-5 pt-2">
              
              {/* Step 1: Read */}
              <div className="flex flex-col gap-2 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs relative overflow-hidden group hover:border-blue-500/30 transition-colors">
                <div className="flex items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-blue-500/10 text-blue-500 text-[10px] font-bold">1</span>
                  <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Read</p>
                </div>
                <BookOpen className="absolute -right-3 -bottom-3 size-12 text-blue-500/5 group-hover:text-blue-500/10 transition-colors" />
                {loading ? (
                  <Skeleton className="h-4 w-full mt-1 rounded" />
                ) : (
                  <p className="text-sm font-semibold text-foreground truncate" title={stats!.slideToRead}>
                    {stats!.slideToRead}
                  </p>
                )}
              </div>

              {/* Step 2: Review */}
              <div className="flex flex-col gap-2 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs relative overflow-hidden group hover:border-violet-500/30 transition-colors">
                <div className="flex items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-violet-500/10 text-violet-500 text-[10px] font-bold">2</span>
                  <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Review</p>
                </div>
                <Layers className="absolute -right-3 -bottom-3 size-12 text-violet-500/5 group-hover:text-violet-500/10 transition-colors" />
                {loading ? (
                  <Skeleton className="h-4 w-full mt-1 rounded" />
                ) : (
                  <p className="text-sm font-semibold text-foreground truncate">
                    {stats!.dueCards > 0 ? `${stats!.dueCards} Flashcards` : "Caught up"}
                  </p>
                )}
              </div>

              {/* Step 3: Practice */}
              <div className="flex flex-col gap-2 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs relative overflow-hidden group hover:border-emerald-500/30 transition-colors">
                <div className="flex items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500 text-[10px] font-bold">3</span>
                  <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Practice</p>
                </div>
                <Target className="absolute -right-3 -bottom-3 size-12 text-emerald-500/5 group-hover:text-emerald-500/10 transition-colors" />
                {loading ? (
                  <Skeleton className="h-4 w-full mt-1 rounded" />
                ) : (
                  <p className="text-sm font-semibold text-foreground truncate" title={stats!.weakTopic}>
                    {stats!.weakTopic}
                  </p>
                )}
              </div>

              {/* Step 4: Revise */}
              <div className="flex flex-col gap-2 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs relative overflow-hidden group hover:border-rose-500/30 transition-colors">
                <div className="flex items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-rose-500/10 text-rose-500 text-[10px] font-bold">4</span>
                  <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Revise</p>
                </div>
                <History className="absolute -right-3 -bottom-3 size-12 text-rose-500/5 group-hover:text-rose-500/10 transition-colors" />
                {loading ? (
                  <Skeleton className="h-4 w-full mt-1 rounded" />
                ) : (
                  <p className="text-sm font-semibold text-foreground truncate">
                    {stats!.staleCount > 0 ? `${stats!.staleCount} Old Slides` : "None"}
                  </p>
                )}
              </div>

              {/* Step 5: Study Plan */}
              <div className="flex flex-col gap-2 bg-background/50 border border-border/60 rounded-2xl p-3.5 backdrop-blur-xs relative overflow-hidden group hover:border-amber-500/30 transition-colors md:col-span-1 col-span-2">
                <div className="flex items-center gap-2">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-500 text-[10px] font-bold">5</span>
                  <p className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Planner</p>
                </div>
                <ListTodo className="absolute -right-3 -bottom-3 size-12 text-amber-500/5 group-hover:text-amber-500/10 transition-colors" />
                {loading ? (
                  <Skeleton className="h-4 w-full mt-1 rounded" />
                ) : (
                  <p className="text-sm font-semibold text-foreground truncate">
                    {stats!.tasksCount > 0 ? `${stats!.tasksCount} Tasks` : "Free day"}
                  </p>
                )}
              </div>
            </div>

            {/* AI Insights */}
            {!loading && stats?.insights && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="pt-2">
                <div className="p-3.5 rounded-xl bg-indigo-50/60 border border-indigo-100/60 flex items-start gap-3">
                  <BrainCircuit className="size-5 text-indigo-500 shrink-0 mt-0.5" />
                  <p className="text-xs text-indigo-900/80 leading-relaxed">
                    <span className="font-semibold text-indigo-700">AI Insight: </span>
                    {stats.insights}
                  </p>
                </div>
              </motion.div>
            )}
          </div>

          <div className="flex flex-col items-center justify-center min-w-[200px] gap-3 shrink-0">
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
              <Clock className="size-3" /> 5-step guided flow
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

