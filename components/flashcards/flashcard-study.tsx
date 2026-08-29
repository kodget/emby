"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RotateCcw } from "lucide-react";

import { Axo, AxoError, AxoLoader } from "@/components/brand/axo";
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
    <div className="flex min-h-screen flex-col">
      {/* Top bar */}
      <div className="mx-auto flex w-full max-w-2xl items-center justify-between px-4 pt-5 sm:px-6">
        <button
          id="back-to-flashcards"
          onClick={() => router.push("/flashcards")}
          className="press flex items-center gap-2 text-sm text-muted-foreground"
        >
          <ArrowLeft className="size-4" />
          Back
        </button>
        <span className="text-sm text-muted-foreground tabular">
          {currentIndex + 1} / {cards.length}
        </span>
      </div>

      {/* Progress */}
      <div className="mx-auto mt-3 w-full max-w-2xl px-4 sm:px-6">
        <div
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Review progress"
        >
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center gap-7 px-4 py-8 sm:px-6">
        {isLoading ? (
          <AxoLoader label="Shuffling your deck…" pose="flashcards" />
        ) : error ? (
          <AxoError description={error} onRetry={loadCards} />
        ) : sessionComplete ? (
          <div className="flex flex-col items-center gap-5 text-center">
            <Axo pose="celebrate" size="lg" float />
            <div>
              <h2 className="font-display text-2xl">Session complete</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                You reviewed{" "}
                <span className="font-medium text-foreground tabular">{reviewed}</span>{" "}
                card{reviewed === 1 ? "" : "s"}.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {onComplete ? (
                <button
                  onClick={onComplete}
                  className="press rounded-full bg-primary px-6 py-3 text-sm font-medium text-primary-foreground"
                >
                  Next activity
                </button>
              ) : (
                <button
                  onClick={() => router.push("/flashcards")}
                  className="press rounded-full border border-border bg-card px-6 py-3 text-sm"
                >
                  Back to decks
                </button>
              )}
              <button
                id="restart-session-btn"
                onClick={loadCards}
                className="press flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm"
              >
                <RotateCcw className="size-4" />
                Review again
              </button>
            </div>
          </div>
        ) : cards.length === 0 ? (
          <FlashcardEmptyState mode="due" />
        ) : currentCard ? (
          <>
            <FlashcardCard
              card={currentCard}
              isFlipped={isFlipped}
              onFlip={() => setIsFlipped((f) => !f)}
              className="w-full"
            />

            {!isFlipped ? (
              <button
                id="reveal-answer-btn"
                onClick={() => setIsFlipped(true)}
                className="press rounded-full border border-border bg-card px-10 py-3.5 text-sm font-medium"
              >
                Reveal answer
              </button>
            ) : (
              <div className="flex w-full flex-col items-center gap-3">
                <p className="text-sm text-muted-foreground">How well did you know this?</p>
                <ReviewRatingButtons onRate={handleRate} isLoading={isRating} />
              </div>
            )}

            {/* Keyboard hints are desktop-only affordances. */}
            <p className="hidden text-xs text-muted-foreground/70 sm:block">
              {!isFlipped ? (
                <>
                  Press <Kbd>Space</Kbd> to flip
                </>
              ) : (
                <>
                  Press <Kbd>1</Kbd>–<Kbd>4</Kbd> to rate
                </>
              )}
            </p>
          </>
        ) : null}
      </div>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
      {children}
    </kbd>
  );
}
