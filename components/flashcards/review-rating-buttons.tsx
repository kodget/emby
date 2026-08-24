"use client";

import { Button } from "@/components/ui/button";
import type { FlashcardRating } from "@/lib/api";

interface ReviewRatingButtonsProps {
  onRate: (rating: FlashcardRating) => void;
  isLoading?: boolean;
}

const ratings: { value: FlashcardRating; label: string; hint: string; shortcut: string; color: string }[] = [
  { value: "again", label: "Again", hint: "<10 min", shortcut: "1", color: "from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 border-red-500/40" },
  { value: "hard",  label: "Hard",  hint: "1 day",  shortcut: "2", color: "from-orange-600 to-orange-700 hover:from-orange-500 hover:to-orange-600 border-orange-500/40" },
  { value: "good",  label: "Good",  hint: "3+ days", shortcut: "3", color: "from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 border-emerald-500/40" },
  { value: "easy",  label: "Easy",  hint: "7+ days", shortcut: "4", color: "from-violet-600 to-violet-700 hover:from-violet-500 hover:to-violet-600 border-violet-500/40" },
];

export function ReviewRatingButtons({ onRate, isLoading }: ReviewRatingButtonsProps) {
  return (
    <div className="flex gap-3 justify-center flex-wrap" role="group" aria-label="Rate this flashcard">
      {ratings.map((r) => (
        <button
          key={r.value}
          id={`rate-${r.value}`}
          disabled={isLoading}
          onClick={() => onRate(r.value)}
          className={`relative group flex flex-col items-center gap-1 px-6 py-3 rounded-xl text-white font-semibold text-sm
            bg-gradient-to-b ${r.color} border transition-all duration-200
            shadow-lg active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed
            min-w-[80px]`}
        >
          <span>{r.label}</span>
          <span className="text-[10px] font-normal opacity-70">{r.hint}</span>
          <span className="absolute -top-2 -right-2 w-5 h-5 bg-white/20 backdrop-blur rounded-full text-[9px] flex items-center justify-center font-bold opacity-0 group-hover:opacity-100 transition-opacity">
            {r.shortcut}
          </span>
        </button>
      ))}
    </div>
  );
}
