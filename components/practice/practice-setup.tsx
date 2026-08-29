"use client";

/**
 * Round setup for Steeplechase and Histology.
 *
 * The student picks sections and a length; the allowance shown comes from the server and
 * is the same number the server enforces, so the UI can never promise a round the backend
 * will refuse. Free students see exactly what they have left rather than discovering the
 * limit by hitting it.
 */

import { useEffect, useState } from "react";
import { Crown } from "lucide-react";
import Link from "next/link";

import { Axo, AxoEmpty, AxoLoader } from "@/components/brand/axo";
import { Icon3D } from "@/components/brand/icon-3d";
import { practiceApi, type PracticeMode, type PracticeOptions } from "@/lib/api";
import { cn } from "@/lib/utils";

const COPY: Record<PracticeMode, { title: string; blurb: string; icon: "steeplechase" | "histology" }> = {
  STEEPLECHASE: {
    title: "Steeplechase",
    blurb:
      "Real specimens from your department. Thirty seconds a station, then you move on — same as the day itself.",
    icon: "steeplechase",
  },
  HISTOLOGY: {
    title: "Histology",
    blurb:
      "Spot the tissue. Thirty seconds a slide, with a supporting question on what you are looking at.",
    icon: "histology",
  },
};

export function PracticeSetup({
  mode,
  onStarted,
}: {
  mode: PracticeMode;
  onStarted: (payload: Awaited<ReturnType<typeof practiceApi.start>>) => void;
}) {
  const [options, setOptions] = useState<PracticeOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [count, setCount] = useState(5);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = COPY[mode];

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await practiceApi.getOptions(mode);
        if (cancelled) return;
        setOptions(data);
        setCount(Math.min(5, data.entitlement.max_stations));
      } catch {
        if (!cancelled) setError("Could not load practice options.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [mode]);

  if (loading) return <AxoLoader label="Setting up…" pose={mode === "HISTOLOGY" ? "microscope" : "magnifier"} />;

  if (error || !options) {
    return <AxoEmpty title="Practice is unavailable" description={error ?? undefined} pose="oops" />;
  }

  const { entitlement, sections } = options;

  if (sections.length === 0) {
    return (
      <AxoEmpty
        title="No stations ready yet"
        description="Approved stations will appear here once your department's material has been processed and reviewed."
        pose="empty"
      />
    );
  }

  const outOfRounds =
    !entitlement.is_premium && (entitlement.rounds_remaining ?? 0) <= 0;

  const toggle = (code: string) =>
    setSelected((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );

  const availableInSelection = selected.length
    ? sections.filter((s) => selected.includes(s.code)).reduce((n, s) => n + s.count, 0)
    : sections.reduce((n, s) => n + s.count, 0);

  const maxCount = Math.min(entitlement.max_stations, Math.max(1, availableInSelection));
  const lengths = [5, 10, 20, 40].filter((n) => n <= maxCount);
  if (!lengths.includes(maxCount)) lengths.push(maxCount);

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const payload = await practiceApi.start(mode, selected, Math.min(count, maxCount));
      onStarted(payload);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Could not start the round.");
      setStarting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6">
      <header className="flex items-start gap-4">
        <Icon3D name={copy.icon} size="lg" />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">
            {copy.title}
          </h1>
          <p className="mt-1 max-w-xl text-pretty text-sm text-muted-foreground">{copy.blurb}</p>
        </div>
        <Axo pose={mode === "HISTOLOGY" ? "microscope" : "magnifier"} size="md" float className="hidden sm:block" />
      </header>

      {/* Allowance — the server's number, not a guess */}
      <div
        className={cn(
          "mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-2xl border px-4 py-3 text-sm",
          outOfRounds
            ? "border-weakness/30 bg-weakness/10"
            : "border-border bg-secondary/40",
        )}
      >
        {entitlement.is_premium ? (
          <span className="flex items-center gap-1.5 font-medium text-primary">
            <Crown className="size-4" /> Unlimited rounds
          </span>
        ) : (
          <span className="tabular">
            <strong>{entitlement.rounds_remaining}</strong> of {entitlement.rounds_limit} free
            rounds left this month
          </span>
        )}
        <span className="text-muted-foreground tabular">
          {entitlement.stations_available} stations available
        </span>
        <span className="text-muted-foreground">30 seconds each</span>
      </div>

      {outOfRounds ? (
        <div className="mt-6">
          <AxoEmpty
            title="You've used this month's free rounds"
            description="Premium removes the monthly cap, unlocks the full station pool, and shows the answer and explanation for every station."
            pose="rocket"
            action={
              <Link
                href="/premium"
                className="press inline-flex h-11 items-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground"
              >
                See Premium
              </Link>
            }
          />
        </div>
      ) : (
        <>
          <section className="mt-6">
            <h2 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              Sections
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Pick as many as you like, or leave all unselected for a mixed round.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {sections.map((section) => {
                const active = selected.includes(section.code);
                return (
                  <button
                    key={section.code}
                    type="button"
                    onClick={() => toggle(section.code)}
                    aria-pressed={active}
                    className={cn(
                      "press rounded-full border px-3.5 py-2 text-sm transition-colors",
                      active
                        ? "border-primary bg-primary/10 font-medium text-primary"
                        : "border-border bg-card hover:border-primary/40",
                    )}
                  >
                    {section.label}
                    <span className="ml-1.5 text-xs text-muted-foreground tabular">
                      {section.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>

          <section className="mt-6">
            <h2 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              How many stations
            </h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {lengths.map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCount(n)}
                  aria-pressed={count === n}
                  className={cn(
                    "press h-11 min-w-[4rem] rounded-xl border text-sm font-medium tabular transition-colors",
                    count === n
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border bg-card hover:border-primary/40",
                  )}
                >
                  {n}
                </button>
              ))}
            </div>
            {!entitlement.is_premium && (
              <p className="mt-2 text-xs text-muted-foreground">
                Free rounds are capped at {entitlement.max_stations} stations.{" "}
                <Link href="/premium" className="underline underline-offset-2">
                  Premium removes the cap.
                </Link>
              </p>
            )}
          </section>

          {error && (
            <p className="mt-4 rounded-xl border border-weakness/30 bg-weakness/10 px-3.5 py-2.5 text-sm text-weakness">
              {error}
            </p>
          )}

          <button
            type="button"
            onClick={() => void start()}
            disabled={starting}
            className="press mt-6 h-13 w-full rounded-full bg-primary py-3.5 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {starting ? "Starting…" : `Start ${Math.min(count, maxCount)}-station round`}
          </button>
        </>
      )}
    </div>
  );
}
