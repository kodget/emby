"use client";

import { Brain, CalendarCheck, TrendingUp, RefreshCw } from "lucide-react";
import type { FlashcardStats } from "@/lib/api";

interface FlashcardStatsBarProps {
  stats: FlashcardStats;
}

export function FlashcardStatsBar({ stats }: FlashcardStatsBarProps) {
  const items = [
    {
      icon: CalendarCheck,
      label: "Due Today",
      value: stats.due_today,
      color: "text-violet-400",
      bg: "from-violet-900/30 to-violet-800/10 border-violet-500/20",
    },
    {
      icon: Brain,
      label: "Total Cards",
      value: stats.total_cards,
      color: "text-cyan-400",
      bg: "from-cyan-900/30 to-cyan-800/10 border-cyan-500/20",
    },
    {
      icon: TrendingUp,
      label: "Retention Rate",
      value: `${stats.retention_rate}%`,
      color: "text-emerald-400",
      bg: "from-emerald-900/30 to-emerald-800/10 border-emerald-500/20",
    },
    {
      icon: RefreshCw,
      label: "Total Reviews",
      value: stats.total_reviews,
      color: "text-amber-400",
      bg: "from-amber-900/30 to-amber-800/10 border-amber-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.label}
            className={`rounded-2xl border bg-gradient-to-br ${item.bg} p-5 flex flex-col gap-2`}
          >
            <div className="flex items-center gap-2">
              <Icon className={`w-4 h-4 ${item.color}`} />
              <span className="text-xs text-white/50 font-medium">{item.label}</span>
            </div>
            <span className={`text-2xl font-bold ${item.color}`}>{item.value}</span>
          </div>
        );
      })}
    </div>
  );
}
