"use client";

import { useEffect, useState } from "react";
import { BookOpenText, Play, Highlighter } from "lucide-react";
import { aiApi } from "@/lib/api";

// Textbook Panel with AI Integration
export function TextbookPanel({ slideId }: { slideId: string }) {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSuggestions() {
      try {
        setLoading(true);
        setError(null);
        const data = await aiApi.getTextbookSuggestions(slideId);
        setSuggestions(data.suggestions || []);
      } catch (err) {
        console.error("Error fetching textbook suggestions:", err);
        setError("Failed to load textbook suggestions");
      } finally {
        setLoading(false);
      }
    }

    fetchSuggestions();
  }, [slideId]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-sm text-muted-foreground">
            Loading textbook suggestions...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Try again
          </button>
        </div>
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
        {suggestions.map((suggestion, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-2xl border border-border bg-background p-3"
          >
            <div className="flex size-14 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <BookOpenText className="size-5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-serif text-base leading-tight">
                {suggestion.textbook}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                {suggestion.chapter}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                {suggestion.relevance}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Videos Panel with AI Integration
export function VideosPanel({
  slideId,
  selection,
}: {
  slideId: string;
  selection: string | null;
}) {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchSuggestions() {
      try {
        setLoading(true);
        setError(null);
        const data = await aiApi.getVideoSuggestions(slideId);
        setSuggestions(data.suggestions || []);
      } catch (err) {
        console.error("Error fetching video suggestions:", err);
        setError("Failed to load video suggestions");
      } finally {
        setLoading(false);
      }
    }

    fetchSuggestions();
  }, [slideId]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-sm text-muted-foreground">
            Finding best videos...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Try again
          </button>
        </div>
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
          "{selection}"
        </p>
      )}

      <ul className="mt-4 space-y-3">
        {suggestions.map((v, idx) => (
          <li key={idx}>
            <div className="flex w-full gap-3 rounded-2xl border border-border bg-background p-3">
              <div className="relative flex size-20 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <Play className="size-5" aria-hidden="true" />
                {v.duration && (
                  <span className="absolute bottom-1 right-1 rounded bg-foreground/80 px-1 py-0.5 text-[10px] font-medium text-background">
                    {v.duration}
                  </span>
                )}
              </div>
              <div className="min-w-0">
                <p className="line-clamp-2 text-sm font-medium">{v.title}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {v.channel}
                </p>
                {v.description && (
                  <p className="mt-1 text-[10px] text-muted-foreground line-clamp-2">
                    {v.description}
                  </p>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Quiz Panel with AI Integration
export function QuizPanel({ slideId }: { slideId: string }) {
  const [mcqs, setMcqs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<
    Record<number, string>
  >({});
  const [showResults, setShowResults] = useState(false);

  useEffect(() => {
    async function fetchMCQs() {
      try {
        setLoading(true);
        setError(null);
        const data = await aiApi.generateMCQs(slideId);
        setMcqs(data.mcqs || []);
      } catch (err) {
        console.error("Error generating MCQs:", err);
        setError("Failed to generate quiz questions");
      } finally {
        setLoading(false);
      }
    }

    fetchMCQs();
  }, [slideId]);

  const handleAnswerSelect = (questionIdx: number, answer: string) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionIdx]: answer,
    }));
  };

  const handleSubmit = () => {
    setShowResults(true);
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-primary border-r-transparent"></div>
          <p className="mt-4 text-sm text-muted-foreground">
            Generating quiz questions...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-destructive/50 bg-destructive/10 p-4 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 text-xs text-muted-foreground hover:text-foreground"
          >
            Try again
          </button>
        </div>
      </div>
    );
  }

  const score = showResults
    ? Object.entries(selectedAnswers).filter(
        ([idx, answer]) => answer === mcqs[parseInt(idx)]?.correct_answer,
      ).length
    : 0;

  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
        AI-Generated from this slide
      </p>
      <h3 className="mt-1 font-serif text-xl">20 MCQs to test yourself</h3>

      {showResults && (
        <div className="mt-3 rounded-2xl border border-primary/50 bg-primary/10 p-3 text-center">
          <p className="text-sm font-medium">
            Score: {score} / {mcqs.length} (
            {Math.round((score / mcqs.length) * 100)}%)
          </p>
        </div>
      )}

      <div className="mt-4 space-y-4 text-sm max-h-[600px] overflow-y-auto">
        {mcqs.slice(0, 5).map((mcq, idx) => (
          <div
            key={idx}
            className="rounded-2xl border border-border bg-background p-4"
          >
            <p className="font-medium">
              {idx + 1}. {mcq.question}
            </p>
            <ul className="mt-2 space-y-1.5 text-muted-foreground">
              {Object.entries(mcq.options).map(
                ([key, value]: [string, any]) => {
                  const isSelected = selectedAnswers[idx] === key;
                  const isCorrect = key === mcq.correct_answer;
                  const showCorrect = showResults && isCorrect;
                  const showWrong = showResults && isSelected && !isCorrect;

                  return (
                    <li
                      key={key}
                      onClick={() =>
                        !showResults && handleAnswerSelect(idx, key)
                      }
                      className={`flex items-center gap-2 rounded-lg border px-3 py-2 cursor-pointer ${
                        showCorrect
                          ? "border-green-500 bg-green-50"
                          : showWrong
                            ? "border-red-500 bg-red-50"
                            : isSelected
                              ? "border-primary bg-primary/5"
                              : "border-border bg-card hover:border-primary"
                      }`}
                    >
                      <span className="size-5 shrink-0 rounded-full border border-border text-[10px] leading-[1.2rem] text-center font-semibold text-foreground">
                        {key}
                      </span>
                      {value}
                    </li>
                  );
                },
              )}
            </ul>
            {showResults && (
              <p className="mt-2 text-xs text-muted-foreground italic">
                {mcq.explanation}
              </p>
            )}
          </div>
        ))}
      </div>

      {!showResults && (
        <button
          onClick={handleSubmit}
          disabled={
            Object.keys(selectedAnswers).length < Math.min(5, mcqs.length)
          }
          className="mt-5 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full bg-primary text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Highlighter className="size-4" aria-hidden="true" />
          Submit Answers
        </button>
      )}

      {showResults && (
        <button
          onClick={() => {
            setSelectedAnswers({});
            setShowResults(false);
          }}
          className="mt-3 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full border border-border bg-card text-sm font-medium hover:bg-muted"
        >
          Try Again
        </button>
      )}
    </div>
  );
}
