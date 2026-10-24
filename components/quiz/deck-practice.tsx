"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api, { quizApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function DeckPractice({ initialSlide = "", missed = false, session = false, onBack }: {
  initialSlide?: string; missed?: boolean; session?: boolean; onBack: () => void;
}) {
  const router = useRouter();
  const [slides, setSlides] = useState<{ id: string; title: string }[]>([]);
  const [slide, setSlide] = useState(initialSlide);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium");
  const [count, setCount] = useState(5);
  const [timed, setTimed] = useState(false);
  const [duration, setDuration] = useState(10);
  const [options, setOptions] = useState<{ slide: string; title: string; available: Record<string, number> } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const source = missed ? "missed_questions" : "hierarchy";

  useEffect(() => {
    const controller = new AbortController();
    api.get("/api/slides/", { signal: controller.signal }).then(({ data }) => {
      if (!controller.signal.aborted) setSlides(Array.isArray(data) ? data : data.results ?? []);
    }).catch(() => { if (!controller.signal.aborted) setError("Could not load decks. Please retry."); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    const controller = new AbortController();
    setOptions(null); setError("");
    if (slide) api.get("/api/quiz-attempts/practice-options/", {
      params: { slide, question_source: source }, signal: controller.signal,
    }).then(({ data }) => { if (!controller.signal.aborted) setOptions(data); })
      .catch(() => { if (!controller.signal.aborted) setError("Could not check this deck’s saved questions. Please retry."); });
    return () => controller.abort();
  }, [slide, source, revision]);

  const available = options?.slide === slide ? options.available[difficulty] ?? 0 : null;
  const valid = Number.isInteger(count) && count >= 1 && count <= 20 && available !== null && count <= available
    && (!timed || (Number.isInteger(duration) && duration >= 1 && duration <= 180));
  async function start() {
    if (!valid || busy) return;
    setBusy(true); setError("");
    try {
      const result = await quizApi.createQuizAttempt({ slide, exam_type: "practice", is_timed: timed,
        ...(timed ? { duration_minutes: duration } : {}),
        configuration: { mcq_count: count, theory_count: 0, difficulty, question_source: source } });
      router.push(`/quiz/attempt/${result.id}${session ? "?session=true&nextStep=4" : ""}`);
    } catch (err: any) {
      const data = err.response?.data;
      setError(data?.error || "Could not start practice. Please retry.");
      if (data?.code === "insufficient_questions") setOptions(current => current && ({ ...current,
        available: { ...current.available, [difficulty]: Number(data.available) } }));
      setBusy(false);
    }
  }

  return <main className="mx-auto max-w-xl space-y-5 px-4 py-8">
    <Button variant="ghost" onClick={onBack} disabled={busy}>Back to practice</Button>
    <h1 className="text-2xl font-semibold">{missed ? "Review mistakes from one deck" : "Practise one deck"}</h1>
    <p>Choose up to 20 saved MCQs at one difficulty. Your score and correct answers appear after submission.</p>
    <fieldset disabled={busy} className="space-y-4">
      <label className="block">Deck<select aria-label="Deck" className="mt-1 block w-full rounded border bg-background p-2" value={slide}
        onChange={e => setSlide(e.target.value)}><option value="">Choose a deck</option>
        {slide && !slides.some(s => s.id === slide) && <option value={slide}>{options?.title ?? "Selected deck"}</option>}
        {slides.map(s => <option key={s.id} value={s.id}>{s.title}</option>)}
      </select></label>
      <label className="block">Difficulty<select aria-label="Difficulty" className="mt-1 block w-full rounded border bg-background p-2" value={difficulty}
        onChange={e => setDifficulty(e.target.value as typeof difficulty)}>
        <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
      </select></label>
      <p role="status">{available === null ? (slide ? "Checking available questions…" : "Select a deck to see available questions.")
        : `${available} ${difficulty} question${available === 1 ? "" : "s"} available in this deck.`}</p>
      <label className="block">Number of questions<input aria-label="Number of questions" className="ml-3 w-20 rounded border bg-background p-2"
        type="number" min={1} max={20} value={count} onChange={e => setCount(Number(e.target.value))} /></label>
      {available !== null && count > available && <div role="alert">
        {available ? <>Choose fewer questions. <button className="underline" onClick={() => setCount(Math.min(20, available))}>Use {Math.min(20, available)} available questions</button></>
          : "No saved questions match yet. The uploader or class head can prepare the bank from the deck reader."}
      </div>}
      <label className="flex gap-2"><input type="checkbox" checked={timed} onChange={e => setTimed(e.target.checked)} />Timed practice</label>
      {timed && <label className="block">Minutes<input aria-label="Minutes" className="ml-3 w-20 rounded border bg-background p-2" type="number"
        min={1} max={180} value={duration} onChange={e => setDuration(Number(e.target.value))} /></label>}
    </fieldset>
    {error && <p role="alert">{error} <button className="underline" disabled={busy} onClick={() => setRevision(v => v + 1)}>Retry</button></p>}
    <Button disabled={!valid || busy} onClick={start}>{busy ? "Starting practice…" : "Start practice"}</Button>
  </main>;
}
