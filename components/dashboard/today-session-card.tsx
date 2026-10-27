"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, BookOpen, Clock, History, Layers, ListTodo, Play, Sparkles, Target } from "lucide-react";
import { aiApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

type SessionStats = { dueCards: number; weakTopic: string; missedCount: number; slideToRead: string; staleCount: number; tasksCount: number; minutes: number; insights?: string };

export function TodaySessionCard() {
  const [stats, setStats] = useState<SessionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(false);
    aiApi.getRecommendations().then(recs => {
      if (!active) return;
      const due = recs.flashcards_due ?? 0, missed = recs.missed_count ?? 0, tasks = recs.study_plan_items?.length ?? 0;
      setStats({ dueCards: due, weakTopic: recs.practice_topic || "Choose a topic", missedCount: missed, slideToRead: recs.slide_to_read?.title || "Open your class notes", staleCount: recs.stale_slides?.length ?? 0, tasksCount: tasks, minutes: Math.max(15, Math.min(120, Math.round(due * .5 + 15 + missed * 2 + tasks * 10))), insights: recs.insights });
    }).catch(() => { if (active) setError(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [retry]);
  const steps = [
    { label: "Read", value: stats?.slideToRead, href: "/courses", icon: BookOpen },
    { label: "Recall", value: stats ? stats.dueCards ? `${stats.dueCards} cards due` : "No cards due" : "", href: "/flashcards", icon: Layers },
    { label: "Practise", value: stats?.weakTopic, href: "/quiz", icon: Target },
    { label: "Revisit", value: stats ? stats.staleCount ? `${stats.staleCount} slides to revisit` : "Explore your library" : "", href: "/courses", icon: History },
    { label: "Plan", value: stats ? stats.tasksCount ? `${stats.tasksCount} activities` : "Make room for study" : "", href: "/study-plan", icon: ListTodo },
  ];
  return <section className="overflow-hidden rounded-[24px] border border-[#b7c59b]/60 bg-[#edf1e2] p-5 sm:p-7" aria-labelledby="today-session-heading">
    <div className="flex flex-wrap items-center justify-between gap-5">
      <div><p className="studio-eyebrow flex items-center gap-2 text-[#52653b]"><Sparkles className="size-3.5" />Your next small steps</p><h2 id="today-session-heading" className="mt-3 font-editorial text-3xl font-medium tracking-tight sm:text-4xl">A little progress, today.</h2><p className="mt-2 text-sm leading-6 text-[#58624c]">A guided path through reading, recall and practice.</p></div>
      {!loading && !error && <div className="space-y-2"><Button asChild className="min-h-12 bg-[#34422b] px-5 text-white hover:bg-[#475c37]"><Link href="/session"><Play className="size-4" />Start Session</Link></Button><p className="flex items-center gap-1.5 text-xs text-[#58624c]"><Clock className="size-3" />About {stats?.minutes} minutes</p></div>}
    </div>
    {error ? <div role="alert" className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#b7c59b] bg-white/60 p-4 text-sm"><p>Your recommendations couldn’t load. Your study tools are still available below.</p><Button variant="outline" onClick={() => setRetry(n => n+1)}>Try again</Button></div> : <ol className="mt-6 grid gap-2 sm:grid-cols-3 xl:grid-cols-5" aria-busy={loading}>
      {steps.map(({label,value,href,icon:Icon},i) => <li key={label}><Link href={href} className="group flex h-full items-center gap-3 rounded-xl border border-[#8c9a7333] bg-white/65 p-4 transition-colors hover:bg-white sm:block"><span className="flex items-center justify-between gap-3"><Icon className="size-4 text-[#52653b]" /><span className="hidden font-mono text-[10px] text-[#78886b] sm:block">0{i+1}</span></span><span className="min-w-0 flex-1"><span className="block text-xs font-semibold sm:mt-4">{label}</span>{loading ? <span className="mt-2 block h-3 w-20 animate-pulse rounded bg-[#cbd4bc]" /> : <span className="mt-1 block text-xs leading-5 text-[#58624c]">{value}</span>}</span><ArrowUpRight className="size-4 text-[#78886b] sm:hidden" /></Link></li>)}
    </ol>}
    {!loading && !error && stats?.insights && <p className="mt-5 border-t border-[#8c9a7333] pt-4 text-xs leading-6 text-[#52613f]"><span className="font-semibold">A note from your AI tutor: </span>{stats.insights}</p>}
  </section>;
}


