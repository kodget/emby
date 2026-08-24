"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RotateCcw, PartyPopper } from "lucide-react";
import { flashcardApi, type Flashcard, type FlashcardRating } from "@/lib/api";
import { FlashcardCard } from "./flashcard-card";
import { ReviewRatingButtons } from "./review-rating-buttons";
import { FlashcardEmptyState } from "./flashcard-empty-state";

interface FlashcardStudyProps {
  subjectId?: string;
  blockId?: string;
  subBlockId?: number;
  topicId?: number;
  onComplete?: () => void;
}

export function FlashcardStudy({ subjectId, blockId, subBlockId, topicId, onComplete }: FlashcardStudyProps) {
  const router = useRouter();

  const [cards, setCards] = useState<Flashcard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isRating, setIsRating] = useState(false);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const [error, setError] = useState("");

  const loadCards = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await flashcardApi.getDue({
        subject: subjectId,
        block: blockId,
        sub_block: subBlockId,
        topic: topicId,
      });
      setCards(data.results);
      setCurrentIndex(0);
      setIsFlipped(false);
      setSessionComplete(false);
      setReviewed(0);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to load cards.");
    } finally {
      setIsLoading(false);
    }
  }, [subjectId, blockId, subBlockId, topicId]);

  useEffect(() => {
    loadCards();
  }, [loadCards]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        setIsFlipped((f) => !f);
      }
      if (isFlipped && !isRating) {
        if (e.key === "1") handleRate("again");
        if (e.key === "2") handleRate("hard");
        if (e.key === "3") handleRate("good");
        if (e.key === "4") handleRate("easy");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFlipped, isRating, currentIndex, cards]);

  const handleRate = async (rating: FlashcardRating) => {
    if (isRating || cards.length === 0) return;
    const card = cards[currentIndex];
    setIsRating(true);
    try {
      await flashcardApi.review(card.id, rating);
      setReviewed((r) => r + 1);
      const nextIndex = currentIndex + 1;
      if (nextIndex >= cards.length) {
        setSessionComplete(true);
      } else {
        setCurrentIndex(nextIndex);
        setIsFlipped(false);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to submit rating.");
    } finally {
      setIsRating(false);
    }
  };

  const currentCard = cards[currentIndex];
  const progress = cards.length > 0 ? Math.round((currentIndex / cards.length) * 100) : 0;

  return (
    <div className="min-h-screen bg-[#080d1a] flex flex-col">
      {/* Top bar */}
      <div className="px-6 pt-6 flex items-center justify-between max-w-2xl mx-auto w-full">
        <button
          id="back-to-flashcards"
          onClick={() => router.push("/flashcards")}
          className="flex items-center gap-2 text-white/50 hover:text-white transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-white/40">
            {currentIndex + 1} / {cards.length}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="px-6 max-w-2xl mx-auto w-full mt-4">
        <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-violet-400 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-8 max-w-2xl mx-auto w-full gap-8">
        {isLoading ? (
          <div className="w-10 h-10 rounded-full border-2 border-violet-500 border-t-transparent animate-spin" />
        ) : error ? (
          <div className="text-center">
            <p className="text-red-400 mb-4">{error}</p>
            <button onClick={loadCards} className="text-sm text-white/60 hover:text-white underline">
              Retry
            </button>
          </div>
        ) : sessionComplete ? (
          /* Session complete state */
          <div className="flex flex-col items-center gap-6 text-center">
            <div className="w-24 h-24 rounded-full bg-gradient-to-br from-emerald-500/30 to-emerald-400/10 border border-emerald-500/30 flex items-center justify-center">
              <PartyPopper className="h-10 w-10 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white mb-2">Session Complete!</h2>
              <p className="text-white/50">
                You reviewed <span className="text-violet-400 font-semibold">{reviewed}</span> cards.
              </p>
            </div>
            <div className="flex gap-3">
              {onComplete ? (
                <button
                  onClick={onComplete}
                  className="px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white text-sm font-medium transition-all shadow-lg"
                >
                  Next Activity
                </button>
              ) : (
                <button
                  onClick={() => router.push("/flashcards")}
                  className="px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white text-sm font-medium transition-colors"
                >
                  Back to Decks
                </button>
              )}
              <button
                id="restart-session-btn"
                onClick={loadCards}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-violet-600 to-violet-500 hover:from-violet-500 hover:to-violet-400 text-white text-sm font-medium transition-all shadow-lg shadow-violet-900/30"
              >
                <RotateCcw className="w-4 h-4" />
                Review Again
              </button>
            </div>
          </div>
        ) : cards.length === 0 ? (
          <FlashcardEmptyState mode="due" />
        ) : currentCard ? (
          <>
            {/* Card */}
            <FlashcardCard
              card={currentCard}
              isFlipped={isFlipped}
              onFlip={() => setIsFlipped((f) => !f)}
              className="w-full"
            />

            {/* Action area */}
            {!isFlipped ? (
              <button
                id="reveal-answer-btn"
                onClick={() => setIsFlipped(true)}
                className="px-10 py-3.5 rounded-2xl bg-white/10 hover:bg-white/20 text-white font-semibold transition-all border border-white/10"
              >
                Reveal Answer
              </button>
            ) : (
              <div className="flex flex-col items-center gap-4 w-full">
                <p className="text-white/40 text-sm">How well did you know this?</p>
                <ReviewRatingButtons onRate={handleRate} isLoading={isRating} />
              </div>
            )}

            {/* Hint */}
            {!isFlipped && (
              <p className="text-white/25 text-xs">
                Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono text-[10px]">Space</kbd> to flip
              </p>
            )}
            {isFlipped && (
              <p className="text-white/25 text-xs">
                Press <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono text-[10px]">1</kbd>–
                <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono text-[10px]">4</kbd> to rate
              </p>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
