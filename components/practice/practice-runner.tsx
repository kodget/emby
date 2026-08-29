"use client";

/**
 * The image-spot practice runner, shared by Steeplechase and Histology.
 *
 * One station at a time, thirty seconds each. The timer is authoritative about *moving
 * on*, not about grading: when it expires whatever the student has typed is submitted
 * and the station is marked timed out, so a slow answer still counts for what it got.
 *
 * Timer notes that matter:
 *   - it is keyed to the station index and fully torn down between stations, which is
 *     what stops the previous station's interval bleeding into the next one,
 *   - it counts against a wall-clock deadline rather than decrementing a counter, so a
 *     backgrounded tab cannot drift,
 *   - it pauses while the reveal is on screen; reading feedback is not part of the 30s.
 */

import Image from "next/image";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, X } from "lucide-react";

import { Axo, AxoLoader } from "@/components/brand/axo";
import { practiceApi, type PracticeMode, type PracticeReveal, type PracticeStation } from "@/lib/api";
import { cn } from "@/lib/utils";

type Props = {
  mode: PracticeMode;
  sessionId: string;
  firstStation: PracticeStation;
  totalStations: number;
  secondsPerStation: number;
  onFinished: (sessionId: string) => void;
};

export function PracticeRunner({
  mode,
  sessionId,
  firstStation,
  totalStations,
  secondsPerStation,
  onFinished,
}: Props) {
  const [station, setStation] = useState<PracticeStation>(firstStation);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [finishing, setFinishing] = useState(false);

  const [mainAnswer, setMainAnswer] = useState("");
  const [supporting, setSupporting] = useState<number | null>(null);
  const [trueFalse, setTrueFalse] = useState<boolean | null>(null);

  const [reveal, setReveal] = useState<PracticeReveal | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(secondsPerStation);

  const startedAt = useRef<number>(Date.now());
  const submitting = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const isLast = index >= totalStations - 1;

  /** Submit the current station. Guarded so the timer and the button cannot double-fire. */
  const submit = useCallback(
    async (timedOut: boolean) => {
      if (submitting.current || reveal) return;
      submitting.current = true;

      const elapsed = Math.round((Date.now() - startedAt.current) / 1000);
      try {
        const result = await practiceApi.answer(sessionId, {
          station_id: station.id,
          main_answer: mainAnswer,
          supporting_choice: supporting,
          true_false_answer: trueFalse,
          seconds_taken: Math.min(elapsed, secondsPerStation),
          timed_out: timedOut,
        });
        setReveal(result);
      } catch {
        // A failed submit must not strand the student mid-round; show a neutral reveal
        // so they can continue, and let the server-side record stand as-is.
        setReveal({
          station_id: station.id,
          main: { correct: false, answer: null, explanation: "" },
          supporting: null,
          true_false: null,
          structure: "",
          timed_out: timedOut,
        });
      } finally {
        submitting.current = false;
      }
    },
    [mainAnswer, reveal, secondsPerStation, sessionId, station.id, supporting, trueFalse],
  );

  // Per-station countdown against a fixed deadline.
  useEffect(() => {
    if (reveal) return; // paused while feedback is shown

    const deadline = Date.now() + secondsPerStation * 1000;
    startedAt.current = Date.now();
    setSecondsLeft(secondsPerStation);

    const id = setInterval(() => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left <= 0) {
        clearInterval(id);
        void submit(true);
      }
    }, 250);

    return () => clearInterval(id);
    // `index` is the key: a new station always restarts a clean timer.
  }, [index, reveal, secondsPerStation, submit]);

  useEffect(() => {
    if (!reveal) inputRef.current?.focus();
  }, [index, reveal]);

  const next = useCallback(async () => {
    if (isLast) {
      setFinishing(true);
      try {
        await practiceApi.complete(sessionId);
      } finally {
        onFinished(sessionId);
      }
      return;
    }

    setLoading(true);
    try {
      const nextStation = await practiceApi.getStation(sessionId, index + 1);
      setStation(nextStation);
      setIndex((i) => i + 1);
      setMainAnswer("");
      setSupporting(null);
      setTrueFalse(null);
      setReveal(null);
    } finally {
      setLoading(false);
    }
  }, [index, isLast, onFinished, sessionId]);

  const urgent = secondsLeft <= 8 && !reveal;
  const progress = ((index + (reveal ? 1 : 0)) / totalStations) * 100;

  if (finishing) {
    return <AxoLoader label="Scoring your round…" pose="clipboard" size="lg" />;
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-8">
      {/* Progress + timer */}
      <div className="sticky top-0 z-10 -mx-4 mb-4 bg-background/85 px-4 pb-3 pt-4 backdrop-blur-xl">
        <div className="flex items-center justify-between gap-3 text-sm">
          <span className="font-medium tabular">
            Station {index + 1}
            <span className="text-muted-foreground"> / {totalStations}</span>
          </span>

          <span
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-sm font-semibold tabular transition-colors",
              reveal
                ? "bg-secondary text-muted-foreground"
                : urgent
                  ? "bg-weakness/15 text-weakness"
                  : "bg-primary/10 text-primary",
            )}
            aria-live={urgent ? "assertive" : "off"}
          >
            {reveal ? "Paused" : `0:${String(secondsLeft).padStart(2, "0")}`}
          </span>
        </div>

        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-secondary">
          <motion.div
            className="h-full rounded-full bg-primary"
            animate={{ width: `${progress}%` }}
            transition={{ type: "spring", stiffness: 200, damping: 30 }}
          />
        </div>

        {/* The per-station drain, separate from overall progress. */}
        {!reveal && (
          <div className="mt-1 h-1 overflow-hidden rounded-full bg-secondary/60">
            <div
              className={cn(
                "h-full rounded-full transition-[width] duration-300 ease-linear",
                urgent ? "bg-weakness" : "bg-review",
              )}
              style={{ width: `${(secondsLeft / secondsPerStation) * 100}%` }}
            />
          </div>
        )}
      </div>

      {loading ? (
        <AxoLoader label="Loading the next station…" pose="magnifier" />
      ) : (
        <>
          {/* The specimen */}
          <figure className="relative overflow-hidden rounded-2xl border border-border bg-black/5 depth-2">
            <Image
              src={station.image_url}
              alt="Anatomy station specimen"
              width={1400}
              height={900}
              priority
              className="h-auto max-h-[52vh] w-full object-contain"
            />
            {station.marker.present && station.marker.x !== null && station.marker.y !== null && (
              <span
                aria-hidden="true"
                className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${station.marker.x * 100}%`, top: `${station.marker.y * 100}%` }}
              >
                <span className="block size-6 animate-ping rounded-full bg-coral/40" />
                <span className="absolute inset-0 m-auto block size-3 rounded-full border-2 border-white bg-[#FF7E9D] shadow-lg" />
              </span>
            )}
            <figcaption className="absolute left-3 top-3 rounded-full bg-background/85 px-2.5 py-1 text-[11px] font-medium backdrop-blur">
              {station.section.replaceAll("_", " ").toLowerCase()}
            </figcaption>
          </figure>

          {/* Questions */}
          <div className="mt-4 space-y-4">
            <div className="card-3d p-4">
              <label htmlFor="main-answer" className="block font-display text-base font-semibold">
                {station.main.question}
              </label>
              <input
                id="main-answer"
                ref={inputRef}
                value={mainAnswer}
                onChange={(e) => setMainAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !reveal) void submit(false);
                }}
                disabled={!!reveal}
                placeholder="Type your answer…"
                autoComplete="off"
                className="mt-3 h-12 w-full rounded-xl border border-input bg-background px-4 text-base outline-none transition-colors focus:border-primary disabled:opacity-70"
              />
              {reveal && (
                <Feedback
                  correct={reveal.main.correct}
                  answer={reveal.main.answer}
                  explanation={reveal.main.explanation}
                />
              )}
            </div>

            {station.supporting && (
              <div className="card-3d p-4">
                <p className="font-display text-base font-semibold">{station.supporting.question}</p>
                <div className="mt-3 grid gap-2">
                  {station.supporting.options.map((option, i) => {
                    const chosen = supporting === i;
                    const isAnswer = reveal?.supporting?.correct_index === i;
                    return (
                      <button
                        key={i}
                        type="button"
                        disabled={!!reveal}
                        onClick={() => setSupporting(i)}
                        className={cn(
                          "press flex items-start gap-3 rounded-xl border px-3.5 py-3 text-left text-sm transition-colors",
                          reveal && isAnswer
                            ? "border-mastery bg-mastery/10"
                            : reveal && chosen
                              ? "border-weakness bg-weakness/10"
                              : chosen
                                ? "border-primary bg-primary/10"
                                : "border-border bg-card hover:border-primary/40",
                        )}
                      >
                        <span className="mt-0.5 font-mono text-xs text-muted-foreground">
                          {String.fromCharCode(65 + i)}
                        </span>
                        <span>{option}</span>
                      </button>
                    );
                  })}
                </div>
                {reveal?.supporting && (
                  <Feedback
                    correct={!!reveal.supporting.correct}
                    explanation={reveal.supporting.explanation}
                  />
                )}
              </div>
            )}

            {station.true_false && (
              <div className="card-3d p-4">
                <p className="font-display text-base font-semibold">
                  {station.true_false.statement}
                </p>
                <div className="mt-3 flex gap-2">
                  {[true, false].map((value) => (
                    <button
                      key={String(value)}
                      type="button"
                      disabled={!!reveal}
                      onClick={() => setTrueFalse(value)}
                      className={cn(
                        "press flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors",
                        reveal && reveal.true_false?.answer === value
                          ? "border-mastery bg-mastery/10"
                          : trueFalse === value
                            ? "border-primary bg-primary/10"
                            : "border-border bg-card hover:border-primary/40",
                      )}
                    >
                      {value ? "True" : "False"}
                    </button>
                  ))}
                </div>
                {reveal?.true_false && (
                  <Feedback
                    correct={!!reveal.true_false.correct}
                    explanation={reveal.true_false.explanation}
                  />
                )}
              </div>
            )}
          </div>

          {/* Action */}
          <div className="mt-5 flex items-center gap-3">
            {!reveal ? (
              <button
                type="button"
                onClick={() => void submit(false)}
                className="press h-12 flex-1 rounded-full bg-primary text-sm font-semibold text-primary-foreground"
              >
                Submit answer
              </button>
            ) : (
              <>
                <Axo
                  pose={reveal.main.correct ? "celebrate" : "heart"}
                  size="sm"
                  className="hidden sm:block"
                />
                <button
                  type="button"
                  onClick={() => void next()}
                  autoFocus
                  className="press h-12 flex-1 rounded-full bg-primary text-sm font-semibold text-primary-foreground"
                >
                  {isLast ? "Finish round" : "Next station"}
                </button>
              </>
            )}
          </div>

          {reveal?.timed_out && (
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Time ran out — whatever you had typed was submitted.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Feedback({
  correct,
  answer,
  explanation,
}: {
  correct: boolean;
  answer?: string | null;
  explanation?: string;
}) {
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: "auto" }}
        className="mt-3 overflow-hidden"
      >
        <div
          className={cn(
            "rounded-xl border px-3.5 py-3 text-sm",
            correct ? "border-mastery/30 bg-mastery/10" : "border-weakness/30 bg-weakness/10",
          )}
        >
          <p className="flex items-center gap-2 font-medium">
            {correct ? (
              <Check className="size-4 text-mastery" />
            ) : (
              <X className="size-4 text-weakness" />
            )}
            {correct ? "Correct" : "Not quite"}
            {!correct && answer && (
              <span className="font-normal text-muted-foreground">— it was {answer}</span>
            )}
          </p>
          {explanation && (
            <p className="mt-1.5 text-pretty text-[13px] leading-relaxed text-muted-foreground">
              {explanation}
            </p>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
