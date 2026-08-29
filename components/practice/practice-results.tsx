"use client";

/**
 * Round results.
 *
 * Every figure here is computed server-side from what the student actually answered —
 * there are no illustrative percentages. Free students get their score and a per-section
 * breakdown; the per-station answers and explanations are the premium half, and the
 * difference is stated plainly rather than hidden behind a blurred panel.
 */

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Axo, AxoCelebrate, AxoLoader } from "@/components/brand/axo";
import { practiceApi, type PracticeResults } from "@/lib/api";
import { cn } from "@/lib/utils";

const label = (code: string) =>
  code.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

export function PracticeResultsView({
  sessionId,
  onAgain,
}: {
  sessionId: string;
  onAgain: () => void;
}) {
  const [results, setResults] = useState<PracticeResults | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await practiceApi.getResults(sessionId);
        if (!cancelled) setResults(data);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (loading) return <AxoLoader label="Working out how you did…" pose="clipboard" />;
  if (!results) return null;

  const sections = Object.entries(results.section_breakdown ?? {});

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <AxoCelebrate
        score={results.accuracy_percent}
        description={`${results.main_correct} of ${results.total_stations} structures identified.`}
      />

      {/* Headline figures */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        <Figure label="Score" value={`${results.accuracy_percent}%`} tone="primary" />
        <Figure label="Identified" value={`${results.main_correct}/${results.total_stations}`} />
        <Figure label="Avg time" value={`${results.average_seconds}s`} />
        <Figure
          label="Timed out"
          value={String(results.timed_out)}
          tone={results.timed_out > 0 ? "weakness" : "mastery"}
        />
      </div>

      {/* Per-section */}
      {sections.length > 0 && (
        <section className="mt-6">
          <h2 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            By section
          </h2>
          <ul className="mt-3 space-y-2">
            {sections
              .sort((a, b) => a[1].accuracy - b[1].accuracy)
              .map(([code, stats]) => (
                <li key={code} className="card-3d flex items-center gap-3 p-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-sm font-medium">{label(code)}</span>
                      <span className="text-sm tabular text-muted-foreground">
                        {stats.correct}/{stats.attempted}
                      </span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-secondary">
                      <div
                        className={cn(
                          "h-full rounded-full",
                          stats.accuracy >= 0.7
                            ? "bg-mastery"
                            : stats.accuracy >= 0.4
                              ? "bg-review"
                              : "bg-weakness",
                        )}
                        style={{ width: `${Math.max(4, stats.accuracy * 100)}%` }}
                      />
                    </div>
                  </div>
                </li>
              ))}
          </ul>
        </section>
      )}

      {/* Premium: every station, with the answer and why */}
      {results.stations ? (
        <section className="mt-6">
          <h2 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
            Every station
          </h2>
          <ul className="mt-3 space-y-2.5">
            {results.stations.map((s, i) => (
              <li key={s.station_id} className="card-3d overflow-hidden">
                <div className="flex gap-3 p-3">
                  <Image
                    src={s.image_url}
                    alt=""
                    width={112}
                    height={84}
                    className="size-[84px] shrink-0 rounded-lg object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground tabular">#{i + 1}</span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                          s.main_correct
                            ? "bg-mastery/15 text-mastery"
                            : "bg-weakness/15 text-weakness",
                        )}
                      >
                        {s.main_correct ? "Correct" : s.timed_out ? "Timed out" : "Missed"}
                      </span>
                    </div>
                    <p className="mt-1 text-sm font-medium leading-snug">{s.question}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      You said{" "}
                      <span className="text-foreground">
                        {s.your_answer?.trim() || "nothing"}
                      </span>
                      {!s.main_correct && s.correct_answer && (
                        <>
                          {" · answer "}
                          <span className="text-mastery">{s.correct_answer}</span>
                        </>
                      )}
                    </p>
                    {s.explanation && (
                      <p className="mt-1.5 text-pretty text-[13px] leading-relaxed text-muted-foreground">
                        {s.explanation}
                      </p>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : (
        <div className="mt-6 flex items-start gap-3 rounded-2xl border border-primary/20 plinth p-4">
          <Axo pose="rocket" size="sm" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">{results.upgrade_hint}</p>
            <Link
              href="/premium"
              className="press mt-2 inline-flex h-9 items-center rounded-full bg-primary px-4 text-xs font-semibold text-primary-foreground"
            >
              See Premium
            </Link>
          </div>
        </div>
      )}

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={onAgain}
          className="press h-12 flex-1 rounded-full bg-primary text-sm font-semibold text-primary-foreground"
        >
          Practise again
        </button>
        <Link
          href="/dashboard"
          className="press flex h-12 flex-1 items-center justify-center rounded-full border border-border bg-card text-sm font-medium"
        >
          Done
        </Link>
      </div>
    </div>
  );
}

function Figure({
  label: name,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "primary" | "mastery" | "weakness";
}) {
  const colour = {
    neutral: "text-foreground",
    primary: "text-primary",
    mastery: "text-mastery",
    weakness: "text-weakness",
  }[tone];

  return (
    <div className="card-3d p-3.5">
      <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
        {name}
      </p>
      <p className={cn("font-display text-2xl font-semibold tabular", colour)}>{value}</p>
    </div>
  );
}
