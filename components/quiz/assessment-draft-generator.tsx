"use client";

import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";

export type DraftGeneration = {
  id: number; status: string; base_revision: number; generated: number; target: number;
  error_code: string; next_attempt_at?: string | null;
  questions: { question_text: string; source_title: string; source_page: number; source_quote: string;
    question_type: string; option_a?: string; option_b?: string; option_c?: string; option_d?: string;
    correct_option?: string; explanation?: string; ideal_answer?: string; maximum_marks: number;
    marking_rubric?: { criterion: string; marks: number }[] }[];
};

type Props = {
  paperId?: string; generation?: DraftGeneration | null; busy: boolean; dirty: boolean;
  onGeneration: (value: DraftGeneration | null) => void;
  onAction: (operation: string, options?: Record<string, unknown>) => Promise<void>;
};

export function AssessmentDraftGenerator({ paperId, generation, busy, dirty, onGeneration, onAction }: Props) {
  const [sources, setSources] = useState<{ id: string; title: string }[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [difficulty, setDifficulty] = useState("medium");
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(true);
  const working = !!generation && ["pending", "running", "retry_wait"].includes(generation.status);
  const outstanding = !!generation && ["pending", "running", "retry_wait", "failed", "completed"].includes(generation.status);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const load = async () => {
      const items: { id: string; title: string }[] = [];
      const visited = new Set<string>();
      let next: string | null = "/api/slides/";
      while (next) {
        if (visited.has(next)) throw new Error("Repeated source page");
        visited.add(next);
        const response: { data: any } = await api.get(next);
        items.push(...(Array.isArray(response.data) ? response.data : response.data.results || []));
        next = Array.isArray(response.data) ? null : response.data.next;
        if (cancelled) return;
      }
      setSources(items); setError("");
    };
    load().catch(() => { if (!cancelled) setError("Could not load class documents. Retry loading sources."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [reload]);

  useEffect(() => {
    if (!paperId || !working) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const { data } = await api.get(`/api/formal-assessments/${paperId}/generation/`);
        if (!cancelled) { onGeneration(data); setError(""); }
      } catch { if (!cancelled) setError("Progress could not be refreshed. Your saved generation can be resumed after reloading."); }
      if (!cancelled) timer = setTimeout(poll, 5000);
    };
    timer = setTimeout(poll, 1500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [paperId, working, onGeneration]);

  return <section aria-label="AI question suggestions" className="space-y-3 rounded-lg border p-4">
    <h3 className="font-medium">Generate private question suggestions</h3>
    <p className="text-sm text-muted-foreground">AI fills the missing question slots from extracted class documents.
      Your manual questions stay in place. Check every answer and source quotation before adding suggestions.</p>
    {!outstanding && <fieldset disabled={busy || loading} className="space-y-3">
      <p className="text-sm">Choose up to 10 documents, no more than the missing question count. Each selected document will be used.</p>
      <div className="max-h-48 space-y-2 overflow-auto">
        {sources.map(source => <label key={source.id} className="flex gap-2 text-sm">
          <input type="checkbox" checked={selected.includes(source.id)}
            disabled={!selected.includes(source.id) && selected.length >= 10}
            onChange={e => setSelected(old => e.target.checked ? [...old, source.id] : old.filter(id => id !== source.id))} />
          {source.title}
        </label>)}
        {loading ? <p>Loading class documents…</p> : !sources.length && <p>No class documents are available.</p>}
      </div>
      <label className="block text-sm">Suggested question difficulty
        <select className="ml-2 rounded border bg-background p-2" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
          {["easy", "medium", "hard"].map(value => <option key={value}>{value}</option>)}
        </select>
      </label>
      <Button variant="outline" disabled={!selected.length || busy || loading}
        onClick={() => onAction("generate", { source_ids: selected, difficulty })}>Save draft and generate suggestions</Button>
    </fieldset>}
    {error && <p role="alert">{error}</p>}
    {!outstanding && <Button variant="ghost" disabled={busy || loading} onClick={() => setReload(n => n + 1)}>Reload sources</Button>}
    {generation && <>
      <p role="status">{generation.generated} of {generation.target} suggestions saved · {generation.status.replace("_", " ")}</p>
      {working && <p className="text-sm">Generation continues if you leave this page. Return to this saved draft to review it.</p>}
      {generation.status === "retry_wait" && <p className="text-sm">The last question could not be generated. A retry is scheduled; saved suggestions are kept.</p>}
      {generation.status === "failed" && <p className="text-sm">Generation needs a retry. Saved suggestions are kept. Retry is available after the five-minute cooldown.</p>}
      {generation.status === "cancelled" && <p className="text-sm">These suggestions were discarded or the saved draft changed. Generate again from the current draft.</p>}
      {dirty && outstanding && <p className="text-sm">You have unsaved edits. Saving them cancels these suggestions; adding suggestions is disabled to protect your edits.</p>}
      {outstanding && <div className="flex flex-wrap gap-2">
        {generation.status === "completed" && <Button disabled={busy || dirty} onClick={() => onAction("apply")}>Add reviewed suggestions to draft</Button>}
        {generation.status === "failed" && <Button disabled={busy || dirty} variant="outline" onClick={() => onAction("retry")}>Retry generation</Button>}
        <Button disabled={busy} variant="outline" onClick={() => onAction("discard")}>Discard suggestions</Button>
      </div>}
      {generation.questions.map((q, index) => <details key={index} className="rounded border p-3">
        <summary className="cursor-pointer text-sm">Suggestion {index + 1}: {q.question_text}</summary>
        <div className="mt-3 space-y-2 text-sm">
          {q.question_type === "mcq" ? <>
            {(["a", "b", "c", "d"] as const).map(option => <p key={option}>{option.toUpperCase()}. {q[`option_${option}`]}</p>)}
            <p>Correct answer: {q.correct_option}</p><p>{q.explanation}</p>
          </> : <><p>Model answer: {q.ideal_answer}</p><p>Maximum marks: {q.maximum_marks}</p>
            {q.marking_rubric?.map((r, i) => <p key={i}>{r.criterion}: {r.marks} marks</p>)}</>}
          <p>Source: {q.source_title}, page {q.source_page}</p>
          <blockquote className="border-l-2 pl-3">{q.source_quote}</blockquote>
        </div>
      </details>)}
    </>}
  </section>;
}
