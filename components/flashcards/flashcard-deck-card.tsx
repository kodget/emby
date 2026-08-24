"use client";

import Link from "next/link";
import { Layers, ChevronRight } from "lucide-react";
import type { FlashcardDeckStat } from "@/lib/api";

interface FlashcardDeckCardProps {
  deck: FlashcardDeckStat;
}

export function FlashcardDeckCard({ deck }: FlashcardDeckCardProps) {
  const percentage = deck.total_cards > 0 ? Math.round((deck.due_today / deck.total_cards) * 100) : 0;

  return (
    <Link
      href={`/flashcards/study?subject=${deck.subject_id}`}
      id={`deck-${deck.subject_id}`}
      className="group relative flex flex-col gap-4 p-5 rounded-2xl border border-white/10 bg-gradient-to-br from-white/5 to-white/[0.02] hover:border-violet-500/40 hover:bg-white/10 transition-all duration-300"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/30 to-violet-400/10 border border-violet-500/20 flex items-center justify-center">
            <Layers className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white text-sm leading-tight">{deck.subject_name}</h3>
            <p className="text-xs text-white/40">{deck.total_cards} cards</p>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-white/30 group-hover:text-violet-400 transition-colors mt-1" />
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-white/40 mb-1.5">
          <span>{deck.due_today} due today</span>
          <span>{percentage}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-violet-400 transition-all duration-500"
            style={{ width: `${Math.min(percentage, 100)}%` }}
          />
        </div>
      </div>

      {deck.due_today > 0 && (
        <div className="absolute top-3 right-3">
          <span className="bg-violet-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full">
            {deck.due_today}
          </span>
        </div>
      )}
    </Link>
  );
}
