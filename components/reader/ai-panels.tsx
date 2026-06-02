"use client";

import { useEffect, useState } from "react";
import { BookOpenText, Play, Highlighter } from "lucide-react";
import { aiApi } from "@/lib/api";

// Textbook Panel with AI Integration
export function TextbookPanel({ slideId }: { slideId: string }) {
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const fetchSuggestions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await aiApi.getTextbookSuggestions(slideId);
      setSuggestions(data.textbooks || data.suggestions || []);
    } catch (err: any) {
      console.error("Error fetching textbook suggestions:", err);

      if (err.response?.status === 403) {
        setError("Premium access required for textbook suggestions");
      } else if (retryCount < 2) {
        // Auto-retry up to 2 times
        setTimeout(
          () => {
            setRetryCount((prev) => prev + 1);
            fetchSuggestions();
          },
          1000 * (retryCount + 1),
        ); // Exponential backoff
        return;
      } else {
        setError(
          "Failed to load textbook suggestions. Please try again later.",
        );
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSuggestions();
  }, [slideId]);

  const handleRetry = () => {
    setRetryCount(0);
    fetchSuggestions();
  };

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
          {!error.includes("Premium access required") && (
            <button
              onClick={handleRetry}
              className="mt-2 inline-flex items-center gap-1 rounded-full bg-destructive px-3 py-1 text-xs text-white hover:opacity-90"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-muted bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            No textbook suggestions available for this slide.
          </p>
          <button
            onClick={handleRetry}
            className="mt-2 text-xs text-primary hover:underline"
          >
            Try generating again
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
                {suggestion.title}
              </p>
              {suggestion.author && (
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  by {suggestion.author}
                </p>
              )}
              <p className="mt-1 text-[11px] font-medium text-primary">
                {suggestion.chapter}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                {suggestion.reason || suggestion.relevance}
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
  const [retryCount, setRetryCount] = useState(0);

  const fetchSuggestions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await aiApi.getVideoSuggestions(slideId);
      setSuggestions(data.videos || data.suggestions || []);
    } catch (err: any) {
      console.error("Error fetching video suggestions:", err);

      if (err.response?.status === 403) {
        setError("Premium access required for video suggestions");
      } else if (retryCount < 2) {
        // Auto-retry up to 2 times
        setTimeout(
          () => {
            setRetryCount((prev) => prev + 1);
            fetchSuggestions();
          },
          1000 * (retryCount + 1),
        ); // Exponential backoff
        return;
      } else {
        setError("Failed to load video suggestions. Please try again later.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSuggestions();
  }, [slideId]);

  const handleRetry = () => {
    setRetryCount(0);
    fetchSuggestions();
  };

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
          {!error.includes("Premium access required") && (
            <button
              onClick={handleRetry}
              className="mt-2 inline-flex items-center gap-1 rounded-full bg-destructive px-3 py-1 text-xs text-white hover:opacity-90"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-muted bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            No video suggestions available for this slide.
          </p>
          <button
            onClick={handleRetry}
            className="mt-2 text-xs text-primary hover:underline"
          >
            Try generating again
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
        {suggestions.map((v, idx) => {
          const youtubeUrl = v.query
            ? `https://www.youtube.com/results?search_query=${encodeURIComponent(v.query)}`
            : `https://www.youtube.com/results?search_query=${encodeURIComponent(v.title)}`;

          return (
            <li key={idx}>
              <a
                href={youtubeUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="block w-full"
              >
                <div className="flex w-full gap-3 rounded-2xl border border-border bg-background p-3 transition-colors hover:border-primary hover:bg-primary/5">
                  <div className="relative flex size-20 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                    <Play className="size-5" aria-hidden="true" />
                    {v.duration && (
                      <span className="absolute bottom-1 right-1 rounded bg-foreground/80 px-1 py-0.5 text-[10px] font-medium text-background">
                        {v.duration}
                      </span>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-sm font-medium">
                      {v.title}
                    </p>
                    {v.channel && (
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        {v.channel}
                      </p>
                    )}
                    {(v.reason || v.description) && (
                      <p className="mt-1 text-[10px] text-muted-foreground line-clamp-2">
                        {v.reason || v.description}
                      </p>
                    )}
                  </div>
                </div>
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// Quiz Panel with AI Integration
export function QuizPanel({ slideId }: { slideId: string }) {
  const [mcqs, setMcqs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState<
    Record<number, number>
  >({});
  const [showResults, setShowResults] = useState<Record<number, boolean>>({});

  const fetchMCQs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await aiApi.generateMCQs(slideId);
      const questions = data.mcqs || [];

      // Ensure we have the expected format
      const formattedQuestions = questions.map((mcq: any) => ({
        ...mcq,
        options: Array.isArray(mcq.options)
          ? mcq.options
          : [
              mcq.options?.A,
              mcq.options?.B,
              mcq.options?.C,
              mcq.options?.D,
            ].filter(Boolean),
        correct: typeof mcq.correct === "number" ? mcq.correct : 0,
      }));

      setMcqs(formattedQuestions);
    } catch (err: any) {
      console.error("Error generating MCQs:", err);

      if (err.response?.status === 403) {
        setError("Premium access required for MCQ generation");
      } else if (retryCount < 2) {
        // Auto-retry up to 2 times
        setTimeout(
          () => {
            setRetryCount((prev) => prev + 1);
            fetchMCQs();
          },
          1000 * (retryCount + 1),
        ); // Exponential backoff
        return;
      } else {
        setError("Failed to generate quiz questions. Please try again later.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMCQs();
  }, [slideId]);

  const handleRetry = () => {
    setRetryCount(0);
    setSelectedAnswers({});
    setShowResults({});
    setCurrentQuestionIndex(0);
    fetchMCQs();
  };

  const handleAnswerSelect = (questionIdx: number, answerIdx: number) => {
    if (showResults[questionIdx]) return; // Don't allow changes after showing results

    setSelectedAnswers((prev) => ({
      ...prev,
      [questionIdx]: answerIdx,
    }));

    // Show result immediately
    setShowResults((prev) => ({
      ...prev,
      [questionIdx]: true,
    }));
  };

  const goToNextQuestion = () => {
    if (currentQuestionIndex < mcqs.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1);
    }
  };

  const goToPrevQuestion = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1);
    }
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
          {!error.includes("Premium access required") && (
            <button
              onClick={handleRetry}
              className="mt-2 inline-flex items-center gap-1 rounded-full bg-destructive px-3 py-1 text-xs text-white hover:opacity-90"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    );
  }

  if (mcqs.length === 0) {
    return (
      <div className="p-5">
        <div className="rounded-2xl border border-muted bg-muted/50 p-4 text-center">
          <p className="text-sm text-muted-foreground">
            No quiz questions could be generated for this slide.
          </p>
          <button
            onClick={handleRetry}
            className="mt-2 text-xs text-primary hover:underline"
          >
            Try generating again
          </button>
        </div>
      </div>
    );
  }

  const totalAnswered = Object.keys(selectedAnswers).length;
  const totalCorrect = Object.entries(selectedAnswers).filter(
    ([idx, answerIdx]) => answerIdx === mcqs[parseInt(idx)]?.correct,
  ).length;

  const currentMCQ = mcqs[currentQuestionIndex];
  const isAnswered = selectedAnswers.hasOwnProperty(currentQuestionIndex);
  const showCurrentResult = showResults[currentQuestionIndex];

  return (
    <div className="p-5">
      <p className="text-[11px] font-medium uppercase tracking-widest text-primary">
        AI-Generated from this slide
      </p>
      <h3 className="mt-1 font-serif text-xl">
        {mcqs.length} MCQs to test yourself
      </h3>

      {/* Progress indicator */}
      <div className="mt-3 flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Question {currentQuestionIndex + 1} of {mcqs.length}
        </span>
        {totalAnswered > 0 && (
          <span className="text-primary">
            Score: {totalCorrect}/{totalAnswered}
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="mt-2 w-full bg-muted rounded-full h-1">
        <div
          className="bg-primary h-1 rounded-full transition-all duration-300"
          style={{ width: `${(totalAnswered / mcqs.length) * 100}%` }}
        />
      </div>

      {/* Current Question */}
      <div className="mt-4">
        <div className="rounded-2xl border border-border bg-background p-4">
          <p className="font-medium text-sm">
            {currentQuestionIndex + 1}. {currentMCQ.question}
          </p>

          <div className="mt-3 space-y-2">
            {currentMCQ.options.map((option: string, idx: number) => {
              const isSelected = selectedAnswers[currentQuestionIndex] === idx;
              const isCorrect = idx === currentMCQ.correct;
              const showCorrect = showCurrentResult && isCorrect;
              const showWrong = showCurrentResult && isSelected && !isCorrect;

              return (
                <button
                  key={idx}
                  onClick={() => handleAnswerSelect(currentQuestionIndex, idx)}
                  disabled={showCurrentResult}
                  className={`w-full text-left flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                    showCorrect
                      ? "border-green-500 bg-green-50 text-green-800"
                      : showWrong
                        ? "border-red-500 bg-red-50 text-red-800"
                        : isSelected
                          ? "border-primary bg-primary/5 text-primary"
                          : "border-border bg-card hover:border-primary hover:bg-primary/5"
                  } ${showCurrentResult ? "cursor-not-allowed" : "cursor-pointer"}`}
                >
                  <span className="size-5 shrink-0 rounded-full border border-current text-[10px] leading-[1.2rem] text-center font-semibold">
                    {String.fromCharCode(65 + idx)}
                  </span>
                  {option}
                </button>
              );
            })}
          </div>

          {/* Explanation */}
          {showCurrentResult && currentMCQ.explanation && (
            <div className="mt-3 p-3 bg-muted rounded-lg">
              <p className="text-xs text-muted-foreground">
                <strong>Explanation:</strong> {currentMCQ.explanation}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="mt-4 flex items-center justify-between">
        <button
          onClick={goToPrevQuestion}
          disabled={currentQuestionIndex === 0}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ← Previous
        </button>

        <div className="flex gap-1">
          {mcqs.slice(0, Math.min(mcqs.length, 20)).map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentQuestionIndex(idx)}
              className={`size-6 rounded text-[10px] font-medium transition-colors ${
                idx === currentQuestionIndex
                  ? "bg-primary text-primary-foreground"
                  : selectedAnswers.hasOwnProperty(idx)
                    ? "bg-green-500 text-white"
                    : "bg-muted text-muted-foreground hover:bg-primary/20"
              }`}
            >
              {idx + 1}
            </button>
          ))}
        </div>

        <button
          onClick={goToNextQuestion}
          disabled={currentQuestionIndex === mcqs.length - 1}
          className="inline-flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next →
        </button>
      </div>

      {/* Generate more questions */}
      {totalAnswered === mcqs.length && (
        <button
          onClick={handleRetry}
          className="mt-4 inline-flex h-10 w-full items-center justify-center gap-1.5 rounded-full border border-border bg-card text-sm font-medium hover:bg-muted"
        >
          <Highlighter className="size-4" aria-hidden="true" />
          Generate New Questions
        </button>
      )}
    </div>
  );
}
