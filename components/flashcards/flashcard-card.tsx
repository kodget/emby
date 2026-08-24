"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { Flashcard } from "@/lib/api";

interface FlashcardCardProps {
  card: Flashcard;
  isFlipped?: boolean;
  onFlip?: () => void;
  className?: string;
}

export function FlashcardCard({
  card,
  isFlipped: externalFlipped,
  onFlip,
  className,
}: FlashcardCardProps) {
  const [internalFlipped, setInternalFlipped] = useState(false);
  const flipped = externalFlipped !== undefined ? externalFlipped : internalFlipped;

  const handleFlip = () => {
    if (onFlip) {
      onFlip();
    } else {
      setInternalFlipped((f) => !f);
    }
  };

  return (
    <div
      className={cn("perspective-1000 cursor-pointer select-none", className)}
      onClick={handleFlip}
      role="button"
      tabIndex={0}
      aria-label={flipped ? "Card back — click to flip" : "Card front — click to reveal answer"}
      onKeyDown={(e) => (e.key === " " || e.key === "Enter") && handleFlip()}
    >
      <div
        className={cn(
          "relative w-full transition-transform duration-500 transform-style-3d",
          flipped && "rotate-y-180"
        )}
        style={{
          transformStyle: "preserve-3d",
          transition: "transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
        }}
      >
        {/* FRONT */}
        <div
          className="w-full backface-hidden"
          style={{ backfaceVisibility: "hidden" }}
        >
          <div className="min-h-[260px] rounded-2xl bg-gradient-to-br from-[#1a1a2e] via-[#16213e] to-[#0f3460] border border-white/10 shadow-2xl flex flex-col items-center justify-center p-8 gap-4">
            <span className="text-xs font-semibold tracking-widest text-violet-400 uppercase opacity-70">
              Question
            </span>
            <p className="text-center text-white text-lg font-medium leading-relaxed">
              {card.front}
            </p>
            {card.topic_name && (
              <span className="text-xs text-white/40 mt-2">
                {card.subject_name && `${card.subject_name} · `}
                {card.topic_name}
              </span>
            )}
            <span className="text-xs text-white/30 mt-4 animate-pulse">
              Tap to reveal answer
            </span>
          </div>
        </div>

        {/* BACK */}
        <div
          className="absolute inset-0 w-full backface-hidden"
          style={{
            backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
          }}
        >
          <div className="min-h-[260px] rounded-2xl bg-gradient-to-br from-[#0d2137] via-[#1a3a5c] to-[#0a1628] border border-violet-500/30 shadow-2xl shadow-violet-900/20 flex flex-col items-start justify-start p-8 gap-4">
            <span className="text-xs font-semibold tracking-widest text-emerald-400 uppercase opacity-70">
              Answer
            </span>
            <p className="text-white text-lg font-medium leading-relaxed">
              {card.back}
            </p>
            {card.explanation && (
              <div className="mt-2 pt-4 border-t border-white/10 w-full">
                <p className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-1">
                  Explanation
                </p>
                <p className="text-white/70 text-sm leading-relaxed">
                  {card.explanation}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
