"use client";

/**
 * ResourcePanel — YouTube, Textbooks, MCQs
 *
 * ARCHITECTURE RULES:
 * 1. Resources are fetched ONCE per slide and cached in global store
 * 2. Auto-generated when slide loads (useEffect on slideIndex)
 * 3. MCQ answers tracked per slide+question in global store
 * 4. YouTube links built from query string — no API key needed
 */

import { useEffect, useState } from "react";
import { BookOpenText, Loader2, Play, RefreshCw } from "lucide-react";
import { aiApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  useSlideStore,
  type ResourceObject,
  type YouTubeResource,
  type TextbookResource,
  type MCQResource,
} from "@/store/slide-store";
import { imageUrlToBase64 } from "@/lib/slide-image-utils";

// ─────────────────────────────────────────────────────────────────────────────
// ResourcePanel
// ─────────────────────────────────────────────────────────────────────────────

export function ResourcePanel({
  slideId,
  slideIndex,
  activeTab,
  onTabChange,
  selection,
}: {
  slideId: string;
  slideIndex: number;
  activeTab: "textbook" | "videos" | "quiz";
  onTabChange?: (tab: string) => void;
  selection: string | null;
}) {
  const { slides, getResources, setResources, setLoading, isLoading } =
    useSlideStore();

  const [localLoading, setLocalLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Auto-generate when slide changes ───────────────────────────────────
  useEffect(() => {
    const cached = getResources(slideIndex);
    if (cached) return; // Already have data — don't re-fetch

    generateResources();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slideIndex]);

  const generateResources = async () => {
    setLocalLoading(true);
    setError(null);

    try {
      const currentSlide = slides[slideIndex];

      // Convert image to base64 so Gemini can see the slide
      // slides[slideIndex] may not be populated yet if slideContent is still loading
      const slideImageBase64 = currentSlide?.imageUrl
        ? await imageUrlToBase64(currentSlide.imageUrl).catch(() => undefined)
        : undefined;

      const data = await aiApi.generateResources({
        slide_id: slideId,
        slide_image_base64: slideImageBase64,
      });

      // Cache in global store keyed by slideIndex
      setResources(slideIndex, {
        youtube: data.youtube ?? [],
        textbooks: data.textbooks ?? [],
        mcqs: data.mcqs ?? [],
      });
    } catch (err: any) {
      console.error("Resource generation failed:", err);
      setError("Failed to generate resources. Tap retry to try again.");
    } finally {
      setLocalLoading(false);
    }
  };

  const resources = getResources(slideIndex);

  if (localLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <Loader2 className="mx-auto size-8 animate-spin text-primary" />
          <p className="mt-4 text-sm text-muted-foreground">
            Generating resources for this slide…
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={generateResources}
            className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-destructive px-4 py-1.5 text-xs text-white hover:opacity-90"
          >
            <RefreshCw className="size-3.5" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!resources) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-border bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            No resources yet for this slide.
          </p>
          <button
            onClick={generateResources}
            className="mt-3 text-xs text-primary hover:underline"
          >
            Generate now
          </button>
        </div>
      </div>
    );
  }

  if (activeTab === "textbook") {
    return <TextbookTab books={resources.textbooks} />;
  }
  if (activeTab === "videos") {
    return <VideosTab videos={resources.youtube} selection={selection} />;
  }
  if (activeTab === "quiz") {
    return (
      <MCQTab
        mcqs={resources.mcqs}
        slideIndex={slideIndex}
        onRegenerate={generateResources}
      />
    );
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Textbook Tab
// ─────────────────────────────────────────────────────────────────────────────

function TextbookTab({ books }: { books: TextbookResource[] }) {
  if (!books.length) {
    return (
      <div className="p-5 text-center text-sm text-muted-foreground">
        No textbook suggestions generated.
      </div>
    );
  }

  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
        AI-Recommended Textbooks
      </p>
      <h3 className="mt-1 font-serif text-xl">Based on this slide</h3>

      <div className="mt-4 space-y-3">
        {books.map((book, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-2xl border border-border bg-background p-3"
          >
            <div className="flex size-14 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <BookOpenText className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-serif text-base leading-tight">{book.title}</p>
              {book.author && (
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  by {book.author}
                </p>
              )}
              <p className="mt-1 text-[11px] font-medium text-primary">
                {book.chapter}
              </p>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                {book.reason}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Videos Tab
// ─────────────────────────────────────────────────────────────────────────────

function VideosTab({
  videos,
  selection,
}: {
  videos: YouTubeResource[];
  selection: string | null;
}) {
  if (!videos.length) {
    return (
      <div className="p-5 text-center text-sm text-muted-foreground">
        No video suggestions generated.
      </div>
    );
  }

  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-accent">
        AI-Curated Videos
      </p>
      <h3 className="mt-1 font-serif text-xl">
        {selection ? "Based on your highlight" : "For this slide"}
      </h3>
      {selection && (
        <p className="mt-1 line-clamp-2 text-[12px] italic text-muted-foreground">
          &ldquo;{selection}&rdquo;
        </p>
      )}

      <ul className="mt-4 space-y-3">
        {videos.map((v, idx) => {
          // Build YouTube search URL from query — no API key needed
          const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(v.query)}`;

          return (
            <li key={idx}>
              <a
                href={searchUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex gap-3 rounded-2xl border border-border bg-background p-3 transition-colors hover:border-primary hover:bg-primary/5"
              >
                <div className="relative flex size-20 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <Play className="size-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-sm font-medium">{v.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed line-clamp-2">
                    {v.reason}
                  </p>
                  <p className="mt-1 text-[10px] text-primary">
                    Search on YouTube →
                  </p>
                </div>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MCQ Tab
// ─────────────────────────────────────────────────────────────────────────────

function MCQTab({
  mcqs,
  slideIndex,
  onRegenerate,
}: {
  mcqs: MCQResource[];
  slideIndex: number;
  onRegenerate: () => void;
}) {
  const { getMCQAnswer, setMCQAnswer } = useSlideStore();
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [showExplanation, setShowExplanation] = useState<
    Record<number, boolean>
  >({});

  if (!mcqs.length) {
    return (
      <div className="p-5 text-center text-sm text-muted-foreground">
        No quiz questions generated.
        <button
          onClick={onRegenerate}
          className="mt-3 block w-full text-xs text-primary hover:underline"
        >
          Generate questions
        </button>
      </div>
    );
  }

  const currentMCQ = mcqs[currentQuestionIndex];
  if (!currentMCQ) return null;

  const savedAnswer = getMCQAnswer(slideIndex, currentQuestionIndex);
  const hasAnswered = savedAnswer !== undefined;
  const totalAnswered = mcqs.filter(
    (_, i) => getMCQAnswer(slideIndex, i) !== undefined,
  ).length;
  const totalCorrect = mcqs.filter((q, i) => {
    const a = getMCQAnswer(slideIndex, i);
    return a !== undefined && a === q.correct;
  }).length;

  const handleAnswer = (optionIdx: number) => {
    if (hasAnswered) return;
    setMCQAnswer(slideIndex, currentQuestionIndex, optionIdx);
    setShowExplanation((p) => ({ ...p, [currentQuestionIndex]: true }));
  };

  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
        AI-Generated from this slide
      </p>
      <h3 className="mt-1 font-serif text-xl">
        {mcqs.length} MCQs to test yourself
      </h3>

      {/* Progress bar */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Question {currentQuestionIndex + 1} of {mcqs.length}
        </span>
        {totalAnswered > 0 && (
          <span className="text-primary font-medium">
            Score: {totalCorrect}/{totalAnswered}
          </span>
        )}
      </div>
      <div className="mt-2 w-full rounded-full bg-muted h-1">
        <div
          className="bg-primary h-1 rounded-full transition-all duration-300"
          style={{ width: `${(totalAnswered / mcqs.length) * 100}%` }}
        />
      </div>

      {/* Question */}
      <div className="mt-4 rounded-2xl border border-border bg-background p-4">
        <p className="font-medium text-sm">
          {currentQuestionIndex + 1}. {currentMCQ.question}
        </p>

        <div className="mt-3 space-y-2">
          {currentMCQ.options.map((option, idx) => {
            const isSelected = savedAnswer === idx;
            const isCorrect = idx === currentMCQ.correct;
            const showResult = hasAnswered;

            return (
              <button
                key={idx}
                onClick={() => handleAnswer(idx)}
                disabled={hasAnswered}
                className={cn(
                  "w-full text-left flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                  showResult && isCorrect
                    ? "border-green-500 bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200"
                    : showResult && isSelected && !isCorrect
                      ? "border-red-500 bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
                      : isSelected
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-border bg-card hover:border-primary hover:bg-primary/5",
                  hasAnswered && "cursor-not-allowed",
                )}
              >
                <span className="size-5 shrink-0 rounded-full border border-current text-[10px] leading-[1.2rem] text-center font-semibold">
                  {String.fromCharCode(65 + idx)}
                </span>
                {option}
              </button>
            );
          })}
        </div>

        {showExplanation[currentQuestionIndex] && currentMCQ.explanation && (
          <div className="mt-3 p-3 bg-muted rounded-lg">
            <p className="text-xs text-muted-foreground">
              <strong>Explanation:</strong> {currentMCQ.explanation}
            </p>
          </div>
        )}
      </div>

      {/* Question navigation */}
      <div className="mt-4 flex items-center justify-between">
        <button
          onClick={() => setCurrentQuestionIndex((p) => Math.max(0, p - 1))}
          disabled={currentQuestionIndex === 0}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
        >
          ← Prev
        </button>

        {/* Dot indicators */}
        <div className="flex gap-1 flex-wrap justify-center max-w-[200px]">
          {mcqs.slice(0, 20).map((_, idx) => {
            const ans = getMCQAnswer(slideIndex, idx);
            const answered = ans !== undefined;
            return (
              <button
                key={idx}
                onClick={() => setCurrentQuestionIndex(idx)}
                className={cn(
                  "size-6 rounded text-[10px] font-medium transition-colors",
                  idx === currentQuestionIndex
                    ? "bg-primary text-primary-foreground"
                    : answered
                      ? "bg-green-500 text-white"
                      : "bg-muted text-muted-foreground hover:bg-primary/20",
                )}
              >
                {idx + 1}
              </button>
            );
          })}
        </div>

        <button
          onClick={() =>
            setCurrentQuestionIndex((p) => Math.min(mcqs.length - 1, p + 1))
          }
          disabled={currentQuestionIndex === mcqs.length - 1}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
        >
          Next →
        </button>
      </div>

      {/* Regenerate when all done */}
      {totalAnswered === mcqs.length && (
        <button
          onClick={onRegenerate}
          className="mt-4 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full border border-border bg-card text-sm font-medium hover:bg-muted"
        >
          <RefreshCw className="size-4" />
          Generate new questions
        </button>
      )}
    </div>
  );
}
