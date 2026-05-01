"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { SteeplechaseItem } from "@/lib/data";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Clock, Check, X, Flag, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFeatureAccess } from "@/hooks/use-feature-access";
import { UpgradePrompt } from "@/components/upgrade-prompt";

type Session = {
  id: string;
  title: string;
  durationSec: number; // per station
  items: SteeplechaseItem[];
};

export function SteeplechaseRunner({ session }: { session: Session }) {
  const { hasAccess } = useFeatureAccess();
  const hasSteeplechase = hasAccess("steeplechase");

  if (!hasSteeplechase) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <UpgradePrompt
          feature="Steeplechase Training"
          description="Practice timed exam simulations with real past questions"
        />
      </div>
    );
  }

  const total = session.items.length;
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<string[]>(Array(total).fill(""));
  const [timeLeft, setTimeLeft] = useState(session.durationSec);
  const [finished, setFinished] = useState(false);
  const [started, setStarted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const current = session.items[index];

  // Per-station timer
  useEffect(() => {
    if (!started || finished) return;
    setTimeLeft(session.durationSec);
    const interval = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          clearInterval(interval);
          advance();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, started, finished]);

  useEffect(() => {
    if (started && !finished) inputRef.current?.focus();
  }, [index, started, finished]);

  function advance() {
    setIndex((i) => {
      if (i + 1 >= total) {
        setFinished(true);
        return i;
      }
      return i + 1;
    });
  }

  function updateAnswer(value: string) {
    setAnswers((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }

  const score = useMemo(() => {
    if (!finished) return 0;
    return session.items.reduce((acc, s, i) => {
      const ans = answers[i].trim().toLowerCase();
      const correct = s.acceptedAnswers.some((a) => a.toLowerCase() === ans);
      return acc + (correct ? 1 : 0);
    }, 0);
  }, [finished, answers, session.items]);

  // Start screen
  if (!started) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10 md:py-16">
        <Link
          href="/steeplechase"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to steeplechase
        </Link>

        <Card className="mt-6 overflow-hidden border-border p-0 study-glow">
          <div className="relative overflow-hidden bg-learning/15 px-7 py-9">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 grid-surface opacity-60"
            />
            <div className="relative">
              <Badge className="mb-3 border-weakness/40 bg-weakness/15 text-weakness hover:bg-weakness/20">
                Spot test simulation
              </Badge>
              <h1 className="font-serif text-3xl font-semibold leading-tight tracking-tight text-balance md:text-[32px]">
                {session.title}
              </h1>
              <p className="mt-2 max-w-xl text-sm text-muted-foreground text-pretty">
                Identify the pinned structure at each station. The timer does
                not stop — just like in the lab.
              </p>
            </div>
          </div>

          <div className="grid gap-6 p-7 md:grid-cols-3">
            <Stat label="Stations" value={String(total)} />
            <Stat label="Per station" value={`${session.durationSec}s`} />
            <Stat
              label="Total"
              value={`${Math.round((session.durationSec * total) / 60)} min`}
            />
          </div>

          <div className="border-t border-border bg-background/40 p-7">
            <h3 className="font-serif text-base font-semibold">How it works</h3>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li className="flex gap-2">
                <span className="text-learning">1.</span>
                <span>
                  You&apos;ll see a labeled specimen image at each station.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-learning">2.</span>
                <span>
                  Type the correct structure or answer before the timer runs
                  out.
                </span>
              </li>
              <li className="flex gap-2">
                <span className="text-learning">3.</span>
                <span>
                  No going back. Review everything at the end with detailed
                  explanations.
                </span>
              </li>
            </ul>
            <Button
              size="lg"
              className="mt-6 w-full rounded-full md:w-auto"
              onClick={() => setStarted(true)}
            >
              Start steeplechase
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  // Results screen
  if (finished) {
    const percent = Math.round((score / total) * 100);
    const overallTone: "mastery" | "review" | "weakness" =
      percent >= 80 ? "mastery" : percent >= 50 ? "review" : "weakness";
    const toneBg =
      overallTone === "mastery"
        ? "bg-mastery/15"
        : overallTone === "review"
          ? "bg-review/15"
          : "bg-weakness/15";
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <Card className="overflow-hidden border-border p-0">
          <div className={cn("px-7 py-9", toneBg)}>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Steeplechase complete
            </p>
            <h1 className="mt-2 font-serif text-3xl font-semibold leading-tight tracking-tight md:text-4xl">
              {score} / {total} correct
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {percent >= 80
                ? "Excellent work. You would pass this spot test."
                : percent >= 50
                  ? "Solid effort. Review the ones you missed — they'll come back in your flashcards."
                  : "Tough round. The review below will help; we'll schedule extra reps."}
            </p>
          </div>

          <div className="divide-y divide-border">
            {session.items.map((s, i) => {
              const ans = answers[i].trim();
              const correct = s.acceptedAnswers.some(
                (a) => a.toLowerCase() === ans.toLowerCase(),
              );
              return (
                <div
                  key={s.id}
                  className="grid gap-4 p-6 md:grid-cols-[1fr_1.3fr]"
                >
                  <div className="relative aspect-[4/3] overflow-hidden rounded-xl border border-border bg-muted">
                    <img
                      src={`/placeholder.svg?height=520&width=720&query=${encodeURIComponent(s.imageQuery)}`}
                      alt={`Station ${i + 1} specimen`}
                      className="h-full w-full object-cover"
                    />
                    <div className="absolute left-3 top-3 rounded-md bg-background/80 px-2 py-1 text-xs font-semibold text-foreground backdrop-blur">
                      Station {i + 1}
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium">{s.prompt}</p>
                    <div className="mt-3 flex items-center gap-2">
                      {correct ? (
                        <Badge className="border-mastery/40 bg-mastery/15 text-mastery hover:bg-mastery/20">
                          <Check className="mr-1 h-3 w-3" /> Correct
                        </Badge>
                      ) : (
                        <Badge className="border-weakness/40 bg-weakness/15 text-weakness hover:bg-weakness/20">
                          <X className="mr-1 h-3 w-3" /> Incorrect
                        </Badge>
                      )}
                    </div>
                    <div className="mt-4 space-y-2 text-sm">
                      <div>
                        <span className="text-muted-foreground">
                          Your answer:{" "}
                        </span>
                        <span
                          className={cn(
                            "font-medium",
                            !correct && "text-weakness line-through",
                          )}
                        >
                          {ans || "— no answer —"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">
                          Accepted:{" "}
                        </span>
                        <span className="font-medium text-mastery">
                          {s.acceptedAnswers.join(", ")}
                        </span>
                      </div>
                    </div>
                    <div className="mt-4 rounded-xl border border-border bg-background/40 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                        Teaching point
                      </p>
                      <p className="mt-1 text-sm leading-relaxed">
                        {s.explanation}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex flex-col gap-3 border-t border-border bg-background/40 p-6 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-muted-foreground">
              Saved to your progress. Spaced repetition will bring missed
              stations back.
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  setAnswers(Array(total).fill(""));
                  setIndex(0);
                  setFinished(false);
                  setStarted(false);
                }}
              >
                <RotateCcw className="mr-2 h-4 w-4" />
                Retry
              </Button>
              <Button asChild className="rounded-full">
                <Link href="/dashboard">Back to dashboard</Link>
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  // Active station — full-screen focus with pressure feel
  const percent = ((index + 1) / total) * 100;
  const urgent = timeLeft <= 5;

  return (
    <div className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-background">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 grid-surface opacity-40"
      />

      <div className="relative mx-auto flex w-full max-w-5xl flex-1 flex-col px-4 py-5 sm:px-6">
        {/* Top bar */}
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Badge
              variant="outline"
              className="border-border bg-card/80 backdrop-blur"
            >
              Station {index + 1} of {total}
            </Badge>
            <div className="hidden text-xs text-muted-foreground md:block">
              {session.title}
            </div>
          </div>
          <div
            className={cn(
              "flex items-center gap-2 rounded-full border px-3.5 py-1.5 font-mono text-sm font-semibold tabular-nums transition-colors",
              urgent
                ? "border-weakness/60 bg-weakness/15 text-weakness pressure-pulse"
                : "border-border bg-card text-foreground",
            )}
            aria-live="polite"
          >
            <Clock className="h-4 w-4" />
            {timeLeft}s
          </div>
        </div>
        <Progress value={percent} className="mb-5 h-1" />

        <div className="grid flex-1 gap-5 md:grid-cols-[1.2fr_1fr]">
          {/* Specimen — hero */}
          <Card className="overflow-hidden border-border p-0">
            <div className="relative h-full min-h-[320px] bg-muted">
              <img
                src={`/placeholder.svg?height=520&width=720&query=${encodeURIComponent(current.imageQuery)}`}
                alt={`Specimen for station ${index + 1}`}
                className="h-full w-full object-cover"
              />
              <div className="absolute left-4 top-4 rounded-md bg-background/80 px-2 py-1 text-xs font-semibold text-foreground backdrop-blur">
                Station {index + 1}
              </div>
              {urgent && (
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 ring-2 ring-inset ring-weakness/50"
                />
              )}
            </div>
          </Card>

          {/* Prompt + answer */}
          <Card className="flex flex-col border-border p-6">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-learning">
              {current.topic}
            </p>
            <h2 className="mt-2 font-serif text-xl font-semibold leading-snug text-balance md:text-2xl">
              {current.prompt}
            </h2>

            <div className="mt-6 flex-1">
              <label
                className="text-xs font-medium text-muted-foreground"
                htmlFor="answer"
              >
                Your answer
              </label>
              <input
                id="answer"
                ref={inputRef}
                value={answers[index]}
                onChange={(e) => updateAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") advance();
                }}
                placeholder="Type the structure name…"
                className={cn(
                  "mt-2 w-full rounded-xl border bg-background/40 px-4 py-3 text-base outline-none transition",
                  urgent
                    ? "border-weakness/60 focus:border-weakness focus:ring-2 focus:ring-weakness/25"
                    : "border-border focus:border-primary focus:ring-2 focus:ring-primary/25",
                )}
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Press Enter to lock in and move to the next station.
              </p>
            </div>

            <div className="mt-6 flex items-center justify-between gap-3 border-t border-border pt-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFinished(true)}
                className="text-muted-foreground hover:text-foreground"
              >
                <Flag className="mr-2 h-4 w-4" />
                End early
              </Button>
              <Button onClick={advance} className="rounded-full">
                {index + 1 === total ? "Finish" : "Next station"}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 font-serif text-xl font-semibold tracking-tight">
        {value}
      </p>
    </div>
  );
}
