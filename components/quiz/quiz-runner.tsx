"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Flame,
  Focus,
  ListChecks,
  Minimize2,
  RotateCcw,
  Timer,
  Trophy,
  X,
} from "lucide-react";
import type { MCQ } from "@/lib/data";
import { cn } from "@/lib/utils";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { UpgradePrompt } from "@/components/upgrade-prompt";
import { useAppSelector } from "@/store/hooks";

type Quiz = {
  id: string;
  title: string;
  topic: string;
  durationSec: number;
  questions: MCQ[];
};

export function QuizRunner({ quiz }: { quiz: Quiz }) {
  const { hasAccess, isFree } = useFeatureAccess();
  const usage = useAppSelector((s) => s.user.usage);

  if (isFree && usage.quizzesTaken >= 1) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <UpgradePrompt
          feature="Daily Quizzes"
          description="Take unlimited quizzes with detailed explanations and performance tracking"
        />
      </div>
    );
  }

  const [started, setStarted] = useState(false);
  const [finished, setFinished] = useState(false);
  const [focusMode, setFocusMode] = useState(true); // brief: exam feel by default

  const [timeLeft, setTimeLeft] = useState(quiz.durationSec);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [answers, setAnswers] = useState<(number | null)[]>(() =>
    quiz.questions.map(() => null),
  );

  useEffect(() => {
    if (!started || finished) return;
    if (timeLeft <= 0) {
      setFinished(true);
      return;
    }
    const t = setInterval(() => setTimeLeft((s) => s - 1), 1000);
    return () => clearInterval(t);
  }, [started, finished, timeLeft]);

  const q = quiz.questions[index];

  function handleSelect(i: number) {
    if (revealed) return;
    setSelected(i);
  }

  function handleSubmit() {
    if (selected === null) return;
    setAnswers((a) => a.map((v, i) => (i === index ? selected : v)));
    setRevealed(true);
  }

  function handleNext() {
    if (index + 1 >= quiz.questions.length) {
      setFinished(true);
      return;
    }
    setIndex((i) => i + 1);
    setSelected(null);
    setRevealed(false);
  }

  function restart() {
    setStarted(false);
    setFinished(false);
    setIndex(0);
    setSelected(null);
    setRevealed(false);
    setTimeLeft(quiz.durationSec);
    setAnswers(quiz.questions.map(() => null));
  }

  if (!started) {
    return <QuizIntro quiz={quiz} onStart={() => setStarted(true)} />;
  }

  if (finished) {
    return <QuizResults quiz={quiz} answers={answers} onRestart={restart} />;
  }

  const urgent = timeLeft < 30;
  const progressPct =
    ((index + (revealed ? 1 : 0)) / quiz.questions.length) * 100;

  // Focus mode wraps everything in fixed full-screen, hiding app chrome.
  const shellClass = focusMode
    ? "fixed inset-0 z-50 overflow-y-auto bg-background"
    : "relative";

  return (
    <div className={shellClass}>
      {focusMode && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 grid-surface opacity-40"
        />
      )}

      <div className="relative mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 md:py-10">
        {/* Status bar */}
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-learning">
            {quiz.topic}
          </p>
          <span className="hidden text-muted-foreground sm:inline">·</span>
          <p className="truncate text-muted-foreground">{quiz.title}</p>

          <div className="ml-auto flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-mono tabular-nums transition-colors",
                urgent
                  ? "border-weakness/50 bg-weakness/15 text-weakness"
                  : "border-border bg-card text-foreground",
                urgent && "pressure-pulse",
              )}
              aria-live="polite"
            >
              <Timer className="size-3.5" aria-hidden="true" />
              {formatTime(timeLeft)}
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-[12px] font-medium">
              {index + 1} / {quiz.questions.length}
            </span>
            <button
              type="button"
              onClick={() => setFocusMode((f) => !f)}
              className="inline-flex size-8 items-center justify-center rounded-full border border-border bg-card text-muted-foreground hover:text-foreground"
              aria-label={focusMode ? "Exit focus mode" : "Enter focus mode"}
              title={focusMode ? "Exit focus mode" : "Focus mode"}
            >
              {focusMode ? (
                <Minimize2 className="size-3.5" aria-hidden="true" />
              ) : (
                <Focus className="size-3.5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>

        {/* Progress */}
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-learning transition-all"
            style={{ width: `${progressPct}%` }}
            aria-hidden="true"
          />
        </div>

        {/* Question */}
        <section className="mt-6 rounded-2xl border border-border bg-card p-5 md:p-8">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Question {index + 1}
          </p>
          <h2 className="mt-2 font-serif text-xl font-semibold leading-snug md:text-2xl">
            {q.question}
          </h2>

          <ul className="mt-6 space-y-2">
            {q.options.map((opt, i) => {
              const isCorrect = i === q.correct;
              const isSelected = i === selected;
              const showState = revealed;
              return (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => handleSelect(i)}
                    disabled={revealed}
                    className={cn(
                      "group flex w-full items-center gap-3 rounded-xl border px-4 py-3.5 text-left transition-colors",
                      !showState && isSelected
                        ? "border-learning bg-learning/10"
                        : !showState
                          ? "border-border bg-background/40 hover:border-learning/50"
                          : "",
                      showState &&
                        isCorrect &&
                        "border-mastery/60 bg-mastery/10",
                      showState &&
                        isSelected &&
                        !isCorrect &&
                        "border-weakness/60 bg-weakness/10",
                      showState &&
                        !isCorrect &&
                        !isSelected &&
                        "border-border bg-background/40 opacity-60",
                    )}
                    aria-pressed={isSelected}
                  >
                    <span
                      className={cn(
                        "flex size-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
                        !showState &&
                          isSelected &&
                          "border-learning bg-learning text-primary-foreground",
                        showState &&
                          isCorrect &&
                          "border-mastery bg-mastery text-accent-foreground",
                        showState &&
                          isSelected &&
                          !isCorrect &&
                          "border-weakness bg-weakness text-destructive-foreground",
                        !showState &&
                          !isSelected &&
                          "border-border text-muted-foreground",
                        showState &&
                          !isCorrect &&
                          !isSelected &&
                          "border-border text-muted-foreground",
                      )}
                    >
                      {showState ? (
                        isCorrect ? (
                          <Check className="size-3.5" aria-hidden="true" />
                        ) : isSelected ? (
                          <X className="size-3.5" aria-hidden="true" />
                        ) : (
                          String.fromCharCode(65 + i)
                        )
                      ) : (
                        String.fromCharCode(65 + i)
                      )}
                    </span>
                    <span className="flex-1 text-sm md:text-[15px]">{opt}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          {revealed && (
            <div
              className={cn(
                "mt-6 rounded-xl border p-4",
                selected === q.correct
                  ? "border-mastery/40 bg-mastery/10"
                  : "border-weakness/40 bg-weakness/10",
              )}
            >
              <p
                className={cn(
                  "text-[11px] font-semibold uppercase tracking-widest",
                  selected === q.correct ? "text-mastery" : "text-weakness",
                )}
              >
                {selected === q.correct ? "Correct" : "Not quite"}
              </p>
              <p className="mt-1 text-sm leading-relaxed">{q.explanation}</p>
            </div>
          )}

          <div className="mt-8 flex items-center justify-between">
            <p className="text-xs text-muted-foreground">Topic: {q.topic}</p>
            {!revealed ? (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={selected === null}
                className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                Submit
              </button>
            ) : (
              <button
                type="button"
                onClick={handleNext}
                className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground hover:opacity-90"
              >
                {index + 1 >= quiz.questions.length
                  ? "See results"
                  : "Next question"}
                <ArrowRight className="size-4" aria-hidden="true" />
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function QuizIntro({ quiz, onStart }: { quiz: Quiz; onStart: () => void }) {
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-12 sm:px-6 md:py-20">
      <div className="rounded-2xl border border-border bg-card p-7 md:p-10 study-glow">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-learning">
          Timed quiz · {quiz.topic}
        </p>
        <h1 className="mt-3 font-serif text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
          {quiz.title}
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          {quiz.questions.length} questions ·{" "}
          {Math.round(quiz.durationSec / 60)} minutes. Runs in focus mode — no
          distractions, just you and the paper.
        </p>

        <dl className="mt-6 grid grid-cols-3 gap-3">
          <Stat
            label="Questions"
            value={String(quiz.questions.length)}
            icon={<ListChecks className="size-4" />}
          />
          <Stat
            label="Time"
            value={`${Math.round(quiz.durationSec / 60)} min`}
            icon={<Timer className="size-4" />}
          />
          <Stat label="Pass" value="60%" icon={<Flame className="size-4" />} />
        </dl>

        <button
          onClick={onStart}
          className="mt-7 inline-flex h-12 items-center gap-2 rounded-full bg-primary px-6 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Start quiz
          <ArrowRight className="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-background/40 p-3">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        {icon}
        <p className="text-[10px] uppercase tracking-widest">{label}</p>
      </div>
      <p className="mt-1 font-serif text-lg font-semibold">{value}</p>
    </div>
  );
}

function QuizResults({
  quiz,
  answers,
  onRestart,
}: {
  quiz: Quiz;
  answers: (number | null)[];
  onRestart: () => void;
}) {
  const correct = answers.filter(
    (a, i) => a !== null && a === quiz.questions[i].correct,
  ).length;
  const total = quiz.questions.length;
  const percent = Math.round((correct / total) * 100);
  const passed = percent >= 60;

  // Topic breakdown
  const topicStats = new Map<string, { correct: number; total: number }>();
  quiz.questions.forEach((q, i) => {
    const t = topicStats.get(q.topic) ?? { correct: 0, total: 0 };
    t.total += 1;
    if (answers[i] === q.correct) t.correct += 1;
    topicStats.set(q.topic, t);
  });

  const topics = Array.from(topicStats.entries()).map(([topic, s]) => {
    const pct = Math.round((s.correct / s.total) * 100);
    const tone: "mastery" | "review" | "weakness" =
      pct >= 80 ? "mastery" : pct >= 50 ? "review" : "weakness";
    return { topic, pct, tone, ...s };
  });

  const weakTopics = topics.filter((t) => t.tone === "weakness");
  const reviewTopics = topics.filter((t) => t.tone === "review");
  const strongTopics = topics.filter((t) => t.tone === "mastery");

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 md:py-14">
      <div className="rounded-2xl border border-border bg-card p-7 md:p-10 study-glow">
        <div className="flex items-start gap-4">
          <span
            className={cn(
              "flex size-12 items-center justify-center rounded-2xl",
              passed
                ? "bg-mastery text-accent-foreground"
                : "bg-review text-accent-foreground",
            )}
          >
            <Trophy className="size-6" aria-hidden="true" />
          </span>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Quiz complete
            </p>
            <h1 className="mt-1 font-serif text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
              {passed
                ? "Solid. You would pass this."
                : "You're close — sharpen the weak spots."}
            </h1>
          </div>
        </div>

        <dl className="mt-7 grid grid-cols-3 gap-3">
          <ScoreStat
            label="Score"
            value={`${percent}%`}
            tone={passed ? "mastery" : "review"}
          />
          <ScoreStat label="Correct" value={`${correct}/${total}`} />
          <ScoreStat
            label="XP earned"
            value={`+${correct * 50}`}
            tone="learning"
          />
        </dl>

        {/* Topic breakdown — colored by mastery */}
        <div className="mt-7">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Topic breakdown
          </p>
          <ul className="mt-3 space-y-2">
            {topics.map(({ topic, pct, tone, correct: c, total: t }) => {
              const barClass =
                tone === "mastery"
                  ? "bg-mastery"
                  : tone === "review"
                    ? "bg-review"
                    : "bg-weakness";
              const textClass =
                tone === "mastery"
                  ? "text-mastery"
                  : tone === "review"
                    ? "text-review"
                    : "text-weakness";
              return (
                <li
                  key={topic}
                  className="rounded-xl border border-border bg-background/40 p-3"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{topic}</span>
                    <span className={cn("font-mono tabular-nums", textClass)}>
                      {c}/{t} · {pct}%
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn("h-full rounded-full", barClass)}
                      style={{ width: `${pct}%` }}
                      aria-hidden="true"
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        {/* What to study next */}
        <div className="mt-7 rounded-xl border border-learning/30 bg-learning/10 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-learning">
            What to study next
          </p>
          {weakTopics.length > 0 ? (
            <p className="mt-1.5 text-sm">
              Drill{" "}
              <span className="font-semibold text-weakness">
                {weakTopics.map((t) => t.topic).join(", ")}
              </span>{" "}
              — these are pulling your score down.
            </p>
          ) : reviewTopics.length > 0 ? (
            <p className="mt-1.5 text-sm">
              Review{" "}
              <span className="font-semibold text-review">
                {reviewTopics.map((t) => t.topic).join(", ")}
              </span>{" "}
              to push them into mastery.
            </p>
          ) : (
            <p className="mt-1.5 text-sm">
              Everything is strong — rotate into the next module to stay ahead.
            </p>
          )}
          {strongTopics.length > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">
              Strong:{" "}
              <span className="text-mastery">
                {strongTopics.map((t) => t.topic).join(", ")}
              </span>
            </p>
          )}
        </div>

        <div className="mt-7 flex flex-wrap gap-2">
          <button
            onClick={onRestart}
            className="inline-flex h-11 items-center gap-2 rounded-full border border-border bg-background/40 px-5 text-sm font-medium hover:border-primary/50"
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            Retake
          </button>
          <Link
            href="/flashcards"
            className="inline-flex h-11 items-center gap-2 rounded-full bg-primary px-5 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Drill weak topics
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </div>
  );
}

function ScoreStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "mastery" | "learning" | "review";
}) {
  const accent =
    tone === "mastery"
      ? "text-mastery"
      : tone === "review"
        ? "text-review"
        : tone === "learning"
          ? "text-learning"
          : "text-foreground";
  return (
    <div className="rounded-xl border border-border bg-background/40 p-4">
      <dt className="text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </dt>
      <dd
        className={cn(
          "mt-1 font-serif text-2xl font-semibold tracking-tight",
          accent,
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function formatTime(total: number) {
  const m = Math.floor(total / 60)
    .toString()
    .padStart(2, "0");
  const s = (total % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}
